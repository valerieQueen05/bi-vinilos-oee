-- =============================================================================
-- consultas_analiticas.sql
-- Consultas que responden preguntas de negocio sobre el modelo dimensional.
-- Ejecutar en DBeaver (conexión a bi_vinilos). Cada consulta indica la pregunta,
-- el usuario que la hace y la técnica SQL que usa.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Q1. ¿Cómo evoluciona el OEE de cada máquina mes a mes y frente al mismo mes
--     del año anterior?                         Usuario: Gerente de planta
--     Técnica: agregación + LAG (mes anterior) + LAG 12 (año anterior)
-- -----------------------------------------------------------------------------
WITH mensual AS (
    SELECT cod_maquina, anio, mes_num, anio_mes, oee, disponibilidad, rendimiento
    FROM dw.v_kpi_maquina_mes
), calendario AS (     -- malla completa máquina × mes para que LAG(12) sea exacto aunque falten meses
    SELECT m.cod_maquina, d.anio, d.mes_num, d.anio_mes
    FROM (SELECT DISTINCT cod_maquina FROM mensual) m
    CROSS JOIN (SELECT DISTINCT anio, mes_num, anio_mes FROM dw.dim_fecha
                WHERE fecha BETWEEN '2022-01-01' AND '2025-03-31') d
)
SELECT c.cod_maquina, c.anio_mes,
       ROUND(100 * m.oee, 1)                                                  AS oee_pct,
       ROUND(100 * (m.oee - LAG(m.oee)     OVER w), 1)                        AS var_vs_mes_ant_pp,
       ROUND(100 * (m.oee - LAG(m.oee, 12) OVER w), 1)                        AS var_vs_anio_ant_pp
FROM calendario c
LEFT JOIN mensual m USING (cod_maquina, anio, mes_num)
WINDOW w AS (PARTITION BY c.cod_maquina ORDER BY c.anio, c.mes_num)
ORDER BY c.cod_maquina, c.anio, c.mes_num;


-- -----------------------------------------------------------------------------
-- Q2. ¿Qué máquina es la mejor y la peor cada año en OEE y en sus componentes?
--     Usuario: Comité mensual / alta dirección
--     Técnica: agregación con FILTER + RANK() por partición
-- -----------------------------------------------------------------------------
WITH anual AS (
    SELECT d.anio, m.cod_maquina,
           SUM(f.tiempo_operativo_h) / SUM(f.tiempo_planificado_h)                     AS disponibilidad,
           SUM(f.tiempo_ideal_h) / SUM(f.tiempo_operativo_h - f.horas_paro_calidad)    AS rendimiento,
           SUM(f.tiempo_ideal_h) / SUM(f.tiempo_planificado_h)                         AS oee
    FROM dw.fact_produccion_turno f
    JOIN dw.dim_fecha d   USING (sk_fecha)
    JOIN dw.dim_maquina m USING (sk_maquina)
    WHERE f.es_valido_oee
    GROUP BY d.anio, m.cod_maquina
)
SELECT anio, cod_maquina,
       ROUND(100 * disponibilidad, 1) AS disp_pct,
       ROUND(100 * rendimiento, 1)    AS rend_pct,
       ROUND(100 * oee, 1)            AS oee_pct,
       RANK() OVER (PARTITION BY anio ORDER BY oee DESC)             AS puesto_oee,
       RANK() OVER (PARTITION BY anio ORDER BY disponibilidad DESC)  AS puesto_disp
FROM anual
ORDER BY anio, puesto_oee;


-- -----------------------------------------------------------------------------
-- Q3. Pareto de causas de paro NO planificadas: ¿qué pocas causas explican el
--     80 % del tiempo perdido?          Usuario: Jefe de mantenimiento / producción
--     Técnica: SUM() OVER (ORDER BY ...) acumulado + clasificación ABC
-- -----------------------------------------------------------------------------
WITH causas AS (
    SELECT c.codigo_desc, c.area_impacto, SUM(p.horas_paro) AS horas, COUNT(*) AS eventos
    FROM dw.fact_paro p
    JOIN dw.dim_causa_paro c USING (sk_causa)
    WHERE c.categoria_oee <> 'Planificado'
    GROUP BY c.codigo_desc, c.area_impacto
)
SELECT codigo_desc, area_impacto, ROUND(horas, 1) AS horas, eventos,
       ROUND(100 * horas / SUM(horas) OVER (), 1)                                 AS pct,
       ROUND(100 * SUM(horas) OVER (ORDER BY horas DESC) / SUM(horas) OVER (), 1) AS pct_acumulado,
       CASE WHEN SUM(horas) OVER (ORDER BY horas DESC) - horas < 0.8  * SUM(horas) OVER () THEN 'A'
            WHEN SUM(horas) OVER (ORDER BY horas DESC) - horas < 0.95 * SUM(horas) OVER () THEN 'B'
            ELSE 'C' END                                                          AS clase_abc
FROM causas
ORDER BY horas DESC;


-- -----------------------------------------------------------------------------
-- Q4. Dentro del "Ajuste operativo" y la "Falla electromecánica", ¿qué
--     sistema/componente pesa más en cada máquina? (drill-down de la jerarquía)
--     Usuario: Jefe de mantenimiento        Técnica: ROW_NUMBER() top-N por grupo
-- -----------------------------------------------------------------------------
WITH det AS (
    SELECT m.cod_maquina, c.codigo_desc, c.sistema_desc, c.componente_desc,
           SUM(p.horas_paro) AS horas, COUNT(*) AS eventos
    FROM dw.fact_paro p
    JOIN dw.dim_causa_paro c USING (sk_causa)
    JOIN dw.dim_maquina m    USING (sk_maquina)
    WHERE c.cod_codigo IN ('01', '05') AND c.nivel_detalle > 1
    GROUP BY 1, 2, 3, 4
)
SELECT * FROM (
    SELECT det.*, ROUND(horas, 1) AS horas_r,
           ROW_NUMBER() OVER (PARTITION BY cod_maquina, codigo_desc ORDER BY horas DESC) AS top
    FROM det
) x
WHERE top <= 3
ORDER BY cod_maquina, codigo_desc, top;


-- -----------------------------------------------------------------------------
-- Q5. ¿La disponibilidad viene cayendo? Tendencia con promedio móvil de 3 meses
--     Usuario: Gerente de planta           Técnica: AVG() OVER (ROWS 2 PRECEDING)
-- -----------------------------------------------------------------------------
WITH mes AS (
    SELECT d.anio, d.mes_num, d.anio_mes,
           SUM(f.tiempo_operativo_h) / NULLIF(SUM(f.tiempo_planificado_h), 0) AS disponibilidad
    FROM dw.fact_produccion_turno f JOIN dw.dim_fecha d USING (sk_fecha)
    WHERE f.horas_trabajadas > 0
    GROUP BY 1, 2, 3
)
SELECT anio_mes,
       ROUND(100 * disponibilidad, 1)                                                   AS disp_pct,
       ROUND(100 * AVG(disponibilidad) OVER (ORDER BY anio, mes_num ROWS 2 PRECEDING), 1) AS media_movil_3m
FROM mes
ORDER BY anio, mes_num;


-- -----------------------------------------------------------------------------
-- Q6. Comparativo año contra año (YoY) por trimestre: pacas producidas y OEE
--     Usuario: Alta dirección              Técnica: agregación + LAG por trimestre
-- -----------------------------------------------------------------------------
WITH trim AS (
    SELECT d.anio, d.trimestre,
           SUM(f.pacas_producidas)                                                         AS pacas,
           SUM(f.tiempo_ideal_h) FILTER (WHERE f.es_valido_oee)
             / SUM(f.tiempo_planificado_h) FILTER (WHERE f.es_valido_oee)                  AS oee
    FROM dw.fact_produccion_turno f JOIN dw.dim_fecha d USING (sk_fecha)
    GROUP BY 1, 2
)
SELECT anio, trimestre, pacas,
       LAG(pacas) OVER (PARTITION BY trimestre ORDER BY anio)                              AS pacas_anio_ant,
       ROUND(100.0 * (pacas / NULLIF(LAG(pacas) OVER (PARTITION BY trimestre ORDER BY anio), 0) - 1), 1) AS crec_pacas_pct,
       ROUND(100 * oee, 1)                                                                 AS oee_pct,
       ROUND(100 * (oee - LAG(oee) OVER (PARTITION BY trimestre ORDER BY anio)), 1)        AS var_oee_pp
FROM trim
ORDER BY trimestre, anio;


-- -----------------------------------------------------------------------------
-- Q7. ¿Hay turnos que rinden menos? OEE por turno y desviación frente al
--     promedio de la misma máquina        Usuario: Supervisor de producción
--     Técnica: AVG() OVER (PARTITION BY máquina) sobre un agregado
-- -----------------------------------------------------------------------------
WITH t AS (
    SELECT m.cod_maquina, tu.nombre_turno,
           COUNT(*) AS turnos,
           SUM(f.tiempo_ideal_h) / SUM(f.tiempo_planificado_h) AS oee
    FROM dw.fact_produccion_turno f
    JOIN dw.dim_maquina m USING (sk_maquina)
    JOIN dw.dim_turno tu  USING (sk_turno)
    WHERE f.es_valido_oee AND tu.cod_turno IN ('T1', 'T2', 'T3', 'TA')
    GROUP BY 1, 2
)
SELECT cod_maquina, nombre_turno, turnos,
       ROUND(100 * oee, 1)                                                   AS oee_pct,
       ROUND(100 * (oee - AVG(oee) OVER (PARTITION BY cod_maquina)), 1)      AS desvio_vs_maquina_pp
FROM t
ORDER BY cod_maquina, oee DESC;


-- -----------------------------------------------------------------------------
-- Q8. Confiabilidad: MTBF y MTTR de fallas electromecánicas (códigos 01 y 02)
--     Usuario: Jefe de mantenimiento        Técnica: agregación cruzada de 2 hechos
--     MTBF = horas operativas / nº de fallas ; MTTR = horas de falla / nº de fallas
-- -----------------------------------------------------------------------------
WITH fallas AS (
    SELECT p.sk_maquina, d.anio, COUNT(*) AS n_fallas, SUM(p.horas_paro) AS horas_falla
    FROM dw.fact_paro p
    JOIN dw.dim_causa_paro c USING (sk_causa)
    JOIN dw.dim_fecha d      USING (sk_fecha)
    WHERE c.cod_codigo IN ('01', '02')
    GROUP BY 1, 2
), oper AS (
    SELECT f.sk_maquina, d.anio, SUM(f.tiempo_operativo_h) AS horas_operativas
    FROM dw.fact_produccion_turno f JOIN dw.dim_fecha d USING (sk_fecha)
    GROUP BY 1, 2
)
SELECT m.cod_maquina, o.anio, o.horas_operativas::int, COALESCE(fa.n_fallas, 0) AS n_fallas,
       ROUND(o.horas_operativas / NULLIF(fa.n_fallas, 0), 1)       AS mtbf_h,
       ROUND(60 * fa.horas_falla / NULLIF(fa.n_fallas, 0), 1)      AS mttr_min
FROM oper o
JOIN dw.dim_maquina m USING (sk_maquina)
LEFT JOIN fallas fa USING (sk_maquina, anio)
ORDER BY m.cod_maquina, o.anio;


-- -----------------------------------------------------------------------------
-- Q9. ¿Cuánta capacidad se pierde porque la línea ni siquiera se programa, y por
--     qué?  Utilización = horas trabajadas / (horas trabajadas + no programadas)
--     Usuario: Gerencia / Planeación / Comercial    Técnica: agregación + % del total por grupo
-- -----------------------------------------------------------------------------
SELECT d.anio, mo.motivo_estandar, mo.responsable,
       ROUND(SUM(t.horas_no_programadas)) AS horas,
       ROUND(100 * SUM(t.horas_no_programadas)
                 / SUM(SUM(t.horas_no_programadas)) OVER (PARTITION BY d.anio), 1) AS pct_del_anio
FROM dw.fact_tiempo_no_programado t
JOIN dw.dim_fecha d                 USING (sk_fecha)
JOIN dw.dim_motivo_no_programado mo USING (sk_motivo)
GROUP BY d.anio, mo.motivo_estandar, mo.responsable
ORDER BY d.anio, horas DESC;


-- -----------------------------------------------------------------------------
-- Q10. ¿Qué referencias cumplen peor la meta de producción? (para revisar el
--      estándar o el proceso)               Usuario: Ingeniería de procesos
--      Técnica: PERCENT_RANK() + HAVING para excluir referencias con pocos turnos
-- -----------------------------------------------------------------------------
SELECT r.nombre_referencia, r.familia_tamano, COUNT(*) AS turnos,
       ROUND(100 * SUM(f.pacas_producidas) / SUM(f.pacas_meta), 1) AS cumplimiento_meta_pct,
       ROUND(PERCENT_RANK() OVER (ORDER BY SUM(f.pacas_producidas) / SUM(f.pacas_meta))::numeric, 2) AS percentil
FROM dw.fact_produccion_turno f
JOIN dw.dim_referencia r USING (sk_referencia)
WHERE f.es_valido_oee AND r.sk_referencia > 0
GROUP BY r.nombre_referencia, r.familia_tamano
HAVING COUNT(*) >= 20
ORDER BY cumplimiento_meta_pct;


-- -----------------------------------------------------------------------------
-- Q11. Indicadores actuales del P-MTO-22 (% productividad y % por código), por
--      máquina, mes y año, para validar contra las tablas dinámicas del Excel
--      Usuario: Coordinador de mantenimiento
-- -----------------------------------------------------------------------------
SELECT cod_maquina, anio, mes_num, codigo_desc,
       ROUND(100 * pct_codigo, 2) AS pct_codigo
FROM dw.v_paro_codigo_mes
WHERE anio = 2024 AND cod_maquina = 'Vinilos_2'
ORDER BY mes_num, pct_codigo DESC;


-- -----------------------------------------------------------------------------
-- Q12. Auditoría: ¿qué hizo la última corrida del ETL?
-- -----------------------------------------------------------------------------
SELECT r.cod_regla, r.dimension_dq, r.filas_afectadas, r.accion
FROM audit.regla_calidad r
WHERE r.id_corrida = (SELECT MAX(id_corrida) FROM audit.etl_corrida)
ORDER BY r.orden;
