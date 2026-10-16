"""Ajuste de los modelos estocásticos a partir de los datos históricos.

Uso:
    python -m electrolinera.ajuste            # descarga el CSV si falta, ajusta y
                                              # guarda modelos/modelos.json

La app solo necesita `modelos/modelos.json` (parámetros ajustados y resúmenes
agregados de los datos). El CSV original no se redistribuye: se descarga de la
fuente.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from urllib.request import urlretrieve

import numpy as np
import pandas as pd
from scipy import stats

from .config import CSV_PATH, DATA_URL, FRANJAS, MODELOS_PATH, NOMBRES, TIPOS

log = logging.getLogger("electrolinera.ajuste")

# Candidatas para energía y potencia. Las de soporte positivo se ajustan con loc=0.
CANDIDATAS = {
    "norm": {},
    "uniform": {},
    "lognorm": {"floc": 0},
    "gamma": {"floc": 0},
    "weibull_min": {"floc": 0},
    "expon": {"floc": 0},
}


def cargar_datos(path: Path = CSV_PATH, url: str = DATA_URL) -> pd.DataFrame:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        log.info("Descargando %s", url)
        urlretrieve(url, path)
    df = pd.read_csv(path)
    df["Tipo"] = df["Tipo_Vehículo"].map(TIPOS)
    if df["Tipo"].isna().any():
        desconocidos = df.loc[df["Tipo"].isna(), "Tipo_Vehículo"].unique()
        raise ValueError(f"Tipos de vehículo desconocidos: {desconocidos}")
    return df


def llegadas_por_hora(df: pd.DataFrame) -> pd.DataFrame:
    """Número de vehículos por día y hora (incluye horas sin llegadas)."""
    dias = range(int(df["Día"].min()), int(df["Día"].max()) + 1)
    idx = pd.MultiIndex.from_product([dias, range(24)], names=["Día", "Hora"])
    n = df.groupby(["Día", "Hora"]).size().reindex(idx, fill_value=0).rename("n").reset_index()
    franja = {h: f for f, hs in FRANJAS.items() for h in hs}
    n["Franja"] = n["Hora"].map(franja)
    return n


def _chi2_poisson(x: np.ndarray, lam: float) -> float:
    """p-valor de la prueba χ² de bondad de ajuste a una Poisson(λ).

    Las clases se agrupan para que todas tengan una frecuencia esperada >= 5.
    Grados de libertad: clases − 1 − 1 (por estimar λ).
    """
    x = np.asarray(x)
    lo, hi = int(stats.poisson.ppf(0.005, lam)), int(stats.poisson.ppf(0.995, lam))
    # Clases: (-inf, lo], lo+1, ..., hi-1, [hi, inf)
    observadas = [(x <= lo).sum()] + [(x == k).sum() for k in range(lo + 1, hi)] + [(x >= hi).sum()]
    probs = ([stats.poisson.cdf(lo, lam)] + [stats.poisson.pmf(k, lam) for k in range(lo + 1, hi)]
             + [stats.poisson.sf(hi - 1, lam)])
    esperadas = np.array(probs) * len(x)

    obs_agr, esp_agr = [], []
    acum_o = acum_e = 0.0
    for o, e in zip(observadas, esperadas):
        acum_o += o
        acum_e += e
        if acum_e >= 5:
            obs_agr.append(acum_o)
            esp_agr.append(acum_e)
            acum_o = acum_e = 0.0
    if acum_e > 0 and esp_agr:          # el resto se suma a la última clase
        obs_agr[-1] += acum_o
        esp_agr[-1] += acum_e
    if len(esp_agr) < 3:
        return float("nan")
    obs_agr, esp_agr = np.array(obs_agr), np.array(esp_agr)
    estadistico = ((obs_agr - esp_agr) ** 2 / esp_agr).sum()
    return float(stats.chi2.sf(estadistico, len(esp_agr) - 2))


def ajustar_llegadas(n: pd.DataFrame) -> dict:
    out = {}
    for franja, horas in FRANJAS.items():
        x = n.loc[n["Franja"] == franja, "n"].to_numpy()
        lam, var = float(x.mean()), float(x.var(ddof=1))
        t = (len(x) - 1) * var / lam
        p_disp = 2 * min(stats.chi2.cdf(t, len(x) - 1), stats.chi2.sf(t, len(x) - 1))
        dias = n.loc[n["Franja"] == franja, "Día"].to_numpy()
        tendencia = stats.linregress(dias, x)
        out[franja] = {
            "horas": horas, "lambda": lam, "varianza": var, "dispersion": var / lam,
            "p_dispersion": float(p_disp), "p_chi2_poisson": _chi2_poisson(x, lam),
            "n_obs": int(len(x)), "tendencia_por_dia": float(tendencia.slope),
            "p_tendencia": float(tendencia.pvalue),
            "frecuencias": {int(k): int(v) for k, v in pd.Series(x).value_counts().sort_index().items()},
        }
    return out


def ajustar_mezcla(df: pd.DataFrame) -> dict:
    p = df["Tipo"].value_counts(normalize=True).reindex(NOMBRES).fillna(0)
    tabla = pd.crosstab(df["Tipo_Franja"], df["Tipo"]).reindex(columns=NOMBRES, fill_value=0)
    homog = stats.chi2_contingency(tabla)
    return {
        "tipos": NOMBRES, "p": [float(v) for v in p],
        "p_homogeneidad_franjas": float(homog.pvalue),
        "por_franja": {f: (fila / fila.sum()).round(4).tolist() for f, fila in tabla.iterrows()},
        "n": int(len(df)),
    }


def mejor_distribucion(x: np.ndarray) -> dict:
    """Ajusta las candidatas por máxima verosimilitud y elige la de menor AIC.

    Si todos los valores son iguales, devuelve una constante.
    """
    x = np.asarray(x, float)
    if np.ptp(x) == 0:
        return {"dist": "constante", "valor": float(x[0]), "candidatas": {}}
    resultados = {}
    for nombre, fijos in CANDIDATAS.items():
        dist = getattr(stats, nombre)
        if fijos.get("floc") == 0 and x.min() <= 0:
            continue
        try:
            params = dist.fit(x, **fijos)
        except Exception:      # pragma: no cover - ajuste numérico fallido
            continue
        ll = float(np.sum(dist.logpdf(x, *params)))
        if not np.isfinite(ll):
            continue
        k = len(params) - len(fijos)
        ks = stats.kstest(x, lambda v, d=dist, p=params: d.cdf(v, *p))
        resultados[nombre] = {"params": [float(v) for v in params], "aic": 2 * k - 2 * ll,
                              "ks_stat": float(ks.statistic), "ks_p": float(ks.pvalue)}
    mejor = min(resultados, key=lambda d: resultados[d]["aic"])
    return {"dist": mejor, **resultados[mejor], "candidatas": resultados}


def _histograma(x: np.ndarray, bins: int = 40) -> dict:
    cuentas, bordes = np.histogram(x, bins=bins)
    return {"cuentas": cuentas.tolist(), "bordes": [float(b) for b in bordes]}


def ajustar(df: pd.DataFrame) -> dict:
    n = llegadas_por_hora(df)
    energia, potencia = {}, {}
    empirico = {"energia": {}, "potencia": {}}
    for tipo in NOMBRES:
        g = df[df["Tipo"] == tipo]
        energia[tipo] = mejor_distribucion(g["Energía_kWh"].to_numpy())
        potencia[tipo] = mejor_distribucion(g["Potencia_kW"].to_numpy())
        energia[tipo].update(minimo=float(g["Energía_kWh"].min()), maximo=float(g["Energía_kWh"].max()),
                             media=float(g["Energía_kWh"].mean()))
        potencia[tipo].update(minimo=float(g["Potencia_kW"].min()), maximo=float(g["Potencia_kW"].max()),
                              media=float(g["Potencia_kW"].mean()))
        empirico["energia"][tipo] = _histograma(g["Energía_kWh"].to_numpy())
        if g["Potencia_kW"].nunique() > 1:
            empirico["potencia"][tipo] = _histograma(g["Potencia_kW"].to_numpy())
    # PIT y beneficio bruto horarios observados (para validar el simulador)
    from .config import COSTE_ENERGIA, PVP
    df = df.assign(BB=df["Energía_kWh"] * (df["Tipo"].map(PVP) - COSTE_ENERGIA))
    hora = df.groupby(["Día", "Hora"]).agg(PIT=("Potencia_kW", "sum"), BB=("BB", "sum"),
                                           E=("Energía_kWh", "sum")).reset_index()
    empirico["pit_dia_hora"] = hora.pivot(index="Día", columns="Hora", values="PIT").round(1).values.tolist()
    empirico["resumen_mes"] = {
        "dias": int(df["Día"].nunique()), "vehiculos": int(len(df)),
        "energia_kwh": float(df["Energía_kWh"].sum()), "bb_eur": float(df["BB"].sum()),
        "pit_p99": float(np.percentile(hora["PIT"], 99)), "pit_max": float(hora["PIT"].max()),
        "horas_sobre_limite": int((hora["PIT"] > 11_500).sum()),
    }
    return {
        "fecha_ajuste": date.today().isoformat(), "fuente": DATA_URL,
        "llegadas": ajustar_llegadas(n), "mezcla": ajustar_mezcla(df),
        "energia": energia, "potencia": potencia, "empirico": empirico,
    }


def guardar(modelos: dict, path: Path = MODELOS_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(modelos, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def cargar_modelos(path: Path = MODELOS_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    modelos = ajustar(cargar_datos())
    for franja, m in modelos["llegadas"].items():
        log.info("Llegadas %-17s λ=%6.2f  dispersión=%.2f  p(χ² Poisson)=%.3f",
                 franja, m["lambda"], m["dispersion"], m["p_chi2_poisson"])
    for var in ("energia", "potencia"):
        for tipo, m in modelos[var].items():
            if m["dist"] == "constante":
                log.info("%-8s %-12s constante = %g", var, tipo, m["valor"])
            else:
                log.info("%-8s %-12s %-11s params=%s  KS p=%.3f", var, tipo, m["dist"],
                         [round(v, 3) for v in m["params"]], m["ks_p"])
    log.info("Guardado en %s", guardar(modelos))


if __name__ == "__main__":
    main()
