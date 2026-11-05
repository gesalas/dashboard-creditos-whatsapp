"""
Canal Correo: estado de los créditos, gasto por unidad, remitentes, journeys y créditos de correo.

Usa los datos y las piezas de dibujo que ya preparó app.py (los recibe con preparar(), una vez por ejecución):
así esta parte vive en su propio archivo sin duplicar el código común (tarjetas, gráficas, formato de números).
Cada canal nuevo (por ejemplo SMS) puede seguir el mismo patrón.
"""

from __future__ import annotations

import types
from datetime import date
from types import SimpleNamespace

import pandas as pd
import streamlit as st

import logica as L

# Lo que este módulo toma de app.py (se llena en preparar)
NECESITA = ("COLOR_CANAL", "COLOR_UNIDAD", "COL_PRECIO", "CTX", "NOMBRE_UNIDAD_APP", "PRECIOS", "PRECIOS_OK", "RUTA_CONFIG", "TEMA", "amarillo_pct", "config", "correo", "etiqueta_semana", "fila_tarjetas", "fin", "grafica_barras", "info_correo", "inicio", "insignia", "nombre_ambito", "nota", "num", "pct", "punto_unidad", "rojo_pct", "subir_y_registrar", "tabs_correo", "tarjeta_semaforo", "txt_precio", "txt_usd", "unidad_sel", "resolver_periodo",
            "opcion_periodo", "personalizado")
COLOR_CANAL = None
COLOR_UNIDAD = None
COL_PRECIO = None
CTX = None
NOMBRE_UNIDAD_APP = None
PRECIOS = None
PRECIOS_OK = None
RUTA_CONFIG = None
TEMA = None
amarillo_pct = None
config = None
correo = None
etiqueta_semana = None
fila_tarjetas = None
fin = None
grafica_barras = None
info_correo = None
inicio = None
insignia = None
nombre_ambito = None
nota = None
num = None
pct = None
punto_unidad = None
rojo_pct = None
subir_y_registrar = None
tabs_correo = None
tarjeta_semaforo = None
txt_precio = None
txt_usd = None
unidad_sel = None
resolver_periodo = None
opcion_periodo = None
personalizado = None
inicio_c = fin_c = fecha_max_c = None   # periodo del correo (con sus propias fechas)
CFG_CORREO: dict = {}
NOMBRE_DESTINO_CORREO: dict = {}
COLOR_DESTINO_CORREO: dict = {}
ESTIMADO_CORREO = ""


def preparar(contexto: dict) -> SimpleNamespace:
    """Recibe de app.py los datos y funciones comunes de esta ejecución y devuelve las funciones del canal.

    Cada ejecución (cada persona conectada) recibe su propia copia de las funciones, con sus propios datos:
    así dos personas usando el tablero al mismo tiempo no se mezclan."""
    faltan = [n for n in NECESITA if n not in contexto]
    if faltan:
        raise RuntimeError(f"canal_correo: faltan {', '.join(faltan)}")
    g = dict(globals())
    g.update({n: contexto[n] for n in NECESITA})
    g["CFG_CORREO"] = L.config_correo(g["config"])
    g["NOMBRE_DESTINO_CORREO"] = {**g["NOMBRE_UNIDAD_APP"], L.NINGUNA_UNIDAD: "Ninguna unidad (solo en el total)",
                                  L.SIN_ASIGNAR: "Sin asignar"}
    g["COLOR_DESTINO_CORREO"] = {**{g["NOMBRE_UNIDAD_APP"][u]: c for u, c in g["COLOR_UNIDAD"].items()},
                                 "Ninguna unidad (solo en el total)": g["TEMA"]["texto_ter"],
                                 "Sin asignar": g["TEMA"]["borde_fuerte"]}
    g["ESTIMADO_CORREO"] = "" if g["PRECIOS_OK"].get("correo") else " (estimado)"
    # El periodo del correo se calcula con SUS fechas (su reporte puede llegar hasta otro día que el de WhatsApp)
    c = g["correo"]
    if g["info_correo"].get("con_fecha") and c is not None and c["fecha"].notna().any():
        fmin, fmax = c["fecha"].min().date(), c["fecha"].max().date()
        ini, fi, _ = g["resolver_periodo"](g["opcion_periodo"], fmin, fmax, g["personalizado"])
        g["inicio_c"], g["fin_c"], g["fecha_max_c"] = pd.Timestamp(ini), pd.Timestamp(fi), pd.Timestamp(fmax)
    else:
        g["inicio_c"], g["fin_c"], g["fecha_max_c"] = g["inicio"], g["fin"], None
    propias = {n: f for n, f in globals().items()
               if isinstance(f, types.FunctionType) and f.__module__ == __name__ and n != "preparar"}
    for n, f in propias.items():
        g[n] = types.FunctionType(f.__code__, g, f.__name__, f.__defaults__, f.__closure__)
    return SimpleNamespace(**{n: g[n] for n in propias}, ESTIMADO_CORREO=g["ESTIMADO_CORREO"],
                           inicio=g["inicio_c"], fin=g["fin_c"], fecha_max=g["fecha_max_c"])


def precio_correo() -> float | None:
    """Precio por 1.000 créditos de correo: promedio de las compras (si alguna trae su precio) o el del canal."""
    total, valor = 0.0, 0.0
    for c in CFG_CORREO["compras"]:
        cred = float(c.get("creditos") or 0)
        p = c.get("precio_usd_1000") or PRECIOS.get("correo")
        if p:
            total += cred
            valor += cred * float(p)
    return valor / total if total else PRECIOS.get("correo")


def usd_correo(creditos: float) -> float | None:
    p = precio_correo()
    return None if p is None else creditos * p / 1000




def corte_correo() -> pd.Timestamp | None:
    g = info_correo.get("generado")
    return pd.Timestamp(g).tz_localize(None) if g is not None and pd.notna(g) else None


def correo_en_periodo(datos: pd.DataFrame) -> pd.DataFrame:
    """Con fecha de envío se filtra por el periodo consultado; sin ella, es todo el acumulado del reporte."""
    if info_correo.get("con_fecha"):
        return datos[(datos["fecha"] >= inicio_c) & (datos["fecha"] <= fin_c)]
    return datos


REF_DIAS = 28   # ritmo con el que se estima el agotamiento (igual que en WhatsApp)


def estado_correo(unidad: str | None = None) -> dict:
    datos = correo if unidad is None else correo[correo["unidad"] == unidad]
    agot, ritmo = None, None
    if info_correo.get("con_fecha"):
        corte_e = min(fin_c, fecha_max_c)
        datos = datos[datos["fecha"] <= corte_e]
        recientes = datos[datos["fecha"] > corte_e - pd.Timedelta(days=REF_DIAS)]
        ritmo = float(recientes["creditos"].sum()) / REF_DIAS
    usado = float(datos["creditos"].sum())
    if unidad is None:
        hasta = fin_c if info_correo.get("con_fecha") else pd.Timestamp(date.today())
        disponible = sum(float(c.get("creditos") or 0) for c in CFG_CORREO["compras"]
                         if not c.get("fecha") or pd.Timestamp(c["fecha"]) <= hasta)
    else:
        disponible = float(CFG_CORREO["unidades"].get(unidad, 0))
    uso = usado / disponible if disponible > 0 else None
    estado = L.estado_consumo(uso * 100 if uso is not None else None, amarillo_pct, rojo_pct)
    if ritmo is not None and disponible > 0:
        restan = disponible - usado
        if restan <= 0:
            agot = "Agotados"
        elif ritmo <= 0:
            agot = "Sin consumo reciente"
        else:
            agot = min(fin_c, fecha_max_c) + pd.Timedelta(days=min(int(restan / ritmo), 36500))
    return {"agotamiento": agot, "ritmo": ritmo,"titulo": "Correo (total)" if unidad is None else punto_unidad(unidad) + NOMBRE_UNIDAD_APP[unidad],
            "usado": usado, "disponible": disponible, "restan": disponible - usado, "uso": uso, "estado": estado,
            "envios": float(datos["envios"].sum()), "usd": usd_correo(usado),
            "usd_disponible": usd_correo(disponible) if disponible else None}


def tarjeta_correo(e: dict, etiqueta_disponible: str) -> str:
    hay = e["disponible"] > 0
    a = e.get("agotamiento")
    if not info_correo.get("con_fecha"):
        agot = '<span class="cifra-sub">Requiere la fecha de envío en el reporte</span>'
    elif isinstance(a, pd.Timestamp):
        agot = (f'{a:%d/%m/%Y}<div class="cifra-sub cifra-reserva">al ritmo de {num(e["ritmo"] * 7)} correos por semana</div>'
                if a.year < 2100 else 'Más de 70 años<div class="cifra-sub cifra-reserva">&nbsp;</div>')
    elif a:
        agot = f'{a}<div class="cifra-sub cifra-reserva">&nbsp;</div>'
    else:
        agot = '<span class="cifra-sub">Sin créditos definidos</span>'
    cifras = [
        ("Usados", num(e["usado"])
         + (f'<div class="cifra-sub">≈ {txt_usd(e["usd"])}{ESTIMADO_CORREO}</div>' if e.get("usd") is not None else "")),
        (etiqueta_disponible, num(e["disponible"]) if hay else "Sin definir"),
        ("Excedido" if e["restan"] < 0 else "Disponibles", num(abs(e["restan"])) if hay else "-"),
        ("Agotamiento estimado", agot),
    ]
    return tarjeta_semaforo(e["titulo"], e["estado"], e["uso"], cifras, amarillo_pct, rojo_pct, "usado")


def aviso_remitentes_pendientes() -> None:
    pend = L.remitentes_pendientes(correo)
    if pend.empty or not CTX["admin"]:
        return
    lista_r = ", ".join(f"{r.remitente} ({num(r.envios)})" for r in pend.head(6).itertuples())
    mas = f" y {len(pend) - 6} más" if len(pend) > 6 else ""
    st.warning(f"**Hay {len(pend)} {'remitente' if len(pend) == 1 else 'remitentes'} de correo sin unidad** "
               f"({num(pend['envios'].sum())} correos): {lista_r}{mas}. Indica de qué unidad es cada uno, o si no "
               "es de ninguna, en Correo → Remitentes. Mientras tanto solo cuentan en el total.",
               icon=":material/person_search:")


def pagina_correo() -> None:
    ambito = correo if not unidad_sel else correo[correo["unidad"] == unidad_sel]
    periodo_c = correo_en_periodo(ambito)
    corte = corte_correo()
    con_fecha = info_correo.get("con_fecha")

    with tabs_correo["Resumen"]:
        rango = info_correo.get("rango")
        if not con_fecha:
            st.info(
                "El reporte de correo trae el **total enviado por journey, sin fecha de envío**"
                + (f" (reporte del {corte:%d/%m/%Y})" if corte is not None else "")
                + ". Por eso aquí todo es acumulado, el «Periodo a consultar» no aplica y no hay gráficas por semana "
                  "ni fecha de agotamiento. Cuando el reporte traiga la columna **Send Date**, se activan solas.",
                icon=":material/event_busy:")
        aviso_remitentes_pendientes()
        st.markdown(
            f'<div class="leyenda"><span class="leyenda-titulo">Estado de los créditos de correo · {nombre_ambito}</span>'
            f'<span>{insignia("verde")} menos de {amarillo_pct:g} %</span>'
            f'<span>{insignia("amarillo")} desde {amarillo_pct:g} %</span>'
            f'<span>{insignia("rojo")} desde {rojo_pct:g} %</span>'
            f'<span class="leyenda-nota">1 crédito por correo enviado'
            + (f'; estado al {min(fin_c, fecha_max_c):%d/%m/%Y}, agotamiento con el ritmo de los últimos {REF_DIAS} días'
               if con_fecha else (f'; envíos del {rango[0]:%d/%m/%Y} al {corte:%d/%m/%Y}' if rango and corte is not None else ""))
            + '</span></div>', unsafe_allow_html=True)
        if unidad_sel:
            tarjetas = [tarjeta_correo(estado_correo(unidad_sel), "Asignados")]
        else:
            tarjetas = [tarjeta_correo(estado_correo(), "Adquiridos")] + [
                tarjeta_correo(estado_correo(u), "Asignados") for u in L.UNIDADES]
        por_fila = 4 if len(tarjetas) % 4 == 0 else 3
        for i in range(0, len(tarjetas), por_fila):
            fila_tarjetas(f"correo-{i}", tarjetas[i:i + por_fila])

        st.markdown("### Envíos" + (f" del {inicio_c:%d/%m/%Y} al {fin_c:%d/%m/%Y}" if con_fecha else " acumulados"))
        if con_fecha and fin_c > fecha_max_c:
            st.caption(f"Los datos de correo llegan hasta el {fecha_max_c:%d/%m/%Y}; después de esa fecha no hay envíos "
                       "reales todavía.")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Correos enviados", num(periodo_c["envios"].sum()))
        c2.metric("Gasto" + ESTIMADO_CORREO, txt_usd(usd_correo(float(periodo_c["creditos"].sum()))),
                  help=f"Créditos × {txt_precio(precio_correo())} USD por 1.000 créditos.")
        c3.metric("Journeys", num(periodo_c["journey"].nunique()))
        c4.metric("Remitentes", num(periodo_c["remitente"].nunique()))

        if periodo_c.empty:
            st.info("Sin envíos de correo en el periodo.", icon=":material/info:")
            return
        if con_fecha:
            semanal = periodo_c.assign(semana_inicio=periodo_c["fecha"] - pd.to_timedelta(periodo_c["fecha"].dt.weekday, unit="D"))
            tabla_s = semanal.groupby("semana_inicio", as_index=False)["envios"].sum().sort_values("semana_inicio")
            tabla_s["semana"] = tabla_s["semana_inicio"].apply(etiqueta_semana)
            st.markdown("### Correos por semana")
            grafica_barras(tabla_s, "semana", "envios", orden=list(tabla_s["semana"]), titulo_valor="Correos",
                           color=COLOR_CANAL["correo"])
            mensual = periodo_c.assign(mes=periodo_c["fecha"].dt.to_period("M").astype(str))
            tabla_m = mensual.groupby("mes", as_index=False)["envios"].sum().sort_values("mes")
            meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
            tabla_m["mes"] = tabla_m["mes"].apply(lambda m: f"{meses[int(m[5:7]) - 1]} {m[:4]}")
            st.markdown("### Correos por mes")
            grafica_barras(tabla_m, "mes", "envios", orden=list(tabla_m["mes"]), titulo_valor="Correos",
                           color=COLOR_CANAL["correo"])
        if not unidad_sel:
            st.markdown("### Gasto por unidad (USD)")
            por_u = periodo_c.groupby("unidad", as_index=False)["creditos"].sum()
            por_u["unidad"] = por_u["unidad"].map(NOMBRE_DESTINO_CORREO)
            por_u["usd"] = por_u["creditos"].apply(lambda v: usd_correo(v) or 0.0)
            total_u = float(por_u["usd"].sum()) or 1.0
            nota(f"Créditos de correo por el precio de 1.000 créditos{ESTIMADO_CORREO}. Total: {txt_usd(total_u)}.")
            grafica_barras(por_u, "unidad", "usd", horizontal=True, titulo_valor="USD", colores=COLOR_DESTINO_CORREO,
                           formato=lambda v: f"{txt_usd(v)} · " + pct(float(v) / total_u, 0))
        st.markdown("### Correos por remitente")
        por_r = periodo_c.groupby("remitente", as_index=False)["envios"].sum()
        grafica_barras(por_r, "remitente", "envios", horizontal=True, titulo_valor="Correos",
                       color=COLOR_CANAL["correo"])
        st.markdown("### Journeys con más correos")
        por_j = periodo_c.groupby("journey", as_index=False)["envios"].sum().nlargest(15, "envios")
        grafica_barras(por_j, "journey", "envios", horizontal=True, titulo_valor="Correos", color=COLOR_CANAL["correo"])

    if "Remitentes" in tabs_correo:
        with tabs_correo["Remitentes"]:
            st.markdown("### ¿De qué unidad es cada remitente?")
            nota("Cada correo se asigna a una unidad según su remitente (Email Sender Name). Elige la unidad de cada "
                 "uno, o «Ninguna unidad» si no es de un área que manejemos: en ese caso solo cuenta en el total. "
                 "Si aparece un remitente nuevo en el reporte, queda «Sin asignar» y el tablero avisa hasta que se asigne. "
                 "Para tener una unidad nueva, créala primero en Todos los canales → Configuración.")
            por_rem = (correo.groupby("remitente").agg(envios=("envios", "sum"), journeys=("journey", "nunique"))
                       .reset_index())
            opciones = [NOMBRE_DESTINO_CORREO[u] for u in L.UNIDADES] + [
                NOMBRE_DESTINO_CORREO[L.NINGUNA_UNIDAD], NOMBRE_DESTINO_CORREO[L.SIN_ASIGNAR]]
            actual = CFG_CORREO["remitentes"]
            por_rem["Unidad"] = por_rem["remitente"].map(
                lambda r: NOMBRE_DESTINO_CORREO.get(actual.get(r) if actual.get(r) in NOMBRE_DESTINO_CORREO else L.SIN_ASIGNAR))
            por_rem["_orden"] = (por_rem["Unidad"] != NOMBRE_DESTINO_CORREO[L.SIN_ASIGNAR]).astype(int)
            por_rem = por_rem.sort_values(["_orden", "envios"], ascending=[True, False]).drop(columns="_orden")
            editado = st.data_editor(
                por_rem.rename(columns={"remitente": "Remitente", "envios": "Correos", "journeys": "Journeys"}),
                key="editor_remitentes", hide_index=True, width="stretch", disabled=["Remitente", "Correos", "Journeys"],
                column_config={
                    "Correos": st.column_config.NumberColumn("Correos enviados", format="localized"),
                    "Unidad": st.column_config.SelectboxColumn("Unidad", options=opciones, required=True, width="medium"),
                })
            pendientes = int((editado["Unidad"] == NOMBRE_DESTINO_CORREO[L.SIN_ASIGNAR]).sum())
            if pendientes:
                st.caption(f"{pendientes} {'remitente sigue' if pendientes == 1 else 'remitentes siguen'} sin asignar.")
            if st.button("Guardar remitentes", type="primary", icon=":material/save:"):
                por_nombre = {v: k for k, v in NOMBRE_DESTINO_CORREO.items()}
                nuevos = dict(actual)
                cambios = []
                for _, r in editado.iterrows():
                    destino = por_nombre.get(r["Unidad"], L.SIN_ASIGNAR)
                    if destino == L.SIN_ASIGNAR:
                        nuevos.pop(r["Remitente"], None)
                    else:
                        nuevos[r["Remitente"]] = destino
                    if actual.get(r["Remitente"]) != nuevos.get(r["Remitente"]):
                        cambios.append(f"{r['Remitente']} → {r['Unidad']}")
                L.guardar_correo(RUTA_CONFIG, config, remitentes=nuevos)
                subir_y_registrar("Asigna remitentes de correo", "; ".join(cambios) or "sin cambios", RUTA_CONFIG)
                st.session_state.pop("editor_remitentes", None)
                st.cache_data.clear()
                st.toast("Remitentes guardados", icon=":material/check:")
                st.rerun()

    with tabs_correo["Journeys"]:
        st.markdown("### Journeys de correo")
        nota("Correos enviados por cada journey y contenido, con su remitente y su unidad"
             + ("" if con_fecha else ", acumulado del reporte") + ".")
        buscar = st.text_input("Buscar journey, contenido o remitente", key="buscar_correo")
        vista = periodo_c.copy()
        if buscar:
            b = buscar.lower()
            vista = vista[vista[["journey", "contenido", "remitente"]].apply(
                lambda f: b in " ".join(f.astype(str)).lower(), axis=1)]
        vista = vista.assign(Unidad=vista["unidad"].map(NOMBRE_DESTINO_CORREO),
                             USD=vista["creditos"].apply(lambda v: usd_correo(v) or 0.0),
                             Prueba=vista["prueba"].map({True: "Sí", False: ""}))
        columnas = ["journey", "contenido", "remitente", "Unidad", "envios", "USD", "Prueba"]
        st.dataframe(vista.sort_values("envios", ascending=False)[columnas], hide_index=True, width="stretch",
                     height=520, column_config={
                         "journey": st.column_config.TextColumn("Journey", width="medium"),
                         "contenido": st.column_config.TextColumn("Contenido", width="medium"),
                         "remitente": st.column_config.TextColumn("Remitente"),
                         "envios": st.column_config.NumberColumn("Correos (= créditos)", format="localized"),
                         "USD": st.column_config.NumberColumn("USD" + ESTIMADO_CORREO, format="%.2f")})
        st.caption(f"{num(len(vista))} filas · {num(vista['envios'].sum())} correos. Un journey puede aparecer "
                   "varias veces, una por cada contenido que envió.")

    if "Créditos" in tabs_correo:
        with tabs_correo["Créditos"]:
            st.markdown("### Créditos de correo adquiridos")
            nota("Compras de créditos de correo. Un correo estándar gasta 1 crédito, sin importar el país "
                 "(Salesforce Message Credits: Email Standard = 1). Si una compra tuvo otro precio, escríbelo en su fila.")
            compras_c = pd.DataFrame([{"Fecha": pd.to_datetime(c.get("fecha"), errors="coerce"),
                                       "Créditos": float(c.get("creditos") or 0),
                                       COL_PRECIO: c.get("precio_usd_1000"), "Nota": c.get("nota", "")}
                                      for c in CFG_CORREO["compras"]] or
                                     [{"Fecha": pd.NaT, "Créditos": 0.0, COL_PRECIO: None, "Nota": ""}])
            compras_ed = st.data_editor(
                compras_c, key="editor_compras_correo", num_rows="dynamic", hide_index=True, width="stretch",
                column_config={"Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                               "Créditos": st.column_config.NumberColumn("Créditos", min_value=0, format="localized"),
                               COL_PRECIO: st.column_config.NumberColumn(COL_PRECIO, min_value=0.0, format="%.3f"),
                               "Nota": st.column_config.TextColumn("Nota", width="large")})
            adquiridos = float(compras_ed["Créditos"].fillna(0).sum())
            st.markdown("### Asignación a unidades")
            nota("Cuántos créditos de correo le corresponden a cada unidad. Es la base del estado de cada unidad.")
            asig = pd.DataFrame([{"clave": u, "Unidad": NOMBRE_UNIDAD_APP[u],
                                  "Asignados": CFG_CORREO["unidades"].get(u, 0.0)} for u in L.UNIDADES])
            asig_ed = st.data_editor(asig, key="editor_asig_correo", hide_index=True, width="stretch",
                                     disabled=["Unidad"], column_order=["Unidad", "Asignados"],
                                     column_config={"Asignados": st.column_config.NumberColumn(
                                         "Créditos asignados", min_value=0, format="localized")})
            libre = adquiridos - float(asig_ed["Asignados"].fillna(0).sum())
            if libre < 0:
                st.error(f"Se asignaron {num(-libre)} créditos más de los adquiridos.", icon=":material/error:")
            else:
                st.caption(f"Adquiridos {num(adquiridos)} · sin asignar a unidades {num(libre)} "
                           "(lo usan los remitentes de «Ninguna unidad» o queda de reserva).")
            if st.button("Guardar créditos de correo", type="primary", icon=":material/save:"):
                compras_g = [{"fecha": f"{pd.Timestamp(r['Fecha']):%Y-%m-%d}" if pd.notna(r["Fecha"]) else "",
                              "creditos": float(r["Créditos"]), "nota": r["Nota"] or "",
                              **({"precio_usd_1000": float(r[COL_PRECIO])} if pd.notna(r[COL_PRECIO]) and r[COL_PRECIO] else {})}
                             for _, r in compras_ed.iterrows() if pd.notna(r["Créditos"]) and r["Créditos"] > 0]
                unidades_g = {r["clave"]: float(r["Asignados"] or 0) for _, r in asig_ed.iterrows()}
                L.guardar_correo(RUTA_CONFIG, config, compras=compras_g, unidades=unidades_g)
                subir_y_registrar("Guarda créditos de correo", f"Adquiridos {num(adquiridos)}; asignados " + ", ".join(
                    f"{NOMBRE_UNIDAD_APP[u]} {num(v)}" for u, v in unidades_g.items()), RUTA_CONFIG)
                for k in ("editor_compras_correo", "editor_asig_correo"):
                    st.session_state.pop(k, None)
                st.cache_data.clear()
                st.toast("Créditos de correo guardados", icon=":material/check:")
                st.rerun()
