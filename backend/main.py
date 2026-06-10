"""
main.py — CashFlow Auditor v2
================================
API FastAPI para el sistema de validación de flujos de caja inmobiliarios.

ENDPOINTS:
  POST /api/upload           → Sube Excel BASE, retorna proyectos y fechas disponibles
  POST /api/snapshot         → Reconstruye el flujo para (proyecto, fecha_datos)
  POST /api/validate         → Ejecuta todas las validaciones, retorna AuditReport
  GET  /api/validate/report  → Informe ejecutivo enriquecido (para el frontend)
  GET  /api/rules            → Lista de reglas activas
  PUT  /api/rules/{rule_id}  → Actualiza una regla en caliente

  [LEGADO] POST /api/analysis/mock → Datos de prueba para la UI antigua
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import date

# ── Módulos v2 ──────────────────────────────
from .models import (
    UploadResponse,
    SnapshotRequest,
    ValidateRequest,
    RuleUpdateRequest,
    CashFlowSnapshot,
    AuditReport,
    ValidationRule,
)
from .parser_excel_v2 import parse_base_excel
from .table_builder import TableBuilder
from .validation_engine import ValidationEngine
from .report_generator import enriquecer_reporte

# ── Módulos legado (compatibilidad) ─────────
# from .models import AnalysisResult  # re-exportado para /mock
# from .engine import analizar_coherencia          # engine.py ya no existe
# from .models import ContratoModel, ContratoClause, CashFlowModel as CashFlowModelLegado, CashFlowLine

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────

BASE_DIR     = Path(__file__).parent.parent
FRONTEND_DIR = BASE_DIR / "frontend" / "dist"
RULES_PATH   = Path(__file__).parent / "rules.json"

app = FastAPI(
    title="CashFlow Auditor — Real Estate",
    description="Sistema de validación automática de flujos de caja inmobiliarios",
    version="2.0.0",
)

# CORS: permite origen del dev server de React (Vite :5173) y producción
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# ESTADO EN MEMORIA
# (En producción se reemplazaría por Redis / DB)
# ─────────────────────────────────────────────

_session_records: List = []       # List[BaseRecord] del último upload
_engine = ValidationEngine(str(RULES_PATH))
_builder = TableBuilder()


# ─────────────────────────────────────────────
# ENDPOINTS V2
# ─────────────────────────────────────────────

@app.post("/api/upload", response_model=UploadResponse, tags=["Ingesta"])
async def upload_base_excel(
    file: UploadFile = File(..., description="Archivo Excel BASE (sistema versionado)")
):
    """
    Paso 1: Carga el Excel BASE y extrae el catálogo de proyectos y fechas de corte.
    Los registros se mantienen en sesión para los siguientes pasos.
    """
    global _session_records

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Solo se aceptan archivos Excel (.xlsx, .xls)"
        )

    content = await file.read()

    try:
        records, response = parse_base_excel(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    _session_records = records
    return response


@app.post("/api/snapshot", response_model=CashFlowSnapshot, tags=["Flujo"])
async def get_snapshot(body: SnapshotRequest):
    """
    Paso 2+3: Reconstruye el flujo de caja estándar para (proyecto, fecha_datos).
    Requiere haber hecho upload previamente.
    """
    if not _session_records:
        raise HTTPException(
            status_code=400,
            detail="No hay datos cargados. Ejecute primero POST /api/upload."
        )

    try:
        fecha = date.fromisoformat(body.fecha_datos)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Fecha inválida: '{body.fecha_datos}'")

    try:
        snapshot = _builder.build(_session_records, body.proyecto, fecha)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return snapshot


@app.post("/api/validate", response_model=AuditReport, tags=["Validación"])
async def validate(body: ValidateRequest):
    """
    Paso 4+5: Ejecuta TODAS las validaciones activas sobre (proyecto, fecha_datos).
    Retorna el AuditReport completo con ValidationResult por regla.
    """
    if not _session_records:
        raise HTTPException(
            status_code=400,
            detail="No hay datos cargados. Ejecute primero POST /api/upload."
        )

    try:
        fecha = date.fromisoformat(body.fecha_datos)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Fecha inválida: '{body.fecha_datos}'")

    try:
        snapshot = _builder.build(_session_records, body.proyecto, fecha)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    report = _engine.generate_report(snapshot, include_snapshot=True)
    return report


@app.post("/api/validate/report", tags=["Validación"])
async def validate_report(body: ValidateRequest):
    """
    Informe ejecutivo enriquecido con narrativa financiera.
    Versión optimizada para el frontend del dashboard.
    """
    if not _session_records:
        raise HTTPException(status_code=400, detail="No hay datos cargados.")

    try:
        fecha = date.fromisoformat(body.fecha_datos)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Fecha inválida: '{body.fecha_datos}'")

    try:
        snapshot = _builder.build(_session_records, body.proyecto, fecha)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    report   = _engine.generate_report(snapshot, include_snapshot=True)
    enriched = enriquecer_reporte(report)
    return JSONResponse(content=enriched)


# ─────────────────────────────────────────────
# GESTIÓN DE REGLAS
# ─────────────────────────────────────────────

@app.get("/api/rules", response_model=List[ValidationRule], tags=["Reglas"])
async def get_rules():
    """Lista todas las reglas de validación (activas e inactivas)."""
    _engine.reload_rules()
    return _engine.get_rules()


@app.put("/api/rules/{rule_id}", response_model=ValidationRule, tags=["Reglas"])
async def update_rule(rule_id: str, body: RuleUpdateRequest):
    """
    Actualiza una regla en caliente (sin reiniciar el servidor).
    Solo se actualizan los campos enviados en el body.
    """
    updates = body.dict(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar.")

    try:
        updated = _engine.update_rule(rule_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return updated


@app.post("/api/rules/reload", tags=["Reglas"])
async def reload_rules():
    """Recarga las reglas desde rules.json sin reiniciar el servidor."""
    count = _engine.reload_rules()
    return {"message": f"{count} reglas recargadas exitosamente."}


# ─────────────────────────────────────────────
# ENDPOINT LEGADO (mock — compatibilidad con UI anterior)
# ─────────────────────────────────────────────

@app.post("/api/analysis/mock", tags=["Legado"])
async def run_mock_analysis():
    """[LEGADO] Endpoint deshabilitado — módulo engine.py fue removido."""
    raise HTTPException(status_code=410, detail="Endpoint legado deshabilitado.")


# ─────────────────────────────────────────────
# FRONTEND (sirve React en producción)
# ─────────────────────────────────────────────

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        """Sirve la SPA de React para cualquier ruta no-API."""
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return JSONResponse(
            {"detail": "Frontend no construido. Ejecute 'npm run build' en /frontend"},
            status_code=503
        )
else:
    @app.get("/")
    async def root():
        return {
            "app": "CashFlow Auditor v2",
            "status": "Backend activo",
            "docs": "/docs",
            "nota": "Frontend no encontrado. Ejecute 'npm run build' en /frontend.",
        }


# ─────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
