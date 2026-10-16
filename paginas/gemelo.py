"""Página principal: resultados del escenario configurado en la barra lateral."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from electrolinera import config as C
from electrolinera import simulacion as S
from electrolinera.app_utils import AZUL, GRIS, ROJO, euros, num, simulacion

esc: S.Escenario = st.session_state["escenario"]
sim = simulacion(esc, st.session_state["n_sims"], st.session_state["seed"])
met = S.evaluar(sim)
res = S.resumen(met)

st.title("⚡ Gemelo digital de una electrolinera en la AP-7")
st.caption(f"{num(len(met))} meses simulados de {esc.dias} días con los parámetros de la barra lateral. "
           "Cada mes es un futuro posible: llegadas de Poisson por franja, tipo de cargador "
           "multinomial y energía y potencia según el tipo.")

# ---- KPIs -------------------------------------------------------------------- #
bn, cortes = res.loc["beneficio_neto"], res.loc["cortes"]
k1, k2, k3, k4 = st.columns(4)
k1.metric("Beneficio neto mensual", euros(bn["media"]),
          help=f"Media de los meses simulados. IC 95 % de la media: {euros(bn['ic_inf'])} – {euros(bn['ic_sup'])}. "
               f"En el 90 % de los meses está entre {euros(bn['p5'])} y {euros(bn['p95'])}.")
k2.metric("Beneficio bruto mensual", euros(res.loc["beneficio_bruto", "media"]),
          help="Energía vendida × (precio de venta − coste de la energía), antes de cortes y baterías.")
k3.metric("Cortes por sobrecarga al mes", num(cortes["media"], 1),
          help=f"Horas con potencia instantánea total > {num(esc.limite_kw)} kW (límite) "
               f"+ {num(esc.bateria_kw)} kW (batería).")
k4.metric("Meses sin ningún corte", f"{100 * (met['cortes'] == 0).mean():.0f} %")

st.caption(f"Peor mes probable (percentil 5): **{euros(bn['p5'])}** · "
           f"mejor mes probable (percentil 95): **{euros(bn['p95'])}**")

# ---- De bruto a neto -------------------------------------------------------- #
izq, der = st.columns([1, 1])
with izq:
    st.subheader("Del beneficio bruto al neto")
    pasos = [("Bruto", res.loc["beneficio_bruto", "media"]),
             ("Ingresos<br>perdidos", -res.loc["ingresos_perdidos", "media"]),
             ("Coste de<br>los cortes", -res.loc["coste_cortes", "media"]),
             ("Alquiler<br>batería", -res.loc["alquiler_bateria", "media"])]
    fig = go.Figure(go.Waterfall(
        x=[p[0] for p in pasos] + ["Neto"],
        y=[p[1] for p in pasos] + [0],
        measure=["absolute", "relative", "relative", "relative", "total"],
        text=[euros(abs(p[1])) for p in pasos] + [euros(bn["media"])], textposition="outside",
        connector={"line": {"color": GRIS, "width": 1}},
        increasing={"marker": {"color": AZUL}}, decreasing={"marker": {"color": ROJO}},
        totals={"marker": {"color": AZUL}}))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
                      yaxis=dict(title="€ / mes", rangemode="tozero"))
    st.plotly_chart(fig, width="stretch", theme="streamlit")

with der:
    st.subheader("¿Cuánto puede variar un mes?")
    fig = go.Figure(go.Histogram(x=met["beneficio_neto"], nbinsx=40, marker_color=AZUL,
                                 hovertemplate="%{x:,.0f} €<br>%{y} meses<extra></extra>"))
    for valor, txt in [(bn["p5"], "P5"), (bn["media"], "media"), (bn["p95"], "P95")]:
        fig.add_vline(x=valor, line_dash="dash" if txt != "media" else "solid", line_color=GRIS,
                      annotation_text=txt, annotation_position="top")
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), bargap=0.05,
                      xaxis_title="Beneficio neto mensual (€)", yaxis_title="Meses simulados")
    st.plotly_chart(fig, width="stretch", theme="streamlit")

# ---- Potencia por hora -------------------------------------------------------- #
st.subheader("Potencia instantánea total (PIT) a lo largo del día")
horas = sim.horas
perfil = pd.DataFrame({h: sim.pit[:, horas == h].ravel() for h in range(24)})
q = perfil.quantile([0.05, 0.5, 0.95, 0.99]).T
umbral = esc.limite_kw + esc.bateria_kw
fig = go.Figure()
fig.add_trace(go.Scatter(x=q.index, y=q[0.95], line=dict(width=0), hoverinfo="skip", showlegend=False))
fig.add_trace(go.Scatter(x=q.index, y=q[0.05], fill="tonexty", fillcolor="rgba(42,120,214,0.18)",
                         line=dict(width=0), name="90 % de las horas", hoverinfo="skip"))
fig.add_trace(go.Scatter(x=q.index, y=q[0.5], line=dict(color=AZUL, width=2.5), name="Mediana",
                         hovertemplate="%{x}:00 · %{y:,.0f} kW<extra>Mediana</extra>"))
fig.add_trace(go.Scatter(x=q.index, y=q[0.99], line=dict(color=AZUL, width=1.5, dash="dot"), name="P99",
                         hovertemplate="%{x}:00 · %{y:,.0f} kW<extra>P99</extra>"))
fig.add_hline(y=esc.limite_kw, line_color=ROJO, line_dash="dash",
              annotation_text=f"Límite transformador ({num(esc.limite_kw)} kW)", annotation_position="top left")
if esc.bateria_kw > 0:
    fig.add_hline(y=umbral, line_color=GRIS, line_dash="dot",
                  annotation_text=f"Con batería ({num(umbral)} kW)", annotation_position="top left")
for franja, hs in C.FRANJAS.items():
    if franja.startswith("Punta"):
        fig.add_vrect(x0=min(hs) - 0.5, x1=max(hs) + 0.5, fillcolor=ROJO, opacity=0.05, line_width=0,
                      annotation_text=franja, annotation_position="bottom left",
                      annotation_font=dict(size=10, color=GRIS))
fig.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified",
                  xaxis=dict(title="Hora del día", dtick=2), yaxis=dict(title="kW", rangemode="tozero"),
                  legend=dict(orientation="h", y=-0.2))
st.plotly_chart(fig, width="stretch", theme="streamlit")

t = S.pit_p99_por_franja(sim)
t["margen_kw"] = umbral - t["p99_media"]
st.dataframe(
    t.assign(**{"Prob. de corte por hora": (100 * t["prob_corte_hora"]).map("{:.2f} %".format)})
     .rename(columns={"franja": "Franja", "p99_media": "P99 de la PIT (kW)", "margen_kw": "Margen hasta el corte (kW)"})
     [["Franja", "P99 de la PIT (kW)", "Margen hasta el corte (kW)", "Prob. de corte por hora"]].round(0),
    hide_index=True, width="stretch")

if met["cortes"].mean() > 0.5:
    st.info(f"Hay una media de {num(met['cortes'].mean(), 1)} cortes al mes. En **¿Alquilar baterías?** "
            "puedes ver si compensa alquilar una batería y de qué tamaño.")
with st.expander("Desglose completo (media, IC 95 % y percentiles)"):
    etiquetas = {"beneficio_bruto": "Beneficio bruto (€)", "ingresos_perdidos": "Ingresos perdidos (€)",
                 "coste_cortes": "Coste de cortes (€)", "alquiler_bateria": "Alquiler batería (€)",
                 "beneficio_neto": "Beneficio neto (€)", "cortes": "Cortes", "energia_kwh": "Energía (kWh)",
                 "vehiculos": "Vehículos", "pit_p99": "P99 PIT (kW)", "pit_max": "PIT máxima (kW)"}
    st.dataframe(res.rename(index=etiquetas, columns={"media": "Media", "ic_inf": "IC 95 % inf.",
                                                       "ic_sup": "IC 95 % sup.", "p5": "P5", "p95": "P95"})
                 .round(1), width="stretch")
    energia_mes = res.loc["energia_kwh", "media"]
    precio_medio = (res.loc["beneficio_bruto", "media"] + esc.coste_energia * energia_mes) / energia_mes
    st.caption(f"Vehículos al mes: {num(res.loc['vehiculos', 'media'])} · energía: "
               f"{num(res.loc['energia_kwh', 'media'] / 1000, 1)} MWh · "
               f"precio medio de venta (ponderado por energía): {precio_medio:.3f} €/kWh")
