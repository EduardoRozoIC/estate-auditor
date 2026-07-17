"""
parser_excel_v2.py — CashFlow Auditor v2
==========================================
Parser robusto del Excel BASE (sistema de información versionado).

CONTRATO DE DATOS ESPERADO:
  La hoja principal del Excel debe tener estas columnas (en cualquier orden):
    - Proyecto       → str   (nombre del proyecto)
    - Fecha_Datos    → date  (fecha de corte / versión del snapshot)
    - Fecha_Flujo    → date  (mes al que corresponde el valor)
    - Indice         → str   (índice estructural: "1.1", "2.3.1", etc.)
    - Nombre_Linea   → str   (nombre descriptivo de la línea)
    - Participacion  → str   ("total" | "ic" | "socio")
    - Valor          → float (valor monetario o de unidades)

  El parser acepta variaciones en mayúsculas/espacios y aliases comunes.

REGLA CRÍTICA:
  NO mezcla información entre distintas fechas de corte.
  Cada (proyecto, fecha_datos) es un universo aislado.
"""

import pandas as pd
import numpy as np
from io import BytesIO
from typing import List, Tuple, Dict, Optional
from datetime import date
import re

from .models import BaseRecord, Participacion, UploadResponse


# ─────────────────────────────────────────────
# MAPAS DE ALIASES PARA TOLERANCIA DE NOMBRES
# ─────────────────────────────────────────────

ALIAS_PROYECTO: List[str] = [
    "proyecto", "project", "nombre_proyecto", "cod_proyecto", "id_proyecto"
]
ALIAS_FECHA_DATOS: List[str] = [
    "fecha_datos", "fecha_corte", "corte", "fecha_version", "version", "fecha_snapshot"
]
ALIAS_FECHA_FLUJO: List[str] = [
    "fecha_flujo", "fecha", "mes", "periodo", "fecha_mes", "month"
]
ALIAS_INDICE: List[str] = [
    "indice", "índice", "codigo", "código", "code", "id_linea", "linea_id", "idx", "p&g", "pyg"
]
ALIAS_NOMBRE: List[str] = [
    "nombre_linea", "nombre", "linea", "línea", "descripcion", "description", "name"
]
ALIAS_PARTICIPACION: List[str] = [
    "participacion", "participación", "tipo_participacion", "part", "participation", "tipo", "total"
]
ALIAS_VALOR: List[str] = [
    "valor", "value", "amount", "monto", "importe"
]
ALIAS_FUENTE: List[str] = [
    "fuente", "source", "tipo_fuente", "origen", "estado_proyecto"
]

VALID_PARTICIPACION_VALUES: Dict[str, str] = {
    "total": "total", "tot": "total", "0": "total", "0.0": "total", "0.": "total",
    "ic":    "ic",    "inv": "ic", "compania": "ic", "compañia": "ic",
    "socio": "socio", "soc": "socio", "partner": "socio",
}


# ─────────────────────────────────────────────
# UTILIDADES INTERNAS
# ─────────────────────────────────────────────

def _normalize_col(name: str) -> str:
    """Normaliza nombre de columna: minúsculas, sin espacios, sin acentos."""
    name = str(name).strip().lower()
    name = name.replace(" ", "_").replace("-", "_")
    # Reemplazar caracteres con tilde (simplificado para columnas comunes)
    replacements = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
    for src, dst in replacements.items():
        name = name.replace(src, dst)
    return name


def _find_column(df_cols_normalized: Dict[str, str], aliases: List[str]) -> Optional[str]:
    """
    Busca el nombre real de una columna dado un listado de aliases normalizados.
    df_cols_normalized: {nombre_normalizado: nombre_original}
    """
    for alias in aliases:
        if alias in df_cols_normalized:
            return df_cols_normalized[alias]
    return None


def _try_parse_date(value) -> Optional[date]:
    """Parsea fechas en múltiples formatos comunes de Excel."""
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp, date)):
        return value.date() if isinstance(value, pd.Timestamp) else value

    val_str = str(value).strip()

    formats = [
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
        "%Y/%m/%d", "%d-%m-%Y", "%Y%m%d",
        "%d-%b-%Y", "%b-%Y", "%Y-%m",
    ]
    for fmt in formats:
        try:
            return pd.to_datetime(val_str, format=fmt).date()
        except (ValueError, TypeError):
            continue

    # Intento genérico
    try:
        return pd.to_datetime(val_str).date()
    except Exception:
        return None


def _normalize_indice(raw: str) -> str:
    """Normaliza un índice estructural: elimina espacios, fuerza punto como separador."""
    s = str(raw).strip()
    # algunos Excel usan coma decimal → reemplazar solo si parece índice
    if re.match(r"^\d+[,\.]\d", s):
        s = s.replace(",", ".")
    return s


# ─────────────────────────────────────────────
# CLASE PRINCIPAL
# ─────────────────────────────────────────────

class ExcelBaseParser:
    """
    Parser del Excel BASE para el sistema CashFlow Auditor.
    Convierte el Excel en una lista de BaseRecord listos para ser procesados.
    """

    def __init__(self, sheet_name: Optional[str] = None):
        """
        sheet_name: si None, intenta detectar automáticamente la hoja de datos.
        """
        self._sheet_name = sheet_name
        self._warnings: List[str] = []
        self._errors: List[str] = []

    # ──────────────────────────────────────────
    # PUNTO DE ENTRADA PRINCIPAL
    # ──────────────────────────────────────────

    def parse(self, excel_bytes: bytes) -> Tuple[List[BaseRecord], List[str], List[str]]:
        """
        Parsea el Excel y retorna (registros, warnings, errors).
        Los errors son fatales; los warnings son recuperables.
        """
        self._warnings = []
        self._errors = []

        try:
            df_raw = self._load_sheet(excel_bytes)
        except Exception as exc:
            self._errors.append(f"No se pudo leer el archivo Excel: {exc}")
            return [], self._warnings, self._errors

        col_map = self._detect_columns(df_raw)
        if self._errors:
            return [], self._warnings, self._errors

        records = self._build_records(df_raw, col_map)
        return records, self._warnings, self._errors

    # ──────────────────────────────────────────
    # CARGA DE HOJA
    # ──────────────────────────────────────────

    def _load_sheet(self, excel_bytes: bytes) -> pd.DataFrame:
        """
        Carga el Excel y combina datos de TODAS las hojas que tengan el formato esperado.
        Esto permite procesar archivos como el Histórico que tienen una hoja por proyecto.
        """
        xl = pd.ExcelFile(BytesIO(excel_bytes), engine="openpyxl")
        sheets = xl.sheet_names

        # Si se especifica una hoja explícita, usar solo esa
        if self._sheet_name:
            if self._sheet_name not in sheets:
                raise ValueError(
                    f"Hoja '{self._sheet_name}' no encontrada. "
                    f"Hojas disponibles: {sheets}"
                )
            return xl.parse(self._sheet_name)

        # Combinar TODAS las hojas que tengan el formato esperado.
        # Una hoja "válida" tiene al menos las columnas Proyecto, Fecha Datos y Valor.
        dfs_combinados: List[pd.DataFrame] = []
        hojas_validas: List[str] = []
        hojas_descartadas: List[str] = []

        for sheet in sheets:
            try:
                df_sheet = xl.parse(sheet)
                if df_sheet.empty:
                    hojas_descartadas.append(f"{sheet} (vacía)")
                    continue
                # Validar columnas mínimas (normalizadas)
                cols_norm = {_normalize_col(c) for c in df_sheet.columns}
                tiene_proyecto = bool(cols_norm & set(ALIAS_PROYECTO))
                tiene_fecha_datos = bool(cols_norm & set(ALIAS_FECHA_DATOS))
                tiene_valor = bool(cols_norm & set(ALIAS_VALOR))
                if not (tiene_proyecto and tiene_fecha_datos and tiene_valor):
                    hojas_descartadas.append(
                        f"{sheet} (faltan columnas: proyecto={tiene_proyecto}, "
                        f"fecha_datos={tiene_fecha_datos}, valor={tiene_valor})"
                    )
                    continue
                dfs_combinados.append(df_sheet)
                hojas_validas.append(sheet)
            except Exception as exc:
                hojas_descartadas.append(f"{sheet} (error: {exc})")

        if not dfs_combinados:
            raise ValueError(
                f"Ninguna hoja válida encontrada. Descartadas: {hojas_descartadas}"
            )

        # Combinar todas las hojas válidas — pandas alinea columnas automáticamente
        df_combinado = pd.concat(dfs_combinados, ignore_index=True)

        self._warnings.append(
            f"Procesadas {len(hojas_validas)} hojas válidas: {hojas_validas}"
        )
        if hojas_descartadas:
            self._warnings.append(
                f"Hojas descartadas (sin formato esperado): {hojas_descartadas}"
            )

        return df_combinado

    # ──────────────────────────────────────────
    # DETECCIÓN DE COLUMNAS
    # ──────────────────────────────────────────

    def _detect_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Construye un mapa {rol: nombre_real_en_df} para las 7 columnas requeridas.
        Falla si alguna columna obligatoria no se puede ubicar.
        """
        norm_map = {_normalize_col(c): c for c in df.columns}

        col_map = {
            "proyecto":      _find_column(norm_map, ALIAS_PROYECTO),
            "fecha_datos":   _find_column(norm_map, ALIAS_FECHA_DATOS),
            "fecha_flujo":   _find_column(norm_map, ALIAS_FECHA_FLUJO),
            "indice":        _find_column(norm_map, ALIAS_INDICE),
            "nombre_linea":  _find_column(norm_map, ALIAS_NOMBRE),
            "participacion": _find_column(norm_map, ALIAS_PARTICIPACION),
            "valor":         _find_column(norm_map, ALIAS_VALOR),
            "fuente":        _find_column(norm_map, ALIAS_FUENTE),  # opcional
        }

        missing = [rol for rol, col in col_map.items() if col is None and rol != "nombre_linea"]
        if missing:
            self._errors.append(
                f"Columnas obligatorias no encontradas: {missing}. "
                f"Columnas detectadas en el archivo: {list(df.columns)}"
            )

        return col_map

    # ──────────────────────────────────────────
    # CONSTRUCCIÓN DE REGISTROS
    # ──────────────────────────────────────────

    def _build_records(
        self,
        df: pd.DataFrame,
        col_map: Dict[str, str]
    ) -> List[BaseRecord]:
        """
        Construye BaseRecord a partir del DataFrame usando operaciones vectorizadas
        de pandas (en vez de iterrows fila-a-fila) — crítico para archivos con
        cientos de miles de filas, donde iterrows es órdenes de magnitud más lento.
        Descarta filas inválidas con warning agregado (no uno por fila).
        """
        n_total = len(df)

        # ── Proyecto: strip + colapsar espacios múltiples ──
        proyecto_s = df[col_map["proyecto"]].astype(str).str.strip()
        proyecto_s = proyecto_s.str.replace(r"\s+", " ", regex=True)
        mask_proyecto = df[col_map["proyecto"]].notna() & (proyecto_s != "") & (proyecto_s.str.lower() != "nan")

        # ── Fechas: parseo vectorizado (Excel ya entrega datetime en la mayoría de casos) ──
        fecha_datos_s = pd.to_datetime(df[col_map["fecha_datos"]], errors="coerce", dayfirst=False)
        mask_fecha_datos = fecha_datos_s.notna()

        fecha_flujo_s = pd.to_datetime(df[col_map["fecha_flujo"]], errors="coerce", dayfirst=False)
        mask_fecha_flujo = fecha_flujo_s.notna()

        # ── Índice y Nombre ──
        indice_raw_s = df[col_map["indice"]].astype(str).str.strip()
        mask_indice = df[col_map["indice"]].notna() & (indice_raw_s != "") & (indice_raw_s.str.lower() != "nan")

        if col_map.get("nombre_linea"):
            nombre_col = df[col_map["nombre_linea"]]
            nombre_linea_s = nombre_col.astype(str).str.strip()
            nombre_linea_s = nombre_linea_s.where(nombre_col.notna(), "")
            # Normalizar índice: forzar punto decimal si el patrón lo sugiere
            _comma_pattern = indice_raw_s.str.match(r"^\d+[,\.]\d")
            indice_s = indice_raw_s.where(~_comma_pattern, indice_raw_s.str.replace(",", ".", regex=False))
        else:
            # Separar "<indice> <descripcion>" (columna combinada tipo "P&G")
            split_parts = indice_raw_s.str.split(" ", n=1, expand=True)
            indice_part = split_parts[0]
            nombre_part = split_parts[1] if split_parts.shape[1] > 1 else pd.Series([None] * n_total, index=df.index)
            nombre_linea_s = nombre_part.where(nombre_part.notna(), indice_raw_s).str.strip()
            _comma_pattern = indice_part.str.match(r"^\d+[,\.]\d")
            indice_s = indice_part.where(~_comma_pattern, indice_part.str.replace(",", ".", regex=False))

        # ── Participación ──
        part_raw_s = df[col_map["participacion"]].astype(str).str.strip().str.lower()
        participacion_s = part_raw_s.map(VALID_PARTICIPACION_VALUES).fillna("total")

        # ── Valor ──
        valor_orig = df[col_map["valor"]]
        valor_num_s = pd.to_numeric(valor_orig, errors="coerce")
        mask_valor_invalido = valor_num_s.isna() & valor_orig.notna()
        n_valor_invalido = int(mask_valor_invalido.sum())
        valor_s = valor_num_s.fillna(0.0)

        # ── Fuente (opcional) ──
        if col_map.get("fuente"):
            fuente_col = df[col_map["fuente"]]
            fuente_s = fuente_col.astype(str).str.strip()
            fuente_s = fuente_s.where(fuente_col.notna() & (fuente_s != ""), "desconocida")
        else:
            fuente_s = pd.Series(["desconocida"] * n_total, index=df.index)

        # ── Máscara final de filas válidas ──
        mask_valida = mask_proyecto & mask_fecha_datos & mask_fecha_flujo & mask_indice
        n_skipped = n_total - int(mask_valida.sum())

        # Filtrar todas las series a las filas válidas, en el mismo orden
        proyecto_f = proyecto_s[mask_valida].to_numpy()
        fecha_datos_f = fecha_datos_s[mask_valida].dt.date.to_numpy()
        fecha_flujo_f = fecha_flujo_s[mask_valida].dt.date.to_numpy()
        indice_f = indice_s[mask_valida].to_numpy()
        nombre_linea_f = nombre_linea_s[mask_valida].to_numpy()
        participacion_f = participacion_s[mask_valida].to_numpy()
        valor_f = valor_s[mask_valida].to_numpy()
        fuente_f = fuente_s[mask_valida].to_numpy()

        records: List[BaseRecord] = [
            BaseRecord(
                proyecto=proyecto_f[i],
                fecha_datos=fecha_datos_f[i],
                fecha_flujo=fecha_flujo_f[i],
                indice=indice_f[i],
                nombre_linea=nombre_linea_f[i],
                participacion=Participacion(participacion_f[i]),
                valor=float(valor_f[i]),
                fuente=fuente_f[i],
            )
            for i in range(len(proyecto_f))
        ]

        if n_skipped > 0:
            self._warnings.append(
                f"Total de filas omitidas durante el parsing: {n_skipped}"
            )
        if n_valor_invalido > 0:
            self._warnings.append(
                f"Filas con valor no numérico (se asignó 0): {n_valor_invalido}"
            )

        return records

    @property
    def warnings(self) -> List[str]:
        return self._warnings

    @property
    def errors(self) -> List[str]:
        return self._errors


# ─────────────────────────────────────────────
# FUNCIÓN DE CONVENIENCIA (usada por la API)
# ─────────────────────────────────────────────

def parse_base_excel(
    excel_bytes: bytes,
    sheet_name: Optional[str] = None
) -> Tuple[List[BaseRecord], UploadResponse]:
    """
    Punto de entrada único para la API.
    Retorna (registros, UploadResponse con metadatos).
    """
    parser = ExcelBaseParser(sheet_name=sheet_name)
    records, warnings, errors = parser.parse(excel_bytes)

    if errors:
        raise ValueError(
            "El archivo Excel no cumple el esquema requerido:\n" +
            "\n".join(errors)
        )

    # Construir catálogo proyecto → fechas
    proyectos_set: Dict[str, set] = {}
    for r in records:
        if r.proyecto not in proyectos_set:
            proyectos_set[r.proyecto] = set()
        proyectos_set[r.proyecto].add(r.fecha_datos.isoformat())

    fechas_por_proyecto = {
        p: sorted(list(f)) for p, f in proyectos_set.items()
    }

    response = UploadResponse(
        proyectos=sorted(list(proyectos_set.keys())),
        fechas_datos=fechas_por_proyecto,
        total_registros=len(records),
        warnings=warnings,
    )

    return records, response
