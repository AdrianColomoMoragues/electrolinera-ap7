"""Datos históricos y modelos ajustados: de dónde salen los parámetros del simulador."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats
import streamlit as st

from electrolinera import config as C
from electrolinera.app_utils import AZUL, COLORES_TIPO, GRIS, ROJO, modelos, num

m = modelos()
NOMBRE_DIST = {"norm": "Normal", "uniform": "Uniforme", "gamma": "Gamma", "lognorm": "Lognormal",
               "weibull_min": "Weibull", "expon": "Exponencial", "constante": "Constante"}



def formato_parametros(dist: str, p: list) -> str:
    if dist == "norm":
        return f"μ = {p[0]:.1f}, σ = {p[1]:.1f}"
    if dist == "uniform":
        return f"[{p[0]:.1f}, {p[0] + p[1]:.1f}]"
    if dist == "gamma":
        return f"forma = {p[0]:.2f}, escala = {p[2]:.2f}"
    return str([round(v, 2) for v in p])


st.title("📊 Datos y modelos")
r = m["empirico"]["resumen_mes"]
st.caption(f"{num(r['vehiculos'])} recargas registradas en {r['dias']} días. Cada parámetro del simulador se "
           "ajusta a estos datos con `python -m electrolinera.ajuste` y se guarda en `modelos/modelos.json`.")

# ---- Llegadas ----------------------------------------------------------------- #
st.subheader("1. Llegadas: Poisson por franja")
ll = m["llegadas"]
filas = [{"Franja": f, "Horas": f"{min(d['horas']):02d}–{max(d['horas']) + 1:02d} h",
          "λ (vehículos/h)": round(d["lambda"], 2), "Varianza / media": round(d["dispersion"], 2),
          "p χ² Poisson": round(d["p_chi2_poisson"], 3),
          "Tendencia (veh/h por día)": round(d["tendencia_por_dia"], 2),
          "p tendencia": round(d["p_tendencia"], 3)} for f, d in ll.items()]
st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
st.caption("Varianza ≈ media y p-valores altos en la prueba χ²: las llegadas son compatibles con una Poisson "
           "en todas las franjas. **Excepción:** en Llano (Mañana) la demanda crece a lo largo del mes "
           "(≈ +10 % de la primera a la segunda quincena); el control de demanda de la barra lateral permite "
           "explorar ese crecimiento.")

franja = st.selectbox("Ver la distribución de una franja", list(ll))
d = ll[franja]
k = np.array([int(x) for x in d["frecuencias"]])
f = np.array(list(d["frecuencias"].values()))
xs = np.arange(k.min() - 3, k.max() + 4)
fig = go.Figure()
fig.add_trace(go.Bar(x=k, y=f / f.sum(), name="Datos", marker_color=AZUL, opacity=0.7,
                     hovertemplate="%{x} veh/h · %{y:.3f}<extra>Datos</extra>"))
fig.add_trace(go.Scatter(x=xs, y=stats.poisson.pmf(xs, d["lambda"]), name=f"Poisson(λ = {d['lambda']:.1f})",
                         mode="lines+markers", line=dict(color=ROJO, width=2), marker=dict(size=5),
                         hovertemplate="%{x} veh/h · %{y:.3f}<extra>Poisson</extra>"))
fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Vehículos por hora",
                  yaxis_title="Proporción de horas", legend=dict(orientation="h", y=-0.25), bargap=0.1)
st.plotly_chart(fig, width="stretch", theme="streamlit")

# ---- Mezcla -------------------------------------------------------------------- #
st.subheader("2. Tipo de cargador: multinomial")
mz = m["mezcla"]
fig = go.Figure()
fig.add_trace(go.Bar(x=C.NOMBRES, y=[C.CUOTA_ESPANA[t] for t in C.NOMBRES], name="Mercado español",
                     marker_color=GRIS, hovertemplate="%{y:.0%}<extra>España</extra>"))
fig.add_trace(go.Bar(x=C.NOMBRES, y=mz["p"], name="Electrolinera AP-7", marker_color=AZUL,
                     hovertemplate="%{y:.1%}<extra>AP-7</extra>"))
fig.update_layout(barmode="group", height=300, margin=dict(l=10, r=10, t=10, b=10),
                  yaxis=dict(title="Cuota", tickformat=".0%"), legend=dict(orientation="h", y=-0.2))
st.plotly_chart(fig, width="stretch", theme="streamlit")
st.caption(f"En autopista hay la mitad de PHEV y el doble de HPC 150 que en el mercado español. La mezcla no "
           f"depende de la franja horaria (χ² de homogeneidad, p = {mz['p_homogeneidad_franjas']:.2f}), así que "
           "se usa la misma en todo el día.")

# ---- Energía y potencia ----------------------------------------------------------- #
st.subheader("3. Energía y potencia por tipo de cargador")
st.caption("Para cada tipo se ajustan por máxima verosimilitud seis distribuciones candidatas y se elige la de "
           "menor AIC. La energía y la potencia no dependen de la franja (Kruskal-Wallis, p > 0,3) ni están "
           "correlacionadas entre sí, así que se simulan de forma independiente.")
tabla = []
for var, unidad in [("energia", "kWh"), ("potencia", "kW")]:
    for t in C.NOMBRES:
        s = m[var][t]
        if s["dist"] == "constante":
            par, ks, seg = f"{s['valor']:g} {unidad}", "—", "—"
        else:
            p = s["params"]
            par = formato_parametros(s["dist"], p)
            otras = sorted(s["candidatas"].items(), key=lambda kv: kv[1]["aic"])
            ks = f"{s['ks_p']:.2f}"
            seg = f"{NOMBRE_DIST[otras[1][0]]} (ΔAIC = {otras[1][1]['aic'] - s['aic']:,.0f})" if len(otras) > 1 else "—"
        tabla.append({"Variable": "Energía" if var == "energia" else "Potencia", "Tipo": t,
                      "Distribución": NOMBRE_DIST[s["dist"]], "Parámetros": par, "p KS": ks,
                      "Segunda mejor": seg})
st.dataframe(pd.DataFrame(tabla), hide_index=True, width="stretch")

var = st.radio("Variable", ["Energía (kWh)", "Potencia (kW)"], horizontal=True)
clave = "energia" if var.startswith("Energía") else "potencia"
cols = st.columns(2)
for i, t in enumerate(C.NOMBRES):
    s = m[clave][t]
    with cols[i % 2]:
        if s["dist"] == "constante":
            st.markdown(f"**{t}** · siempre {s['valor']:g} kW (cargador de potencia fija)")
            continue
        h = m["empirico"][clave][t]
        bordes = np.array(h["bordes"])
        anchos = np.diff(bordes)
        dens = np.array(h["cuentas"]) / (np.sum(h["cuentas"]) * anchos)
        xs = np.linspace(bordes[0], bordes[-1], 300)
        pdf = getattr(stats, s["dist"]).pdf(xs, *s["params"])
        fig = go.Figure()
        fig.add_trace(go.Bar(x=(bordes[:-1] + bordes[1:]) / 2, y=dens, width=anchos, name="Datos",
                             marker_color=COLORES_TIPO[t], opacity=0.55, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=xs, y=pdf, name=NOMBRE_DIST[s["dist"]], line=dict(color=COLORES_TIPO[t], width=2.5),
                                 hovertemplate="%{x:.1f} · %{y:.4f}<extra></extra>"))
        fig.update_layout(title=dict(text=f"{t} · {NOMBRE_DIST[s['dist']]}", font=dict(size=14)), height=260,
                          margin=dict(l=10, r=10, t=40, b=10), showlegend=False, bargap=0, yaxis_title="Densidad")
        st.plotly_chart(fig, width="stretch", theme="streamlit")

# ---- PIT observada ------------------------------------------------------------------ #
st.subheader("4. Potencia instantánea total observada")
pit = np.array(m["empirico"]["pit_dia_hora"])
fig = go.Figure(go.Heatmap(z=pit, x=list(range(24)), y=list(range(1, pit.shape[0] + 1)), colorscale="Blues",
                           colorbar=dict(title="kW"), hovertemplate="Día %{y}, %{x}:00 · %{z:,.0f} kW<extra></extra>"))
dias, horas = np.where(pit > C.LIMITE_TRANSFORMADOR)
fig.add_trace(go.Scatter(x=horas, y=dias + 1, mode="markers", name="Sobre el límite",
                         marker=dict(symbol="x", size=10, color=ROJO, line=dict(width=2)),
                         hovertemplate="Día %{y}, %{x}:00 · sobre el límite<extra></extra>"))
fig.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(title="Hora", dtick=2),
                  yaxis=dict(title="Día", autorange="reversed"), legend=dict(orientation="h", y=-0.15))
st.plotly_chart(fig, width="stretch", theme="streamlit")
st.caption(f"En el mes registrado la PIT superó {num(C.LIMITE_TRANSFORMADOR)} kW en {r['horas_sobre_limite']} horas "
           f"(✕), todas en las franjas punta. P99 observado: {num(r['pit_p99'])} kW; el simulador da de media "
           "un P99 muy parecido, lo que sirve como validación.")
