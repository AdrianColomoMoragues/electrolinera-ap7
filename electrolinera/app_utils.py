"""Controles compartidos de la barra lateral y simulación en caché (dependen de Streamlit)."""
from __future__ import annotations

import streamlit as st

from . import config as C
from . import simulacion as S
from .ajuste import cargar_modelos

COLORES_TIPO = {"AC/PHEV": "#1baf7a", "DC Estándar": "#2a78d6", "HPC 150": "#eda100", "HPC 350": "#eb6834"}
AZUL, GRIS, ROJO = "#2a78d6", "#898781", "#d03b3b"


@st.cache_resource
def modelos() -> dict:
    return cargar_modelos()


@st.cache_data(show_spinner="Simulando…", max_entries=12)
def _simular(factor: float, cuotas: tuple, pvp: tuple, coste_energia: float, coste_corte: tuple,
             n_sims: int, seed: int) -> S.Simulacion:
    esc = S.Escenario(factor_demanda=factor, cuotas=dict(zip(C.NOMBRES, cuotas)),
                      pvp=dict(zip(C.NOMBRES, pvp)), coste_energia=coste_energia,
                      coste_corte=coste_corte)
    return S.simular(modelos(), esc, n_sims=n_sims, seed=seed)


def simulacion(esc: S.Escenario, n_sims: int, seed: int) -> S.Simulacion:
    """Simula (o recupera de la caché) y adjunta el escenario completo.

    El límite, la batería y su coste no cambian las horas simuladas, solo la
    evaluación, así que no forman parte de la clave de la caché.
    """
    sim = _simular(esc.factor_demanda, tuple(esc.cuotas[t] for t in C.NOMBRES),
                   tuple(esc.pvp[t] for t in C.NOMBRES), esc.coste_energia, tuple(esc.coste_corte),
                   n_sims, seed)
    return S.Simulacion(sim.pit, sim.bb, sim.energia, sim.vehiculos, sim.coste_corte_hora, esc)


def _restablecer():
    for k in list(st.session_state):
        if k.startswith("p_"):
            del st.session_state[k]


def barra_lateral() -> tuple[S.Escenario, int, int]:
    """Dibuja los controles y devuelve (escenario, n_sims, semilla)."""
    m = modelos()
    base = dict(zip(C.NOMBRES, m["mezcla"]["p"]))
    sb = st.sidebar
    sb.header("⚙️ Parámetros")
    sb.button("Restablecer valores del caso", on_click=_restablecer, width="stretch")

    with sb.expander("🚗 Demanda y mezcla", expanded=True):
        factor = st.slider("Demanda respecto a la histórica", 0.5, 2.0, 1.0, 0.05, key="p_factor",
                           format="%.2f×", help="Multiplica la tasa de llegadas de todas las franjas.")
        st.caption("Cuota de cada tipo de cargador (%). Se reescalan para sumar 100 %.")
        crudas = {t: st.slider(t, 0.0, 100.0, round(100 * base[t], 1), 0.5, key=f"p_cuota_{t}")
                  for t in C.NOMBRES}
        total = sum(crudas.values()) or 1.0
        cuotas = {t: v / total for t, v in crudas.items()}
        if abs(total - 100) > 0.05:
            st.caption("Normalizadas: " + " · ".join(f"{t} {100 * v:.1f} %" for t, v in cuotas.items()))

    with sb.expander("💶 Precios y costes"):
        pvp = {t: st.number_input(f"PVP {t} (€/kWh)", 0.0, 2.0, C.PVP[t], 0.01, key=f"p_pvp_{t}")
               for t in C.NOMBRES}
        ce = st.number_input("Coste de la energía (€/kWh)", 0.0, 1.0, C.COSTE_ENERGIA, 0.01, key="p_ce")
        a, mo, b = C.COSTE_CORTE
        corte = st.slider("Coste por corte: mínimo y máximo (€)", 0, 10_000, (a, b), 100, key="p_corte")
        moda = st.number_input("Coste por corte: valor más probable (€)", float(corte[0]), float(corte[1]),
                               float(min(max(mo, corte[0]), corte[1])), 100.0, key="p_moda")
        pierde = st.checkbox("En una hora con corte se pierden sus ingresos", True, key="p_pierde",
                             help="Supuesto del caso: el corte deja sin servicio toda esa hora.")

    with sb.expander("🔌 Infraestructura", expanded=True):
        limite = st.number_input("Límite del transformador (kW)", 1_000, 50_000, C.LIMITE_TRANSFORMADOR,
                                 100, key="p_limite")
        bateria = st.number_input("Batería alquilada (kW)", 0, 20_000, 0, 100, key="p_bateria")
        cbat = st.number_input("Alquiler de batería (€/kW·mes)", 0, 1_000, C.COSTE_BATERIA_KW_MES, 5,
                               key="p_cbat")

    with sb.expander("🎲 Simulación"):
        n_sims = st.select_slider("Meses simulados", [50, 100, 200, 500, 1000], 200, key="p_nsims",
                                  help="Más meses = intervalos más estrechos, pero más lento.")
        seed = st.number_input("Semilla", 0, 10_000, 123, 1, key="p_seed")

    esc = S.Escenario(factor_demanda=factor, cuotas=cuotas, pvp=pvp, coste_energia=ce,
                      limite_kw=limite, bateria_kw=bateria, coste_bateria_kw_mes=cbat,
                      coste_corte=(corte[0], moda, corte[1]), pierde_ingresos_en_corte=pierde)
    sb.caption("Basado en un caso práctico de la asignatura (UMH). Ver *Acerca del proyecto*.")
    return esc, int(n_sims), int(seed)


def euros(x: float) -> str:
    return f"{x:,.0f} €".replace(",", ".")


def num(x: float, dec: int = 0) -> str:
    s = f"{x:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")
