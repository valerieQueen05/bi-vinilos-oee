# 2. Diagnóstico de la fuente

## 2.1 Estructura del libro `SEGUIMIENTO TEMPERAS Y VINILOS Actividad.xlsm`

| Hoja | Contenido | Uso en el proyecto |
|---|---|---|
| **Base De Datos** (tabla `T_baseDeDatos`, A9:BF8217) | 8.208 filas × 58 columnas, ene-2022 a mar-2025 | **Fuente principal** de hechos |
| Base de datos de Sub codigos (A8:S1260) | 1.252 filas de paros con subcódigo (oct-2023 a may-2024) | Solo conciliación: el 100 % de sus eventos ya está en la Base (ver reporte) |
| Tablas Desplegables | Catálogo de códigos [01]–[18] con área de impacto; subcódigos 1.x, 3.x y 5.x; **tablas de estándares** por máquina (Tabla8/14/15/16: unidades/paca y unidades/minuto); listas de turnos, operarias y personal de mantenimiento | Dimensiones y estándar de velocidad |
| TABLA CODIGOS | Catálogo impreso de códigos y subcódigos | Contraste (tiene diferencias con las listas) |
| Registro / Calculadora de tiempos / Tiempos | Formulario de captura (macros) y fórmulas de meta | Reglas de negocio: minutos de aseo (40 o 70) y pausa activa (3 o 6), factor 0,93 (V1) y 0,96 (V2) |
| TD_* y gráficos | Tablas dinámicas del informe mensual | Indicadores actuales a replicar |

Indicadores que calcula hoy el Excel (campos calculados de la caché dinámica):
`% Productividad = (Horas trabajadas − Tiempo de paro) / Horas trabajadas`, `% Paro = 1 − % Productividad` y `% Código N = Código N en horas / Horas trabajadas`, por máquina, mes y año.

## 2.2 Problemas de calidad de datos encontrados

| # | Problema | Evidencia | Dimensión DQ |
|---|---|---|---|
| 1 | **Una tabla, cuatro tipos de fila**: registro de turno, continuación de paros ("Ingreso subcódigo"), día no programado y filas sin actividad | 4.759 / 1.336 / 1.863 / 250 | Consistencia |
| 2 | **Esquema ancho**: 18 pares de columnas *Código N (min)* / *Código N en horas*; solo 3 códigos tienen subcódigo | 147.294 celdas para 16.490 paros reales | Diseño |
| 3 | **Duplicados exactos** | 25 registros (129 h, 1.019 pacas) | Unicidad |
| 4 | **Pacas imposibles** (se digitaron unidades): 4.128 a 9.417 "pacas" en 8 h en Vinilos_1, jul-2023 | 25 registros = 54.965 "pacas" (14,5 % del total) | Exactitud |
| 5 | **Turno**: 7 escrituras distintas + 3.912 vacíos (2022-2023 no lo registraban) | — | Completitud / consistencia |
| 6 | **Columna mal rotulada**: "Unidad por display" contiene una copia del turno | 687 filas | Validez |
| 7 | **Columnas vacías**: "Unidades producidas cada minuto" y "Display por paca" | 100 % nulas | Completitud |
| 8 | **Operaria y referencia vacías** en registros de 2022-2023 | 2.210 de 4.742 turnos sin referencia | Completitud |
| 9 | **Nombres de personas** con variantes ("Argüello Molsalve" / "Arguello Monsalve", "Luis Mercado" / "Luis Carlos Mercado Mercado"), "No" y "No aplica" | 72 escrituras → 43 personas | Consistencia |
| 10 | **Referencias** con variantes ("Alocdor", "Stilo/Estilo Kids", "(6col)", "15 cc") | 52 escrituras → 48 referencias | Consistencia |
| 11 | **Dos catálogos de subcódigos** para el código 5 (4.x viejo vs 5.x nuevo) y escrituras "1.2C" vs "1.2.C", "1.4.3" para la llave 1.4.C | 1.113 eventos normalizados | Consistencia |
| 12 | **Dos catálogos de "Tipo de paro"** (viejo "17. PARO DE MAQUINA", nuevo "[18] Paro de maquina por ventas") y observaciones con errores ("FALTADE", "RESESO", "NO SE PROGRAMOS") | 19 valores → 11 motivos | Consistencia |
| 13 | **Código 18 ambiguo**: la columna es "Desinfección" (hoja Registro) pero la lista desplegable lo llama "Paro de máquina" (área Ventas) | — | Consistencia |
| 14 | **Estándares incompletos**: combinaciones máquina×referencia producidas sin velocidad estándar; una fila de Vinilos_2 dentro de la tabla de Vinilos_1; "Klips 15cc (12 col)" con 6 colores | 13 de 86 combinaciones | Completitud |
| 15 | **Paro > horas trabajadas** en el mismo registro | 5 registros | Exactitud |
| 16 | **Horas no trabajadas > 24** en un registro | 1 (32 h) | Validez |
| 17 | **Huecos de cobertura**: jun-2022 sin registros y jul–sep-2022 casi vacíos | 0 / 11 / 6 / 8 filas | Completitud |
| 18 | Año guardado como **texto**; mes como texto | — | Validez |
| 19 | **Documento**: el PDF del procedimiento dice P-MTO-22 pero el archivo se llama P-MTO-21; lista 17 códigos mientras el Excel usa 18 (+ "[19] No aplica") | — | Gobierno de datos |
| 20 | **Sin datos de calidad de producto** (unidades rechazadas o reprocesadas): el componente Calidad del OEE solo puede aproximarse con el tiempo de reproceso (código 11) | — | Completitud |

Las reglas que trata cada problema, con conteos antes y después, están en [`generados/calidad_y_conciliacion.md`](generados/calidad_y_conciliacion.md) (lo genera el ETL en cada corrida).

## 2.3 Limitaciones del esquema actual de reporte

- **Captura doble y manual**: formato en papel → producción → mantenimiento → Excel. Latencia de días y errores de digitación (problema 4).
- **El informe es mensual**: nadie ve una falla mientras ocurre.
- **No calcula OEE**: el "% Productividad" solo mira tiempo de paro; ignora la velocidad (rendimiento) y el tiempo planificado (aseo y pausas cuentan como pérdida).
- **Promedios engañosos**: las tablas dinámicas suman por fila sin distinguir filas de continuación ni duplicados.
- **Análisis limitado a 3 códigos** (01, 03, 05) y a comparativos 2024 vs 2025 armados a mano.
- **No escala** (8 mil filas, macros, un solo usuario a la vez) y **expone datos personales** (nombres completos del personal) a cualquiera que abra el archivo.
- **Sin trazabilidad**: no queda registro de quién cambió qué ni de qué versión se usó para el comité.
