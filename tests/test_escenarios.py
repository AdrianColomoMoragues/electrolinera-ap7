import numpy as np
import pytest

from electrolinera import config as C
from electrolinera import escenarios as E
from electrolinera import simulacion as S


def test_cambiar_cuota_reparte_proporcionalmente():
    base = {"AC/PHEV": 0.15, "DC Estándar": 0.35, "HPC 150": 0.40, "HPC 350": 0.10}
    nueva = E.cambiar_cuota(base, "AC/PHEV", 0.075)
    assert sum(nueva.values()) == pytest.approx(1)
    assert nueva["AC/PHEV"] == 0.075
    # las demás mantienen sus proporciones relativas
    assert nueva["HPC 150"] / nueva["DC Estándar"] == pytest.approx(0.40 / 0.35)
    with pytest.raises(ValueError):
        E.cambiar_cuota(base, "HPC 350", 1.5)


def test_predefinidos_son_validos(modelos):
    esc = E.predefinidos(modelos)
    assert "Situación actual" in esc and len(esc) == 6
    for d in esc.values():
        if "cuotas" in d["cambios"]:
            assert sum(d["cambios"]["cuotas"].values()) == pytest.approx(1)


def test_comparar(modelos):
    t = E.comparar(modelos, S.Escenario(dias=10), n_sims=20, seed=1)
    fila = t.set_index("escenario")
    assert fila.loc["Situación actual", "bn_vs_actual"] == 0
    # más demanda -> más beneficio bruto; energía más cara -> menos
    assert fila.loc["Demanda +25 %", "bb_media"] > fila.loc["Situación actual", "bb_media"]
    assert fila.loc["Energía +10 %", "bb_media"] < fila.loc["Situación actual", "bb_media"]
    # el coste de la energía no cambia los cortes (mismos números aleatorios)
    assert fila.loc["Energía +10 %", "cortes_sin_bateria"] == fila.loc["Situación actual", "cortes_sin_bateria"]
    # con la batería óptima nunca se gana menos que sin batería
    assert (t["bn_con_optima"] >= t["bn_sin_bateria"] - 1e-6).all()


def test_rejilla_cubre_el_pico(modelos):
    sim = S.simular(modelos, S.Escenario(dias=5, factor_demanda=1.6), n_sims=10, seed=2)
    rejilla = E.rejilla_baterias(sim)
    assert rejilla[0] == 0 and rejilla[-1] >= sim.pit.max(axis=1).mean() - sim.escenario.limite_kw


def test_regla_p99_nunca_supera_a_la_optima(modelos):
    sim = S.simular(modelos, S.Escenario(dias=10, cuotas=E.cambiar_cuota(
        dict(zip(C.NOMBRES, modelos["mezcla"]["p"])), "HPC 350", 0.2)), n_sims=30, seed=3)
    r = E.regla_p99_vs_optima(sim)
    assert r["bn_optima"] >= r["bn_regla"] - 1e-6
    assert r["ganancia_optima_vs_regla"] >= -1e-6
    assert np.isclose(r["regla_kw"], S.bateria_por_p99(sim))
