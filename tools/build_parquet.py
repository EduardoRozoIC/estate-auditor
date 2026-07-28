"""
build_parquet.py — Regenera data/base.parquet desde un Excel fuente.
=====================================================================
La app en la nube lee SOLO data/base.parquet (ver docs/DESPLIEGUE.md y
docs/ARQUITECTURA.md). Este script convierte el Excel fuente del consolidador
en ese parquet compacto, limpiando filas basura y asignando la columna `version`.

Soporta archivos con UNA o VARIAS hojas válidas (mismo esquema
Proyecto/Fecha Datos/Fuente/P&G/TOTAL/Fecha/Valor). Ejemplos vistos:
  - Un solo consolidador: hoja "ERConsolidado" (o "Pipeline.xlsx" con "Consolidado").
  - Consolidador con DOS hojas: "HistoricoConsolidado" (proyectos en control/obra,
    Fuente="Proyectos") + "ER_Pipeline" (proyectos en estructuración,
    Fuente="Estructuración"). Se detectan automáticamente TODAS las hojas con el
    esquema válido — no hace falta indicar nombres.

Versionado cuando dos hojas comparten (proyecto, fecha_datos): igual que
`backend/folder_loader.py` para archivos múltiples — cada hoja se procesa en el
orden en que aparece en el libro y los solapes se numeran como sub-versiones
(1, 2, …), quedando AMBAS disponibles y seleccionables por separado en la app
(p. ej. "2026-04-01" y "2026-04-01-2") — nunca se mezclan ni se descarta ninguna.

NO subir el .xlsx al repo — parsearlo en la nube dispara la RAM (>600MB) y tumba
el contenedor (OOM). Solo se versiona el .parquet resultante.

Uso:
    py tools/build_parquet.py "C:\\ruta\\al\\archivo.xlsx"
    py tools/build_parquet.py "archivo.xlsx" --out data/base.parquet

Después:
    git add data/base.parquet && git commit -m "data: actualizar base.parquet" && git push
"""

import sys
import argparse
from pathlib import Path

# Hacer importable el backend (este script vive en tools/)
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd  # noqa: E402
from backend.parser_excel_v2 import ExcelBaseParser  # noqa: E402


def _hojas_validas(xlsx_path: Path, data: bytes):
    """Devuelve [(nombre_hoja, DataFrame_limpio)] para cada hoja con el esquema
    esperado, en el orden en que aparecen en el libro."""
    sheet_names = pd.ExcelFile(xlsx_path, engine="openpyxl").sheet_names
    resultado = []
    for sheet in sheet_names:
        parser = ExcelBaseParser(sheet_name=sheet)
        df, warnings, errors = parser.parse_dataframe(data)
        if errors or df is None or df.empty:
            motivo = "; ".join(errors) if errors else "vacía o sin columnas válidas"
            print(f"  hoja omitida '{sheet}': {motivo}")
            continue
        for w in warnings:
            print(f"  [{sheet}] aviso: {w}")
        resultado.append((sheet, df))
    return resultado


def _asignar_version(hojas):
    """Concatena las hojas asignando `version` acumulada por (proyecto, fecha_datos),
    igual que folder_loader.load_database_from_folder para archivos múltiples."""
    version_counter = {}
    frames = []
    for sheet, df in hojas:
        df = df.copy()
        keys = df[["proyecto", "fecha_datos"]].drop_duplicates()
        vmap = {}
        for pr, fd in zip(keys["proyecto"], keys["fecha_datos"]):
            v = version_counter.get((pr, fd), 0) + 1
            version_counter[(pr, fd)] = v
            vmap[(pr, fd)] = v
        df["version"] = [vmap[(pr, fd)] for pr, fd in zip(df["proyecto"], df["fecha_datos"])]
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def build(xlsx_path: Path, out_path: Path) -> None:
    if not xlsx_path.exists():
        raise FileNotFoundError(f"No existe el Excel: {xlsx_path}")

    print(f"Leyendo {xlsx_path.name} …")
    data = xlsx_path.read_bytes()

    hojas = _hojas_validas(xlsx_path, data)
    if not hojas:
        raise ValueError("Ninguna hoja del Excel tiene el esquema esperado.")

    print(f"Hojas válidas detectadas: {[s for s, _ in hojas]}")
    df = _asignar_version(hojas)
    df["version"] = pd.to_numeric(df["version"], downcast="unsigned")

    n_solapes = int((df.groupby(["proyecto", "fecha_datos"])["version"].transform("max") > 1).sum())
    if n_solapes:
        print(f"  aviso: {n_solapes} filas con sub-versión (mismo proyecto+corte en >1 hoja) — "
              f"quedan ambas disponibles en la app con sufijo -2, -3, …")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, engine="pyarrow", index=False)

    size_mb = out_path.stat().st_size / 1024 / 1024
    print(
        f"OK → {out_path}  ({size_mb:.1f} MB)\n"
        f"    filas: {len(df):,} | proyectos: {df['proyecto'].nunique()} | "
        f"cortes: {df['fecha_datos'].nunique()}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera data/base.parquet desde un Excel fuente.")
    ap.add_argument("xlsx", help="Ruta al Excel fuente (una o varias hojas con el esquema esperado).")
    ap.add_argument("--out", default=str(_REPO_ROOT / "data" / "base.parquet"),
                    help="Ruta de salida del parquet (default: data/base.parquet).")
    args = ap.parse_args()
    build(Path(args.xlsx), Path(args.out))


if __name__ == "__main__":
    main()
