"""
Actualiza data.xlsx con el último reporte que llega por correo.

Busca en el Outlook de escritorio el correo más reciente que cumpla los filtros de
actualizar_datos.json (asunto, remitente, carpeta), toma el adjunto de Excel, revisa que
sea un reporte válido de Marketing Cloud y más nuevo que el actual, y reemplaza data.xlsx
(el anterior queda como data_anterior.xlsx). Si "publicar_en_github" está activo, además
sube el archivo al repositorio para que el dashboard publicado se actualice solo.

Uso (desde la carpeta del repositorio):
    py actualizar_datos.py              Busca y actualiza.
    py actualizar_datos.py --simular    Muestra qué haría, sin cambiar nada.
    py actualizar_datos.py --forzar     Reemplaza aunque el reporte no sea más nuevo.

Para que corra solo cada día: ejecutar_actualizacion.bat en el Programador de tareas de
Windows (ver README).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

import logica as L

CARPETA = Path(__file__).parent
RUTA_DATOS = CARPETA / "data.xlsx"
RUTA_ANTERIOR = CARPETA / "data_anterior.xlsx"
RUTA_CONFIG = CARPETA / "actualizar_datos.json"
RUTA_LOG = CARPETA / "actualizar_datos.log"

CONFIG_POR_DEFECTO = {
    "buzon": "",                    # cuenta de Outlook (correo); vacío = la cuenta principal
    "carpeta": "",                  # subcarpeta de la bandeja de entrada (p. ej. "Reportes/WhatsApp"); vacío = bandeja
    "asunto_contiene": "",          # texto que debe tener el asunto (sin distinguir mayúsculas)
    "remitente_contiene": "",       # texto que debe tener el correo o nombre del remitente
    "adjunto_contiene": "",         # texto que debe tener el nombre del adjunto
    "dias_a_revisar": 7,            # solo se miran correos de los últimos N días
    "publicar_en_github": False,    # si es true, hace commit y push de data.xlsx
    "mensaje_commit": "Actualiza data.xlsx con el reporte del {fecha}",
}

log = logging.getLogger("actualizar_datos")


def leer_config() -> dict:
    cfg = dict(CONFIG_POR_DEFECTO)
    if RUTA_CONFIG.exists():
        cfg.update(json.loads(RUTA_CONFIG.read_text(encoding="utf-8")))
    return cfg


def contiene(texto, buscado: str) -> bool:
    return not buscado or buscado.lower() in str(texto or "").lower()


def remitente(correo) -> str:
    """Correo y nombre del remitente (en Exchange, SenderEmailAddress puede venir en formato interno)."""
    partes = [getattr(correo, "SenderName", ""), getattr(correo, "SenderEmailAddress", "")]
    try:
        partes.append(correo.Sender.GetExchangeUser().PrimarySmtpAddress)
    except Exception:
        pass
    return " ".join(str(p or "") for p in partes)


def adjuntos_excel(correo, cfg: dict) -> list:
    encontrados = []
    for i in range(1, int(correo.Attachments.Count) + 1):
        adjunto = correo.Attachments.Item(i)
        nombre = str(adjunto.FileName or "")
        if nombre.lower().endswith((".xlsx", ".xls")) and contiene(nombre, cfg["adjunto_contiene"]):
            encontrados.append(adjunto)
    return encontrados


def candidatos(items, cfg: dict, ahora: datetime) -> list:
    """Correos que cumplen los filtros, del más reciente al más antiguo."""
    limite = ahora - timedelta(days=int(cfg["dias_a_revisar"]))
    lista = []
    for correo in items:
        try:
            recibido = datetime(*tuple(correo.ReceivedTime.timetuple())[:6])
        except Exception:
            continue   # citas, avisos de lectura y otros elementos que no son correos
        if recibido < limite:
            continue
        if not contiene(correo.Subject, cfg["asunto_contiene"]):
            continue
        if not contiene(remitente(correo), cfg["remitente_contiene"]):
            continue
        if correo.Attachments.Count and adjuntos_excel(correo, cfg):
            lista.append((recibido, correo))
    lista.sort(key=lambda x: x[0], reverse=True)
    return lista


def _subcarpetas(carpeta) -> list:
    try:
        return list(carpeta.Folders)
    except Exception:
        return []


def _nombre(carpeta) -> str:
    return str(getattr(carpeta, "Name", "") or "").strip().lower()


def buscar_carpeta(raices: list, ruta: str):
    """Busca una carpeta de Outlook por nombre o ruta ("Reportes_Datorama" o "Reportes/WhatsApp"),
    sin distinguir mayúsculas. Primero dentro de la bandeja de entrada y luego en todo el buzón
    (por ejemplo, una carpeta al mismo nivel que la bandeja de entrada)."""
    partes = [p.strip().lower() for p in str(ruta).replace("\\", "/").split("/") if p.strip()]
    if not partes:
        return None

    def bajar(desde, nombres):
        actual = desde
        for nombre in nombres:
            actual = next((f for f in _subcarpetas(actual) if _nombre(f) == nombre), None)
            if actual is None:
                return None
        return actual

    for raiz in raices:          # ruta exacta desde cada raíz
        encontrada = bajar(raiz, partes)
        if encontrada is not None:
            return encontrada
    # Si no, se busca la primera parte en cualquier nivel (hasta 6 niveles) y desde ahí el resto
    pendientes, vistas = [(r, 0) for r in raices], set()
    while pendientes:
        carpeta, nivel = pendientes.pop(0)
        for sub in _subcarpetas(carpeta):
            marca = id(sub)
            if marca in vistas:
                continue
            vistas.add(marca)
            if _nombre(sub) == partes[0]:
                encontrada = bajar(sub, partes[1:]) if len(partes) > 1 else sub
                if encontrada is not None:
                    return encontrada
            if nivel < 6:
                pendientes.append((sub, nivel + 1))
    return None


def carpeta_outlook(cfg: dict):
    try:
        import win32com.client  # pywin32, solo Windows
    except ImportError:
        raise RuntimeError("Falta el paquete pywin32. Instálalo con: py -m pip install pywin32") from None
    sesion = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    if cfg["buzon"]:
        cuenta = next((c for c in sesion.Folders if cfg["buzon"].lower() in str(c.Name).lower()), None)
        if cuenta is None:
            raise RuntimeError(f"No se encontró la cuenta o buzón «{cfg['buzon']}» en Outlook.")
        bandeja = next((f for f in _subcarpetas(cuenta) if _nombre(f) in ("bandeja de entrada", "inbox")), None)
        raiz = cuenta
    else:
        bandeja = sesion.GetDefaultFolder(6)   # 6 = bandeja de entrada
        raiz = bandeja.Parent
    if not str(cfg.get("carpeta") or "").strip():
        if bandeja is None:
            raise RuntimeError("No se encontró la bandeja de entrada.")
        return bandeja
    raices = [c for c in (bandeja, raiz) if c is not None]
    carpeta = buscar_carpeta(raices, cfg["carpeta"])
    if carpeta is None:
        raise RuntimeError(f"No se encontró la carpeta «{cfg['carpeta']}» en Outlook (se buscó sin distinguir "
                           "mayúsculas, dentro de la bandeja de entrada y en todo el buzón).")
    log.info("Buscando el reporte en la carpeta «%s».", carpeta.Name)
    return carpeta


def huella(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest() if ruta.exists() else ""


def fecha_generado(ruta: Path) -> pd.Timestamp | None:
    try:
        _, generado = L.leer_reporte(ruta)
    except Exception:
        return None
    f = pd.to_datetime(generado, errors="coerce") if generado else pd.NaT
    return None if pd.isna(f) else f


def revisar_archivo(ruta: Path) -> tuple[bool, str, pd.Timestamp | None]:
    """¿Es un reporte de Marketing Cloud que el dashboard puede leer?"""
    try:
        reporte, generado = L.leer_reporte(ruta)
    except Exception as error:
        return False, f"no es un reporte válido ({error})", None
    if reporte.empty:
        return False, "el reporte no trae filas", None
    f = pd.to_datetime(generado, errors="coerce") if generado else pd.NaT
    return True, f"{len(reporte)} filas", (None if pd.isna(f) else f)


def publicar(cfg: dict, fecha_txt: str) -> None:
    """git add + commit + push de data.xlsx, en la carpeta del repositorio."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=CARPETA, capture_output=True, text=True)
    if git("rev-parse", "--is-inside-work-tree").returncode != 0:
        raise RuntimeError("La carpeta no es un repositorio de git; no se puede publicar.")
    git("add", "data.xlsx")
    commit = git("commit", "-m", cfg["mensaje_commit"].format(fecha=fecha_txt))
    if commit.returncode != 0 and "nothing to commit" not in (commit.stdout + commit.stderr):
        raise RuntimeError(f"git commit falló: {commit.stderr.strip() or commit.stdout.strip()}")
    # Si alguien subió cambios mientras tanto, se traen antes de subir para que el push no se rechace
    traer = git("pull", "--rebase", "--autostash")
    if traer.returncode != 0:
        git("rebase", "--abort")
        raise RuntimeError(f"git pull falló (¿cambios en conflicto?): {traer.stderr.strip()}")
    push = git("push")
    if push.returncode != 0:
        raise RuntimeError(f"git push falló: {push.stderr.strip()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Actualiza data.xlsx con el último reporte recibido por correo.")
    parser.add_argument("--simular", action="store_true", help="Muestra qué haría, sin cambiar nada.")
    parser.add_argument("--forzar", action="store_true", help="Reemplaza aunque el reporte no sea más nuevo.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
                        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(RUTA_LOG, encoding="utf-8")])
    cfg = leer_config()
    if not (cfg["asunto_contiene"] or cfg["remitente_contiene"] or cfg["adjunto_contiene"]):
        log.error("Configura al menos un filtro (asunto, remitente o adjunto) en actualizar_datos.json.")
        return 2
    try:
        bandeja = carpeta_outlook(cfg)
        items = bandeja.Items
        items.Sort("[ReceivedTime]", True)
        lista = candidatos(items, cfg, datetime.now())
    except Exception as error:
        log.error("No se pudo leer el correo: %s", error)
        return 1
    if not lista:
        log.info("No hay correos con el reporte en los últimos %s días.", cfg["dias_a_revisar"])
        return 0

    actual = fecha_generado(RUTA_DATOS)
    with tempfile.TemporaryDirectory() as tmp:
        for recibido, correo in lista:
            for adjunto in adjuntos_excel(correo, cfg):
                ruta_tmp = Path(tmp) / "nuevo.xlsx"
                adjunto.SaveAsFile(str(ruta_tmp))
                valido, detalle, generado = revisar_archivo(ruta_tmp)
                origen = f"«{correo.Subject}» del {recibido:%d/%m/%Y %H:%M} ({adjunto.FileName})"
                if not valido:
                    log.warning("Se omite %s: %s.", origen, detalle)
                    continue
                if huella(ruta_tmp) == huella(RUTA_DATOS):
                    log.info("data.xlsx ya es el reporte más reciente (%s). No hay cambios.", origen)
                    return 0
                if not args.forzar and actual is not None and generado is not None and generado <= actual:
                    log.info("El reporte del correo (%s) no es más nuevo que el actual (%s). No hay cambios.",
                             generado, actual)
                    return 0
                if args.simular:
                    log.info("SIMULACIÓN: se reemplazaría data.xlsx con %s, %s.", origen, detalle)
                    return 0
                if RUTA_DATOS.exists():
                    shutil.copy2(RUTA_DATOS, RUTA_ANTERIOR)
                shutil.copy2(ruta_tmp, RUTA_DATOS)
                log.info("data.xlsx actualizado con %s, %s.", origen, detalle)
                if cfg["publicar_en_github"]:
                    try:
                        publicar(cfg, f"{(generado or recibido):%d/%m/%Y}")
                        log.info("data.xlsx publicado en GitHub: el dashboard se actualiza en unos minutos.")
                    except Exception as error:
                        log.error("Se actualizó data.xlsx en esta carpeta, pero no se pudo publicar: %s", error)
                        return 1
                return 0
    log.warning("Ningún adjunto de los correos encontrados es un reporte válido.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
