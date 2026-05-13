import streamlit as st
import pandas as pd
import json
import altair as alt

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

tarifas, config = load_tarifas_config()

# -----------------------
# UPLOADER EXCEL
# -----------------------

uploaded_file = st.file_uploader(
    "📂 Sube el archivo data.xlsx",
    type=["xlsx"]
)

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
else:
    st.warning("⚠️ Debes subir el archivo data.xlsx")
    st.stop()

# -----------------------
# AJUSTE GLOBAL
# -----------------------

FACTOR_AJUSTE = 0.9716314236

# -----------------------
# LIMPIEZA
# -----------------------

df.columns = df.columns.str.strip()

df["Journey Name"] = df["Journey Name"].fillna("SIN_NOMBRE")

df["WhatsApp Country"] = (
    df["WhatsApp Country"]
    .astype(str)
    .str.upper()
    .str.strip()
)

tarifas["ISO"] = (
    tarifas["ISO"]
    .astype(str)
    .str.upper()
    .str.strip()
)

# -----------------------
# FECHAS
# -----------------------

df["Send Date"] = pd.to_datetime(
    df["Send Date"],
    errors="coerce"
)

df = df[df["Send Date"].notna()]

# -----------------------
# MERGE TARIFAS
# -----------------------

df = df.merge(
    tarifas,
    left_on="WhatsApp Country",
    right_on="ISO",
    how="left"
)

# fallback OTHER

other_value = tarifas[
    tarifas["ISO"] == "OTHER"
]["Marketing"]

other_value = (
    other_value.values[0]
    if not other_value.empty else 0
)

df["Marketing"] = df["Marketing"].fillna(other_value)

# -----------------------
# MÉTRICAS BASE
# -----------------------

df["creditos"] = (
    df["WhatsApp Deliveries"] *
    df["Marketing"]
)

# -----------------------
# UNIDADES
# -----------------------

df["unidad_raw"] = (
    df["Journey Name"]
    .str.split("_")
    .str[0]
    .str.lower()
)

def map_unidad(x):

    if x == "egres":
        return "egresados"

    elif x == "donac":
        return "donaciones"

    else:
        return "mercadeo"

df["unidad"] = df["unidad_raw"].apply(map_unidad)

df["mes"] = (
    df["Send Date"]
    .dt.to_period("M")
    .astype(str)
)

df["semana"] = (
    df["Send Date"]
    .dt.isocalendar()
    .week
    .astype(str)
)

# -----------------------
# CLASIFICACIÓN
# -----------------------

def clasificar_journey(nombre):

    nombre = str(nombre).upper()

    if "ACCESO" in nombre:
        return "AUTOMATICO - ACCESO"

    elif (
        nombre.startswith("MERCA_FINANCIACION")
        or nombre.startswith("MERCA_MANTENIMIENTO")
    ):
        return "AUTOMATICO - FINANCIACION"

    elif "VISITAS_LOS_VIERNES" in nombre:
        return "AUTOMATICO - VISITAS"

    else:
        return "CAMPAÑA"

df["tipo_journey"] = (
    df["Journey Name"]
    .apply(clasificar_journey)
)

# -----------------------
# SIDEBAR
# -----------------------

st.sidebar.title("⚙️ Configuración")

creditos_totales = st.sidebar.number_input(
    "Créditos totales",
    value=config["creditos_totales"]
)

creditos_unidad = {}

for unidad, valor in config["unidades"].items():

    creditos_unidad[unidad] = (
        st.sidebar.number_input(
            unidad,
            value=valor
        )
    )

map_creditos = {
    "mercadeo": creditos_unidad.get("MERCA", 0),
    "egresados": creditos_unidad.get("EGRES", 0),
    "donaciones": creditos_unidad.get("DONAC", 0),
}

# -----------------------
# FILTRO GLOBAL
# -----------------------

st.title("📊 Dashboard Créditos WhatsApp")

fecha_min = df["Send Date"].min()
fecha_max = df["Send Date"].max()

col1, col2 = st.columns(2)

fecha_inicio = col1.date_input(
    "Fecha inicio",
    fecha_min
)

fecha_fin = col2.date_input(
    "Fecha fin",
    fecha_max
)

df_filtrado = df[
    (df["Send Date"] >= pd.to_datetime(fecha_inicio))
    &
    (df["Send Date"] <= pd.to_datetime(fecha_fin))
]

# -----------------------
# KPIS
# -----------------------

st.header("📌 Estatus Global")

total_consumido = (
    df_filtrado["creditos"].sum()
    * FACTOR_AJUSTE
)

total_deliveries = (
    df_filtrado["WhatsApp Deliveries"].sum()
)

restante = (
    creditos_totales - total_consumido
)

dias = (
    pd.to_datetime(fecha_fin)
    -
    pd.to_datetime(fecha_inicio)
).days + 1

consumo_diario = (
    total_consumido / dias
    if dias > 0 else 0
)

deliveries_diario = (
    total_deliveries / dias
    if dias > 0 else 0
)

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "💳 Créditos consumidos",
    f"{total_consumido:,.0f}"
)

c2.metric(
    "💰 Créditos restantes",
    f"{restante:,.0f}"
)

c3.metric(
    "📦 Deliveries",
    f"{total_deliveries:,.0f}"
)

c4.metric(
    "📈 % uso",
    f"{(total_consumido / creditos_totales)*100:.2f}%"
)

c5, c6 = st.columns(2)

c5.metric(
    "📅 Consumo diario",
    f"{consumo_diario:,.0f}"
)

c6.metric(
    "📨 Deliveries diarios",
    f"{deliveries_diario:,.0f}"
)

# -----------------------
# 🔮 PROYECCIONES
# -----------------------

st.subheader("🔮 Proyecciones")

colp1, colp2 = st.columns(2)

fecha_inicio_proj = colp1.date_input(
    "Inicio histórico",
    fecha_fin - pd.Timedelta(days=28)
)

fecha_fin_proj = colp2.date_input(
    "Fin histórico",
    fecha_fin
)

df_proj = df[
    (df["Send Date"] >= pd.to_datetime(fecha_inicio_proj))
    &
    (df["Send Date"] <= pd.to_datetime(fecha_fin_proj))
]

if not df_proj.empty:

    dias_proj = (
        pd.to_datetime(fecha_fin_proj)
        -
        pd.to_datetime(fecha_inicio_proj)
    ).days + 1

    consumo_diario_proj = (
        (
            df_proj["creditos"].sum()
            * FACTOR_AJUSTE
        )
        / dias_proj
    )

    deliveries_diario_proj = (
        df_proj["WhatsApp Deliveries"].sum()
        / dias_proj
    )

    proy_creditos = (
        consumo_diario_proj * 7
    )

    proy_deliveries = (
        deliveries_diario_proj * 7
    )

    fecha_agotamiento = (
        pd.to_datetime(fecha_fin)
        +
        pd.Timedelta(
            days=(
                restante /
                consumo_diario_proj
            )
        )
        if consumo_diario_proj > 0
        else None
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "💳 Créditos próxima semana",
        f"{proy_creditos:,.0f}"
    )

    c2.metric(
        "📦 Deliveries próxima semana",
        f"{proy_deliveries:,.0f}"
    )

    c3.metric(
        "⏳ Agotamiento",
        fecha_agotamiento.strftime("%Y-%m-%d")
        if fecha_agotamiento else "N/A"
    )

# -----------------------
# FUNCIÓN GRÁFICAS
# -----------------------

def grafica_barras(
    df_chart,
    x_col,
    y_col,
    titulo
):

    # evitar problemas con valores 0
    df_chart = df_chart.copy()

    df_chart[y_col] = (
        df_chart[y_col]
        .fillna(0)
        .astype(float)
    )

    base = alt.Chart(df_chart).encode(
        x=alt.X(
            x_col,
            sort="-y",
            axis=alt.Axis(labelAngle=0)
        ),
        y=alt.Y(
            y_col,
            title="Créditos"
        ),
        tooltip=[
            x_col,
            alt.Tooltip(
                y_col,
                format=",.0f"
            )
        ]
    )

    bars = base.mark_bar()

    text = base.mark_text(
        dy=-10,
        size=12
    ).encode(
        text=alt.Text(
            y_col,
            format=",.0f"
        )
    )

    final_chart = (
        bars + text
    ).properties(
        height=450,
        title=titulo
    )

    st.altair_chart(
        final_chart,
        use_container_width=True
    )

# -----------------------
# ANÁLISIS GENERAL
# -----------------------

st.header("📊 Análisis General")

# -----------------------
# CONSUMO MENSUAL
# -----------------------

st.subheader("📅 Consumo mensual")

consumo_mes = (
    df_filtrado
    .groupby("mes")["creditos"]
    .sum()
    .reset_index()
)

consumo_mes["creditos"] = (
    consumo_mes["creditos"]
    * FACTOR_AJUSTE
)

grafica_barras(
    consumo_mes,
    "mes",
    "creditos",
    "Consumo mensual"
)

# -----------------------
# CONSUMO SEMANAL
# -----------------------

st.subheader("📆 Consumo semanal")

consumo_semana = (
    df_filtrado
    .groupby("semana")["creditos"]
    .sum()
    .reset_index()
)

consumo_semana["creditos"] = (
    consumo_semana["creditos"]
    * FACTOR_AJUSTE
)

grafica_barras(
    consumo_semana,
    "semana",
    "creditos",
    "Consumo semanal"
)

# -----------------------
# CONSUMO POR UNIDAD
# -----------------------

st.subheader("🏢 Consumo por unidad")

consumo_unidad = (
    df_filtrado
    .groupby("unidad")["creditos"]
    .sum()
    .reset_index()
)

consumo_unidad["creditos"] = (
    consumo_unidad["creditos"]
    * FACTOR_AJUSTE
)

grafica_barras(
    consumo_unidad,
    "unidad",
    "creditos",
    "Consumo por unidad"
)

# -----------------------
# SECCIÓN POR UNIDAD
# -----------------------

st.header("🏢 Análisis por Unidad")

for unidad in [
    "mercadeo",
    "egresados",
    "donaciones"
]:

    st.subheader(
        f"Unidad: {unidad.upper()}"
    )

    df_u = df_filtrado[
        df_filtrado["unidad"] == unidad
    ]

    if df_u.empty:
        st.info("Sin datos")
        continue

    usados = (
        df_u["creditos"].sum()
        * FACTOR_AJUSTE
    )

    deliveries = (
        df_u["WhatsApp Deliveries"].sum()
    )

    asignados = (
        map_creditos.get(unidad, 0)
    )

    restantes = (
        asignados - usados
    )

    porcentaje = (
        (usados / asignados * 100)
        if asignados > 0 else 0
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "💳 Usados",
        f"{usados:,.0f}"
    )

    c2.metric(
        "📊 Asignados",
        f"{asignados:,.0f}"
    )

    c3.metric(
        "💰 Restantes",
        f"{restantes:,.0f}"
    )

    c4.metric(
        "📈 % uso",
        f"{porcentaje:.2f}%"
    )

    st.progress(
        min(porcentaje / 100, 1.0)
    )

    st.metric(
        "📦 Deliveries",
        f"{deliveries:,.0f}"
    )

    semana_unidad = (
        df_u
        .groupby("semana")["creditos"]
        .sum()
        .reset_index()
    )

    semana_unidad["creditos"] = (
        semana_unidad["creditos"]
        * FACTOR_AJUSTE
    )

    grafica_barras(
        semana_unidad,
        "semana",
        "creditos",
        f"Consumo semanal - {unidad}"
    )

    if unidad == "mercadeo":

        st.subheader(
            "📌 Clasificación de Journeys"
        )

        tipo_chart = (
            df_u
            .groupby("tipo_journey")["creditos"]
            .sum()
            .reset_index()
        )

        tipo_chart["creditos"] = (
            tipo_chart["creditos"]
            * FACTOR_AJUSTE
        )

        grafica_barras(
            tipo_chart,
            "tipo_journey",
            "creditos",
            "Clasificación journeys mercadeo"
        )

# -----------------------
# JOURNEYS
# -----------------------

st.header("🎯 Journeys específicos")

colf1, colf2 = st.columns(2)

filtro_inicio = colf1.date_input(
    "Fecha inicio journeys",
    fecha_fin - pd.Timedelta(days=28)
)

filtro_fin = colf2.date_input(
    "Fecha fin journeys",
    fecha_fin
)

df_j_base = df[
    (df["Send Date"] >= pd.to_datetime(filtro_inicio))
    &
    (df["Send Date"] <= pd.to_datetime(filtro_fin))
]

journeys_sel = st.multiselect(
    "Selecciona journeys",
    sorted(df_j_base["Journey Name"].unique())
)

if journeys_sel:

    df_j = df_j_base[
        df_j_base["Journey Name"]
        .isin(journeys_sel)
    ]

    creditos_j = (
        df_j["creditos"].sum()
        * FACTOR_AJUSTE
    )

    deliveries_j = (
        df_j["WhatsApp Deliveries"].sum()
    )

    c1, c2 = st.columns(2)

    c1.metric(
        "💳 Créditos",
        f"{creditos_j:,.0f}"
    )

    c2.metric(
        "📦 Deliveries",
        f"{deliveries_j:,.0f}"
    )

    semana_j = (
        df_j
        .groupby("semana")["creditos"]
        .sum()
        .reset_index()
    )

    semana_j["creditos"] = (
        semana_j["creditos"]
        * FACTOR_AJUSTE
    )

    grafica_barras(
        semana_j,
        "semana",
        "creditos",
        "Consumo semanal journeys"
    )

    # -----------------------
    # PROYECCIÓN JOURNEYS
    # -----------------------

    st.subheader("🔮 Proyección Journeys")

    dias_j = (
        pd.to_datetime(filtro_fin)
        -
        pd.to_datetime(filtro_inicio)
    ).days + 1

    consumo_diario_j = (
        creditos_j / dias_j
        if dias_j > 0 else 0
    )

    deliveries_diario_j = (
        deliveries_j / dias_j
        if dias_j > 0 else 0
    )

    proy_creditos_j = (
        consumo_diario_j * 7
    )

    proy_deliveries_j = (
        deliveries_diario_j * 7
    )

    creditos_restantes_j = (
        st.number_input(
            "Créditos disponibles para estos journeys",
            value=float(creditos_j)
        )
    )

    if consumo_diario_j > 0:

        dias_restantes_j = (
            creditos_restantes_j /
            consumo_diario_j
        )

        fecha_agotamiento_j = (
            pd.to_datetime(filtro_fin)
            +
            pd.Timedelta(
                days=dias_restantes_j
            )
        )

    else:
        fecha_agotamiento_j = None

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "💳 Créditos próxima semana",
        f"{proy_creditos_j:,.0f}"
    )

    c2.metric(
        "📦 Deliveries próxima semana",
        f"{proy_deliveries_j:,.0f}"
    )

    c3.metric(
        "⏳ Agotamiento",
        fecha_agotamiento_j.strftime("%Y-%m-%d")
        if fecha_agotamiento_j else "N/A"
    )

# -----------------------
# DETALLE
# -----------------------

st.header("🔍 Detalle")

st.dataframe(df_filtrado)