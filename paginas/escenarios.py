"""Comparación de escenarios estratégicos predefinidos."""
import plotly.graph_objects as go
import streamlit as st

from electrolinera import escenarios as E
from electrolinera import simulacion as S
from electrolinera.app_utils import AZUL, GRIS, euros, modelos, num

esc: S.Escenario = st.session_state["escenario"]
n_sims = min(st.session_state["n_sims"], 200)

st.title("🧭 Escenarios estratégicos")
st.caption("Seis futuros posibles evaluados con los mismos meses aleatorios (misma semilla), para que las "
           "diferencias se deban al escenario y no al azar. Para cada uno se calcula también la batería "
           "óptima. Los precios, el límite y los costes son los de la barra lateral.")


@st.cache_data(show_spinner="Simulando los seis escenarios…", max_entries=6)
def _comparar(clave):
    base = S.Escenario(pvp=dict(esc.pvp), coste_energia=esc.coste_energia, limite_kw=esc.limite_kw,
                       coste_bateria_kw_mes=esc.coste_bateria_kw_mes, coste_corte=tuple(esc.coste_corte),
                       pierde_ingresos_en_corte=esc.pierde_ingresos_en_corte)
    return E.comparar(modelos(), base, n_sims=n_sims, seed=st.session_state["seed"])


t = _comparar((tuple(esc.pvp.values()), esc.coste_energia, esc.limite_kw, esc.coste_bateria_kw_mes,
               tuple(esc.coste_corte), esc.pierde_ingresos_en_corte, n_sims, st.session_state["seed"]))

fig = go.Figure()
fig.add_trace(go.Bar(y=t["escenario"], x=t["bn_sin_bateria"], orientation="h", name="Sin batería",
                     marker_color=GRIS, hovertemplate="%{x:,.0f} €<extra>Sin batería</extra>"))
fig.add_trace(go.Bar(y=t["escenario"], x=t["bn_con_optima"], orientation="h", name="Con la batería óptima",
                     marker_color=AZUL, customdata=t["bateria_optima_kw"],
                     hovertemplate="%{x:,.0f} € con %{customdata:,.0f} kW<extra></extra>"))
fig.update_layout(barmode="group", height=420, margin=dict(l=10, r=10, t=10, b=10),
                  xaxis_title="Beneficio neto mensual medio (€)", yaxis=dict(autorange="reversed"),
                  legend=dict(orientation="h", y=-0.15), bargap=0.25, bargroupgap=0.05)
st.plotly_chart(fig, width="stretch", theme="streamlit")

st.dataframe(t.assign(
    **{"Beneficio bruto": t["bb_media"].map(euros),
       "BN sin batería": t["bn_sin_bateria"].map(euros),
       "Cortes/mes sin batería": t["cortes_sin_bateria"].round(1),
       "Batería óptima": t["bateria_optima_kw"].map(lambda v: f"{num(v)} kW"),
       "BN con la óptima": t["bn_con_optima"].map(euros),
       "Regla P99": t["bateria_regla_p99_kw"].map(lambda v: f"{num(v)} kW"),
       "BN vs. actual": t["bn_vs_actual"].map(euros)})
    [["escenario", "Beneficio bruto", "BN sin batería", "Cortes/mes sin batería",
      "Batería óptima", "BN con la óptima", "Regla P99", "BN vs. actual"]]
    .rename(columns={"escenario": "Escenario"}),
    hide_index=True, width="stretch")
with st.expander("Qué cambia en cada escenario"):
    st.markdown("\n".join(f"- **{e}**: {d}" for e, d in zip(t["escenario"], t["descripcion"])))
st.caption("BN = beneficio neto mensual medio. «BN vs. actual» compara cada escenario, con su batería óptima, "
           "con la situación actual con la suya.")

fila = t.set_index("escenario")
act, dem, phev = fila.loc["Situación actual"], fila.loc["Demanda +25 %"], fila.loc["Fin de subsidios PHEV"]
lecturas = []
if dem["bb_media"] > act["bb_media"] and dem["bn_sin_bateria"] < act["bn_sin_bateria"]:
    lecturas.append(
        f"**Más clientes no es más dinero si la red no acompaña.** Con la demanda +25 %, el beneficio bruto sube a "
        f"{euros(dem['bb_media'])}, pero sin batería el neto baja a {euros(dem['bn_sin_bateria'])} por los cortes "
        f"({num(dem['cortes_sin_bateria'])} al mes).")
signo_bb = "sube" if phev["bb_media"] > act["bb_media"] else "baja"
signo_bn = "sube" if phev["bn_sin_bateria"] > act["bn_sin_bateria"] else "baja"
lecturas.append(
    f"**Fin de los subsidios PHEV: el bruto {signo_bb} ({euros(act['bb_media'])} → {euros(phev['bb_media'])}) "
    f"y el neto sin batería {signo_bn} ({euros(act['bn_sin_bateria'])} → {euros(phev['bn_sin_bateria'])}).** "
    "Se sustituyen recargas lentas y baratas por otras rápidas y caras: más ingresos por vehículo, pero también "
    f"más picos de potencia ({num(act['cortes_sin_bateria'], 1)} → "
    f"{num(phev['cortes_sin_bateria'], 1)} cortes al mes).")
lecturas.append("**El coste de la energía no cambia los cortes**: solo reduce el margen por kWh.")
con_cortes = t[t["cortes_sin_bateria"] >= 1]
if len(con_cortes):
    mayor = int((con_cortes["bateria_regla_p99_kw"] > con_cortes["bateria_optima_kw"]).sum())
    lecturas.append(f"La **regla del P99** propone una batería mayor que la óptima en {mayor} de los "
                    f"{len(con_cortes)} escenarios con cortes.")
st.subheader("Lecturas")
st.markdown("\n".join(f"- {x}" for x in lecturas))
