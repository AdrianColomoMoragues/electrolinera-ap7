"""Escenarios estratégicos predefinidos y comparación entre ellos."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from . import simulacion as S


def cuotas_base(modelos: dict) -> dict:
    return dict(zip(C.NOMBRES, modelos["mezcla"]["p"]))


def cambiar_cuota(cuotas: dict, tipo: str, nueva: float) -> dict:
    """Fija la cuota de `tipo` y reparte el resto en proporción a las demás."""
    if not 0 <= nueva <= 1:
        raise ValueError("La cuota debe estar entre 0 y 1")
    resto = 1 - cuotas[tipo]
    return {t: (nueva if t == tipo else cuotas[t] * (1 - nueva) / resto) for t in cuotas}


def predefinidos(modelos: dict) -> dict[str, dict]:
    """Nombre -> (descripción, cambios sobre el escenario base)."""
    base = cuotas_base(modelos)
    return {
        "Situación actual": {
            "descripcion": "Demanda, mezcla y precios de los datos históricos.", "cambios": {}},
        "Demanda +25 %": {
            "descripcion": "Campaña de marketing o crecimiento del tráfico: un 25 % más de llegadas.",
            "cambios": {"factor_demanda": 1.25}},
        "Fin de subsidios PHEV": {
            "descripcion": "Los híbridos enchufables pierden la etiqueta 0: su cuota cae a la mitad.",
            "cambios": {"cuotas": cambiar_cuota(base, "AC/PHEV", base["AC/PHEV"] / 2)}},
        "HPC 350 +10 pp": {
            "descripcion": "Más vehículos de 800 V: la cuota de HPC 350 sube 10 puntos.",
            "cambios": {"cuotas": cambiar_cuota(base, "HPC 350", base["HPC 350"] + 0.10)}},
        "Energía +10 %": {
            "descripcion": "El coste de la energía sube un 10 % y no se repercute al cliente.",
            "cambios": {"coste_energia": C.COSTE_ENERGIA * 1.10}},
        "Electrificación rápida": {
            "descripcion": "Demanda +25 % y HPC 350 +10 pp a la vez.",
            "cambios": {"factor_demanda": 1.25,
                        "cuotas": cambiar_cuota(base, "HPC 350", base["HPC 350"] + 0.10)}},
    }


def rejilla_baterias(sim: S.Simulacion, paso: int = 100, minimo: int = 4000) -> np.ndarray:
    """Tamaños a evaluar: hasta el mayor de `minimo` y 1,5 veces el pico medio sobre el límite."""
    exceso = float(np.mean(sim.pit.max(axis=1))) - sim.escenario.limite_kw
    tope = max(minimo, int(np.ceil(1.5 * max(exceso, 0) / paso) * paso))
    return np.arange(0, tope + 1, paso)


def comparar(modelos: dict, base: S.Escenario, n_sims: int = 200, seed: int = 123) -> pd.DataFrame:
    """Compara los escenarios predefinidos con números aleatorios comunes (misma semilla)."""
    filas = []
    for nombre, esc_def in predefinidos(modelos).items():
        esc = base.con(**esc_def["cambios"])
        sim = S.simular(modelos, esc, n_sims=n_sims, seed=seed)
        sin = S.evaluar(sim, bateria_kw=0)
        curva = S.curva_baterias(sim, rejilla_baterias(sim))
        opt = S.bateria_optima(curva)
        filas.append({
            "escenario": nombre, "descripcion": esc_def["descripcion"],
            "bb_media": sin["beneficio_bruto"].mean(),
            "bn_sin_bateria": sin["beneficio_neto"].mean(),
            "cortes_sin_bateria": sin["cortes"].mean(),
            "pit_p99": sin["pit_p99"].mean(),
            "bateria_optima_kw": opt["bateria_kw"],
            "bn_con_optima": opt["bn_media"],
            "mejora_bateria": opt["mejora_vs_sin_bateria"],
            "bateria_regla_p99_kw": S.bateria_por_p99(sim),
            "cortes_con_optima": opt["cortes_medios"],
        })
    out = pd.DataFrame(filas)
    out["bn_vs_actual"] = out["bn_con_optima"] - out.loc[0, "bn_con_optima"]
    return out


def regla_p99_vs_optima(sim: S.Simulacion, paso: int = 100, maximo: int = 4000) -> dict:
    """Compara la batería de la regla P99 con la óptima (redondeada al paso de la curva)."""
    regla = S.bateria_por_p99(sim)
    tamanos = np.union1d(rejilla_baterias(sim, paso, maximo), np.arange(0, regla + 2 * paso, paso))
    curva = S.curva_baterias(sim, tamanos)
    opt = S.bateria_optima(curva)
    regla_r = float(np.round(regla / paso) * paso)
    fila_regla = curva.set_index("bateria_kw").loc[regla_r]
    return {"regla_kw": regla, "regla_redondeada_kw": regla_r, "bn_regla": float(fila_regla["bn_media"]),
            "optima_kw": float(opt["bateria_kw"]), "bn_optima": float(opt["bn_media"]),
            "ganancia_optima_vs_regla": float(opt["bn_media"] - fila_regla["bn_media"]),
            "curva": curva}
