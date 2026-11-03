"""CARGA: ejecuta el DDL desde cero y carga staging, dimensiones y hechos en PostgreSQL."""
from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values


def conectar():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "bi_vinilos"),
        user=os.getenv("POSTGRES_USER", "etl_admin"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def ejecutar_ddl(cur, sql_dir: Path) -> list[str]:
    archivos = sorted(sql_dir.glob("*.sql"))
    for a in archivos:
        cur.execute(a.read_text(encoding="utf-8"))
    return [a.name for a in archivos]


def _limpio(v):
    if v is None:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    if v is pd.NaT or (not isinstance(v, (str, bytes)) and pd.isna(v)):
        return None
    if isinstance(v, np.generic):
        return v.item()
    return v


def insertar(cur, tabla: str, df: pd.DataFrame, columnas: list[str]) -> int:
    filas = [tuple(_limpio(v) for v in fila) for fila in df[columnas].itertuples(index=False, name=None)]
    if filas:
        execute_values(cur, f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES %s", filas, page_size=2000)
    return len(filas)


def _col_sql(nombre: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", nombre.lower().translate(str.maketrans("áéíóúñ", "aeioun"))).strip("_")
    return s or "col"


def cargar_staging(cur, nombre: str, df: pd.DataFrame) -> int:
    """Copia cruda (todo como texto) para conservar el linaje exacto de la fuente."""
    cols = [_col_sql(c) for c in df.columns]
    vistos = {}
    for i, c in enumerate(cols):
        vistos[c] = vistos.get(c, 0) + 1
        if vistos[c] > 1:
            cols[i] = f"{c}_{vistos[c]}"
    cur.execute(f"CREATE TABLE stg.{nombre} ({', '.join(f'{c} TEXT' for c in cols)})")
    datos = df.astype(object).where(df.notna(), None)
    filas = [tuple(None if v is None else str(v) for v in r) for r in datos.itertuples(index=False, name=None)]
    execute_values(cur, f"INSERT INTO stg.{nombre} VALUES %s", filas, page_size=2000)
    return len(filas)


def reiniciar_secuencias(cur) -> None:
    for tabla, col in [("dw.dim_maquina", "sk_maquina"), ("dw.dim_persona", "sk_persona"),
                       ("dw.dim_referencia", "sk_referencia"), ("dw.dim_causa_paro", "sk_causa"),
                       ("dw.dim_motivo_no_programado", "sk_motivo")]:
        cur.execute(f"SELECT setval(pg_get_serial_sequence('{tabla}', '{col}'), "
                    f"GREATEST((SELECT MAX({col}) FROM {tabla}), 1))")
