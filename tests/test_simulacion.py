import numpy as np
import pytest

from electrolinera import config as C
from electrolinera import simulacion as S


def test_reproducible_y_formas(modelos):
    a = S.simular(modelos, S.Escenario(dias=3), n_sims=5, seed=1)
    b = S.simular(modelos, S.Escenario(dias=3), n_sims=5, seed=1)
    assert a.pit.shape == (5, 72)
    np.testing.assert_array_equal(a.pit, b.pit)


def test_medias_coherentes_con_el_modelo(modelos):
    sim = S.simular(modelos, S.Escenario(dias=10), n_sims=50, seed=2)
    lam_dia = sum(m["lambda"] * len(m["horas"]) for m in modelos["llegadas"].values())
    assert abs(sim.vehiculos.sum(axis=1).mean() / 10 / lam_dia - 1) < 0.01
    # beneficio bruto esperado por vehículo
    p = np.array(modelos["mezcla"]["p"])
    e = np.array([modelos["energia"][t]["media"] for t in C.NOMBRES])
    margen = np.array([C.PVP[t] - C.COSTE_ENERGIA for t in C.NOMBRES])
    esperado = lam_dia * 10 * (p * e * margen).sum()
    assert abs(sim.bb.sum(axis=1).mean() / esperado - 1) < 0.01


def test_factor_demanda(modelos):
    def media(esc):
        return S.simular(modelos, esc, n_sims=30, seed=3).vehiculos.sum(1).mean()
    base, mas = media(S.Escenario(dias=5)), media(S.Escenario(dias=5, factor_demanda=1.25))
    assert abs(mas / base - 1.25) < 0.02


def test_cuotas_personalizadas(modelos):
    solo_ac = {t: (1.0 if t == "AC/PHEV" else 0.0) for t in C.NOMBRES}
    sim = S.simular(modelos, S.Escenario(dias=2, cuotas=solo_ac), n_sims=3, seed=4)
    # todos los vehículos cargan a 11 kW -> PIT = 11 · N
    np.testing.assert_allclose(sim.pit, 11.0 * sim.vehiculos)
    with pytest.raises(ValueError):
        S.cuotas_vector(modelos, {t: 0.0 for t in C.NOMBRES})


def test_contabilidad_del_beneficio_neto(modelos):
    sim = S.simular(modelos, S.Escenario(limite_kw=5_000), n_sims=20, seed=5)
    m = S.evaluar(sim, bateria_kw=300)
    np.testing.assert_allclose(
        m["beneficio_neto"],
        m["beneficio_bruto"] - m["ingresos_perdidos"] - m["coste_cortes"] - m["alquiler_bateria"])
    assert (m["alquiler_bateria"] == 300 * C.COSTE_BATERIA_KW_MES).all()
    # coste medio por corte ≈ media de la triangular (1500+2000+3500)/3
    assert abs(m["coste_cortes"].sum() / m["cortes"].sum() - 7000 / 3) < 60


def test_bateria_reduce_cortes_monotonamente(modelos):
    sim = S.simular(modelos, S.Escenario(limite_kw=11_000), n_sims=40, seed=6)
    curva = S.curva_baterias(sim, [0, 500, 1000, 2000])
    assert curva["cortes_medios"].is_monotonic_decreasing
    assert curva.loc[0, "mejora_vs_sin_bateria"] == 0


def test_bateria_optima_en_un_caso_conocido(modelos):
    """Con batería gratis, el óptimo es la más grande; muy cara, ninguna."""
    sim = S.simular(modelos, S.Escenario(limite_kw=11_000), n_sims=30, seed=8)
    tam = [0, 1000, 3000]
    gratis = S.curva_baterias(S.Simulacion(sim.pit, sim.bb, sim.energia, sim.vehiculos,
                                           sim.coste_corte_hora,
                                           sim.escenario.con(coste_bateria_kw_mes=0)), tam)
    assert S.bateria_optima(gratis)["bateria_kw"] == 3000
    cara = S.curva_baterias(S.Simulacion(sim.pit, sim.bb, sim.energia, sim.vehiculos,
                                         sim.coste_corte_hora,
                                         sim.escenario.con(coste_bateria_kw_mes=10_000)), tam)
    assert S.bateria_optima(cara)["bateria_kw"] == 0


def test_pit_p99_por_franja_y_regla(modelos):
    sim = S.simular(modelos, S.Escenario(), n_sims=20, seed=9)
    t = S.pit_p99_por_franja(sim).set_index("franja")
    assert t.loc["Punta (Mediodía)", "p99_media"] > t.loc["Llano (Tarde)", "p99_media"]
    assert S.bateria_por_p99(sim) == pytest.approx(max(0, t.loc["Punta (Mediodía)", "p99_media"] - 11_500))
