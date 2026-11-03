"""Orquestador del ETL:  python -m etl.main

1. Extrae el .xlsm   2. Recrea el esquema (DDL)   3. Carga staging
4. Limpia y transforma (reglas Rxx)   5. Carga dimensiones y hechos
6. Concilia totales   7. Escribe la bitácora en audit.* y en docs/generados/
Todo dentro de UNA transacción: si algo falla no queda una carga a medias.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd

from . import load
from .calidad import BitacoraCalidad
from .conciliacion import conciliar
from .extract import extraer
from .fechas import construir_dim_fecha
from .transform import transformar

RAIZ = Path(__file__).resolve().parents[3]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def escribir_reportes(dir_rep: Path, dq: BitacoraCalidad, conc: list[dict], fuente, conteos: dict) -> None:
    dir_rep.mkdir(parents=True, exist_ok=True)
    reglas = pd.DataFrame(dq.como_filas())
    reglas.to_csv(dir_rep / "reglas_calidad.csv", index=False)
    pd.DataFrame(conc).to_csv(dir_rep / "conciliacion.csv", index=False)

    lin = ["# Reporte de calidad de datos y conciliación (generado por el ETL)", "",
           f"- Archivo fuente: `{fuente.archivo}`",
           f"- SHA-256: `{fuente.sha256}`",
           f"- Fecha de la corrida: {time.strftime('%Y-%m-%d %H:%M')}", "",
           "## Filas cargadas por tabla", "", "| Tabla | Filas |", "|---|---:|"]
    lin += [f"| `{k}` | {v:,} |" for k, v in conteos.items()]
    lin += ["", "## Reglas de limpieza aplicadas", "",
            "| # | Regla | Dimensión | Problema detectado | Acción | Antes | Afectadas | Después |",
            "|---|---|---|---|---|---:|---:|---:|"]
    for r in dq.como_filas():
        lin.append(f"| {r['orden']} | {r['cod_regla']} | {r['dimension_dq']} | {r['descripcion']} | "
                   f"{r['accion']} | {r['filas_antes']:,} | {r['filas_afectadas']:,} | {r['filas_despues']:,} |")
    lin += ["", "## Conciliación de totales fuente vs. DW", "",
            "| Métrica | Fuente | DW | Diferencia | % | Explicación |", "|---|---:|---:|---:|---:|---|"]
    for c in conc:
        pct = "" if c["pct_diferencia"] is None else f"{c['pct_diferencia']:.2f} %"
        lin.append(f"| {c['metrica']} | {c['total_fuente']:,.2f} | {c['total_dw']:,.2f} | "
                   f"{c['diferencia']:,.2f} | {pct} | {c['explicacion']} |")
    (dir_rep / "calidad_y_conciliacion.md").write_text("\n".join(lin) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ETL Seguimiento Témperas y Vinilos -> PostgreSQL")
    ap.add_argument("--excel", default=os.getenv("FUENTE_EXCEL",
                    str(RAIZ / "data/raw/SEGUIMIENTO_TEMPERAS_Y_VINILOS_Actividad.xlsm")))
    ap.add_argument("--sql-dir", default=os.getenv("SQL_DIR", str(RAIZ / "sql/ddl")))
    ap.add_argument("--config", default=os.getenv("ETL_CONFIG", str(RAIZ / "etl/config")))
    ap.add_argument("--reportes", default=os.getenv("REPORTES_DIR", str(RAIZ / "docs/generados")))
    a = ap.parse_args(argv)

    t0 = time.time()
    log(f"Extrayendo {a.excel}")
    fuente = extraer(a.excel)
    log(f"  Base De Datos: {len(fuente.base):,} filas · Sub codigos: {len(fuente.subcodigos):,} · "
        f"estándares: {len(fuente.estandares)}")

    dq = BitacoraCalidad()
    log("Transformando y aplicando reglas de calidad")
    m = transformar(fuente, Path(a.config), dq)
    m.dim_fecha = construir_dim_fecha(date(2022, 1, 1), date(2027, 12, 31))

    conn = load.conectar()
    try:
        with conn:
            with conn.cursor() as cur:
                log("Recreando esquema desde cero (DDL)")
                archivos = load.ejecutar_ddl(cur, Path(a.sql_dir))
                log(f"  {', '.join(archivos)}")

                cur.execute("INSERT INTO audit.etl_corrida (archivo_fuente, sha256_fuente, filas_leidas) "
                            "VALUES (%s, %s, %s) RETURNING id_corrida",
                            (fuente.archivo, fuente.sha256, len(fuente.base)))
                id_corrida = cur.fetchone()[0]

                log("Cargando staging")
                load.cargar_staging(cur, "base_de_datos", fuente.base)
                load.cargar_staging(cur, "sub_codigos", fuente.subcodigos)
                load.cargar_staging(cur, "estandares", fuente.estandares)

                log("Cargando dimensiones")
                c = {}
                c["dw.dim_fecha"] = load.insertar(cur, "dw.dim_fecha", m.dim_fecha, list(m.dim_fecha.columns))
                c["dw.dim_maquina"] = load.insertar(cur, "dw.dim_maquina", m.dim_maquina, list(m.dim_maquina.columns))
                c["dw.dim_turno"] = load.insertar(cur, "dw.dim_turno", m.dim_turno, list(m.dim_turno.columns))
                c["dw.dim_persona"] = load.insertar(cur, "dw.dim_persona", m.dim_persona, list(m.dim_persona.columns))
                c["priv.persona_identidad"] = load.insertar(cur, "priv.persona_identidad", m.persona_identidad,
                                                            list(m.persona_identidad.columns))
                c["dw.dim_referencia"] = load.insertar(cur, "dw.dim_referencia", m.dim_referencia,
                                                       list(m.dim_referencia.columns))
                c["dw.estandar_produccion"] = load.insertar(cur, "dw.estandar_produccion", m.estandar,
                                                            list(m.estandar.columns))
                desconocida = pd.DataFrame([{"sk_causa": -1, "cod_causa": "NR", "cod_codigo": "00",
                    "codigo_desc": "[00] Sin paro registrado", "area_impacto": "No aplica",
                    "categoria_oee": "Disponibilidad", "es_planificado": False, "cod_sistema": None,
                    "sistema_desc": "(sin subcódigo)", "cod_componente": None, "componente_desc": "(general)",
                    "nivel_detalle": 1}])
                causas = pd.concat([desconocida, m.dim_causa], ignore_index=True)
                c["dw.dim_causa_paro"] = load.insertar(cur, "dw.dim_causa_paro", causas, list(causas.columns))
                c["dw.dim_motivo_no_programado"] = load.insertar(cur, "dw.dim_motivo_no_programado", m.dim_motivo,
                                                                 list(m.dim_motivo.columns))
                load.reiniciar_secuencias(cur)

                log("Cargando hechos")
                ft = m.fact_turno
                cols_ft = ["id_registro", "sk_fecha", "sk_maquina", "sk_turno", "sk_operario", "sk_referencia",
                           "horas_trabajadas", "horas_paro_planificado", "horas_paro_disponibilidad",
                           "horas_paro_calidad", "horas_paro_total", "tiempo_planificado_h", "tiempo_operativo_h",
                           "tiempo_ideal_h", "pacas_producidas", "pacas_meta", "n_eventos_paro", "pacas_hora_ideal",
                           "origen_estandar", "es_registro_historico", "dq_pacas_atipica", "dq_paro_mayor_turno",
                           "es_valido_oee"]
                c["dw.fact_produccion_turno"] = load.insertar(cur, "dw.fact_produccion_turno", ft, cols_ft)
                fp = m.fact_paro.copy()
                fp["id_registro"] = fp["id_registro"].astype("Int64")
                cols_fp = ["id_registro", "fila_origen", "sk_fecha", "sk_maquina", "sk_turno", "sk_operario",
                           "sk_referencia", "sk_causa", "sk_persona_involucrada", "area_involucrada",
                           "minutos_paro", "horas_paro", "es_fila_continuacion"]
                c["dw.fact_paro"] = load.insertar(cur, "dw.fact_paro", fp, cols_fp)
                tn = m.fact_tnp.drop(columns=["id_registro"]).rename(columns={"fila_excel": "id_registro"})
                c["dw.fact_tiempo_no_programado"] = load.insertar(
                    cur, "dw.fact_tiempo_no_programado", tn,
                    ["id_registro", "sk_fecha", "sk_maquina", "sk_turno", "sk_motivo", "horas_no_programadas",
                     "dq_horas_recortadas"])

                log("Conciliando totales contra la base de datos")
                cur.execute("""SELECT
                    (SELECT COALESCE(SUM(horas_trabajadas),0) FROM dw.fact_produccion_turno),
                    (SELECT COALESCE(SUM(pacas_producidas),0) FROM dw.fact_produccion_turno),
                    (SELECT COALESCE(SUM(minutos_paro),0) / 60.0 FROM dw.fact_paro),
                    (SELECT COALESCE(SUM(horas_paro_total),0) FROM dw.fact_produccion_turno),
                    (SELECT COALESCE(SUM(horas_no_programadas),0) FROM dw.fact_tiempo_no_programado)""")
                v = [float(x) for x in cur.fetchone()]
                totales = dict(zip(["horas_trabajadas", "pacas", "horas_paro_fact_paro", "horas_paro_turno",
                                    "horas_no_programadas"], v))
                conc = conciliar(fuente, m, totales)

                for r in dq.como_filas():
                    cur.execute("INSERT INTO audit.regla_calidad VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                (id_corrida, r["orden"], r["cod_regla"], r["dimension_dq"], r["descripcion"],
                                 r["accion"], r["filas_antes"], r["filas_afectadas"], r["filas_despues"]))
                for r in conc:
                    cur.execute("INSERT INTO audit.conciliacion VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                (id_corrida, r["metrica"], r["total_fuente"], r["total_dw"], r["diferencia"],
                                 r["pct_diferencia"], r["explicacion"]))
                cur.execute("UPDATE audit.etl_corrida SET fin = now(), estado = 'ok' WHERE id_corrida = %s",
                            (id_corrida,))
        cur = conn.cursor()
        cur.execute("ANALYZE")
    finally:
        conn.close()

    dq.imprimir()
    try:
        escribir_reportes(Path(a.reportes), dq, conc, fuente, c)
    except OSError as e:   # p. ej. carpeta montada sin permiso de escritura: la carga ya quedó en audit.*
        log(f"AVISO: no se pudo escribir el reporte en {a.reportes} ({e}). Consúltelo en audit.regla_calidad")
    for k, n in c.items():
        log(f"  {k:32} {n:>7,}")
    log(f"ETL terminado en {time.time() - t0:.1f} s. Reporte: {a.reportes}/calidad_y_conciliacion.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
