"""EXTRACCIÓN: lee el libro .xlsm tal como está (sin macros) y devuelve DataFrames crudos.

No se transforma nada aquí: lo que sale de este módulo se carga en el esquema
`stg` para que quede evidencia de la fuente original (linaje).
"""
from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass
from pathlib import Path

import openpyxl
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

HOJA_BASE = "Base De Datos"
HOJA_SUBCOD = "Base de datos de Sub codigos"
HOJA_LISTAS = "Tablas Desplegables"
FILA_ENCABEZADO_BASE = 9      # la tabla T_baseDeDatos empieza en A9
FILA_ENCABEZADO_SUBCOD = 8    # la tabla Base_de_datos_subcodigos empieza en A8


@dataclass
class Fuente:
    base: pd.DataFrame          # Base De Datos (T_baseDeDatos)
    subcodigos: pd.DataFrame    # Base de datos de Sub codigos
    codigos: pd.DataFrame       # catálogo [01]..[18] con área de impacto
    subcod_catalogo: pd.DataFrame  # catálogo oficial de subcódigos 1.x, 3.x, 5.x
    estandares: pd.DataFrame    # Tabla8/14/15/16: velocidad por máquina y referencia
    mantenimiento: list[str]    # personal de mantenimiento (lista desplegable)
    sha256: str
    archivo: str


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _rango(ws, min_row, max_row, min_col, max_col) -> list[tuple]:
    return list(ws.iter_rows(min_row=min_row, max_row=max_row,
                             min_col=min_col, max_col=max_col, values_only=True))


def extraer(ruta_excel: str | Path) -> Fuente:
    ruta = Path(ruta_excel)
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró la fuente: {ruta}")

    # --- Tabla principal ----------------------------------------------------
    base = pd.read_excel(ruta, sheet_name=HOJA_BASE, header=FILA_ENCABEZADO_BASE - 1,
                         engine="openpyxl")
    base.insert(0, "fila_excel", base.index + FILA_ENCABEZADO_BASE + 1)
    base.columns = [str(c).replace("\n", " ").strip() for c in base.columns]

    sub = pd.read_excel(ruta, sheet_name=HOJA_SUBCOD, header=FILA_ENCABEZADO_SUBCOD - 1,
                        engine="openpyxl")
    sub.insert(0, "fila_excel", sub.index + FILA_ENCABEZADO_SUBCOD + 1)
    sub.columns = [str(c).replace("\n", " ").strip() for c in sub.columns]

    # --- Catálogos de la hoja "Tablas Desplegables" ---------------------------
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    ws = wb[HOJA_LISTAS]

    # Tabla2 (AM4:AO22): ÁREA DE IMPACTO | PARO | KEY
    codigos = pd.DataFrame(_rango(ws, 5, 22, 39, 41), columns=["area_impacto", "paro", "key"])
    codigos = codigos.dropna(subset=["paro"])

    # Subcódigos: código 1 (AQ4:AR35), código 3 (AT4:AU9), código 5 (AT19:AU30)
    filas = []
    for cod, (r1, r2, c1, c2) in {"01": (5, 35, 43, 44),
                                  "03": (5, 9, 46, 47),
                                  "05": (20, 30, 46, 47)}.items():
        for llave, desc in _rango(ws, r1, r2, c1, c2):
            if llave is not None and desc is not None:
                filas.append({"cod_codigo": cod, "llave": str(llave).strip(),
                              "descripcion": str(desc).strip()})
    subcod_catalogo = pd.DataFrame(filas)

    # Estándares por máquina (C124:M262, cuatro tablas con encabezado repetido)
    cols = ["maquina", "referencia", "n_colores", "pacas", "display", "unidades_por_paca",
            "unidades_por_minuto", "horas", "minutos_turno", "unidades_ideales", "pacas_ideales"]
    est = pd.DataFrame(_rango(ws, 125, 262, 3, 13), columns=cols)
    est["fila_excel"] = range(125, 125 + len(est))
    est = est[est["maquina"].astype(str).str.startswith("Vinilos")]

    # Personal de mantenimiento (AW19:AW30)
    mantenimiento = [str(v[0]).strip() for v in _rango(ws, 20, 30, 49, 49) if v[0]]
    wb.close()

    return Fuente(base=base, subcodigos=sub, codigos=codigos,
                  subcod_catalogo=subcod_catalogo, estandares=est,
                  mantenimiento=mantenimiento, sha256=_sha256(ruta), archivo=ruta.name)
