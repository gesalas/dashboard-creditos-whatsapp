"""
Estilos del tablero (CSS). Los colores salen de las variables del tema (--t-..., ver temas.py), así cada persona
ve el tablero con su tema. Aquí van la forma, los tamaños, el espaciado, lo que se adapta al ancho de la pantalla
(zoom y celular) y cómo se imprime (Descargar PDF).
"""

BASE = """
    <style>
    .block-container {padding-top: 2.6rem; padding-bottom: 4rem; max-width: 1400px;
                      padding-left: clamp(1rem, 3vw, 3rem); padding-right: clamp(1rem, 3vw, 3rem);}
    [data-testid="stHeader"] {background: var(--t-fondo); border-bottom: 1px solid var(--t-linea);}
    h3 {margin-top: 1.6rem !important;}
    @media (max-width: 640px) {
        .block-container {padding-top: 1.5rem;}
        .titulo {align-items: flex-start;}
        .titulo-icono img, .titulo-icono svg {width: 34px !important; height: 34px !important;}
        .subtitulo {gap: 6px;}
        .frescura, .frescura-alerta, .pastilla {font-size: 0.75rem;}
        .semaforo-cifras {grid-template-columns: 1fr 1fr;}
        [class*="st-key-zona-canal"] button[data-variant="segmented_control"] {padding: 8px 12px; min-height: 42px;}
        [class*="st-key-zona-canal"] button[data-variant="segmented_control"] p {font-size: 0.9rem;}
    }
    [data-testid="stMetric"] {
        background: var(--t-superficie);
        border: 1px solid var(--t-borde);
        border-radius: 10px;
        padding: 14px 16px 12px 16px;
    }
    [data-testid="stMetricLabel"] p {color: var(--t-texto-sec); font-size: 0.85rem;}
    [data-testid="stMetricValue"] {font-size: 1.65rem; font-weight: 600;}
    .stTabs [data-baseweb="tab-list"] {gap: 4px; border-bottom: 1px solid var(--t-borde);}
    .stTabs [data-baseweb="tab"] {padding: 8px 16px; font-weight: 500;}
    h1 {font-weight: 650; letter-spacing: -0.01em;}
    h3 {font-weight: 600; margin-top: 0.6rem;}
    .nota {color: var(--t-texto-sec); font-size: 0.88rem; margin: -0.4rem 0 0.8rem 0;}
    .semaforo {display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem 2rem;
               margin: 0.6rem 0 0.7rem 0; align-items: stretch;}
    /* Filas de tarjetas (fila_tarjetas): cuadrícula que se adapta al ancho real del contenido */
    [class*="st-key-fila-"] {container-type: inline-size; margin: 0.4rem 0 0.8rem 0;}
    [class*="st-key-fila-"] [data-testid="stHorizontalBlock"] {display: grid !important; gap: 1.25rem 1.5rem;
        grid-template-columns: repeat(var(--cols, 3), minmax(0, 1fr)); align-items: stretch;}
    [class*="st-key-fila-2"] {--cols: 2;} [class*="st-key-fila-3"] {--cols: 3;} [class*="st-key-fila-4"] {--cols: 4;}
    [class*="st-key-fila-1"] {--cols: 1;}
    [class*="st-key-fila-"] [data-testid="stColumn"] {width: auto !important; min-width: 0 !important;}
    [class*="st-key-fila-"] [data-testid="stColumn"] > [data-testid="stVerticalBlock"] {height: 100%; gap: 0.6rem;}
    [class*="st-key-fila-"] [data-testid="stElementContainer"]:has(.semaforo) {flex: 1 1 auto;}
    [class*="st-key-fila-"] [data-testid="stElementContainer"]:has(.semaforo) > div,
    [class*="st-key-fila-"] [data-testid="stElementContainer"]:has(.semaforo) [data-testid="stMarkdownContainer"],
    [class*="st-key-fila-"] .semaforo, [class*="st-key-fila-"] .semaforo-item {height: 100%;}
    [class*="st-key-fila-"] .stMarkdown > div {height: 100%;}
    [class*="st-key-fila-"] .semaforo {display: block; margin: 0;}
    [class*="st-key-fila-"] .semaforo-item {box-sizing: border-box;}
    [class*="st-key-fila-"] [data-testid="stElementContainer"]:has(.semaforo) [data-testid="stMarkdownContainer"] {margin-bottom: 0;}
    [class*="st-key-fila-"] [data-testid="stElementContainer"]:has(button) {margin-top: 0.25rem;}
    @container (max-width: 1180px) {[class*="st-key-fila-4"] [data-testid="stHorizontalBlock"] {grid-template-columns: repeat(2, minmax(0, 1fr));}}
    @container (max-width: 900px) {[class*="st-key-fila-3"] [data-testid="stHorizontalBlock"] {grid-template-columns: minmax(0, 1fr);}}
    @container (max-width: 600px) {[class*="st-key-fila-"] [data-testid="stHorizontalBlock"] {grid-template-columns: minmax(0, 1fr) !important;}}
    .semaforo-item {display: flex; flex-direction: column;}
    .semaforo-cifras {flex: 1; align-content: start;}
    .cifra-reserva {min-height: 2.7em; line-height: 1.35;}
    .semaforo-item {border-radius: 12px; padding: 16px 18px 14px 18px; border: 1px solid; border-left-width: 6px;}
    .semaforo-cabecera {display: flex; justify-content: space-between; align-items: center; gap: 8px;}
    .semaforo-titulo {font-size: 0.95rem; color: var(--t-texto); font-weight: 600;}
    .semaforo-valor {font-size: clamp(2rem, 1.4rem + 1.4vw, 2.6rem); font-weight: 700; color: var(--t-texto); line-height: 1.1; margin: 6px 0 10px 0;}
    .semaforo-valor small {display: block; white-space: nowrap; font-size: 0.85rem; font-weight: 500; color: var(--t-texto-sec);
                           margin: 2px 0 0 1px; line-height: 1.2;}
    .medidor {position: relative; height: 16px; background: var(--t-linea); border-radius: 999px; overflow: visible;}
    .medidor-relleno {height: 100%; border-radius: 999px;}
    .medidor-marca {position: absolute; top: -4px; bottom: -4px; width: 2px; background: var(--t-texto); opacity: 0.55;}
    .medidor-escala {position: relative; height: 16px; font-size: 0.72rem; color: var(--t-texto-sec); margin: 3px 0 12px 0;}
    .medidor-escala span {position: absolute; transform: translateX(-50%); white-space: nowrap;}
    .semaforo-cifras {display: grid; grid-template-columns: 1fr 1fr; gap: 6px 12px; margin-top: 10px;}
    .cifra-etiqueta {font-size: 0.75rem; color: var(--t-texto-sec);}
    .cifra-valor {font-size: 1.05rem; font-weight: 650; color: var(--t-texto);}
    .desglose {display: flex; gap: 8px; flex-wrap: wrap; margin: -4px 0 14px 0;}
    .chip {padding: 4px 12px; border-radius: 999px; font-size: 0.82rem; border: 1px solid;}
    .chip-mkt {background: var(--t-mkt-suave); color: var(--t-mkt-texto); border-color: var(--t-mkt-borde);}
    .chip-uti {background: var(--t-uti-suave); color: var(--t-uti-texto); border-color: var(--t-uti-borde);}
    .subtitulo-bloque {font-size: 0.8rem; font-weight: 700; color: var(--t-texto-sec); letter-spacing: 0.05em;
                       text-transform: uppercase; margin: 6px 0 6px 0;}
    .subtitulo {display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 6px;}
    .frescura, .frescura-alerta, .pastilla {font-size: 0.82rem; border-radius: 999px; padding: 3px 10px;
                                            border: 1px solid var(--t-borde); background: var(--t-superficie2); color: var(--t-texto);}
    .frescura {background: var(--t-verde-fondo); border-color: var(--t-verde-suave); color: var(--t-verde-borde); font-weight: 600;}
    .frescura-alerta {background: var(--t-amarillo-fondo); border-color: var(--t-amarillo-suave); color: var(--t-amarillo-borde); font-weight: 600;}
    .leyenda {display: flex; flex-wrap: wrap; gap: 6px 16px; align-items: center; margin: 14px 0 2px 0;
              font-size: 0.85rem; color: var(--t-texto-sec);}
    .leyenda .insignia {margin-left: 0; margin-right: 4px;}
    .leyenda-titulo {font-weight: 700; color: var(--t-texto);}
    .leyenda-nota {font-style: italic;}
    @media (max-width: 640px) {
        .titulo-texto {font-size: 1.75rem;}
        .titulo-icono img, .titulo-icono svg {width: 36px; height: 36px;}
        .semaforo-valor {font-size: 2.1rem;}
    }
    .semaforo-detalle .semaforo-cifras {grid-template-columns: 1fr 1fr;}
    .semaforo-detalle .semaforo-valor {font-size: 3rem;}
    .panel-unidades {border: 1px solid var(--t-borde); border-radius: 12px; padding: 14px 16px; background: var(--t-superficie);
                     margin: 0.6rem 0 1rem 0;}
    .panel-titulo {font-size: 0.95rem; font-weight: 600; color: var(--t-texto); margin-bottom: 8px;}
    .unidad-fila {padding: 10px 0; border-top: 1px solid var(--t-linea);}
    .unidad-fila:first-of-type {border-top: none;}
    .unidad-cabecera {display: flex; align-items: center; gap: 4px; margin-bottom: 6px;}
    .unidad-nombre {font-weight: 600; color: var(--t-texto);}
    .unidad-pct {margin-left: auto; font-weight: 700; color: var(--t-texto);}
    .unidad-detalle {font-size: 0.78rem; color: var(--t-texto-sec); margin-top: 6px;}
    .unidad-fila .medidor {height: 10px;}
    .unidad-fila .medidor-marca {top: -3px; bottom: -3px;}
    .franja-titulo {font-size: 0.8rem; font-weight: 700; color: var(--t-texto-sec); letter-spacing: 0.05em;
                    text-transform: uppercase; padding-top: 9px;}
    .titulo {display: flex; align-items: center; gap: 14px; margin: 0 0 4px 0;}
    .titulo-icono img, .titulo-icono svg {width: 46px; height: 46px; display: block;}
    .titulo-texto {font-size: clamp(1.6rem, 1.1rem + 1.6vw, 2.35rem); font-weight: 700; color: var(--t-texto); letter-spacing: -0.01em; line-height: 1.15;}
    .insignia {display: inline-block; border-radius: 999px; padding: 2px 10px; font-size: 0.78rem;
               font-weight: 650; text-transform: uppercase; letter-spacing: 0.02em; margin-left: 8px;
               vertical-align: middle;}
    .titulo-tipo {font-size: 0.95rem; font-weight: 650; color: var(--t-texto); padding: 2px 0 2px 10px;
                  border-left: 4px solid; margin: 14px 0 2px 0;}
    .tipo-mkt {border-color: var(--t-mkt);}
    .tipo-uti {border-color: var(--t-uti);}
    .tipo-mkt-texto {color: var(--t-mkt-texto);}
    .tipo-uti-texto {color: var(--t-uti-texto);}
    [class*="st-key-caja-mkt"] {border: 2px solid var(--t-mkt) !important; border-radius: 12px;}
    [class*="st-key-caja-uti"] {border: 2px solid var(--t-uti) !important; border-radius: 12px;}
    [class*="st-key-caja-mkt"] [data-testid="stMetric"] {border-color: var(--t-mkt-borde);}
    [class*="st-key-caja-"] [data-testid="stMetricValue"] {font-size: 1.4rem;}
    [class*="st-key-caja-uti"] [data-testid="stMetric"] {border-color: var(--t-uti-borde);}
    .cifra-valor small {font-size: 0.78rem; font-weight: 500; color: var(--t-texto-sec);}
    .cifra-sub {font-size: 0.8rem; font-weight: 500; color: var(--t-texto-sec);}
    .cifra-mkt {color: var(--t-mkt-texto); font-weight: 700; border-left: 3px solid var(--t-mkt); padding-left: 6px;}
    .cifra-uti {color: var(--t-uti-texto); font-weight: 700; border-left: 3px solid var(--t-uti); padding-left: 6px;}
    .stTabs [data-baseweb="tab-list"] {position: sticky; top: 2.9rem; z-index: 5; background: var(--t-fondo);}
    [data-testid="stSidebar"] {background: var(--t-lateral); border-right: 1px solid var(--t-borde);}
    [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {padding-top: 0.25rem;}
    .marca {background: linear-gradient(160deg, var(--t-marca-1) 0%, var(--t-marca-2) 100%); border-radius: 14px;
            padding: 18px 16px 14px 16px; margin: 0 0 14px 0; color: var(--t-marca-texto); text-align: left;
            box-shadow: var(--t-sombra-primario);}
    .marca-logo {background: #FFFFFF; border-radius: 12px; padding: 14px 16px; margin: 0 0 14px 0; display: flex;
                 justify-content: center; align-items: center; box-shadow: 0 1px 4px rgba(0,0,0,0.12);}
    .marca-logo img, .marca-logo svg {max-height: 104px; max-width: 100%; width: auto; display: block;}
    .marca-institucion {font-size: 1.02rem; font-weight: 700; line-height: 1.25;}
    .marca-area {font-size: 0.8rem; opacity: 0.8; margin-top: 3px;}
    .marca-producto {display: inline-flex; align-items: center; gap: 7px; font-size: 0.74rem; font-weight: 600;
                     margin-top: 12px; padding: 4px 10px; border-radius: 999px; background: rgba(255,255,255,0.12);
                     letter-spacing: 0.04em; text-transform: uppercase;}
    .marca-punto {width: 7px; height: 7px; border-radius: 50%; background: #3DDC84; display: inline-block;}
    [class*="st-key-lado-"] {background: var(--t-superficie); border: 1px solid var(--t-borde); border-radius: 14px;
                             padding: 12px 12px 12px 12px; gap: 0.55rem; box-shadow: var(--t-sombra);}
    .lado-titulo {display: flex; align-items: center; gap: 10px; font-size: 0.86rem; font-weight: 700;
                  color: var(--t-texto); line-height: 1.2;}
    .lado-icono {font-family: "Material Symbols Rounded"; font-size: 18px; line-height: 1; color: var(--t-primario);
                 background: var(--t-primario-suave); border-radius: 9px; padding: 6px; font-weight: normal;
                 font-variation-settings: "FILL" 0, "wght" 500;}
    .lado-sub {font-size: 0.74rem; font-weight: 500; color: var(--t-texto-ter); margin-top: 2px;}
    .lado-nota {font-size: 0.72rem; color: var(--t-texto-ter); line-height: 1.35;}
    [class*="st-key-lado-"] .stMarkdown [data-testid="stMarkdownContainer"] {margin-bottom: 0;}
    [class*="st-key-lado-linea"] [data-testid="stElementContainer"],
    [class*="st-key-lado-linea"] [data-testid="stRadio"],
    [class*="st-key-lado-linea"] [role="radiogroup"] {gap: 6px; width: 100% !important; display: flex; flex-direction: column;}
    [class*="st-key-lado-linea"] [role="radiogroup"] > div {box-sizing: border-box; align-self: stretch;}
    [class*="st-key-lado-linea"] [role="radiogroup"] > div {border: 1px solid var(--t-borde); border-radius: 10px;
                             padding: 7px 10px 7px 10px; width: 100%; background: var(--t-superficie); transition: all .12s;}
    [class*="st-key-lado-linea"] [role="radiogroup"] > div:hover {border-color: var(--t-borde-fuerte); background: var(--t-superficie2);}
    [class*="st-key-lado-linea"] [role="radiogroup"] > div[data-selected="true"] {border-color: var(--t-primario);
                             background: var(--t-primario-suave); box-shadow: inset 3px 0 0 var(--t-primario);}
    [class*="st-key-lado-linea"] [data-testid="stRadioOption"] {width: 100%; margin: 0;}
    [class*="st-key-lado-linea"] [data-testid="stRadioOption"] p {font-weight: 600; color: var(--t-texto); font-size: 0.88rem;}
    [class*="st-key-lado-linea"] [data-testid="stRadioCaption"] {margin: 0 0 0 1.75rem; padding: 0;}
    [class*="st-key-lado-linea"] [data-testid="stRadioCaption"] p {font-size: 0.72rem; color: var(--t-texto-ter); margin: 0;}
    @media print {
        [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
        [data-testid="stStatusWidget"], .st-key-menu-perfil, .stButton, [data-testid="stPopover"],
        .stTabs [data-baseweb="tab-list"], [class*="st-key-novedades"], .modo-pruebas, [data-testid="stExpandSidebarButton"],
        [class*="st-key-zona-canal"] button:not([aria-checked="true"]) {display: none !important;}
        html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stMainBlockContainer"],
        .block-container {overflow: visible !important; height: auto !important; position: static !important;
                          max-width: 100% !important; padding: 0 !important; margin: 0 !important;}
        body, .stApp {-webkit-print-color-adjust: exact; print-color-adjust: exact;}
        .semaforo-item, [data-testid="stMetric"], [data-testid="stVegaLiteChart"], [data-testid="stDataFrame"] {break-inside: avoid;}
        h3 {break-after: avoid;}
    }
    .punto-unidad {display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px;
      vertical-align: 1px;}
    .modo-pruebas {background: var(--t-amarillo-fondo); border: 1px solid var(--t-amarillo-barra); color: var(--t-amarillo-borde); border-radius: 8px;
      padding: 8px 10px; font-size: 0.78rem; font-weight: 600; line-height: 1.35; margin-bottom: 10px;}
    .modo-pruebas-ancho {font-size: 0.85rem; padding: 8px 14px;}
    .periodo-resuelto {display: flex; justify-content: space-between; align-items: center; font-size: 0.82rem;
                       color: var(--t-texto); background: var(--t-superficie2); border-radius: 8px; padding: 7px 10px; margin: 0;}
    .periodo-resuelto b {font-weight: 650; color: var(--t-primario);}
    .dato-fila {display: flex; justify-content: space-between; gap: 10px; font-size: 0.78rem; padding: 6px 0;
                border-bottom: 1px dashed var(--t-linea); color: var(--t-texto-ter);}
    .dato-fila:last-of-type {border-bottom: none;}
    .dato-fila b {color: var(--t-texto); font-weight: 600; text-align: right; display: inline-flex; align-items: center; gap: 6px;}
    .punto-ok, .punto-alerta {width: 7px; height: 7px; border-radius: 50%; display: inline-block;}
    .punto-ok {background: var(--t-verde-barra);}
    .punto-alerta {background: var(--t-amarillo-barra);}
    [data-testid="stSidebar"] [data-testid="stExpander"] details {background: var(--t-superficie); border-radius: 14px;}
    [class*="st-key-zona-canal"] {background: var(--t-superficie); border: 1px solid var(--t-borde); border-radius: 14px;
                                  padding: 14px 16px 12px 16px; margin: 10px 0 6px 0; gap: 0.35rem;
                                  box-shadow: var(--t-sombra);}
    .zona-etiqueta {font-size: 0.78rem; font-weight: 700; color: var(--t-texto-sec); letter-spacing: 0.05em;
                    text-transform: uppercase; margin: 2px 0 2px 2px;}
    .zona-nota {font-size: 0.78rem; color: var(--t-texto-ter); margin: 0 0 2px 2px;}
    [class*="st-key-zona-canal"] [role="radiogroup"] {gap: 10px; flex-wrap: wrap;}
    [class*="st-key-zona-canal"] button[data-variant="segmented_control"] {
        border: 1.5px solid var(--t-borde-fuerte) !important; border-radius: 12px !important; background: var(--t-superficie);
        padding: 10px 20px; min-height: 46px; box-shadow: var(--t-sombra); transition: all .12s;}
    [class*="st-key-zona-canal"] button[data-variant="segmented_control"] p {font-size: 1rem; font-weight: 600;
                                                                             color: var(--t-texto);}
    [class*="st-key-zona-canal"] button[data-variant="segmented_control"]:hover {border-color: var(--t-primario) !important;
                                                                                 background: var(--t-primario-suave);}
    [class*="st-key-zona-canal"] button[data-variant="segmented_control"][aria-checked="true"] {
        background: var(--t-primario); border-color: var(--t-primario) !important; box-shadow: var(--t-sombra-primario);}
    [class*="st-key-zona-canal"] button[data-variant="segmented_control"][aria-checked="true"] p,
    [class*="st-key-zona-canal"] button[data-variant="segmented_control"][aria-checked="true"] span {color: var(--t-sobre-primario);}
    [class*="st-key-linea"] button[data-variant="segmented_control"] {min-height: 40px; padding: 7px 16px;}
    [class*="st-key-zona-canal"] .stMarkdown [data-testid="stMarkdownContainer"] {margin-bottom: 0;}
    [class*="st-key-zona-canal"] button[data-variant="segmented_control"][aria-checked="true"]:hover {
        background: var(--t-primario-hover); border-color: var(--t-primario-hover) !important;}
    [class*="st-key-linea"] button[data-variant="segmented_control"] p {font-size: 0.93rem;}
    .barra-canales {display: flex; height: 26px; border-radius: 8px; overflow: hidden; background: var(--t-borde);
                    margin: 6px 0 8px 0;}
    .barra-canales .seg {height: 100%;}
    .leyenda-canales {display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 0.85rem; color: var(--t-texto-sec);
                      margin-bottom: 14px;}
    .leyenda-canales i {display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px;}
    .leyenda-canales b {color: var(--t-texto);}
    .cifra-grande {font-size: 1.9rem; font-weight: 700; color: var(--t-texto); margin: 2px 0 0 0;}
    .cifra-grande small {font-size: 0.95rem; font-weight: 500; color: var(--t-texto-sec);}
    .canal-pendiente {background: var(--t-superficie2); border-left-width: 6px; min-height: 170px;}
    .pendiente-texto {font-size: 0.88rem; color: var(--t-texto-sec); margin-top: 14px; line-height: 1.45;}
    </style>
"""
