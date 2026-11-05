"""
Cuentas, roles y seguridad del dashboard (sin pantallas; las pantallas están en sesion.py).

Roles:
- Equipo CRM (administrador): solo los correos de acceso.json -> "equipo_crm". Nadie puede darse este rol
  desde la app; se cambia en el código.
- Usuario de unidad: ve solo las unidades que tiene aprobadas (puede tener varias y cambiar entre ellas).
- Pendiente: creó su cuenta pero aún no tiene ninguna unidad aprobada.

Archivos:
- acceso.json (en el repositorio): dominio permitido y lista del Equipo CRM.
- usuarios.json y bitacora.json: se guardan con almacen.py (en local o en GitHub). Las contraseñas se
  guardan con bcrypt (nunca en texto plano) y los códigos de verificación solo existen en memoria.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt

import almacen

CARPETA = Path(__file__).parent
RUTA_ACCESO = CARPETA / "acceso.json"
ARCHIVO_USUARIOS = "usuarios.json"
ARCHIVO_BITACORA = "bitacora.json"
ARCHIVO_PERFILES = "perfiles.json"      # foto de perfil y personalización del tablero, por persona
RUTA_CLAVE_LOCAL = CARPETA / ".streamlit" / "clave_sesion.txt"

DIAS_RECORDAR = 30
MIN_CLAVE = 10
MAX_CLAVE_BYTES = 72          # límite de bcrypt
CODIGO_MINUTOS = 15
CODIGO_INTENTOS = 5
REENVIO_SEGUNDOS = 60
ENVIOS_POR_HORA = 5
FALLOS_BLOQUEO = 5
BLOQUEO_MINUTOS = 15
DIAS_INACTIVO = 90
MAX_EVENTOS = 3000
CACHE_SEGUNDOS = 20

USUARIOS_VACIO = {"usuarios": {}}
PERFILES_VACIO = {"perfiles": {}}
BITACORA_VACIA = {"eventos": []}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def ahora() -> datetime:
    return datetime.now(timezone.utc)


def iso(momento: datetime | None = None) -> str:
    return (momento or ahora()).strftime("%Y-%m-%dT%H:%M:%SZ")


def desde_iso(texto: str | None) -> datetime | None:
    if not texto:
        return None
    try:
        return datetime.strptime(texto, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def normalizar(correo: str) -> str:
    return str(correo or "").strip().lower()


def leer_acceso() -> dict:
    try:
        datos = json.loads(RUTA_ACCESO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        datos = {}
    dominios = datos.get("dominios") or [datos.get("dominio") or "javeriana.edu.co"]
    return {"dominios": [d.lower().lstrip("@") for d in dominios],
            "equipo_crm": sorted({normalizar(c) for c in datos.get("equipo_crm", []) if normalizar(c)})}


def es_admin(correo: str) -> bool:
    return normalizar(correo) in leer_acceso()["equipo_crm"]


def correo_valido(correo: str) -> str | None:
    """None si el correo sirve; si no, el motivo."""
    correo = normalizar(correo)
    if not re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", correo):
        return "Escribe un correo válido."
    dominios = leer_acceso()["dominios"]
    if correo.split("@", 1)[1] not in dominios:
        return "Solo se pueden crear cuentas con correo " + " o ".join(f"@{d}" for d in dominios) + "."
    return None


def clave_valida(clave: str, correo: str) -> str | None:
    if len(clave) < MIN_CLAVE:
        return f"La contraseña debe tener al menos {MIN_CLAVE} caracteres."
    if len(clave.encode("utf-8")) > MAX_CLAVE_BYTES:
        return "La contraseña es demasiado larga (máximo 72 caracteres sin tildes)."
    usuario = normalizar(correo).split("@")[0]
    if normalizar(clave) == normalizar(correo) or (len(usuario) >= 4 and usuario in clave.lower()):
        return "La contraseña no puede contener tu correo."
    if clave.isdigit() or len(set(clave)) < 4:
        return "Usa una contraseña menos predecible (combina letras, números o una frase)."
    return None


def cifrar(clave: str) -> str:
    return bcrypt.hashpw(clave.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def coincide(clave: str, cifrada: str | None) -> bool:
    if not cifrada:
        return False
    try:
        return bcrypt.checkpw(clave.encode("utf-8"), cifrada.encode("ascii"))
    except ValueError:
        return False


# Hash que se usa cuando el correo no existe, para que la respuesta tarde lo mismo (no delata qué correos hay)
_HASH_FALSO = cifrar(secrets.token_urlsafe(16))


def clave_temporal() -> str:
    """Contraseña temporal legible (sin caracteres que se confundan)."""
    letras = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "-".join("".join(secrets.choice(letras) for _ in range(4)) for _ in range(3))


# ---------------------------------------------------------------------------
# Memoria compartida entre sesiones (códigos, intentos fallidos, caché de archivos)
# ---------------------------------------------------------------------------

def _memoria() -> dict:
    try:
        import streamlit as st

        @st.cache_resource(show_spinner=False)
        def _compartida() -> dict:
            return {"codigos": {}, "fallos": {}, "cache": {}, "clave": None}

        return _compartida()
    except Exception:  # fuera de Streamlit (pruebas)
        global _MEMORIA_LOCAL
        try:
            return _MEMORIA_LOCAL
        except NameError:
            _MEMORIA_LOCAL = {"codigos": {}, "fallos": {}, "cache": {}, "clave": None}
            return _MEMORIA_LOCAL


def clave_sesion() -> bytes:
    """Clave con la que se firman las cookies de "recordarme". Viene de los Secrets ([acceso] clave_sesion);
    en local, si no está, se crea una y se guarda en .streamlit/clave_sesion.txt (no se sube al repositorio)."""
    try:
        import streamlit as st
        valor = st.secrets.get("acceso", {}).get("clave_sesion")
    except Exception:
        valor = None
    if valor:
        return str(valor).encode("utf-8")
    mem = _memoria()
    if mem["clave"]:
        return mem["clave"]
    try:
        if RUTA_CLAVE_LOCAL.exists():
            mem["clave"] = RUTA_CLAVE_LOCAL.read_text(encoding="utf-8").strip().encode("utf-8")
        else:
            RUTA_CLAVE_LOCAL.parent.mkdir(exist_ok=True)
            nueva = secrets.token_urlsafe(48)
            RUTA_CLAVE_LOCAL.write_text(nueva, encoding="utf-8")
            mem["clave"] = nueva.encode("utf-8")
    except OSError:
        mem["clave"] = secrets.token_urlsafe(48).encode("utf-8")
    return mem["clave"]


def tiene_clave_sesion_fija() -> bool:
    try:
        import streamlit as st
        return bool(st.secrets.get("acceso", {}).get("clave_sesion"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Usuarios y bitácora (archivos)
# ---------------------------------------------------------------------------

def _leer_con_cache(nombre: str, vacio: dict) -> dict:
    cache = _memoria()["cache"]
    guardado = cache.get(nombre)
    if guardado and time.time() - guardado[0] < CACHE_SEGUNDOS:
        return json.loads(json.dumps(guardado[1]))
    datos = almacen.leer(nombre, vacio)
    cache[nombre] = (time.time(), datos)
    return json.loads(json.dumps(datos))


def _guardar(nombre: str, cambio, vacio: dict, mensaje: str) -> dict:
    nuevo = almacen.actualizar(nombre, cambio, vacio, mensaje)
    _memoria()["cache"][nombre] = (time.time(), nuevo)
    return json.loads(json.dumps(nuevo))


def usuarios(fresco: bool = False) -> dict[str, dict]:
    if fresco:
        _memoria()["cache"].pop(ARCHIVO_USUARIOS, None)
    return _leer_con_cache(ARCHIVO_USUARIOS, USUARIOS_VACIO).get("usuarios", {})


def usuario(correo: str, fresco: bool = False) -> dict | None:
    return usuarios(fresco).get(normalizar(correo))


def modificar_usuario(correo: str, cambio, mensaje: str) -> dict | None:
    """Aplica `cambio(registro)` al usuario y guarda. Devuelve el registro guardado."""
    correo = normalizar(correo)

    def aplicar(datos: dict) -> dict:
        registro = datos.setdefault("usuarios", {}).get(correo)
        if registro is None:
            return datos
        cambio(registro)
        return datos

    return _guardar(ARCHIVO_USUARIOS, aplicar, USUARIOS_VACIO, mensaje).get("usuarios", {}).get(correo)


def registrar(evento: str, quien: str, detalle: str = "", sobre: str = "") -> None:
    """Agrega una línea a la bitácora. Nunca se escriben contraseñas ni códigos."""
    linea = {"fecha": iso(), "quien": normalizar(quien) or quien, "evento": evento, "sobre": normalizar(sobre),
             "detalle": detalle}

    def aplicar(datos: dict) -> dict:
        eventos = datos.setdefault("eventos", [])
        eventos.append(linea)
        datos["eventos"] = eventos[-MAX_EVENTOS:]
        return datos

    try:
        _guardar(ARCHIVO_BITACORA, aplicar, BITACORA_VACIA, f"Bitácora: {evento}")
    except Exception:
        pass   # la bitácora nunca debe impedir que la app funcione


def bitacora() -> list[dict]:
    return _leer_con_cache(ARCHIVO_BITACORA, BITACORA_VACIA).get("eventos", [])


def perfil(correo: str) -> dict:
    """Foto (avatar, data URI) y preferencias del tablero de una persona."""
    return _leer_con_cache(ARCHIVO_PERFILES, PERFILES_VACIO).get("perfiles", {}).get(normalizar(correo) or correo, {})


def guardar_perfil(correo: str, cambio, mensaje: str) -> dict:
    """Aplica `cambio(perfil)` y guarda. Devuelve el perfil guardado."""
    clave = normalizar(correo) or correo

    def aplicar(datos: dict) -> dict:
        cambio(datos.setdefault("perfiles", {}).setdefault(clave, {}))
        return datos

    return _guardar(ARCHIVO_PERFILES, aplicar, PERFILES_VACIO, mensaje).get("perfiles", {}).get(clave, {})


def crear_usuario(correo: str, nombre: str, clave: str, unidad: str | None, responsables: dict) -> dict:
    """Crea la cuenta. Si el correo es responsable de la unidad elegida, la unidad queda aprobada;
    si no, queda como solicitud pendiente. Devuelve el registro."""
    correo = normalizar(correo)
    registro = {"nombre": nombre.strip(), "clave": cifrar(clave), "estado": "activo", "unidades": [],
                "solicitudes": [], "creado": iso(), "ultimo_ingreso": None, "version": 1,
                "cambiar_clave": False}
    if unidad and not es_admin(correo):
        if es_responsable(correo, unidad, responsables):
            registro["unidades"] = [unidad]
        else:
            registro["solicitudes"] = [{"unidad": unidad, "fecha": iso()}]

    def aplicar(datos: dict) -> dict:
        lista = datos.setdefault("usuarios", {})
        if correo in lista:
            raise ValueError("Ya existe una cuenta con ese correo.")
        lista[correo] = registro
        return datos

    _guardar(ARCHIVO_USUARIOS, aplicar, USUARIOS_VACIO, "Nueva cuenta")
    return registro


def es_responsable(correo: str, unidad: str, responsables: dict) -> bool:
    return normalizar(correo) in {normalizar(c) for c in (responsables.get(unidad) or [])}


def pedir_unidad(correo: str, unidad: str, responsables: dict) -> str:
    """El usuario pide otra unidad. Devuelve "aprobada" o "pendiente"."""
    auto = es_responsable(correo, unidad, responsables)

    def cambio(r: dict) -> None:
        if auto:
            if unidad not in r["unidades"]:
                r["unidades"].append(unidad)
            r["solicitudes"] = [s for s in r.get("solicitudes", []) if s["unidad"] != unidad]
        elif unidad not in r["unidades"] and all(s["unidad"] != unidad for s in r.get("solicitudes", [])):
            r.setdefault("solicitudes", []).append({"unidad": unidad, "fecha": iso()})

    modificar_usuario(correo, cambio, "Solicitud de unidad")
    return "aprobada" if auto else "pendiente"


def resolver_solicitud(correo: str, unidad: str, aprobar: bool) -> None:
    def cambio(r: dict) -> None:
        r["solicitudes"] = [s for s in r.get("solicitudes", []) if s["unidad"] != unidad]
        if aprobar and unidad not in r["unidades"]:
            r["unidades"].append(unidad)
        if not aprobar:
            r.setdefault("rechazadas", []).append({"unidad": unidad, "fecha": iso()})

    modificar_usuario(correo, cambio, "Aprueba solicitud" if aprobar else "Rechaza solicitud")


def unidades_permitidas(correo: str, todas: list[str]) -> list[str]:
    """Unidades que puede ver (en el orden de config.json). Equipo CRM: todas."""
    if es_admin(correo):
        return list(todas)
    r = usuario(correo) or {}
    return [u for u in todas if u in r.get("unidades", [])]


def solicitudes_pendientes() -> list[tuple[str, dict, dict]]:
    """(correo, usuario, solicitud) de todas las solicitudes sin resolver, de la más antigua a la más nueva."""
    salida = [(c, r, s) for c, r in usuarios().items() if r.get("estado") == "activo"
              for s in r.get("solicitudes", [])]
    return sorted(salida, key=lambda x: x[2].get("fecha", ""))


def inactivo(r: dict) -> bool:
    ultimo = desde_iso(r.get("ultimo_ingreso")) or desde_iso(r.get("creado"))
    return bool(ultimo and ahora() - ultimo > timedelta(days=DIAS_INACTIVO))


# ---------------------------------------------------------------------------
# Inicio de sesión e intentos fallidos
# ---------------------------------------------------------------------------

def bloqueado_hasta(correo: str) -> datetime | None:
    fallos = [t for t in _memoria()["fallos"].get(normalizar(correo), []) if time.time() - t < BLOQUEO_MINUTOS * 60]
    _memoria()["fallos"][normalizar(correo)] = fallos
    if len(fallos) >= FALLOS_BLOQUEO:
        return datetime.fromtimestamp(fallos[-1] + BLOQUEO_MINUTOS * 60, tz=timezone.utc)
    return None


def iniciar_sesion(correo: str, clave: str) -> tuple[dict | None, str | None]:
    """(usuario, None) si entra; (None, mensaje) si no."""
    correo = normalizar(correo)
    hasta = bloqueado_hasta(correo)
    if hasta:
        minutos = max(1, int((hasta - ahora()).total_seconds() // 60) + 1)
        return None, (f"Hubo demasiados intentos fallidos. Por seguridad, espera {minutos} "
                      f"{'minuto' if minutos == 1 else 'minutos'} o recupera tu contraseña.")
    r = usuario(correo, fresco=True)
    if not coincide(clave, r.get("clave") if r else _HASH_FALSO):
        fallos = _memoria()["fallos"].setdefault(correo, [])
        fallos.append(time.time())
        if len(fallos) >= FALLOS_BLOQUEO:
            registrar("Cuenta bloqueada 15 minutos por intentos fallidos", "sistema", sobre=correo)
        return None, "Correo o contraseña incorrectos."
    if r.get("estado") != "activo":
        return None, "Tu cuenta está desactivada. Escríbele al Equipo CRM si necesitas acceso."
    _memoria()["fallos"].pop(correo, None)
    return r, None


def marcar_ingreso(correo: str) -> None:
    def cambio(r: dict) -> None:
        r["ultimo_ingreso"] = iso()
    try:
        modificar_usuario(correo, cambio, "Ingreso")
    except Exception:
        pass


def cambiar_clave(correo: str, nueva: str, *, temporal: bool = False) -> dict | None:
    """Guarda la nueva contraseña y sube la versión: las sesiones recordadas en otros equipos se cierran."""
    def cambio(r: dict) -> None:
        r["clave"] = cifrar(nueva)
        r["version"] = int(r.get("version", 1)) + 1
        r["cambiar_clave"] = temporal
    return modificar_usuario(correo, cambio, "Cambio de contraseña")


# ---------------------------------------------------------------------------
# Cookie de "recordarme"
# ---------------------------------------------------------------------------

def _firma(texto: str) -> str:
    return hmac.new(clave_sesion(), texto.encode("utf-8"), hashlib.sha256).hexdigest()


def crear_token(correo: str, version: int, dias: int = DIAS_RECORDAR) -> str:
    vence = int(time.time() + dias * 86400)
    cuerpo = base64.urlsafe_b64encode(f"{normalizar(correo)}|{version}|{vence}".encode("utf-8")).decode("ascii")
    return f"{cuerpo}.{_firma(cuerpo)}"


def leer_token(token: str | None) -> str | None:
    """Correo del token si la firma es válida, no ha vencido y la cuenta sigue activa con esa versión."""
    if not token or "." not in token:
        return None
    cuerpo, firma = token.rsplit(".", 1)
    if not hmac.compare_digest(firma, _firma(cuerpo)):
        return None
    try:
        correo, version, vence = base64.urlsafe_b64decode(cuerpo.encode("ascii")).decode("utf-8").split("|")
    except (ValueError, UnicodeDecodeError):
        return None
    if int(vence) < time.time():
        return None
    r = usuario(correo)
    if not r or r.get("estado") != "activo" or int(r.get("version", 1)) != int(version):
        return None
    return correo


# ---------------------------------------------------------------------------
# Códigos de verificación (solo en memoria; se guarda su huella, no el código)
# ---------------------------------------------------------------------------

def _huella(codigo: str) -> str:
    return _firma("codigo:" + codigo)


def puede_enviar(correo: str, proposito: str) -> str | None:
    """None si se puede enviar un código; si no, el motivo."""
    reg = _memoria()["codigos"].get((normalizar(correo), proposito), {})
    envios = [t for t in reg.get("envios", []) if time.time() - t < 3600]
    if envios and time.time() - envios[-1] < REENVIO_SEGUNDOS:
        return f"Espera {int(REENVIO_SEGUNDOS - (time.time() - envios[-1])) + 1} segundos para pedir otro código."
    if len(envios) >= ENVIOS_POR_HORA:
        return "Ya se enviaron varios códigos a este correo. Intenta de nuevo en una hora."
    return None


def nuevo_codigo(correo: str, proposito: str) -> str:
    clave = (normalizar(correo), proposito)
    reg = _memoria()["codigos"].get(clave, {})
    codigo = f"{secrets.randbelow(10 ** 6):06d}"
    _memoria()["codigos"][clave] = {
        "huella": _huella(codigo), "vence": time.time() + CODIGO_MINUTOS * 60, "intentos": 0,
        "envios": [t for t in reg.get("envios", []) if time.time() - t < 3600] + [time.time()]}
    return codigo


def anular_codigo(correo: str, proposito: str) -> None:
    """El correo no salió: el código queda inservible (nadie lo recibió)."""
    reg = _memoria()["codigos"].get((normalizar(correo), proposito))
    if reg:
        reg["huella"] = None


def verificar_codigo(correo: str, proposito: str, codigo: str) -> str | None:
    """None si el código es correcto (y lo gasta); si no, el motivo."""
    clave = (normalizar(correo), proposito)
    reg = _memoria()["codigos"].get(clave)
    if not reg or not reg.get("huella"):
        return "Pide un código primero."
    if time.time() > reg["vence"]:
        reg["huella"] = None
        return "El código venció. Pide uno nuevo."
    if reg["intentos"] >= CODIGO_INTENTOS:
        reg["huella"] = None
        return "Demasiados intentos con este código. Pide uno nuevo."
    reg["intentos"] += 1
    if not hmac.compare_digest(reg["huella"], _huella(re.sub(r"\D", "", str(codigo)))):
        restan = CODIGO_INTENTOS - reg["intentos"]
        return f"Código incorrecto. Te quedan {restan} {'intento' if restan == 1 else 'intentos'}."
    reg["huella"] = None
    return None
