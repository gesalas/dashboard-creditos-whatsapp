"""
Correos del dashboard de créditos de WhatsApp.

Arma el asunto, el texto plano y el HTML de:
- el informe de una unidad, para sus responsables (mercadeo, egresados, donaciones);
- el resumen general, para el equipo CRM.

El formato imita un correo institucional normal (texto, una tabla sobria y la firma
del equipo) para que se reconozca como un mensaje interno legítimo y no como publicidad
o phishing: asunto informativo sin urgencia, remitente y motivo claros, enlace visible
completo, sin adjuntos y sin pedir datos. El HTML usa tablas y estilos en línea porque
Outlook no muestra bien diseños modernos.
"""

from __future__ import annotations

from html import escape

import pandas as pd

import logica as L

NOMBRE_UNIDAD = L.NOMBRE_UNIDAD   # unidades configuradas en config.json

# Estado: solo un texto de color discreto (sin franjas ni alarmas visuales)
ESTADOS = {
    "verde": {"etiqueta": "Normal", "color": "#1E7B3C"},
    "amarillo": {"etiqueta": "Atención", "color": "#8A6100"},
    "rojo": {"etiqueta": "Crítico", "color": "#B3261E"},
    "sin_definir": {"etiqueta": "Sin créditos asignados", "color": "#52514E"},
}

FUENTE = "Calibri, 'Segoe UI', Arial, sans-serif"
TEXTO = "#1F1F1F"
GRIS = "#595959"
AZUL = "#1F4E79"       # azul de la firma institucional
BORDE = "#D9D9D9"
FONDO_ENCABEZADO = "#F2F2F2"

PLANTILLA_POR_DEFECTO = {
    "url_dashboard": "",
    "firma": {
        "nombre": "Equipo CRM",
        "area": "Dirección de Tecnologías de Información",
        "institucion": "Pontificia Universidad Javeriana",
        "direccion": ["Edificio Emilio Arango S.J, Piso 7", "Cra 7 # 42-60", "Bogotá, Colombia"],
        "correo": "",
    },
}


def plantilla_desde_config(cfg_alertas: dict) -> dict:
    """Datos de la firma y el enlace (alertas.json, sección "plantilla")."""
    base = {"url_dashboard": PLANTILLA_POR_DEFECTO["url_dashboard"], "firma": dict(PLANTILLA_POR_DEFECTO["firma"])}
    propia = cfg_alertas.get("plantilla", {}) or {}
    base["url_dashboard"] = propia.get("url_dashboard", base["url_dashboard"]) or ""
    base["firma"].update(propia.get("firma", {}) or {})
    return base


def num(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def pct(valor: float) -> str:
    """Formatea un porcentaje ya expresado en 0-100."""
    return f"{valor:.1f} %".replace(".", ",")


# ---------------------------------------------------------------------------
# Piezas de HTML
# ---------------------------------------------------------------------------

def _p(texto_html: str, estilo: str = "") -> str:
    return f'<p style="margin:0 0 12px 0; {estilo}">{texto_html}</p>'


def _tabla_datos(filas: list[tuple[str, str]]) -> str:
    """Tabla de dos columnas (dato, valor) con bordes finos."""
    cuerpo = "".join(
        f'<tr><td style="padding:6px 12px; border:1px solid {BORDE}; background:{FONDO_ENCABEZADO}; '
        f'width:55%;">{escape(e)}</td>'
        f'<td style="padding:6px 12px; border:1px solid {BORDE}; text-align:right;">{v}</td></tr>'
        for e, v in filas)
    return (f'<table cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin:4px 0 16px 0; '
            f'font-family:{FUENTE}; font-size:11pt; color:{TEXTO}; width:440px; max-width:100%;">{cuerpo}</table>')


def _tabla(encabezados: list[str], filas: list[list[str]], derecha: set[int]) -> str:
    th = "".join(
        f'<th style="padding:6px 12px; border:1px solid {BORDE}; background:{FONDO_ENCABEZADO}; '
        f'text-align:{"right" if i in derecha else "left"}; font-weight:bold;">{escape(h)}</th>'
        for i, h in enumerate(encabezados))
    cuerpo = "".join(
        "<tr>" + "".join(
            f'<td style="padding:6px 12px; border:1px solid {BORDE}; '
            f'text-align:{"right" if i in derecha else "left"};">{escape(str(v))}</td>'
            for i, v in enumerate(fila)) + "</tr>"
        for fila in filas)
    return (f'<table cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin:4px 0 16px 0; '
            f'font-family:{FUENTE}; font-size:11pt; color:{TEXTO};"><tr>{th}</tr>{cuerpo}</table>')


def _titulo_seccion(texto: str) -> str:
    """Título de sección (por ejemplo, el canal): azul institucional con una línea debajo."""
    return (f'<p style="margin:22px 0 8px 0; padding-bottom:4px; border-bottom:2px solid {AZUL}; color:{AZUL}; '
            f'font-size:12.5pt; font-weight:bold;">{escape(texto)}</p>')


def _subtitulo(texto: str) -> str:
    return f'<p style="margin:14px 0 4px 0; font-weight:bold; color:{TEXTO};">{escape(texto)}</p>'


def filas_saldo(consumido: float, disponible: float, etiqueta: str, uso_pct: float | None = None,
                estado: str | None = None) -> list[tuple[str, str]]:
    """Filas de una tablita de estado. Si se usó más de lo disponible, los disponibles son 0 y aparte se
    muestra cuánto se usó de más (lo que hay que reponer); nunca un saldo negativo."""
    filas = []
    if estado:
        filas.append(("Estado", _estado_html(estado)))
    filas.append((etiqueta, num(disponible) if disponible > 0 else "Sin asignar"))
    uso_txt = f" ({pct(uso_pct)})" if uso_pct is not None else ""
    filas.append(("Créditos utilizados", num(consumido) + uso_txt))
    if disponible > 0:
        restan = disponible - consumido
        filas.append(("Créditos disponibles", num(max(restan, 0))))
        if restan < 0:
            filas.append(("Utilizados de más (por reponer)", f'<b style="color:{ESTADOS["rojo"]["color"]};">'
                                                             f'{num(-restan)}</b>'))
    return filas


def columna_saldo(consumido: float, disponible: float, amarillo_pct: float, rojo_pct: float) -> dict[str, str]:
    """Valores de una columna (Total, UCP u Outbound) para las tablas por columnas del correo del equipo."""
    uso = consumido / disponible * 100 if disponible > 0 else None
    estado = L.estado_consumo(uso, amarillo_pct, rojo_pct)
    restan = disponible - consumido
    return {
        "estado": _estado_html(estado) if disponible > 0 else ("Sin asignar" if consumido > 0 else "-"),
        "disponible": num(disponible) if disponible > 0 else "-",
        "utilizados": num(consumido) + (f"<br><span style='color:{GRIS}; font-size:9.5pt;'>{pct(uso)}</span>"
                                        if uso is not None else ""),
        "libres": num(max(restan, 0)) if disponible > 0 else "-",
        "de_mas": (f'<b style="color:{ESTADOS["rojo"]["color"]};">{num(-restan)}</b>'
                   if disponible > 0 and restan < 0 else ("-" if disponible > 0 or consumido <= 0 else num(consumido))),
    }


def tabla_columnas(columnas: dict[str, dict[str, str]], etiqueta_disponible: str) -> str:
    """Tabla compacta: una fila por dato y una columna por ámbito (Total, UCP, Outbound)."""
    filas = [("Estado", "estado"), (etiqueta_disponible, "disponible"), ("Créditos utilizados", "utilizados"),
             ("Créditos disponibles", "libres")]
    if any(c["de_mas"] not in ("-",) for c in columnas.values()):
        filas.append(("Utilizados de más (por reponer)", "de_mas"))
    celda = f"padding:6px 10px; border:1px solid {BORDE};"
    ancho = f"{60 / max(len(columnas), 1):.0f}%"
    th = f'<th style="{celda} background:{FONDO_ENCABEZADO}; width:40%;"></th>' + "".join(
        f'<th style="{celda} background:{FONDO_ENCABEZADO}; text-align:right; font-weight:bold; width:{ancho};">'
        f'{escape(n)}</th>' for n in columnas)
    cuerpo = "".join(
        f'<tr><td style="{celda} background:{FONDO_ENCABEZADO};">{escape(etq)}</td>'
        + "".join(f'<td style="{celda} text-align:right;">{c[clave]}</td>' for c in columnas.values()) + "</tr>"
        for etq, clave in filas)
    return (f'<table cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin:4px 0 16px 0; '
            f'font-family:{FUENTE}; font-size:10.5pt; color:{TEXTO}; width:100%; max-width:640px; '
            f'table-layout:fixed;">'
            f'<tr>{th}</tr>{cuerpo}</table>')


def _texto_columnas(titulo: str, columnas: dict[str, dict[str, str]]) -> list[str]:
    lineas = [f"{titulo}:"]
    for nombre, c in columnas.items():
        partes = [f"{k}: {v}" for k, v in (("asignados/adquiridos", c["disponible"]), ("utilizados", c["utilizados"]),
                                           ("disponibles", c["libres"]), ("de más", c["de_mas"])) if v != "-"]
        texto = "; ".join(partes)
        for etiqueta in ("<br>", "</span>", "</b>"):
            texto = texto.replace(etiqueta, " " if etiqueta == "<br>" else "")
        while "<" in texto:
            texto = texto[:texto.index("<")] + texto[texto.index(">") + 1:]
        lineas.append(f"- {nombre}: {texto}")
    return lineas


def _texto_filas(filas: list[tuple[str, str]]) -> list[str]:
    limpio = []
    for e, v in filas:
        v = v.replace("</b>", "")
        while "<b" in v:
            v = v[:v.index("<b")] + v[v.index(">", v.index("<b")) + 1:]
        limpio.append(f"- {e}: {v}")
    return limpio


def _estado_html(estado: str) -> str:
    e = ESTADOS[estado]
    return f'<b style="color:{e["color"]};">{e["etiqueta"]}</b>'


def _firma(plantilla: dict, logo_src: str | None) -> str:
    f = plantilla["firma"]
    lineas = "".join(f"{escape(l)}<br>" for l in (f.get("direccion") or []))
    correo = f.get("correo") or ""
    correo_html = (f'<a href="mailto:{escape(correo)}" style="color:#0563C1;">{escape(correo)}</a>' if correo else "")
    texto = (f'<b style="color:{AZUL}; font-size:11pt;">{escape(f.get("nombre", ""))}</b><br>'
             f'<span style="color:{AZUL};">{escape(f.get("area", ""))}</span><br>'
             f'<span style="color:{AZUL};">{escape(f.get("institucion", ""))}</span><br><br>'
             f'<span style="color:{TEXTO};">{lineas}{correo_html}</span>')
    if logo_src:
        return (f'<table cellpadding="0" cellspacing="0" style="font-family:{FUENTE}; font-size:10.5pt;"><tr>'
                f'<td style="padding:0 24px 0 0; vertical-align:middle;">'
                f'<img src="{logo_src}" alt="{escape(f.get("institucion", ""))}" width="190" '
                f'style="display:block; border:0; width:190px; height:auto;"></td>'
                f'<td style="vertical-align:middle;">{texto}</td></tr></table>')
    return f'<div style="font-family:{FUENTE}; font-size:10.5pt;">{texto}</div>'


def _documento(asunto: str, cuerpo_html: str, plantilla: dict, logo_src: str | None, pie: str) -> str:
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{escape(asunto)}</title></head>'
            f'<body style="margin:0; padding:16px; background:#FFFFFF;">'
            f'<div style="font-family:{FUENTE}; font-size:11pt; color:{TEXTO}; line-height:1.4; max-width:680px;">'
            f'{cuerpo_html}'
            f'{_p("Cordial saludo,", f"margin-top:20px; color:{AZUL};")}'
            f'<div style="margin:18px 0 18px 0;">{_firma(plantilla, logo_src)}</div>'
            f'<p style="margin:0; font-size:9.5pt; color:{GRIS}; font-style:italic;">{pie}</p>'
            f'</div></body></html>')


def url_dashboard(plantilla: dict, unidad: str | None = None) -> str:
    """Dirección del dashboard; con una unidad, abre directo la vista de esa unidad (?unidad=...)."""
    url = (plantilla.get("url_dashboard") or "").strip()
    if url and unidad:
        url += ("&" if "?" in url else "?") + f"unidad={unidad}"
    return url


def _bloque_enlace(plantilla: dict, unidad: str | None = None) -> str:
    url = url_dashboard(plantilla, unidad)
    donde = f"la vista de {NOMBRE_UNIDAD.get(unidad, unidad)} en el" if unidad else "el"
    if url:
        return _p(f"Puedes consultar el detalle actualizado en {donde} dashboard de créditos de WhatsApp:<br>"
                  f'<a href="{escape(url)}" style="color:#0563C1;">{escape(url)}</a>')
    return _p("Puedes consultar el detalle en el dashboard de créditos de WhatsApp del Equipo CRM.")


def _bloque_contacto(plantilla: dict) -> str:
    correo = plantilla["firma"].get("correo") or ""
    if correo:
        return _p(f'Si tienes preguntas sobre esta información, escríbenos a '
                  f'<a href="mailto:{escape(correo)}" style="color:#0563C1;">{escape(correo)}</a>.')
    return _p("Si tienes preguntas sobre esta información, puedes responder a este correo.")


PIE_SEGURIDAD = ("Este mensaje no contiene archivos adjuntos ni te solicitará contraseñas o datos personales. "
                 "Si este mensaje fue enviado fuera de tu horario, por favor siéntete libre de atenderlo dentro "
                 "de tu jornada habitual.")


def _fecha_corte(info: dict) -> str:
    f = info.get("ultima_fecha_envio")
    return f"{f:%d/%m/%Y}" if f is not None else "-"


# ---------------------------------------------------------------------------
# Informe de una unidad
# ---------------------------------------------------------------------------

TOP_JOURNEYS = 10   # journeys con mayor consumo que se muestran en el correo de cada unidad


def informe_unidad(unidad: str, envios: pd.DataFrame, tarifas: pd.DataFrame, asignado: float,
                   amarillo_pct: float, rojo_pct: float, info: dict, motivo: str,
                   plantilla: dict | None = None, logo_src: str | None = None,
                   asignado_lineas: dict[str, float] | None = None) -> tuple[str, str, str]:
    """Asunto, texto plano y HTML del correo para los responsables de una unidad.

    `motivo`: "alerta" (cruzó un umbral) o "resumen" (resumen periódico).
    `logo_src`: origen de la imagen del logo en la firma ("cid:..." en Outlook o data URI en la vista previa).
    """
    plantilla = plantilla or plantilla_desde_config({})
    nombre = NOMBRE_UNIDAD.get(unidad, unidad.capitalize())
    datos = envios[envios["unidad"] == unidad]
    consumido = float(datos["creditos"].sum())
    uso = consumido / asignado * 100 if asignado > 0 else None
    estado = L.estado_consumo(uso, amarillo_pct, rojo_pct)
    restan = asignado - consumido
    corte = _fecha_corte(info)

    # Ritmo reciente y proyección (últimos 28 días, tarifas vigentes cada día)
    agotamiento_txt, semana_txt, ult7, prev7 = "-", "-", 0.0, 0.0
    if not datos.empty:
        fin = datos["fecha"].max()
        ult7 = float(datos.loc[datos["fecha"] > fin - pd.Timedelta(days=7), "creditos"].sum())
        prev7 = float(datos.loc[(datos["fecha"] <= fin - pd.Timedelta(days=7))
                                & (datos["fecha"] > fin - pd.Timedelta(days=14)), "creditos"].sum())
        proy = L.proyeccion(datos, fin - pd.Timedelta(days=27), fin, restan, tarifas=tarifas)
        semana_txt = num(proy["semana"]["creditos"])
        agot = proy["agotamiento"]
        if asignado <= 0:
            agotamiento_txt = "No aplica (sin créditos asignados)"
        elif agot == "agotado":
            agotamiento_txt = "Créditos asignados ya utilizados"
        elif isinstance(agot, pd.Timestamp):
            agotamiento_txt = f"{agot:%d/%m/%Y}"
        else:
            agotamiento_txt = "Sin consumo reciente"
    frase_semana = ""
    if prev7 > 0:
        cambio = (ult7 / prev7 - 1) * 100
        comparacion = (f"un {abs(cambio):.0f} % más que" if cambio > 0.5 else
                       f"un {abs(cambio):.0f} % menos que" if cambio < -0.5 else "lo mismo que")
        frase_semana = (f"En los últimos 7 días se utilizaron {num(ult7)} créditos, {comparacion} "
                        f"en los 7 días anteriores.")

    # Mensaje principal y recomendación según el estado
    if estado == "rojo" and uso is not None and uso >= 100:
        situacion = (f"la unidad ya utilizó el {pct(uso)} de los créditos asignados, es decir, "
                     f"{num(-restan)} créditos más de lo asignado")
        recomendacion = ("Antes de programar nuevos envíos de WhatsApp, te recomendamos coordinar con el Equipo CRM "
                         "la asignación de créditos adicionales para la unidad.")
    elif estado == "rojo":
        situacion = f"la unidad ya utilizó el {pct(uso)} de los créditos asignados"
        recomendacion = ("Quedan pocos créditos disponibles. Te recomendamos priorizar los envíos pendientes y, si se "
                         "necesitan más créditos, coordinarlo con el Equipo CRM.")
    elif estado == "amarillo":
        situacion = f"la unidad ya utilizó el {pct(uso)} de los créditos asignados"
        recomendacion = ("Te recomendamos revisar los envíos programados para las próximas semanas frente a la fecha "
                         "estimada de agotamiento, para planear con tiempo.")
    elif estado == "sin_definir":
        situacion = "la unidad no tiene créditos de WhatsApp asignados"
        recomendacion = "Si la unidad necesita realizar envíos, coordina con el Equipo CRM la asignación de créditos."
    else:
        situacion = f"la unidad ha utilizado el {pct(uso)} de los créditos asignados"
        recomendacion = "El consumo se encuentra dentro de lo esperado; no se requiere ninguna acción."

    uso_txt = pct(uso) if uso is not None else "-"
    if motivo == "resumen":
        asunto = f"Resumen semanal de créditos de WhatsApp - {nombre} (corte {corte})"
        intro = (f"Te compartimos el resumen semanal del uso de los créditos de WhatsApp asignados a "
                 f"<b>{escape(nombre)}</b>, con corte al {corte}.")
    else:
        asunto = f"Créditos de WhatsApp de {nombre}: {uso_txt} utilizado (corte {corte})"
        intro = (f"Te escribimos desde el Equipo CRM de la Dirección de Tecnologías de Información para informarte "
                 f"el estado de los créditos de WhatsApp asignados a <b>{escape(nombre)}</b>, con corte al {corte}.")

    filas = filas_saldo(consumido, asignado, "Créditos asignados", uso, estado) + [
        ("Consumo de los últimos 7 días", num(ult7)),
        ("Consumo estimado de la próxima semana", semana_txt),
        ("Fecha estimada de agotamiento", escape(agotamiento_txt)),
    ]

    # Cada línea de WhatsApp por separado (UCP y Outbound son bolsas distintas)
    cols_linea = {}
    if asignado_lineas:
        cols_linea["Total"] = columna_saldo(consumido, asignado, amarillo_pct, rojo_pct)
        for nombre_l, asignado_l in asignado_lineas.items():
            consumido_l = float(datos.loc[datos["linea"] == nombre_l, "creditos"].sum())
            cols_linea[nombre_l] = columna_saldo(consumido_l, asignado_l, amarillo_pct, rojo_pct)

    filas_journey = []
    if not datos.empty:
        fin = datos["fecha"].max()
        recientes = datos[datos["fecha"] > fin - pd.Timedelta(days=28)]
        top = (recientes.groupby("journey", as_index=False)[["deliveries", "creditos"]].sum()
                        .nlargest(TOP_JOURNEYS, "creditos"))
        filas_journey = [[r.journey.strip(), num(r.deliveries), num(r.creditos)] for r in top.itertuples()]

    if motivo == "resumen":
        motivo_pie = (f"Recibes este resumen semanal porque estás registrado como responsable de los créditos de "
                      f"WhatsApp de {nombre}.")
    else:
        motivo_pie = (f"Recibes este aviso porque estás registrado como responsable de los créditos de WhatsApp de "
                      f"{nombre}. Se envía automáticamente cuando el consumo de la unidad supera el "
                      f"{amarillo_pct:g} % o el {rojo_pct:g} % de lo asignado.")
    pie = escape(motivo_pie + " " + PIE_SEGURIDAD)

    cuerpo = (
        _p("Hola,")
        + _p(intro)
        + _p(f"A la fecha de corte, {escape(situacion)}.")
        + _titulo_seccion("WhatsApp")
        + _subtitulo("Total (ambas líneas)")
        + _tabla_datos(filas)
        + (_p(escape(frase_semana)) if frase_semana else "")
        + ((_subtitulo("Por línea (UCP y Outbound son bolsas separadas)")
            + tabla_columnas(cols_linea, "Créditos asignados")) if cols_linea else "")
        + _p(f"<b>Recomendación:</b> {escape(recomendacion)}")
        + ((_p(f"Estos son los {len(filas_journey)} journeys con mayor consumo de la unidad en los últimos 28 días:")
            + _tabla(["Journey", "Entregas", "Créditos"], filas_journey, {1, 2})) if filas_journey else "")
        + _bloque_enlace(plantilla, unidad)
        + _bloque_contacto(plantilla)
    )
    html = _documento(asunto, cuerpo, plantilla, logo_src, pie)

    # Texto plano (para clientes de correo que no muestran HTML)
    f = plantilla["firma"]
    texto = ["Hola,", "", intro.replace("<b>", "").replace("</b>", ""), "",
             f"A la fecha de corte, {situacion}.", ""]
    texto += ["WhatsApp - Total (ambas líneas):"] + _texto_filas(filas)
    if frase_semana:
        texto += ["", frase_semana]
    if cols_linea:
        texto += [""] + _texto_columnas("WhatsApp por línea", cols_linea)
    texto += ["", f"Recomendación: {recomendacion}"]
    if filas_journey:
        texto += ["", f"Los {len(filas_journey)} journeys con mayor consumo en los últimos 28 días:"]
        texto += [f"- {j}: {cr} créditos ({d} entregas)" for j, d, cr in filas_journey]
    if plantilla.get("url_dashboard"):
        texto += ["", f"Dashboard: {url_dashboard(plantilla, unidad)}"]
    texto += ["", "Cordial saludo,", "", f.get("nombre", ""), f.get("area", ""), f.get("institucion", "")]
    texto += list(f.get("direccion") or [])
    if f.get("correo"):
        texto.append(f["correo"])
    texto += ["", motivo_pie + " " + PIE_SEGURIDAD]
    return asunto, "\n".join(texto), html


# ---------------------------------------------------------------------------
# Resumen general para el equipo CRM
# ---------------------------------------------------------------------------

def informe_general(ambitos: list[dict], pendientes: list[dict], aviso_reporte: str | None, info: dict,
                    amarillo_pct: float, rojo_pct: float, plantilla: dict | None = None,
                    logo_src: str | None = None,
                    detalle_unidades: dict[str, dict[str, tuple[float, float]]] | None = None) -> tuple[str, str, str]:
    """Correo al equipo CRM con las alertas nuevas y el estado de todas las líneas y unidades."""
    plantilla = plantilla or plantilla_desde_config({})
    corte = _fecha_corte(info)
    if pendientes:
        peor = max(pendientes, key=lambda a: a["uso_pct"] or 0)
        if len(pendientes) == 1:
            asunto = f"Créditos de WhatsApp: {peor['nombre']} al {pct(peor['uso_pct'])} (corte {corte})"
        else:
            asunto = f"Créditos de WhatsApp: {len(pendientes)} alertas de consumo (corte {corte})"
    else:
        asunto = f"Créditos de WhatsApp: el reporte de consumo no se ha actualizado (corte {corte})"

    def col(a_consumido: float, a_disponible: float) -> dict[str, str]:
        return columna_saldo(a_consumido, a_disponible, amarillo_pct, rojo_pct)

    # Líneas: una sola tabla con columnas Total, UCP y Outbound
    nombres_linea = {"Total (ambas líneas)": "Total", "Línea UCP": "UCP", "Línea Outbound": "Outbound"}
    cols_lineas = {nombres_linea.get(a["nombre"], a["nombre"]): col(a["consumido"], a["disponible"])
                   for a in ambitos if a["tipo"] == "linea"}
    # Unidades: una tabla por unidad, con su total y su detalle en cada línea
    tablas_unidades = []
    for a in ambitos:
        if a["tipo"] != "unidad":
            continue
        columnas = {"Total": col(a["consumido"], a["disponible"])}
        for nombre_l, (cons_l, asig_l) in ((detalle_unidades or {}).get(a.get("unidad"), {}) or {}).items():
            columnas[nombre_l] = col(cons_l, asig_l)
        tablas_unidades.append((a["nombre"].replace("Unidad ", "", 1), columnas))

    lineas_alerta = [f"{a['nombre']}: {pct(a['uso_pct'])} utilizado (umbral de {a['umbral']:g} %)"
                     for a in pendientes]
    cuerpo = _p("Hola,") + _p(f"Este es el reporte automático de créditos de WhatsApp con corte al {corte}.")
    if pendientes:
        cuerpo += _p("Se superaron los siguientes umbrales de consumo desde el último aviso:")
        cuerpo += "<ul style=\"margin:0 0 12px 18px; padding:0;\">" + "".join(
            f"<li style=\"margin:0 0 4px 0;\">{escape(t)}</li>" for t in lineas_alerta) + "</ul>"
    if aviso_reporte:
        cuerpo += _p(f"<b>Reporte desactualizado:</b> {escape(aviso_reporte)}")
    cuerpo += _p("Este es el estado actual de los créditos: las líneas frente a los créditos adquiridos y las "
                 "unidades frente a los asignados.")
    cuerpo += _titulo_seccion("WhatsApp")
    if cols_lineas:
        cuerpo += _subtitulo("Líneas") + tabla_columnas(cols_lineas, "Créditos adquiridos")
    if tablas_unidades:
        cuerpo += _p("<b>Por unidad</b>, con lo que usó en cada línea (UCP y Outbound son bolsas separadas):",
                     f"margin:20px 0 4px 0; color:{AZUL};")
        cuerpo += "".join(_subtitulo(t) + tabla_columnas(c, "Créditos asignados") for t, c in tablas_unidades)
    detalle = []
    if info.get("generado"):
        detalle.append(f"reporte de Marketing Cloud generado el {info['generado']} (UTC)")
    if info.get("desde") is not None:
        detalle.append(f"consumo contado desde el {info['desde']:%d/%m/%Y}")
    if detalle:
        cuerpo += _p(escape("Fuente: " + "; ".join(detalle) + "."), f"font-size:10pt; color:{GRIS};")
    cuerpo += _bloque_enlace(plantilla)
    pie = escape("Recibes este reporte porque estás registrado en el aviso general de créditos de WhatsApp del "
                 "Equipo CRM. " + PIE_SEGURIDAD)
    html = _documento(asunto, cuerpo, plantilla, logo_src, pie)

    texto = ["Hola,", "", f"Este es el reporte automático de créditos de WhatsApp con corte al {corte}.", ""]
    if pendientes:
        texto += ["Se superaron los siguientes umbrales de consumo desde el último aviso:"]
        texto += [f"- {t}" for t in lineas_alerta] + [""]
    if aviso_reporte:
        texto += [f"Reporte desactualizado: {aviso_reporte}", ""]
    texto += ["Estado actual de los créditos de WhatsApp:"]
    if cols_lineas:
        texto += [""] + _texto_columnas("Líneas", cols_lineas)
    for t, c in tablas_unidades:
        texto += [""] + _texto_columnas(t, c)
    if plantilla.get("url_dashboard"):
        texto += ["", f"Dashboard: {plantilla['url_dashboard']}"]
    return asunto, "\n".join(texto), html
