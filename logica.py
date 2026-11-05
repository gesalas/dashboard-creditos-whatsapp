"""
Lógica de cálculo del dashboard de créditos de WhatsApp.

Este módulo no depende de Streamlit: carga los archivos, limpia el reporte de
Marketing Cloud, calcula los créditos de cada fila y asigna unidad, línea y tipo de
journey. La interfaz (app.py) solo filtra y muestra.

Archivos de entrada (en la carpeta del repositorio):
    data.xlsx       Reporte de envíos de WhatsApp exportado de Marketing Cloud.
    tarifas/        Una tabla de tarifas por vigencia, nombrada con la fecha en que
                    empieza a regir (AAAA-MM-DD.csv). Cada envío se cobra con la
                    tabla vigente en su fecha de envío.
    tarifas.csv     Respaldo: tabla única que se usa solo si no existe la carpeta tarifas/.
    config.json     Compras de créditos por línea y asignación por unidad.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

LINEAS = {
    "Ambas líneas": None,
    "UCP": "573102190903",
    "Outbound": "573160271386",
}
CLAVE_CONFIG_LINEA = {"Ambas líneas": "general", "UCP": "ucp", "Outbound": "outbound"}

# Unidades. Se configuran en config.json (sección "unidades") desde la pestaña Configuración;
# estos son los valores por defecto si el archivo no la trae. configurar_unidades() actualiza
# estas estructuras en su lugar, así que los demás módulos siempre ven las unidades vigentes.
UNIDADES_POR_DEFECTO = [
    {"clave": "mercadeo", "nombre": "Mercadeo", "codigo": "MERCA", "prefijos": ["MERCA"]},
    {"clave": "egresados", "nombre": "Egresados", "codigo": "EGRES", "prefijos": ["EGRES"]},
    {"clave": "donaciones", "nombre": "Donaciones", "codigo": "DONAC", "prefijos": ["DONAC"]},
]
SIN_UNIDAD = "sin_unidad"             # journeys que no coinciden con ninguna unidad (si no hay unidad por defecto)
UNIDADES: list[str] = []               # claves, en orden
CLAVE_CONFIG_UNIDAD: dict[str, str] = {}   # clave -> código usado en las secciones de créditos de config.json
NOMBRE_UNIDAD: dict[str, str] = {}     # clave -> nombre para mostrar (incluye SIN_UNIDAD)
PREFIJOS_UNIDAD: dict[str, list[str]] = {}
JOURNEYS_ASIGNADOS: dict[str, str] = {}    # nombre exacto del journey -> clave de unidad (asignación manual)
_AJUSTES = {"por_defecto": "mercadeo"}


def unidades_de_config(config: dict) -> list[dict]:
    """Lista de unidades de config.json, completando valores faltantes."""
    unidades = []
    for u in config.get("unidades") or UNIDADES_POR_DEFECTO:
        clave = str(u.get("clave") or "").strip()
        if not clave:
            continue
        unidades.append({"clave": clave, "nombre": str(u.get("nombre") or clave.capitalize()),
                         "codigo": str(u.get("codigo") or clave.upper()),
                         "prefijos": [str(p).strip() for p in (u.get("prefijos") or []) if str(p).strip()]})
    return unidades or [dict(u) for u in UNIDADES_POR_DEFECTO]


def configurar_unidades(config: dict) -> None:
    """Carga en el módulo las unidades, la unidad por defecto y la asignación manual de journeys."""
    unidades = unidades_de_config(config)
    UNIDADES[:] = [u["clave"] for u in unidades]
    CLAVE_CONFIG_UNIDAD.clear()
    CLAVE_CONFIG_UNIDAD.update({u["clave"]: u["codigo"] for u in unidades})
    NOMBRE_UNIDAD.clear()
    NOMBRE_UNIDAD.update({u["clave"]: u["nombre"] for u in unidades})
    NOMBRE_UNIDAD[SIN_UNIDAD] = "Sin unidad"
    PREFIJOS_UNIDAD.clear()
    PREFIJOS_UNIDAD.update({u["clave"]: u["prefijos"] for u in unidades})
    JOURNEYS_ASIGNADOS.clear()
    JOURNEYS_ASIGNADOS.update({j: c for j, c in (config.get("journeys") or {}).items() if c in UNIDADES})
    defecto = config.get("unidad_por_defecto", "mercadeo")
    _AJUSTES["por_defecto"] = defecto if defecto in UNIDADES else SIN_UNIDAD


def unidad_por_defecto() -> str:
    return _AJUSTES["por_defecto"]


configurar_unidades({})


# ---------------------------------------------------------------------------
# Carga de archivos
# ---------------------------------------------------------------------------

def leer_reporte(ruta: Path) -> tuple[pd.DataFrame, str | None]:
    """Lee el reporte de Marketing Cloud.

    El archivo trae filas de encabezado del widget (nombre, fecha de
    generación, rango de fechas) antes de la fila real de columnas, y puede
    traer una fila "Totals" al final. Se busca la fila que contiene
    "WhatsApp Country" para usarla como encabezado.

    Devuelve el dataframe y la fecha de generación del reporte (si viene).
    """
    with warnings.catch_warnings():
        # El Excel de Marketing Cloud no trae estilo por defecto y openpyxl avisa; no afecta los datos.
        warnings.filterwarnings("ignore", message="Workbook contains no default style")
        crudo = pd.read_excel(ruta, header=None)

    fila_encabezado = None
    fecha_generacion = None
    for i in range(len(crudo)):
        valores = [str(v).strip() for v in crudo.iloc[i]]
        if valores[0].lower().startswith("date/time generated"):
            fecha_generacion = valores[1]
        if "WhatsApp Country" in valores:
            fila_encabezado = i
            break
    if fila_encabezado is None:
        raise ValueError("No se encontró la fila de encabezados ('WhatsApp Country') en el reporte.")

    df = crudo.iloc[fila_encabezado + 1:].copy()
    df.columns = [str(c).strip() for c in crudo.iloc[fila_encabezado]]
    df = df[df["WhatsApp Country"].notna()]
    df = df[df["WhatsApp Country"].astype(str).str.strip().str.lower() != "totals"]
    df = df[df["Journey Name"].notna()]
    return df.reset_index(drop=True), fecha_generacion


def leer_tarifas(ruta: Path) -> pd.DataFrame:
    """Lee las tarifas.

    - Si `ruta` es una carpeta, lee todos los archivos AAAA-MM-DD.csv que contiene;
      cada uno rige desde esa fecha hasta el día anterior al siguiente.
    - Si es un archivo, es una tabla única (rige para todas las fechas).

    Devuelve las columnas vigente_desde, ISO, Country, Marketing y Utility.
    """
    ruta = Path(ruta)
    if ruta.is_dir():
        partes = []
        for archivo in sorted(ruta.glob("*.csv")):
            try:
                desde = pd.Timestamp(archivo.stem)
            except ValueError:
                continue  # archivos que no se llaman como una fecha se ignoran
            tabla = pd.read_csv(archivo, keep_default_na=False, na_values={"Marketing": [""], "Utility": [""]})
            tabla["vigente_desde"] = desde
            partes.append(tabla)
        if not partes:
            raise ValueError(f"La carpeta {ruta.name} no tiene archivos de tarifas con nombre AAAA-MM-DD.csv.")
        tarifas = pd.concat(partes, ignore_index=True)
    else:
        tarifas = pd.read_csv(ruta, keep_default_na=False, na_values={"Marketing": [""], "Utility": [""]})
        tarifas["vigente_desde"] = pd.Timestamp.min
    # keep_default_na=False: "NA" es el código ISO de Namibia, no un dato vacío.
    tarifas["ISO"] = tarifas["ISO"].astype(str).str.upper().str.strip()
    if tarifas.duplicated(["vigente_desde", "ISO"]).any():
        raise ValueError("Hay países repetidos dentro de una misma tabla de tarifas.")
    return tarifas[["vigente_desde", "ISO", "Country", "Marketing", "Utility"]]


def vigencias(tarifas: pd.DataFrame) -> list[pd.Timestamp]:
    """Fechas de inicio de cada tabla de tarifas, en orden."""
    return sorted(tarifas["vigente_desde"].unique())


def tarifa_vigente(tarifas: pd.DataFrame, fecha: pd.Timestamp) -> pd.Timestamp:
    """Fecha de inicio de la tabla que rige en `fecha` (la primera si es anterior a todas)."""
    fechas = vigencias(tarifas)
    aplicables = [f for f in fechas if f <= fecha]
    return aplicables[-1] if aplicables else fechas[0]


def leer_config(ruta: Path) -> dict:
    """Lee config.json y deja configuradas las unidades (antes de clasificar las entregas)."""
    with open(ruta, encoding="utf-8") as f:
        config = json.load(f)
    configurar_unidades(config)
    return config


LINEAS_COMPRA = ["UCP", "Outbound"]   # cada línea tiene su propia bolsa de créditos


def compras_con_linea(config: dict) -> bool:
    """True si las compras registradas indican a qué línea pertenecen (formato actual)."""
    compras = config.get("compras") or []
    return bool(compras) and all(str(c.get("linea") or "") in LINEAS_COMPRA for c in compras)


def config_linea(config: dict, linea: str) -> dict:
    """Créditos adquiridos de una línea y lo asignado a cada unidad dentro de ella.

    UCP y Outbound son bolsas separadas: cada compra es para una sola línea.
    - UCP / Outbound: la suma de las compras de esa línea ("compras" en config.json, campo "linea").
      Si las compras no indican línea (formato anterior), se usa "creditos_totales" de la sección de la línea.
    - Ambas líneas: UCP + Outbound, en el total y en cada unidad.
    """
    if linea == "Ambas líneas":
        partes = [config_linea(config, l) for l in LINEAS_COMPRA]
        if not ("ucp" in config or "outbound" in config):   # formato muy antiguo: solo "general"
            cfg = config.get("general", {"creditos_totales": config.get("creditos_totales", 0),
                                         "unidades": config.get("unidades", {})})
            unidades = cfg.get("unidades", {})
            return {"creditos_totales": float(cfg.get("creditos_totales", 0)),
                    "unidades": {u: float(unidades.get(CLAVE_CONFIG_UNIDAD[u], 0)) for u in UNIDADES}}
        return {"creditos_totales": sum(p["creditos_totales"] for p in partes),
                "unidades": {u: sum(p["unidades"][u] for p in partes) for u in UNIDADES}}
    cfg = config.get(CLAVE_CONFIG_LINEA[linea], {})
    unidades = cfg.get("unidades", {})
    if compras_con_linea(config):
        total = total_compras([c for c in config["compras"] if c.get("linea") == linea])
    else:
        total = float(cfg.get("creditos_totales", 0))
    return {
        "creditos_totales": total,
        "unidades": {u: float(unidades.get(CLAVE_CONFIG_UNIDAD[u], 0)) for u in UNIDADES},
    }


def total_compras(compras: list[dict] | None) -> float:
    return float(sum(float(c.get("creditos", 0) or 0) for c in (compras or [])))


def sin_asignar(creditos_linea: dict) -> float:
    """Créditos de la línea que no están repartidos entre unidades (negativo si se asignó de más)."""
    return creditos_linea["creditos_totales"] - sum(creditos_linea["unidades"].values())


def guardar_creditos(ruta: Path, config: dict, unidades: dict[str, dict[str, float]],
                     compras: list[dict] | None = None) -> None:
    """Escribe en config.json las compras de créditos (cada una con su línea) y lo asignado a cada unidad.

    `unidades`: {"UCP" | "Outbound": {"mercadeo": n, "egresados": n, "donaciones": n}}.
    `compras`: [{"fecha": "AAAA-MM-DD", "linea": "UCP" | "Outbound", "creditos": n, "nota": "..."}];
    si es None se conservan las actuales.
    Las secciones "ucp", "outbound" y "general" guardan el total calculado, solo como referencia.
    Conserva el resto de secciones del archivo (semáforo, marca, etc.).
    """
    nuevo = dict(config)
    if compras is not None:
        nuevo["compras"] = []
        for c in compras:
            fila = {"fecha": str(c.get("fecha") or "")[:10], "linea": str(c.get("linea") or ""),
                    "creditos": round(float(c.get("creditos") or 0)), "nota": str(c.get("nota") or "")}
            precio = c.get("precio_usd_1000")
            if precio is not None and not pd.isna(precio) and float(precio) > 0:
                fila["precio_usd_1000"] = float(precio)   # precio propio de esa compra (opcional)
            nuevo["compras"].append(fila)
    for linea in LINEAS_COMPRA:
        clave = CLAVE_CONFIG_LINEA[linea]
        anterior = config_linea(nuevo, linea)
        valores = unidades.get(linea, anterior["unidades"])
        nuevo[clave] = {"creditos_totales": round(anterior["creditos_totales"]),
                        "unidades": {CLAVE_CONFIG_UNIDAD[u]: round(float(v)) for u, v in valores.items()}}
    general = config_linea(nuevo, "Ambas líneas")
    nuevo["general"] = {
        "creditos_totales": round(general["creditos_totales"]),
        "unidades": {CLAVE_CONFIG_UNIDAD[u]: round(v) for u, v in general["unidades"].items()},
    }
    for clave in ("creditos_totales", "unidades"):  # formato antiguo (plano), ya migrado
        if not isinstance(nuevo.get(clave), list):
            nuevo.pop(clave, None)
    escribir_config(ruta, nuevo)


def escribir_config(ruta: Path, nuevo: dict) -> None:
    """Escribe config.json de forma legible (una compra, unidad o journey por línea) y segura."""
    orden = ["compras", "general", "ucp", "outbound", "precios_usd_1000", "precios_confirmados",
             "unidades", "unidad_por_defecto", "journeys"]
    claves = [k for k in orden if k in nuevo] + [k for k in nuevo if k not in orden]
    partes = []
    for k in claves:
        if k in ("compras", "unidades") and isinstance(nuevo[k], list):
            filas = ",\n".join(f"    {json.dumps(c, ensure_ascii=False)}" for c in nuevo[k])
            partes.append(f'  "{k}": [\n{filas}\n  ]')
        elif k == "journeys" and isinstance(nuevo[k], dict):
            filas = ",\n".join(f"    {json.dumps(j, ensure_ascii=False)}: {json.dumps(c, ensure_ascii=False)}"
                                for j, c in sorted(nuevo[k].items(), key=lambda x: x[0].lower()))
            partes.append('  "journeys": {' + (f"\n{filas}\n  " if filas else "") + "}")
        else:
            partes.append(f'  "{k}": {json.dumps(nuevo[k], ensure_ascii=False)}')
    temporal = Path(ruta).with_suffix(".tmp")
    temporal.write_text("{\n" + ",\n".join(partes) + "\n}\n", encoding="utf-8")
    temporal.replace(ruta)


def guardar_unidades(ruta: Path, config: dict, unidades: list[dict], por_defecto: str,
                     journeys: dict[str, str]) -> None:
    """Escribe en config.json las unidades, la unidad por defecto y la asignación manual de journeys.

    Los créditos asignados a cada unidad se conservan; los de una unidad eliminada se quitan.
    """
    nuevo = dict(config)
    nuevo["unidades"] = [{"clave": u["clave"], "nombre": u["nombre"], "codigo": u["codigo"],
                          "prefijos": list(u.get("prefijos") or [])} for u in unidades]
    nuevo["unidad_por_defecto"] = por_defecto
    validas = {u["clave"] for u in unidades}
    nuevo["journeys"] = {j: c for j, c in journeys.items() if c in validas}
    codigos = [u["codigo"] for u in unidades]
    for linea in LINEAS_COMPRA:
        seccion = dict(nuevo.get(CLAVE_CONFIG_LINEA[linea], {}))
        anteriores = seccion.get("unidades", {})
        seccion["unidades"] = {c: anteriores.get(c, 0) for c in codigos}
        nuevo[CLAVE_CONFIG_LINEA[linea]] = seccion
    gen = dict(nuevo.get("general", {}))
    gen["unidades"] = {c: round(sum(float(nuevo[CLAVE_CONFIG_LINEA[l]]["unidades"].get(c, 0)) for l in LINEAS_COMPRA))
                       for c in codigos}
    nuevo["general"] = gen
    escribir_config(ruta, nuevo)
    configurar_unidades(nuevo)


def adquirido_al(config_compras: list[dict], linea: str, fecha: pd.Timestamp | None) -> float:
    """Créditos comprados para una línea con fecha de compra hasta `fecha` (None = todas)."""
    total = 0.0
    for c in config_compras or []:
        if c.get("linea") != linea:
            continue
        f = pd.to_datetime(c.get("fecha"), errors="coerce")
        if fecha is None or pd.isna(f) or f <= fecha:
            total += float(c.get("creditos") or 0)
    return total


# ---------------------------------------------------------------------------
# Dinero (USD)
# ---------------------------------------------------------------------------

CANALES = {"whatsapp": "WhatsApp", "correo": "Correo", "sms": "SMS"}
PRECIOS_POR_DEFECTO = {"whatsapp": 4.16, "correo": None, "sms": None}   # USD por cada 1.000 créditos (editable)


def precios_canal(config: dict) -> dict[str, float | None]:
    """Precio en USD por cada 1.000 créditos de cada canal (config.json, "precios_usd_1000")."""
    precios = dict(PRECIOS_POR_DEFECTO)
    precios.update(config.get("precios_usd_1000") or {})
    return {c: (float(v) if v not in (None, "") and float(v) > 0 else None) for c, v in precios.items()}


def precios_confirmados(config: dict) -> dict[str, bool]:
    return {c: bool((config.get("precios_confirmados") or {}).get(c, False)) for c in CANALES}


def guardar_precios(ruta: Path, config: dict, precios: dict[str, float | None], confirmados: dict[str, bool]) -> None:
    nuevo = dict(config)
    nuevo["precios_usd_1000"] = {c: (round(float(v), 6) if v else None) for c, v in precios.items()}
    nuevo["precios_confirmados"] = {c: bool(v) for c, v in confirmados.items()}
    escribir_config(ruta, nuevo)


def precio_promedio(compras: list[dict], linea: str, precio_canal: float | None) -> float | None:
    """Precio por 1.000 créditos de la bolsa de una línea: promedio de sus compras, ponderado por créditos.
    Cada compra usa su propio precio si lo tiene; si no, el del canal."""
    total, valor = 0.0, 0.0
    for c in compras or []:
        if c.get("linea") != linea:
            continue
        creditos = float(c.get("creditos") or 0)
        precio = c.get("precio_usd_1000")
        precio = float(precio) if precio not in (None, "") and not pd.isna(precio) and float(precio) > 0 else precio_canal
        if precio is None:
            continue
        total += creditos
        valor += creditos * precio
    if total > 0:
        return valor / total
    return precio_canal


def journeys_sinteticos(nuevos: list[dict], inicio: pd.Timestamp, fin: pd.Timestamp) -> pd.DataFrame:
    """Filas diarias para journeys nuevos o de reemplazo (entregas por semana, país, tipo, línea), en el
    periodo de referencia, para sumarlas a la proyección. Los créditos los calcula la proyección con la
    tarifa vigente de cada día."""
    dias = pd.date_range(inicio, fin, freq="D")
    filas = []
    for n in nuevos:
        semanal = float(n.get("entregas_semana") or 0)
        if semanal <= 0 or len(dias) == 0:
            continue
        utility = str(n.get("tipo") or "Marketing").lower() == "utility"
        diario = semanal / 7
        for d in dias:
            filas.append({"fecha": d, "journey": str(n.get("nombre") or "Journey nuevo"),
                          "pais": str(n.get("pais") or "CO").upper(), "es_utility": utility,
                          "linea": n.get("linea") or "", "unidad": n.get("unidad") or "",
                          "deliveries": diario, "deliveries_marketing": 0.0 if utility else diario,
                          "deliveries_utility": diario if utility else 0.0,
                          "creditos": 0.0, "creditos_marketing": 0.0, "creditos_utility": 0.0})
    return pd.DataFrame(filas)


SEMAFORO_POR_DEFECTO = {"amarillo_pct": 80.0, "rojo_pct": 95.0, "fecha_inicio_conteo": None}


def config_semaforo(config: dict) -> dict:
    """Umbrales del semáforo (config.json, sección "semaforo")."""
    cfg = dict(SEMAFORO_POR_DEFECTO)
    cfg.update(config.get("semaforo", {}))
    return cfg


def estado_consumo(uso_pct: float | None, amarillo_pct: float, rojo_pct: float) -> str:
    """'verde', 'amarillo', 'rojo' o 'sin_definir' según el porcentaje de uso."""
    if uso_pct is None:
        return "sin_definir"
    if uso_pct >= rojo_pct:
        return "rojo"
    if uso_pct >= amarillo_pct:
        return "amarillo"
    return "verde"


# ---------------------------------------------------------------------------
# Clasificación de cada envío
# ---------------------------------------------------------------------------

def unidad_automatica(nombre: str) -> str:
    """Unidad según el prefijo del journey (sin tener en cuenta la asignación manual)."""
    texto = str(nombre).strip().upper()
    for clave in UNIDADES:
        if any(texto.startswith(p.upper()) for p in PREFIJOS_UNIDAD.get(clave, [])):
            return clave
    return unidad_por_defecto()


def unidad_de(nombre: str) -> str:
    """Unidad del journey: la asignada a mano en Configuración o, si no tiene, la de su prefijo."""
    asignada = JOURNEYS_ASIGNADOS.get(str(nombre))
    return asignada if asignada in UNIDADES else unidad_automatica(nombre)


NO_SON_PRUEBAS = ["PRUEBAESPECIFICA", "PRUEBA_ESPECIFICA", "PRUEBA ESPECIFICA", "PRUEBAESPECÍFICA",
                  "PRUEBA_ESPECÍFICA", "PRUEBA ESPECÍFICA"]
CATEGORIA_SOLICITUD = "Entregas a solicitud"   # antes "Campaña": envíos que piden las unidades


def tipo_journey(nombre: str) -> str:
    texto = str(nombre).upper()
    # "Prueba específica" es la prueba de admisión de algunos programas: son entregas reales, no pruebas.
    sin_admision = texto
    for frase in NO_SON_PRUEBAS:
        sin_admision = sin_admision.replace(frase, "")
    if "PRUEBA" in sin_admision:
        return "Pruebas"
    if "ACCESO" in texto:
        return "Automático - Acceso"
    if texto.startswith("MERCA_FINANCIACION") or texto.startswith("MERCA_MANTENIMIENTO"):
        return "Automático - Financiación"
    if "VISITAS_LOS_VIERNES" in texto:
        return "Automático - Visitas"
    return CATEGORIA_SOLICITUD


def _normalizar_canal(valor) -> str:
    try:
        return str(int(float(valor)))
    except (ValueError, TypeError):
        texto = str(valor).strip()
        return "" if texto.lower() == "nan" else texto


def preparar_envios(reporte: pd.DataFrame, tarifas: pd.DataFrame) -> pd.DataFrame:
    """Limpia el reporte y calcula créditos y clasificaciones por fila."""
    df = reporte.copy()

    # Igual que la versión original: los nombres se usan tal cual (sin recortar espacios),
    # porque Marketing Cloud tiene journeys distintos que solo se diferencian por un espacio final.
    df["journey"] = df["Journey Name"].astype(str)
    df["pais"] = df["WhatsApp Country"].astype(str).str.upper().str.strip()
    df["fecha"] = pd.to_datetime(df["Send Date"], errors="coerce")
    df = df[df["fecha"].notna()].copy()
    df["deliveries"] = pd.to_numeric(df["WhatsApp Deliveries"], errors="coerce").fillna(0)

    canal = df["WhatsApp Channel ID"] if "WhatsApp Channel ID" in df.columns else ""
    df["canal"] = pd.Series(canal, index=df.index).apply(_normalizar_canal)
    nombre_linea = {v: k for k, v in LINEAS.items() if v}
    df["linea"] = df["canal"].map(nombre_linea).fillna("Sin línea")

    # Tipo de conversación. Marketing Cloud exporta este campo con errores
    # ("8", vacíos). Regla confirmada con el equipo: todo lo que no sea
    # explícitamente "Utility" se cobra con tarifa Marketing.
    tipo = df["WhatsApp Conversation Type"].astype(str).str.upper().str.strip()
    df["es_utility"] = tipo.eq("UTILITY")
    df["tipo_conversacion"] = np.where(df["es_utility"], "Utility", "Marketing")

    # Tarifa: cada envío se cobra con la tabla vigente en su fecha de envío
    # (la más reciente cuya fecha de inicio sea menor o igual). Los envíos
    # anteriores a la primera tabla usan la primera. Dentro de cada tabla, los
    # países que no aparecen usan la fila OTHER.
    df["tarifa_vigente_desde"] = df["fecha"].apply(lambda f: tarifa_vigente(tarifas, f))
    df = df.merge(tarifas, left_on=["tarifa_vigente_desde", "pais"],
                  right_on=["vigente_desde", "ISO"], how="left")
    otros = (tarifas[tarifas["ISO"] == "OTHER"]
             .set_index("vigente_desde")[["Marketing", "Utility"]])
    df["tarifa_por_defecto"] = df["ISO"].isna()
    df["nombre_pais"] = df["Country"].fillna(df["pais"])
    df["Marketing"] = df["Marketing"].fillna(df["tarifa_vigente_desde"].map(otros["Marketing"])).fillna(0.0)
    df["Utility"] = df["Utility"].fillna(df["tarifa_vigente_desde"].map(otros["Utility"])).fillna(0.0)
    df["tarifa"] = np.where(df["es_utility"], df["Utility"], df["Marketing"])
    df["creditos"] = df["deliveries"] * df["tarifa"]
    df["creditos_marketing"] = np.where(df["es_utility"], 0.0, df["creditos"])
    df["creditos_utility"] = np.where(df["es_utility"], df["creditos"], 0.0)
    df["deliveries_marketing"] = np.where(df["es_utility"], 0.0, df["deliveries"])
    df["deliveries_utility"] = np.where(df["es_utility"], df["deliveries"], 0.0)

    # Clasificaciones
    df["unidad"] = df["journey"].apply(unidad_de)
    df["tipo_journey"] = df["journey"].apply(tipo_journey)


    df["mes"] = df["fecha"].dt.to_period("M").astype(str)
    iso = df["fecha"].dt.isocalendar()
    df["semana_inicio"] = (df["fecha"] - pd.to_timedelta(df["fecha"].dt.weekday, unit="D")).dt.normalize()
    df["semana"] = "S" + iso["week"].astype(str).str.zfill(2) + " · " + df["semana_inicio"].dt.strftime("%d/%m")

    columnas = [
        "fecha", "mes", "semana", "semana_inicio", "linea", "canal", "unidad", "journey",
        "tipo_journey", "pais", "nombre_pais", "tipo_conversacion",
        "es_utility", "deliveries", "tarifa", "tarifa_vigente_desde", "tarifa_por_defecto", "creditos",
        "creditos_marketing", "creditos_utility", "deliveries_marketing", "deliveries_utility",
        "WhatsApp Send Name",
    ]
    columnas = [c for c in columnas if c in df.columns]
    return df[columnas].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Agregaciones
# ---------------------------------------------------------------------------

METRICAS = ["deliveries", "creditos", "creditos_marketing", "creditos_utility",
            "deliveries_marketing", "deliveries_utility"]


def totales(df: pd.DataFrame) -> dict[str, float]:
    return {m: float(df[m].sum()) for m in METRICAS}


def repreciar(envios: pd.DataFrame, tarifas: pd.DataFrame, fecha: pd.Timestamp) -> pd.DataFrame:
    """Los mismos envíos, cobrados con la tabla de tarifas vigente en `fecha`.

    Sirve para proyectar con la tarifa que va a regir y para separar cuánto del
    cambio en el cobro se debe al volumen y cuánto a la tarifa.
    """
    desde = tarifa_vigente(tarifas, fecha)
    tabla = tarifas[tarifas["vigente_desde"] == desde].set_index("ISO")
    otro = tabla.loc["OTHER"] if "OTHER" in tabla.index else pd.Series({"Marketing": 0.0, "Utility": 0.0})
    datos = envios.copy()
    mkt = datos["pais"].map(tabla["Marketing"]).fillna(otro["Marketing"])
    uti = datos["pais"].map(tabla["Utility"]).fillna(otro["Utility"])
    datos["tarifa"] = np.where(datos["es_utility"], uti, mkt)
    datos["tarifa_vigente_desde"] = desde
    datos["creditos"] = datos["deliveries"] * datos["tarifa"]
    datos["creditos_marketing"] = np.where(datos["es_utility"], 0.0, datos["creditos"])
    datos["creditos_utility"] = np.where(datos["es_utility"], datos["creditos"], 0.0)
    return datos


def resumen_vigencias(envios: pd.DataFrame, tarifas: pd.DataFrame) -> pd.DataFrame:
    """Envíos y créditos por tabla de tarifas aplicada, con su periodo de vigencia."""
    fechas = vigencias(tarifas)
    tabla = envios.groupby("tarifa_vigente_desde", as_index=False)[METRICAS].sum()
    hasta = {f: (fechas[i + 1] - pd.Timedelta(days=1)) if i + 1 < len(fechas) else None
             for i, f in enumerate(fechas)}
    tabla["vigente_hasta"] = tabla["tarifa_vigente_desde"].map(hasta)
    tabla["creditos_por_envio"] = tabla["creditos"] / tabla["deliveries"].where(tabla["deliveries"] > 0)
    return tabla.sort_values("tarifa_vigente_desde").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Proyección de agotamiento
# ---------------------------------------------------------------------------

def proyeccion(envios: pd.DataFrame, inicio: pd.Timestamp, fin: pd.Timestamp,
               restante: float, desde: pd.Timestamp | None = None,
               tarifas: pd.DataFrame | None = None) -> dict:
    """Consumo diario promedio en [inicio, fin] y fecha estimada de agotamiento.

    Sin `tarifas`: el consumo futuro es el promedio diario de la ventana, tal
    como se cobró, y la fecha de agotamiento es desde + restante / consumo diario.

    Con `tarifas`: se toma el volumen promedio diario de la ventana (por país y
    tipo de conversación) y cada día futuro se cobra con la tabla de tarifas que
    rija ese día. Así la proyección ya incluye los cambios de tarifa publicados.

    La fecha de agotamiento se cuenta a partir de `desde` (por defecto, `fin`).
    """
    ventana = envios[(envios["fecha"] >= inicio) & (envios["fecha"] <= fin)]
    dias = max((fin - inicio).days + 1, 1)
    base = desde if desde is not None else fin
    diario = {k: v / dias for k, v in totales(ventana).items()}

    if tarifas is None:
        semana = {k: v * 7 for k, v in diario.items()}
        agotamiento = None
        if restante <= 0:
            agotamiento = "agotado"
        elif diario["creditos"] > 0:
            agotamiento = base + pd.Timedelta(days=restante / diario["creditos"])
        return {"dias": dias, "diario": diario, "semana": semana, "agotamiento": agotamiento,
                "tarifas_proyeccion": []}

    # Consumo diario según la tabla de tarifas de cada vigencia
    por_vigencia = {f: {k: v / dias for k, v in totales(repreciar(ventana, tarifas, f)).items()}
                    for f in vigencias(tarifas)}

    def diario_en(dia: pd.Timestamp) -> dict:
        return por_vigencia[tarifa_vigente(tarifas, dia)]

    proximos = [base + pd.Timedelta(days=d) for d in range(1, 8)]
    semana = {k: sum(diario_en(d)[k] for d in proximos) for k in METRICAS}

    agotamiento = None
    if restante <= 0:
        agotamiento = "agotado"
    else:
        acumulado = 0.0
        for d in range(1, 3651):  # hasta 10 años
            consumo = diario_en(base + pd.Timedelta(days=d))["creditos"]
            if consumo <= 0:
                continue
            if acumulado + consumo >= restante:
                fraccion = (restante - acumulado) / consumo
                agotamiento = base + pd.Timedelta(days=d - 1 + fraccion)
                break
            acumulado += consumo

    usadas = sorted({tarifa_vigente(tarifas, base + pd.Timedelta(days=1))}
                    | {f for f in vigencias(tarifas) if f > base})
    return {"dias": dias, "diario": diario, "semana": semana, "agotamiento": agotamiento,
            "tarifas_proyeccion": usadas}


def consumo_estimado(envios: pd.DataFrame, inicio: pd.Timestamp, fin: pd.Timestamp, desde: pd.Timestamp,
                     hasta: pd.Timestamp, tarifas: pd.DataFrame) -> dict[str, float]:
    """Consumo estimado entre el día siguiente a `desde` y `hasta` (incluido), con el volumen promedio
    diario de [inicio, fin] y la tabla de tarifas que rija cada día futuro."""
    ventana = envios[(envios["fecha"] >= inicio) & (envios["fecha"] <= fin)]
    dias_ref = max((fin - inicio).days + 1, 1)
    por_vigencia = {f: {k: v / dias_ref for k, v in totales(repreciar(ventana, tarifas, f)).items()}
                    for f in vigencias(tarifas)}
    total = {k: 0.0 for k in METRICAS}
    for d in range(1, max((hasta - desde).days, 0) + 1):
        diario = por_vigencia[tarifa_vigente(tarifas, desde + pd.Timedelta(days=d))]
        for k in METRICAS:
            total[k] += diario[k]
    return total
