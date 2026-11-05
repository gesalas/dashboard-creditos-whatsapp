"""
Personalización del tablero, guardada por persona (en perfiles.json, junto con la foto de perfil):
- el orden de las secciones del Resumen y cuáles se ocultan (se arrastran entre «Se muestran» y «Ocultas»);
- el color de cada unidad en las gráficas y tarjetas.

En el modo pruebas se guarda como la persona "modo pruebas", en la carpeta local.
"""

from __future__ import annotations

import re

import streamlit as st
from streamlit_sortables import sort_items

import acceso as A

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

# Colores predeterminados de las unidades (en el orden de config.json)
PALETA = ["#E0A21B", "#2E9A4E", "#2F6FD6", "#8E5BD0", "#D1495B", "#1C9AA0", "#6B7A8F", "#C26A2E"]

ESTILO_LISTA = """
.sortable-component {background: transparent; border: 0; padding: 0; gap: 14px; display: flex;}
.sortable-container {flex: 1 1 0;}
.sortable-container {background: #F7F8FB; border: 1px solid #E1E5EC; border-radius: 12px; padding: 10px; min-width: 0;}
.sortable-container-header {background: transparent; color: #1F3864; font-weight: 650; padding: 4px 6px 8px;}
.sortable-container-body {background: transparent; min-height: 60px;}
.sortable-item, .sortable-item:hover {background: #FFFFFF; color: #1B1F24; border: 1px solid #DDE2EA;
  border-radius: 8px; font-weight: 500; font-size: 15px; text-align: left; padding: 9px 14px; margin: 4px 0; cursor: grab;}
.sortable-item:hover {border-color: #1F3864;}
"""


def _vacio() -> dict:
    return {"orden": list(SECCIONES), "ocultas": [], "colores": {}}


def preferencias(ctx: dict) -> dict:
    """Preferencias guardadas de esta persona, completadas con lo predeterminado."""
    guardadas = (A.perfil(ctx["correo"]) or {}).get("preferencias") or {}
    p = _vacio()
    orden = [s for s in guardadas.get("orden", []) if s in SECCIONES]
    p["orden"] = orden + [s for s in SECCIONES if s not in orden]   # secciones nuevas al final
    p["ocultas"] = [s for s in guardadas.get("ocultas", []) if s in SECCIONES]
    p["colores"] = {u: c for u, c in (guardadas.get("colores") or {}).items() if re.fullmatch(r"#[0-9A-Fa-f]{6}", str(c))}
    return p


def colores_unidades(ctx: dict, unidades: list[str]) -> dict[str, str]:
    """Color de cada unidad (clave -> #RRGGBB): el que eligió la persona o el de la paleta."""
    propios = preferencias(ctx)["colores"]
    return {u: propios.get(u, PALETA[i % len(PALETA)]) for i, u in enumerate(unidades)}


def secciones_visibles(ctx: dict, equipo: bool) -> list[str]:
    p = preferencias(ctx)
    return [s for s in p["orden"] if s not in p["ocultas"] and (equipo or s not in SOLO_EQUIPO)]


def pagina(ctx: dict, nombres: dict[str, str]) -> None:
    st.markdown("## Personalizar tablero")
    st.caption("Estos cambios son solo para ti: cada persona ve el tablero con su propio orden y sus colores.")
    p = preferencias(ctx)
    version = st.session_state.setdefault("personalizar_version", 0)   # para reiniciar los controles

    st.markdown("### Secciones del Resumen")
    st.caption("Arrastra las secciones para cambiar el orden en que aparecen. Para ocultar una, pásala a la "
               "columna «Ocultas»." + ("" if ctx["admin"] else " Gasto por unidad y Consumo por unidad solo se "
                                                                 "ven en la vista del Equipo CRM."))
    visibles = [SECCIONES[s] for s in p["orden"] if s not in p["ocultas"]]
    ocultas = [SECCIONES[s] for s in p["orden"] if s in p["ocultas"]]
    resultado = sort_items([{"header": "Se muestran", "items": visibles}, {"header": "Ocultas", "items": ocultas}],
                           multi_containers=True, direction="vertical", custom_style=ESTILO_LISTA,
                           key=f"orden_secciones_{version}")
    por_nombre = {v: k for k, v in SECCIONES.items()}
    nuevo_visibles = [por_nombre[n] for n in resultado[0]["items"]]
    nuevo_ocultas = [por_nombre[n] for n in resultado[1]["items"]]

    st.markdown("### Colores de las unidades")
    st.caption("Se usan en las gráficas que comparan unidades y en las tarjetas de cada unidad.")
    actuales = colores_unidades(ctx, list(nombres))
    nuevos_colores = {}
    cols = st.columns(min(4, max(1, len(nombres))))
    for i, (u, nombre) in enumerate(nombres.items()):
        nuevos_colores[u] = cols[i % len(cols)].color_picker(nombre, actuales[u], key=f"color_{u}_{version}")

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    b1, b2, _ = st.columns([1, 1.4, 3])
    if b1.button("Guardar", type="primary", icon=":material/save:", width="stretch"):
        if not nuevo_visibles:
            st.error("Deja al menos una sección visible.")
            return
        prefs = {"orden": nuevo_visibles + nuevo_ocultas, "ocultas": nuevo_ocultas,
                 "colores": {u: c for u, c in nuevos_colores.items()}}
        A.guardar_perfil(ctx["correo"], lambda perfil: perfil.update(preferencias=prefs), "Personaliza el tablero")
        st.toast("Tablero personalizado", icon=":material/check:")
        st.session_state["pagina"] = None
        st.rerun()
    if b2.button("Volver a lo predeterminado", icon=":material/restart_alt:", width="stretch"):
        A.guardar_perfil(ctx["correo"], lambda perfil: perfil.pop("preferencias", None), "Restablece el tablero")
        st.session_state["personalizar_version"] = version + 1
        st.toast("Se restableció el orden y los colores", icon=":material/check:")
        st.rerun()
