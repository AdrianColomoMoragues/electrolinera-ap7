"""Simulador Monte Carlo de la electrolinera (vectorizado con NumPy).

Modelo, para cada hora h de cada día:
    N_h            ~ Poisson(λ_franja(h) · factor_demanda)
    (N_1..N_4)_h   ~ Multinomial(N_h, cuotas)                 tipo de cargador
    E_i, P_i       ~ distribución ajustada a su tipo (independientes)
    PIT_h          = Σ P_i                                     potencia instantánea total
    BB_h           = Σ E_i · (PVP_tipo − coste_energía)        beneficio bruto

Cortes: hay corte en la hora h si PIT_h > límite + kW de batería. Cada corte
cuesta Triangular(1500, 2000, 3500) € y, por defecto, se pierde el beneficio
bruto de esa hora. La batería se alquila por kW y mes y se supone limitada solo
por potencia (energía suficiente para cubrir el pico de esa hora).

Beneficio neto = BB − BB perdido en cortes − costes de corte − alquiler batería.

Para comparar alternativas (p. ej. distintos tamaños de batería) se usan
**números aleatorios comunes**: se simulan las horas una sola vez y todas las
alternativas se evalúan sobre las mismas horas y los mismos costes de corte, de
modo que las diferencias se deben a la decisión y no al azar.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd
from scipy import stats

from . import config as C


@dataclass(frozen=True)
class Escenario:
    dias: int = C.DIAS_MES
    factor_demanda: float = 1.0
    cuotas: dict | None = None             # None = mezcla ajustada a los datos
    pvp: dict = field(default_factory=lambda: dict(C.PVP))
    coste_energia: float = C.COSTE_ENERGIA
    limite_kw: float = C.LIMITE_TRANSFORMADOR
    bateria_kw: float = 0.0
    coste_bateria_kw_mes: float = C.COSTE_BATERIA_KW_MES
    coste_corte: tuple = C.COSTE_CORTE
    pierde_ingresos_en_corte: bool = True

    def con(self, **cambios) -> "Escenario":
        return replace(self, **cambios)


@dataclass
class Simulacion:
    """Resultado horario de n simulaciones: matrices (n_sims, dias·24)."""
    pit: np.ndarray
    bb: np.ndarray
    energia: np.ndarray
    vehiculos: np.ndarray
    coste_corte_hora: np.ndarray         # coste que tendría un corte en cada hora (CRN)
    escenario: Escenario

    @property
    def horas(self) -> np.ndarray:
        return np.tile(np.arange(24), self.escenario.dias)


# --------------------------------------------------------------------------- #
# Muestreo de las distribuciones ajustadas
# --------------------------------------------------------------------------- #

def muestrear(spec: dict, n: int, rng: np.random.Generator) -> np.ndarray:
    if n == 0:
        return np.empty(0)
    if spec["dist"] == "constante":
        return np.full(n, spec["valor"], dtype=float)
    return getattr(stats, spec["dist"]).rvs(*spec["params"], size=n, random_state=rng)


def cuotas_vector(modelos: dict, cuotas: dict | None) -> np.ndarray:
    if cuotas is None:
        p = np.array(modelos["mezcla"]["p"], float)
    else:
        p = np.array([cuotas[t] for t in C.NOMBRES], float)
    if (p < 0).any() or p.sum() <= 0:
        raise ValueError("Las cuotas deben ser no negativas y sumar más de 0")
    return p / p.sum()


def lambdas_por_hora(modelos: dict) -> np.ndarray:
    lam = np.zeros(24)
    for franja, m in modelos["llegadas"].items():
        lam[m["horas"]] = m["lambda"]
    return lam


# --------------------------------------------------------------------------- #
# Simulación
# --------------------------------------------------------------------------- #

def simular(modelos: dict, esc: Escenario = Escenario(), n_sims: int = 200,
            seed: int | None = 123) -> Simulacion:
    rng = np.random.default_rng(seed)
    horas = esc.dias * 24
    lam = np.tile(lambdas_por_hora(modelos) * esc.factor_demanda, esc.dias)
    p = cuotas_vector(modelos, esc.cuotas)
    margen = np.array([esc.pvp[t] - esc.coste_energia for t in C.NOMBRES])

    pit = np.zeros((n_sims, horas))
    bb = np.zeros((n_sims, horas))
    ene = np.zeros((n_sims, horas))
    nveh = np.zeros((n_sims, horas), dtype=np.int64)
    idx_horas = np.arange(horas)
    for s in range(n_sims):
        n = rng.poisson(lam)
        nveh[s] = n
        por_tipo = rng.multinomial(n, p)                       # (horas, 4)
        for k, tipo in enumerate(C.NOMBRES):
            nk = por_tipo[:, k]
            total = int(nk.sum())
            if total == 0:
                continue
            h = np.repeat(idx_horas, nk)
            e = np.maximum(muestrear(modelos["energia"][tipo], total, rng), C.ENERGIA_MINIMA)
            pk = muestrear(modelos["potencia"][tipo], total, rng)
            pit[s] += np.bincount(h, weights=pk, minlength=horas)
            ene[s] += np.bincount(h, weights=e, minlength=horas)
            bb[s] += np.bincount(h, weights=e * margen[k], minlength=horas)
    a, m, b = esc.coste_corte
    coste_corte_hora = rng.triangular(a, m, b, size=(n_sims, horas))
    return Simulacion(pit, bb, ene, nveh, coste_corte_hora, esc)


# --------------------------------------------------------------------------- #
# Evaluación económica
# --------------------------------------------------------------------------- #

def evaluar(sim: Simulacion, bateria_kw: float | None = None, limite_kw: float | None = None,
            coste_bateria_kw_mes: float | None = None) -> pd.DataFrame:
    """Métricas por simulación (una fila por simulación)."""
    esc = sim.escenario
    bat = esc.bateria_kw if bateria_kw is None else bateria_kw
    lim = esc.limite_kw if limite_kw is None else limite_kw
    cbat = esc.coste_bateria_kw_mes if coste_bateria_kw_mes is None else coste_bateria_kw_mes
    corte = sim.pit > lim + bat
    bb_total = sim.bb.sum(axis=1)
    perdido = (sim.bb * corte).sum(axis=1) if esc.pierde_ingresos_en_corte else np.zeros(len(bb_total))
    cop = (sim.coste_corte_hora * corte).sum(axis=1)
    alquiler = bat * cbat * esc.dias / C.DIAS_MES
    return pd.DataFrame({
        "beneficio_bruto": bb_total,
        "ingresos_perdidos": perdido,
        "coste_cortes": cop,
        "alquiler_bateria": alquiler,
        "beneficio_neto": bb_total - perdido - cop - alquiler,
        "cortes": corte.sum(axis=1),
        "energia_kwh": sim.energia.sum(axis=1),
        "vehiculos": sim.vehiculos.sum(axis=1),
        "pit_p99": np.percentile(sim.pit, 99, axis=1),
        "pit_max": sim.pit.max(axis=1),
    })


def intervalo(x, nivel: float = 0.95) -> tuple[float, float, float]:
    """Media e intervalo de confianza de la media (aproximación normal)."""
    x = np.asarray(x, float)
    z = stats.norm.ppf(0.5 + nivel / 2)
    se = x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0
    return float(x.mean()), float(x.mean() - z * se), float(x.mean() + z * se)


def resumen(metricas: pd.DataFrame) -> pd.DataFrame:
    """Media, IC95 de la media y percentiles 5 y 95 de cada métrica."""
    filas = {}
    for col in metricas.columns:
        m, lo, hi = intervalo(metricas[col])
        filas[col] = {"media": m, "ic_inf": lo, "ic_sup": hi,
                      "p5": float(metricas[col].quantile(0.05)), "p95": float(metricas[col].quantile(0.95))}
    return pd.DataFrame(filas).T


def pit_p99_por_franja(sim: Simulacion) -> pd.DataFrame:
    """P99 de la PIT por franja: media entre simulaciones e IC95."""
    filas = []
    horas = sim.horas
    for franja, hs in C.FRANJAS.items():
        cols = np.isin(horas, hs)
        p99 = np.percentile(sim.pit[:, cols], 99, axis=1)
        m, lo, hi = intervalo(p99)
        filas.append({"franja": franja, "p99_media": m, "ic_inf": lo, "ic_sup": hi,
                      "prob_corte_hora": float((sim.pit[:, cols] > sim.escenario.limite_kw
                                                + sim.escenario.bateria_kw).mean())})
    return pd.DataFrame(filas)


def bateria_por_p99(sim: Simulacion, franja: str = "Punta (Mediodía)") -> float:
    """Regla del caso original: déficit del P99 de la PIT en la franja crítica."""
    t = pit_p99_por_franja(sim).set_index("franja")
    return max(0.0, float(t.loc[franja, "p99_media"]) - sim.escenario.limite_kw)


def curva_baterias(sim: Simulacion, tamanos_kw) -> pd.DataFrame:
    """Beneficio neto y riesgo para cada tamaño de batería (números aleatorios comunes)."""
    filas = []
    base = evaluar(sim, bateria_kw=0.0)["beneficio_neto"].to_numpy()
    for kw in tamanos_kw:
        m = evaluar(sim, bateria_kw=float(kw))
        bn = m["beneficio_neto"].to_numpy()
        media, lo, hi = intervalo(bn)
        dif_m, dif_lo, dif_hi = intervalo(bn - base)
        filas.append({
            "bateria_kw": float(kw), "bn_media": media, "bn_ic_inf": lo, "bn_ic_sup": hi,
            "bn_p5": float(np.percentile(bn, 5)),
            "mejora_vs_sin_bateria": dif_m, "mejora_ic_inf": dif_lo, "mejora_ic_sup": dif_hi,
            "cortes_medios": float(m["cortes"].mean()),
            "prob_algun_corte": float((m["cortes"] > 0).mean()),
            "alquiler": float(m["alquiler_bateria"].iloc[0]),
        })
    return pd.DataFrame(filas)


def bateria_optima(curva: pd.DataFrame) -> pd.Series:
    """Tamaño con mayor beneficio neto medio (a igualdad, el más pequeño)."""
    mejor = curva["bn_media"].max()
    return curva[curva["bn_media"] >= mejor - 1e-9].sort_values("bateria_kw").iloc[0]
