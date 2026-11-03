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
            f'font-family:{FUENTE}; font-size:11pt; color:{TEXTO}; min-width:360px;">{cuerpo}</table>')


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

def informe_unidad(unidad: str, envios: pd.DataFrame, tarifas: pd.DataFrame, asignado: float,
                   amarillo_pct: float, rojo_pct: float, info: dict, motivo: str,
                   plantilla: dict | None = None, logo_src: str | None = None) -> tuple[str, str, str]:
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

    filas = [
        ("Estado", _estado_html(estado)),
        ("Créditos asignados", num(asignado) if asignado > 0 else "Sin asignar"),
        ("Créditos utilizados", f"{num(consumido)} ({uso_txt})" if uso is not None else num(consumido)),
        ("Créditos disponibles" if restan >= 0 or asignado <= 0 else "Créditos utilizados de más",
         num(abs(restan)) if asignado > 0 else "-"),
        ("Consumo de los últimos 7 días", num(ult7)),
        ("Consumo estimado de la próxima semana", semana_txt),
        ("Fecha estimada de agotamiento", escape(agotamiento_txt)),
    ]

    filas_journey = []
    if not datos.empty:
        fin = datos["fecha"].max()
        recientes = datos[datos["fecha"] > fin - pd.Timedelta(days=28)]
        top = (recientes.groupby("journey", as_index=False)[["deliveries", "creditos"]].sum()
                        .nlargest(3, "creditos"))
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
        + _tabla_datos(filas)
        + (_p(escape(frase_semana)) if frase_semana else "")
        + _p(f"<b>Recomendación:</b> {escape(recomendacion)}")
        + ((_p("Estos son los journeys con mayor consumo de la unidad en los últimos 28 días:")
            + _tabla(["Journey", "Entregas", "Créditos"], filas_journey, {1, 2})) if filas_journey else "")
        + _bloque_enlace(plantilla, unidad)
        + _bloque_contacto(plantilla)
    )
    html = _documento(asunto, cuerpo, plantilla, logo_src, pie)

    # Texto plano (para clientes de correo que no muestran HTML)
    f = plantilla["firma"]
    texto = ["Hola,", "", intro.replace("<b>", "").replace("</b>", ""), "",
             f"A la fecha de corte, {situacion}.", ""]
    for e, v in filas:
        limpio = v.replace(f'<b style="color:{ESTADOS[estado]["color"]};">', "").replace("</b>", "")
        texto.append(f"- {e}: {limpio}")
    if frase_semana:
        texto += ["", frase_semana]
    texto += ["", f"Recomendación: {recomendacion}"]
    if filas_journey:
        texto += ["", "Journeys con mayor consumo en los últimos 28 días:"]
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
                    logo_src: str | None = None) -> tuple[str, str, str]:
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

    def fila(a: dict) -> list[str]:
        estado = L.estado_consumo(a["uso_pct"], amarillo_pct, rojo_pct)
        restan = a["disponible"] - a["consumido"]
        return [a["nombre"], ESTADOS[estado]["etiqueta"],
                pct(a["uso_pct"]) if a["uso_pct"] is not None else "-",
                num(a["consumido"]), num(a["disponible"]) if a["disponible"] > 0 else "Sin asignar",
                (num(restan) if restan >= 0 else f"-{num(-restan)}") if a["disponible"] > 0 else "-"]

    lineas_alerta = [f"{a['nombre']}: {pct(a['uso_pct'])} utilizado (umbral de {a['umbral']:g} %)"
                     for a in pendientes]
    cuerpo = _p("Hola,") + _p(f"Este es el reporte automático de créditos de WhatsApp con corte al {corte}.")
    if pendientes:
        cuerpo += _p("Se superaron los siguientes umbrales de consumo desde el último aviso:")
        cuerpo += "<ul style=\"margin:0 0 12px 18px; padding:0;\">" + "".join(
            f"<li style=\"margin:0 0 4px 0;\">{escape(t)}</li>" for t in lineas_alerta) + "</ul>"
    if aviso_reporte:
        cuerpo += _p(f"<b>Reporte desactualizado:</b> {escape(aviso_reporte)}")
    cuerpo += _p("Estado actual de los créditos (las líneas frente a los créditos adquiridos; las unidades, frente "
                 "a los asignados):")
    cuerpo += _tabla(["Ámbito", "Estado", "Uso", "Utilizados", "Adquiridos o asignados", "Disponibles"],
                     [fila(a) for a in ambitos], {2, 3, 4, 5})
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
    texto += ["Estado actual de los créditos:"]
    texto += [f"- {r[0]}: {r[1]}, {r[2]} ({r[3]} de {r[4]})" for r in (fila(a) for a in ambitos)]
    if plantilla.get("url_dashboard"):
        texto += ["", f"Dashboard: {plantilla['url_dashboard']}"]
    return asunto, "\n".join(texto), html
