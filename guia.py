"""
Guía rápida: 4 pasos que se muestran la primera vez que alguien entra al tablero (y cuando la pide desde el
menú de su perfil). Que ya la vio se guarda en su perfil.
"""

from __future__ import annotations

import streamlit as st

import acceso as A

PASOS = [
    ("Créditos y canales", ":material/forum:",
     "Cada mensaje que se envía desde Marketing Cloud gasta **créditos**. WhatsApp, Correo y SMS tienen cada uno "
     "su propia bolsa y su propio precio:\n\n"
     "- **WhatsApp:** según el país y el tipo de plantilla (Marketing es mucho más caro que Utility).\n"
     "- **Correo:** 1 crédito por correo.\n"
     "- **SMS:** según el país (en Colombia, 0,74 por SMS).\n\n"
     "Arriba eliges el canal; en WhatsApp también la línea (UCP u Outbound, que son bolsas separadas)."),
    ("El semáforo", ":material/traffic:",
     "Cada tarjeta compara lo **usado** con lo **adquirido** (o lo **asignado** a una unidad):\n\n"
     "- **Normal:** menos del 80 %.\n- **Atención:** desde el 80 %.\n- **Crítico:** desde el 95 %.\n\n"
     "El **agotamiento estimado** es el día en que se acabarían los créditos si se sigue enviando al mismo ritmo."),
    ("Tu vista", ":material/tune:",
     "En la barra lateral eliges la **Vista** (todo el Equipo CRM o una unidad) y el **Periodo** que quieres "
     "consultar. Las pestañas de arriba tienen la proyección, los journeys y el detalle.\n\n"
     "En el menú de tu perfil (arriba a la derecha) → **Personalizar tablero** puedes cambiar el tema, los colores, "
     "el tamaño del texto, el orden de las secciones y con qué canal y unidad abre el tablero."),
    ("Para el día a día", ":material/lightbulb:",
     "- **Mi cuenta:** tu foto y qué **alertas por correo** quieres recibir.\n"
     "- **Descargar PDF** (junto al título): guarda lo que estás viendo para una reunión.\n"
     "- **Enlaces útiles** (barra lateral): Marketing Cloud y las tablas de tarifas de Salesforce.\n"
     "- Al entrar verás **qué cambió desde tu última visita**.\n\n"
     "Puedes volver a abrir esta guía desde el menú de tu perfil."),
]


def _cerrar(ctx: dict) -> None:
    st.session_state.pop("guia_paso", None)
    st.session_state["guia_abierta"] = False
    st.session_state["guia_vista_sesion"] = True
    if not ctx.get("pruebas"):
        try:
            A.guardar_perfil(ctx["correo"], lambda p: p.update(guia_vista=True), "Guía vista")
        except Exception:
            pass


def _mover(delta: int) -> None:
    st.session_state["guia_paso"] = st.session_state.get("guia_paso", 0) + delta


@st.dialog("Guía rápida", width="large", dismissible=False)
def _dialogo(ctx: dict) -> None:
    paso = st.session_state.get("guia_paso", 0)
    titulo, icono, texto = PASOS[paso]
    puntos = "".join(f'<span class="guia-punto{" activo" if i == paso else ""}"></span>' for i in range(len(PASOS)))
    st.markdown(f'<div class="guia-pasos">{puntos}<span class="guia-n">Paso {paso + 1} de {len(PASOS)}</span></div>',
                unsafe_allow_html=True)
    st.markdown(f"#### {titulo}")
    st.markdown(texto)
    c1, c2, c3 = st.columns([1, 1, 1])
    c1.button("Saltar guía", on_click=_cerrar, args=(ctx,), width="stretch", key="guia_saltar")
    c2.button("Anterior", on_click=_mover, args=(-1,), disabled=paso == 0, width="stretch", key="guia_ant",
              icon=":material/arrow_back:")
    if paso < len(PASOS) - 1:
        c3.button("Siguiente", on_click=_mover, args=(1,), type="primary", width="stretch", key="guia_sig",
                  icon=":material/arrow_forward:")
    else:
        c3.button("Empezar", on_click=_cerrar, args=(ctx,), type="primary", width="stretch", key="guia_fin",
                  icon=":material/check:")


CSS = """<style>
.guia-pasos {display: flex; align-items: center; gap: 6px; margin-bottom: 4px;}
.guia-punto {width: 26px; height: 6px; border-radius: 999px; background: var(--t-linea);}
.guia-punto.activo {background: var(--t-acento);}
.guia-n {margin-left: 8px; font-size: 0.78rem; color: var(--t-texto-ter);}
</style>"""


def abrir() -> None:
    st.session_state["guia_abierta"] = True
    st.session_state["guia_paso"] = 0
    st.session_state["pagina"] = None


def mostrar(ctx: dict, hay_otro_dialogo: bool = False) -> None:
    """La muestra la primera vez (no en el modo pruebas) o cuando la persona la pide."""
    st.markdown(CSS, unsafe_allow_html=True)
    if hay_otro_dialogo:
        return
    primera = (not ctx.get("pruebas") and not st.session_state.get("guia_vista_sesion")
               and not (A.perfil(ctx["correo"]) or {}).get("guia_vista"))
    if st.session_state.get("guia_abierta") or primera:
        st.session_state["guia_abierta"] = True
        _dialogo(ctx)
