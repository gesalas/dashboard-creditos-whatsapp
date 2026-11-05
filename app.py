"""
Dashboard de créditos de WhatsApp (Marketing Cloud).

Ejecutar desde la carpeta del repositorio:
    streamlit run app.py

Toda la lógica de cálculo está en logica.py; este archivo solo filtra y muestra.
"""

from __future__ import annotations

import base64
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import acceso as A
import almacen
import logica as L
import sesion as S

CARPETA = Path(__file__).parent
RUTA_REPORTE = CARPETA / "data.xlsx"
CARPETA_TARIFAS = CARPETA / "tarifas"          # una tabla por vigencia (AAAA-MM-DD.csv)
RUTA_TARIFAS_UNICA = CARPETA / "tarifas.csv"    # respaldo si no existe la carpeta
RUTA_NOTAS_TARIFAS = CARPETA_TARIFAS / "notas.json"


def ruta_tarifas() -> Path:
    return CARPETA_TARIFAS if CARPETA_TARIFAS.is_dir() else RUTA_TARIFAS_UNICA
RUTA_CONFIG = CARPETA / "config.json"

CARPETA_ASSETS = CARPETA / "assets"


def buscar_imagen(*nombres: str) -> Path | None:
    """Primera imagen que exista en assets/ con alguno de esos nombres (png, jpg o svg)."""
    for nombre in nombres:
        for extension in (".png", ".jpg", ".jpeg", ".svg"):
            ruta = CARPETA_ASSETS / f"{nombre}{extension}"
            if ruta.exists():
                return ruta
    return None


NOMBRE_UNIDAD_APP = L.NOMBRE_UNIDAD   # unidades configuradas en config.json (se llena al leerlo)

RUTA_LOGO = buscar_imagen("logo_javeriana", "logo")
RUTA_ICONO = buscar_imagen("icono_whatsapp", "icono")

st.set_page_config(page_title="Créditos de WhatsApp", layout="wide", initial_sidebar_state="auto",
                   page_icon=str(RUTA_ICONO) if RUTA_ICONO else ":material/chat:")

# ---------------------------------------------------------------------------
# Estilo
# ---------------------------------------------------------------------------

COLOR_SERIE = "#2a78d6"          # serie única
COLOR_MARKETING = "#2a78d6"
COLOR_UTILITY = "#eb6834"
COLOR_TEXTO = "#1B1F24"
COLOR_TEXTO_SEC = "#52514e"
COLOR_GRILLA = "#E6E8EC"

# Semáforo: color de fondo, color de borde/texto y etiqueta (la etiqueta evita depender solo del color)
SEMAFORO = {
    "verde": {"fondo": "#E8F5EC", "borde": "#1E7B3C", "barra": "#2E9A4E", "etiqueta": "Normal"},
    "amarillo": {"fondo": "#FFF6DB", "borde": "#8A6100", "barra": "#D99A00", "etiqueta": "Atención"},
    "rojo": {"fondo": "#FDECEA", "borde": "#B3261E", "barra": "#D1372C", "etiqueta": "Crítico"},
    "sin_definir": {"fondo": "#F3F5F9", "borde": "#52514E", "barra": "#8C8C88", "etiqueta": "Sin asignación"},
}

st.markdown(
    """
    <style>
    .block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px;}
    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E3E7EE;
        border-radius: 10px;
        padding: 14px 16px 12px 16px;
    }
    [data-testid="stMetricLabel"] p {color: #52514e; font-size: 0.85rem;}
    [data-testid="stMetricValue"] {font-size: 1.65rem; font-weight: 600;}
    .stTabs [data-baseweb="tab-list"] {gap: 4px; border-bottom: 1px solid #E3E7EE;}
    .stTabs [data-baseweb="tab"] {padding: 8px 16px; font-weight: 500;}
    h1 {font-weight: 650; letter-spacing: -0.01em;}
    h3 {font-weight: 600; margin-top: 0.6rem;}
    .nota {color: #52514e; font-size: 0.88rem; margin: -0.4rem 0 0.8rem 0;}
    .semaforo {display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; margin: 0.6rem 0 1.2rem 0;}
    .semaforo-item {border-radius: 12px; padding: 16px 18px 14px 18px; border: 1px solid; border-left-width: 6px;}
    .semaforo-cabecera {display: flex; justify-content: space-between; align-items: center; gap: 8px;}
    .semaforo-titulo {font-size: 0.95rem; color: #1B1F24; font-weight: 600;}
    .semaforo-valor {font-size: 2.6rem; font-weight: 700; color: #1B1F24; line-height: 1.1; margin: 6px 0 10px 0;}
    .semaforo-valor small {display: block; white-space: nowrap; font-size: 0.85rem; font-weight: 500; color: #52514e;
                           margin: 2px 0 0 1px; line-height: 1.2;}
    .medidor {position: relative; height: 16px; background: #E3E7EE; border-radius: 999px; overflow: visible;}
    .medidor-relleno {height: 100%; border-radius: 999px;}
    .medidor-marca {position: absolute; top: -4px; bottom: -4px; width: 2px; background: #1B1F24; opacity: 0.55;}
    .medidor-escala {position: relative; height: 16px; font-size: 0.72rem; color: #52514e; margin: 3px 0 12px 0;}
    .medidor-escala span {position: absolute; transform: translateX(-50%); white-space: nowrap;}
    .semaforo-cifras {display: grid; grid-template-columns: 1fr 1fr; gap: 6px 12px; margin-top: 10px;}
    .cifra-etiqueta {font-size: 0.75rem; color: #52514e;}
    .cifra-valor {font-size: 1.05rem; font-weight: 650; color: #1B1F24;}
    .desglose {display: flex; gap: 8px; flex-wrap: wrap; margin: -4px 0 14px 0;}
    .chip {padding: 4px 12px; border-radius: 999px; font-size: 0.82rem; border: 1px solid;}
    .chip-mkt {background: #EAF2FC; color: #1C5CAB; border-color: #B7D3F6;}
    .chip-uti {background: #FDEEE6; color: #A8441A; border-color: #F6C8B2;}
    .subtitulo-bloque {font-size: 0.8rem; font-weight: 700; color: #52514e; letter-spacing: 0.05em;
                       text-transform: uppercase; margin: 6px 0 6px 0;}
    .subtitulo {display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 6px;}
    .frescura, .frescura-alerta, .pastilla {font-size: 0.82rem; border-radius: 999px; padding: 3px 10px;
                                            border: 1px solid #E3E7EE; background: #F3F5F9; color: #1B1F24;}
    .frescura {background: #E8F5EC; border-color: #B9DEC5; color: #1E7B3C; font-weight: 600;}
    .frescura-alerta {background: #FFF6DB; border-color: #F0D58A; color: #8A6100; font-weight: 600;}
    .leyenda {display: flex; flex-wrap: wrap; gap: 6px 16px; align-items: center; margin: 14px 0 2px 0;
              font-size: 0.85rem; color: #52514e;}
    .leyenda .insignia {margin-left: 0; margin-right: 4px;}
    .leyenda-titulo {font-weight: 700; color: #1B1F24;}
    .leyenda-nota {font-style: italic;}
    @media (max-width: 640px) {
        .titulo-texto {font-size: 1.75rem;}
        .titulo-icono img, .titulo-icono svg {width: 36px; height: 36px;}
        .semaforo-valor {font-size: 2.1rem;}
    }
    .semaforo-detalle .semaforo-cifras {grid-template-columns: 1fr 1fr;}
    .semaforo-detalle .semaforo-valor {font-size: 3rem;}
    .panel-unidades {border: 1px solid #E3E7EE; border-radius: 12px; padding: 14px 16px; background: #FFFFFF;
                     margin: 0.6rem 0 1rem 0;}
    .panel-titulo {font-size: 0.95rem; font-weight: 600; color: #1B1F24; margin-bottom: 8px;}
    .unidad-fila {padding: 10px 0; border-top: 1px solid #F0F2F6;}
    .unidad-fila:first-of-type {border-top: none;}
    .unidad-cabecera {display: flex; align-items: center; gap: 4px; margin-bottom: 6px;}
    .unidad-nombre {font-weight: 600; color: #1B1F24;}
    .unidad-pct {margin-left: auto; font-weight: 700; color: #1B1F24;}
    .unidad-detalle {font-size: 0.78rem; color: #52514e; margin-top: 6px;}
    .unidad-fila .medidor {height: 10px;}
    .unidad-fila .medidor-marca {top: -3px; bottom: -3px;}
    .franja-titulo {font-size: 0.8rem; font-weight: 700; color: #52514e; letter-spacing: 0.05em;
                    text-transform: uppercase; padding-top: 9px;}
    .titulo {display: flex; align-items: center; gap: 14px; margin: 0 0 4px 0;}
    .titulo-icono img, .titulo-icono svg {width: 46px; height: 46px; display: block;}
    .titulo-texto {font-size: 2.35rem; font-weight: 700; color: #1B1F24; letter-spacing: -0.01em; line-height: 1.15;}
    .insignia {display: inline-block; border-radius: 999px; padding: 2px 10px; font-size: 0.78rem;
               font-weight: 650; text-transform: uppercase; letter-spacing: 0.02em; margin-left: 8px;
               vertical-align: middle;}
    .titulo-tipo {font-size: 0.95rem; font-weight: 650; color: #1B1F24; padding: 2px 0 2px 10px;
                  border-left: 4px solid; margin: 14px 0 2px 0;}
    .tipo-mkt {border-color: #2a78d6;}
    .tipo-uti {border-color: #eb6834;}
    .tipo-mkt-texto {color: #1C5CAB;}
    .tipo-uti-texto {color: #A8441A;}
    [class*="st-key-caja-mkt"] {border: 2px solid #2a78d6 !important; border-radius: 12px;}
    [class*="st-key-caja-uti"] {border: 2px solid #eb6834 !important; border-radius: 12px;}
    [class*="st-key-caja-mkt"] [data-testid="stMetric"] {border-color: #9DC1EE;}
    [class*="st-key-caja-"] [data-testid="stMetricValue"] {font-size: 1.4rem;}
    [class*="st-key-caja-uti"] [data-testid="stMetric"] {border-color: #F4BBA0;}
    .cifra-valor small {font-size: 0.78rem; font-weight: 500; color: #52514e;}
    .cifra-sub {font-size: 0.8rem; font-weight: 500; color: #52514e;}
    .cifra-mkt {color: #1C5CAB; font-weight: 700; border-left: 3px solid #2a78d6; padding-left: 6px;}
    .cifra-uti {color: #A8441A; font-weight: 700; border-left: 3px solid #eb6834; padding-left: 6px;}
    .stTabs [data-baseweb="tab-list"] {position: sticky; top: 2.9rem; z-index: 5; background: var(--background-color, #FFFFFF);}
    [data-testid="stSidebar"] {background: #F4F6FA; border-right: 1px solid #E3E7EE;}
    [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {padding-top: 0.25rem;}
    .marca {background: linear-gradient(160deg, #1F3864 0%, #2C4F8C 100%); border-radius: 14px;
            padding: 18px 16px 14px 16px; margin: 0 0 14px 0; color: #FFFFFF; text-align: left;
            box-shadow: 0 6px 18px rgba(31, 56, 100, 0.18);}
    .marca-logo {background: #FFFFFF; border-radius: 10px; padding: 8px 10px; margin: 0 0 12px 0; display: inline-block;}
    .marca-logo img {max-height: 52px; max-width: 200px; display: block;}
    .marca-institucion {font-size: 1.02rem; font-weight: 700; line-height: 1.25;}
    .marca-area {font-size: 0.8rem; opacity: 0.8; margin-top: 3px;}
    .marca-producto {display: inline-flex; align-items: center; gap: 7px; font-size: 0.74rem; font-weight: 600;
                     margin-top: 12px; padding: 4px 10px; border-radius: 999px; background: rgba(255,255,255,0.12);
                     letter-spacing: 0.04em; text-transform: uppercase;}
    .marca-punto {width: 7px; height: 7px; border-radius: 50%; background: #3DDC84; display: inline-block;}
    [class*="st-key-lado-"] {background: #FFFFFF; border: 1px solid #E3E7EE; border-radius: 14px;
                             padding: 12px 12px 12px 12px; gap: 0.55rem; box-shadow: 0 1px 2px rgba(16,24,40,0.04);}
    .lado-titulo {display: flex; align-items: center; gap: 10px; font-size: 0.86rem; font-weight: 700;
                  color: #1B1F24; line-height: 1.2;}
    .lado-icono {font-family: "Material Symbols Rounded"; font-size: 18px; line-height: 1; color: #1F3864;
                 background: #EAF0FA; border-radius: 9px; padding: 6px; font-weight: normal;
                 font-variation-settings: "FILL" 0, "wght" 500;}
    .lado-sub {font-size: 0.74rem; font-weight: 500; color: #6B6F76; margin-top: 2px;}
    .lado-nota {font-size: 0.72rem; color: #6B6F76; line-height: 1.35;}
    [class*="st-key-lado-"] .stMarkdown [data-testid="stMarkdownContainer"] {margin-bottom: 0;}
    [class*="st-key-lado-linea"] [data-testid="stElementContainer"],
    [class*="st-key-lado-linea"] [data-testid="stRadio"],
    [class*="st-key-lado-linea"] [role="radiogroup"] {gap: 6px; width: 100% !important; display: flex; flex-direction: column;}
    [class*="st-key-lado-linea"] [role="radiogroup"] > div {box-sizing: border-box; align-self: stretch;}
    [class*="st-key-lado-linea"] [role="radiogroup"] > div {border: 1px solid #E3E7EE; border-radius: 10px;
                             padding: 7px 10px 7px 10px; width: 100%; background: #FFFFFF; transition: all .12s;}
    [class*="st-key-lado-linea"] [role="radiogroup"] > div:hover {border-color: #B9C6DC; background: #F8FAFD;}
    [class*="st-key-lado-linea"] [role="radiogroup"] > div[data-selected="true"] {border-color: #1F3864;
                             background: #EEF3FB; box-shadow: inset 3px 0 0 #1F3864;}
    [class*="st-key-lado-linea"] [data-testid="stRadioOption"] {width: 100%; margin: 0;}
    [class*="st-key-lado-linea"] [data-testid="stRadioOption"] p {font-weight: 600; color: #1B1F24; font-size: 0.88rem;}
    [class*="st-key-lado-linea"] [data-testid="stRadioCaption"] {margin: 0 0 0 1.75rem; padding: 0;}
    [class*="st-key-lado-linea"] [data-testid="stRadioCaption"] p {font-size: 0.72rem; color: #6B6F76; margin: 0;}
    .modo-pruebas {background: #FFF4E5; border: 1px solid #E8A33D; color: #7A4B00; border-radius: 8px;
      padding: 8px 10px; font-size: 0.78rem; font-weight: 600; line-height: 1.35; margin-bottom: 10px;}
    .modo-pruebas-ancho {font-size: 0.85rem; padding: 8px 14px;}
    .periodo-resuelto {display: flex; justify-content: space-between; align-items: center; font-size: 0.82rem;
                       color: #1B1F24; background: #F4F6FA; border-radius: 8px; padding: 7px 10px; margin: 0;}
    .periodo-resuelto b {font-weight: 650; color: #1F3864;}
    .dato-fila {display: flex; justify-content: space-between; gap: 10px; font-size: 0.78rem; padding: 6px 0;
                border-bottom: 1px dashed #E8EBF0; color: #6B6F76;}
    .dato-fila:last-of-type {border-bottom: none;}
    .dato-fila b {color: #1B1F24; font-weight: 600; text-align: right; display: inline-flex; align-items: center; gap: 6px;}
    .punto-ok, .punto-alerta {width: 7px; height: 7px; border-radius: 50%; display: inline-block;}
    .punto-ok {background: #2E9A4E;}
    .punto-alerta {background: #D99A00;}
    [data-testid="stSidebar"] [data-testid="stExpander"] details {background: #FFFFFF; border-radius: 14px;}
    [class*="st-key-zona-canal"] {background: #FFFFFF; border: 1px solid #E3E7EE; border-radius: 14px;
                                  padding: 14px 16px 12px 16px; margin: 10px 0 6px 0; gap: 0.35rem;
                                  box-shadow: 0 1px 3px rgba(16,24,40,0.05);}
    .zona-etiqueta {font-size: 0.78rem; font-weight: 700; color: #52514e; letter-spacing: 0.05em;
                    text-transform: uppercase; margin: 2px 0 2px 2px;}
    .zona-nota {font-size: 0.78rem; color: #6B6F76; margin: 0 0 2px 2px;}
    [class*="st-key-zona-canal"] [role="radiogroup"] {gap: 10px; flex-wrap: wrap;}
    [class*="st-key-zona-canal"] button[data-variant="segmented_control"] {
        border: 1.5px solid #C9D3E3 !important; border-radius: 12px !important; background: #FFFFFF;
        padding: 10px 20px; min-height: 46px; box-shadow: 0 1px 2px rgba(16,24,40,0.06); transition: all .12s;}
    [class*="st-key-zona-canal"] button[data-variant="segmented_control"] p {font-size: 1rem; font-weight: 600;
                                                                             color: #1B1F24;}
    [class*="st-key-zona-canal"] button[data-variant="segmented_control"]:hover {border-color: #1F3864 !important;
                                                                                 background: #F3F6FB;}
    [class*="st-key-zona-canal"] button[data-variant="segmented_control"][aria-checked="true"] {
        background: #1F3864; border-color: #1F3864 !important; box-shadow: 0 3px 8px rgba(31,56,100,0.25);}
    [class*="st-key-zona-canal"] button[data-variant="segmented_control"][aria-checked="true"] p,
    [class*="st-key-zona-canal"] button[data-variant="segmented_control"][aria-checked="true"] span {color: #FFFFFF;}
    [class*="st-key-linea"] button[data-variant="segmented_control"] {min-height: 40px; padding: 7px 16px;}
    [class*="st-key-zona-canal"] .stMarkdown [data-testid="stMarkdownContainer"] {margin-bottom: 0;}
    [class*="st-key-zona-canal"] button[data-variant="segmented_control"][aria-checked="true"]:hover {
        background: #2C4F8C; border-color: #2C4F8C !important;}
    [class*="st-key-linea"] button[data-variant="segmented_control"] p {font-size: 0.93rem;}
    .barra-canales {display: flex; height: 26px; border-radius: 8px; overflow: hidden; background: #E3E7EE;
                    margin: 6px 0 8px 0;}
    .barra-canales .seg {height: 100%;}
    .leyenda-canales {display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 0.85rem; color: #52514e;
                      margin-bottom: 14px;}
    .leyenda-canales i {display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px;}
    .leyenda-canales b {color: #1B1F24;}
    .cifra-grande {font-size: 1.9rem; font-weight: 700; color: #1B1F24; margin: 2px 0 0 0;}
    .cifra-grande small {font-size: 0.95rem; font-weight: 500; color: #52514e;}
    .canal-pendiente {background: #F8F9FB; border-left-width: 6px; min-height: 170px;}
    .pendiente-texto {font-size: 0.88rem; color: #52514e; margin-top: 14px; line-height: 1.45;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Formato
# ---------------------------------------------------------------------------

def num(valor: float) -> str:
    """Número con separador de miles colombiano (punto)."""
    return f"{valor:,.0f}".replace(",", ".")


def pct(valor: float, decimales: int = 1) -> str:
    return f"{valor * 100:.{decimales}f} %".replace(".", ",")


def imagen_html(ruta: Path, alt: str) -> str:
    """Imagen local embebida en base64 para poder usarla dentro de HTML."""
    tipo = "image/svg+xml" if ruta.suffix.lower() == ".svg" else f"image/{ruta.suffix.lower().lstrip('.').replace('jpg', 'jpeg')}"
    datos = base64.b64encode(ruta.read_bytes()).decode("ascii")
    return f'<img src="data:{tipo};base64,{datos}" alt="{alt}">'


# Ícono genérico de chat (se usa si no hay un ícono en assets/)
ICONO_CHAT = (
    '<svg viewBox="0 0 48 48" role="img" aria-label="Mensajería">'
    '<rect width="48" height="48" rx="12" fill="#1E9E57"/>'
    '<path d="M14 13h20a5 5 0 0 1 5 5v11a5 5 0 0 1-5 5H23l-7 6v-6h-2a5 5 0 0 1-5-5V18a5 5 0 0 1 5-5z" fill="#FFFFFF"/>'
    '<circle cx="17.5" cy="23.5" r="2.2" fill="#1E9E57"/><circle cx="24" cy="23.5" r="2.2" fill="#1E9E57"/>'
    '<circle cx="30.5" cy="23.5" r="2.2" fill="#1E9E57"/></svg>')


def nota(texto: str) -> None:
    st.markdown(f'<p class="nota">{texto}</p>', unsafe_allow_html=True)


def medidor(uso: float | None, estado: str, amarillo_pct: float, rojo_pct: float, escala: bool = True) -> str:
    """Barra de progreso del consumo, del color del estado, con marcas en los umbrales."""
    color = SEMAFORO[estado]["barra"]
    ancho = 0 if uso is None else max(0.0, min(uso * 100, 100.0))
    marcas = "".join(f'<div class="medidor-marca" style="left:calc({u}% - 1px);"></div>'
                     for u in (amarillo_pct, rojo_pct) if 0 < u < 100)
    html = (f'<div class="medidor" role="progressbar" aria-valuenow="{ancho:.0f}" aria-valuemin="0" aria-valuemax="100">'
            f'<div class="medidor-relleno" style="width:{ancho:.2f}%; background:{color};"></div>{marcas}</div>')
    if escala:
        etiquetas = "".join(f'<span style="left:{u}%;">{u:g} %</span>' for u in (amarillo_pct, rojo_pct) if 0 < u < 100)
        html += f'<div class="medidor-escala"><span style="left:0; transform:none;">0 %</span>{etiquetas}</div>'
    return html


def tarjeta_semaforo(titulo: str, estado: str, uso: float | None, cifras: list[tuple],
                     amarillo_pct: float, rojo_pct: float, etiqueta_uso: str = "usado a la fecha") -> str:
    """Tarjeta de estado. Cada cifra es (etiqueta, valor) o (etiqueta, valor, "mkt" | "uti")."""
    fondo, borde = SEMAFORO[estado]["fondo"], SEMAFORO[estado]["borde"]
    valor = pct(uso) if uso is not None else "-"
    extra = f"<small>{etiqueta_uso}</small>" if uso is not None else ""
    celdas = "".join(
        f'<div><div class="cifra-etiqueta{" cifra-" + c[2] if len(c) > 2 else ""}">{c[0]}</div>'
        f'<div class="cifra-valor">{c[1]}</div></div>' for c in cifras)
    return (f'<div class="semaforo-item" style="background:{fondo}; border-color:{borde};">'
            f'<div class="semaforo-cabecera"><div class="semaforo-titulo">{titulo}</div>{insignia(estado)}</div>'
            f'<div class="semaforo-valor">{valor}{extra}</div>'
            f'{medidor(uso, estado, amarillo_pct, rojo_pct)}'
            f'<div class="semaforo-cifras">{celdas}</div></div>')


def insignia(estado: str) -> str:
    fondo, borde, etiqueta = (SEMAFORO[estado][k] for k in ("fondo", "borde", "etiqueta"))
    return (f'<span class="insignia" style="background:{fondo}; color:{borde}; '
            f'border:1px solid {borde};">{etiqueta}</span>')


COLOR_TARIFA = "#8A6100"   # línea de cambio de tarifa en las gráficas


def etiqueta_semana(fecha: pd.Timestamp) -> str:
    """Igual que la columna "semana" de los datos: "S44 · 26/10"."""
    lunes = (fecha - pd.Timedelta(days=fecha.weekday())).normalize()
    return f"S{fecha.isocalendar()[1]:02d} · {lunes:%d/%m}"


def marcas_tarifa(por: str) -> list[tuple[str, str]]:
    """Categorías (semana o mes) en que empezó a regir una tabla de tarifas nueva."""
    if por not in ("semana", "mes"):
        return []
    marcas = []
    for f in L.vigencias(tarifas)[1:]:
        cat = etiqueta_semana(f) if por == "semana" else nombre_mes(f"{f:%Y-%m}")
        marcas.append((cat, f"Tarifa {f:%d/%m}"))
    return marcas


EJE_NUMERO = "replace(format(datum.value, ',.0f'), regexp(',', 'g'), '.')"
TIPOS = ("Marketing", "Utility")
COLOR_TIPO = {"Marketing": COLOR_MARKETING, "Utility": COLOR_UTILITY}
CLASE_TIPO = {"Marketing": "mkt", "Utility": "uti"}
NOMBRE_MEDIDA = {"creditos": "Créditos", "deliveries": "Entregas"}


def _config_grafica(chart: alt.Chart, altura: int) -> alt.Chart:
    return (chart.properties(height=altura or "auto")
                 .configure_view(strokeWidth=0)
                 .configure_axis(labelColor=COLOR_TEXTO_SEC, titleColor=COLOR_TEXTO_SEC,
                                 gridColor=COLOR_GRILLA, domainColor=COLOR_GRILLA, tickColor=COLOR_GRILLA,
                                 labelFontSize=12, titleFontSize=12, titleFontWeight="normal")
                 .configure_title(color=COLOR_TEXTO, fontSize=14, anchor="start", fontWeight=600))


def grafica_barras(datos: pd.DataFrame, categoria: str, valor: str, *, horizontal: bool = False,
                   orden: str | list | None = None, titulo_valor: str = "Créditos",
                   altura: int | None = None, color: str = COLOR_SERIE,
                   dominio_max: float | None = None, estrecho: bool = False,
                   marcas: list[tuple[str, str]] | None = None) -> None:
    """Barras de una sola serie con el valor escrito sobre cada barra.

    `marcas`: [(categoría, texto)] para dibujar una línea vertical punteada (por ejemplo, cambios de tarifa).

    `estrecho`: la gráfica va en media pantalla (comparativo), así que las etiquetas se giran antes.

    `dominio_max` fija el máximo del eje (para comparar dos gráficas con la misma escala).
    """
    if datos.empty:
        st.info("Sin datos para el periodo seleccionado.")
        return
    datos = datos.copy()
    datos["_etiqueta"] = datos[valor].apply(num)
    n = len(datos)
    maximo = float(dominio_max if dominio_max is not None else datos[valor].max()) or 1.0
    orden_eje = orden if orden is not None else ("-x" if horizontal else "-y")
    limite = 8 if estrecho else 16
    eje_cat = (alt.Axis(title=None, labelLimit=420, labelAngle=0) if horizontal or n <= limite
               else alt.Axis(title=None, labelAngle=-90, labelOverlap=False, labelFontSize=11 if n <= 30 else 9))
    eje_val = alt.Axis(title=titulo_valor, labelExpr=EJE_NUMERO, tickCount=5)
    if horizontal:
        escala = alt.Scale(domain=[0, maximo * 1.16])
        x = alt.X(f"{valor}:Q", axis=eje_val, scale=escala)
        y = alt.Y(f"{categoria}:N", sort=orden_eje, axis=eje_cat)
        texto_kw = {"align": "left", "baseline": "middle", "dx": 4, "fontSize": 11}
        altura = altura or max(150, 30 * n + 60)
    else:
        rotar = n > limite   # con muchas barras el valor va vertical para que no se monte sobre el de al lado
        escala = alt.Scale(domain=[0, maximo * (1.28 if rotar else 1.14)])
        x = alt.X(f"{categoria}:N", sort=orden_eje, axis=eje_cat)
        y = alt.Y(f"{valor}:Q", axis=eje_val, scale=escala)
        texto_kw = ({"angle": 270, "align": "left", "baseline": "middle", "dx": 4,
                     "fontSize": 10 if n <= 30 or not estrecho else 8} if rotar
                    else {"baseline": "bottom", "dy": -4, "fontSize": 11})
        altura = altura or 330
    base = alt.Chart(datos).encode(
        x=x, y=y,
        tooltip=[alt.Tooltip(f"{categoria}:N", title=" "), alt.Tooltip("_etiqueta:N", title=titulo_valor)],
    )
    barras = base.mark_bar(color=color, cornerRadiusEnd=3)
    textos = base.mark_text(color=COLOR_TEXTO, **texto_kw).encode(text="_etiqueta:N")
    capa = barras + textos
    presentes = set(datos[categoria])
    marcas = [(c, t) for c, t in (marcas or []) if c in presentes]
    if marcas and not horizontal:
        m = pd.DataFrame([{categoria: c, "_txt": t} for c, t in marcas])
        x_m = alt.X(f"{categoria}:N", sort=orden_eje, bandPosition=0, axis=eje_cat)
        capa = (capa + alt.Chart(m).mark_rule(color=COLOR_TARIFA, strokeDash=[5, 4], strokeWidth=1.6).encode(x=x_m)
                + alt.Chart(m).mark_text(align="left", baseline="top", dx=4, fontSize=10, fontWeight=600,
                                         color=COLOR_TARIFA).encode(x=x_m, y=alt.value(2), text="_txt:N"))
    st.altair_chart(_config_grafica(capa, altura), width="stretch")


def titulo_tipo(tipo: str, texto: str = "") -> None:
    """Rótulo de una gráfica, con el color del tipo de mensaje."""
    st.markdown(f'<div class="titulo-tipo tipo-{CLASE_TIPO[tipo]}">{tipo}'
                f'{" · " + texto if texto else ""}</div>', unsafe_allow_html=True)


def grafica_tipo(datos: pd.DataFrame, categoria: str, tipo: str, *, medida: str = "creditos",
                 orden: str | list | None = None, horizontal: bool = False, top: int | None = None,
                 altura: int | None = None, dominio_max: float | None = None, estrecho: bool = False,
                 marcas: list[tuple[str, str]] | None = None) -> None:
    """Gráfica de un solo tipo de mensaje (Marketing o Utility), en créditos o en entregas."""
    columna = f"{medida}_{tipo.lower()}"
    if datos.empty or float(datos[columna].sum()) <= 0:
        st.info(f"Sin consumo de {tipo} en este periodo.", icon=":material/info:")
        return
    vista = datos[[categoria, columna]]
    if top:
        vista = vista[vista[columna] > 0].nlargest(top, columna)
    grafica_barras(vista, categoria, columna, horizontal=horizontal, orden=orden,
                   titulo_valor=f"{NOMBRE_MEDIDA[medida]} {tipo}", color=COLOR_TIPO[tipo],
                   altura=altura, dominio_max=dominio_max, estrecho=estrecho, marcas=marcas)


MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def nombre_mes(periodo_mes: str) -> str:
    """'2026-04' -> 'Abr 2026'."""
    anio, mes = str(periodo_mes).split("-")[:2]
    return f"{MESES[int(mes) - 1]} {anio}"


def agrupar(datos: pd.DataFrame, por: str) -> tuple[pd.DataFrame, list | None]:
    """Suma las métricas por mes, semana u otra columna. Devuelve la tabla y el orden del eje
    (cronológico para mes y semana; None = de mayor a menor)."""
    if por == "semana":
        tabla_s = (datos.groupby(["semana_inicio", "semana"], as_index=False)[L.METRICAS].sum()
                   .sort_values("semana_inicio"))
        return tabla_s.drop(columns="semana_inicio"), list(tabla_s["semana"])
    tabla_p = datos.groupby(por, as_index=False)[L.METRICAS].sum()
    if por == "unidad":
        tabla_p["unidad"] = tabla_p["unidad"].map(NOMBRE_UNIDAD_APP)
    if por == "mes":
        tabla_p = tabla_p.sort_values("mes")
        tabla_p["mes"] = tabla_p["mes"].apply(nombre_mes)
        return tabla_p, list(tabla_p["mes"])
    return tabla_p, None


def graficas_por_tipo(datos: pd.DataFrame, por: str, medida: str, *, horizontal: bool = False,
                      top: int | None = None, texto: str = "") -> None:
    """Una gráfica de Marketing y debajo una de Utility, a lo ancho."""
    tabla_g, orden = agrupar(datos, por)
    for tipo in TIPOS:
        titulo_tipo(tipo, texto or NOMBRE_MEDIDA[medida])
        grafica_tipo(tabla_g, por, tipo, medida=medida, orden=orden, horizontal=horizontal, top=top,
                     marcas=marcas_tarifa(por))


def graficas_versus(datos_por_linea: dict[str, pd.DataFrame], por: str, medida: str, *,
                    horizontal: bool = False, top: int | None = None) -> None:
    """Comparativo UCP vs Outbound: una fila para Marketing y otra para Utility, cada línea en su
    columna y con la misma escala para que las barras se puedan comparar."""
    tablas = {}
    for nombre_l, datos_l in datos_por_linea.items():
        tablas[nombre_l] = agrupar(datos_l, por)
    # Mismas categorías en las dos columnas (semanas o meses), con cero donde una línea no tuvo consumo
    if por in ("semana", "mes"):
        todas = pd.concat([t for t, _ in tablas.values()])
        if por == "semana":
            orden_c = list(agrupar(pd.concat(datos_por_linea.values()), "semana")[1])
        else:
            orden_c = list(agrupar(pd.concat(datos_por_linea.values()), "mes")[1])
        for nombre_l, (t, _) in tablas.items():
            t = t.set_index(por).reindex(orden_c, fill_value=0).reset_index()
            tablas[nombre_l] = (t, orden_c)
    for tipo in TIPOS:
        columna = f"{medida}_{tipo.lower()}"
        maximos = [float(t[columna].max()) for t, _ in tablas.values() if not t.empty]
        dominio = max(maximos) if maximos and max(maximos) > 0 else None
        cols = st.columns(len(tablas))
        for col, (nombre_l, (t, orden)) in zip(cols, tablas.items()):
            with col:
                titulo_tipo(tipo, f"{nombre_l} · {NOMBRE_MEDIDA[medida]}")
                grafica_tipo(t, por, tipo, medida=medida, orden=orden, horizontal=horizontal, top=top,
                             dominio_max=dominio, estrecho=True, marcas=marcas_tarifa(por))


def selector_medida(clave: str) -> str:
    medida = st.segmented_control("Medir en", ["creditos", "deliveries"], default="creditos", key=clave,
                                  format_func=lambda m: NOMBRE_MEDIDA[m],
                                  help="Créditos muestra el costo; Entregas muestra cuántos mensajes recibieron "
                                       "las personas (WhatsApp cobra por mensaje entregado).")
    return medida or "creditos"


def cajas_por_tipo(t: dict, clave: str, *, apilado: bool = False) -> None:
    """Cajas de Marketing y Utility (créditos, entregas y créditos por entrega), con borde de su color."""
    cols = [st.container() for _ in TIPOS] if apilado else st.columns(2)
    for col, tipo in zip(cols, TIPOS):
        sufijo = tipo.lower()
        with col.container(border=True, key=f"caja-{CLASE_TIPO[tipo]}-{clave}"):
            cred, ent = t[f"creditos_{sufijo}"], t[f"deliveries_{sufijo}"]
            st.markdown(f'<div class="subtitulo-bloque tipo-{CLASE_TIPO[tipo]}-texto">{tipo}</div>',
                        unsafe_allow_html=True)
            k1, k2, k3 = st.columns([1.3, 1.1, 1.15])
            k1.metric("Créditos", num(cred),
                      help=f"{pct(cred / t['creditos']) if t['creditos'] else '-'} de los créditos del periodo")
            k2.metric("Entregas", num(ent),
                      help=f"{pct(ent / t['deliveries']) if t['deliveries'] else '-'} de las entregas del periodo")
            k3.metric("Por entrega", f"{cred / ent:.2f}".replace(".", ",") if ent else "-")


def desglose(mkt: float, uti: float, sufijo: str = "créditos") -> str:
    """Etiquetas Marketing / Utility debajo de una cifra."""
    return (f'<div class="desglose"><span class="chip chip-mkt">Marketing: <b>{num(mkt)}</b> {sufijo}</span>'
            f'<span class="chip chip-uti">Utility: <b>{num(uti)}</b> {sufijo}</span></div>')


def tabla(datos: pd.DataFrame, columnas: dict[str, str], *, enteros: list[str] = (),
          porcentajes: list[str] = (), altura: int | None = None) -> None:
    """Muestra un dataframe con nombres en español y formato numérico local."""
    vista = datos[list(columnas)].rename(columns=columnas)
    config_t = {}
    for c in enteros:
        vista[columnas[c]] = vista[columnas[c]].round(0).astype("int64")
        config_t[columnas[c]] = st.column_config.NumberColumn(format="localized")
    for c in porcentajes:
        vista[columnas[c]] = (vista[columnas[c]] * 100).round(1)
        config_t[columnas[c]] = st.column_config.NumberColumn(format="%.1f %%")
    st.dataframe(vista, column_config=config_t, hide_index=True, width="stretch", height=altura or "auto")


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------

def _marcas_archivos() -> tuple:
    """Fecha de modificación de los archivos: si cambian, se recargan los datos solos."""
    archivos = [RUTA_REPORTE, RUTA_CONFIG, RUTA_TARIFAS_UNICA]
    if CARPETA_TARIFAS.is_dir():
        archivos += sorted(CARPETA_TARIFAS.iterdir())
    return tuple((p.name, p.stat().st_mtime if p.exists() else 0) for p in archivos)


@st.cache_data(show_spinner="Cargando datos...")
def cargar_datos(_marcas: tuple):
    config = L.leer_config(RUTA_CONFIG)   # primero: define las unidades con las que se clasifica
    reporte, generado = L.leer_reporte(RUTA_REPORTE)
    tarifas = L.leer_tarifas(ruta_tarifas())
    envios = L.preparar_envios(reporte, tarifas)
    notas = {}
    if RUTA_NOTAS_TARIFAS.exists():
        with open(RUTA_NOTAS_TARIFAS, encoding="utf-8") as f:
            notas = json.load(f)
    return envios, config, generado, tarifas, notas


try:
    envios, config, generado, tarifas, notas_tarifas = cargar_datos(_marcas_archivos())
    L.configurar_unidades(config)   # por si los datos vinieron de la caché
except FileNotFoundError as error:
    st.error(f"No se encontró el archivo {Path(error.filename).name} en la carpeta del repositorio.")
    st.stop()
except ValueError as error:
    st.error(str(error))
    st.stop()


# ---------------------------------------------------------------------------
# Acceso: quién está viendo y qué unidades puede ver
# ---------------------------------------------------------------------------

marca = {"institucion": "Pontificia Universidad Javeriana", "area": "DTI · Equipo CRM",
         "producto": "Créditos de WhatsApp"}
marca.update(config.get("marca", {}))


def responsables_unidades() -> dict:
    try:
        datos = json.loads((CARPETA / "alertas.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return (datos.get("unidades", {}) or {}).get("responsables", {}) or {}


_logo_acceso = imagen_html(RUTA_LOGO, marca["institucion"]) if RUTA_LOGO else ""
CTX = S.puerta({u: L.NOMBRE_UNIDAD[u] for u in L.UNIDADES}, responsables_unidades(), marca, _logo_acceso)
QUIEN = CTX["correo"]


def subir_y_registrar(evento: str, detalle: str, *rutas: Path) -> None:
    """Después de guardar un archivo de configuración: lo anota en la bitácora y, en el enlace publicado,
    lo sube a GitHub (si no, se perdería al reiniciarse la app)."""
    A.registrar(evento, QUIEN, detalle)
    for ruta in rutas:
        try:
            almacen.subir_archivo(ruta, f"{evento} ({QUIEN})")
        except almacen.ErrorAlmacen as error:
            st.session_state["aviso_subida"] = f"Se guardó, pero no se pudo subir {ruta.name} a GitHub: {error}"


# ---------------------------------------------------------------------------
# Periodos
# ---------------------------------------------------------------------------

OPCIONES_PERIODO = ["Todo hasta la fecha", "Últimos 7 días", "Últimos 30 días", "Este mes",
                    "Mes anterior", "Este año", "Próximos 30 días (estimado)", "Hasta fin de año (estimado)",
                    "Personalizado"]
DIAS_FUTURO_MAX = 730   # hasta cuántos días después del último dato se puede consultar (estimado)


def resolver_periodo(opcion: str, fmin: date, fmax: date, personalizado) -> tuple[date, date, str | None]:
    """Fechas de inicio y fin para una opción de periodo. Las opciones relativas se cuentan
    hasta el último día con datos (fmax), no hasta hoy, para que siempre muestren datos."""
    aviso = None
    if opcion == "Últimos 7 días":
        ini, fi = fmax - pd.Timedelta(days=6), fmax
    elif opcion == "Últimos 30 días":
        ini, fi = fmax - pd.Timedelta(days=29), fmax
    elif opcion == "Este mes":
        ini, fi = fmax.replace(day=1), fmax
    elif opcion == "Mes anterior":
        fi = fmax.replace(day=1) - pd.Timedelta(days=1)
        ini = fi.replace(day=1)
    elif opcion == "Este año":
        ini, fi = fmax.replace(month=1, day=1), fmax
    elif opcion == "Próximos 30 días (estimado)":
        ini, fi = fmax + pd.Timedelta(days=1), fmax + pd.Timedelta(days=30)
    elif opcion == "Hasta fin de año (estimado)":
        ini, fi = fmin, date(fmax.year, 12, 31)
    elif opcion == "Personalizado":
        if isinstance(personalizado, (tuple, list)) and len(personalizado) == 2:
            ini, fi = personalizado
        else:
            ini, fi = fmin, fmax
            aviso = "Elige la fecha de inicio y la de fin. Mientras tanto se muestra todo hasta la fecha."
    else:
        ini, fi = fmin, fmax
    limite = (pd.Timestamp(fmax) + pd.Timedelta(days=DIAS_FUTURO_MAX)).date()
    ini, fi = max(pd.Timestamp(ini).date(), fmin), min(pd.Timestamp(fi).date(), limite)
    if ini > fi:
        ini, fi = fmin, fmax
        aviso = "Ese periodo no es válido. Se muestra todo hasta la fecha."
    return ini, fi, aviso


OPCIONES_REFERENCIA = {"Últimos 7 días": 7, "Últimos 14 días": 14, "Últimos 28 días": 28,
                       "Últimos 56 días": 56, "Últimos 90 días": 90, "Periodo consultado": None,
                       "Fechas personalizadas": "personalizado"}


def selector_referencia(contenedor, clave: str, fin_datos: pd.Timestamp, inicio_periodo: pd.Timestamp,
                        fin_periodo: pd.Timestamp, minimo: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Periodo cuyo ritmo de consumo se usa para proyectar (rápido o con fechas propias)."""
    opcion = contenedor.selectbox(
        "Proyectar con el ritmo de", list(OPCIONES_REFERENCIA), index=2, key=clave,
        help="Se toma el promedio diario de entregas de este periodo y se proyecta hacia adelante con las "
             "tarifas que rijan cada día. Los últimos 28 días suelen reflejar mejor el ritmo actual; con "
             "fechas personalizadas se puede usar, por ejemplo, el ritmo de un evento o campaña anterior.")
    dias = OPCIONES_REFERENCIA[opcion]
    if dias is None:
        return inicio_periodo, fin_periodo
    if dias == "personalizado":
        defecto = (max(minimo, fin_datos - pd.Timedelta(days=27)).date(), fin_datos.date())
        fechas = contenedor.date_input("Fechas de referencia", value=defecto, min_value=minimo.date(),
                                       max_value=fin_datos.date(), format="DD/MM/YYYY", key=f"{clave}_fechas",
                                       help="Primer y último día cuyo ritmo de consumo se quiere usar. Se incluyen los dos.")
        if isinstance(fechas, (tuple, list)) and len(fechas) == 2:
            return pd.Timestamp(fechas[0]), pd.Timestamp(fechas[1])
        contenedor.caption("Elige también la fecha final. Mientras tanto se usan los últimos 28 días.")
        return max(fin_datos - pd.Timedelta(days=27), minimo), fin_datos
    return max(fin_datos - pd.Timedelta(days=dias - 1), minimo), fin_datos


# ---------------------------------------------------------------------------
# Créditos: compras por línea y asignación a unidades (pestaña Configuración)
# ---------------------------------------------------------------------------

LINEAS_COMPRA = L.LINEAS_COMPRA          # UCP y Outbound: bolsas separadas
FILAS_UNIDADES = [f"{NOMBRE_UNIDAD_APP[u]} ({L.CLAVE_CONFIG_UNIDAD[u]})" for u in L.UNIDADES]


def tabla_unidades(config: dict) -> pd.DataFrame:
    datos = {"Unidad": FILAS_UNIDADES}
    for linea_c in LINEAS_COMPRA:
        datos[linea_c] = [L.config_linea(config, linea_c)["unidades"][u] for u in L.UNIDADES]
    return pd.DataFrame(datos)


def aplicar_ediciones(base: pd.DataFrame, estado: dict | None) -> pd.DataFrame:
    """Aplica los cambios de la tabla editable (guardados por Streamlit en session_state)."""
    tabla_c = base.copy()
    for fila, cambios in ((estado or {}).get("edited_rows", {}) or {}).items():
        for columna, valor in cambios.items():
            if columna in LINEAS_COMPRA:
                tabla_c.at[tabla_c.index[int(fila)], columna] = float(valor or 0)
    return tabla_c


COL_PRECIO = "Precio por 1.000 (USD)"


def tabla_compras(config: dict) -> pd.DataFrame:
    filas = []
    for c in config.get("compras", []) or []:
        fecha_c = pd.to_datetime(c.get("fecha"), errors="coerce")
        filas.append({"Fecha": fecha_c.date() if pd.notna(fecha_c) else None,
                      "Línea": c.get("linea") if c.get("linea") in LINEAS_COMPRA else None,
                      "Créditos": float(c.get("creditos") or 0),
                      COL_PRECIO: float(c["precio_usd_1000"]) if c.get("precio_usd_1000") else None,
                      "Nota": str(c.get("nota") or "")})
    return pd.DataFrame(filas, columns=["Fecha", "Línea", "Créditos", COL_PRECIO, "Nota"])


def aplicar_ediciones_compras(base: pd.DataFrame, estado: dict | None) -> pd.DataFrame:
    """Aplica filas editadas, agregadas y borradas de la tabla de compras."""
    estado = estado or {}
    tabla_c = base.copy()
    for fila, cambios in (estado.get("edited_rows", {}) or {}).items():
        for columna, valor in cambios.items():
            tabla_c.at[tabla_c.index[int(fila)], columna] = valor
    borradas = [tabla_c.index[int(i)] for i in (estado.get("deleted_rows", []) or []) if int(i) < len(tabla_c)]
    tabla_c = tabla_c.drop(index=borradas)
    nuevas = [f for f in (estado.get("added_rows", []) or []) if f]
    if nuevas:
        tabla_c = pd.concat([tabla_c, pd.DataFrame(nuevas)], ignore_index=True)
    tabla_c["Créditos"] = pd.to_numeric(tabla_c["Créditos"], errors="coerce").fillna(0.0)
    tabla_c["Nota"] = tabla_c["Nota"].fillna("").astype(str)
    tabla_c[COL_PRECIO] = pd.to_numeric(tabla_c.get(COL_PRECIO), errors="coerce")
    tabla_c["Fecha"] = pd.to_datetime(tabla_c["Fecha"], errors="coerce").dt.date
    return tabla_c.reset_index(drop=True)


compras_guardadas = tabla_compras(config)
compras_vigentes = aplicar_ediciones_compras(compras_guardadas, st.session_state.get("editor_compras"))
unidades_guardadas = tabla_unidades(config)
unidades_vigentes = aplicar_ediciones(unidades_guardadas, st.session_state.get("editor_unidades"))
compras_sin_linea = compras_vigentes[~compras_vigentes["Línea"].isin(LINEAS_COMPRA) & (compras_vigentes["Créditos"] > 0)]

presupuestos = {}
for _l in LINEAS_COMPRA:
    if len(compras_vigentes) and not L.compras_con_linea(config) and not st.session_state.get("editor_compras"):
        adquirido_l = L.config_linea(config, _l)["creditos_totales"]   # formato anterior, sin línea en las compras
    else:
        adquirido_l = float(compras_vigentes.loc[compras_vigentes["Línea"] == _l, "Créditos"].sum())
    presupuestos[_l] = {"creditos_totales": adquirido_l,
                        "unidades": dict(zip(L.UNIDADES, [float(v) for v in unidades_vigentes[_l]]))}
presupuestos["Ambas líneas"] = {
    "creditos_totales": sum(presupuestos[l]["creditos_totales"] for l in LINEAS_COMPRA),
    "unidades": {u: sum(presupuestos[l]["unidades"][u] for l in LINEAS_COMPRA) for u in L.UNIDADES},
}


def adquirido_al(nombre_linea: str, hasta: pd.Timestamp | None) -> float:
    """Créditos comprados para una línea (o ambas) con fecha de compra hasta `hasta` (None = todas)."""
    if L.LINEAS.get(nombre_linea) is None:
        return sum(adquirido_al(l, hasta) for l in LINEAS_COMPRA)
    if hasta is None or not L.compras_con_linea(config) and not st.session_state.get("editor_compras"):
        return presupuestos[nombre_linea]["creditos_totales"]
    filas = compras_vigentes[compras_vigentes["Línea"] == nombre_linea]
    fechas = pd.to_datetime(filas["Fecha"], errors="coerce")
    return float(filas.loc[fechas.isna() | (fechas <= hasta), "Créditos"].sum())


# Dinero: precio por 1.000 créditos de cada canal (editable en Todos los canales → Configuración) y, en
# WhatsApp, el precio promedio de cada bolsa según sus compras (cada compra puede tener su propio precio).
PRECIOS = L.precios_canal(config)
PRECIOS_OK = L.precios_confirmados(config)


def precio_linea(nombre_linea: str) -> float | None:
    """USD por 1.000 créditos de la bolsa de una línea de WhatsApp."""
    compras_l = [{"linea": r["Línea"], "creditos": r["Créditos"], "precio_usd_1000": r[COL_PRECIO]}
                 for _, r in compras_vigentes.iterrows()]
    return L.precio_promedio(compras_l, nombre_linea, PRECIOS["whatsapp"])


PRECIO_LINEA = {l: precio_linea(l) for l in LINEAS_COMPRA}


def usd_de(datos: pd.DataFrame, columna: str = "creditos") -> float | None:
    """Dólares de unas entregas de WhatsApp, cada una con el precio de la bolsa de su línea."""
    if datos.empty:
        return 0.0
    total, alguno = 0.0, False
    for l, grupo in datos.groupby("linea"):
        precio = PRECIO_LINEA.get(l)
        if precio is not None:
            total += float(grupo[columna].sum()) * precio / 1000
            alguno = True
    return total if alguno else None


def usd_creditos(creditos: float, nombre_linea: str) -> float | None:
    if L.LINEAS.get(nombre_linea) is None:
        return None
    precio = PRECIO_LINEA.get(nombre_linea)
    return None if precio is None else creditos * precio / 1000


def txt_usd(valor: float | None, signo: bool = False) -> str:
    if valor is None:
        return "sin precio"
    return ("-" if valor < 0 and signo else "") + f"US$ {num(abs(valor) if signo else valor)}"


ESTIMADO_USD = "" if PRECIOS_OK.get("whatsapp") else " (estimado)"


def txt_precio(valor: float | None) -> str:
    return "-" if valor is None else f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


_ed_compras = st.session_state.get("editor_compras") or {}
hay_cambios = (not unidades_vigentes[LINEAS_COMPRA].round(0).equals(unidades_guardadas[LINEAS_COMPRA].round(0))
               or any(bool(_ed_compras.get(k)) for k in ("edited_rows", "added_rows", "deleted_rows")))


# ---------------------------------------------------------------------------
# Barra lateral: qué ver
# ---------------------------------------------------------------------------

VISTAS = (["crm"] if CTX["admin"] else []) + [u for u in L.UNIDADES if u in CTX["unidades"]]
NOMBRE_VISTA = {"crm": "Equipo CRM (todo)", **NOMBRE_UNIDAD_APP}
VISTAS_LINEA = ["Ambas líneas", "UCP vs Outbound", "UCP", "Outbound"]
ETIQUETA_LINEA = {"Ambas líneas": "Ambas líneas (total)", "UCP vs Outbound": "UCP vs Outbound (comparar)",
                  "UCP": f"UCP ({L.LINEAS['UCP']})", "Outbound": f"Outbound ({L.LINEAS['Outbound']})"}

# La vista se puede abrir directo desde un enlace: ...?unidad=mercadeo (solo si esa persona puede verla)
if st.session_state.get("vista") not in (None, *VISTAS):
    st.session_state["vista"] = VISTAS[0]
if "vista" not in st.session_state:
    pedida = str(st.query_params.get("unidad", "")).lower().strip()
    st.session_state["vista"] = pedida if pedida in VISTAS else VISTAS[0]

def titulo_lado(icono: str, titulo: str, subtitulo: str = "") -> None:
    """Encabezado de una sección de la barra lateral (ícono de Material Symbols + título)."""
    st.markdown(f'<div class="lado-titulo"><span class="lado-icono">{icono}</span><div><div>{titulo}</div>'
                f'{f"<div class=lado-sub>{subtitulo}</div>" if subtitulo else ""}</div></div>',
                unsafe_allow_html=True)


SUBTITULO_LINEA = {"Ambas líneas": "Suma de UCP y Outbound", "UCP vs Outbound": "Las dos líneas lado a lado",
                   "UCP": L.LINEAS["UCP"], "Outbound": L.LINEAS["Outbound"]}

with st.sidebar:
    logo_html = f'<div class="marca-logo">{imagen_html(RUTA_LOGO, marca["institucion"])}</div>' if RUTA_LOGO else ""
    st.markdown(
        f'<div class="marca">{logo_html}'
        f'<div class="marca-institucion">{marca["institucion"]}</div>'
        f'<div class="marca-area">{marca["area"]}</div>'
        f'<div class="marca-producto"><span class="marca-punto"></span>{marca["producto"]}</div></div>',
        unsafe_allow_html=True)
    S.bloque_lateral(CTX)

    with st.container(key="lado-vista"):
        titulo_lado("visibility", "Vista", "Todo el Equipo CRM o una sola unidad" if CTX["admin"] else
                    ("Tus unidades" if len(VISTAS) > 1 else "Tu unidad"))
        vista = st.selectbox("Vista", VISTAS, key="vista", format_func=lambda v: NOMBRE_VISTA[v],
                             label_visibility="collapsed", disabled=len(VISTAS) == 1)
    unidad_sel = None if vista == "crm" else vista
    if unidad_sel:
        st.query_params["unidad"] = unidad_sel
    elif "unidad" in st.query_params:
        del st.query_params["unidad"]


    fecha_min = envios["fecha"].min().date()
    fecha_max = envios["fecha"].max().date()
    with st.container(key="lado-periodo"):
        titulo_lado("calendar_month", "Periodo a consultar", "Filtra lo usado en esas fechas")
        opcion_periodo = st.selectbox("Periodo a consultar", OPCIONES_PERIODO, index=0, key="opcion_periodo",
                                      label_visibility="collapsed")
        personalizado = None
        if opcion_periodo == "Personalizado":
            personalizado = st.date_input("Fechas", value=(max(fecha_min, fecha_max - pd.Timedelta(days=6)), fecha_max),
                                          min_value=fecha_min,
                                          max_value=fecha_max + pd.Timedelta(days=DIAS_FUTURO_MAX),
                                          format="DD/MM/YYYY", key="periodo_personalizado",
                                          label_visibility="collapsed")
            st.caption(f"Puedes elegir una fecha final después del {fecha_max:%d/%m/%Y} (último dato): "
                       "lo que pase de ese día es un estimado.")
        ini_d, fin_d, aviso_periodo = resolver_periodo(opcion_periodo, fecha_min, fecha_max, personalizado)
        inicio, fin = pd.Timestamp(ini_d), pd.Timestamp(fin_d)
        futuro = fin_d > fecha_max                         # el periodo llega a fechas sin datos: parte estimada
        fin_real = min(fin, pd.Timestamp(fecha_max))       # último día del periodo con datos reales
        dias_periodo = max((fin_real - inicio).days + 1, 0)   # días con datos reales (para promedios)
        dias_totales = (fin - inicio).days + 1
        filtrado = ini_d > fecha_min or fin_d != fecha_max
        if aviso_periodo:
            st.caption(aviso_periodo)
        st.markdown(f'<div class="periodo-resuelto"><span>{inicio:%d/%m/%Y} – {fin:%d/%m/%Y}</span>'
                    f'<b>{dias_totales} {"día" if dias_totales == 1 else "días"}</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="lado-nota">Las tarjetas de estado muestran cómo estaban los créditos el '
                    f'{fin:%d/%m/%Y}'
                    + (f'; después del {fecha_max:%d/%m/%Y} es un estimado con el ritmo de los últimos 28 días.'
                       if futuro else '.') + '</div>', unsafe_allow_html=True)

    fechas_tarifas = L.vigencias(tarifas)
    texto_tarifas = (f"{len(fechas_tarifas)} tablas · última {fechas_tarifas[-1]:%d/%m/%Y}"
                     if fechas_tarifas[-1] != pd.Timestamp.min else "tabla única")
    generado_ts = pd.to_datetime(generado, errors="coerce") if generado else pd.NaT
    generado_txt = f"{generado_ts:%d/%m/%Y %H:%M} UTC" if pd.notna(generado_ts) else (generado or "sin fecha")
    atraso = (date.today() - fecha_max).days
    clase_punto = "punto-alerta" if atraso > 7 else "punto-ok"
    texto_atraso = "hoy" if atraso <= 0 else ("hace 1 día" if atraso == 1 else f"hace {atraso} días")
    with st.container(key="lado-datos"):
        titulo_lado("database", "Datos")
        st.markdown(
            f'<div class="dato-fila"><span>Último dato</span><b><i class="{clase_punto}"></i>'
            f'{fecha_max:%d/%m/%Y}</b></div>'
            f'<div class="dato-fila"><span>Antigüedad</span><b>{texto_atraso}</b></div>'
            f'<div class="dato-fila"><span>Desde</span><b>{fecha_min:%d/%m/%Y}</b></div>'
            f'<div class="dato-fila"><span>Reporte</span><b>{generado_txt}</b></div>'
            f'<div class="dato-fila"><span>Tarifas</span><b>{texto_tarifas}</b></div>',
            unsafe_allow_html=True)
        if st.button("Recargar datos", width="stretch", icon=":material/refresh:",
                     help="Vuelve a leer data.xlsx, las tarifas y config.json. Úsalo después de reemplazar el reporte."):
            st.cache_data.clear()
            st.rerun()

    with st.expander("Cómo leer este tablero", icon=":material/help:"):
        st.markdown(
            "- **Crédito:** unidad con la que se cobran los mensajes. Cada mensaje consume créditos según el "
            "país del destinatario y el tipo de mensaje.\n"
            "- **Entrega:** mensaje que le llegó a la persona (en el reporte, *deliveries*). WhatsApp cobra por "
            "entrega, no por envío.\n"
            "- **Marketing (azul) / Utility (naranja):** tipos de mensaje. Utility (confirmaciones, "
            "recordatorios) es mucho más barato que Marketing.\n"
            "- **Créditos adquiridos:** los comprados para cada línea. UCP y Outbound son bolsas separadas.\n"
            "- **Créditos asignados:** la parte de los créditos de una línea que corresponde a una unidad.\n"
            "- **Vista:** Equipo CRM ve todo; cada unidad puede ver solo lo suyo.\n"
            "- **Canales:** WhatsApp, Correo y SMS tienen cada uno su bolsa de créditos y sus tarifas. "
            "«Todos los canales» los compara en dólares (con el precio por 1.000 créditos de Configuración) "
            "y en entregas.\n"
            "- **Estado:** todo lo consumido frente a los créditos adquiridos o asignados. Normal, Atención "
            "o Crítico según el porcentaje usado.\n"
            "- **Periodo a consultar:** filtra lo usado en esas fechas; no cambia los disponibles ni el estado.\n"
            "- **Agotamiento estimado:** fecha en que se acabarían los créditos si se sigue al ritmo de los "
            "últimos 28 días, con las tarifas que rijan cada día.")


if "aviso_subida" in st.session_state:
    st.warning(st.session_state.pop("aviso_subida"), icon=":material/cloud_off:")
if CTX["pruebas"]:
    st.markdown('<div class="modo-pruebas modo-pruebas-ancho">MODO PRUEBAS · No es el tablero publicado: aquí no '
                'se pide iniciar sesión, tienes permisos del Equipo CRM y los cambios se guardan solo en esta '
                'carpeta.</div>', unsafe_allow_html=True)
if S.pagina_actual(CTX, {u: L.NOMBRE_UNIDAD[u] for u in L.UNIDADES}, responsables_unidades()):
    st.stop()


# ---------------------------------------------------------------------------
# Canal (arriba) y línea de WhatsApp
# ---------------------------------------------------------------------------

CANALES = list(L.CANALES)                      # whatsapp, correo, sms
OPCIONES_CANAL = ["todos"] + CANALES
NOMBRE_CANAL = {"todos": "Todos los canales", **L.CANALES}
COLOR_CANAL = {"whatsapp": "#128C7E", "correo": "#7B4FBF", "sms": "#5B6B7F"}
CANALES_CONECTADOS = {"whatsapp"}              # correo y SMS: falta su reporte y sus tarifas

if st.session_state.get("canal") not in OPCIONES_CANAL:
    pedido = str(st.query_params.get("canal", "")).lower().strip()
    st.session_state["canal"] = pedido if pedido in OPCIONES_CANAL else "whatsapp"
if st.session_state.get("linea_guardada") not in VISTAS_LINEA:
    st.session_state["linea_guardada"] = "Ambas líneas"

zona_titulo = st.container()
zona_canal = st.container(key="zona-canal")
ICONO_CANAL = {"todos": ":material/dashboard:", "whatsapp": ":material/forum:", "correo": ":material/mail:",
               "sms": ":material/sms:"}
ICONO_LINEA = {"Ambas líneas": ":material/join:", "UCP vs Outbound": ":material/compare_arrows:",
               "UCP": ":material/call:", "Outbound": ":material/campaign:"}


def telefono(numero: str) -> str:
    """573102190903 -> +57 310 219 0903."""
    n = str(numero)
    return f"+{n[:2]} {n[2:5]} {n[5:8]} {n[8:]}" if len(n) == 12 else n


with zona_canal:
    st.markdown('<div class="zona-etiqueta">¿Qué canal quieres ver?</div>', unsafe_allow_html=True)
    canal = st.segmented_control("Canal", OPCIONES_CANAL, key="canal",
                                 format_func=lambda c: f"{ICONO_CANAL[c]} {NOMBRE_CANAL[c]}",
                                 label_visibility="collapsed") or "whatsapp"
    st.query_params["canal"] = canal
    if canal == "whatsapp":
        if st.session_state.get("linea") not in VISTAS_LINEA:
            st.session_state["linea"] = st.session_state["linea_guardada"]
        st.markdown('<div class="zona-etiqueta">Línea de WhatsApp</div>', unsafe_allow_html=True)
        vista_linea = st.segmented_control(
            "Línea de WhatsApp", VISTAS_LINEA, key="linea", label_visibility="collapsed",
            format_func=lambda v: f"{ICONO_LINEA[v]} {v}") or "Ambas líneas"
        st.markdown(f'<div class="zona-nota">UCP y Outbound son los dos números de WhatsApp de la universidad '
                    f'(UCP: {telefono(L.LINEAS["UCP"])} · Outbound: {telefono(L.LINEAS["Outbound"])}), cada uno '
                    f'con su propia bolsa de créditos.</div>', unsafe_allow_html=True)
        st.session_state["linea_guardada"] = vista_linea
    else:
        vista_linea = "Ambas líneas"
versus = vista_linea == "UCP vs Outbound"
linea = "Ambas líneas" if versus else vista_linea   # línea de los datos (el comparativo usa las dos)


def filtrar(datos: pd.DataFrame, nombre_linea: str = "Ambas líneas", unidad: str | None = None) -> pd.DataFrame:
    """Datos de una línea (o ambas) y una unidad (o todas)."""
    if L.LINEAS.get(nombre_linea) is not None:
        datos = datos[datos["linea"] == nombre_linea]
    if unidad:
        datos = datos[datos["unidad"] == unidad]
    return datos


def en_periodo(datos: pd.DataFrame) -> pd.DataFrame:
    return datos[(datos["fecha"] >= inicio) & (datos["fecha"] <= fin)]


envios_ambito = filtrar(envios, linea, unidad_sel)   # todo el consumo de lo que se está viendo
periodo = en_periodo(envios_ambito)
nombre_ambito = NOMBRE_UNIDAD_APP[unidad_sel] if unidad_sel else "todas las unidades"
texto_linea = {"Ambas líneas": "ambas líneas", "UCP vs Outbound": "UCP y Outbound"}.get(vista_linea,
                                                                                       f"la línea {vista_linea}")
texto_ambito = f"{nombre_ambito} en {texto_linea}"


# ---------------------------------------------------------------------------
# Encabezado
# ---------------------------------------------------------------------------

icono_html = imagen_html(RUTA_ICONO, "WhatsApp") if RUTA_ICONO else ICONO_CHAT
dias_desde = (date.today() - fecha_max).days
frescura = ("hoy" if dias_desde <= 0 else "hace 1 día" if dias_desde == 1 else f"hace {dias_desde} días")
clase_frescura = "frescura-alerta" if dias_desde > 7 else "frescura"
with zona_titulo:
    st.markdown(
        f'<div class="titulo"><div class="titulo-icono">{icono_html}</div>'
        f'<div><div class="titulo-texto">Créditos de mensajería'
        f'{" · " + NOMBRE_UNIDAD_APP[unidad_sel] if unidad_sel else ""}</div>'
        f'<div class="subtitulo">'
        f'<span class="{clase_frescura}">Datos de WhatsApp al {fecha_max:%d/%m/%Y} · {frescura}</span>'
        f'<span class="pastilla">{"Unidad " + NOMBRE_UNIDAD_APP[unidad_sel] if unidad_sel else "Equipo CRM"}</span>'
        f'<span class="pastilla">Periodo: {inicio:%d/%m/%Y} – {fin:%d/%m/%Y}</span>'
        f'</div></div></div>', unsafe_allow_html=True)
    if dias_desde > 7:
        st.warning(f"El reporte llega hasta el {fecha_max:%d/%m/%Y} ({frescura}). El consumo real puede ser mayor: "
                   "exporta un reporte nuevo de Marketing Cloud y reemplaza data.xlsx.", icon=":material/schedule:")
    if hay_cambios:
        st.info("Estás viendo compras o asignaciones de créditos editadas que aún no se han guardado. "
                "Guárdalas o descártalas en WhatsApp → Créditos.", icon=":material/edit:")

if canal == "whatsapp":
    nombres_tabs = (["Resumen", "Proyección", "Journeys", "Detalle"] if unidad_sel else
                    ["Resumen", "Proyección", "Unidades", "Journeys", "Detalle", "Créditos"])
elif canal == "todos":
    nombres_tabs = ["Resumen"] if unidad_sel else ["Resumen", "Configuración"]
else:
    nombres_tabs = []
tabs = dict(zip(nombres_tabs, st.tabs(nombres_tabs))) if nombres_tabs else {}
tabs_todos = tabs if canal == "todos" else {}
if canal != "whatsapp":
    tabs = {}   # las secciones de WhatsApp no se dibujan


# ---------------------------------------------------------------------------
# Estado de los créditos (todo el consumo; no depende del periodo consultado)
# ---------------------------------------------------------------------------

cfg_semaforo = L.config_semaforo(config)
amarillo_pct, rojo_pct = cfg_semaforo["amarillo_pct"], cfg_semaforo["rojo_pct"]
base_semaforo = envios
if cfg_semaforo.get("fecha_inicio_conteo"):
    base_semaforo = envios[envios["fecha"] >= pd.Timestamp(cfg_semaforo["fecha_inicio_conteo"])]
desde_txt = (f"desde el {pd.Timestamp(cfg_semaforo['fecha_inicio_conteo']):%d/%m/%Y}"
             if cfg_semaforo.get("fecha_inicio_conteo") else "todo el consumo registrado")
fin_datos = envios["fecha"].max()
minimo_datos = envios["fecha"].min()


def ir_a_linea(nombre: str) -> None:
    st.session_state["linea"] = nombre


def ir_a_vista(nombre: str) -> None:
    st.session_state["vista"] = nombre


REF_DIAS = 28   # ritmo con el que se estima el consumo de fechas futuras en las tarjetas


def estado_de(nombre_linea: str, unidad: str | None = None) -> dict:
    """Estado de una línea (o de una unidad dentro de ella) al último día del periodo consultado.

    - Si ese día es pasado: lo consumido hasta ese día frente a lo adquirido hasta ese día.
    - Si es futuro (después del último dato): lo consumido real más lo estimado hasta ese día, con el
      ritmo de los últimos 28 días y la tarifa que rija cada día.
    También guarda el saldo real de hoy, que es el que usan la proyección y la fecha de agotamiento.
    """
    datos = filtrar(base_semaforo, nombre_linea, unidad)
    hoy = max(fin_datos, pd.Timestamp(date.today()))
    if unidad:
        disponible_hoy = disponible = presupuestos[nombre_linea]["unidades"][unidad]
    else:
        disponible_hoy = adquirido_al(nombre_linea, hoy)
        # al consultar el pasado solo cuentan las compras hechas hasta ese día
        disponible = adquirido_al(nombre_linea, fin if fin < fin_datos else max(fin, hoy))
    consumido_hoy = float(datos["creditos"].sum())
    real_corte = float(datos.loc[datos["fecha"] <= fin, "creditos"].sum())
    ref_ini = fin_datos - pd.Timedelta(days=REF_DIAS - 1)
    vacio = {k: 0.0 for k in L.METRICAS}
    est_corte = (L.consumo_estimado(datos, ref_ini, fin_datos, fin_datos, fin, tarifas)
                 if futuro and not datos.empty else vacio)
    desde_est = max(inicio - pd.Timedelta(days=1), fin_datos)
    est_periodo = (L.consumo_estimado(datos, ref_ini, fin_datos, desde_est, fin, tarifas)
                   if futuro and not datos.empty else vacio)
    consumido = real_corte + est_corte["creditos"]
    uso = consumido / disponible if disponible > 0 else None
    titulo_l = "Total (ambas líneas)" if L.LINEAS[nombre_linea] is None else f"Línea {nombre_linea}"
    periodo_e = en_periodo(filtrar(envios, nombre_linea, unidad))
    info = {
        "linea": nombre_linea, "unidad": unidad, "datos": datos, "periodo": periodo_e, "est_periodo": est_periodo,
        "titulo": f"{NOMBRE_UNIDAD_APP[unidad]} · {titulo_l}" if unidad else titulo_l,
        "etiqueta_disponible": "Asignados" if unidad else "Adquiridos",
        "disponible": disponible, "consumido": consumido, "restan_corte": disponible - consumido,
        "disponible_hoy": disponible_hoy, "consumido_hoy": consumido_hoy, "restan": disponible_hoy - consumido_hoy,
        "uso": uso, "estado": L.estado_consumo(uso * 100 if uso is not None else None, amarillo_pct, rojo_pct),
        "agotamiento": "No aplica" if disponible_hoy <= 0 else "Sin consumo", "semana": None,
        "ult7": 0.0, "prev7": 0.0, "proyeccion": None, "agot_ts": None, "ritmo": 0.0, "agot_linea": None,
    }
    if not datos.empty:
        fin_l = fin_datos
        info["ult7"] = float(datos.loc[datos["fecha"] > fin_l - pd.Timedelta(days=7), "creditos"].sum())
        info["prev7"] = float(datos.loc[(datos["fecha"] <= fin_l - pd.Timedelta(days=7))
                                        & (datos["fecha"] > fin_l - pd.Timedelta(days=14)), "creditos"].sum())
        proy_l = L.proyeccion(datos, ref_ini, fin_l, info["restan"], tarifas=tarifas)
        info["semana"] = proy_l["semana"]
        info["proyeccion"] = proy_l
        info["ritmo"] = proy_l["diario"]["creditos"]
        if disponible_hoy > 0:
            info["agot_ts"] = proy_l["agotamiento"]
            info["agotamiento"] = texto_agotamiento(info["agot_ts"])
    info["usado_periodo"] = float(periodo_e["creditos"].sum()) + est_periodo["creditos"]
    info["usd"] = usd_creditos(consumido, nombre_linea)            # gasto en USD hasta el corte
    info["usd_disponible"] = usd_creditos(disponible, nombre_linea)  # valor de lo adquirido / asignado
    if L.LINEAS[nombre_linea] is None:
        # UCP y Outbound son bolsas separadas: lo que sobra en una no cubre a la otra. El total se agota
        # cuando se agota la primera línea, no cuando se acaba la suma de las dos.
        por_linea_e = {l: estado_de(l, unidad) for l in LINEAS_COMPRA}
        valores = [por_linea_e[l]["usd"] for l in LINEAS_COMPRA if por_linea_e[l]["usd"] is not None]
        info["usd"] = sum(valores) if valores else None
        valores = [por_linea_e[l]["usd_disponible"] for l in LINEAS_COMPRA if por_linea_e[l]["usd_disponible"] is not None]
        info["usd_disponible"] = sum(valores) if valores else None
        primera = primera_en_agotarse(por_linea_e)
        if primera:
            info["agot_ts"], info["agot_linea"], info["ritmo"] = primera
            info["agotamiento"] = texto_agotamiento(info["agot_ts"])
    return info


def texto_agotamiento(agot) -> str:
    return ("Ya agotados" if agot == "agotado" else f"{agot:%d/%m/%Y}" if isinstance(agot, pd.Timestamp)
            else "Sin consumo")


def primera_en_agotarse(por_linea: dict[str, dict]) -> tuple | None:
    """(fecha o "agotado", línea, ritmo diario) de la línea que se agota primero, entre las que tienen créditos."""
    candidatas = []
    for nombre_l, e_l in por_linea.items():
        a = e_l["agot_ts"]
        if a == "agotado":
            candidatas.append((pd.Timestamp.min, a, nombre_l, e_l["ritmo"]))
        elif isinstance(a, pd.Timestamp):
            candidatas.append((a, a, nombre_l, e_l["ritmo"]))
    if not candidatas:
        return None
    _, agot, nombre_l, ritmo = min(candidatas, key=lambda c: c[0])
    return agot, nombre_l, ritmo


def etiqueta_corte() -> str:
    """Cómo se nombra el día al que se calcula el estado."""
    if futuro:
        return f"estimado al {fin:%d/%m/%Y}"
    return "usado a la fecha" if fin >= fin_datos else f"usado al {fin:%d/%m/%Y}"


def detalle_agotamiento(e: dict) -> str:
    """En el total de ambas líneas: qué línea se agota primero (son bolsas separadas)."""
    if not isinstance(e["agot_ts"], pd.Timestamp) or not e["agot_linea"]:
        return ""
    return f'<div class="cifra-sub">Primero se agota {e["agot_linea"]}</div>'


def cifras_basicas(e: dict) -> list[tuple]:
    hay = e["disponible"] > 0
    al = "a la fecha" if (fin >= fin_datos and not futuro) else f"al {fin:%d/%m/%Y}"
    cifras = []
    if inicio > minimo_datos:   # si el periodo empieza en el primer dato, sería la misma cifra que "Usados al ..."
        cifras.append(("Usados en el periodo", num(e["usado_periodo"])))
    cifras += [
        (f"Usados {al}" + (" (estimado)" if futuro else ""), num(e["consumido"])
         + (f'<div class="cifra-sub">≈ {txt_usd(e["usd"])}{ESTIMADO_USD}</div>' if e.get("usd") is not None else "")),
        (e["etiqueta_disponible"] + ("" if al == "a la fecha" else f" {al}"), num(e["disponible"]) if hay else "Sin definir"),
        (("Excedido" if e["restan_corte"] < 0 else "Disponibles") + (" hoy" if al == "a la fecha" else f" {al}"),
         num(abs(e["restan_corte"])) if hay else "-"),
        ("Agotamiento estimado", e["agotamiento"] + detalle_agotamiento(e)),
    ]
    return cifras


def cifras_tipo(e: dict) -> list[tuple]:
    p, est = e["periodo"], e["est_periodo"]
    return [(tipo,
             f"{num(p[f'creditos_{tipo.lower()}'].sum() + est[f'creditos_{tipo.lower()}'])} <small>créditos</small>"
             f'<div class="cifra-sub">{num(p[f"deliveries_{tipo.lower()}"].sum() + est[f"deliveries_{tipo.lower()}"])}'
             f' entregas</div>', CLASE_TIPO[tipo]) for tipo in TIPOS]


def cifras_detalle(e: dict) -> list[tuple]:
    return cifras_basicas(e) + cifras_tipo(e) + [
        ("Últimos 7 días", f"{num(e['ult7'])} créditos"),
        ("Próxima semana (estimado)", f"{num(e['semana']['creditos'])} créditos" if e["semana"] else "-"),
    ]


def texto_variacion(e: dict) -> str:
    if e["prev7"] <= 0:
        return "Últimos 7 días: sin datos de los 7 días anteriores para comparar."
    cambio = (e["ult7"] / e["prev7"] - 1) * 100
    return f"Últimos 7 días: {cambio:+.0f} % frente a los 7 días anteriores."


def tarjeta(e: dict, detalle: bool = False) -> None:
    clase = "semaforo semaforo-detalle" if detalle else "semaforo"
    cifras = cifras_detalle(e) if detalle else cifras_basicas(e) + cifras_tipo(e)
    st.markdown(f'<div class="{clase}">{tarjeta_semaforo(e["titulo"], e["estado"], e["uso"], cifras, amarillo_pct, rojo_pct, etiqueta_corte())}'
                f'</div>', unsafe_allow_html=True)


def fila_medidor(nombre: str, e: dict) -> str:
    if e["disponible"] > 0:
        detalle_u = f"{num(e['consumido'])} de {num(e['disponible'])} créditos"
    elif e["consumido"] > 0:
        detalle_u = f"{num(e['consumido'])} créditos usados · sin créditos asignados aquí"
    else:
        detalle_u = "Sin entregas ni créditos asignados aquí"
    return (f'<div class="unidad-fila"><div class="unidad-cabecera"><span class="unidad-nombre">{nombre}</span>'
            f'{insignia(e["estado"])}<span class="unidad-pct">{pct(e["uso"]) if e["uso"] is not None else "-"}'
            f'</span></div>{medidor(e["uso"], e["estado"], amarillo_pct, rojo_pct, escala=False)}'
            f'<div class="unidad-detalle">{detalle_u}</div></div>')


estados = {nombre: estado_de(nombre, unidad_sel) for nombre in L.LINEAS}
orden_gravedad = ["sin_definir", "verde", "amarillo", "rojo"]


def bloque_estado() -> None:
    """Tarjetas de estado según la vista de línea elegida."""
    st.markdown(
        f'<div class="leyenda"><span class="leyenda-titulo">Estado de los créditos de {nombre_ambito}</span>'
        f'<span>{insignia("verde")} menos de {amarillo_pct:g} %</span>'
        f'<span>{insignia("amarillo")} desde {amarillo_pct:g} %</span>'
        f'<span>{insignia("rojo")} desde {rojo_pct:g} %</span>'
        f'<span class="leyenda-nota">Estado al {fin:%d/%m/%Y}'
        f'{" (estimado con el ritmo de los últimos 28 días)" if futuro else ""}, contando {desde_txt}'
        f'{"; Marketing y Utility del periodo consultado" if filtrado else ""}</span></div>',
        unsafe_allow_html=True)

    if vista_linea == "Ambas líneas":
        cols = st.columns(3)
        for col, (nombre_l, e) in zip(cols, estados.items()):
            with col:
                tarjeta(e)
                if L.LINEAS[nombre_l] is not None:
                    st.button(f"Ver detalle de {nombre_l}", key=f"ir_{nombre_l}", on_click=ir_a_linea,
                              args=(nombre_l,), icon=":material/arrow_forward:", width="stretch")
                else:
                    st.button("Comparar UCP vs Outbound", key="ir_versus", on_click=ir_a_linea,
                              args=("UCP vs Outbound",), icon=":material/compare_arrows:", width="stretch")
    elif versus:
        cols = st.columns(2)
        for col, nombre_l in zip(cols, LINEAS_COMPRA):
            with col:
                tarjeta(estados[nombre_l], detalle=True)
                st.caption(texto_variacion(estados[nombre_l]))
                if not unidad_sel:
                    filas = [fila_medidor(NOMBRE_UNIDAD_APP[u], estado_de(nombre_l, u)) for u in L.UNIDADES]
                    st.markdown(f'<div class="panel-unidades"><div class="panel-titulo">Unidades en {nombre_l}</div>'
                                f'{"".join(filas)}</div>', unsafe_allow_html=True)
    else:
        e = estados[linea]
        col_card, col_lado = st.columns([1.35, 1])
        with col_card:
            tarjeta(e, detalle=True)
            st.caption(texto_variacion(e))
        with col_lado:
            if unidad_sel:
                filas = [fila_medidor("Total (ambas líneas)" if L.LINEAS[n] is None else f"Línea {n}", estados[n])
                         for n in L.LINEAS]
                titulo_panel = f"{NOMBRE_UNIDAD_APP[unidad_sel]} en cada línea"
            else:
                filas = [fila_medidor(NOMBRE_UNIDAD_APP[u], estado_de(linea, u)) for u in L.UNIDADES]
                titulo_panel = "Unidades en esta línea"
            st.markdown(f'<div class="panel-unidades"><div class="panel-titulo">{titulo_panel}</div>'
                        f'{"".join(filas)}</div>', unsafe_allow_html=True)

    if vista_linea != "Ambas líneas":
        otras = [n for n in VISTAS_LINEA if n != vista_linea]
        cols_f = st.columns([1.2] + [1] * len(otras))
        cols_f[0].markdown('<div class="franja-titulo">Otras vistas</div>', unsafe_allow_html=True)
        for col, nombre_o in zip(cols_f[1:], otras):
            if nombre_o == "UCP vs Outbound":
                texto_b, icono = "UCP vs Outbound", ":material/compare_arrows:"
            else:
                eo = estados[nombre_o]
                texto_b = (f"{'Ambas' if nombre_o == 'Ambas líneas' else nombre_o}: "
                           f"{pct(eo['uso']) if eo['uso'] is not None else '-'} · {SEMAFORO[eo['estado']]['etiqueta']}")
                icono = ":material/dashboard:" if nombre_o == "Ambas líneas" else ":material/swap_horiz:"
            col.button(texto_b, key=f"ir_{nombre_o}", on_click=ir_a_linea, args=(nombre_o,), width="stretch",
                       icon=icono)

    peor = max((e["estado"] for e in estados.values()), key=orden_gravedad.index)
    if futuro:
        sujeto = (f"al {fin:%d/%m/%Y}, {NOMBRE_UNIDAD_APP[unidad_sel]} habría usado" if unidad_sel
                  else f"al {fin:%d/%m/%Y}, al menos una línea llegaría")
    else:
        sujeto = (f"{NOMBRE_UNIDAD_APP[unidad_sel]} " + ("ya usó" if fin >= fin_datos else f"había usado al {fin:%d/%m/%Y}")
                  if unidad_sel else "al menos una línea " + ("llegó" if fin >= fin_datos else f"había llegado al {fin:%d/%m/%Y}"))
    if peor == "rojo":
        st.error(f"Consumo crítico: {sujeto} al {rojo_pct:g} % o más de sus créditos.", icon=":material/error:")
    elif peor == "amarillo":
        st.warning(f"Atención: {sujeto} al {amarillo_pct:g} % o más de sus créditos.", icon=":material/warning:")


def sin_datos_periodo() -> None:
    st.info(f"No hay entregas de {texto_ambito} entre el {inicio:%d/%m/%Y} y el {fin:%d/%m/%Y}. "
            "Elige otro periodo en la barra lateral.", icon=":material/event_busy:")


def bloque_efecto_tarifa(datos: pd.DataFrame) -> None:
    """Separa, para cada cambio de tarifa del periodo, cuánto del consumo se debe a la tarifa y no al volumen."""
    efectos = L.efecto_tarifas(datos, tarifas, inicio, fin_real)
    if not efectos:
        return
    st.markdown("#### Efecto de los cambios de tarifa")
    nota("Cuando cambia la tarifa, las mismas entregas pueden costar más o menos créditos. Aquí se compara lo "
         "que se cobró desde cada cambio con lo que habrían costado esas mismas entregas con la tabla anterior. "
         "En las gráficas de semana y mes, la línea punteada marca el cambio.")
    for ef in efectos:
        dif = ef["efecto"]
        usd = usd_de(datos[(datos["fecha"] >= ef["desde"]) & (datos["fecha"] <= ef["hasta"])])
        usd_ef = None if usd is None or ef["creditos"] == 0 else usd * dif / ef["creditos"]
        pct_ef = dif / ef["con_tabla_anterior"] * 100 if ef["con_tabla_anterior"] else 0
        sentido = "sumó" if dif > 0.5 else ("restó" if dif < -0.5 else "no cambió")
        with st.container(border=True):
            st.markdown(f'<div class="subtitulo-bloque">Tabla del {ef["desde"]:%d/%m/%Y}</div>', unsafe_allow_html=True)
            k1, k2, k3 = st.columns(3)
            k1.metric(f"Cobrado del {ef['desde']:%d/%m} al {ef['hasta']:%d/%m}", num(ef["creditos"]),
                      help=f"{num(ef['entregas'])} entregas en ese tramo.")
            k2.metric(f"Con la tabla anterior ({ef['tabla_anterior']:%d/%m/%Y})", num(ef["con_tabla_anterior"]))
            k3.metric("Efecto de la tarifa", ("+" if dif > 0 else "") + num(dif) if abs(dif) >= 0.5 else "0",
                      delta=(f"{pct_ef:+.1f} %".replace(".", ",") if abs(dif) >= 0.5 else None), delta_color="inverse",
                      help="Créditos de más (o de menos) solo por el cambio de tarifa, con las mismas entregas.")
            if abs(dif) >= 0.5:
                texto_ef = f"El cambio de tarifa {sentido} {num(abs(dif))} créditos"
                if usd_ef is not None:
                    texto_ef += f" (≈ {txt_usd(abs(usd_ef))}{ESTIMADO_USD})"
            else:
                texto_ef = "El cambio de tarifa no cambió lo cobrado por estas entregas"
            st.caption(texto_ef + ". El resto de la variación del consumo se debe a cuántas entregas hubo, "
                       "no a la tarifa.")


def cifras_periodo(datos: pd.DataFrame, clave: str, *, apilado: bool = False) -> None:
    t = L.totales(datos)
    if apilado:
        c1, c2, c3 = st.columns(3)
        c1.metric("Créditos usados", num(t["creditos"]))
        c2.metric("Gasto" + ESTIMADO_USD, txt_usd(usd_de(datos)))
        c3.metric("Entregas", num(t["deliveries"]), help="Mensajes que les llegaron a las personas.")
    else:
        c1, c2, c3, c4, c5 = st.columns([1.1, 1.1, 1, 1, 1])
        c1.metric("Créditos usados", num(t["creditos"]))
        c2.metric("Gasto" + ESTIMADO_USD, txt_usd(usd_de(datos)),
                  help="Créditos usados por el precio por 1.000 créditos de cada línea (Todos los canales → "
                       "Configuración y WhatsApp → Créditos).")
        c3.metric("Entregas", num(t["deliveries"]), help="Mensajes que les llegaron a las personas (deliveries).")
        c4.metric("Créditos por día", num(t["creditos"] / dias_periodo), help="Promedio diario del periodo.")
        c5.metric("Entregas por día", num(t["deliveries"] / dias_periodo), help="Promedio diario del periodo.")
    cajas_por_tipo(t, clave, apilado=apilado)


# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------

if "Resumen" in tabs:
    with tabs["Resumen"]:
        bloque_estado()

        st.markdown(f"### Consumo del {inicio:%d/%m/%Y} al {fin:%d/%m/%Y}")
        nota(f"Lo que usó {texto_ambito} en el periodo consultado ({dias_periodo} "
             f"{'día' if dias_periodo == 1 else 'días'} con datos). Para cambiarlo, usa «Periodo a consultar» en la barra lateral.")
        if futuro:
            st.info(f"El periodo llega hasta el {fin:%d/%m/%Y}, pero los datos reales van hasta el {fin_datos:%d/%m/%Y}. "
                    "Las cifras y gráficas de esta sección muestran solo lo real; lo estimado para después de esa "
                    "fecha está en las tarjetas de estado y en la pestaña Proyección.", icon=":material/update:")
        if periodo.empty:
            sin_datos_periodo()
        else:
            por_linea = {n: filtrar(periodo, n) for n in LINEAS_COMPRA}
            if versus:
                cols = st.columns(2)
                for col, nombre_l in zip(cols, LINEAS_COMPRA):
                    with col:
                        st.markdown(f'<div class="subtitulo-bloque">Línea {nombre_l}</div>', unsafe_allow_html=True)
                        cifras_periodo(por_linea[nombre_l], f"res-{nombre_l}", apilado=True)
            else:
                cifras_periodo(periodo, "resumen")
            nota("Utility tiene tarifas mucho más bajas que Marketing (en Colombia, 0,99 frente a 15,44 créditos por "
                 "mensaje): pesa poco en créditos aunque tenga entregas. Por eso cada tipo tiene su propia gráfica.")
            bloque_efecto_tarifa(periodo)

            st.markdown("### Consumo en el tiempo")
            medida = selector_medida("medida_resumen")
            secciones = [("Por semana", "semana", False, None), ("Por mes", "mes", False, None),
                         ("Países con mayor consumo", "nombre_pais", True, 10)]
            if not unidad_sel:
                secciones.append(("Consumo por unidad", "unidad", True, None))
            for titulo_s, por, horizontal, top in secciones:
                if titulo_s.startswith("Países"):
                    st.markdown(f"### {titulo_s}")
                elif titulo_s.startswith("Consumo por unidad"):
                    st.markdown(f"### {titulo_s}")
                else:
                    st.markdown(f"#### {titulo_s}")
                if versus:
                    graficas_versus(por_linea, por, medida, horizontal=horizontal, top=top)
                else:
                    graficas_por_tipo(periodo, por, medida, horizontal=horizontal, top=top)


# ---------------------------------------------------------------------------
# Unidades (solo vista del Equipo CRM)
# ---------------------------------------------------------------------------

if "Unidades" in tabs:
    with tabs["Unidades"]:
        st.markdown("### Estado de cada unidad")
        nota(f"Créditos asignados a cada unidad en {'ambas líneas' if versus else texto_linea}, frente a todo lo "
             "que ha usado. Con «Ver la vista de...» el tablero completo muestra solo esa unidad, igual que la "
             "verá su responsable.")
        cols = st.columns(3)
        filas_t = []
        for col, u in zip(cols, L.UNIDADES):
            e = estado_de(linea, u)
            e["titulo"] = NOMBRE_UNIDAD_APP[u]
            with col:
                tarjeta(e)
                st.button(f"Ver la vista de {NOMBRE_UNIDAD_APP[u]}", key=f"vista_{u}", on_click=ir_a_vista,
                          args=(u,), icon=":material/arrow_forward:", width="stretch")
            tp = L.totales(e["periodo"])
            filas_t.append({"Unidad": NOMBRE_UNIDAD_APP[u], "asignados": e["disponible"], "usados": e["consumido"],
                            "uso": e["uso"] if e["uso"] is not None else float("nan"),
                            "periodo": tp["creditos"], "mkt": tp["creditos_marketing"], "uti": tp["creditos_utility"],
                            "entregas": tp["deliveries"]})
        st.markdown("### Comparativo de unidades")
        nota(f"Usados en el periodo: del {inicio:%d/%m/%Y} al {fin:%d/%m/%Y}.")
        tabla(pd.DataFrame(filas_t),
              {"Unidad": "Unidad", "asignados": "Créditos asignados",
               "usados": ("Usados a la fecha" if fin >= fin_datos and not futuro else f"Usados al {fin:%d/%m/%Y}")
               + (" (estimado)" if futuro else ""), "uso": "Uso",
               "periodo": "Usados en el periodo", "mkt": "Marketing (periodo)", "uti": "Utility (periodo)",
               "entregas": "Entregas (periodo)"},
              enteros=["asignados", "usados", "periodo", "mkt", "uti", "entregas"], porcentajes=["uso"])
        if not periodo.empty:
            medida_u = selector_medida("medida_unidades")
            if versus:
                graficas_versus({n: filtrar(periodo, n) for n in LINEAS_COMPRA}, "unidad", medida_u, horizontal=True)
            else:
                graficas_por_tipo(periodo, "unidad", medida_u, horizontal=True)


# ---------------------------------------------------------------------------
# Journeys
# ---------------------------------------------------------------------------

if "Journeys" in tabs:
    with tabs["Journeys"]:
        st.markdown("### Journeys")
        nota(f"Consumo de los journeys de {texto_ambito} del {inicio:%d/%m/%Y} al {fin:%d/%m/%Y} "
             "(periodo de la barra lateral). Elige uno o varios para ver su detalle y proyección.")
        if periodo.empty:
            sin_datos_periodo()
        else:
            ranking = periodo.groupby("journey")["creditos"].sum().sort_values(ascending=False)
            clave_j = f"{unidad_sel or 'crm'}_{vista_linea}"
            seleccion = st.multiselect("Journeys", list(ranking.index), key=f"sel_journeys_{clave_j}",
                                       placeholder="Escribe parte del nombre para buscar",
                                       format_func=lambda j: j.strip(),
                                       help="Ordenados de mayor a menor consumo en el periodo consultado.")
            medida_j = selector_medida(f"medida_journeys_{clave_j}")
            if not seleccion:
                st.markdown("#### Clasificación de journeys")
                nota("Automático - Acceso, Financiación y Visitas son journeys que corren solos; Pruebas son los que tienen "
                     "«prueba» en el nombre; Entregas a solicitud es lo que piden las unidades.")
                if versus:
                    graficas_versus({n: filtrar(periodo, n) for n in LINEAS_COMPRA}, "tipo_journey", medida_j,
                                    horizontal=True)
                else:
                    graficas_por_tipo(periodo, "tipo_journey", medida_j, horizontal=True)
                st.markdown("#### Los 15 journeys con mayor consumo")
                top = periodo.assign(journey=periodo["journey"].str.strip())
                if versus:
                    graficas_versus({n: filtrar(top, n) for n in LINEAS_COMPRA}, "journey", medida_j, horizontal=True,
                                    top=15)
                else:
                    graficas_por_tipo(top, "journey", medida_j, horizontal=True, top=15)
            else:
                datos_j = periodo[periodo["journey"].isin(seleccion)]
                cifras_periodo(datos_j, "journeys")
                st.markdown("#### Consumo semanal")
                graficas_por_tipo(datos_j, "semana", medida_j)
                st.markdown("#### Países con mayor consumo")
                graficas_por_tipo(datos_j, "nombre_pais", medida_j, horizontal=True, top=10)

                st.markdown("### Proyección de los journeys seleccionados")
                todos_j = envios_ambito[envios_ambito["journey"].isin(seleccion)]
                col_cfg, col_res = st.columns([1, 2.4])
                ini_rj, fin_rj = selector_referencia(col_cfg, f"ref_journeys_{clave_j}", fin_datos, inicio, fin, minimo_datos)
                disponibles_j = col_cfg.number_input(
                    "Créditos reservados para estos journeys", min_value=0.0, value=0.0, step=10000.0, format="%.0f",
                    key=f"disp_j_{clave_j}_{'|'.join(seleccion)}",
                    help="Opcional. Si estos journeys tienen una bolsa de créditos propia, escríbela para estimar "
                         "cuándo se agotaría.")
                proy_j = L.proyeccion(todos_j, ini_rj, fin_rj, disponibles_j, desde=fin_datos, tarifas=tarifas)
                with col_res:
                    p1, p2, p3 = st.columns(3)
                    p1.metric("Créditos próxima semana", num(proy_j["semana"]["creditos"]))
                    p2.metric("Entregas próxima semana", num(proy_j["semana"]["deliveries"]))
                    agot = proy_j["agotamiento"]
                    p3.metric("Agotamiento estimado",
                              "Escribe los créditos" if disponibles_j == 0 else
                              (f"{agot:%d/%m/%Y}" if isinstance(agot, pd.Timestamp) else
                               ("Ya agotados" if agot == "agotado" else "Sin consumo reciente")))
                    st.markdown(desglose(proy_j["semana"]["creditos_marketing"], proy_j["semana"]["creditos_utility"]),
                                unsafe_allow_html=True)
                nota(f"Con el ritmo de entregas del {ini_rj:%d/%m/%Y} al {fin_rj:%d/%m/%Y}.")


# ---------------------------------------------------------------------------
# Proyección
# ---------------------------------------------------------------------------

def bloque_proyeccion(nombre_l: str, contenedor, clave: str) -> None:
    e = estados[nombre_l]
    datos_l = filtrar(envios, nombre_l, unidad_sel)
    with contenedor:
        if versus:
            st.markdown(f'<div class="subtitulo-bloque">Línea {nombre_l}</div>', unsafe_allow_html=True)
        if datos_l.empty:
            st.info(f"{NOMBRE_UNIDAD_APP[unidad_sel] if unidad_sel else 'Esta línea'} no tiene entregas aquí.")
            return
        col_cfg, col_res = (st.container(), st.container()) if versus else st.columns([1, 2.4])
        inicio_ref, fin_ref = selector_referencia(col_cfg, f"ref_{clave}", fin_datos, inicio, fin, minimo_datos)
        hasta = col_cfg.date_input(
            "Proyectar hasta", value=(fin_datos + pd.Timedelta(days=30)).date(),
            min_value=(fin_datos + pd.Timedelta(days=1)).date(), max_value=(fin_datos + pd.Timedelta(days=730)).date(),
            format="DD/MM/YYYY", key=f"hasta_{clave}",
            help="Fecha futura (por ejemplo, la de un evento) hasta la que se quiere estimar el consumo.")
        hasta = pd.Timestamp(hasta)
        proy = L.proyeccion(datos_l, inicio_ref, fin_ref, e["restan"], desde=fin_datos, tarifas=tarifas)
        est = L.consumo_estimado(datos_l, inicio_ref, fin_ref, fin_datos, hasta, tarifas)
        with col_res:
            st.markdown('<div class="subtitulo-bloque">Próxima semana</div>', unsafe_allow_html=True)
            p1, p2, p3 = st.columns(3)
            p1.metric("Créditos próxima semana", num(proy["semana"]["creditos"]))
            p2.metric("Entregas próxima semana", num(proy["semana"]["deliveries"]))
            agot, ayuda = proy["agotamiento"], f"Con el ritmo del {inicio_ref:%d/%m/%Y} al {fin_ref:%d/%m/%Y}: {num(proy['diario']['creditos'])} créditos/día."
            if L.LINEAS[nombre_l] is None:
                # Bolsas separadas: el total se agota cuando se agota la primera línea
                por_linea = {}
                for l_ in LINEAS_COMPRA:
                    d_ = filtrar(envios, l_, unidad_sel)
                    if estados[l_]["disponible_hoy"] > 0 and not d_.empty:
                        p_ = L.proyeccion(d_, inicio_ref, fin_ref, estados[l_]["restan"], desde=fin_datos, tarifas=tarifas)
                        por_linea[l_] = {"agot_ts": p_["agotamiento"], "ritmo": p_["diario"]["creditos"]}
                primera = primera_en_agotarse(por_linea)
                if primera:
                    agot = primera[0]
                    ayuda += (f" UCP y Outbound son bolsas separadas: esta es la fecha en que se agota la primera "
                              f"({primera[1]}).")
            p3.metric("Agotamiento estimado",
                      "No aplica" if e["disponible_hoy"] <= 0 else
                      "Ya agotados" if agot == "agotado" else (f"{agot:%d/%m/%Y}" if agot is not None else "Sin consumo"),
                      help=ayuda if e["disponible_hoy"] > 0 else "No hay créditos asignados para calcularlo.")
            st.markdown(desglose(proy["semana"]["creditos_marketing"], proy["semana"]["creditos_utility"]),
                        unsafe_allow_html=True)
            dias_h = (hasta - fin_datos).days
            st.markdown(f'<div class="subtitulo-bloque">Hasta el {hasta:%d/%m/%Y} ({dias_h} días)</div>',
                        unsafe_allow_html=True)
            q1, q2, q3 = st.columns(3)
            q1.metric(f"Créditos hasta el {hasta:%d/%m/%Y}", num(est["creditos"]),
                      help=f"Consumo estimado en los próximos {dias_h} días, del {fin_datos + pd.Timedelta(days=1):%d/%m/%Y} "
                           f"al {hasta:%d/%m/%Y}.")
            q2.metric(f"Entregas hasta el {hasta:%d/%m/%Y}", num(est["deliveries"]))
            if e["disponible_hoy"] > 0:
                saldo_h = e["restan"] - est["creditos"]
                q3.metric(f"Saldo al {hasta:%d/%m/%Y}" if saldo_h >= 0 else f"Faltarían al {hasta:%d/%m/%Y}",
                          num(abs(saldo_h)),
                          help="Disponibles hoy menos el consumo estimado hasta esa fecha.")
            else:
                q3.metric(f"Saldo al {hasta:%d/%m/%Y}", "No aplica", help="No hay créditos definidos.")
            st.markdown(desglose(est["creditos_marketing"], est["creditos_utility"]), unsafe_allow_html=True)
        saldo = ("sin créditos definidos" if e["disponible_hoy"] <= 0 else
                 f"{num(e['restan'])} disponibles hoy" if e["restan"] >= 0 else
                 f"ya se usaron {num(-e['restan'])} créditos más de los {e['etiqueta_disponible'].lower()}")
        nota(f"Saldo: {saldo}. Ritmo tomado del {inicio_ref:%d/%m/%Y} al {fin_ref:%d/%m/%Y} ({proy['dias']} días).")



DIAS_EN_USO = 14   # un journey "está en uso" si tuvo entregas en los últimos 14 días (y en más de un día)


def bloque_proyeccion_journeys(clave: str) -> None:
    """Proyección con los journeys que de verdad siguen en uso: se pueden quitar journeys y agregar nuevos."""
    lineas_p = LINEAS_COMPRA if (versus or linea == "Ambas líneas") else [linea]
    datos_s = filtrar(envios, "Ambas líneas" if len(lineas_p) > 1 else lineas_p[0], unidad_sel)
    if datos_s.empty:
        st.info("No hay entregas para proyectar en lo que se está viendo.")
        return
    col_cfg, col_res = st.columns([1, 2.4])
    ini_r, fin_r = selector_referencia(col_cfg, f"refj_{clave}", fin_datos, inicio, fin, minimo_datos)
    hasta = pd.Timestamp(col_cfg.date_input(
        "Proyectar hasta", value=(fin_datos + pd.Timedelta(days=30)).date(),
        min_value=(fin_datos + pd.Timedelta(days=1)).date(), max_value=(fin_datos + pd.Timedelta(days=730)).date(),
        format="DD/MM/YYYY", key=f"hastaj_{clave}"))
    dias_ref = max((fin_r - ini_r).days + 1, 1)
    ventana = datos_s[(datos_s["fecha"] >= ini_r) & (datos_s["fecha"] <= fin_r)]
    if ventana.empty:
        col_res.info("No hubo entregas en el periodo de referencia. Elige otro ritmo.")
        return

    # Journeys del periodo de referencia, con su ritmo y si siguen en uso
    res = (ventana.groupby(["journey", "linea"])
           .agg(entregas=("deliveries", "sum"), creditos=("creditos", "sum"), dias=("fecha", "nunique"))
           .reset_index())
    ultimos = datos_s.groupby(["journey", "linea"])["fecha"].max().rename("ultimo").reset_index()
    res = res.merge(ultimos, on=["journey", "linea"], how="left")
    res["entregas_sem"] = (res["entregas"] / dias_ref * 7).round(0)
    res["creditos_sem"] = (res["creditos"] / dias_ref * 7).round(0)
    res["Incluir"] = (res["ultimo"] >= fin_datos - pd.Timedelta(days=DIAS_EN_USO - 1)) & (res["dias"] >= 2)
    res["Journey"] = res["journey"].str.strip()
    res = res.sort_values("creditos_sem", ascending=False).reset_index(drop=True)

    st.markdown("#### Journeys a incluir")
    nota(f"Vienen marcados los journeys que siguen en uso: con entregas en los últimos {DIAS_EN_USO} días y en más "
         "de un día (los de un solo uso quedan por fuera). Marca o desmarca los que quieras; el ritmo de cada uno "
         f"es su promedio semanal del {ini_r:%d/%m/%Y} al {fin_r:%d/%m/%Y}.")
    columnas = ["Incluir", "Journey"] + (["linea"] if len(lineas_p) > 1 else []) + \
               ["entregas_sem", "creditos_sem", "ultimo", "dias"]
    editado = st.data_editor(
        res[columnas], key=f"ed_journeys_{clave}_{ini_r:%Y%m%d}_{fin_r:%Y%m%d}", hide_index=True, width="stretch",
        height=min(420, 38 + 35 * len(res)), disabled=[c for c in columnas if c != "Incluir"],
        column_config={
            "Incluir": st.column_config.CheckboxColumn("Incluir", width="small"),
            "Journey": st.column_config.TextColumn("Journey", width="large"),
            "linea": st.column_config.TextColumn("Línea"),
            "entregas_sem": st.column_config.NumberColumn("Entregas / semana", format="localized"),
            "creditos_sem": st.column_config.NumberColumn("Créditos / semana", format="localized"),
            "ultimo": st.column_config.DateColumn("Último uso", format="DD/MM/YYYY"),
            "dias": st.column_config.NumberColumn("Días con entregas"),
        })
    incluidos = set(zip(res.loc[editado["Incluir"].astype(bool).values, "journey"],
                        res.loc[editado["Incluir"].astype(bool).values, "linea"]))

    st.markdown("#### Journeys nuevos o de reemplazo")
    nota("Agrega una fila por cada journey que se va a empezar a usar, con cuántas entregas por semana esperas. "
         "Los créditos se calculan con la tarifa vigente del país y del tipo de mensaje.")
    paises = list(ventana.groupby("pais")["deliveries"].sum().sort_values(ascending=False).index)
    paises = paises + [p for p in ("CO", "US", "MX", "OTHER") if p not in paises]
    base_n = pd.DataFrame({"Nombre": pd.Series(dtype=str), "Línea": pd.Series(dtype=str),
                           "Tipo": pd.Series(dtype=str), "País": pd.Series(dtype=str),
                           "Entregas por semana": pd.Series(dtype=float)})
    if len(lineas_p) == 1:
        base_n = base_n.drop(columns="Línea")
    nuevos = st.data_editor(
        base_n, key=f"nuevos_{clave}", num_rows="dynamic", hide_index=True, width="stretch",
        column_config={
            "Nombre": st.column_config.TextColumn("Nombre", width="large"),
            "Línea": st.column_config.SelectboxColumn("Línea", options=LINEAS_COMPRA, required=True),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=list(TIPOS), default="Marketing", required=True),
            "País": st.column_config.SelectboxColumn("País", options=paises, default="CO", required=True),
            "Entregas por semana": st.column_config.NumberColumn("Entregas por semana", min_value=0, step=100,
                                                                 format="localized"),
        })
    filas_nuevas = []
    for _, n in nuevos.iterrows():
        if pd.notna(n.get("Entregas por semana")) and float(n.get("Entregas por semana") or 0) > 0:
            filas_nuevas.append({"nombre": n.get("Nombre") or "Journey nuevo", "entregas_semana": n["Entregas por semana"],
                                 "pais": n.get("País") or "CO", "tipo": n.get("Tipo") or "Marketing",
                                 "linea": n.get("Línea") if len(lineas_p) > 1 else lineas_p[0], "unidad": unidad_sel})
    sinteticos = L.journeys_sinteticos(filas_nuevas, ini_r, fin_r)

    # Proyección por línea (bolsas separadas), con todos los journeys y con el escenario
    total = {"g_sem": 0.0, "e_sem": 0.0, "g_hasta": 0.0, "e_hasta": 0.0, "e_ent": 0.0, "e_usd": 0.0, "g_usd": 0.0}
    agot_g, agot_e = {}, {}
    for l in lineas_p:
        e_l = estados[l]
        base_l = ventana[ventana["linea"] == l]
        mascara = pd.Series([k in incluidos for k in zip(base_l["journey"], base_l["linea"])],
                            index=base_l.index, dtype=bool)
        escenario_l = base_l.loc[mascara]
        if not sinteticos.empty:
            escenario_l = pd.concat([escenario_l, sinteticos[sinteticos["linea"] == l]], ignore_index=True)
        pg = L.proyeccion(base_l, ini_r, fin_r, e_l["restan"], desde=fin_datos, tarifas=tarifas)
        pe = L.proyeccion(escenario_l, ini_r, fin_r, e_l["restan"], desde=fin_datos, tarifas=tarifas)
        hg = L.consumo_estimado(base_l, ini_r, fin_r, fin_datos, hasta, tarifas)
        he = L.consumo_estimado(escenario_l, ini_r, fin_r, fin_datos, hasta, tarifas)
        total["g_sem"] += pg["semana"]["creditos"]; total["e_sem"] += pe["semana"]["creditos"]
        total["g_hasta"] += hg["creditos"]; total["e_hasta"] += he["creditos"]; total["e_ent"] += he["deliveries"]
        total["g_usd"] += usd_creditos(hg["creditos"], l) or 0; total["e_usd"] += usd_creditos(he["creditos"], l) or 0
        if e_l["disponible_hoy"] > 0:
            agot_g[l] = {"agot_ts": pg["agotamiento"], "ritmo": pg["diario"]["creditos"]}
            agot_e[l] = {"agot_ts": pe["agotamiento"], "ritmo": pe["diario"]["creditos"]}
    pg_ag, pe_ag = primera_en_agotarse(agot_g), primera_en_agotarse(agot_e)

    def fecha_txt(p, con_linea: bool = True):
        if p is None:
            return "No aplica"
        return texto_agotamiento(p[0]) + (f" ({p[1]})" if con_linea and len(lineas_p) > 1 else "")

    def delta_txt(a, b):
        d = a - b
        return None if abs(d) < 0.5 else ("+" if d > 0 else "-") + num(abs(d)) + " frente a todos"

    with col_res:
        quitados = len(res) - len(incluidos)
        st.markdown(f'<div class="subtitulo-bloque">Escenario: {len(incluidos)} de {len(res)} journeys'
                    f'{f" + {len(filas_nuevas)} nuevo(s)" if filas_nuevas else ""}</div>', unsafe_allow_html=True)
        q1, q2, q3 = st.columns(3)
        q1.metric("Créditos próxima semana", num(total["e_sem"]), delta=delta_txt(total["e_sem"], total["g_sem"]),
                  delta_color="inverse")
        q2.metric(f"Créditos hasta el {hasta:%d/%m/%Y}", num(total["e_hasta"]),
                  delta=delta_txt(total["e_hasta"], total["g_hasta"]), delta_color="inverse",
                  help=f"{num(total['e_ent'])} entregas · ≈ {txt_usd(total['e_usd'])}{ESTIMADO_USD}")
        q3.metric("Agotamiento estimado", fecha_txt(pe_ag, con_linea=False),
                  help=(f"Primera línea en agotarse: {pe_ag[1]}. " if pe_ag and len(lineas_p) > 1 else "")
                       + "Con todos los journeys del periodo de referencia: " + fecha_txt(pg_ag) + ". "
                       + ("UCP y Outbound son bolsas separadas: es la fecha de la primera en agotarse."
                          if len(lineas_p) > 1 else ""))
        st.caption(f"Con todos los journeys: {num(total['g_sem'])} créditos la próxima semana, {num(total['g_hasta'])} "
                   f"hasta el {hasta:%d/%m/%Y} (≈ {txt_usd(total['g_usd'])}{ESTIMADO_USD}) y agotamiento "
                   f"{fecha_txt(pg_ag)}. En el escenario quedan por fuera {quitados} journeys"
                   + (f" y se suman {len(filas_nuevas)} nuevos" if filas_nuevas else "") + ".")


if "Proyección" in tabs:
    with tabs["Proyección"]:
        st.markdown(f"### Proyección de {nombre_ambito}")
        nota(f"Qué pasaría con los créditos de {texto_ambito} si se sigue al mismo ritmo, desde el último día con "
             f"datos ({fin_datos:%d/%m/%Y}).")
        clave_p = f"{unidad_sel or 'crm'}"
        modo_proy = st.segmented_control(
            "Cómo proyectar", ["ritmo", "journeys"], key=f"modo_proy_{clave_p}", default="ritmo",
            format_func=lambda m: {"ritmo": "Con el ritmo actual", "journeys": "Eligiendo journeys"}[m],
            help="«Con el ritmo actual» usa todo lo que se envió en el periodo de referencia. «Eligiendo journeys» "
                 "deja quitar los journeys que ya no se van a usar y agregar journeys nuevos o de reemplazo.") or "ritmo"
        if modo_proy == "journeys":
            bloque_proyeccion_journeys(f"{clave_p}_{vista_linea}")
        elif versus:
            cols = st.columns(2)
            for col, nombre_l in zip(cols, LINEAS_COMPRA):
                bloque_proyeccion(nombre_l, col, f"{clave_p}_{nombre_l}_vs")
        else:
            bloque_proyeccion(linea, st.container(), f"{clave_p}_{linea}")

        ultima_tabla = L.vigencias(tarifas)[-1]
        if ultima_tabla != pd.Timestamp.min:
            vigente_hoy = L.tarifa_vigente(tarifas, max(fin_datos, pd.Timestamp(date.today())))
            nota(f"Tarifas: cada día proyectado se cobra con la tabla oficial de Salesforce vigente ese día. Hoy rige "
                 f"la del {vigente_hoy:%d/%m/%Y}; la más reciente publicada es la del {ultima_tabla:%d/%m/%Y} y se "
                 "aplica desde esa fecha. Cuando se publique una tabla nueva, basta con agregarla a la carpeta tarifas/.")


# ---------------------------------------------------------------------------
# Detalle
# ---------------------------------------------------------------------------

if "Detalle" in tabs:
    with tabs["Detalle"]:
        st.markdown("### Detalle de entregas")
        nota(f"Cada fila del reporte de Marketing Cloud de {texto_ambito} en el periodo consultado "
             f"({inicio:%d/%m/%Y} al {fin:%d/%m/%Y}), con la tarifa y los créditos calculados. Se puede ordenar por "
             "cualquier columna y descargar.")
        columnas_detalle = {
            "fecha": "Fecha", "linea": "Línea", "unidad": "Unidad", "journey": "Journey",
            "WhatsApp Send Name": "Send Name", "tipo_journey": "Tipo de journey", "pais": "País",
            "tipo_conversacion": "Tipo", "deliveries": "Entregas", "tarifa": "Tarifa",
            "tarifa_vigente_desde": "Tarifa vigente desde", "creditos": "Créditos",
        }
        columnas_detalle = {k: v for k, v in columnas_detalle.items() if k in periodo.columns}
        vista_d = periodo.sort_values("fecha", ascending=False)[list(columnas_detalle)].rename(columns=columnas_detalle)
        vista_d["Unidad"] = vista_d["Unidad"].map(NOMBRE_UNIDAD_APP)
        st.dataframe(vista_d, hide_index=True, width="stretch", height=560,
                     column_config={"Fecha": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                    "Tarifa vigente desde": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                    "Entregas": st.column_config.NumberColumn(format="localized"),
                                    "Créditos": st.column_config.NumberColumn(format="localized")})
        sufijo_archivo = f"_{unidad_sel}" if unidad_sel else ""
        st.download_button("Descargar detalle (CSV)", vista_d.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                           file_name=f"Detalle_creditos_WhatsApp{sufijo_archivo}_{date.today():%Y%m%d}.csv",
                           mime="text/csv", icon=":material/download:")


# ---------------------------------------------------------------------------
# Configuración (solo vista del Equipo CRM)
# ---------------------------------------------------------------------------

RUTA_ALERTAS = CARPETA / "alertas.json"
AUTOMATICA = "Automática (por prefijo)"


def clave_de(nombre: str, usadas: set[str]) -> str:
    """Clave interna para una unidad nueva a partir de su nombre ("Educación Continua" -> "educacion_continua")."""
    base = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", "_", base).strip("_") or "unidad"
    clave, n = base, 2
    while clave in usadas or clave == L.SIN_UNIDAD:
        clave, n = f"{base}_{n}", n + 1
    return clave


def leer_alertas() -> dict:
    try:
        return json.loads(RUTA_ALERTAS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def lista(texto) -> list[str]:
    return [t.strip() for t in re.split(r"[,;\s]+", str(texto or "")) if t.strip()]


def seccion_unidades_y_journeys() -> None:
    """Unidades (agregar, renombrar, quitar), sus prefijos y responsables, y la asignación manual de journeys."""
    st.markdown("### Unidades")
    nota("Agrega una unidad en la última fila, cambia su nombre o quítala seleccionando la fila y borrándola. "
         "Los <b>prefijos</b> sirven para asignar los journeys solos: un journey que empieza por ese texto queda en "
         "esa unidad (por ejemplo, EGRES para EGRES_BIENVENIDA). Los <b>responsables</b> son los correos que "
         "reciben las alertas de la unidad. Los cambios se aplican al dar «Guardar unidades y journeys».")
    unidades_cfg = L.unidades_de_config(config)
    resp = (leer_alertas().get("unidades", {}) or {}).get("responsables", {}) or {}
    base_u = pd.DataFrame([{"clave": u["clave"], "Unidad": u["nombre"], "Prefijos": ", ".join(u["prefijos"]),
                            "Responsables": ", ".join(resp.get(u["clave"], []))} for u in unidades_cfg])
    editadas = st.data_editor(
        base_u, key="editor_lista_unidades", num_rows="dynamic", hide_index=True, width="stretch",
        column_order=["Unidad", "Prefijos", "Responsables"],
        column_config={
            "Unidad": st.column_config.TextColumn("Unidad", required=True, width="medium"),
            "Prefijos": st.column_config.TextColumn("Prefijos de journeys", width="medium",
                                                    help="Separados por coma. Puede quedar vacío."),
            "Responsables": st.column_config.TextColumn("Responsables (correos)", width="large",
                                                        help="Correos separados por coma. Reciben las alertas de la unidad."),
        })
    opciones_def = [u["clave"] for u in unidades_cfg] + [L.SIN_UNIDAD]
    actual_def = L.unidad_por_defecto()
    por_defecto = st.selectbox(
        "Los journeys que no coinciden con ningún prefijo van a", opciones_def,
        index=opciones_def.index(actual_def) if actual_def in opciones_def else 0,
        format_func=lambda c: L.NOMBRE_UNIDAD.get(c, c) if c != L.SIN_UNIDAD else "Sin unidad (quedan aparte)",
        key="unidad_por_defecto")

    st.markdown("### Asignación de journeys")
    nota("Cada journey queda en la unidad de su prefijo. Si un journey no tiene prefijo o debe ir a otra unidad, "
         "elige la unidad en la columna «Unidad»; «Automática» vuelve a usar el prefijo. Usa la búsqueda para "
         "encontrarlo; si cambias la búsqueda antes de guardar, los cambios de la tabla se pierden.")
    resumen_j = (envios.groupby("journey").agg(entregas=("deliveries", "sum"), ultimo=("fecha", "max"))
                 .reset_index().sort_values("ultimo", ascending=False))
    resumen_j["auto"] = resumen_j["journey"].map(lambda j: L.NOMBRE_UNIDAD.get(L.unidad_automatica(j), "-"))
    asignados = dict(config.get("journeys") or {})
    nombre_a_clave = {u["nombre"]: u["clave"] for u in unidades_cfg}
    resumen_j["Unidad"] = resumen_j["journey"].map(
        lambda j: L.NOMBRE_UNIDAD.get(asignados[j], AUTOMATICA) if asignados.get(j) in nombre_a_clave.values()
        else AUTOMATICA)
    c_b, c_f = st.columns([2, 1])
    buscar = c_b.text_input("Buscar journey", key="buscar_journey", placeholder="Parte del nombre")
    solo_manual = c_f.checkbox("Solo los asignados a mano", key="solo_manual")
    vista_j = resumen_j
    if buscar:
        vista_j = vista_j[vista_j["journey"].str.contains(re.escape(buscar), case=False)]
    if solo_manual:
        vista_j = vista_j[vista_j["Unidad"] != AUTOMATICA]
    vista_j = vista_j.reset_index(drop=True)
    st.caption(f"{len(vista_j)} de {len(resumen_j)} journeys · {len(asignados)} asignados a mano.")
    editados_j = st.data_editor(
        vista_j[["journey", "entregas", "ultimo", "auto", "Unidad"]], hide_index=True, width="stretch", height=380,
        key=f"editor_journeys_{buscar}_{solo_manual}", disabled=["journey", "entregas", "ultimo", "auto"],
        column_config={
            "journey": st.column_config.TextColumn("Journey", width="large"),
            "entregas": st.column_config.NumberColumn("Entregas", format="localized"),
            "ultimo": st.column_config.DateColumn("Último uso", format="DD/MM/YYYY"),
            "auto": st.column_config.TextColumn("Por prefijo"),
            "Unidad": st.column_config.SelectboxColumn("Unidad", options=[AUTOMATICA] + list(nombre_a_clave),
                                                       required=True, width="medium"),
        })

    if st.button("Guardar unidades y journeys", type="primary", icon=":material/save:"):
        # Unidades: las existentes conservan su clave (y sus créditos asignados); las nuevas reciben una
        nuevas, usadas, errores = [], set(), []
        previas = {u["clave"]: u for u in unidades_cfg}
        for _, fila in editadas.iterrows():
            nombre = str(fila.get("Unidad") or "").strip()
            if not nombre:
                continue
            clave = fila.get("clave") if isinstance(fila.get("clave"), str) and fila.get("clave") in previas else None
            clave = clave or clave_de(nombre, usadas | set(previas))
            usadas.add(clave)
            nuevas.append({"clave": clave, "nombre": nombre,
                           "codigo": previas.get(clave, {}).get("codigo") or clave.upper(),
                           "prefijos": lista(fila.get("Prefijos")),
                           "responsables": lista(fila.get("Responsables"))})
        nombres = [u["nombre"].lower() for u in nuevas]
        if not nuevas:
            errores.append("Debe quedar al menos una unidad.")
        if len(set(nombres)) != len(nombres):
            errores.append("Hay dos unidades con el mismo nombre.")
        if errores:
            for e_ in errores:
                st.error(e_, icon=":material/error:")
            return
        claves = [u["clave"] for u in nuevas]
        defecto = por_defecto if por_defecto in claves or por_defecto == L.SIN_UNIDAD else claves[0]
        # Journeys: lo guardado más los cambios de las filas que se ven en la tabla
        for _, fila in editados_j.iterrows():
            valor = fila["Unidad"]
            if valor == AUTOMATICA or nombre_a_clave.get(valor) not in claves:
                asignados.pop(fila["journey"], None)
            else:
                asignados[fila["journey"]] = nombre_a_clave[valor]
        L.guardar_unidades(RUTA_CONFIG, config, nuevas, defecto, asignados)
        # Responsables en alertas.json (lo demás del archivo se conserva)
        cfg_a = leer_alertas()
        cfg_a.setdefault("unidades", {})["responsables"] = {u["clave"]: u["responsables"] for u in nuevas}
        RUTA_ALERTAS.write_text(json.dumps(cfg_a, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        quitadas = [previas[c]["nombre"] for c in previas if c not in claves]
        agregadas = [u["nombre"] for u in nuevas if u["clave"] not in previas]
        subir_y_registrar("Guarda unidades y journeys", "; ".join(x for x in (
            f"{len(nuevas)} unidades", f"agrega {', '.join(agregadas)}" if agregadas else "",
            f"quita {', '.join(quitadas)}" if quitadas else "",
            f"{len(asignados)} journeys asignados a mano") if x), RUTA_CONFIG, RUTA_ALERTAS)
        for k in ("editor_lista_unidades", "editor_unidades"):
            st.session_state.pop(k, None)
        st.cache_data.clear()
        st.toast("Unidades y journeys guardados" + (f". Se quitó: {', '.join(quitadas)}" if quitadas else ""),
                 icon=":material/check:")
        st.rerun()
    st.caption("Al guardar se vuelven a clasificar todas las entregas. Si quitas una unidad, sus créditos "
               "asignados se eliminan y sus journeys pasan a la unidad por defecto (o a otra por su prefijo).")


if "Créditos" in tabs:
    with tabs["Créditos"]:
        st.markdown("### Créditos adquiridos")
        nota("UCP y Outbound son bolsas separadas: los créditos se compran para una línea y solo sirven para esa "
             "línea. Por eso cada compra se registra con su línea. Hoy la tarifa por país es la misma en las dos. "
             "Para registrar una compra, agrega una fila al final con la fecha, la línea, los créditos y una nota "
             "(por ejemplo, el número de orden).")
        st.data_editor(
            compras_guardadas, key="editor_compras", num_rows="dynamic", hide_index=True, width="stretch",
            column_config={
                "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY", required=True),
                "Línea": st.column_config.SelectboxColumn("Línea", options=LINEAS_COMPRA, required=True,
                                                          help="Línea para la que se compraron los créditos."),
                "Créditos": st.column_config.NumberColumn("Créditos", min_value=0, step=1, format="localized",
                                                          required=True),
                COL_PRECIO: st.column_config.NumberColumn(
                    COL_PRECIO, min_value=0.0, step=0.01, format="%.2f",
                    help="Opcional. Déjalo vacío para usar el precio de WhatsApp de Configuración; llénalo si esta "
                         "compra se pagó a otro precio."),
                "Nota": st.column_config.TextColumn("Nota", width="large"),
            })
        c1, c2, c3 = st.columns(3)
        c1.metric("Adquiridos UCP", num(presupuestos["UCP"]["creditos_totales"]))
        c2.metric("Adquiridos Outbound", num(presupuestos["Outbound"]["creditos_totales"]))
        c3.metric("Total ambas líneas", num(presupuestos["Ambas líneas"]["creditos_totales"]),
                  help="Suma de las dos bolsas. Los créditos de una línea no se pueden usar en la otra.")
        valor_l = {l: usd_creditos(presupuestos[l]["creditos_totales"], l) for l in LINEAS_COMPRA}
        partes_v = [f"{l}: {txt_usd(valor_l[l])} (a US$ {txt_precio(PRECIO_LINEA[l])} por 1.000)"
                    if PRECIO_LINEA[l] is not None else f"{l}: sin precio" for l in LINEAS_COMPRA]
        st.caption("Valor de lo adquirido" + ESTIMADO_USD + ": " + " · ".join(partes_v) + ". El precio general de "
                   "WhatsApp se cambia en Todos los canales → Configuración; si una compra tuvo otro precio, "
                   "escríbelo en su fila.")
        if len(compras_sin_linea):
            st.warning(f"{len(compras_sin_linea)} compra(s) no tienen línea y no se están contando. Elige UCP u "
                       "Outbound en la columna Línea.", icon=":material/warning:")

        st.markdown("### Asignación a unidades")
        nota("Cuántos de los créditos de cada línea le corresponden a cada unidad. Es la base del estado de cada "
             "unidad, de su vista y de sus alertas por correo.")
        st.data_editor(
            unidades_guardadas, key="editor_unidades", hide_index=True, width="stretch", disabled=["Unidad"],
            column_config={
                "Unidad": st.column_config.TextColumn("Unidad", width="medium"),
                **{col: st.column_config.NumberColumn(col, min_value=0, step=1, format="localized", required=True)
                   for col in LINEAS_COMPRA},
            })

        filas_r = [{"Concepto": "Créditos adquiridos", **{l: presupuestos[l]["creditos_totales"] for l in LINEAS_COMPRA}}]
        for u, nombre_f in zip(L.UNIDADES, FILAS_UNIDADES):
            filas_r.append({"Concepto": f"Asignado a {nombre_f}", **{l: presupuestos[l]["unidades"][u] for l in LINEAS_COMPRA}})
        filas_r.append({"Concepto": "Sin asignar a unidades",
                        **{l: L.sin_asignar(presupuestos[l]) for l in LINEAS_COMPRA}})
        resumen_cred = pd.DataFrame(filas_r)
        resumen_cred["Total"] = resumen_cred[LINEAS_COMPRA].sum(axis=1)
        st.markdown("**Resumen** (se calcula solo)")

        def resaltar(fila: pd.Series) -> list[str]:
            if fila["Concepto"] == "Créditos adquiridos":
                return ["font-weight: 600"] * len(fila)
            if fila["Concepto"] == "Sin asignar a unidades":
                negativo = any(fila[c] < 0 for c in LINEAS_COMPRA)
                pendiente = any(round(fila[c]) != 0 for c in LINEAS_COMPRA)
                fondo = "#FDECEA" if negativo else ("#FFF6DB" if pendiente else "#E8F5EC")
                return [f"background-color: {fondo}; font-weight: 600"] * len(fila)
            return [""] * len(fila)

        st.dataframe(
            resumen_cred.style.apply(resaltar, axis=1), hide_index=True, width="stretch",
            column_config={"Concepto": st.column_config.TextColumn("Concepto", width="medium"),
                           **{c: st.column_config.NumberColumn(c, format="localized")
                              for c in LINEAS_COMPRA + ["Total"]}})
        for linea_c in LINEAS_COMPRA:
            libre = L.sin_asignar(presupuestos[linea_c])
            if libre < 0:
                st.error(f"En {linea_c} se asignaron a las unidades {num(-libre)} créditos más de los adquiridos "
                         "para esa línea.", icon=":material/error:")
            elif round(libre) > 0:
                st.caption(f"{linea_c}: {num(libre)} créditos no están asignados a ninguna unidad. Si es una "
                           "reserva, está bien; si no, repártelos entre las unidades.")

        b1, b2, _ = st.columns([1, 1, 3])
        if b1.button("Guardar", type="primary", icon=":material/save:", disabled=not hay_cambios, width="stretch"):
            compras_a_guardar = [{"fecha": (f"{pd.Timestamp(r['Fecha']):%Y-%m-%d}" if pd.notna(r["Fecha"]) else ""),
                                  "linea": r["Línea"] or "", "creditos": r["Créditos"], "nota": r["Nota"],
                                  "precio_usd_1000": r[COL_PRECIO] if pd.notna(r[COL_PRECIO]) else None}
                                 for _, r in compras_vigentes.iterrows() if r["Créditos"] > 0]
            antes = {l: L.config_linea(config, l)["creditos_totales"] for l in LINEAS_COMPRA}
            L.guardar_creditos(RUTA_CONFIG, config, {l: presupuestos[l]["unidades"] for l in LINEAS_COMPRA},
                               compras_a_guardar)
            subir_y_registrar("Guarda créditos", "; ".join(
                f"{l}: {num(antes[l])} → {num(presupuestos[l]['creditos_totales'])} adquiridos, asignados "
                + ", ".join(f"{NOMBRE_UNIDAD_APP[u]} {num(v)}" for u, v in presupuestos[l]["unidades"].items())
                for l in LINEAS_COMPRA), RUTA_CONFIG)
            st.session_state.pop("editor_unidades", None)
            st.session_state.pop("editor_compras", None)
            st.cache_data.clear()
            st.toast("Créditos guardados en config.json", icon=":material/check:")
            st.rerun()
        if b2.button("Descartar cambios", icon=":material/undo:", disabled=not hay_cambios, width="stretch"):
            st.session_state.pop("editor_unidades", None)
            st.session_state.pop("editor_compras", None)
            st.rerun()
        st.caption("Los cambios se ven en todo el tablero apenas se escriben. Al guardar quedan en config.json para "
                   "la próxima vez y para las alertas por correo.")

        st.markdown("### Otros ajustes")
        st.markdown(
            f"- **Umbrales del estado:** Atención desde {amarillo_pct:g} %, Crítico desde {rojo_pct:g} % "
            "(`config.json`, sección `semaforo`).\n"
            "- **Enlace directo a la vista de una unidad:** agrega `?unidad=mercadeo`, `?unidad=egresados` o "
            "`?unidad=donaciones` a la dirección del dashboard.\n"
            "- **Responsables por unidad y alertas:** `alertas.json` (ver README).\n"
            "- **Tarifas:** carpeta `tarifas/`, un archivo por vigencia.\n"
            "- **Logo e ícono:** carpeta `assets/`.")


# ---------------------------------------------------------------------------
# Todos los canales (consolidado) y canales sin conectar
# ---------------------------------------------------------------------------

def ir_a_canal(nombre: str) -> None:
    st.session_state["canal"] = nombre


def barra_canales(partes: list[tuple[str, float]], total: float | None, formato) -> str:
    """Barra dividida por canal (cada parte en su color) y leyenda. Con `total`, lo que sobra queda en gris."""
    suma = sum(v for _, v in partes)
    base = total if total and total > 0 else suma
    if not base:
        return '<div class="lado-nota">Sin datos en el periodo.</div>'
    segmentos = "".join(
        f'<div class="seg" style="width:{max(v / base * 100, 0):.2f}%; background:{COLOR_CANAL[c]};" '
        f'title="{NOMBRE_CANAL[c]}: {formato(v)}"></div>' for c, v in partes if v > 0)
    leyenda = "".join(
        f'<span><i style="background:{COLOR_CANAL[c]};"></i>{NOMBRE_CANAL[c]} <b>{formato(v)}</b> '
        f'({v / base * 100:.0f} %)</span>' for c, v in partes)
    if total and total > 0:
        resto = max(total - suma, 0)
        leyenda += f'<span><i style="background:#E3E7EE;"></i>Disponible <b>{formato(resto)}</b></span>'
    return f'<div class="barra-canales">{segmentos}</div><div class="leyenda-canales">{leyenda}</div>'


def tarjeta_pendiente(c: str) -> str:
    return (f'<div class="semaforo-item canal-pendiente" style="border-color:{COLOR_CANAL[c]};">'
            f'<div class="semaforo-cabecera"><div class="semaforo-titulo">{NOMBRE_CANAL[c]}</div>'
            f'<span class="insignia" style="background:#F3F5F9; color:#52514E; border:1px solid #C9CDD3;">Sin conectar'
            f'</span></div><div class="pendiente-texto">Aún no está conectado: falta su reporte de Marketing Cloud '
            f'y su tabla de tarifas. Cuando estén, aparecerá aquí con sus créditos, su gasto y sus entregas.</div></div>')


def pagina_todos() -> None:
    e_w = estados["Ambas líneas"]
    with tabs_todos["Resumen"]:
        st.markdown(f"### Todos los canales · {nombre_ambito}")
        nota("Cada canal tiene su propia bolsa de créditos y sus créditos no valen lo mismo, así que aquí se comparan "
             "en lo que sí se puede sumar: <b>dólares</b> (con el precio por 1.000 créditos de cada canal) y "
             "<b>entregas</b>. Por ahora solo WhatsApp está conectado.")

        al = "a la fecha" if (fin >= fin_datos and not futuro) else f"al {fin:%d/%m/%Y}"
        gasto = {"whatsapp": e_w.get("usd") or 0.0}
        comprado = e_w.get("usd_disponible")
        st.markdown(f"#### Gasto en dólares {al}{ESTIMADO_USD}")
        if comprado:
            st.markdown(f'<div class="cifra-grande">{txt_usd(sum(gasto.values()))} <small>de {txt_usd(comprado)} '
                        f'{"comprados" if not unidad_sel else "asignados"} ({pct(sum(gasto.values()) / comprado)})'
                        f'</small></div>', unsafe_allow_html=True)
            st.markdown(barra_canales([(c, v) for c, v in gasto.items()], comprado, txt_usd), unsafe_allow_html=True)
        else:
            st.info("Falta el precio por 1.000 créditos para calcular el gasto en dólares. Se define en "
                    "Todos los canales → Configuración.", icon=":material/payments:")

        entregas = {"whatsapp": float(periodo["deliveries"].sum())}
        st.markdown(f"#### Entregas del {inicio:%d/%m/%Y} al {fin_real:%d/%m/%Y}")
        st.markdown(f'<div class="cifra-grande">{num(sum(entregas.values()))} <small>mensajes entregados</small></div>',
                    unsafe_allow_html=True)
        st.markdown(barra_canales(list(entregas.items()), None, num), unsafe_allow_html=True)

        st.markdown("#### Cada canal")
        cols = st.columns(len(CANALES))
        for col, c in zip(cols, CANALES):
            with col:
                if c in CANALES_CONECTADOS:
                    e_c = dict(e_w, titulo=NOMBRE_CANAL[c])
                    tarjeta(e_c)
                    st.button(f"Ver {NOMBRE_CANAL[c]}", key=f"ir_canal_{c}", on_click=ir_a_canal, args=(c,),
                              icon=":material/arrow_forward:", width="stretch")
                else:
                    st.markdown(f'<div class="semaforo">{tarjeta_pendiente(c)}</div>', unsafe_allow_html=True)

        if not periodo.empty:
            semanal = periodo.assign(usd=periodo["creditos"] * periodo["linea"].map(PRECIO_LINEA).astype(float) / 1000)
            tabla_s, orden_s = agrupar(semanal.assign(**{"creditos": semanal["usd"]}), "semana")
            st.markdown(f"#### Gasto por semana{ESTIMADO_USD}")
            st.markdown(f'<div class="titulo-tipo" style="border-color:{COLOR_CANAL["whatsapp"]};">WhatsApp · USD</div>',
                        unsafe_allow_html=True)
            grafica_barras(tabla_s, "semana", "creditos", orden=orden_s, titulo_valor="USD",
                           color=COLOR_CANAL["whatsapp"], marcas=marcas_tarifa("semana"))
            tabla_e, orden_e = agrupar(periodo, "semana")
            st.markdown("#### Entregas por semana")
            st.markdown(f'<div class="titulo-tipo" style="border-color:{COLOR_CANAL["whatsapp"]};">WhatsApp · Entregas</div>',
                        unsafe_allow_html=True)
            grafica_barras(tabla_e, "semana", "deliveries", orden=orden_e, titulo_valor="Entregas",
                           color=COLOR_CANAL["whatsapp"])
            st.caption("Cuando se conecten Correo y SMS, cada canal tendrá su gráfica aquí, una debajo de la otra.")

        if not unidad_sel:
            st.markdown("#### Por unidad")
            filas_u = []
            for u in L.UNIDADES:
                d_u = periodo[periodo["unidad"] == u]
                filas_u.append({"Unidad": NOMBRE_UNIDAD_APP[u], "w_usd": round(usd_de(d_u) or 0.0),
                                "w_ent": float(d_u["deliveries"].sum()), "correo": "Sin conectar", "sms": "Sin conectar"})
            vista_u = pd.DataFrame(filas_u)
            st.dataframe(vista_u, hide_index=True, width="stretch", column_config={
                "w_usd": st.column_config.NumberColumn(f"WhatsApp · gasto USD{ESTIMADO_USD}", format="localized"),
                "w_ent": st.column_config.NumberColumn("WhatsApp · entregas", format="localized"),
                "correo": st.column_config.TextColumn("Correo"), "sms": st.column_config.TextColumn("SMS")})
            st.caption(f"Gasto y entregas del periodo consultado ({inicio:%d/%m/%Y} al {fin_real:%d/%m/%Y}).")

    if "Configuración" in tabs_todos:
        with tabs_todos["Configuración"]:
            st.markdown("### Precio de los créditos")
            nota("Cuánto cuestan 1.000 créditos de cada canal, en dólares. Sirve para mostrar el gasto en dólares y "
                 "comparar canales. Salesforce no publica este valor: sale del contrato o de la orden de compra. "
                 "Mientras no esté confirmado, el dashboard marca los dólares como «estimado».")
            base_p = pd.DataFrame([{"Canal": NOMBRE_CANAL[c], "Precio": PRECIOS.get(c), "Confirmado": PRECIOS_OK.get(c, False)}
                                   for c in CANALES])
            precios_ed = st.data_editor(
                base_p, key="editor_precios", hide_index=True, width="stretch", disabled=["Canal"],
                column_config={
                    "Canal": st.column_config.TextColumn("Canal"),
                    "Precio": st.column_config.NumberColumn("USD por 1.000 créditos", min_value=0.0, step=0.01,
                                                            format="%.2f"),
                    "Confirmado": st.column_config.CheckboxColumn(
                        "Confirmado", help="Márcalo cuando el valor venga del contrato o la factura."),
                })
            if st.button("Guardar precios", type="primary", icon=":material/save:"):
                nuevos_p = {c: (float(r["Precio"]) if pd.notna(r["Precio"]) and float(r["Precio"]) > 0 else None)
                            for c, (_, r) in zip(CANALES, precios_ed.iterrows())}
                nuevos_ok = {c: bool(r["Confirmado"]) for c, (_, r) in zip(CANALES, precios_ed.iterrows())}
                L.guardar_precios(RUTA_CONFIG, config, nuevos_p, nuevos_ok)
                subir_y_registrar("Guarda precios", "; ".join(
                    f"{NOMBRE_CANAL[c]}: {txt_precio(nuevos_p[c])}{' (confirmado)' if nuevos_ok[c] else ''}"
                    for c in CANALES), RUTA_CONFIG)
                st.session_state.pop("editor_precios", None)
                st.cache_data.clear()
                st.toast("Precios guardados en config.json", icon=":material/check:")
                st.rerun()
            st.caption("En WhatsApp, si una compra se pagó a otro precio, se escribe en su fila en WhatsApp → Créditos.")
            seccion_unidades_y_journeys()


def pagina_pendiente(c: str) -> None:
    st.markdown(f"### {NOMBRE_CANAL[c]}")
    st.markdown(f'<div class="semaforo">{tarjeta_pendiente(c)}</div>', unsafe_allow_html=True)
    st.markdown(
        f"Para conectar **{NOMBRE_CANAL[c]}** se necesita:\n"
        f"1. **El reporte de Marketing Cloud** de {NOMBRE_CANAL[c].lower()}, como el `data.xlsx` de WhatsApp.\n"
        f"2. **Su tabla de tarifas** (multiplicadores de Salesforce Message Credits para {NOMBRE_CANAL[c].lower()}), "
        "con su fecha de vigencia.\n"
        "3. **Sus compras de créditos** y el **precio por 1.000 créditos** (Todos los canales → Configuración).\n\n"
        "Con eso, este canal tendrá las mismas pestañas que WhatsApp: Resumen, Proyección, Journeys y Detalle, "
        "separadas por unidad.")


if canal == "todos":
    pagina_todos()
elif canal not in CANALES_CONECTADOS:
    pagina_pendiente(canal)
