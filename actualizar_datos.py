"""
Actualiza data.xlsx (WhatsApp) y data_correo.xlsx (Correo) con el último reporte que llega por correo.

Busca en el Outlook de escritorio el correo más reciente que cumpla los filtros de
actualizar_datos.json (asunto, remitente, carpeta), toma el adjunto de Excel, revisa que
sea un reporte válido de Marketing Cloud y más nuevo que el actual, y reemplaza data.xlsx
(el anterior queda como data_anterior.xlsx). Si "publicar_en_github" está activo, además
sube el archivo al repositorio para que el dashboard publicado se actualice solo.

Uso (desde la carpeta del repositorio):
    py actualizar_datos.py              Busca y actualiza.
    py actualizar_datos.py --simular    Muestra qué haría, sin cambiar nada.
    py actualizar_datos.py --forzar     Reemplaza aunque el reporte no sea más nuevo.

El reporte de correo se configura en la sección "correo" de actualizar_datos.json (sus propios filtros de
asunto y adjunto; lo que no se escriba se toma de la configuración general). Se activa con "activo": true.

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
RUTA_CORREO = CARPETA / "data_correo.xlsx"
RUTA_CORREO_ANTERIOR = CARPETA / "data_correo_anterior.xlsx"
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
    "correo": {                     # reporte de correos enviados (Marketing Cloud Intelligence)
        "activo": False,
        "asunto_contiene": "",
        "adjunto_contiene": "",
        "mensaje_commit": "Actualiza data_correo.xlsx con el reporte del {fecha}",
    },
}

log = logging.getLogger("actualizar_datos")


def leer_config() -> dict:
    cfg = dict(CONFIG_POR_DEFECTO)
    if RUTA_CONFIG.exists():
        cfg.update(json.loads(RUTA_CONFIG.read_text(encoding="utf-8")))
    return cfg


def config_correo(cfg: dict) -> dict:
    """Filtros del reporte de correo: los propios y, si faltan, los generales."""
    propios = {**CONFIG_POR_DEFECTO["correo"], **(cfg.get("correo") or {})}
    base = {k: v for k, v in cfg.items() if k != "correo"}
    base.update({k: v for k, v in propios.items() if v not in ("", None)})
    return base


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


def fecha_correo(ruta: Path) -> pd.Timestamp | None:
    try:
        _, info = L.leer_reporte_correo(ruta)
    except Exception:
        return None
    g = info.get("generado")
    return None if g is None or pd.isna(g) else pd.Timestamp(g).tz_localize(None)


def revisar_correo(ruta: Path) -> tuple[bool, str, pd.Timestamp | None]:
    """¿Es un reporte de correos enviados que el dashboard puede leer?"""
    try:
        envios, info = L.leer_reporte_correo(ruta)
    except Exception as error:
        return False, f"no es un reporte de correo válido ({error})", None
    if envios.empty:
        return False, "el reporte de correo no trae envíos", None
    g = info.get("generado")
    total = f"{int(envios['envios'].sum()):,}".replace(",", ".")
    return True, f"{len(envios)} filas, {total} correos", (
        None if g is None or pd.isna(g) else pd.Timestamp(g).tz_localize(None))


REPORTES = {
    "whatsapp": {"destino": RUTA_DATOS, "anterior": RUTA_ANTERIOR, "revisar": revisar_archivo, "fecha": fecha_generado},
    "correo": {"destino": RUTA_CORREO, "anterior": RUTA_CORREO_ANTERIOR, "revisar": revisar_correo, "fecha": fecha_correo},
}


def publicar(cfg: dict, fecha_txt: str, archivos: tuple[str, ...] = ("data.xlsx",)) -> None:
    """git add + commit + push de los reportes, en la carpeta del repositorio."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=CARPETA, capture_output=True, text=True)
    if git("rev-parse", "--is-inside-work-tree").returncode != 0:
        raise RuntimeError("La carpeta no es un repositorio de git; no se puede publicar.")
    git("add", *archivos)
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


def actualizar(nombre: str, cfg: dict, args) -> tuple[int, str | None]:
    """Busca el último reporte de un canal en Outlook y, si es válido y más nuevo, reemplaza el archivo.
    Devuelve (código, fecha del reporte nuevo o None si no cambió)."""
    r = REPORTES[nombre]
    destino = r["destino"]
    try:
        bandeja = carpeta_outlook(cfg)
        items = bandeja.Items
        items.Sort("[ReceivedTime]", True)
        lista = candidatos(items, cfg, datetime.now())
    except Exception as error:
        log.error("[%s] No se pudo leer el correo: %s", nombre, error)
        return 1, None
    if not lista:
        log.info("[%s] No hay correos con el reporte en los últimos %s días.", nombre, cfg["dias_a_revisar"])
        return 0, None
    actual = r["fecha"](destino)
    with tempfile.TemporaryDirectory() as tmp:
        for recibido, correo in lista:
            for adjunto in adjuntos_excel(correo, cfg):
                ruta_tmp = Path(tmp) / "nuevo.xlsx"
                adjunto.SaveAsFile(str(ruta_tmp))
                valido, detalle, generado = r["revisar"](ruta_tmp)
                origen = f"«{correo.Subject}» del {recibido:%d/%m/%Y %H:%M} ({adjunto.FileName})"
                if not valido:
                    log.warning("[%s] Se omite %s: %s.", nombre, origen, detalle)
                    continue
                if huella(ruta_tmp) == huella(destino):
                    log.info("[%s] %s ya es el reporte más reciente (%s).", nombre, destino.name, origen)
                    return 0, None
                if not args.forzar and actual is not None and generado is not None and generado <= actual:
                    log.info("[%s] El reporte del correo (%s) no es más nuevo que el actual (%s).", nombre, generado, actual)
                    return 0, None
                if args.simular:
                    log.info("[%s] SIMULACIÓN: se reemplazaría %s con %s, %s.", nombre, destino.name, origen, detalle)
                    return 0, None
                if destino.exists():
                    shutil.copy2(destino, r["anterior"])
                shutil.copy2(ruta_tmp, destino)
                log.info("[%s] %s actualizado con %s, %s.", nombre, destino.name, origen, detalle)
                return 0, f"{(generado or recibido):%d/%m/%Y}"
    log.warning("[%s] Ningún adjunto de los correos encontrados es un reporte válido.", nombre)
    return 1, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Actualiza los reportes con el último recibido por correo.")
    parser.add_argument("--simular", action="store_true", help="Muestra qué haría, sin cambiar nada.")
    parser.add_argument("--forzar", action="store_true", help="Reemplaza aunque el reporte no sea más nuevo.")
    parser.add_argument("--solo", choices=list(REPORTES), help="Actualiza solo ese canal.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
                        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(RUTA_LOG, encoding="utf-8")])
    cfg = leer_config()
    trabajos = []
    if args.solo in (None, "whatsapp"):
        if cfg["asunto_contiene"] or cfg["remitente_contiene"] or cfg["adjunto_contiene"]:
            trabajos.append(("whatsapp", cfg))
        else:
            log.error("Configura al menos un filtro (asunto, remitente o adjunto) en actualizar_datos.json.")
            return 2
    cfg_c = config_correo(cfg)
    if args.solo in (None, "correo") and (cfg.get("correo") or {}).get("activo"):
        trabajos.append(("correo", cfg_c))
    codigo, publicados, fechas = 0, [], []
    for nombre, cfg_r in trabajos:
        c, fecha = actualizar(nombre, cfg_r, args)
        codigo = max(codigo, c)
        if fecha:
            publicados.append(REPORTES[nombre]["destino"].name)
            fechas.append(fecha)
    if publicados and cfg["publicar_en_github"]:
        try:
            publicar(cfg, " y ".join(sorted(set(fechas))), tuple(publicados))
            log.info("%s publicado en GitHub: el dashboard se actualiza en unos minutos.", ", ".join(publicados))
        except Exception as error:
            log.error("Se actualizó en esta carpeta, pero no se pudo publicar: %s", error)
            return 1
    return codigo


if __name__ == "__main__":
    sys.exit(main())
