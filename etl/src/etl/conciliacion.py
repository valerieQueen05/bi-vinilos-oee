"""CONCILIACIÓN: demuestra que los totales cargados cuadran con la fuente
o explica, con números, cada diferencia."""
from __future__ import annotations

import pandas as pd

from .extract import Fuente
from .transform import Modelo


def _n(s: pd.Series) -> float:
    return float(pd.to_numeric(s, errors="coerce").fillna(0).sum())


def conciliar(f: Fuente, m: Modelo, totales_dw: dict[str, float]) -> list[dict]:
    src = f.base
    quedan = set(m.base_limpia["fila_excel"])
    quitadas = src[~src["fila_excel"].isin(quedan)]
    b = m.base_limpia
    ft = m.fact_turno
    filas_prod = set(ft["id_registro"])
    fuera_prod = b[~b["fila_excel"].isin(filas_prod)]
    res = []

    def fila(metrica, fuente, dw, explicacion):
        dif = fuente - dw
        res.append({"metrica": metrica, "total_fuente": round(fuente, 3), "total_dw": round(dw, 3),
                    "diferencia": round(dif, 3),
                    "pct_diferencia": round(100 * dif / fuente, 4) if fuente else None,
                    "explicacion": explicacion})

    # 1. Filas
    tipos = b["tipo_fila"].value_counts().to_dict()
    fila("Filas de la Base De Datos", len(src), len(ft) + tipos.get("continuacion", 0)
         + tipos.get("no_programado", 0) + tipos.get("sin_actividad", 0),
         f"Duplicados exactos eliminados: {len(quitadas)}. Las filas se reparten en: registros de turno="
         f"{len(ft)}, continuaciones={tipos.get('continuacion', 0)}, no programado={tipos.get('no_programado', 0)}, "
         f"sin actividad={tipos.get('sin_actividad', 0)}")

    # 2. Horas trabajadas
    ht_src = _n(src["Horas trabajadas"])
    ht_dup = _n(quitadas["Horas trabajadas"])
    ht_fuera = _n(fuera_prod["Horas trabajadas"])
    fila("Horas trabajadas", ht_src, totales_dw["horas_trabajadas"],
         f"{ht_dup:.2f} h de filas duplicadas eliminadas + {ht_fuera:.2f} h en filas que no son registro de turno. "
         f"Residuo sin explicar: {ht_src - ht_dup - ht_fuera - totales_dw['horas_trabajadas']:.3f} h")

    # 3. Pacas
    pac_src = _n(src["Pacas producidas"])
    pac_dup = _n(quitadas["Pacas producidas"])
    pac_atip = float(ft.loc[ft["dq_pacas_atipica"], "Pacas producidas"].sum())
    pac_fuera = _n(fuera_prod["Pacas producidas"])
    fila("Pacas producidas", pac_src, totales_dw["pacas"],
         f"{pac_dup:.0f} pacas de duplicados + {pac_atip:.0f} 'pacas' atípicas anuladas (regla R18, eran unidades) "
         f"+ {pac_fuera:.0f} en filas fuera de producción. Residuo: "
         f"{pac_src - pac_dup - pac_atip - pac_fuera - totales_dw['pacas']:.1f}")

    # 4. Tiempo de paro (hechos de paro)
    tp_src = _n(src["Tiempo de Paro"])
    tp_dup = _n(quitadas["Tiempo de Paro"])
    fila("Tiempo de paro (h) · fact_paro", tp_src, totales_dw["horas_paro_fact_paro"],
         f"{tp_dup:.2f} h de paros en filas duplicadas eliminadas (las continuaciones idénticas se conservan). Residuo: "
         f"{tp_src - tp_dup - totales_dw['horas_paro_fact_paro']:.3f} h")

    # 5. Tiempo de paro dentro de los registros de turno
    huerf = m.fact_paro[m.fact_paro["id_registro"].isna()]["horas_paro"].sum()
    fila("Tiempo de paro (h) · fact_produccion_turno", totales_dw["horas_paro_fact_paro"],
         totales_dw["horas_paro_turno"],
         f"{huerf:.2f} h de paros que no pertenecen a un registro de turno (continuaciones sin encabezado o "
         "paros anotados en días no programados). Se conservan en fact_paro para el Pareto")

    # 6. Horas no trabajadas
    hnt_src = _n(src["Horas no trabajadas"])
    hnt_dup = _n(quitadas["Horas no trabajadas"])
    rec = m.fact_tnp
    hnt_rec = float((rec["Horas no trabajadas"] - rec["horas_no_programadas"]).sum())
    fila("Horas no trabajadas", hnt_src, totales_dw["horas_no_programadas"],
         f"{hnt_dup:.2f} h de duplicados + {hnt_rec:.2f} h recortadas por superar 24 h (R19). Residuo: "
         f"{hnt_src - hnt_dup - hnt_rec - totales_dw['horas_no_programadas']:.3f} h")

    # 7. Hoja 'Base de datos de Sub codigos' (no se carga: es redundante)
    s = f.subcodigos.copy()
    bb = src.copy()
    s["Fecha"] = pd.to_datetime(s["Fecha"], errors="coerce")
    bb["Fecha"] = pd.to_datetime(bb["Fecha"], errors="coerce")
    llave = ["Fecha", "Maquina", "Operario", "codigo", "minutos"]

    def eventos(df, col_fmt):
        partes = []
        for c in (1, 3, 5):
            col = col_fmt.format(c)
            e = df[pd.to_numeric(df[col], errors="coerce") > 0][["Fecha", "Maquina", "Operario", col]].copy()
            e.columns = ["Fecha", "Maquina", "Operario", "minutos"]
            e["minutos"] = pd.to_numeric(e["minutos"])
            e["codigo"] = c
            partes.append(e)
        e = pd.concat(partes, ignore_index=True)
        e["n"] = e.groupby(llave).cumcount()
        return e

    es = eventos(s, "Codigo de paro {}")
    eb = eventos(bb, "Codigo de paro {}")
    cruce = es.merge(eb, on=llave + ["n"], how="left", indicator=True)
    min_hoja = float(es["minutos"].sum()) / 60
    min_encontrados = float(cruce.loc[cruce["_merge"] == "both", "minutos"].sum()) / 60
    fila("Paros con subcódigo (h) · hoja 'Sub codigos' encontrados en la Base De Datos", min_hoja,
         min_encontrados,
         f"{(cruce['_merge'] == 'both').sum()} de {len(es)} eventos de la hoja (códigos 1, 3 y 5) existen en la "
         "Base De Datos con la misma fecha, máquina, operaria, código y minutos: la hoja es una copia del detalle "
         "y NO se carga (se duplicarían paros)")
    return res
