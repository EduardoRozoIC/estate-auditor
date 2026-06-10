# Registro de cambios — Estate Auditor

Bitácora legible de las mejoras aplicadas. Cada bloque corresponde a un commit
de git; para revertir un cambio puntual usar `git log` + `git revert <hash>` o
`git checkout <hash> -- <archivo>`.

---

## Fase 0 — Fundamentos operativos (2026-06-10)

### 0.1 Control de versiones
- Se inicializó **git** en la raíz del proyecto.
- Se añadió `.gitignore` (excluye `__pycache__`, `node_modules`, `.cache`,
  Excel fuente, secretos de Streamlit, etc.).
- **Commit inicial** captura el estado completo del proyecto antes de cualquier
  modificación → permite revertir todo a este punto.

### 0.2 Dependencias fijadas
- `requirements.txt` pasó de nombres sueltos a **versiones exactas** instaladas
  y verificadas:
  pandas 3.0.2, numpy 2.4.4, openpyxl 3.1.5, pydantic 2.13.3,
  streamlit 1.57.0, plotly 6.7.0.

### 0.3 Corrección del error de config TOML
- **Causa:** `C:\Users\erozo\.streamlit\config.toml` (config global) tenía un
  BOM UTF-8 (`EF BB BF`) antes de `[browser]`; la librería `toml` de
  Streamlit 1.57 no lo tolera → error en cada arranque.
- **Fix:** reescrito el archivo **sin BOM** (mismo contenido).
- Se añadió un `.streamlit/config.toml` **a nivel de proyecto** con tema
  corporativo (vinotinto IC) y `gatherUsageStats=false`.

### 0.4 Script de arranque
- `run_app.bat` y `run_app.ps1`: lanzan la app en el puerto 8501 desde la
  carpeta correcta, sin tener que recordar el comando.

### 0.5 Limpieza de código muerto (commit separado, reversible)
- Eliminados (no los importa la app Streamlit):
  - `frontend/` (experimento Vite/JS abandonado, incluía `node_modules`)
  - `backend/api_server.py`, `backend/main.py` (servidor FastAPI legado)
  - `read_excel.ps1` (script suelto de pruebas)
- Recuperables desde el historial de git si hicieran falta.

### Pendiente / no ejecutado
- **0.6 Mover el proyecto fuera de OneDrive:** NO ejecutado por ser disruptivo
  (cambia rutas, requiere decisión del usuario). Recomendado a futuro para
  evitar locks de sincronización durante edición.

---

## Fase 1 — Eficiencia y estabilidad (2026-06-10)

### 1.1 Caché de parseo de Excel
- `backend/folder_loader.py`: `load_database_from_folder` ahora acepta un
  parámetro opcional `parse_fn` (compatible hacia atrás; por defecto usa
  `parse_base_excel`).
- `app.py`: parser cacheado `_parse_excel_cached` con `@st.cache_data`
  (keyed por bytes del archivo). Re-cargar un Excel idéntico ya no lo
  re-parsea. Inyectado en la carga por carpeta y en la subida manual.

### 1.2 Persistencia de la base en disco
- Tras cada carga exitosa se guarda `{records, upload_response, files_processed,
  saved_at}` en `.cache/last_base.pkl` (carpeta ignorada por git).
- Al arrancar, si no hay base en sesión pero existe el archivo, se
  **restaura automáticamente** → recargar la página o reabrir la app ya no
  obliga a re-procesar los Excel.
- En "📂 Cargar Base" aparece un aviso "Base restaurada del último guardado
  (fecha)" con botón **🗑️ Limpiar caché**.
- Helpers nuevos en `app.py`: `_persist_base`, `_restore_base`,
  `_clear_base_cache` (todos best-effort: nunca tumban la app).
- Verificado: round-trip de pickle de los modelos Pydantic funciona.
