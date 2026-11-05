"""
Correos de acceso que envía la app: códigos de verificación, acceso aprobado o no aprobado, contraseña
temporal, contraseña cambiada y aviso de nueva solicitud al Equipo CRM.

Usan la misma plantilla que los informes de créditos (informes.py): texto institucional, tablas sobrias,
firma del Equipo CRM con el logo y pie de seguridad. La firma y el enlace al dashboard salen de
alertas.json -> "plantilla", igual que en los informes.

Se envían por el primer camino disponible:
1. SMTP, si está en los Secrets (es el único que sirve en el enlace publicado de Streamlit Cloud).
2. Outlook de escritorio (clásico) del computador donde corre la app, el mismo que usan las alertas.
   Funciona solo en Windows con pywin32; el correo sale de la cuenta de Outlook de ese computador.

SMTP en los Secrets (Settings > Secrets en Streamlit Cloud, o .streamlit/secrets.toml en local):

    [correo]
    servidor = "smtp.gmail.com"
    puerto = 465
    usuario = "cuenta.del.dashboard@gmail.com"
    clave = "contraseña de aplicación de 16 letras"     # nunca la contraseña normal de la cuenta
    remitente = "Créditos de mensajería · Equipo CRM"

Sin ninguno de los dos, la app no envía correos: crear cuenta y recuperar contraseña quedan desactivados
(en el modo pruebas los correos se muestran en pantalla en lugar de enviarse).

Vista previa de todos los correos (sin enviar nada), como la de los informes:
    py correo_app.py --vista-previa            -> carpeta vista_previa/
    py correo_app.py --vista-previa --abrir    -> además los abre en el navegador
"""

from __future__ import annotations

import base64
import json
import os
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import informes as I

CARPETA = Path(__file__).parent
CID_LOGO = "logo_institucional"
ZONA = ZoneInfo("America/Bogota")
NOMBRE_APP = "dashboard de créditos de mensajería"

PIE_ACCESO = ("El Equipo CRM nunca te pedirá tu contraseña ni códigos de verificación por teléfono, chat o correo. "
              "Este mensaje no contiene archivos adjuntos.")


# ---------------------------------------------------------------------------
# Configuración y envío
# ---------------------------------------------------------------------------

def configuracion() -> dict:
    try:
        import streamlit as st
        return dict(st.secrets.get("correo", {}))
    except Exception:
        return {}


def _hay_smtp() -> bool:
    c = configuracion()
    return bool(c.get("usuario") and c.get("clave"))


def _hay_outlook() -> bool:
    if os.name != "nt":
        return False
    try:
        import win32com.client  # noqa: F401  pywin32, solo Windows
        return True
    except ImportError:
        return False


def metodo() -> str | None:
    """"smtp", "outlook" o None si no hay cómo enviar."""
    if _hay_smtp():
        return "smtp"
    if _hay_outlook():
        return "outlook"
    return None


def configurado() -> bool:
    return metodo() is not None


def plantilla() -> dict:
    """Firma y enlace al dashboard (alertas.json -> "plantilla"), los mismos de los informes."""
    try:
        cfg = json.loads((CARPETA / "alertas.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}
    return I.plantilla_desde_config(cfg)


def ruta_logo() -> Path | None:
    """Logo oficial para la firma (assets/logo_javeriana.png o .jpg), el mismo de los informes."""
    for nombre in ("logo_javeriana", "logo"):
        for extension in (".png", ".jpg", ".jpeg"):
            ruta = CARPETA / "assets" / f"{nombre}{extension}"
            if ruta.exists():
                return ruta
    return None


def _tipo_logo(ruta: Path) -> str:
    return "png" if ruta.suffix.lower() == ".png" else "jpeg"


@dataclass
class Mensaje:
    asunto: str
    cuerpo: str          # HTML del contenido de la tarjeta (sin logo, firma ni pie)
    texto: str           # versión en texto plano
    pie: str             # por qué lo recibe + nota de seguridad

    def html(self, logo_src: str | None) -> str:
        return _documento(self.asunto, self.cuerpo, logo_src, self.pie)

    def vista_previa(self) -> str:
        """HTML con el logo incrustado (para verlo en el navegador o en el modo pruebas)."""
        logo = ruta_logo()
        src = (f"data:image/{_tipo_logo(logo)};base64,{base64.b64encode(logo.read_bytes()).decode('ascii')}"
               if logo else None)
        return self.html(src)


def _enviar_outlook(destinatarios: list[str], m: Mensaje) -> None:
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()   # Streamlit ejecuta cada sesión en su propio hilo
    try:
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
        except Exception as error:
            raise RuntimeError("No se pudo abrir Outlook de escritorio (¿está instalado el Outlook clásico?). "
                               f"Detalle: {error}") from None
        correo = outlook.CreateItem(0)  # 0 = mensaje de correo
        correo.To = "; ".join(destinatarios)
        correo.Subject = m.asunto
        logo = ruta_logo()
        if logo:   # logo de la firma: adjunto oculto que el HTML usa con "cid:", igual que en las alertas
            adjunto = correo.Attachments.Add(str(logo), 1, 0)
            adjunto.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3712001F", CID_LOGO)
        correo.HTMLBody = m.html(f"cid:{CID_LOGO}" if logo else None)
        correo.Send()
    finally:
        pythoncom.CoUninitialize()


def _enviar_smtp(destinatarios: list[str], m: Mensaje) -> None:
    c = configuracion()
    logo = ruta_logo()
    mensaje = EmailMessage()
    mensaje["Subject"] = m.asunto
    mensaje["From"] = formataddr((c.get("remitente", "Créditos de mensajería · Equipo CRM"), c["usuario"]))
    mensaje["To"] = ", ".join(destinatarios)
    mensaje.set_content(m.texto)
    mensaje.add_alternative(m.html(f"cid:{CID_LOGO}" if logo else None), subtype="html")
    if logo:
        mensaje.get_payload()[1].add_related(logo.read_bytes(), "image", _tipo_logo(logo), cid=f"<{CID_LOGO}>")
    servidor, puerto = c.get("servidor", "smtp.gmail.com"), int(c.get("puerto", 465))
    contexto = ssl.create_default_context()
    if puerto == 465:
        with smtplib.SMTP_SSL(servidor, puerto, context=contexto, timeout=20) as smtp:
            smtp.login(c["usuario"], c["clave"])
            smtp.send_message(mensaje)
    else:
        with smtplib.SMTP(servidor, puerto, timeout=20) as smtp:
            smtp.starttls(context=contexto)
            smtp.login(c["usuario"], c["clave"])
            smtp.send_message(mensaje)


def enviar(destinatarios: list[str] | str, m: Mensaje) -> None:
    """Envía el correo. Lanza una excepción si falla (quien llama decide qué mostrar)."""
    if isinstance(destinatarios, str):
        destinatarios = [destinatarios]
    if metodo() == "outlook":
        _enviar_outlook(destinatarios, m)
    else:
        _enviar_smtp(destinatarios, m)


# ---------------------------------------------------------------------------
# Diseño de los correos de acceso
#
# Tarjeta blanca centrada sobre fondo gris claro, logo pequeño arriba, título y textos centrados, el código
# grande sin recuadros duros, detalles en filas suaves y la firma del Equipo CRM abajo. Todo con tablas y
# estilos en línea porque Outlook no entiende diseños modernos (ignora las esquinas redondeadas, que en los
# demás clientes sí se ven).
# ---------------------------------------------------------------------------

FONDO = "#F3F5F9"
TARJETA_BORDE = "#E3E7EE"
SUAVE = "#EEF3FA"          # fondo del código
LINEA = "#ECEFF4"
GRIS_TEXTO = "#5F6773"
GRIS_CLARO = "#8A919C"
VERDE = "#1E7B3C"
ANCHO = 560


def _documento(asunto: str, cuerpo: str, logo_src: str | None, pie: str) -> str:
    f = plantilla()["firma"]
    logo = (f'<img src="{logo_src}" alt="{escape(f.get("institucion", ""))}" width="104" '
            f'style="display:block; margin:0 auto; border:0; width:104px; height:auto;">' if logo_src else
            f'<div style="font-size:11pt; font-weight:bold; color:{I.AZUL};">{escape(f.get("institucion", ""))}</div>')
    direccion = " · ".join(escape(l) for l in (f.get("direccion") or []))
    correo = f.get("correo") or ""
    correo_html = (f'<br><a href="mailto:{escape(correo)}" style="color:{I.AZUL}; text-decoration:none;">'
                   f'{escape(correo)}</a>' if correo else "")
    return (
        f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" '
        f'content="width=device-width, initial-scale=1"><title>{escape(asunto)}</title></head>'
        f'<body style="margin:0; padding:0; background:{FONDO};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{FONDO};">'
        f'<tr><td align="center" style="padding:28px 12px;">'
        f'<table role="presentation" width="{ANCHO}" cellpadding="0" cellspacing="0" style="width:100%; '
        f'max-width:{ANCHO}px; background:#FFFFFF; border:1px solid {TARJETA_BORDE}; border-radius:14px; '
        f'border-collapse:separate; font-family:{I.FUENTE}; color:{I.TEXTO};">'
        f'<tr><td style="height:5px; line-height:5px; font-size:0; background:{I.AZUL}; '
        f'border-radius:14px 14px 0 0;">&nbsp;</td></tr>'
        f'<tr><td align="center" style="padding:26px 40px 6px 40px;">{logo}</td></tr>'
        f'<tr><td style="padding:10px 32px 30px 32px; font-size:11pt; line-height:1.55;">{cuerpo}</td></tr>'
        f'<tr><td align="center" style="padding:18px 28px 22px 28px; border-top:1px solid {LINEA}; '
        f'font-size:9.5pt; color:{GRIS_TEXTO}; line-height:1.5;">'
        f'<b style="color:{I.AZUL};">{escape(f.get("nombre", ""))}</b> · {escape(f.get("area", ""))}<br>'
        f'{escape(f.get("institucion", ""))}<br><span style="color:{GRIS_CLARO};">{direccion}</span>{correo_html}'
        f'</td></tr></table>'
        f'<table role="presentation" width="{ANCHO}" cellpadding="0" cellspacing="0" style="width:100%; '
        f'max-width:{ANCHO}px;"><tr><td align="center" style="padding:14px 30px 0 30px; font-family:{I.FUENTE}; '
        f'font-size:8.5pt; line-height:1.5; color:{GRIS_CLARO};">{escape(pie)}</td></tr></table>'
        f'</td></tr></table></body></html>')


def _titulo(texto: str, etiqueta: str = "") -> str:
    sobre = (f'<div style="font-size:8.5pt; font-weight:bold; letter-spacing:1.2px; text-transform:uppercase; '
             f'color:{GRIS_CLARO}; margin-bottom:6px;">{escape(etiqueta)}</div>' if etiqueta else "")
    return (f'<div style="text-align:center; margin:6px 0 14px 0;">{sobre}'
            f'<div style="font-size:17pt; font-weight:bold; color:{I.AZUL}; line-height:1.25;">{escape(texto)}</div>'
            f'</div>')


def _parrafo(texto_html: str, *, centrado: bool = True, color: str | None = None, tamano: str = "11pt",
             margen: str = "0 0 14px 0") -> str:
    return (f'<p style="margin:{margen}; text-align:{"center" if centrado else "left"}; font-size:{tamano}; '
            f'color:{color or I.TEXTO};">{texto_html}</p>')


def _destacado(valor: str, nota: str = "", *, grande: bool = True) -> str:
    """El código o la contraseña temporal, centrado y grande, sobre un fondo suave sin bordes."""
    estilo = ("font-size:30pt; letter-spacing:12px; padding:16px 22px 16px 34px;" if grande
              else "font-size:19pt; letter-spacing:3px; padding:14px 28px;")
    nota_html = (f'<div style="margin-top:10px; font-size:9.5pt; color:{GRIS_TEXTO};">{nota}</div>' if nota else "")
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" align="center" style="margin:6px auto 4px auto;">'
            f'<tr><td align="center" style="background:{SUAVE}; border-radius:12px; {estilo} '
            f'font-family:Consolas, \'Courier New\', monospace; font-weight:bold; color:{I.AZUL};">'
            f'{escape(valor)}</td></tr></table>'
            f'<div style="text-align:center; margin-bottom:20px;">{nota_html}</div>')


def _detalles(filas: list[tuple[str, str]]) -> str:
    """Datos en filas suaves (sin cuadrícula): etiqueta en gris a la izquierda, valor a la derecha."""
    cuerpo = "".join(
        f'<tr><td style="padding:9px 0; border-bottom:1px solid {LINEA}; color:{GRIS_TEXTO}; font-size:10pt;">'
        f'{escape(e)}</td><td align="right" style="padding:9px 0; border-bottom:1px solid {LINEA}; '
        f'font-size:10pt; font-weight:bold; color:{I.TEXTO};">{v}</td></tr>'
        for e, v in filas)
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="margin:6px 0 20px 0; border-top:1px solid {LINEA};">{cuerpo}</table>')


def _boton(texto: str, url: str) -> str:
    """Botón que Outlook también respeta (tabla con fondo de color)."""
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" align="center" style="margin:4px auto 18px auto;">'
            f'<tr><td align="center" style="background:{I.AZUL}; border-radius:8px;">'
            f'<a href="{escape(url)}" style="display:inline-block; padding:12px 30px; font-family:{I.FUENTE}; '
            f'font-size:11pt; font-weight:bold; color:#FFFFFF; text-decoration:none;">{escape(texto)}</a>'
            f'</td></tr></table>')


def _boton_dashboard(texto: str, unidad: str | None = None) -> str:
    url = I.url_dashboard(plantilla(), unidad)
    return _boton(texto, url) if url else ""


def _consejo(texto_html: str) -> str:
    """Nota pequeña al final del contenido (seguridad o siguiente paso)."""
    return _parrafo(texto_html, color=GRIS_TEXTO, tamano="9.5pt", margen="4px 0 0 0")


def _contacto() -> str:
    correo = plantilla()["firma"].get("correo") or ""
    if correo:
        return _consejo(f'¿No fuiste tú? Escríbenos de inmediato a <a href="mailto:{escape(correo)}" '
                        f'style="color:{I.AZUL};">{escape(correo)}</a>.')
    return _consejo("¿No fuiste tú? Responde a este correo para avisarnos de inmediato.")


def _ahora() -> datetime:
    return datetime.now(ZONA)


def _hora(momento: datetime) -> str:
    return f"{momento:%I:%M %p}".lstrip("0").replace("AM", "a. m.").replace("PM", "p. m.")


def _fecha_hora(momento: datetime) -> str:
    return f"{momento:%d/%m/%Y}, {_hora(momento)}"


def _primer_nombre(nombre: str | None) -> str:
    return (nombre or "").strip().split(" ")[0]


def _saludo(nombre: str | None) -> str:
    primero = _primer_nombre(nombre)
    return f"Hola, {escape(primero)}" if primero else "Hola"


def _enlace_texto(unidad: str | None = None) -> str:
    url = I.url_dashboard(plantilla(), unidad)
    return f"Dashboard: {url}" if url else ""


def _texto_plano(*partes: str) -> str:
    f = plantilla()["firma"]
    return "\n\n".join([p for p in partes if p] + ["Cordial saludo,",
                                                   "\n".join([f.get("nombre", ""), f.get("area", ""),
                                                              f.get("institucion", "")])])


def _lista(nombres: list[str]) -> str:
    if len(nombres) <= 1:
        return "".join(nombres)
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


# ---------------------------------------------------------------------------
# Los correos
# ---------------------------------------------------------------------------

def codigo(nombre: str | None, correo: str, valor: str, proposito: str, minutos: int) -> Mensaje:
    """Código de verificación para crear la cuenta ("registro") o restablecer la contraseña ("recuperar")."""
    registro = proposito == "registro"
    ahora = _ahora()
    vence = ahora + timedelta(minutes=minutos)
    asunto = ("Tu código para crear tu cuenta en el dashboard de créditos" if registro
              else "Tu código para restablecer tu contraseña del dashboard de créditos")
    if registro:
        titulo, etiqueta = "Confirma tu correo", "Crear cuenta"
        intro = (f"{_saludo(nombre)}. Ya casi terminas: escribe este código en la pantalla de registro del "
                 f"{NOMBRE_APP} para confirmar que este correo es tuyo.")
        no_fuiste = "Si no fuiste tú, ignora este correo: sin el código nadie puede crear una cuenta con él."
    else:
        titulo, etiqueta = "Restablece tu contraseña", "Recuperar acceso"
        intro = (f"{_saludo(nombre)}. Recibimos una solicitud para restablecer la contraseña de tu cuenta. "
                 f"Escribe este código en la pantalla donde lo pediste y luego crea tu nueva contraseña.")
        no_fuiste = "Si no fuiste tú, ignora este correo: tu contraseña sigue siendo la misma."
    cuerpo = (_titulo(titulo, etiqueta) + _parrafo(intro)
              + _destacado(valor, f"Vence a las <b>{_hora(vence)}</b> ({minutos} minutos) y sirve una sola vez.")
              + _detalles([("Cuenta", escape(correo)), ("Solicitado", _fecha_hora(ahora))])
              + _consejo(no_fuiste))
    texto = _texto_plano(f"{_saludo(nombre)},", intro, f"Tu código: {valor}",
                         f"Vence en {minutos} minutos y sirve una sola vez.", no_fuiste)
    pie = (f"Recibes este correo porque alguien escribió {correo} en el {NOMBRE_APP}. " + PIE_ACCESO)
    return Mensaje(asunto, cuerpo, texto, pie)


def acceso_aprobado(nombre: str | None, correo: str, unidades: dict[str, str], automatico: bool = False) -> Mensaje:
    """`unidades`: {clave: nombre} de las unidades que ahora puede ver."""
    nombres = list(unidades.values())
    clave = next(iter(unidades)) if len(unidades) == 1 else None
    asunto = f"Ya tienes acceso a {_lista(nombres)} en el dashboard de créditos"
    motivo = ("Como estás registrado como responsable de la unidad, tu acceso quedó listo de una vez."
              if automatico else "El Equipo CRM aprobó tu solicitud.")
    cuerpo = (_titulo("Tu acceso está listo", "Acceso aprobado")
              + _parrafo(f"{_saludo(nombre)}. {motivo} Desde ahora puedes ver el consumo de "
                         f"créditos de <b>{escape(_lista(nombres))}</b>: cuánto se ha usado, cuánto queda, cuándo se "
                         f"agotaría y qué journeys consumen más.")
              + _boton_dashboard("Ir al dashboard", clave)
              + _detalles([("Cuenta", escape(correo)), ("Unidades que puedes ver", escape(_lista(nombres))),
                           ("Aprobado", _fecha_hora(_ahora()))])
              + _consejo("Entra con tu correo institucional y la contraseña que creaste. Si tienes más de una "
                         "unidad, cámbiala en <b>Vista</b>, en la barra lateral."))
    texto = _texto_plano(f"{_saludo(nombre)},", f"{motivo} Ya puedes ver {_lista(nombres)} en el {NOMBRE_APP}.",
                         _enlace_texto(clave))
    pie = f"Recibes este correo porque pediste acceso al {NOMBRE_APP}. " + PIE_ACCESO
    return Mensaje(asunto, cuerpo, texto, pie)


def solicitud_no_aprobada(nombre: str | None, correo: str, unidad: str) -> Mensaje:
    asunto = f"Tu solicitud de acceso a {unidad} en el dashboard de créditos"
    cuerpo = (_titulo("Revisamos tu solicitud", "Solicitud de acceso")
              + _parrafo(f"{_saludo(nombre)}. El Equipo CRM revisó tu solicitud para ver <b>{escape(unidad)}</b> y, "
                         f"por ahora, no fue aprobada.")
              + _detalles([("Cuenta", escape(correo)), ("Unidad solicitada", escape(unidad)),
                           ("Revisada", _fecha_hora(_ahora()))])
              + _consejo("Suele pasar cuando la unidad elegida no corresponde a tu área. Si crees que es un error, "
                         "responde a este correo o pide otra unidad desde el dashboard."))
    texto = _texto_plano(f"{_saludo(nombre)},", f"El Equipo CRM revisó tu solicitud para ver {unidad} y, por "
                         "ahora, no fue aprobada. Si crees que es un error, responde a este correo.")
    pie = f"Recibes este correo porque pediste acceso al {NOMBRE_APP}. " + PIE_ACCESO
    return Mensaje(asunto, cuerpo, texto, pie)


def contrasena_temporal(nombre: str | None, correo: str, valor: str, unidades: list[str]) -> Mensaje:
    asunto = "Tu contraseña temporal del dashboard de créditos"
    filas = [("Cuenta", escape(correo))]
    if unidades:
        filas.append(("Unidades que puedes ver", escape(_lista(unidades))))
    cuerpo = (_titulo("Tu contraseña temporal", "Acceso al dashboard")
              + _parrafo(f"{_saludo(nombre)}. El Equipo CRM te preparó una contraseña temporal para entrar al "
                         f"{NOMBRE_APP}. Escríbela tal como aparece, con los guiones.")
              + _destacado(valor, "Al entrar te pediremos crear una contraseña nueva.", grande=False)
              + _boton_dashboard("Entrar al dashboard")
              + _detalles(filas)
              + _contacto())
    texto = _texto_plano(f"{_saludo(nombre)},", f"El Equipo CRM te preparó una contraseña temporal para el {NOMBRE_APP}.",
                         f"Contraseña temporal: {valor}", "Al entrar te pediremos crear una nueva.", _enlace_texto())
    pie = f"Recibes este correo porque el Equipo CRM gestionó tu cuenta del {NOMBRE_APP}. " + PIE_ACCESO
    return Mensaje(asunto, cuerpo, texto, pie)


def contrasena_cambiada(nombre: str | None, correo: str, como: str) -> Mensaje:
    """Aviso de seguridad después de cambiar o restablecer la contraseña."""
    asunto = "Tu contraseña del dashboard de créditos cambió"
    cuerpo = (_titulo("Tu contraseña cambió", "Aviso de seguridad")
              + _parrafo(f"{_saludo(nombre)}. Te confirmamos que la contraseña de tu cuenta cambió. Por seguridad, "
                         f"cerramos las sesiones que tenías recordadas en otros equipos.")
              + _detalles([("Cuenta", escape(correo)), ("Cómo", escape(como)), ("Fecha", _fecha_hora(_ahora()))])
              + _contacto())
    texto = _texto_plano(f"{_saludo(nombre)},", f"La contraseña de tu cuenta del {NOMBRE_APP} ({correo}) cambió "
                         f"({como}). Si no fuiste tú, avísanos de inmediato.")
    pie = "Recibes este aviso de seguridad cada vez que cambia la contraseña de tu cuenta. " + PIE_ACCESO
    return Mensaje(asunto, cuerpo, texto, pie)


def nueva_solicitud(nombre: str, correo: str, unidad: str, pendientes: int) -> Mensaje:
    """Aviso al Equipo CRM: alguien pidió acceso a una unidad."""
    asunto = f"Solicitud de acceso al dashboard de créditos: {unidad}"
    cuerpo = (_titulo("Nueva solicitud de acceso", "Para el Equipo CRM")
              + _parrafo(f"<b>{escape(nombre)}</b> pidió acceso a <b>{escape(unidad)}</b>. Su correo no está "
                         f"registrado como responsable de esa unidad, así que la solicitud espera tu revisión.")
              + _boton_dashboard("Revisar en Usuarios")
              + _detalles([("Nombre", escape(nombre)), ("Correo", escape(correo)), ("Unidad", escape(unidad)),
                           ("Fecha", _fecha_hora(_ahora())), ("Solicitudes por revisar", str(pendientes))])
              + _consejo("En el dashboard, abre el menú de tu perfil (arriba a la derecha) y entra a <b>Usuarios</b>."))
    texto = _texto_plano("Hola,", f"{nombre} ({correo}) pidió acceso a {unidad} en el {NOMBRE_APP}.",
                         "Apruébala o recházala en el dashboard, en Usuarios.", _enlace_texto())
    pie = (f"Recibes este aviso porque estás en la lista del Equipo CRM del {NOMBRE_APP} (acceso.json). "
           "Este mensaje no contiene archivos adjuntos.")
    return Mensaje(asunto, cuerpo, texto, pie)


# ---------------------------------------------------------------------------
# Vista previa:  py correo_app.py --vista-previa
# ---------------------------------------------------------------------------

def vista_previa(carpeta: Path | None = None) -> list[tuple[str, Path]]:
    """Guarda los 7 correos de acceso con datos de ejemplo (HTML con el logo incrustado), sin enviar nada."""
    carpeta = carpeta or CARPETA / "vista_previa"
    carpeta.mkdir(exist_ok=True)
    ana = ("Ana Pérez", "ana.perez@javeriana.edu.co")
    ejemplos = {
        "acceso_1_codigo_registro": codigo(*ana, "968048", "registro", 15),
        "acceso_2_codigo_recuperar": codigo(*ana, "305117", "recuperar", 15),
        "acceso_3_aprobado": acceso_aprobado(*ana, {"egresados": "Egresados"}),
        "acceso_4_no_aprobado": solicitud_no_aprobada(*ana, "Donaciones"),
        "acceso_5_temporal": contrasena_temporal(*ana, "hT7k-Qm2R-x9Pd", ["Egresados"]),
        "acceso_6_cambiada": contrasena_cambiada(*ana, "Restablecida con código de verificación"),
        "acceso_7_solicitud_admin": nueva_solicitud(*ana, "Egresados", 1),
    }
    salida = []
    for nombre_archivo, m in ejemplos.items():
        ruta = carpeta / f"{nombre_archivo}.html"
        ruta.write_text(m.vista_previa(), encoding="utf-8")
        salida.append((m.asunto, ruta))
    return salida


if __name__ == "__main__":
    import argparse
    import webbrowser

    parser = argparse.ArgumentParser(description="Correos de acceso del dashboard (códigos, aprobaciones, "
                                                 "contraseñas).")
    parser.add_argument("--vista-previa", action="store_true",
                        help="Guarda en vista_previa/ los correos de acceso con datos de ejemplo, sin enviar.")
    parser.add_argument("--abrir", action="store_true", help="Además, abre los correos en el navegador.")
    args = parser.parse_args()
    if not (args.vista_previa or args.abrir):
        parser.print_help()
        raise SystemExit(0)
    for asunto, ruta in vista_previa():
        print(f"{asunto}\n   Archivo: {ruta}")
        if args.abrir:
            webbrowser.open(ruta.resolve().as_uri())
    print(f"\nEnvío configurado: {metodo() or 'ninguno'} (smtp en los Secrets u Outlook de escritorio).")
