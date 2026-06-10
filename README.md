---
title: Estate Auditor
emoji: 🏢
colorFrom: red
colorTo: gray
sdk: streamlit
sdk_version: "1.35.0"
app_file: app.py
pinned: false
---

# 🏢 Estate Auditor — IC Constructora

Plataforma modular de análisis financiero inmobiliario.

## Módulos Disponibles (MVP)

| Módulo | Descripción |
|--------|-------------|
| 📂 **Cargar Base** | Carga el archivo Excel histórico versionado. Es la fuente única de datos para todos los módulos. |
| 🔍 **Auditoría** | Motor de validación automática de flujos de caja. Detecta inconsistencias matemáticas y financieras. |
| 📈 **Reporte Inversionista** | Dashboard con Ventas Totales, Utilidad (FCO), TIR Operativa, TIR del Inversionista y gráfico de Flujo de Caja del Inversionista. |

## Formato de la BASE

El archivo Excel debe tener una hoja con las siguientes columnas:

| Columna | Descripción |
|---------|-------------|
| `Proyecto` | Nombre del proyecto |
| `Fecha_Datos` | Fecha de corte / versión del snapshot |
| `Fecha_Flujo` | Mes al que corresponde el valor |
| `Indice` | Índice estructural (`1.0`, `10.0`, `13.2`, etc.) |
| `Nombre_Linea` | Nombre descriptivo de la línea |
| `Participacion` | `total`, `ic` o `socio` |
| `Valor` | Valor numérico |

## Líneas Requeridas para Reporte Inversionista

- `1.0 Ingresos` (o prefijo `1.0`)
- `10.0 FCO`
- `13.2 Aportes IC`
- `13.4 Reintegros IC`
