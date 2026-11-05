"""
Personalización del tablero, guardada por persona (en perfiles.json, junto con la foto de perfil):
- el tema (Javeriana, oscuros, claros de color, accesibilidad...) y, encima, el color principal, el de acento,
  Marketing y Utility;
- el color de cada unidad en las gráficas y tarjetas;
- el orden de las secciones del Resumen y cuáles se ocultan (se arrastran entre «Se muestran» y «Ocultas»).

Los colores propios se guardan POR TEMA: si en «Javeriana» Mercadeo es rosado y luego se elige «Carbón», Mercadeo
toma el color de Carbón (o el que la persona haya elegido antes dentro de Carbón). Al volver a «Javeriana»,
vuelve a ser rosado.

Mientras la persona está en Personalizar tablero, lo que elige se ve de una vez (borrador). Si sale de la página
sin guardar, el tablero le pregunta si quiere guardar, descartar o seguir editando.

En el modo pruebas se guarda como la persona "modo pruebas", en la carpeta local.
"""

from __future__ import annotations

import copy

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
PAGINA = "personalizar"

# Cómo se ve: tamaño del texto, estilo de las tarjetas y espaciado (para quien se sienta abrumado o use zoom)
VISTA = {
    "texto": {"titulo": "Tamaño del texto", "opciones": {"normal": "Normal", "grande": "Grande", "muy_grande": "Muy grande"},
              "defecto": "normal"},
    "tarjetas": {"titulo": "Tarjetas de estado", "opciones": {"color": "Con color de fondo", "sobrio": "Sobrias (solo borde)"},
                 "defecto": "color"},
    "densidad": {"titulo": "Espaciado", "opciones": {"comodo": "Cómodo", "compacto": "Compacto"}, "defecto": "comodo"},
}
VISTA_DEFECTO = {k: v["defecto"] for k, v in VISTA.items()}

# Con qué abre el tablero cada persona
CANALES_INICIO = {"whatsapp": "WhatsApp", "correo": "Correo", "sms": "SMS", "todos": "Todos los canales"}
INICIO_DEFECTO = {"canal": "whatsapp", "unidad": ""}   # unidad "" = la primera que pueda ver


# ---------------------------------------------------------------------------
# Preferencias guardadas
# ---------------------------------------------------------------------------

def preferencias(ctx: dict) -> dict:
    """Preferencias guardadas, completadas con lo predeterminado.
    {"tema", "orden", "ocultas", "personal": {tema: {"colores_tema": {...}, "colores": {unidad: color}}}}"""
    g = (A.perfil(ctx["correo"]) or {}).get("preferencias") or {}
    tema = g.get("tema") if g.get("tema") in T.TEMAS else T.PREDETERMINADO
    orden = [s for s in g.get("orden", []) if s in SECCIONES]
    personal = {}
    for k, v in (g.get("personal") or {}).items():
        if k in T.TEMAS and isinstance(v, dict):
            personal[k] = {"colores_tema": {c: x.upper() for c, x in (v.get("colores_tema") or {}).items()
                                            if c in T.PERSONALIZABLES and T.es_hex(x)},
                           "colores": {u: x.upper() for u, x in (v.get("colores") or {}).items() if T.es_hex(x)}}
    # Formato anterior: los colores propios eran de todos los temas; ahora son del tema que estaba guardado
    if (g.get("colores_tema") or g.get("colores")) and tema not in personal:
        personal[tema] = {"colores_tema": {c: x.upper() for c, x in (g.get("colores_tema") or {}).items()
                                           if c in T.PERSONALIZABLES and T.es_hex(x)},
                          "colores": {u: x.upper() for u, x in (g.get("colores") or {}).items() if T.es_hex(x)}}
    vista = {k: (g.get("vista") or {}).get(k) if (g.get("vista") or {}).get(k) in VISTA[k]["opciones"] else d
             for k, d in VISTA_DEFECTO.items()}
    ini = g.get("inicio") or {}
    inicio = {"canal": ini.get("canal") if ini.get("canal") in CANALES_INICIO else INICIO_DEFECTO["canal"],
              "unidad": str(ini.get("unidad") or "")}
    return {"tema": tema, "orden": orden + [s for s in SECCIONES if s not in orden],
            "ocultas": [s for s in g.get("ocultas", []) if s in SECCIONES], "personal": personal, "vista": vista,
            "inicio": inicio}


def _propios(prefs: dict, tema: str) -> dict:
    return prefs["personal"].get(tema) or {"colores_tema": {}, "colores": {}}


def _guardado_como_borrador(prefs: dict) -> dict:
    p = _propios(prefs, prefs["tema"])
    return {"tema": prefs["tema"], "colores_tema": dict(p["colores_tema"]), "colores": dict(p["colores"]),
            "orden": list(prefs["orden"]), "ocultas": list(prefs["ocultas"]), "vista": dict(prefs["vista"]),
            "inicio": dict(prefs["inicio"])}


# ---------------------------------------------------------------------------
# Borrador (lo que la persona está probando)
# ---------------------------------------------------------------------------

def _en_pagina() -> bool:
    return st.session_state.get("pagina") == PAGINA


def _version() -> int:
    return st.session_state.setdefault("personalizar_version", 0)


def _clave_color(campo: str) -> str:
    return f"pc_{campo}_{_version()}"


def _clave_unidad(u: str) -> str:
    return f"pu_{u}_{_version()}"


def _borrador_desde_controles(ctx: dict) -> dict:
    """Borrador base más lo que hay en los controles de la página (colores y orden de secciones)."""
    base = copy.deepcopy(st.session_state.get("p_borrador") or _guardado_como_borrador(preferencias(ctx)))
    tema = T.resolver(base["tema"], base["colores_tema"])
    for campo in T.PERSONALIZABLES:
        v = st.session_state.get(_clave_color(campo))
        if T.es_hex(v):
            if v.upper() != T.resolver(base["tema"])[campo].upper():
                base["colores_tema"][campo] = v.upper()
            else:
                base["colores_tema"].pop(campo, None)
    paleta = tema["unidades"]
    for i, u in enumerate(st.session_state.get("p_unidades") or []):
        v = st.session_state.get(_clave_unidad(u))
        if T.es_hex(v):
            if v.upper() != paleta[i % len(paleta)].upper():
                base["colores"][u] = v.upper()
            else:
                base["colores"].pop(u, None)
    if st.session_state.get("p_secciones"):
        base["orden"], base["ocultas"] = copy.deepcopy(st.session_state["p_secciones"])
    base.setdefault("vista", dict(VISTA_DEFECTO))
    base.setdefault("inicio", dict(INICIO_DEFECTO))
    for campo in INICIO_DEFECTO:
        v = st.session_state.get(f"pi_{campo}_{_version()}")
        if v is not None:
            base["inicio"][campo] = v
    for campo in VISTA:
        v = st.session_state.get(f"pv_{campo}_{_version()}")
        if v in VISTA[campo]["opciones"]:
            base["vista"][campo] = v
    return base


def _normal(b: dict) -> tuple:
    return (b["tema"], tuple(sorted(b["colores_tema"].items())), tuple(sorted(b["colores"].items())),
            tuple(b["orden"]), tuple(b["ocultas"]), tuple(sorted((b.get("vista") or VISTA_DEFECTO).items())),
            tuple(sorted((b.get("inicio") or INICIO_DEFECTO).items())))


def hay_cambios(ctx: dict) -> bool:
    return _normal(_borrador_desde_controles(ctx)) != _normal(_guardado_como_borrador(preferencias(ctx)))


def _limpiar_borrador() -> None:
    for k in [k for k in st.session_state.keys() if str(k).startswith(("pc_", "pu_", "pv_", "pi_", "p_borrador", "p_secciones"))]:
        del st.session_state[k]
    st.session_state["personalizar_version"] = _version() + 1


def _borrador_vigente(ctx: dict) -> dict:
    """El borrador con el que se dibuja el tablero en este momento."""
    if _en_pagina():
        return _borrador_desde_controles(ctx)
    if st.session_state.get("p_pendiente"):
        return st.session_state["p_pendiente"]
    if st.session_state.get("p_borrador") is not None:
        # Acaba de salir de Personalizar: si dejó cambios sin guardar, se guardan aparte para preguntarle
        borrador = _borrador_desde_controles(ctx)
        if hay_cambios(ctx):
            st.session_state["p_pendiente"] = borrador
        _limpiar_borrador()
        if st.session_state.get("p_pendiente"):
            return st.session_state["p_pendiente"]
    return _guardado_como_borrador(preferencias(ctx))


def tema_actual(ctx: dict) -> dict:
    """Tema con el que se dibuja el tablero: el guardado o el que se está probando."""
    b = _borrador_vigente(ctx)
    return T.resolver(b["tema"], b["colores_tema"])


def colores_unidades(ctx: dict, unidades: list[str], tema: dict) -> dict[str, str]:
    """Color de cada unidad (clave -> #RRGGBB): el que la persona eligió en este tema o el de la paleta del tema."""
    st.session_state["p_unidades"] = list(unidades)
    b = _borrador_vigente(ctx)
    paleta = tema["unidades"]
    return {u: b["colores"].get(u, paleta[i % len(paleta)]) for i, u in enumerate(unidades)}


def css_vista(ctx: dict) -> str:
    """Estilos del tamaño de texto, las tarjetas y el espaciado elegidos."""
    v = _borrador_vigente(ctx).get("vista") or VISTA_DEFECTO
    reglas = []
    escala = {"normal": None, "grande": "112.5%", "muy_grande": "125%"}[v["texto"]]
    if escala:
        reglas.append(f"html {{font-size: {escala};}} .stApp p, .stApp li, .stApp label {{font-size: 1rem;}}"
                      ".semaforo-titulo {font-size: 1.05rem;} .cifra-etiqueta {font-size: 0.85rem;}"
                      ".cifra-valor {font-size: 1.15rem;}")
    if v["tarjetas"] == "sobrio":
        reglas.append(".semaforo-item {background: var(--t-superficie) !important; border-top-color: var(--t-borde) !important;"
                      "border-right-color: var(--t-borde) !important; border-bottom-color: var(--t-borde) !important;}")
    if v["densidad"] == "compacto":
        reglas.append(".block-container {padding-top: 1.6rem;} [data-testid='stVerticalBlock'] {gap: 0.55rem;}"
                      ".semaforo-item {padding: 12px 14px 10px 14px;} h3 {margin-top: 0.8rem !important;}"
                      "[class*='st-key-lado-'] {padding: 9px 10px;}")
    return f"<style>{''.join(reglas)}</style>" if reglas else ""


def inicio(ctx: dict) -> dict:
    """Canal y unidad con los que abre el tablero (lo guardado)."""
    return preferencias(ctx)["inicio"]


def secciones_visibles(ctx: dict, equipo: bool) -> list[str]:
    b = _borrador_vigente(ctx)
    return [s for s in b["orden"] if s not in b["ocultas"] and (equipo or s not in SOLO_EQUIPO)]


# ---------------------------------------------------------------------------
# Guardar, descartar y la pregunta al salir
# ---------------------------------------------------------------------------

def guardar(ctx: dict, borrador: dict) -> None:
    def cambio(perfil: dict) -> None:
        actual = perfil.get("preferencias") or {}
        personal = dict(preferencias(ctx)["personal"])
        personal[borrador["tema"]] = {"colores_tema": borrador["colores_tema"], "colores": borrador["colores"]}
        actual = {"tema": borrador["tema"], "orden": borrador["orden"], "ocultas": borrador["ocultas"],
                  "vista": borrador.get("vista") or dict(VISTA_DEFECTO),
                  "inicio": borrador.get("inicio") or dict(INICIO_DEFECTO),
                  "personal": {k: v for k, v in personal.items() if v["colores_tema"] or v["colores"]}}
        perfil["preferencias"] = actual
    A.guardar_perfil(ctx["correo"], cambio, "Personaliza el tablero")


def _al_guardar(ctx: dict) -> None:
    guardar(ctx, _borrador_desde_controles(ctx))
    _limpiar_borrador()
    st.session_state["pagina"] = None
    st.session_state["p_aviso"] = "Tablero personalizado"


def _al_descartar() -> None:
    _limpiar_borrador()


@st.dialog("Tienes cambios sin guardar", dismissible=False)
def dialogo_pendiente(ctx: dict) -> None:
    b = st.session_state["p_pendiente"]
    st.markdown(f"Probaste el tema **{T.TEMAS[b['tema']]['nombre']}** y otros ajustes en Personalizar tablero, "
                "pero no los guardaste. ¿Qué quieres hacer?")
    c1, c2, c3 = st.columns(3)
    if c1.button("Guardar", type="primary", icon=":material/save:", width="stretch"):
        guardar(ctx, b)
        st.session_state.pop("p_pendiente", None)
        st.session_state["p_aviso"] = "Cambios guardados"
        st.rerun()
    if c2.button("Descartar", icon=":material/undo:", width="stretch"):
        st.session_state.pop("p_pendiente", None)
        st.rerun()
    if c3.button("Seguir editando", icon=":material/edit:", width="stretch"):
        st.session_state["p_borrador"] = st.session_state.pop("p_pendiente")
        st.session_state["personalizar_version"] = _version() + 1
        st.session_state["pagina"] = PAGINA
        st.rerun()


def avisos(ctx: dict) -> None:
    """Pregunta por los cambios sin guardar y muestra el aviso de guardado (se llama en cada ejecución)."""
    if st.session_state.get("p_pendiente") and not _en_pagina():
        dialogo_pendiente(ctx)
    aviso = st.session_state.pop("p_aviso", None)
    if aviso:
        st.toast(aviso, icon=":material/check:")


# ---------------------------------------------------------------------------
# La página
# ---------------------------------------------------------------------------

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


def _elegir_tema(ctx: dict, clave: str) -> None:
    """Cambia el tema del borrador. Los colores pasan a ser los de ese tema (o los que la persona eligió antes
    dentro de él); el orden de las secciones se conserva."""
    b = _borrador_desde_controles(ctx)
    propios = _propios(preferencias(ctx), clave)
    st.session_state["p_borrador"] = {"tema": clave, "colores_tema": dict(propios["colores_tema"]),
                                      "colores": dict(propios["colores"]), "orden": b["orden"], "ocultas": b["ocultas"],
                                      "vista": b.get("vista") or dict(VISTA_DEFECTO),
                                      "inicio": b.get("inicio") or dict(INICIO_DEFECTO)}
    st.session_state["personalizar_version"] = _version() + 1


def _restablecer(ctx: dict) -> None:
    A.guardar_perfil(ctx["correo"], lambda perfil: perfil.pop("preferencias", None), "Restablece el tablero")
    _limpiar_borrador()
    st.session_state["p_aviso"] = "Se restableció el tema, los colores y el orden"


def pagina(ctx: dict, nombres: dict[str, str], tema: dict) -> None:
    if st.session_state.get("p_borrador") is None:
        st.session_state["p_borrador"] = _guardado_como_borrador(preferencias(ctx))
    b = _borrador_desde_controles(ctx)
    clave = b["tema"]
    v = _version()

    st.markdown("""<style>
.st-key-barra-guardar {position: sticky; top: 3.4rem; z-index: 40; background: var(--t-fondo);
  border: 1px solid var(--t-borde); border-radius: 12px; padding: 10px 14px; box-shadow: var(--t-sombra);}
.barra-estado {font-size: 0.9rem; color: var(--t-texto-sec);}
.barra-estado.con-cambios {color: var(--t-amarillo-borde);}
[class*="st-key-tema-"] [data-testid="stCaptionContainer"] {min-height: 2.6em;}
</style>""", unsafe_allow_html=True)
    st.markdown("## Personalizar tablero")
    st.caption("Estos cambios son solo para ti. Lo que elijas se ve de una vez en todo el tablero.")

    # Barra fija con el estado y los botones: siempre a la vista, sin tener que bajar hasta el final
    cambios = hay_cambios(ctx)
    with st.container(key="barra-guardar"):
        c0, c1, c2, c3 = st.columns([3, 1, 1, 1.5], vertical_alignment="center")
        c0.markdown(
            f'<div class="barra-estado {"con-cambios" if cambios else ""}">'
            + ("<b>Tienes cambios sin guardar.</b> Si sales de esta página, te preguntaremos si quieres guardarlos."
               if cambios else f"Todo guardado · tema <b>{T.TEMAS[clave]['nombre']}</b>") + "</div>",
            unsafe_allow_html=True)
        c1.button("Guardar", type="primary", icon=":material/save:", width="stretch", disabled=not cambios,
                  on_click=_al_guardar, args=(ctx,), key="p_guardar")
        c2.button("Descartar", icon=":material/undo:", width="stretch", disabled=not cambios,
                  on_click=_al_descartar, key="p_descartar")
        c3.button("Volver a lo predeterminado", icon=":material/restart_alt:", width="stretch",
                  on_click=_restablecer, args=(ctx,), key="p_restablecer")

    # ---- Tema
    st.markdown("### Tema")
    for grupo in T.GRUPOS:
        temas_g = [(k, t) for k, t in T.TEMAS.items() if t.get("grupo") == grupo]
        st.markdown(f'<div class="subtitulo-bloque">{grupo}</div>', unsafe_allow_html=True)
        cols = st.columns(4, gap="medium")
        for i, (k, base) in enumerate(temas_g):
            propios = _propios(preferencias(ctx), k)["colores_tema"] if k != clave else b["colores_tema"]
            with cols[i % 4], st.container(border=True, key=f"tema-{k}"):
                st.markdown(T.muestra(T.resolver(k, propios)), unsafe_allow_html=True)
                st.markdown(f"**{base['nombre']}**")
                st.caption(base["descripcion"])
                st.button("En uso" if k == clave else "Usar este tema", key=f"usar_{k}", width="stretch",
                          type="primary" if k == clave else "secondary", disabled=k == clave,
                          on_click=_elegir_tema, args=(ctx, k))

    # ---- Cómo se ve
    st.markdown("### Cómo se ve")
    st.caption("Si el tablero te parece muy cargado o lo usas con zoom, prueba texto más grande, tarjetas sobrias "
               "o espaciado compacto.")
    cv = st.columns(3, gap="medium")
    vista_b = b.get("vista") or VISTA_DEFECTO
    for col, (campo, cfg) in zip(cv, VISTA.items()):
        col.segmented_control(cfg["titulo"], list(cfg["opciones"]), default=vista_b[campo],
                              format_func=lambda o, c=cfg: c["opciones"][o], key=f"pv_{campo}_{v}")

    # ---- Al abrir
    st.markdown("### Al abrir el tablero")
    ci = st.columns(2, gap="medium")
    ini = b.get("inicio") or INICIO_DEFECTO
    ci[0].selectbox("Mostrar primero el canal", list(CANALES_INICIO), format_func=CANALES_INICIO.get,
                    index=list(CANALES_INICIO).index(ini["canal"]), key=f"pi_canal_{v}")
    opciones_u = [""] + (["crm"] if ctx["admin"] else []) + list(ctx["unidades"])
    etiqueta_u = {"": "La primera que puedo ver", "crm": "Equipo CRM (todo)", **nombres}
    ci[1].selectbox("Con la vista de", opciones_u, format_func=lambda u: etiqueta_u.get(u, u),
                    index=opciones_u.index(ini["unidad"]) if ini["unidad"] in opciones_u else 0, key=f"pi_unidad_{v}")

    # ---- Colores del tema elegido
    st.markdown(f"### Colores en {T.TEMAS[clave]['nombre']}")
    st.caption("Parten del tema elegido. Lo que cambies aquí se guarda solo para este tema: si eliges otro, "
               "se usan sus colores (o los que hayas elegido antes en él).")
    actual = T.resolver(clave, b["colores_tema"])
    c = st.columns(4)
    for i, (campo, etiqueta) in enumerate(T.PERSONALIZABLES.items()):
        c[i % 4].color_picker(etiqueta, actual[campo], key=_clave_color(campo))
    st.markdown("**Unidades**")
    paleta = actual["unidades"]
    cu = st.columns(min(4, max(1, len(nombres))))
    for i, (u, nombre) in enumerate(nombres.items()):
        cu[i % len(cu)].color_picker(nombre, b["colores"].get(u, paleta[i % len(paleta)]), key=_clave_unidad(u))

    # ---- Secciones
    st.markdown("### Secciones del Resumen")
    st.caption("Arrastra las secciones para cambiar el orden en que aparecen. Para ocultar una, pásala a la "
               "columna «Ocultas»." + ("" if ctx["admin"] else " Gasto por unidad y Consumo por unidad solo se "
                                                                 "ven en la vista del Equipo CRM."))
    visibles = [SECCIONES[s] for s in b["orden"] if s not in b["ocultas"]]
    ocultas = [SECCIONES[s] for s in b["orden"] if s in b["ocultas"]]
    resultado = sort_items([{"header": "Se muestran", "items": visibles}, {"header": "Ocultas", "items": ocultas}],
                           multi_containers=True, direction="vertical", custom_style=estilo_lista(tema),
                           key=f"orden_secciones_{v}")
    por_nombre = {n: k for k, n in SECCIONES.items()}
    nuevo_vis = [por_nombre[n] for n in resultado[0]["items"]]
    nuevo_ocu = [por_nombre[n] for n in resultado[1]["items"]]
    if not nuevo_vis:
        st.error("Deja al menos una sección visible.")
    elif (nuevo_vis + nuevo_ocu, nuevo_ocu) != (b["orden"], b["ocultas"]):
        st.session_state["p_secciones"] = (nuevo_vis + nuevo_ocu, nuevo_ocu)
        st.rerun()   # para que la barra de arriba se entere del cambio
