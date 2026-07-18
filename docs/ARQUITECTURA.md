# Arquitectura

## Stack

- **Python** (3.14 en la nube), **Streamlit 1.57**, **pandas 3.0.2**, **numpy**,
  **openpyxl 3.1.5**, **pydantic 2.13**, **plotly 6.7**, **pyarrow 24** (leer parquet).
- Versiones exactas fijadas en `requirements.txt`.
- Un único archivo monolítico principal: **`app.py`** (~7000+ líneas). La lógica de
  dominio vive en `backend/`.

## Estructura de carpetas

```
app.py                     # UI + orquestación (monolito)
backend/
  models.py                # BaseRecord, CashFlowSnapshot, CashFlowLineV2, Participacion, UploadResponse
  parser_excel_v2.py       # Parser Excel → DataFrame / objetos
  table_builder.py         # TableBuilder.build(): records → CashFlowSnapshot
  folder_loader.py         # carga por carpeta + etiquetas de versión (parse_fecha_label, make_fecha_label)
  validation_engine.py     # motor de reglas (módulo Auditoría, oculto)
  report_generator.py      # enriquecimiento de reportes de auditoría
  rules.json               # reglas de validación
data/
  base.parquet             # LA BASE que sirve la app (versionada en el repo)
tools/
  build_parquet.py         # regenera data/base.parquet desde un .xlsx
docs/                      # esta documentación
.streamlit/config.toml     # tema + runOnSave=false + headless
```

## Flujo de datos (el corazón)

```
data/base.parquet
      │  (_cargar_full_df: pd.read_parquet, ~2.5s, pico ~145MB)
      ▼
_load_shared_base()  @st.cache_resource   ← UNA copia, compartida por TODAS las sesiones
      │  DataFrame ~90MB (columnas categoría) + UploadResponse (catálogo) + files_meta
      ▼
_records_subset(proyecto, fecha, version)  ← filtra el DF y materializa SOLO ese
      │  subconjunto (~pocos miles de filas) como objetos BaseRecord
      ▼
builder.build(subset, proyecto, fecha, version)  → CashFlowSnapshot
      │  (memoizado por sesión en _build_snapshot, key = base_sig+proyecto+fecha+version)
      ▼
UI (Reporte Proyecto, Comparación, etc.)  ← consume snapshots en solo-lectura
```

### Por qué este diseño (crítico — no revertir sin entender)

El diseño resuelve **dos causas de OOM** en Streamlit Community Cloud (~1 GB de RAM):

1. **Materializar toda la base como objetos por sesión.** Antes, `st.session_state.records`
   guardaba ~980K objetos Pydantic `BaseRecord` **por sesión** (~800 MB), y se duplicaba
   con la caché. Con varios usuarios simultáneos era garantía de OOM. **Solución:** un
   único DataFrame compartido vía `@st.cache_resource` (una sola copia en RAM sin importar
   cuántos usuarios), y materializar solo el subconjunto de un snapshot bajo demanda.

2. **Parsear el `.xlsx` grande con openpyxl.** Leer el Excel de 980K filas dispara la RAM
   a **>600 MB** (medido con `tracemalloc`; el RSS real es mayor) y tarda ~260s → tumba el
   contenedor al arrancar (síntoma en logs: `healthz: EOF` sin traceback). **Solución:**
   servir un **Parquet** pre-generado (`data/base.parquet`, ~3.4 MB) que carga en ~2.5s con
   pico ~145 MB. **El `.xlsx` NO va al repo**; el fallback que parsea Excel solo debe correr
   en local o con bases pequeñas.

## Parser (`backend/parser_excel_v2.py`)

Dos rutas que comparten la limpieza vectorizada (`_clean_columns`, sin `iterrows`):

- **Ruta DataFrame (la que usa la app):** `parse_dataframe` / `parse_base_excel_df(bytes)`
  → devuelve `(DataFrame, warnings, errors)` sin construir objetos. Bajo consumo de memoria.
- **Ruta objetos (legada / carga por subida):** `_build_records` / `parse_base_excel(bytes)`
  → devuelve `(List[BaseRecord], UploadResponse)`.

Ambas seleccionan **exactamente las mismas filas** (verificado con test diferencial). El
parser tolera variaciones de nombres de columna (aliases) y separa la columna combinada
`"<índice> <descripción>"` (formato "P&G") en índice + nombre de línea.

Columnas del DataFrame limpio: `proyecto, fecha_datos, fecha_flujo, indice, nombre_linea,
participacion, valor, fuente` (+ `version` que asigna el loader). Fechas como `date` de Python.

## Builder (`backend/table_builder.py`)

`TableBuilder.build(records, proyecto, fecha_datos, version)`:
1. Filtra por `(proyecto, fecha_datos, version)` — NUNCA mezcla versiones/cortes.
2. Arma matriz `(indice, participacion) → {fecha_flujo → valor}`.
3. Ordena índices con un comparador de índices jerárquicos, detecta subtotales.
4. Rellena meses faltantes con 0 y devuelve `CashFlowSnapshot` con líneas
   (`CashFlowLineV2`: indice, nombre, nivel, categoría, participación, es_subtotal,
   valores por mes, total_periodo).

Como `build` ya filtra internamente, pasarle el subconjunto pre-filtrado de
`_records_subset` es correcto (el filtro interno queda como no-op y conserva todo).

## Caché y memoización (en `app.py`)

- `@st.cache_resource _load_shared_base()`: la base compartida (una vez por proceso).
- `_build_snapshot()`: memoiza snapshots por sesión en `st.session_state["_snap_memo"]`,
  con clave `(base_sig, proyecto, fecha_iso, version)`. `base_sig` se renueva con
  `_nueva_firma_base()`.
- Helpers: `_hay_base()` (¿hay base?), `_get_base_df()` (el DataFrame compartido),
  `_records_subset()` (materializa un snapshot).
- Código legado presente pero **sin usar**: `_parse_excel_cached`, `_persist_base`,
  `_restore_base`, `_cached_base_is_fresh`, `_clear_base_cache`, `load_database_from_folder`.
  No se llaman (la base viene del parquet compartido). No dependas de ellos.

## Convenciones de UI relevantes

- Tablas HTML vía `st.markdown(unsafe_allow_html=True)` con clases CSS (`.pyg-table`,
  `.cat-*`, `.cmp-*`, `.hcmp`, `.kpi-box`, `.hitos-tbl`).
- Comparación usa **una sola `<table>`** (no tres tablas flex) para que las filas de los
  dos grupos y la diferencia queden alineadas; `table-layout:auto` para que las columnas
  se ajusten al contenido sin desperdiciar espacio y sin scroll horizontal.
