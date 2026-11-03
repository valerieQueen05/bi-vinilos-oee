# 3. Catálogo de indicadores

## 3.1 Definiciones de tiempo (base de todos los indicadores)

```
Horas trabajadas (HT) ─┬─ Paros planificados (04 preventivo, 16 aseo/alimentación, 17 pausa activa, 18 desinfección)
                       └─ Tiempo planificado (TP) ─┬─ Paros de disponibilidad (01-03, 05-10, 12-15)
                                                   └─ Tiempo operativo (TO) ─┬─ Paros de calidad (11 reproceso)
                                                                             └─ Tiempo neto (TN) ─┬─ Pérdida de velocidad
                                                                                                  └─ Tiempo ideal (TI) = Pacas / pacas-hora ideal
Pacas-hora ideal = 60 × unidades por minuto (máquina) / unidades por paca (referencia)   ← Tablas Desplegables
```

La clasificación de cada código está en `etl/config/clasificacion_codigos.csv` (editable sin tocar código).

## 3.2 Indicadores que hoy reporta el P-MTO-22 (se replican)

| Indicador | Fórmula | Unidad | Granularidad | Meta / umbral | Fuente (DW) | Usuario |
|---|---|---|---|---|---|---|
| **% Productividad** | (Σ HT − Σ Tiempo de paro) / Σ HT | % | Máquina × mes × año | ≥ 80 % (propuesta) | `fact_produccion_turno` · vista `v_kpi_maquina_mes.pct_productividad` · DAX `[% Productividad]` | Coordinador de mantenimiento, comité |
| **% Paro** | 1 − % Productividad | % | Máquina × mes × año | ≤ 20 % | ídem | ídem |
| **% Código N** | Σ horas del código N / Σ HT | % | Máquina × mes × año × código | Pareto: atacar clase A | `fact_paro` + `fact_produccion_turno` · vista `v_paro_codigo_mes` · DAX `[% Código s/ Horas Trabajadas]` | Mantenimiento, producción |
| **Producción (pacas)** | Σ pacas producidas | pacas | Máquina × mes × año (comparativo entre años) | Pacas meta | `fact_produccion_turno.pacas_producidas` · DAX `[Pacas]` | Producción, comité |
| **Análisis de códigos 01, 03 y 05 por subcódigo** | Σ horas por subcódigo / Σ horas del código | % | Código × sistema × componente | — | `fact_paro` + `dim_causa_paro` (jerarquía) | Mantenimiento |

## 3.3 Indicadores nuevos que el Excel no calcula

| Indicador | Fórmula | Unidad | Granularidad | Meta / umbral | Fuente | Usuario | ¿Por qué se propone? |
|---|---|---|---|---|---|---|---|
| **OEE** | TI / TP = A × P × Q | % | Turno → día → mes → año; máquina | Meta 75 %; clase mundial 85 %; mínimo de planta 60 %; **alerta < P25 de la máquina** | `fact_produccion_turno`, `fact_produccion_hora` | Gerencia, supervisores | El % Productividad ignora la velocidad y cuenta el aseo como pérdida. El OEE es el estándar de la industria y separa *dónde* se pierde |
| **Disponibilidad (A)** | TO / TP | % | ídem | ≥ 90 % | ídem | Mantenimiento | Aísla las pérdidas por paros |
| **Rendimiento (P)** | TI / TN | % | ídem | ≥ 95 % | ídem + `estandar_produccion` | Producción, ingeniería | Mide micro-paradas y velocidad reducida que nadie anota como paro |
| **Calidad (Q)** | TN / TO (proxy por tiempo de reproceso) | % | ídem | ≥ 99 % | ídem | Calidad | Completa el OEE; documenta que hace falta registrar rechazos |
| **Cumplimiento de meta** | Σ pacas / Σ (pacas-hora ideal × factor máquina × TP) | % | Turno, referencia, máquina | ≥ 100 % | `fact_produccion_turno.pacas_meta` | Supervisores | Usa la meta de la "Calculadora de tiempos" que hoy se calcula registro por registro y no se acumula |
| **MTBF** | Horas operativas / nº fallas (01+02) | h | Máquina × año | ↑ cada año | `fact_produccion_turno` + `fact_paro` | Mantenimiento | Mide confiabilidad; guía el plan preventivo |
| **MTTR** | Minutos de falla / nº fallas | min | Máquina × año | ≤ 30 min | `fact_paro` | Mantenimiento | Mide la velocidad de respuesta de mantenimiento |
| **Pareto de causas (% acumulado, clase ABC)** | Σ horas causa ordenadas / Σ total | % | Código / sistema / componente | Clase A = 80 % | `fact_paro` | Comité, mantenimiento | Prioriza dónde invertir |
| **Utilización** | HT / (HT + horas no programadas) | % | Máquina × mes | — | `fact_tiempo_no_programado` | Gerencia, planeación | Cuantifica la capacidad ociosa (sin demanda, sin material) |
| **TEEP** | OEE × Utilización | % | Máquina × mes | — | ídem | Alta dirección | Productividad sobre el tiempo calendario: base para decidir si se necesita otra línea |
| **Horas no programadas controlables** | Σ horas con `es_controlable` | h | Motivo × responsable | ↓ | `dim_motivo_no_programado` | Compras, almacén, planeación | Asigna responsable a la capacidad perdida por falta de material |
| **Duración media del paro** | Σ minutos / nº eventos | min/evento | Código | — | `fact_paro` | Mantenimiento | Distingue muchos paros cortos de pocos largos |
| **% turnos con estándar imputado** | Turnos con `origen_estandar ≠ tabla_maquina` / turnos | % | Máquina × año | ↓ | `fact_produccion_turno` | Ingeniería, analistas | Transparencia: dice qué tan confiable es el rendimiento calculado |

## 3.4 Umbral de la alerta operativa (Grafana)

**Índice = OEE promedio de las últimas 3 horas de la máquina ÷ percentil 25 histórico de esa misma máquina. Alerta si el índice < 1 durante 1 minuto.**

Distribución del OEE por turno (2024-2025, turnos con ≥ 6 h planificadas), vista `dw.v_umbral_alerta_oee`:

| Máquina | P10 | **P25 = umbral** | Mediana |
|---|---:|---:|---:|
| Vinilos_1 | 31,0 % | **45,5 %** | 59,8 % |
| Vinilos_2 | 37,9 % | **51,0 %** | 62,5 % |
| Vinilos_3 | 56,6 % | **70,4 %** | 83,7 % |
| Vinilos_4 | 54,8 % | **67,8 %** | 84,8 % |
| Planta | 44,8 % | 60,2 % | 75,5 % |

**Por qué un umbral por máquina y no uno fijo para la planta.** Con 60 % fijo, Vinilos_1 (mediana 59,8 %) estaría en alerta la mitad del tiempo y los supervisores dejarían de prestarle atención (fatiga de alertas), mientras que una falla real en Vinilos_3 (de 84 % a 65 %) no dispararía nada. Comparar cada línea con el peor cuartil de su propia historia detecta lo **anormal para esa máquina**, que es lo accionable en el turno. El bajo desempeño crónico de Vinilos_1 y Vinilos_2 es un problema estratégico y se gestiona en Power BI y en el comité. La meta mínima de planta (60 %) se sigue mostrando como línea roja en el tablero.

- **3 lecturas promediadas**: una sola hora mala no dispara la alerta.
- **`for: 1m`**: la condición tiene que sostenerse.
- **Verificación con el simulador**: en operación normal cada máquina pasa entre el 2 % y el 6 % del tiempo bajo su umbral. Con `forzar_falla.py` la máquina afectada cae a un índice cercano a 0,6 y la alerta se dispara en 1 a 2 minutos.
