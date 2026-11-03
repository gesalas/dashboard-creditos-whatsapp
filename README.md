# Dashboard de créditos de WhatsApp

Dashboard en Streamlit para seguir el consumo de créditos de WhatsApp enviados desde Marketing Cloud: cuánto se ha consumido, cuánto queda, cuándo se agotarían los créditos y cómo se reparte el consumo por línea, unidad, país y journey.

## Cómo correrlo

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Ejecutar desde la carpeta del repositorio. El dashboard abre en `http://localhost:8501`.

En Windows, si `python` no se reconoce, usar `py` en su lugar (`py -m streamlit run app.py`). Se usa `python -m` en lugar de `streamlit` directamente porque en Windows la carpeta de ejecutables de Python muchas veces no está en el PATH.

## Archivos

| Archivo | Qué es | Cuándo se actualiza |
|---|---|---|
| `data.xlsx` | Reporte de entregas de WhatsApp exportado de Marketing Cloud. Se usa tal como sale, con las filas de encabezado del reporte. | Cada vez que hay un reporte nuevo |
| `tarifas/` | Una tabla de tarifas por vigencia, con el nombre de la fecha en que empieza a regir (`2026-11-01.csv`). Columnas `ISO`, `Country`, `Marketing`, `Utility`. La fila `OTHER` se usa para países que no están en la tabla. `notas.json` guarda observaciones por tabla (por ejemplo, si es provisional). | Cada vez que Salesforce publique una tabla nueva |
| `tarifas.csv` | Respaldo: tabla única que solo se usa si no existe la carpeta `tarifas/`. | No hace falta actualizarlo |
| `config.json` | Compras de créditos con su línea (`compras`), asignación a unidades por línea (`ucp`, `outbound`; los totales y `general` se calculan solos), umbrales del semáforo (`semaforo`) y textos del encabezado (`marca`). Se edita desde la pestaña Configuración. | Cuando se compren créditos o cambie la asignación |
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

## Vocabulario

- **Entrega:** mensaje que le llegó a la persona (*deliveries* en el reporte). WhatsApp cobra por entrega, no por envío, así que el tablero habla de entregas.
- **Créditos adquiridos:** los comprados para una línea. UCP y Outbound son bolsas separadas: cada compra es para una sola línea y sus créditos no se pueden usar en la otra. Hoy la tarifa por país es la misma en las dos.
- **Créditos asignados:** la parte de los créditos de una línea que le corresponde a una unidad.

## Vistas

La barra lateral tiene dos selectores que se combinan:

- **Vista:** *Equipo CRM* ve todas las unidades, con las pestañas Unidades y Configuración. Al elegir **Mercadeo**, **Egresados** o **Donaciones**, todo el tablero muestra solo esa unidad: su estado, su resumen, sus gráficas, sus journeys, su proyección y su detalle (las pestañas Unidades y Configuración no aparecen). Cada unidad tiene un enlace directo: la dirección del dashboard con `?unidad=mercadeo`, `?unidad=egresados` o `?unidad=donaciones`; el correo de cada unidad usa ese enlace.
- **Línea de WhatsApp:**
  - *Ambas líneas (total):* tres tarjetas (total, UCP y Outbound) con un botón para ver el detalle de cada línea o compararlas.
  - *UCP vs Outbound (comparar):* las dos líneas lado a lado: tarjetas de estado, consumo del periodo y gráficas de Marketing y de Utility, cada línea en su columna y con la misma escala para que las barras se puedan comparar. La proyección también se muestra por línea.
  - *UCP* u *Outbound:* una tarjeta grande con más información (Marketing y Utility, últimos 7 días frente a los 7 anteriores, estimado de la próxima semana) y, al lado, el estado de cada unidad en esa línea (en la vista Equipo CRM) o el de la unidad en cada línea (en la vista de una unidad).

Las pestañas van arriba, justo debajo del título. Las tarjetas de estado están al inicio de la pestaña Resumen.

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
- **Créditos (pestaña Configuración, vista Equipo CRM):**
  - *Créditos adquiridos:* lista de compras con fecha, **línea**, créditos y nota. Lo adquirido por cada línea es la suma de sus compras; el total de ambas líneas es UCP + Outbound. Para registrar una compra se agrega una fila al final.
  - *Asignación a unidades:* cuántos créditos de cada línea le corresponden a cada unidad. Es la base del estado de cada unidad, de su vista y de sus alertas.
  - Un resumen muestra lo adquirido, lo asignado y lo que queda *sin asignar a unidades* en cada línea; si se asignó de más, aparece en rojo.
  - Los cambios se ven de inmediato en todo el tablero (con un aviso de "sin guardar"); **Guardar** los escribe en `config.json` y **Descartar cambios** vuelve a lo guardado.
- **Frescura de los datos:** el encabezado muestra hasta qué día llegan los datos y hace cuánto; si pasan más de 7 días, aparece un aviso para exportar un reporte nuevo.

## Marketing y Utility

Marketing se identifica siempre en azul y Utility en naranja: en las cajas de cifras (solo el borde), en las tarjetas de estado y en las gráficas. Cada gráfica muestra un solo tipo: primero Marketing y debajo Utility, a lo ancho de la página y con el valor escrito sobre cada barra. Como Utility es mucho más barato (en Colombia, 0,99 frente a 15,44 créditos por mensaje), así se ve aunque sea poco; las semanas sin consumo muestran 0, y si no hubo nada en el periodo aparece "Sin consumo de Utility en este periodo". Todas las gráficas se pueden ver en créditos o en entregas.

## Unidades y journeys

En la pestaña Configuración (vista Equipo CRM), sin tocar el código:

- **Unidades:** se agregan en la última fila de la tabla, se renombran escribiendo encima y se quitan seleccionando la fila y borrándola. Cada unidad tiene:
  - *Prefijos de journeys:* un journey cuyo nombre empieza por ese texto queda en esa unidad (por ejemplo, `EGRES` para `EGRES_BIENVENIDA`). Pueden ser varios, separados por coma, o ninguno.
  - *Responsables:* correos que reciben las alertas de la unidad (se guardan en `alertas.json`).
- **Unidad por defecto:** a dónde van los journeys que no coinciden con ningún prefijo (hoy, Mercadeo). También se puede elegir "Sin unidad".
- **Asignación de journeys:** tabla con todos los journeys del reporte, sus entregas, su último uso y la unidad que le daría el prefijo. En la columna *Unidad* se le asigna otra unidad a mano; *Automática* vuelve a usar el prefijo. Hay una búsqueda y un filtro para ver solo los asignados a mano.
- **Guardar unidades y journeys** lo escribe en `config.json` (secciones `unidades`, `unidad_por_defecto` y `journeys`) y vuelve a clasificar todas las entregas. Una unidad nueva aparece en el selector de Vista, en las gráficas y en la tabla de asignación de créditos (con 0 créditos, para que se le asignen). Si se quita una unidad, sus créditos asignados se eliminan y sus journeys pasan a otra unidad por su prefijo o a la unidad por defecto.

## Pestañas

Orden: Resumen, Proyección, Unidades (solo Equipo CRM), Journeys, Detalle y Configuración (solo Equipo CRM).

- **Resumen**: estado de los créditos, consumo del periodo (total, Marketing y Utility) y gráficas por semana, por mes, por país y (en la vista Equipo CRM) por unidad.
- **Unidades** (solo Equipo CRM): estado de cada unidad, comparativo en tabla y gráficas, y un botón para abrir la vista de cada unidad.
- **Journeys**: clasificación de journeys y los 15 con mayor consumo, separados en Marketing y Utility; al elegir journeys, su detalle y su proyección.
- **Proyección**: para lo que se esté viendo (una unidad, una línea o ambas):
  - *Proyectar con el ritmo de:* los últimos 7, 14, 28 (por defecto), 56 o 90 días con datos, el periodo consultado o **fechas personalizadas** (por ejemplo, el ritmo de un evento o campaña anterior).
  - *Proyectar hasta:* una fecha futura (por ejemplo, la de un evento). Muestra los créditos y entregas estimados hasta ese día y el saldo que quedaría, o cuántos créditos faltarían.
  - Créditos y entregas estimados de la próxima semana y fecha de agotamiento.
  - Qué tabla de tarifas se usa (la vigente cada día proyectado).
- **Detalle**: las filas del reporte del periodo consultado con los cálculos, descargables en CSV.
- **Configuración** (solo Equipo CRM): compras por línea, asignación de créditos a unidades, unidades y journeys, y dónde cambiar los demás ajustes.

## Actualización automática de data.xlsx desde el correo

`actualizar_datos.py` busca en el Outlook de escritorio el correo más reciente con el reporte, toma el adjunto de Excel, revisa que sea un reporte válido y más nuevo que el actual, y reemplaza `data.xlsx` (el anterior queda como `data_anterior.xlsx`). Si se activa, además lo sube a GitHub para que el dashboard publicado se actualice solo.

1. **Configurar `actualizar_datos.json`** con al menos un filtro para reconocer el correo del reporte. Ya viene configurado para el correo que envía Marketing Cloud (asunto "Marketing Report: Data", adjunto `Data-...xlsx`):

   ```json
   {
     "buzon": "",
     "carpeta": "",
     "asunto_contiene": "Marketing Report: Data",
     "remitente_contiene": "",
     "adjunto_contiene": "Data-",
     "dias_a_revisar": 7,
     "publicar_en_github": false,
     "mensaje_commit": "Actualiza data.xlsx con el reporte del {fecha}"
   }
   ```

   - `buzon`: si el correo llega a otra cuenta o buzón compartido que está en el mismo Outlook, parte de su nombre o correo. Vacío = la cuenta principal.
   - `carpeta`: si una regla de Outlook mueve el correo a una carpeta, su ruta dentro de la bandeja de entrada (por ejemplo `Reportes/WhatsApp`). Vacío = la bandeja de entrada.
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
