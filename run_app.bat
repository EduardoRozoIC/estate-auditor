@echo off
REM ── Lanzador de Estate Auditor ──
REM Arranca la app Streamlit en el puerto 8501 desde la carpeta correcta
REM y abre el navegador. Doble clic para usar.

cd /d "%~dp0"
echo Iniciando Estate Auditor en http://localhost:8501 ...
start "" http://localhost:8501
py -m streamlit run app.py --server.port 8501
pause
