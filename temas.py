"""
Temas del tablero (presets de colores), como los temas de Visual Studio Code.

Cada tema define los colores de todo el tablero: fondo, barra lateral, tarjetas, textos, color principal,
Marketing y Utility, semáforo, gráficas y la paleta de las unidades. Cada persona elige su tema en
Personalizar tablero y, encima de él, puede cambiar el color principal, Marketing, Utility y el de cada unidad.

Los colores se aplican con variables CSS (--t-...) que usan los estilos de app.py; para los elementos propios
de Streamlit (botones, campos, pestañas, tablas) se agregan reglas que los adaptan al tema.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Utilidades de color
# ---------------------------------------------------------------------------

def es_hex(valor) -> bool:
    return bool(re.fullmatch(r"#[0-9A-Fa-f]{6}", str(valor or "")))


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def mezclar(a: str, b: str, t: float) -> str:
    """Color entre a (t=0) y b (t=1)."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex([ra[i] + (rb[i] - ra[i]) * t for i in range(3)])


def rgba(h: str, alfa: float) -> str:
    r, g, b = _rgb(h)
    return f"rgba({r},{g},{b},{alfa})"


def _luminancia(h: str) -> float:
    def canal(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def texto_sobre(fondo: str) -> str:
    """Negro o blanco, el que más contraste haga sobre ese fondo."""
    return "#000000" if _luminancia(fondo) > 0.42 else "#FFFFFF"



PREDETERMINADO = "claro"

# Semáforo de cada tema: (fondo, borde/texto, barra)
_SEM_CLARO = {"verde": ("#E8F5EC", "#1E7B3C", "#2E9A4E"), "amarillo": ("#FFF6DB", "#8A6100", "#D99A00"),
              "rojo": ("#FDECEA", "#B3261E", "#D1372C"), "sin_definir": ("#F3F5F9", "#52514E", "#8C8C88")}
_SEM_OSCURO = {"verde": ("#11291D", "#4ADE80", "#34C26A"), "amarillo": ("#2D2611", "#FACC15", "#E3B10E"),
               "rojo": ("#331719", "#F87171", "#EF4444"), "sin_definir": ("#1F2940", "#AAB2C3", "#6B7487")}


def _tema(nombre: str, descripcion: str, grupo: str, oscuro: bool, **colores) -> dict:
    t = {"nombre": nombre, "descripcion": descripcion, "grupo": grupo, "oscuro": oscuro,
         "semaforo": _SEM_OSCURO if oscuro else _SEM_CLARO}
    t.update(colores)
    t.setdefault("acento", t["primario"])
    t.setdefault("sobre_acento", texto_sobre(t["acento"]))
    return t


TEMAS: dict[str, dict] = {
    # ---- Institucionales (colores de la Pontificia Universidad Javeriana: azul #2C5697, azul profundo #195793,
    #      amarillo #F8CD00, tomados de javeriana.edu.co)
    "claro": _tema(
        "Javeriana", "El institucional: blanco, azul Javeriana y el amarillo de la universidad.", "Institucionales",
        False, fondo="#FFFFFF", lateral="#F3F6FB", superficie="#FFFFFF", superficie2="#F2F5FA", linea="#E9EEF5",
        borde="#DDE4EE", borde_fuerte="#C3CFE2", texto="#16243D", texto_sec="#4A5568", texto_ter="#667085",
        primario="#2C5697", sobre_primario="#FFFFFF", acento="#F8CD00", sobre_acento="#16305C",
        marca_1="#195793", marca_2="#2C5697", marketing="#2C5697", utility="#E07B1A", grilla="#E6EAF0",
        unidades=["#F8CD00", "#2E9A4E", "#2C5697", "#8E5BD0", "#D1495B", "#1C9AA0", "#6B7A8F", "#C26A2E"]),
    "javeriana_noche": _tema(
        "Javeriana noche", "Azul profundo de la universidad con acentos amarillos.", "Institucionales",
        True, fondo="#0B1A30", lateral="#0E2140", superficie="#12284B", superficie2="#173159", linea="#1F3B66",
        borde="#24457A", borde_fuerte="#335A96", texto="#EEF3FB", texto_sec="#B7C6DE", texto_ter="#8FA3C4",
        primario="#F8CD00", sobre_primario="#0B1A30", acento="#F8CD00", sobre_acento="#0B1A30",
        marca_1="#195793", marca_2="#2C5697", marca_texto="#FFFFFF", marketing="#7FB0FF", utility="#FFB454",
        grilla="#1F3B66",
        unidades=["#F8CD00", "#4ADE80", "#7FB0FF", "#C084FC", "#FB7185", "#2DD4BF", "#94A3B8", "#FB923C"]),
    "institucional_clasico": _tema(
        "Azul clásico", "El primer diseño del tablero: blanco con azul marino.", "Institucionales",
        False, fondo="#FFFFFF", lateral="#F4F6FA", superficie="#FFFFFF", superficie2="#F3F5F9", linea="#ECEFF4",
        borde="#E3E7EE", borde_fuerte="#C9D3E3", texto="#1B1F24", texto_sec="#52514E", texto_ter="#6B6F76",
        primario="#1F3864", sobre_primario="#FFFFFF", marketing="#2A78D6", utility="#EB6834", grilla="#E6E8EC",
        unidades=["#E0A21B", "#2E9A4E", "#2F6FD6", "#8E5BD0", "#D1495B", "#1C9AA0", "#6B7A8F", "#C26A2E"]),
    # ---- Oscuros
    "oscuro": _tema(
        "Oscuro", "Fondo azul noche, cómodo para la vista con poca luz.", "Oscuros",
        True, fondo="#0F1420", lateral="#131A28", superficie="#182032", superficie2="#1F2940", linea="#263049",
        borde="#2C3752", borde_fuerte="#3C4A6B", texto="#E7EAF0", texto_sec="#AAB2C3", texto_ter="#8791A7",
        primario="#6EA8FE", sobre_primario="#0B1220", marketing="#5AA2F0", utility="#F28A55", grilla="#283247",
        unidades=["#F2C14E", "#4ADE80", "#60A5FA", "#C084FC", "#FB7185", "#2DD4BF", "#94A3B8", "#FB923C"]),
    "carbon": _tema(
        "Carbón", "Grafito neutro con acento turquesa, sin tintes azules.", "Oscuros",
        True, fondo="#161616", lateral="#1C1C1C", superficie="#222222", superficie2="#2A2A2A", linea="#303030",
        borde="#363636", borde_fuerte="#4A4A4A", texto="#EDEDED", texto_sec="#B5B5B5", texto_ter="#8F8F8F",
        primario="#3DDBD9", sobre_primario="#0E0E0E", marketing="#78A9FF", utility="#FF8C61", grilla="#333333",
        semaforo={"verde": ("#15281C", "#42BE65", "#24A148"), "amarillo": ("#2A2613", "#F1C21B", "#D2A106"),
                  "rojo": ("#2D1719", "#FF8389", "#DA1E28"), "sin_definir": ("#2A2A2A", "#B5B5B5", "#6F6F6F")},
        unidades=["#F1C21B", "#42BE65", "#78A9FF", "#BE95FF", "#FF7EB6", "#3DDBD9", "#A8A8A8", "#FF8C61"]),
    "medianoche": _tema(
        "Medianoche violeta", "Morado muy oscuro con acentos lavanda.", "Oscuros",
        True, fondo="#140F22", lateral="#19132B", superficie="#201833", superficie2="#281F3F", linea="#30264A",
        borde="#382C56", borde_fuerte="#4C3D72", texto="#EEEAF7", texto_sec="#BDB3D6", texto_ter="#958AB2",
        primario="#B794F6", sobre_primario="#140F22", marketing="#8AB4F8", utility="#F6AD55", grilla="#30264A",
        unidades=["#F6E05E", "#68D391", "#8AB4F8", "#B794F6", "#F687B3", "#4FD1C5", "#A0AEC0", "#F6AD55"]),
    "bosque_noche": _tema(
        "Bosque nocturno", "Verde muy oscuro, sereno, con acento menta.", "Oscuros",
        True, fondo="#0E1A15", lateral="#11201A", superficie="#16291F", superficie2="#1C3327", linea="#23402F",
        borde="#294A37", borde_fuerte="#376249", texto="#E8F3EC", texto_sec="#AFC8B9", texto_ter="#86A593",
        primario="#5EE6A8", sobre_primario="#0E1A15", marketing="#74B9FF", utility="#FFB86B", grilla="#23402F",
        unidades=["#F6D365", "#5EE6A8", "#74B9FF", "#C3A6FF", "#FF8FA3", "#4FD1C5", "#9DB4A6", "#FFB86B"]),
    # ---- Claros de color
    "otono": _tema(
        "Otoño", "Tonos crema y café, cálidos y suaves.", "Claros de color",
        False, fondo="#FBF6EE", lateral="#F3E9DA", superficie="#FFFDF8", superficie2="#F5ECDD", linea="#ECE1CE",
        borde="#E2D3BA", borde_fuerte="#CDB896", texto="#2E2219", texto_sec="#6B5643", texto_ter="#8A7360",
        primario="#8B4A1C", sobre_primario="#FFFFFF", acento="#D19A1B", marketing="#2F6F8F", utility="#C0661E",
        grilla="#EADFCB",
        semaforo={"verde": ("#EAF2E1", "#3F6B21", "#5E8C31"), "amarillo": ("#FBEFD3", "#8A5A00", "#D19A1B"),
                  "rojo": ("#F8E3DC", "#9C2B1B", "#C2412B"), "sin_definir": ("#F5ECDD", "#6B5643", "#A08C77")},
        unidades=["#D19A1B", "#5E8C31", "#2F6F8F", "#8B4A1C", "#B5523B", "#7C6A9A", "#8A7360", "#C0661E"]),
    "vino": _tema(
        "Vino tinto", "Rosados claros con acento vino tinto.", "Claros de color",
        False, fondo="#FCF8F8", lateral="#F6ECEE", superficie="#FFFFFF", superficie2="#F7EEF0", linea="#F0E3E6",
        borde="#E8D5DA", borde_fuerte="#D4B3BC", texto="#2A1A1F", texto_sec="#6A4C55", texto_ter="#8A6C75",
        primario="#7A1F35", sobre_primario="#FFFFFF", marketing="#A3324E", utility="#C7782A", grilla="#EFE1E4",
        semaforo={"verde": ("#E9F3EC", "#226B3A", "#2F8F4E"), "amarillo": ("#FCF1D9", "#8A5A00", "#D19A1B"),
                  "rojo": ("#FBE4E6", "#A11D2E", "#C9283D"), "sin_definir": ("#F7EEF0", "#6A4C55", "#A38990")},
        unidades=["#C7782A", "#2F8F4E", "#4F6D9A", "#7A1F35", "#D45D79", "#3E8A8A", "#8A6C75", "#9C6ADE"]),
    "oceano": _tema(
        "Océano", "Azules y turquesas frescos sobre blanco.", "Claros de color",
        False, fondo="#F7FBFC", lateral="#EAF4F7", superficie="#FFFFFF", superficie2="#EEF6F8", linea="#E0EEF2",
        borde="#D3E5EA", borde_fuerte="#AECDD6", texto="#12303A", texto_sec="#4B6670", texto_ter="#6C858E",
        primario="#0E6E83", sobre_primario="#FFFFFF", acento="#16A3B8", marketing="#1F78B4", utility="#F28C28",
        grilla="#E0EEF2",
        unidades=["#F2B705", "#2A9D8F", "#1F78B4", "#7B61FF", "#E76F51", "#16A3B8", "#6C858E", "#F28C28"]),
    "bosque": _tema(
        "Bosque", "Verdes naturales, tranquilos y legibles.", "Claros de color",
        False, fondo="#F7FAF6", lateral="#EDF4EA", superficie="#FFFFFF", superficie2="#EFF5EC", linea="#E3EDDF",
        borde="#D6E3D0", borde_fuerte="#B3CBA9", texto="#1C2B1E", texto_sec="#4F6150", texto_ter="#6C7F6D",
        primario="#2F6B3A", sobre_primario="#FFFFFF", acento="#7DB04B", marketing="#2E6FA7", utility="#D9822B",
        grilla="#E3EDDF",
        unidades=["#E0A21B", "#7DB04B", "#2E6FA7", "#8E5BD0", "#C8553D", "#2A9D8F", "#6C7F6D", "#D9822B"]),
    "lavanda": _tema(
        "Lavanda", "Morados suaves y luminosos.", "Claros de color",
        False, fondo="#FAF8FD", lateral="#F1ECF9", superficie="#FFFFFF", superficie2="#F3EFFA", linea="#E9E2F4",
        borde="#DDD3EE", borde_fuerte="#C2B2E0", texto="#241B33", texto_sec="#5A4E70", texto_ter="#7A6E90",
        primario="#5B3E96", sobre_primario="#FFFFFF", acento="#9B7BD8", marketing="#3F6FD8", utility="#E58A3A",
        grilla="#E9E2F4",
        unidades=["#E8B10E", "#3BA272", "#3F6FD8", "#9B7BD8", "#E0607E", "#2BA3A3", "#7A6E90", "#E58A3A"]),
    "minimal": _tema(
        "Grafito claro", "Grises neutros y sobrios, sin color de marca.", "Claros de color",
        False, fondo="#FAFAFA", lateral="#F2F2F2", superficie="#FFFFFF", superficie2="#F4F4F5", linea="#E7E7E9",
        borde="#DCDCE0", borde_fuerte="#BDBDC4", texto="#18181B", texto_sec="#52525B", texto_ter="#71717A",
        primario="#27272A", sobre_primario="#FFFFFF", marketing="#2563EB", utility="#EA580C", grilla="#E7E7E9",
        unidades=["#CA8A04", "#16A34A", "#2563EB", "#9333EA", "#DC2626", "#0891B2", "#71717A", "#EA580C"]),
    # ---- Accesibilidad
    "contraste": _tema(
        "Alto contraste oscuro", "Fondo negro, texto blanco y colores neón. Para baja visión.", "Accesibilidad",
        True, contraste=True, fondo="#000000", lateral="#000000", superficie="#000000", superficie2="#111111",
        linea="#5A5A5A", borde="#FFFFFF", borde_fuerte="#FFFFFF", texto="#FFFFFF", texto_sec="#F2F2F2",
        texto_ter="#DCDCDC", primario="#FFE600", sobre_primario="#000000", marketing="#00E5FF", utility="#FF4FD8",
        grilla="#4D4D4D", marca_1="#000000", marca_2="#000000", marca_texto="#FFFFFF",
        semaforo={"verde": ("#002B12", "#39FF14", "#39FF14"), "amarillo": ("#2B2600", "#FFE600", "#FFE600"),
                  "rojo": ("#330000", "#FF4D4D", "#FF4D4D"), "sin_definir": ("#111111", "#FFFFFF", "#BBBBBB")},
        unidades=["#FFE600", "#39FF14", "#00E5FF", "#FF4FD8", "#FF9F1C", "#B388FF", "#FFFFFF", "#FF4D4D"]),
    "contraste_claro": _tema(
        "Alto contraste claro", "Fondo blanco, texto negro y bordes marcados. Para baja visión con luz.",
        "Accesibilidad", False, contraste=True, fondo="#FFFFFF", lateral="#FFFFFF", superficie="#FFFFFF",
        superficie2="#F2F2F2", linea="#8A8A8A", borde="#000000", borde_fuerte="#000000", texto="#000000",
        texto_sec="#1A1A1A", texto_ter="#2B2B2B", primario="#0033CC", sobre_primario="#FFFFFF", marketing="#0033CC",
        utility="#B34700", grilla="#9A9A9A", marca_1="#000000", marca_2="#000000", marca_texto="#FFFFFF",
        semaforo={"verde": ("#E6F4EA", "#00591F", "#00802B"), "amarillo": ("#FFF4CC", "#5C4300", "#B38600"),
                  "rojo": ("#FDE2E2", "#8B0000", "#C40000"), "sin_definir": ("#F2F2F2", "#000000", "#595959")},
        unidades=["#B38600", "#00802B", "#0033CC", "#6A1B9A", "#C40000", "#00727A", "#404040", "#B34700"]),
    "daltonismo": _tema(
        "Apto para daltonismo", "Paleta Okabe-Ito: se distingue con cualquier tipo de daltonismo.", "Accesibilidad",
        False, fondo="#FFFFFF", lateral="#F5F6F8", superficie="#FFFFFF", superficie2="#F4F5F7", linea="#E8EAED",
        borde="#DCDFE4", borde_fuerte="#BFC5CE", texto="#1A1D21", texto_sec="#4D535C", texto_ter="#69707A",
        primario="#0072B2", sobre_primario="#FFFFFF", acento="#E69F00", marketing="#0072B2", utility="#E69F00",
        grilla="#E8EAED",
        semaforo={"verde": ("#E3F4EF", "#00684C", "#009E73"), "amarillo": ("#FDF1DC", "#7A5200", "#E69F00"),
                  "rojo": ("#FBE8DE", "#9A3D00", "#D55E00"), "sin_definir": ("#F4F5F7", "#4D535C", "#8C939D")},
        unidades=["#E69F00", "#009E73", "#0072B2", "#CC79A7", "#D55E00", "#56B4E9", "#69707A", "#F0E442"]),
}
GRUPOS = ["Institucionales", "Oscuros", "Claros de color", "Accesibilidad"]

# Colores que cada persona puede cambiar encima del tema
PERSONALIZABLES = {"primario": "Color principal", "acento": "Color de acento", "marketing": "Marketing",
                   "utility": "Utility"}


# ---------------------------------------------------------------------------
# Tema final de una persona
# ---------------------------------------------------------------------------

def resolver(nombre: str | None, propios: dict | None = None) -> dict:
    """Tema con los colores que la persona cambió encima, más los colores derivados."""
    base = TEMAS.get(nombre or PREDETERMINADO, TEMAS[PREDETERMINADO])
    t = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v) for k, v in base.items()}
    t["clave"] = nombre if nombre in TEMAS else PREDETERMINADO
    for k, v in (propios or {}).items():
        if k in PERSONALIZABLES and es_hex(v):
            t[k] = v.upper()
    if (propios or {}).get("primario") and es_hex(propios["primario"]):
        t["sobre_primario"] = texto_sobre(t["primario"])
    if (propios or {}).get("acento") and es_hex(propios["acento"]):
        t["sobre_acento"] = texto_sobre(t["acento"])
    oscuro, sup = t["oscuro"], t["superficie"]
    # Derivados: tonos suaves para fondos y bordes, y versiones legibles como texto
    t["primario_hover"] = mezclar(t["primario"], "#FFFFFF" if oscuro else "#000000", 0.18)
    t["primario_suave"] = mezclar(t["primario"], sup, 0.86 if not oscuro else 0.80)
    for tipo in ("marketing", "utility"):
        c = t[tipo]
        t[f"{tipo}_suave"] = mezclar(c, sup, 0.88 if not oscuro else 0.80)
        t[f"{tipo}_borde"] = mezclar(c, sup, 0.60 if not oscuro else 0.45)
        t[f"{tipo}_texto"] = c if oscuro else mezclar(c, "#000000", 0.25)
    return t


def semaforo(t: dict) -> dict:
    etiquetas = {"verde": "Normal", "amarillo": "Atención", "rojo": "Crítico", "sin_definir": "Sin asignación"}
    return {k: {"fondo": f, "borde": b, "barra": ba, "etiqueta": etiquetas[k]}
            for k, (f, b, ba) in t["semaforo"].items()}


def variables(t: dict) -> str:
    """Variables CSS del tema (--t-...)."""
    s = t["semaforo"]
    pares = {
        "fondo": t["fondo"], "lateral": t["lateral"], "superficie": t["superficie"], "superficie2": t["superficie2"],
        "linea": t["linea"], "borde": t["borde"], "borde-fuerte": t["borde_fuerte"],
        "texto": t["texto"], "texto-sec": t["texto_sec"], "texto-ter": t["texto_ter"],
        "primario": t["primario"], "primario-hover": t["primario_hover"], "primario-suave": t["primario_suave"],
        "sobre-primario": t["sobre_primario"],
        "mkt": t["marketing"], "mkt-suave": t["marketing_suave"], "mkt-borde": t["marketing_borde"],
        "mkt-texto": t["marketing_texto"],
        "uti": t["utility"], "uti-suave": t["utility_suave"], "uti-borde": t["utility_borde"],
        "uti-texto": t["utility_texto"],
        "verde-fondo": s["verde"][0], "verde-borde": s["verde"][1], "verde-barra": s["verde"][2],
        "verde-suave": mezclar(s["verde"][1], t["superficie"], 0.65),
        "amarillo-fondo": s["amarillo"][0], "amarillo-borde": s["amarillo"][1], "amarillo-barra": s["amarillo"][2],
        "amarillo-suave": mezclar(s["amarillo"][1], t["superficie"], 0.65),
        "marca-1": t.get("marca_1") or (mezclar(t["primario"], t["fondo"], 0.72) if t["oscuro"] else t["primario"]),
        "marca-2": t.get("marca_2") or (mezclar(t["primario"], t["fondo"], 0.55) if t["oscuro"] else t["primario_hover"]),
        "marca-texto": t.get("marca_texto") or (t["texto"] if t["oscuro"] else t["sobre_primario"]),
        "acento": t["acento"], "sobre-acento": t["sobre_acento"],
        "acento-suave": mezclar(t["acento"], t["superficie"], 0.82),
        "sombra": "none" if t["oscuro"] else "0 1px 3px rgba(16,24,40,0.06)",
        "sombra-primario": "none" if t["oscuro"] else f"0 3px 8px {rgba(t['primario'], 0.25)}",
    }
    return ":root {" + " ".join(f"--t-{k}: {v};" for k, v in pares.items()) + "}"


def css(t: dict) -> str:
    """Estilos del tema: variables y, si no es el claro, la adaptación de los elementos de Streamlit."""
    reglas = [variables(t)]
    # Color principal en los elementos de Streamlit (en todos los temas)
    reglas.append("""
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
  background: var(--t-primario) !important; border-color: var(--t-primario) !important; color: var(--t-sobre-primario) !important;}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
  background: var(--t-primario-hover) !important; border-color: var(--t-primario-hover) !important;}
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-primaryFormSubmit"] p {color: var(--t-sobre-primario) !important;}
.stTabs [data-baseweb="tab-highlight"] {background-color: var(--t-primario) !important;}
.stTabs [data-baseweb="tab"][aria-selected="true"] p {color: var(--t-primario) !important;}
button[data-variant="segmented_control"][aria-checked="true"] {background: var(--t-acento) !important;
  border-color: var(--t-acento) !important;}
button[data-variant="segmented_control"][aria-checked="true"] p,
button[data-variant="segmented_control"][aria-checked="true"] span {color: var(--t-sobre-acento) !important;}
.marca {border-bottom: 4px solid var(--t-acento);}
.marca-producto {background: var(--t-acento) !important; color: var(--t-sobre-acento) !important;}
.titulo-texto {border-bottom: 3px solid var(--t-acento); display: inline-block; padding-bottom: 2px;}
a, [data-testid="stMarkdownContainer"] a {color: var(--t-primario) !important;}
""")
    if not t["oscuro"] and t["fondo"] == "#FFFFFF" and t["superficie"] == "#FFFFFF" and not t.get("contraste"):
        return "<style>" + "\n".join(reglas) + "</style>"
    reglas.append("""
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stHeader"],
[data-testid="stBottomBlockContainer"] {background: var(--t-fondo) !important; color: var(--t-texto);}
[data-testid="stSidebar"], [data-testid="stSidebarContent"] {background: var(--t-lateral) !important;}
.stApp, .stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] p, [data-testid="stMetricValue"],
[data-testid="stExpander"] summary p, [data-testid="stHeadingWithActionElements"] {color: var(--t-texto);}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p, [data-testid="stMetricDelta"] {color: var(--t-texto-ter);}
[data-testid="stMetricLabel"] p {color: var(--t-texto-sec) !important;}
body {background: var(--t-fondo);}
[data-testid="stSelectbox"] div:has(> input), [data-testid="stMultiSelect"] div:has(> input),
[data-testid="stTextInput"] div:has(> input), [data-testid="stDateInput"] div:has(> input),
[data-testid="stNumberInput"] div:has(> input), [data-testid="stTextArea"] div:has(> textarea),
[data-testid="stSelectbox"] input, [data-testid="stMultiSelect"] input {
  background: var(--t-superficie2) !important; color: var(--t-texto) !important; border-color: var(--t-borde) !important;}
[data-testid="stSelectbox"] svg, [data-testid="stMultiSelect"] svg, [data-testid="stDateInput"] svg {color: var(--t-texto-sec); fill: var(--t-texto-sec);}
[data-testid="stSelectboxVirtualDropdown"], [data-testid="stMultiSelectVirtualDropdown"],
[data-testid="stSelectboxVirtualDropdown"] [role="listbox"] {background: var(--t-superficie) !important;
  border-color: var(--t-borde) !important;}
[data-testid="stSelectboxVirtualDropdown"] [role="option"], [data-testid="stMultiSelectVirtualDropdown"] [role="option"] {color: var(--t-texto) !important;}
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"],
[data-testid="stDateInputField"], [data-baseweb="input"] input, [data-baseweb="base-input"] input, textarea {
  background: var(--t-superficie2) !important; color: var(--t-texto) !important; border-color: var(--t-borde) !important;}
[data-baseweb="select"] span, [data-baseweb="select"] div, [data-baseweb="select"] svg {color: var(--t-texto);}
input::placeholder, textarea::placeholder {color: var(--t-texto-ter) !important;}
[data-baseweb="popover"] ul, [data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"],
[data-baseweb="calendar"], [data-baseweb="calendar"] div {background: var(--t-superficie) !important; color: var(--t-texto);}
[data-baseweb="popover"] li, [role="option"] {color: var(--t-texto) !important;}
[data-baseweb="popover"] li:hover, [role="option"]:hover, [role="option"][aria-selected="true"] {background: var(--t-superficie2) !important;}
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"],
[data-testid="stPopoverButton"], [data-testid="stDownloadButton"] button, [data-testid="stBaseButton-minimal"] {
  background: var(--t-superficie) !important; color: var(--t-texto) !important; border-color: var(--t-borde-fuerte) !important;}
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stPopoverButton"]:hover {border-color: var(--t-primario) !important;
  color: var(--t-primario) !important;}
[data-testid="stBaseButton-secondary"] p, [data-testid="stBaseButton-tertiary"] p, [data-testid="stBaseButton-tertiary"] {color: var(--t-texto) !important;}
[data-testid="stBaseButton-tertiary"]:hover {background: var(--t-superficie2) !important;}
[data-testid="stBaseButton-secondary"]:disabled, [data-testid="stBaseButton-primary"]:disabled {opacity: 0.45;}
button[data-variant="segmented_control"] {background: var(--t-superficie) !important; border-color: var(--t-borde-fuerte) !important;}
button[data-variant="segmented_control"] p, button[data-variant="segmented_control"] span {color: var(--t-texto);}
.stTabs [data-baseweb="tab"] p {color: var(--t-texto-sec);}
.stTabs [data-baseweb="tab-border"] {background-color: var(--t-borde) !important;}
[data-testid="stExpander"] details {background: var(--t-superficie) !important; border-color: var(--t-borde) !important;}
[data-testid="stExpander"] summary:hover p {color: var(--t-primario);}
[data-testid="stPopoverBody"], [data-baseweb="popover"] > div {background: var(--t-superficie) !important; color: var(--t-texto);
  border-color: var(--t-borde) !important;}
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stForm"] {border-color: var(--t-borde) !important;}
[data-testid="stFileUploaderDropzone"] {background: var(--t-superficie2) !important; color: var(--t-texto);}
[data-testid="stFileUploaderDropzone"] span, [data-testid="stFileUploaderDropzone"] small {color: var(--t-texto-sec) !important;}
[data-testid="stAlertContainer"] p, [data-testid="stAlertContainer"] li {color: var(--t-texto) !important;}
[data-testid="stCheckbox"] label span, [data-testid="stRadio"] label span {border-color: var(--t-borde-fuerte);}
[data-testid="stToast"] {background: var(--t-superficie) !important; color: var(--t-texto);}
[data-testid="stSidebarCollapseButton"] svg, [data-testid="stExpandSidebarButton"] svg,
[data-testid="stMainMenu"] svg, [data-testid="stToolbar"] svg {color: var(--t-texto-sec); fill: var(--t-texto-sec);}
hr {border-color: var(--t-borde) !important;}
code {background: var(--t-superficie2); color: var(--t-texto);}
""")
    if t["oscuro"]:
        # Las tablas de Streamlit se dibujan en un lienzo con colores fijos: se invierten para el modo oscuro
        reglas.append("""
[data-testid="stDataFrame"], [data-testid="stDataEditor"], [data-testid="stTable"] {
  filter: invert(0.92) hue-rotate(180deg); border-radius: 8px;}
""")
    if t.get("contraste"):
        reglas.append("""
html, .stApp {font-size: 17px;}
[data-testid="stBaseButton-secondary"], [data-testid="stPopoverButton"], button[data-variant="segmented_control"],
[data-baseweb="select"] > div, [data-baseweb="input"], [data-testid="stMetric"] {border-width: 2px !important;}
a {text-decoration: underline;}
*:focus-visible {outline: 3px solid var(--t-primario) !important; outline-offset: 2px;}
.semaforo-item {border-width: 2px !important; border-left-width: 8px !important;}
""")
    return "<style>" + "\n".join(reglas) + "</style>"


def muestra(t: dict) -> str:
    """Miniatura del tema para elegirlo (HTML)."""
    s = t["semaforo"]
    return (f'<div style="border:1px solid {t["borde"]}; border-radius:12px; overflow:hidden; background:{t["fondo"]};">'
            f'<div style="display:flex; height:86px;">'
            f'<div style="width:28%; background:{t["lateral"]}; border-right:1px solid {t["borde"]}; padding:8px;">'
            f'<div style="height:16px; border-radius:5px; background:{t["primario"]};"></div>'
            f'<div style="height:8px; margin-top:8px; border-radius:4px; background:{t["borde"]};"></div>'
            f'<div style="height:8px; margin-top:5px; width:70%; border-radius:4px; background:{t["borde"]};"></div></div>'
            f'<div style="flex:1; padding:8px; display:flex; flex-direction:column; gap:6px;">'
            f'<div style="height:9px; width:60%; border-radius:4px; background:{t["texto"]}; opacity:.85;"></div>'
            f'<div style="display:flex; gap:5px;">'
            + "".join(f'<div style="flex:1; height:26px; border-radius:6px; background:{s[k][0]}; '
                      f'border-left:4px solid {s[k][1]};"></div>' for k in ("verde", "amarillo", "rojo"))
            + '</div><div style="display:flex; gap:4px; align-items:flex-end; height:22px;">'
            + "".join(f'<div style="flex:1; height:{h}px; border-radius:2px 2px 0 0; background:{c};"></div>'
                      for h, c in ((10, t["marketing"]), (18, t["marketing"]), (14, t["utility"]), (22, t["marketing"]),
                                   (8, t["utility"])))
            + '</div></div></div></div>')
