# Bitácora de decisiones

Registro cronológico de decisiones y su **porqué** (incluye alternativas descartadas).
Mantener al día según el protocolo de `CLAUDE.md`: cada sesión que trabaje en el
proyecto añade sus entradas aquí antes de terminar. Las fechas de las primeras entradas
son aproximadas (reconstruidas del historial).

---

## Fundamentos (Fase 0 y 1)

- **Control de versiones e higiene:** se inicializó git, se fijaron dependencias exactas
  en `requirements.txt`, se corrigió un `config.toml` global con BOM UTF-8 que rompía el
  arranque, se eliminó código muerto (`frontend/`, `backend/api_server.py`, etc.). Se
  añadió tema corporativo vinotinto y scripts de arranque.
- **Eficiencia:** caché de parseo, persistencia de la base en disco y **memoización de
  snapshots** por sesión (evita reconstruir todo en cada rerun al cambiar un toggle).
  *Nota:* la persistencia en disco y la caché de parseo quedaron **obsoletas** al migrar a
  la base Parquet compartida (ver "Saga OOM").

## Ajustes de reportes (Reporte Proyecto / Inversionista)

- **Toggles "reciclar capital" y "sin retornos intermedios":** son conceptualmente
  contrarios → se hicieron **mutuamente excluyentes** a nivel de widget.
- **Gráfica "Forma de pago Lote":** debe considerar **solo la línea `2.22` (Lote Bruto)**,
  no la suma de lote + relacionados. Toggle Año/Mes y % Canje por periodo.
- **Etiquetas de línea acumulada cortadas:** faltaba `cliponaxis=False` en el trazo de
  línea (Plotly recortaba las etiquetas del borde). Añadido.
- **Pestaña Indicadores:** replica los KPIs de Factibilidad (grupo "💰 Factibilidad
  (P&G)") + los operativos, en un grid de **4 columnas**, reutilizando el mismo cálculo
  (sin divergencia). Cada sección tiene un botón **🔁 Transponer** (estilo Excel).
- **Dashboard de Factibilidad:** tablas compactas por categorías (Arquitectura, Ventas,
  Costos, Financiero/Equity) pensadas para captura de pantalla. Se pasó de `data_editor`
  (fuente en canvas incontrolable, se veía mal) a **tablas HTML**. Se agregaron
  indicadores manuales editables (áreas, costos por m²). Cambio de nomenclatura: "imp" → "inc".
- **Cronograma:** rediseñado a formato Gantt (una fila por etapa; segmentos Ventas/Obra/
  Entregas; ejes grandes y simples; meses en X sin solaparse). *Lección recurrente:*
  verificar visualmente que los textos no se encimen antes de entregar.

## Flujo de Caja — anualización de saldos

- Las líneas **`11.0` (Saldo Crédito)** y **`16.1` (FCL Acumulado)** son saldos
  acumulados: en vista Anual su valor es el **saldo de cierre** (último mes del año), no la
  suma de los 12 saldos mensuales. El resto de líneas sí se suman.

## Módulo Comparación de Proyectos

- **Objetivo:** comparar dos grupos de proyectos lado a lado (factibilidad consolidada +
  por proyecto) con una columna de **Diferencia = B − A** (no A − B), y debajo **TIR FCO /
  TIR K** e hitos de cronograma por grupo.
- **TIR FCO daba N/A** para algún grupo: el cálculo fallaba con TIR muy altas (>1000%). Se
  reescribió `_cmp_xirr` con barrido de cambio de signo + bisección.
- **Ajuste de espacio (saga larga):** el requisito duro es que **todo quepa en pantalla sin
  scroll horizontal** y sin desperdiciar espacio. Iteraciones: `width:max-content` (se
  salía) → `table-layout:fixed` con anchos % (letras cortadas / primera columna mal) →
  **`table-layout:auto`** (columnas ajustadas al contenido). Finalmente, para alinear
  perfectamente las filas de A, B y Diferencia y el separador vertical, se unificó todo en
  **una sola `<table>`** con `colspan` (en vez de tres tablas en flex). *Lección:* para
  alinear bloques, una tabla única gana a varias tablas separadas.

## Despliegue en la nube

- Se creó repo en GitHub (`EduardoRozoIC/estate-auditor`) y se desplegó en **Streamlit
  Community Cloud**. El repo se hizo **público** porque Streamlit no accedía al privado por
  OAuth (alternativa de GitHub App para privados era más engorrosa); el código no tiene
  secretos.
- **Base desde el repo:** se creó `data/` y la app auto-carga los datos al arrancar
  (la ruta local de OneDrive no existe en la nube). El módulo "Base de Datos" se simplificó:
  **el usuario ya no sube archivos**; la base vive en el repo.
- **Renombrado** "Cargar Base" → "📂 Base de Datos". Se **ocultaron** del nav los módulos
  `🔍 Auditoría` y `💼 Flujo Proyecto (Control)` ("en desarrollo"; código conservado).
- **Reporte Inversionista** dejó de ser módulo independiente y pasó a ser la **pestaña
  "🧑‍💼 Inversionista" (3ª)** dentro de Reporte Proyecto, reutilizando los snapshots,
  proyectos y corte ya seleccionados (se eliminó el selector duplicado).
- **Sidebar:** enlace **ORIGINACIÓN** (Hugging Face) con tamaño +50% y color vinotinto;
  título de la app cambiado a **"Estructuración"**.

## Migración de datos a ERConsolidado

- La base pasó de `Pipeline.xlsx` (26 proyectos, 60K filas) a la tabla **ERConsolidado**
  del consolidador (59 proyectos, ~980K filas). Mismo formato de columnas → sin cambios de
  esquema. Se limpian 138 filas basura (proyecto vacío, "P&G" con formato de fecha, fechas
  inválidas).
- **Parser vectorizado:** `_build_records` pasó de `iterrows` fila-a-fila a operaciones
  pandas vectorizadas → 374s a 60s en el archivo grande, salida verificada idéntica.

## Saga OOM → Parquet (crítica)

- Con 980K filas la app se caía en la nube (`healthz: EOF` = OOM en el contenedor de 1 GB).
- **Fix 1:** dejar de materializar ~980K objetos Pydantic por sesión → **DataFrame
  compartido** (`@st.cache_resource`, ~90 MB, una copia para todos los usuarios);
  materializar solo el subconjunto de cada snapshot. Verificado idéntico al método previo.
- **Seguía cayendo.** Causa real medida con `tracemalloc`: **parsear el `.xlsx` con
  openpyxl** dispara la RAM a **>600 MB** (y ~260s) al arrancar. **Fix 2 (definitivo):**
  servir **`data/base.parquet`** (3.4 MB, carga ~2.5s, pico ~145 MB); **sacar el `.xlsx`
  del repo** para que el fallback nunca lo parsee en la nube. Se añadió `tools/build_parquet.py`.
- Nota operativa: tras un OOM, Streamlit Cloud necesita **Reboot** manual (un auto-pull no
  recupera el proceso muerto).
- Bug lateral resuelto de camino: la caché en disco servía una base vieja tras cambiar el
  Excel; con la base Parquet compartida + recarga por deploy, el problema desaparece.

## Documentación y protocolo (2026-07-18)

- Se creó `CLAUDE.md` + `docs/` (ARQUITECTURA, DOMINIO, DESPLIEGUE, esta bitácora) y
  `tools/build_parquet.py`, para que **cualquier sesión de Claude conectada al repo** tenga
  todo el contexto sin depender de la memoria local de una máquina. Se estableció el
  **protocolo obligatorio** (ver `CLAUDE.md`): documentar todos los cambios/decisiones en
  el repo, no en local, y hacer push de la documentación junto con el código.

## 2026-07-28 — Base ampliada a dos hojas (control + pipeline), 60 proyectos

- Nuevo consolidador fuente: `20260728 Consolidado.xlsx`, con **dos hojas** válidas
  (mismo esquema `Proyecto/Fecha Datos/Fuente/P&G/TOTAL/Fecha/Valor` cada una):
  - `HistoricoConsolidado` (37 proyectos, ~960K filas, `Fuente="Proyectos"`) — datos
    reales de control/obra en ejecución.
  - `ER_Pipeline` (26 proyectos, ~272K filas, `Fuente="Estructuración"`) — modelo de
    factibilidad de proyectos aún en estructuración.
  - 3 proyectos aparecen en ambas (`Mitika 2.1`, `Mitika 2.2`, `Praia E3`), con **solape
    real** de `(proyecto, fecha_datos)` en varios cortes (misma fecha, dos fuentes).
- **`tools/build_parquet.py` generalizado:** ya no asume una sola hoja. Detecta
  automáticamente TODAS las hojas con el esquema válido (sin hardcodear nombres) y las
  concatena asignando `version` de forma **acumulada por (proyecto, fecha_datos)** en el
  orden en que aparecen las hojas en el libro — igual convención que
  `backend/folder_loader.py` ya usaba para varios *archivos*. Los solapes quedan como
  sub-versiones separadas y **seleccionables por separado** en la app (sufijo `-1`, `-2`),
  sin mezclar ni descartar ninguna fuente. Se descartó concatenar con `version=1` fijo
  para todo por generar snapshots incorrectos (mezcla de control + estructuración en la
  misma vista).
- Resultado: `data/base.parquet` → **60 proyectos, 1,231,861 filas, 18 cortes, 3.2 MB**.
  35,927 filas quedaron con sub-versión por el solape. Verificado con `AppTest`: arranca
  en 4s, 0 excepciones; los cortes solapados (p. ej. `Mitika 2.1: 2026-04-01-1 /
  2026-04-01-2`) aparecen correctamente separados.

## 2026-08-14 — Base reemplazada por Pipeline.xlsx (solo estructuración), 29 proyectos

- Fuente: `20260814 Pipeline.xlsx`. A diferencia del consolidador del 2026-07-28 (dos
  hojas: control + estructuración), este archivo trae **una sola hoja válida**
  (`ER_Pipeline`, `Fuente="Estructuración"`) — no incluye los proyectos de control/obra
  (`HistoricoConsolidado`). `tools/build_parquet.py` ya soportaba esto sin cambios
  (detecta automáticamente cuántas hojas válidas hay).
- Resultado: `data/base.parquet` → **29 proyectos, 293.044 filas, 12 cortes, 0.8 MB**
  (29 filas omitidas en la limpieza). Verificado con `AppTest`: arranca en 3.8s, 0
  excepciones.
- Reemplaza por completo la base anterior (60 proyectos / control+estructuración) — se
  ejecutó a petición explícita del usuario, no es una fusión ni una actualización
  incremental. Si en el futuro se necesita volver a tener proyectos de control además
  de estructuración, hay que volver a cargar un archivo con ambas hojas (como el
  consolidador del 2026-07-28).

### Actualización sobre el mismo archivo (2026-08-14, misma tarde)
- El usuario actualizó `20260814 Pipeline.xlsx` en el mismo día (mismo nombre de
  archivo, contenido refrescado). Se repitió el flujo estándar sin cambios de proceso.
- Resultado: `data/base.parquet` → **29 proyectos, 293.049 filas, 12 cortes** (5 filas
  más que la corrida anterior del mismo día). Verificado con `AppTest`: arranca en
  1.6s, 0 excepciones.
- **Tras este push, la app en la nube siguió mostrando la base vieja** — ver el fix
  de fondo justo abajo.

## 2026-08-14 — Fix: `@st.cache_resource` no se invalidaba al actualizar la base

- **Síntoma:** tras hacer push de un `data/base.parquet` nuevo (mismo nombre de
  archivo, contenido distinto), la app desplegada seguía mostrando la información
  vieja — el usuario reportó "la página me sale desactualizada".
- **Causa raíz:** `_load_shared_base()` estaba decorada con `@st.cache_resource`
  **sin ningún argumento**, es decir, sin ninguna clave de caché que dependiera del
  contenido del archivo. `cache_resource` guarda el resultado para el resto de la
  vida del **proceso** de Streamlit, no por deploy. Si Streamlit Community Cloud
  actualiza el código/datos de un redeploy ligero sin matar y recrear el proceso
  Python subyacente (algo que no está garantizado que ocurra en cada push), el
  DataFrame viejo se queda servido indefinidamente sin que ningún nuevo `git push`
  lo refresque — el usuario tendría que esperar a que el proceso se reciclara por
  otra razón (redeploy pesado, reinicio manual, etc.), de forma impredecible.
- **Fix:** se agregó `_shared_base_signature()` — una firma ligera
  (nombre+tamaño+mtime) de los archivos candidatos en `data/` (parquet o excel) — y
  se pasa como argumento a `_load_shared_base(_sig)`. Como `st.cache_resource`
  incluye los argumentos en la clave de caché, cualquier cambio en el archivo
  (nuevo `git push` con un `base.parquet` distinto) genera una firma distinta y
  fuerza el recálculo, sin importar si el proceso subyacente se reinició o no.
  Mismo patrón ya usado antes para el caché en disco (obsoleto, ver "Saga OOM →
  Parquet"), ahora aplicado también al `cache_resource` en memoria.
- Verificado con `AppTest`: sigue arrancando sin excepciones, mismos datos
  correctos (29 proyectos, 293.049 filas).
- **Lección para el protocolo:** cualquier `@st.cache_resource`/`@st.cache_data`
  que envuelva una lectura de archivo debe llevar el contenido/mtime del archivo
  como parte de su clave de caché — nunca asumir que un redeploy de Streamlit
  Cloud reinicia el proceso desde cero.

---

## 2026-09-23 — Fix: espacios duros (NBSP) corrompían el parseo de índices P&G

- **Síntoma reportado:** un comentario de calidad de datos sobre el consolidador
  señaló que algunos nombres de proyecto y líneas de P&G (`3.22 Costo Directo
  Construccion`, `3.24 Urbanismo Interno`) llegaban con **espacio duro (NBSP,
  U+00A0)** en vez de espacio normal — típico de copiar/pegar desde otra hoja o un
  PDF. Afectaba 18.419 filas en el archivo reportado.
- **Causa raíz:** la columna "proyecto" ya se limpiaba con `\s+` → espacio normal
  (esa regex de Python **sí** normaliza NBSP), pero la separación de la columna
  combinada `"<índice> <descripción>"` (formato "P&G", como en `ER_Pipeline`) usaba
  `.str.split(" ", n=1)` con un espacio **literal** — que NO reconoce NBSP. Con dos
  NBSP seguidos tras el índice, el split fallaba silenciosamente y el número quedaba
  pegado a la descripción, corrompiendo `indice`/`nombre_linea` para esas filas.
- **Fix:** normalizar con `\s+` → espacio normal **antes** de separar índice y
  nombre (`backend/parser_excel_v2.py`, `_clean_columns`). Aplica tanto a la ruta
  de columna combinada como a la ruta con columna `nombre_linea` separada.
- **Verificado** contra el archivo real (`20260814 Pipeline.xlsx`): el índice
  `3.22` ahora separa correctamente (`nombre_linea = "Costo Directo Construccion"`,
  sin residuo); cero filas con NBSP en `proyecto`/`indice`/`nombre_linea` en toda la
  base regenerada.
- **Nota:** el caso específico reportado (proyectos "Bosque Central") **no aplica
  a la base actual** — ese proyecto no existe en `20260814 Pipeline.xlsx` (solo
  estructuración); pertenecía al consolidador completo del 2026-07-28
  (control+estructuración). El fix queda igual de vigente para proteger cualquier
  carga futura que sí lo incluya.

## 2026-10-09 — Base cargada desde el Data Model (Power Pivot) de `000005 CONSOLIDADOR UNIFICADO TOTAL.xlsm`

- **Fuente nueva y distinta:** ya no es un Excel con hojas de datos, sino el **modelo
  de datos embebido** del consolidador (`xl/model/item.data`). El modelo tiene 3 tablas:
  `ERConsolidado` (1.518.972 filas, esquema idéntico al de la app: Proyecto/Fecha
  Datos/Fuente/P&G/TOTAL/Fecha/Valor), `McTotalFlujoProy` y `McTotalFlujoProy 2`
  (~88K filas c/u, otra estructura — **no cargadas**, no encajan con el esquema).
  Se cargó solo `ERConsolidado`.
- **Cómo se extrajo (reproducible):** no se leen las hojas con openpyxl. Se abre el
  libro con Excel por COM y se consulta el modelo con DAX vía la conexión embebida
  (`wb.Model.DataModelConnection.ModelConnection.ADOConnection`), p. ej.
  `EVALUATE SELECTCOLUMNS(ERConsolidado, ..., FORMAT([Fecha Datos],"yyyy-mm-dd"), ...)`.
  Fechas formateadas como texto ISO para evitar ambigüedad de configuración regional.
  Se vuelca a TSV en bloques de 100K (`Recordset.GetString`) y luego se limpia con el
  mismo `ExcelBaseParser._clean_columns` del proyecto y se escribe `data/base.parquet`.
  Tarda ~3-4 min en total. Si el archivo está bloqueado por OneDrive (permiso denegado
  desde Python), basta **copiarlo primero** a una carpeta local y trabajar sobre la copia.
- **Resultado:** `data/base.parquet` → **68 proyectos, 22 cortes, 1.518.941 filas, 3.6
  MB** (31 filas omitidas en limpieza, 0 valores no numéricos, 0 NBSP). Fuentes:
  Proyectos 1.145.885 / Estructuración 373.056. **Sin solapes** de proyecto+corte entre
  fuentes, por eso `version=1` para todo (no hay sub-versiones). `AppTest`: arranca en
  2.5s, 0 excepciones.
- **Reemplaza por completo** la base anterior (29 proyectos, solo estructuración).

---

<!-- Nuevas entradas al final. Formato sugerido:
## AAAA-MM-DD — Título corto
Qué se hizo, por qué, alternativas descartadas, archivos tocados.
-->
