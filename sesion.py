"""
Pantallas de acceso: iniciar sesión, crear cuenta, recuperar contraseña, cuenta pendiente,
Mi cuenta, Usuarios (Equipo CRM) y Bitácora (Equipo CRM).

Modos:
- Producción (por defecto):  py -m streamlit run app.py
  Pide iniciar sesión. Es el único modo en el enlace publicado.
- Pruebas (solo en un computador): py -m streamlit run app.py -- --pruebas
  Sin inicio de sesión, con permisos del Equipo CRM y todo guardado en la carpeta local.
"""

from __future__ import annotations

import base64
import html
import io
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from PIL import Image, ImageOps

import acceso as A
import almacen
import correo_app

COOKIE = "creditos_sesion"
ZONA = ZoneInfo("America/Bogota")
QUIEN_PRUEBAS = "modo pruebas"


# ---------------------------------------------------------------------------
# Modo
# ---------------------------------------------------------------------------

def en_la_nube() -> bool:
    """True en Streamlit Community Cloud (ahí el modo pruebas no existe)."""
    return Path("/mount/src").exists() or os.environ.get("HOME", "") == "/home/appuser"


def modo_pruebas() -> bool:
    return "--pruebas" in sys.argv[1:] and not en_la_nube()


def puede_mostrar_correos() -> bool:
    """Los correos se muestran en pantalla en lugar de enviarse solo en el modo pruebas. En producción un código
    nunca se muestra: si se mostrara, cualquiera podría crear una cuenta con un correo que no es suyo."""
    return modo_pruebas()


def fecha_local(texto: str | None, con_hora: bool = True) -> str:
    momento = A.desde_iso(texto)
    if not momento:
        return "—"
    return momento.astimezone(ZONA).strftime("%d/%m/%Y %H:%M" if con_hora else "%d/%m/%Y")


# ---------------------------------------------------------------------------
# Correos
# ---------------------------------------------------------------------------

def avisar(destinatarios, mensaje: correo_app.Mensaje) -> str:
    """Envía un correo. En el modo pruebas no le escribe a nadie: lo guarda para mostrarlo en pantalla.
    Devuelve "enviado", "en_pantalla", "sin_correo" o "error"."""
    destinatarios = [d for d in ([destinatarios] if isinstance(destinatarios, str) else destinatarios) if d]
    if not destinatarios:
        return "sin_correo"
    if puede_mostrar_correos():
        st.session_state.setdefault("correos_simulados", []).append((destinatarios, mensaje))
        return "en_pantalla"
    if not correo_app.configurado():
        return "sin_correo"
    try:
        correo_app.enviar(destinatarios, mensaje)
        return "enviado"
    except Exception as error:
        print(f"[correo] No se pudo enviar un correo a {', '.join(destinatarios)}: {error}", file=sys.stderr)
        return "error"


def mostrar_correos_simulados() -> None:
    """Modo pruebas: muestra los correos que se habrían enviado, tal como se verían."""
    for destinatarios, m in st.session_state.pop("correos_simulados", []):
        with st.expander(f"Correo simulado (modo pruebas, no se envió) para {', '.join(destinatarios)}: {m.asunto}",
                         icon=":material/forward_to_inbox:", expanded=True):
            st.html(m.vista_previa())


def enviar_codigo(correo: str, proposito: str, nombre: str | None = None) -> str | None:
    """Envía un código de verificación. None si salió bien; si no, el mensaje de error.
    En producción el código nunca se muestra en pantalla."""
    motivo = A.puede_enviar(correo, proposito)
    if motivo:
        return motivo
    if not correo_app.configurado():
        return ("El envío de correos aún no está configurado. Pídele al Equipo CRM que te cree la cuenta "
                "o te dé una contraseña temporal.")
    codigo = A.nuevo_codigo(correo, proposito)
    resultado = avisar(correo, correo_app.codigo(nombre, correo, codigo, proposito, A.CODIGO_MINUTOS))
    if resultado != "enviado":
        A.anular_codigo(correo, proposito)
        return "No se pudo enviar el correo con el código. Intenta de nuevo en unos minutos."
    return None


def avisar_admins(nombre: str, correo: str, unidad: str) -> None:
    """Aviso al Equipo CRM de una solicitud nueva (si no hay cómo enviar, la ven en Usuarios)."""
    avisar(A.leer_acceso()["equipo_crm"],
           correo_app.nueva_solicitud(nombre, correo, unidad, len(A.solicitudes_pendientes())))


def avisar_cambio_clave(correo: str, como: str) -> None:
    avisar(correo, correo_app.contrasena_cambiada((A.usuario(correo) or {}).get("nombre"), correo, como))


# ---------------------------------------------------------------------------
# Cookie de "recordarme"
# ---------------------------------------------------------------------------

def _script_cookie(valor: str, segundos: int) -> None:
    seguro = "; Secure" if str(getattr(st.context, "url", "") or "").startswith("https") else ""
    st.html(f"<script>document.cookie = '{COOKIE}={valor}; Max-Age={segundos}; Path=/; SameSite=Lax{seguro}';"
            f"</script>", unsafe_allow_javascript=True)


def aplicar_cookie_pendiente() -> None:
    """Escribe o borra la cookie en el navegador (se hace en la ejecución siguiente al inicio o cierre)."""
    pendiente = st.session_state.pop("cookie_pendiente", None)
    if pendiente == "borrar":
        _script_cookie("", 0)
    elif pendiente:
        _script_cookie(pendiente, A.DIAS_RECORDAR * 86400)


def entrar(correo: str, registro: dict, recordar: bool, como: str = "contraseña") -> None:
    st.session_state["usuario"] = A.normalizar(correo)
    st.session_state["version_sesion"] = int(registro.get("version", 1))
    if recordar:
        st.session_state["cookie_pendiente"] = A.crear_token(correo, int(registro.get("version", 1)))
    A.marcar_ingreso(correo)
    A.registrar(f"Inicia sesión ({como})", correo)
    for k in ("reg", "olv"):
        st.session_state.pop(k, None)
    st.rerun()


def salir(registrar: bool = True) -> None:
    correo = st.session_state.get("usuario")
    if registrar and correo:
        A.registrar("Cierra sesión", correo)
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.session_state["cookie_pendiente"] = "borrar"
    st.session_state["salio"] = True      # que no vuelva a entrar con la cookie que ya leyó esta pestaña
    st.rerun()


# ---------------------------------------------------------------------------
# Estilo de las pantallas de acceso
# ---------------------------------------------------------------------------

CSS_ACCESO = """
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] {display:none}
.acceso-marca {text-align:center; margin: 28px 0 18px}
.acceso-marca img {max-height:64px; margin-bottom:10px}
.acceso-institucion {font-size:13px; color:#52514e; letter-spacing:.2px}
.acceso-titulo {font-size:26px; font-weight:650; color:#1F3864; margin-top:4px}
.acceso-sub {font-size:14px; color:#52514e; margin-top:4px}
[class*="st-key-caja-acceso"] {border:1px solid #E1E5EC; border-radius:12px; padding:22px 24px 10px;
  background:#FFFFFF; box-shadow:0 1px 3px rgba(16,24,40,.06)}
.acceso-nota {font-size:12.5px; color:#52514e; margin:6px 0 12px; line-height:1.45}
.acceso-paso {font-size:12px; font-weight:600; color:#1F3864; text-transform:uppercase; letter-spacing:.6px;
  margin-bottom:6px}
</style>
"""


def encabezado_acceso(marca: dict, logo_html: str) -> None:
    st.markdown(CSS_ACCESO, unsafe_allow_html=True)
    st.markdown(f'<div class="acceso-marca">{logo_html}<div class="acceso-institucion">{marca["institucion"]} · '
                f'{marca["area"]}</div><div class="acceso-titulo">Créditos de mensajería</div>'
                f'<div class="acceso-sub">Consumo de créditos de Marketing Cloud por unidad</div></div>',
                unsafe_allow_html=True)


def caja_central():
    _, centro, _ = st.columns([1, 1.25, 1])
    return centro


# ---------------------------------------------------------------------------
# Pantalla de inicio de sesión
# ---------------------------------------------------------------------------

def _pestana_entrar() -> None:
    with st.form("form_entrar", border=False):
        correo = st.text_input("Correo institucional", placeholder="nombre@javeriana.edu.co", autocomplete="email")
        clave = st.text_input("Contraseña", type="password", autocomplete="current-password")
        recordar = st.checkbox(f"Recordarme en este equipo por {A.DIAS_RECORDAR} días", value=True)
        enviar = st.form_submit_button("Iniciar sesión", type="primary", width="stretch")
    if enviar:
        if not correo or not clave:
            st.error("Escribe tu correo y tu contraseña.")
            return
        with st.spinner("Verificando..."):
            registro, error = A.iniciar_sesion(correo, clave)
        if error:
            st.error(error)
            return
        entrar(correo, registro, recordar)
    st.markdown('<div class="acceso-nota">En un computador compartido, desmarca «Recordarme».</div>',
                unsafe_allow_html=True)


def _pestana_crear(nombres: dict[str, str], responsables: dict) -> None:
    reg = st.session_state.setdefault("reg", {"paso": 1})
    if reg["paso"] == 1:
        st.markdown('<div class="acceso-paso">Paso 1 de 3 · Tu correo</div>', unsafe_allow_html=True)
        with st.form("form_reg1", border=False):
            nombre = st.text_input("Nombre y apellido")
            correo = st.text_input("Correo institucional", placeholder="nombre@javeriana.edu.co")
            ok = st.form_submit_button("Enviarme un código", type="primary", width="stretch")
        st.markdown('<div class="acceso-nota">Te enviaremos un código para confirmar que el correo es tuyo.</div>',
                    unsafe_allow_html=True)
        if ok:
            correo = A.normalizar(correo)
            error = (("Escribe tu nombre." if len(nombre.strip()) < 3 else None) or A.correo_valido(correo)
                     or ("Ya existe una cuenta con ese correo. Inicia sesión o recupera tu contraseña."
                         if A.usuario(correo, fresco=True) else None))
            error = error or enviar_codigo(correo, "registro", nombre.strip())
            if error:
                st.error(error)
                return
            st.session_state["reg"] = {"paso": 2, "correo": correo, "nombre": nombre.strip()}
            st.rerun()
    elif reg["paso"] == 2:
        st.markdown('<div class="acceso-paso">Paso 2 de 3 · Código</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="acceso-nota">Enviamos un código de 6 dígitos a <b>{reg["correo"]}</b>. '
                    f'Vence en {A.CODIGO_MINUTOS} minutos. Revisa también la carpeta de correo no deseado.</div>',
                    unsafe_allow_html=True)
        with st.form("form_reg2", border=False):
            codigo = st.text_input("Código", max_chars=6)
            ok = st.form_submit_button("Verificar", type="primary", width="stretch")
        if ok:
            error = A.verificar_codigo(reg["correo"], "registro", codigo)
            if error:
                st.error(error)
            else:
                reg["paso"] = 3
                st.rerun()
        _botones_reenvio("reg", reg["correo"], "registro")
    else:
        correo = reg["correo"]
        admin = A.es_admin(correo)
        st.markdown('<div class="acceso-paso">Paso 3 de 3 · Unidad y contraseña</div>', unsafe_allow_html=True)
        with st.form("form_reg3", border=False):
            unidad = None
            if admin:
                st.markdown('<div class="acceso-nota">Tu correo está en la lista del <b>Equipo CRM</b>: tendrás '
                            'acceso a todas las unidades.</div>', unsafe_allow_html=True)
            else:
                unidad = st.selectbox("¿De qué unidad eres?", list(nombres), format_func=lambda u: nombres[u],
                                      index=None, placeholder="Elige tu unidad")
            clave = st.text_input("Crea una contraseña", type="password", autocomplete="new-password",
                                  help=f"Mínimo {A.MIN_CLAVE} caracteres. Una frase corta funciona bien.")
            clave2 = st.text_input("Repite la contraseña", type="password", autocomplete="new-password")
            ok = st.form_submit_button("Crear cuenta", type="primary", width="stretch")
        if ok:
            error = ((None if admin or unidad else "Elige tu unidad.") or A.clave_valida(clave, correo)
                     or (None if clave == clave2 else "Las contraseñas no coinciden."))
            if error:
                st.error(error)
                return
            try:
                registro = A.crear_usuario(correo, reg["nombre"], clave, unidad, responsables)
            except ValueError as e:
                st.error(str(e))
                return
            if admin:
                A.registrar("Crea su cuenta (Equipo CRM)", correo)
            elif registro["unidades"]:
                A.registrar("Crea su cuenta", correo,
                            f"Unidad {nombres[unidad]} aprobada sola: es responsable de la unidad")
            else:
                A.registrar("Crea su cuenta", correo, f"Solicita la unidad {nombres[unidad]}")
                avisar_admins(reg["nombre"], correo, nombres[unidad])
            entrar(correo, registro, True, "cuenta nueva")


def _botones_reenvio(clave_estado: str, correo: str, proposito: str) -> None:
    c1, c2 = st.columns(2)
    if c1.button("Reenviar código", key=f"reenviar_{clave_estado}", width="stretch"):
        nombre = (st.session_state.get(clave_estado) or {}).get("nombre") or (A.usuario(correo) or {}).get("nombre")
        error = enviar_codigo(correo, proposito, nombre)
        if error:
            st.error(error)
        else:
            st.success("Te enviamos un código nuevo.")
    if c2.button("Usar otro correo", key=f"otro_{clave_estado}", width="stretch"):
        st.session_state.pop(clave_estado, None)
        st.rerun()


def _pestana_olvido() -> None:
    olv = st.session_state.setdefault("olv", {"paso": 1})
    if olv["paso"] == 1:
        with st.form("form_olv1", border=False):
            correo = st.text_input("Correo de tu cuenta", placeholder="nombre@javeriana.edu.co")
            ok = st.form_submit_button("Enviarme un código", type="primary", width="stretch")
        if ok:
            correo = A.normalizar(correo)
            error = A.correo_valido(correo)
            if error:
                st.error(error)
                return
            r = A.usuario(correo, fresco=True)
            if r and r.get("estado") == "activo":
                error = enviar_codigo(correo, "recuperar", r.get("nombre"))
                if error:
                    st.error(error)
                    return
            # Mismo mensaje exista o no la cuenta (no se revela qué correos están registrados)
            st.session_state["olv"] = {"paso": 2, "correo": correo}
            st.rerun()
    else:
        correo = olv["correo"]
        st.markdown(f'<div class="acceso-nota">Si <b>{correo}</b> tiene una cuenta activa, le enviamos un código '
                    f'de 6 dígitos (vence en {A.CODIGO_MINUTOS} minutos).</div>', unsafe_allow_html=True)
        with st.form("form_olv2", border=False):
            codigo = st.text_input("Código", max_chars=6)
            clave = st.text_input("Nueva contraseña", type="password", autocomplete="new-password",
                                  help=f"Mínimo {A.MIN_CLAVE} caracteres.")
            clave2 = st.text_input("Repite la nueva contraseña", type="password", autocomplete="new-password")
            ok = st.form_submit_button("Cambiar contraseña", type="primary", width="stretch")
        if ok:
            error = (A.clave_valida(clave, correo) or (None if clave == clave2 else "Las contraseñas no coinciden.")
                     or A.verificar_codigo(correo, "recuperar", codigo))
            if error:
                st.error(error)
                return
            registro = A.cambiar_clave(correo, clave)
            A.registrar("Recupera su contraseña con código", correo)
            avisar_cambio_clave(correo, "Restablecida con código de verificación")
            A._memoria()["fallos"].pop(A.normalizar(correo), None)
            entrar(correo, registro, True, "recuperación")
        _botones_reenvio("olv", correo, "recuperar")


def pantalla_acceso(marca: dict, logo_html: str, nombres: dict[str, str], responsables: dict) -> None:
    encabezado_acceso(marca, logo_html)
    with caja_central():
        if not correo_app.configurado():
            st.warning("El envío de correos no está configurado: no se pueden crear cuentas ni recuperar "
                       "contraseñas. El Equipo CRM puede crear cuentas con contraseña temporal.",
                       icon=":material/mail_lock:")
        if not A.leer_acceso()["equipo_crm"]:
            st.warning("Aún no hay correos del Equipo CRM en acceso.json: nadie podrá aprobar solicitudes.",
                       icon=":material/warning:")
        with st.container(key="caja-acceso"):
            t1, t2, t3 = st.tabs(["Iniciar sesión", "Crear cuenta", "Olvidé mi contraseña"])
            with t1:
                _pestana_entrar()
            with t2:
                _pestana_crear(nombres, responsables)
            with t3:
                _pestana_olvido()
        st.markdown('<div class="acceso-nota" style="text-align:center">Solo para correos @javeriana.edu.co. '
                    'Las cuentas de unidad ven solo los créditos de su unidad.</div>', unsafe_allow_html=True)


def pantalla_cambio_obligatorio(correo: str, marca: dict, logo_html: str) -> None:
    encabezado_acceso(marca, logo_html)
    with caja_central(), st.container(key="caja-acceso"):
        st.markdown("#### Crea tu contraseña")
        st.markdown('<div class="acceso-nota">Entraste con una contraseña temporal. Crea una nueva para '
                    'continuar.</div>', unsafe_allow_html=True)
        with st.form("form_obligatorio", border=False):
            clave = st.text_input("Nueva contraseña", type="password", autocomplete="new-password",
                                  help=f"Mínimo {A.MIN_CLAVE} caracteres.")
            clave2 = st.text_input("Repite la nueva contraseña", type="password", autocomplete="new-password")
            ok = st.form_submit_button("Guardar y entrar", type="primary", width="stretch")
        if ok:
            error = A.clave_valida(clave, correo) or (None if clave == clave2 else "Las contraseñas no coinciden.")
            if error:
                st.error(error)
            else:
                registro = A.cambiar_clave(correo, clave)
                A.registrar("Cambia la contraseña temporal", correo)
                st.session_state["version_sesion"] = int(registro["version"])
                st.session_state["cookie_pendiente"] = A.crear_token(correo, int(registro["version"]))
                st.rerun()
        if st.button("Cerrar sesión", width="stretch"):
            salir()


def pantalla_pendiente(correo: str, registro: dict, nombres: dict[str, str], responsables: dict,
                       marca: dict, logo_html: str) -> None:
    encabezado_acceso(marca, logo_html)
    with caja_central(), st.container(key="caja-acceso"):
        st.markdown(f"#### Hola, {registro.get('nombre') or correo}")
        pedidas = [s["unidad"] for s in registro.get("solicitudes", []) if s["unidad"] in nombres]
        rechazadas = [s["unidad"] for s in registro.get("rechazadas", []) if s["unidad"] in nombres
                      and s["unidad"] not in pedidas]
        if pedidas:
            st.info("Tu solicitud para **" + "**, **".join(nombres[u] for u in pedidas) + "** está pendiente de "
                    "aprobación del Equipo CRM. Cuando la aprueben podrás ver el tablero (vuelve a entrar o "
                    "recarga la página).", icon=":material/hourglass_top:")
        elif rechazadas:
            st.warning("El Equipo CRM no aprobó tu solicitud para " + ", ".join(nombres[u] for u in rechazadas)
                       + ". Si crees que es un error, escríbeles o pide otra unidad.", icon=":material/block:")
        else:
            st.info("Tu cuenta aún no tiene unidades. Pide la de tu área.", icon=":material/info:")
        _pedir_otra_unidad(correo, registro, nombres, responsables)
        c1, c2 = st.columns(2)
        if c1.button("Revisar de nuevo", icon=":material/refresh:", width="stretch"):
            A.usuarios(fresco=True)
            st.rerun()
        if c2.button("Cerrar sesión", icon=":material/logout:", width="stretch"):
            salir()


def _pedir_otra_unidad(correo: str, registro: dict, nombres: dict[str, str], responsables: dict) -> None:
    ya = set(registro.get("unidades", [])) | {s["unidad"] for s in registro.get("solicitudes", [])}
    opciones = [u for u in nombres if u not in ya]
    if not opciones:
        return
    c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
    unidad = c1.selectbox("Pedir acceso a otra unidad", opciones, format_func=lambda u: nombres[u], index=None,
                          placeholder="Elige una unidad", key="pedir_unidad")
    if c2.button("Pedir acceso", disabled=unidad is None, width="stretch"):
        resultado = A.pedir_unidad(correo, unidad, responsables)
        if resultado == "aprobada":
            A.registrar("Agrega una unidad", correo, f"{nombres[unidad]} aprobada sola: es responsable de la unidad")
            st.toast(f"Ya tienes acceso a {nombres[unidad]}", icon=":material/check:")
        else:
            A.registrar("Solicita una unidad", correo, nombres[unidad])
            avisar_admins(registro.get("nombre") or correo, correo, nombres[unidad])
            st.toast("Solicitud enviada al Equipo CRM", icon=":material/send:")
        st.session_state.pop("pedir_unidad", None)
        st.rerun()


# ---------------------------------------------------------------------------
# Puerta de entrada
# ---------------------------------------------------------------------------

def puerta(nombres: dict[str, str], responsables: dict, marca: dict, logo_html: str) -> dict:
    """Decide quién está viendo. Si no hay sesión, muestra la pantalla de acceso y detiene la app.
    Devuelve {"correo", "nombre", "admin", "unidades", "pruebas"}."""
    if modo_pruebas():
        almacen.FORZAR_LOCAL = True
        return {"correo": QUIEN_PRUEBAS, "nombre": "Modo pruebas", "admin": True, "unidades": list(nombres),
                "pruebas": True}

    aplicar_cookie_pendiente()
    try:
        correo = st.session_state.get("usuario")
        if not correo and not st.session_state.get("salio"):
            token = st.context.cookies.get(COOKIE)
            correo = A.leer_token(token)
            if correo:
                st.session_state["usuario"] = correo
                st.session_state["version_sesion"] = int((A.usuario(correo) or {}).get("version", 1))
                A.marcar_ingreso(correo)
                A.registrar("Inicia sesión (recordada en el equipo)", correo)
            elif token:
                st.session_state["cookie_pendiente"] = "borrar"
                aplicar_cookie_pendiente()
        if not correo:
            pantalla_acceso(marca, logo_html, nombres, responsables)
            st.stop()

        registro = A.usuario(correo)
        # Cuenta desactivada o contraseña cambiada en otro equipo: se cierra esta sesión
        if (not registro or registro.get("estado") != "activo"
                or int(registro.get("version", 1)) != int(st.session_state.get("version_sesion", 0))):
            salir(registrar=False)
        if registro.get("cambiar_clave"):
            pantalla_cambio_obligatorio(correo, marca, logo_html)
            st.stop()
        admin = A.es_admin(correo)
        permitidas = list(nombres) if admin else [u for u in nombres if u in registro.get("unidades", [])]
        if not admin and not permitidas:
            pantalla_pendiente(correo, registro, nombres, responsables, marca, logo_html)
            st.stop()
    except almacen.ErrorAlmacen as error:
        st.error(f"No se pudieron leer las cuentas de usuario: {error}", icon=":material/cloud_off:")
        st.stop()
    return {"correo": correo, "nombre": registro.get("nombre") or correo, "admin": admin,
            "unidades": permitidas, "pruebas": False}


# ---------------------------------------------------------------------------
# Menú de perfil (arriba a la derecha) y páginas de cuenta
# ---------------------------------------------------------------------------

PAGINAS = {"cuenta": "Mi cuenta", "personalizar": "Personalizar tablero", "usuarios": "Usuarios",
           "bitacora": "Bitácora"}
COLORES_INICIALES = ["#1F3864", "#2C6E91", "#5B4B8A", "#1E7B3C", "#8A5A00", "#7A2E3A", "#36586E"]


def ir(pagina: str | None) -> None:
    st.session_state["pagina"] = pagina


def iniciales(nombre: str) -> str:
    partes = [p for p in str(nombre or "").replace(".", " ").split() if p[:1].isalpha()]
    return "".join(p[0] for p in partes[:2]).upper() or "?"


def avatar_src(ctx: dict, perfil: dict | None = None) -> str:
    """Foto de perfil (data URI) o, si no hay, un círculo con las iniciales."""
    perfil = A.perfil(ctx["correo"]) if perfil is None else perfil
    if perfil.get("avatar"):
        return perfil["avatar"]
    color = COLORES_INICIALES[sum(map(ord, ctx["correo"])) % len(COLORES_INICIALES)]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">'
           f'<circle cx="48" cy="48" r="48" fill="{color}"/><text x="48" y="49" text-anchor="middle" '
           f'dominant-baseline="central" font-family="Segoe UI, Arial, sans-serif" font-size="38" font-weight="600" '
           f'fill="#FFFFFF">{html.escape(iniciales(ctx["nombre"]))}</text></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def preparar_foto(archivo) -> str:
    """Recorta la imagen al centro en cuadrado, la reduce a 256 px y la devuelve como data URI (JPEG)."""
    archivo.seek(0)
    imagen = Image.open(archivo)
    imagen = ImageOps.exif_transpose(imagen).convert("RGB")
    lado = min(imagen.size)
    x, y = (imagen.width - lado) // 2, (imagen.height - lado) // 2
    imagen = imagen.crop((x, y, x + lado, y + lado)).resize((256, 256), Image.LANCZOS)
    salida = io.BytesIO()
    imagen.save(salida, format="JPEG", quality=86, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(salida.getvalue()).decode("ascii")


CSS_MENU = """
<style>
.st-key-menu-perfil {position: fixed; top: 0.55rem; right: 3.6rem; z-index: 999992; width: auto !important;}
.st-key-menu-perfil [data-testid="stPopover"] > div > button,
.st-key-menu-perfil [data-testid="stPopoverButton"] {
  border-radius: 999px !important; padding: 3px 12px 3px 4px; min-height: 0; height: 42px; gap: 8px;
  background: var(--t-superficie) !important; border: 1px solid var(--t-borde-fuerte) !important; box-shadow: var(--t-sombra);}
.st-key-menu-perfil [data-testid="stPopover"] > div > button:hover,
.st-key-menu-perfil [data-testid="stPopoverButton"]:hover {border-color: var(--t-primario) !important;}
.st-key-menu-perfil button p {font-size: 0.86rem; font-weight: 600; color: var(--t-texto) !important;}
.st-key-menu-perfil button::before {content: ""; width: 34px; height: 34px; border-radius: 50%;
  background: var(--avatar) center / cover no-repeat; flex: 0 0 34px;}
.perfil-cabeza {display: flex; gap: 12px; align-items: center; padding: 2px 0 10px 0;
  border-bottom: 1px solid var(--t-linea); margin-bottom: 6px;}
.perfil-cabeza img {width: 56px; height: 56px; border-radius: 50%; object-fit: cover;}
.perfil-nombre {font-weight: 650; font-size: 0.98rem; color: var(--t-texto); line-height: 1.2;}
.perfil-correo {font-size: 0.8rem; color: var(--t-texto-ter);}
.perfil-rol {display: inline-block; margin-top: 4px; font-size: 0.72rem; font-weight: 600; color: var(--t-primario);
  background: var(--t-primario-suave); border-radius: 999px; padding: 1px 8px;}
.st-key-menu-opciones button {justify-content: flex-start !important; border: 0 !important; padding-left: 8px; min-height: 2.3rem;}
.st-key-menu-opciones button > div, .st-key-menu-opciones button span {justify-content: flex-start !important;}
.st-key-menu-opciones [data-testid="stVerticalBlock"] {gap: 0.15rem;}
.st-key-menu-opciones button:hover {background: var(--t-superficie2) !important;}
.cuenta-foto {text-align: center;}
.cuenta-foto img {width: 168px; height: 168px; border-radius: 50%; object-fit: cover;
  border: 4px solid var(--t-primario-suave); box-shadow: var(--t-sombra);}
.cuenta-foto-nota {font-size: 0.78rem; color: var(--t-texto-ter); margin-top: 8px;}
</style>
"""


def rol_texto(ctx: dict) -> str:
    if ctx["pruebas"]:
        return "Modo pruebas · Equipo CRM"
    if ctx["admin"]:
        return "Equipo CRM"
    n = len(ctx["unidades"])
    return f"{n} {'unidad' if n == 1 else 'unidades'}"


def menu_perfil(ctx: dict) -> None:
    """Botón con la foto y el nombre arriba a la derecha; al abrirlo, las opciones de la cuenta."""
    perfil = A.perfil(ctx["correo"])
    src = avatar_src(ctx, perfil)
    st.markdown(CSS_MENU + f"<style>.st-key-menu-perfil {{--avatar: url('{src}');}}</style>",
                unsafe_allow_html=True)
    pendientes = len(A.solicitudes_pendientes()) if ctx["admin"] else 0
    primer = str(ctx["nombre"]).split()[0] if ctx["nombre"] else ""
    with st.container(key="menu-perfil"):
        with st.popover(primer + (f" ({pendientes})" if pendientes else ""), width="content"):
            st.markdown(f'<div class="perfil-cabeza"><img src="{src}" alt=""><div>'
                        f'<div class="perfil-nombre">{html.escape(ctx["nombre"])}</div>'
                        f'<div class="perfil-correo">{html.escape(ctx["correo"]) if not ctx["pruebas"] else "Sin inicio de sesión"}</div>'
                        f'<span class="perfil-rol">{rol_texto(ctx)}</span></div></div>', unsafe_allow_html=True)
            opciones = ([] if ctx["pruebas"] else [("cuenta", ":material/person:")]) + [("personalizar", ":material/tune:")]
            if ctx["admin"]:
                opciones += [("usuarios", ":material/group:"), ("bitacora", ":material/history:")]
            with st.container(key="menu-opciones"):
                if st.session_state.get("pagina"):
                    st.button("Volver al tablero", icon=":material/space_dashboard:", width="stretch",
                              on_click=ir, args=(None,), key="menu_volver", type="tertiary")
                for clave, icono in opciones:
                    etiqueta = PAGINAS[clave] + (f" · {pendientes} por aprobar" if clave == "usuarios" and pendientes else "")
                    st.button(etiqueta, icon=icono, width="stretch", key=f"menu_{clave}", on_click=ir, args=(clave,),
                              type="tertiary")
                if not ctx["pruebas"] and st.button("Cerrar sesión", icon=":material/logout:", width="stretch",
                                                    key="menu_salir", type="tertiary"):
                    salir()


def pagina_actual(ctx: dict, nombres: dict[str, str], responsables: dict) -> bool:
    """Dibuja Mi cuenta / Personalizar / Usuarios / Bitácora si están abiertas. True si se dibujó alguna."""
    mostrar_correos_simulados()
    pagina = st.session_state.get("pagina")
    validas = {"personalizar"} | ({"cuenta"} if not ctx["pruebas"] else set()) | (
        {"usuarios", "bitacora"} if ctx["admin"] else set())
    if pagina not in validas:
        st.session_state.pop("pagina", None)
        return False
    st.button("Volver al tablero", icon=":material/arrow_back:", on_click=ir, args=(None,), key="volver_pagina")
    if pagina == "cuenta":
        pagina_cuenta(ctx, nombres, responsables)
    elif pagina == "personalizar":
        import personalizar
        personalizar.pagina(ctx, nombres, ctx["tema"])
    elif pagina == "usuarios":
        pagina_usuarios(ctx, nombres)
    else:
        pagina_bitacora(nombres)
    return True


def seccion_foto(ctx: dict) -> None:
    """Foto grande para ver bien cómo queda; al elegir un archivo se muestra cómo se verá antes de guardarla."""
    perfil = A.perfil(ctx["correo"])
    st.markdown("### Foto de perfil")
    n = st.session_state.setdefault("foto_perfil_n", 0)
    archivo = st.session_state.get(f"foto_perfil_{n}")
    previa, error = None, None
    if archivo is not None:
        try:
            previa = preparar_foto(archivo)
        except Exception:
            error = "No se pudo leer la imagen. Prueba con otro archivo JPG o PNG."
    c1, c2 = st.columns([1, 1.5], vertical_alignment="center", gap="medium")
    nota_foto = ("Así se verá. Aún no está guardada." if previa else
                 "Tu foto actual." if perfil.get("avatar") else "Sin foto: se muestran tus iniciales.")
    c1.markdown(f'<div class="cuenta-foto"><img src="{previa or avatar_src(ctx, perfil)}" alt="Foto de perfil">'
                f'<div class="cuenta-foto-nota">{nota_foto}</div></div>', unsafe_allow_html=True)
    with c2:
        st.file_uploader("Sube una foto (JPG o PNG)", type=["jpg", "jpeg", "png"], key=f"foto_perfil_{n}",
                         help="Se recorta al centro en cuadrado. Una foto de frente, con la cara centrada, queda mejor.")
        if error:
            st.error(error)
        b1, b2 = st.columns(2)
        if b1.button("Guardar foto", type="primary", disabled=previa is None, width="stretch"):
            A.guardar_perfil(ctx["correo"], lambda p: p.update(avatar=previa), "Foto de perfil")
            A.registrar("Cambia su foto de perfil", ctx["correo"])
            st.session_state["foto_perfil_n"] = n + 1   # deja el selector de archivo vacío
            st.toast("Foto guardada", icon=":material/check:")
            st.rerun()
        if b2.button("Quitar foto", disabled=not perfil.get("avatar"), width="stretch"):
            A.guardar_perfil(ctx["correo"], lambda p: p.pop("avatar", None), "Quita foto de perfil")
            st.rerun()


def pagina_cuenta(ctx: dict, nombres: dict[str, str], responsables: dict) -> None:
    correo = ctx["correo"]
    registro = A.usuario(correo) or {}
    st.markdown("## Mi cuenta")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        seccion_foto(ctx)
        st.markdown("### Datos")
        st.markdown(f"- **Nombre:** {registro.get('nombre', '')}\n- **Correo:** {correo}\n"
                    f"- **Rol:** {'Equipo CRM (todas las unidades)' if ctx['admin'] else 'Usuario de unidad'}\n"
                    f"- **Cuenta creada:** {fecha_local(registro.get('creado'), False)}")
        if not ctx["admin"]:
            st.markdown("### Unidades")
            st.markdown("\n".join(f"- {nombres[u]}" for u in ctx["unidades"]) or "Ninguna")
            pedidas = [nombres[s["unidad"]] for s in registro.get("solicitudes", []) if s["unidad"] in nombres]
            if pedidas:
                st.caption("Pendientes de aprobación: " + ", ".join(pedidas))
            _pedir_otra_unidad(correo, registro, nombres, responsables)
    with c2:
        st.markdown("### Cambiar contraseña")
        with st.form("form_cambiar", border=True):
            actual = st.text_input("Contraseña actual", type="password", autocomplete="current-password")
            nueva = st.text_input("Nueva contraseña", type="password", autocomplete="new-password",
                                  help=f"Mínimo {A.MIN_CLAVE} caracteres.")
            nueva2 = st.text_input("Repite la nueva contraseña", type="password", autocomplete="new-password")
            ok = st.form_submit_button("Cambiar contraseña", type="primary")
        if ok:
            error = ((None if A.coincide(actual, registro.get("clave")) else "La contraseña actual no es correcta.")
                     or A.clave_valida(nueva, correo) or (None if nueva == nueva2 else "Las contraseñas no coinciden."))
            if error:
                st.error(error)
            else:
                nuevo = A.cambiar_clave(correo, nueva)
                A.registrar("Cambia su contraseña", correo)
                avisar_cambio_clave(correo, "Cambiada desde Mi cuenta")
                st.session_state["version_sesion"] = int(nuevo["version"])
                st.session_state["cookie_pendiente"] = A.crear_token(correo, int(nuevo["version"]))
                st.toast("Contraseña cambiada. Las sesiones recordadas en otros equipos se cerraron.",
                         icon=":material/check:")
                st.rerun()
        st.markdown("### Sesiones")
        st.caption("Si entraste desde un computador que no es tuyo, cierra la sesión en todos los equipos.")
        if st.button("Cerrar sesión en todos los equipos", icon=":material/devices:"):
            def cambio(r):
                r["version"] = int(r.get("version", 1)) + 1
            A.modificar_usuario(correo, cambio, "Cierra sesiones")
            A.registrar("Cierra la sesión en todos los equipos", correo)
            salir(registrar=False)


def _texto_unidades(lista: list[str], nombres: dict[str, str]) -> str:
    return ", ".join(nombres.get(u, f"{u} (ya no existe)") for u in lista) or "—"


def pagina_usuarios(ctx: dict, nombres: dict[str, str]) -> None:
    quien = ctx["correo"]
    st.markdown("## Usuarios")
    admins = A.leer_acceso()["equipo_crm"]
    todos = A.usuarios(fresco=True)

    # Solicitudes
    st.markdown("### Solicitudes por aprobar")
    pendientes = A.solicitudes_pendientes()
    if not pendientes:
        st.caption("No hay solicitudes pendientes.")
    for correo, r, s in pendientes:
        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 1, 1], vertical_alignment="center")
            c1.markdown(f"**{r.get('nombre') or correo}** · {correo}  \nPide **{nombres.get(s['unidad'], s['unidad'])}** "
                        f"· {fecha_local(s.get('fecha'))}")
            for col, aprobar in ((c2, True), (c3, False)):
                if col.button("Aprobar" if aprobar else "Rechazar", key=f"{'ap' if aprobar else 're'}_{correo}_{s['unidad']}",
                              type="primary" if aprobar else "secondary", width="stretch",
                              icon=":material/check:" if aprobar else ":material/close:"):
                    A.resolver_solicitud(correo, s["unidad"], aprobar)
                    unidad_txt = nombres.get(s["unidad"], s["unidad"])
                    A.registrar("Aprueba acceso" if aprobar else "Rechaza acceso", quien, unidad_txt, sobre=correo)
                    avisar(correo, correo_app.acceso_aprobado(r.get("nombre"), correo, {s["unidad"]: unidad_txt})
                           if aprobar else correo_app.solicitud_no_aprobada(r.get("nombre"), correo, unidad_txt))
                    st.rerun()

    # Cuentas
    st.markdown("### Cuentas")
    if todos:
        filas = []
        for correo, r in sorted(todos.items()):
            es_adm = correo in admins
            filas.append({
                "Correo": correo, "Nombre": r.get("nombre", ""),
                "Rol": "Equipo CRM" if es_adm else "Unidad",
                "Unidades": "Todas" if es_adm else _texto_unidades(r.get("unidades", []), nombres),
                "Estado": {"activo": "Activa", "inactivo": "Desactivada"}.get(r.get("estado"), r.get("estado")),
                "Último ingreso": fecha_local(r.get("ultimo_ingreso")),
                "Aviso": ("Sin entrar hace más de 90 días" if A.inactivo(r) and r.get("estado") == "activo" else
                          "Debe cambiar la contraseña" if r.get("cambiar_clave") else
                          "Sin unidades" if not es_adm and not r.get("unidades") else ""),
            })
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
        viejos = [f["Correo"] for f in filas if f["Aviso"].startswith("Sin entrar")]
        if viejos:
            st.caption(f"{len(viejos)} {'cuenta lleva' if len(viejos) == 1 else 'cuentas llevan'} más de 90 días sin "
                       "entrar. Si esa persona ya no está en la unidad, desactívala.")
    else:
        st.caption("Aún no hay cuentas.")

    if todos:
        st.markdown("### Administrar una cuenta")
        elegido = st.selectbox("Cuenta", sorted(todos), index=None, placeholder="Elige un correo",
                               format_func=lambda c: f"{todos[c].get('nombre') or c} · {c}", key="cuenta_admin")
        if elegido:
            _administrar(elegido, todos[elegido], quien, nombres, elegido in admins)

    with st.expander("Crear una cuenta para alguien", icon=":material/person_add:"):
        st.caption("Útil si la persona no recibe el código. Se crea con una contraseña temporal que debe cambiar "
                   "al entrar.")
        with st.form("form_crear_admin"):
            nombre = st.text_input("Nombre y apellido")
            correo = st.text_input("Correo institucional")
            unidades = st.multiselect("Unidades", list(nombres), format_func=lambda u: nombres[u])
            ok = st.form_submit_button("Crear cuenta", type="primary")
        if ok:
            correo = A.normalizar(correo)
            error = (("Escribe el nombre." if len(nombre.strip()) < 3 else None) or A.correo_valido(correo)
                     or ("Ya existe una cuenta con ese correo." if correo in todos else None))
            if error:
                st.error(error)
            else:
                temporal = A.clave_temporal()
                A.crear_usuario(correo, nombre, temporal, None, {})

                def cambio(r):
                    r["unidades"] = list(unidades)
                    r["cambiar_clave"] = True
                A.modificar_usuario(correo, cambio, "Cuenta creada por el Equipo CRM")
                A.registrar("Crea una cuenta", quien, f"Unidades: {_texto_unidades(unidades, nombres)}", sobre=correo)
                _entregar_temporal(correo, temporal, nombre.strip(), [nombres[u] for u in unidades])

    st.markdown("### Equipo CRM")
    st.markdown("\n".join(f"- {c}" + ("" if c in todos else " (aún no ha creado su cuenta)") for c in admins)
                or "Ninguno")
    st.caption("Esta lista solo se cambia en el archivo acceso.json del repositorio, no desde la app.")


def _entregar_temporal(correo: str, temporal: str, nombre: str | None, unidades: list[str]) -> None:
    resultado = avisar(correo, correo_app.contrasena_temporal(nombre, correo, temporal, unidades))
    if resultado != "enviado":
        st.session_state["temporal_mostrar"] = (correo, temporal)
    else:
        st.toast(f"Contraseña temporal enviada a {correo}", icon=":material/send:")
    st.rerun()


def _administrar(correo: str, r: dict, quien: str, nombres: dict[str, str], es_adm: bool) -> None:
    mostrar = st.session_state.get("temporal_mostrar")
    if mostrar and mostrar[0] == correo:
        st.success(f"Contraseña temporal de {correo}: **{mostrar[1]}**. Dásela a la persona por un canal seguro "
                   "(no se vuelve a mostrar).", icon=":material/key:")
        st.session_state.pop("temporal_mostrar", None)
    with st.container(border=True):
        if es_adm:
            st.caption("Es del Equipo CRM: ve todas las unidades. Para quitarle ese rol, sácalo de acceso.json.")
        else:
            c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
            actuales = [u for u in r.get("unidades", []) if u in nombres]
            nuevas = c1.multiselect("Unidades que puede ver", list(nombres), default=actuales,
                                    format_func=lambda u: nombres[u], key=f"unid_{correo}")
            if c2.button("Guardar unidades", disabled=set(nuevas) == set(actuales), width="stretch",
                         key=f"g_unid_{correo}"):
                def cambio(reg):
                    reg["unidades"] = list(nuevas)
                    reg["solicitudes"] = [s for s in reg.get("solicitudes", []) if s["unidad"] not in nuevas]
                A.modificar_usuario(correo, cambio, "Cambia unidades")
                agregadas = [u for u in nuevas if u not in actuales]
                quitadas = [u for u in actuales if u not in nuevas]
                detalle = "; ".join(x for x in (
                    f"agrega {_texto_unidades(agregadas, nombres)}" if agregadas else "",
                    f"quita {_texto_unidades(quitadas, nombres)}" if quitadas else "") if x)
                A.registrar("Cambia las unidades de una cuenta", quien, detalle, sobre=correo)
                st.toast("Unidades guardadas", icon=":material/check:")
                st.rerun()
        b1, b2, _ = st.columns([1, 1, 1])
        activa = r.get("estado") == "activo"
        if b1.button("Desactivar cuenta" if activa else "Activar cuenta", width="stretch", key=f"act_{correo}",
                     icon=":material/person_off:" if activa else ":material/person_check:",
                     disabled=correo == quien):
            def cambio(reg):
                reg["estado"] = "inactivo" if activa else "activo"
                reg["version"] = int(reg.get("version", 1)) + 1   # cierra sus sesiones abiertas
            A.modificar_usuario(correo, cambio, "Cambia estado")
            A.registrar("Desactiva una cuenta" if activa else "Activa una cuenta", quien, sobre=correo)
            st.rerun()
        if b2.button("Dar contraseña temporal", width="stretch", key=f"temp_{correo}", icon=":material/key:",
                     disabled=correo == quien):
            temporal = A.clave_temporal()
            A.cambiar_clave(correo, temporal, temporal=True)
            A.registrar("Da una contraseña temporal", quien, sobre=correo)
            _entregar_temporal(correo, temporal, r.get("nombre"),
                               [nombres[u] for u in r.get("unidades", []) if u in nombres])
        st.caption(f"Creada el {fecha_local(r.get('creado'), False)} · último ingreso "
                   f"{fecha_local(r.get('ultimo_ingreso'))}. Desactivar o dar una contraseña temporal cierra sus "
                   "sesiones abiertas.")


def pagina_bitacora(nombres: dict[str, str]) -> None:
    st.markdown("## Bitácora")
    st.caption("Quién hizo qué y cuándo: cuentas, aprobaciones, inicios de sesión y cambios de créditos, precios y "
               "unidades. Nunca guarda contraseñas ni códigos.")
    eventos = list(reversed(A.bitacora()))
    if not eventos:
        st.caption("Aún no hay registros.")
        return
    datos = pd.DataFrame([{"Fecha": fecha_local(e.get("fecha")), "Quién": e.get("quien", ""),
                           "Qué": e.get("evento", ""), "Sobre": e.get("sobre", ""), "Detalle": e.get("detalle", "")}
                          for e in eventos])
    c1, c2, c3 = st.columns([2, 2, 1.2], vertical_alignment="bottom")
    buscar = c1.text_input("Buscar (correo, evento o detalle)", key="bit_buscar")
    tipos = c2.multiselect("Tipo", ["Créditos, precios y unidades", "Cuentas y accesos", "Inicios de sesión"],
                           key="bit_tipos", placeholder="Todos")
    sin_ingresos = c3.checkbox("Ocultar inicios de sesión", value=True, key="bit_sin",
                               help="Oculta los inicios y cierres de sesión, que son la mayoría de los registros.")
    mascara = pd.Series(True, index=datos.index)
    if buscar:
        b = buscar.lower()
        mascara &= datos.apply(lambda f: b in " ".join(map(str, f.values)).lower(), axis=1)
    es_sesion = datos["Qué"].str.contains("sesión", case=False)
    es_datos = datos["Qué"].str.contains("crédito|precio|unidades y journeys", case=False)
    if sin_ingresos:
        mascara &= ~es_sesion
    if tipos:
        elegido = pd.Series(False, index=datos.index)
        if "Inicios de sesión" in tipos:
            elegido |= es_sesion
        if "Créditos, precios y unidades" in tipos:
            elegido |= es_datos
        if "Cuentas y accesos" in tipos:
            elegido |= ~es_sesion & ~es_datos
        mascara &= elegido
    vista = datos.loc[mascara]
    st.dataframe(vista, hide_index=True, width="stretch", height=min(35 * (len(vista) + 1) + 3, 640),
                 column_config={"Fecha": st.column_config.TextColumn(width="small"),
                                "Quién": st.column_config.TextColumn(width="medium"),
                                "Qué": st.column_config.TextColumn(width="medium"),
                                "Sobre": st.column_config.TextColumn(width="medium"),
                                "Detalle": st.column_config.TextColumn(width="large")})
    st.caption(f"{len(vista)} de {len(datos)} registros.")
    st.download_button("Descargar bitácora (CSV)", datos.to_csv(index=False).encode("utf-8-sig"),
                       file_name="bitacora.csv", mime="text/csv", icon=":material/download:")

