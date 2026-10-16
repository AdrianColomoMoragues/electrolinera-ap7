"""¿Alquilar baterías? Curva de beneficio neto según el tamaño de la batería."""
import plotly.graph_objects as go
import streamlit as st

from electrolinera import escenarios as E
from electrolinera import simulacion as S
from electrolinera.app_utils import AZUL, GRIS, ROJO, euros, num, simulacion

esc: S.Escenario = st.session_state["escenario"]
sim = simulacion(esc.con(bateria_kw=0), st.session_state["n_sims"], st.session_state["seed"])

st.title("🔋 ¿Cuánta batería conviene alquilar?")
st.caption("Cuando la potencia instantánea supera el límite del transformador, una batería alquilada "
           f"(BESS) puede cubrir el exceso. Cuesta {num(esc.coste_bateria_kw_mes)} € por kW y mes, "
           "así que solo compensa si los cortes que evita valen más que su alquiler.")


@st.cache_data(show_spinner="Calculando la curva…", max_entries=12)
def _comparar(clave, _sim):
    return E.regla_p99_vs_optima(_sim)


clave = (esc.factor_demanda, tuple(esc.cuotas.values()), tuple(esc.pvp.values()), esc.coste_energia,
         esc.limite_kw, esc.coste_bateria_kw_mes, tuple(esc.coste_corte), esc.pierde_ingresos_en_corte,
         st.session_state["n_sims"], st.session_state["seed"])
r = _comparar(clave, sim)
curva = r["curva"]
base = curva.iloc[0]

k1, k2, k3 = st.columns(3)
k1.metric("Batería óptima", f"{num(r['optima_kw'])} kW",
          help="El tamaño con mayor beneficio neto medio (en pasos de 100 kW).")
mejora = r["bn_optima"] - base["bn_media"]
k2.metric("Beneficio neto con la óptima", euros(r["bn_optima"]),
          delta=f"+{euros(mejora)} frente a no alquilar" if mejora > 1 else None)
perdida_regla = r["bn_regla"] - r["bn_optima"]          # <= 0 por construcción
k3.metric("Regla del P99 (caso original)", f"{num(r['regla_kw'])} kW",
          delta=f"{euros(perdida_regla)} al mes frente a la óptima" if perdida_regla < -1 else None,
          delta_color="normal",
          help="Dimensionar la batería para cubrir el déficit del percentil 99 de la PIT en la franja "
               "Punta (Mediodía): el criterio habitual de ingeniería.")

if r["optima_kw"] == 0:
    st.success("**No compensa alquilar baterías en este escenario.** Los cortes son pocos y cada kW de "
               "batería cuesta más de lo que ahorra.")
else:
    st.info(f"**Conviene alquilar unos {num(r['optima_kw'])} kW.** Mejora el beneficio neto en "
            f"{euros(r['bn_optima'] - base['bn_media'])} al mes frente a no hacer nada "
            + (f"y en {euros(r['ganancia_optima_vs_regla'])} frente a la regla del P99."
               if r["ganancia_optima_vs_regla"] > 1 else "."))

fig = go.Figure()
x = curva["bateria_kw"]
fig.add_trace(go.Scatter(x=x, y=curva["bn_ic_sup"], line=dict(width=0), hoverinfo="skip", showlegend=False))
fig.add_trace(go.Scatter(x=x, y=curva["bn_ic_inf"], fill="tonexty", fillcolor="rgba(42,120,214,0.2)",
                         line=dict(width=0), name="IC 95 % de la media", hoverinfo="skip"))
fig.add_trace(go.Scatter(x=x, y=curva["bn_media"], line=dict(color=AZUL, width=2.5), name="Beneficio neto medio",
                         customdata=curva[["cortes_medios", "alquiler"]],
                         hovertemplate="%{x:,.0f} kW<br>%{y:,.0f} €/mes<br>%{customdata[0]:.1f} cortes/mes"
                                       "<br>alquiler %{customdata[1]:,.0f} €<extra></extra>"))
fig.add_trace(go.Scatter(x=x, y=curva["bn_p5"], line=dict(color=AZUL, width=1.2, dash="dot"),
                         name="Peor mes probable (P5)", hovertemplate="%{y:,.0f} €<extra>P5</extra>"))
fig.add_vline(x=r["optima_kw"], line_color=AZUL, annotation_text="Óptima", annotation_position="top right")
fig.add_vline(x=r["regla_kw"], line_color=ROJO, line_dash="dash", annotation_text="Regla P99",
              annotation_position="top left")
if esc.bateria_kw > 0:
    fig.add_vline(x=esc.bateria_kw, line_color=GRIS, line_dash="dot", annotation_text="Tu elección",
                  annotation_position="bottom right")
fig.update_layout(height=430, margin=dict(l=10, r=10, t=30, b=10), hovermode="x unified",
                  xaxis_title="Batería alquilada (kW)", yaxis_title="Beneficio neto (€ / mes)",
                  legend=dict(orientation="h", y=-0.2))
st.plotly_chart(fig, width="stretch", theme="streamlit")

c1, c2 = st.columns(2)
with c1:
    st.subheader("Cortes evitados")
    fig2 = go.Figure(go.Scatter(x=x, y=curva["cortes_medios"], line=dict(color=AZUL, width=2.5),
                                hovertemplate="%{x:,.0f} kW · %{y:.1f} cortes/mes<extra></extra>"))
    fig2.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Batería (kW)",
                       yaxis=dict(title="Cortes al mes", rangemode="tozero"))
    st.plotly_chart(fig2, width="stretch", theme="streamlit")
with c2:
    if r["regla_kw"] > r["optima_kw"] + 50:
        st.subheader("Por qué la regla del P99 se pasa")
    elif r["regla_kw"] < r["optima_kw"] - 50:
        st.subheader("Aquí la regla del P99 se queda corta")
    else:
        st.subheader("Aquí la regla del P99 acierta")
    st.markdown(
        "El P99 dimensiona la batería para cubrir el **99 % de las horas** de la franja crítica. "
        "Pero los últimos kW solo evitan cortes muy raros: cada uno ahorra de media unos "
        f"{euros(sum(esc.coste_corte) / 3)} más los ingresos de esa hora, y cuesta "
        f"{euros(esc.coste_bateria_kw_mes)} al mes.\n\n"
        "La curva busca el punto en que **un kW más cuesta más de lo que ahorra**. "
        "Como se evalúan todos los tamaños sobre los mismos meses simulados (números aleatorios "
        "comunes), las diferencias entre tamaños se deben a la batería y no al azar.")

with st.expander("Tabla de la curva"):
    st.dataframe(curva.rename(columns={
        "bateria_kw": "Batería (kW)", "bn_media": "BN medio (€)", "bn_ic_inf": "IC inf.", "bn_ic_sup": "IC sup.",
        "bn_p5": "BN P5 (€)", "mejora_vs_sin_bateria": "Mejora vs. sin batería (€)",
        "mejora_ic_inf": "Mejora IC inf.", "mejora_ic_sup": "Mejora IC sup.",
        "cortes_medios": "Cortes/mes", "prob_algun_corte": "P(algún corte)", "alquiler": "Alquiler (€)"})
        .round(2), hide_index=True, width="stretch")
st.caption("Supuestos: la batería solo está limitada por potencia (su energía basta para cubrir el pico de "
           "esa hora) y la potencia instantánea de una hora es la suma de las potencias de los vehículos "
           "que llegan en ella, como en el caso original.")
