"""Gemelo digital de una electrolinera de autopista (Streamlit).

Punto de entrada: barra lateral compartida y navegación entre páginas.
`streamlit run app.py`
"""
import streamlit as st

st.set_page_config(page_title="Gemelo digital · Electrolinera AP-7", page_icon="⚡", layout="wide")

from electrolinera.app_utils import barra_lateral  # noqa: E402

st.session_state["escenario"], st.session_state["n_sims"], st.session_state["seed"] = barra_lateral()

paginas = [
    st.Page("paginas/gemelo.py", title="Gemelo digital", icon="⚡", default=True),
    st.Page("paginas/baterias.py", title="¿Alquilar baterías?", icon="🔋"),
    st.Page("paginas/escenarios.py", title="Escenarios", icon="🧭"),
    st.Page("paginas/modelos.py", title="Datos y modelos", icon="📊"),
    st.Page("paginas/acerca.py", title="Acerca del proyecto", icon="ℹ️"),
]
st.navigation(paginas).run()
