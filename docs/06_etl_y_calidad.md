# 6. Proceso ETL, calidad de datos y conciliación

## 6.1 Herramienta: **Python (pandas + openpyxl + psycopg2)**, en contenedor

| Alternativa | Por qué no / por qué sí |
|---|---|
| Power Query | Quedaría "atrapado" dentro del archivo de Power BI: Grafana no vería los datos limpios y no se podría correr desde Docker ni versionar con diferencias legibles. |
| Solo SQL | PostgreSQL no lee `.xlsm` directamente; habría que exportar a CSV a mano (paso no reproducible). |
| **Python** ✅ | Lee el `.xlsm` sin ejecutar macros, deja cada regla de limpieza como código revisable en Git, corre igual en cualquier equipo dentro de Docker, y escribe la bitácora de calidad en la propia base (`audit.*`). Es el mismo lenguaje del simulador. |

Ejecución: `docker compose up` lo corre automáticamente; para volver a cargar: `docker compose run --rm etl`.

## 6.2 Flujo (todo en una sola transacción)

```
extract.py      Lee "Base De Datos", "Sub codigos" y los catálogos/estándares de "Tablas Desplegables". Calcula el SHA-256 del archivo.
   │
load.py         Ejecuta sql/ddl/01..06 → borra y recrea los esquemas (proceso DESDE CERO, idempotente)
   │            Copia cruda a stg.base_de_datos, stg.sub_codigos, stg.estandares (todo TEXT: linaje exacto)
   │
transform.py    R01-R05 limpieza básica · R06 clasifica filas · R07 duplicados · R08-R09 personas
   │            R10-R11 referencias · R12-R13 estándares · R14-R15 unpivot de paros y subcódigos
   │            R16 enlace de continuaciones · R17-R18 exactitud · R19-R20 tiempo no programado
   │
load.py         Dimensiones (con miembro -1) → hechos
   │
conciliacion.py Compara totales de la fuente vs. lo cargado (consultando la BD, no los DataFrames)
   │
main.py         Escribe audit.etl_corrida / regla_calidad / conciliacion y docs/generados/*.md, *.csv
```

Si cualquier paso falla se hace *rollback*: nunca queda una carga a medias.

## 6.3 Reglas de limpieza y su efecto

El detalle **con conteos antes / afectadas / después de la última corrida** se genera automáticamente en
[`generados/calidad_y_conciliacion.md`](generados/calidad_y_conciliacion.md) y en la tabla `audit.regla_calidad`.
Resumen de la corrida de referencia:

| Regla | Problema | Acción | Filas afectadas |
|---|---|---|---:|
| R01 | Filas vacías en el rango de la tabla | Eliminar | 0 |
| R02 | 2 columnas 100 % vacías | Descartar columnas | — |
| R03 | Año como texto | Convertir y validar contra la fecha | 0 incoherencias |
| R04 | "Unidad por display" contiene el turno | Descartar; usar solo para rellenar | 687 |
| R05 | Turno con 7 escrituras y 3.912 vacíos | Mapear a `dim_turno`; vacío → "Sin turno (histórico)" | 4.248 |
| R06 | 4 tipos de fila mezclados | Clasificar y enrutar a su hecho | 3.449 |
| R07 | Duplicados exactos | Eliminar (se conservan continuaciones iguales) | 25 |
| R08 | Variantes de nombres de personas | Unificar con `personas_alias.csv` | 72 → 43 personas |
| R09 | Turnos sin operaria | Miembro -1 | 2.234 |
| R10 | Variantes de referencias | Normalizar | 506 |
| R11 | Turnos sin referencia | Miembro -1 + estándar de mezcla | 2.210 |
| R12 | Estándares duplicados o mal ubicados | Depurar | 5 |
| R13 | Combinaciones sin estándar de velocidad | Imputación jerárquica marcada | 13 de 86 |
| R14 | 18 pares de columnas de códigos | *Unpivot* a 16.490 eventos | — |
| R15 | Dos catálogos de subcódigos | Normalizar a llave oficial | 1.113 |
| R16 | Continuaciones sin enlazar a su turno | Enlazar por llave completa / corta | 18 huérfanas |
| R17 | Paro > horas trabajadas | Marcar; acotar tiempo operativo en 0 | 5 |
| R18 | Pacas imposibles (eran unidades) | Pacas → NULL en el hecho; marcar | 25 |
| R19 | Horas no trabajadas > 24 | Recortar a 24 y marcar | 1 |
| R20 | Dos catálogos de tipo de paro | Unificar en 11 motivos | 13 sin especificar |

## 6.4 Conciliación de totales (fuente vs. DW)

| Métrica | Fuente | DW | Diferencia | Explicación |
|---|---:|---:|---:|---|
| Filas | 8.208 | 8.183 | 25 | Duplicados exactos (R07) |
| Horas trabajadas | 38.063,35 | 37.934,35 | 129,00 | 129,00 h de los 25 duplicados. **Residuo 0** |
| Pacas producidas | 378.778 | 322.794 | 55.984 | 1.019 de duplicados + 54.965 "pacas" que eran unidades (R18). **Residuo 0** |
| Tiempo de paro (h) | 8.449,65 | 8.435,33 | 14,32 | Paros de los duplicados. **Residuo 0** |
| Paro dentro de turnos | 8.435,33 | 8.361,68 | 73,65 | Paros en continuaciones huérfanas o en días no programados: quedan en `fact_paro` (Pareto) pero no en un turno |
| Horas no trabajadas | 41.519,85 | 41.335,85 | 184,00 | 176 h de duplicados + 8 h recortadas (R19). **Residuo 0** |
| Hoja "Sub codigos" | 620,18 h | 620,18 h | 0 | Los 1.124 eventos ya están en la Base De Datos → no se carga (evita duplicar) |

Toda diferencia queda **explicada al 100 %** con un residuo de 0,000.

## 6.5 Supuestos documentados

1. **Clasificación OEE de los códigos** (`clasificacion_codigos.csv`): 04, 16, 17 y 18 son planificados; 11 es calidad; el resto, disponibilidad. El 15 (cambio de insumos) el catálogo lo llama "paro programado", pero se trata como pérdida de *setup* (evitable con SMED).
2. **Calidad** es un *proxy* por tiempo de reproceso: la fuente no registra unidades rechazadas.
3. **Velocidad ideal** de los registros 2022-2023 sin referencia: velocidad de mezcla de la máquina (media armónica ponderada por las pacas de los turnos con referencia). Esos turnos quedan marcados `origen_estandar = 'imputado_mezcla_maquina'` y se pueden filtrar.
4. Los nombres "Marcela" y "Marcela C." (y casos similares) se tratan como **personas distintas**, porque la inicial es justamente lo que las operarias usan para diferenciarse.
