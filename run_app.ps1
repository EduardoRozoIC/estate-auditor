# ── Lanzador de Estate Auditor (PowerShell) ──
# Verifica si el puerto 8501 ya está en uso; si no, lanza la app y abre el navegador.

Set-Location -Path $PSScriptRoot

$puerto = 8501
$enUso = Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue

if ($enUso) {
    Write-Host "La app ya parece estar corriendo en http://localhost:$puerto" -ForegroundColor Yellow
    Start-Process "http://localhost:$puerto"
} else {
    Write-Host "Iniciando Estate Auditor en http://localhost:$puerto ..." -ForegroundColor Green
    Start-Process "http://localhost:$puerto"
    py -m streamlit run app.py --server.port $puerto
}
