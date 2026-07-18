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

---

<!-- Nuevas entradas al final. Formato sugerido:
## AAAA-MM-DD — Título corto
Qué se hizo, por qué, alternativas descartadas, archivos tocados.
-->
