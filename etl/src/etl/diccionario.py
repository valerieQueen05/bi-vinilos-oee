"""Genera docs/05_diccionario_datos.md a partir del catálogo de PostgreSQL + el linaje declarado aquí.

    python -m etl.diccionario            (con las mismas variables de entorno del ETL)

Así el diccionario nunca queda desactualizado respecto al DDL: tipos, llaves y
nulabilidad salen de information_schema; la descripción, la regla de
transformación y el origen (linaje) se declaran en LINAJE.
"""
from __future__ import annotations

import os
from pathlib import Path

from .load import conectar

BD = "Base De Datos"
TD = "Tablas Desplegables"

TABLAS = {
    "dim_fecha": "Calendario 2022-2027 con festivos de Colombia. Dimensión construida por el equipo (no viene del Excel).",
    "dim_maquina": "Líneas de envasado. SCD Tipo 2 sobre la velocidad nominal.",
    "dim_turno": "Turnos y jornadas estandarizados (7 escrituras + vacíos → 9 miembros).",
    "dim_persona": "Operarias y personal de mantenimiento con seudónimo. Dimensión con rol (operaria / persona involucrada).",
    "dim_referencia": "Productos envasados con atributos derivados del nombre.",
    "estandar_produccion": "Velocidad ideal por máquina y referencia (base del rendimiento).",
    "dim_causa_paro": "Jerarquía aplanada Código › Sistema › Componente.",
    "dim_motivo_no_programado": "Motivos por los que la línea no se programó, unificando dos catálogos.",
    "fact_produccion_turno": "Grano: un registro de turno (máquina × fecha × turno × operaria × referencia).",
    "fact_paro": "Grano: un evento de paro (registro × código/subcódigo).",
    "fact_tiempo_no_programado": "Grano: horas no programadas de una máquina en una fecha por un motivo.",
    "fact_produccion_hora": "Grano: una máquina × una hora (streaming simulado; futuro PLC/SCADA).",
}

# columna: (origen / linaje, regla de transformación)
LINAJE = {
    "dim_fecha": {
        "sk_fecha": ("Generado", "AAAAMMDD de la fecha"),
        "es_festivo": ("Generado", "Ley 51/1983 (Emiliani) + Pascua; festivo Virgen de Chiquinquirá desde 2026"),
        "*": ("Generado por fechas.py", "Derivado de la fecha"),
    },
    "dim_maquina": {
        "sk_maquina": ("Generado", "Secuencia"),
        "cod_maquina": (f"{BD}.Maquina", "Sin cambios (4 valores válidos)"),
        "nombre_maquina": (f"{BD}.Maquina", "'_' → espacio"),
        "velocidad_nominal_upm": (f"{TD} Tabla8/14/15/16.'unidades *minuto'", "Moda de la tabla de cada máquina"),
        "factor_eficiencia": ("Calculadora de tiempos!K10", "0,93 V1 · 0,96 V2 · 1 V3/V4"),
        "*": ("Generado", "Control SCD2"),
    },
    "dim_turno": {"*": (f"{BD}.Turno + etl/config/dim_turno.csv", "Mapeo turnos.csv; vacío → 'SH' histórico")},
    "dim_persona": {
        "cod_persona": ("Generado", "OP-/MT-/OT- + consecutivo por orden alfabético del nombre normalizado"),
        "rol": (f"{TD} lista de mantenimiento", "Mantenimiento si está en la lista; Operaria si aparece como operario"),
        "alias_publico": ("Generado", "Seudónimo visible en tableros"),
        "*": ("Generado", "—"),
    },
    "dim_referencia": {
        "cod_referencia": (f"{BD}.Referencia y {TD}.'Nombre de referencia'", "normalizar_referencia(): 'Alocdor'→'Alocolor', '(6col)'→'(6 col)', '15 cc'→'15cc'"),
        "marca": ("Derivado del nombre", "Texto antes del tamaño"),
        "tamano_cc": ("Derivado del nombre", "Regex (\\d+)cc"),
        "n_colores": ("Derivado del nombre", "Regex (N col); 125 cc → 1"),
        "*": ("Derivado", "—"),
    },
    "estandar_produccion": {
        "unidades_por_paca": (f"{TD}.'Unidades * paca'", "Si falta: otra máquina → mediana tamaño/colores → mezcla de la máquina"),
        "unidades_por_minuto": (f"{TD}.'unidades *minuto'", "Velocidad de la máquina"),
        "pacas_hora_ideal": ("Calculado", "60 × u/min ÷ u/paca"),
        "origen_estandar": ("Calculado", "Marca de imputación"),
        "*": ("Llave", "—"),
    },
    "dim_causa_paro": {
        "cod_codigo": (f"{TD}.KEY (paro01..paro18)", "Dos dígitos"),
        "codigo_desc": (f"{TD}.PARO", "[18] sobrescrito a 'Desinfección' (clasificacion_codigos.csv)"),
        "area_impacto": (f"{TD}.'ÁREA DE IMPACTO'", "Sin cambios"),
        "categoria_oee": ("etl/config/clasificacion_codigos.csv", "Planificado / Disponibilidad / Calidad"),
        "cod_sistema": (f"{TD} listas de subcódigos 1.x, 3.x, 5.x", "Nivel 2"),
        "cod_componente": (f"{TD} listas de subcódigos", "Nivel 3 (solo código 01)"),
        "*": ("Generado", "Jerarquía aplanada con relleno '(sin subcódigo)' / '(general)'"),
    },
    "dim_motivo_no_programado": {"*": (f"{BD}.'Tipo de paro' + 'Observaciones de paro'",
                                       "Regex de motivos_no_programado.csv y motivos_tipo_paro.csv")},
    "fact_produccion_turno": {
        "id_registro": (f"{BD} (fila del Excel)", "Fila de origen: linaje"),
        "sk_fecha": (f"{BD}.Fecha", "AAAAMMDD"),
        "sk_operario": (f"{BD}.Operario", "Normalizado (personas_alias.csv); vacío → -1"),
        "sk_referencia": (f"{BD}.Referencia", "Normalizada; vacío/'No aplica' → -1"),
        "horas_trabajadas": (f"{BD}.'Horas trabajadas'", "Numérico"),
        "horas_paro_planificado": (f"{BD}.'Codigo de paro N' (min)", "Σ/60 de códigos 04,16,17,18 del registro + sus continuaciones"),
        "horas_paro_disponibilidad": (f"{BD}.'Codigo de paro N' (min)", "Σ/60 de códigos de disponibilidad"),
        "horas_paro_calidad": (f"{BD}.'Codigo de paro 11'", "Σ/60"),
        "horas_paro_total": ("Calculado", "Suma de las tres anteriores (= 'Tiempo de Paro' + continuaciones)"),
        "tiempo_planificado_h": ("Calculado", "máx(HT − planificado, 0)"),
        "tiempo_operativo_h": ("Calculado", "máx(TP − disponibilidad, 0)"),
        "tiempo_ideal_h": ("Calculado", "pacas ÷ pacas_hora_ideal"),
        "pacas_producidas": (f"{BD}.'Pacas producidas'", "NULL si atípica (R18)"),
        "pacas_meta": ("Calculado", "pacas_hora_ideal × factor × TP"),
        "pacas_hora_ideal": ("estandar_produccion", "Lookup máquina × referencia"),
        "es_valido_oee": ("Calculado", "HT>0 ∧ pacas válidas ∧ TN>0"),
        "*": ("Calculado", "Bandera de calidad / atributo derivado"),
    },
    "fact_paro": {
        "id_paro": ("Generado", "BIGSERIAL"),
        "fila_origen": (f"{BD} (fila del Excel)", "Linaje"),
        "id_registro": ("Calculado", "Registro de turno al que pertenece (R16)"),
        "sk_causa": (f"{BD}.'Codigo de paro N' + 'Sub Codigo de paro 1' / 'Subcodigo 3' / 'Subcodigo 5'", "Unpivot + normalización de subcódigo (R14, R15)"),
        "sk_persona_involucrada": (f"{BD}.'Personal involucrado'", "Solo para código 05"),
        "area_involucrada": (f"{BD}.'Área involucrada en subcodigo 5'", "Personal_de_mantenimiento → Mantenimiento"),
        "minutos_paro": (f"{BD}.'Codigo de paro N'", "Minutos > 0"),
        "horas_paro": ("Calculado", "minutos ÷ 60"),
        "*": ("Heredado de la fila de origen", "—"),
    },
    "fact_tiempo_no_programado": {
        "horas_no_programadas": (f"{BD}.'Horas no trabajadas'", "Recorte a 24 h (R19)"),
        "sk_motivo": (f"{BD}.'Tipo de paro' + 'Observaciones de paro'", "Clasificación por regex (R20)"),
        "*": ("Heredado de la fila de origen", "—"),
    },
    "fact_produccion_hora": {"*": ("simulador/simulador.py (futuro: PLC/SCADA)", "Muestreo de la distribución histórica de cada máquina")},
}


def generar(salida: Path) -> None:
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.table_name, c.column_name, c.data_type,
               COALESCE(c.character_maximum_length::text, c.numeric_precision || ',' || c.numeric_scale, ''),
               c.is_nullable,
               EXISTS (SELECT 1 FROM information_schema.table_constraints tc
                       JOIN information_schema.key_column_usage k USING (constraint_schema, constraint_name)
                       WHERE tc.constraint_type = 'PRIMARY KEY' AND k.table_schema = 'dw'
                         AND k.table_name = c.table_name AND k.column_name = c.column_name),
               (SELECT ccu.table_name FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage k USING (constraint_schema, constraint_name)
                JOIN information_schema.constraint_column_usage ccu USING (constraint_schema, constraint_name)
                WHERE tc.constraint_type = 'FOREIGN KEY' AND k.table_schema = 'dw'
                  AND k.table_name = c.table_name AND k.column_name = c.column_name LIMIT 1)
        FROM information_schema.columns c
        WHERE c.table_schema = 'dw' AND c.table_name = ANY(%s)
        ORDER BY c.table_name, c.ordinal_position""", (list(TABLAS),))
    filas = cur.fetchall()
    conn.close()

    out = ["# 5. Diccionario de datos y linaje", "",
           "> Generado con `python -m etl.diccionario` desde el catálogo de PostgreSQL. "
           "Tipos, llaves y nulabilidad salen de `information_schema`; el origen y la regla de cada campo, "
           "del linaje declarado en `etl/src/etl/diccionario.py`.", "",
           "Convenciones: **SK** = llave sustituta, **NK** = llave natural, **FK** = llave foránea, "
           "**DD** = dimensión degenerada.", ""]
    for t, desc in TABLAS.items():
        out += [f"## `dw.{t}`", "", desc, "",
                "| Columna | Tipo | Llave | Nulo | Origen (linaje) | Regla de transformación |",
                "|---|---|---|---|---|---|"]
        lin = LINAJE.get(t, {})
        for tabla, col, tipo, largo, nulo, pk, fk in [f for f in filas if f[0] == t]:
            llave = "PK" + (" / SK" if col.startswith("sk_") else "") if pk else (f"FK → {fk}" if fk else (
                "NK" if col.startswith("cod_") else ("DD" if col in ("id_registro", "fila_origen") else "")))
            origen, regla = lin.get(col, lin.get("*", ("", "")))
            tipo_txt = f"{tipo}({largo})" if largo and tipo in ("character varying", "numeric", "character") else tipo
            out.append(f"| `{col}` | {tipo_txt} | {llave} | {'sí' if nulo == 'YES' else 'no'} | {origen} | {regla} |")
        out.append("")
    salida.write_text("\n".join(out), encoding="utf-8")
    print(f"Diccionario escrito en {salida}")


if __name__ == "__main__":
    raiz = Path(__file__).resolve().parents[3]
    generar(Path(os.getenv("DICCIONARIO_SALIDA", raiz / "docs/05_diccionario_datos.md")))
