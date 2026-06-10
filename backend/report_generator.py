"""
report_generator.py — CashFlow Auditor v2
==========================================
Generador de informes ejecutivos enriquecidos.

Toma un AuditReport (output del ValidationEngine) y lo enriquece con:
  - Narrativa ejecutiva del estado del proyecto
  - Priorización de hallazgos por impacto financiero
  - Secciones en lenguaje de analista financiero senior

El informe está diseñado para ser leído por un Comité de Inversión,
NO como un log técnico.
"""

from typing import List, Dict, Optional
from datetime import datetime

from .models import AuditReport, ValidationResult, Severidad


# ─────────────────────────────────────────────
# NARRATIVAS POR ESTADO GENERAL
# ─────────────────────────────────────────────

NARRATIVAS_ESTADO = {
    "OK": (
        "El flujo de caja ha superado el proceso de validación automática con un nivel "
        "de integridad satisfactorio. Las identidades financieras fundamentales se cumplen "
        "y no se detectaron inconsistencias críticas. Se recomienda proceder con el análisis "
        "de rentabilidad sobre este modelo."
    ),
    "REVISAR": (
        "El flujo de caja presenta inconsistencias que requieren atención antes de ser "
        "utilizado para decisiones de inversión. Se han detectado advertencias que, si bien "
        "no rompen la lógica financiera fundamental, pueden distorsionar los indicadores "
        "de rentabilidad (TIR, VPN, payback). Se sugiere revisar las líneas afectadas "
        "con el equipo de estructuración antes de aprobar el modelo."
    ),
    "RECHAZAR": (
        "El flujo de caja contiene errores críticos que comprometen la integridad del modelo "
        "financiero. Las identidades fundamentales (FCL, cuadre de participación, balance "
        "fuentes/usos) no se cumplen. Este modelo NO debe utilizarse para evaluación de "
        "inversión hasta que los errores sean corregidos y el proceso de validación sea "
        "ejecutado nuevamente."
    ),
}


NIVEL_URGENCIA = {
    Severidad.CRITICO:     1,
    Severidad.ADVERTENCIA: 2,
    Severidad.INFORMATIVO: 3,
}


# ─────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────

def enriquecer_reporte(report: AuditReport) -> Dict:
    """
    Transforma el AuditReport en un diccionario estructurado para el frontend.
    Incluye narrativa ejecutiva, hallazgos priorizados y secciones formateadas.
    """
    # Separar resultados
    fallidas = [v for v in report.validaciones if not v.aprobado]
    aprobadas = [v for v in report.validaciones if v.aprobado]

    # Ordenar fallidas por urgencia
    fallidas_ordenadas = sorted(
        fallidas,
        key=lambda v: (NIVEL_URGENCIA.get(Severidad(v.severidad), 99), v.validation_id)
    )

    # Narrativa ejecutiva
    estado = report.resumen.estado_general
    narrativa = NARRATIVAS_ESTADO.get(estado, "Estado desconocido.")

    # Secciones del informe
    return {
        "encabezado": {
            "proyecto":     report.proyecto,
            "fecha_datos":  report.fecha_datos.isoformat(),
            "generado_en":  report.generado_en.strftime("%Y-%m-%d %H:%M UTC"),
            "estado":       estado,
            "score":        report.resumen.score_integridad,
        },
        "resumen_ejecutivo": {
            "narrativa":          narrativa,
            "total_validaciones": report.resumen.total_validaciones,
            "aprobadas":          report.resumen.aprobadas,
            "errores_criticos":   report.resumen.errores_criticos,
            "advertencias":       report.resumen.advertencias,
            "informativos":       report.resumen.informativos,
        },
        "hallazgos": [_formatear_hallazgo(v) for v in fallidas_ordenadas],
        "validaciones_ok": [
            {"id": v.validation_id, "nombre": v.nombre}
            for v in aprobadas
        ],
        "metadata_snapshot": _metadata_snapshot(report),
    }


def _formatear_hallazgo(v: ValidationResult) -> Dict:
    """Formatea un ValidationResult como hallazgo ejecutivo."""
    return {
        "id":                    v.validation_id,
        "nombre":                v.nombre,
        "descripcion":           v.descripcion,
        "severidad":             v.severidad,
        "lineas_afectadas":      v.lineas_afectadas,
        "valor_observado":       _fmt_numero(v.valor_observado),
        "valor_esperado":        _fmt_numero(v.valor_esperado),
        "diferencia":            _fmt_numero(v.diferencia),
        "tolerancia":            _fmt_numero(v.tolerancia),
        "explicacion_financiera": v.explicacion_financiera,
        "detalle_por_mes":       v.detalle_por_mes or {},
    }


def _metadata_snapshot(report: AuditReport) -> Dict:
    """Extrae metadata del snapshot para el panel de contexto."""
    if not report.snapshot:
        return {}

    meta = report.snapshot.metadata
    return {
        "total_meses":         meta.total_meses,
        "total_lineas":        meta.total_lineas,
        "total_registros":     meta.total_registros,
        "tiene_ic":            meta.tiene_ic,
        "tiene_socio":         meta.tiene_socio,
        "prefijos_detectados": meta.prefijos_detectados,
        "rango_fechas": {
            "inicio": report.snapshot.fechas_flujo[0] if report.snapshot.fechas_flujo else None,
            "fin":    report.snapshot.fechas_flujo[-1] if report.snapshot.fechas_flujo else None,
        },
    }


def _fmt_numero(valor: Optional[float]) -> Optional[str]:
    """Formatea número con separadores de miles y 2 decimales."""
    if valor is None:
        return None
    return f"{valor:,.2f}"
