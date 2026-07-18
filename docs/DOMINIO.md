# Dominio: factibilidad inmobiliaria de IC Constructora

## Contexto de negocio

IC Constructora desarrolla proyectos inmobiliarios en Colombia (vivienda VIS y no VIS,
comercio, oficinas). Cada **proyecto/etapa** tiene un **modelo de factibilidad**: un flujo
de caja mensual proyectado con su P&G (Pérdidas y Ganancias), del cual se derivan
indicadores de retorno para la compañía (IC) y para el socio dueño del lote.

Conceptos clave:

- **Proyecto / etapa:** unidad de análisis (p. ej. "Brizza VIS E1", "Anapoima E2"). La
  base tiene 59.
- **Fecha de datos / corte (`fecha_datos`):** versión del snapshot del modelo (un corte
  mensual). Cada `(proyecto, fecha_datos)` es un universo aislado; NO se mezcla con otros
  cortes. Cuando hay varios archivos para el mismo corte se numeran con sufijo `-2`, `-3`.
- **Fecha de flujo (`fecha_flujo`):** el mes al que corresponde un valor dentro del flujo.
- **Fuente:** `Proyectos` (control real de obra) vs `Estructuración` (modelo de factibilidad).
- **Participación:** `total` | `ic` (la compañía) | `socio` (dueño del lote / aportante).

## Estructura del P&G (`pyg_struct` en app.py)

Orden y agrupación de líneas del P&G que arma la app:

- **Ventas** (índice `1.0`)
- **Lote** (subíndices `2.x`, incl. `2.22 Lote Bruto`, relacionados del lote)
- **Costo Directo** (`3.0`, incl. `3.22` Construcción/Obra)
- **- Iva** (`7.0`)
- **Honorarios** (`5.0` y subíndices, con variantes IC/Socio)
- **Indirectos** (`4.x`: Estudios y Diseños, Comerciales y Mercadeo, Impuestos y Seguros,
  Operativos y Legales)
- **Totales calculados:** Total Costos (`9.0 = 9.0 - 6.0` según convención del modelo),
  Utilidad Operativa (FCO), Financieros, Utilidad, Capital Requerido (`13.2 + 14.2`).

## Tabla de índices de línea (referencia)

| Índice | Línea | Notas |
|--------|-------|-------|
| `1.0`  | Ingresos / Ventas | base para % del P&G |
| `2.22` | Lote Bruto | usada sola para la gráfica "Forma de pago Lote" (no sumar relacionados) |
| `3.22` | Costo Directo Construcción / Obra | |
| `5.22 / 5.42 / 5.62 / 5.82` | Honorarios IC (Construcción/Comercialización/Gerencia/Estructuración) | sufijo define participación IC vs Socio |
| `6.x`  | Financieros (F. Constructor intereses, etc.) | |
| `9.0`  | Total Costos | |
| `10.0` | FCO (Flujo de Caja Operativo) | |
| `11.0` | Saldo Crédito | **saldo acumulado** (ver anualización) |
| `12.x` | Aportes (IC/Socio) según modelo | |
| `13.2` | Aportes IC | |
| `13.4` | Reintegros IC | |
| `14.2` | Aportes Socio | |
| `16.0` | FCL (Flujo de Caja Libre) | |
| `16.1` | FCL Acumulado | **saldo acumulado** (ver anualización) |
| `17.1` | Ventas Vivienda (Unidades) | soporte, no monetario |
| `17.3` | m² vendible | soporte |
| `18.1` | Escrituraciones | soporte |
| `19.0` | Fuentes y Usos | |
| `20.0` | Necesidad de Capital | |

> Nota: los índices y nombres provienen del texto de la columna `P&G` del consolidador,
> que combina `"<índice> <descripción>"`. El parser los separa.

### Anualización de saldos acumulados

En la vista **Anual** del Flujo de Caja, las líneas que son **saldos acumulados** NO se
suman: su valor anual es el **saldo de cierre** (valor del último mes del año), y el TOTAL
es el saldo del último mes con dato. Actualmente aplica a **`11.0` (Saldo Crédito)** y
**`16.1` (FCL Acumulado)**. El resto de líneas (flujos) sí se suman. La vista Mensual
muestra el saldo de cada mes tal cual.

## Indicadores

- **TIR FCO** (operativa): XIRR sobre el FCO (a veces FCO + financieros). No depende de la
  estructura de capital.
- **TIR K** (capital): XIRR sobre el flujo de aportes/reintegros de IC (`13.2`, `13.4`).
- **XIRR anualizada:** se calcula con un barrido de cambio de signo de la TIR (hasta
  valores muy altos) + bisección, porque algunos proyectos tienen TIR > 1000% y los
  métodos ingenuos fallan (dan N/A). Ver `_cmp_xirr` / `xirr` en `app.py`.
- **Factibilidad (tab):** dashboard compacto por categorías (Arquitectura, Ventas, Costos,
  Financiero/Equity) con indicadores del P&G + indicadores **manuales** editables (área
  lote, Vr m² lote, área vendible/construida, eficiencia, costo directo por m² con/sin
  imp/inc, etc.). Los manuales se guardan por "firma" de selección de proyectos.
- **Equity IC / Socio, Honorarios IC / Socio, Margen FCO/Operativo:** derivados del P&G.

## Cronograma / hitos

Cada proyecto tiene hitos: **Ventas** (17.1), **Obra** (3.22), **Entregas** (18.1), con
inicio, fin y duración en meses. Se muestran como Gantt (tab Cronograma) y como tablas de
hitos (en Comparación).
