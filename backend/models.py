"""
models.py — CashFlow Auditor v2
================================
Sistema de modelos de datos para la validación de flujos de caja inmobiliarios.

PRINCIPIO FUNDAMENTAL:
  - BaseRecord es el átomo de información (una línea, un mes, una versión).
  - CashFlowSnapshot es la reconstrucción completa para (proyecto, fecha_datos).
  - NO se mezcla información entre distintas fechas de corte.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Literal, Any
from datetime import date, datetime
from enum import Enum


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class Participacion(str, Enum):
    TOTAL = "total"
    IC    = "ic"
    SOCIO = "socio"

class Severidad(str, Enum):
    CRITICO      = "critico"
    ADVERTENCIA  = "advertencia"
    INFORMATIVO  = "informativo"

class CategoriaLinea(str, Enum):
    OPERATIVO  = "operativo"     # Ingresos, Costos, Gastos, Inversión
    FINANCIERO = "financiero"    # FCL, Fuentes, Usos
    SOPORTE    = "soporte"       # Ventas (uds), Ventas (m²), Escrituraciones
    SUBTOTAL   = "subtotal"      # Líneas calculadas / agrupaciones


# ─────────────────────────────────────────────
# CAPA 1: REGISTRO ATÓMICO (FUENTE DE VERDAD)
# ─────────────────────────────────────────────

class BaseRecord(BaseModel):
    """
    Unidad mínima de información extraída del Excel BASE.

    Representa: proyecto × fecha_datos × fecha_flujo × índice × participación → valor
    Cada 'fecha_datos' es un snapshot completo (pasado real + futuro proyectado).
    """
    proyecto:      str            = Field(..., description="Identificador del proyecto")
    fecha_datos:   date           = Field(..., description="Fecha de corte (versión del snapshot)")
    fecha_flujo:   date           = Field(..., description="Mes al que corresponde el valor")
    indice:        str            = Field(..., description="Índice estructural: '1.1', '2.3.1', etc.")
    nombre_linea:  str            = Field(..., description="Nombre descriptivo de la línea")
    participacion: Participacion  = Field(..., description="Dimensión de participación: total | ic | socio")
    valor:         float          = Field(..., description="Valor monetario o de unidades")
    version:       int            = Field(1, description="Versión/sub-corte cuando existen múltiples archivos para la misma (proyecto, fecha_datos)")
    fuente:        str            = Field("desconocida", description="Clasificación: 'Proyectos' (control) | 'Estructuración' | 'desconocida'")

    class Config:
        use_enum_values = True


# ─────────────────────────────────────────────
# CAPA 2: LÍNEA JERÁRQUICA DEL FLUJO
# ─────────────────────────────────────────────

class CashFlowLineV2(BaseModel):
    """
    Línea del flujo de caja reconstruido con jerarquía y valores temporales.
    La jerarquía se infiere del índice: "1." → nivel 1, "1.1" → nivel 2, etc.
    """
    indice:        str                   = Field(..., description="Índice estructural de la línea")
    nombre:        str                   = Field(..., description="Nombre de la línea")
    nivel:         int                   = Field(..., description="Profundidad jerárquica (1=raíz)")
    categoria:     CategoriaLinea        = Field(..., description="Categoría funcional de la línea")
    participacion: Participacion         = Field(..., description="Dimensión de participación")
    es_subtotal:   bool                  = Field(False, description="True si es línea calculada/agrupación")
    valores:       Dict[str, float]      = Field(default_factory=dict,
                                                  description="Valores por fecha: {'2024-01-01': 100.0}")
    total_periodo: float                 = Field(0.0, description="Suma del flujo completo")

    class Config:
        use_enum_values = True


# ─────────────────────────────────────────────
# CAPA 3: SNAPSHOT DEL FLUJO COMPLETO
# ─────────────────────────────────────────────

class SnapshotMetadata(BaseModel):
    total_registros:   int   = 0
    total_meses:       int   = 0
    total_lineas:      int   = 0
    tiene_ic:          bool  = False
    tiene_socio:       bool  = False
    prefijos_detectados: List[str] = Field(default_factory=list)

class CashFlowSnapshot(BaseModel):
    """
    Reconstrucción completa del flujo de caja para un (proyecto, fecha_datos).
    Es la unidad de análisis sobre la que se ejecutan las validaciones.

    REGLA CRÍTICA: Solo contiene registros de una única fecha_datos.
    """
    proyecto:     str                  = Field(..., description="Identificador del proyecto")
    fecha_datos:  date                 = Field(..., description="Fecha de corte de este snapshot")
    fechas_flujo: List[str]            = Field(default_factory=list,
                                               description="Columnas temporales ordenadas (ISO strings)")
    lineas:       List[CashFlowLineV2] = Field(default_factory=list,
                                               description="Líneas del flujo ordenadas por índice")
    metadata:     SnapshotMetadata     = Field(default_factory=SnapshotMetadata)


# ─────────────────────────────────────────────
# CAPA 4: MOTOR DE VALIDACIONES
# ─────────────────────────────────────────────

class ValidationRule(BaseModel):
    """
    Regla de validación declarativa. Vive en rules.json, NO en el código.
    El motor la interpreta y ejecuta dinámicamente.
    """
    id:          str                    = Field(..., description="Identificador único, ej: 'VAL-001'")
    nombre:      str                    = Field(..., description="Nombre corto de la validación")
    descripcion: str                    = Field(..., description="Descripción completa")
    severidad:   Severidad              = Field(..., description="critico | advertencia | informativo")
    activa:      bool                   = Field(True, description="Si False, la regla se omite")
    tipo:        str                    = Field(..., description="Tipo de evaluador: existencia, matematica, participacion, etc.")
    config:      Dict[str, Any]         = Field(default_factory=dict,
                                                description="Configuración específica del tipo de regla")

    class Config:
        use_enum_values = True


class ValidationResult(BaseModel):
    """
    Resultado de ejecutar una ValidationRule sobre un CashFlowSnapshot.
    El campo 'explicacion_financiera' debe redactarse como lo haría un analista senior.
    """
    validation_id:          str             = Field(..., description="ID de la regla ejecutada")
    nombre:                 str
    descripcion:            str
    severidad:              Severidad
    aprobado:               bool            = Field(..., description="True = regla pasa, False = regla falla")

    # Diagnóstico
    lineas_afectadas:       List[str]       = Field(default_factory=list,
                                                    description="Índices involucrados en la validación")
    valor_observado:        Optional[float] = None
    valor_esperado:         Optional[float] = None
    tolerancia:             float           = 0.0
    diferencia:             Optional[float] = None

    # Informe financiero
    explicacion_financiera: str             = Field("", description="Diagnóstico en lenguaje de analista senior")
    detalle_por_mes:        Optional[Dict[str, float]] = Field(None,
                                                               description="Diferencia mes a mes (si aplica)")

    class Config:
        use_enum_values = True


# ─────────────────────────────────────────────
# CAPA 5: INFORME EJECUTIVO
# ─────────────────────────────────────────────

class AuditSummary(BaseModel):
    """Cuadro de mando del informe ejecutivo."""
    total_validaciones:   int   = 0
    errores_criticos:     int   = 0
    advertencias:         int   = 0
    informativos:         int   = 0
    aprobadas:            int   = 0
    score_integridad:     float = Field(100.0, description="0-100, penaliza por tipo de error")
    estado_general:       str   = Field("OK", description="OK | REVISAR | RECHAZAR")

class AuditReport(BaseModel):
    """
    Informe completo de auditoría para (proyecto, fecha_datos).
    Diseñado para ser leído por un analista financiero senior o un comité de inversión.
    """
    proyecto:     str
    fecha_datos:  date
    generado_en:  datetime            = Field(default_factory=datetime.utcnow)
    resumen:      AuditSummary        = Field(default_factory=AuditSummary)
    validaciones: List[ValidationResult] = Field(default_factory=list)
    snapshot:     Optional[CashFlowSnapshot] = None   # incluido para trazabilidad


# ─────────────────────────────────────────────
# CAPA 6: MODELOS DE API (request / response)
# ─────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Respuesta al subir el Excel BASE."""
    proyectos:    List[str]
    fechas_datos: Dict[str, List[str]]   # {proyecto: [fecha1, fecha2, ...]}
    total_registros: int
    warnings:     List[str] = Field(default_factory=list)

class SnapshotRequest(BaseModel):
    proyecto:    str
    fecha_datos: str   # ISO date string

class ValidateRequest(BaseModel):
    proyecto:    str
    fecha_datos: str   # ISO date string

class RuleUpdateRequest(BaseModel):
    activa:      Optional[bool]         = None
    severidad:   Optional[Severidad]    = None
    config:      Optional[Dict[str, Any]] = None


# ─────────────────────────────────────────────
# COMPATIBILIDAD HACIA ATRÁS (deprecado)
# ─────────────────────────────────────────────
# Mantenidos para no romper el endpoint /api/analysis/mock y engine.py legado.

class ContratoClause(BaseModel):
    category:          str
    valor:             float       = 0.0
    base_calculo:      str         = ""
    timing_pago:       str         = ""
    condicion_especial: Optional[str] = None
    texto_original:    str         = ""

class ContratoModel(BaseModel):
    clausulas: List[ContratoClause]

class CashFlowLine(BaseModel):
    codigo:            str
    nombre:            str
    valores_mensuales: List[float]

class CashFlowModel(BaseModel):
    lineas: List[CashFlowLine]

class Alerta(BaseModel):
    severidad:    str
    mensaje:      str
    diferencia:   Optional[float] = None
    clausula_ref: Optional[str]   = None
    flujo_ref:    Optional[str]   = None

class AnalysisResult(BaseModel):
    score_consistencia: float
    alertas:            List[Alerta]
    detalle_calculos:   Dict[str, float]
