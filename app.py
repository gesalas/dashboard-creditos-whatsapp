import streamlit as st
import pandas as pd
import numpy as np
import json
import altair as alt

st.set_page_config(layout="wide")

# -----------------------
# ESTILOS
# -----------------------

st.markdown(
    """
    <style>
    .section-header {
        background: linear-gradient(90deg, #002855 0%, #0056b3 100%);
        color: white;
        padding: 14px 22px;
        border-radius: 10px;
        margin: 30px 0 18px 0;
        font-size: 1.4rem;
        font-weight: 700;
        box-shadow: 0 3px 10px rgba(0,0,0,0.18);
        letter-spacing: 0.3px;
    }

    .subsection-header {
        border-left: 5px solid #0056b3;
        background: #f0f4f9;
        padding: 8px 14px;
        margin: 22px 0 12px 0;
        font-size: 1.08rem;
        font-weight: 600;
        color: #002855;
        border-radius: 0 6px 6px 0;
    }

    .unidad-header {
        background: #e8edf5;
        border: 1px solid #c9d6e8;
        padding: 10px 16px;
        margin: 26px 0 14px 0;
        border-radius: 8px;
        font-size: 1.15rem;
        font-weight: 700;
        color: #002855;
    }

    hr.section-divider {
        border: none;
        height: 3px;
        background: linear-gradient(90deg, #0056b3, rgba(0,86,179,0));
        margin: 34px 0 10px 0;
        border-radius: 3px;
    }

    .desglose-box {
        display: flex;
        gap: 12px;
        margin: -6px 0 18px 0;
        flex-wrap: wrap;
    }

    .desglose-item {
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.88rem;
        font-weight: 600;
    }

    .desglose-item.mkt {
        background: #e6f0ff;
        color: #0056b3;
        border: 1px solid #b8d4ff;
    }

    .desglose-item.uti {
        background: #fff2e0;
        color: #b96a00;
        border: 1px solid #ffd9a3;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def section_header(texto):
    st.markdown(f'<div class="section-header">{texto}</div>', unsafe_allow_html=True)


def subsection_header(texto):
    st.markdown(f'<div class="subsection-header">{texto}</div>', unsafe_allow_html=True)


def unidad_header(texto):
    st.markdown(f'<div class="unidad-header">{texto}</div>', unsafe_allow_html=True)


def section_divider():
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)


# -----------------------
# RECARGA MANUAL
# -----------------------

if st.button("🔄 Recargar datos"):
    st.cache_data.clear()

# -----------------------
# CARGA DE ARCHIVOS (todo se lee directamente del repositorio)
# -----------------------

@st.cache_data
def load_data():

    tarifas = pd.read_csv("tarifas.csv")

    with open("config.json") as f:
        config = json.load(f)

    df = pd.read_excel("data.xlsx")

    return tarifas, config, df


tarifas, config, df = load_data()

# -----------------------
# AJUSTE GLOBAL
# -----------------------

FACTOR_AJUSTE = 0.9448253844046506

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
# TIPO DE CONVERSACIÓN (Marketing / Utility)
# -----------------------

df["WhatsApp Conversation Type"] = (
    df["WhatsApp Conversation Type"]
    .astype(str)
    .str.upper()
    .str.strip()
)

df["es_utility"] = df["WhatsApp Conversation Type"] == "UTILITY"

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

# fallback OTHER (Marketing y Utility)

other_row = tarifas[tarifas["ISO"] == "OTHER"]

other_marketing = (
    other_row["Marketing"].values[0]
    if not other_row.empty else 0
)

other_utility = (
    other_row["Utility"].values[0]
    if not other_row.empty else 0
)

df["Marketing"] = df["Marketing"].fillna(other_marketing)
df["Utility"] = df["Utility"].fillna(other_utility)

# -----------------------
# MÉTRICAS BASE
# -----------------------

df["tarifa_aplicada"] = np.where(
    df["es_utility"],
    df["Utility"],
    df["Marketing"]
)

df["creditos"] = (
    df["WhatsApp Deliveries"] *
    df["tarifa_aplicada"]
)

df["creditos_marketing"] = np.where(
    df["es_utility"], 0, df["creditos"]
)

df["creditos_utility"] = np.where(
    df["es_utility"], df["creditos"], 0
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

df["semana_num"] = (
    df["Send Date"]
    .dt.isocalendar()
    .week
)

df["semana"] = (
    "Semana " +
    df["semana_num"].astype(str)
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
# HELPER DESGLOSE MARKETING / UTILITY
# -----------------------

def desglose_tipo(df_subset, factor=FACTOR_AJUSTE):
    """Devuelve (total, marketing, utility) ajustados por el factor."""
    marketing = df_subset["creditos_marketing"].sum() * factor
    utility = df_subset["creditos_utility"].sum() * factor
    total = marketing + utility
    return total, marketing, utility


def render_desglose(df_subset, factor=FACTOR_AJUSTE):
    total, marketing, utility = desglose_tipo(df_subset, factor)
    st.markdown(
        f"""
        <div class="desglose-box">
            <span class="desglose-item mkt">📣 Marketing: <b>{marketing:,.0f}</b></span>
            <span class="desglose-item uti">🔧 Utility: <b>{utility:,.0f}</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return total, marketing, utility


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

section_header("📌 Estatus Global")

total_consumido, marketing_consumido, utility_consumido = desglose_tipo(df_filtrado)

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
    "📈 % uso",
    f"{(total_consumido / creditos_totales)*100:.2f}%"
)

c3.metric(
    "💰 Créditos restantes",
    f"{restante:,.0f}"
)

c4.metric(
    "📅 Consumo de créditos diario",
    f"{consumo_diario:,.0f}"
)

render_desglose(df_filtrado)

c5, c6 = st.columns(2)

c5.metric(
    "📦 Deliveries",
    f"{total_deliveries:,.0f}"
)

c6.metric(
    "📨 Deliveries diarios",
    f"{deliveries_diario:,.0f}"
)

# -----------------------
# 🔮 PROYECCIONES
# -----------------------

subsection_header("🔮 Proyecciones")
st.caption("Establece un rango de fechas para realizar el cálculo")

colp1, colp2 = st.columns(2)

fecha_inicio_proj = colp1.date_input(
    "Fecha de Inicio",
    fecha_fin - pd.Timedelta(days=28)
)

fecha_fin_proj = colp2.date_input(
    "Fecha de Fin",
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

    total_proj, marketing_proj, utility_proj = desglose_tipo(df_proj)

    consumo_diario_proj = total_proj / dias_proj
    consumo_diario_proj_mkt = marketing_proj / dias_proj
    consumo_diario_proj_uti = utility_proj / dias_proj

    deliveries_diario_proj = (
        df_proj["WhatsApp Deliveries"].sum()
        / dias_proj
    )

    proy_creditos = consumo_diario_proj * 7
    proy_creditos_mkt = consumo_diario_proj_mkt * 7
    proy_creditos_uti = consumo_diario_proj_uti * 7

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

    st.markdown("**Proyección basada en el consumo del periodo seleccionado**")

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
        "⏳ Fecha de Agotamiento de Créditos",
        fecha_agotamiento.strftime("%Y-%m-%d")
        if fecha_agotamiento else "N/A"
    )

    st.markdown(
        f"""
        <div class="desglose-box">
            <span class="desglose-item mkt">📣 Marketing: <b>{proy_creditos_mkt:,.0f}</b></span>
            <span class="desglose-item uti">🔧 Utility: <b>{proy_creditos_uti:,.0f}</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

section_divider()

# -----------------------
# FUNCIÓN GRÁFICAS
# -----------------------

def grafica_barras(
    df_chart,
    x_col,
    y_col,
    titulo,
    sort_field=None
):

    df_chart = df_chart.copy()

    df_chart[y_col] = (
        df_chart[y_col]
        .fillna(0)
        .astype(float)
    )

    if sort_field:
        sort_value = alt.SortField(
            field=sort_field,
            order="ascending"
        )
    else:
        sort_value = "-y"

    base = alt.Chart(df_chart).encode(
        x=alt.X(
            x_col,
            sort=sort_value,
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
# TOP PAISES
# -----------------------

def top_paises(df_base, titulo):

    subsection_header(titulo)

    paises = (
        df_base
        .groupby("WhatsApp Country")["creditos"]
        .sum()
        .reset_index()
        .sort_values("creditos", ascending=False)
        .head(10)
    )

    paises["creditos"] = (
        paises["creditos"]
        * FACTOR_AJUSTE
    )

    grafica_barras(
        paises,
        "WhatsApp Country",
        "creditos",
        titulo
    )

# -----------------------
# ANÁLISIS GENERAL
# -----------------------

section_header("📊 Análisis General")

# -----------------------
# CONSUMO MENSUAL
# -----------------------

subsection_header("📅 Consumo mensual")

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
    "Consumo mensual del periodo seleccionado",
    sort_field="mes"
)

# -----------------------
# CONSUMO SEMANAL
# -----------------------

subsection_header("📆 Consumo semanal")

consumo_semana = (
    df_filtrado
    .groupby(["semana", "semana_num"])["creditos"]
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
    "Consumo semanal del periodo seleccionado",
    sort_field="semana_num"
)

# -----------------------
# CONSUMO POR UNIDAD
# -----------------------

subsection_header("🏢 Consumo por unidad")

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
    "Consumo por unidad en el periodo seleccionado"
)

# -----------------------
# TOP PAISES GENERAL
# -----------------------

top_paises(
    df_filtrado,
    "🌎 Países con mayor consumo en el periodo seleccionado"
)

section_divider()

# -----------------------
# SECCIÓN POR UNIDAD
# -----------------------

section_header("🏢 Análisis por Unidad")

for unidad in [
    "mercadeo",
    "egresados",
    "donaciones"
]:

    unidad_header(f"Unidad: {unidad.upper()}")

    df_u = df_filtrado[
        df_filtrado["unidad"] == unidad
    ]

    if df_u.empty:
        st.info("Sin datos")
        continue

    usados, usados_mkt, usados_uti = desglose_tipo(df_u)

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
        "💳 Créditos Usados",
        f"{usados:,.0f}"
    )

    c2.metric(
        "📊 Créditos estimados",
        f"{asignados:,.0f}"
    )

    c3.metric(
        "💰 Créditos Restantes",
        f"{restantes:,.0f}"
    )

    c4.metric(
        "📈 % uso",
        f"{porcentaje:.2f}%"
    )

    st.markdown(
        f"""
        <div class="desglose-box">
            <span class="desglose-item mkt">📣 Marketing: <b>{usados_mkt:,.0f}</b></span>
            <span class="desglose-item uti">🔧 Utility: <b>{usados_uti:,.0f}</b></span>
        </div>
        """,
        unsafe_allow_html=True,
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
        .groupby(["semana", "semana_num"])["creditos"]
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
        f"Consumo semanal - {unidad}",
        sort_field="semana_num"
    )

    top_paises(
        df_u,
        f"🌎 Países con mayor consumo - {unidad}"
    )

    if unidad == "mercadeo":

        subsection_header("📌 Clasificación de Journeys")

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

section_divider()

# -----------------------
# JOURNEYS
# -----------------------

section_header("🎯 Journeys específicos")

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

    creditos_j, creditos_j_mkt, creditos_j_uti = desglose_tipo(df_j)

    deliveries_j = (
        df_j["WhatsApp Deliveries"].sum()
    )

    c1, c2 = st.columns(2)

    c1.metric(
        "💳 Créditos consumidos",
        f"{creditos_j:,.0f}"
    )

    c2.metric(
        "📦 Deliveries",
        f"{deliveries_j:,.0f}"
    )

    render_desglose(df_j)

    semana_j = (
        df_j
        .groupby(["semana", "semana_num"])["creditos"]
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
        "Consumo semanal journeys",
        sort_field="semana_num"
    )

    top_paises(
        df_j,
        "🌎 Países con mayor consumo - Journeys"
    )

    # -----------------------
    # PROYECCIÓN JOURNEYS
    # -----------------------

    subsection_header("🔮 Proyección Journeys")

    dias_j = (
        pd.to_datetime(filtro_fin)
        -
        pd.to_datetime(filtro_inicio)
    ).days + 1

    consumo_diario_j = (
        creditos_j / dias_j
        if dias_j > 0 else 0
    )

    consumo_diario_j_mkt = (
        creditos_j_mkt / dias_j
        if dias_j > 0 else 0
    )

    consumo_diario_j_uti = (
        creditos_j_uti / dias_j
        if dias_j > 0 else 0
    )

    deliveries_diario_j = (
        deliveries_j / dias_j
        if dias_j > 0 else 0
    )

    proy_creditos_j = (
        consumo_diario_j * 7
    )

    proy_creditos_j_mkt = (
        consumo_diario_j_mkt * 7
    )

    proy_creditos_j_uti = (
        consumo_diario_j_uti * 7
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

    st.markdown(
        f"""
        <div class="desglose-box">
            <span class="desglose-item mkt">📣 Marketing: <b>{proy_creditos_j_mkt:,.0f}</b></span>
            <span class="desglose-item uti">🔧 Utility: <b>{proy_creditos_j_uti:,.0f}</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

section_divider()

# -----------------------
# DETALLE
# -----------------------

section_header("🔍 Detalle")

st.dataframe(df_filtrado)
