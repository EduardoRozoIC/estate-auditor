# Estate Auditor — Contexto del proyecto para Claude

> Este archivo lo lee automáticamente cualquier sesión de Claude conectada al repo.
> Es la **fuente de verdad del contexto**: qué es la app, cómo trabajarla, su
> arquitectura, su dominio y las convenciones. Léelo completo antes de actuar.

---

## ⚠️ PROTOCOLO OBLIGATORIO — documentar SIEMPRE en el repo, nunca solo en local

**Toda sesión de Claude que trabaje en este proyecto (esta o cualquier otra, en
cualquier equipo) DEBE dejar su rastro en el repositorio, no en memoria local.**
El objetivo es que al conectar un chat nuevo NO haya que re-explicar nada: todo el
conocimiento, las decisiones y el estado viven versionados en Git.

Reglas del protocolo:

1. **El contexto del proyecto va al repo, no a la memoria local de Claude.** La
   función de "memoria" local de Claude es por-equipo y NO se transfiere a otras
   sesiones. Si aprendes algo del proyecto que valga la pena recordar, escríbelo en
   `CLAUDE.md` o en `docs/`, no (solo) en memoria local.
2. **Después de cada cambio o decisión relevante**, antes de terminar el turno:
   - Actualiza el/los doc afectados en `docs/` si cambió arquitectura, dominio o
     despliegue.
   - Añade una entrada al final de [`docs/DECISIONES.md`](docs/DECISIONES.md) (la
     bitácora): fecha, qué se hizo y **por qué** (incluye alternativas descartadas).
   - Registra el cambio en [`CHANGELOG.md`](CHANGELOG.md) si es funcional/visible.
   - Si cambió una convención o "cómo se trabaja", actualiza este `CLAUDE.md`.
3. **Haz `git commit` + `git push` de esos documentos junto con el código.** Un
   cambio no está "terminado" hasta que su documentación está en el repo remoto.
   Nada debe quedar aislado en la máquina local.
4. **Mensajes de commit descriptivos** (qué y por qué). `git log` es parte del
   registro histórico; escríbelos pensando en que otra sesión los leerá.
5. Si el usuario te pide algo que contradice estas convenciones, síguelo pero
   **documenta la excepción** en la bitácora.

En resumen: **si trabajaste en el proyecto y no lo escribiste en el repo, no pasó.**

---

## Qué es este proyecto

**Estate Auditor** (título en la app: *Estructuración*) es una app web en **Streamlit**
para **IC Constructora SAS**, una constructora/desarrolladora inmobiliaria en Colombia.
Sirve para analizar la **factibilidad financiera** y el **flujo de caja** de sus
proyectos inmobiliarios: P&G, indicadores (TIR, utilidad, equity), cronograma de
hitos, y comparación entre proyectos.

- **Repo:** `github.com/EduardoRozoIC/estate-auditor` (PÚBLICO).
- **Desplegada en:** Streamlit Community Cloud → `estructuracion-ic.streamlit.app`.
- **Usuario principal:** Eduardo (dirige estructuración en IC). Idioma de trabajo:
  **español**.

> ⚠️ **Repo público:** no incluyas datos personales ni sensibles en el código, docs
> o commits (correos, credenciales, información financiera privada, rutas personales
> innecesarias). Mantén todo profesional y acotado a la app y su dominio.

---

## Cómo trabajar en este proyecto (convenciones y "trampas")

- **Idioma:** responde en español.
- **Lanzar la app localmente (Windows/PowerShell):** hazlo como **proceso
  independiente** para que sobreviva entre turnos de herramientas; nunca como tarea
  en segundo plano del tooling (la mata al cerrar el turno → exit 255). Patrón:
  ```powershell
  Start-Process -FilePath "py" -ArgumentList "-m","streamlit","run","app.py","--server.port","8501" `
    -WorkingDirectory $proj -WindowStyle Hidden `
    -RedirectStandardOutput "$proj\.cache\st.out.log" -RedirectStandardError "$proj\.cache\st.err.log"
  ```
  También existe `run_app.bat` / `run_app.ps1`.
- **`runOnSave=false`** en `.streamlit/config.toml`: tras editar el código, el usuario
  **debe refrescar / Rerun** en el navegador para ver los cambios. Avísale.
- **Editar archivos con acentos/emojis:** usa la herramienta **Edit**, NO
  `PowerShell -replace` ni reescrituras con `Set-Content` (introducen BOM/mojibake
  que rompe el parseo del `.py`). Escribe siempre UTF-8 sin BOM.
- **Valida sintaxis antes de commit:** `py -c "import ast; ast.parse(open('app.py',encoding='utf-8').read())"`.
- **Verifica visualmente antes de entregar** gráficos o tablas: renderiza a imagen
  (kaleido/Playwright) o usa `streamlit.testing.v1.AppTest`, y revisa que no haya
  textos encimados, ejes ilegibles ni recortes. Eduardo es **muy sensible** a errores
  visuales. Las tablas deben **caber en pantalla sin scroll horizontal**.
- **Flujo de despliegue:** editar → `git commit` → `git push`. Streamlit Cloud
  redespliega solo en ~1-2 min. Cada deploy es un proceso nuevo (la caché
  `cache_resource` se recarga sola).
- **Nunca parsees el `.xlsx` grande en la nube.** Ver Arquitectura / Despliegue: la
  base se sirve como `data/base.parquet`. Parsear el Excel con openpyxl dispara la
  RAM > 600 MB y tumba el contenedor de 1 GB (OOM).
- **Tema corporativo:** vinotinto `#681E1E`. Logo `LOGO IC 2026.png`.

---

## Arquitectura en una frase

La base (≈980K filas, 59 proyectos) se carga UNA vez desde `data/base.parquet` como un
**DataFrame compacto compartido entre todas las sesiones** (`@st.cache_resource`), y
cada reporte materializa **solo** las filas de un `(proyecto, corte)` puntual como
objetos para construir su snapshot. Detalle completo en
[`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md).

---

## Mapa de módulos (navegación del sidebar)

- **📂 Base de Datos** — estado de la carga (registros, proyectos, versiones de corte)
  y lista de proyectos/versiones disponibles. Ya no se cargan archivos a mano; la base
  viene de `data/base.parquet`.
- **📊 Reporte Proyecto** — reporte ejecutivo por proyecto(s) y corte. Pestañas, en
  orden: `💰 Factibilidad (P&G)`, `📏 Indicadores`, `🧑‍💼 Inversionista`,
  `🏞️ Forma de pago Lote`, `📅 Cronograma`, `📋 Flujo de Caja`, `📈 Flujo Acumulado`.
- **🆚 Comparación Proyectos** — dos grupos de proyectos lado a lado en una sola tabla
  unificada + columna de **Diferencia (B−A)**; debajo, TIR FCO / TIR K y tablas de
  hitos por grupo.
- **Ocultos (código presente, fuera del nav, "en desarrollo"):** `🔍 Auditoría` y
  `💼 Flujo Proyecto (Control)`. No borrarlos; se habilitarán más adelante.

Detalle de dominio (P&G, índices de línea, participación, TIR) en
[`docs/DOMINIO.md`](docs/DOMINIO.md).

---

## Actualizar la base de datos

La app lee `data/base.parquet`. Para actualizarla con datos nuevos:

1. El usuario entrega el Excel fuente (hoja **ERConsolidado** del consolidador, o su
   copia `Pipeline.xlsx`). **Ese `.xlsx` NO se sube al repo.**
2. Genera el parquet localmente:
   ```powershell
   py tools/build_parquet.py "ruta\al\archivo.xlsx"
   ```
   Esto limpia, asigna versión y escribe `data/base.parquet`.
3. `git add data/base.parquet && git commit && git push`.

Ver [`docs/DESPLIEGUE.md`](docs/DESPLIEGUE.md) para el detalle y el procedimiento de
**Reboot** en Streamlit Cloud (necesario si el contenedor quedó en mal estado tras un
OOM).

---

## Documentos de referencia

- [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) — flujo de datos, base Parquet
  compartida, diseño de memoria, internals de parser/builder/módulos.
- [`docs/DOMINIO.md`](docs/DOMINIO.md) — modelo de factibilidad inmobiliaria, tabla de
  índices de línea del P&G, participación, indicadores.
- [`docs/DESPLIEGUE.md`](docs/DESPLIEGUE.md) — GitHub → Streamlit Cloud, límites de
  RAM, reboot tras OOM, actualización de la base.
- [`docs/DECISIONES.md`](docs/DECISIONES.md) — bitácora cronológica de decisiones y el
  porqué de cada una (mantener al día, ver protocolo).
- [`CHANGELOG.md`](CHANGELOG.md) — registro de cambios funcionales.
- `git log` — historial detallado de commits.
