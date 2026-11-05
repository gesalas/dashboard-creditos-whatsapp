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

import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

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
    """Sin correo configurado, los mensajes se muestran en pantalla solo en el modo pruebas o en este mismo
    computador (nunca en el enlace publicado ni a otro equipo de la red)."""
    if modo_pruebas():
        return True
    if en_la_nube():
        return False
    try:
        ip = st.context.ip_address
    except Exception:
        ip = None
    return ip in (None, "127.0.0.1", "::1", "localhost")


def fecha_local(texto: str | None, con_hora: bool = True) -> str:
    momento = A.desde_iso(texto)
    if not momento:
        return "—"
    return momento.astimezone(ZONA).strftime("%d/%m/%Y %H:%M" if con_hora else "%d/%m/%Y")


# ---------------------------------------------------------------------------
# Correos
# ---------------------------------------------------------------------------

def avisar(destinatarios, asunto: str, titulo: str, parrafos: list[str], destacado: str | None = None,
           *, contenedor=None) -> str:
    """Envía un correo. Sin correo configurado lo muestra en pantalla si se puede.
    Devuelve "enviado", "en_pantalla", "sin_correo" o "error"."""
    destinatarios = [d for d in ([destinatarios] if isinstance(destinatarios, str) else destinatarios) if d]
    if not destinatarios:
        return "sin_correo"
    if correo_app.configurado():
        try:
            correo_app.enviar(destinatarios, asunto, titulo, parrafos, destacado)
            return "enviado"
        except Exception as error:
            print(f"[correo] No se pudo enviar «{asunto}»: {error}", file=sys.stderr)
            return "error"
    if puede_mostrar_correos():
        destino = contenedor or st
        texto = " ".join(p.replace("<b>", "**").replace("</b>", "**") for p in parrafos)
        destino.info(f"**Correo simulado** (el correo no está configurado; solo se ve en este computador) "
                     f"para {', '.join(destinatarios)}: *{asunto}*. {texto}"
                     + (f"\n\n**{destacado}**" if destacado else ""), icon=":material/forward_to_inbox:")
        return "en_pantalla"
    return "sin_correo"


def enviar_codigo(correo: str, proposito: str) -> str | None:
    """Envía un código de verificación. None si salió bien; si no, el mensaje de error."""
    motivo = A.puede_enviar(correo, proposito)
    if motivo:
        return motivo
    if not correo_app.configurado() and not puede_mostrar_correos():
        return ("El envío de correos aún no está configurado. Pídele al Equipo CRM que te cree la cuenta "
                "o te dé una contraseña temporal.")
    codigo = A.nuevo_codigo(correo, proposito)
    accion = "crear tu cuenta" if proposito == "registro" else "cambiar tu contraseña"
    resultado = avisar(correo, f"Tu código para {accion}: {codigo}", "Código de verificación",
                       [f"Usa este código para {accion} en el dashboard de créditos de mensajería.",
                        f"Vence en {A.CODIGO_MINUTOS} minutos. Si no lo pediste, ignora este correo."], codigo)
    if resultado == "error":
        return "No se pudo enviar el correo. Intenta de nuevo en unos minutos."
    if resultado == "en_pantalla":
        st.session_state["codigo_simulado"] = (correo, codigo)
    return None


def avisar_admins(asunto: str, parrafos: list[str]) -> None:
    if correo_app.configurado():
        avisar(A.leer_acceso()["equipo_crm"], asunto, asunto, parrafos)


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
    for k in ("reg", "olv", "codigo_simulado"):
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
            error = error or enviar_codigo(correo, "registro")
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
        _mostrar_codigo_simulado(reg["correo"])
        with st.form("form_reg2", border=False):
            codigo = st.text_input("Código", max_chars=6)
            ok = st.form_submit_button("Verificar", type="primary", width="stretch")
        if ok:
            error = A.verificar_codigo(reg["correo"], "registro", codigo)
            if error:
                st.error(error)
            else:
                reg["paso"] = 3
                st.session_state.pop("codigo_simulado", None)
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
                avisar_admins("Nueva solicitud de acceso",
                              [f"<b>{reg['nombre']}</b> ({correo}) pidió acceso a <b>{nombres[unidad]}</b>.",
                               "Apruébala o recházala en el dashboard: Usuarios."])
            entrar(correo, registro, True, "cuenta nueva")


def _mostrar_codigo_simulado(correo: str) -> None:
    sim = st.session_state.get("codigo_simulado")
    if sim and sim[0] == correo:
        st.info(f"Correo simulado (el envío de correos no está configurado; solo se ve en este computador). "
                f"Código: **{sim[1]}**", icon=":material/forward_to_inbox:")


def _botones_reenvio(clave_estado: str, correo: str, proposito: str) -> None:
    c1, c2 = st.columns(2)
    if c1.button("Reenviar código", key=f"reenviar_{clave_estado}", width="stretch"):
        error = enviar_codigo(correo, proposito)
        if error:
            st.error(error)
        else:
            st.success("Te enviamos un código nuevo.")
    if c2.button("Usar otro correo", key=f"otro_{clave_estado}", width="stretch"):
        st.session_state.pop(clave_estado, None)
        st.session_state.pop("codigo_simulado", None)
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
                error = enviar_codigo(correo, "recuperar")
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
        _mostrar_codigo_simulado(correo)
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
            A._memoria()["fallos"].pop(A.normalizar(correo), None)
            entrar(correo, registro, True, "recuperación")
        _botones_reenvio("olv", correo, "recuperar")


def pantalla_acceso(marca: dict, logo_html: str, nombres: dict[str, str], responsables: dict) -> None:
    encabezado_acceso(marca, logo_html)
    with caja_central():
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
            avisar_admins("Nueva solicitud de acceso",
                          [f"<b>{registro.get('nombre') or correo}</b> ({correo}) pidió acceso a "
                           f"<b>{nombres[unidad]}</b>.", "Apruébala o recházala en el dashboard: Usuarios."])
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
# Barra lateral y páginas de cuenta
# ---------------------------------------------------------------------------

PAGINAS = {"cuenta": "Mi cuenta", "usuarios": "Usuarios", "bitacora": "Bitácora"}


def ir(pagina: str | None) -> None:
    st.session_state["pagina"] = pagina


def bloque_lateral(ctx: dict) -> None:
    """Tarjeta de la barra lateral con quién está viendo y los accesos a cuenta y administración."""
    rol = "Permisos del Equipo CRM" if ctx["pruebas"] else ("Equipo CRM" if ctx["admin"] else
                                                 f"{len(ctx['unidades'])} {'unidad' if len(ctx['unidades']) == 1 else 'unidades'}")
    with st.container(key="lado-cuenta"):
        st.markdown(f'<div class="lado-titulo"><span class="lado-icono">account_circle</span><div>'
                    f'<div>{ctx["nombre"]}</div><div class="lado-sub">{rol}</div></div></div>',
                    unsafe_allow_html=True)
        pagina = st.session_state.get("pagina")
        if pagina:
            st.button("Volver al tablero", icon=":material/arrow_back:", width="stretch", type="primary",
                      on_click=ir, args=(None,), key="volver_lado")
        botones = [] if ctx["pruebas"] else [("cuenta", ":material/person:")]
        pendientes = 0
        if ctx["admin"]:
            pendientes = len(A.solicitudes_pendientes())
            botones += [("usuarios", ":material/group:"), ("bitacora", ":material/history:")]
        for clave, icono in botones:
            etiqueta = PAGINAS[clave]
            if clave == "usuarios" and pendientes:
                etiqueta += f" ({pendientes} por aprobar)"
            st.button(etiqueta, icon=icono, width="stretch", key=f"ir_{clave}", on_click=ir, args=(clave,),
                      disabled=pagina == clave)
        if not ctx["pruebas"] and st.button("Cerrar sesión", icon=":material/logout:", width="stretch",
                                            key="salir_lado"):
            salir()


def pagina_actual(ctx: dict, nombres: dict[str, str], responsables: dict) -> bool:
    """Dibuja Mi cuenta / Usuarios / Bitácora si están abiertas. True si se dibujó alguna."""
    pagina = st.session_state.get("pagina")
    if pagina == "cuenta" and not ctx["pruebas"]:
        pagina_cuenta(ctx, nombres, responsables)
    elif pagina == "usuarios" and ctx["admin"]:
        pagina_usuarios(ctx, nombres)
    elif pagina == "bitacora" and ctx["admin"]:
        pagina_bitacora(nombres)
    else:
        st.session_state.pop("pagina", None)
        return False
    return True


def pagina_cuenta(ctx: dict, nombres: dict[str, str], responsables: dict) -> None:
    correo = ctx["correo"]
    registro = A.usuario(correo) or {}
    st.markdown("## Mi cuenta")
    c1, c2 = st.columns(2, gap="large")
    with c1:
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
                    avisar(correo, "Tu acceso al dashboard de créditos" if aprobar else "Tu solicitud de acceso",
                           "Acceso aprobado" if aprobar else "Solicitud no aprobada",
                           [f"Ya puedes ver <b>{unidad_txt}</b> en el dashboard de créditos de mensajería."
                            if aprobar else f"El Equipo CRM no aprobó tu solicitud para <b>{unidad_txt}</b>. "
                                            "Si crees que es un error, escríbeles."])
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
                _entregar_temporal(correo, temporal)

    st.markdown("### Equipo CRM")
    st.markdown("\n".join(f"- {c}" + ("" if c in todos else " (aún no ha creado su cuenta)") for c in admins)
                or "Ninguno")
    st.caption("Esta lista solo se cambia en el archivo acceso.json del repositorio, no desde la app.")


def _entregar_temporal(correo: str, temporal: str) -> None:
    resultado = avisar(correo, "Tu contraseña temporal del dashboard de créditos", "Contraseña temporal",
                       ["El Equipo CRM te dio acceso al dashboard de créditos de mensajería. Entra con tu correo y "
                        "esta contraseña temporal; te pedirá crear una nueva."], temporal)
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
            _entregar_temporal(correo, temporal)
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

