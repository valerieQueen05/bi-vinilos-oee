# Power BI · tablero analítico

## Formato elegido: **PBIP (Power BI Project)** con modelo en **TMDL**

| Formato | ¿Sirve en Git? | Por qué |
|---|---|---|
| `.pbix` | ❌ | Binario comprimido: Git no puede mostrar diferencias ni fusionar cambios de los dos integrantes. Además guarda una copia de los datos (con nombres de personas). |
| `.pbit` | ⚠️ | Plantilla sin datos, pero sigue siendo binaria. |
| **`.pbip` + TMDL** | ✅ | Guarda el modelo semántico como archivos de texto (`*.tmdl`, una tabla por archivo) y el reporte como JSON. Cada medida DAX nueva aparece como una línea en el `git diff`, se puede revisar en un *pull request* y **no incluye datos** (solo la definición). |

Activar en Power BI Desktop: *Archivo → Opciones → Características en versión preliminar →* **Guardar como proyecto de Power BI (.pbip)** y **Formato TMDL del modelo semántico**. Luego *Archivo → Guardar como →* `powerbi/BI_Vinilos_OEE.pbip`.

El `.gitignore` ya excluye `localSettings.json` y `cache.abf` (la caché con datos).

## Atajo: crear TODO el modelo de una vez (vista TMDL)

`modelo_powerbi.tmdl` crea en un solo paso las 10 tablas (conectadas a PostgreSQL), las 16 relaciones, las 4 jerarquías, la tabla de fecha marcada y las 43 medidas DAX organizadas en carpetas.

1. Abrir Power BI Desktop → vista **TMDL** (último ícono de la barra izquierda).
2. Pegar todo el contenido de `modelo_powerbi.tmdl` y presionar **Aplicar**.
3. *Inicio → Actualizar*. Cuando pida credenciales: **Base de datos**, usuario `bi_lector` y la contraseña de `BI_LECTOR_PASSWORD`. Si pregunta por cifrado, aceptar sin cifrado.
4. Si el servidor no es `172.16.213.1:5432` (la IP del Mac vista desde VMware), cambiar el parámetro en *Transformar datos → Administrar parámetros → ServidorPostgres*. En un Windows normal con Docker, usar `localhost:5432`.

Las secciones 1 y 2 explican lo mismo paso a paso, por si prefieren hacerlo a mano.

## 1. Conexión (a la base de datos, nunca al Excel)

1. *Obtener datos → Base de datos PostgreSQL*.
2. Servidor: `localhost:5432` · Base de datos: `bi_vinilos` · Modo: **Importar**.
3. Credenciales: *Base de datos* → usuario `bi_lector` y la contraseña de `BI_LECTOR_PASSWORD` del `.env`. Es un rol **de solo lectura** que no puede ver el esquema `priv` (los nombres reales).
4. Seleccionar las tablas del esquema `dw`:
   `dim_fecha, dim_maquina, dim_turno, dim_persona, dim_referencia, dim_causa_paro, dim_motivo_no_programado, fact_produccion_turno, fact_paro, fact_tiempo_no_programado`.
   Opcional para la página de calidad de datos: `audit.regla_calidad`, `audit.conciliacion`.
5. En Power Query quitar el prefijo `dw ` de los nombres de las tablas.

> **¿Por qué Importar y no DirectQuery?** El histórico es pequeño (≈ 25 mil filas), cambia una vez al mes (cuando se corre el ETL) y el comité necesita respuestas rápidas con inteligencia de tiempo. El monitoreo en vivo es trabajo de Grafana.

## 2. Modelo semántico (estrella)

Relaciones (todas **varios a uno, dirección simple**, de la dimensión al hecho):

| Desde (hecho) | Hacia (dimensión) | Activa |
|---|---|---|
| `fact_produccion_turno[sk_fecha]` | `dim_fecha[sk_fecha]` | ✅ |
| `fact_produccion_turno[sk_maquina]` | `dim_maquina[sk_maquina]` | ✅ |
| `fact_produccion_turno[sk_turno]` | `dim_turno[sk_turno]` | ✅ |
| `fact_produccion_turno[sk_operario]` | `dim_persona[sk_persona]` | ✅ |
| `fact_produccion_turno[sk_referencia]` | `dim_referencia[sk_referencia]` | ✅ |
| `fact_paro[sk_fecha / sk_maquina / sk_turno / sk_referencia]` | dimensiones respectivas | ✅ |
| `fact_paro[sk_causa]` | `dim_causa_paro[sk_causa]` | ✅ |
| `fact_paro[sk_operario]` | `dim_persona[sk_persona]` | ✅ |
| `fact_paro[sk_persona_involucrada]` | `dim_persona[sk_persona]` | ❌ inactiva (rol "persona involucrada"; se usa con `USERELATIONSHIP`) |
| `fact_tiempo_no_programado[sk_fecha / sk_maquina / sk_turno]` | dimensiones respectivas | ✅ |
| `fact_tiempo_no_programado[sk_motivo]` | `dim_motivo_no_programado[sk_motivo]` | ✅ |

Configuración:
- `dim_fecha` → *Marcar como tabla de fechas* (columna `fecha`). Ordenar `mes_nombre` por `mes_num`.
- Ocultar todas las columnas `sk_*` y las medidas aditivas crudas de los hechos (se usan las medidas).
- **Jerarquías:**
  - `dim_fecha`: **Calendario** = `anio › trimestre › mes_nombre › fecha`
  - `dim_causa_paro`: **Causa de paro** = `codigo_desc › sistema_desc › componente_desc` ← drill-down obligatorio
  - `dim_referencia`: **Producto** = `familia_tamano › marca › nombre_referencia`
  - `dim_maquina`: **Planta** = `linea › cod_maquina`
- Crear una tabla vacía `_Medidas` (*Especificar datos* con una columna que luego se oculta) y pegar las medidas de [`medidas.dax`](medidas.dax) (respetar las carpetas de visualización indicadas).

## 3. Páginas sugeridas (mínimo 3, con navegación por botones)

| Página | Pregunta que responde | Visuales clave |
|---|---|---|
| **1. Resumen ejecutivo** | ¿Cómo va la planta y cómo se compara con el año anterior? | Tarjetas OEE / Disponibilidad / Rendimiento / Calidad / Pacas YTD vs AA · Línea OEE mensual vs `OEE Año Anterior` y `OEE Meta` · Segmentaciones Año, Máquina, Turno |
| **2. Causas de paro** | ¿Qué pocas causas explican la mayoría del tiempo perdido? | **Pareto** (gráfico combinado: columnas `Horas Paro (eventos)` + línea `Pareto % Acumulado`, eje `codigo_desc`, línea de referencia 80 %) · Matriz con jerarquía **Causa de paro** (drill-down código → sistema → componente) · Segmentación `categoria_oee` |
| **3. Máquinas y turnos** | ¿Qué línea y qué turno rinden menos? | Matriz máquina × mes con formato condicional `OEE Semáforo` · Barras OEE por turno · MTBF / MTTR por máquina |
| **4. Capacidad no programada** | ¿Cuánta capacidad se pierde sin siquiera programar la línea, y por qué? | Utilización y TEEP · Barras por `motivo_estandar` y `responsable` · Anillo controlable vs no controlable |
| 5. Calidad de datos (opcional) | ¿Qué tan confiables son las cifras? | Tabla `audit.regla_calidad` · `% Turnos con Estándar Imputado` · tabla `audit.conciliacion` |

Botones de navegación: *Insertar → Botones → Navegador → Navegador de páginas*.

## 4. Valores de control (para verificar que el modelo quedó bien)

Con todo el periodo y sin filtros, Power BI debe mostrar exactamente lo mismo que las vistas SQL:

| Año | Horas trabajadas | % Productividad | Pacas | Disponibilidad | Rendimiento | OEE |
|---|---:|---:|---:|---:|---:|---:|
| 2022 | 7.870,0 | 87,70 % | 59.298 | 91,67 % | 77,75 % | 71,27 % |
| 2023 | 12.746,4 | 79,71 % | 100.876 | 84,76 % | 78,33 % | 66,39 % |
| 2024 | 14.501,0 | 72,65 % | 137.124 | 80,66 % | 90,96 % | 73,32 % |
| 2025 (ene-mar) | 2.817,0 | 70,16 % | 25.496 | 78,25 % | 94,17 % | 73,62 % |
| **Total** | **37.934,4** | **77,96 %** | **322.794** | **84,24 %** | **83,77 %** | **70,55 %** |

`Horas Paro (eventos)` total = 8.435,34 h en 16.490 eventos · `Horas No Programadas` = 41.336 h.

## 5. Preguntas típicas del docente en vivo (y cómo responderlas)

- *"Agregue el OEE del trimestre anterior"* → `OEE Trimestre Anterior = CALCULATE([OEE], DATEADD(dim_fecha[fecha], -1, QUARTER))`
- *"¿Por qué el OEE no es el promedio de los OEE mensuales?"* → porque es `DIVIDE` de sumas de tiempo: un mes con pocas horas no puede pesar igual que uno con muchas.
- *"Muestre el top 3 de componentes de la falla electromecánica"* → filtro de nivel visual *N superior = 3* por `Horas Paro (eventos)` sobre `componente_desc` con `cod_codigo = "01"`.
