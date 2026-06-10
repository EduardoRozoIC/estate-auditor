"""
validation_engine.py — CashFlow Auditor v2
============================================
Motor de validaciones dinámico basado en reglas declarativas (rules.json).

PRINCIPIOS FUNDAMENTALES:
  1. NINGUNA regla vive en este archivo.
     Toda la lógica está en rules.json y puede modificarse sin reiniciar.
  2. Este motor solo INTERPRETA y EJECUTA las reglas.
  3. Cada tipo de validación tiene un handler dedicado.
  4. Agregar un nuevo TIPO requiere solo añadir un handler y registrarlo en _handlers.
  5. Los resultados usan lenguaje de analista financiero senior, no logs técnicos.

TIPOS DE VALIDACIÓN SOPORTADOS:
  - participacion:        Total Proyecto == IC + Socio (por línea, por mes)
  - existencia:           Líneas obligatorias no son cero/nulas
  - matematica:           Expresiones algebraicas entre grupos de líneas (DSL propio)
  - estructural:          Suma de hijos == valor del padre
  - coherencia_economica: Relaciones entre líneas de soporte y operativas
"""

import json
import re
import math
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime

from .models import (
    CashFlowSnapshot,
    CashFlowLineV2,
    ValidationRule,
    ValidationResult,
    AuditReport,
    AuditSummary,
    Participacion,
    Severidad,
)
from .table_builder import TableBuilder


# ─────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────

SCORE_PENALIZACION = {
    Severidad.CRITICO:     40,
    Severidad.ADVERTENCIA: 15,
    Severidad.INFORMATIVO:  5,
}

ESTADO_POR_SCORE = {
    (80, 101): "OK",
    (50,  80): "REVISAR",
    (  0, 50): "RECHAZAR",
}


def _estado_desde_score(score: float) -> str:
    for (lo, hi), estado in ESTADO_POR_SCORE.items():
        if lo <= score < hi:
            return estado
    return "RECHAZAR"


# ─────────────────────────────────────────────
# MOTOR PRINCIPAL
# ─────────────────────────────────────────────

class ValidationEngine:
    """
    Motor de validaciones de flujos de caja inmobiliarios.

    Carga reglas desde un archivo JSON y las ejecuta sobre un CashFlowSnapshot.
    Las reglas pueden modificarse en caliente (reload_rules).
    """

    def __init__(self, rules_path: str):
        self._rules_path = Path(rules_path)
        self._builder = TableBuilder()
        self._rules: List[ValidationRule] = []
        self._handlers: Dict[str, Callable] = {
            "participacion":        self._eval_participacion,
            "existencia":           self._eval_existencia,
            "matematica_total":     self._eval_matematica,
            "matematica_mensual":   self._eval_matematica,
            "estructural":          self._eval_estructural,
            "coherencia_economica": self._eval_coherencia_economica,
        }
        self.reload_rules()

    # ──────────────────────────────────────────
    # GESTIÓN DE REGLAS
    # ──────────────────────────────────────────

    def reload_rules(self) -> int:
        """Recarga reglas desde el JSON. Retorna número de reglas cargadas."""
        with open(self._rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._rules = [
            ValidationRule(**rule) for rule in data.get("validaciones", [])
        ]
        return len(self._rules)

    def get_rules(self) -> List[ValidationRule]:
        return self._rules

    def update_rule(self, rule_id: str, updates: Dict[str, Any]) -> ValidationRule:
        """Actualiza una regla en memoria y persiste el JSON."""
        with open(self._rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        found = False
        for rule in data["validaciones"]:
            if rule["id"] == rule_id:
                rule.update(updates)
                found = True
                break

        if not found:
            raise ValueError(f"Regla '{rule_id}' no encontrada en rules.json")

        with open(self._rules_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self.reload_rules()
        updated = next(r for r in self._rules if r.id == rule_id)
        return updated

    # ──────────────────────────────────────────
    # EJECUCIÓN PRINCIPAL
    # ──────────────────────────────────────────

    def run_all(self, snapshot: CashFlowSnapshot) -> List[ValidationResult]:
        """Ejecuta TODAS las reglas activas sobre el snapshot. Sin excepciones."""
        results: List[ValidationResult] = []

        for rule in self._rules:
            if not rule.activa:
                continue

            handler = self._handlers.get(rule.tipo)
            if handler is None:
                # Tipo desconocido → informativo
                results.append(ValidationResult(
                    validation_id=rule.id,
                    nombre=rule.nombre,
                    descripcion=rule.descripcion,
                    severidad=Severidad.INFORMATIVO,
                    aprobado=False,
                    lineas_afectadas=[],
                    explicacion_financiera=(
                        f"Tipo de validación '{rule.tipo}' no reconocido por el motor. "
                        f"Verifique el archivo rules.json."
                    ),
                ))
                continue

            try:
                result = handler(rule, snapshot)
            except Exception as exc:
                result = ValidationResult(
                    validation_id=rule.id,
                    nombre=rule.nombre,
                    descripcion=rule.descripcion,
                    severidad=Severidad.INFORMATIVO,
                    aprobado=False,
                    lineas_afectadas=[],
                    explicacion_financiera=(
                        f"Error interno al ejecutar la validación: {exc}. "
                        f"Revise la configuración de la regla en rules.json."
                    ),
                )

            results.append(result)

        return results

    def generate_report(
        self,
        snapshot: CashFlowSnapshot,
        include_snapshot: bool = True,
    ) -> AuditReport:
        """Ejecuta todas las reglas y genera el AuditReport completo."""
        resultados = self.run_all(snapshot)

        # Calcular resumen
        criticos    = sum(1 for r in resultados if not r.aprobado and r.severidad == Severidad.CRITICO)
        advertencias = sum(1 for r in resultados if not r.aprobado and r.severidad == Severidad.ADVERTENCIA)
        informativos = sum(1 for r in resultados if not r.aprobado and r.severidad == Severidad.INFORMATIVO)
        aprobadas   = sum(1 for r in resultados if r.aprobado)

        score = 100.0
        score -= criticos    * SCORE_PENALIZACION[Severidad.CRITICO]
        score -= advertencias * SCORE_PENALIZACION[Severidad.ADVERTENCIA]
        score -= informativos * SCORE_PENALIZACION[Severidad.INFORMATIVO]
        score = max(0.0, score)

        resumen = AuditSummary(
            total_validaciones=len(resultados),
            errores_criticos=criticos,
            advertencias=advertencias,
            informativos=informativos,
            aprobadas=aprobadas,
            score_integridad=round(score, 1),
            estado_general=_estado_desde_score(score),
        )

        return AuditReport(
            proyecto=snapshot.proyecto,
            fecha_datos=snapshot.fecha_datos,
            generado_en=datetime.utcnow(),
            resumen=resumen,
            validaciones=resultados,
            snapshot=snapshot if include_snapshot else None,
        )

    # ──────────────────────────────────────────
    # HANDLER: PARTICIPACIÓN
    # Total Proyecto == IC + Socio (por mes, por línea del prefijo)
    # ──────────────────────────────────────────

    def _eval_participacion(
        self, rule: ValidationRule, snapshot: CashFlowSnapshot
    ) -> ValidationResult:
        cfg = rule.config
        prefijo = cfg["prefijo_indice"]
        tolerancia = float(cfg.get("tolerancia_absoluta", 1.0))

        if not snapshot.metadata.tiene_ic or not snapshot.metadata.tiene_socio:
            return ValidationResult(
                validation_id=rule.id,
                nombre=rule.nombre,
                descripcion=rule.descripcion,
                severidad=Severidad.INFORMATIVO,
                aprobado=True,
                lineas_afectadas=[],
                explicacion_financiera=(
                    "El snapshot no contiene dimensiones IC y/o Socio. "
                    "La validación de participación no aplica (proyecto sin socio)."
                ),
            )

        # Sumar por mes, por participación, todas las líneas del prefijo
        sum_total = self._builder.sum_prefijo_por_mes(snapshot, prefijo, Participacion.TOTAL)
        sum_ic    = self._builder.sum_prefijo_por_mes(snapshot, prefijo, Participacion.IC)
        sum_socio = self._builder.sum_prefijo_por_mes(snapshot, prefijo, Participacion.SOCIO)

        diferencias: Dict[str, float] = {}
        meses_fallidos = []

        for fecha in snapshot.fechas_flujo:
            diff = sum_total.get(fecha, 0.0) - (
                sum_ic.get(fecha, 0.0) + sum_socio.get(fecha, 0.0)
            )
            diferencias[fecha] = diff
            if abs(diff) > tolerancia:
                meses_fallidos.append(fecha)

        aprobado = len(meses_fallidos) == 0
        indices_afectados = sorted(set(
            l.indice for l in snapshot.lineas
            if l.indice.startswith(prefijo)
        ))

        if aprobado:
            explicacion = (
                f"✓ El cuadre Total = IC + Socio se cumple en todos los meses "
                f"para las líneas con prefijo '{prefijo}'. "
                f"Tolerancia aplicada: {tolerancia:,.0f}."
            )
        else:
            max_diff = max(abs(diferencias[m]) for m in meses_fallidos)
            explicacion = (
                f"⚠ Se detectaron {len(meses_fallidos)} mes(es) donde "
                f"Total ≠ IC + Socio para las líneas con prefijo '{prefijo}'. "
                f"La máxima diferencia observada es {max_diff:,.2f}. "
                f"Esto indica que los valores por participación no cuadran con el total del proyecto, "
                f"lo que puede implicar un error en la distribución de resultados entre socios "
                f"o un ajuste contable no registrado. "
                f"Meses afectados: {', '.join(meses_fallidos[:5])}"
                f"{'...' if len(meses_fallidos) > 5 else ''}."
            )

        return ValidationResult(
            validation_id=rule.id,
            nombre=rule.nombre,
            descripcion=rule.descripcion,
            severidad=Severidad(rule.severidad),
            aprobado=aprobado,
            lineas_afectadas=indices_afectados,
            tolerancia=tolerancia,
            diferencia=max(abs(v) for v in diferencias.values()) if diferencias else 0.0,
            explicacion_financiera=explicacion,
            detalle_por_mes={k: v for k, v in diferencias.items() if abs(v) > tolerancia},
        )

    # ──────────────────────────────────────────
    # HANDLER: EXISTENCIA
    # Líneas no pueden ser cero/nulas
    # ──────────────────────────────────────────

    def _eval_existencia(
        self, rule: ValidationRule, snapshot: CashFlowSnapshot
    ) -> ValidationResult:
        cfg = rule.config
        prefijo = cfg["prefijo_indice"]
        part_str = cfg.get("participacion", "total")
        condicion = cfg.get("condicion", "total_sum > 0")

        try:
            participacion = Participacion(part_str)
        except ValueError:
            participacion = Participacion.TOTAL

        lineas = self._builder.get_lineas_por_prefijo(snapshot, prefijo, participacion)
        total_sum = sum(l.total_periodo for l in lineas)

        # Evaluar condición
        contexto = {"total_sum": total_sum}
        try:
            aprobado = bool(eval(condicion, {"__builtins__": {}}, contexto))
        except Exception:
            aprobado = total_sum != 0

        indices = [l.indice for l in lineas]

        if aprobado:
            explicacion = (
                f"✓ Las líneas con prefijo '{prefijo}' registran actividad "
                f"({total_sum:,.2f} en el período completo). "
                f"La condición de existencia se cumple."
            )
        else:
            explicacion = (
                f"⚠ Las líneas con prefijo '{prefijo}' no cumplen la condición esperada. "
                f"Valor acumulado en el período: {total_sum:,.2f}. "
                f"Condición requerida: '{condicion}'. "
                f"Un flujo de caja sin actividad en este grupo de líneas es inconsistente "
                f"con un proyecto de desarrollo inmobiliario activo. "
                f"Verifique si el archivo BASE contiene todos los períodos del proyecto."
            )

        return ValidationResult(
            validation_id=rule.id,
            nombre=rule.nombre,
            descripcion=rule.descripcion,
            severidad=Severidad(rule.severidad),
            aprobado=aprobado,
            lineas_afectadas=indices,
            valor_observado=total_sum,
            valor_esperado=None,
            explicacion_financiera=explicacion,
        )

    # ──────────────────────────────────────────
    # HANDLER: MATEMÁTICA
    # Evalúa expresiones DSL: SUM(1.) - SUM(2.) == LINE(5.0)
    # ──────────────────────────────────────────

    # ──────────────────────────────────────────
    # HANDLER: MATEMÁTICA TOTAL Y MENSUAL
    # ──────────────────────────────────────────

    def _eval_matematica(
        self, rule: ValidationRule, snapshot: CashFlowSnapshot
    ) -> ValidationResult:
        cfg = rule.config
        expresion = cfg["expresion"]
        part_str = cfg.get("participacion", "total")
        tol_rel = float(cfg.get("tolerancia_relativa", 0.001))
        tol_abs = float(cfg.get("tolerancia_absoluta", 100.0))
        por_mes = (rule.tipo == "matematica_mensual")

        try:
            participacion = Participacion(part_str)
        except ValueError:
            participacion = Participacion.TOTAL

        if por_mes:
            diferencias = {}
            meses_fallidos = []
            max_diferencia = 0.0
            
            valor_lhs_dict, valor_rhs_dict, lineas_involucradas = self._resolver_expresion_dsl_mensual(
                expresion, snapshot, participacion
            )
            
            for fecha in snapshot.fechas_flujo:
                val_lhs = valor_lhs_dict.get(fecha, 0.0)
                val_rhs = valor_rhs_dict.get(fecha, 0.0)
                diff = abs(val_lhs - val_rhs)
                
                # Tolerancia
                ref = max(abs(val_lhs), abs(val_rhs), 1.0)
                tol_efectiva = max(tol_abs, ref * tol_rel)
                
                # Soportar operadores de desigualdad
                aprobado_mes = True
                if "==" in expresion: aprobado_mes = diff <= tol_efectiva
                elif "<=" in expresion: aprobado_mes = val_lhs <= (val_rhs + tol_efectiva)
                elif ">=" in expresion: aprobado_mes = val_lhs >= (val_rhs - tol_efectiva)
                elif "<" in expresion: aprobado_mes = val_lhs < val_rhs
                elif ">" in expresion: aprobado_mes = val_lhs > val_rhs
                
                if not aprobado_mes:
                    meses_fallidos.append(fecha)
                    diferencias[fecha] = diff
                    max_diferencia = max(max_diferencia, diff)
            
            aprobado = len(meses_fallidos) == 0
            nombres_lineas = self._obtener_nombres_lineas_str(lineas_involucradas, snapshot, participacion)
            
            if aprobado:
                explicacion = (f"✓ La regla mes a mes se cumple: '{expresion}'.\\n"
                               f"Líneas evaluadas explícitamente: {nombres_lineas}")
                val_obs = None
                val_esp = None
            else:
                explicacion = (f"⚠ Falla de regla mensual: '{expresion}'.\\n"
                               f"Se detectó un rompimiento en {len(meses_fallidos)} periodos.\\n"
                               f"Líneas involucradas que generaron este descuadre: {nombres_lineas}.\\n"
                               f"La diferencia máxima encontrada fue {max_diferencia:,.2f}. "
                               f"Un desbalance mes a mes implica que hay meses contables donde la partida no cruza.")
                peor_mes = meses_fallidos[0]
                val_obs = valor_lhs_dict.get(peor_mes, 0.0)
                val_esp = valor_rhs_dict.get(peor_mes, 0.0)

            return ValidationResult(
                validation_id=rule.id, nombre=rule.nombre, descripcion=rule.descripcion,
                severidad=Severidad(rule.severidad), aprobado=aprobado,
                lineas_afectadas=lineas_involucradas, valor_observado=val_obs, valor_esperado=val_esp,
                tolerancia=tol_abs, diferencia=max_diferencia,
                explicacion_financiera=explicacion, detalle_por_mes=diferencias
            )
        else:
            # Lógica TOTAL
            valor_lhs, valor_rhs, lineas_involucradas = self._resolver_expresion_dsl(
                expresion, snapshot, participacion
            )
            diferencia = abs(valor_lhs - valor_rhs)
            referencia = max(abs(valor_lhs), abs(valor_rhs), 1.0)
            tol_efectiva = max(tol_abs, referencia * tol_rel)
            
            aprobado = True
            if "==" in expresion: aprobado = diferencia <= tol_efectiva
            elif "<=" in expresion: aprobado = valor_lhs <= (valor_rhs + tol_efectiva)
            elif ">=" in expresion: aprobado = valor_lhs >= (valor_rhs - tol_efectiva)
            elif "<" in expresion: aprobado = valor_lhs < valor_rhs
            elif ">" in expresion: aprobado = valor_lhs > valor_rhs

            nombres_lineas = self._obtener_nombres_lineas_str(lineas_involucradas, snapshot, participacion)

            if aprobado:
                explicacion = (
                    f"✓ La regla sobre totales se cumple: '{expresion}'.\\n"
                    f"Líneas evaluadas explícitamente: {nombres_lineas}"
                )
            else:
                explicacion = (
                    f"⚠ La condición matemática total '{expresion}' NO cuadra.\\n"
                    f"Líneas involucradas que generaron este descuadre: {nombres_lineas}.\\n"
                    f"Valor calculado (izq): {valor_lhs:,.2f} | Valor esperado (der): {valor_rhs:,.2f} | "
                    f"Diferencia: {diferencia:,.2f}. Es fundamental verificar el acumulado de estos elementos."
                )

            return ValidationResult(
                validation_id=rule.id, nombre=rule.nombre, descripcion=rule.descripcion,
                severidad=Severidad(rule.severidad), aprobado=aprobado, lineas_afectadas=lineas_involucradas,
                valor_observado=valor_lhs, valor_esperado=valor_rhs, tolerancia=tol_efectiva,
                diferencia=diferencia, explicacion_financiera=explicacion,
            )

    def _obtener_nombres_lineas_str(self, indices: List[str], snapshot: CashFlowSnapshot, participacion: Participacion) -> str:
        nombres = []
        for idx in indices:
            linea = self._builder.get_linea_exacta(snapshot, idx, participacion)
            nombre = linea.nombre if linea else "INDICE SIN NOMBRE O NO EXISTE"
            nombres.append(f"[{idx} {nombre}]")
        return ", ".join(nombres) if nombres else "Ninguna línea explícita detectada"

    def _resolver_expresion_dsl(self, expresion: str, snapshot: CashFlowSnapshot, participacion: Participacion):
        lineas_involucradas = []
        comparadores = ["==", ">=", "<=", ">", "<"]
        sep = None
        for c in comparadores:
            if c in expresion:
                sep = c
                break
        
        if sep is None: raise ValueError(f"Sin operador en '{expresion}'")
        
        lhs_str, rhs_str = expresion.split(sep, 1)

        def resolver_lado(expr_str: str) -> float:
            expr = expr_str.strip()
            
            abs_match = re.match(r"^ABS\((.+)\)$", expr)
            if abs_match: return abs(resolver_lado(abs_match.group(1)))
            
            sum_match = re.match(r"^SUM\((.+)\)$", expr)
            if sum_match:
                prefijo = sum_match.group(1)
                lineas = self._builder.get_lineas_por_prefijo(snapshot, prefijo, participacion)
                lineas_involucradas.extend(l.indice for l in lineas)
                return sum(l.total_periodo for l in lineas)

            # Porcentajes tipo LINE(1.3)*0.04
            mult_match = re.match(r"^LINE\((.+)\)\s*\*\s*([0-9.]+|%.+)$", expr)
            if mult_match:
                idx = mult_match.group(1)
                pct_str = mult_match.group(2)
                pct = float(pct_str.replace('%','')) / 100.0 if '%' in pct_str else float(pct_str)
                linea = self._builder.get_linea_exacta(snapshot, idx, participacion)
                if linea:
                    lineas_involucradas.append(idx)
                    return linea.total_periodo * pct
                return 0.0

            line_match = re.match(r"^LINE\((.+)\)$", expr)
            if line_match:
                indice = line_match.group(1)
                linea = self._builder.get_linea_exacta(snapshot, indice, participacion)
                if linea:
                    lineas_involucradas.append(indice)
                    return linea.total_periodo
                return 0.0

            try: return float(expr)
            except ValueError: pass

            tokens = re.split(r"(\s*[+\-]\s*)", expr)
            result = None
            operator = "+"
            for token in tokens:
                token = token.strip()
                if token in ("+", "-"):
                    operator = token
                    continue
                if not token: continue
                val = resolver_lado(token)
                if result is None: result = val
                elif operator == "+": result += val
                else: result -= val
            return result or 0.0

        return resolver_lado(lhs_str), resolver_lado(rhs_str), list(set(lineas_involucradas))

    def _resolver_expresion_dsl_mensual(self, expresion: str, snapshot: CashFlowSnapshot, participacion: Participacion):
        lineas_involucradas = []
        comparadores = ["==", ">=", "<=", ">", "<"]
        sep = None
        for c in comparadores:
            if c in expresion:
                sep = c
                break
        
        if sep is None: raise ValueError(f"Sin operador en '{expresion}'")
        
        lhs_str, rhs_str = expresion.split(sep, 1)
        fechas = snapshot.fechas_flujo

        def resolver_lado(expr_str: str) -> Dict[str, float]:
            expr = expr_str.strip()
            
            abs_match = re.match(r"^ABS\((.+)\)$", expr)
            if abs_match:
                vals = resolver_lado(abs_match.group(1))
                return {f: abs(v) for f, v in vals.items()}
                
            mult_match = re.match(r"^LINE\((.+)\)\s*\*\s*([0-9.]+|%.+)$", expr)
            if mult_match:
                idx = mult_match.group(1)
                pct_str = mult_match.group(2)
                pct = float(pct_str.replace('%','')) / 100.0 if '%' in pct_str else float(pct_str)
                linea = self._builder.get_linea_exacta(snapshot, idx, participacion)
                if linea:
                    lineas_involucradas.append(idx)
                    return {f: v * pct for f, v in linea.valores.items()}
                return {f: 0.0 for f in fechas}

            line_match = re.match(r"^LINE\((.+)\)$", expr)
            if line_match:
                indice = line_match.group(1)
                linea = self._builder.get_linea_exacta(snapshot, indice, participacion)
                if linea:
                    lineas_involucradas.append(indice)
                    return linea.valores.copy()
                return {f: 0.0 for f in fechas}

            try: 
                val = float(expr)
                return {f: val for f in fechas}
            except ValueError: pass

            tokens = re.split(r"(\s*[+\-]\s*)", expr)
            result_dict = None
            operator = "+"
            for token in tokens:
                token = token.strip()
                if token in ("+", "-"):
                    operator = token
                    continue
                if not token: continue
                val_dict = resolver_lado(token)
                
                if result_dict is None:
                    result_dict = val_dict.copy()
                else:
                    for f in fechas:
                        if operator == "+": result_dict[f] += val_dict.get(f, 0.0)
                        else: result_dict[f] -= val_dict.get(f, 0.0)
            return result_dict or {f: 0.0 for f in fechas}

        return resolver_lado(lhs_str), resolver_lado(rhs_str), list(set(lineas_involucradas))

    # ──────────────────────────────────────────
    # HANDLER: ESTRUCTURAL
    # Suma de hijos == valor del padre
    # ──────────────────────────────────────────

    def _eval_estructural(
        self, rule: ValidationRule, snapshot: CashFlowSnapshot
    ) -> ValidationResult:
        cfg = rule.config
        indice_padre = cfg["indice_padre"]
        prefijo_hijos = cfg["prefijo_hijos"]
        part_str = cfg.get("participacion", "total")
        tolerancia = float(cfg.get("tolerancia_absoluta", 1.0))

        try:
            participacion = Participacion(part_str)
        except ValueError:
            participacion = Participacion.TOTAL

        padre = self._builder.get_linea_exacta(snapshot, indice_padre, participacion)
        hijos = [
            l for l in self._builder.get_lineas_por_prefijo(snapshot, prefijo_hijos, participacion)
            if l.indice != indice_padre and _es_hijo_directo(l.indice, indice_padre)
        ]

        if not padre:
            return ValidationResult(
                validation_id=rule.id,
                nombre=rule.nombre,
                descripcion=rule.descripcion,
                severidad=Severidad.INFORMATIVO,
                aprobado=True,
                lineas_afectadas=[],
                explicacion_financiera=(
                    f"La línea padre '{indice_padre}' no existe en este snapshot. "
                    f"La validación estructural no aplica."
                ),
            )

        suma_hijos = sum(h.total_periodo for h in hijos)
        diferencia = abs(padre.total_periodo - suma_hijos)
        aprobado = diferencia <= tolerancia

        indices = [indice_padre] + [h.indice for h in hijos]

        if aprobado:
            explicacion = (
                f"✓ La línea '{indice_padre}' ({padre.nombre}) cuadra con la suma "
                f"de sus {len(hijos)} líneas hijas. "
                f"Total padre: {padre.total_periodo:,.2f} | "
                f"Suma hijas: {suma_hijos:,.2f}."
            )
        else:
            explicacion = (
                f"⚠ La línea '{indice_padre}' ({padre.nombre}) NO cuadra con la suma "
                f"de sus líneas hijas. "
                f"Valor del padre: {padre.total_periodo:,.2f} | "
                f"Suma de hijos: {suma_hijos:,.2f} | "
                f"Diferencia: {diferencia:,.2f}. "
                f"Esto indica que el subtotal está mal calculado en el modelo de origen, "
                f"o que alguna línea hija está siendo excluida o duplicada."
            )

        return ValidationResult(
            validation_id=rule.id,
            nombre=rule.nombre,
            descripcion=rule.descripcion,
            severidad=Severidad(rule.severidad),
            aprobado=aprobado,
            lineas_afectadas=indices,
            valor_observado=suma_hijos,
            valor_esperado=padre.total_periodo,
            tolerancia=tolerancia,
            diferencia=diferencia,
            explicacion_financiera=explicacion,
        )

    # ──────────────────────────────────────────
    # HANDLER: COHERENCIA ECONÓMICA
    # ──────────────────────────────────────────

    def _eval_coherencia_economica(
        self, rule: ValidationRule, snapshot: CashFlowSnapshot
    ) -> ValidationResult:
        cfg = rule.config
        condicion = cfg.get("condicion", "")
        part_str = cfg.get("participacion", "total")

        try:
            participacion = Participacion(part_str)
        except ValueError:
            participacion = Participacion.TOTAL

        # Caso 1: precio_por_m2 > 0
        if "precio_por_m2" in condicion:
            indice_ing = cfg.get("indice_ingresos", "1.")
            indice_m2  = cfg.get("indice_ventas_m2", "18.")

            lineas_ing = self._builder.get_lineas_por_prefijo(snapshot, indice_ing, participacion)
            lineas_m2  = self._builder.get_lineas_por_prefijo(snapshot, indice_m2, participacion)

            total_ing = sum(l.total_periodo for l in lineas_ing)
            total_m2  = sum(l.total_periodo for l in lineas_m2)
            precio_m2 = total_ing / total_m2 if total_m2 != 0 else 0.0

            aprobado = precio_m2 > 0
            indices  = [l.indice for l in lineas_ing + lineas_m2]

            if aprobado:
                explicacion = (
                    f"✓ El precio implícito por m² es positivo: {precio_m2:,.0f}. "
                    f"Ingresos totales: {total_ing:,.0f} | M² totales: {total_m2:,.0f}."
                )
            else:
                explicacion = (
                    f"⚠ El precio implícito por m² es {precio_m2:,.0f}, lo cual es inválido. "
                    f"Ingresos totales: {total_ing:,.0f} | M² totales: {total_m2:,.0f}. "
                    f"Un precio nulo o negativo sugiere errores de signo en los ingresos "
                    f"o ausencia de datos de ventas en m²."
                )

            return ValidationResult(
                validation_id=rule.id, nombre=rule.nombre, descripcion=rule.descripcion,
                severidad=Severidad(rule.severidad), aprobado=aprobado,
                lineas_afectadas=indices, valor_observado=precio_m2,
                explicacion_financiera=explicacion,
            )

        # Caso 2: total_ventas >= total_escrituraciones
        elif "total_ventas >= total_escrituraciones" in condicion:
            ind_ven  = cfg.get("indice_ventas_unidades", "17.")
            ind_escr = cfg.get("indice_escrituraciones", "19.")

            lin_ven  = self._builder.get_lineas_por_prefijo(snapshot, ind_ven, participacion)
            lin_escr = self._builder.get_lineas_por_prefijo(snapshot, ind_escr, participacion)

            total_ven  = sum(l.total_periodo for l in lin_ven)
            total_escr = sum(l.total_periodo for l in lin_escr)
            aprobado   = total_ven >= total_escr

            if aprobado:
                explicacion = (
                    f"✓ Ventas ({total_ven:,.0f} uds) ≥ Escrituraciones ({total_escr:,.0f} uds). "
                    f"La lógica de comercialización es coherente."
                )
            else:
                brecha = total_escr - total_ven
                explicacion = (
                    f"⚠ Se escrituran más unidades ({total_escr:,.0f}) de las vendidas "
                    f"({total_ven:,.0f}). Brecha: {brecha:,.0f} unidades. "
                    f"Esto es financieramente imposible y sugiere un error de captura "
                    f"o un desajuste entre las líneas de ventas y escrituraciones en el modelo."
                )

            return ValidationResult(
                validation_id=rule.id, nombre=rule.nombre, descripcion=rule.descripcion,
                severidad=Severidad(rule.severidad), aprobado=aprobado,
                lineas_afectadas=[l.indice for l in lin_ven + lin_escr],
                valor_observado=total_ven, valor_esperado=total_escr,
                diferencia=total_ven - total_escr,
                explicacion_financiera=explicacion,
            )

        # Caso 3: ingresos_sin_escrituracion == 0
        elif "ingresos_sin_escrituracion" in condicion:
            ind_ing  = cfg.get("indice_ingresos", "1.")
            ind_escr = cfg.get("indice_escrituraciones", "19.")

            sum_ing  = self._builder.sum_prefijo_por_mes(snapshot, ind_ing, participacion)
            sum_escr = self._builder.sum_prefijo_por_mes(snapshot, ind_escr, participacion)

            meses_problema = [
                f for f in snapshot.fechas_flujo
                if sum_ing.get(f, 0) > 0 and sum_escr.get(f, 0) == 0
            ]
            aprobado = len(meses_problema) == 0

            if aprobado:
                explicacion = (
                    f"✓ No se detectaron meses con ingresos sin escrituraciones correspondientes. "
                    f"El reconocimiento de ingresos es temporalmente coherente."
                )
            else:
                explicacion = (
                    f"ℹ Se detectaron {len(meses_problema)} mes(es) con ingresos "
                    f"pero sin escrituraciones en el mismo período. "
                    f"Meses: {', '.join(meses_problema[:5])}{'...' if len(meses_problema) > 5 else ''}. "
                    f"Esto puede indicar un diferimiento en el reconocimiento de ingresos "
                    f"o simplemente que los ingresos son preventa. Revise el timing del modelo."
                )

            return ValidationResult(
                validation_id=rule.id, nombre=rule.nombre, descripcion=rule.descripcion,
                severidad=Severidad(rule.severidad), aprobado=aprobado,
                lineas_afectadas=[ind_ing, ind_escr],
                explicacion_financiera=explicacion,
                detalle_por_mes={m: sum_ing.get(m, 0) for m in meses_problema},
            )

        # Condición no reconocida
        return ValidationResult(
            validation_id=rule.id, nombre=rule.nombre, descripcion=rule.descripcion,
            severidad=Severidad.INFORMATIVO, aprobado=True, lineas_afectadas=[],
            explicacion_financiera=f"Condición de coherencia económica no reconocida: '{condicion}'.",
        )


# ─────────────────────────────────────────────
# UTILIDADES INTERNAS
# ─────────────────────────────────────────────

def _es_hijo_directo(indice_hijo: str, indice_padre: str) -> bool:
    """
    True si indice_hijo es hijo DIRECTO de indice_padre.
    "1.1" es hijo directo de "1" → True
    "1.1.1" NO es hijo directo de "1" → False
    """
    padre_partes = indice_padre.split(".")
    hijo_partes  = indice_hijo.split(".")
    return (
        len(hijo_partes) == len(padre_partes) + 1 and
        hijo_partes[:len(padre_partes)] == padre_partes
    )
