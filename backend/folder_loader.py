"""
folder_loader.py — CashFlow Auditor v2
========================================
Carga la base de datos a partir de TODOS los archivos Excel contenidos
en una carpeta fija. Cada archivo se trata como una fuente independiente.

Convención de versiones:
    - Cuando varios archivos contienen registros con la misma
      (proyecto, fecha_datos), cada uno se etiqueta como una "sub-versión"
      del mismo corte: 2026-04-01-1, 2026-04-01-2, ...
    - La numeración de versiones se asigna en el orden de modificación
      (LastWriteTime) de los archivos en la carpeta.
    - Si solo existe una versión para una (proyecto, fecha_datos), la
      etiqueta se muestra sin sufijo: "2026-04-01".
"""

from pathlib import Path
from datetime import date, datetime
from typing import List, Tuple, Dict, Callable, Optional

from .models import BaseRecord, UploadResponse
from .parser_excel_v2 import parse_base_excel


# ─────────────────────────────────────────────
# PARSEO DE ETIQUETAS DE VERSIÓN
# ─────────────────────────────────────────────

def parse_fecha_label(label: str) -> Tuple[date, int]:
    """
    Convierte una etiqueta de UI a (fecha, versión).

        "2026-04-01"   → (date(2026,4,1), 1)
        "2026-04-01-2" → (date(2026,4,1), 2)
    """
    parts = label.strip().split("-")
    if len(parts) == 3:
        return date.fromisoformat(label), 1
    if len(parts) == 4:
        fecha = date.fromisoformat("-".join(parts[:3]))
        version = int(parts[3])
        return fecha, version
    raise ValueError(f"Etiqueta de fecha inválida: '{label}'")


def make_fecha_label(fecha: date, version: int, total_versiones: int) -> str:
    """Construye la etiqueta de UI a partir de fecha + versión."""
    base = fecha.isoformat()
    if total_versiones <= 1:
        return base
    return f"{base}-{version}"


# ─────────────────────────────────────────────
# CARGADOR DE CARPETA
# ─────────────────────────────────────────────

# Tipo: (nombre_archivo, fecha_modificacion, n_registros, n_proyectos)
FileMeta = Tuple[str, datetime, int, int]


def list_database_files(folder_path: Path) -> List[Tuple[str, datetime, int]]:
    """
    Escanea NO recursivamente folder_path y devuelve metadatos LIGEROS de
    cada archivo Excel (sin parsear). Ideal para que la UI muestre la lista
    antes de que el usuario decida qué cargar.

    Returns:
        Lista de tuplas (nombre_archivo, fecha_modificacion, tamano_bytes)
        ordenadas por fecha de modificación descendente (más reciente primero).
    """
    folder_path = Path(folder_path)
    if not folder_path.exists() or not folder_path.is_dir():
        raise FileNotFoundError(f"Carpeta no accesible: {folder_path}")

    files_info = []
    for p in folder_path.iterdir():
        if (p.is_file()
                and p.suffix.lower() in (".xlsx", ".xls")
                and not p.name.startswith("~$")):
            stat = p.stat()
            files_info.append((p.name, datetime.fromtimestamp(stat.st_mtime), stat.st_size))

    # Más recientes primero
    files_info.sort(key=lambda t: t[1], reverse=True)
    return files_info


def load_database_from_folder(
    folder_path: Path,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    selected_filenames: Optional[List[str]] = None,
    parse_fn: Optional[Callable[[bytes], Tuple[List[BaseRecord], UploadResponse]]] = None,
) -> Tuple[List[BaseRecord], UploadResponse, List[FileMeta]]:
    """
    Escanea NO recursivamente folder_path, procesa cada .xlsx/.xls y
    combina los registros en una sola base con versionado automático.

    Args:
        folder_path: Carpeta a escanear.
        progress_callback: Callback opcional para reportar avance.
        selected_filenames: Si se entrega, SOLO procesa los archivos cuyos
            nombres aparezcan en esta lista. Si es None, procesa todos.
        parse_fn: Parser de bytes Excel a usar. Por defecto `parse_base_excel`.
            La app Streamlit inyecta aquí una versión cacheada para evitar
            re-parsear archivos idénticos.

    Returns:
        records_combinados, upload_response_con_versiones, lista_archivos_procesados
    """
    if parse_fn is None:
        parse_fn = parse_base_excel
    folder_path = Path(folder_path)
    if not folder_path.exists() or not folder_path.is_dir():
        raise FileNotFoundError(f"Carpeta no accesible: {folder_path}")

    # Listar archivos Excel directos, ignorando archivos de lock de Excel (~$...)
    files = sorted(
        [p for p in folder_path.iterdir()
         if p.is_file()
         and p.suffix.lower() in (".xlsx", ".xls")
         and not p.name.startswith("~$")],
        key=lambda p: p.stat().st_mtime,
    )

    # Filtrar a los archivos seleccionados si aplica
    if selected_filenames is not None:
        selected_set = set(selected_filenames)
        files = [p for p in files if p.name in selected_set]

    if not files:
        raise FileNotFoundError(
            f"No se encontraron archivos Excel (.xlsx/.xls) para cargar en: {folder_path}"
        )

    all_records: List[BaseRecord] = []
    all_warnings: List[str] = []
    files_processed: List[FileMeta] = []

    # Contador acumulado de versiones por (proyecto, fecha_datos)
    version_counter: Dict[Tuple[str, date], int] = {}

    total_files = len(files)
    for i, file_path in enumerate(files):
        if progress_callback is not None:
            try:
                progress_callback(i, total_files, file_path.name)
            except Exception:
                pass
        try:
            with open(file_path, "rb") as f:
                excel_bytes = f.read()
            records, response = parse_fn(excel_bytes)
        except Exception as e:
            all_warnings.append(f"❌ Error procesando '{file_path.name}': {e}")
            continue

        # Prefijar warnings con el nombre del archivo
        for w in response.warnings:
            all_warnings.append(f"[{file_path.name}] {w}")

        # Asignar versión a cada combinación (proyecto, fecha_datos) presente en este archivo
        keys_en_archivo = {(r.proyecto, r.fecha_datos) for r in records}
        version_asignada: Dict[Tuple[str, date], int] = {}
        for key in keys_en_archivo:
            actual = version_counter.get(key, 0)
            nueva = actual + 1
            version_asignada[key] = nueva
            version_counter[key] = nueva

        # Etiquetar cada record con su versión
        for r in records:
            r.version = version_asignada[(r.proyecto, r.fecha_datos)]

        all_records.extend(records)

        n_proyectos = len({r.proyecto for r in records})
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        files_processed.append((file_path.name, mtime, len(records), n_proyectos))

    # Reportar finalización (100%)
    if progress_callback is not None:
        try:
            progress_callback(total_files, total_files, "Finalizando…")
        except Exception:
            pass

    if not all_records:
        raise ValueError(
            "No se pudo extraer ningún registro válido de los archivos encontrados."
        )

    # Construir UploadResponse con etiquetas que reflejen sub-versiones
    proyectos_labels: Dict[str, set] = {}
    for r in all_records:
        proyectos_labels.setdefault(r.proyecto, set())
        max_v = version_counter[(r.proyecto, r.fecha_datos)]
        label = make_fecha_label(r.fecha_datos, r.version, max_v)
        proyectos_labels[r.proyecto].add(label)

    fechas_por_proyecto = {
        p: sorted(list(labels)) for p, labels in proyectos_labels.items()
    }

    response = UploadResponse(
        proyectos=sorted(list(proyectos_labels.keys())),
        fechas_datos=fechas_por_proyecto,
        total_registros=len(all_records),
        warnings=all_warnings,
    )

    return all_records, response, files_processed
