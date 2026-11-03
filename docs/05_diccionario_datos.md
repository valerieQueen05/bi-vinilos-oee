# 5. Diccionario de datos y linaje

> Generado con `python -m etl.diccionario` desde el catálogo de PostgreSQL. Tipos, llaves y nulabilidad salen de `information_schema`; el origen y la regla de cada campo, del linaje declarado en `etl/src/etl/diccionario.py`.

Convenciones: **SK** = llave sustituta, **NK** = llave natural, **FK** = llave foránea, **DD** = dimensión degenerada.

## `dw.dim_fecha`

Calendario 2022-2027 con festivos de Colombia. Dimensión construida por el equipo (no viene del Excel).

| Columna | Tipo | Llave | Nulo | Origen (linaje) | Regla de transformación |
|---|---|---|---|---|---|
| `sk_fecha` | integer | PK / SK | no | Generado | AAAAMMDD de la fecha |
| `fecha` | date |  | no | Generado por fechas.py | Derivado de la fecha |
| `anio` | smallint |  | no | Generado por fechas.py | Derivado de la fecha |
| `semestre` | smallint |  | no | Generado por fechas.py | Derivado de la fecha |
| `trimestre` | smallint |  | no | Generado por fechas.py | Derivado de la fecha |
| `mes_num` | smallint |  | no | Generado por fechas.py | Derivado de la fecha |
| `mes_nombre` | character varying(12) |  | no | Generado por fechas.py | Derivado de la fecha |
| `mes_abrev` | character(3) |  | no | Generado por fechas.py | Derivado de la fecha |
| `anio_mes` | character(7) |  | no | Generado por fechas.py | Derivado de la fecha |
| `dia_mes` | smallint |  | no | Generado por fechas.py | Derivado de la fecha |
| `dia_semana_num` | smallint |  | no | Generado por fechas.py | Derivado de la fecha |
| `dia_semana_nombre` | character varying(10) |  | no | Generado por fechas.py | Derivado de la fecha |
| `semana_iso` | smallint |  | no | Generado por fechas.py | Derivado de la fecha |
| `anio_iso` | smallint |  | no | Generado por fechas.py | Derivado de la fecha |
| `es_fin_de_semana` | boolean |  | no | Generado por fechas.py | Derivado de la fecha |
| `es_festivo` | boolean |  | no | Generado | Ley 51/1983 (Emiliani) + Pascua; festivo Virgen de Chiquinquirá desde 2026 |
| `nombre_festivo` | character varying(60) |  | sí | Generado por fechas.py | Derivado de la fecha |
| `es_dia_habil` | boolean |  | no | Generado por fechas.py | Derivado de la fecha |

## `dw.dim_maquina`

Líneas de envasado. SCD Tipo 2 sobre la velocidad nominal.

| Columna | Tipo | Llave | Nulo | Origen (linaje) | Regla de transformación |
|---|---|---|---|---|---|
| `sk_maquina` | integer | PK / SK | no | Generado | Secuencia |
| `cod_maquina` | character varying(20) | NK | no | Base De Datos.Maquina | Sin cambios (4 valores válidos) |
| `nombre_maquina` | character varying(40) |  | no | Base De Datos.Maquina | '_' → espacio |
| `linea` | character varying(40) |  | no | Generado | Control SCD2 |
| `velocidad_nominal_upm` | numeric(6,1) |  | sí | Tablas Desplegables Tabla8/14/15/16.'unidades *minuto' | Moda de la tabla de cada máquina |
| `factor_eficiencia` | numeric(4,3) |  | sí | Calculadora de tiempos!K10 | 0,93 V1 · 0,96 V2 · 1 V3/V4 |
| `valido_desde` | date |  | no | Generado | Control SCD2 |
| `valido_hasta` | date |  | no | Generado | Control SCD2 |
| `es_actual` | boolean |  | no | Generado | Control SCD2 |

## `dw.dim_turno`

Turnos y jornadas estandarizados (7 escrituras + vacíos → 9 miembros).

| Columna | Tipo | Llave | Nulo | Origen (linaje) | Regla de transformación |
|---|---|---|---|---|---|
| `sk_turno` | smallint | PK / SK | no | Base De Datos.Turno + etl/config/dim_turno.csv | Mapeo turnos.csv; vacío → 'SH' histórico |
| `cod_turno` | character varying(10) | NK | no | Base De Datos.Turno + etl/config/dim_turno.csv | Mapeo turnos.csv; vacío → 'SH' histórico |
| `nombre_turno` | character varying(40) |  | no | Base De Datos.Turno + etl/config/dim_turno.csv | Mapeo turnos.csv; vacío → 'SH' histórico |
| `hora_inicio` | time without time zone |  | sí | Base De Datos.Turno + etl/config/dim_turno.csv | Mapeo turnos.csv; vacío → 'SH' histórico |
| `hora_fin` | time without time zone |  | sí | Base De Datos.Turno + etl/config/dim_turno.csv | Mapeo turnos.csv; vacío → 'SH' histórico |
| `duracion_h` | numeric(4,1) |  | sí | Base De Datos.Turno + etl/config/dim_turno.csv | Mapeo turnos.csv; vacío → 'SH' histórico |
| `minutos_paro_programado_std` | smallint |  | sí | Base De Datos.Turno + etl/config/dim_turno.csv | Mapeo turnos.csv; vacío → 'SH' histórico |
| `tipo_jornada` | character varying(20) |  | no | Base De Datos.Turno + etl/config/dim_turno.csv | Mapeo turnos.csv; vacío → 'SH' histórico |
| `franja` | character varying(10) |  | no | Base De Datos.Turno + etl/config/dim_turno.csv | Mapeo turnos.csv; vacío → 'SH' histórico |

## `dw.dim_persona`

Operarias y personal de mantenimiento con seudónimo. Dimensión con rol (operaria / persona involucrada).

| Columna | Tipo | Llave | Nulo | Origen (linaje) | Regla de transformación |
|---|---|---|---|---|---|
| `sk_persona` | integer | PK / SK | no | Generado | — |
| `cod_persona` | character varying(12) | NK | no | Generado | OP-/MT-/OT- + consecutivo por orden alfabético del nombre normalizado |
| `rol` | character varying(30) |  | no | Tablas Desplegables lista de mantenimiento | Mantenimiento si está en la lista; Operaria si aparece como operario |
| `alias_publico` | character varying(40) |  | no | Generado | Seudónimo visible en tableros |

## `dw.dim_referencia`

Productos envasados con atributos derivados del nombre.

| Columna | Tipo | Llave | Nulo | Origen (linaje) | Regla de transformación |
|---|---|---|---|---|---|
| `sk_referencia` | integer | PK / SK | no | Derivado | — |
| `cod_referencia` | character varying(60) | NK | no | Base De Datos.Referencia y Tablas Desplegables.'Nombre de referencia' | normalizar_referencia(): 'Alocdor'→'Alocolor', '(6col)'→'(6 col)', '15 cc'→'15cc' |
| `nombre_referencia` | character varying(60) |  | no | Derivado | — |
| `marca` | character varying(30) |  | no | Derivado del nombre | Texto antes del tamaño |
| `tamano_cc` | smallint |  | sí | Derivado del nombre | Regex (\d+)cc |
| `n_colores` | smallint |  | sí | Derivado del nombre | Regex (N col); 125 cc → 1 |
| `familia_tamano` | character varying(20) |  | no | Derivado | — |

## `dw.estandar_produccion`

Velocidad ideal por máquina y referencia (base del rendimiento).

| Columna | Tipo | Llave | Nulo | Origen (linaje) | Regla de transformación |
|---|---|---|---|---|---|
| `sk_maquina` | integer | PK / SK | no | Llave | — |
| `sk_referencia` | integer | PK / SK | no | Llave | — |
| `unidades_por_paca` | numeric(8,1) |  | no | Tablas Desplegables.'Unidades * paca' | Si falta: otra máquina → mediana tamaño/colores → mezcla de la máquina |
| `unidades_por_minuto` | numeric(6,1) |  | no | Tablas Desplegables.'unidades *minuto' | Velocidad de la máquina |
| `pacas_hora_ideal` | numeric(8,3) |  | no | Calculado | 60 × u/min ÷ u/paca |
| `origen_estandar` | character varying(30) |  | no | Calculado | Marca de imputación |

## `dw.dim_causa_paro`

Jerarquía aplanada Código › Sistema › Componente.

| Columna | Tipo | Llave | Nulo | Origen (linaje) | Regla de transformación |
|---|---|---|---|---|---|
| `sk_causa` | integer | PK / SK | no | Generado | Jerarquía aplanada con relleno '(sin subcódigo)' / '(general)' |
| `cod_causa` | character varying(20) | NK | no | Generado | Jerarquía aplanada con relleno '(sin subcódigo)' / '(general)' |
| `cod_codigo` | character(2) | NK | no | Tablas Desplegables.KEY (paro01..paro18) | Dos dígitos |
| `codigo_desc` | character varying(80) |  | no | Tablas Desplegables.PARO | [18] sobrescrito a 'Desinfección' (clasificacion_codigos.csv) |
| `area_impacto` | character varying(40) |  | no | Tablas Desplegables.'ÁREA DE IMPACTO' | Sin cambios |
| `categoria_oee` | character varying(20) |  | no | etl/config/clasificacion_codigos.csv | Planificado / Disponibilidad / Calidad |
| `es_planificado` | boolean |  | no | Generado | Jerarquía aplanada con relleno '(sin subcódigo)' / '(general)' |
| `cod_sistema` | character varying(8) | NK | sí | Tablas Desplegables listas de subcódigos 1.x, 3.x, 5.x | Nivel 2 |
| `sistema_desc` | character varying(80) |  | no | Generado | Jerarquía aplanada con relleno '(sin subcódigo)' / '(general)' |
| `cod_componente` | character varying(8) | NK | sí | Tablas Desplegables listas de subcódigos | Nivel 3 (solo código 01) |
| `componente_desc` | character varying(80) |  | no | Generado | Jerarquía aplanada con relleno '(sin subcódigo)' / '(general)' |
| `nivel_detalle` | smallint |  | no | Generado | Jerarquía aplanada con relleno '(sin subcódigo)' / '(general)' |

## `dw.dim_motivo_no_programado`

Motivos por los que la línea no se programó, unificando dos catálogos.

| Columna | Tipo | Llave | Nulo | Origen (linaje) | Regla de transformación |
|---|---|---|---|---|---|
| `sk_motivo` | integer | PK / SK | no | Base De Datos.'Tipo de paro' + 'Observaciones de paro' | Regex de motivos_no_programado.csv y motivos_tipo_paro.csv |
| `cod_motivo` | character varying(80) | NK | no | Base De Datos.'Tipo de paro' + 'Observaciones de paro' | Regex de motivos_no_programado.csv y motivos_tipo_paro.csv |
| `motivo_estandar` | character varying(50) |  | no | Base De Datos.'Tipo de paro' + 'Observaciones de paro' | Regex de motivos_no_programado.csv y motivos_tipo_paro.csv |
| `responsable` | character varying(30) |  | no | Base De Datos.'Tipo de paro' + 'Observaciones de paro' | Regex de motivos_no_programado.csv y motivos_tipo_paro.csv |
| `observacion` | character varying(80) |  | no | Base De Datos.'Tipo de paro' + 'Observaciones de paro' | Regex de motivos_no_programado.csv y motivos_tipo_paro.csv |
| `es_controlable` | boolean |  | no | Base De Datos.'Tipo de paro' + 'Observaciones de paro' | Regex de motivos_no_programado.csv y motivos_tipo_paro.csv |

## `dw.fact_produccion_turno`

Grano: un registro de turno (máquina × fecha × turno × operaria × referencia).

| Columna | Tipo | Llave | Nulo | Origen (linaje) | Regla de transformación |
|---|---|---|---|---|---|
| `id_registro` | integer | PK | no | Base De Datos (fila del Excel) | Fila de origen: linaje |
| `sk_fecha` | integer | FK → dim_fecha | no | Base De Datos.Fecha | AAAAMMDD |
| `sk_maquina` | integer | FK → dim_maquina | no | Calculado | Bandera de calidad / atributo derivado |
| `sk_turno` | smallint | FK → dim_turno | no | Calculado | Bandera de calidad / atributo derivado |
| `sk_operario` | integer | FK → dim_persona | no | Base De Datos.Operario | Normalizado (personas_alias.csv); vacío → -1 |
| `sk_referencia` | integer | FK → dim_referencia | no | Base De Datos.Referencia | Normalizada; vacío/'No aplica' → -1 |
| `horas_trabajadas` | numeric(9,5) |  | no | Base De Datos.'Horas trabajadas' | Numérico |
| `horas_paro_planificado` | numeric(9,5) |  | no | Base De Datos.'Codigo de paro N' (min) | Σ/60 de códigos 04,16,17,18 del registro + sus continuaciones |
| `horas_paro_disponibilidad` | numeric(9,5) |  | no | Base De Datos.'Codigo de paro N' (min) | Σ/60 de códigos de disponibilidad |
| `horas_paro_calidad` | numeric(9,5) |  | no | Base De Datos.'Codigo de paro 11' | Σ/60 |
| `horas_paro_total` | numeric(9,5) |  | no | Calculado | Suma de las tres anteriores (= 'Tiempo de Paro' + continuaciones) |
| `tiempo_planificado_h` | numeric(9,5) |  | no | Calculado | máx(HT − planificado, 0) |
| `tiempo_operativo_h` | numeric(9,5) |  | no | Calculado | máx(TP − disponibilidad, 0) |
| `tiempo_ideal_h` | numeric(10,5) |  | sí | Calculado | pacas ÷ pacas_hora_ideal |
| `pacas_producidas` | numeric(8,1) |  | sí | Base De Datos.'Pacas producidas' | NULL si atípica (R18) |
| `pacas_meta` | numeric(8,1) |  | sí | Calculado | pacas_hora_ideal × factor × TP |
| `n_eventos_paro` | smallint |  | no | Calculado | Bandera de calidad / atributo derivado |
| `pacas_hora_ideal` | numeric(8,3) |  | sí | estandar_produccion | Lookup máquina × referencia |
| `origen_estandar` | character varying(30) |  | no | Calculado | Bandera de calidad / atributo derivado |
| `es_registro_historico` | boolean |  | no | Calculado | Bandera de calidad / atributo derivado |
| `dq_pacas_atipica` | boolean |  | no | Calculado | Bandera de calidad / atributo derivado |
| `dq_paro_mayor_turno` | boolean |  | no | Calculado | Bandera de calidad / atributo derivado |
| `es_valido_oee` | boolean |  | no | Calculado | HT>0 ∧ pacas válidas ∧ TN>0 |

## `dw.fact_paro`

Grano: un evento de paro (registro × código/subcódigo).

| Columna | Tipo | Llave | Nulo | Origen (linaje) | Regla de transformación |
|---|---|---|---|---|---|
| `id_paro` | bigint | PK | no | Generado | BIGSERIAL |
| `id_registro` | integer | DD | sí | Calculado | Registro de turno al que pertenece (R16) |
| `fila_origen` | integer | DD | no | Base De Datos (fila del Excel) | Linaje |
| `sk_fecha` | integer | FK → dim_fecha | no | Heredado de la fila de origen | — |
| `sk_maquina` | integer | FK → dim_maquina | no | Heredado de la fila de origen | — |
| `sk_turno` | smallint | FK → dim_turno | no | Heredado de la fila de origen | — |
| `sk_operario` | integer | FK → dim_persona | no | Heredado de la fila de origen | — |
| `sk_referencia` | integer | FK → dim_referencia | no | Heredado de la fila de origen | — |
| `sk_causa` | integer | FK → dim_causa_paro | no | Base De Datos.'Codigo de paro N' + 'Sub Codigo de paro 1' / 'Subcodigo 3' / 'Subcodigo 5' | Unpivot + normalización de subcódigo (R14, R15) |
| `sk_persona_involucrada` | integer | FK → dim_persona | no | Base De Datos.'Personal involucrado' | Solo para código 05 |
| `area_involucrada` | character varying(30) |  | no | Base De Datos.'Área involucrada en subcodigo 5' | Personal_de_mantenimiento → Mantenimiento |
| `minutos_paro` | numeric(7,2) |  | no | Base De Datos.'Codigo de paro N' | Minutos > 0 |
| `horas_paro` | numeric(10,6) |  | no | Calculado | minutos ÷ 60 |
| `es_fila_continuacion` | boolean |  | no | Heredado de la fila de origen | — |

## `dw.fact_tiempo_no_programado`

Grano: horas no programadas de una máquina en una fecha por un motivo.

| Columna | Tipo | Llave | Nulo | Origen (linaje) | Regla de transformación |
|---|---|---|---|---|---|
| `id_registro` | integer | PK | no | Heredado de la fila de origen | — |
| `sk_fecha` | integer | FK → dim_fecha | no | Heredado de la fila de origen | — |
| `sk_maquina` | integer | FK → dim_maquina | no | Heredado de la fila de origen | — |
| `sk_turno` | smallint | FK → dim_turno | no | Heredado de la fila de origen | — |
| `sk_motivo` | integer | FK → dim_motivo_no_programado | no | Base De Datos.'Tipo de paro' + 'Observaciones de paro' | Clasificación por regex (R20) |
| `horas_no_programadas` | numeric(6,2) |  | no | Base De Datos.'Horas no trabajadas' | Recorte a 24 h (R19) |
| `dq_horas_recortadas` | boolean |  | no | Heredado de la fila de origen | — |

## `dw.fact_produccion_hora`

Grano: una máquina × una hora (streaming simulado; futuro PLC/SCADA).

| Columna | Tipo | Llave | Nulo | Origen (linaje) | Regla de transformación |
|---|---|---|---|---|---|
| `id_lectura` | bigint | PK | no | simulador/simulador.py (futuro: PLC/SCADA) | Muestreo de la distribución histórica de cada máquina |
| `ts` | timestamp with time zone |  | no | simulador/simulador.py (futuro: PLC/SCADA) | Muestreo de la distribución histórica de cada máquina |
| `sk_fecha` | integer | FK → dim_fecha | no | simulador/simulador.py (futuro: PLC/SCADA) | Muestreo de la distribución histórica de cada máquina |
| `sk_maquina` | integer | FK → dim_maquina | no | simulador/simulador.py (futuro: PLC/SCADA) | Muestreo de la distribución histórica de cada máquina |
| `sk_turno` | smallint | FK → dim_turno | no | simulador/simulador.py (futuro: PLC/SCADA) | Muestreo de la distribución histórica de cada máquina |
| `sk_referencia` | integer | FK → dim_referencia | no | simulador/simulador.py (futuro: PLC/SCADA) | Muestreo de la distribución histórica de cada máquina |
| `sk_causa_principal` | integer | FK → dim_causa_paro | no | simulador/simulador.py (futuro: PLC/SCADA) | Muestreo de la distribución histórica de cada máquina |
| `minutos_planificados` | numeric(5,2) |  | no | simulador/simulador.py (futuro: PLC/SCADA) | Muestreo de la distribución histórica de cada máquina |
| `minutos_paro_disponibilidad` | numeric(5,2) |  | no | simulador/simulador.py (futuro: PLC/SCADA) | Muestreo de la distribución histórica de cada máquina |
| `minutos_paro_calidad` | numeric(5,2) |  | no | simulador/simulador.py (futuro: PLC/SCADA) | Muestreo de la distribución histórica de cada máquina |
| `pacas_producidas` | numeric(7,2) |  | no | simulador/simulador.py (futuro: PLC/SCADA) | Muestreo de la distribución histórica de cada máquina |
| `pacas_hora_ideal` | numeric(8,3) |  | no | simulador/simulador.py (futuro: PLC/SCADA) | Muestreo de la distribución histórica de cada máquina |
| `origen` | character varying(20) |  | no | simulador/simulador.py (futuro: PLC/SCADA) | Muestreo de la distribución histórica de cada máquina |
