"""
Correos que envía la app (códigos de verificación, avisos de solicitudes, contraseñas temporales).

Se configuran en los Secrets (Settings > Secrets en Streamlit Cloud, o .streamlit/secrets.toml en local):

    [correo]
    servidor = "smtp.gmail.com"
    puerto = 465
    usuario = "cuenta.del.dashboard@gmail.com"
    clave = "contraseña de aplicación de 16 letras"     # nunca la contraseña normal de la cuenta
    remitente = "Créditos de mensajería · Equipo CRM"

Sin esa sección, los correos no se envían: en el modo pruebas y en local se muestran en pantalla.
"""

from __future__ import annotations

import html
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


def configurado() -> bool:
    c = configuracion()
    return bool(c.get("usuario") and c.get("clave"))


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
    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = formataddr((c.get("remitente", "Créditos de mensajería"), c["usuario"]))
    mensaje["To"] = ", ".join(destinatarios)
    texto = "\n\n".join([titulo, *[html.unescape(p.replace("<b>", "").replace("</b>", "")) for p in parrafos]]
                        + ([destacado] if destacado else []))
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
