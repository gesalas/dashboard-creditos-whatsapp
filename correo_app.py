"""
Correos que envía la app (códigos de verificación, avisos de solicitudes, contraseñas temporales).

Se envían por el primer camino disponible:
1. SMTP, si están en los Secrets (es el único que sirve en el enlace publicado de Streamlit Cloud).
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
"""

from __future__ import annotations

import html
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr


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


def _enviar_outlook(destinatarios: list[str], asunto: str, texto: str, cuerpo_html: str) -> None:
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
        correo.Subject = asunto
        correo.Body = texto
        correo.HTMLBody = cuerpo_html
        correo.Send()
    finally:
        pythoncom.CoUninitialize()


def _html(titulo: str, parrafos: list[str], destacado: str | None = None) -> str:
    cuerpo = "".join(f'<p style="margin:0 0 12px">{p}</p>' for p in parrafos)
    caja = (f'<div style="font-size:28px;letter-spacing:6px;font-weight:700;color:#1F3864;background:#F3F5F9;'
            f'border-radius:8px;padding:14px 18px;display:inline-block;margin:4px 0 16px">{html.escape(destacado)}</div>'
            if destacado else "")
    return (f'<div style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#1B1F24;max-width:520px">'
            f'<div style="font-size:18px;font-weight:600;color:#1F3864;margin-bottom:14px">{html.escape(titulo)}</div>'
            f'{cuerpo}{caja}'
            f'<p style="margin:16px 0 0;color:#52514e;font-size:12px">Equipo CRM · Dirección de Tecnologías de '
            f'Información · Pontificia Universidad Javeriana</p></div>')


def enviar(destinatarios: list[str] | str, asunto: str, titulo: str, parrafos: list[str],
           destacado: str | None = None) -> None:
    """Envía el correo. Lanza una excepción si falla (quien llama decide qué mostrar)."""
    c = configuracion()
    if isinstance(destinatarios, str):
        destinatarios = [destinatarios]
    texto = "\n\n".join([titulo, *[html.unescape(p.replace("<b>", "").replace("</b>", "")) for p in parrafos]]
                        + ([destacado] if destacado else []))
    if metodo() == "outlook":
        _enviar_outlook(destinatarios, asunto, texto, _html(titulo, parrafos, destacado))
        return
    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = formataddr((c.get("remitente", "Créditos de mensajería"), c["usuario"]))
    mensaje["To"] = ", ".join(destinatarios)
    mensaje.set_content(texto)
    mensaje.add_alternative(_html(titulo, parrafos, destacado), subtype="html")
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
