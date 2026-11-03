# Reporte de calidad de datos y conciliación (generado por el ETL)

- Archivo fuente: `SEGUIMIENTO_TEMPERAS_Y_VINILOS_Actividad.xlsm`
- SHA-256: `c7d7eabbd55844757c2be07bd61efcee9eb5e0b03aaf9fd76b798737a92d5c55`
- Fecha de la corrida: 2026-11-01 19:39

## Filas cargadas por tabla

| Tabla | Filas |
|---|---:|
| `dw.dim_fecha` | 2,191 |
| `dw.dim_maquina` | 4 |
| `dw.dim_turno` | 9 |
| `dw.dim_persona` | 44 |
| `priv.persona_identidad` | 43 |
| `dw.dim_referencia` | 62 |
| `dw.estandar_produccion` | 143 |
| `dw.dim_causa_paro` | 66 |
| `dw.dim_motivo_no_programado` | 25 |
| `dw.fact_produccion_turno` | 4,742 |
| `dw.fact_paro` | 16,490 |
| `dw.fact_tiempo_no_programado` | 2,147 |

## Reglas de limpieza aplicadas

| # | Regla | Dimensión | Problema detectado | Acción | Antes | Afectadas | Después |
|---|---|---|---|---|---:|---:|---:|
| 1 | R01 | completitud | Filas completamente vacías dentro del rango de la tabla | Eliminadas | 8,208 | 0 | 8,208 |
| 2 | R02 | completitud | Columnas sin ningún dato: Unidades producidas cada minuto, Display por paca | Columnas descartadas del modelo | 8,208 | 0 | 8,208 |
| 3 | R03 | validez | Año guardado como texto; se valida contra la fecha. Mes en texto se reemplaza por la dimensión fecha | Año convertido a entero; fechas inválidas: 0; año≠fecha: 0 | 8,208 | 0 | 8,208 |
| 4 | R04 | validez | La columna 'Unidad por display' no trae unidades: en 687 filas tiene una copia del turno (3 escritas distinto, p. ej. '10pm-6am' sin '(Turno 3)') | Columna descartada; se usa solo para rellenar Turno vacío (0 casos) | 8,208 | 687 | 8,208 |
| 5 | R05 | consistencia | Turno con 7 escrituras distintas y 3912 vacíos (registros 2022-2023) | Mapeado a catálogo dim_turno; vacíos -> 'Sin turno (histórico)' | 8,208 | 4,248 | 8,208 |
| 6 | R06 | consistencia | La tabla mezcla 4 tipos de fila: registro de turno ('Ingreso total'), continuación de paros ('Ingreso subcódigo'), día no programado y filas sin actividad. Conteo: continuacion=1336, no_programado=1863, produccion=4759, sin_actividad=250 | Cada tipo se enruta a su tabla de hechos | 8,208 | 3,449 | 8,208 |
| 7 | R07 | unicidad | Filas idénticas en todos los campos (registros de turno / días no programados). Además hay 8 filas de continuación idénticas que SÍ se conservan (dos paros iguales en el mismo turno son posibles) | Se conserva la primera aparición | 8,208 | 25 | 8,183 |
| 8 | R08 | consistencia | Nombres de personas con variantes ortográficas (p. ej. 'Argüello Molsalve' vs 'Arguello Monsalve', 'Luis Mercado' vs 'Luis Carlos Mercado Mercado') y valores 'No'/'No aplica'/vacíos. Los nombres con inicial distinta ('Marcela' / 'Marcela C.') se tratan como personas diferentes | Unificadas con personas_alias.csv; 43 personas únicas (antes 72 escrituras) | 72 | 6 | 43 |
| 9 | R09 | completitud | Registros de turno/paro sin operaria (mayoría 2022-2023) | Asignados al miembro -1 'No registrado' | 6,078 | 2,234 | 6,078 |
| 10 | R10 | consistencia | Referencias escritas de varias formas ('Alocdor 22cc (6col)', 'Stilo/Estilo Kids', 'Klips 15cc (12col)', '15 cc' vs '15cc') | Normalizadas: 52 escrituras -> 48 referencias | 8,183 | 506 | 8,183 |
| 11 | R11 | completitud | Registros de turno sin referencia (2022-2023 o 'No aplica') | Miembro -1 'No registrada'; la velocidad ideal se imputa con el promedio de la máquina | 4,742 | 2,210 | 4,742 |
| 12 | R12 | unicidad | Tabla de estándares (Tabla8/14/15/16): filas 'No aplica', referencias repetidas en la misma máquina y una fila de Vinilos_2 dentro de la tabla de Vinilos_1 | Se eliminan vacías/duplicadas; la velocidad de cada máquina es la moda de su tabla | 135 | 5 | 130 |
| 13 | R13 | completitud | Combinaciones máquina×referencia producidas sin estándar de velocidad en las tablas del Excel. Origen del estándar: tabla_maquina=73, imputado_mezcla_maquina=6, imputado_tamano=4, otra_maquina=3 | Imputación jerárquica: misma referencia en otra máquina -> mediana por tamaño/colores -> velocidad de mezcla de la máquina (registros sin referencia). Queda marcado en origen_estandar | 86 | 13 | 86 |
| 14 | R14 | consistencia | Formato ancho: 18 pares de columnas 'Código N'/'Código N en horas' (147294 celdas). Los minutos coinciden con las horas en el 100 % de las filas y 'Tiempo de Paro' = suma de códigos | Unpivot a una fila por evento de paro con minutos > 0 | 147,294 | 130,804 | 16,490 |
| 15 | R15 | consistencia | Subcódigos con dos catálogos (código 5: '4.2 SISTEMA DOSIFICADOR...' vs '5.2 Sistema de dosificación...'; código 1: '1.2C' vs '1.2.C', '1.4.3' vs '1.4.C') | Normalizados a la llave oficial con subcodigos_equivalencias.csv; 0 sin catálogo subidos al nivel superior | 16,490 | 1,113 | 16,490 |
| 16 | R16 | integridad | Filas de continuación ('Ingreso subcódigo') que deben sumarse a su registro de turno. Enlazadas por llave completa: 1286; por fecha+máquina+turno: 32 | Sus paros se agregan al registro; las no enlazables quedan como paros huérfanos (id_registro NULL) | 1,336 | 18 | 1,336 |
| 17 | R17 | exactitud | Registros de turno cuyo tiempo de paro supera las horas trabajadas | Se marcan (dq_paro_mayor_turno); el tiempo operativo se acota en 0 | 4,742 | 5 | 4,742 |
| 18 | R18 | exactitud | Pacas imposibles: más de 2× lo que la máquina produce a velocidad ideal en las horas del turno (p. ej. 4.320 a 9.417 'pacas' en 8 h en Vinilos_1, jul-2023: se digitaron unidades) | Pacas -> NULL en el hecho (excluidas de rendimiento/OEE); valor original queda en stg | 4,740 | 25 | 4,740 |
| 19 | R19 | validez | Horas no trabajadas mayores a 24 en un solo registro (máx. 32) | Recortadas a 24 h y marcadas | 2,147 | 1 | 2,147 |
| 20 | R20 | consistencia | 'Tipo de paro' usa dos catálogos (viejo '17. PARO DE MAQUINA' y nuevo '[18] Paro de maquina por ventas'; 19 valores) y la observación tiene errores ('FALTADE', 'RESESO', 'NO SE PROGRAMOS') | Unificados en 11 motivos estándar con responsable | 2,147 | 13 | 2,147 |

## Conciliación de totales fuente vs. DW

| Métrica | Fuente | DW | Diferencia | % | Explicación |
|---|---:|---:|---:|---:|---|
| Filas de la Base De Datos | 8,208.00 | 8,183.00 | 25.00 | 0.30 % | Duplicados exactos eliminados: 25. Las filas se reparten en: registros de turno=4742, continuaciones=1336, no programado=1855, sin actividad=250 |
| Horas trabajadas | 38,063.35 | 37,934.35 | 129.00 | 0.34 % | 129.00 h de filas duplicadas eliminadas + 0.00 h en filas que no son registro de turno. Residuo sin explicar: 0.000 h |
| Pacas producidas | 378,778.00 | 322,794.00 | 55,984.00 | 14.78 % | 1019 pacas de duplicados + 54965 'pacas' atípicas anuladas (regla R18, eran unidades) + 0 en filas fuera de producción. Residuo: 0.0 |
| Tiempo de paro (h) · fact_paro | 8,449.65 | 8,435.33 | 14.32 | 0.17 % | 14.32 h de paros en filas duplicadas eliminadas (las continuaciones idénticas se conservan). Residuo: 0.000 h |
| Tiempo de paro (h) · fact_produccion_turno | 8,435.33 | 8,361.68 | 73.65 | 0.87 % | 73.65 h de paros que no pertenecen a un registro de turno (continuaciones sin encabezado o paros anotados en días no programados). Se conservan en fact_paro para el Pareto |
| Horas no trabajadas | 41,519.85 | 41,335.85 | 184.00 | 0.44 % | 176.00 h de duplicados + 8.00 h recortadas por superar 24 h (R19). Residuo: 0.000 h |
| Paros con subcódigo (h) · hoja 'Sub codigos' encontrados en la Base De Datos | 620.18 | 620.18 | 0.00 | 0.00 % | 1124 de 1124 eventos de la hoja (códigos 1, 3 y 5) existen en la Base De Datos con la misma fecha, máquina, operaria, código y minutos: la hoja es una copia del detalle y NO se carga (se duplicarían paros) |
