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
    cuerpo: str          # HTML del cuerpo (sin saludo final ni firma)
    texto: str           # versión en texto plano
    pie: str             # por qué lo recibe + nota de seguridad

    def html(self, logo_src: str | None) -> str:
        return I._documento(self.asunto, self.cuerpo, plantilla(), logo_src, escape(self.pie))

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
# Piezas comunes
# ---------------------------------------------------------------------------

def _ahora() -> datetime:
    return datetime.now(ZONA)


def _fecha_hora(momento: datetime) -> str:
    return f"{momento:%d/%m/%Y} a las {momento:%I:%M %p}".replace("AM", "a. m.").replace("PM", "p. m.")


def _saludo(nombre: str | None) -> str:
    primero = (nombre or "").strip().split(" ")[0]
    return f"Hola, {escape(primero)}:" if primero else "Hola:"


def _caja_codigo(valor: str, *, tamano: str = "24pt", espacio: str = "6px") -> str:
    """El código o la contraseña temporal, destacado en una caja sobria (tabla, para que Outlook la respete)."""
    return (f'<table cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin:4px 0 16px 0;"><tr>'
            f'<td style="padding:12px 28px; border:1px solid {I.BORDE}; border-left:4px solid {I.AZUL}; '
            f'background:{I.FONDO_ENCABEZADO}; font-family:Consolas, \'Courier New\', monospace; font-size:{tamano}; '
            f'font-weight:bold; letter-spacing:{espacio}; color:{I.AZUL};">{escape(valor)}</td></tr></table>')


def _enlace(unidad: str | None = None, texto: str = "Ingresa al dashboard con tu correo institucional") -> str:
    """Enlace visible y completo al dashboard (como en los informes). Sin URL en alertas.json, solo la frase."""
    url = I.url_dashboard(plantilla(), unidad)
    if url:
        return I._p(f"{escape(texto)}:<br><a href=\"{escape(url)}\" style=\"color:#0563C1;\">{escape(url)}</a>")
    return I._p(f"{escape(texto)}.")


def _enlace_texto(unidad: str | None = None) -> str:
    url = I.url_dashboard(plantilla(), unidad)
    return f"Dashboard: {url}" if url else ""


def _contacto() -> str:
    correo = plantilla()["firma"].get("correo") or ""
    if correo:
        return I._p(f'Si no reconoces esta actividad, escríbenos de inmediato a '
                    f'<a href="mailto:{escape(correo)}" style="color:#0563C1;">{escape(correo)}</a>.')
    return I._p("Si no reconoces esta actividad, responde a este correo para avisarnos.")


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
    accion = "crear tu cuenta" if registro else "restablecer tu contraseña"
    ahora = _ahora()
    asunto = ("Código para crear tu cuenta en el dashboard de créditos" if registro
              else "Código para restablecer tu contraseña del dashboard de créditos")
    intro = (f"Recibimos una solicitud para {accion} en el {NOMBRE_APP} del Equipo CRM con el correo "
             f"<b>{escape(correo)}</b>. Para continuar, escribe este código en la pantalla donde lo pediste:")
    filas = [("Cuenta", escape(correo)), ("Solicitado", _fecha_hora(ahora)),
             ("Válido hasta", _fecha_hora(ahora + timedelta(minutes=minutos)))]
    cuerpo = (I._p(_saludo(nombre)) + I._p(intro)
              + I._titulo_seccion("Código de verificación") + _caja_codigo(valor)
              + I._tabla_datos(filas)
              + I._p(f"El código sirve una sola vez y vence en {minutos} minutos. Si no fuiste tú, ignora este "
                     f"correo: {'no se creará ninguna cuenta' if registro else 'tu contraseña sigue igual'}."))
    texto = _texto_plano(_saludo(nombre),
                         f"Recibimos una solicitud para {accion} en el {NOMBRE_APP} con el correo {correo}.",
                         f"Tu código: {valor}", f"Vence en {minutos} minutos y sirve una sola vez. "
                         "Si no fuiste tú, ignora este correo.")
    pie = f"Recibes este correo porque alguien escribió {correo} en el {NOMBRE_APP}. " + PIE_ACCESO
    return Mensaje(asunto, cuerpo, texto, pie)


def acceso_aprobado(nombre: str | None, correo: str, unidades: dict[str, str], automatico: bool = False) -> Mensaje:
    """`unidades`: {clave: nombre} de las unidades que ahora puede ver."""
    nombres = list(unidades.values())
    clave = next(iter(unidades)) if len(unidades) == 1 else None
    asunto = f"Ya tienes acceso a {_lista(nombres)} en el dashboard de créditos"
    motivo = ("Como estás registrado como responsable de la unidad, el acceso quedó aprobado de una vez."
              if automatico else "El Equipo CRM aprobó tu solicitud de acceso.")
    filas = [("Cuenta", escape(correo)), ("Unidades que puedes ver", escape(_lista(nombres))),
             ("Aprobado", _fecha_hora(_ahora()))]
    cuerpo = (I._p(_saludo(nombre))
              + I._p(f"{motivo} Desde ahora puedes consultar en el {NOMBRE_APP} el consumo de créditos de "
                     f"<b>{escape(_lista(nombres))}</b>: el estado de los créditos asignados, la proyección de "
                     f"agotamiento y el detalle por journey.")
              + I._titulo_seccion("Acceso aprobado")
              + I._tabla_datos(filas)
              + _enlace(clave, "Ingresa con tu correo institucional y la contraseña que creaste")
              + I._p("Si tienes más de una unidad, puedes cambiar entre ellas en la opción <b>Vista</b> de la "
                     "barra lateral."))
    texto = _texto_plano(_saludo(nombre), f"{motivo} Ya puedes ver {_lista(nombres)} en el {NOMBRE_APP}.",
                         _enlace_texto(clave))
    pie = f"Recibes este correo porque pediste acceso al {NOMBRE_APP}. " + PIE_ACCESO
    return Mensaje(asunto, cuerpo, texto, pie)


def solicitud_no_aprobada(nombre: str | None, correo: str, unidad: str) -> Mensaje:
    asunto = f"Tu solicitud de acceso a {unidad} en el dashboard de créditos"
    cuerpo = (I._p(_saludo(nombre))
              + I._p(f"El Equipo CRM revisó tu solicitud para ver <b>{escape(unidad)}</b> en el {NOMBRE_APP} y, "
                     f"por ahora, no fue aprobada.")
              + I._titulo_seccion("Solicitud de acceso")
              + I._tabla_datos([("Cuenta", escape(correo)), ("Unidad solicitada", escape(unidad)),
                                ("Revisada", _fecha_hora(_ahora()))])
              + I._p("Esto suele pasar cuando la unidad elegida no corresponde a tu área. Si crees que es un error, "
                     "responde a este correo o pide acceso a otra unidad desde el dashboard."))
    texto = _texto_plano(_saludo(nombre), f"El Equipo CRM revisó tu solicitud para ver {unidad} y, por ahora, "
                         "no fue aprobada. Si crees que es un error, responde a este correo.")
    pie = f"Recibes este correo porque pediste acceso al {NOMBRE_APP}. " + PIE_ACCESO
    return Mensaje(asunto, cuerpo, texto, pie)


def contrasena_temporal(nombre: str | None, correo: str, valor: str, unidades: list[str]) -> Mensaje:
    asunto = "Tu contraseña temporal del dashboard de créditos"
    filas = [("Cuenta", escape(correo))]
    if unidades:
        filas.append(("Unidades que puedes ver", escape(_lista(unidades))))
    cuerpo = (I._p(_saludo(nombre))
              + I._p(f"El Equipo CRM te asignó una contraseña temporal para entrar al {NOMBRE_APP}.")
              + I._titulo_seccion("Contraseña temporal")
              + _caja_codigo(valor, tamano="18pt", espacio="2px")
              + I._tabla_datos(filas)
              + I._p("Al entrar te pediremos crear una contraseña nueva; la temporal deja de servir en ese "
                     "momento. Escríbela tal como aparece, con los guiones.")
              + _enlace(None, "Ingresa con tu correo institucional y esta contraseña")
              + _contacto())
    texto = _texto_plano(_saludo(nombre), f"El Equipo CRM te asignó una contraseña temporal para el {NOMBRE_APP}.",
                         f"Contraseña temporal: {valor}", "Al entrar te pediremos crear una nueva.", _enlace_texto())
    pie = f"Recibes este correo porque el Equipo CRM gestionó tu cuenta del {NOMBRE_APP}. " + PIE_ACCESO
    return Mensaje(asunto, cuerpo, texto, pie)


def contrasena_cambiada(nombre: str | None, correo: str, como: str) -> Mensaje:
    """Aviso de seguridad después de cambiar o restablecer la contraseña."""
    asunto = "Tu contraseña del dashboard de créditos cambió"
    cuerpo = (I._p(_saludo(nombre))
              + I._p(f"Te confirmamos que la contraseña de tu cuenta del {NOMBRE_APP} cambió. Por seguridad, se "
                     f"cerraron las sesiones que tenías recordadas en otros equipos.")
              + I._titulo_seccion("Cambio de contraseña")
              + I._tabla_datos([("Cuenta", escape(correo)), ("Cómo", escape(como)),
                                ("Fecha", _fecha_hora(_ahora()))])
              + _contacto())
    texto = _texto_plano(_saludo(nombre), f"La contraseña de tu cuenta del {NOMBRE_APP} ({correo}) cambió "
                         f"({como}). Si no fuiste tú, avísanos de inmediato.")
    pie = "Recibes este aviso de seguridad cada vez que cambia la contraseña de tu cuenta. " + PIE_ACCESO
    return Mensaje(asunto, cuerpo, texto, pie)


def nueva_solicitud(nombre: str, correo: str, unidad: str, pendientes: int) -> Mensaje:
    """Aviso al Equipo CRM: alguien pidió acceso a una unidad."""
    asunto = f"Solicitud de acceso al dashboard de créditos: {unidad}"
    filas = [("Nombre", escape(nombre)), ("Correo", escape(correo)), ("Unidad solicitada", escape(unidad)),
             ("Fecha", _fecha_hora(_ahora())), ("Solicitudes por aprobar", str(pendientes))]
    cuerpo = (I._p("Hola,")
              + I._p(f"<b>{escape(nombre)}</b> pidió acceso a <b>{escape(unidad)}</b> en el {NOMBRE_APP}. Su correo "
                     f"no está registrado como responsable de esa unidad, así que la solicitud quedó pendiente.")
              + I._titulo_seccion("Solicitud por revisar")
              + I._tabla_datos(filas)
              + I._p("Para aprobarla o rechazarla, entra al dashboard con tu cuenta del Equipo CRM y abre "
                     "<b>Usuarios</b> en la barra lateral.")
              + _enlace(None, "Ingresa al dashboard"))
    texto = _texto_plano("Hola,", f"{nombre} ({correo}) pidió acceso a {unidad} en el {NOMBRE_APP}.",
                         "Apruébala o recházala en el dashboard, en Usuarios.", _enlace_texto())
    pie = (f"Recibes este aviso porque estás en la lista del Equipo CRM del {NOMBRE_APP} (acceso.json). "
           "Este mensaje no contiene archivos adjuntos.")
    return Mensaje(asunto, cuerpo, texto, pie)


# ---------------------------------------------------------------------------
# Vista previa:  py correo_app.py
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
