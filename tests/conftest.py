import numpy as np
import pandas as pd
import pytest

from electrolinera import config as C


def _datos_sinteticos(dias=30, seed=0):
    """CSV con la misma estructura que el original y parámetros conocidos."""
    rng = np.random.default_rng(seed)
    lam = {"Valle (Noche)": 10, "Llano (Mañana)": 44, "Punta (Mediodía)": 118,
           "Llano (Tarde)": 50, "Punta (Retorno)": 110, "Valle (Cierre)": 20}
    p = [0.15, 0.35, 0.40, 0.10]
    filas = []
    for d in range(1, dias + 1):
        for h in range(24):
            f = C.FRANJA_DE_HORA[h]
            n = rng.poisson(lam[f])
            tipos = rng.choice(list(C.TIPOS), size=n, p=p)
            for t in tipos:
                if t == "1. AC/PHEV":
                    e, pot = max(rng.gamma(3, 4), 1.0), 11.0
                elif t == "2. DC Estándar":
                    e, pot = rng.normal(25, 5), 50.0
                elif t == "3. HPC 150":
                    e, pot = rng.normal(50, 10), rng.uniform(80, 130)
                else:
                    e, pot = rng.uniform(50, 90), rng.normal(200, 20)
                filas.append((d, h, f, t, round(e, 2), round(pot, 2)))
    return pd.DataFrame(filas, columns=["Día", "Hora", "Tipo_Franja", "Tipo_Vehículo",
                                        "Energía_kWh", "Potencia_kW"])


@pytest.fixture(scope="session")
def csv_sintetico(tmp_path_factory):
    path = tmp_path_factory.mktemp("datos") / "datos.csv"
    _datos_sinteticos().to_csv(path, index=False)
    return path


@pytest.fixture(scope="session")
def modelos(csv_sintetico):
    from electrolinera.ajuste import ajustar, cargar_datos
    return ajustar(cargar_datos(csv_sintetico, url="no-usar"))
