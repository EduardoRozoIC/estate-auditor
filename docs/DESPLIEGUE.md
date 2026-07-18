# Despliegue y operación

## Dónde vive

- **Código:** GitHub `github.com/EduardoRozoIC/estate-auditor` (rama `main`, PÚBLICO).
- **App en producción:** Streamlit Community Cloud → `estructuracion-ic.streamlit.app`.
- Streamlit Cloud está conectado al repo: cada `git push` a `main` dispara un redeploy
  automático en ~1-2 min. Cada deploy es un **proceso nuevo** (la caché `cache_resource`
  se reconstruye desde cero → recarga `data/base.parquet`).

## Límite de RAM y OOM

Streamlit Community Cloud (plan gratuito) da **~1 GB de RAM**. Esto condiciona todo el
diseño de datos (ver `docs/ARQUITECTURA.md`):

- **NO parsear el `.xlsx` en la nube:** openpyxl leyendo ~980K filas dispara la RAM a
  >600 MB y tumba el contenedor. Por eso se sirve `data/base.parquet` (carga en ~2.5s,
  pico ~145 MB) y el `.xlsx` no está en el repo.
- Síntoma de OOM en los logs: `The service has encountered an error while checking the
  health of the Streamlit app: Get "http://localhost:8501/healthz": EOF` (sin traceback
  de Python — el proceso fue matado).

### Reboot tras un OOM (importante)

Después de un OOM, el contenedor queda en mal estado y **un auto-pull ("Updated app!") NO
lo recupera** — re-ejecuta el script en un proceso ya muerto. Hay que **reiniciar a mano**:

1. Ir a `https://share.streamlit.io/` (login con GitHub).
2. En la app de la lista, menú **⋮ → "Reboot"**. (También desde el panel "Manage app" de
   la propia app: menú **⋮ → "Reboot app"**.)
3. Esperar 2-3 min. En los logs debe aparecer un pull del último commit y la app cargando.

## Actualizar la base de datos (`data/base.parquet`)

La app lee **solo** `data/base.parquet`. Flujo para actualizar con datos frescos:

1. El usuario entrega el Excel fuente: la hoja **ERConsolidado** del consolidador
   (`...CONSOLIDADOR UNIFICADO...xlsm`) o su copia `Pipeline.xlsx`. Formato de columnas:
   `Proyecto, Fecha Datos, Fuente, P&G, TOTAL, Fecha, Valor`. **Ese `.xlsx` NO se sube al
   repo.**
2. Generar el parquet localmente:
   ```powershell
   py tools/build_parquet.py "C:\ruta\al\archivo.xlsx"
   ```
   El script: parsea (limpia filas basura: proyecto vacío, "P&G" que parece fecha,
   fechas inválidas), asigna `version` por `(proyecto, fecha_datos)` y escribe
   `data/base.parquet`. Reporta filas resultantes y nº de proyectos.
3. Verificar (opcional pero recomendado) con `AppTest` que la app arranca sin excepciones
   y con el nº de proyectos esperado.
4. `git add data/base.parquet && git commit -m "data: actualizar base.parquet ..." && git push`.
5. Si en la nube no refresca, hacer **Reboot** (ver arriba).

> La hoja ERConsolidado ya viene en **formato largo** (una fila por
> proyecto × línea P&G × mes), así que el mapeo al esquema de la app es directo, sin
> pivoteo. Solo se separa la columna `P&G` en índice + nombre y se deriva la
> participación (total por defecto; IC/Socio si el nombre lo indica).

## Arranque local (desarrollo)

- `py -m streamlit run app.py --server.port 8501` (o `run_app.bat` / `run_app.ps1`).
- Para que la app sobreviva entre turnos de una sesión de Claude, lanzarla como proceso
  **independiente** (`Start-Process ... -WindowStyle Hidden`), no como tarea en segundo
  plano del tooling.
- `runOnSave=false`: tras editar, refrescar/Rerun en el navegador para ver cambios.
- En local, si hay `data/base.parquet`, la app lo usa (rápido). Si no, cae al fallback que
  parsea `.xlsx` de `data/` (alto consumo de memoria; solo para local).

## Enlaces en la app

- Sidebar: enlace **ORIGINACIÓN** → `huggingface.co/spaces/CGIRALDO/ori19` (app hermana de
  originación, mantenida aparte).
