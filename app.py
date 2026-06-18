import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional
import sys
import plotly.graph_objects as go

# ─── Asegurar que el backend sea importable ───
sys.path.append(str(Path(__file__).parent))

from backend.parser_excel_v2 import parse_base_excel
from backend.table_builder import TableBuilder
from backend.validation_engine import ValidationEngine
from backend.report_generator import enriquecer_reporte
from backend.models import Participacion
from backend.folder_loader import load_database_from_folder, parse_fecha_label, list_database_files

# ─── Ruta por defecto a la carpeta con la BASE de datos ───
DEFAULT_DB_FOLDER = Path(
    r"C:\Users\erozo\OneDrive - IC CONSTRUCTORA SAS\AA ESTRUCTURACION - ESTR - PROYECTOS\05. Consolidadores\3. DATABASE"
)

# ─────────────────────────────────────────────
# CONFIGURACIÓN DE LA PÁGINA
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="Estate Auditor | IC Constructora",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Estilos corporativos ─────────────────────
st.markdown("""
<style>
  [data-testid="stSidebar"] { background-color: #f9f5f5; }
  [data-testid="stSidebar"] h1 { color: #681E1E !important; }
  .block-container { padding-top: 1.5rem; }
  .kpi-box {
      background: white;
      border-radius: 10px;
      padding: 1.2rem 1.5rem;
      box-shadow: 0 2px 8px rgba(104,30,30,0.08);
      border-left: 4px solid #681E1E;
      margin-bottom: 1rem;
  }
  .kpi-label { font-size: 0.78rem; color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
  .kpi-value { font-size: 1.8rem; font-weight: 700; color: #681E1E; margin: 0; }
  .kpi-sub   { font-size: 0.85rem; color: #555; }
  .status-ok       { color: #10b981; font-weight: 700; }
  .status-warning  { color: #f59e0b; font-weight: 700; }
  .status-critical { color: #ef4444; font-weight: 700; }
  .metric-card {
      background-color: white;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 20px;
      text-align: center;
  }
  .metric-value { font-size: 2.2rem; font-weight: 700; }
  .metric-label { font-size: 0.875rem; color: #888; text-transform: uppercase; font-weight: 600; letter-spacing: 0.05em; }

  /* ── Tabla P&G estilo IC ── */
  /* overflow visible para que el popover (mini-gráfico) no quede recortado.
     Si la tabla se vuelve demasiado ancha, el viewport del navegador hace scroll. */
  .pyg-wrapper { overflow: visible; margin: 0.5rem 0 1rem; }
  .pyg-table {
      width: 100%;
      border-collapse: collapse;
      font-family: Inter, sans-serif;
      font-size: 1.235rem;
      color: #222;
  }
  .pyg-table th, .pyg-table td {
      padding: 8px 12px;
      border: 1px solid #d6d6d6;
      white-space: nowrap;
  }
  .pyg-table thead th {
      background-color: #681E1E;
      color: #FFFFFF;
      font-weight: 700;
      text-align: right;
      border-color: #4a1414;
      border-bottom: 2px solid #4a1414;
  }
  .pyg-table thead th.pyg-label-col { text-align: left; }
  .pyg-table td.pyg-label { text-align: right; font-weight: 500; }
  .pyg-table td.pyg-num   { text-align: right; font-variant-numeric: tabular-nums; }
  .pyg-table td.pyg-consolidado { background-color: #ececec; font-weight: 700; }
  .pyg-table tr.pyg-header td { font-weight: 700; }
  .pyg-table tr.pyg-subtotal td { font-weight: 700; border-top: 1px solid #b0b0b0; }
  .pyg-table tr.pyg-result td   { font-weight: 700; }
  .pyg-table tr.pyg-italic td   { font-style: italic; }
  .pyg-table tr.pyg-subitem td  { color: #9a9a9a; font-style: italic; padding-left: 24px; }
  .pyg-table tr.pyg-subitem td.pyg-label { padding-right: 12px; }
  .pyg-table tr.pyg-negative td.pyg-num { color: #c0392b; }
  .pyg-table tr.pyg-negative td.pyg-label { color: #c0392b; }

  /* Variante compacta: cuando hay pocas columnas, la tabla no ocupa todo el ancho */
  .pyg-table.pyg-table-compact { width: auto; min-width: 480px; }
  .pyg-table.pyg-table-compact th,
  .pyg-table.pyg-table-compact td { min-width: 140px; }
  .pyg-table.pyg-table-compact th.pyg-label-col,
  .pyg-table.pyg-table-compact td.pyg-label { min-width: 240px; max-width: 340px; }

  /* Barra de avance detrás del valor — modo "Mostrar avance" activo */
  .pyg-table td.pyg-num.has-progress { position: relative; cursor: help; }
  .pyg-table td.pyg-num.has-progress .pyg-bar {
      position: absolute;
      top: 5px;
      bottom: 5px;
      left: 5px;
      background: linear-gradient(90deg,
        rgba(46, 125, 82, 0.14),
        rgba(46, 125, 82, 0.30));
      border-right: 2px solid rgba(46, 125, 82, 0.55);
      border-radius: 2px;
      z-index: 0;
      pointer-events: none;
      transition: width 200ms ease;
  }
  .pyg-table td.pyg-num.has-progress .pyg-bar-val {
      position: relative;
      z-index: 1;
  }
  /* En filas consolidado (fondo gris) usar un verde un poco más opaco */
  .pyg-table td.pyg-num.pyg-consolidado.has-progress .pyg-bar {
      background: linear-gradient(90deg,
        rgba(46, 125, 82, 0.20),
        rgba(46, 125, 82, 0.40));
  }

  /* ── Popover con mini-gráfico (hover) ── */
  .pyg-table td.pyg-num.has-popover { position: relative; cursor: help; }
  .pyg-table td.pyg-num.has-popover .pyg-popover {
      display: none;
      position: absolute;
      /* Vertical: por defecto ABAJO de la celda (no se corta arriba) */
      top: calc(100% + 6px);
      /* Horizontal: por defecto se abre hacia la DERECHA (hay espacio libre
         a la derecha de la tabla). La última columna se invierte abajo. */
      left: 0;
      right: auto;
      z-index: 1000;
      width: 850px;
      padding: 25px 30px;
      background: #ffffff;
      border: 1px solid #d0d0d0;
      border-radius: 14px;
      box-shadow: 0 14px 40px rgba(0,0,0,0.22);
      text-align: left;
      font-weight: 400;
      font-style: normal;
      color: #222;
      pointer-events: none;
  }
  /* Última columna numérica: abrir hacia la IZQUIERDA para no salirse por
     el borde derecho de la pantalla. */
  .pyg-table td.pyg-num.has-popover:last-child .pyg-popover {
      left: auto;
      right: 0;
  }
  /* Para las últimas 5 filas: invertimos y mostramos ARRIBA
     (porque ya hay poco espacio debajo de la tabla) */
  .pyg-table tbody tr:nth-last-of-type(-n+5) td.pyg-num.has-popover .pyg-popover {
      top: auto;
      bottom: calc(100% + 6px);
  }
  .pyg-table td.pyg-num.has-popover:hover .pyg-popover {
      display: block;
  }
  .pyg-popover .pop-title {
      font-weight: 700;
      font-size: 30px;
      color: #681E1E;
      margin-bottom: 10px;
      border-bottom: 1px solid #eee;
      padding-bottom: 10px;
  }
  .pyg-popover .pop-foot {
      font-size: 27px;
      color: #333;
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px solid #eee;
  }
  .pyg-popover .pop-foot b { color: #1A7A42; }
  .pyg-popover .pop-legend {
      font-size: 25px;
      color: #888;
      margin-top: 5px;
  }
  .pyg-popover .pop-legend .leg-bar  { color: #681E1E; }
  .pyg-popover .pop-legend .leg-line { color: #1F6F40; }

  /* KPIs al lado de la tabla compacta: grilla de 2 columnas para
     aprovechar el alto y no extenderse muy por debajo de la tabla. */
  .pyg-kpi-stack {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 0.6rem;
      align-content: start;
  }
  .pyg-kpi-stack .kpi-box { margin: 0; }

  /* Grid de KPIs cuando van debajo de la tabla (muchas columnas) */
  .pyg-kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 0.8rem;
      margin-top: 1rem;
  }
  .pyg-kpi-grid .kpi-box { margin: 0; }

  /* ─────────────────────────────────────────── */
  /* ── Módulo "Flujo Proyecto (Control)"      ── */
  /* ─────────────────────────────────────────── */
  .fcp-hero {
      background: linear-gradient(135deg, #681E1E 0%, #4a1414 100%);
      color: white;
      padding: 1.8rem 2rem;
      border-radius: 14px;
      margin-bottom: 1.5rem;
      box-shadow: 0 4px 18px rgba(104,30,30,0.25);
  }
  .fcp-hero h1 { color: white; margin: 0 0 0.5rem 0; font-size: 1.9rem; font-weight: 700; }
  .fcp-hero p  { color: #f8d7c4; margin: 0; font-size: 0.95rem; line-height: 1.5; }

  .fcp-ctrlbar {
      background: #fff;
      border: 1px solid #e0d4d4;
      border-radius: 12px;
      padding: 1rem 1.25rem;
      margin-bottom: 1.2rem;
      box-shadow: 0 1px 5px rgba(0,0,0,0.04);
  }

  .fcp-kpi-strip {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 1rem;
      margin: 1rem 0 1.5rem 0;
  }
  .fcp-kpi {
      background: white;
      border-radius: 12px;
      padding: 1.1rem 1.3rem;
      box-shadow: 0 2px 10px rgba(0,0,0,0.06);
      border-left: 5px solid #681E1E;
  }
  .fcp-kpi.fcp-kpi-ok      { border-left-color: #10b981; }
  .fcp-kpi.fcp-kpi-warn    { border-left-color: #f59e0b; }
  .fcp-kpi.fcp-kpi-crit    { border-left-color: #ef4444; }
  .fcp-kpi-lbl  { font-size: 0.72rem; color: #888; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; }
  .fcp-kpi-val  { font-size: 1.7rem; font-weight: 700; color: #681E1E; margin: 0.2rem 0 0.05rem 0; line-height: 1.1; }
  .fcp-kpi-sub  { font-size: 0.78rem; color: #666; }

  .fcp-wrapper { overflow-x: auto; border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
  .fcp-table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      font-family: Inter, sans-serif;
      font-size: 0.92rem;
      color: #222;
      background: white;
  }
  .fcp-table th, .fcp-table td {
      padding: 7px 10px;
      border-bottom: 1px solid #ecdfdf;
      white-space: nowrap;
  }
  .fcp-table thead tr.fcp-head-l1 th {
      background: #681E1E;
      color: white;
      font-weight: 700;
      text-align: center;
      border-bottom: 1px solid #4a1414;
      font-size: 0.86rem;
      letter-spacing: 0.03em;
      text-transform: uppercase;
  }
  .fcp-table thead tr.fcp-head-l2 th {
      background: #f5e8e8;
      color: #681E1E;
      font-weight: 700;
      text-align: center;
      font-size: 0.78rem;
      border-bottom: 2px solid #b78a8a;
      text-transform: uppercase;
      letter-spacing: 0.04em;
  }
  .fcp-table thead th.fcp-th-rubro { text-align: left; padding-left: 18px; width: 28%; }
  .fcp-table thead th.fcp-th-uso   { color: #fde4e4 !important; }
  .fcp-table thead tr.fcp-head-l2 th.fcp-th-uso    { color: #c0392b; background: #fde7e7; }
  .fcp-table thead tr.fcp-head-l2 th.fcp-th-fuente { color: #1e7a4d; background: #e1f4ea; }

  .fcp-table td.fcp-rubro { text-align: left; font-weight: 500; padding-left: 18px; }
  .fcp-table td.fcp-num   { text-align: right; font-variant-numeric: tabular-nums; }
  .fcp-table td.fcp-uso    { color: #c0392b; }
  .fcp-table td.fcp-fuente { color: #1e7a4d; }
  .fcp-table td.fcp-empty  { color: #d8d8d8; }

  .fcp-table tr.fcp-group td {
      background: linear-gradient(90deg, #f8eded 0%, #faf3f3 100%);
      border-top: 2px solid #b78a8a;
      font-weight: 700;
      color: #681E1E;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      font-size: 0.82rem;
      padding-top: 10px;
      padding-bottom: 10px;
  }
  .fcp-table tr.fcp-subtotal td {
      background: #fbf6f6;
      font-weight: 700;
      border-top: 1px solid #d8c4c4;
  }
  .fcp-table tr.fcp-grand-total td {
      background: #ecdfdf;
      font-weight: 700;
      color: #681E1E;
      border-top: 2px solid #681E1E;
      border-bottom: 2px solid #681E1E;
      font-size: 0.96rem;
  }
  .fcp-table tr.fcp-info td {
      color: #888;
      font-style: italic;
      background: #fafafa;
  }
  .fcp-table tr.fcp-caja td {
      background: #fff7e6;
      color: #874d0c;
      font-weight: 700;
      font-size: 1rem;
      border-top: 3px double #d4a45a;
  }
  .fcp-table tr.fcp-check-ok td  { background: #e6f8ee; color: #1b6e3f; font-weight: 700; }
  .fcp-table tr.fcp-check-bad td { background: #fde6e6; color: #b03030; font-weight: 700; }
  .fcp-table tr.fcp-item:hover td { background-color: #fdf8f8; }
  .fcp-table tr.fcp-subitem td {
      color: #888;
      font-size: 0.85rem;
      padding-left: 38px !important;
  }
  .fcp-divider-col { border-left: 2px solid #b78a8a !important; }

  /* Divisores oscuros entre tramos (cada par U/F) */
  .fcp-table td.fcp-tramo-end, .fcp-table th.fcp-tramo-end {
      border-right: 3px solid #681E1E !important;
  }
  .fcp-table td.fcp-uf-sep, .fcp-table th.fcp-uf-sep {
      border-right: 1px dashed #b78a8a !important;
  }

  /* ── Top nav (cuando se oculta el sidebar) ── */
  .fcp-topnav-wrapper {
      background: linear-gradient(90deg, #4a1414 0%, #681E1E 100%);
      padding: 0.6rem 1rem;
      margin: -1.5rem -1rem 1rem -1rem;
      border-radius: 0 0 14px 14px;
      box-shadow: 0 4px 14px rgba(0,0,0,0.18);
  }
  .fcp-topnav-title {
      color: #f8d7c4; font-weight: 700; font-size: 0.78rem;
      text-transform: uppercase; letter-spacing: 0.08em;
      padding-left: 0.4rem;
  }

  /* ─────────────────────────────────────────── */
  /* ── NUEVO SISTEMA · CSS GRID UNIFICADO    ── */
  /* ─────────────────────────────────────────── */

  /* Header de 2 filas en grid (RUBRO ocupa rowspan=2) */
  .fcp-header-grid {
      display: grid;
      grid-template-columns: 28% 9% 9% 9% 9% 9% 9% 9% 9%;
      grid-template-rows: auto auto;
      width: 100%;
      font-family: Inter, sans-serif;
      box-shadow: 0 2px 6px rgba(0,0,0,0.18);
  }
  .fcp-hcell {
      box-sizing: border-box;
      padding: 8px 6px;
      font-size: 0.78rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #681E1E;
      color: white;
      border-right: 1px solid rgba(255,255,255,0.12);
      text-align: center;
  }
  .fcp-hcell.fcp-h-rubro {
      background: #4a1414;
      justify-content: flex-start;
      padding-left: 14px;
      text-align: left;
  }
  .fcp-hcell.fcp-h-sub {
      background: #f5e8e8;
      color: #681E1E;
      padding: 5px;
      font-size: 0.72rem;
      letter-spacing: 0.04em;
      border-bottom: 2px solid #b78a8a;
  }
  .fcp-hcell.fcp-h-sub.fcp-h-uso    { color: #c0392b; background: #fde7e7; }
  .fcp-hcell.fcp-h-sub.fcp-h-fuente { color: #1e7a4d; background: #e1f4ea; }
  .fcp-hcell.fcp-tramo-end { border-right: 3px solid #f5e8e8; }

  /* Fila base en grid: alineada con el header */
  .fcp-grid-row {
      display: grid;
      grid-template-columns: 28% 9% 9% 9% 9% 9% 9% 9% 9%;
      width: 100%;
      box-sizing: border-box;
      font-family: Inter, sans-serif;
      font-size: 0.87rem;
      background: white;
      border-bottom: 1px solid #f0e6e6;
  }
  .fcp-gcell {
      box-sizing: border-box;
      padding: 7px 10px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      display: flex;
      align-items: center;
  }
  .fcp-gcell.fcp-rubro {
      justify-content: flex-start;
      text-align: left;
  }
  .fcp-gcell.fcp-num {
      justify-content: flex-end;
      text-align: right;
      font-variant-numeric: tabular-nums;
  }
  .fcp-gcell.fcp-uso    { color: #c0392b; border-right: 1px dashed #b78a8a; }
  .fcp-gcell.fcp-fuente { color: #1e7a4d; }
  .fcp-gcell.fcp-fuente.fcp-tramo-end { border-right: 3px solid #681E1E; }
  .fcp-gcell.fcp-empty  { color: #d8d8d8; }

  /* Variantes de fila */
  .fcp-grid-row.fcp-row-item:hover { background: #fdf8f8; }
  .fcp-grid-row.fcp-row-subtotal {
      background: #fbf6f6;
      font-weight: 700;
      border-top: 1px solid #d8c4c4;
  }
  .fcp-grid-row.fcp-row-subtotal .fcp-gcell { font-weight: 700; }
  .fcp-grid-row.fcp-row-grand-total {
      background: #ecdfdf;
      font-weight: 700;
      color: #681E1E;
      border-top: 2px solid #681E1E;
      border-bottom: 2px solid #681E1E;
  }
  .fcp-grid-row.fcp-row-grand-total .fcp-gcell { color: #681E1E; font-weight: 700; }
  .fcp-grid-row.fcp-row-subitem .fcp-gcell.fcp-rubro {
      padding-left: 36px;
      color: #777;
      font-style: italic;
      font-size: 0.82rem;
  }
  .fcp-grid-row.fcp-row-info {
      background: #fafafa;
  }
  .fcp-grid-row.fcp-row-info .fcp-gcell { color: #888; font-style: italic; }

  /* Pie: CAJA / CHECK F&U */
  .fcp-grid-row.fcp-row-caja {
      background: #fff7e6;
      color: #874d0c;
      font-weight: 700;
      font-size: 0.95rem;
      border-top: 3px double #d4a45a;
      margin-top: 2px;
  }
  .fcp-grid-row.fcp-row-caja .fcp-gcell { color: #874d0c; font-weight: 700; }
  .fcp-grid-row.fcp-row-check-ok  { background: #e6f8ee; }
  .fcp-grid-row.fcp-row-check-bad { background: #fde6e6; }
  .fcp-grid-row.fcp-row-check-ok  .fcp-gcell { color: #1b6e3f; font-weight: 700; }
  .fcp-grid-row.fcp-row-check-bad .fcp-gcell { color: #b03030; font-weight: 700; }

  /* ── Details / Summary (clave del colapsable) ── */
  /* La SUMMARY es la fila .0 (subtotal) — siempre visible.
     El contenido interno son los sub-ítems — visible solo cuando [open]. */
  details.fcp-group-d {
      margin: 0;
      border-top: 2px solid #b78a8a;
      background: white;
  }
  details.fcp-group-d > summary {
      list-style: none;
      cursor: pointer;
      user-select: none;
      outline: none;
      display: block;
  }
  details.fcp-group-d > summary::-webkit-details-marker { display: none; }

  /* El caret indica si está abierto o cerrado */
  .fcp-caret {
      display: inline-block;
      width: 14px;
      text-align: center;
      color: #681E1E;
      font-size: 0.72rem;
      margin-right: 6px;
      flex-shrink: 0;
  }
  details.fcp-group-d > summary .fcp-caret::before { content: "▶"; }
  details.fcp-group-d[open] > summary .fcp-caret::before { content: "▼"; }

  /* Grupos sin colapso (totales operativos / fondeo) — solo fila standalone */
  .fcp-standalone-group { border-top: 2px solid #b78a8a; }

  /* Botones de acción global "Expandir/Colapsar todos" */
  .fcp-btn-row { margin: 0.4rem 0 0.4rem 0; }

  /* Header sticky para que se vea siempre */
  .fcp-sticky-header {
      position: sticky;
      top: 0;
      z-index: 5;
      background: #681E1E;
      color: white;
      box-shadow: 0 2px 6px rgba(0,0,0,0.15);
  }

  /* ── Panel de alertas (LEFT) ── */
  .fcp-alert {
      background: white;
      border-radius: 10px;
      padding: 0.7rem 0.9rem;
      margin-bottom: 0.6rem;
      border-left: 4px solid #ccc;
      font-size: 0.83rem;
      box-shadow: 0 1px 4px rgba(0,0,0,0.05);
  }
  .fcp-alert.alert-ok    { border-left-color: #10b981; background: #f0fdf4; }
  .fcp-alert.alert-warn  { border-left-color: #f59e0b; background: #fffbeb; }
  .fcp-alert.alert-crit  { border-left-color: #ef4444; background: #fef2f2; }
  .fcp-alert .alert-title { font-weight: 700; margin-bottom: 0.2rem; }
  .fcp-alert .alert-value { font-size: 1.05rem; font-weight: 700; color: #333; }
  .fcp-alert .alert-meta  { font-size: 0.74rem; color: #666; margin-top: 0.15rem; }

  /* Compactar KPIs en columna izquierda */
  .fcp-left-kpi {
      background: white;
      border-radius: 10px;
      padding: 0.7rem 0.9rem;
      margin-bottom: 0.55rem;
      border-left: 5px solid #681E1E;
      box-shadow: 0 1px 5px rgba(0,0,0,0.06);
  }
  .fcp-left-kpi.kpi-ok   { border-left-color: #10b981; }
  .fcp-left-kpi.kpi-warn { border-left-color: #f59e0b; }
  .fcp-left-kpi.kpi-crit { border-left-color: #ef4444; }
  .fcp-left-kpi-lbl { font-size: 0.68rem; color: #888; font-weight: 700;
                       text-transform: uppercase; letter-spacing: 0.06em; }
  .fcp-left-kpi-val { font-size: 1.25rem; font-weight: 700; color: #681E1E; line-height: 1.15; margin-top: 0.15rem; }
  .fcp-left-kpi-sub { font-size: 0.72rem; color: #666; }

  /* Encabezado fijo arriba del centro (replicado en cada grupo via colgroup) */
  table.fcp-header-only {
      width: 100%;
      border-collapse: collapse;
      font-family: Inter, sans-serif;
      table-layout: fixed;
  }
  table.fcp-header-only thead tr.fcp-head-l1 th {
      background: #681E1E;
      color: white;
      font-weight: 700;
      text-align: center;
      padding: 8px 6px;
      font-size: 0.78rem;
      letter-spacing: 0.03em;
      text-transform: uppercase;
  }
  table.fcp-header-only thead tr.fcp-head-l2 th {
      background: #f5e8e8;
      color: #681E1E;
      font-weight: 700;
      text-align: center;
      padding: 5px;
      font-size: 0.72rem;
      border-bottom: 2px solid #b78a8a;
      text-transform: uppercase;
      letter-spacing: 0.04em;
  }
  table.fcp-header-only thead tr.fcp-head-l2 th.fcp-th-uso    { color: #c0392b; background: #fde7e7; }
  table.fcp-header-only thead tr.fcp-head-l2 th.fcp-th-fuente { color: #1e7a4d; background: #e1f4ea; }
  table.fcp-header-only thead th.fcp-th-rubro {
      text-align: left; padding-left: 14px; background: #4a1414;
  }
  table.fcp-header-only thead th.fcp-tramo-end { border-right: 3px solid #f5e8e8; }

  /* Filas de pie (Caja / CHECK) en la parte inferior del centro */
  .fcp-footer-table { width: 100%; border-collapse: collapse; font-family: Inter, sans-serif; table-layout: fixed; }
  .fcp-footer-table td { padding: 9px 10px; }
  .fcp-footer-table tr.fcp-caja td {
      background: #fff7e6;
      color: #874d0c;
      font-weight: 700;
      font-size: 0.95rem;
      border-top: 3px double #d4a45a;
  }
  .fcp-footer-table tr.fcp-check-ok td  { background: #e6f8ee; color: #1b6e3f; font-weight: 700; }
  .fcp-footer-table tr.fcp-check-bad td { background: #fde6e6; color: #b03030; font-weight: 700; }
  .fcp-footer-table td.fcp-num { text-align: right; font-variant-numeric: tabular-nums; }
  .fcp-footer-table td.fcp-rubro { text-align: left; padding-left: 14px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# INICIALIZACIÓN DE ESTADO Y MOTORES
# ─────────────────────────────────────────────

@st.cache_resource
def get_engines():
    rules_path = Path(__file__).parent / "backend" / "rules.json"
    engine = ValidationEngine(str(rules_path))
    builder = TableBuilder()
    return engine, builder

engine, builder = get_engines()

if "records" not in st.session_state:
    st.session_state.records = None
if "upload_response" not in st.session_state:
    st.session_state.upload_response = None
if "report" not in st.session_state:
    st.session_state.report = None

# ─────────────────────────────────────────────
# CACHÉ DE PARSEO Y PERSISTENCIA DE LA BASE
# ─────────────────────────────────────────────
# Fase 1.1 — Evita re-parsear un Excel idéntico (mismo contenido de bytes).
#            st.cache_data devuelve una copia, así que mutar `version` aguas
#            abajo no corrompe la caché.
# Fase 1.2 — Persiste la base parseada en disco para restaurarla tras recargar
#            la página o reabrir la app, sin volver a parsear los Excel.

@st.cache_data(show_spinner=False, max_entries=128)
def _parse_excel_cached(file_bytes: bytes):
    return parse_base_excel(file_bytes)

_CACHE_DIR = Path(__file__).parent / ".cache"
_BASE_CACHE_FILE = _CACHE_DIR / "last_base.pkl"

def _persist_base():
    """Guarda la base actual (records + response + meta) en disco."""
    import pickle
    try:
        _CACHE_DIR.mkdir(exist_ok=True)
        with open(_BASE_CACHE_FILE, "wb") as f:
            pickle.dump({
                "records": st.session_state.records,
                "upload_response": st.session_state.upload_response,
                "files_processed": st.session_state.get("files_processed", []),
                "saved_at": datetime.now(),
            }, f)
    except Exception:
        pass  # la persistencia es best-effort; nunca debe tumbar la app

def _restore_base():
    """Restaura la base desde disco. Devuelve la fecha de guardado o None."""
    import pickle
    try:
        with open(_BASE_CACHE_FILE, "rb") as f:
            data = pickle.load(f)
        st.session_state.records = data["records"]
        st.session_state.upload_response = data["upload_response"]
        st.session_state.files_processed = data.get("files_processed", [])
        st.session_state.auto_load_ok = True
        _nueva_firma_base()
        return data.get("saved_at")
    except Exception:
        return None

def _clear_base_cache():
    """Borra el archivo de base persistida."""
    try:
        if _BASE_CACHE_FILE.exists():
            _BASE_CACHE_FILE.unlink()
    except Exception:
        pass

# Fase 1.3 — Memoización de snapshots por sesión.
# `builder.build` hace un barrido O(n) de TODA la base y se invoca en bucles
# en cada rerun (cambiar un toggle reconstruía todo). Aquí se memoiza el
# resultado por (firma_base, proyecto, fecha, versión). Es seguro porque los
# snapshots se consumen en modo solo-lectura (get_linea_exacta / sum_prefijo).
# La caché se invalida sola: al cargar una base nueva se renueva `base_sig` y
# se vacía el memo.

def _nueva_firma_base():
    """Renueva la firma de la base cargada y limpia el memo de snapshots."""
    st.session_state["base_sig"] = datetime.now().isoformat()
    st.session_state["_snap_memo"] = {}

def _build_snapshot(proyecto, fecha_obj, version):
    """Versión memoizada de builder.build sobre la base en sesión."""
    sig = st.session_state.get("base_sig", "none")
    memo = st.session_state.setdefault("_snap_memo", {})
    key = (sig, proyecto, fecha_obj.isoformat(), version)
    snap = memo.get(key)
    if snap is None:
        snap = builder.build(st.session_state.records, proyecto, fecha_obj, version=version)
        memo[key] = snap
    return snap

# ── Valores MANUALES de indicadores (no provienen del flujo de caja) ──
# Se guardan por "firma" de selección de proyectos para que cada conjunto de
# proyectos recuerde sus propios valores. Persistencia best-effort en disco.
_MANUAL_IND_FILE = _CACHE_DIR / "manual_indicators.pkl"

def _load_manual_ind():
    import pickle
    if "_manual_ind" in st.session_state:
        return
    try:
        with open(_MANUAL_IND_FILE, "rb") as f:
            st.session_state["_manual_ind"] = pickle.load(f)
    except Exception:
        st.session_state["_manual_ind"] = {}

def _persist_manual_ind():
    import pickle
    try:
        _CACHE_DIR.mkdir(exist_ok=True)
        with open(_MANUAL_IND_FILE, "wb") as f:
            pickle.dump(st.session_state.get("_manual_ind", {}), f)
    except Exception:
        pass

def _get_manual(sig, key):
    return st.session_state.get("_manual_ind", {}).get(sig, {}).get(key, "")

def _set_manual(sig, key, value):
    store = st.session_state.setdefault("_manual_ind", {})
    store.setdefault(sig, {})[key] = value

_load_manual_ind()

# Auto-restauración al arrancar: si no hay base en sesión pero existe una
# guardada en disco, se restaura para que recargar la página no obligue a
# reprocesar los Excel.
if st.session_state.records is None and _BASE_CACHE_FILE.exists():
    _ts_restore = _restore_base()
    if _ts_restore is not None:
        st.session_state["base_restored_at"] = _ts_restore

# ─────────────────────────────────────────────
# SIN AUTO-CARGA — el usuario elige qué archivos cargar
# ─────────────────────────────────────────────
# Antes la app cargaba TODA la carpeta al abrir (muy lento). Ahora la lista
# de archivos se muestra en el módulo "📂 Cargar Base" y el usuario decide
# cuáles procesar — escaneo de carpeta es instantáneo (no parsea Excel).


# ─────────────────────────────────────────────
# HELPERS COMPARTIDOS — INDICADORES AVANZADOS
# ─────────────────────────────────────────────
# Función reutilizada por el Reporte Proyecto (pestaña Indicadores) y
# por el módulo Reporte Inversionista (sección de indicadores operativos).
# Retorna una lista de tuplas (nombre, valor_str, fuente_str).

def compute_indicadores_avanzados(snapshots_list, builder_obj):
    """
    Calcula 6 indicadores complementarios a los básicos:
      1. Vr. m² Inicial vs. Final (escalamiento de precio)
      3. Duración Comercial Total (meses)
      4. Costo Construcción / m² vendible
      7. Apalancamiento Máximo Requerido
      8. Punto de Equilibrio Operativo (fecha + meses desde inicio ventas)
      10. Rezago Venta → Escrituración (meses)
    """
    from backend.models import Participacion as _Part
    from datetime import date as _date

    def _fmt_cop_local(v):
        if v is None:
            return "N/A"
        sign = "-" if v < 0 else ""
        av = abs(v)
        if av >= 1_000_000:
            mills = av / 1_000_000
            if mills >= 1_000:
                fmt = f"{mills:,.0f}".replace(",", ".")
            else:
                fmt = f"{mills:,.1f}"
            return f"{sign}${fmt}M"
        return f"{sign}${av:,.0f}"

    # ── Recolectar valores por (mes, proyecto) para 1.3, 17.1, 17.3, 3.22, 10.0, 19.x ──
    # Sumamos los snapshots (consolidado).
    serie_13: Dict[str, float] = {}   # ventas vendido por mes (línea 1.3)
    serie_17_1: Dict[str, float] = {} # unidades vendidas por mes
    serie_17_3: Dict[str, float] = {} # m² vendidos por mes
    serie_3_22: Dict[str, float] = {} # construcción por mes
    serie_10_0: Dict[str, float] = {} # FCO por mes
    serie_1_0: Dict[str, float]  = {} # ingresos totales al proyecto por mes (línea 1.0)

    def _acumular(serie: Dict[str, float], linea):
        if not linea:
            return
        for fecha_str, val in linea.valores.items():
            serie[fecha_str] = serie.get(fecha_str, 0.0) + (val or 0.0)

    todas_las_fechas = set()
    for s in snapshots_list:
        todas_las_fechas.update(s.fechas_flujo)
        _acumular(serie_13,   builder_obj.get_linea_exacta(s, "1.3",  _Part.TOTAL))
        _acumular(serie_17_1, builder_obj.get_linea_exacta(s, "17.1", _Part.TOTAL))
        _acumular(serie_17_3, builder_obj.get_linea_exacta(s, "17.3", _Part.TOTAL))
        _acumular(serie_3_22, builder_obj.get_linea_exacta(s, "3.22", _Part.TOTAL))
        _acumular(serie_10_0, builder_obj.get_linea_exacta(s, "10.0", _Part.TOTAL))
        _acumular(serie_1_0,  builder_obj.get_linea_exacta(s, "1.0",  _Part.TOTAL))

    fechas_ord = sorted(todas_las_fechas)

    # Fallback de línea 1.3: si no existe, usar 1.0 (ingresos totales)
    if not serie_13 and serie_17_3:
        for s in snapshots_list:
            _acumular(serie_13, builder_obj.get_linea_exacta(s, "1.0", _Part.TOTAL))
        fuente_ventas_lbl = "1.0"
    else:
        fuente_ventas_lbl = "1.3"

    inds = []

    # ── (1) Vr. m² Inicial vs. Final ─────────────────────────────────────
    meses_ventas_act = [f for f in fechas_ord if serie_17_1.get(f, 0.0) > 0]
    if meses_ventas_act and serie_17_3:
        f_ini = meses_ventas_act[0]
        f_fin = meses_ventas_act[-1]
        m2_ini = serie_17_3.get(f_ini, 0.0)
        m2_fin = serie_17_3.get(f_fin, 0.0)
        v_ini = serie_13.get(f_ini, 0.0)
        v_fin = serie_13.get(f_fin, 0.0)
        precio_ini = (v_ini / m2_ini) if m2_ini > 0 else None
        precio_fin = (v_fin / m2_fin) if m2_fin > 0 else None
        if precio_ini and precio_fin and precio_ini > 0:
            delta_pct = (precio_fin / precio_ini - 1.0) * 100
            inds.append((
                "Vr. m² Inicial → Final",
                f"${precio_ini:,.0f} → ${precio_fin:,.0f}  ({delta_pct:+.1f}%)",
                f"{fuente_ventas_lbl} / 17.3 (primer vs. último mes de ventas)",
            ))
        else:
            inds.append(("Vr. m² Inicial → Final", "N/A", f"{fuente_ventas_lbl} / 17.3"))
    else:
        inds.append(("Vr. m² Inicial → Final", "N/A", f"{fuente_ventas_lbl} / 17.3"))

    # ── (3) Duración Comercial Total ─────────────────────────────────────
    if len(meses_ventas_act) >= 1:
        d_ini = _date.fromisoformat(meses_ventas_act[0])
        d_fin = _date.fromisoformat(meses_ventas_act[-1])
        meses_dur = (d_fin.year - d_ini.year) * 12 + (d_fin.month - d_ini.month) + 1
        inds.append((
            "Duración Comercial Total",
            f"{meses_dur} meses",
            f"17.1 ({meses_ventas_act[0]} → {meses_ventas_act[-1]})",
        ))
    else:
        inds.append(("Duración Comercial Total", "N/A", "17.1"))

    # ── (4) Costo Construcción / m² vendible ─────────────────────────────
    total_3_22 = sum(serie_3_22.values())
    total_17_3 = sum(serie_17_3.values())
    if total_17_3 > 0 and total_3_22 != 0:
        inds.append((
            "Costo Construcción / m² vendible",
            f"${abs(total_3_22)/total_17_3:,.0f}/m²",
            "3.22 / 17.3",
        ))
    else:
        inds.append(("Costo Construcción / m² vendible", "N/A", "3.22 / 17.3"))

    # ── (7) Apalancamiento Máximo Requerido (min del acumulado FCO 10.0) ──
    if serie_10_0:
        acum = 0.0
        min_acum = 0.0
        min_fecha = None
        for f in fechas_ord:
            acum += serie_10_0.get(f, 0.0)
            if acum < min_acum:
                min_acum = acum
                min_fecha = f
        if min_acum < 0 and min_fecha:
            inds.append((
                "Apalancamiento Máximo Requerido",
                f"{_fmt_cop_local(min_acum)}",
                f"min(Σ 10.0) en {min_fecha}",
            ))
        else:
            inds.append((
                "Apalancamiento Máximo Requerido",
                "$0 (sin déficit)",
                "min(Σ 10.0)",
            ))
    else:
        inds.append(("Apalancamiento Máximo Requerido", "N/A", "10.0"))

    # ── (8) Punto de Equilibrio Comercial ────────────────────────────────
    # Distancia en meses entre el inicio de ventas (17.1 > 0) y el inicio
    # de los ingresos al proyecto (1.0 > 0). Mide cuánto se demora la caja
    # del proyecto en recibir flujos efectivos después de comenzar a vender.
    meses_ingresos_act = [f for f in fechas_ord if serie_1_0.get(f, 0.0) > 0]
    if meses_ventas_act and meses_ingresos_act:
        f_v0 = meses_ventas_act[0]
        f_i0 = meses_ingresos_act[0]
        d_v0 = _date.fromisoformat(f_v0)
        d_i0 = _date.fromisoformat(f_i0)
        delta_pe_com = (d_i0.year - d_v0.year) * 12 + (d_i0.month - d_v0.month)
        inds.append((
            "Punto de Equilibrio Comercial",
            f"{delta_pe_com:+d} meses",
            f"Inicio ingresos ({f_i0}) − Inicio ventas ({f_v0})",
        ))
    else:
        inds.append((
            "Punto de Equilibrio Comercial",
            "N/A",
            "Inicio 1.0 − Inicio 17.1",
        ))

    return inds


# ─────────────────────────────────────────────
# HELPERS COMPARTIDOS — P&G DE FACTIBILIDAD
# ─────────────────────────────────────────────
# Construcción reutilizable del P&G (misma lógica que la pestaña Factibilidad)
# para el módulo "Comparación Proyectos". Autocontenido: no modifica la pestaña.

def _pyg_fmt_num(v):
    sign = "-" if v < 0 else ""
    av = abs(v)
    if av >= 1_000_000:
        s_ = f"${av/1_000_000:,.0f}".replace(",", ".")
    else:
        s_ = f"${av:,.0f}".replace(",", ".")
    return f"{sign}{s_}" if v < 0 else s_

def pyg_estructura(snapshots, builder):
    """Devuelve (pyg_struct, dev_idx) replicando la estructura del P&G."""
    from itertools import combinations
    P = Participacion

    def _tot(snap, indice):
        l = builder.get_linea_exacta(snap, indice, P.TOTAL)
        if not l:
            l = builder.get_linea_exacta(snap, indice, P.IC)
        return l.total_periodo if l else 0.0

    def _val(indice):
        return sum(_tot(s, indice) for s in snapshots)

    def _subs(root):
        found = {}
        for s in snapshots:
            for ln in s.lineas:
                parts = ln.indice.split(".")
                if len(parts) == 2 and parts[0] == root and parts[1] != "0":
                    found[ln.indice] = ln.nombre or ln.indice
        return sorted(found.items(), key=lambda x: [int(p) for p in x[0].split(".") if p.isdigit()])

    def _existe(indice):
        return any(ln.indice == indice for s in snapshots for ln in s.lineas)

    def _nombre(indice):
        for s in snapshots:
            for ln in s.lineas:
                if ln.indice == indice and ln.nombre:
                    return ln.nombre
        return ""

    _OVR = {"costos incurridos": "Relacionados Lote"}
    def _nm(nm):
        return _OVR.get((nm or "").strip().lower(), nm)

    def _es_suma_subset(target, vals, tol=0.01):
        if not vals or abs(target) < 1.0:
            return False
        base = max(abs(target), 1.0)
        for n in range(1, min(len(vals), 6) + 1):
            for combo in combinations(vals, n):
                if abs(sum(combo) - target) / base < tol:
                    return True
        return False

    struct = [("1.0", "Ventas", "header", 1)]
    subs_2 = _subs("2")
    if subs_2:
        if len(subs_2) >= 2:
            fv = _val(subs_2[0][0]); ov = [_val(idx) for idx, _ in subs_2[1:]]
            if _es_suma_subset(fv, ov):
                subs_2 = subs_2[1:]
        for idx, nm in subs_2:
            struct.append((idx, _nm(nm), "item", 1))
    else:
        struct.append(("2.0", "Lote", "item", 1))
    struct.append(("3.0", "Costo Directo", "item", 1))
    if _existe("7.0"):
        struct.append(("7.0", "-Iva", "negative", -1))
    struct.append(("5.0", "Honorarios", "item", 1))
    struct.append(("4.0", "Indirectos", "italic", 1))
    for idx, nm in _subs("4"):
        struct.append((idx, nm, "subitem", 1))
    struct.append(("__calc:total_costos", "Total Costos", "subtotal", 1))
    struct.append(("__calc:uo", "Utilidad Operativa", "result", 1))
    struct.append(("__calc:financieros", "Financieros", "item", 1))
    dev_idx = None
    for ti in ("8.0", "5.9", "5.10"):
        if _existe(ti):
            struct.append((ti, _nombre(ti) or "Devolución Honorarios", "italic", 1))
            dev_idx = ti
            break
    struct.append(("__calc:utilidad", "Utilidad", "result", 1))
    struct.append(("__calc:capital_req", "Capital Requerido", "result", 1))
    return struct, dev_idx

def pyg_filas(struct, dev_idx, snapshots, builder):
    """Devuelve (col_defs, filas) para una estructura dada y un grupo de snapshots.
    filas: lista de dicts {key,label,tipo,signo,vals} donde vals[0]=Consolidado."""
    P = Participacion

    def _tot(snap, indice):
        l = builder.get_linea_exacta(snap, indice, P.TOTAL)
        if not l:
            l = builder.get_linea_exacta(snap, indice, P.IC)
        return l.total_periodo if l else 0.0

    def _val(indice, snap=None):
        if snap is not None:
            return _tot(snap, indice)
        return sum(_tot(s, indice) for s in snapshots)

    def _val_for(key, snap):
        if key == "__calc:total_costos":
            return _val("9.0", snap) - _val("6.0", snap)
        if key == "__calc:uo":
            return _val("1.0", snap) - (_val("9.0", snap) - _val("6.0", snap))
        if key == "__calc:financieros":
            return abs(_val("6.0", snap))
        if key == "__calc:utilidad":
            uo = _val("1.0", snap) - (_val("9.0", snap) - _val("6.0", snap))
            fin = abs(_val("6.0", snap))
            dev = _val(dev_idx, snap) if dev_idx else 0.0
            return uo - fin + dev
        if key == "__calc:capital_req":
            return abs(_val("13.2", snap)) + abs(_val("14.2", snap))
        return _val(key, snap)

    col_defs = [(None, "Consolidado")] + [(s, str(s.proyecto)) for s in snapshots]
    filas = []
    for key, label, tipo, signo in struct:
        vals = [_val_for(key, snap) * signo for snap, _ in col_defs]
        filas.append({"key": key, "label": label, "tipo": tipo, "signo": signo, "vals": vals})
    return col_defs, filas


def _cmp_xirr(cashflows, fechas_iso, guess=0.1):
    """XIRR anualizada (misma lógica que xirr_fc) para flujos mensuales."""
    from datetime import date as _d
    pairs = [(cf, _d.fromisoformat(str(f)[:10])) for cf, f in zip(cashflows, fechas_iso) if cf != 0.0]
    if len(pairs) < 2:
        return None
    cfs = [p[0] for p in pairs]
    dts = [p[1] for p in pairs]
    if not (any(v > 0 for v in cfs) and any(v < 0 for v in cfs)):
        return None
    d0 = dts[0]
    yf = [(d - d0).days / 365.0 for d in dts]

    def npv(r):
        t = 0.0
        for cf, y in zip(cfs, yf):
            try:
                t += cf / ((1.0 + r) ** y)
            except (OverflowError, ZeroDivisionError):
                return float("inf")
        return t

    if npv(10.0) > 0:
        return None

    def dnpv(r):
        t = 0.0
        for cf, y in zip(cfs, yf):
            try:
                t -= y * cf / ((1.0 + r) ** (y + 1.0))
            except (OverflowError, ZeroDivisionError):
                return float("inf")
        return t

    rate = guess
    for _ in range(500):
        fv, dfv = npv(rate), dnpv(rate)
        if abs(dfv) < 1e-14:
            break
        nr = max(-0.99, min(rate - fv / dfv, 10.0))
        if abs(nr - rate) < 1e-9:
            return nr
        rate = nr
    lo, hi = -0.99, 10.0
    f_lo = npv(lo)
    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid)
        if abs(f_mid) < 1e-6 or (hi - lo) < 1e-9:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return None

def _cmp_fmt_tir(v):
    return f"{v * 100:.2f}% E.A." if v is not None else "N/A"

def _cmp_serie_mes(indice, snapshots, builder, fechas):
    P = Participacion
    agg = {}
    for s in snapshots:
        l = builder.get_linea_exacta(s, indice, P.TOTAL) or builder.get_linea_exacta(s, indice, P.IC)
        if l:
            for f, v in l.valores.items():
                agg[f] = agg.get(f, 0.0) + (v or 0.0)
    return [agg.get(f, 0.0) for f in fechas]

def cmp_tirs(snapshots, builder):
    """Devuelve (TIR FCO, TIR K) consolidadas del grupo."""
    fechas = sorted(set().union(*[set(s.fechas_flujo) for s in snapshots])) if snapshots else []
    if not fechas:
        return None, None
    ing = _cmp_serie_mes("1.0", snapshots, builder, fechas)
    c9  = _cmp_serie_mes("9.0", snapshots, builder, fechas)
    c6  = _cmp_serie_mes("6.0", snapshots, builder, fechas)
    raw = [ing[k] - (c9[k] - c6[k]) for k in range(len(fechas))]
    tir_fco = _cmp_xirr(raw, fechas)
    ap = [-abs(v) for v in _cmp_serie_mes("13.2", snapshots, builder, fechas)]
    re = [abs(v) for v in _cmp_serie_mes("13.4", snapshots, builder, fechas)]
    fk = [a + r for a, r in zip(ap, re)]
    tir_k = _cmp_xirr(fk, fechas)
    return tir_fco, tir_k

def cmp_hitos(snapshots, builder):
    """Devuelve (grupos, orden) con hitos Ventas/Obra/Entregas por proyecto."""
    from datetime import date as _d
    P = Participacion
    hito_defs = [("Ventas", "17.1"), ("Obra", "3.22"), ("Entregas", "18.1")]

    def _rango(snap, idx):
        l = builder.get_linea_exacta(snap, idx, P.TOTAL)
        if not l:
            return None, None
        act = [f for f in snap.fechas_flujo if l.valores.get(f, 0.0) != 0.0]
        return (act[0], act[-1]) if act else (None, None)

    grupos, orden = {}, []
    for s in snapshots:
        for nm, idx in hito_defs:
            fi, ff = _rango(s, idx)
            if fi:
                p = str(s.proyecto)
                if p not in grupos:
                    grupos[p] = []; orden.append(p)
                di, df_ = _d.fromisoformat(fi), _d.fromisoformat(ff)
                dur = max(1, (df_.year - di.year) * 12 + df_.month - di.month)
                grupos[p].append((nm, fi, ff, f"{dur} meses"))
    return grupos, orden


# ─────────────────────────────────────────────
# SIDEBAR NAVEGACIÓN
# ─────────────────────────────────────────────

logo_path = Path(__file__).parent / "LOGO IC 2026.png"
if logo_path.exists():
    st.sidebar.image(str(logo_path), width=160)

st.sidebar.title("Estate Auditor")
st.sidebar.markdown("---")

# Limpiar query params residuales de iteraciones anteriores (legacy)
for _qp_key in ("pyg_open_inv_key", "pyg_open_inv_col",
                "pyg_open_proy_key", "pyg_open_proy_col"):
    if _qp_key in st.query_params:
        del st.query_params[_qp_key]

modulo = st.sidebar.radio(
    "Módulos",
    ["📂 Cargar Base", "🔍 Auditoría", "📈 Reporte Inversionista",
     "📊 Reporte Proyecto", "🆚 Comparación Proyectos", "💼 Flujo Proyecto (Control)"],
    label_visibility="collapsed",
    key="modulo_main_nav",
)

# Indicador de estado de la base
if st.session_state.records:
    resp = st.session_state.upload_response
    st.sidebar.success(f"✅ Base cargada\n{resp.total_registros:,} registros · {len(resp.proyectos)} proyecto(s)")
else:
    st.sidebar.warning("⚠️ Sin base cargada")

st.sidebar.markdown("---")
st.sidebar.caption("IC Constructora SAS · v2.0 MVP")


# ═════════════════════════════════════════════
# MÓDULO 1 — CARGAR BASE
# ═════════════════════════════════════════════

if modulo == "📂 Cargar Base":
    st.title("📂 Cargar Base de Datos")
    st.markdown(
        "Selecciona los archivos `.xlsx` que quieres procesar. "
        "Cuando hay varios archivos para el mismo (proyecto, corte), las versiones "
        "se etiquetan como `YYYY-MM-DD-1`, `YYYY-MM-DD-2`, … según la fecha de modificación."
    )

    # ── Aviso de base restaurada desde caché (Fase 1.2) ──
    if st.session_state.get("base_restored_at") is not None and st.session_state.records:
        _ts = st.session_state["base_restored_at"]
        _ts_str = _ts.strftime("%Y-%m-%d %H:%M") if hasattr(_ts, "strftime") else str(_ts)
        _ci1, _ci2 = st.columns([4, 1])
        with _ci1:
            st.info(
                f"♻️ Base restaurada automáticamente del último guardado "
                f"(**{_ts_str}**). Para usar datos frescos, vuelve a cargar abajo."
            )
        with _ci2:
            if st.button("🗑️ Limpiar caché", help="Borra la base guardada en disco."):
                _clear_base_cache()
                for _k in ("records", "upload_response", "files_processed",
                           "auto_load_ok", "base_restored_at"):
                    st.session_state.pop(_k, None)
                st.session_state.records = None
                st.rerun()

    def _do_load(folder_path: Path, selected: Optional[list] = None):
        """Carga la base desde la carpeta, filtrando archivos si selected != None."""
        _pbar_ph = st.empty()
        _status_ph = st.empty()
        _pbar = _pbar_ph.progress(0, text="Inicializando…")

        def _cb(done: int, total: int, current_name: str):
            try:
                pct = int(min(100, max(0, round((done / max(total, 1)) * 100))))
                _pbar.progress(
                    pct,
                    text=(f"Procesando {min(done + 1, total)}/{total}: {current_name}"
                          if done < total else f"Procesados {total}/{total}")
                )
                _status_ph.caption(f"📂 {done}/{total} archivos · {pct}%")
            except Exception:
                pass

        try:
            records, response, files_meta = load_database_from_folder(
                folder_path, progress_callback=_cb, selected_filenames=selected,
                parse_fn=_parse_excel_cached,
            )
            st.session_state.records = records
            st.session_state.upload_response = response
            st.session_state.files_processed = files_meta
            st.session_state.report = None
            st.session_state.auto_load_ok = True
            st.session_state.auto_load_error = None
            _nueva_firma_base()  # Fase 1.3 — invalidar memo de snapshots
            _persist_base()  # Fase 1.2 — guardar para restaurar tras recargar
            _pbar_ph.empty(); _status_ph.empty()
            return True
        except Exception as e:
            _pbar_ph.empty(); _status_ph.empty()
            st.session_state.auto_load_ok = False
            st.session_state.auto_load_error = str(e)
            return False

    # ── Panel de selección de archivos ──
    st.markdown(f"**Carpeta fuente:**  \n`{DEFAULT_DB_FOLDER}`")

    # Listar archivos (rápido, sin parsear)
    try:
        archivos_disponibles = list_database_files(DEFAULT_DB_FOLDER)
    except Exception as e:
        archivos_disponibles = []
        st.error(f"❌ No se pudo leer la carpeta: {e}")

    if archivos_disponibles:
        st.markdown(f"#### 📑 Archivos disponibles ({len(archivos_disponibles)})")
        st.caption(
            "Marca solo los que necesites. Cargar menos archivos = arranque mucho más rápido. "
            "Los archivos están ordenados por **fecha de modificación** (más reciente primero)."
        )

        # Tabla informativa con tamaños y fechas
        df_disp = pd.DataFrame(
            [{"Archivo": n,
              "Modificado": ts.strftime("%Y-%m-%d %H:%M"),
              "Tamaño (MB)": round(sz / (1024 * 1024), 2)}
             for n, ts, sz in archivos_disponibles]
        )
        st.dataframe(df_disp, use_container_width=True, hide_index=True,
                     height=min(35 * len(archivos_disponibles) + 38, 320))

        nombres_archivos = [n for n, _, _ in archivos_disponibles]

        # Default: el más reciente seleccionado (1 archivo)
        default_sel = [nombres_archivos[0]] if nombres_archivos else []

        seleccion = st.multiselect(
            "Selecciona los archivos a cargar:",
            options=nombres_archivos,
            default=default_sel,
            key="files_to_load",
            help="Por defecto se preselecciona el más reciente.",
        )

        b1, b2, b3, _ = st.columns([1.3, 1.3, 1.3, 3])
        with b1:
            cargar_sel = st.button(
                f"📥 Cargar seleccionados ({len(seleccion)})",
                type="primary",
                disabled=(len(seleccion) == 0),
                help="Procesa solo los archivos marcados arriba.",
            )
        with b2:
            cargar_todos = st.button(
                f"📦 Cargar TODOS ({len(nombres_archivos)})",
                help="Procesa los " + str(len(nombres_archivos)) + " archivos. Puede tardar varios minutos.",
            )
        with b3:
            if st.button("🔄 Refrescar lista", help="Vuelve a escanear la carpeta."):
                st.rerun()

        if cargar_sel and seleccion:
            with st.spinner(f"Procesando {len(seleccion)} archivo(s)…"):
                if _do_load(DEFAULT_DB_FOLDER, selected=seleccion):
                    st.success(f"✅ {len(seleccion)} archivo(s) cargados")
                    st.rerun()
                else:
                    st.error(f"❌ Error: {st.session_state.get('auto_load_error', '')}")

        if cargar_todos:
            with st.spinner(f"Procesando {len(nombres_archivos)} archivos (toma varios minutos)…"):
                if _do_load(DEFAULT_DB_FOLDER, selected=None):
                    st.success("✅ Base cargada completa")
                    st.rerun()
                else:
                    st.error(f"❌ Error: {st.session_state.get('auto_load_error', '')}")

    # ── Estado de carga ──
    st.divider()
    if st.session_state.get("auto_load_ok") is True and st.session_state.records:
        n_files = len(st.session_state.get("files_processed", []))
        st.success(f"✅ Base cargada — {n_files} archivo(s), {st.session_state.upload_response.total_registros:,} registros.")
    elif st.session_state.get("auto_load_error"):
        st.error(f"⚠️ Último intento falló:  \n`{st.session_state.get('auto_load_error')}`")
        st.markdown("#### 📥 Subida manual (fallback)")
        st.caption("Si la carpeta no está accesible, puedes subir manualmente uno o varios archivos.")
        uploaded_files = st.file_uploader(
            "Arrastra uno o varios archivos Excel BASE aquí:",
            type=["xlsx", "xls"],
            accept_multiple_files=True,
            key="fallback_uploader",
        )
        if uploaded_files and st.button("⚙️ Procesar archivos manuales", type="primary"):
            with st.spinner("Procesando archivos manuales…"):
                try:
                    # Reusar la lógica de versionado: replicar load_database_from_folder en memoria.
                    from datetime import datetime as _dt
                    all_records = []
                    all_warnings = []
                    files_meta = []
                    version_counter = {}
                    # Ordenar por nombre como proxy (no hay mtime para uploaded files)
                    for uf in sorted(uploaded_files, key=lambda x: x.name):
                        try:
                            records, response = _parse_excel_cached(uf.getvalue())
                        except Exception as e:
                            all_warnings.append(f"❌ Error procesando '{uf.name}': {e}")
                            continue
                        for w in response.warnings:
                            all_warnings.append(f"[{uf.name}] {w}")
                        keys = {(r.proyecto, r.fecha_datos) for r in records}
                        version_asignada = {}
                        for k in keys:
                            actual = version_counter.get(k, 0)
                            version_asignada[k] = actual + 1
                            version_counter[k] = actual + 1
                        for r in records:
                            r.version = version_asignada[(r.proyecto, r.fecha_datos)]
                        all_records.extend(records)
                        files_meta.append((uf.name, _dt.now(), len(records), len({r.proyecto for r in records})))

                    if not all_records:
                        st.error("No se extrajo ningún registro válido de los archivos.")
                    else:
                        # Construir UploadResponse
                        from backend.models import UploadResponse as _UR
                        from backend.folder_loader import make_fecha_label
                        proyectos_labels = {}
                        for r in all_records:
                            proyectos_labels.setdefault(r.proyecto, set())
                            max_v = version_counter[(r.proyecto, r.fecha_datos)]
                            proyectos_labels[r.proyecto].add(
                                make_fecha_label(r.fecha_datos, r.version, max_v)
                            )
                        fpp = {p: sorted(list(l)) for p, l in proyectos_labels.items()}
                        resp = _UR(
                            proyectos=sorted(list(proyectos_labels.keys())),
                            fechas_datos=fpp,
                            total_registros=len(all_records),
                            warnings=all_warnings,
                        )
                        st.session_state.records = all_records
                        st.session_state.upload_response = resp
                        st.session_state.files_processed = files_meta
                        st.session_state.report = None
                        st.session_state.auto_load_ok = True
                        _nueva_firma_base()  # Fase 1.3 — invalidar memo de snapshots
                        _persist_base()  # Fase 1.2 — guardar para restaurar tras recargar
                        st.success(f"✅ {len(files_meta)} archivo(s) procesado(s) · {len(all_records):,} registros")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error procesando archivos manuales: {e}")

    # ── Métricas y detalle ──
    if st.session_state.upload_response:
        st.divider()
        resp = st.session_state.upload_response
        files_meta = st.session_state.get("files_processed", [])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Archivos cargados", len(files_meta))
        c2.metric("Registros Totales", f"{resp.total_registros:,}")
        c3.metric("Proyectos", len(resp.proyectos))
        c4.metric("Versiones de corte", sum(len(v) for v in resp.fechas_datos.values()))

        if files_meta:
            with st.expander(f"📑 Archivos procesados ({len(files_meta)})"):
                df_files = pd.DataFrame(
                    [{"Archivo": n, "Modificado": ts.strftime("%Y-%m-%d %H:%M"),
                      "Registros": cnt, "Proyectos": npr}
                     for n, ts, cnt, npr in files_meta]
                )
                st.dataframe(df_files, use_container_width=True, hide_index=True)

        if resp.warnings:
            with st.expander(f"⚠️ Advertencias del parser ({len(resp.warnings)})"):
                for w in resp.warnings:
                    st.caption(w)

        st.subheader("Proyectos y Versiones Disponibles")
        for proy in resp.proyectos:
            fechas = resp.fechas_datos.get(proy, [])
            with st.expander(f"📂 **{proy}** — {len(fechas)} versión(es)"):
                # Sufijo -N indica sub-versión del mismo mes
                df_vers = pd.DataFrame({"Versión": sorted(fechas, reverse=True)})
                st.dataframe(df_vers, use_container_width=True, hide_index=True, height=min(35*len(fechas)+38, 400))


# ═════════════════════════════════════════════
# MÓDULO 2 — AUDITORÍA
# ═════════════════════════════════════════════

elif modulo == "🔍 Auditoría":
    st.title("🔍 Módulo de Auditoría")
    st.markdown("Ejecuta el motor de validación completo sobre el flujo de caja de un proyecto.")
    st.divider()

    if not st.session_state.records:
        st.warning("⚠️ Primero carga la Base de Datos en el módulo **📂 Cargar Base**.")
        st.stop()

    resp = st.session_state.upload_response
    c1, c2 = st.columns(2)

    with c1:
        selected_proyecto = st.selectbox("Proyecto", resp.proyectos)

    with c2:
        fechas = resp.fechas_datos.get(selected_proyecto, [])
        selected_fecha = st.selectbox("Fecha de Corte (Versión)", sorted(fechas, reverse=True))

    if st.button("🚀 Ejecutar Validación Completa", type="primary"):
        with st.spinner("Reconstruyendo modelo financiero y corriendo motor de reglas…"):
            try:
                fecha_obj, version_obj = parse_fecha_label(selected_fecha)
                snapshot = builder.build(st.session_state.records, selected_proyecto, fecha_obj, version=version_obj)
                reporte_crudo = engine.generate_report(snapshot, include_snapshot=True)
                st.session_state.report = enriquecer_reporte(reporte_crudo)
            except Exception as e:
                import traceback
                st.error(f"Error en validación: {e}")
                st.code(traceback.format_exc())

    if st.session_state.report:
        rep = st.session_state.report
        enc = rep["encabezado"]
        res = rep["resumen_ejecutivo"]

        color_class = (
            "status-ok" if enc["estado"] == "OK"
            else "status-warning" if enc["estado"] == "REVISAR"
            else "status-critical"
        )

        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.subheader(f"Diagnóstico Financiero: {enc['proyecto']}")
            st.caption(f"Corte: {enc['fecha_datos']}")
            st.info(f"📋 Dictamen: {res['narrativa']}")
        with col_b:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Score Integridad</div>
                <div class="metric-value {color_class}">{enc['score']}%</div>
                <div class="{color_class}">{enc['estado']}</div>
            </div>
            """, unsafe_allow_html=True)

        st.write("")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Reglas Aprobadas", f"{res['aprobadas']} / {res['total_validaciones']}")
        kpi2.metric("Errores Críticos", res['errores_criticos'])
        kpi3.metric("Advertencias", res['advertencias'])
        kpi4.metric("Informativos", res['informativos'])

        st.divider()
        st.subheader(f"Detalle de Inconsistencias ({len(rep['hallazgos'])})")

        if not rep['hallazgos']:
            st.success("✅ ¡El flujo de caja no presenta ninguna inconsistencia bajo las reglas actuales!")

        for h in rep['hallazgos']:
            icon = "🔴" if h['severidad'] == "critico" else "🟠" if h['severidad'] == "advertencia" else "🔵"
            with st.expander(f"{icon} {h['nombre']}  —  Líneas afectadas: {', '.join(h['lineas_afectadas'])}"):
                st.write(f"**Descripción:** {h['descripcion']}")
                if h['valor_esperado'] is not None or h['valor_observado'] is not None:
                    cols_met = st.columns(3)
                    cols_met[0].metric("Valor Observado", h['valor_observado'])
                    cols_met[1].metric("Valor Esperado", h['valor_esperado'])
                    cols_met[2].metric("Diferencia / Tolerancia", f"Δ {h['diferencia']}", f"Tol: {h['tolerancia']}")
                st.markdown(f"**Diagnóstico de Analista:**\n> {h['explicacion_financiera']}")
                if h.get('detalle_por_mes'):
                    st.write("**Detalle mensual:**")
                    df_meses = pd.DataFrame(list(h['detalle_por_mes'].items()), columns=["Mes", "Diferencia"])
                    st.dataframe(df_meses.set_index("Mes").T, use_container_width=True)


# ═════════════════════════════════════════════
# MÓDULO 3 — REPORTE INVERSIONISTA
# ═════════════════════════════════════════════

elif modulo == "📈 Reporte Inversionista":
    st.title("📈 Reporte Inversionista")
    st.markdown("Análisis financiero del retorno del inversionista sobre el flujo de caja del proyecto.")
    st.divider()

    if not st.session_state.records:
        st.warning("⚠️ Primero carga la Base de Datos en el módulo **📂 Cargar Base**.")
        st.stop()

    def _reset_inv():
        st.session_state.show_reporte_inversionista = False

    resp = st.session_state.upload_response
    c1, c2 = st.columns(2)
    with c1:
        inv_proyectos = st.multiselect("Proyectos", resp.proyectos, default=[resp.proyectos[0]], key="inv_proyectos", on_change=_reset_inv)
    with c2:
        if len(inv_proyectos) == 1:
            fechas_inv = resp.fechas_datos.get(inv_proyectos[0], [])
            inv_fecha = st.selectbox("Fecha de Corte", sorted(fechas_inv, reverse=True), key="inv_fecha", on_change=_reset_inv)
        else:
            st.info("Usando la última versión de cada proyecto.")
            inv_fecha = None

    if not inv_proyectos:
        st.warning("Selecciona al menos un proyecto para continuar.")
        st.stop()

    if st.button("📊 Generar Reporte Inversionista", type="primary"):
        st.session_state.show_reporte_inversionista = True

    if st.session_state.get("show_reporte_inversionista", False):
        with st.spinner("Reconstruyendo flujos y calculando indicadores del portafolio…"):
            try:
                snapshots = []
                for p in inv_proyectos:
                    if inv_fecha and len(inv_proyectos) == 1:
                        f_obj, v_obj = parse_fecha_label(inv_fecha)
                    else:
                        fechas_p = resp.fechas_datos.get(p, [])
                        ultima_f = sorted(fechas_p, reverse=True)[0]
                        f_obj, v_obj = parse_fecha_label(ultima_f)

                    snap = _build_snapshot(p, f_obj, v_obj)
                    snapshots.append(snap)

                # ── 1. HELPER DE EXTRACCIÓN MÚLTIPLE ──
                def get_valores(snaps, indice_prefix, part=Participacion.IC):
                    """Busca la línea y suma los valores de todos los snapshots seleccionados, alineando fechas."""
                    todas_fechas = set()
                    for s in snaps:
                        todas_fechas.update(s.fechas_flujo)
                    fechas_ordenadas = sorted(list(todas_fechas))
                    
                    valores_agregados = {f: 0.0 for f in fechas_ordenadas}
                    
                    for s in snaps:
                        linea = None
                        for suffix in [".0", ""]:
                            linea = builder.get_linea_exacta(s, indice_prefix + suffix, part)
                            if linea: break
                        if not linea:
                            for suffix in [".0", ""]:
                                linea = builder.get_linea_exacta(s, indice_prefix + suffix, Participacion.TOTAL)
                                if linea: break
                        if linea:
                            for f in s.fechas_flujo:
                                valores_agregados[f] += linea.valores.get(f, 0.0)
                                
                    return fechas_ordenadas, [valores_agregados[f] for f in fechas_ordenadas]

                # ── 2. EXTRACCIÓN DE LÍNEAS BASE ──
                fechas_labels, ingresos_vals   = get_valores(snapshots, "1")
                _,             fco_vals        = get_valores(snapshots, "10")
                _,             financieros_vals = get_valores(snapshots, "6")
                _,             aportes_raw      = get_valores(snapshots, "13.2")
                _,             reintegros_raw   = get_valores(snapshots, "13.4")

                # ── 3. EXTRACCIÓN DE HONORARIOS IC ──
                # 5.22 H. Construcción IC | 5.42 H. Comercialización IC
                # 5.62 H. Gerencia IC     | 5.82 H. Estructuración IC
                INDICES_HON = ["5.22", "5.42", "5.62", "5.82"]
                n = len(fechas_labels)
                hon_raw = [0.0] * n
                hon_encontrados = []
                for idx_hon in INDICES_HON:
                    _, vals_hon = get_valores(snapshots, idx_hon)
                    if any(v != 0.0 for v in vals_hon):
                        hon_encontrados.append(idx_hon)
                    hon_raw = [h + v for h, v in zip(hon_raw, vals_hon)]
                # Honorarios son ingresos para el inversionista → signo positivo
                honorarios = [abs(v) for v in hon_raw]

                # ── 4. FORZAR SIGNOS EQUITY (CFO LOGIC — NON NEGOTIABLE) ──
                aportes    = [-abs(v) for v in aportes_raw]
                reintegros = [ abs(v) for v in reintegros_raw]

                # ── 5. FLUJOS DERIVADOS (solo equity) ──
                flujo_inv  = [a + r for a, r in zip(aportes, reintegros)]
                flujo_acum = []
                acum = 0.0
                for f in flujo_inv:
                    acum += f
                    flujo_acum.append(acum)


                # ── 6. HELPERS FINANCIEROS ──
                from datetime import datetime as _dt

                def _parse_date(s):
                    if isinstance(s, date):
                        return s
                    return date.fromisoformat(str(s)[:10])

                def xirr(cashflows, dates_str, guess=0.1):
                    pairs = [(cf, _parse_date(d)) for cf, d in zip(cashflows, dates_str) if cf != 0.0]
                    if len(pairs) < 2:
                        return None
                    cfs = [p[0] for p in pairs]
                    dts = [p[1] for p in pairs]
                    if not (any(v > 0 for v in cfs) and any(v < 0 for v in cfs)):
                        return None
                    d0 = dts[0]
                    year_fracs = [(d - d0).days / 365.0 for d in dts]

                    def npv_at(r):
                        total = 0.0
                        for cf, yf in zip(cfs, year_fracs):
                            try:
                                total += cf / ((1.0 + r) ** yf)
                            except (OverflowError, ZeroDivisionError):
                                return float('inf')
                        return total

                    # Si el NPV a 1000% sigue siendo positivo, la TIR real es
                    # mayor a 1000% → la consideramos "infinita" y retornamos None
                    # (evita reportar artificialmente un techo de 1000%).
                    if npv_at(10.0) > 0:
                        return None

                    def dnpv_at(r):
                        total = 0.0
                        for cf, yf in zip(cfs, year_fracs):
                            try:
                                total -= yf * cf / ((1.0 + r) ** (yf + 1.0))
                            except (OverflowError, ZeroDivisionError):
                                return float('inf')
                        return total

                    rate = guess
                    for _ in range(500):
                        f_val  = npv_at(rate)
                        df_val = dnpv_at(rate)
                        if abs(df_val) < 1e-14:
                            break
                        new_rate = rate - f_val / df_val
                        new_rate = max(-0.99, min(new_rate, 10.0))
                        if abs(new_rate - rate) < 1e-9:
                            return new_rate
                        rate = new_rate

                    lo, hi = -0.99, 10.0
                    f_lo = npv_at(lo)
                    for _ in range(200):
                        mid   = (lo + hi) / 2.0
                        f_mid = npv_at(mid)
                        if abs(f_mid) < 1e-6 or (hi - lo) < 1e-9:
                            return mid
                        if f_lo * f_mid < 0:
                            hi = mid
                        else:
                            lo   = mid
                            f_lo = f_mid
                    return None

                # ── 7. FORMATO MONEDA (convención colombiana — M siempre = millones) ──
                def fmt_cop(v):
                    """
                    Convención colombiana: M = millones (siempre).
                      ≥ 1.000.000.000  →  $X.XXXM  (miles de millones con separador de miles)
                                          Ej: 53.000.000.000 → $53.000M
                      ≥ 1.000.000      →  $XXXM    (millones)
                                          Ej: 320.000.000 → $320M
                      < 1.000.000      →  $X.XXX   (pesos)
                    """
                    if v is None:
                        return "N/A"
                    sign = "-" if v < 0 else ""
                    av = abs(v)
                    if av >= 1_000_000:
                        mills = av / 1_000_000
                        # Usar separador de miles (punto en convención colombiana)
                        # Python usa coma como separador de miles en :, → lo reemplazamos por punto
                        if mills >= 1_000:
                            fmt = f"{mills:,.0f}".replace(",", ".")
                        elif mills >= 100:
                            fmt = f"{mills:,.0f}"
                        else:
                            fmt = f"{mills:,.1f}"
                        return f"{sign}${fmt}M"
                    return f"{sign}${av:,.0f}"

                def fmt_cop_short(v):
                    """Versión corta para etiquetas en el gráfico (misma convención)."""
                    if v is None:
                        return ""
                    sign = "-" if v < 0 else ""
                    av = abs(v)
                    if av >= 1_000_000:
                        mills = av / 1_000_000
                        if mills >= 1_000:
                            fmt = f"{mills:,.0f}".replace(",", ".")
                        else:
                            fmt = f"{mills:,.0f}"
                        return f"{sign}${fmt}M"
                    return f"{sign}${av:,.0f}"

                def fmt_tir(v):
                    if v is None:
                        return "N/A"
                    return f"{v * 100:.2f}% E.A."

                # ── 8. KPIs SUPERIORES (fijos: no dependen de honorarios) ──
                ventas_total = sum(ingresos_vals)
                utilidad     = sum(fco_vals)
                fco_fin_vals = [f + fin for f, fin in zip(fco_vals, financieros_vals)]
                tir_op       = xirr(fco_fin_vals, fechas_labels)
                tir_inv_base = xirr(flujo_inv, fechas_labels)
                margen_op    = (utilidad / ventas_total * 100) if ventas_total != 0 else 0

                if len(inv_proyectos) == 1:
                    tit_proy = inv_proyectos[0]
                    tit_fecha = inv_fecha
                else:
                    tit_proy = f"Portafolio ({len(inv_proyectos)} proyectos)"
                    tit_fecha = "Últimas versiones"

                st.subheader(f"Indicadores Clave — {tit_proy} | Corte: {tit_fecha}")
                k1, k2, k3, k4 = st.columns(4)
                with k1:
                    st.markdown(f"""
                    <div class="kpi-box">
                      <div class="kpi-label">Ventas Totales (1.0 Ingresos)</div>
                      <div class="kpi-value">{fmt_cop(ventas_total)}</div>
                    </div>""", unsafe_allow_html=True)
                with k2:
                    st.markdown(f"""
                    <div class="kpi-box">
                      <div class="kpi-label">Utilidad Operativa (10.0 FCO)</div>
                      <div class="kpi-value">{fmt_cop(utilidad)}</div>
                    </div>""", unsafe_allow_html=True)
                with k3:
                    st.markdown(f"""
                    <div class="kpi-box">
                      <div class="kpi-label">Margen Operativo (%)</div>
                      <div class="kpi-value">{margen_op:.1f}%</div>
                    </div>""", unsafe_allow_html=True)
                with k4:
                    st.markdown(f"""
                    <div class="kpi-box">
                      <div class="kpi-label">TIR Operativa (FCO + Financieros)</div>
                      <div class="kpi-value">{fmt_tir(tir_op)}</div>
                    </div>""", unsafe_allow_html=True)

                # ── 9. CONTROLES DEL GRÁFICO ──
                st.subheader("Flujo de Caja IC")

                # Toggle "Consolidado / Por proyecto" solo si hay más de 1 proyecto
                _multi_proj_inv = len(inv_proyectos) > 1
                if _multi_proj_inv:
                    ctrl_view = st.columns([1.8, 5])
                    with ctrl_view[0]:
                        view_mode_inv = st.radio(
                            "Modo de vista:",
                            ["Consolidado", "Por proyecto"],
                            horizontal=True,
                            key="inv_view_mode",
                            help=("Por proyecto: dibuja barras y líneas separadas para cada "
                                  "proyecto filtrado, con un color distinto por etapa."),
                        )
                else:
                    view_mode_inv = "Consolidado"
                is_por_proy_inv = (view_mode_inv == "Por proyecto")

                # Callbacks para mutua exclusividad a nivel de widget:
                # al prender uno, el otro se apaga automáticamente.
                def _on_toggle_reciclar_cap():
                    if st.session_state.get("inv_reciclar_cap"):
                        st.session_state["inv_sin_retornos"] = False

                def _on_toggle_sin_retornos():
                    if st.session_state.get("inv_sin_retornos"):
                        st.session_state["inv_reciclar_cap"] = False

                ctrl1, ctrl2, ctrl3, ctrl4, ctrl5 = st.columns([2, 1, 1, 1.1, 1.3])
                with ctrl1:
                    agrupacion = st.radio(
                        "Agrupar por:", ["Mes", "Año"], horizontal=True,
                        index=1, key="inv_agrupacion"
                    )
                with ctrl2:
                    incl_hon = st.toggle(
                        "➕ Incluir Honorarios IC",
                        value=False,
                        key="inv_incl_hon",
                        help="Suma las líneas 5.22, 5.42, 5.62, 5.82 al flujo del inversionista"
                    )
                with ctrl3:
                    _popover_lbl = getattr(st, "popover", None)
                    if _popover_lbl is not None:
                        with st.popover("🏷️ Etiquetas"):
                            lbl_inv_aportes    = st.checkbox("Aportes Equity",    value=False, key="inv_lbl_aportes")
                            lbl_inv_reintegros = st.checkbox("Reintegros Equity", value=False, key="inv_lbl_reintegros")
                            lbl_inv_honorarios = st.checkbox("Honorarios IC",     value=False, key="inv_lbl_honorarios")
                            lbl_inv_acumulado  = st.checkbox("Línea acumulada",   value=False, key="inv_lbl_acumulado")
                    else:
                        with st.expander("🏷️ Etiquetas"):
                            lbl_inv_aportes    = st.checkbox("Aportes Equity",    value=False, key="inv_lbl_aportes")
                            lbl_inv_reintegros = st.checkbox("Reintegros Equity", value=False, key="inv_lbl_reintegros")
                            lbl_inv_honorarios = st.checkbox("Honorarios IC",     value=False, key="inv_lbl_honorarios")
                            lbl_inv_acumulado  = st.checkbox("Línea acumulada",   value=False, key="inv_lbl_acumulado")
                with ctrl4:
                    reciclar_cap = st.toggle(
                        "♻️ Reciclar capital",
                        value=False,
                        key="inv_reciclar_cap",
                        on_change=_on_toggle_reciclar_cap,
                        disabled=is_por_proy_inv,
                        help=("Reutiliza los primeros reintegros para cubrir aportes posteriores. "
                              "Sólo se piden recursos hasta el punto de máxima inversión necesaria. "
                              "Solo aplica en vista Consolidado.")
                    )
                with ctrl5:
                    sin_retornos = st.toggle(
                        "⛔ Sin retornos intermedios",
                        value=False,
                        key="inv_sin_retornos",
                        on_change=_on_toggle_sin_retornos,
                        disabled=is_por_proy_inv,
                        help=("Represa TODOS los reintegros: primero solo aportes (100% del "
                              "capital), y los reintegros se sueltan de golpe cuando la última "
                              "etapa (la que escritura más tarde, línea 18.1) salda su crédito "
                              "(11.0 ≤ 0) y termina de pagar el lote bruto (2.22). "
                              "Mutuamente excluyente con Reciclar capital. "
                              "Solo aplica en vista Consolidado.")
                    )
                # En vista "Por proyecto" estas transformaciones no aplican (son
                # conceptos del flujo consolidado): se fuerzan a OFF.
                if is_por_proy_inv:
                    reciclar_cap = False
                    sin_retornos = False
                # Mutuamente excluyentes: si está "sin retornos", se ignora el reciclaje.
                elif sin_retornos:
                    reciclar_cap = False

                if incl_hon and not hon_encontrados:
                    st.warning("⚠️ No se encontraron líneas de honorarios IC (5.22, 5.42, 5.62, 5.82) en este snapshot.")

                # ── 9.b RECICLADO DE CAPITAL (opcional) ──
                # Recicla el flujo neto del proyecto: el capital se pide año tras
                # año a medida que el acumulado baja a un nuevo mínimo. Cualquier
                # ingreso (reintegros y, si Incluir Honorarios está activo, también
                # honorarios) que llegue antes del peak se HOLDea y se usa para
                # cubrir aportes futuros. Después del peak no se pide más capital y
                # cualquier caída transitoria se absorbe reteniendo distribuciones.
                def _recyc_net(net_in):
                    n_ = len(net_in)
                    if n_ == 0:
                        return []
                    cum = [0.0] * n_
                    s_ = 0.0
                    for i, f in enumerate(net_in):
                        s_ += f
                        cum[i] = s_
                    p_idx = 0
                    p_val = cum[0]
                    for i in range(1, n_):
                        if cum[i] < p_val:
                            p_val = cum[i]
                            p_idx = i
                    f_rec = [0.0] * n_
                    run_prev = 0.0
                    for i in range(p_idx + 1):
                        run_min = min(run_prev, cum[i])
                        f_rec[i] = run_min - run_prev
                        run_prev = run_min
                    run_prev = cum[p_idx]
                    for i in range(p_idx + 1, n_):
                        run_max = max(run_prev, cum[i])
                        f_rec[i] = run_max - run_prev
                        run_prev = run_max
                    return f_rec

                # ── 9.c SIN RETORNOS INTERMEDIOS (opcional) ──
                # Represa TODOS los reintegros hasta que la última etapa (la que
                # escritura más tarde, 18.1) salde su crédito (11.0 ≤ 0) y termine
                # de pagar el lote bruto (2.22). Los aportes quedan intactos en su
                # cronograma; los honorarios no se tocan.
                def _ultimo_mes_con_valor(snap, indice):
                    """Última fecha del snapshot con valor != 0 en `indice`."""
                    linea = builder.get_linea_exacta(snap, indice, Participacion.TOTAL)
                    if not linea:
                        return None
                    fs = [f for f in snap.fechas_flujo if abs(linea.valores.get(f, 0.0)) > 1e-9]
                    return max(fs) if fs else None

                def _fecha_saldo_cero(snap, indice="11.0"):
                    """Primer mes en que el saldo (11.0) cae a <= 0 tras haber sido positivo."""
                    linea = builder.get_linea_exacta(snap, indice, Participacion.TOTAL)
                    if not linea:
                        return None
                    visto_pos = False
                    for f in sorted(snap.fechas_flujo):
                        v = linea.valores.get(f, 0.0)
                        if v > 1e-6:
                            visto_pos = True
                        elif visto_pos and v <= 1e-6:
                            return f
                    return None

                if sin_retornos:
                    # 1) Última etapa = la que escritura (18.1) más tarde
                    _ult_snap, _ult_fecha = None, None
                    for s in snapshots:
                        f18 = _ultimo_mes_con_valor(s, "18.1")
                        if f18 is not None and (
                            _ult_fecha is None or _parse_date(f18) > _parse_date(_ult_fecha)
                        ):
                            _ult_fecha, _ult_snap = f18, s
                    if _ult_snap is None:  # fallback: fin de flujo más tardío
                        _ult_snap = max(
                            snapshots,
                            key=lambda s: _parse_date(max(s.fechas_flujo)) if s.fechas_flujo else _parse_date("1900-01-01")
                        )

                    # 2) Momento de liberación = max(saldo 11.0 ≤ 0, lote bruto 2.22 pagado)
                    _f_credito = _fecha_saldo_cero(_ult_snap, "11.0")
                    _f_lote    = _ultimo_mes_con_valor(_ult_snap, "2.22")
                    _cands = [f for f in (_f_credito, _f_lote) if f is not None]
                    _f_liberacion = max(_cands, key=lambda f: _parse_date(f)) if _cands else None

                    # 3) Mapear la fecha de liberación al índice del eje consolidado
                    if _f_liberacion is None:
                        rel_idx = len(fechas_labels) - 1
                    else:
                        _fl_d = _parse_date(_f_liberacion)
                        rel_idx = next(
                            (i for i, f in enumerate(fechas_labels) if _parse_date(f) >= _fl_d),
                            len(fechas_labels) - 1,
                        )

                    # 4) Represar reintegros previos y soltarlos de golpe en rel_idx
                    aportes_view    = list(aportes)      # intactos
                    honorarios_view = list(honorarios)   # intactos
                    reintegros_view = [0.0] * n
                    _held = 0.0
                    for i in range(n):
                        if i < rel_idx:
                            _held += reintegros[i]                       # represado
                        elif i == rel_idx:
                            reintegros_view[i] = reintegros[i] + _held    # suelta de golpe
                        else:
                            reintegros_view[i] = reintegros[i]            # posteriores normales

                    flujo_inv_view  = [a + r for a, r in zip(aportes_view, reintegros_view)]
                    flujo_acum_view = []
                    _s = 0.0
                    for _f in flujo_inv_view:
                        _s += _f
                        flujo_acum_view.append(_s)
                    tir_inv_base_view = xirr(flujo_inv_view, fechas_labels)

                    _lbl_lib   = str(_f_liberacion)[:7] if _f_liberacion else "fin del flujo"
                    _lbl_etapa = str(_ult_snap.proyecto) if _ult_snap else "?"
                    st.caption(
                        f"⛔ **Sin retornos intermedios** · Última etapa: **{_lbl_etapa}** · "
                        f"Reintegros liberados en **{_lbl_lib}** "
                        f"(saldo crédito 11.0 ≤ 0 y lote bruto 2.22 pagado)."
                    )
                elif reciclar_cap:
                    # Si se incluyen honorarios, también participan del reciclado
                    # (cubren aportes futuros y se HOLDean pre-peak).
                    if incl_hon:
                        net_in = [a + r + h for a, r, h in zip(aportes, reintegros, honorarios)]
                    else:
                        net_in = [a + r for a, r in zip(aportes, reintegros)]
                    f_rec = _recyc_net(net_in)

                    aportes_view  = [v if v < 0.0 else 0.0 for v in f_rec]
                    pos_view      = [v if v > 0.0 else 0.0 for v in f_rec]

                    if incl_hon:
                        # Repartir las distribuciones recicladas entre reintegros y
                        # honorarios según la proporción original del periodo.
                        reintegros_view  = [0.0] * n
                        honorarios_view  = [0.0] * n
                        for i, p_ in enumerate(pos_view):
                            denom = reintegros[i] + honorarios[i]
                            if denom > 0.0:
                                honorarios_view[i] = p_ * honorarios[i] / denom
                                reintegros_view[i] = p_ * reintegros[i] / denom
                            else:
                                reintegros_view[i] = p_
                    else:
                        reintegros_view = list(pos_view)
                        honorarios_view = list(honorarios)

                    flujo_inv_view  = [a + r for a, r in zip(aportes_view, reintegros_view)]
                    flujo_acum_view = []
                    _s = 0.0
                    for _f in flujo_inv_view:
                        _s += _f
                        flujo_acum_view.append(_s)
                    tir_inv_base_view = xirr(flujo_inv_view, fechas_labels)
                else:
                    aportes_view      = aportes
                    reintegros_view   = reintegros
                    honorarios_view   = honorarios
                    flujo_inv_view    = flujo_inv
                    flujo_acum_view   = flujo_acum
                    tir_inv_base_view = tir_inv_base

                # ── 10. PREPARAR SERIES SEGÚN AGRUPACIÓN ──
                if agrupacion == "Año":
                    df_chart = pd.DataFrame({
                        "Fecha":      [_parse_date(d) for d in fechas_labels],
                        "Aportes":    aportes_view,
                        "Reintegros": reintegros_view,
                        "Honorarios": honorarios_view,
                        "Flujo":      flujo_inv_view,
                    })
                    df_chart["Año"] = [d.year for d in df_chart["Fecha"]]
                    df_agrup = df_chart.groupby("Año")[
                        ["Aportes", "Reintegros", "Honorarios", "Flujo"]
                    ].sum().reset_index()
                    df_agrup["Flujo Acumulado"] = df_agrup["Flujo"].cumsum()
                    df_agrup["Flujo + Hon"]     = (df_agrup["Flujo"] + df_agrup["Honorarios"]).cumsum()

                    chart_x          = df_agrup["Año"].astype(str).tolist()
                    chart_aportes    = df_agrup["Aportes"].tolist()
                    chart_reintegros = df_agrup["Reintegros"].tolist()
                    chart_honorarios = df_agrup["Honorarios"].tolist()
                    chart_acum       = df_agrup["Flujo Acumulado"].tolist()
                    chart_acum_hon   = df_agrup["Flujo + Hon"].tolist()
                else:
                    chart_x          = list(fechas_labels)
                    chart_aportes    = aportes_view
                    chart_reintegros = reintegros_view
                    chart_honorarios = honorarios_view
                    chart_acum       = flujo_acum_view
                    hon_acum_tmp = []
                    a2 = 0.0
                    for f, h in zip(flujo_inv_view, honorarios_view):
                        a2 += f + h
                        hon_acum_tmp.append(a2)
                    chart_acum_hon = hon_acum_tmp

                # Seleccionar qué acumulado graficar
                acum_a_graficar = chart_acum_hon if incl_hon else chart_acum
                linea_nombre    = "Acumulado + Honorarios" if incl_hon else "Flujo Acumulado Equity"

                # ── Colores per-periodo para etiquetas (contraste cuando se superponen a barras) ──
                # Regla: blanco sobre barras oscuras, negro sobre barras claras, color
                # original cuando la etiqueta cae en espacio en blanco.
                _n_chart = len(chart_x)
                # Reintegros: etiqueta "outside" queda en la base de la barra de honorarios
                # cuando honorarios > 0 (verde claro) → negro.
                _rein_lbl_colors = []
                for _i in range(_n_chart):
                    _h = chart_honorarios[_i] if (incl_hon and _i < len(chart_honorarios)) else 0
                    if _h > 0:
                        _rein_lbl_colors.append("#000000")
                    else:
                        _rein_lbl_colors.append("#2E7D52")

                # Línea acumulado: revisar si el marcador cae dentro de alguna barra.
                _line_lbl_colors = []
                for _i in range(_n_chart):
                    _y = acum_a_graficar[_i]
                    _apo = chart_aportes[_i] if chart_aportes[_i] < 0 else 0.0
                    _rein = chart_reintegros[_i] if chart_reintegros[_i] > 0 else 0.0
                    _hon = chart_honorarios[_i] if (incl_hon and chart_honorarios[_i] > 0) else 0.0
                    _stack_top = _rein + _hon
                    if _y < 0 and _y > _apo:
                        _line_lbl_colors.append("#FFFFFF")     # dentro de aportes (oscuro)
                    elif 0 < _y <= _rein:
                        _line_lbl_colors.append("#FFFFFF")     # dentro de reintegros (oscuro)
                    elif _rein < _y <= _stack_top:
                        _line_lbl_colors.append("#000000")     # dentro de honorarios (claro)
                    else:
                        _line_lbl_colors.append("#681E1E")     # sin superposición

                # ── 11. CALCULAR TIR PARA TÍTULO DEL GRÁFICO ──
                if incl_hon:
                    flujo_con_hon = [a + r + h for a, r, h in zip(aportes_view, reintegros_view, honorarios_view)]
                    tir_grafico   = xirr(flujo_con_hon, fechas_labels)
                else:
                    tir_grafico = tir_inv_base_view

                # ── 12. CONSTRUIR FIGURA ──
                fig = go.Figure()

                # Paleta para "Por proyecto" — un color por etapa filtrada.
                PROYECTO_COLORS_INV = [
                    "#681E1E", "#1F6F40", "#1E5FA8", "#B8841F",
                    "#7B287B", "#16A085", "#34495E", "#C0392B",
                ]

                # ── Acumuladores para alinear los ceros del eje y y el y2 ──
                # Reúno aquí todos los valores que van a barras (eje y) y todos
                # los que van a línea acumulada (eje y2), para luego calcular
                # rangos que mantengan el cero en la misma posición en ambos ejes.
                _bar_vals_all  = []
                _line_vals_all = []

                if is_por_proy_inv:
                    # ══════════ MODO POR PROYECTO ══════════
                    # Para cada snapshot, recomputar series y graficar con
                    # offsetgroup distinto y color único por proyecto.
                    titulo_inv_dyn = f"Flujo de Caja IC · Vista por proyecto ({len(snapshots)} etapas)"
                    for _idx, _snap in enumerate(snapshots):
                        _proj = str(_snap.proyecto)
                        _color_p = PROYECTO_COLORS_INV[_idx % len(PROYECTO_COLORS_INV)]

                        # Extracción por snapshot
                        _fechas_p, _aportes_raw_p = get_valores([_snap], "13.2")
                        _, _reintegros_raw_p = get_valores([_snap], "13.4")
                        _n_p = len(_fechas_p)
                        _hon_raw_p = [0.0] * _n_p
                        for _idx_hon in INDICES_HON:
                            _, _vals_hon_p = get_valores([_snap], _idx_hon)
                            _hon_raw_p = [h + v for h, v in zip(_hon_raw_p, _vals_hon_p)]

                        # Convención de signos (mismo que el flujo principal)
                        _aportes_p    = [-abs(v) for v in _aportes_raw_p]
                        _reintegros_p = [ abs(v) for v in _reintegros_raw_p]
                        _honorarios_p = [ abs(v) for v in _hon_raw_p]
                        _flujo_inv_p  = [a + r for a, r in zip(_aportes_p, _reintegros_p)]

                        # Reciclado por proyecto (opcional)
                        if reciclar_cap:
                            if incl_hon:
                                _net_in_p = [a + r + h for a, r, h in zip(
                                    _aportes_p, _reintegros_p, _honorarios_p)]
                            else:
                                _net_in_p = [a + r for a, r in zip(_aportes_p, _reintegros_p)]
                            _f_rec_p = _recyc_net(_net_in_p)
                            _aportes_view_p = [v if v < 0 else 0.0 for v in _f_rec_p]
                            _pos_view_p     = [v if v > 0 else 0.0 for v in _f_rec_p]
                            if incl_hon:
                                _rein_view_p = [0.0] * _n_p
                                _hon_view_p  = [0.0] * _n_p
                                for _i, _p_ in enumerate(_pos_view_p):
                                    _den = _reintegros_p[_i] + _honorarios_p[_i]
                                    if _den > 0:
                                        _hon_view_p[_i]  = _p_ * _honorarios_p[_i] / _den
                                        _rein_view_p[_i] = _p_ * _reintegros_p[_i] / _den
                                    else:
                                        _rein_view_p[_i] = _p_
                            else:
                                _rein_view_p = list(_pos_view_p)
                                _hon_view_p  = list(_honorarios_p)
                        else:
                            _aportes_view_p = _aportes_p
                            _rein_view_p    = _reintegros_p
                            _hon_view_p     = _honorarios_p

                        # Agrupación Mes/Año
                        if agrupacion == "Año":
                            _df_p = pd.DataFrame({
                                "Fecha":      [_parse_date(d) for d in _fechas_p],
                                "Aportes":    _aportes_view_p,
                                "Reintegros": _rein_view_p,
                                "Honorarios": _hon_view_p,
                            })
                            _df_p["Año"] = [d.year for d in _df_p["Fecha"]]
                            _g = _df_p.groupby("Año")[["Aportes", "Reintegros", "Honorarios"]].sum().reset_index()
                            _x_p = _g["Año"].astype(str).tolist()
                            _ap_x  = _g["Aportes"].tolist()
                            _re_x  = _g["Reintegros"].tolist()
                            _hon_x = _g["Honorarios"].tolist()
                        else:
                            _x_p = list(_fechas_p)
                            _ap_x  = list(_aportes_view_p)
                            _re_x  = list(_rein_view_p)
                            _hon_x = list(_hon_view_p)

                        # Acumulado por proyecto
                        if incl_hon:
                            _per_net_p = [a + r + h for a, r, h in zip(_ap_x, _re_x, _hon_x)]
                        else:
                            _per_net_p = [a + r for a, r in zip(_ap_x, _re_x)]
                        _acum_p = []
                        _s_p = 0.0
                        for _v in _per_net_p:
                            _s_p += _v
                            _acum_p.append(_s_p)

                        # TIR por proyecto (sobre serie mensual original, no agregada)
                        if incl_hon:
                            _flujo_tir_p = [a + r + h for a, r, h in zip(
                                _aportes_view_p, _rein_view_p, _hon_view_p)]
                        else:
                            _flujo_tir_p = [a + r for a, r in zip(_aportes_view_p, _rein_view_p)]
                        _tir_p = xirr(_flujo_tir_p, _fechas_p)

                        # Recolectar para alinear ceros entre y e y2
                        _bar_vals_all.extend(list(_ap_x) + list(_re_x) + list(_hon_x))
                        _line_vals_all.extend(list(_acum_p))

                        # ── Barras del proyecto, con offsetgroup = proj ──
                        fig.add_trace(go.Bar(
                            x=_x_p, y=_ap_x,
                            name=f"{_proj} · Aportes",
                            marker_color=_color_p,
                            opacity=0.92,
                            offsetgroup=_proj,
                            text=[fmt_cop_short(v) for v in _ap_x] if lbl_inv_aportes else None,
                            textposition="outside",
                            outsidetextfont=dict(size=12, color=_color_p),
                            cliponaxis=False,
                        ))
                        fig.add_trace(go.Bar(
                            x=_x_p, y=_re_x,
                            name=f"{_proj} · Reintegros",
                            marker_color=_color_p,
                            opacity=0.55,
                            offsetgroup=_proj,
                            text=[fmt_cop_short(v) for v in _re_x] if lbl_inv_reintegros else None,
                            textposition="outside",
                            outsidetextfont=dict(size=12, color=_color_p),
                            cliponaxis=False,
                        ))
                        if incl_hon and any(v > 0 for v in _hon_x):
                            fig.add_trace(go.Bar(
                                x=_x_p, y=_hon_x,
                                name=f"{_proj} · Honorarios",
                                marker_color=_color_p,
                                marker_line=dict(color=_color_p, width=1),
                                opacity=0.30,
                                offsetgroup=_proj,
                                text=[fmt_cop_short(v) for v in _hon_x] if lbl_inv_honorarios else None,
                                textposition="outside",
                                outsidetextfont=dict(size=12, color=_color_p),
                                cliponaxis=False,
                            ))
                        # ── Línea acumulada del proyecto (eje secundario) ──
                        _suffix_tir = f" (TIR {fmt_tir(_tir_p)})" if _tir_p is not None else ""
                        fig.add_trace(go.Scatter(
                            x=_x_p, y=_acum_p,
                            name=f"{_proj} · Acum{_suffix_tir}",
                            mode="lines+markers+text" if lbl_inv_acumulado else "lines+markers",
                            line=dict(color=_color_p, width=3),
                            marker=dict(size=6),
                            text=[fmt_cop_short(v) for v in _acum_p] if lbl_inv_acumulado else None,
                            textposition="top center",
                            textfont=dict(size=11, color=_color_p),
                            cliponaxis=False,
                            yaxis="y2",
                        ))
                else:
                    # ══════════ MODO CONSOLIDADO (comportamiento original) ══════════
                    titulo_inv_dyn = (
                        f"Flujo de Caja IC | TIR: {fmt_tir(tir_grafico)}"
                        + (" (incl. Honorarios)" if incl_hon else "")
                    )
                    # Recolectar para alinear ceros entre y e y2
                    _bar_vals_all.extend(list(chart_aportes) + list(chart_reintegros))
                    if incl_hon:
                        _bar_vals_all.extend(list(chart_honorarios))
                    _line_vals_all.extend(list(acum_a_graficar))

                    # Barras aportes (negativo) — rojo oscuro
                    fig.add_trace(go.Bar(
                        x=chart_x,
                        y=chart_aportes,
                        name="Aportes Equity (13.2)",
                        marker_color="#7B1F1F",
                        opacity=0.90,
                        text=[fmt_cop_short(v) for v in chart_aportes] if lbl_inv_aportes else None,
                        textposition="outside",
                        outsidetextfont=dict(size=14, color="#7B1F1F"),
                        insidetextfont=dict(size=14, color="#FFFFFF"),
                        cliponaxis=False,
                    ))

                    # Barras reintegros equity (positivo) — verde oscuro
                    fig.add_trace(go.Bar(
                        x=chart_x,
                        y=chart_reintegros,
                        name="Reintegros Equity (13.4)",
                        marker_color="#2E7D52",
                        opacity=0.90,
                        text=[fmt_cop_short(v) for v in chart_reintegros] if lbl_inv_reintegros else None,
                        textposition="outside",
                        outsidetextfont=dict(size=14, color=_rein_lbl_colors),
                        insidetextfont=dict(size=14, color="#FFFFFF"),
                        cliponaxis=False,
                    ))

                    # Barras honorarios apiladas (positivo) — verde agua diferenciado
                    if incl_hon:
                        fig.add_trace(go.Bar(
                            x=chart_x,
                            y=chart_honorarios,
                            name="Honorarios IC (5.xx)",
                            marker_color="#82C4A0",
                            marker_line=dict(color="#2E7D52", width=1),
                            opacity=0.85,
                            text=[fmt_cop_short(v) for v in chart_honorarios] if lbl_inv_honorarios else None,
                            textposition="outside",
                            outsidetextfont=dict(size=14, color="#1a5c38"),
                            insidetextfont=dict(size=14, color="#1a5c38"),
                            cliponaxis=False,
                        ))

                    # Línea flujo acumulado (eje secundario)
                    fig.add_trace(go.Scatter(
                        x=chart_x,
                        y=acum_a_graficar,
                        name=linea_nombre,
                        mode="lines+markers+text" if lbl_inv_acumulado else "lines+markers",
                        line=dict(color="#681E1E", width=3),
                        marker=dict(size=6),
                        text=[fmt_cop_short(v) for v in acum_a_graficar] if lbl_inv_acumulado else None,
                        textposition="top center",
                        textfont=dict(size=14, color=_line_lbl_colors),
                        cliponaxis=False,
                        yaxis="y2",
                    ))

                # ── Alinear cero entre eje y (barras) y eje y2 (acumulado) ──
                # Estrategia: forzar la MISMA fracción del cero en ambos ejes.
                # f = -y_min / (y_max - y_min). Si los datos no requieren cierta
                # extensión, expandimos el lado faltante para igualar la fracción.
                def _aligned_ranges(bar_vals, line_vals, pad=0.05):
                    bmin = min(bar_vals + [0.0]) if bar_vals else -1.0
                    bmax = max(bar_vals + [0.0]) if bar_vals else 1.0
                    lmin = min(line_vals + [0.0]) if line_vals else -1.0
                    lmax = max(line_vals + [0.0]) if line_vals else 1.0
                    # Span sin contar cero (mínimo 1 para no dividir por cero)
                    b_span = max(bmax - bmin, 1.0)
                    l_span = max(lmax - lmin, 1.0)
                    fb = -bmin / b_span
                    fl = -lmin / l_span
                    f  = max(fb, fl)
                    f  = min(max(f, 0.0), 0.999)
                    # Ajustar cada eje a la fracción común manteniendo su max o min.
                    def _fit(y_min, y_max, target_f):
                        # Si f==0 → eje sin parte negativa
                        if target_f <= 0:
                            return (0.0, max(y_max, 1.0))
                        # Opción A: mantener y_max, recalcular y_min
                        if y_max > 0:
                            new_min_A = -target_f * y_max / (1 - target_f)
                        else:
                            new_min_A = y_min
                        # Opción B: mantener y_min, recalcular y_max
                        if y_min < 0:
                            new_max_B = -y_min * (1 - target_f) / target_f
                        else:
                            new_max_B = y_max
                        # Elegir la que cubre los datos originales
                        if new_min_A <= y_min and y_max <= y_max:
                            return (new_min_A, y_max)
                        return (y_min, new_max_B)
                    b_new = _fit(bmin, bmax, f)
                    l_new = _fit(lmin, lmax, f)
                    # Padding proporcional al span (mantiene f constante)
                    def _pad(rng):
                        s = rng[1] - rng[0]
                        return (rng[0] - pad * s, rng[1] + pad * s)
                    return _pad(b_new), _pad(l_new)

                _bar_range, _line_range = _aligned_ranges(_bar_vals_all, _line_vals_all)

                fig.update_layout(
                    barmode="relative",
                    height=560 if is_por_proy_inv else 520,
                    title=dict(
                        text=titulo_inv_dyn,
                        font=dict(size=16, color="#681E1E"),
                    ),
                    xaxis=dict(title="Periodo", tickangle=-45),
                    # Eje principal: barras (aportes / reintegros / honorarios)
                    yaxis=dict(
                        title="Barras · COP",
                        zeroline=True, zerolinecolor="#681E1E", zerolinewidth=1.5,
                        range=list(_bar_range),
                    ),
                    # Eje secundario: línea acumulada — mismo cero que el principal
                    yaxis2=dict(
                        title=dict(text="Acumulado · COP", font=dict(color="#681E1E")),
                        overlaying="y",
                        side="right",
                        showgrid=False,
                        zeroline=True,
                        zerolinecolor="#681E1E",
                        zerolinewidth=1,
                        tickfont=dict(color="#681E1E"),
                        range=list(_line_range),
                    ),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    plot_bgcolor="white",
                    paper_bgcolor="white",
                    font=dict(family="Inter, sans-serif"),
                    margin=dict(l=60, r=70, t=90, b=80),
                )
                fig.add_hline(y=0, line_color="#681E1E", line_dash="dash", line_width=1, opacity=0.5)

                st.plotly_chart(fig, use_container_width=True)

                # ── 13. KPIs INVERSIONISTA (sensibles a honorarios y reciclado) ──
                equity_req = sum(abs(a) for a in aportes_view)

                if incl_hon:
                    flujo_con_hon   = [a + r + h for a, r, h in zip(aportes_view, reintegros_view, honorarios_view)]
                    total_retorno   = sum(r + h for r, h in zip(reintegros_view, honorarios_view))
                    multiplo        = (total_retorno / equity_req) if equity_req != 0 else 0
                    tir_inv_kpi     = xirr(flujo_con_hon, fechas_labels)
                    # Acumulado para payback
                    flujo_acum_kpi  = []
                    a3 = 0.0
                    for f in flujo_con_hon:
                        a3 += f
                        flujo_acum_kpi.append(a3)
                    lbl_equity = f"{fmt_cop(equity_req)} (solo Equity)"
                    lbl_kpi_sfx = " + Hon."
                else:
                    total_retorno   = sum(reintegros_view)
                    multiplo        = (total_retorno / equity_req) if equity_req != 0 else 0
                    tir_inv_kpi     = tir_inv_base_view
                    flujo_acum_kpi  = flujo_acum_view
                    lbl_equity      = fmt_cop(equity_req)
                    lbl_kpi_sfx     = ""

                # Periodo de Retorno (Payback)
                first_aporte_idx   = next((i for i, a in enumerate(aportes_view) if a < 0), None)
                last_reintegro_idx = next(
                    (i for i in reversed(range(len(reintegros_view))) if reintegros_view[i] > 0), None
                )
                txt_retorno = "N/A"
                if equity_req > 0 and first_aporte_idx is not None:
                    payback_idx = None
                    for i, acum_v in enumerate(flujo_acum_kpi):
                        if acum_v >= 0 and i >= first_aporte_idx:
                            payback_idx = i
                            break
                    if payback_idx is not None:
                        d1 = _parse_date(fechas_labels[first_aporte_idx])
                        d2 = _parse_date(fechas_labels[payback_idx])
                        txt_retorno = f"{(d2 - d1).days / 365.25:.1f} años"
                    elif last_reintegro_idx is not None:
                        d1 = _parse_date(fechas_labels[first_aporte_idx])
                        d2 = _parse_date(fechas_labels[last_reintegro_idx])
                        txt_retorno = f"{(d2 - d1).days / 365.25:.1f} años (duración)"

                if incl_hon:
                    st.info("ℹ️ Los indicadores a continuación **incluyen Honorarios IC** (5.22, 5.42, 5.62, 5.82).")

                ik1, ik2, ik3, ik4 = st.columns(4)
                with ik1:
                    st.markdown(f"""<div class="kpi-box"><div class="kpi-label">Equity Requerido</div><div class="kpi-value">{lbl_equity}</div></div>""", unsafe_allow_html=True)
                with ik2:
                    st.markdown(f"""<div class="kpi-box"><div class="kpi-label">TIR Inversionista{lbl_kpi_sfx}</div><div class="kpi-value">{fmt_tir(tir_inv_kpi)}</div></div>""", unsafe_allow_html=True)
                with ik3:
                    st.markdown(f"""<div class="kpi-box"><div class="kpi-label">Múltiplo de Inversión{lbl_kpi_sfx}</div><div class="kpi-value">{multiplo:.2f}x</div></div>""", unsafe_allow_html=True)
                with ik4:
                    st.markdown(f"""<div class="kpi-box"><div class="kpi-label">Periodo de Retorno</div><div class="kpi-value">{txt_retorno}</div></div>""", unsafe_allow_html=True)

                # ── 14b. FACTIBILIDAD (P&G) — vista consolidada + por proyecto ──
                st.divider()
                st.subheader(f"💰 Factibilidad (P&G) — {tit_proy}")

                # Helpers de lectura del P&G
                def _pyg_val(indice, snap=None):
                    """Suma del total de un índice; en un snapshot o consolidado."""
                    src = [snap] if snap is not None else snapshots
                    total = 0.0
                    for s in src:
                        linea = builder.get_linea_exacta(s, indice, Participacion.TOTAL)
                        if not linea:
                            linea = builder.get_linea_exacta(s, indice, Participacion.IC)
                        if linea:
                            total += linea.total_periodo
                    return total

                def _pyg_nombre(indice):
                    """Nombre real del índice (toma del primer snapshot donde aparezca)."""
                    for s in snapshots:
                        for linea in s.lineas:
                            if linea.indice == indice and linea.nombre:
                                return linea.nombre
                    return ""

                def _pyg_subs(parent_root):
                    """Sub-índices directos 'root.x' donde x != '0'."""
                    found = {}
                    for s in snapshots:
                        for linea in s.lineas:
                            parts = linea.indice.split(".")
                            if len(parts) == 2 and parts[0] == parent_root and parts[1] != "0":
                                found[linea.indice] = linea.nombre or linea.indice
                    return sorted(found.items(), key=lambda x: [int(p) for p in x[0].split(".") if p.isdigit()])

                def _pyg_existe(indice):
                    for s in snapshots:
                        for linea in s.lineas:
                            if linea.indice == indice:
                                return True
                    return False

                # ── Construir estructura jerárquica del P&G ──
                # Cada entrada: (key, label, tipo, signo)
                # key: índice exacto del modelo, o "__calc:<expr>" para calculados.
                # tipo: 'header' | 'item' | 'subitem' | 'subtotal' | 'result' | 'italic' | 'negative'
                # signo: 1 (mostrar tal cual) o -1 (mostrar como negativo, ej. devolución IVA)
                pyg_struct = []
                pyg_struct.append(("1.0", "Ventas", "header", 1))

                # Lote y sub-conceptos (2.x). Si hay sub-índices, mostrar los subs; si no, mostrar 2.0.
                # ── Detectar subtotal redundante dentro de los subs de Lote ──
                # En algunos modelos el primer sub (ej. 2.1 "Lote Bruto") es la
                # suma de los siguientes (subconjunto) → es un subtotal duplicado
                # que conviene ocultar para no confundir.
                def _es_suma_subset(target, vals, tol=0.01):
                    from itertools import combinations
                    if not vals or abs(target) < 1.0:
                        return False
                    base = max(abs(target), 1.0)
                    for n in range(1, min(len(vals), 6) + 1):
                        for combo in combinations(vals, n):
                            if abs(sum(combo) - target) / base < tol:
                                return True
                    return False

                # Mapeo de nombres a presentar: cuando el flujo trae
                # nombres no canónicos, los normalizamos para que la tabla
                # quede consistente con la convención IC.
                _NAME_OVERRIDES = {
                    "costos incurridos": "Relacionados Lote",
                }
                def _nombre_pyg(nm):
                    key = (nm or "").strip().lower()
                    return _NAME_OVERRIDES.get(key, nm)

                subs_2 = _pyg_subs("2")
                if subs_2:
                    if len(subs_2) >= 2:
                        first_val   = _pyg_val(subs_2[0][0])
                        others_vals = [_pyg_val(idx) for idx, _ in subs_2[1:]]
                        if _es_suma_subset(first_val, others_vals):
                            subs_2 = subs_2[1:]
                    for idx, nm in subs_2:
                        pyg_struct.append((idx, _nombre_pyg(nm), "item", 1))
                else:
                    pyg_struct.append(("2.0", "Lote", "item", 1))

                pyg_struct.append(("3.0", "Costo Directo", "item", 1))
                if _pyg_existe("7.0"):
                    pyg_struct.append(("7.0", "-Iva", "negative", -1))
                pyg_struct.append(("5.0", "Honorarios", "item", 1))

                # Indirectos (4.x): mostrar 4.0 (subtotal italic) + subs (gris italic)
                pyg_struct.append(("4.0", "Indirectos", "italic", 1))
                for idx, nm in _pyg_subs("4"):
                    pyg_struct.append((idx, nm, "subitem", 1))

                # IMPORTANTE: 9.0 Total Costos del modelo INCLUYE financieros (6.0).
                # Para presentar UO antes de financieros y los financieros como línea
                # aparte, RESTAMOS 6.0 del 9.0 (lo sacamos del total de costos) y luego
                # lo sumamos como gasto independiente por fuera de la UO.
                pyg_struct.append(("__calc:total_costos", "Total Costos", "subtotal", 1))
                pyg_struct.append(("__calc:uo", "Utilidad Operativa", "result", 1))
                pyg_struct.append(("__calc:financieros", "Financieros", "item", 1))

                # Devolución honorarios (italic) — intentar índices comunes
                _dev_hon_idx = None
                for try_idx in ("8.0", "5.9", "5.10"):
                    if _pyg_existe(try_idx):
                        nm = _pyg_nombre(try_idx) or "Devolución Honorarios"
                        pyg_struct.append((try_idx, nm, "italic", 1))
                        _dev_hon_idx = try_idx
                        break

                # Utilidad neta calculada
                pyg_struct.append(("__calc:utilidad", "Utilidad", "result", 1))

                # Capital Requerido por etapa (Σ Aportes IC + Aportes Socio)
                pyg_struct.append(("__calc:capital_req", "Capital Requerido", "result", 1))

                # ── Columnas: Consolidado + un proyecto/snapshot por columna ──
                col_defs = [(None, "Consolidado")]
                for s in snapshots:
                    col_defs.append((s, str(s.proyecto)))

                # Total Ventas consolidado (denominador del %)
                ventas_consol = _pyg_val("1.0")

                def _val_for(key, snap):
                    if key == "__calc:total_costos":
                        # Restamos 6.0 (Financieros) del 9.0 para sacarlos del total
                        # de costos. Quedan como línea aparte, fuera de la UO.
                        return _pyg_val("9.0", snap) - _pyg_val("6.0", snap)
                    if key == "__calc:uo":
                        # Utilidad Operativa = Ventas - Costos (sin Financieros)
                        return _pyg_val("1.0", snap) - (_pyg_val("9.0", snap) - _pyg_val("6.0", snap))
                    if key == "__calc:financieros":
                        # Mostrar Financieros como gasto positivo (absoluto)
                        return abs(_pyg_val("6.0", snap))
                    if key == "__calc:utilidad":
                        # Utilidad Neta = UO - Financieros + Dev. Honorarios
                        uo  = _pyg_val("1.0", snap) - (_pyg_val("9.0", snap) - _pyg_val("6.0", snap))
                        fin = abs(_pyg_val("6.0", snap))
                        dev = _pyg_val(_dev_hon_idx, snap) if _dev_hon_idx else 0.0
                        return uo - fin + dev
                    if key == "__calc:capital_req":
                        # Capital Requerido = Σ Aportes IC (13.2) + Σ Aportes Socio (14.2)
                        return abs(_pyg_val("13.2", snap)) + abs(_pyg_val("14.2", snap))
                    return _pyg_val(key, snap)

                # ── Toggle "Mostrar avance" ──
                # Cuando está activo, cada celda numérica muestra una barra de
                # progreso de fondo con el % ejecutado al último día del mes
                # anterior (el flujo es mensual, así que evitamos cortar a mitad
                # de mes en curso).
                from datetime import date as _date_pyg, timedelta as _td_pyg
                _today_real    = _date_pyg.today()
                _hoy_pyg       = _date_pyg(_today_real.year, _today_real.month, 1) - _td_pyg(days=1)
                _hoy_pyg_label = _hoy_pyg.strftime("%d %b %Y")

                mostrar_avance_pyg = st.toggle(
                    f"📊 Mostrar avance al {_hoy_pyg_label}",
                    value=False,
                    key="pyg_mostrar_avance_inv",
                    help=(
                        "Pinta una barra detrás de cada valor con el % ejecutado "
                        f"al cierre del mes anterior ({_hoy_pyg_label}). "
                        "Pasa el cursor sobre la celda para ver el detalle."
                    ),
                )

                def _pyg_val_hoy(indice, snap=None):
                    """Suma de la línea sumando solo fechas <= hoy."""
                    src = [snap] if snap is not None else snapshots
                    total = 0.0
                    for s in src:
                        linea = builder.get_linea_exacta(s, indice, Participacion.TOTAL)
                        if not linea:
                            linea = builder.get_linea_exacta(s, indice, Participacion.IC)
                        if not linea:
                            continue
                        for f, v in linea.valores.items():
                            f_d = f if isinstance(f, _date_pyg) else _date_pyg.fromisoformat(str(f)[:10])
                            if f_d <= _hoy_pyg:
                                total += v
                    return total

                def _val_for_hoy(key, snap):
                    if key == "__calc:total_costos":
                        return _pyg_val_hoy("9.0", snap) - _pyg_val_hoy("6.0", snap)
                    if key == "__calc:uo":
                        return _pyg_val_hoy("1.0", snap) - (_pyg_val_hoy("9.0", snap) - _pyg_val_hoy("6.0", snap))
                    if key == "__calc:financieros":
                        return abs(_pyg_val_hoy("6.0", snap))
                    if key == "__calc:capital_req":
                        # Avance de capital: aportes IC + Socio ejecutados hasta hoy
                        return abs(_pyg_val_hoy("13.2", snap)) + abs(_pyg_val_hoy("14.2", snap))
                    if key == "__calc:utilidad":
                        # Convención IC: la utilidad se "materializa" cuando los reintegros
                        # superan el capital aportado. Reintegros (13.4 + 14.4) hasta hoy
                        # primero devuelven el capital total, y lo que sobra es utilidad.
                        rein_hoy      = abs(_pyg_val_hoy("13.4", snap)) + abs(_pyg_val_hoy("14.4", snap))
                        capital_total = abs(_pyg_val("13.2", snap))     + abs(_pyg_val("14.2", snap))
                        return max(0.0, rein_hoy - capital_total)
                    return _pyg_val_hoy(key, snap)

                # ── Render HTML ──
                def _fmt_pyg_num(v):
                    # Formato $X,XXX (en millones, sin decimales)
                    sign = "-" if v < 0 else ""
                    av = abs(v)
                    # Convención COP: en millones
                    if av >= 1_000_000:
                        m = av / 1_000_000
                        s = f"${m:,.0f}".replace(",", ".")
                    else:
                        s = f"${av:,.0f}".replace(",", ".")
                    return f"{sign}{s}" if v < 0 else s

                # ── Helpers para mini-gráfico de hover (barras + acumulado por año) ──
                def _pyg_serie_anual(indice, snap=None):
                    """Serie anual: [(año, total_año)] del índice (o consolidado)."""
                    src = [snap] if snap is not None else snapshots
                    por_anio = {}
                    for s in src:
                        linea = builder.get_linea_exacta(s, indice, Participacion.TOTAL)
                        if not linea:
                            linea = builder.get_linea_exacta(s, indice, Participacion.IC)
                        if not linea:
                            continue
                        for f, v in linea.valores.items():
                            f_d = f if isinstance(f, _date_pyg) else _date_pyg.fromisoformat(str(f)[:10])
                            por_anio[f_d.year] = por_anio.get(f_d.year, 0.0) + v
                    return sorted(por_anio.items())

                def _serie_anual_for(key, snap):
                    """Serie anual del valor (incluye fórmulas calculadas)."""
                    def _as_dict(idx):
                        return dict(_pyg_serie_anual(idx, snap))
                    if key == "__calc:total_costos":
                        s9, s6 = _as_dict("9.0"), _as_dict("6.0")
                        anios = sorted(set(s9) | set(s6))
                        return [(a, s9.get(a, 0.0) - s6.get(a, 0.0)) for a in anios]
                    if key == "__calc:uo":
                        s1, s9, s6 = _as_dict("1.0"), _as_dict("9.0"), _as_dict("6.0")
                        anios = sorted(set(s1) | set(s9) | set(s6))
                        return [(a, s1.get(a, 0.0) - (s9.get(a, 0.0) - s6.get(a, 0.0))) for a in anios]
                    if key == "__calc:financieros":
                        s6 = _as_dict("6.0")
                        return [(a, abs(v)) for a, v in sorted(s6.items())]
                    if key == "__calc:capital_req":
                        s132, s142 = _as_dict("13.2"), _as_dict("14.2")
                        anios = sorted(set(s132) | set(s142))
                        return [(a, abs(s132.get(a, 0.0)) + abs(s142.get(a, 0.0))) for a in anios]
                    if key == "__calc:utilidad":
                        s1, s9, s6 = _as_dict("1.0"), _as_dict("9.0"), _as_dict("6.0")
                        sdev = _as_dict(_dev_hon_idx) if _dev_hon_idx else {}
                        anios = sorted(set(s1) | set(s9) | set(s6) | set(sdev))
                        return [(a,
                                 s1.get(a, 0.0) - (s9.get(a, 0.0) - s6.get(a, 0.0))
                                 - abs(s6.get(a, 0.0)) + sdev.get(a, 0.0))
                                for a in anios]
                    return _pyg_serie_anual(key, snap)

                def _fmt_compact(v):
                    """Formato corto para SVG (sin decimales, M/B según escala)."""
                    sign = "-" if v < 0 else ""
                    av = abs(v)
                    if av >= 1_000_000_000:
                        return f"{sign}${av/1_000_000_000:.1f}B"
                    if av >= 1_000_000:
                        return f"{sign}${av/1_000_000:.0f}M"
                    if av >= 1_000:
                        return f"{sign}${av/1_000:.0f}K"
                    return f"{sign}${av:.0f}"

                def _build_minigraph_svg(serie_anual, signo=1):
                    W, H = 320, 130
                    _SC = 2.5  # factor de escala visual del popover
                    ml, mr, mt, mb = 36, 14, 14, 26
                    pw, ph = W - ml - mr, H - mt - mb
                    if not serie_anual:
                        return f'<svg width="{W*_SC:.0f}" height="{H*_SC:.0f}"></svg>'
                    anios = [a for a, _ in serie_anual]
                    vals  = [v * signo for _, v in serie_anual]
                    acum  = []
                    s = 0.0
                    for v in vals:
                        s += v
                        acum.append(s)
                    n = len(anios)
                    bar_w = (pw / n) * 0.62
                    y_min_b = min(0.0, min(vals))
                    y_max_b = max(0.0, max(vals))
                    y_rg_b  = max(y_max_b - y_min_b, 1.0)
                    y_min_a = min(0.0, min(acum))
                    y_max_a = max(0.0, max(acum))
                    y_rg_a  = max(y_max_a - y_min_a, 1.0)
                    def scb(v): return mt + ph * (1 - (v - y_min_b) / y_rg_b)
                    def sca(v): return mt + ph * (1 - (v - y_min_a) / y_rg_a)
                    zero = scb(0.0)
                    parts = [f'<svg width="{W*_SC:.0f}" height="{H*_SC:.0f}" '
                             f'viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">']
                    parts.append(f'<line x1="{ml}" y1="{zero:.1f}" x2="{W-mr}" y2="{zero:.1f}" stroke="#bbb" stroke-width="0.6"/>')
                    for i, (a, v) in enumerate(zip(anios, vals)):
                        xc = ml + pw * (i + 0.5) / n
                        x  = xc - bar_w/2
                        if v >= 0:
                            y_top, hgt = scb(v), max(scb(0.0) - scb(v), 1.0)
                        else:
                            y_top, hgt = scb(0.0), max(scb(v) - scb(0.0), 1.0)
                        color = "#681E1E" if v >= 0 else "#C0392B"
                        parts.append(f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" height="{hgt:.1f}" fill="{color}" opacity="0.80"/>')
                        parts.append(f'<text x="{xc:.1f}" y="{H-9}" text-anchor="middle" font-size="9" font-family="Inter,sans-serif" fill="#555">{a}</text>')
                    pts = []
                    for i, vac in enumerate(acum):
                        xc = ml + pw * (i + 0.5) / n
                        y  = sca(vac)
                        pts.append(f"{xc:.1f},{y:.1f}")
                    parts.append(f'<polyline fill="none" stroke="#1F6F40" stroke-width="2" points="{" ".join(pts)}"/>')
                    for i, vac in enumerate(acum):
                        xc = ml + pw * (i + 0.5) / n
                        y  = sca(vac)
                        parts.append(f'<circle cx="{xc:.1f}" cy="{y:.1f}" r="2.6" fill="#1F6F40"/>')
                        # Etiqueta del valor acumulado sobre el punto
                        parts.append(
                            f'<text x="{xc:.1f}" y="{y-4:.1f}" text-anchor="middle" '
                            f'font-size="7.5" font-family="Inter,sans-serif" '
                            f'font-weight="600" fill="#1F6F40">{_fmt_compact(vac)}</text>'
                        )
                    # Eje Y compacto (max barra y max acum)
                    parts.append(f'<text x="{ml-3}" y="{mt+8}" text-anchor="end" font-size="8.5" fill="#999">{_fmt_compact(y_max_a)}</text>')
                    parts.append(f'<text x="{ml-3}" y="{zero+3}" text-anchor="end" font-size="8.5" fill="#999">0</text>')
                    parts.append('</svg>')
                    return ''.join(parts)

                def _build_popover_html(label, key, snap, signo, v, ejec, pct_real):
                    serie  = _serie_anual_for(key, snap)
                    svg    = _build_minigraph_svg(serie, signo)
                    return (
                        f'<div class="pyg-popover">'
                        f'  <div class="pop-title">{label}</div>'
                        f'  {svg}'
                        f'  <div class="pop-legend"><span class="leg-bar">■ Anual</span>  ·  '
                        f'<span class="leg-line">── Acumulado</span></div>'
                        f'  <div class="pop-foot">Ejecutado al {_hoy_pyg_label}: '
                        f'<b>{_fmt_pyg_num(ejec)}</b> · {pct_real:.1f}% del total</div>'
                        f'</div>'
                    )

                def _celda_num_html(v, signo, key, snap, base_cls, label, col_name=None):
                    """Genera el <td>: barra de avance (si toggle activo) + popover con mini-gráfico."""
                    txt = _fmt_pyg_num(v)
                    if v == 0:
                        return f'<td class="pyg-num {base_cls}">{txt}</td>'
                    ejec     = _val_for_hoy(key, snap) * signo
                    pct_real = (ejec / v * 100.0) if v != 0 else 0.0
                    pct_bar  = max(0.0, min(100.0, pct_real))
                    pop_html = _build_popover_html(label, key, snap, signo, v, ejec, pct_real)
                    classes  = f"pyg-num {base_cls} has-popover" + (" has-progress" if mostrar_avance_pyg else "")
                    if mostrar_avance_pyg:
                        return (
                            f'<td class="{classes}">'
                            f'  <span class="pyg-bar" style="width: calc({pct_bar:.2f}% - 10px);"></span>'
                            f'  <span class="pyg-bar-val">{txt}</span>'
                            f'  {pop_html}'
                            f'</td>'
                        )
                    return f'<td class="{classes}"><span class="pyg-bar-val">{txt}</span>{pop_html}</td>'

                rows_html = []
                for key, label, tipo, signo in pyg_struct:
                    # Valor para la columna consolidado
                    val_consol = _val_for(key, None) * signo
                    pct = (val_consol / ventas_consol * 100) if ventas_consol != 0 else 0.0

                    # Label con porcentaje (excepto encabezados puros como Ventas/Bolsa)
                    if tipo in ("header",):
                        label_html = f"<strong>{label}</strong>"
                    elif tipo in ("subtotal", "result"):
                        label_html = f"<strong>{label}: {pct:.2f}%</strong>"
                    elif tipo == "italic":
                        label_html = f"<em>{label}: {pct:.2f}%</em>"
                    elif tipo == "subitem":
                        label_html = f"{label}: {pct:.2f}%"
                    elif tipo == "negative":
                        label_html = f"{label}: {abs(pct):.2f}%"
                    else:
                        label_html = f"{label}: {pct:.2f}%"

                    row_class_map = {
                        "header": "pyg-header",
                        "subtotal": "pyg-subtotal",
                        "result": "pyg-result",
                        "italic": "pyg-italic",
                        "subitem": "pyg-subitem",
                        "negative": "pyg-negative",
                    }
                    row_cls = row_class_map.get(tipo, "")

                    cells = [f'<td class="pyg-label">{label_html}</td>']
                    for i, (snap, _proj) in enumerate(col_defs):
                        v = _val_for(key, snap) * signo
                        extra = "pyg-consolidado" if i == 0 else ""
                        cells.append(_celda_num_html(v, signo, key, snap, extra, label))
                    rows_html.append(f'<tr class="{row_cls}">{"".join(cells)}</tr>')

                header_cells = ['<th class="pyg-label-col">P&G Consolidado</th>']
                for i, (_snap, proj) in enumerate(col_defs):
                    header_cells.append(f"<th>{proj}</th>")

                # Layout compacto cuando hay pocas columnas (≤3 = Consol + hasta 2 proyectos)
                is_compact_pyg = len(col_defs) <= 3
                table_cls = "pyg-table" + (" pyg-table-compact" if is_compact_pyg else "")

                table_html = (
                    f'<div class="pyg-wrapper"><table class="{table_cls}">'
                    f"<thead><tr>{''.join(header_cells)}</tr></thead>"
                    f"<tbody>{''.join(rows_html)}</tbody>"
                    "</table></div>"
                )

                # ── KPIs resumen (alineados con la pestaña Factibilidad de Reporte Proyecto) ──
                # Convención: Total Costos = 9.0 − 6.0 (Financieros fuera del UO),
                # para coincidir con la tabla P&G y con la TIR Operativa.
                costos_total_pyg = _pyg_val("9.0") - _pyg_val("6.0")
                fco_total_pyg   = _pyg_val("10.0")
                margen_pyg      = (fco_total_pyg / ventas_consol * 100) if ventas_consol != 0 else 0.0
                utilidad_pyg    = _val_for("__calc:utilidad", None)
                utilidad_pct    = (utilidad_pyg / ventas_consol * 100) if ventas_consol != 0 else 0.0

                # TIR Operativa (FCO sin financieros). Se reutiliza la `tir_op`
                # calculada en la sección de indicadores superiores.
                tir_op_str = fmt_tir(tir_op)

                # TIR Inversionista — usar `tir_inv_kpi` que ya respeta el
                # toggle de honorarios y la vista activa.
                tir_inv_str_pyg = fmt_tir(tir_inv_kpi)

                # ── Equity Requerido (IC / Socio) ──
                # IC    = Σ Aportes IC    (13.2)
                # Socio = Σ Aportes Socio (14.2)
                _, aportes_socio_raw_pyg = get_valores(snapshots, "14.2")
                equity_ic_pyg    = abs(sum(aportes_raw))
                equity_socio_pyg = abs(sum(aportes_socio_raw_pyg))

                # ── Honorarios (IC / Socio) = suma de los 4 tipos ──
                # IC:    5.22 Construcción · 5.42 Comercialización · 5.62 Gerencia · 5.82 Estructuración
                # Socio: 5.24 Construcción · 5.44 Comercialización · 5.64 Gerencia · 5.84 Estructuración
                _HON_IC_IDX    = ["5.22", "5.42", "5.62", "5.82"]
                _HON_SOCIO_IDX = ["5.24", "5.44", "5.64", "5.84"]
                hon_ic_pyg    = abs(sum(sum(get_valores(snapshots, _ix)[1]) for _ix in _HON_IC_IDX))
                hon_socio_pyg = abs(sum(sum(get_valores(snapshots, _ix)[1]) for _ix in _HON_SOCIO_IDX))

                # Bloque de tarjetas KPI (mismo orden que Reporte Proyecto)
                kpi_cards_html_pyg = f"""
                  <div class="kpi-box"><div class="kpi-label">Ingresos Totales</div>
                    <div class="kpi-value">{fmt_cop(ventas_consol)}</div>
                  </div>
                  <div class="kpi-box"><div class="kpi-label">Total Costos</div>
                    <div class="kpi-value">{fmt_cop(costos_total_pyg)}</div>
                    <div class="kpi-sub">9.0 − 6.0 (excluye Financieros)</div>
                  </div>
                  <div class="kpi-box"><div class="kpi-label">Utilidad</div>
                    <div class="kpi-value">{fmt_cop(utilidad_pyg)}</div>
                    <div class="kpi-sub">{utilidad_pct:.1f}% s/ ventas</div>
                  </div>
                  <div class="kpi-box"><div class="kpi-label">Margen Operativo</div>
                    <div class="kpi-value">{margen_pyg:.1f}%</div>
                    <div class="kpi-sub">FCO / Ingresos</div>
                  </div>
                  <div class="kpi-box"><div class="kpi-label">TIR Operativa</div>
                    <div class="kpi-value">{tir_op_str}</div>
                    <div class="kpi-sub">Anual efectiva · sin financieros</div>
                  </div>
                  <div class="kpi-box"><div class="kpi-label">TIR Inversionista{lbl_kpi_sfx}</div>
                    <div class="kpi-value">{tir_inv_str_pyg}</div>
                    <div class="kpi-sub">XIRR sobre aportes y reintegros IC</div>
                  </div>
                  <div class="kpi-box"><div class="kpi-label">Equity Requerido IC</div>
                    <div class="kpi-value">{fmt_cop(equity_ic_pyg)}</div>
                    <div class="kpi-sub">Σ 13.2 Aportes IC</div>
                  </div>
                  <div class="kpi-box"><div class="kpi-label">Equity Requerido Socio</div>
                    <div class="kpi-value">{fmt_cop(equity_socio_pyg)}</div>
                    <div class="kpi-sub">Σ 14.2 Aportes Socio</div>
                  </div>
                  <div class="kpi-box"><div class="kpi-label">Honorarios IC</div>
                    <div class="kpi-value">{fmt_cop(hon_ic_pyg)}</div>
                    <div class="kpi-sub">5.22 + 5.42 + 5.62 + 5.82</div>
                  </div>
                  <div class="kpi-box"><div class="kpi-label">Honorarios Socio</div>
                    <div class="kpi-value">{fmt_cop(hon_socio_pyg)}</div>
                    <div class="kpi-sub">5.24 + 5.44 + 5.64 + 5.84</div>
                  </div>
                """

                if is_compact_pyg:
                    pyg_l, pyg_r = st.columns([6, 6])
                    with pyg_l:
                        st.markdown(table_html, unsafe_allow_html=True)
                    with pyg_r:
                        st.markdown(
                            f'<div class="pyg-kpi-stack">{kpi_cards_html_pyg}</div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(table_html, unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="pyg-kpi-grid">{kpi_cards_html_pyg}</div>',
                        unsafe_allow_html=True,
                    )

                # ── 14c. INDICADORES OPERATIVOS Y COMERCIALES ──
                # Indicadores adicionales que complementan la lectura del P&G:
                # precio, costos por m², apalancamiento y ciclo comercial.
                st.markdown("##### 📏 Indicadores Operativos y Comerciales")
                try:
                    inds_inv = compute_indicadores_avanzados(snapshots, builder)
                except Exception as _ex_inv_inds:
                    inds_inv = [("Indicadores Avanzados", "Error", str(_ex_inv_inds))]

                # Render compacto en 3 columnas (consistente con el estilo de KPI boxes)
                _cols_per_row_inv = 3
                for _i_inv in range(0, len(inds_inv), _cols_per_row_inv):
                    _cols_inv = st.columns(_cols_per_row_inv)
                    for _j_inv, _col_inv in enumerate(_cols_inv):
                        _idx_inv = _i_inv + _j_inv
                        if _idx_inv < len(inds_inv):
                            _nom, _val, _src = inds_inv[_idx_inv]
                            with _col_inv:
                                st.markdown(f"""
                                <div class="kpi-box">
                                  <div class="kpi-label">{_nom}</div>
                                  <div class="kpi-value" style="font-size:1.25rem; line-height:1.3;">{_val}</div>
                                  <div class="kpi-sub">Fuente: {_src}</div>
                                </div>""", unsafe_allow_html=True)

                # ── 15. SIMULADOR INVERSIONISTA (WATERFALL) ──
                st.divider()
                st.subheader("🔮 Simulador Inversionista Externo")
                st.markdown(
                    "Simula el comportamiento de un inversionista externo que financia una parte del capital bajo una estructura de cascada (waterfall) "
                    "y el resultado de apalancamiento neto para IC."
                )

                # Opción con/sin honorarios
                sim_con_honorarios = st.toggle(
                    "💼 Incluir Estructura con Honorarios",
                    value=True,
                    key="sim_con_honorarios",
                    help="Si se activa, el modelo incluirá el cobro de honorarios y los tramos relacionados. De lo contrario, solo modelará capital (Equity) y reintegros."
                )

                # Entradas en 3 columnas
                col_p1, col_p2, col_p3 = st.columns(3)
                with col_p1:
                    p_part = st.number_input(
                        "Participación Inversionista (%)",
                        min_value=0.0,
                        max_value=100.0,
                        value=50.0,
                        step=5.0,
                        key="sim_p_part",
                        help="Porcentaje de la inversión de capital (Aportes) que será financiado por el inversionista externo."
                    ) / 100.0

                    if sim_con_honorarios:
                        h2_hon = st.number_input(
                            "Honorarios cedidos en Repago (Tramo 2) (%)",
                            min_value=0.0,
                            max_value=100.0,
                            value=20.0,
                            step=5.0,
                            key="sim_h2_hon",
                            help="Porcentaje de honorarios que se le cederán al inversionista externo hasta lograr el repago de su inversión inicial."
                        ) / 100.0
                    else:
                        h2_hon = 0.0

                with col_p2:
                    r2_reint = st.number_input(
                        "Reintegros cedidos en Repago (Tramo 2) (%)",
                        min_value=0.0,
                        max_value=100.0,
                        value=100.0,
                        step=5.0,
                        key="sim_r2_reint",
                        help="Porcentaje de reintegros de capital que se le cederán al inversionista externo en el Tramo 2 para acelerar su repago."
                    ) / 100.0

                    tir1_obj = st.number_input(
                        "TIR Objetivo 1 (Tramo 3) (% E.A.)",
                        min_value=0.0,
                        max_value=100.0,
                        value=20.0,
                        step=1.0,
                        key="sim_tir1_obj",
                        help="Rentabilidad (TIR) anual efectiva requerida para completar el Tramo 3."
                    ) / 100.0

                with col_p3:
                    r3_reint = st.number_input(
                        "Reintegros cedidos en TIR 1 (Tramo 3) (%)",
                        min_value=0.0,
                        max_value=100.0,
                        value=80.0,
                        step=5.0,
                        key="sim_r3_reint",
                        help="Porcentaje de reintegros de capital que se le destinarán al inversionista externo en el Tramo 3."
                    ) / 100.0

                    tir2_obj = st.number_input(
                        "TIR Objetivo 2 (Tramo 4) (% E.A.)",
                        min_value=0.0,
                        max_value=100.0,
                        value=25.0,
                        step=1.0,
                        key="sim_tir2_obj",
                        help="Rentabilidad (TIR) anual efectiva total requerida al finalizar el Tramo 4."
                    ) / 100.0

                # Lógica del Simulador
                def get_recycled_flow(fechas, aportes, reintegros):
                    n = len(fechas)
                    f_net = [a + r for a, r in zip(aportes, reintegros)]
                    cum_f = np.cumsum(f_net)
                    future_min = np.zeros(n)
                    current_min = float('inf')
                    for i in range(n-1, -1, -1):
                        current_min = min(current_min, cum_f[i])
                        future_min[i] = current_min
                    
                    rec_cum_f = np.minimum(0.0, future_min)
                    f_rec = np.zeros(n)
                    f_rec[0] = rec_cum_f[0]
                    for i in range(1, n):
                        f_rec[i] = rec_cum_f[i] - rec_cum_f[i-1]
                        
                    aportes_rec = [v if v < 0.0 else 0.0 for v in f_rec]
                    reintegros_rec = [v if v > 0.0 else 0.0 for v in f_rec]
                    return aportes_rec, reintegros_rec

                def get_npv_local(values, dates, rate):
                    if len(values) == 0:
                        return 0.0
                    d0 = dates[0]
                    npv = 0.0
                    for v, d in zip(values, dates):
                        yf = (d - d0).days / 365.0
                        npv += v / ((1.0 + rate) ** yf)
                    return npv

                # A. Reciclar los aportes y reintegros
                aportes_rec, reintegros_rec = get_recycled_flow(fechas_labels, aportes, reintegros)

                # B. Correr el waterfall periodo a periodo
                n_periods = len(fechas_labels)
                dates_parsed = [_parse_date(d) for d in fechas_labels]

                # ── FIX 1: flujos previos a la fecha actual quedan a cargo de IC ──
                # El inversionista externo sólo aporta a partir del mes actual.
                # La inversión TOTAL del inversionista sigue calculándose sobre el
                # total del proyecto (p_part * suma de aportes reciclados); para
                # efectos del flujo, los aportes anteriores al mes actual se
                # concentran en el mes actual.
                _today = date.today()
                _current_month_start = date(_today.year, _today.month, 1)
                current_idx = next(
                    (i for i, d in enumerate(dates_parsed) if d >= _current_month_start),
                    n_periods,
                )
                if current_idx >= n_periods:
                    current_idx = max(0, n_periods - 1)

                # El inversionista hace UN solo desembolso en current_idx por el
                # total de su participación sobre la inversión total del proyecto
                # (peak de capital requerido, calculado sobre aportes reciclados).
                # Cualquier aporte adicional posterior corre por cuenta de IC.
                total_inv_proyecto = sum(aportes_rec)  # negativo
                flujo_t1 = [0.0] * n_periods
                if n_periods > 0:
                    flujo_t1[current_idx] = p_part * total_inv_proyecto

                flujo_t2 = [0.0] * n_periods
                flujo_t3 = [0.0] * n_periods
                # Desglose de T2 entre honorarios y reintegros (para gráfico)
                flujo_t2_h = [0.0] * n_periods
                flujo_t2_r = [0.0] * n_periods

                u_bal = 0.0
                u_bal_list = []
                bal1 = 0.0
                bal1_list = []
                r_avail_t4 = [0.0] * n_periods

                EPS = 1e-9

                for t in range(n_periods):
                    if t == 0:
                        days = 0
                    else:
                        days = (dates_parsed[t] - dates_parsed[t-1]).days

                    # FIX 1 (cont.): antes de la fecha actual el inversionista no
                    # participa del flujo del proyecto. Esos reintegros/honorarios
                    # pertenecen exclusivamente a IC y NO deben entrar al waterfall
                    # del inversionista (en particular, no deben terminar en r_avail_t4).
                    if t < current_idx:
                        u_bal_list.append(u_bal)
                        bal1_list.append(bal1)
                        r_avail_t4[t] = 0.0
                        continue

                    i_t = flujo_t1[t]
                    # Usar reintegros BRUTOS (no reciclados): el inversionista
                    # recibe las distribuciones reales del proyecto. Aportes
                    # futuros del proyecto los cubre IC, no se descuentan de los
                    # reintegros del inversionista.
                    r_pool = reintegros[t]
                    h_pool = honorarios[t] if sim_con_honorarios else 0.0

                    # --- TRAMO 2: REPAGO ---
                    u_bal_pre = u_bal + abs(i_t)
                    d_t2_alloc = r2_reint * r_pool + h2_hon * h_pool
                    d_t2 = min(d_t2_alloc, u_bal_pre)
                    flujo_t2[t] = d_t2
                    u_bal = u_bal_pre - d_t2
                    u_bal_list.append(u_bal)

                    # Descontar del pool lo realmente usado por T2 (proporcional al alloc)
                    if d_t2_alloc > 0:
                        frac2 = d_t2 / d_t2_alloc
                        r_used_t2 = r2_reint * r_pool * frac2
                        h_used_t2 = h2_hon * h_pool * frac2
                    else:
                        r_used_t2 = 0.0
                        h_used_t2 = 0.0
                    r_pool -= r_used_t2
                    h_pool -= h_used_t2
                    flujo_t2_r[t] = r_used_t2
                    flujo_t2_h[t] = h_used_t2

                    # --- TRAMO 3: TIR 1 ──
                    # FIX 2: si T2 alcanzó su objetivo en este periodo, el remanente
                    # positivo del MISMO periodo cascada a T3 (no se espera al
                    # siguiente periodo). Si T2 aún no termina, T3 no recibe nada.
                    if t == 0:
                        bal1_pre = abs(i_t) - d_t2
                    else:
                        bal1_pre = bal1 * ((1.0 + tir1_obj) ** (days / 365.0)) + abs(i_t) - d_t2

                    if u_bal <= EPS:
                        d_t3_alloc = r3_reint * r_pool
                        d_t3 = min(d_t3_alloc, max(0.0, bal1_pre))
                        flujo_t3[t] = d_t3
                        bal1 = bal1_pre - d_t3
                        if d_t3_alloc > 0:
                            frac3 = d_t3 / d_t3_alloc
                            r_used_t3 = r3_reint * r_pool * frac3
                        else:
                            r_used_t3 = 0.0
                        r_pool -= r_used_t3
                    else:
                        flujo_t3[t] = 0.0
                        bal1 = bal1_pre

                    bal1_list.append(bal1)

                    # --- TRAMO 4: sólo si T3 ya cerró (mismo periodo o anterior) ──
                    # FIX 2 (cont.): el remanente positivo del periodo después de T3
                    # queda disponible para T4 en el MISMO periodo.
                    if u_bal <= EPS and bal1 <= EPS:
                        r_avail_t4[t] = r_pool
                    else:
                        r_avail_t4[t] = 0.0

                # --- TRAMO 4: SOLVER DE TIR 2 ---
                flujo_fixed = [i_t + d2 + d3 for i_t, d2, d3 in zip(flujo_t1, flujo_t2, flujo_t3)]
                npv_fixed = get_npv_local(flujo_fixed, dates_parsed, tir2_obj)
                npv_rem = get_npv_local(r_avail_t4, dates_parsed, tir2_obj)

                r4_solved = 0.0
                warning_msg = None

                if npv_rem > 0.0:
                    r4_solved = -npv_fixed / npv_rem
                    if r4_solved < 0.0:
                        r4_solved = 0.0
                    elif r4_solved > 1.0:
                        warning_msg = f"⚠️ Los reintegros restantes no son suficientes para alcanzar la TIR Objetivo 2 ({tir2_obj*100:.1f}%). Se requeriría ceder el {r4_solved*100:.2f}% (capacidad máxima de 100% excedida)."
                        r4_solved = 1.0
                else:
                    if npv_fixed < 0.0:
                        warning_msg = f"⚠️ No hay reintegros disponibles en el Tramo 4 para alcanzar la TIR Objetivo 2 ({tir2_obj*100:.1f}%)."
                        r4_solved = 1.0
                    else:
                        r4_solved = 0.0

                flujo_t4 = [r4_solved * r for r in r_avail_t4]

                # Flujos Totales
                flujo_ext = [i_t + d2 + d3 + d4 for i_t, d2, d3, d4 in zip(flujo_t1, flujo_t2, flujo_t3, flujo_t4)]
                
                # Flujo inicial IC de base (dependiendo de honorarios)
                if sim_con_honorarios:
                    flujo_inicial_ic = [a + r + h for a, r, h in zip(aportes, reintegros, honorarios)]
                else:
                    flujo_inicial_ic = [a + r for a, r in zip(aportes, reintegros)]

                flujo_ic_neto = [init - ext for init, ext in zip(flujo_inicial_ic, flujo_ext)]

                # ── Desglose por componente (Honorarios vs Reintegros) para el gráfico ──
                # Inversionista externo:
                inv_hon_per   = list(flujo_t2_h)
                inv_rein_per  = [r + t3 + t4 for r, t3, t4 in zip(flujo_t2_r, flujo_t3, flujo_t4)]
                inv_aportes_per = list(flujo_t1)  # ≤ 0

                # IC apalancado: lo que NO se llevó el inversionista
                if sim_con_honorarios:
                    ic_hon_per = [h - hi for h, hi in zip(honorarios, flujo_t2_h)]
                else:
                    ic_hon_per = [0.0] * n_periods
                ic_equity_net_per = [
                    (a + r) - i1 - (rt2 + t3 + t4)
                    for a, r, i1, rt2, t3, t4 in zip(
                        aportes, reintegros, flujo_t1, flujo_t2_r, flujo_t3, flujo_t4
                    )
                ]
                ic_aportes_per = [v if v < 0.0 else 0.0 for v in ic_equity_net_per]
                ic_rein_per    = [v if v > 0.0 else 0.0 for v in ic_equity_net_per]

                # Mostrar el % de Reintegros requerido del Tramo 4
                st.write("")
                col_solve1, col_solve2 = st.columns([1, 2])
                with col_solve1:
                    st.metric(
                        label="🎯 % Reintegros requeridos (Tramo 4)",
                        value=f"{r4_solved * 100:.2f}%",
                        help="Porcentaje de los reintegros restantes necesarios para que el inversionista alcance la TIR Objetivo 2."
                    )
                with col_solve2:
                    if warning_msg:
                        st.warning(warning_msg)
                    else:
                        st.success("✅ Estructura viable. El flujo es suficiente para cubrir los objetivos de rentabilidad.")

                # Perspectiva del Gráfico
                st.write("")
                col_view1, col_view2, col_view3 = st.columns([2, 1, 1.5])
                with col_view1:
                    perspectiva = st.selectbox(
                        "👁️ Seleccionar perspectiva del reporte:",
                        ["Inversionista Externo", "IC Neto (Apalancado)", "Ambos (Comparativo)"],
                        key="sim_perspectiva"
                    )
                with col_view2:
                    sim_agrupacion = st.radio(
                        "Agrupar simulación por:", ["Mes", "Año"],
                        horizontal=True,
                        index=1,
                        key="sim_agrupacion"
                    )
                with col_view3:
                    # Toggle de honorarios SOLO para IC. Aparece siempre que existan
                    # honorarios en el proyecto, independiente de cómo se haya
                    # configurado la simulación para el inversionista externo:
                    #   - Si la simulación se hizo SIN honorarios: el toggle permite
                    #     ENCENDERLOS sólo para IC y ver el efecto en su flujo.
                    #   - Si la simulación se hizo CON honorarios: el toggle permite
                    #     APAGARLOS solo del gráfico de IC para ver el flujo "limpio".
                    # Para el inv. externo los honorarios quedan fijados al configurar
                    # la simulación arriba y NO se pueden alterar en este gráfico.
                    _show_ic_now = perspectiva in ["IC Neto (Apalancado)", "Ambos (Comparativo)"]
                    _proyecto_tiene_hon = any(v > 0 for v in honorarios)
                    if _show_ic_now and _proyecto_tiene_hon:
                        # Default = lo que ya está configurado (no disruptivo)
                        _ic_incl_hon = st.toggle(
                            "💼 Incluir Honorarios IC",
                            value=bool(sim_con_honorarios),
                            key="sim_ic_incl_hon",
                            help=("Solo afecta la perspectiva IC (apalancada). "
                                  "Si la simulación se hizo sin honorarios, este toggle "
                                  "permite ENCENDERLOS solo para IC; si la simulación "
                                  "se hizo con honorarios, permite APAGARLOS solo del "
                                  "gráfico de IC. Para el inversionista externo los "
                                  "honorarios quedan fijos según parámetros de arriba."),
                        )
                    else:
                        _ic_incl_hon = bool(sim_con_honorarios)  # no-op cuando no aplica

                # ── Vista filtrada del flujo IC según el toggle ──
                # ic_hon_efectivos = lo que LE TOCARÍA a IC en honorarios según el
                # estado del toggle, considerando la cesión al inv. externo.
                #   - Si sim_con_honorarios = TRUE: a IC le toca ic_hon_per (lo que
                #     queda tras ceder flujo_t2_h al Ext.).
                #   - Si sim_con_honorarios = FALSE: a IC le tocan TODOS los
                #     honorarios (no se cedió nada al Ext.).
                if sim_con_honorarios:
                    ic_hon_efectivos = list(ic_hon_per)
                else:
                    ic_hon_efectivos = list(honorarios)

                # Aplicar el toggle: si ON, la vista incluye ic_hon_efectivos en el
                # flujo IC; si OFF, los excluye. Comparado con el flujo base:
                #   base flujo_ic_neto YA INCLUYE ic_hon_per cuando sim_con_honorarios=TRUE
                #   base flujo_ic_neto NO INCLUYE nada de hon cuando sim_con_honorarios=FALSE
                if _ic_incl_hon and not sim_con_honorarios:
                    # encender hon que NO estaban en el base → SUMAR
                    flujo_ic_neto_view = [v + h for v, h in zip(flujo_ic_neto, ic_hon_efectivos)]
                    ic_hon_per_view = list(ic_hon_efectivos)
                elif (not _ic_incl_hon) and sim_con_honorarios:
                    # apagar hon que SÍ estaban en el base → RESTAR
                    flujo_ic_neto_view = [v - h for v, h in zip(flujo_ic_neto, ic_hon_per)]
                    ic_hon_per_view = [0.0] * len(ic_hon_per)
                elif _ic_incl_hon and sim_con_honorarios:
                    # ya está incluido en el base → no-op
                    flujo_ic_neto_view = list(flujo_ic_neto)
                    ic_hon_per_view = list(ic_hon_per)
                else:
                    # toggle OFF y base sin hon → no-op
                    flujo_ic_neto_view = list(flujo_ic_neto)
                    ic_hon_per_view = [0.0] * len(flujo_ic_neto)

                # --- KPIs ---
                EPS_KPI = 1.0  # tolerancia en COP para comparar saldos a cero

                def _has_pos_and_neg(flow):
                    return any(v > 0 for v in flow) and any(v < 0 for v in flow)

                def _fmt_tir_or_inf(v, flow):
                    if v is not None:
                        return fmt_tir(v)
                    return "∞" if _has_pos_and_neg(flow) else "N/A"

                # A. Inversionista Externo
                inv_total_ext     = sum(abs(i) for i in flujo_t1)
                tir_total_ext     = xirr(flujo_ext, fechas_labels)
                retorno_total_ext = sum(v for v in flujo_ext if v > 0)

                # Momento de la primera inversión del inversionista (= current_idx)
                first_inv_idx = next((i for i, v in enumerate(flujo_t1) if v < 0), None)

                plazo_repago_txt = "N/A"
                if first_inv_idx is not None:
                    repago_idx = None
                    for idx in range(first_inv_idx, n_periods):
                        if u_bal_list[idx] <= EPS_KPI:
                            repago_idx = idx
                            break
                    if repago_idx is not None:
                        d1 = dates_parsed[first_inv_idx]
                        d2 = dates_parsed[repago_idx]
                        plazo_repago_txt = f"{(d2 - d1).days / 365.25:.1f} años"

                plazo_tir1_txt = "N/A"
                if first_inv_idx is not None:
                    tir1_idx = None
                    for idx in range(first_inv_idx, n_periods):
                        if u_bal_list[idx] <= EPS_KPI and bal1_list[idx] <= EPS_KPI:
                            tir1_idx = idx
                            break
                    if tir1_idx is not None:
                        d1 = dates_parsed[first_inv_idx]
                        d2 = dates_parsed[tir1_idx]
                        plazo_tir1_txt = f"{(d2 - d1).days / 365.25:.1f} años"

                # Plazo a TIR Obj 2: hasta el último periodo con flujo positivo
                # (por construcción del solver, la TIR global converge a tir2_obj
                # en ese instante)
                plazo_tir2_txt = "N/A"
                if first_inv_idx is not None:
                    last_pos_idx = None
                    for idx in range(n_periods - 1, first_inv_idx - 1, -1):
                        if flujo_ext[idx] > EPS_KPI:
                            last_pos_idx = idx
                            break
                    if last_pos_idx is not None and last_pos_idx > first_inv_idx:
                        d1 = dates_parsed[first_inv_idx]
                        d2 = dates_parsed[last_pos_idx]
                        plazo_tir2_txt = f"{(d2 - d1).days / 365.25:.1f} años"

                cobertura_hon = 0.0
                if inv_total_ext > 0.0 and sim_con_honorarios:
                    cobertura_hon = (h2_hon * sum(honorarios) / inv_total_ext) * 100.0

                # B. IC Neto Apalancado
                inv_total_ic     = sum(abs(v) for v in flujo_ic_neto if v < 0)
                tir_total_ic     = xirr(flujo_ic_neto, fechas_labels)
                retorno_total_ic = sum(v for v in flujo_ic_neto if v > 0)

                cum_ic_neto      = np.cumsum(flujo_ic_neto)
                first_ic_inv_idx = next((i for i, v in enumerate(flujo_ic_neto) if v < 0), None)
                plazo_repago_ic  = "N/A"
                if first_ic_inv_idx is not None:
                    payback_ic_idx = None
                    for idx in range(first_ic_inv_idx, n_periods):
                        if cum_ic_neto[idx] >= 0.0:
                            payback_ic_idx = idx
                            break
                    if payback_ic_idx is not None:
                        d1 = dates_parsed[first_ic_inv_idx]
                        d2 = dates_parsed[payback_ic_idx]
                        plazo_repago_ic = f"{(d2 - d1).days / 365.25:.1f} años"

                duracion_ejercicio = f"{(dates_parsed[-1] - dates_parsed[0]).days / 365.25:.1f} años"

                st.write("")
                if perspectiva == "Inversionista Externo":
                    # Fila 1
                    sk1, sk2, sk3 = st.columns(3)
                    with sk1:
                        st.markdown(f"""<div class="kpi-box"><div class="kpi-label">Inversión Total</div><div class="kpi-value">{fmt_cop(inv_total_ext)}</div></div>""", unsafe_allow_html=True)
                    with sk2:
                        st.markdown(f"""<div class="kpi-box"><div class="kpi-label">Plazo de Repago</div><div class="kpi-value">{plazo_repago_txt}</div></div>""", unsafe_allow_html=True)
                    with sk3:
                        st.markdown(f"""<div class="kpi-box"><div class="kpi-label">Retorno Total</div><div class="kpi-value">{fmt_cop(retorno_total_ext)}</div></div>""", unsafe_allow_html=True)
                    # Fila 2
                    sk4, sk5, sk6 = st.columns(3)
                    with sk4:
                        st.markdown(
                            f"""<div class="kpi-box"><div class="kpi-label">TIR Objetivo 1</div>"""
                            f"""<div class="kpi-value" style="font-size:1.4rem; line-height: 1.25;">{fmt_tir(tir1_obj)}"""
                            f"""<br><span style="font-size:0.95rem; color:#681E1E;">Plazo: {plazo_tir1_txt}</span></div></div>""",
                            unsafe_allow_html=True,
                        )
                    with sk5:
                        st.markdown(
                            f"""<div class="kpi-box"><div class="kpi-label">TIR Objetivo 2</div>"""
                            f"""<div class="kpi-value" style="font-size:1.4rem; line-height: 1.25;">{fmt_tir(tir2_obj)}"""
                            f"""<br><span style="font-size:0.95rem; color:#681E1E;">Plazo: {plazo_tir2_txt}</span></div></div>""",
                            unsafe_allow_html=True,
                        )
                    with sk6:
                        lbl_hon_val = f"{cobertura_hon:.1f}%" if sim_con_honorarios else "N/A"
                        st.markdown(f"""<div class="kpi-box"><div class="kpi-label">Cobertura con Honorarios</div><div class="kpi-value">{lbl_hon_val}</div></div>""", unsafe_allow_html=True)
                elif perspectiva == "IC Neto (Apalancado)":
                    sk1, sk2, sk3, sk4 = st.columns(4)
                    with sk1:
                        st.markdown(f"""<div class="kpi-box"><div class="kpi-label">Inversión Restante IC</div><div class="kpi-value">{fmt_cop(inv_total_ic)}</div></div>""", unsafe_allow_html=True)
                    with sk2:
                        st.markdown(f"""<div class="kpi-box"><div class="kpi-label">Plazo Repago IC</div><div class="kpi-value">{plazo_repago_ic}</div></div>""", unsafe_allow_html=True)
                    with sk3:
                        st.markdown(f"""<div class="kpi-box"><div class="kpi-label">TIR Total Apalancada IC</div><div class="kpi-value">{_fmt_tir_or_inf(tir_total_ic, flujo_ic_neto)}</div></div>""", unsafe_allow_html=True)
                    with sk4:
                        st.markdown(f"""<div class="kpi-box"><div class="kpi-label">Retorno Total IC</div><div class="kpi-value">{fmt_cop(retorno_total_ic)}</div></div>""", unsafe_allow_html=True)
                else:
                    st.markdown("### 📊 Comparativa de Indicadores")
                    df_comp = pd.DataFrame({
                        "Indicador": ["Inversión Requerida", "TIR Global del Ejercicio", "Plazo de Repago", "Retorno Total"],
                        "Inversionista Externo": [
                            fmt_cop(inv_total_ext),
                            _fmt_tir_or_inf(tir_total_ext, flujo_ext),
                            plazo_repago_txt,
                            fmt_cop(retorno_total_ext),
                        ],
                        "IC Neto (Apalancado)": [
                            fmt_cop(inv_total_ic),
                            _fmt_tir_or_inf(tir_total_ic, flujo_ic_neto),
                            plazo_repago_ic,
                            fmt_cop(retorno_total_ic),
                        ],
                    })
                    st.dataframe(df_comp, use_container_width=True, hide_index=True)

                # --- GRÁFICO DE SIMULACIÓN ---
                if sim_agrupacion == "Año":
                    df_sim_chart = pd.DataFrame({
                        "Fecha": dates_parsed,
                        "Aportes_Ext": inv_aportes_per,
                        "Reintegros_Ext": inv_rein_per,
                        "Honorarios_Ext": inv_hon_per,
                        "Aportes_IC": ic_aportes_per,
                        "Reintegros_IC": ic_rein_per,
                        "Honorarios_IC": ic_hon_per_view,
                        "Flujo_Ext": flujo_ext,
                        "Flujo_IC": flujo_ic_neto_view,
                    })
                    df_sim_chart["Año"] = [d.year for d in df_sim_chart["Fecha"]]
                    df_sim_agrup = df_sim_chart.groupby("Año")[
                        ["Aportes_Ext", "Reintegros_Ext", "Honorarios_Ext",
                         "Aportes_IC", "Reintegros_IC", "Honorarios_IC",
                         "Flujo_Ext", "Flujo_IC"]
                    ].sum().reset_index()
                    df_sim_agrup["Acum_Ext"] = df_sim_agrup["Flujo_Ext"].cumsum()
                    df_sim_agrup["Acum_IC"] = df_sim_agrup["Flujo_IC"].cumsum()

                    sim_x = df_sim_agrup["Año"].astype(str).tolist()
                    sim_aportes_ext = df_sim_agrup["Aportes_Ext"].tolist()
                    sim_reintegros_ext = df_sim_agrup["Reintegros_Ext"].tolist()
                    sim_honorarios_ext = df_sim_agrup["Honorarios_Ext"].tolist()
                    sim_aportes_ic = df_sim_agrup["Aportes_IC"].tolist()
                    sim_reintegros_ic = df_sim_agrup["Reintegros_IC"].tolist()
                    sim_honorarios_ic = df_sim_agrup["Honorarios_IC"].tolist()
                    sim_acum_ext = df_sim_agrup["Acum_Ext"].tolist()
                    sim_acum_ic = df_sim_agrup["Acum_IC"].tolist()
                else:
                    sim_x = list(fechas_labels)
                    sim_aportes_ext = list(inv_aportes_per)
                    sim_reintegros_ext = list(inv_rein_per)
                    sim_honorarios_ext = list(inv_hon_per)
                    sim_aportes_ic = list(ic_aportes_per)
                    sim_reintegros_ic = list(ic_rein_per)
                    sim_honorarios_ic = list(ic_hon_per_view)

                    sim_acum_ext = []
                    a_ext = 0.0
                    for f in flujo_ext:
                        a_ext += f
                        sim_acum_ext.append(a_ext)

                    sim_acum_ic = []
                    a_ic = 0.0
                    for f in flujo_ic_neto_view:
                        a_ic += f
                        sim_acum_ic.append(a_ic)

                # ── Colores per-periodo de etiquetas (contraste cuando se superponen) ──
                # Blanco sobre fondos oscuros, negro sobre fondos claros, color
                # original si la etiqueta queda en espacio en blanco.
                _n_sim = len(sim_x)

                # Reintegros Ext: etiqueta "outside" cae en la base de Honorarios Ext
                # cuando hay honorarios > 0 (verde claro) → negro.
                _sim_rein_ext_lbl = []
                for _i in range(_n_sim):
                    _h = sim_honorarios_ext[_i] if sim_con_honorarios else 0
                    _sim_rein_ext_lbl.append("#000000" if _h > 0 else "#2E7D52")

                # Reintegros IC: superposición con Honorarios IC (verde más claro) → negro.
                # Usar _ic_incl_hon (toggle del gráfico) en vez de sim_con_honorarios.
                _sim_rein_ic_lbl = []
                for _i in range(_n_sim):
                    _h = sim_honorarios_ic[_i] if _ic_incl_hon else 0
                    _sim_rein_ic_lbl.append("#000000" if _h > 0 else "#82C4A0")

                # Línea Acum Ext: ¿el marcador cae dentro de alguna barra Ext?
                _sim_line_ext_lbl = []
                for _i in range(_n_sim):
                    _y    = sim_acum_ext[_i]
                    _apo  = sim_aportes_ext[_i] if sim_aportes_ext[_i] < 0 else 0.0
                    _rein = sim_reintegros_ext[_i] if sim_reintegros_ext[_i] > 0 else 0.0
                    _hon  = sim_honorarios_ext[_i] if (sim_con_honorarios and sim_honorarios_ext[_i] > 0) else 0.0
                    _top  = _rein + _hon
                    if _y < 0 and _y > _apo:
                        _sim_line_ext_lbl.append("#FFFFFF")    # aportes oscuro
                    elif 0 < _y <= _rein:
                        _sim_line_ext_lbl.append("#FFFFFF")    # reintegros oscuro
                    elif _rein < _y <= _top:
                        _sim_line_ext_lbl.append("#000000")    # honorarios claro
                    else:
                        _sim_line_ext_lbl.append("#2E7D52")    # sin superposición

                # Línea Acum IC: todas las barras IC son "claras" → negro si dentro.
                _sim_line_ic_lbl = []
                for _i in range(_n_sim):
                    _y    = sim_acum_ic[_i]
                    _apo  = sim_aportes_ic[_i] if sim_aportes_ic[_i] < 0 else 0.0
                    _rein = sim_reintegros_ic[_i] if sim_reintegros_ic[_i] > 0 else 0.0
                    _hon  = sim_honorarios_ic[_i] if (_ic_incl_hon and sim_honorarios_ic[_i] > 0) else 0.0
                    _top  = _rein + _hon
                    if (_y < 0 and _y > _apo) or (0 < _y <= _top):
                        _sim_line_ic_lbl.append("#000000")     # barra IC clara
                    else:
                        _sim_line_ic_lbl.append("#681E1E")     # sin superposición

                fig_sim = go.Figure()
                # Acumuladores para alinear el cero entre los 3 ejes Y
                _bar_vals_sim  = []
                _line_vals_sim = []
                _tir_vals_sim  = []

                show_ext = perspectiva in ["Inversionista Externo", "Ambos (Comparativo)"]
                show_ic  = perspectiva in ["IC Neto (Apalancado)", "Ambos (Comparativo)"]

                # ── Disponibilidad del toggle de curva de TIR ──
                # Sólo se ofrece si la TIR del flujo correspondiente a la
                # perspectiva activa es FINITA (≠ None). Si es infinita para IC
                # (caso típico cuando IC recibe sólo positivos), no se muestra
                # ni la opción ni la curva.
                tir_ext_ok = tir_total_ext is not None
                tir_ic_ok  = tir_total_ic  is not None
                if perspectiva == "Inversionista Externo":
                    tir_toggle_available = tir_ext_ok
                elif perspectiva == "IC Neto (Apalancado)":
                    tir_toggle_available = tir_ic_ok
                else:
                    tir_toggle_available = tir_ext_ok or tir_ic_ok

                tg_col1, tg_col2 = st.columns(2)
                with tg_col1:
                    _popover_sim = getattr(st, "popover", None)
                    _container = _popover_sim("🏷️ Etiquetas") if _popover_sim is not None else st.expander("🏷️ Etiquetas")
                    with _container:
                        lbl_sim_ext_aportes    = st.checkbox("Aportes Ext.",         value=False, key="sim_lbl_ext_ap")
                        lbl_sim_ext_reintegros = st.checkbox("Reintegros Ext.",      value=False, key="sim_lbl_ext_re")
                        lbl_sim_ext_honorarios = st.checkbox("Honorarios Ext.",      value=False, key="sim_lbl_ext_ho")
                        lbl_sim_ext_acumulado  = st.checkbox("Acumulado Ext.",       value=False, key="sim_lbl_ext_ac")
                        lbl_sim_ic_aportes     = st.checkbox("Aportes IC Apal.",     value=False, key="sim_lbl_ic_ap")
                        lbl_sim_ic_reintegros  = st.checkbox("Reintegros IC Apal.",  value=False, key="sim_lbl_ic_re")
                        lbl_sim_ic_honorarios  = st.checkbox("Honorarios IC Apal.",  value=False, key="sim_lbl_ic_ho")
                        lbl_sim_ic_acumulado   = st.checkbox("Acumulado IC Apal.",   value=False, key="sim_lbl_ic_ac")
                        lbl_sim_tir_ext        = st.checkbox("TIR Inversionista",    value=False, key="sim_lbl_tir_ext")
                        lbl_sim_tir_ic         = st.checkbox("TIR IC Apal.",         value=False, key="sim_lbl_tir_ic")
                with tg_col2:
                    if tir_toggle_available:
                        show_tir_curve = st.toggle(
                            "📈 Mostrar curva de TIR",
                            value=False,
                            key="sim_show_tir",
                            help="Agrega un eje secundario derecho con la TIR acumulada. La curva arranca en 0% en el momento en que se recupera el capital y va subiendo a medida que se reciben excedentes."
                        )
                    else:
                        show_tir_curve = False
                        st.caption("TIR no disponible (flujo sin retorno finito).")

                # ── Curvas de TIR acumulada por perspectiva ──
                def _running_tir(flow, start_check):
                    """TIR running periodo a periodo. None antes de start_check."""
                    out = [None] * n_periods
                    s_idx = None
                    for _i in range(n_periods):
                        if start_check(_i):
                            s_idx = _i
                            break
                    if s_idx is None:
                        return out
                    for _t in range(s_idx, n_periods):
                        _r = xirr(flow[: _t + 1], fechas_labels[: _t + 1])
                        if _r is None:
                            _cum = sum(flow[: _t + 1])
                            out[_t] = 0.0 if abs(_cum) < 1.0 else None
                        else:
                            out[_t] = float(_r)
                    return out

                def _agg_tir(running):
                    if sim_agrupacion == "Año":
                        agg = []
                        for _y in df_sim_agrup["Año"].tolist():
                            _last = None
                            for _i in range(n_periods):
                                if dates_parsed[_i].year == _y:
                                    _last = _i
                            agg.append(running[_last] if _last is not None else None)
                        return agg
                    return list(running)

                sim_tir_ext = None
                sim_tir_ic  = None
                if show_tir_curve:
                    if show_ext and tir_ext_ok:
                        running_ext = _running_tir(
                            flujo_ext,
                            lambda i: (i >= current_idx) and (u_bal_list[i] <= EPS),
                        )
                        sim_tir_ext = _agg_tir(running_ext)
                    if show_ic and tir_ic_ok and first_ic_inv_idx is not None:
                        # Recalcular cum sobre la vista filtrada (sin honorarios si OFF)
                        cum_ic_neto_view = np.cumsum(flujo_ic_neto_view)
                        running_ic = _running_tir(
                            list(flujo_ic_neto_view),
                            lambda i: (i >= first_ic_inv_idx) and (cum_ic_neto_view[i] >= 0.0),
                        )
                        sim_tir_ic = _agg_tir(running_ic)
                
                if show_ext:
                    _bar_vals_sim.extend(list(sim_aportes_ext) + list(sim_reintegros_ext))
                    if sim_con_honorarios:
                        _bar_vals_sim.extend(list(sim_honorarios_ext))
                    _line_vals_sim.extend(list(sim_acum_ext))
                    fig_sim.add_trace(go.Bar(
                        x=sim_x,
                        y=sim_aportes_ext,
                        name="Aportes Ext.",
                        marker_color="#7B1F1F",
                        opacity=0.90,
                        offsetgroup="ext",
                        text=[fmt_cop_short(v) for v in sim_aportes_ext] if lbl_sim_ext_aportes else None,
                        textposition="outside",
                        outsidetextfont=dict(size=14, color="#7B1F1F"),
                        insidetextfont=dict(size=14, color="#FFFFFF"),
                        cliponaxis=False,
                    ))
                    fig_sim.add_trace(go.Bar(
                        x=sim_x,
                        y=sim_reintegros_ext,
                        name="Reintegros Ext.",
                        marker_color="#2E7D52",
                        opacity=0.90,
                        offsetgroup="ext",
                        text=[fmt_cop_short(v) for v in sim_reintegros_ext] if lbl_sim_ext_reintegros else None,
                        textposition="outside",
                        outsidetextfont=dict(size=14, color=_sim_rein_ext_lbl),
                        insidetextfont=dict(size=14, color="#FFFFFF"),
                        cliponaxis=False,
                    ))
                    if sim_con_honorarios and any(v > 0 for v in sim_honorarios_ext):
                        fig_sim.add_trace(go.Bar(
                            x=sim_x,
                            y=sim_honorarios_ext,
                            name="Honorarios Ext.",
                            marker_color="#82C4A0",
                            marker_line=dict(color="#2E7D52", width=1),
                            opacity=0.85,
                            offsetgroup="ext",
                            text=[fmt_cop_short(v) for v in sim_honorarios_ext] if lbl_sim_ext_honorarios else None,
                            textposition="outside",
                            outsidetextfont=dict(size=14, color="#1a5c38"),
                            insidetextfont=dict(size=14, color="#1a5c38"),
                            cliponaxis=False,
                        ))
                    fig_sim.add_trace(go.Scatter(
                        x=sim_x,
                        y=sim_acum_ext,
                        name="Acumulado Externo",
                        mode="lines+markers+text" if lbl_sim_ext_acumulado else "lines+markers",
                        line=dict(color="#2E7D52", width=3),
                        marker=dict(size=6),
                        text=[fmt_cop_short(v) for v in sim_acum_ext] if lbl_sim_ext_acumulado else None,
                        textposition="top center",
                        textfont=dict(size=14, color=_sim_line_ext_lbl),
                        yaxis="y2",
                    ))
                    
                if show_ic:
                    _bar_vals_sim.extend(list(sim_aportes_ic) + list(sim_reintegros_ic))
                    if _ic_incl_hon:
                        _bar_vals_sim.extend(list(sim_honorarios_ic))
                    _line_vals_sim.extend(list(sim_acum_ic))
                    fig_sim.add_trace(go.Bar(
                        x=sim_x,
                        y=sim_aportes_ic,
                        name="Aportes IC Apal.",
                        marker_color="#C08A8A",
                        opacity=0.60,
                        offsetgroup="ic",
                        text=[fmt_cop_short(v) for v in sim_aportes_ic] if lbl_sim_ic_aportes else None,
                        textposition="outside",
                        outsidetextfont=dict(size=14, color="#7B1F1F"),
                        insidetextfont=dict(size=14, color="#FFFFFF"),
                        cliponaxis=False,
                    ))
                    fig_sim.add_trace(go.Bar(
                        x=sim_x,
                        y=sim_reintegros_ic,
                        name="Reintegros IC Apal.",
                        marker_color="#82C4A0",
                        opacity=0.60,
                        offsetgroup="ic",
                        text=[fmt_cop_short(v) for v in sim_reintegros_ic] if lbl_sim_ic_reintegros else None,
                        textposition="outside",
                        outsidetextfont=dict(size=14, color=_sim_rein_ic_lbl),
                        insidetextfont=dict(size=14, color="#1a5c38"),
                        cliponaxis=False,
                    ))
                    # Dibujar barra de honorarios IC solo si el toggle está ON
                    # y hay valores > 0 (independiente de sim_con_honorarios).
                    if _ic_incl_hon and any(v > 0 for v in sim_honorarios_ic):
                        fig_sim.add_trace(go.Bar(
                            x=sim_x,
                            y=sim_honorarios_ic,
                            name="Honorarios IC Apal.",
                            marker_color="#B5DCC4",
                            marker_line=dict(color="#82C4A0", width=1),
                            opacity=0.70,
                            offsetgroup="ic",
                            text=[fmt_cop_short(v) for v in sim_honorarios_ic] if lbl_sim_ic_honorarios else None,
                            textposition="outside",
                            outsidetextfont=dict(size=14, color="#1a5c38"),
                            insidetextfont=dict(size=14, color="#1a5c38"),
                            cliponaxis=False,
                        ))
                    fig_sim.add_trace(go.Scatter(
                        x=sim_x,
                        y=sim_acum_ic,
                        name="Acumulado IC Apal.",
                        mode="lines+markers+text" if lbl_sim_ic_acumulado else "lines+markers",
                        line=dict(color="#681E1E", width=3, dash="dash"),
                        marker=dict(size=6),
                        text=[fmt_cop_short(v) for v in sim_acum_ic] if lbl_sim_ic_acumulado else None,
                        textposition="top center",
                        textfont=dict(size=14, color=_sim_line_ic_lbl),
                        yaxis="y2",
                    ))
                    
                # ── Trazas de TIR acumulada (eje y3 — escala porcentual) ──
                tir_trace_added = False
                if show_tir_curve and sim_tir_ext is not None:
                    _tir_vals_sim.extend([v for v in sim_tir_ext if v is not None])
                    _tir_vals_sim.append(tir2_obj)
                    fig_sim.add_trace(go.Scatter(
                        x=sim_x,
                        y=sim_tir_ext,
                        name="TIR Inversionista (acum.)",
                        mode="lines+markers+text" if lbl_sim_tir_ext else "lines+markers",
                        line=dict(color="#FF8C00", width=3),
                        marker=dict(size=6, symbol="diamond"),
                        text=[(fmt_tir(v) if v is not None else "") for v in sim_tir_ext] if lbl_sim_tir_ext else None,
                        textposition="top center",
                        textfont=dict(size=12, color="#FF8C00"),
                        yaxis="y3",
                        connectgaps=False,
                    ))
                    # Línea horizontal en TIR Objetivo 2 (sólo aplica para Ext)
                    fig_sim.add_trace(go.Scatter(
                        x=[sim_x[0], sim_x[-1]] if sim_x else [],
                        y=[tir2_obj, tir2_obj],
                        name=f"TIR Objetivo 2 ({tir2_obj*100:.1f}%)",
                        mode="lines",
                        line=dict(color="#FF8C00", width=1, dash="dot"),
                        yaxis="y3",
                        showlegend=True,
                    ))
                    tir_trace_added = True
                if show_tir_curve and sim_tir_ic is not None:
                    _tir_vals_sim.extend([v for v in sim_tir_ic if v is not None])
                    fig_sim.add_trace(go.Scatter(
                        x=sim_x,
                        y=sim_tir_ic,
                        name="TIR IC Apal. (acum.)",
                        mode="lines+markers+text" if lbl_sim_tir_ic else "lines+markers",
                        line=dict(color="#A03BD1", width=3, dash="dash"),
                        marker=dict(size=6, symbol="square"),
                        text=[(fmt_tir(v) if v is not None else "") for v in sim_tir_ic] if lbl_sim_tir_ic else None,
                        textposition="top center",
                        textfont=dict(size=12, color="#A03BD1"),
                        yaxis="y3",
                        connectgaps=False,
                    ))
                    tir_trace_added = True

                # ── Layout con 3 ejes Y ──
                # y  (izquierda)             → barras (COP)
                # y2 (derecha, posición 1.0) → acumulados (COP)
                # y3 (derecha, posición ~1.0) → TIR acumulada (%), solo si está activa.
                # Los 3 ejes se alinean en el cero (misma fracción del cero
                # vertical en cada uno) para facilitar la lectura.
                _has_tir = bool(show_tir_curve and tir_trace_added)
                _xaxis_kwargs = dict(title="Periodo", tickangle=-45)
                if _has_tir:
                    _xaxis_kwargs["domain"] = [0.0, 0.92]

                # ── Alineación de los 3 ceros ──
                def _aligned_three(bar_vals, line_vals, tir_vals, pad=0.05):
                    bmin = min(bar_vals + [0.0]) if bar_vals else -1.0
                    bmax = max(bar_vals + [0.0]) if bar_vals else 1.0
                    lmin = min(line_vals + [0.0]) if line_vals else -1.0
                    lmax = max(line_vals + [0.0]) if line_vals else 1.0
                    tmin = min(tir_vals + [0.0]) if tir_vals else -0.1
                    tmax = max(tir_vals + [0.0]) if tir_vals else 0.5
                    def frac(y_min, y_max):
                        span = max(y_max - y_min, 1e-9)
                        return -y_min / span
                    f = max(frac(bmin, bmax), frac(lmin, lmax), frac(tmin, tmax))
                    f = min(max(f, 0.0), 0.999)
                    def _fit(y_min, y_max, target_f):
                        if target_f <= 0:
                            return (0.0, max(y_max, 1.0))
                        new_min_A = (-target_f * y_max / (1 - target_f)) if y_max > 0 else y_min
                        new_max_B = (-y_min * (1 - target_f) / target_f) if y_min < 0 else y_max
                        if new_min_A <= y_min:
                            return (new_min_A, y_max)
                        return (y_min, new_max_B)
                    def _pad(rng):
                        s = rng[1] - rng[0]
                        return (rng[0] - pad * s, rng[1] + pad * s)
                    return (_pad(_fit(bmin, bmax, f)),
                            _pad(_fit(lmin, lmax, f)),
                            _pad(_fit(tmin, tmax, f)))

                _bar_rng_sim, _line_rng_sim, _tir_rng_sim = _aligned_three(
                    _bar_vals_sim, _line_vals_sim, _tir_vals_sim
                )

                _layout_kwargs = dict(
                    barmode="relative",
                    height=520,
                    title=dict(
                        text=f"Simulación de Flujo de Caja - Perspectiva: {perspectiva}",
                        font=dict(size=16, color="#681E1E"),
                    ),
                    xaxis=_xaxis_kwargs,
                    yaxis=dict(
                        title="Barras · COP",
                        zeroline=True, zerolinecolor="#681E1E", zerolinewidth=1.5,
                        range=list(_bar_rng_sim),
                    ),
                    yaxis2=dict(
                        title=dict(text="Acumulado · COP", font=dict(color="#681E1E")),
                        overlaying="y",
                        side="right",
                        showgrid=False,
                        zeroline=True,
                        zerolinecolor="#681E1E",
                        zerolinewidth=1,
                        tickfont=dict(color="#681E1E"),
                        range=list(_line_rng_sim),
                    ),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    plot_bgcolor="white",
                    paper_bgcolor="white",
                    font=dict(family="Inter, sans-serif"),
                    margin=dict(l=60, r=70 if not _has_tir else 110, t=90, b=80),
                )
                if _has_tir:
                    _layout_kwargs["yaxis3"] = dict(
                        title=dict(text="TIR acumulada (% E.A.)", font=dict(color="#FF8C00")),
                        overlaying="y",
                        side="right",
                        anchor="free",
                        autoshift=False,
                        position=1.0,
                        tickformat=".0%",
                        showgrid=False,
                        zeroline=False,
                        tickfont=dict(color="#FF8C00"),
                        range=list(_tir_rng_sim),
                    )
                fig_sim.update_layout(**_layout_kwargs)
                fig_sim.add_hline(y=0, line_color="#681E1E", line_dash="dash", line_width=1, opacity=0.5)

                st.plotly_chart(fig_sim, use_container_width=True)

                with st.expander("📋 Ver tabla de datos de la simulación"):
                    sim_dict = {
                        "Periodo": list(fechas_labels),
                        "Aportes Ext. (T1)": flujo_t1,
                        "Repago Ext. (T2)": flujo_t2,
                        "Retorno Ext. (T3)": flujo_t3,
                        "Retorno Ext. (T4)": flujo_t4,
                        "Flujo Total Ext.": flujo_ext,
                        "Flujo IC Apalancado": flujo_ic_neto,
                    }
                    df_sim_data = pd.DataFrame(sim_dict)
                    cols_num_sim = [c for c in df_sim_data.columns if c != "Periodo"]
                    st.dataframe(
                        df_sim_data.style.format({c: "${:,.0f}" for c in cols_num_sim}),
                        use_container_width=True,
                        hide_index=True,
                    )

                # ── 14. TABLA RESUMEN (dinámica según toggle) ──
                st.divider()
                with st.expander("📋 Ver tabla de datos del flujo"):
                    tabla_dict = {
                        "Periodo":       list(fechas_labels),
                        "Aportes IC":    aportes,
                        "Reintegros IC": reintegros,
                    }
                    if incl_hon:
                        tabla_dict["Honorarios IC"] = honorarios
                    tabla_dict["Flujo Periodo"]   = [
                        a + r + (h if incl_hon else 0)
                        for a, r, h in zip(aportes, reintegros, honorarios)
                    ]
                    tabla_dict["Flujo Acumulado"] = flujo_acum_kpi

                    df_flujo = pd.DataFrame(tabla_dict)
                    cols_num = [c for c in df_flujo.columns if c != "Periodo"]
                    st.dataframe(
                        df_flujo.style.format({c: "${:,.0f}" for c in cols_num}),
                        use_container_width=True,
                        hide_index=True,
                    )


            except Exception as e:
                import traceback
                st.error(f"❌ Error al generar el reporte: {e}")
                st.code(traceback.format_exc())


# ═════════════════════════════════════════════
# MÓDULO 4 — FLUJO DE CAJA POR PROYECTO
# ═════════════════════════════════════════════

elif modulo == "📊 Reporte Proyecto":
    st.title("📊 Reporte Proyecto")
    st.markdown("Reporte ejecutivo completo: factibilidad, indicadores, cronograma y flujo de caja detallado.")
    st.divider()

    if not st.session_state.records:
        st.warning("⚠️ Primero carga la Base de Datos en el módulo **📂 Cargar Base**.")
        st.stop()

    def _reset_fc():
        st.session_state.show_flujo_caja_proyecto = False

    resp = st.session_state.upload_response
    c1, c2 = st.columns(2)
    with c1:
        fc_proyectos = st.multiselect(
            "Proyectos",
            resp.proyectos,
            default=resp.proyectos[:1] if resp.proyectos else [],
            key="fc_proyectos",
            on_change=_reset_fc,
            help="Selecciona uno o más proyectos. La fecha de corte mostrada es la común a todos los seleccionados."
        )
    with c2:
        fc_fecha = None
        if fc_proyectos:
            sets_fechas = [set(resp.fechas_datos.get(p, [])) for p in fc_proyectos]
            fechas_comunes = sorted(set.intersection(*sets_fechas), reverse=True) if sets_fechas else []
            if not fechas_comunes:
                st.warning("⚠️ No hay fechas de corte comunes a los proyectos seleccionados.")
            else:
                fc_fecha = st.selectbox(
                    "Fecha de Corte (común)",
                    fechas_comunes,
                    key="fc_fecha",
                    on_change=_reset_fc
                )
        else:
            st.selectbox("Fecha de Corte", [], disabled=True, key="fc_fecha_disabled")

    btn_disabled = (not fc_proyectos) or (not fc_fecha)
    if st.button("📊 Generar Reporte de Flujo de Caja", type="primary", disabled=btn_disabled):
        st.session_state.show_flujo_caja_proyecto = True

    if st.session_state.get("show_flujo_caja_proyecto", False):
        with st.spinner("Reconstruyendo flujo de caja completo…"):
            try:
                # `fc_fecha` puede traer sufijo de versión (-2, -3, etc.)
                fecha_obj, version_obj = parse_fecha_label(fc_fecha)
                # Construir snapshots para cada proyecto seleccionado
                # (cada proyecto puede tener la misma versión sólo si su archivo aporta esa combinación)
                snapshots = [
                    _build_snapshot(p, fecha_obj, version_obj)
                    for p in fc_proyectos
                ]
                # Snapshot de referencia (primero) — usado por helpers legacy
                snapshot = snapshots[0]
                # Unión ordenada de fechas de todos los snapshots
                fechas_union = sorted(set().union(*[set(s.fechas_flujo) for s in snapshots])) if snapshots else []
                # Título compacto del conjunto
                if len(fc_proyectos) == 1:
                    tit_proyectos = fc_proyectos[0]
                elif len(fc_proyectos) <= 3:
                    tit_proyectos = " + ".join(fc_proyectos)
                else:
                    tit_proyectos = f"{len(fc_proyectos)} proyectos"

                # ── Helpers de lectura (por snapshot y agregado entre todos) ──
                def _get_total_snap(snap, indice, part=Participacion.TOTAL):
                    linea = builder.get_linea_exacta(snap, indice, part)
                    if not linea and part == Participacion.TOTAL:
                        linea = builder.get_linea_exacta(snap, indice, Participacion.IC)
                    return linea.total_periodo if linea else 0.0

                def _get_total(indice, part=Participacion.TOTAL):
                    """Total agregado entre todos los snapshots seleccionados."""
                    return sum(_get_total_snap(s, indice, part) for s in snapshots)

                def _get_valores_dict_snap(snap, indice, part=Participacion.TOTAL):
                    linea = builder.get_linea_exacta(snap, indice, part)
                    if not linea and part == Participacion.TOTAL:
                        linea = builder.get_linea_exacta(snap, indice, Participacion.IC)
                    if not linea:
                        return {}
                    return dict(linea.valores)

                def _get_valores_lista(indice, part=Participacion.TOTAL):
                    """Lista por fecha-unión, agregando valores entre snapshots."""
                    agg = {}
                    for s in snapshots:
                        for f, v in _get_valores_dict_snap(s, indice, part).items():
                            agg[f] = agg.get(f, 0.0) + v
                    return [agg.get(f, 0.0) for f in fechas_union]

                def _get_line(indice, part=Participacion.TOTAL):
                    """Compat: línea del primer snapshot (uso interno)."""
                    return builder.get_linea_exacta(snapshot, indice, part)

                # ── Helpers compartidos (formato + XIRR) ──
                def _parse_date_fc(s):
                    if isinstance(s, date):
                        return s
                    return date.fromisoformat(str(s)[:10])

                def fmt_cop_fc(v):
                    if v is None:
                        return "N/A"
                    sign = "-" if v < 0 else ""
                    av = abs(v)
                    if av >= 1_000_000:
                        mills = av / 1_000_000
                        if mills >= 1_000:
                            fmt = f"{mills:,.0f}".replace(",", ".")
                        elif mills >= 100:
                            fmt = f"{mills:,.0f}"
                        else:
                            fmt = f"{mills:,.1f}"
                        return f"{sign}${fmt}M"
                    return f"{sign}${av:,.0f}"

                def fmt_cop_short_fc(v):
                    if v is None:
                        return ""
                    sign = "-" if v < 0 else ""
                    av = abs(v)
                    if av >= 1_000_000:
                        mills = av / 1_000_000
                        if mills >= 1_000:
                            fmt = f"{mills:,.0f}".replace(",", ".")
                        else:
                            fmt = f"{mills:,.0f}"
                        return f"{sign}${fmt}M"
                    return f"{sign}${av:,.0f}"

                def fmt_tir_fc(v):
                    if v is None:
                        return "N/A"
                    return f"{v * 100:.2f}% E.A."

                def xirr_fc(cashflows, dates_str, guess=0.1):
                    pairs = [(cf, _parse_date_fc(d)) for cf, d in zip(cashflows, dates_str) if cf != 0.0]
                    if len(pairs) < 2:
                        return None
                    cfs = [p[0] for p in pairs]
                    dts = [p[1] for p in pairs]
                    if not (any(v > 0 for v in cfs) and any(v < 0 for v in cfs)):
                        return None
                    d0 = dts[0]
                    year_fracs = [(d - d0).days / 365.0 for d in dts]

                    def npv_at(r):
                        total = 0.0
                        for cf, yf in zip(cfs, year_fracs):
                            try:
                                total += cf / ((1.0 + r) ** yf)
                            except (OverflowError, ZeroDivisionError):
                                return float('inf')
                        return total

                    if npv_at(10.0) > 0:
                        return None

                    def dnpv_at(r):
                        total = 0.0
                        for cf, yf in zip(cfs, year_fracs):
                            try:
                                total -= yf * cf / ((1.0 + r) ** (yf + 1.0))
                            except (OverflowError, ZeroDivisionError):
                                return float('inf')
                        return total

                    rate = guess
                    for _ in range(500):
                        f_val  = npv_at(rate)
                        df_val = dnpv_at(rate)
                        if abs(df_val) < 1e-14:
                            break
                        new_rate = rate - f_val / df_val
                        new_rate = max(-0.99, min(new_rate, 10.0))
                        if abs(new_rate - rate) < 1e-9:
                            return new_rate
                        rate = new_rate

                    lo, hi = -0.99, 10.0
                    f_lo = npv_at(lo)
                    for _ in range(200):
                        mid   = (lo + hi) / 2.0
                        f_mid = npv_at(mid)
                        if abs(f_mid) < 1e-6 or (hi - lo) < 1e-9:
                            return mid
                        if f_lo * f_mid < 0:
                            hi = mid
                        else:
                            lo   = mid
                            f_lo = f_mid
                    return None

                # ═══════════════════════════════════
                # TAB LAYOUT
                # ═══════════════════════════════════
                tab_pyg, tab_kpi, tab_lote, tab_crono, tab_flujo, tab_acum = st.tabs([
                    "💰 Factibilidad (P&G)", "📏 Indicadores", "🏞️ Forma de pago Lote",
                    "📅 Cronograma", "📋 Flujo de Caja", "📈 Flujo Acumulado"
                ])

                # ───────────────────────────────────
                # TAB 1: FLUJO DE CAJA NAVEGABLE
                # ───────────────────────────────────
                with tab_flujo:
                    st.subheader(f"Flujo de Caja Detallado — Corte: {fc_fecha}")

                    # Selector de proyecto + participación + agrupación temporal
                    cf1, cf2, cf3 = st.columns([2, 2, 1.4])
                    with cf1:
                        flujo_proy_sel = st.selectbox(
                            "Proyecto a visualizar",
                            [str(s.proyecto) for s in snapshots],
                            key="fc_flujo_proy_sel"
                        )
                    snap_sel = next(s for s in snapshots if str(s.proyecto) == flujo_proy_sel)
                    with cf2:
                        part_sel = st.radio(
                            "Participación",
                            ["TOTAL", "IC", "SOCIO"],
                            horizontal=True,
                            key="fc_part_sel"
                        )
                    with cf3:
                        agrupacion_temp = st.radio(
                            "Agrupar por",
                            ["Mensual", "Anual"],
                            index=1,                # Default = Anual
                            horizontal=True,
                            key="fc_flujo_agrup"
                        )
                    part_map = {"TOTAL": Participacion.TOTAL, "IC": Participacion.IC, "SOCIO": Participacion.SOCIO}
                    part_filtro = part_map[part_sel]

                    # Filtrar líneas por participación seleccionada
                    lineas_filtradas = [l for l in snap_sel.lineas if l.participacion == part_filtro]

                    if not lineas_filtradas:
                        st.info(f"No hay líneas con participación '{part_sel}' en este snapshot.")
                    else:
                        # ── Filtro de líneas a visualizar ──────────────────────
                        # Cada línea se identifica por su índice (string único).
                        # Etiqueta legible para el multiselect.
                        def _label_linea(l):
                            indent = "  " * max(0, l.nivel - 1)
                            return f"{indent}{l.indice}  {l.nombre or ''}".strip()

                        opciones_lineas = {_label_linea(l): l.indice for l in lineas_filtradas}
                        # Por defecto: solo líneas raíz (índices terminados en `.0`)
                        # — 1.0, 2.0, … hasta 16.0. El resto se activa desde el filtro.
                        default_lineas = [
                            lbl for lbl, idx in opciones_lineas.items()
                            if idx.endswith(".0")
                        ]
                        todas_lineas = list(opciones_lineas.keys())

                        with st.expander("🔍 Filtrar líneas a visualizar", expanded=False):
                            f_b1, f_b2, f_b3 = st.columns([1, 1, 1])
                            _flt_key = f"fc_flujo_lineas__{flujo_proy_sel}__{part_sel}"
                            if _flt_key not in st.session_state:
                                st.session_state[_flt_key] = default_lineas
                            with f_b1:
                                if st.button("✅ Todas", key=f"{_flt_key}__all"):
                                    st.session_state[_flt_key] = todas_lineas
                                    st.rerun()
                            with f_b2:
                                if st.button("Solo raíz (`.0`)", key=f"{_flt_key}__root"):
                                    st.session_state[_flt_key] = default_lineas
                                    st.rerun()
                            with f_b3:
                                if st.button("⬜ Ninguna", key=f"{_flt_key}__none"):
                                    st.session_state[_flt_key] = []
                                    st.rerun()

                            seleccion_labels = st.multiselect(
                                "Líneas visibles",
                                options=todas_lineas,
                                default=st.session_state[_flt_key],
                                key=_flt_key,
                                help="Selecciona o quita las líneas que quieras visualizar en la tabla."
                            )

                        indices_seleccionados = {opciones_lineas[lbl] for lbl in seleccion_labels}
                        lineas_visibles = [
                            l for l in lineas_filtradas if l.indice in indices_seleccionados
                        ]

                        if not lineas_visibles:
                            st.warning("No hay líneas seleccionadas. Activa al menos una desde el filtro.")
                        else:
                            # ── Construir columnas temporales según agrupación ──
                            fechas_flujo = list(snap_sel.fechas_flujo)
                            if agrupacion_temp == "Anual":
                                # Agrupar fechas por año → suma de valores
                                def _anio_de(f):
                                    if isinstance(f, date):
                                        return f.year
                                    return int(str(f)[:4])

                                anios_ord = sorted({_anio_de(f) for f in fechas_flujo})
                                cols_periodo = anios_ord

                                def _val_periodo(linea, anio):
                                    return sum(
                                        linea.valores.get(f, 0.0)
                                        for f in fechas_flujo if _anio_de(f) == anio
                                    )
                                col_label = lambda c: str(c)
                            else:
                                cols_periodo = fechas_flujo
                                def _val_periodo(linea, f):
                                    return linea.valores.get(f, 0.0)
                                col_label = lambda c: c

                            # ── Construir el DataFrame ──
                            rows = []
                            for linea in lineas_visibles:
                                indent = "  " * (linea.nivel - 1)
                                nombre_display = f"{indent}{linea.indice}  {linea.nombre}"
                                if linea.es_subtotal:
                                    nombre_display = f"**{nombre_display}**"

                                row = {"Línea": nombre_display}
                                for c in cols_periodo:
                                    row[col_label(c)] = _val_periodo(linea, c)
                                row["TOTAL"] = linea.total_periodo
                                rows.append(row)

                            df_flujo = pd.DataFrame(rows)
                            col_numericas = [c for c in df_flujo.columns if c != "Línea"]
                            st.dataframe(
                                df_flujo.style.format(
                                    {c: "${:,.0f}" for c in col_numericas}
                                ).map(
                                    lambda v: "color: #c0392b" if isinstance(v, (int, float)) and v < 0 else "",
                                    subset=col_numericas
                                ),
                                use_container_width=True,
                                hide_index=True,
                                height=700,
                            )

                            n_periodos = len(cols_periodo)
                            sufijo_period = "años" if agrupacion_temp == "Anual" else "meses"
                            st.caption(
                                f"Líneas visibles: {len(lineas_visibles)} de {len(lineas_filtradas)} · "
                                f"Periodos: {n_periodos} {sufijo_period} · Agrupación: {agrupacion_temp}"
                            )

                # ───────────────────────────────────
                # TAB 5: FLUJO ACUMULADO (LÍNEAS COMPARATIVAS)
                # ───────────────────────────────────
                with tab_acum:
                    st.subheader(f"📈 Flujo Acumulado por Línea — Corte: {fc_fecha}")
                    st.caption(
                        "Visualiza el comportamiento acumulado mes a mes de cada línea del flujo. "
                        "Por defecto se muestran únicamente las líneas raíz (índices terminados en `.0`); "
                        "el resto está disponible para activar con un clic."
                    )

                    # Selector de proyecto y participación
                    ac1, ac2 = st.columns([2, 2])
                    with ac1:
                        acum_proy_sel = st.selectbox(
                            "Proyecto a visualizar",
                            [str(s.proyecto) for s in snapshots],
                            key="fc_acum_proy_sel"
                        )
                    snap_acum = next(s for s in snapshots if str(s.proyecto) == acum_proy_sel)
                    with ac2:
                        acum_part_sel = st.radio(
                            "Participación",
                            ["TOTAL", "IC", "SOCIO"],
                            horizontal=True,
                            key="fc_acum_part_sel"
                        )
                    acum_part_map = {
                        "TOTAL": Participacion.TOTAL,
                        "IC":    Participacion.IC,
                        "SOCIO": Participacion.SOCIO,
                    }
                    acum_part = acum_part_map[acum_part_sel]

                    # Filtrar líneas del snapshot por participación
                    lineas_acum_all = [
                        l for l in snap_acum.lineas if l.participacion == acum_part
                    ]

                    if not lineas_acum_all:
                        st.info(f"No hay líneas con participación '{acum_part_sel}' en este snapshot.")
                    else:
                        # ── Modo de vista inicial (qué líneas arrancan visibles) ──
                        # Las líneas que NO arrancan visibles van con visible="legendonly"
                        # → aparecen apagadas en la leyenda y el usuario las prende con UN clic.
                        # Los botones rápidos recargan el gráfico cambiando este modo.
                        _view_key = f"acum_view_mode__{acum_proy_sel}__{acum_part_sel}"
                        if _view_key not in st.session_state:
                            st.session_state[_view_key] = "root"  # Por defecto: solo *.0

                        bcol1, bcol2, bcol3, bcol4 = st.columns([1.6, 1.3, 1.3, 4])
                        with bcol1:
                            if st.button("✅ Solo líneas raíz (`.0`)", key=f"{_view_key}__btn_root",
                                         help="Muestra inicialmente solo los índices terminados en `.0`. "
                                              "El resto sigue disponible en la leyenda (clic para activar)."):
                                st.session_state[_view_key] = "root"
                                st.rerun()
                        with bcol2:
                            if st.button("🟢 Todas", key=f"{_view_key}__btn_all"):
                                st.session_state[_view_key] = "all"
                                st.rerun()
                        with bcol3:
                            if st.button("⬜ Ninguna", key=f"{_view_key}__btn_none",
                                         help="Apaga todas las líneas. Actívalas desde la leyenda."):
                                st.session_state[_view_key] = "none"
                                st.rerun()
                        with bcol4:
                            mostrar_etiquetas = st.toggle(
                                "🏷️ Etiquetas en líneas",
                                value=False,
                                key=f"{_view_key}__lbl_show",
                                help="Muestra el valor final acumulado al lado de cada serie visible."
                            )

                        st.caption(
                            "💡 **Tip:** la leyenda lateral del gráfico es interactiva — "
                            "haz **clic** en cualquier ítem para encenderlo/apagarlo, o **doble clic** "
                            "para aislar una sola línea. Cuando hay muchas líneas, la leyenda se vuelve scrollable."
                        )

                        view_mode = st.session_state[_view_key]

                        def _initial_visibility(linea_):
                            if view_mode == "all":
                                return True
                            if view_mode == "none":
                                return "legendonly"
                            # "root" → solo las que terminan en .0
                            return True if linea_.indice.endswith(".0") else "legendonly"

                        # ── Clasificación de líneas ──
                        # (a) SALDOS / CUPOS  → se grafican mes a mes (NO acumulado), eje principal $
                        # (b) UNIDADES / m²   → eje secundario (no monetario)
                        # (c) Resto           → acumulado, eje principal $
                        def _es_saldo_o_cupo(l):
                            n_lc = (l.nombre or "").lower()
                            return ("saldo" in n_lc) or ("cupo" in n_lc)

                        def _es_no_monetaria(l):
                            n_lc = (l.nombre or "").lower()
                            if any(k in n_lc for k in ["unidad", "m²", "m2", "metro", "escritur"]):
                                return True
                            cat = getattr(l, "categoria", None)
                            if cat is not None and "soporte" in str(cat).lower():
                                return True
                            return False

                        # ── Construcción del gráfico ──
                        fechas_acum = snap_acum.fechas_flujo
                        fig_acum = go.Figure()

                        # Paleta consistente con el estilo IC
                        palette = [
                            "#681E1E", "#C0392B", "#E67E22", "#F1C40F",
                            "#27AE60", "#16A085", "#2980B9", "#8E44AD",
                            "#7F8C8D", "#34495E", "#D35400", "#1ABC9C",
                            "#9B59B6", "#3498DB", "#E74C3C", "#2ECC71",
                        ]

                        n_visible_inicial = 0
                        hay_no_monetaria = False  # para decidir si mostrar eje y2
                        for i_s, l in enumerate(lineas_acum_all):
                            # Serie de valores en el orden de fechas_flujo
                            vals = [l.valores.get(f, 0.0) for f in fechas_acum]

                            es_saldo = _es_saldo_o_cupo(l)
                            es_no_mon = _es_no_monetaria(l)

                            if es_saldo:
                                # Saldo/Cupo → valor mes a mes (NO acumulado)
                                y_vals = vals
                                modo_serie = "Mensual"
                            else:
                                # Resto → acumulado
                                acum = []
                                ac = 0.0
                                for v in vals:
                                    ac += v
                                    acum.append(ac)
                                y_vals = acum
                                modo_serie = "Acumulado"

                            # Etiqueta de leyenda + sufijo informativo
                            nombre_leg = l.nombre if l.nombre else l.indice
                            sufijo_modo = ""
                            if es_saldo:
                                sufijo_modo = "  〔mensual〕"
                            if es_no_mon:
                                sufijo_modo += "  〔eje 2〕"
                            leg = f"{l.indice} · {nombre_leg}{sufijo_modo}"
                            color = palette[i_s % len(palette)]

                            visibilidad_inicial = _initial_visibility(l)
                            if visibilidad_inicial is True:
                                n_visible_inicial += 1
                                if es_no_mon:
                                    hay_no_monetaria = True

                            # Determinar el formato del hover (monetario vs unidades)
                            if es_no_mon:
                                # No es dinero; formato sin "$", 1 decimal
                                fmt_hover = "%{y:,.1f}"
                                unidad_lbl = "Unidades/m²"
                            else:
                                fmt_hover = "$%{y:,.0f}"
                                unidad_lbl = "COP"

                            hovertemplate = (
                                f"<b>{leg}</b><br>"
                                "Fecha: %{x}<br>"
                                f"{modo_serie}: {fmt_hover} {unidad_lbl}"
                                "<extra></extra>"
                            )

                            # Texto final si etiquetas activas
                            if mostrar_etiquetas and y_vals:
                                if es_no_mon:
                                    last_lbl = f"{y_vals[-1]:,.1f}"
                                elif abs(y_vals[-1]) >= 1_000_000:
                                    last_lbl = f"${y_vals[-1]/1_000_000:,.0f}M"
                                else:
                                    last_lbl = f"${y_vals[-1]:,.0f}"
                                text_arr = [""] * (len(y_vals) - 1) + [last_lbl]
                                textposition = "top right"
                            else:
                                text_arr = None
                                textposition = None

                            trace_kwargs = dict(
                                x=fechas_acum,
                                y=y_vals,
                                mode="lines+markers+text" if text_arr else "lines+markers",
                                name=leg,
                                visible=visibilidad_inicial,
                                line=dict(
                                    color=color,
                                    width=2,
                                    dash="dot" if es_saldo else "solid",  # Saldo/Cupo punteados para distinguir
                                ),
                                marker=dict(size=5),
                                text=text_arr,
                                textposition=textposition,
                                textfont=dict(size=13, color=color),  # +30%
                                hovertemplate=hovertemplate,
                            )
                            # Asignar eje secundario a líneas no monetarias
                            if es_no_mon:
                                trace_kwargs["yaxis"] = "y2"

                            fig_acum.add_trace(go.Scatter(**trace_kwargs))

                        # ── Detectar si hay alguna línea no monetaria asignada (visible o no) ──
                        # para decidir si dibujamos el eje y2 siempre presente.
                        hay_no_mon_total = any(_es_no_monetaria(l) for l in lineas_acum_all)

                        # ── Layout con tipografía aumentada +30% ──
                        layout_kwargs = dict(
                            title=dict(
                                text=f"Flujo Acumulado — {acum_proy_sel} ({acum_part_sel})",
                                font=dict(size=21, color="#681E1E"),
                            ),
                            xaxis=dict(
                                title=dict(text="Periodo", font=dict(size=16)),
                                tickfont=dict(size=16),
                                type="category",
                            ),
                            yaxis=dict(
                                title=dict(text="Valor Acumulado / Saldo Mensual (COP)",
                                           font=dict(size=16)),
                                tickfont=dict(size=16),
                                tickformat=",.0f",
                            ),
                            # closest → al pasar sobre un punto específico de UNA línea,
                            # muestra solo ese punto (no la lista completa del mes).
                            hovermode="closest",
                            hoverlabel=dict(
                                font=dict(size=16, family="Inter, sans-serif"),
                                bgcolor="white",
                                bordercolor="#681E1E",
                            ),
                            plot_bgcolor="white",
                            paper_bgcolor="white",
                            height=650,
                            font=dict(family="Inter, sans-serif", size=14),
                            legend=dict(
                                orientation="v",
                                yanchor="top", y=1,
                                xanchor="left", x=1.02,
                                font=dict(size=14),
                                itemclick="toggle",
                                itemdoubleclick="toggleothers",
                                bgcolor="rgba(255,255,255,0.95)",
                                bordercolor="#E0E0E0",
                                borderwidth=1,
                                entrywidth=320,
                                entrywidthmode="pixels",
                                tracegroupgap=2,
                            ),
                            margin=dict(l=70, r=340, t=70, b=80),
                        )
                        # Eje secundario para líneas en unidades / m² (siempre presente
                        # si existen líneas no monetarias en la lista)
                        if hay_no_mon_total:
                            layout_kwargs["yaxis2"] = dict(
                                title=dict(text="Unidades / m²", font=dict(size=16, color="#27AE60")),
                                tickfont=dict(size=16, color="#27AE60"),
                                overlaying="y",
                                side="right",
                                showgrid=False,
                                tickformat=",.0f",
                                anchor="x",
                                # Apartar el eje secundario del área de leyenda
                                position=1.0,
                            )

                        fig_acum.update_layout(**layout_kwargs)
                        # Línea de cero en el eje principal
                        fig_acum.add_hline(y=0, line_dash="dot", line_color="#999", line_width=1)

                        st.plotly_chart(fig_acum, use_container_width=True, theme=None)

                        # Resumen
                        st.caption(
                            f"Líneas en el gráfico: **{len(lineas_acum_all)}** total · "
                            f"**{n_visible_inicial}** activas inicialmente · "
                            f"Periodos: {len(fechas_acum)} · Participación: {acum_part_sel} · "
                            f"{'Eje secundario disponible para Unidades/m²' if hay_no_mon_total else ''}"
                        )
                        st.caption(
                            "🔁 **Saldos y Cupos** se grafican **mes a mes (no acumulado)**, en línea punteada. "
                            "📐 **Unidades / m² / Escrituraciones** usan el **eje derecho**. "
                            "💲 El resto (ingresos, costos, FCO, etc.) se muestra **acumulado** en el eje izquierdo."
                        )

                # ───────────────────────────────────
                # TAB 2: FACTIBILIDAD (P&G)
                # ───────────────────────────────────
                with tab_pyg:
                    st.subheader(f"💰 Factibilidad (P&G) — {tit_proyectos}")

                    # ── Helpers de lectura (consolidado o por snapshot) ──
                    def _pyg_val(indice, snap=None):
                        if snap is not None:
                            return _get_total_snap(snap, indice)
                        return sum(_get_total_snap(s, indice) for s in snapshots)

                    def _pyg_nombre(indice):
                        for s in snapshots:
                            for linea in s.lineas:
                                if linea.indice == indice and linea.nombre:
                                    return linea.nombre
                        return ""

                    def _pyg_subs(parent_root):
                        found = {}
                        for s in snapshots:
                            for linea in s.lineas:
                                parts = linea.indice.split(".")
                                if len(parts) == 2 and parts[0] == parent_root and parts[1] != "0":
                                    found[linea.indice] = linea.nombre or linea.indice
                        return sorted(found.items(), key=lambda x: [int(p) for p in x[0].split(".") if p.isdigit()])

                    def _pyg_existe(indice):
                        for s in snapshots:
                            for linea in s.lineas:
                                if linea.indice == indice:
                                    return True
                        return False

                    # ── Construir estructura jerárquica del P&G ──
                    pyg_struct = []
                    pyg_struct.append(("1.0", "Ventas", "header", 1))

                    # ── Detectar subtotal redundante dentro de los subs de Lote ──
                    # En algunos modelos el primer sub (ej. 2.1 "Lote Bruto") es la
                    # suma de los siguientes (subconjunto) → es un subtotal duplicado
                    # que conviene ocultar para no confundir.
                    def _es_suma_subset(target, vals, tol=0.01):
                        from itertools import combinations
                        if not vals or abs(target) < 1.0:
                            return False
                        base = max(abs(target), 1.0)
                        for n in range(1, min(len(vals), 6) + 1):
                            for combo in combinations(vals, n):
                                if abs(sum(combo) - target) / base < tol:
                                    return True
                        return False

                    # Mapeo de nombres a presentar: normalizamos etiquetas
                    # no canónicas del flujo para mantener consistencia IC.
                    _NAME_OVERRIDES = {
                        "costos incurridos": "Relacionados Lote",
                    }
                    def _nombre_pyg(nm):
                        key = (nm or "").strip().lower()
                        return _NAME_OVERRIDES.get(key, nm)

                    subs_2 = _pyg_subs("2")
                    if subs_2:
                        if len(subs_2) >= 2:
                            first_val   = _pyg_val(subs_2[0][0])
                            others_vals = [_pyg_val(idx) for idx, _ in subs_2[1:]]
                            if _es_suma_subset(first_val, others_vals):
                                subs_2 = subs_2[1:]
                        for idx, nm in subs_2:
                            pyg_struct.append((idx, _nombre_pyg(nm), "item", 1))
                    else:
                        pyg_struct.append(("2.0", "Lote", "item", 1))

                    pyg_struct.append(("3.0", "Costo Directo", "item", 1))
                    if _pyg_existe("7.0"):
                        pyg_struct.append(("7.0", "-Iva", "negative", -1))
                    pyg_struct.append(("5.0", "Honorarios", "item", 1))

                    pyg_struct.append(("4.0", "Indirectos", "italic", 1))
                    for idx, nm in _pyg_subs("4"):
                        pyg_struct.append((idx, nm, "subitem", 1))

                    # Misma lógica que Reporte Inversionista:
                    # Total Costos = 9.0 - 6.0 (Financieros fuera del UO)
                    pyg_struct.append(("__calc:total_costos", "Total Costos", "subtotal", 1))
                    pyg_struct.append(("__calc:uo", "Utilidad Operativa", "result", 1))
                    pyg_struct.append(("__calc:financieros", "Financieros", "item", 1))

                    _dev_hon_idx_fc = None
                    for try_idx in ("8.0", "5.9", "5.10"):
                        if _pyg_existe(try_idx):
                            nm = _pyg_nombre(try_idx) or "Devolución Honorarios"
                            pyg_struct.append((try_idx, nm, "italic", 1))
                            _dev_hon_idx_fc = try_idx
                            break

                    pyg_struct.append(("__calc:utilidad", "Utilidad", "result", 1))

                    # Capital Requerido por etapa (Σ Aportes IC + Aportes Socio)
                    pyg_struct.append(("__calc:capital_req", "Capital Requerido", "result", 1))

                    # Columnas: Consolidado + una por snapshot
                    col_defs = [(None, "Consolidado")]
                    for s in snapshots:
                        col_defs.append((s, str(s.proyecto)))

                    ventas_consol = _pyg_val("1.0")

                    def _val_for(key, snap):
                        if key == "__calc:total_costos":
                            return _pyg_val("9.0", snap) - _pyg_val("6.0", snap)
                        if key == "__calc:uo":
                            return _pyg_val("1.0", snap) - (_pyg_val("9.0", snap) - _pyg_val("6.0", snap))
                        if key == "__calc:financieros":
                            return abs(_pyg_val("6.0", snap))
                        if key == "__calc:utilidad":
                            uo  = _pyg_val("1.0", snap) - (_pyg_val("9.0", snap) - _pyg_val("6.0", snap))
                            fin = abs(_pyg_val("6.0", snap))
                            dev = _pyg_val(_dev_hon_idx_fc, snap) if _dev_hon_idx_fc else 0.0
                            return uo - fin + dev
                        if key == "__calc:capital_req":
                            # Capital Requerido = Σ Aportes IC (13.2) + Σ Aportes Socio (14.2)
                            return abs(_pyg_val("13.2", snap)) + abs(_pyg_val("14.2", snap))
                        return _pyg_val(key, snap)

                    # ── Render HTML estilo IC ──
                    def _fmt_pyg_num(v):
                        sign = "-" if v < 0 else ""
                        av = abs(v)
                        if av >= 1_000_000:
                            m = av / 1_000_000
                            s_ = f"${m:,.0f}".replace(",", ".")
                        else:
                            s_ = f"${av:,.0f}".replace(",", ".")
                        return f"{sign}{s_}" if v < 0 else s_

                    # ── Toggle "Mostrar avance" ──
                    # Corte: último día del mes anterior (el flujo es mensual).
                    from datetime import date as _date_pyg_p, timedelta as _td_pyg_p
                    _today_real_p     = _date_pyg_p.today()
                    _hoy_pyg_p        = _date_pyg_p(_today_real_p.year, _today_real_p.month, 1) - _td_pyg_p(days=1)
                    _hoy_pyg_p_label  = _hoy_pyg_p.strftime("%d %b %Y")

                    mostrar_avance_pyg_p = st.toggle(
                        f"📊 Mostrar avance al {_hoy_pyg_p_label}",
                        value=False,
                        key="pyg_mostrar_avance_proy",
                        help=(
                            "Pinta una barra detrás de cada valor con el % ejecutado "
                            f"al cierre del mes anterior ({_hoy_pyg_p_label}). "
                            "Pasa el cursor sobre la celda para ver el detalle."
                        ),
                    )

                    def _pyg_val_hoy_p(indice, snap=None):
                        """Suma de la línea sumando solo fechas <= hoy."""
                        src = [snap] if snap is not None else snapshots
                        total = 0.0
                        for s in src:
                            linea = builder.get_linea_exacta(s, indice, Participacion.TOTAL)
                            if not linea:
                                linea = builder.get_linea_exacta(s, indice, Participacion.IC)
                            if not linea:
                                continue
                            for f, v in linea.valores.items():
                                f_d = f if isinstance(f, _date_pyg_p) else _date_pyg_p.fromisoformat(str(f)[:10])
                                if f_d <= _hoy_pyg_p:
                                    total += v
                        return total

                    def _val_for_hoy_p(key, snap):
                        if key == "__calc:total_costos":
                            return _pyg_val_hoy_p("9.0", snap) - _pyg_val_hoy_p("6.0", snap)
                        if key == "__calc:uo":
                            return _pyg_val_hoy_p("1.0", snap) - (_pyg_val_hoy_p("9.0", snap) - _pyg_val_hoy_p("6.0", snap))
                        if key == "__calc:financieros":
                            return abs(_pyg_val_hoy_p("6.0", snap))
                        if key == "__calc:capital_req":
                            # Avance de capital: aportes IC + Socio ejecutados hasta hoy
                            return abs(_pyg_val_hoy_p("13.2", snap)) + abs(_pyg_val_hoy_p("14.2", snap))
                        if key == "__calc:utilidad":
                            # Convención IC: la utilidad se "materializa" cuando los reintegros
                            # superan el capital aportado. Reintegros (13.4 + 14.4) hasta hoy
                            # primero devuelven el capital total, y lo que sobra es utilidad.
                            rein_hoy      = abs(_pyg_val_hoy_p("13.4", snap)) + abs(_pyg_val_hoy_p("14.4", snap))
                            capital_total = abs(_pyg_val("13.2", snap))       + abs(_pyg_val("14.2", snap))
                            return max(0.0, rein_hoy - capital_total)
                        return _pyg_val_hoy_p(key, snap)

                    # ── Helpers para mini-gráfico de hover (barras + acumulado por año) ──
                    def _pyg_serie_anual_p(indice, snap=None):
                        src = [snap] if snap is not None else snapshots
                        por_anio = {}
                        for s in src:
                            linea = builder.get_linea_exacta(s, indice, Participacion.TOTAL)
                            if not linea:
                                linea = builder.get_linea_exacta(s, indice, Participacion.IC)
                            if not linea:
                                continue
                            for f, v in linea.valores.items():
                                f_d = f if isinstance(f, _date_pyg_p) else _date_pyg_p.fromisoformat(str(f)[:10])
                                por_anio[f_d.year] = por_anio.get(f_d.year, 0.0) + v
                        return sorted(por_anio.items())

                    def _serie_anual_for_p(key, snap):
                        def _as_dict(idx):
                            return dict(_pyg_serie_anual_p(idx, snap))
                        if key == "__calc:total_costos":
                            s9, s6 = _as_dict("9.0"), _as_dict("6.0")
                            anios = sorted(set(s9) | set(s6))
                            return [(a, s9.get(a, 0.0) - s6.get(a, 0.0)) for a in anios]
                        if key == "__calc:uo":
                            s1, s9, s6 = _as_dict("1.0"), _as_dict("9.0"), _as_dict("6.0")
                            anios = sorted(set(s1) | set(s9) | set(s6))
                            return [(a, s1.get(a, 0.0) - (s9.get(a, 0.0) - s6.get(a, 0.0))) for a in anios]
                        if key == "__calc:financieros":
                            s6 = _as_dict("6.0")
                            return [(a, abs(v)) for a, v in sorted(s6.items())]
                        if key == "__calc:capital_req":
                            s132, s142 = _as_dict("13.2"), _as_dict("14.2")
                            anios = sorted(set(s132) | set(s142))
                            return [(a, abs(s132.get(a, 0.0)) + abs(s142.get(a, 0.0))) for a in anios]
                        if key == "__calc:utilidad":
                            s1, s9, s6 = _as_dict("1.0"), _as_dict("9.0"), _as_dict("6.0")
                            sdev = _as_dict(_dev_hon_idx_fc) if _dev_hon_idx_fc else {}
                            anios = sorted(set(s1) | set(s9) | set(s6) | set(sdev))
                            return [(a,
                                     s1.get(a, 0.0) - (s9.get(a, 0.0) - s6.get(a, 0.0))
                                     - abs(s6.get(a, 0.0)) + sdev.get(a, 0.0))
                                    for a in anios]
                        return _pyg_serie_anual_p(key, snap)

                    def _fmt_compact_p(v):
                        sign = "-" if v < 0 else ""
                        av = abs(v)
                        if av >= 1_000_000_000: return f"{sign}${av/1_000_000_000:.1f}B"
                        if av >= 1_000_000:     return f"{sign}${av/1_000_000:.0f}M"
                        if av >= 1_000:         return f"{sign}${av/1_000:.0f}K"
                        return f"{sign}${av:.0f}"

                    def _build_minigraph_svg_p(serie_anual, signo=1):
                        W, H = 320, 130
                        _SC = 2.5  # factor de escala visual del popover
                        ml, mr, mt, mb = 36, 14, 14, 26
                        pw, ph = W - ml - mr, H - mt - mb
                        if not serie_anual:
                            return f'<svg width="{W*_SC:.0f}" height="{H*_SC:.0f}"></svg>'
                        anios = [a for a, _ in serie_anual]
                        vals  = [v * signo for _, v in serie_anual]
                        acum, s = [], 0.0
                        for v in vals:
                            s += v; acum.append(s)
                        n = len(anios)
                        bar_w = (pw / n) * 0.62
                        y_min_b, y_max_b = min(0.0, min(vals)), max(0.0, max(vals))
                        y_rg_b  = max(y_max_b - y_min_b, 1.0)
                        y_min_a, y_max_a = min(0.0, min(acum)), max(0.0, max(acum))
                        y_rg_a  = max(y_max_a - y_min_a, 1.0)
                        def scb(v): return mt + ph * (1 - (v - y_min_b) / y_rg_b)
                        def sca(v): return mt + ph * (1 - (v - y_min_a) / y_rg_a)
                        zero = scb(0.0)
                        parts = [f'<svg width="{W*_SC:.0f}" height="{H*_SC:.0f}" '
                                 f'viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">']
                        parts.append(f'<line x1="{ml}" y1="{zero:.1f}" x2="{W-mr}" y2="{zero:.1f}" stroke="#bbb" stroke-width="0.6"/>')
                        for i, (a, v) in enumerate(zip(anios, vals)):
                            xc = ml + pw * (i + 0.5) / n
                            x  = xc - bar_w/2
                            if v >= 0:
                                y_top, hgt = scb(v), max(scb(0.0) - scb(v), 1.0)
                            else:
                                y_top, hgt = scb(0.0), max(scb(v) - scb(0.0), 1.0)
                            color = "#681E1E" if v >= 0 else "#C0392B"
                            parts.append(f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" height="{hgt:.1f}" fill="{color}" opacity="0.80"/>')
                            parts.append(f'<text x="{xc:.1f}" y="{H-9}" text-anchor="middle" font-size="9" font-family="Inter,sans-serif" fill="#555">{a}</text>')
                        pts = []
                        for i, vac in enumerate(acum):
                            xc = ml + pw * (i + 0.5) / n
                            pts.append(f"{xc:.1f},{sca(vac):.1f}")
                        parts.append(f'<polyline fill="none" stroke="#1F6F40" stroke-width="2" points="{" ".join(pts)}"/>')
                        for i, vac in enumerate(acum):
                            xc = ml + pw * (i + 0.5) / n
                            _yc = sca(vac)
                            parts.append(f'<circle cx="{xc:.1f}" cy="{_yc:.1f}" r="2.6" fill="#1F6F40"/>')
                            # Etiqueta del valor acumulado sobre el punto
                            parts.append(
                                f'<text x="{xc:.1f}" y="{_yc-4:.1f}" text-anchor="middle" '
                                f'font-size="7.5" font-family="Inter,sans-serif" '
                                f'font-weight="600" fill="#1F6F40">{_fmt_compact_p(vac)}</text>'
                            )
                        parts.append(f'<text x="{ml-3}" y="{mt+8}" text-anchor="end" font-size="8.5" fill="#999">{_fmt_compact_p(y_max_a)}</text>')
                        parts.append(f'<text x="{ml-3}" y="{zero+3}" text-anchor="end" font-size="8.5" fill="#999">0</text>')
                        parts.append('</svg>')
                        return ''.join(parts)

                    def _build_popover_html_p(label, key, snap, signo, v, ejec, pct_real):
                        serie = _serie_anual_for_p(key, snap)
                        svg   = _build_minigraph_svg_p(serie, signo)
                        return (
                            f'<div class="pyg-popover">'
                            f'  <div class="pop-title">{label}</div>'
                            f'  {svg}'
                            f'  <div class="pop-legend"><span class="leg-bar">■ Anual</span>  ·  '
                            f'<span class="leg-line">── Acumulado</span></div>'
                            f'  <div class="pop-foot">Ejecutado al {_hoy_pyg_p_label}: '
                            f'<b>{_fmt_pyg_num(ejec)}</b> · {pct_real:.1f}% del total</div>'
                            f'</div>'
                        )

                    def _celda_num_html_p(v, signo, key, snap, base_cls, label, col_name=None):
                        """<td>: barra de avance + popover con mini-gráfico."""
                        txt = _fmt_pyg_num(v)
                        if v == 0:
                            return f'<td class="pyg-num {base_cls}">{txt}</td>'
                        ejec     = _val_for_hoy_p(key, snap) * signo
                        pct_real = (ejec / v * 100.0) if v != 0 else 0.0
                        pct_bar  = max(0.0, min(100.0, pct_real))
                        pop_html = _build_popover_html_p(label, key, snap, signo, v, ejec, pct_real)
                        classes  = f"pyg-num {base_cls} has-popover" + (" has-progress" if mostrar_avance_pyg_p else "")
                        if mostrar_avance_pyg_p:
                            return (
                                f'<td class="{classes}">'
                                f'  <span class="pyg-bar" style="width: calc({pct_bar:.2f}% - 10px);"></span>'
                                f'  <span class="pyg-bar-val">{txt}</span>'
                                f'  {pop_html}'
                                f'</td>'
                            )
                        return f'<td class="{classes}"><span class="pyg-bar-val">{txt}</span>{pop_html}</td>'

                    rows_html = []
                    for key, label, tipo, signo in pyg_struct:
                        val_consol = _val_for(key, None) * signo
                        pct = (val_consol / ventas_consol * 100) if ventas_consol != 0 else 0.0

                        if tipo == "header":
                            label_html = f"<strong>{label}</strong>"
                        elif tipo in ("subtotal", "result"):
                            label_html = f"<strong>{label}: {pct:.2f}%</strong>"
                        elif tipo == "italic":
                            label_html = f"<em>{label}: {pct:.2f}%</em>"
                        elif tipo == "subitem":
                            label_html = f"{label}: {pct:.2f}%"
                        elif tipo == "negative":
                            label_html = f"{label}: {abs(pct):.2f}%"
                        else:
                            label_html = f"{label}: {pct:.2f}%"

                        row_class_map = {
                            "header": "pyg-header",
                            "subtotal": "pyg-subtotal",
                            "result": "pyg-result",
                            "italic": "pyg-italic",
                            "subitem": "pyg-subitem",
                            "negative": "pyg-negative",
                        }
                        row_cls = row_class_map.get(tipo, "")

                        cells = [f'<td class="pyg-label">{label_html}</td>']
                        for i, (snap, _proj) in enumerate(col_defs):
                            v = _val_for(key, snap) * signo
                            extra = "pyg-consolidado" if i == 0 else ""
                            cells.append(_celda_num_html_p(v, signo, key, snap, extra, label))
                        rows_html.append(f'<tr class="{row_cls}">{"".join(cells)}</tr>')

                    header_cells = ['<th class="pyg-label-col">P&G Consolidado</th>']
                    for _snap, proj in col_defs:
                        header_cells.append(f"<th>{proj}</th>")

                    # Layout compacto cuando hay pocas columnas (≤3)
                    is_compact_pyg = len(col_defs) <= 3
                    table_cls = "pyg-table" + (" pyg-table-compact" if is_compact_pyg else "")

                    table_html = (
                        f'<div class="pyg-wrapper"><table class="{table_cls}">'
                        f"<thead><tr>{''.join(header_cells)}</tr></thead>"
                        f"<tbody>{''.join(rows_html)}</tbody>"
                        "</table></div>"
                    )

                    # KPIs resumen (consolidado)
                    # Convención: Total Costos = 9.0 - 6.0 (sin Financieros, igual a la
                    # tabla P&G y a la TIR del chart de FCO Operativo).
                    costos_total_pyg = _pyg_val("9.0") - _pyg_val("6.0")
                    fco_total_pyg   = _pyg_val("10.0")
                    financieros_pyg = abs(_pyg_val("6.0"))
                    margen_pyg      = (fco_total_pyg / ventas_consol * 100) if ventas_consol != 0 else 0.0
                    ventas_total    = ventas_consol  # alias
                    utilidad_pyg    = _val_for("__calc:utilidad", None)
                    utilidad_pct    = (utilidad_pyg / ventas_consol * 100) if ventas_consol != 0 else 0.0

                    # ── TIR FCO consolidada (mismo cálculo que el chart) ──
                    # raw_net[t] = Ingresos(1.0) − [Costos(9.0) − Financieros(6.0)]
                    # = Utilidad Operativa mensual del proyecto consolidado.
                    _ing_pyg  = _get_valores_lista("1.0")
                    _c9_pyg   = _get_valores_lista("9.0")
                    _c6_pyg   = _get_valores_lista("6.0")
                    _raw_net_pyg = [
                        _ing_pyg[k] - (_c9_pyg[k] - _c6_pyg[k])
                        for k in range(len(fechas_union))
                    ]
                    tir_fco_pyg = xirr_fc(_raw_net_pyg, fechas_union) if fechas_union else None
                    tir_fco_str = fmt_tir_fc(tir_fco_pyg)

                    # ── Equity Requerido (IC / Socio) ──
                    # IC    = Σ Aportes IC    (13.2)
                    # Socio = Σ Aportes Socio (14.2)
                    equity_ic_fc    = abs(sum(_get_valores_lista("13.2")))
                    equity_socio_fc = abs(sum(_get_valores_lista("14.2")))

                    # ── Honorarios (IC / Socio) = suma de los 4 tipos ──
                    # IC:    5.22 Construcción · 5.42 Comercialización · 5.62 Gerencia · 5.82 Estructuración
                    # Socio: 5.24 Construcción · 5.44 Comercialización · 5.64 Gerencia · 5.84 Estructuración
                    _HON_IC_IDX_FC    = ["5.22", "5.42", "5.62", "5.82"]
                    _HON_SOCIO_IDX_FC = ["5.24", "5.44", "5.64", "5.84"]
                    hon_ic_fc    = abs(sum(sum(_get_valores_lista(_ix)) for _ix in _HON_IC_IDX_FC))
                    hon_socio_fc = abs(sum(sum(_get_valores_lista(_ix)) for _ix in _HON_SOCIO_IDX_FC))

                    # ── TIR Inversionista (mismo cálculo que Reporte Inversionista) ──
                    # Aportes IC (13.2) en signo negativo + Reintegros IC (13.4)
                    # en signo positivo → flujo equity → XIRR.
                    _aportes_inv_pyg    = [-abs(v) for v in _get_valores_lista("13.2")]
                    _reintegros_inv_pyg = [ abs(v) for v in _get_valores_lista("13.4")]
                    _flujo_inv_pyg = [a + r for a, r in zip(_aportes_inv_pyg, _reintegros_inv_pyg)]
                    tir_inv_pyg = xirr_fc(_flujo_inv_pyg, fechas_union) if fechas_union else None
                    tir_inv_str = fmt_tir_fc(tir_inv_pyg)

                    # ── Bloque de KPIs unificado (mismo estilo en compact y wide) ──
                    # Orden: Ingresos · Total Costos · Utilidad · Margen Operativo ·
                    # TIR Operativa · TIR Inversionista · Equity IC/Socio · Honorarios IC/Socio
                    kpi_cards_html = f"""
                      <div class="kpi-box"><div class="kpi-label">Ingresos Totales</div>
                        <div class="kpi-value">{fmt_cop_fc(ventas_total)}</div>
                      </div>
                      <div class="kpi-box"><div class="kpi-label">Total Costos</div>
                        <div class="kpi-value">{fmt_cop_fc(costos_total_pyg)}</div>
                        <div class="kpi-sub">9.0 − 6.0 (excluye Financieros)</div>
                      </div>
                      <div class="kpi-box"><div class="kpi-label">Utilidad</div>
                        <div class="kpi-value">{fmt_cop_fc(utilidad_pyg)}</div>
                        <div class="kpi-sub">{utilidad_pct:.1f}% s/ ventas</div>
                      </div>
                      <div class="kpi-box"><div class="kpi-label">Margen Operativo</div>
                        <div class="kpi-value">{margen_pyg:.1f}%</div>
                        <div class="kpi-sub">FCO / Ingresos</div>
                      </div>
                      <div class="kpi-box"><div class="kpi-label">TIR Operativa</div>
                        <div class="kpi-value">{tir_fco_str}</div>
                        <div class="kpi-sub">Anual efectiva · sin financieros</div>
                      </div>
                      <div class="kpi-box"><div class="kpi-label">TIR Inversionista</div>
                        <div class="kpi-value">{tir_inv_str}</div>
                        <div class="kpi-sub">XIRR sobre aportes y reintegros IC</div>
                      </div>
                      <div class="kpi-box"><div class="kpi-label">Equity Requerido IC</div>
                        <div class="kpi-value">{fmt_cop_fc(equity_ic_fc)}</div>
                        <div class="kpi-sub">Σ 13.2 Aportes IC</div>
                      </div>
                      <div class="kpi-box"><div class="kpi-label">Equity Requerido Socio</div>
                        <div class="kpi-value">{fmt_cop_fc(equity_socio_fc)}</div>
                        <div class="kpi-sub">Σ 14.2 Aportes Socio</div>
                      </div>
                      <div class="kpi-box"><div class="kpi-label">Honorarios IC</div>
                        <div class="kpi-value">{fmt_cop_fc(hon_ic_fc)}</div>
                        <div class="kpi-sub">5.22 + 5.42 + 5.62 + 5.82</div>
                      </div>
                      <div class="kpi-box"><div class="kpi-label">Honorarios Socio</div>
                        <div class="kpi-value">{fmt_cop_fc(hon_socio_fc)}</div>
                        <div class="kpi-sub">5.24 + 5.44 + 5.64 + 5.84</div>
                      </div>
                    """

                    # Lista reutilizable de los KPIs de Factibilidad (mismos valores
                    # ya calculados) para mostrarlos también en la pestaña Indicadores
                    # sin recalcular → consistencia garantizada. Formato (label, valor, fuente).
                    # Orden solicitado (grilla 4 col):
                    #   Ingresos · Total Costos · Utilidad · Margen FCO
                    #   TIR Op · TIR Inv · Equity Req Total · Honorarios Totales
                    #   Equity IC · Honorarios IC · Equity Socio · Honorarios Socio
                    st.session_state["_factib_kpis_proy"] = [
                        ("Ingresos Totales",        fmt_cop_fc(ventas_total),                    "1.0 Ventas"),
                        ("Total Costos",            fmt_cop_fc(costos_total_pyg),                "9.0 − 6.0 (excluye Financieros)"),
                        ("Utilidad",                fmt_cop_fc(utilidad_pyg),                    f"{utilidad_pct:.1f}% s/ ventas"),
                        ("Margen FCO",              f"{margen_pyg:.1f}%",                        "FCO / Ingresos"),
                        ("TIR Operativa",           tir_fco_str,                                 "Anual efectiva · sin financieros"),
                        ("TIR Inversionista",       tir_inv_str,                                 "XIRR aportes/reintegros IC"),
                        ("Equity Requerido Total",  fmt_cop_fc(equity_ic_fc + equity_socio_fc),  "Σ 13.2 + 14.2"),
                        ("Honorarios Totales",      fmt_cop_fc(hon_ic_fc + hon_socio_fc),        "Honorarios IC + Socio"),
                        ("Equity Requerido IC",     fmt_cop_fc(equity_ic_fc),                    "Σ 13.2 Aportes IC"),
                        ("Honorarios IC",           fmt_cop_fc(hon_ic_fc),                       "5.22 + 5.42 + 5.62 + 5.82"),
                        ("Equity Requerido Socio",  fmt_cop_fc(equity_socio_fc),                 "Σ 14.2 Aportes Socio"),
                        ("Honorarios Socio",        fmt_cop_fc(hon_socio_fc),                    "5.24 + 5.44 + 5.64 + 5.84"),
                    ]

                    # ════════════════════════════════════════════════════
                    # DASHBOARD DE INDICADORES POR CATEGORÍA (lado derecho)
                    # ════════════════════════════════════════════════════
                    # Tablas HTML (fuente grande, controlable por CSS) en cuadrícula
                    # 2×2 para que todo entre en una pantalla sin scroll. Los
                    # indicadores que NO provienen del flujo se ingresan a mano en el
                    # popover "✏️ Editar" y se guardan por selección de proyectos.
                    _sig_proy = "|".join(sorted(str(s.proyecto) for s in snapshots))

                    # Indicadores avanzados (reutiliza valores ya formateados)
                    _adv_p = {}
                    try:
                        for _t in compute_indicadores_avanzados(snapshots, builder):
                            _adv_p[_t[0]] = _t[1]
                    except Exception:
                        _adv_p = {}
                    def _advv(n):
                        return _adv_p.get(n, "N/A")

                    import re as _re_pesos
                    def _compact_pesos_str(s):
                        # Convierte montos completos ($11,510,666) a compactos ($11.5M)
                        if not s:
                            return s
                        return _re_pesos.sub(
                            r"\$[\d,]+",
                            lambda m: fmt_cop_fc(int(m.group(0)[1:].replace(",", ""))),
                            s,
                        )

                    _tot_un   = sum(_get_total_snap(s, "17.1") for s in snapshots)
                    _tot_m2v  = sum(_get_total_snap(s, "17.3") for s in snapshots)
                    _tot_lote = sum(_get_total_snap(s, "2.0") for s in snapshots)

                    def _meses_activos_idx(idx):
                        act = set()
                        for s in snapshots:
                            l = builder.get_linea_exacta(s, idx, Participacion.TOTAL)
                            if l:
                                for f, v in l.valores.items():
                                    if v != 0.0:
                                        act.add(str(f)[:10])
                        return len(act)
                    _mes_vtas = _meses_activos_idx("17.1")
                    _mes_obra = _meses_activos_idx("3.22")

                    _f_unid  = f"{_tot_un:,.0f}" if _tot_un else "N/A"
                    _f_apu   = f"{_tot_m2v/_tot_un:,.1f} m²" if (_tot_un and _tot_m2v) else "N/A"
                    _f_vvu   = fmt_cop_fc(ventas_total/_tot_un) if _tot_un else "N/A"
                    _f_vvm   = (fmt_cop_fc(ventas_total/_tot_m2v) + "/m²") if _tot_m2v else "N/A"
                    _f_ritmo = f"{_tot_un/_mes_vtas:,.1f} Un/mes" if (_tot_un and _mes_vtas) else "N/A"
                    _f_durc  = f"{_mes_obra} meses" if _mes_obra else "N/A"
                    _f_incl  = f"{abs(_tot_lote)/ventas_total*100:.1f}%" if ventas_total else "N/A"

                    # ── Campos manuales (valores numéricos guardados por selección) ──
                    _manual_defs = [
                        ("area_lote",       "Área Lote (m²)",                  100.0),
                        ("area_vendible",   "Área Vendible (m²)",              100.0),
                        ("area_construida", "Área Construida (m²)",            100.0),
                        ("vr_m2_lote",      "Vr. m² Lote ($/m²)",              10000.0),
                        ("cd_m2_sin",       "Costo Directo / m² s/inc ($/m²)", 10000.0),
                        ("cd_m2_con",       "Costo Directo / m² c/inc ($/m²)", 10000.0),
                    ]
                    for _mid, _lbl, _step in _manual_defs:
                        _k = f"mi::{_mid}::{_sig_proy}"
                        if _k not in st.session_state:
                            _sv = _get_manual(_sig_proy, _mid)
                            st.session_state[_k] = (_sv if isinstance(_sv, (int, float)) else None)

                    def _mval(mid):
                        return st.session_state.get(f"mi::{mid}::{_sig_proy}")
                    def _fa(mid):   # área
                        v = _mval(mid); return f"{v:,.0f} m²" if v else None
                    def _fmm(mid):  # $/m²
                        v = _mval(mid); return (fmt_cop_fc(v) + "/m²") if v else None

                    _av, _ac = _mval("area_vendible"), _mval("area_construida")
                    _f_efic = f"{_av/_ac*100:.1f}%" if (_av and _ac) else None

                    # (label, valor) — valor None = celda en blanco (manual sin llenar)
                    _cat_arq = [
                        ("Área Lote",           _fa("area_lote")),
                        ("Área Vendible",       _fa("area_vendible")),
                        ("Área Construida",     _fa("area_construida")),
                        ("Eficiencia",          _f_efic),
                        ("Unidades Vendidas",   _f_unid),
                        ("Área Prom. / Unidad", _f_apu),
                    ]
                    _cat_vtas = [
                        ("Vr. Inicial Venta / Unidad", _f_vvu),
                        ("Vr. m² Inicial → Final",     _compact_pesos_str(_advv("Vr. m² Inicial → Final"))),
                        ("Vr. Prom. Venta / m² vend.", _f_vvm),
                        ("Ritmo de Ventas",            _f_ritmo),
                        ("Punto Equilibrio Comercial", _advv("Punto de Equilibrio Comercial")),
                        ("Duración Comercial Total",   _advv("Duración Comercial Total")),
                    ]
                    _cat_costos = [
                        ("Vr. m² Lote",              _fmm("vr_m2_lote")),
                        ("Incidencia Lote",          _f_incl),
                        ("Costo Directo / m² s/inc", _fmm("cd_m2_sin")),
                        ("Costo Directo / m² c/inc", _fmm("cd_m2_con")),
                        ("Duración Construcción",    _f_durc),
                    ]
                    _cat_fin = [
                        ("TIR Operativa",          tir_fco_str),
                        ("TIR Inversionista",      tir_inv_str),
                        ("Equity Requerido IC",    fmt_cop_fc(equity_ic_fc)),
                        ("Equity Requerido Socio", fmt_cop_fc(equity_socio_fc)),
                        ("Honorarios IC",          fmt_cop_fc(hon_ic_fc)),
                        ("Honorarios Socio",       fmt_cop_fc(hon_socio_fc)),
                    ]

                    _cat_css = """<style>
                      .cat-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:10px;margin-top:2px;}
                      .cat-card{border:1px solid #e6dede;border-radius:8px;overflow:hidden;background:#fff;}
                      .cat-ttl{background:#681E1E;color:#fff;font-weight:700;font-size:18px;
                               padding:7px 12px;font-family:'Inter',sans-serif;}
                      .cat-tbl{width:100%;border-collapse:collapse;table-layout:fixed;font-family:'Inter',sans-serif;}
                      .cat-tbl td{padding:7px 11px;border-bottom:1px solid #f1ebeb;font-size:20px;line-height:1.22;}
                      .cat-tbl tr:last-child td{border-bottom:none;}
                      .cat-tbl td.cind{color:#333;width:49%;overflow-wrap:normal;word-break:keep-all;}
                      .cat-tbl td.cval{text-align:right;font-weight:700;color:#222;width:51%;
                                       overflow-wrap:break-word;font-variant-numeric:tabular-nums;}
                      .cat-tbl td.cval.cempty{color:#cbbcbc;font-weight:400;}
                    </style>"""

                    def _cat_card(titulo, filas):
                        rs = ""
                        for _l, _v in filas:
                            if _v in (None, ""):
                                rs += f'<tr><td class="cind">{_l}</td><td class="cval cempty">—</td></tr>'
                            else:
                                rs += f'<tr><td class="cind">{_l}</td><td class="cval">{_v}</td></tr>'
                        return (f'<div class="cat-card"><div class="cat-ttl">{titulo}</div>'
                                f'<table class="cat-tbl"><tbody>{rs}</tbody></table></div>')

                    _grid_html = (
                        _cat_css + '<div class="cat-grid">'
                        + _cat_card("🏛️ Arquitectura", _cat_arq)
                        + _cat_card("🏷️ Ventas", _cat_vtas)
                        + _cat_card("💵 Costos (lote y costo directo)", _cat_costos)
                        + _cat_card("📊 Financiero / Equity", _cat_fin)
                        + '</div>'
                    )

                    def _popover_editar():
                        _pop = getattr(st, "popover", None)
                        _ctx = (st.popover("✏️ Editar valores manuales") if _pop
                                else st.expander("✏️ Editar valores manuales"))
                        with _ctx:
                            _ec = st.columns(2)
                            for _i, (_mid, _lbl, _step) in enumerate(_manual_defs):
                                with _ec[_i % 2]:
                                    st.number_input(_lbl, min_value=0.0, step=_step,
                                                    format="%.0f", key=f"mi::{_mid}::{_sig_proy}")
                            _dirty = False
                            for _mid, _l2, _s2 in _manual_defs:
                                _cur = st.session_state.get(f"mi::{_mid}::{_sig_proy}")
                                if _cur != _get_manual(_sig_proy, _mid):
                                    _set_manual(_sig_proy, _mid, _cur)
                                    _dirty = True
                            if _dirty:
                                _persist_manual_ind()

                    def _render_dashboard():
                        _popover_editar()
                        st.markdown(_grid_html, unsafe_allow_html=True)

                    if is_compact_pyg:
                        # El ancho del P&G crece con el nº de columnas (Consolidado +
                        # proyectos) para que no se desborde sobre el dashboard.
                        pyg_l, pyg_r = st.columns([len(col_defs) + 3, 5])
                        with pyg_l:
                            st.markdown(table_html, unsafe_allow_html=True)
                        with pyg_r:
                            _render_dashboard()
                    else:
                        st.markdown(table_html, unsafe_allow_html=True)
                        _render_dashboard()

                    # ════════════════════════════════════════════
                    # GRÁFICO FLUJO DE CAJA OPERATIVO DEL PROYECTO
                    # ════════════════════════════════════════════
                    st.divider()
                    st.subheader("📊 Flujo de Caja Operativo del Proyecto")
                    st.caption(
                        "Visión global del flujo operativo: ingresos vs. costos. "
                        "**No incluye** aportes de equity, desembolsos de créditos ni otros rubros de fondeo. "
                        f"Consolidado entre **{len(fc_proyectos)}** proyecto(s)."
                    )

                    # ── Controles ──
                    _multi_proj_fc = len(fc_proyectos) > 1
                    if _multi_proj_fc:
                        ctrl_v, ctrl0, ctrl1, ctrl2 = st.columns([1.6, 2, 1.6, 1])
                        with ctrl_v:
                            view_mode_fc = st.radio(
                                "Modo:",
                                ["Consolidado", "Por proyecto"],
                                horizontal=True,
                                key="fc_op_view_mode",
                                help=("Por proyecto: dibuja barras y líneas separadas para "
                                      "cada proyecto filtrado, con color distinto. Solo aplica "
                                      "en vista Simple."),
                            )
                    else:
                        ctrl0, ctrl1, ctrl2 = st.columns([2, 2, 1])
                        view_mode_fc = "Consolidado"
                    is_por_proyecto_fc = (view_mode_fc == "Por proyecto")
                    with ctrl0:
                        chart_mode = st.radio(
                            "Vista:",
                            ["Simple (consolidada)", "Detallada (por concepto)"],
                            horizontal=True,
                            key="fc_op_chart_mode",
                            disabled=is_por_proyecto_fc,
                            help=("La vista detallada solo aplica en modo Consolidado."
                                  if is_por_proyecto_fc else None),
                        )
                        is_detail = (chart_mode.startswith("Detall")) and (not is_por_proyecto_fc)
                    with ctrl1:
                        op_agrup = st.radio(
                            "Agrupar por:", ["Mes", "Año"], horizontal=True,
                            index=1, key="fc_op_agrup"
                        )
                    with ctrl2:
                        _pop = getattr(st, "popover", None)
                        if _pop is not None:
                            with st.popover("🏷️ Etiquetas"):
                                lbl_op_ing  = st.checkbox("Ingresos",  value=False, key="fc_op_lbl_ing")
                                lbl_op_cost = st.checkbox("Costos",    value=False, key="fc_op_lbl_cost")
                                lbl_op_acum = st.checkbox("Acumulado", value=False, key="fc_op_lbl_acum")
                        else:
                            with st.expander("🏷️ Etiquetas"):
                                lbl_op_ing  = st.checkbox("Ingresos",  value=False, key="fc_op_lbl_ing")
                                lbl_op_cost = st.checkbox("Costos",    value=False, key="fc_op_lbl_cost")
                                lbl_op_acum = st.checkbox("Acumulado", value=False, key="fc_op_lbl_acum")

                    # ── Series base por período ──
                    fechas_op = list(fechas_union)

                    # Convención de signo de costos: si la suma de 9.0 viene positiva
                    # (modelo guarda costos sin signo), invertimos; si ya es negativa,
                    # la dejamos. Esto se aplica a TODOS los conceptos de costo, lo que
                    # automáticamente convierte valores negativos dentro del bloque de
                    # costos (devolución IVA, anticipos, garantías) en barras positivas
                    # (flujos hacia arriba).
                    costos_9_chk = _get_valores_lista("9.0")
                    cost_mult = -1.0 if sum(costos_9_chk) > 0 else 1.0

                    # Paleta de colores para cuando se muestra "Por proyecto":
                    # un color distinto por etapa/proyecto seleccionado.
                    PROYECTO_COLORS_FC = [
                        "#681E1E",  # IC rojo oscuro
                        "#1F6F40",  # verde oscuro
                        "#1E5FA8",  # azul oscuro
                        "#B8841F",  # ámbar
                        "#7B287B",  # púrpura
                        "#16A085",  # turquesa
                        "#34495E",  # gris azulado
                        "#C0392B",  # rojo brillante
                    ]

                    # Construcción de series según modo
                    # Cada elemento: (label, color, valores_por_fecha_op, kind,
                    #                 breakdown_text, offsetgroup)
                    # offsetgroup permite que cada proyecto aparezca lado a lado
                    # cuando view_mode = "Por proyecto"; en consolidado es None.
                    series_input = []

                    if is_por_proyecto_fc:
                        # ── MODO POR PROYECTO ──
                        # Por cada snapshot/proyecto: 1 barra ingresos + 1 barra
                        # costos, en el mismo color, con offsetgroup distinto.
                        for idx_p, _snap in enumerate(snapshots):
                            proj_name = str(_snap.proyecto)
                            color_p = PROYECTO_COLORS_FC[idx_p % len(PROYECTO_COLORS_FC)]

                            # Extracción per-snapshot sobre fechas_op
                            def _snap_vals(indice, _sn=_snap):
                                d = _get_valores_dict_snap(_sn, indice, Participacion.TOTAL)
                                return [d.get(f, 0.0) for f in fechas_op]

                            ing_p = _snap_vals("1.0")
                            c9_p = _snap_vals("9.0")
                            c6_p = _snap_vals("6.0")
                            cost_op_raw_p = [c9 - c6 for c9, c6 in zip(c9_p, c6_p)]
                            cost_op_signed_p = [v * cost_mult for v in cost_op_raw_p]

                            series_input.append((
                                f"{proj_name} · Ingresos", color_p, ing_p,
                                "ingreso", "", proj_name,
                            ))
                            series_input.append((
                                f"{proj_name} · Costos Op.", color_p,
                                cost_op_signed_p, "costo", "", proj_name,
                            ))
                    elif is_detail:
                        # ── INGRESOS · SOLO nivel-1 (1.2 + 1.4 + 1.6 + 1.8 = 1.0) ──
                        # Whitelist explícita para que la suma de las barras coincida
                        # con el total de 1.0 del modo simple. Los subniveles (1.21,
                        # 1.22, 1.23) se muestran en el tooltip al pasar el mouse.
                        ingresos_whitelist = [
                            ("1.2", "Ingreso Vendido",     "#0E4D2A"),  # verde oscuro
                            ("1.4", "Ingreso No Vendido",  "#5BA77A"),  # verde medio
                            ("1.6", "Otros Ingresos",      "#82C4A0"),  # verde claro
                            ("1.8", "Devolución IVA Ingr.", "#A9DBC0"), # verde muy claro
                        ]

                        # Buscar subs (1.21, 1.22…) de un padre dado para tooltip
                        def _hijos_directos(parent_idx: str):
                            """
                            Devuelve [(idx, nombre)] de líneas cuyo índice empieza con
                            parent_idx pero NO es parent_idx (ej: padre 1.2 → 1.21, 1.22).
                            """
                            hijos = {}
                            for s in snapshots:
                                for linea in s.lineas:
                                    if (linea.indice.startswith(parent_idx)
                                            and linea.indice != parent_idx
                                            and len(linea.indice) > len(parent_idx)):
                                        # Asegurar que es hijo directo: lo que sigue
                                        # al prefijo NO contiene otro punto
                                        suffix = linea.indice[len(parent_idx):]
                                        if "." not in suffix:
                                            hijos[linea.indice] = linea.nombre or linea.indice
                            return sorted(hijos.items(), key=lambda x: x[0])

                        for idx_p, label_p, color_p in ingresos_whitelist:
                            if not _pyg_existe(idx_p):
                                continue
                            vals = _get_valores_lista(idx_p)
                            if not any(abs(v) > 1e-6 for v in vals):
                                continue
                            # Buscar hijos para tooltip
                            hijos = _hijos_directos(idx_p)
                            breakdown_text = ""
                            if hijos:
                                lineas_bd = [f"{idx_p} {label_p}"]
                                for idx_h, nm_h in hijos:
                                    vals_h = _get_valores_lista(idx_h)
                                    if any(abs(v) > 1e-6 for v in vals_h):
                                        total_h = sum(vals_h)
                                        lineas_bd.append(
                                            f"  • {idx_h} {nm_h}: {fmt_cop_short_fc(total_h)}"
                                        )
                                breakdown_text = "<br>".join(lineas_bd) if len(lineas_bd) > 1 else ""
                            series_input.append((label_p, color_p, vals, "ingreso", breakdown_text))

                        # ── COSTOS (cada concepto top-level con su color) ──
                        # NO incluir 6.0 Financieros: la vista simple usa (9.0 − 6.0),
                        # así que el detallado debe excluir financieros para que los
                        # totales coincidan entre ambas vistas.
                        cost_concepts = [
                            ("Lote",            "2.0", "#7B1F1F"),
                            ("Costo Directo",   "3.0", "#C0392B"),
                            ("Indirectos",      "4.0", "#D87E51"),
                            ("Honorarios",      "5.0", "#B8841F"),
                            # 6.0 Financieros EXCLUIDO (coherencia con vista simple)
                            ("Devolución IVA",  "7.0", "#2980B9"),
                            ("Otros (8.x)",     "8.0", "#7F8C8D"),
                        ]
                        for label_c, idx_c, color_c in cost_concepts:
                            if _pyg_existe(idx_c):
                                vals = _get_valores_lista(idx_c)
                                vals_signed = [v * cost_mult for v in vals]
                                # Solo agregar si hay algún valor distinto de cero
                                if any(abs(v) > 1e-6 for v in vals_signed):
                                    series_input.append((label_c, color_c, vals_signed, "costo", ""))
                    else:
                        # ── MODO SIMPLE: 1 barra ingresos + 1 barra costos agregados ──
                        ingresos_per_s = _get_valores_lista("1.0")
                        costos_9_per_s = _get_valores_lista("9.0")
                        costos_6_per_s = _get_valores_lista("6.0")
                        costos_op_raw  = [c9 - c6 for c9, c6 in zip(costos_9_per_s, costos_6_per_s)]
                        costos_op_signed = [v * cost_mult for v in costos_op_raw]
                        series_input.append(("Ingresos (1.0)", "#2E7D52", ingresos_per_s, "ingreso", ""))
                        series_input.append(("Costos Operativos (9.0 − 6.0)", "#7B1F1F",
                                             costos_op_signed, "costo", ""))

                    # ── Agrupación Mes/Año ──
                    def _agg_series(series_list, agrup, fechas):
                        """Devuelve (x_labels, [(label, color, vals_agg, kind, breakdown, offsetgroup)], net_por_x)."""
                        if agrup == "Año":
                            df_tmp = pd.DataFrame({"Fecha": [_parse_date_fc(d) for d in fechas]})
                            df_tmp["Año"] = [d.year for d in df_tmp["Fecha"]]
                            col_names = []
                            for i, tup in enumerate(series_list):
                                cn = f"__s{i}"
                                df_tmp[cn] = tup[2]
                                col_names.append(cn)
                            df_g = df_tmp.groupby("Año")[col_names].sum().reset_index()
                            x_ = df_g["Año"].astype(str).tolist()
                            out = [(series_list[i][0], series_list[i][1],
                                    df_g[col_names[i]].tolist(),
                                    series_list[i][3],
                                    series_list[i][4] if len(series_list[i]) > 4 else "",
                                    series_list[i][5] if len(series_list[i]) > 5 else None)
                                   for i in range(len(series_list))]
                        else:
                            x_ = list(fechas)
                            out = [(t[0], t[1], t[2], t[3],
                                    t[4] if len(t) > 4 else "",
                                    t[5] if len(t) > 5 else None)
                                   for t in series_list]
                        net = [sum(s[2][k] for s in out) for k in range(len(x_))]
                        return x_, out, net

                    x_op, series_agg, net_per_x = _agg_series(series_input, op_agrup, fechas_op)

                    # Acumulado de net
                    acum_op = []
                    _s_acc = 0.0
                    for v in net_per_x:
                        _s_acc += v
                        acum_op.append(_s_acc)

                    # TIR sobre el flujo neto a granularidad mensual original
                    raw_net = [0.0] * len(fechas_op)
                    for tup in series_input:
                        vals = tup[2]
                        for k in range(len(fechas_op)):
                            raw_net[k] += vals[k]
                    tir_op_g = xirr_fc(raw_net, fechas_op)

                    # ── Construcción de la figura ──
                    fig_op = go.Figure()
                    # Acumuladores para alinear el cero entre y (barras) e y2 (acumulado)
                    _bar_vals_op  = []
                    _line_vals_op = []
                    for tup in series_agg:
                        lbl_s, col_s, vals_s, kind_s = tup[0], tup[1], tup[2], tup[3]
                        breakdown_s = tup[4] if len(tup) > 4 else ""
                        offset_s   = tup[5] if len(tup) > 5 else None
                        # Toggle de etiquetas por tipo
                        show_lbl = lbl_op_ing if kind_s == "ingreso" else lbl_op_cost
                        # Hovertemplate: si hay breakdown, mostrarlo; si no, el default
                        if breakdown_s:
                            hover_tpl = (
                                f"<b>{lbl_s}</b><br>"
                                "Periodo: %{x}<br>"
                                "Total: %{y:,.0f}<br>"
                                "<br><b>Detalle:</b><br>"
                                f"{breakdown_s}"
                                "<extra></extra>"
                            )
                        else:
                            hover_tpl = (
                                f"<b>{lbl_s}</b><br>"
                                "Periodo: %{x}<br>"
                                "Valor: %{y:,.0f}<extra></extra>"
                            )
                        # En modo "Por proyecto", diferenciar ingresos (opacidad alta)
                        # de costos (opacidad media + patrón) usando el mismo color.
                        if is_por_proyecto_fc:
                            opacity_s = 0.92 if kind_s == "ingreso" else 0.55
                        else:
                            opacity_s = 0.92
                        bar_kwargs = dict(
                            x=x_op,
                            y=vals_s,
                            name=lbl_s,
                            marker_color=col_s,
                            opacity=opacity_s,
                            text=[fmt_cop_short_fc(v) for v in vals_s] if show_lbl else None,
                            textposition="outside",
                            outsidetextfont=dict(size=12, color=col_s),
                            insidetextfont=dict(size=12, color="#FFFFFF"),
                            cliponaxis=False,
                            hovertemplate=hover_tpl,
                        )
                        if offset_s is not None:
                            bar_kwargs["offsetgroup"] = offset_s
                        fig_op.add_trace(go.Bar(**bar_kwargs))
                        # Recolectar valores de barras para alinear cero
                        _bar_vals_op.extend(list(vals_s))

                    # Línea acumulado (color simple en detalle; per-periodo en simple)
                    if is_detail:
                        _line_op_colors = ["#681E1E"] * len(x_op)
                    else:
                        # Contraste por periodo cuando solo hay 2 barras
                        ing_v = series_agg[0][2] if len(series_agg) > 0 else [0] * len(x_op)
                        cost_v = series_agg[1][2] if len(series_agg) > 1 else [0] * len(x_op)
                        _line_op_colors = []
                        for _i in range(len(x_op)):
                            _y = acum_op[_i]
                            _c = cost_v[_i] if cost_v[_i] < 0 else 0.0
                            _g = ing_v[_i]  if ing_v[_i]  > 0 else 0.0
                            if _y < 0 and _y > _c:
                                _line_op_colors.append("#FFFFFF")
                            elif 0 < _y <= _g:
                                _line_op_colors.append("#FFFFFF")
                            else:
                                _line_op_colors.append("#681E1E")

                    if is_por_proyecto_fc:
                        # ── Acumulado por proyecto: una línea por cada uno ──
                        from collections import defaultdict as _dd
                        proj_groups = _dd(lambda: {"color": None, "vals_sum": [0.0] * len(x_op)})
                        for tup in series_agg:
                            _proj = tup[5] if len(tup) > 5 else None
                            if not _proj:
                                continue
                            proj_groups[_proj]["color"] = tup[1]
                            for _k in range(len(x_op)):
                                proj_groups[_proj]["vals_sum"][_k] += tup[2][_k]

                        for _proj_name, _info in proj_groups.items():
                            _net_p = _info["vals_sum"]
                            _acum_p = []
                            _acc_p = 0.0
                            for _v in _net_p:
                                _acc_p += _v
                                _acum_p.append(_acc_p)
                            # TIR por proyecto (sobre serie mensual original)
                            _raw_p = [0.0] * len(fechas_op)
                            for _tup in series_input:
                                if (_tup[5] if len(_tup) > 5 else None) == _proj_name:
                                    for _k in range(len(fechas_op)):
                                        _raw_p[_k] += _tup[2][_k]
                            _tir_p = xirr_fc(_raw_p, fechas_op)
                            _line_lbl = f"{_proj_name} · Acum (TIR {fmt_tir_fc(_tir_p)})"
                            fig_op.add_trace(go.Scatter(
                                x=x_op,
                                y=_acum_p,
                                name=_line_lbl,
                                mode="lines+markers+text" if lbl_op_acum else "lines+markers",
                                line=dict(color=_info["color"], width=3),
                                marker=dict(size=6),
                                text=[fmt_cop_short_fc(v) for v in _acum_p] if lbl_op_acum else None,
                                textposition="top center",
                                textfont=dict(size=12, color=_info["color"]),
                                yaxis="y2",
                            ))
                            _line_vals_op.extend(list(_acum_p))
                    else:
                        fig_op.add_trace(go.Scatter(
                            x=x_op,
                            y=acum_op,
                            name="Flujo Operativo Acumulado",
                            mode="lines+markers+text" if lbl_op_acum else "lines+markers",
                            line=dict(color="#681E1E", width=3),
                            marker=dict(size=6),
                            text=[fmt_cop_short_fc(v) for v in acum_op] if lbl_op_acum else None,
                            textposition="top center",
                            textfont=dict(size=14, color=_line_op_colors),
                            yaxis="y2",
                        ))
                        _line_vals_op.extend(list(acum_op))

                    # Título dinámico según modo
                    if is_por_proyecto_fc:
                        _title_text = f"Flujo de Caja Operativo · Vista por proyecto ({len(snapshots)} etapas)"
                    else:
                        _title_text = (
                            f"Flujo de Caja Operativo | TIR: {fmt_tir_fc(tir_op_g)}"
                            + ("  ·  Vista detallada" if is_detail else "")
                        )

                    # ── Alinear cero entre y (barras) e y2 (acumulado) ──
                    def _aligned_ranges_op(bar_vals, line_vals, pad=0.05):
                        bmin = min(bar_vals + [0.0]) if bar_vals else -1.0
                        bmax = max(bar_vals + [0.0]) if bar_vals else 1.0
                        lmin = min(line_vals + [0.0]) if line_vals else -1.0
                        lmax = max(line_vals + [0.0]) if line_vals else 1.0
                        b_span = max(bmax - bmin, 1.0)
                        l_span = max(lmax - lmin, 1.0)
                        fb = -bmin / b_span
                        fl = -lmin / l_span
                        f  = min(max(max(fb, fl), 0.0), 0.999)
                        def _fit(y_min, y_max, target_f):
                            if target_f <= 0:
                                return (0.0, max(y_max, 1.0))
                            new_min_A = (-target_f * y_max / (1 - target_f)) if y_max > 0 else y_min
                            new_max_B = (-y_min * (1 - target_f) / target_f) if y_min < 0 else y_max
                            if new_min_A <= y_min:
                                return (new_min_A, y_max)
                            return (y_min, new_max_B)
                        b_new = _fit(bmin, bmax, f)
                        l_new = _fit(lmin, lmax, f)
                        def _pad(rng):
                            s = rng[1] - rng[0]
                            return (rng[0] - pad * s, rng[1] + pad * s)
                        return _pad(b_new), _pad(l_new)

                    _bar_range_op, _line_range_op = _aligned_ranges_op(
                        _bar_vals_op, _line_vals_op
                    )

                    fig_op.update_layout(
                        barmode="relative",
                        height=600 if (is_detail or is_por_proyecto_fc) else 520,
                        title=dict(
                            text=_title_text,
                            font=dict(size=16, color="#681E1E"),
                        ),
                        xaxis=dict(title="Periodo", tickangle=-45),
                        # Eje principal: barras (ingresos / costos / financieros)
                        yaxis=dict(
                            title="Barras · COP",
                            zeroline=True, zerolinecolor="#681E1E", zerolinewidth=1.5,
                            range=list(_bar_range_op),
                        ),
                        # Eje secundario: línea acumulada — mismo cero que el principal.
                        yaxis2=dict(
                            title=dict(text="Acumulado · COP", font=dict(color="#681E1E")),
                            overlaying="y",
                            side="right",
                            showgrid=False,
                            zeroline=True,
                            zerolinecolor="#681E1E",
                            zerolinewidth=1,
                            tickfont=dict(color="#681E1E"),
                            range=list(_line_range_op),
                        ),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        plot_bgcolor="white",
                        paper_bgcolor="white",
                        font=dict(family="Inter, sans-serif"),
                        margin=dict(l=60, r=70, t=90, b=80),
                    )

                    st.plotly_chart(fig_op, use_container_width=True)

                # ───────────────────────────────────
                # TAB 3: INDICADORES CLAVE
                # ───────────────────────────────────
                with tab_kpi:
                    st.subheader(f"Indicadores Clave — {tit_proyectos}")

                    def _compute_indicadores(snaps):
                        def _val_soporte(idx):
                            total = 0.0
                            found = False
                            for s in snaps:
                                linea = builder.get_linea_exacta(s, idx, Participacion.TOTAL)
                                if linea:
                                    total += linea.total_periodo
                                    found = True
                            return total if found else None

                        total_unidades  = _val_soporte("17.1")
                        total_m2_ventas = _val_soporte("17.3")
                        total_ingresos  = sum(_get_total_snap(s, "1.0") for s in snaps)
                        total_lote      = sum(_get_total_snap(s, "2.0") for s in snaps)

                        total_cd = sum(_get_total_snap(s, "3.0") for s in snaps)

                        # ── Básicos (se calculan y guardan; el orden se arma al final) ──
                        t_unidades = ("Unidades Vendidas",
                                      f"{total_unidades:,.0f}" if total_unidades else "N/A", "17.1")
                        if total_unidades and total_unidades != 0:
                            t_vr_unidad = ("Vr. Prom. Venta / Unidad",
                                           f"${total_ingresos/total_unidades:,.0f}", "1.0 / 17.1")
                        else:
                            t_vr_unidad = ("Vr. Prom. Venta / Unidad", "N/A", "—")
                        if total_m2_ventas and total_m2_ventas != 0:
                            t_vr_m2 = ("Vr. Prom. Venta / m² vendible",
                                       f"${total_ingresos/total_m2_ventas:,.0f}", "1.0 / 17.3")
                        else:
                            t_vr_m2 = ("Vr. Prom. Venta / m² vendible", "N/A", "—")
                        if total_m2_ventas and total_unidades and total_unidades != 0:
                            t_area = ("Área Promedio / Unidad",
                                      f"{total_m2_ventas/total_unidades:,.1f} m²", "17.3 / 17.1")
                        else:
                            t_area = ("Área Promedio / Unidad", "N/A", "—")
                        if total_m2_ventas and total_m2_ventas != 0 and total_lote != 0:
                            t_vr_lote = ("Vr. Lote / m² vendible",
                                         f"${abs(total_lote)/total_m2_ventas:,.0f}", "2.0 / 17.3")
                        else:
                            t_vr_lote = ("Vr. Lote / m² vendible", "N/A", "—")

                        # Ritmo de Ventas: periodos activos en UNIÓN entre snaps
                        periodos_activos_set = set()
                        for s in snaps:
                            linea_u = builder.get_linea_exacta(s, "17.1", Participacion.TOTAL)
                            if linea_u:
                                for f in s.fechas_flujo:
                                    if linea_u.valores.get(f, 0.0) != 0.0:
                                        periodos_activos_set.add(f)
                        periodos_activos = len(periodos_activos_set)
                        if total_unidades and total_unidades > 0 and periodos_activos > 0:
                            t_ritmo = ("Ritmo de Ventas",
                                       f"{total_unidades/periodos_activos:,.1f} Un/mes",
                                       f"{periodos_activos} meses activos")
                        else:
                            t_ritmo = ("Ritmo de Ventas", "N/A", "—")

                        # Incidencia Lote
                        if total_ingresos != 0:
                            t_inc_lote = ("Incidencia Lote",
                                          f"{abs(total_lote)/total_ingresos*100:.1f}%", "2.0 / 1.0")
                        else:
                            t_inc_lote = ("Incidencia Lote", "N/A", "—")

                        # NUEVO — Incidencia Costo Directo / Ventas
                        if total_ingresos != 0:
                            t_inc_cd = ("Incidencia Costo Directo",
                                        f"{abs(total_cd)/total_ingresos*100:.1f}%", "3.0 / 1.0")
                        else:
                            t_inc_cd = ("Incidencia Costo Directo", "N/A", "—")

                        # NUEVO — Duración Construcción (meses activos de 3.22, fallback 3.0)
                        def _dur_meses(idx):
                            activos = set()
                            for s in snaps:
                                l = builder.get_linea_exacta(s, idx, Participacion.TOTAL)
                                if l:
                                    for f, v in l.valores.items():
                                        if v != 0.0:
                                            activos.add(str(f)[:10])
                            if not activos:
                                return None
                            ds = sorted(date.fromisoformat(x) for x in activos)
                            return (ds[-1].year - ds[0].year) * 12 + (ds[-1].month - ds[0].month) + 1
                        _dc_idx = "3.22"
                        _dur = _dur_meses("3.22")
                        if _dur is None:
                            _dur, _dc_idx = _dur_meses("3.0"), "3.0"
                        t_dur_con = (("Duración Construcción", f"{_dur} meses", _dc_idx)
                                     if _dur else ("Duración Construcción", "N/A", "3.22"))

                        # ── Avanzados (dict por nombre) ──
                        _adv = {}
                        try:
                            for _t in compute_indicadores_avanzados(snaps, builder):
                                _adv[_t[0]] = _t
                        except Exception:
                            _adv = {}
                        def _A(name, label):
                            return _adv.get(name, (label, "N/A", "—"))

                        # ── Orden solicitado (grilla 4 col) ──
                        return [
                            t_area,
                            t_unidades,
                            _A("Punto de Equilibrio Comercial", "Punto Equilibrio Comercial"),
                            _A("Duración Comercial Total", "Duración Comercial Total"),
                            t_ritmo,
                            t_vr_unidad,
                            t_vr_m2,
                            _A("Vr. m² Inicial → Final", "Vr. m² Inicial → Final"),
                            _A("Costo Construcción / m² vendible", "Costo Construcción / m² vendible"),
                            t_inc_cd,
                            t_dur_con,
                            t_vr_lote,
                            t_inc_lote,
                        ]

                    def _ind_card(col, item, fuente_prefix):
                        nombre_ind, valor_ind, fuente_ind = item
                        _sub = f"Fuente: {fuente_ind}" if fuente_prefix else fuente_ind
                        with col:
                            st.markdown(f"""
                            <div class="kpi-box">
                              <div class="kpi-label">{nombre_ind}</div>
                              <div class="kpi-value">{valor_ind}</div>
                              <div class="kpi-sub">{_sub}</div>
                            </div>""", unsafe_allow_html=True)

                    def _render_indicadores(inds, cols_per_row=4, fuente_prefix=True, transpose=False):
                        if not inds:
                            return
                        # Filas en la disposición normal (row-major, ancho cols_per_row)
                        rows = [inds[i:i + cols_per_row] for i in range(0, len(inds), cols_per_row)]
                        if not transpose:
                            for row in rows:
                                cols = st.columns(cols_per_row)
                                for j, item in enumerate(row):
                                    _ind_card(cols[j], item, fuente_prefix)
                        else:
                            # Transponer (estilo Excel): cada fila original se vuelve una
                            # columna. La fila 0 pasa a ser la 1ª columna, etc.
                            nrows = len(rows)
                            for new_r in range(cols_per_row):
                                cols = st.columns(nrows)
                                for c in range(nrows):
                                    if new_r < len(rows[c]):
                                        _ind_card(cols[c], rows[c][new_r], fuente_prefix)

                    def _seccion_header(titulo, key):
                        """Header de sección con toggle 'Transponer'. Devuelve el estado."""
                        _h1, _h2 = st.columns([4, 1])
                        with _h1:
                            st.markdown(f"##### {titulo}")
                        with _h2:
                            return st.toggle("🔁 Transponer", key=key,
                                             help="Intercambia filas por columnas (como en Excel).")

                    # ── Consolidado ──
                    st.markdown("#### 🌐 Consolidado")

                    # Grupo 1 — KPIs de la pestaña Factibilidad (mismos valores, sin
                    # recalcular → consistencia garantizada). Incluye Margen FCO; los
                    # operativos ya no lo repiten.
                    _factib_proy = st.session_state.get("_factib_kpis_proy", [])
                    if _factib_proy:
                        _t_factib = _seccion_header("💰 Factibilidad (P&G)", "factib_transpose")
                        _render_indicadores(_factib_proy, fuente_prefix=False, transpose=_t_factib)

                    # Grupo 2 — indicadores operativos y comerciales.
                    _t_oper = _seccion_header("📏 Operativos y Comerciales", "oper_transpose")
                    _render_indicadores(_compute_indicadores(snapshots), transpose=_t_oper)

                    # ── Por proyecto (expandibles) ──
                    if len(snapshots) > 1:
                        st.divider()
                        st.markdown("#### 📁 Por proyecto")
                        for s in snapshots:
                            with st.expander(f"📂 {s.proyecto}"):
                                _render_indicadores(_compute_indicadores([s]))

                    # Líneas de soporte detectadas (consolidado)
                    with st.expander("🔎 Líneas de Soporte Detectadas (17.x / 18.x)"):
                        soporte_rows = []
                        for s in snapshots:
                            for l in s.lineas:
                                if (l.participacion == Participacion.TOTAL
                                        and l.indice.split(".")[0] in ("17", "18")):
                                    soporte_rows.append({
                                        "Proyecto": str(s.proyecto),
                                        "Índice": l.indice,
                                        "Nombre": l.nombre,
                                        "Total": l.total_periodo,
                                    })
                        if soporte_rows:
                            df_soporte = pd.DataFrame(soporte_rows)
                            st.dataframe(df_soporte.style.format({"Total": "{:,.0f}"}),
                                         use_container_width=True, hide_index=True)
                        else:
                            st.info("No se detectaron líneas de soporte en los snapshots.")

                # ───────────────────────────────────
                # TAB: FORMA DE PAGO LOTE
                # ───────────────────────────────────
                with tab_lote:
                    st.subheader(f"🏞️ Forma de Pago del Lote — {tit_proyectos}")
                    st.caption(
                        "Distribución del flujo de **Lote Bruto** (consolidado de los "
                        "proyectos filtrados). Ingresa el % de cada periodo pagado con "
                        "**Canje (m²)**; el resto se considera **Pago ($)**."
                    )

                    # 1) Lote Bruto = línea EXACTA 2.22 (no sumar padres ni hermanos).
                    lote_idx = "2.22"
                    lote_nombre = "Lote Bruto"
                    for s in snapshots:
                        _l = builder.get_linea_exacta(s, lote_idx, Participacion.TOTAL)
                        if _l and _l.nombre:
                            lote_nombre = _l.nombre
                            break

                    # 2) Serie mensual consolidada (alineada a fechas_union). El lote
                    #    se muestra en positivo (valor a pagar).
                    serie_mes_lote = [abs(v) for v in _get_valores_lista(lote_idx)]

                    if not fechas_union or sum(serie_mes_lote) == 0:
                        st.info(
                            f"No se detectó flujo de lote (línea {lote_idx} · "
                            f"{lote_nombre}) en los proyectos filtrados."
                        )
                    else:
                        # ── Controles ──
                        lc1, lc2 = st.columns([1.2, 2])
                        with lc1:
                            lote_gran = st.radio(
                                "Ver por:", ["Año", "Mes"], horizontal=True,
                                index=0, key="lote_granularidad",
                            )
                        with lc2:
                            _lbl_exp = getattr(st, "popover", None)
                            _ctx = st.popover("🏷️ Etiquetas") if _lbl_exp else st.expander("🏷️ Etiquetas")
                            with _ctx:
                                lote_lbl_canje = st.checkbox("Canje (m²)", value=False, key="lote_lbl_canje")
                                lote_lbl_pago  = st.checkbox("Pago ($)",   value=False, key="lote_lbl_pago")
                                lote_lbl_acum  = st.checkbox("Acumulado",  value=False, key="lote_lbl_acum")

                        # ── Agregación según granularidad ──
                        _MESES_AB = {1:"ene",2:"feb",3:"mar",4:"abr",5:"may",6:"jun",
                                     7:"jul",8:"ago",9:"sep",10:"oct",11:"nov",12:"dic"}
                        if lote_gran == "Año":
                            _buckets = {}
                            for f, v in zip(fechas_union, serie_mes_lote):
                                y = str(f)[:4]
                                _buckets[y] = _buckets.get(y, 0.0) + v
                            per_labels = sorted(_buckets)
                            per_vals   = [_buckets[p] for p in per_labels]
                        else:
                            per_labels, per_vals = [], []
                            for f, v in zip(fechas_union, serie_mes_lote):
                                d = date.fromisoformat(str(f)[:10])
                                per_labels.append(f"{_MESES_AB[d.month]}-{d.year}")
                                per_vals.append(v)

                        # ── % Canje por periodo (estado en session_state) ──
                        def _canje_key(lbl):
                            return f"lote_canje::{lote_gran}::{lbl}"

                        activos = [i for i, v in enumerate(per_vals) if v > 0]
                        for i in activos:
                            k = _canje_key(per_labels[i])
                            if k not in st.session_state:
                                st.session_state[k] = 0.0

                        # Leer % ANTES de instanciar widgets (para que la gráfica de
                        # arriba refleje el último valor en cada rerun).
                        pct_canje = [
                            (float(st.session_state.get(_canje_key(per_labels[i]), 0.0)) / 100.0
                             if i in activos else 0.0)
                            for i in range(len(per_vals))
                        ]
                        canje_vals = [per_vals[i] * pct_canje[i] for i in range(len(per_vals))]
                        pago_vals  = [per_vals[i] - canje_vals[i] for i in range(len(per_vals))]

                        # Acumulado del TOTAL (no se parte)
                        acum_lote, _s = [], 0.0
                        for v in per_vals:
                            _s += v
                            acum_lote.append(_s)

                        # ── Gráfica (barras apiladas Pago+Canje + línea acumulada) ──
                        fig_lote = go.Figure()
                        fig_lote.add_trace(go.Bar(
                            x=per_labels, y=pago_vals, name="Pago ($)",
                            marker_color="#681E1E", opacity=0.92,
                            text=[fmt_cop_fc(v) if (lote_lbl_pago and v > 0) else "" for v in pago_vals],
                            textposition="inside", insidetextfont=dict(color="#FFFFFF", size=12),
                        ))
                        fig_lote.add_trace(go.Bar(
                            x=per_labels, y=canje_vals, name="Canje (m²)",
                            marker_color="#2E86C1", opacity=0.92,
                            text=[fmt_cop_fc(v) if (lote_lbl_canje and v > 0) else "" for v in canje_vals],
                            textposition="inside", insidetextfont=dict(color="#FFFFFF", size=12),
                        ))
                        fig_lote.add_trace(go.Scatter(
                            x=per_labels, y=acum_lote, name="Acumulado",
                            mode="lines+markers+text" if lote_lbl_acum else "lines+markers",
                            line=dict(color="#1F6F40", width=3), marker=dict(size=6),
                            text=[fmt_cop_fc(v) for v in acum_lote] if lote_lbl_acum else None,
                            textposition="top center", textfont=dict(size=12, color="#1F6F40"),
                            cliponaxis=False, yaxis="y2",
                        ))
                        _acum_max = max(acum_lote + [1.0])
                        fig_lote.update_layout(
                            barmode="stack",
                            height=480,
                            title=dict(text=f"Forma de Pago — {lote_nombre} ({lote_idx})  ·  Total: {fmt_cop_fc(sum(per_vals))}",
                                       font=dict(size=15, color="#681E1E")),
                            xaxis=dict(title="Periodo", tickangle=-45 if lote_gran == "Mes" else 0),
                            yaxis=dict(title="Lote · COP", rangemode="tozero"),
                            yaxis2=dict(title=dict(text="Acumulado · COP", font=dict(color="#1F6F40")),
                                        overlaying="y", side="right", showgrid=False,
                                        rangemode="tozero", range=[0, _acum_max * 1.15],
                                        tickfont=dict(color="#1F6F40")),
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                            plot_bgcolor="white", paper_bgcolor="white",
                            font=dict(family="Inter, sans-serif"),
                            margin=dict(l=60, r=70, t=80, b=80),
                        )
                        st.plotly_chart(fig_lote, use_container_width=True)

                        # ── Inputs de % Canje (debajo de la gráfica) ──
                        st.markdown("##### % Canje (m²) por periodo")
                        st.caption("Solo se muestran los periodos con flujo de lote. Rango 0–100%.")
                        if activos:
                            _per_row = 6
                            for _start in range(0, len(activos), _per_row):
                                _chunk = activos[_start:_start + _per_row]
                                _cols = st.columns(_per_row)
                                for _ci, _pi in enumerate(_chunk):
                                    with _cols[_ci]:
                                        st.number_input(
                                            f"{per_labels[_pi]}  ({fmt_cop_fc(per_vals[_pi])})",
                                            min_value=0.0, max_value=100.0, step=5.0,
                                            format="%.1f", key=_canje_key(per_labels[_pi]),
                                        )
                        else:
                            st.info("No hay periodos con flujo de lote para asignar canje.")

                # ───────────────────────────────────
                # TAB 4: CRONOGRAMA (GANTT)
                # ───────────────────────────────────
                with tab_crono:
                    st.subheader(f"Cronograma — {tit_proyectos}")

                    def _detectar_rango_snap(snap, indice_str, part=Participacion.TOTAL):
                        linea = builder.get_linea_exacta(snap, indice_str, part)
                        if not linea:
                            return None, None
                        fechas_activas = [
                            f for f in snap.fechas_flujo
                            if linea.valores.get(f, 0.0) != 0.0
                        ]
                        if not fechas_activas:
                            return None, None
                        return fechas_activas[0], fechas_activas[-1]

                    # Paleta del formato de referencia: Ventas (mauve) · Obra
                    # (vinotinto IC) · Entregas (verde).
                    hito_defs = [
                        ("Ventas",   "17.1", "#B08A8A"),
                        ("Obra",     "3.22", "#7B1F1F"),
                        ("Entregas", "18.1", "#1F7A44"),
                    ]

                    # Una fila por PROYECTO (etapa); cada fase es un segmento ubicado
                    # en su rango real de fechas sobre la misma fila.
                    hitos = []
                    proy_rangos = {}  # proyecto -> {fase: (ini, fin)}
                    for s in snapshots:
                        for nombre_h, idx_h, color_h in hito_defs:
                            f_ini, f_fin = _detectar_rango_snap(s, idx_h)
                            if f_ini:
                                hitos.append((str(s.proyecto), f_ini, f_fin, color_h, nombre_h, str(s.proyecto)))
                                proy_rangos.setdefault(str(s.proyecto), {})[nombre_h] = (f_ini, f_fin)

                    if not hitos:
                        st.info("No se detectaron líneas de cronograma (17.1, 3.22, 18.1) en los snapshots.")
                    else:
                        from datetime import timedelta as _td
                        _dmin = min(date.fromisoformat(h[1]) for h in hitos)
                        _dmax = max(date.fromisoformat(h[2]) for h in hitos)
                        # Encuadre del eje X a años completos, con un pequeño margen.
                        _rng_ini = date(_dmin.year, 1, 1) - _td(days=20)
                        _rng_fin = date(_dmax.year + 1, 1, 1) + _td(days=20)

                        # Orden de etapas por fecha de inicio (la más temprana arriba).
                        def _proy_start(p):
                            return min(v[0] for v in proy_rangos[p].values())
                        proy_orden = sorted(proy_rangos.keys(), key=_proy_start)

                        fig_gantt = go.Figure()
                        _seen_lg = set()
                        for p in proy_orden:
                            for nombre_h, idx_h, color_h in hito_defs:
                                rng = proy_rangos[p].get(nombre_h)
                                if not rng:
                                    continue
                                f_ini, f_fin = rng
                                d_ini = date.fromisoformat(f_ini)
                                d_fin = date.fromisoformat(f_fin)
                                dias = max(20, (d_fin - d_ini).days)
                                _show_lg = nombre_h not in _seen_lg
                                _seen_lg.add(nombre_h)
                                fig_gantt.add_trace(go.Bar(
                                    y=[p],
                                    x=[dias * 24 * 60 * 60 * 1000],
                                    base=[f_ini],
                                    orientation="h",
                                    name=nombre_h,
                                    legendgroup=nombre_h,
                                    showlegend=_show_lg,
                                    marker_color=color_h,
                                    marker_line_width=0,
                                    hovertemplate=f"<b>{p}</b> · {nombre_h}<br>{f_ini} → {f_fin}<extra></extra>",
                                ))

                        # ── Ticks del eje X: año en enero + nº de mes (4/7/10) por
                        #    trimestre. Trimestral evita que los textos se superpongan
                        #    aunque el rango abarque muchos años. (Verificado en imagen.)
                        def _meses_entre(a, b):
                            y, m, out = a.year, a.month, []
                            while (y < b.year) or (y == b.year and m <= b.month):
                                out.append(date(y, m, 1))
                                m += 1
                                if m > 12:
                                    m = 1; y += 1
                            return out
                        _ticks_q = [x for x in _meses_entre(_rng_ini, _rng_fin) if x.month in (1, 4, 7, 10)]
                        _tickvals = [x.isoformat() for x in _ticks_q]
                        _ticktext = [(str(x.year) if x.month == 1 else str(x.month)) for x in _ticks_q]

                        # Altura: ~90 px por etapa para un look aireado como la referencia.
                        fig_gantt.update_layout(
                            height=max(300, 90 * len(proy_orden) + 130),
                            title=dict(
                                text="Cronograma por etapa",
                                font=dict(size=20, color="#681E1E"),
                                x=0.01, xanchor="left",
                            ),
                            xaxis=dict(
                                type="date",
                                tickmode="array",
                                tickvals=_tickvals,
                                ticktext=_ticktext,
                                range=[_rng_ini.isoformat(), _rng_fin.isoformat()],
                                tickfont=dict(size=14, color="#333"),
                                showgrid=False, showline=False, ticks="", zeroline=False,
                            ),
                            yaxis=dict(
                                autorange="reversed",
                                tickfont=dict(size=17, color="#333"),
                                showgrid=False, showline=False, ticks="",
                            ),
                            barmode="overlay",
                            bargap=0.45,
                            legend=dict(
                                orientation="h", yanchor="bottom", y=1.02,
                                xanchor="right", x=1, font=dict(size=15),
                            ),
                            plot_bgcolor="white",
                            paper_bgcolor="white",
                            font=dict(family="Inter, sans-serif"),
                            margin=dict(l=110, r=30, t=70, b=40),
                        )
                        # Grilla vertical SOLO por año (look limpio de la referencia).
                        for _yr in range(_rng_ini.year, _rng_fin.year + 1):
                            fig_gantt.add_vline(x=f"{_yr}-01-01", line_color="#E2E2E2",
                                                line_width=1, layer="below")
                        st.plotly_chart(fig_gantt, use_container_width=True)

                        st.markdown("#### Resumen de Hitos")
                        # Agrupar por proyecto (etapa) preservando orden de aparición.
                        _grp_h = {}
                        _ord_h = []
                        for h in hitos:
                            _p = h[5]
                            if _p not in _grp_h:
                                _grp_h[_p] = []
                                _ord_h.append(_p)
                            _di, _df_ = date.fromisoformat(h[1]), date.fromisoformat(h[2])
                            _dur = max(1, (_df_.year - _di.year) * 12 + _df_.month - _di.month)
                            _grp_h[_p].append((h[4], h[1], h[2], f"{_dur} meses"))

                        _hitos_css = """<style>
                          .hitos-tbl{border-collapse:collapse;width:100%;font-family:'Inter',sans-serif;font-size:14px;}
                          .hitos-tbl thead th{background:#681E1E;color:#fff;font-weight:700;
                              text-align:left;padding:9px 14px;}
                          .hitos-tbl td{padding:8px 14px;border-bottom:1px solid #eee;}
                          .hitos-tbl td.hp{font-weight:700;color:#681E1E;vertical-align:middle;
                              background:#faf6f6;border-right:1px solid #e2d6d6;}
                          .hitos-tbl tr.grp-top td{border-top:3px solid #681E1E;}
                        </style>"""

                        _rows_h = ""
                        for _p in _ord_h:
                            _g = _grp_h[_p]
                            for _ri, (_hi, _in, _fn, _du) in enumerate(_g):
                                _cls = ' class="grp-top"' if _ri == 0 else ""
                                _pcell = (f'<td class="hp" rowspan="{len(_g)}">{_p}</td>'
                                          if _ri == 0 else "")
                                _rows_h += (f'<tr{_cls}>{_pcell}<td>{_hi}</td>'
                                            f'<td>{_in}</td><td>{_fn}</td><td>{_du}</td></tr>')

                        st.markdown(
                            _hitos_css
                            + '<table class="hitos-tbl"><thead><tr>'
                            + '<th>Proyecto</th><th>Hito</th><th>Inicio</th>'
                            + '<th>Fin</th><th>Duración</th></tr></thead>'
                            + f'<tbody>{_rows_h}</tbody></table>',
                            unsafe_allow_html=True,
                        )

            except Exception as e:
                import traceback
                st.error(f"❌ Error al generar el reporte: {e}")
                st.code(traceback.format_exc())


# ═════════════════════════════════════════════
# MÓDULO 5 — FLUJO PROYECTO (CONTROL DE CAJA)
# Réplica de la hoja FCxPROYECTO del consolidador
# ═════════════════════════════════════════════

elif modulo == "💼 Flujo Proyecto (Control)":
    # ── 1) Ocultar el sidebar lateral en este módulo para ganar ancho ──
    st.markdown(
        """
        <style>
          section[data-testid="stSidebar"] { display: none !important; }
          [data-testid="collapsedControl"] { display: none !important; }
          .main .block-container {
              padding-left: 1rem !important;
              padding-right: 1rem !important;
              padding-top: 0.5rem !important;
              max-width: 100% !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── 2) Top-nav (reemplaza el sidebar en este módulo) ──
    _modulos_lst = [
        ("📂 Cargar Base", "📂"),
        ("🔍 Auditoría", "🔍"),
        ("📈 Reporte Inversionista", "📈"),
        ("📊 Reporte Proyecto", "📊"),
        ("🆚 Comparación Proyectos", "🆚"),
        ("💼 Flujo Proyecto (Control)", "💼"),
    ]

    def _switch_module(target):
        st.session_state["modulo_main_nav"] = target

    st.markdown('<div class="fcp-topnav-wrapper">', unsafe_allow_html=True)
    _topnav_cols = st.columns([0.9] + [1] * len(_modulos_lst))
    with _topnav_cols[0]:
        st.markdown(
            '<div class="fcp-topnav-title">Estate<br/>Auditor</div>',
            unsafe_allow_html=True,
        )
    for _idx, (_mod_name, _icon) in enumerate(_modulos_lst):
        with _topnav_cols[_idx + 1]:
            is_current = (_mod_name == modulo)
            st.button(
                _mod_name,
                key=f"topnav_btn_{_idx}",
                on_click=_switch_module,
                args=(_mod_name,),
                disabled=is_current,
                type="primary" if is_current else "secondary",
                use_container_width=True,
            )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 3) Hero ──
    st.markdown(
        """
        <div class="fcp-hero" style="padding:1.2rem 1.5rem; margin-bottom:1rem;">
          <h1 style="font-size:1.5rem;">💼 Flujo Proyecto · Control de Caja en Tiempo Real</h1>
          <p style="font-size:0.88rem;">
            Vista segmentada por tramos (realidad ejecutada · proyección cercana · pendiente al cierre · total).
            A la izquierda <b>indicadores y alertas</b>, en el centro la <b>tabla de tramos</b> con grupos colapsables
            y a la derecha el <b>flujo mensual navegable</b>.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.records:
        st.warning("⚠️ Carga la base de datos en el módulo 📂 Cargar Base.")
        st.stop()

    resp = st.session_state.upload_response

    # ── BARRA DE CONTROLES ─────────────────────
    with st.container():
        st.markdown('<div class="fcp-ctrlbar">', unsafe_allow_html=True)
        ctrl_a, ctrl_b, ctrl_c, ctrl_d = st.columns([2.2, 1.6, 1.6, 1.6])

        with ctrl_a:
            fcp_proy = st.selectbox(
                "🏢 Proyecto",
                resp.proyectos,
                key="fcp_proy",
                help="Proyecto cuyo flujo de caja se controlará."
            )

        # Fechas disponibles para el proyecto seleccionado
        fechas_disp = resp.fechas_datos.get(fcp_proy, [])
        if not fechas_disp:
            st.markdown('</div>', unsafe_allow_html=True)
            st.error("Este proyecto no tiene cortes cargados en la base.")
            st.stop()

        with ctrl_b:
            fcp_fecha_snap_lbl = st.selectbox(
                "🗓️ Snapshot a usar",
                sorted(fechas_disp, reverse=True),
                key="fcp_fecha_snap",
                help="Versión del snapshot (corte de los datos cargados)."
            )

        # Parsear la etiqueta de versión → fecha + version
        from datetime import date as _date_mod
        fcp_fecha_snap_obj, fcp_version_obj = parse_fecha_label(fcp_fecha_snap_lbl)

        with ctrl_c:
            fcp_corte = st.date_input(
                "📍 Fecha de Corte (al corte)",
                value=fcp_fecha_snap_obj,
                key="fcp_corte",
                help="Fecha hasta la cual se considera 'realidad ejecutada'. "
                     "Por defecto, coincide con la fecha del snapshot."
            )

        # Default del hito: diciembre del año en curso
        _hoy = _date_mod.today()
        _default_hito = _date_mod(_hoy.year, 12, 1)
        # Si el corte ya pasó diciembre del año en curso, mover el hito al
        # diciembre del año del corte
        if _default_hito <= fcp_corte:
            _default_hito = _date_mod(fcp_corte.year, 12, 1)
            if _default_hito <= fcp_corte:
                _default_hito = _date_mod(fcp_corte.year + 1, 12, 1)

        with ctrl_d:
            fcp_hito = st.date_input(
                "🎯 Hito (corte → hito)",
                value=_default_hito,
                key="fcp_hito",
                help="Fecha de hito intermedio (típicamente cierre del año en curso). "
                     "Define el final del tramo 'corte → hito'."
            )

        st.markdown('</div>', unsafe_allow_html=True)

    if fcp_hito <= fcp_corte:
        st.error("⚠️ La fecha de hito debe ser posterior a la fecha de corte.")
        st.stop()

    # ── CONSTRUIR SNAPSHOT ─────────────────────
    try:
        fcp_snapshot = _build_snapshot(fcp_proy, fcp_fecha_snap_obj, fcp_version_obj)
    except Exception as ex:
        st.error(f"❌ Error al construir el snapshot: {ex}")
        st.stop()

    # ── CLASIFICACIÓN DE LÍNEAS (Fuente / Uso / Informativo) ──
    # Basado en la convención de la hoja FCxPROYECTO original.
    FCP_FUENTES_EXACTAS = {"11.2", "12.2", "13.2", "14.2", "15.2", "21.2"}
    FCP_USOS_EXACTAS    = {"11.4", "11.5", "11.7", "12.4", "12.5", "12.7",
                           "13.4", "14.4", "15.4", "21.1"}

    def _fcp_lado(indice: str):
        """Retorna 'F' (Fuente), 'U' (Uso) o 'I' (Informativo)."""
        # Subtotales/saldos/informativos
        if indice in ("9.0", "10.0", "11.0", "12.0", "13.0", "14.0", "15.0",
                      "16.0", "16.1", "17.0", "18.0", "19.0", "20.0", "21.0"):
            return "I"
        # Ingresos (todas las 1.x)
        if indice.startswith("1.") or indice == "1.0":
            return "F"
        # Lote, Costos, Indirectos, Honorarios, Financieros, IVA, Anticipos
        if indice.startswith(("2.", "3.", "4.", "5.", "6.", "7.", "8.")):
            return "U"
        if indice in FCP_FUENTES_EXACTAS:
            return "F"
        if indice in FCP_USOS_EXACTAS:
            return "U"
        # Soporte (17.x, 18.x, 19.x, 20.x) — unidades, m², etc.
        if indice.startswith(("17.", "18.", "19.", "20.", "21.")):
            return "I"
        return "I"

    # ── ESTRUCTURA DE GRUPOS PARA LA TABLA ─────
    FCP_GRUPOS = [
        ("ingresos",   "📥 Ingresos (1.x)",
         lambda i: i.startswith("1.") or i == "1.0"),
        ("lote",       "🏞️ Lote (2.x)",
         lambda i: i.startswith("2.") or i == "2.0"),
        ("costo_dir",  "🧱 Costo Directo (3.x)",
         lambda i: i.startswith("3.") or i == "3.0"),
        ("indirecto",  "🏗️ Costo Indirecto (4.x)",
         lambda i: i.startswith("4.") or i == "4.0"),
        ("honorarios", "💼 Honorarios (5.x)",
         lambda i: i.startswith("5.") or i == "5.0"),
        ("financ",     "💸 Financieros (6.x)",
         lambda i: i.startswith("6.") or i == "6.0"),
        ("iva",        "🧾 IVA y Anticipos (7.x / 8.x)",
         lambda i: i.startswith("7.") or i.startswith("8.") or i in ("7.0", "8.0")),
        ("total_op",   "🟦 TOTAL OPERATIVOS",
         lambda i: i in ("9.0", "10.0")),
        ("credito",    "🏦 Crédito Constructor (11.x)",
         lambda i: i.startswith("11.") or i == "11.0"),
        ("otros_cred", "🏦 Otros Créditos (12.x)",
         lambda i: i.startswith("12.") or i == "12.0"),
        ("aportes_ic", "💎 Aportes IC (13.x)",
         lambda i: i.startswith("13.") or i == "13.0"),
        ("aportes_so", "🤝 Aportes Socio (14.x)",
         lambda i: i.startswith("14.") or i == "14.0"),
        ("prest_et",   "🔁 Préstamos entre Etapas (15.x)",
         lambda i: i.startswith("15.") or i == "15.0"),
        ("retenc",     "📜 Retenciones por Escrituración (21.x)",
         lambda i: i.startswith("21.") or i == "21.0"),
        ("total_fon",  "🟩 TOTAL FONDEO",
         lambda i: i in ("16.0", "16.1")),
        ("ventas_u",   "📊 Ventas / Escrituraciones (informativo)",
         lambda i: i.startswith(("17.", "18.")) or i in ("17.0", "18.0")),
        ("fyu",        "📐 Fuentes y Usos · Capitalización (informativo)",
         lambda i: i.startswith(("19.", "20."))),
    ]

    # ── AGREGACIÓN POR TRAMO ───────────────────
    def _val_tramo(linea, f_ini=None, f_fin_excl=None, f_fin_incl=None):
        """Suma los valores de la línea en el tramo dado."""
        total = 0.0
        for fstr, v in linea.valores.items():
            if not v:
                continue
            try:
                d = _date_mod.fromisoformat(fstr)
            except Exception:
                continue
            if f_ini is not None and d < f_ini:
                continue
            if f_fin_excl is not None and d >= f_fin_excl:
                continue
            if f_fin_incl is not None and d > f_fin_incl:
                continue
            total += v
        return total

    # Solo participación TOTAL
    lineas_total = [l for l in fcp_snapshot.lineas if l.participacion == Participacion.TOTAL]

    fcp_data = {}
    for l in lineas_total:
        lado = _fcp_lado(l.indice)
        v_real      = _val_tramo(l, f_fin_incl=fcp_corte)
        v_proy_cerc = _val_tramo(l, f_ini=_date_mod.fromordinal(fcp_corte.toordinal() + 1),
                                 f_fin_incl=fcp_hito)
        v_pend      = _val_tramo(l, f_ini=_date_mod.fromordinal(fcp_hito.toordinal() + 1))
        v_total     = l.total_periodo
        fcp_data[l.indice] = {
            "linea": l,
            "lado": lado,
            "real": v_real,
            "proy_cerc": v_proy_cerc,
            "pend": v_pend,
            "total": v_total,
        }

    # ── KPIs SUPERIORES ────────────────────────
    fuentes_real = sum(d["real"]  for d in fcp_data.values() if d["lado"] == "F")
    usos_real    = sum(d["real"]  for d in fcp_data.values() if d["lado"] == "U")
    caja_corte   = fuentes_real - usos_real

    fuentes_proy = sum(d["proy_cerc"] for d in fcp_data.values() if d["lado"] == "F")
    usos_proy    = sum(d["proy_cerc"] for d in fcp_data.values() if d["lado"] == "U")
    caja_hito_est = caja_corte + (fuentes_proy - usos_proy)

    fuentes_vida = sum(d["total"] for d in fcp_data.values() if d["lado"] == "F")
    usos_vida    = sum(d["total"] for d in fcp_data.values() if d["lado"] == "U")

    check_fyu = fuentes_vida - usos_vida

    def _fcp_fmt(v):
        if v is None:
            return "—"
        sign = "-" if v < 0 else ""
        av = abs(v)
        if av >= 1_000_000:
            mills = av / 1_000_000
            if mills >= 1_000:
                fmt_v = f"{mills:,.0f}".replace(",", ".")
            else:
                fmt_v = f"{mills:,.1f}"
            return f"{sign}${fmt_v}M"
        if av < 1:
            return "$0"
        return f"{sign}${av:,.0f}"

    def _fcp_fmt_full(v):
        if v is None or abs(v) < 1:
            return "—"
        sign = "-" if v < 0 else ""
        return f"{sign}${abs(v):,.0f}"

    # ── DATOS ADICIONALES PARA EL PANEL DERECHO Y ALERTAS ──
    # Caja proyectada mes a mes (acumulado F-U), para detectar negativos
    fechas_ord = sorted(fcp_snapshot.fechas_flujo)
    fuentes_mes = {f: 0.0 for f in fechas_ord}
    usos_mes    = {f: 0.0 for f in fechas_ord}
    for d in fcp_data.values():
        for f, v in d["linea"].valores.items():
            if d["lado"] == "F":
                fuentes_mes[f] = fuentes_mes.get(f, 0.0) + (v or 0.0)
            elif d["lado"] == "U":
                usos_mes[f]    = usos_mes.get(f, 0.0)    + (v or 0.0)
    caja_acum_mes = {}
    _ac = 0.0
    for f in fechas_ord:
        _ac += fuentes_mes.get(f, 0.0) - usos_mes.get(f, 0.0)
        caja_acum_mes[f] = _ac

    meses_negativos = [(f, v) for f, v in caja_acum_mes.items() if v < -1]
    peor_mes = min(meses_negativos, key=lambda x: x[1]) if meses_negativos else None

    # ═══════════════════════════════════════════
    # LAYOUT DE 3 COLUMNAS
    # ═══════════════════════════════════════════
    col_left, col_center, col_right = st.columns([1.6, 5, 4.4], gap="small")

    # ─────────────────────────────────────────────
    # COLUMNA IZQUIERDA · KPIs + ALERTAS
    # ─────────────────────────────────────────────
    with col_left:
        st.markdown("##### 📊 Indicadores")

        caja_cls   = "kpi-ok"   if caja_corte >= 0 else "kpi-crit"
        hito_cls   = "kpi-ok"   if caja_hito_est >= 0 else "kpi-crit"
        check_cls  = "kpi-ok"   if abs(check_fyu) < 100_000 else "kpi-warn"
        check_lbl  = "✅ Cuadra" if abs(check_fyu) < 100_000 else f"⚠️ Δ {_fcp_fmt(check_fyu)}"

        st.markdown(
            f"""
            <div class="fcp-left-kpi {caja_cls}">
              <div class="fcp-left-kpi-lbl">💰 Caja al corte</div>
              <div class="fcp-left-kpi-val">{_fcp_fmt(caja_corte)}</div>
              <div class="fcp-left-kpi-sub">Σ F − Σ U a {fcp_corte}</div>
            </div>
            <div class="fcp-left-kpi {hito_cls}">
              <div class="fcp-left-kpi-lbl">🎯 Caja al hito</div>
              <div class="fcp-left-kpi-val">{_fcp_fmt(caja_hito_est)}</div>
              <div class="fcp-left-kpi-sub">Estimado a {fcp_hito}</div>
            </div>
            <div class="fcp-left-kpi {check_cls}">
              <div class="fcp-left-kpi-lbl">🧮 CHECK F&amp;U</div>
              <div class="fcp-left-kpi-val" style="font-size:1rem;">{check_lbl}</div>
              <div class="fcp-left-kpi-sub">Σ F − Σ U vida total</div>
            </div>
            <div class="fcp-left-kpi">
              <div class="fcp-left-kpi-lbl">📦 Total Vida</div>
              <div class="fcp-left-kpi-val">{_fcp_fmt(fuentes_vida)}</div>
              <div class="fcp-left-kpi-sub">Usos: {_fcp_fmt(usos_vida)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("##### 🚨 Alertas")

        # Alerta 1: Negativos en caja
        if meses_negativos:
            st.markdown(
                f"""
                <div class="fcp-alert alert-crit">
                  <div class="alert-title">📉 Caja negativa</div>
                  <div class="alert-value">{len(meses_negativos)} mes(es)</div>
                  <div class="alert-meta">
                    Peor: <b>{peor_mes[0]}</b><br/>
                    Mínimo: <b>{_fcp_fmt(peor_mes[1])}</b>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="fcp-alert alert-ok">
                  <div class="alert-title">✅ Caja siempre positiva</div>
                  <div class="alert-meta">No se detectan meses con caja proyectada negativa.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Alerta 2: descuadre F&U
        if abs(check_fyu) >= 100_000:
            st.markdown(
                f"""
                <div class="fcp-alert alert-warn">
                  <div class="alert-title">⚠️ F&amp;U no cuadra</div>
                  <div class="alert-value">{_fcp_fmt(check_fyu)}</div>
                  <div class="alert-meta">Σ Fuentes − Σ Usos del proyecto total</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Alerta 3: exposición máxima
        if meses_negativos:
            exp_max = abs(peor_mes[1])
            st.markdown(
                f"""
                <div class="fcp-alert alert-warn">
                  <div class="alert-title">💸 Exposición máx.</div>
                  <div class="alert-value">{_fcp_fmt(exp_max)}</div>
                  <div class="alert-meta">Capital máximo requerido para cubrir el déficit.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Alerta 4: ratio del corte (% de la vida ya ejecutado)
        if abs(fuentes_vida) > 0:
            pct_real = abs(fuentes_real) / abs(fuentes_vida) * 100
            st.markdown(
                f"""
                <div class="fcp-alert">
                  <div class="alert-title">📈 Avance al corte</div>
                  <div class="alert-value">{pct_real:.1f}%</div>
                  <div class="alert-meta">de los ingresos totales del proyecto ya ejecutados.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ─────────────────────────────────────────────
    # COLUMNA CENTRAL · TABLA DE TRAMOS CON GRUPOS
    # ─────────────────────────────────────────────
    with col_center:
        # Header con título y botones expandir/colapsar
        ttl_a, ttl_b = st.columns([3, 1.4])
        with ttl_a:
            st.markdown("##### 📋 Tabla de Tramos · Realidad vs Proyección")
        with ttl_b:
            _exp_state_key = "fcp_groups_expanded"
            if _exp_state_key not in st.session_state:
                st.session_state[_exp_state_key] = "default"
            ecol1, ecol2 = st.columns(2)
            with ecol1:
                if st.button("▼ Expandir", key="fcp_btn_exp", use_container_width=True):
                    st.session_state[_exp_state_key] = "open"
                    st.rerun()
            with ecol2:
                if st.button("▶ Colapsar", key="fcp_btn_col", use_container_width=True):
                    st.session_state[_exp_state_key] = "closed"
                    st.rerun()

        _open_mode = st.session_state.get(_exp_state_key, "default")

        def _open_attr(default_open: bool) -> str:
            if _open_mode == "open":
                return "open"
            if _open_mode == "closed":
                return ""
            return "open" if default_open else ""

        # ── Header en CSS grid (RUBRO ocupa rowspan = 2) ──
        header_html = ['<div class="fcp-sticky-header"><div class="fcp-header-grid">']
        # Fila 1
        header_html.append(
            f'<div class="fcp-hcell fcp-h-rubro" style="grid-area: 1 / 1 / span 2 / 2;">RUBRO</div>'
            f'<div class="fcp-hcell fcp-tramo-end" style="grid-area: 1 / 2 / 2 / 4;">📍 Real ≤ {fcp_corte}</div>'
            f'<div class="fcp-hcell fcp-tramo-end" style="grid-area: 1 / 4 / 2 / 6;">⏱️ {fcp_corte} → {fcp_hito}</div>'
            f'<div class="fcp-hcell fcp-tramo-end" style="grid-area: 1 / 6 / 2 / 8;">📅 &gt; {fcp_hito}</div>'
            f'<div class="fcp-hcell" style="grid-area: 1 / 8 / 2 / 10;">🏁 Total Vida</div>'
        )
        # Fila 2 (sub-encabezados U/F)
        sub_headers = [
            (2, "fcp-h-uso", "Usos"),    (3, "fcp-h-fuente fcp-tramo-end", "Fuentes"),
            (4, "fcp-h-uso", "Usos"),    (5, "fcp-h-fuente fcp-tramo-end", "Fuentes"),
            (6, "fcp-h-uso", "Usos"),    (7, "fcp-h-fuente fcp-tramo-end", "Fuentes"),
            (8, "fcp-h-uso", "Usos"),    (9, "fcp-h-fuente", "Fuentes"),
        ]
        for col_n, extra_cls, lbl in sub_headers:
            header_html.append(
                f'<div class="fcp-hcell fcp-h-sub {extra_cls}" style="grid-area: 2 / {col_n} / 3 / {col_n + 1};">{lbl}</div>'
            )
        header_html.append('</div></div>')
        st.markdown("".join(header_html), unsafe_allow_html=True)

        # ── Helpers de renderizado en CSS grid ──
        def _num_gcell(v, lado_linea, lado_col, is_end_tramo):
            classes = "fcp-gcell fcp-num"
            if lado_col == "U":
                classes += " fcp-uso"
            else:
                classes += " fcp-fuente"
                if is_end_tramo:
                    classes += " fcp-tramo-end"
            # Línea informativa: usa la columna Fuentes para mostrar el dato
            if lado_linea == "I":
                if lado_col == "F":
                    if abs(v) < 1:
                        return f'<div class="{classes} fcp-empty">—</div>'
                    sign = "-" if v < 0 else ""
                    return f'<div class="{classes}">{sign}${abs(v):,.0f}</div>'
                return f'<div class="{classes} fcp-empty">—</div>'
            # Fuente o Uso: solo aparece en su columna
            if lado_linea != lado_col:
                return f'<div class="{classes} fcp-empty">—</div>'
            if abs(v) < 1:
                return f'<div class="{classes} fcp-empty">—</div>'
            return f'<div class="{classes}">${abs(v):,.0f}</div>'

        def _row_cells_8_num(d):
            """Devuelve los 8 divs numéricos (U/F × 4 tramos)."""
            lado = d["lado"]
            tramos = [("real", True), ("proy_cerc", True), ("pend", True), ("total", False)]
            cells = []
            for tk, is_end in tramos:
                v = d[tk]
                cells.append(_num_gcell(v, lado, "U", False))
                cells.append(_num_gcell(v, lado, "F", is_end))
            return "".join(cells)

        def _grid_row_for_data(d, row_classes_extra="", with_caret=False):
            l = d["linea"]
            classes = "fcp-grid-row " + row_classes_extra
            # Rubro (con caret opcional si está en summary)
            caret = '<span class="fcp-caret"></span>' if with_caret else ""
            nombre = f'{caret}<b>{l.indice}</b> · {l.nombre}'
            rubro_cell = f'<div class="fcp-gcell fcp-rubro">{nombre}</div>'
            return f'<div class="{classes.strip()}">{rubro_cell}{_row_cells_8_num(d)}</div>'

        def _row_class_for_line(d):
            l = d["linea"]
            if l.indice in ("9.0", "10.0", "16.0", "16.1"):
                return "fcp-row-grand-total"
            if l.indice.endswith(".0"):
                return "fcp-row-subtotal"
            if d["lado"] == "I":
                return "fcp-row-info"
            if len(l.indice.split(".")) > 2:
                return "fcp-row-item fcp-row-subitem"
            return "fcp-row-item"

        # ── Render grupos ──
        indices_usados = set()
        for gid, titulo, pertenece in FCP_GRUPOS:
            lineas_grupo = sorted(
                [d for idx, d in fcp_data.items() if pertenece(idx) and idx not in indices_usados],
                key=lambda d: [int(p) if p.isdigit() else p for p in d["linea"].indice.split(".")],
            )
            if not lineas_grupo:
                continue

            # Marcar todas las líneas como usadas
            for d in lineas_grupo:
                indices_usados.add(d["linea"].indice)

            # Grupos sin colapso: total_op, total_fon → solo las líneas grand-total
            is_grand_group = gid in ("total_op", "total_fon")
            if is_grand_group:
                block = ['<div class="fcp-standalone-group">']
                for d in lineas_grupo:
                    cls = _row_class_for_line(d)
                    block.append(_grid_row_for_data(d, cls, with_caret=False))
                block.append('</div>')
                st.markdown("".join(block), unsafe_allow_html=True)
                continue

            # Separar línea subtotal `.0` del grupo (cabecera del details) de los sub-ítems
            subtotal_line = next(
                (d for d in lineas_grupo if d["linea"].indice.endswith(".0")),
                None,
            )
            sub_lineas = [d for d in lineas_grupo if d is not subtotal_line]

            default_open = gid in ("ingresos", "lote", "costo_dir", "honorarios",
                                   "credito", "aportes_ic")
            open_attr = _open_attr(default_open)

            # Si hay subtotal: summary muestra la fila subtotal con caret. Si NO hay (raro),
            # se genera una pseudo-fila con el título del grupo.
            grp = [f'<details class="fcp-group-d" {open_attr}>']
            if subtotal_line is not None:
                summary_row_cls = "fcp-row-subtotal"
                grp.append('<summary>')
                grp.append(_grid_row_for_data(subtotal_line, summary_row_cls, with_caret=True))
                grp.append('</summary>')
            else:
                # Pseudo-fila de cabecera con el título del grupo (sin valores)
                empty_num = '<div class="fcp-gcell fcp-num fcp-empty">—</div>' * 8
                grp.append(
                    '<summary>'
                    '<div class="fcp-grid-row fcp-row-subtotal">'
                    f'<div class="fcp-gcell fcp-rubro"><span class="fcp-caret"></span>{titulo}</div>'
                    f'{empty_num}'
                    '</div>'
                    '</summary>'
                )

            # Contenido interno (sub-ítems)
            for d in sub_lineas:
                cls = _row_class_for_line(d)
                grp.append(_grid_row_for_data(d, cls, with_caret=False))
            grp.append('</details>')
            st.markdown("".join(grp), unsafe_allow_html=True)

        # ── Pie: CAJA y CHECK ──
        check_class = "fcp-row-check-ok" if abs(check_fyu) < 100_000 else "fcp-row-check-bad"
        check_msg = "✅ Cuadra" if abs(check_fyu) < 100_000 else f"⚠️ Diferencia: {_fcp_fmt_full(check_fyu)}"

        # Fila CAJA (con valores en columnas Fuentes de Real y Hito)
        caja_cells = [
            '<div class="fcp-gcell fcp-rubro">💰 CAJA AL CORTE</div>',
            '<div class="fcp-gcell fcp-num fcp-empty">—</div>',  # Real Usos
            f'<div class="fcp-gcell fcp-num fcp-tramo-end">{_fcp_fmt_full(caja_corte)}</div>',  # Real F
            '<div class="fcp-gcell fcp-num fcp-empty">—</div>',  # Hito Usos
            f'<div class="fcp-gcell fcp-num fcp-tramo-end">{_fcp_fmt_full(caja_hito_est - caja_corte)}</div>',
            '<div class="fcp-gcell fcp-num fcp-empty">—</div>',
            '<div class="fcp-gcell fcp-num fcp-empty fcp-tramo-end">—</div>',
            '<div class="fcp-gcell fcp-num fcp-empty">—</div>',
            '<div class="fcp-gcell fcp-num fcp-empty">—</div>',
        ]
        st.markdown(
            '<div class="fcp-grid-row fcp-row-caja">' + "".join(caja_cells) + '</div>',
            unsafe_allow_html=True,
        )

        # Fila CHECK F&U — usa grid pero el mensaje ocupa todas las columnas numéricas
        check_cells = (
            '<div class="fcp-gcell fcp-rubro">🧮 CHECK F&amp;U  '
            '<span style="font-weight:400;">(Σ Fuentes − Σ Usos del proyecto)</span></div>'
            f'<div class="fcp-gcell fcp-num" style="grid-column: 2 / 10; justify-content: center;">{check_msg}</div>'
        )
        st.markdown(
            f'<div class="fcp-grid-row {check_class}">{check_cells}</div>',
            unsafe_allow_html=True,
        )

    # ─────────────────────────────────────────────
    # COLUMNA DERECHA · FLUJO MENSUAL NAVEGABLE
    # ─────────────────────────────────────────────
    with col_right:
        st.markdown("##### 📅 Flujo Mensual Navegable")

        # Sincronizar con el estado de expansión del centro
        # - "closed"  → solo líneas .0 (subtotales del grupo + grand totals)
        # - "open"    → todas las líneas
        # - "default" → todas las líneas (igual que "open" en este panel)
        if _open_mode == "closed":
            def _incluir_idx(idx):
                return idx.endswith(".0")
            _sync_lbl = "🗜️ Vista colapsada (subtotales)"
        else:
            def _incluir_idx(idx):
                return True
            _sync_lbl = "📖 Vista expandida (todas las líneas)"

        st.caption(
            f"{_sync_lbl} — sincronizado con la tabla central. "
            f"Scroll horizontal en los {len(fechas_ord)} periodos."
        )

        # Construir DataFrame: filas = líneas (con índice + nombre), columnas = meses
        rows_data = []
        row_labels = []
        for indice in sorted(fcp_data.keys(),
                             key=lambda k: [int(p) if p.isdigit() else p for p in k.split(".")]):
            if not _incluir_idx(indice):
                continue
            d = fcp_data[indice]
            l = d["linea"]
            lado_lbl = {"U": "🔴 U", "F": "🟢 F", "I": "ℹ️ I"}[d["lado"]]
            row_labels.append(f"{lado_lbl}  {l.indice}  {l.nombre}")
            row = {f: l.valores.get(f, 0.0) for f in fechas_ord}
            row["TOTAL"] = l.total_periodo
            rows_data.append(row)

        df_mensual = pd.DataFrame(rows_data, index=row_labels,
                                  columns=fechas_ord + ["TOTAL"])

        # Formato condicional: corte resaltado, valores negativos en rojo, totales bold
        corte_str = fcp_corte.isoformat()
        hito_str  = fcp_hito.isoformat()

        def _color_celda(v):
            if pd.isna(v) or v == 0:
                return "color: #d8d8d8;"
            if v < 0:
                return "color: #c0392b; font-weight: 600;"
            return ""

        def _highlight_corte_hito(col):
            # Resalta columnas de meses críticos (corte y hito)
            colname = str(col.name) if hasattr(col, "name") else ""
            if colname == corte_str:
                return ["background-color: #fde7e7; border-left: 2px solid #c0392b;"] * len(col)
            if colname == hito_str:
                return ["background-color: #fff7e6; border-left: 2px solid #d4a45a;"] * len(col)
            if colname == "TOTAL":
                return ["background-color: #ecdfdf; font-weight: 700; border-left: 2px solid #681E1E;"] * len(col)
            return [""] * len(col)

        styled = df_mensual.style.format("${:,.0f}").map(_color_celda).apply(_highlight_corte_hito, axis=0)
        st.dataframe(
            styled,
            use_container_width=True,
            height=720,
        )

        # Mini-leyenda del panel derecho
        st.caption(
            "🟢 Fuente · 🔴 Uso · ℹ️ Informativo  ·  "
            f"📍 Resaltado: corte ({corte_str}) y hito ({hito_str})"
        )

    # ─────────────────────────────────────────────
    # PIE DE PÁGINA · LEYENDA Y EXPORT
    # ─────────────────────────────────────────────
    st.markdown("---")
    pie1, pie2, pie3, pie_exp = st.columns([1, 1, 1, 1.2])
    with pie1:
        st.markdown(
            f"""
            <div style="padding:0.6rem 0.9rem; background:#f5e8e8; border-radius:8px; font-size:0.78rem;">
              <b>📍 Real al corte:</b> meses ≤ <b>{fcp_corte}</b>. Valor ejecutado, ya no cambia.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with pie2:
        st.markdown(
            f"""
            <div style="padding:0.6rem 0.9rem; background:#e6f8ee; border-radius:8px; font-size:0.78rem;">
              <b>⏱️ Corte → Hito:</b> entre <b>{fcp_corte}</b> y <b>{fcp_hito}</b>. Proyección cercana.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with pie3:
        st.markdown(
            f"""
            <div style="padding:0.6rem 0.9rem; background:#fff7e6; border-radius:8px; font-size:0.78rem;">
              <b>📅 Pendiente al cierre:</b> meses &gt; <b>{fcp_hito}</b>. Largo plazo.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with pie_exp:
        export_rows = []
        for _, _, pertenece in FCP_GRUPOS:
            for indice in sorted(fcp_data.keys(),
                                 key=lambda k: [int(p) if p.isdigit() else p for p in k.split(".")]):
                if not pertenece(indice):
                    continue
                d = fcp_data[indice]
                l = d["linea"]
                lado_lbl = {"U": "Uso", "F": "Fuente", "I": "Informativo"}[d["lado"]]
                export_rows.append({
                    "Índice": l.indice,
                    "Rubro": l.nombre,
                    "Lado": lado_lbl,
                    "Real al corte": d["real"],
                    "Corte → Hito": d["proy_cerc"],
                    "Pendiente al cierre": d["pend"],
                    "Total Vida": d["total"],
                })
        if export_rows:
            df_export = pd.DataFrame(export_rows)
            csv = df_export.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇️ Exportar tabla CSV",
                data=csv,
                file_name=f"FCxPROYECTO_{fcp_proy}_{fcp_corte}.csv",
                mime="text/csv",
                use_container_width=True,
            )


# ═════════════════════════════════════════════
# MÓDULO 6 — COMPARACIÓN DE PROYECTOS
# ═════════════════════════════════════════════

elif modulo == "🆚 Comparación Proyectos":
    st.title("🆚 Comparación de Proyectos")
    st.markdown(
        "Selecciona **dos grupos** de proyectos/etapas y compara sus "
        "factibilidades (P&G) lado a lado, con la **diferencia** en los valores "
        "consolidados (Grupo A − Grupo B)."
    )
    st.divider()

    if not st.session_state.records:
        st.warning("⚠️ Primero carga la Base de Datos en el módulo **📂 Cargar Base**.")
        st.stop()

    resp = st.session_state.upload_response

    def _fechas_comunes(grupo):
        sets = [set(resp.fechas_datos.get(p, [])) for p in grupo]
        return sorted(set.intersection(*sets), reverse=True) if sets else []

    selA, selB = st.columns(2)
    with selA:
        st.markdown("#### 🅰️ Grupo A")
        grpA = st.multiselect("Proyectos A", resp.proyectos,
                              default=resp.proyectos[:1], key="cmp_A_proy")
        fa_com = _fechas_comunes(grpA)
        if grpA and not fa_com:
            st.warning("⚠️ No hay corte común a los proyectos del Grupo A.")
        fechaA = st.selectbox("Corte A", fa_com, key="cmp_A_fecha") if fa_com else None
    with selB:
        st.markdown("#### 🅱️ Grupo B")
        _defB = resp.proyectos[1:2] if len(resp.proyectos) > 1 else resp.proyectos[:1]
        grpB = st.multiselect("Proyectos B", resp.proyectos,
                              default=_defB, key="cmp_B_proy")
        fb_com = _fechas_comunes(grpB)
        if grpB and not fb_com:
            st.warning("⚠️ No hay corte común a los proyectos del Grupo B.")
        fechaB = st.selectbox("Corte B", fb_com, key="cmp_B_fecha") if fb_com else None

    _cmp_disabled = not (grpA and fechaA and grpB and fechaB)
    if st.button("📊 Comparar factibilidades", type="primary", disabled=_cmp_disabled):
        st.session_state["cmp_run"] = True

    if st.session_state.get("cmp_run") and not _cmp_disabled:
        try:
            with st.spinner("Reconstruyendo factibilidades…"):
                fa_obj, fa_ver = parse_fecha_label(fechaA)
                fb_obj, fb_ver = parse_fecha_label(fechaB)
                snapsA = [_build_snapshot(p, fa_obj, fa_ver) for p in grpA]
                snapsB = [_build_snapshot(p, fb_obj, fb_ver) for p in grpB]

                # Estructura común (unión) para que las filas se alineen.
                struct, dev = pyg_estructura(snapsA + snapsB, builder)
                col_defs_A, filas_A = pyg_filas(struct, dev, snapsA, builder)
                col_defs_B, filas_B = pyg_filas(struct, dev, snapsB, builder)

            ventas_A = filas_A[0]["vals"][0] or 1.0
            ventas_B = filas_B[0]["vals"][0] or 1.0
            _rcls = {"header": "r-header", "subtotal": "r-sub", "result": "r-res",
                     "italic": "r-ital", "subitem": "r-subi", "negative": "r-neg"}

            def _label_html(f, ventas):
                pct = (f["vals"][0] / ventas * 100) if ventas else 0.0
                lab = f["label"]
                tipo = f["tipo"]
                if tipo == "header":
                    return f"<strong>{lab}</strong>"
                if tipo in ("subtotal", "result"):
                    return f"<strong>{lab}: {pct:.2f}%</strong>"
                if tipo == "italic":
                    return f"<em>{lab}: {pct:.2f}%</em>"
                if tipo == "negative":
                    return f"{lab}: {abs(pct):.2f}%"
                return f"{lab}: {pct:.2f}%"

            def _tabla_grupo_html(col_defs, filas, ventas, titulo):
                head = (f'<th class="lbl">{titulo}</th>'
                        + "".join(f"<th>{nm}</th>" for _s, nm in col_defs))
                body = ""
                for f in filas:
                    cls = _rcls.get(f["tipo"], "")
                    cells = f'<td class="lbl">{_label_html(f, ventas)}</td>'
                    for i, v in enumerate(f["vals"]):
                        extra = " cons" if i == 0 else ""
                        cells += f'<td class="num{extra}">{_pyg_fmt_num(v)}</td>'
                    body += f'<tr class="{cls}">{cells}</tr>'
                return (f'<table class="cmp-tbl"><thead><tr>{head}</tr></thead>'
                        f'<tbody>{body}</tbody></table>')

            def _tabla_diff_html(filas_a, filas_b):
                body = ""
                for fa, fb in zip(filas_a, filas_b):
                    cls = _rcls.get(fa["tipo"], "")
                    d = fa["vals"][0] - fb["vals"][0]
                    pn = "pos" if d >= 0 else "neg"
                    body += (f'<tr class="{cls}"><td class="num {pn}">'
                             f'{_pyg_fmt_num(d)}</td></tr>')
                return (f'<table class="cmp-tbl cmp-diff"><thead><tr>'
                        f'<th>Diferencia (A−B)</th></tr></thead>'
                        f'<tbody>{body}</tbody></table>')

            _cmp_css = """<style>
              .cmp-wrap{overflow-x:auto;padding-bottom:6px;}
              .cmp-row{display:flex;gap:14px;align-items:flex-start;width:max-content;}
              .cmp-tbl{border-collapse:collapse;font-size:14px;font-family:'Inter',sans-serif;}
              .cmp-tbl th,.cmp-tbl td{padding:7px 12px;border-bottom:1px solid #eee;white-space:nowrap;}
              .cmp-tbl thead th{background:#681E1E;color:#fff;text-align:right;font-weight:700;}
              .cmp-tbl thead th.lbl{text-align:left;}
              .cmp-tbl td.lbl{text-align:right;font-weight:500;color:#333;}
              .cmp-tbl td.num{text-align:right;font-variant-numeric:tabular-nums;}
              .cmp-tbl td.cons{background:#ececec;font-weight:700;}
              .cmp-tbl tr.r-header td,.cmp-tbl tr.r-sub td,.cmp-tbl tr.r-res td{font-weight:700;}
              .cmp-tbl tr.r-sub td{border-top:1px solid #b0b0b0;}
              .cmp-tbl tr.r-ital td{font-style:italic;}
              .cmp-tbl tr.r-subi td{color:#9a9a9a;font-style:italic;}
              .cmp-tbl tr.r-neg td.num{color:#c0392b;}
              .cmp-diff td.num.pos{color:#1F7A44;font-weight:700;}
              .cmp-diff td.num.neg{color:#c0392b;font-weight:700;}
            </style>"""

            _titA = " + ".join(grpA)
            _titB = " + ".join(grpB)
            html = (_cmp_css + '<div class="cmp-wrap"><div class="cmp-row">'
                    + _tabla_grupo_html(col_defs_A, filas_A, ventas_A, f"🅰️ {_titA}")
                    + _tabla_grupo_html(col_defs_B, filas_B, ventas_B, f"🅱️ {_titB}")
                    + _tabla_diff_html(filas_A, filas_B)
                    + '</div></div>')
            st.markdown(html, unsafe_allow_html=True)
            st.caption(f"Grupo A: {_titA} · corte {fechaA}  |  "
                       f"Grupo B: {_titB} · corte {fechaB}")

            # ── Indicadores TIR + cronograma de hitos bajo cada factibilidad ──
            tirfco_A, tirk_A = cmp_tirs(snapsA, builder)
            tirfco_B, tirk_B = cmp_tirs(snapsB, builder)
            gruposA, ordenA = cmp_hitos(snapsA, builder)
            gruposB, ordenB = cmp_hitos(snapsB, builder)

            _hitos_css = """<style>
              .hcmp{border-collapse:collapse;width:100%;font-family:'Inter',sans-serif;font-size:13px;}
              .hcmp thead th{background:#681E1E;color:#fff;font-weight:700;text-align:left;padding:6px 9px;}
              .hcmp td{padding:5px 9px;border-bottom:1px solid #eee;}
              .hcmp td.hp{font-weight:700;color:#681E1E;background:#faf6f6;
                          border-right:1px solid #e2d6d6;vertical-align:middle;}
              .hcmp tr.grp-top td{border-top:2.5px solid #681E1E;}
            </style>"""

            def _tir_html(tfco, tk):
                return (
                    '<div style="display:flex;gap:10px;margin:6px 0 10px;">'
                    f'<div class="kpi-box" style="flex:1"><div class="kpi-label">TIR FCO</div>'
                    f'<div class="kpi-value">{_cmp_fmt_tir(tfco)}</div>'
                    '<div class="kpi-sub">Operativa · sin financieros</div></div>'
                    f'<div class="kpi-box" style="flex:1"><div class="kpi-label">TIR K</div>'
                    f'<div class="kpi-value">{_cmp_fmt_tir(tk)}</div>'
                    '<div class="kpi-sub">Capital · aportes/reintegros IC</div></div>'
                    '</div>'
                )

            def _hitos_html(grupos, orden):
                if not orden:
                    return '<p style="color:#888;font-size:13px;">Sin hitos de cronograma (17.1/3.22/18.1).</p>'
                rows = ""
                for p in orden:
                    g = grupos[p]
                    for ri, (hi, ini, fn, du) in enumerate(g):
                        cls = ' class="grp-top"' if ri == 0 else ""
                        pcell = f'<td class="hp" rowspan="{len(g)}">{p}</td>' if ri == 0 else ""
                        rows += (f'<tr{cls}>{pcell}<td>{hi}</td><td>{ini}</td>'
                                 f'<td>{fn}</td><td>{du}</td></tr>')
                return (_hitos_css + '<table class="hcmp"><thead><tr>'
                        '<th>Proyecto</th><th>Hito</th><th>Inicio</th>'
                        '<th>Fin</th><th>Duración</th></tr></thead>'
                        f'<tbody>{rows}</tbody></table>')

            st.divider()
            cgA, cgB = st.columns(2)
            with cgA:
                st.markdown(f"##### 🅰️ {_titA}")
                st.markdown(_tir_html(tirfco_A, tirk_A), unsafe_allow_html=True)
                st.markdown("**📅 Cronograma — Hitos**")
                st.markdown(_hitos_html(gruposA, ordenA), unsafe_allow_html=True)
            with cgB:
                st.markdown(f"##### 🅱️ {_titB}")
                st.markdown(_tir_html(tirfco_B, tirk_B), unsafe_allow_html=True)
                st.markdown("**📅 Cronograma — Hitos**")
                st.markdown(_hitos_html(gruposB, ordenB), unsafe_allow_html=True)
        except Exception as _e_cmp:
            import traceback
            st.error(f"❌ Error al comparar: {_e_cmp}")
            st.code(traceback.format_exc())
