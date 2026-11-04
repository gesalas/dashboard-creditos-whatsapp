"""
Alertas de consumo de créditos de WhatsApp.

Revisa el consumo calculado a partir de data.xlsx (con la misma lógica del
dashboard) contra los créditos disponibles de config.json y envía un aviso
por correo y por Teams cuando se cruza un umbral (por defecto, 95 %).

Pensado para correr de forma programada (Programador de tareas de Windows),
por ejemplo cada hora. Cada alerta se envía una sola vez: el script guarda lo
que ya avisó en alertas_estado.json.

Uso:
    python alertas.py             Revisa y envía las alertas pendientes.
    python alertas.py --simular   Muestra qué enviaría, sin enviar ni guardar estado.
    python alertas.py --prueba    Envía un mensaje de prueba por los canales activos.
    python alertas.py --vista-previa
                                  Guarda en la carpeta vista_previa/ el correo que recibiría
                                  cada unidad (HTML), sin enviar nada.

Configuración: alertas.json. Las credenciales NO van en ese archivo sino en
variables de entorno (ver README):
    ALERTA_SMTP_PASSWORD   contraseña de la cuenta de correo que envía.
    ALERTA_TEAMS_WEBHOOK   URL del flujo de Teams (Workflows) que publica en el canal.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import smtplib
import sys
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import pandas as pd

import informes as I
import logica as L

CARPETA = Path(__file__).resolve().parent
RUTA_REPORTE = CARPETA / "data.xlsx"
CARPETA_TARIFAS = CARPETA / "tarifas"
RUTA_TARIFAS_UNICA = CARPETA / "tarifas.csv"
RUTA_CONFIG = CARPETA / "config.json"
RUTA_ALERTAS = CARPETA / "alertas.json"
RUTA_ESTADO = CARPETA / "alertas_estado.json"
RUTA_LOG = CARPETA / "alertas.log"
CID_LOGO = "logo_institucional"


def ruta_logo() -> Path | None:
    """Logo oficial para la firma del correo (assets/logo_javeriana.png o .jpg), si existe."""
    for nombre in ("logo_javeriana", "logo"):
        for extension in (".png", ".jpg", ".jpeg"):
            ruta = CARPETA / "assets" / f"{nombre}{extension}"
            if ruta.exists():
                return ruta
    return None


def logo_data_uri(ruta: Path | None) -> str | None:
    if ruta is None:
        return None
    tipo = "image/png" if ruta.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{tipo};base64,{base64.b64encode(ruta.read_bytes()).decode('ascii')}"

NOMBRE_UNIDAD = L.NOMBRE_UNIDAD   # se llena con las unidades de config.json al leerlo

log = logging.getLogger("alertas")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def num(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def pct(valor: float) -> str:
    return f"{valor:.1f} %".replace(".", ",")


def leer_json(ruta: Path, por_defecto: dict) -> dict:
    if not ruta.exists():
        return por_defecto
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def guardar_json(ruta: Path, datos: dict) -> None:
    temporal = ruta.with_suffix(".tmp")
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    temporal.replace(ruta)


def fecha_reporte(generado: str | None) -> datetime | None:
    """Fecha de generación del reporte de Marketing Cloud (ej. '19-Oct-2026 14:09:30', en UTC)."""
    if not generado:
        return None
    for formato in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y"):
        try:
            return datetime.strptime(generado.strip(), formato)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Cálculo del consumo
# ---------------------------------------------------------------------------

def calcular_consumos(cfg_alertas: dict) -> tuple[list[dict], dict, pd.DataFrame, pd.DataFrame, dict]:
    """Consumo frente a créditos disponibles en cada ámbito configurado.

    Ámbitos:
    - "linea": total de ambas líneas y cada línea (UCP, Outbound), frente a config.json.
    - "unidad": cada unidad configurada en config.json, sumando ambas líneas,
      frente a lo asignado en config.json (UCP + Outbound de cada unidad).
    """
    config = L.leer_config(RUTA_CONFIG)   # primero: define las unidades con las que se clasifica
    reporte, generado = L.leer_reporte(RUTA_REPORTE)
    ruta = CARPETA_TARIFAS if CARPETA_TARIFAS.is_dir() else RUTA_TARIFAS_UNICA
    tarifas = L.leer_tarifas(ruta)
    envios = L.preparar_envios(reporte, tarifas)

    inicio = cfg_alertas.get("fecha_inicio_conteo")
    if inicio:
        envios = envios[envios["fecha"] >= pd.Timestamp(inicio)]

    revisar = cfg_alertas.get("revisar", {})
    ambitos = []

    def agregar(nombre: str, tipo: str, datos: pd.DataFrame, disponible: float, unidad: str | None = None) -> None:
        consumido = float(datos["creditos"].sum())
        ambitos.append({
            "nombre": nombre,
            "tipo": tipo,
            "unidad": unidad,
            "consumido": consumido,
            "disponible": disponible,
            "uso_pct": consumido / disponible * 100 if disponible > 0 else None,
        })

    for linea, canal in L.LINEAS.items():
        es_general = canal is None
        if es_general and not revisar.get("general", True):
            continue
        if not es_general and not revisar.get("lineas", True):
            continue
        datos_linea = envios if es_general else envios[envios["linea"] == linea]
        etiqueta = "Total (ambas líneas)" if es_general else f"Línea {linea}"
        agregar(etiqueta, "linea", datos_linea, L.config_linea(config, linea)["creditos_totales"])

    if cfg_alertas.get("unidades", {}).get("activo", False):
        asignado = L.config_linea(config, "Ambas líneas")["unidades"]
        for unidad in L.UNIDADES:
            agregar(f"Unidad {NOMBRE_UNIDAD[unidad]}", "unidad", envios[envios["unidad"] == unidad],
                    asignado[unidad], unidad)

    info = {
        "generado": generado,
        "fecha_generado": fecha_reporte(generado),
        "ultima_fecha_envio": envios["fecha"].max() if not envios.empty else None,
        "desde": envios["fecha"].min() if not envios.empty else None,
    }
    return ambitos, info, envios, tarifas, config


def alertas_pendientes(ambitos: list[dict], umbrales: dict[str, list[float]], estado: dict) -> list[dict]:
    """Ámbitos que cruzaron un umbral y aún no se han avisado.

    La clave incluye los créditos disponibles: si se recargan créditos (cambia
    el valor en config.json), las alertas de ese ámbito vuelven a quedar activas.
    Si un ámbito cruzó varios umbrales a la vez, solo se avisa el más alto.
    """
    enviadas = estado.setdefault("enviadas", {})
    pendientes = []
    for ambito in ambitos:
        if ambito["uso_pct"] is None:
            continue
        cruzados = [u for u in sorted(umbrales[ambito["tipo"]]) if ambito["uso_pct"] >= u]
        nuevos = [u for u in cruzados
                  if f"{ambito['nombre']}|{u}|{ambito['disponible']:.0f}" not in enviadas]
        if nuevos:
            pendientes.append({**ambito, "umbral": max(nuevos), "umbrales_nuevos": nuevos})
    return pendientes


# ---------------------------------------------------------------------------
# Mensajes
# ---------------------------------------------------------------------------

def armar_mensaje(pendientes: list[dict], aviso_reporte: str | None, info: dict) -> tuple[str, str, list[str]]:
    """Asunto, texto plano y líneas de detalle del mensaje."""
    lineas = []
    for a in pendientes:
        lineas.append(
            f"{a['nombre']}: {pct(a['uso_pct'])} de uso "
            f"({num(a['consumido'])} de {num(a['disponible'])} créditos; "
            + (f"excedido en {num(a['consumido'] - a['disponible'])}" if a['consumido'] > a['disponible']
               else f"restan {num(a['disponible'] - a['consumido'])}")
            + f"). Umbral: {a['umbral']:g} %."
        )
    if pendientes:
        peor = max(pendientes, key=lambda a: a["uso_pct"])
        if len(pendientes) == 1:
            asunto = f"Alerta: créditos de WhatsApp - {peor['nombre']} al {pct(peor['uso_pct'])}"
        else:
            asunto = (f"Alerta: {len(pendientes)} alertas de créditos de WhatsApp "
                      f"(mayor: {peor['nombre']} al {pct(peor['uso_pct'])})")
    else:
        asunto = "Aviso: el reporte de créditos de WhatsApp no se ha actualizado"

    contexto = []
    if info.get("generado"):
        contexto.append(f"Reporte de Marketing Cloud generado: {info['generado']} (UTC).")
    if info.get("ultima_fecha_envio") is not None:
        contexto.append(f"Último día con entregas en el reporte: {info['ultima_fecha_envio']:%d/%m/%Y}.")
    if info.get("desde") is not None:
        contexto.append(f"Consumo contado desde: {info['desde']:%d/%m/%Y}.")

    partes = []
    if pendientes:
        partes.append("Se superó el umbral de consumo de créditos de WhatsApp:")
        partes += [f"- {l}" for l in lineas]
    if aviso_reporte:
        partes.append(aviso_reporte)
    partes.append("")
    partes += contexto
    partes.append("Detalle en el dashboard de créditos de WhatsApp.")
    return asunto, "\n".join(partes), lineas + ([aviso_reporte] if aviso_reporte else []) + contexto


def enviar_correo(cfg: dict, asunto: str, cuerpo: str) -> None:
    destinatarios = cfg.get("destinatarios") or []
    if not destinatarios:
        raise ValueError("No hay destinatarios configurados en alertas.json (correo.destinatarios).")
    usuario = cfg.get("usuario", "")
    variable = cfg.get("variable_contrasena", "ALERTA_SMTP_PASSWORD")
    contrasena = os.environ.get(variable, "")
    if usuario and not contrasena:
        raise ValueError(f"No está definida la variable de entorno {variable} con la contraseña del correo. "
                         f"Defínela con: setx {variable} \"contraseña\" y abre una terminal nueva.")
    remitente = cfg.get("remitente") or usuario
    if not remitente:
        raise ValueError("Falta el remitente o el usuario del correo en alertas.json.")

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = remitente
    mensaje["To"] = ", ".join(destinatarios)
    mensaje.set_content(cuerpo)

    with smtplib.SMTP(cfg.get("servidor", "smtp.office365.com"), int(cfg.get("puerto", 587)), timeout=30) as smtp:
        smtp.ehlo()
        if smtp.has_extn("starttls"):
            smtp.starttls()
            smtp.ehlo()
        if usuario and contrasena:
            try:
                smtp.login(usuario, contrasena)
            except smtplib.SMTPAuthenticationError as error:
                detalle = error.smtp_error.decode("utf-8", "replace") if isinstance(error.smtp_error, bytes) else str(error)
                if "SmtpClientAuthentication is disabled" in detalle or "5.7.139" in detalle:
                    raise RuntimeError("Office 365 tiene deshabilitado el envío SMTP para esta cuenta. "
                                       "Hay que pedir a TI que habilite SMTP AUTH para el remitente. "
                                       f"Detalle: {detalle}") from None
                raise RuntimeError(f"Usuario o contraseña rechazados por el servidor de correo. Detalle: {detalle}") from None
        smtp.send_message(mensaje)


def enviar_teams(cfg: dict, asunto: str, detalle: list[str]) -> None:
    """Publica una tarjeta en Teams mediante un flujo de Workflows (Power Automate).

    El mensaje también lleva los campos "asunto", "texto" y "texto_html", para que
    el flujo pueda enviar el correo de alerta con la acción de Outlook (Office 365
    ya no acepta SMTP con usuario y contraseña desde el 30 de abril de 2026).

    El flujo debe usar el desencadenador "When a Teams webhook request is received"
    (plantilla "Post to a channel when a webhook request is received").
    """
    url = os.environ.get(cfg.get("variable_webhook", "ALERTA_TEAMS_WEBHOOK"), "")
    if not url:
        variable = cfg.get("variable_webhook", "ALERTA_TEAMS_WEBHOOK")
        raise ValueError(f"No está definida la variable de entorno {variable} con la URL del flujo de Teams. "
                         f"Defínela con: setx {variable} \"url\" y abre una terminal nueva.")
    tarjeta = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [{"type": "TextBlock", "text": asunto, "weight": "Bolder", "size": "Medium", "wrap": True}]
                + [{"type": "TextBlock", "text": t, "wrap": True, "spacing": "Small"} for t in detalle],
    }
    cuerpo = json.dumps({
        "type": "message",
        "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": tarjeta}],
        # Campos de texto plano para que el mismo flujo pueda enviar también un correo
        # (acción "Enviar un correo (V2)" de Outlook): triggerBody()?['asunto'] y triggerBody()?['texto_html'].
        "asunto": asunto,
        "texto": "\n".join(detalle),
        "texto_html": "<br>".join(detalle),
    }).encode("utf-8")
    peticion = urllib.request.Request(url, data=cuerpo, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(peticion, timeout=30) as respuesta:
        if respuesta.status >= 300:
            raise RuntimeError(f"Teams respondió con estado {respuesta.status}.")


def enviar_windows(cfg: dict, asunto: str, cuerpo: str) -> None:
    """Aviso en el escritorio de Windows del usuario que corre el script.

    Abre una ventana de advertencia que queda encima de las demás hasta pulsar
    Aceptar. Usa directamente la función MessageBoxW de Windows desde Python, sin
    PowerShell ni otros programas, para que no la bloqueen las políticas de grupo.
    Solo funciona en Windows y con la sesión del usuario iniciada.
    """
    if not sys.platform.startswith("win"):
        raise RuntimeError("El aviso de escritorio solo funciona en Windows.")
    import ctypes

    MB_OK, MB_ICONWARNING, MB_SYSTEMMODAL, MB_SETFOREGROUND, MB_TOPMOST = 0x0, 0x30, 0x1000, 0x10000, 0x40000
    estilo = MB_OK | MB_ICONWARNING | MB_SYSTEMMODAL | MB_SETFOREGROUND | MB_TOPMOST
    resultado = ctypes.windll.user32.MessageBoxW(None, cuerpo, asunto, estilo)
    if resultado == 0:
        raise RuntimeError(f"Windows no pudo mostrar la ventana (código {ctypes.GetLastError()}).")


def enviar_outlook(destinatarios: list[str], asunto: str, cuerpo: str, html: str | None = None,
                   imagenes: dict[str, Path] | None = None) -> None:
    """Envía el correo a través del Outlook de escritorio (versión clásica) instalado.

    Usa la sesión de Outlook del usuario, así que no pasa por SMTP y no le afecta
    el bloqueo de usuario y contraseña de Office 365. Requiere Windows, Outlook
    clásico instalado y configurado, y el paquete pywin32. El "nuevo Outlook" no
    sirve porque no permite que otros programas envíen correo.
    """
    if not destinatarios:
        raise ValueError("No hay destinatarios configurados en alertas.json.")
    try:
        import win32com.client  # pywin32, solo Windows
    except ImportError:
        raise RuntimeError("Falta el paquete pywin32. Instálalo con: py -m pip install pywin32") from None
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
    except Exception as error:
        raise RuntimeError("No se pudo abrir Outlook de escritorio (¿está instalado el Outlook clásico?). "
                           f"Detalle: {error}") from None
    correo = outlook.CreateItem(0)  # 0 = mensaje de correo
    correo.To = "; ".join(destinatarios)
    correo.Subject = asunto
    if html:
        # Imágenes incrustadas (logo de la firma): se adjuntan ocultas y el HTML las usa con "cid:".
        for cid, ruta in (imagenes or {}).items():
            adjunto = correo.Attachments.Add(str(ruta), 1, 0)
            adjunto.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3712001F", cid)
        correo.HTMLBody = html
    else:
        correo.Body = cuerpo
    correo.Send()


def notificar(cfg_alertas: dict, asunto: str, cuerpo: str, detalle: list[str],
              correo_html: tuple[str, str, str] | None = None) -> list[str]:
    """Envía por los canales activos. Devuelve los canales que funcionaron.

    `correo_html`: (asunto, texto, html) del correo con formato institucional para Outlook;
    si no se da, Outlook envía el texto plano.
    """
    exitosos = []
    if cfg_alertas.get("outlook", {}).get("activo", False):
        try:
            if correo_html:
                asunto_o, texto_o, html_o = correo_html
                logo = ruta_logo()
                enviar_outlook(cfg_alertas["outlook"].get("destinatarios") or [], asunto_o, texto_o, html_o,
                               {CID_LOGO: logo} if logo else None)
            else:
                asunto_o = asunto
                enviar_outlook(cfg_alertas["outlook"].get("destinatarios") or [], asunto, cuerpo)
            exitosos.append("outlook")
            log.info("Correo enviado por Outlook: %s", asunto_o)
        except Exception as error:
            log.error("No se pudo enviar el correo por Outlook: %s", error)
    if cfg_alertas.get("correo", {}).get("activo", False):
        try:
            enviar_correo(cfg_alertas["correo"], asunto, cuerpo)
            exitosos.append("correo")
            log.info("Correo enviado: %s", asunto)
        except Exception as error:  # se registra y se intenta el otro canal
            log.error("No se pudo enviar el correo: %s", error)
    if cfg_alertas.get("teams", {}).get("activo", False):
        try:
            enviar_teams(cfg_alertas["teams"], asunto, detalle)
            exitosos.append("teams")
            log.info("Mensaje de Teams enviado: %s", asunto)
        except Exception as error:
            log.error("No se pudo enviar el mensaje de Teams: %s", error)
    # El aviso de escritorio va de último porque el modo "ventana" espera a que se cierre.
    if cfg_alertas.get("windows", {}).get("activo", False):
        try:
            enviar_windows(cfg_alertas["windows"], asunto, cuerpo)
            exitosos.append("windows")
            log.info("Aviso de Windows mostrado: %s", asunto)
        except Exception as error:
            log.error("No se pudo mostrar el aviso de Windows: %s", error)
    return exitosos


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------

def configurar_log() -> None:
    log.setLevel(logging.INFO)
    formato = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    archivo = logging.FileHandler(RUTA_LOG, encoding="utf-8")
    archivo.setFormatter(formato)
    consola = logging.StreamHandler(sys.stdout)
    consola.setFormatter(formato)
    log.handlers = [archivo, consola]


DIAS_SEMANA = {"lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2, "jueves": 3, "viernes": 4,
               "sabado": 5, "sábado": 5, "domingo": 6}


def responsables_de(cfg_alertas: dict, unidad: str) -> list[str]:
    return list((cfg_alertas.get("unidades", {}).get("responsables", {}) or {}).get(unidad, []) or [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Alertas de consumo de créditos de WhatsApp.")
    parser.add_argument("--simular", action="store_true", help="Muestra qué enviaría, sin enviar.")
    parser.add_argument("--prueba", action="store_true", help="Envía un mensaje de prueba.")
    parser.add_argument("--vista-previa", action="store_true",
                        help="Guarda en vista_previa/ el correo de cada unidad, sin enviar.")
    parser.add_argument("--enviar-informes", action="store_true",
                        help="Envía ya el informe actual a los responsables de cada unidad.")
    args = parser.parse_args(argv)
    configurar_log()

    cfg_alertas = leer_json(RUTA_ALERTAS, {})
    if not cfg_alertas:
        log.error("No se encontró alertas.json en %s.", CARPETA)
        return 2

    if args.prueba:
        asunto = "Prueba: alertas de créditos de WhatsApp"
        texto = "Este es un mensaje de prueba del script de alertas de créditos de WhatsApp."
        exitosos = notificar(cfg_alertas, asunto, texto, [texto])
        return 0 if exitosos else 1

    try:
        ambitos, info, envios, tarifas, config = calcular_consumos(cfg_alertas)
    except Exception as error:
        log.error("No se pudo calcular el consumo: %s", error)
        return 1

    for a in ambitos:
        uso = pct(a["uso_pct"]) if a["uso_pct"] is not None else "sin créditos definidos"
        log.info("%s: %s consumidos de %s (%s).", a["nombre"], num(a["consumido"]), num(a["disponible"]), uso)

    semaforo = L.config_semaforo(config)
    amarillo, rojo = float(semaforo["amarillo_pct"]), float(semaforo["rojo_pct"])
    asignado = L.config_linea(config, "Ambas líneas")["unidades"]
    cfg_unidades = cfg_alertas.get("unidades", {})

    plantilla = I.plantilla_desde_config(cfg_alertas)
    logo = ruta_logo()
    imagenes = {CID_LOGO: logo} if logo else None

    def informe(unidad: str, motivo: str, vista_previa: bool = False) -> tuple[str, str, str]:
        logo_src = (logo_data_uri(logo) if vista_previa else f"cid:{CID_LOGO}") if logo else None
        asignado_lineas = {l: L.config_linea(config, l)["unidades"][unidad] for l in L.LINEAS_COMPRA}
        return I.informe_unidad(unidad, envios, tarifas, asignado[unidad], amarillo, rojo, info, motivo,
                                plantilla, logo_src, asignado_lineas)

    def informe_general(pend: list[dict], aviso: str | None, vista_previa: bool = False) -> tuple[str, str, str]:
        logo_src = (logo_data_uri(logo) if vista_previa else f"cid:{CID_LOGO}") if logo else None
        return I.informe_general(ambitos, pend, aviso, info, amarillo, rojo, plantilla, logo_src)

    # ---- Vista previa: un HTML por unidad, sin enviar ni guardar estado
    if args.vista_previa:
        umbrales_previa = [float(u) for u in cfg_unidades.get("umbrales_pct", [amarillo, rojo])]
        carpeta = CARPETA / "vista_previa"
        carpeta.mkdir(exist_ok=True)
        pend_previa = [a for a in ambitos if a["uso_pct"] is not None and a["uso_pct"] >= min(umbrales_previa)]
        for a in pend_previa:
            a.setdefault("umbral", max(u for u in umbrales_previa if a["uso_pct"] >= u))
        asunto_g, _, html_g = informe_general(pend_previa, None, vista_previa=True)
        (carpeta / "correo_general.html").write_text(html_g, encoding="utf-8")
        print(f"General: {asunto_g}\n   Para: {', '.join(cfg_alertas.get('outlook', {}).get('destinatarios') or []) or 'sin destinatarios'}"
              f"\n   Archivo: {carpeta / 'correo_general.html'}")
        for unidad in L.UNIDADES:
            asunto, _, html = informe(unidad, "alerta", vista_previa=True)
            ruta = carpeta / f"correo_{unidad}.html"
            ruta.write_text(html, encoding="utf-8")
            destino = ", ".join(responsables_de(cfg_alertas, unidad)) or "sin responsables configurados"
            print(f"{NOMBRE_UNIDAD[unidad]}: {asunto}\n   Para: {destino}\n   Archivo: {ruta}")
        return 0

    outlook_activo = cfg_alertas.get("outlook", {}).get("activo", False)

    # ---- Envío manual del informe actual a todas las unidades
    if args.enviar_informes:
        fallas = 0
        for unidad in L.UNIDADES:
            destinatarios = responsables_de(cfg_alertas, unidad)
            if not destinatarios:
                log.info("%s: sin responsables configurados, no se envía.", NOMBRE_UNIDAD[unidad])
                continue
            asunto, texto, html = informe(unidad, "resumen")
            try:
                enviar_outlook(destinatarios, asunto, texto, html, imagenes)
                log.info("Informe de %s enviado a %s.", NOMBRE_UNIDAD[unidad], ", ".join(destinatarios))
            except Exception as error:
                fallas += 1
                log.error("No se pudo enviar el informe de %s: %s", NOMBRE_UNIDAD[unidad], error)
        return 1 if fallas else 0

    estado = leer_json(RUTA_ESTADO, {"enviadas": {}, "avisos_reporte": {}, "resumenes": {}})
    estado.setdefault("avisos_reporte", {})
    estado.setdefault("resumenes", {})
    umbrales = {
        "linea": [float(u) for u in cfg_alertas.get("umbrales_pct", [95])],
        "unidad": [float(u) for u in cfg_unidades.get("umbrales_pct", [amarillo, rojo])],
    }
    pendientes = alertas_pendientes(ambitos, umbrales, estado)

    # Aviso de reporte desactualizado (una vez por versión del reporte)
    aviso_reporte = None
    dias_max = cfg_alertas.get("aviso_reporte_desactualizado_dias")
    fecha_gen = info.get("fecha_generado")
    if dias_max and fecha_gen is not None:
        dias = (datetime.now(timezone.utc).replace(tzinfo=None) - fecha_gen).days
        if dias >= int(dias_max) and info["generado"] not in estado["avisos_reporte"]:
            aviso_reporte = (f"El reporte data.xlsx tiene {dias} días de generado: el consumo real puede ser "
                             "mayor al calculado. Actualiza el reporte desde Marketing Cloud.")

    # Resumen semanal por unidad (opcional)
    resumenes = []
    cfg_resumen = cfg_unidades.get("resumen_semanal", {})
    if cfg_unidades.get("activo") and cfg_resumen.get("activo"):
        hoy = datetime.now()
        dia = DIAS_SEMANA.get(str(cfg_resumen.get("dia", "lunes")).lower(), 0)
        semana = f"{hoy.isocalendar()[0]}-W{hoy.isocalendar()[1]:02d}"
        if hoy.weekday() == dia:
            resumenes = [u for u in L.UNIDADES
                         if responsables_de(cfg_alertas, u) and f"{u}|{semana}" not in estado["resumenes"]]

    if not pendientes and not aviso_reporte and not resumenes:
        log.info("Sin alertas nuevas.")
        return 0

    pend_unidades = [a for a in pendientes if a["tipo"] == "unidad"]

    if args.simular:
        print("\n--- SIMULACIÓN (no se envía nada) ---")
        if pendientes or aviso_reporte:
            asunto, cuerpo, _ = armar_mensaje(pendientes, aviso_reporte, info)
            print("Aviso general:", asunto)
            print(cuerpo)
        for a in pend_unidades:
            asunto, _, _ = informe(a["unidad"], "alerta")
            destino = ", ".join(responsables_de(cfg_alertas, a["unidad"])) or "sin responsables (solo aviso general)"
            print(f"\nCorreo a {destino}: {asunto}")
        for u in resumenes:
            print(f"\nResumen semanal a {', '.join(responsables_de(cfg_alertas, u))}: {NOMBRE_UNIDAD[u]}")
        return 0

    ahora = datetime.now().isoformat(timespec="seconds")
    resultado = 0

    # 1) Correo de cada unidad a sus responsables
    unidades_enviadas = set()
    for a in pend_unidades:
        destinatarios = responsables_de(cfg_alertas, a["unidad"])
        if not destinatarios or not outlook_activo:
            continue
        asunto, texto, html = informe(a["unidad"], "alerta")
        try:
            enviar_outlook(destinatarios, asunto, texto, html, imagenes)
            unidades_enviadas.add(a["unidad"])
            log.info("Alerta de %s enviada a %s.", NOMBRE_UNIDAD[a["unidad"]], ", ".join(destinatarios))
        except Exception as error:
            resultado = 1
            log.error("No se pudo enviar la alerta de %s: %s", NOMBRE_UNIDAD[a["unidad"]], error)

    # 2) Resúmenes semanales
    for u in resumenes:
        asunto, texto, html = informe(u, "resumen")
        try:
            enviar_outlook(responsables_de(cfg_alertas, u), asunto, texto, html, imagenes)
            estado["resumenes"][f"{u}|{semana}"] = {"fecha": ahora}
            log.info("Resumen semanal de %s enviado.", NOMBRE_UNIDAD[u])
        except Exception as error:
            resultado = 1
            log.error("No se pudo enviar el resumen semanal de %s: %s", NOMBRE_UNIDAD[u], error)

    # 3) Aviso general (Windows, Outlook general, Teams, correo): todas las alertas nuevas
    exitosos = []
    if pendientes or aviso_reporte:
        asunto, cuerpo, detalle = armar_mensaje(pendientes, aviso_reporte, info)
        exitosos = notificar(cfg_alertas, asunto, cuerpo, detalle,
                             correo_html=informe_general(pendientes, aviso_reporte))
        if not exitosos and not unidades_enviadas:
            log.error("No se pudo avisar por ningún canal; se intentará de nuevo en la próxima ejecución.")
            resultado = 1

    # Estado: una alerta de unidad queda registrada si le llegó a su responsable, o si la
    # unidad no tiene responsable y salió el aviso general. Las de línea, si salió el aviso general.
    for a in pendientes:
        if a["tipo"] == "unidad":
            tiene_responsable = bool(responsables_de(cfg_alertas, a["unidad"])) and outlook_activo
            registrar = a["unidad"] in unidades_enviadas or (not tiene_responsable and exitosos)
            canales = ["outlook_unidad"] if a["unidad"] in unidades_enviadas else exitosos
        else:
            registrar, canales = bool(exitosos), exitosos
        if registrar:
            for u in a["umbrales_nuevos"]:
                estado["enviadas"][f"{a['nombre']}|{u}|{a['disponible']:.0f}"] = {
                    "fecha": ahora, "uso_pct": round(a["uso_pct"], 2), "canales": canales}
    if aviso_reporte and exitosos:
        estado["avisos_reporte"][info["generado"]] = {"fecha": ahora, "canales": exitosos}
    guardar_json(RUTA_ESTADO, estado)
    return resultado


if __name__ == "__main__":
    sys.exit(main())
