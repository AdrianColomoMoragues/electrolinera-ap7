"""Acerca del proyecto: el caso, el origen de los datos y el método."""
import streamlit as st

from electrolinera import config as C

st.title("ℹ️ Acerca del proyecto")
st.markdown(f"""
### El caso

Una empresa que opera electrolineras en autopistas abre una estación de gran tamaño en la **AP-7**. Tiene
cargadores de los cuatro tipos del mercado (AC para híbridos enchufables, DC estándar de 50 kW, HPC de 150 kW
y HPC de más de 250 kW) y atiende a todos los vehículos que llegan.

La estación tiene un límite físico: el **transformador** que la conecta a la red admite como máximo
**{C.LIMITE_TRANSFORMADOR:,} kW**. Si en una hora la suma de las potencias de los coches que cargan supera ese
límite, la protección salta: se corta el servicio, se pierde la facturación de esa hora y la reparación cuesta
entre {C.COSTE_CORTE[0]:,} y {C.COSTE_CORTE[2]:,} €. Una alternativa es **alquilar baterías** (BESS) que cubran
los picos, a {C.COSTE_BATERIA_KW_MES} € por kW y mes.

La pregunta de negocio: **¿cuánto gana la estación, cuánto riesgo de cortes tiene y cuándo compensa alquilar
baterías?**, hoy y ante cambios del mercado.

### Qué hace este proyecto

1. **Ajusta modelos estocásticos** a 30 días de registros: llegadas de Poisson por franja horaria, tipo de
   cargador multinomial y energía y potencia según el tipo (seis distribuciones candidatas, elegidas por AIC).
2. **Simula meses completos** con Monte Carlo vectorizado (200 meses en menos de un segundo).
3. **Calcula el beneficio neto** descontando los cortes y el alquiler de baterías.
4. **Busca la batería óptima** con una curva de beneficio frente a kW, con números aleatorios comunes, y la
   compara con la regla clásica del percentil 99.

### Origen

Proyecto propio basado en un caso práctico de {C.ASIGNATURA}. El planteamiento se ha reescrito y el código
es nuevo: el ajuste de distribuciones, el simulador vectorizado, la optimización de baterías, los escenarios
y la app.

**Datos:** registros sintéticos de 30 días de una electrolinera, publicados en el repositorio docente
[UMH1477/python]({C.DATA_URL}). No se redistribuyen en este repositorio: `python -m electrolinera.ajuste` los
descarga de la fuente y guarda solo los parámetros ajustados y resúmenes agregados (`modelos/modelos.json`).

### Supuestos y limitaciones
- La potencia instantánea de una hora es la **suma de las potencias** de los vehículos que llegan en ella; no
  se modela el solapamiento real de recargas entre horas.
- En una hora con corte se pierde toda su facturación (se puede desactivar en la barra lateral).
- La batería está limitada solo por potencia: se supone que tiene energía suficiente para el pico.
- Las tasas de llegada son constantes en cada franja. En los datos, la franja Llano (Mañana) crece a lo largo
  del mes: es un indicio de que la demanda no es estacionaria.
""")
