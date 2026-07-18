"""
build_parquet.py — Regenera data/base.parquet desde un Excel fuente.
=====================================================================
La app en la nube lee SOLO data/base.parquet (ver docs/DESPLIEGUE.md y
docs/ARQUITECTURA.md). Este script convierte el Excel fuente (hoja ERConsolidado
del consolidador, o su copia Pipeline.xlsx) en ese parquet compacto, limpiando
filas basura y asignando la columna `version`.

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
from backend.parser_excel_v2 import parse_base_excel_df  # noqa: E402


def build(xlsx_path: Path, out_path: Path) -> None:
    if not xlsx_path.exists():
        raise FileNotFoundError(f"No existe el Excel: {xlsx_path}")

    print(f"Leyendo {xlsx_path.name} …")
    data = xlsx_path.read_bytes()
    df, warnings, errors = parse_base_excel_df(data)
    if errors:
        raise ValueError("El Excel no cumple el esquema:\n" + "\n".join(errors))
    for w in warnings:
        print(f"  aviso: {w}")

    # Asignar version por (proyecto, fecha_datos). Con un solo archivo → todo v1.
    # (Si algún día se combinan varios archivos aquí, replicar el conteo acumulado
    #  del loader en app.py: version creciente por (proyecto, fecha_datos).)
    df["version"] = 1
    df["version"] = pd.to_numeric(df["version"], downcast="unsigned")

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
    ap.add_argument("xlsx", help="Ruta al Excel fuente (hoja ERConsolidado / Pipeline.xlsx).")
    ap.add_argument("--out", default=str(_REPO_ROOT / "data" / "base.parquet"),
                    help="Ruta de salida del parquet (default: data/base.parquet).")
    args = ap.parse_args()
    build(Path(args.xlsx), Path(args.out))


if __name__ == "__main__":
    main()
