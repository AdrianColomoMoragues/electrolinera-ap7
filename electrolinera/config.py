"""Parámetros del caso: franjas, tipos de cargador, tarifas e infraestructura."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CSV_PATH = DATA_DIR / "datos_electrolinera_raw.csv"
MODELOS_PATH = ROOT / "modelos" / "modelos.json"

# Datos del caso práctico (30 días de registros de una electrolinera en la AP-7).
DATA_URL = ("https://raw.githubusercontent.com/UMH1477/python/refs/heads/main/"
            "data/datos_electrolinera_raw.csv")

# Franjas horarias -> horas que incluyen
FRANJAS = {
    "Valle (Noche)": list(range(0, 7)),
    "Llano (Mañana)": list(range(7, 11)),
    "Punta (Mediodía)": list(range(11, 15)),
    "Llano (Tarde)": list(range(15, 18)),
    "Punta (Retorno)": list(range(18, 23)),
    "Valle (Cierre)": [23],
}
FRANJA_DE_HORA = {h: f for f, horas in FRANJAS.items() for h in horas}

# Tipos de cargador (nombre en el CSV -> nombre corto) y precio de venta (€/kWh)
TIPOS = {
    "1. AC/PHEV": "AC/PHEV",
    "2. DC Estándar": "DC Estándar",
    "3. HPC 150": "HPC 150",
    "4. HPC 350": "HPC 350",
}
NOMBRES = list(TIPOS.values())
PVP = {"AC/PHEV": 0.30, "DC Estándar": 0.40, "HPC 150": 0.60, "HPC 350": 0.75}
CUOTA_ESPANA = {"AC/PHEV": 0.30, "DC Estándar": 0.40, "HPC 150": 0.20, "HPC 350": 0.10}

COSTE_ENERGIA = 0.20            # €/kWh que paga la electrolinera
EFICIENCIA_CARGA = 0.90         # tiempo (h) = E / (P · 0,9)
ENERGIA_MINIMA = 1.0            # kWh: los datos están recortados en 1 kWh

LIMITE_TRANSFORMADOR = 11_500   # kW
COSTE_BATERIA_KW_MES = 100      # € por kW de batería alquilada y mes
COSTE_CORTE = (1_500, 2_000, 3_500)   # triangular (mínimo, moda, máximo) en €
DIAS_MES = 30

# Origen del caso (para la página "Acerca del proyecto" y el README)
ASIGNATURA = "una asignatura del Grado en Ciencia de Datos e Inteligencia Artificial de la UMH"
