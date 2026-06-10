"""
table_builder.py — CashFlow Auditor v2
========================================
Reconstruye el flujo de caja estándar (CashFlowSnapshot) a partir de
una lista de BaseRecord filtrados por (proyecto, fecha_datos).

RESPONSABILIDADES:
  1. Filtrar registros por proyecto + fecha_datos (STRICTo — no se mezclan versiones)
  2. Ordenar líneas por índice estructural (orden numérico jerárquico, no lexicográfico)
  3. Inferir jerarquía y nivel de cada línea a partir del índice
  4. Detectar qué líneas tienen hijos (son subtotales/agrupaciones)
  5. Construir la matriz de valores: {indice → {fecha_flujo → valor}}
  6. Calcular totales del período por línea
  7. Asignar categorías financieras por prefijo de índice
  8. Retornar CashFlowSnapshot validado y listo para el motor de reglas

REGLA CRÍTICA:
  Total Proyecto = IC + Socio debe verificarse en TODAS las líneas aplicables.
  Esta verificación es responsabilidad del ValidationEngine, NO del TableBuilder.
  El TableBuilder solo garantiza que las tres vistas existan en el Snapshot.
"""

from typing import List, Dict, Optional, Tuple
from datetime import date
from functools import cmp_to_key
import re
from collections import defaultdict

from .models import (
    BaseRecord,
    CashFlowLineV2,
    CashFlowSnapshot,
    SnapshotMetadata,
    Participacion,
    CategoriaLinea,
)


# ─────────────────────────────────────────────
# MAPA DE CATEGORÍAS POR PREFIJO DE ÍNDICE
# ─────────────────────────────────────────────

# Configurable: mapea el prefijo numérico del índice a la categoría financiera.
# IMPORTANTE: Este mapa se debe ajustar al esquema real de índices del cliente.
CATEGORIA_POR_PREFIJO: Dict[str, CategoriaLinea] = {
    "1":  CategoriaLinea.OPERATIVO,   # Ingresos
    "2":  CategoriaLinea.OPERATIVO,   # Costos
    "3":  CategoriaLinea.OPERATIVO,   # Gastos
    "4":  CategoriaLinea.OPERATIVO,   # Inversión
    "5":  CategoriaLinea.FINANCIERO,  # Flujo de Caja Libre (FCL)
    "6":  CategoriaLinea.FINANCIERO,  # Fuentes
    "7":  CategoriaLinea.FINANCIERO,  # Usos
    "8":  CategoriaLinea.FINANCIERO,  # FCL con financiamiento
    "17": CategoriaLinea.SOPORTE,     # Ventas (unidades)
    "18": CategoriaLinea.SOPORTE,     # Ventas (m²)
    "19": CategoriaLinea.SOPORTE,     # Escrituraciones
}

DEFAULT_CATEGORIA = CategoriaLinea.OPERATIVO


# ─────────────────────────────────────────────
# UTILIDADES DE ÍNDICES
# ─────────────────────────────────────────────

def _parse_indice(indice: str) -> List[int]:
    """
    Convierte un índice estructural en lista de enteros para ordenamiento correcto.
    "1.10.2" → [1, 10, 2]   (no "1" < "10" como string)
    """
    parts = []
    for part in indice.split("."):
        part = part.strip()
        if part.isdigit():
            parts.append(int(part))
        else:
            # Índice alfanumérico: usar orden lexicográfico como fallback
            parts.append(part)
    return parts


def _compare_indices(a: str, b: str) -> int:
    """Comparador para ordenamiento jerárquico correcto de índices."""
    pa = _parse_indice(a)
    pb = _parse_indice(b)

    for va, vb in zip(pa, pb):
        if type(va) == type(vb):
            if va < vb:
                return -1
            if va > vb:
                return 1
        else:
            # mezcla de int y str: convertir a str
            if str(va) < str(vb):
                return -1
            if str(va) > str(vb):
                return 1

    # Prefijo igual: el más corto va primero (índice padre antes que hijos)
    return len(pa) - len(pb)


def _get_nivel(indice: str) -> int:
    """
    Nivel jerárquico en el árbol (1 = raíz).
    "1"     → 1
    "1.1"   → 2
    "1.1.1" → 3
    """
    return len(indice.split("."))


def _get_prefijo_raiz(indice: str) -> str:
    """Extrae el prefijo raíz (primer segmento del índice)."""
    return indice.split(".")[0]


def _get_categoria(indice: str) -> CategoriaLinea:
    """Asigna categoría financiera según el prefijo raíz del índice."""
    prefijo = _get_prefijo_raiz(indice)
    return CATEGORIA_POR_PREFIJO.get(prefijo, DEFAULT_CATEGORIA)


def _detectar_subtotales(todos_los_indices: List[str]) -> set:
    """
    Un índice es 'subtotal' (padre) si tiene al menos un hijo directo.
    Hijo directo de "1.0" seria "1.0.1" (no "1.1").
    """
    subtotales = set()
    indices_set = set(todos_los_indices)

    for indice in todos_los_indices:
        partes = indice.split(".")
        for i in range(1, len(partes)):
            padre = ".".join(partes[:i])
            if padre in indices_set:
                subtotales.add(padre)

    return subtotales


# ─────────────────────────────────────────────
# CLASE PRINCIPAL
# ─────────────────────────────────────────────

class TableBuilder:
    """
    Reconstruye el flujo de caja estándar a partir de BaseRecord.

    Uso:
        builder = TableBuilder()
        snapshot = builder.build(records, proyecto="PROYECTO_A", fecha_datos=date(2024,3,31))
    """

    def build(
        self,
        records: List[BaseRecord],
        proyecto: str,
        fecha_datos: date,
        version: int = 1,
    ) -> CashFlowSnapshot:
        """
        Punto de entrada principal. Devuelve el CashFlowSnapshot completo.

        Cuando hay varias versiones para el mismo (proyecto, fecha_datos)
        — porque la carpeta de la base contiene múltiples archivos para el
        mismo corte —, se filtra adicionalmente por `version` para mantener
        cada sub-corte aislado.
        """
        # ── 1. FILTRAR por proyecto + fecha_datos + version (NUNCA mezclar versiones) ──
        filtered = [
            r for r in records
            if r.proyecto == proyecto
            and r.fecha_datos == fecha_datos
            and getattr(r, "version", 1) == version
        ]

        if not filtered:
            raise ValueError(
                f"No se encontraron registros para "
                f"proyecto='{proyecto}' | fecha_datos={fecha_datos} | version={version}"
            )

        # ── 2. CONSTRUIR MATRIZ: (indice, participacion) → {fecha_flujo → valor} ──
        matriz: Dict[Tuple[str, str], Dict[str, float]] = defaultdict(dict)
        nombres: Dict[str, str] = {}

        for r in filtered:
            key = (r.indice, r.participacion)
            fecha_str = r.fecha_flujo.isoformat()
            matriz[key][fecha_str] = r.valor
            if r.indice not in nombres:
                nombres[r.indice] = r.nombre_linea

        # ── 3. OBTENER FECHAS ORDENADAS ──
        all_fechas = sorted(set(
            r.fecha_flujo.isoformat() for r in filtered
        ))

        # ── 4. ORDENAR ÍNDICES ÚNICOS ──
        indices_unicos = sorted(
            set(r.indice for r in filtered),
            key=cmp_to_key(_compare_indices)
        )

        # ── 5. DETECTAR SUBTOTALES (índices que tienen hijos) ──
        subtotales = _detectar_subtotales(indices_unicos)

        # ── 6. DETECTAR PARTICIPACIONES PRESENTES ──
        participaciones_presentes = set(r.participacion for r in filtered)

        # ── 7. CONSTRUIR LÍNEAS ──
        lineas: List[CashFlowLineV2] = []

        for indice in indices_unicos:
            for part in [Participacion.TOTAL, Participacion.IC, Participacion.SOCIO]:
                if part not in participaciones_presentes:
                    continue

                key = (indice, part)
                valores_map = matriz.get(key, {})

                # Rellenar meses faltantes con 0
                valores_completos = {f: valores_map.get(f, 0.0) for f in all_fechas}
                total = sum(valores_completos.values())

                lineas.append(CashFlowLineV2(
                    indice=indice,
                    nombre=nombres.get(indice, ""),
                    nivel=_get_nivel(indice),
                    categoria=_get_categoria(indice),
                    participacion=part,
                    es_subtotal=(indice in subtotales),
                    valores=valores_completos,
                    total_periodo=total,
                ))

        # ── 8. METADATA ──
        metadata = SnapshotMetadata(
            total_registros=len(filtered),
            total_meses=len(all_fechas),
            total_lineas=len(indices_unicos),
            tiene_ic=Participacion.IC in participaciones_presentes,
            tiene_socio=Participacion.SOCIO in participaciones_presentes,
            prefijos_detectados=sorted(set(
                _get_prefijo_raiz(i) for i in indices_unicos
            )),
        )

        return CashFlowSnapshot(
            proyecto=proyecto,
            fecha_datos=fecha_datos,
            fechas_flujo=all_fechas,
            lineas=lineas,
            metadata=metadata,
        )

    def get_lineas_por_prefijo(
        self,
        snapshot: CashFlowSnapshot,
        prefijo: str,
        participacion: Participacion,
    ) -> List[CashFlowLineV2]:
        """
        Helper: retorna todas las líneas cuyo índice empieza con 'prefijo'
        y tienen la participación indicada.
        """
        return [
            l for l in snapshot.lineas
            if l.indice.startswith(prefijo) and l.participacion == participacion
        ]

    def get_linea_exacta(
        self,
        snapshot: CashFlowSnapshot,
        indice: str,
        participacion: Participacion,
    ) -> Optional[CashFlowLineV2]:
        """
        Helper: retorna la línea con índice EXACTO y participación indicada.
        """
        for linea in snapshot.lineas:
            if linea.indice == indice and linea.participacion == participacion:
                return linea
        return None

    def sum_prefijo_por_mes(
        self,
        snapshot: CashFlowSnapshot,
        prefijo: str,
        participacion: Participacion,
    ) -> Dict[str, float]:
        """
        Helper: suma por mes todas las líneas que empiezan con 'prefijo'
        para una participación dada.
        Retorna {fecha_str: suma_total}
        """
        lineas = self.get_lineas_por_prefijo(snapshot, prefijo, participacion)
        resultado: Dict[str, float] = {f: 0.0 for f in snapshot.fechas_flujo}
        for linea in lineas:
            for fecha, valor in linea.valores.items():
                resultado[fecha] = resultado.get(fecha, 0.0) + valor
        return resultado
