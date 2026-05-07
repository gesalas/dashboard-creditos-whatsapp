import streamlit as st
import pandas as pd
import json

st.set_page_config(layout="wide")

# -----------------------
# RECARGA MANUAL
# -----------------------

if st.button("🔄 Recargar datos"):
    st.cache_data.clear()

# -----------------------
# CARGA DE ARCHIVOS
# -----------------------

@st.cache_data
def load_tarifas_config():
    tarifas = pd.read_csv("tarifas.csv")

    with open("config.json") as f:
        config = json.load(f)

    return tarifas, config

# cargar archivos fijos
tarifas, config = load_tarifas_config()

# uploader excel
uploaded_file = st.file_uploader(
    "📂 Sube el archivo data.xlsx",
    type=["xlsx"]
)

# validar carga
if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
else:
    st.warning("⚠️ Debes subir el archivo data.xlsx")
    st.stop()

# -----------------------
# AJUSTE GLOBAL
# -----------------------

FACTOR_AJUSTE = 0.97031

# -----------------------
# LIMPIEZA
# -----------------------

df.columns = df.columns.str.strip()
df["Journey Name"] = df["Journey Name"].fillna("SIN_NOMBRE")

df["WhatsApp Country"] = df["WhatsApp Country"].str.upper().str.strip()
tarifas["ISO"] = tarifas["ISO"].str.upper().str.strip()

# -----------------------
# FECHAS
# -----------------------

df["Send Date"] = pd.to_datetime(df["Send Date"], errors="coerce")
df = df[df["Send Date"].notna()]

# -----------------------
# MERGE TARIFAS
# -----------------------

df = df.merge(tarifas, left_on="WhatsApp Country", right_on="ISO", how="left")

# fallback OTHER
other_value = tarifas[tarifas["ISO"] == "OTHER"]["Marketing"]
other_value = other_value.values[0] if not other_value.empty else 0

df["Marketing"] = df["Marketing"].fillna(other_value)

# -----------------------
# MÉTRICAS BASE
# -----------------------

df["creditos"] = df["WhatsApp Deliveries"] * df["Marketing"]

# -----------------------
# UNIDADES
# -----------------------

df["unidad_raw"] = df["Journey Name"].str.split("_").str[0].str.lower()

def map_unidad(x):
    if x == "egres":
        return "egresados"
    elif x == "donac":
        return "donaciones"
    else:
        return "mercadeo"

df["unidad"] = df["unidad_raw"].apply(map_unidad)

df["mes"] = df["Send Date"].dt.to_period("M").astype(str)
df["semana"] = df["Send Date"].dt.isocalendar().week

# -----------------------
# CLASIFICACIÓN
# -----------------------

def clasificar_journey(nombre):
    nombre = nombre.upper()

    if "ACCESO" in nombre:
        return "AUTOMATICO - ACCESO"
    elif nombre.startswith("MERCA_FINANCIACION") or nombre.startswith("MERCA_MANTENIMIENTO"):
        return "AUTOMATICO - FINANCIACION"
    elif "VISITAS_LOS_VIERNES" in nombre:
        return "AUTOMATICO - VISITAS"
    else:
        return "CAMPAÑA"

df["tipo_journey"] = df["Journey Name"].apply(clasificar_journey)

# -----------------------
# SIDEBAR
# -----------------------

st.sidebar.title("⚙️ Configuración")

creditos_totales = st.sidebar.number_input("Créditos totales", value=config["creditos_totales"])

creditos_unidad = {}
for unidad, valor in config["unidades"].items():
    creditos_unidad[unidad] = st.sidebar.number_input(unidad, value=valor)

map_creditos = {
    "mercadeo": creditos_unidad.get("MERCA", 0),
    "egresados": creditos_unidad.get("EGRES", 0),
    "donaciones": creditos_unidad.get("DONAC", 0),
}

# -----------------------
# FILTRO FECHA GLOBAL
# -----------------------

st.title("📊 Dashboard Créditos WhatsApp")

fecha_min = df["Send Date"].min()
fecha_max = df["Send Date"].max()

col1, col2 = st.columns(2)
fecha_inicio = col1.date_input("Fecha inicio", fecha_min)
fecha_fin = col2.date_input("Fecha fin", fecha_max)

df_filtrado = df[
    (df["Send Date"] >= pd.to_datetime(fecha_inicio)) &
    (df["Send Date"] <= pd.to_datetime(fecha_fin))
]

# -----------------------
# KPIs
# -----------------------

st.header("📌 Estatus Global")

total_consumido = df_filtrado["creditos"].sum() * FACTOR_AJUSTE
total_deliveries = df_filtrado["WhatsApp Deliveries"].sum()
restante = creditos_totales - total_consumido

dias = (pd.to_datetime(fecha_fin) - pd.to_datetime(fecha_inicio)).days + 1

consumo_diario = total_consumido / dias if dias > 0 else 0
deliveries_diario = total_deliveries / dias if dias > 0 else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("💳 Créditos consumidos", f"{total_consumido:,.0f}")
c2.metric("💰 Créditos restantes", f"{restante:,.0f}")
c3.metric("📦 Deliveries", f"{total_deliveries:,.0f}")
c4.metric("📈 % uso", f"{(total_consumido / creditos_totales)*100:.2f}%")

c5, c6 = st.columns(2)
c5.metric("📅 Consumo diario", f"{consumo_diario:,.0f}")
c6.metric("📨 Deliveries diarios", f"{deliveries_diario:,.0f}")

# -----------------------
# 🔮 PROYECCIONES GLOBALES
# -----------------------

st.subheader("🔮 Proyecciones")

colp1, colp2 = st.columns(2)

fecha_inicio_proj = colp1.date_input("Inicio histórico", fecha_fin - pd.Timedelta(days=28))
fecha_fin_proj = colp2.date_input("Fin histórico", fecha_fin)

df_proj = df[
    (df["Send Date"] >= pd.to_datetime(fecha_inicio_proj)) &
    (df["Send Date"] <= pd.to_datetime(fecha_fin_proj))
]

if not df_proj.empty:
    dias_proj = (pd.to_datetime(fecha_fin_proj) - pd.to_datetime(fecha_inicio_proj)).days + 1

    consumo_diario_proj = (df_proj["creditos"].sum() * FACTOR_AJUSTE) / dias_proj
    deliveries_diario_proj = df_proj["WhatsApp Deliveries"].sum() / dias_proj

    proy_creditos = consumo_diario_proj * 7
    proy_deliveries = deliveries_diario_proj * 7

    fecha_agotamiento = (
        pd.to_datetime(fecha_fin) + pd.Timedelta(days=(restante / consumo_diario_proj))
        if consumo_diario_proj > 0 else None
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("💳 Próxima semana", f"{proy_creditos:,.0f}")
    c2.metric("📦 Deliveries semana", f"{proy_deliveries:,.0f}")
    c3.metric("⏳ Agotamiento", fecha_agotamiento.strftime("%Y-%m-%d") if fecha_agotamiento else "N/A")

# -----------------------
# GRÁFICAS
# -----------------------

st.header("📊 Análisis General")

st.bar_chart(df_filtrado.groupby("unidad")["creditos"].sum() * FACTOR_AJUSTE)
st.line_chart(df_filtrado.groupby("mes")["creditos"].sum() * FACTOR_AJUSTE)
st.line_chart(df_filtrado.groupby("semana")["creditos"].sum() * FACTOR_AJUSTE)

# -----------------------
# SECCIÓN POR UNIDAD
# -----------------------

st.header("🏢 Análisis por Unidad")

for unidad in ["mercadeo", "egresados", "donaciones"]:
    st.subheader(f"Unidad: {unidad.upper()}")

    df_u = df_filtrado[df_filtrado["unidad"] == unidad]

    if df_u.empty:
        st.info("Sin datos")
        continue

    usados = df_u["creditos"].sum() * FACTOR_AJUSTE
    deliveries = df_u["WhatsApp Deliveries"].sum()
    asignados = map_creditos.get(unidad, 0)
    restantes = asignados - usados
    porcentaje = (usados / asignados * 100) if asignados > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💳 Usados", f"{usados:,.0f}")
    c2.metric("📊 Asignados", f"{asignados:,.0f}")
    c3.metric("💰 Restantes", f"{restantes:,.0f}")
    c4.metric("📈 % uso", f"{porcentaje:.2f}%")

    st.progress(min(porcentaje / 100, 1.0))
    st.metric("📦 Deliveries", f"{deliveries:,.0f}")

    st.line_chart(df_u.groupby("semana")["creditos"].sum() * FACTOR_AJUSTE)

    if unidad == "mercadeo":
        st.bar_chart(df_u.groupby("tipo_journey")["creditos"].sum() * FACTOR_AJUSTE)

# -----------------------
# 🎯 JOURNEYS PERSONALIZADOS
# -----------------------

st.header("🎯 Journeys específicos")

colf1, colf2 = st.columns(2)

filtro_inicio = colf1.date_input("Fecha inicio journeys", fecha_fin - pd.Timedelta(days=28))
filtro_fin = colf2.date_input("Fecha fin journeys", fecha_fin)

df_j_base = df[
    (df["Send Date"] >= pd.to_datetime(filtro_inicio)) &
    (df["Send Date"] <= pd.to_datetime(filtro_fin))
]

journeys_sel = st.multiselect("Selecciona journeys", df_j_base["Journey Name"].unique())

if journeys_sel:
    df_j = df_j_base[df_j_base["Journey Name"].isin(journeys_sel)]

    creditos_j = df_j["creditos"].sum() * FACTOR_AJUSTE
    deliveries_j = df_j["WhatsApp Deliveries"].sum()

    st.metric("💳 Créditos", f"{creditos_j:,.0f}")
    st.metric("📦 Deliveries", f"{deliveries_j:,.0f}")

    st.line_chart(df_j.groupby("semana")["creditos"].sum() * FACTOR_AJUSTE)

    # PROYECCIÓN
    st.subheader("🔮 Proyección Journeys")

    dias_j = (pd.to_datetime(filtro_fin) - pd.to_datetime(filtro_inicio)).days + 1

    consumo_diario_j = (creditos_j / dias_j) if dias_j > 0 else 0
    deliveries_diario_j = deliveries_j / dias_j if dias_j > 0 else 0

    proy_creditos_j = consumo_diario_j * 7
    proy_deliveries_j = deliveries_diario_j * 7

    creditos_restantes_j = st.number_input(
        "Créditos disponibles para estos journeys",
        value=float(creditos_j)
    )

    if consumo_diario_j > 0:
        dias_restantes_j = creditos_restantes_j / consumo_diario_j
        fecha_agotamiento_j = pd.to_datetime(filtro_fin) + pd.Timedelta(days=dias_restantes_j)
    else:
        fecha_agotamiento_j = None

    c1, c2, c3 = st.columns(3)
    c1.metric("💳 Próxima semana", f"{proy_creditos_j:,.0f}")
    c2.metric("📦 Deliveries", f"{proy_deliveries_j:,.0f}")
    c3.metric("⏳ Agotamiento", fecha_agotamiento_j.strftime("%Y-%m-%d") if fecha_agotamiento_j else "N/A")

# -----------------------
# DETALLE
# -----------------------

st.header("🔍 Detalle")
st.dataframe(df_filtrado)