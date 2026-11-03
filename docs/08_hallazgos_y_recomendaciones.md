# 8. Hallazgos y recomendaciones (guion para la sustentación)

> Cifras del histórico ene-2022 a mar-2025 después de la limpieza. Cada una se puede reproducir con
> `sql/consultas/consultas_analiticas.sql` (entre paréntesis, la consulta).

## La historia en una frase

**La planta pierde cerca de 3 de cada 10 horas planificadas (OEE 70,6 %), la disponibilidad viene cayendo desde 2022 y más de la mitad del tiempo perdido sale de dos causas operativas (ajustes y derrames) que se concentran en el sistema de dosificación.**

## Hallazgos

### 1. El OEE se estancó alrededor del 70 % y la disponibilidad cae año tras año (Q2, Q5)

| Año | Disponibilidad | Rendimiento | OEE | % Productividad (Excel) |
|---|---:|---:|---:|---:|
| 2022 | 91,7 % | 77,8 % | 71,3 % | 87,7 % |
| 2023 | 84,8 % | 78,3 % | 66,4 % | 79,7 % |
| 2024 | 80,7 % | 91,0 % | 73,3 % | 72,7 % |
| 2025 (ene-mar) | 78,3 % | 94,2 % | 73,6 % | 70,2 % |

- La disponibilidad perdió **13 puntos** en tres años. El indicador del Excel ("% Productividad") muestra la caída, pero no dice que el rendimiento sí mejoró: por eso hace falta el OEE.
- Ojo con el rendimiento de 2022-2023: esos turnos no registraban referencia y su velocidad ideal es estimada (ver supuestos). La comparación más sólida es 2024 vs 2025.

### 2. Dos causas explican el 59 % del paro no planificado (Q3 · Pareto)

| Causa | Horas | % del paro no planificado | % acumulado |
|---|---:|---:|---:|
| [05] Ajuste operativo | 1.817 | 31,9 % | 31,9 % |
| [06] Limpieza por derrame operativo | 1.546 | 27,1 % | 59,0 % |
| [07] Alistamiento / cambio de referencia | 621 | 10,9 % | 69,8 % |
| [10] Paro por ventaja / evacuación | 356 | 6,2 % | 76,1 % |
| [01] Falla electromecánica | 323 | 5,7 % | 81,7 % |

Y crecen: el **derrame** pasó de consumir el 1,5 % de las horas trabajadas en 2022 al **8,1 % en 2025**; el **ajuste operativo**, del 2,3 % al 6,6 %.

### 3. El sistema de dosificación es el punto técnico n.º 1 (Q4 · drill-down)

- Dentro del ajuste operativo, **"Sistema de dosificación de pintura" = 784 h (43 %)**, seguido de transfer y pisador de tapa (238 h).
- Dentro de la falla electromecánica, **"Sistema de dosificación" = 117 h (36 %)**: válvulas, retenedores y o-rings.
- Hipótesis para validar con mantenimiento: los derrames (código 06) tienen el mismo origen (boquillas y dosificación), lo que haría de este sistema la causa de más de la mitad del tiempo perdido.

### 4. Vinilos_1 y Vinilos_2 rinden 20 puntos menos que Vinilos_3 y Vinilos_4 (Q2)

OEE 2024: Vinilos_3 **81,8 %** · Vinilos_4 **79,5 %** · Vinilos_2 **60,8 %** · Vinilos_1 **56,2 %**. La brecha es sobre todo de **disponibilidad** (71–74 % vs 84–85 %). Entre turnos de una misma máquina las diferencias son pequeñas (±3 pp, Q7): el problema es del equipo, no de un turno.

### 5. Mantenimiento mejora en confiabilidad (Q8)

MTBF de Vinilos_4: **35 h (2022) → 91 h (2024)**; MTTR de Vinilos_3: **50 → 23 min**. Las fallas (código 01) pesan solo el 5,7 %: el reto ya no está en las averías sino en los ajustes y la limpieza.

### 6. La capacidad que ni siquiera se programa es enorme (Q9)

En 2024 las líneas estuvieron **9.725 h sin programar**: 55 % por falta de demanda (Comercial) y **33 % (3.191 h) por falta de envase, tapa, display o materia prima** (Almacén/Compras), que es controlable.

### 7. Los datos tenían problemas que distorsionaban el informe mensual (doc. 02)

25 registros con unidades digitadas como pacas inflaban la producción en **54.965 pacas (14,5 %)**; 86 % de los turnos 2022-2023 no tenía referencia ni operaria; hay dos catálogos de códigos en uso.

## Recomendaciones a la gerencia

| # | Recomendación | Responsable | Indicador de seguimiento | Meta propuesta |
|---|---|---|---|---|
| 1 | Proyecto de mejora del **sistema de dosificación**: análisis causa raíz, kit de repuestos (válvulas, o-rings, retenedores), estándar de ajuste y lista de verificación de arranque | Mantenimiento + Ingeniería | Horas de código 05 y 01 en dosificación | −40 % en 6 meses |
| 2 | Programa contra **derrames**: bandejas de contención, revisión de canecas y boquillas, 5S | Producción | % código 06 sobre horas trabajadas | De 8,1 % a ≤ 3 % |
| 3 | **Foco en Vinilos_1 y Vinilos_2**: replicar las prácticas de Vinilos_3/4 y evaluar repotenciación | Gerencia de planta | OEE V1/V2 | ≥ 70 % en 2026 |
| 4 | **SMED** para cambios de referencia y de insumos (códigos 07 y 15) | Ingeniería | Minutos por cambio | −30 % |
| 5 | Acuerdo de abastecimiento: inventario de seguridad de envase, tapa y display | Compras / Almacén | Horas no programadas controlables | −50 % |
| 6 | **Captura digital** en tableta (o PLC) con validación inmediata (pacas vs. velocidad máxima), **registro de rechazos** y catálogo único de códigos | TI + Mantenimiento | Reglas de calidad con filas afectadas | → 0 |
| 7 | Usar el tablero de Grafana en pantallas de planta, con la alerta por máquina (OEE por debajo de su percentil 25) | Supervisores | Tiempo de respuesta a la alerta | < 15 min |
| 8 | Revisar los estándares de velocidad: 23 % de los turnos supera el 100 % de rendimiento (10 % supera el 105 %) | Ingeniería de procesos | % turnos con rendimiento > 105 % | < 2 % |
