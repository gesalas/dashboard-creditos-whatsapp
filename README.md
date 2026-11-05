# Dashboard de créditos de WhatsApp

Dashboard en Streamlit para seguir el consumo de créditos de WhatsApp enviados desde Marketing Cloud: cuánto se ha consumido, cuánto queda, cuándo se agotarían los créditos y cómo se reparte el consumo por línea, unidad, país y journey.

## Cómo correrlo

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Ejecutar desde la carpeta del repositorio. El dashboard abre en `http://localhost:8501`.

Hay dos modos (en Windows también con doble clic en los `.bat`):

| Modo | Comando | Para qué |
|---|---|---|
| Producción | `py -m streamlit run app.py` (`abrir_dashboard.bat`) | Igual que el enlace publicado: pide iniciar sesión. |
| Pruebas | `py -m streamlit run app.py -- --pruebas` (`abrir_pruebas.bat`) | Sin inicio de sesión, con permisos del Equipo CRM, aviso naranja arriba y todo guardado en la carpeta local. Los correos (contraseñas temporales, avisos) se muestran en pantalla y no se envían. En el enlace publicado este modo no existe aunque se pase el parámetro. |

En Windows, si `python` no se reconoce, usar `py` en su lugar (`py -m streamlit run app.py`). Se usa `python -m` en lugar de `streamlit` directamente porque en Windows la carpeta de ejecutables de Python muchas veces no está en el PATH.

## Archivos

| Archivo | Qué es | Cuándo se actualiza |
|---|---|---|
| `data.xlsx` | Reporte de entregas de WhatsApp exportado de Marketing Cloud. Se usa tal como sale, con las filas de encabezado del reporte. | Cada vez que hay un reporte nuevo |
| `tarifas/` | Una tabla de tarifas por vigencia, con el nombre de la fecha en que empieza a regir (`2026-11-01.csv`). Columnas `ISO`, `Country`, `Marketing`, `Utility`. La fila `OTHER` se usa para países que no están en la tabla. `notas.json` guarda observaciones por tabla (por ejemplo, si es provisional). | Cada vez que Salesforce publique una tabla nueva |
| `data_correo.xlsx` | Reporte de correos enviados de Marketing Cloud Intelligence (Email Sender Name, Journey Name, Email Content Name, Email Sends; si trae *Send Date*, mejor). Se usa tal como sale. | Cada vez que hay un reporte nuevo de correo |
| `tarifas_sms/` | Multiplicadores de SMS por país de Salesforce Message Credits (un CSV por vigencia). Listo para cuando llegue el reporte de SMS. | Cuando Salesforce publique una tabla nueva |
| `tarifas.csv` | Respaldo: tabla única que solo se usa si no existe la carpeta `tarifas/`. | No hace falta actualizarlo |
| `config.json` | Compras de créditos con su línea (`compras`), asignación a unidades por línea (`ucp`, `outbound`; los totales y `general` se calculan solos), umbrales del semáforo (`semaforo`) y textos del encabezado (`marca`). Precios por canal (`precios_usd_1000`), unidades y journeys. Se edita desde WhatsApp → Créditos y Todos los canales → Configuración. | Cuando se compren créditos o cambie la asignación |
| `acceso.json` | Dominio permitido para crear cuentas y lista de correos del **Equipo CRM** (administradores). | Cuando entre o salga alguien del Equipo CRM |
| `usuarios.json`, `bitacora.json`, `perfiles.json` | Cuentas (contraseñas cifradas con bcrypt), registro de cambios, y foto y personalización de cada persona. Los crea la app; no se suben con git (ver Acceso). | Solos |
| `canal_correo.py` | El canal Correo (estado, remitentes, journeys, créditos). Cada canal nuevo puede seguir el mismo patrón. | Desarrollo |
| `estilos.py` | Los estilos (CSS): forma, espaciado, adaptación a zoom y celular, impresión. Los colores vienen del tema. | Desarrollo |
| `guia.py`, `novedades.py` | La guía rápida del primer ingreso y el recuadro «Desde tu última visita». | Desarrollo |
| `personalizar.py`, `temas.py` | La página Personalizar tablero (tema, colores, secciones) y los temas con sus colores. | Desarrollo |
| `acceso.py`, `sesion.py`, `almacen.py`, `correo_app.py` | Cuentas y roles, pantallas de acceso, dónde se guardan los archivos y envío de correos de la app. | Desarrollo |
| `logica.py` | Todos los cálculos. No depende de Streamlit. | Desarrollo |
| `app.py` | La interfaz: filtros, pestañas y gráficas. | Desarrollo |
| `.streamlit/config.toml` | Colores y tema del dashboard. | Desarrollo |
| `actualizar_datos.py`, `actualizar_datos.json`, `ejecutar_actualizacion.bat` | Actualización automática de `data.xlsx` desde el correo (ver abajo). | Al configurarla |
| `alertas.py`, `informes.py`, `alertas.json`, `ejecutar_alertas.bat` | Alertas de consumo: aviso de Windows, correo general y correo por unidad a cada responsable (ver abajo). | Al configurar las alertas |
| `assets/` | Imágenes oficiales opcionales: `logo_javeriana.png` (barra lateral) e `icono_whatsapp.png` (junto al título). No se incluyen; ver `assets/LEEME.txt`. | Una vez |

Si cambia alguno de los archivos de datos, el dashboard los vuelve a cargar solo al refrescar la página. El botón "Recargar datos" fuerza la recarga.

## Cómo se calcula

Los cálculos son los mismos de la versión anterior del dashboard, salvo las tarifas: antes se usaba una sola tabla para todas las fechas y ahora cada entrega se cobra con la tarifa vigente en su fecha.

- **Créditos** = deliveries x tarifa del país, usando la tabla de tarifas vigente en la fecha de envío (la más reciente de `tarifas/` cuya fecha de inicio sea menor o igual a la del envío). Se usa la tarifa Utility solo si el tipo de conversación es explícitamente `Utility`; todo lo demás se cobra como Marketing. Marketing Cloud exporta ese campo con errores (`8`, vacíos), y esta es la regla confirmada con el equipo.
- **Línea**: según el `WhatsApp Channel ID`. 573102190903 es UCP y 573160271386 es Outbound.
- **Unidad**: la que se le asignó al journey a mano en Configuración; si no tiene, la de su prefijo (`MERCA`, `EGRES`, `DONAC` o el que se configure para cada unidad); si no coincide con ningún prefijo, la unidad por defecto (hoy, Mercadeo). Ver "Unidades y journeys".
- **Tipo de journey**: Pruebas (el nombre tiene "prueba"; no cuenta "prueba específica", que es la prueba de admisión de algunos programas), Automático - Acceso, Automático - Financiación (`MERCA_FINANCIACION`, `MERCA_MANTENIMIENTO`), Automático - Visitas o Entregas a solicitud (todo lo demás: lo que piden las unidades).
- **Proyección**: se toma el volumen promedio diario de entregas del periodo de referencia (por defecto, los últimos 28 días con datos), por país y tipo de conversación, y cada día futuro se cobra con la tabla de tarifas que rija ese día. La próxima semana suma los 7 días siguientes a la fecha de fin; la fecha de agotamiento es el día en que ese consumo acumulado alcanza los créditos restantes. Si ya hay publicada una tabla futura (por ejemplo, la del 1 de noviembre), la proyección la incluye.
- **Tarifa de las proyecciones**: cada día futuro se cobra con la tabla oficial vigente ese día, es decir, la más reciente publicada a esa fecha. Si ya hay una tabla futura cargada (por ejemplo, la del 1 de noviembre), se usa desde su fecha de inicio.

### Agregar una tabla de tarifas nueva

1. Descargar el PDF de Salesforce ("WhatsApp Business Messaging (1,000)") desde la [página de archivo](https://www.salesforce.com/marketing/sms-ratio-archive/) o el enlace vigente.
2. Copiar cualquier archivo de `tarifas/` con el nombre de la fecha de inicio de la nueva tabla (`AAAA-MM-DD.csv`) y actualizar las columnas `Marketing` y `Utility` de cada país.
3. Recargar el dashboard. No hay que cambiar código.

Tablas cargadas hoy: 01/12/2025, 01/05/2026, 01/08/2026 y 01/11/2026. Las de mayo, agosto y noviembre se extrajeron de los PDFs oficiales y se verificaron con dos lecturas independientes (la de mayo, además, contra el PDF descargado). La de diciembre 2025 no tiene PDF oficial disponible; se usa la tabla que traía el dashboard (ver `tarifas/notas.json`).

## Acceso: cuentas y roles

Para entrar hay que iniciar sesión. Quien encuentre el enlace sin una cuenta aprobada no ve ningún dato.

**Roles**

| Rol | Quién | Qué ve |
|---|---|---|
| Equipo CRM | Solo los correos de `acceso.json` → `equipo_crm`. Nadie puede darse este rol desde la app. | Todo, más Usuarios y Bitácora |
| Usuario de unidad | Cuenta con una o más unidades aprobadas | Solo sus unidades (si tiene varias, las cambia en Vista; no se suman). Sin las pestañas Unidades, Créditos ni Configuración. Un enlace `?unidad=` a otra unidad lo lleva a la suya. |
| Pendiente | Creó la cuenta pero no tiene unidades aprobadas | Una pantalla de espera; puede pedir otra unidad o cerrar sesión |

**Crear cuenta:** solo correos `@javeriana.edu.co`. La persona escribe su nombre y correo, recibe un código de 6 dígitos (vence en 15 minutos, 5 intentos), elige su unidad y crea su contraseña (mínimo 10 caracteres, sin contener su correo). Si su correo es **responsable** de esa unidad (Configuración → Unidades, que es lo mismo que `alertas.json`), la unidad queda aprobada de una vez; si no, queda pendiente y el Equipo CRM recibe un correo para aprobarla o rechazarla en **Usuarios**. Los del Equipo CRM no eligen unidad.

**Seguridad**

- Las contraseñas se guardan cifradas con bcrypt; los códigos solo existen en memoria y la bitácora nunca guarda ninguno de los dos.
- 5 intentos fallidos bloquean la cuenta 15 minutos (recuperar la contraseña con código la desbloquea).
- Códigos: uno por minuto y máximo 5 por hora por correo.
- «Recordarme» deja la sesión abierta 30 días en ese navegador con una cookie firmada. Cambiar la contraseña, recibir una contraseña temporal, ser desactivado o usar «Cerrar sesión en todos los equipos» cierra todas las sesiones recordadas.

**Usuarios (Equipo CRM):** aprobar o rechazar solicitudes, cambiar las unidades de una cuenta, desactivarla o activarla, darle una contraseña temporal (debe cambiarla al entrar) y crear una cuenta para alguien que no recibe el código. Marca las cuentas que llevan más de 90 días sin entrar.

**Menú de perfil (arriba a la derecha):** botón con la foto y el nombre de la persona. Al abrirlo muestra su correo y rol, y lleva a Mi cuenta, Personalizar tablero, Usuarios y Bitácora (estas dos solo para el Equipo CRM; Usuarios muestra cuántas solicitudes hay por aprobar) y Cerrar sesión. Sin foto, se ven las iniciales.

**Alertas de cada persona (Mi cuenta → Alertas por correo):** cada quien decide si le llegan las alertas de sus unidades (todas o solo las críticas) y el resumen semanal de los lunes. Los responsables de alertas.json las reciben siempre; esto suma a las personas que lo pidan. Las envía `alertas.py` (en el computador del Equipo CRM), que lee estas preferencias de `perfiles.json`, en local o en GitHub si `.streamlit/secrets.toml` tiene el token.

**Guía rápida:** 4 pasos que aparecen la primera vez que alguien entra (créditos y canales, el semáforo, su vista y lo útil del día a día). Se vuelve a abrir desde el menú del perfil.

**Desde tu última visita:** al entrar, un recuadro dice qué cambió desde la vez anterior: datos nuevos, créditos usados y cuánto subió el porcentaje, unidades que cambiaron de estado, correos nuevos y (Equipo CRM) remitentes nuevos sin unidad.

**Descargar PDF:** junto al título; abre la ventana de impresión con lo que se está viendo, sin la barra lateral ni los botones (elegir «Guardar como PDF»).

**Al abrir el tablero** (Personalizar): canal y unidad con los que abre cada persona.

**Mi cuenta:** subir o quitar la foto de perfil (se ve grande antes de guardarla; se recorta en cuadrado y se guarda pequeña, 256 px), cambiar la contraseña, pedir acceso a otra unidad y cerrar sesión en todos los equipos.

**Personalizar tablero (cada persona el suyo):**
- **Tema** (16, en cuatro grupos): *Institucionales* (Javeriana —el predeterminado, con el azul #2C5697 y el amarillo #F8CD00 de la universidad—, Javeriana noche y Azul clásico), *Oscuros* (Oscuro, Carbón, Medianoche violeta, Bosque nocturno), *Claros de color* (Otoño, Vino tinto, Océano, Bosque, Lavanda, Grafito claro) y *Accesibilidad* (Alto contraste oscuro, Alto contraste claro y Apto para daltonismo, con la paleta Okabe-Ito).
- **Colores** encima del tema: principal, acento, Marketing, Utility y cada unidad. Se guardan **por tema**: si en Javeriana Mercadeo es rosado y se pasa a Carbón, Mercadeo toma el color de Carbón; al volver a Javeriana vuelve a ser rosado.
- **Cómo se ve:** tamaño del texto (normal, grande, muy grande), tarjetas con color o sobrias (solo el borde de color) y espaciado cómodo o compacto. Pensado para quien usa zoom o siente el tablero muy cargado.
- Lo elegido se ve de una vez. Arriba hay una barra fija con «Guardar», «Descartar» y «Volver a lo predeterminado». Si la persona sale de la página sin guardar, el tablero le pregunta si quiere guardar, descartar o seguir editando. Los temas están en `temas.py`. También se arrastran las secciones del Resumen para cambiar su orden o pasarlas a «Ocultas», y se elige el color de cada unidad (se usa en las gráficas que comparan unidades, en *Gasto por unidad* y en las tarjetas de Unidades). «Volver a lo predeterminado» deshace todo. Se guarda en `perfiles.json` junto con la foto (en el enlace publicado, en la rama `datos-acceso`, como los usuarios).

**Bitácora (Equipo CRM):** quién hizo qué y cuándo: cuentas creadas, aprobaciones y rechazos, cambios de unidades de una cuenta, desactivaciones, contraseñas temporales, bloqueos, inicios de sesión y cambios de créditos, precios y unidades (con lo que cambió). Se puede buscar, filtrar y descargar en CSV.

### Configuración para el enlace publicado (Secrets)

En Streamlit Community Cloud los archivos que la app modifica se borran cuando la app se reinicia. Por eso, en el enlace publicado, `usuarios.json` y `bitacora.json` se guardan en GitHub, en una rama aparte (`datos-acceso`, se crea sola) para que cada registro no vuelva a publicar la app; y lo que se guarda en Créditos o Configuración (`config.json`, `alertas.json`) se sube a la rama de la app.

Los valores van en **Settings → Secrets** de la app en Streamlit Cloud (o en `.streamlit/secrets.toml` en local, que no se sube). El modelo está en `.streamlit/secrets.toml.ejemplo`:

- `[acceso] clave_sesion`: frase larga al azar para firmar el «recordarme».
- `[correo]`: cuenta de Gmail con **contraseña de aplicación** (no la contraseña normal) para enviar códigos y avisos. En el enlace publicado es la única forma de enviar correos.
- `[github]`: token de grano fino creado por el dueño del repositorio, solo para este repositorio, con permiso *Contents: Read and write*. Tiene fecha de vencimiento: hay que renovarlo antes.

Antes de pasar el inicio de sesión a la rama publicada: poner los correos del Equipo CRM en `acceso.json`, llenar los Secrets y que cada persona del Equipo CRM cree su cuenta. Sin `[correo]` en el enlace publicado no se pueden enviar códigos: crear cuenta y recuperar contraseña quedan desactivados (el Equipo CRM puede crear cuentas con contraseña temporal).

**Correos de acceso:** código para crear la cuenta, código para restablecer la contraseña, acceso aprobado, solicitud no aprobada, contraseña temporal, aviso de contraseña cambiada (seguridad) y aviso al Equipo CRM de una solicitud nueva. Tienen un diseño propio de tarjeta centrada: logo pequeño arriba, título, el código grande en el centro, botón para ir al dashboard (con el enlace de `alertas.json` → `plantilla`) y la firma del Equipo CRM con los mismos datos de los informes. Para verlos sin enviar nada: `py correo_app.py --vista-previa` (quedan en `vista_previa/`; con `--abrir` se abren en el navegador). En el modo pruebas se muestran dentro de la app.

**Cómo se envían los códigos:** por SMTP si `[correo]` está en los Secrets; si no, en Windows, por el **Outlook de escritorio** del computador donde corre la app (el mismo de las alertas; el correo sale de esa cuenta de Outlook). En producción el código nunca se muestra en pantalla: si no hay cómo enviarlo, crear cuenta y recuperar contraseña quedan desactivados, porque mostrarlo permitiría registrarse con un correo ajeno. Si el envío falla, el código se anula.

En local, sin Secrets, usuarios y bitácora se guardan en la carpeta del proyecto.

## Correo

- **Créditos:** un correo estándar gasta **1 crédito**, sin importar el país (Salesforce Message Credits, Email Standard = 1; los envíos con prioridad o adjuntos cuestan más, pero el reporte no los distingue). **1.000 créditos = 4 USD** (confirmado).
- **Unidad de cada correo:** se decide por su **remitente** (Email Sender Name), en Correo → **Remitentes**: a cada remitente se le elige una unidad, o «Ninguna unidad» si no es de un área que manejemos (solo cuenta en el total). Ya vienen asignados *Pontificia Universidad Javeriana* → Mercadeo, *Egresados – …* → Egresados y *Donaciones …* → Donaciones. Si un reporte trae un **remitente nuevo**, queda «Sin asignar» y el tablero avisa al Equipo CRM hasta que alguien lo asigne. Para una unidad nueva (por ejemplo, Educación Continua), primero se crea en Todos los canales → Configuración.
- **Créditos adquiridos y asignados:** en Correo → Créditos (hoy 30.000.000 adquiridos el 01/01/2026, de la captura del dashboard de Marketing Cloud). Las asignaciones por unidad están en 0 hasta que se llenen.
- **Pestañas:** Resumen (estado del total y de cada unidad, gasto por unidad en USD, correos por remitente, journeys con más correos), Remitentes, Journeys (buscador) y Créditos. Una unidad ve su Resumen y sus Journeys.
- **Fecha de envío:** el reporte trae la columna de fecha (*Send Date*), que se detecta sola. Con ella:
  - el «Periodo a consultar» filtra los correos con sus propias fechas (el correo puede llegar más lejos que WhatsApp; el encabezado dice «Datos de correo al …»);
  - la **fecha de agotamiento** se estima con el ritmo de los últimos 28 días (en la tarjeta se ve «al ritmo de N correos por semana»);
  - hay gráficas de **correos por semana y por mes**, y Todos los canales muestra el gasto y los envíos de correo por semana.
- **Sin fecha de envío:** si algún reporte llega sin esa columna, el correo se muestra **acumulado** (al día en que se exportó), sin gráficas por semana ni fecha de agotamiento. No hay que cambiar código en ningún caso.
- Se guarda en `config.json`, sección `correo` (compras, unidades, remitentes).

## SMS

Aún sin reporte. Ya están el precio (**0,004888 USD por crédito = 4,888 USD por 1.000**, confirmado) y los multiplicadores por país de Salesforce en `tarifas_sms/` (vigentes desde el 1 de noviembre de 2026): **Colombia 0,74 créditos por SMS**; los países que no están en la tabla se cobran a 80. Como en WhatsApp, el multiplicador depende del país de destino y puede cambiar con cada tabla nueva. Para conectarlo falta el reporte de SMS (ideal con fecha y país) y las compras de créditos.

## Vocabulario

- **Entrega:** mensaje que le llegó a la persona (*deliveries* en el reporte). WhatsApp cobra por entrega, no por envío, así que el tablero habla de entregas.
- **Créditos adquiridos:** los comprados para una línea. UCP y Outbound son bolsas separadas: cada compra es para una sola línea y sus créditos no se pueden usar en la otra. Hoy la tarifa por país es la misma en las dos.
- **Créditos asignados:** la parte de los créditos de una línea que le corresponde a una unidad.

## Organización: unidad, canal y secciones

- **Barra lateral:** *Vista* (Equipo CRM o una unidad) y *Periodo a consultar*. Aplican a todo el tablero.
- **Canal**, arriba: **Todos los canales**, **WhatsApp**, **Correo** y **SMS**. Cada canal tiene su propia bolsa de créditos y sus propias tarifas. Correo y SMS aparecen como "Sin conectar" hasta que se agreguen su reporte, su tabla de tarifas y sus compras. El enlace puede abrir un canal directo: `?canal=whatsapp`, `?canal=todos` (se combina con `?unidad=...`).
- **Dentro de WhatsApp:**
  - La **línea** (Ambas líneas, UCP vs Outbound, UCP u Outbound) se elige justo debajo del canal.
  - Las secciones son Resumen, Proyección, Journeys y Detalle; en la vista Equipo CRM, además, Unidades y Créditos (compras por línea y asignación a unidades).
- **Todos los canales:** compara los canales en lo que sí se puede sumar.
  - *Gasto en dólares:* barra dividida por canal sobre lo comprado (o asignado a la unidad).
  - *Entregas:* cómo se reparten los mensajes entregados entre canales.
  - Una tarjeta por canal, gráficas de gasto y de entregas por semana y, para el Equipo CRM, una tabla por unidad.
  - En la vista Equipo CRM tiene una pestaña **Configuración** con el precio de los créditos de cada canal, las unidades y la asignación de journeys.
- **Vista de una unidad:** Mercadeo (o la que sea) ve solo lo suyo en cada canal y en Todos los canales. Cada unidad tiene un enlace directo con `?unidad=mercadeo`, que usa también su correo de alertas.

## Dinero (USD)

- El gasto en dólares se calcula con el **precio por cada 1.000 créditos** de cada canal, que se edita en Todos los canales → Configuración. Salesforce no publica ese valor: sale del contrato o de la orden de compra. Confirmados: **WhatsApp 4,16**, **Correo 4,00** y **SMS 4,888** USD por cada 1.000 créditos. Lo que cambia entre canales es cuántos créditos gasta cada mensaje: WhatsApp según el país y el tipo de plantilla, Correo 1 por correo, SMS según el país.
- Mientras el precio no esté marcado como *Confirmado*, las cifras en dólares dicen "(estimado)".
- En WhatsApp → Créditos, cada compra puede llevar su propio precio (columna *Precio por 1.000 (USD)*), si se pagó a otro valor. Cada bolsa usa el promedio de sus compras, ponderado por créditos.
- Se guarda en `config.json`: `precios_usd_1000`, `precios_confirmados` y, en cada compra, `precio_usd_1000` (opcional).

## Cambios de tarifa

- En las gráficas por semana y por mes, una **línea punteada** marca el día en que empezó a regir cada tabla de tarifas.
- Las proyecciones siempre usan la tabla vigente en cada día proyectado, es decir, la más reciente.

## Semáforo de consumo

Cada tarjeta muestra el estado según el porcentaje usado: las líneas frente a sus créditos adquiridos y las unidades frente a sus créditos asignados.

| Estado | Rango por defecto |
|---|---|
| Normal (verde) | menos de 80 % |
| Atención (amarillo) | desde 80 % |
| Crítico (rojo) | desde 95 % |

Si algo está en amarillo o rojo aparece además un aviso. Los umbrales se cambian en `config.json`:

```json
"semaforo": {"amarillo_pct": 80, "rojo_pct": 95, "fecha_inicio_conteo": null}
```

`fecha_inicio_conteo` (por ejemplo `"2026-01-01"`) define desde qué fecha se cuenta el consumo del semáforo, para que coincida con el inicio de la bolsa de créditos; `null` cuenta todo el reporte.

## Barra lateral y encabezado

**Pantallas pequeñas, zoom y celular:** las filas de tarjetas tienen todas la misma altura, con sus botones alineados, y se reacomodan solas según el ancho disponible (4 tarjetas pasan a 2 por fila y luego a 1; 3 y 2 pasan a 1). Títulos y cifras grandes se ajustan al ancho; en el celular la barra lateral se esconde y se abre con «>>».

**Enlaces útiles** (barra lateral): Marketing Cloud y las tablas oficiales de Salesforce Message Credits de cada canal. Se editan en Todos los canales → Configuración.

**Estado del sistema** (Todos los canales → Configuración, Equipo CRM): revisa de un vistazo el envío de correos, dónde se guardan los usuarios, la clave del «recordarme», el Equipo CRM, la antigüedad de los reportes, los remitentes sin unidad y los precios.

Secciones del Resumen (en este orden por defecto; cada persona puede cambiarlo): Estado de los créditos, Consumo del periodo, Consumo por semana, Consumo por mes, Gasto por unidad (USD), Consumo por unidad y Países con mayor consumo. *Gasto por unidad* y *Consumo por unidad* solo se ven en la vista del Equipo CRM.

La barra lateral agrupa los filtros en tarjetas: **Vista**, **Línea de WhatsApp** (cada opción con su descripción o número), **Periodo a consultar** (con las fechas y días que quedan elegidos) y **Datos** (hasta qué día llegan los datos, con un punto verde o amarillo según qué tan recientes son; fecha del reporte, tablas de tarifas y el botón para recargar).

El encabezado de la barra lateral muestra el nombre de la institución y del área (se cambian en `config.json`, sección `marca`). Para mostrar el logo oficial, se copia en `assets/logo_javeriana.png`; para el ícono junto al título, `assets/icono_whatsapp.png`. Si no están, se usa un ícono genérico de chat.

## Periodo consultado y créditos

- **Periodo a consultar (barra lateral):** opciones rápidas (todo hasta la fecha, últimos 7 o 30 días, este mes, mes anterior, este año, próximos 30 días, hasta fin de año) o fechas personalizadas. Las opciones relativas se cuentan desde el último día con datos del reporte. La fecha final puede ser futura (hasta dos años después del último dato).
- **Tarjetas de estado:** muestran cómo estaban los créditos el **último día del periodo**:
  - si ese día ya pasó, lo usado hasta ese día frente a lo adquirido hasta ese día (las compras cuentan desde su fecha);
  - si es el último día con datos ("Todo hasta la fecha"), el estado actual, contando todas las compras registradas hasta hoy;
  - si es futuro, un **estimado**: lo real más lo que se usaría hasta ese día al ritmo de los últimos 28 días, con la tarifa vigente cada día. La tarjeta lo indica ("estimado al 31/12/2026").
  - La fecha de agotamiento siempre se calcula desde el saldo real de hoy.
- **Qué más cambia con el periodo:** *Usados en el periodo* (cuando el periodo no empieza en el primer dato), Marketing y Utility, el consumo del periodo, las gráficas, los journeys y el detalle. Las gráficas solo muestran datos reales.
- **Créditos (WhatsApp → Créditos, vista Equipo CRM):**
  - *Créditos adquiridos:* lista de compras con fecha, **línea**, créditos y nota. Lo adquirido por cada línea es la suma de sus compras; el total de ambas líneas es UCP + Outbound. Para registrar una compra se agrega una fila al final.
  - *Asignación a unidades:* cuántos créditos de cada línea le corresponden a cada unidad. Es la base del estado de cada unidad, de su vista y de sus alertas.
  - Un resumen muestra lo adquirido, lo asignado y lo que queda *sin asignar a unidades* en cada línea; si se asignó de más, aparece en rojo.
  - Los cambios se ven de inmediato en todo el tablero (con un aviso de "sin guardar"); **Guardar** los escribe en `config.json` y **Descartar cambios** vuelve a lo guardado.
- **Frescura de los datos:** el encabezado muestra hasta qué día llegan los datos y hace cuánto; si pasan más de 7 días, aparece un aviso para exportar un reporte nuevo.

## Marketing y Utility

Marketing se identifica siempre en azul y Utility en naranja: en las cajas de cifras (solo el borde), en las tarjetas de estado y en las gráficas. Cada gráfica muestra un solo tipo: primero Marketing y debajo Utility, a lo ancho de la página y con el valor escrito sobre cada barra. Como Utility es mucho más barato (en Colombia, 0,99 frente a 15,44 créditos por mensaje), así se ve aunque sea poco; las semanas sin consumo muestran 0, y si no hubo nada en el periodo aparece "Sin consumo de Utility en este periodo". Todas las gráficas se pueden ver en créditos o en entregas.

## Unidades y journeys

En Todos los canales → Configuración (vista Equipo CRM), sin tocar el código:

- **Unidades:** se agregan en la última fila de la tabla, se renombran escribiendo encima y se quitan seleccionando la fila y borrándola. Cada unidad tiene:
  - *Prefijos de journeys:* un journey cuyo nombre empieza por ese texto queda en esa unidad (por ejemplo, `EGRES` para `EGRES_BIENVENIDA`). Pueden ser varios, separados por coma, o ninguno.
  - *Responsables:* correos que reciben las alertas de la unidad (se guardan en `alertas.json`).
- **Unidad por defecto:** a dónde van los journeys que no coinciden con ningún prefijo (hoy, Mercadeo). También se puede elegir "Sin unidad".
- **Asignación de journeys:** tabla con todos los journeys del reporte, sus entregas, su último uso y la unidad que le daría el prefijo. En la columna *Unidad* se le asigna otra unidad a mano; *Automática* vuelve a usar el prefijo. Hay una búsqueda y un filtro para ver solo los asignados a mano.
- **Guardar unidades y journeys** lo escribe en `config.json` (secciones `unidades`, `unidad_por_defecto` y `journeys`) y vuelve a clasificar todas las entregas. Una unidad nueva aparece en el selector de Vista, en las gráficas y en la tabla de asignación de créditos (con 0 créditos, para que se le asignen). Si se quita una unidad, sus créditos asignados se eliminan y sus journeys pasan a otra unidad por su prefijo o a la unidad por defecto.

## Pestañas

Orden en WhatsApp: Resumen, Proyección, Unidades (solo Equipo CRM), Journeys, Detalle y Créditos (solo Equipo CRM).

- **Resumen**: estado de los créditos, consumo del periodo (total, Marketing y Utility) y gráficas por semana, por mes, por país y (en la vista Equipo CRM) por unidad.
- **Unidades** (solo Equipo CRM): estado de cada unidad, comparativo en tabla y gráficas, y un botón para abrir la vista de cada unidad.
- **Journeys**: clasificación de journeys y los 15 con mayor consumo, separados en Marketing y Utility; al elegir journeys, su detalle y su proyección.
- **Proyección**: tiene dos modos.
  - **Eligiendo journeys:** una tabla con los journeys del periodo de referencia, su ritmo (entregas y créditos por semana), su último uso y una casilla *Incluir*. Vienen marcados los que siguen en uso: con entregas en los últimos 14 días y en más de un día; los de un solo uso quedan por fuera. Se pueden marcar o desmarcar, y agregar **journeys nuevos o de reemplazo** con sus entregas por semana, país, tipo y línea. Muestra la próxima semana, el consumo hasta una fecha y la fecha de agotamiento del escenario, comparados con los de todos los journeys.
  - **Con el ritmo actual**, para lo que se esté viendo (una unidad, una línea o ambas):
  - *Proyectar con el ritmo de:* los últimos 7, 14, 28 (por defecto), 56 o 90 días con datos, el periodo consultado o **fechas personalizadas** (por ejemplo, el ritmo de un evento o campaña anterior).
  - *Proyectar hasta:* una fecha futura (por ejemplo, la de un evento). Muestra los créditos y entregas estimados hasta ese día y el saldo que quedaría, o cuántos créditos faltarían.
  - Créditos y entregas estimados de la próxima semana y fecha de agotamiento.
  - Qué tabla de tarifas se usa (la vigente cada día proyectado).
- **Detalle**: las filas del reporte del periodo consultado con los cálculos, descargables en CSV.
- **Créditos** (solo Equipo CRM): compras por línea (con precio opcional), asignación de créditos a unidades y dónde cambiar los demás ajustes. Las unidades, los journeys y los precios por canal están en Todos los canales → Configuración.

## Actualización automática de data.xlsx desde el correo

**También el correo:** `actualizar_datos.py` trae `data_correo.xlsx` si en `actualizar_datos.json` la sección `correo` tiene `"activo": true`. Usa sus propios filtros (`asunto_contiene`, `adjunto_contiene`, por defecto el adjunto debe tener «Data_correo»); lo que no se escriba se toma de la configuración general (buzón, carpeta, días). Revisa que el archivo sea un reporte de correo válido y más nuevo antes de reemplazarlo (el anterior queda como `data_correo_anterior.xlsx`) y lo publica en GitHub junto con data.xlsx si está activo. `py actualizar_datos.py --solo correo` actualiza solo el correo.

**Revisión diaria:** cada vez que corre `alertas.py` revisa que los reportes se puedan leer y no lleguen vacíos o con las columnas cambiadas, y avisa una vez al día si hay un problema. También avisa (una sola vez por remitente) cuando el reporte de correo trae remitentes nuevos sin unidad. Todo esto también se ve en Configuración → Estado del sistema, junto con la fecha de vencimiento del token de GitHub (el Equipo CRM ve además un aviso 15 días antes de que venza).


`actualizar_datos.py` busca en el Outlook de escritorio el correo más reciente con el reporte, toma el adjunto de Excel, revisa que sea un reporte válido y más nuevo que el actual, y reemplaza `data.xlsx` (el anterior queda como `data_anterior.xlsx`). Si se activa, además lo sube a GitHub para que el dashboard publicado se actualice solo.

1. **Configurar `actualizar_datos.json`** con al menos un filtro para reconocer el correo del reporte. Ya viene configurado para el correo que envía Marketing Cloud (asunto "Marketing Report: Data", adjunto `Data-...xlsx`):

   ```json
   {
     "buzon": "",
     "carpeta": "Reportes_Datorama",
     "asunto_contiene": "Marketing Report: Data",
     "remitente_contiene": "",
     "adjunto_contiene": "Data-",
     "dias_a_revisar": 7,
     "publicar_en_github": false,
     "mensaje_commit": "Actualiza data.xlsx con el reporte del {fecha}"
   }
   ```

   - `buzon`: si el correo llega a otra cuenta o buzón compartido que está en el mismo Outlook, parte de su nombre o correo. Vacío = la cuenta principal.
   - `carpeta`: carpeta de Outlook donde llega el reporte (hoy `Reportes_Datorama`). Se busca sin distinguir mayúsculas, dentro de la bandeja de entrada o en cualquier otra parte del buzón. También acepta una ruta (`Reportes/WhatsApp`). Vacío = la bandeja de entrada.
   - `asunto_contiene`, `remitente_contiene`, `adjunto_contiene`: textos para reconocer el correo y el adjunto (sin distinguir mayúsculas).
   - `publicar_en_github`: `true` para hacer commit y push de `data.xlsx` después de actualizarlo. Requiere que la carpeta sea el repositorio clonado (con VS Code o GitHub Desktop) y que git ya tenga guardado el inicio de sesión de GitHub.
2. **Probar:** `py actualizar_datos.py --simular` muestra qué correo encontraría y qué haría, sin cambiar nada. Luego `py actualizar_datos.py`. Lo que pasa queda en `actualizar_datos.log`.
3. **Programar:** en el Programador de tareas de Windows, una tarea diaria (después de la hora en que suele llegar el correo) que ejecute `ejecutar_actualizacion.bat`. Ese archivo actualiza los datos y después revisa las alertas, así que puede reemplazar la tarea de `ejecutar_alertas.bat`. Como usa Outlook, la tarea debe correr con la sesión iniciada ("Ejecutar solo cuando el usuario haya iniciado sesión") y el computador encendido.

Si no hay correo nuevo, el reporte no es válido o no es más nuevo que el actual, no se cambia nada.

## Alertas de consumo

`alertas.py` revisa el consumo con la misma lógica del dashboard y avisa cuando se cruza un umbral (por defecto, 95 % de los créditos disponibles de `config.json`). Cada alerta se envía una sola vez; lo que ya se avisó queda en `alertas_estado.json`. Si se recargan créditos (cambia el valor en `config.json`), las alertas de ese ámbito vuelven a quedar activas.

También avisa si `data.xlsx` lleva varios días sin actualizarse (por defecto, 7), porque el script solo ve el consumo que trae ese reporte.

### Canales de aviso

| Canal (`alertas.json`) | Qué hace | Requisitos |
|---|---|---|
| `windows` (activo por defecto) | Muestra una ventana de advertencia en el escritorio del computador donde corre el script; queda encima de las demás hasta pulsar Aceptar. No usa PowerShell, así que no la bloquean las políticas de grupo. | Windows y la sesión del usuario iniciada. |
| `outlook` | Envía el correo de alerta desde el Outlook de escritorio con la sesión ya iniciada. No usa SMTP, así que no le afecta el bloqueo de Office 365. | Outlook clásico instalado (el "nuevo Outlook" no sirve) y el paquete `pywin32` (se instala con `requirements.txt`). Puede que Outlook pida confirmar el envío la primera vez. |
| `teams` | Publica en un canal mediante un flujo de Workflows. | La app Workflows habilitada para la cuenta (hoy no lo está). |
| `correo` | Envío SMTP directo. | Un servidor que acepte usuario y contraseña; Office 365 ya no lo permite. |

Para activar el correo por Outlook, en `alertas.json`:

```json
"outlook": {"activo": true, "destinatarios": ["persona1@javeriana.edu.co", "persona2@javeriana.edu.co"]}
```

### Formato de los correos

Los correos siguen el formato de un correo institucional normal para que se reconozcan como legítimos y no como publicidad o phishing: saludo, texto, una tabla sobria con las cifras, la recomendación según el estado, los journeys con mayor consumo, el enlace visible al dashboard (en el correo de una unidad, directo a la vista de esa unidad), la firma del Equipo CRM con el logo y una nota que explica por qué se recibe el mensaje y que no contiene adjuntos ni pide contraseñas. El asunto es informativo, por ejemplo: "Créditos de WhatsApp de Mercadeo: 93,8 % utilizado (corte 18/10/2026)".

Se configuran en `alertas.json`, sección `plantilla`:

```json
"plantilla": {
  "url_dashboard": "https://direccion-del-dashboard",
  "firma": {
    "nombre": "Equipo CRM",
    "area": "Dirección de Tecnologías de Información",
    "institucion": "Pontificia Universidad Javeriana",
    "direccion": ["Edificio Emilio Arango S.J, Piso 7", "Cra 7 # 42-60", "Bogotá, Colombia"],
    "correo": "correo.de.contacto@javeriana.edu.co"
  }
}
```

- `url_dashboard`: dirección del dashboard publicado. Si está vacía, el correo menciona el dashboard sin enlace.
- `correo`: a dónde escribir con preguntas. Si está vacío, se invita a responder el correo.
- El logo de la firma sale de `assets/logo_javeriana.png` (o `.jpg`); Outlook lo muestra dentro del correo, no como adjunto. Sin ese archivo, la firma va solo con texto.
- `py alertas.py --vista-previa` guarda en `vista_previa/` el correo general y el de cada unidad para revisarlos en el navegador antes de enviar.

### Correo por unidad

Cada responsable recibe solo el informe de su unidad (mercadeo, egresados o donaciones), enviado por Outlook de escritorio, cuando la unidad cruza 80 % (Atención) o 95 % (Crítico) de lo asignado en `config.json` (UCP + Outbound de cada unidad). El correo trae:

- el estado, el porcentaje usado con su barra, y qué hacer según el estado;
- créditos consumidos, asignados y restantes (o excedidos), consumo estimado de la próxima semana y fecha estimada de agotamiento;
- los journeys de la unidad con mayor consumo en los últimos 28 días;
- el consumo de las últimas 6 semanas y por línea de WhatsApp.

Configuración en `alertas.json`:

```json
"unidades": {
  "activo": true,
  "umbrales_pct": [80, 95],
  "responsables": {
    "mercadeo": ["responsable.mercadeo@javeriana.edu.co"],
    "egresados": ["responsable.egresados@javeriana.edu.co"],
    "donaciones": ["responsable.donaciones@javeriana.edu.co"]
  },
  "resumen_semanal": {"activo": false, "dia": "lunes"}
}
```

- Cada alerta se envía una sola vez por umbral; si se asignan más créditos a la unidad (cambia el valor en `config.json`), vuelven a quedar activas.
- Si una unidad no tiene responsable, su alerta va solo en el aviso general (ventana de Windows y `outlook.destinatarios`).
- `resumen_semanal`: si se activa, cada responsable recibe además el informe de su unidad una vez por semana, el día indicado, aunque no haya alerta.
- El aviso general (`outlook.destinatarios` y la ventana de Windows) recibe todas las alertas: de líneas y de unidades.

Comandos útiles:

```
py alertas.py --vista-previa     guarda en vista_previa/ el correo de cada unidad (HTML) para revisarlo, sin enviar
py alertas.py --simular          muestra qué se enviaría hoy y a quién, sin enviar
py alertas.py --enviar-informes  envía ya el informe actual a los responsables de cada unidad
```

Importante: la primera vez que corra con responsables configurados, las unidades que ya superaron los umbrales (hoy Mercadeo y Egresados) recibirán su alerta de inmediato.

### Configuración (`alertas.json`)

| Campo | Qué es |
|---|---|
| `umbrales_pct` | Umbrales del aviso general por línea, por ejemplo `[95]` o `[80, 95]`. |
| `unidades` | Correo por unidad: responsables, umbrales y resumen semanal (ver arriba). |
| `revisar` | Qué líneas revisar en el aviso general: `general` (ambas líneas) y `lineas` (UCP y Outbound). Las unidades se configuran en `unidades`. |
| `fecha_inicio_conteo` | Fecha desde la que se cuenta el consumo (`"2026-01-01"`), por ejemplo el inicio del contrato de créditos. `null` = todo el reporte. |
| `aviso_reporte_desactualizado_dias` | Días sin actualizar el reporte para enviar el aviso. `null` lo desactiva. |
| `correo` | Servidor SMTP, usuario, remitente y destinatarios. |
| `teams` | Activa o desactiva el envío a Teams. |

Las credenciales no van en `alertas.json`, sino en variables de entorno del usuario de Windows (se definen una vez en una terminal y quedan guardadas):

```
setx ALERTA_SMTP_PASSWORD "contraseña-de-la-cuenta"
setx ALERTA_TEAMS_WEBHOOK "url-del-flujo-de-teams"
```

Después de `setx` hay que abrir una terminal nueva para que se tomen.

### Teams

En el canal de Teams donde deben llegar las alertas: menú `...` del canal > **Workflows** > plantilla **"Post to a channel when a webhook request is received"** (o "Enviar al canal cuando se reciba una solicitud de webhook"). Al terminar, Teams entrega una URL; esa es la que va en `ALERTA_TEAMS_WEBHOOK`.

### Correo

Desde el 30 de abril de 2026, Office 365 rechaza el envío SMTP con usuario y contraseña, así que el correo se envía desde el mismo flujo de Teams: en el flujo de Workflows, después de "Post card in a chat or channel", se agrega la acción de Outlook **"Send an email (V2)"** ("Enviar un correo electrónico (V2)") con:

- **To**: los destinatarios de la alerta.
- **Subject**: la expresión `triggerBody()?['asunto']`.
- **Body**: la expresión `triggerBody()?['texto_html']`.

El correo sale desde la cuenta de quien creó el flujo. El envío SMTP directo (sección `correo` de `alertas.json`) queda desactivado (`"activo": false`); solo sirve con un servidor SMTP que acepte usuario y contraseña.

### Probar

```
python alertas.py --prueba     envía un mensaje de prueba por los canales activos
python alertas.py --simular    muestra qué alertas enviaría hoy, sin enviar nada
python alertas.py              revisión normal
```

Todo queda registrado en `alertas.log`.

### Programar la revisión (Programador de tareas de Windows)

Desde una terminal, reemplazando la ruta por la de la carpeta del repositorio:

```
schtasks /Create /SC HOURLY /TN "Alertas creditos WhatsApp" /TR "\"C:\ruta\al\repositorio\ejecutar_alertas.bat\""
```

Así corre cada hora mientras la sesión del usuario esté iniciada. Para revisarla o borrarla: `schtasks /Query /TN "Alertas creditos WhatsApp"` y `schtasks /Delete /TN "Alertas creditos WhatsApp"`.
