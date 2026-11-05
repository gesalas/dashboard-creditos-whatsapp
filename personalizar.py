"""
Personalización del tablero, guardada por persona (en perfiles.json, junto con la foto de perfil):
- el tema (claro, oscuro, carbón, otoño, vino tinto o alto contraste) y, encima, el color principal y los de
  Marketing y Utility;
- el color de cada unidad en las gráficas y tarjetas;
- el orden de las secciones del Resumen y cuáles se ocultan (se arrastran entre «Se muestran» y «Ocultas»).

Mientras la persona está en Personalizar tablero, lo que elige se ve de una vez (vista previa); se guarda con
«Guardar». Solo se guardan los colores que cambió frente al tema, así que si cambia de tema más adelante,
conserva lo que eligió a propósito (por ejemplo, Mercadeo en amarillo).

En el modo pruebas se guarda como la persona "modo pruebas", en la carpeta local.
"""

from __future__ import annotations

import streamlit as st
from streamlit_sortables import sort_items

import acceso as A
import temas as T

# Secciones del Resumen, en el orden predeterminado
SECCIONES = {
    "estado": "Estado de los créditos",
    "periodo": "Consumo del periodo",
    "semana": "Consumo por semana",
    "mes": "Consumo por mes",
    "gasto_unidad": "Gasto por unidad (USD)",
    "unidades": "Consumo por unidad",
    "paises": "Países con mayor consumo",
}
SOLO_EQUIPO = {"gasto_unidad", "unidades"}   # comparan unidades: solo en la vista del Equipo CRM
PREVIA = ("p_tema", "pc_", "pu_")            # claves de la vista previa en session_state


def _vacio() -> dict:
    return {"orden": list(SECCIONES), "ocultas": [], "colores": {}, "tema": T.PREDETERMINADO, "colores_tema": {}}


def preferencias(ctx: dict) -> dict:
    """Preferencias guardadas de esta persona, completadas con lo predeterminado."""
    guardadas = (A.perfil(ctx["correo"]) or {}).get("preferencias") or {}
    p = _vacio()
    orden = [s for s in guardadas.get("orden", []) if s in SECCIONES]
    p["orden"] = orden + [s for s in SECCIONES if s not in orden]   # secciones nuevas al final
    p["ocultas"] = [s for s in guardadas.get("ocultas", []) if s in SECCIONES]
    p["colores"] = {u: c.upper() for u, c in (guardadas.get("colores") or {}).items() if T.es_hex(c)}
    p["tema"] = guardadas.get("tema") if guardadas.get("tema") in T.TEMAS else T.PREDETERMINADO
    p["colores_tema"] = {k: c.upper() for k, c in (guardadas.get("colores_tema") or {}).items()
                         if k in T.PERSONALIZABLES and T.es_hex(c)}
    return p


def _en_pagina() -> bool:
    return st.session_state.get("pagina") == "personalizar"


def _limpiar_previa() -> None:
    for k in [k for k in st.session_state.keys() if str(k).startswith(PREVIA)]:
        del st.session_state[k]


def tema_actual(ctx: dict) -> dict:
    """Tema con el que se dibuja el tablero: el guardado o, en Personalizar, el que se está probando."""
    p = preferencias(ctx)
    if not _en_pagina():
        _limpiar_previa()
        return T.resolver(p["tema"], p["colores_tema"])
    clave = st.session_state.get("p_tema") or p["tema"]
    propios = dict(p["colores_tema"]) if clave == p["tema"] else {}
    v = st.session_state.get("personalizar_version", 0)
    for campo in T.PERSONALIZABLES:
        valor = st.session_state.get(f"pc_{campo}_{clave}_{v}")
        if T.es_hex(valor):
            propios[campo] = valor
    return T.resolver(clave, propios)


def colores_unidades(ctx: dict, unidades: list[str], tema: dict) -> dict[str, str]:
    """Color de cada unidad (clave -> #RRGGBB): el que eligió la persona o el de la paleta del tema."""
    propios = preferencias(ctx)["colores"]
    paleta = tema["unidades"]
    colores = {u: propios.get(u, paleta[i % len(paleta)]) for i, u in enumerate(unidades)}
    if _en_pagina():
        v = st.session_state.get("personalizar_version", 0)
        for u in unidades:
            valor = st.session_state.get(f"pu_{u}_{tema['clave']}_{v}")
            if T.es_hex(valor):
                colores[u] = valor.upper()
    return colores


def secciones_visibles(ctx: dict, equipo: bool) -> list[str]:
    p = preferencias(ctx)
    return [s for s in p["orden"] if s not in p["ocultas"] and (equipo or s not in SOLO_EQUIPO)]


def estilo_lista(t: dict) -> str:
    return f"""
.sortable-component {{background: transparent; border: 0; padding: 0; gap: 14px; display: flex;}}
.sortable-container {{flex: 1 1 0; background: {t['superficie2']}; border: 1px solid {t['borde']}; border-radius: 12px;
  padding: 10px; min-width: 0;}}
.sortable-container-header {{background: transparent; color: {t['primario']}; font-weight: 650; padding: 4px 6px 8px;}}
.sortable-container-body {{background: transparent; min-height: 60px;}}
.sortable-item, .sortable-item:hover {{background: {t['superficie']}; color: {t['texto']}; border: 1px solid {t['borde_fuerte']};
  border-radius: 8px; font-weight: 500; font-size: 15px; text-align: left; padding: 9px 14px; margin: 4px 0; cursor: grab;}}
.sortable-item:hover {{border-color: {t['primario']};}}
body {{background: transparent; color: {t['texto']};}}
"""


def _elegir_tema(clave: str) -> None:
    st.session_state["p_tema"] = clave


def pagina(ctx: dict, nombres: dict[str, str], tema: dict) -> None:
    st.markdown("## Personalizar tablero")
    st.caption("Estos cambios son solo para ti: cada persona ve el tablero con su propio tema, orden y colores. "
               "Lo que elijas se ve de una vez; para conservarlo, dale «Guardar» al final.")
    p = preferencias(ctx)
    version = st.session_state.setdefault("personalizar_version", 0)   # para reiniciar los controles
    clave = tema["clave"]

    # ---- Tema
    st.markdown("### Tema")
    cols = st.columns(3)
    for i, (k, base) in enumerate(T.TEMAS.items()):
        with cols[i % 3], st.container(border=True, key=f"tema-{k}"):
            st.markdown(T.muestra(T.resolver(k)), unsafe_allow_html=True)
            st.markdown(f"**{base['nombre']}**" + ("  · en uso" if k == clave else ""))
            st.caption(base["descripcion"])
            st.button("Elegido" if k == clave else "Usar este tema", key=f"usar_{k}", width="stretch",
                      type="primary" if k == clave else "secondary", disabled=k == clave,
                      on_click=_elegir_tema, args=(k,))

    # ---- Colores del tema
    st.markdown("### Colores")
    st.caption("Parten del tema elegido. Cámbialos si quieres, por ejemplo, otro color para Marketing o Utility.")
    base = T.resolver(clave)
    c = st.columns(4)
    nuevos_tema = {}
    for i, (campo, etiqueta) in enumerate(T.PERSONALIZABLES.items()):
        nuevos_tema[campo] = c[i].color_picker(etiqueta, tema[campo], key=f"pc_{campo}_{clave}_{version}")

    st.markdown("**Unidades**")
    actuales = colores_unidades(ctx, list(nombres), tema)
    nuevos_unidades = {}
    cu = st.columns(min(4, max(1, len(nombres))))
    for i, (u, nombre) in enumerate(nombres.items()):
        nuevos_unidades[u] = cu[i % len(cu)].color_picker(nombre, actuales[u], key=f"pu_{u}_{clave}_{version}")

    # ---- Secciones
    st.markdown("### Secciones del Resumen")
    st.caption("Arrastra las secciones para cambiar el orden en que aparecen. Para ocultar una, pásala a la "
               "columna «Ocultas»." + ("" if ctx["admin"] else " Gasto por unidad y Consumo por unidad solo se "
                                                                 "ven en la vista del Equipo CRM."))
    visibles = [SECCIONES[s] for s in p["orden"] if s not in p["ocultas"]]
    ocultas = [SECCIONES[s] for s in p["orden"] if s in p["ocultas"]]
    resultado = sort_items([{"header": "Se muestran", "items": visibles}, {"header": "Ocultas", "items": ocultas}],
                           multi_containers=True, direction="vertical", custom_style=estilo_lista(tema),
                           key=f"orden_secciones_{version}_{clave}")
    por_nombre = {v: k for k, v in SECCIONES.items()}
    nuevo_visibles = [por_nombre[n] for n in resultado[0]["items"]]
    nuevo_ocultas = [por_nombre[n] for n in resultado[1]["items"]]

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    b1, b2, b3, _ = st.columns([1, 1, 1.4, 2])
    if b1.button("Guardar", type="primary", icon=":material/save:", width="stretch"):
        if not nuevo_visibles:
            st.error("Deja al menos una sección visible.")
            return
        paleta = base["unidades"]
        prefs = {
            "tema": clave,
            # solo lo que cambió frente al tema
            "colores_tema": {k: v.upper() for k, v in nuevos_tema.items() if v.upper() != base[k].upper()},
            "colores": {u: v.upper() for i, (u, v) in enumerate(nuevos_unidades.items())
                        if v.upper() != paleta[i % len(paleta)].upper()},
            "orden": nuevo_visibles + nuevo_ocultas, "ocultas": nuevo_ocultas,
        }
        A.guardar_perfil(ctx["correo"], lambda perfil: perfil.update(preferencias=prefs), "Personaliza el tablero")
        _limpiar_previa()
        st.toast(f"Tablero personalizado · tema {T.TEMAS[clave]['nombre']}", icon=":material/check:")
        st.session_state["pagina"] = None
        st.rerun()
    if b2.button("Descartar", icon=":material/undo:", width="stretch",
                 help="Vuelve a lo que tenías guardado, sin guardar lo que estabas probando."):
        _limpiar_previa()
        st.session_state["personalizar_version"] = version + 1
        st.rerun()
    if b3.button("Volver a lo predeterminado", icon=":material/restart_alt:", width="stretch"):
        A.guardar_perfil(ctx["correo"], lambda perfil: perfil.pop("preferencias", None), "Restablece el tablero")
        _limpiar_previa()
        st.session_state["personalizar_version"] = version + 1
        st.toast("Se restableció el tema, los colores y el orden", icon=":material/check:")
        st.rerun()
