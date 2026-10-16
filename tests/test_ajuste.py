import json

import numpy as np
from scipy import stats

from electrolinera import ajuste
from electrolinera import config as C


def test_llegadas_recupera_lambda(modelos):
    ll = modelos["llegadas"]
    assert abs(ll["Punta (Mediodía)"]["lambda"] - 118) < 3
    assert abs(ll["Valle (Noche)"]["lambda"] - 10) < 1
    for m in ll.values():
        if m["n_obs"] >= 90:                           # con 30 datos el índice es muy ruidoso
            assert 0.7 < m["dispersion"] < 1.3        # Poisson: varianza ≈ media
    assert sum(len(m["horas"]) for m in ll.values()) == 24


def test_mezcla(modelos):
    p = modelos["mezcla"]["p"]
    assert abs(sum(p) - 1) < 1e-9
    assert np.allclose(p, [0.15, 0.35, 0.40, 0.10], atol=0.015)
    assert modelos["mezcla"]["p_homogeneidad_franjas"] > 0.01   # la mezcla no depende de la franja


def test_elige_la_distribucion_correcta(modelos):
    ac = modelos["potencia"]["AC/PHEV"]
    assert ac["dist"] == "constante" and ac["valor"] == 11.0
    assert modelos["potencia"]["HPC 150"]["dist"] == "uniform"
    assert modelos["potencia"]["HPC 350"]["dist"] == "norm"
    assert modelos["energia"]["DC Estándar"]["dist"] == "norm"
    assert modelos["energia"]["HPC 350"]["dist"] == "uniform"
    mu, sigma = modelos["energia"]["HPC 150"]["params"]
    assert abs(mu - 50) < 1 and abs(sigma - 10) < 1


def test_mejor_distribucion_gamma():
    x = stats.gamma(3, scale=4).rvs(5000, random_state=1)
    r = ajuste.mejor_distribucion(x)
    assert r["dist"] == "gamma" and r["ks_p"] > 0.01
    assert set(r["candidatas"]) >= {"norm", "gamma", "lognorm"}


def test_chi2_poisson():
    rng = np.random.default_rng(0)
    assert ajuste._chi2_poisson(rng.poisson(40, 500), 40) > 0.01
    sobredisperso = rng.negative_binomial(5, 5 / 45, 500)        # media 40, varianza ~360
    assert ajuste._chi2_poisson(sobredisperso, sobredisperso.mean()) < 0.01


def test_guardar_y_cargar(modelos, tmp_path):
    p = ajuste.guardar(modelos, tmp_path / "m.json")
    assert ajuste.cargar_modelos(p) == json.loads(json.dumps(modelos))
    assert len(modelos["empirico"]["pit_dia_hora"]) == 30
    assert set(modelos["energia"]) == set(C.NOMBRES)
