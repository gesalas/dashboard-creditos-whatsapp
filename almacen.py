"""
Dónde se guardan los archivos que la app modifica (usuarios, bitácora, config.json, alertas.json).

- En local, o si no hay token de GitHub: en la carpeta del proyecto.
- En el enlace publicado (Streamlit Cloud), con un token de GitHub en los Secrets: directamente en el
  repositorio, porque Streamlit Cloud borra los archivos modificados cada vez que la app se reinicia.
  Los usuarios y la bitácora van a una rama aparte ("datos-acceso" por defecto) para que guardar un
  usuario no vuelva a publicar la app; config.json y alertas.json van a la rama que usa la app.

Secrets (Settings > Secrets en Streamlit Cloud, o .streamlit/secrets.toml en local):

    [github]
    token = "github_pat_..."                       # token de grano fino: solo este repositorio, Contents: read/write
    repositorio = "gesalas/dashboard-creditos-whatsapp"
    rama_app = "main"                              # rama que publica la app
    rama_datos = "datos-acceso"                    # rama para usuarios y bitácora (se crea sola)
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Callable

import requests

CARPETA = Path(__file__).parent
API = "https://api.github.com"
FORZAR_LOCAL = False   # modo pruebas: todo se guarda en la carpeta local aunque haya token
_VENCE = {"valor": None, "consultado": False}   # vencimiento del token (lo informa GitHub en cada respuesta)


class ErrorAlmacen(RuntimeError):
    pass


def _secretos() -> dict:
    try:
        import streamlit as st
        return dict(st.secrets.get("github", {}))
    except Exception:
        return {}


def usa_github() -> bool:
    if FORZAR_LOCAL:
        return False
    s = _secretos()
    return bool(s.get("token") and s.get("repositorio"))


def _cabeceras() -> dict:
    return {"Authorization": f"Bearer {_secretos()['token']}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def _rama(datos: bool) -> str:
    s = _secretos()
    return s.get("rama_datos", "datos-acceso") if datos else s.get("rama_app", "main")


def _asegurar_rama(rama: str) -> None:
    """Crea la rama de datos a partir de la rama de la app si todavía no existe."""
    s = _secretos()
    r = requests.get(f"{API}/repos/{s['repositorio']}/git/ref/heads/{rama}", headers=_cabeceras(), timeout=20)
    if r.status_code == 200:
        return
    base = requests.get(f"{API}/repos/{s['repositorio']}/git/ref/heads/{_rama(False)}", headers=_cabeceras(),
                        timeout=20)
    if base.status_code != 200:
        raise ErrorAlmacen(f"No se pudo leer la rama {_rama(False)} en GitHub ({base.status_code}).")
    r = requests.post(f"{API}/repos/{s['repositorio']}/git/refs", headers=_cabeceras(), timeout=20,
                      json={"ref": f"refs/heads/{rama}", "sha": base.json()["object"]["sha"]})
    if r.status_code not in (200, 201, 422):   # 422: ya existe (otra sesión la creó al tiempo)
        raise ErrorAlmacen(f"No se pudo crear la rama {rama} en GitHub ({r.status_code}).")


def _leer_github(nombre: str, datos: bool) -> tuple[dict | None, str | None]:
    s = _secretos()
    rama = _rama(datos)
    r = requests.get(f"{API}/repos/{s['repositorio']}/contents/{nombre}", headers=_cabeceras(),
                     params={"ref": rama}, timeout=20)
    _anotar_vencimiento(r)
    if r.status_code == 401:
        raise ErrorAlmacen("GitHub rechazó el token (¿venció o se revocó?). El dueño del repositorio debe crear uno "
                           "nuevo y ponerlo en los Secrets.")
    if r.status_code == 404:
        return None, None
    if r.status_code != 200:
        raise ErrorAlmacen(f"GitHub respondió {r.status_code} al leer {nombre}.")
    cuerpo = r.json()
    return json.loads(base64.b64decode(cuerpo["content"]).decode("utf-8")), cuerpo["sha"]


def _escribir_github(nombre: str, contenido: dict, sha: str | None, mensaje: str, datos: bool) -> bool:
    """True si se guardó; False si el archivo cambió mientras tanto (hay que releer y reintentar)."""
    s = _secretos()
    rama = _rama(datos)
    if datos:
        _asegurar_rama(rama)
    cuerpo = {"message": mensaje, "branch": rama,
              "content": base64.b64encode(_serializar(contenido).encode("utf-8")).decode("ascii")}
    if sha:
        cuerpo["sha"] = sha
    r = requests.put(f"{API}/repos/{s['repositorio']}/contents/{nombre}", headers=_cabeceras(), json=cuerpo,
                     timeout=30)
    if r.status_code in (200, 201):
        return True
    if r.status_code in (409, 422):
        return False
    raise ErrorAlmacen(f"GitHub respondió {r.status_code} al guardar {nombre}: {r.text[:200]}")


def _serializar(contenido: dict) -> str:
    return json.dumps(contenido, ensure_ascii=False, indent=2) + "\n"


def leer(nombre: str, por_defecto: dict, *, datos: bool = True, local: Path | None = None) -> dict:
    """Lee un archivo JSON (de GitHub si está configurado; si no, de la carpeta local)."""
    if usa_github():
        contenido, _ = _leer_github(nombre, datos)
        return contenido if contenido is not None else json.loads(json.dumps(por_defecto))
    ruta = local or CARPETA / nombre
    if not ruta.exists():
        return json.loads(json.dumps(por_defecto))
    return json.loads(ruta.read_text(encoding="utf-8"))


def actualizar(nombre: str, cambio: Callable[[dict], dict | None], por_defecto: dict, mensaje: str, *,
               datos: bool = True, local: Path | None = None, intentos: int = 4) -> dict:
    """Lee, aplica `cambio` y guarda. Si otra sesión guardó mientras tanto, vuelve a leer y reintenta,
    así dos registros al mismo tiempo no se pisan. Devuelve el contenido guardado."""
    if usa_github():
        for _ in range(intentos):
            contenido, sha = _leer_github(nombre, datos)
            contenido = contenido if contenido is not None else json.loads(json.dumps(por_defecto))
            nuevo = cambio(contenido)
            nuevo = contenido if nuevo is None else nuevo
            if _escribir_github(nombre, nuevo, sha, mensaje, datos):
                return nuevo
            time.sleep(0.6)
        raise ErrorAlmacen(f"No se pudo guardar {nombre}: el archivo cambió varias veces seguidas.")
    ruta = local or CARPETA / nombre
    contenido = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else json.loads(json.dumps(por_defecto))
    nuevo = cambio(contenido)
    nuevo = contenido if nuevo is None else nuevo
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(_serializar(nuevo), encoding="utf-8")
    temporal.replace(ruta)
    return nuevo


def subir_archivo(ruta: Path, mensaje: str) -> None:
    """Sube a la rama de la app un archivo que la app ya guardó en local (config.json, alertas.json).
    Sin GitHub configurado no hace nada (en local el archivo ya quedó guardado)."""
    if not usa_github():
        return
    nombre = ruta.name
    for _ in range(4):
        _, sha = _leer_github(nombre, datos=False)
        s = _secretos()
        cuerpo = {"message": mensaje, "branch": _rama(False),
                  "content": base64.b64encode(ruta.read_text(encoding="utf-8").encode("utf-8")).decode("ascii")}
        if sha:
            cuerpo["sha"] = sha
        r = requests.put(f"{API}/repos/{s['repositorio']}/contents/{nombre}", headers=_cabeceras(), json=cuerpo,
                         timeout=30)
        if r.status_code in (200, 201):
            return
        if r.status_code not in (409, 422):
            raise ErrorAlmacen(f"GitHub respondió {r.status_code} al subir {nombre}.")
        time.sleep(0.6)
    raise ErrorAlmacen(f"No se pudo subir {nombre} a GitHub.")



def _anotar_vencimiento(respuesta) -> None:
    v = respuesta.headers.get("github-authentication-token-expiration")
    if v:
        _VENCE["valor"] = v


def vencimiento_token():
    """Fecha en que vence el token de GitHub (los tokens de grano fino vencen), o None si no se sabe o no vence."""
    if not usa_github():
        return None
    if _VENCE["valor"] is None and not _VENCE["consultado"]:
        _VENCE["consultado"] = True
        try:
            _anotar_vencimiento(requests.get(f"{API}/rate_limit", headers=_cabeceras(), timeout=15))
        except Exception:
            return None
    if not _VENCE["valor"]:
        return None
    try:
        import pandas as pd
        return pd.Timestamp(_VENCE["valor"]).tz_convert(None) if pd.Timestamp(_VENCE["valor"]).tzinfo else pd.Timestamp(_VENCE["valor"])
    except Exception:
        return None
