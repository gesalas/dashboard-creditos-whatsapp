"""
«Desde tu última visita»: al entrar, compara cómo estaban los créditos la vez anterior con cómo están ahora
(datos nuevos, créditos usados, cambios de estado, correos, remitentes nuevos) y lo muestra en un recuadro.
La foto de cada visita se guarda en el perfil de la persona (una vez por sesión).
"""

from __future__ import annotations

import html

import streamlit as st

import acceso as A

ORDEN_ESTADO = ["sin_definir", "verde", "amarillo", "rojo"]
NOMBRE_ESTADO = {"verde": "Normal", "amarillo": "Atención", "rojo": "Crítico", "sin_definir": "Sin asignación"}


def _num(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


def _pct(v: float | None) -> str:
    return "-" if v is None else f"{v * 100:.1f} %".replace(".", ",")


def _fecha(texto: str) -> str:
    try:
        import pandas as pd
        return pd.Timestamp(texto).tz_convert("America/Bogota").strftime("%d/%m/%Y, %I:%M %p").replace(
            "AM", "a. m.").replace("PM", "p. m.")
    except Exception:
        return texto


def comparar(antes: dict, ahora: dict) -> list[str]:
    """Frases con lo que cambió (vacía si nada cambió)."""
    cambios = []
    if ahora.get("datos_w") and antes.get("datos_w") and ahora["datos_w"] != antes["datos_w"]:
        cambios.append(f"Llegaron datos de WhatsApp hasta el <b>{ahora['datos_w']}</b> (antes llegaban hasta el "
                       f"{antes['datos_w']}).")
    usado = ahora.get("usado_w", 0) - antes.get("usado_w", 0)
    if usado > 0.5:
        cambios.append(f"Se usaron <b>{_num(usado)}</b> créditos de WhatsApp: el total pasó de "
                       f"{_pct(antes.get('uso_w'))} a <b>{_pct(ahora.get('uso_w'))}</b>.")
    for nombre, e in (ahora.get("estados") or {}).items():
        previo = (antes.get("estados") or {}).get(nombre)
        if previo and previo != e and e in ORDEN_ESTADO and previo in ORDEN_ESTADO:
            peor = ORDEN_ESTADO.index(e) > ORDEN_ESTADO.index(previo)
            cambios.append(f"{html.escape(nombre)} pasó de {NOMBRE_ESTADO[previo]} a "
                           f"<b class=\"{'nov-peor' if peor else 'nov-mejor'}\">{NOMBRE_ESTADO[e]}</b>.")
    correos = ahora.get("correos", 0) - antes.get("correos", 0)
    if correos > 0.5:
        cambios.append(f"Se enviaron <b>{_num(correos)}</b> correos más (según el último reporte de correo).")
    nuevos = sorted(set(ahora.get("remitentes_pend") or []) - set(antes.get("remitentes_pend") or []))
    if nuevos:
        cambios.append(f"{len(nuevos)} {'remitente nuevo' if len(nuevos) == 1 else 'remitentes nuevos'} de correo sin "
                       f"unidad: {html.escape(', '.join(nuevos[:4]))}{'…' if len(nuevos) > 4 else ''}.")
    return cambios


def mostrar(ctx: dict, foto: dict) -> None:
    """Muestra el recuadro (si hubo cambios) y guarda la foto de esta visita (una vez por sesión)."""
    if st.session_state.get("nov_cerrado"):
        return
    if "nov_antes" not in st.session_state:
        perfil = A.perfil(ctx["correo"]) or {}
        st.session_state["nov_antes"] = perfil.get("ultima_visita")
        try:
            A.guardar_perfil(ctx["correo"], lambda p: p.update(ultima_visita={"fecha": A.iso(), "datos": foto}),
                             "Última visita")
        except Exception:
            pass
    antes = st.session_state.get("nov_antes")
    if not antes or not antes.get("datos"):
        return
    cambios = comparar(antes["datos"], foto)
    if not cambios:
        return
    with st.container(key="novedades", border=True):
        c1, c2 = st.columns([12, 1], vertical_alignment="top")
        c1.markdown(f'<div class="nov-titulo">Desde tu última visita ({_fecha(antes.get("fecha", ""))})</div>'
                    + "<ul class='nov-lista'>" + "".join(f"<li>{c}</li>" for c in cambios[:6]) + "</ul>",
                    unsafe_allow_html=True)
        if c2.button("", icon=":material/close:", key="nov_cerrar", help="Ocultar", type="tertiary"):
            st.session_state["nov_cerrado"] = True
            st.rerun()


CSS = """<style>
.st-key-novedades {background: var(--t-acento-suave); border-color: var(--t-acento) !important; margin: 0.4rem 0 0.6rem;}
.nov-titulo {font-weight: 650; color: var(--t-texto); margin-bottom: 4px;}
.nov-lista {margin: 0; padding-left: 1.1rem; color: var(--t-texto); font-size: 0.92rem;}
.nov-lista li {margin: 2px 0;}
.nov-peor {color: var(--t-semaforo-rojo, #B3261E);}
.nov-mejor {color: var(--t-verde-borde);}
</style>"""
