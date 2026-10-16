"""Prueba de humo de la app: todas las páginas se ejecutan sin errores con los modelos guardados."""
import pytest
from streamlit.testing.v1 import AppTest

from electrolinera.config import MODELOS_PATH, ROOT

pytestmark = pytest.mark.skipif(not MODELOS_PATH.exists(), reason="falta modelos/modelos.json")
PAGINAS = ["paginas/baterias.py", "paginas/escenarios.py", "paginas/modelos.py", "paginas/acerca.py"]


@pytest.fixture(scope="module")
def app():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300).run()
    at.select_slider(key="p_nsims").set_value(50)       # menos meses: tests más rápidos
    return at.run()


def test_pagina_principal(app):
    assert not app.exception
    assert len(app.metric) == 4


@pytest.mark.parametrize("pagina", PAGINAS)
def test_paginas(app, pagina):
    app.switch_page(pagina).run()
    assert not app.exception


def test_cambiar_demanda_cambia_resultados(app):
    app.switch_page("paginas/gemelo.py").run()
    antes = app.metric[1].value
    app.slider(key="p_factor").set_value(1.25).run()
    assert not app.exception and app.metric[1].value != antes
