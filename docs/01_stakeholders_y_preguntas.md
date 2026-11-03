# 1. Usuarios de la solución y preguntas de negocio

| Usuario (stakeholder) | Rol frente a los datos | Preguntas que necesita responder | Capa | Frecuencia |
|---|---|---|---|---|
| **Alta dirección / comité mensual** | Decide inversiones y prioridades | ¿El OEE de la planta mejora o empeora frente al año anterior? ¿Qué línea merece inversión? ¿Cuánta capacidad perdemos porque no se programa la línea (ventas, materiales)? | Power BI | Mensual |
| **Gerente de planta / producción** | Dueño del OEE | ¿Qué componente del OEE (disponibilidad, rendimiento, calidad) explica la caída? ¿Qué turnos y referencias rinden menos? ¿Se cumple la meta de pacas? | Power BI | Semanal / mensual |
| **Coordinador de mantenimiento** (autor del P-MTO-22) | Registra los paros y presenta el informe | ¿Cuáles son las causas principales (Pareto)? Dentro de "falla electromecánica" y "ajuste operativo", ¿qué sistema/componente falla? ¿Cómo evolucionan MTBF y MTTR? | Power BI + Grafana | Diaria / mensual |
| **Supervisores de turno** | Reaccionan durante el turno | ¿Cómo va cada máquina en esta hora? ¿Alguna está por debajo del umbral? ¿Cuál es la causa del paro actual? | Grafana | Continua (cada 10 s) |
| **Técnicos de mantenimiento** | Atienden la falla | ¿Qué máquina está en falla y desde cuándo? | Grafana (alerta) | Continua |
| **Planeación / Compras / Almacén** | Programan y abastecen | ¿Cuántas horas se pierden por falta de envase, tapa, display o materia prima? | Power BI | Mensual |
| **Calidad** | Libera producto | ¿Cuánto tiempo se espera el aval de microbiología? ¿Cuánto reproceso hay? | Power BI | Mensual |
| **Ingeniería de procesos** | Ajusta estándares | ¿Los estándares de velocidad (unidades/minuto, unidades/paca) son realistas para cada referencia? | Power BI + SQL | Trimestral |
| **Operarias** | Registran el formato "hora a hora" | (Fuente de los datos; con los tableros ven el resultado de su registro) | Grafana (pantalla en planta) | Turno |

## Preguntas de negocio priorizadas

1. ¿Cuál es el OEE por máquina, mes y año, y cómo se compara con el año anterior?
2. ¿Qué pocas causas explican el 80 % del tiempo de paro no planificado? (Pareto)
3. ¿Qué sistema de la máquina (subcódigo) origina los ajustes operativos y las fallas?
4. ¿Hay diferencias de desempeño entre turnos o referencias?
5. ¿Cuánta capacidad se pierde por no programar la línea y quién es responsable de cada motivo?
6. ¿La confiabilidad de las máquinas mejora (MTBF ↑, MTTR ↓)?
7. **En vivo:** ¿Alguna línea está por debajo del OEE mínimo aceptable ahora mismo?
