-- =============================================================================
-- 05_vistas.sql  ·  Capa semántica en SQL (la reutilizan Grafana y las consultas)
--
-- Definición de OEE usada en todo el proyecto (ver docs/03_catalogo_indicadores.md):
--   Tiempo planificado (TP) = Horas trabajadas − paros planificados (04,16,17,18)
--   Tiempo operativo   (TO) = TP − paros de disponibilidad (01,02,03,05..10,12..15)
--   Tiempo neto        (TN) = TO − paros de calidad (11 Reproceso)
--   Tiempo ideal       (TI) = Pacas producidas / pacas por hora ideal
--   Disponibilidad A = TO / TP      Rendimiento P = TI / TN      Calidad Q = TN / TO
--   OEE = A × P × Q = TI / TP
-- Siempre como cociente de SUMAS sobre el subconjunto válido (es_valido_oee).
-- =============================================================================

-- Detalle por turno con los componentes del OEE -------------------------------
CREATE OR REPLACE VIEW dw.v_oee_turno AS
SELECT
    f.id_registro,
    d.fecha, d.anio, d.mes_num, d.anio_mes,
    m.cod_maquina, t.nombre_turno, r.nombre_referencia, p.alias_publico AS operaria,
    f.horas_trabajadas, f.horas_paro_total, f.pacas_producidas, f.pacas_meta,
    f.tiempo_planificado_h, f.tiempo_operativo_h,
    (f.tiempo_operativo_h - f.horas_paro_calidad)                               AS tiempo_neto_h,
    f.tiempo_ideal_h,
    f.tiempo_operativo_h / NULLIF(f.tiempo_planificado_h, 0)                    AS disponibilidad,
    f.tiempo_ideal_h / NULLIF(f.tiempo_operativo_h - f.horas_paro_calidad, 0)   AS rendimiento,
    (f.tiempo_operativo_h - f.horas_paro_calidad) / NULLIF(f.tiempo_operativo_h, 0) AS calidad,
    f.tiempo_ideal_h / NULLIF(f.tiempo_planificado_h, 0)                        AS oee,
    f.es_valido_oee, f.origen_estandar, f.es_registro_historico
FROM dw.fact_produccion_turno f
JOIN dw.dim_fecha      d ON d.sk_fecha      = f.sk_fecha
JOIN dw.dim_maquina    m ON m.sk_maquina    = f.sk_maquina
JOIN dw.dim_turno      t ON t.sk_turno      = f.sk_turno
JOIN dw.dim_referencia r ON r.sk_referencia = f.sk_referencia
JOIN dw.dim_persona    p ON p.sk_persona    = f.sk_operario;

-- KPI mensual por máquina (indicadores del P-MTO-22 + OEE) --------------------
CREATE OR REPLACE VIEW dw.v_kpi_maquina_mes AS
SELECT
    d.anio, d.mes_num, d.anio_mes, m.cod_maquina,
    COUNT(*)                                     AS registros_turno,
    SUM(f.horas_trabajadas)                      AS horas_trabajadas,
    SUM(f.horas_paro_total)                      AS horas_paro,
    SUM(f.pacas_producidas)                      AS pacas,
    -- Indicadores actuales del Excel (P-MTO-22)
    (SUM(f.horas_trabajadas) - SUM(f.horas_paro_total)) / NULLIF(SUM(f.horas_trabajadas), 0) AS pct_productividad,
    SUM(f.horas_paro_total) / NULLIF(SUM(f.horas_trabajadas), 0)                             AS pct_paro,
    -- OEE y componentes (subconjunto válido)
    SUM(f.tiempo_operativo_h) FILTER (WHERE f.es_valido_oee)
        / NULLIF(SUM(f.tiempo_planificado_h) FILTER (WHERE f.es_valido_oee), 0)              AS disponibilidad,
    SUM(f.tiempo_ideal_h) FILTER (WHERE f.es_valido_oee)
        / NULLIF(SUM(f.tiempo_operativo_h - f.horas_paro_calidad) FILTER (WHERE f.es_valido_oee), 0) AS rendimiento,
    SUM(f.tiempo_operativo_h - f.horas_paro_calidad) FILTER (WHERE f.es_valido_oee)
        / NULLIF(SUM(f.tiempo_operativo_h) FILTER (WHERE f.es_valido_oee), 0)                AS calidad,
    SUM(f.tiempo_ideal_h) FILTER (WHERE f.es_valido_oee)
        / NULLIF(SUM(f.tiempo_planificado_h) FILTER (WHERE f.es_valido_oee), 0)              AS oee,
    SUM(f.pacas_producidas) FILTER (WHERE f.es_valido_oee)
        / NULLIF(SUM(f.pacas_meta) FILTER (WHERE f.es_valido_oee), 0)                        AS cumplimiento_meta
FROM dw.fact_produccion_turno f
JOIN dw.dim_fecha   d ON d.sk_fecha   = f.sk_fecha
JOIN dw.dim_maquina m ON m.sk_maquina = f.sk_maquina
GROUP BY d.anio, d.mes_num, d.anio_mes, m.cod_maquina;

-- % de tiempo de paro por código (indicador "% Código N" del Excel) -----------
-- Excel: Σ horas del código / Σ horas trabajadas, por máquina y periodo.
CREATE OR REPLACE VIEW dw.v_paro_codigo_mes AS
WITH paro AS (
    SELECT fp.sk_maquina, d.anio, d.mes_num, c.cod_codigo, c.codigo_desc, c.categoria_oee,
           SUM(fp.horas_paro) AS horas_paro, COUNT(*) AS eventos
    FROM dw.fact_paro fp
    JOIN dw.dim_fecha d      ON d.sk_fecha = fp.sk_fecha
    JOIN dw.dim_causa_paro c ON c.sk_causa = fp.sk_causa
    GROUP BY 1,2,3,4,5,6
), horas AS (
    SELECT f.sk_maquina, d.anio, d.mes_num, SUM(f.horas_trabajadas) AS horas_trabajadas
    FROM dw.fact_produccion_turno f JOIN dw.dim_fecha d ON d.sk_fecha = f.sk_fecha
    GROUP BY 1,2,3
)
SELECT p.anio, p.mes_num, m.cod_maquina, p.cod_codigo, p.codigo_desc, p.categoria_oee,
       p.horas_paro, p.eventos, h.horas_trabajadas,
       p.horas_paro / NULLIF(h.horas_trabajadas, 0) AS pct_codigo
FROM paro p
JOIN dw.dim_maquina m ON m.sk_maquina = p.sk_maquina
LEFT JOIN horas h ON h.sk_maquina = p.sk_maquina AND h.anio = p.anio AND h.mes_num = p.mes_num;

-- =============================================================================
-- Vistas para Grafana (capa casi en tiempo real)
-- =============================================================================
CREATE OR REPLACE VIEW dw.v_rt_hora AS
SELECT
    h.ts, m.cod_maquina AS maquina, t.nombre_turno AS turno, r.nombre_referencia AS referencia,
    c.codigo_desc AS causa_principal, c.categoria_oee AS categoria_causa,
    h.pacas_producidas, h.pacas_hora_ideal,
    h.minutos_planificados,
    h.minutos_paro_disponibilidad, h.minutos_paro_calidad,
    (h.minutos_planificados - h.minutos_paro_disponibilidad)                         AS minutos_operativos,
    (h.minutos_planificados - h.minutos_paro_disponibilidad) / NULLIF(h.minutos_planificados, 0) AS disponibilidad,
    (h.pacas_producidas / h.pacas_hora_ideal * 60)
        / NULLIF(h.minutos_planificados - h.minutos_paro_disponibilidad - h.minutos_paro_calidad, 0) AS rendimiento,
    (h.minutos_planificados - h.minutos_paro_disponibilidad - h.minutos_paro_calidad)
        / NULLIF(h.minutos_planificados - h.minutos_paro_disponibilidad, 0)           AS calidad,
    (h.pacas_producidas / h.pacas_hora_ideal * 60) / NULLIF(h.minutos_planificados, 0) AS oee
FROM dw.fact_produccion_hora h
JOIN dw.dim_maquina    m ON m.sk_maquina    = h.sk_maquina
JOIN dw.dim_turno      t ON t.sk_turno      = h.sk_turno
JOIN dw.dim_referencia r ON r.sk_referencia = h.sk_referencia
JOIN dw.dim_causa_paro c ON c.sk_causa      = h.sk_causa_principal;

-- Última lectura por máquina (panel "estado actual")
CREATE OR REPLACE VIEW dw.v_rt_estado_actual AS
SELECT DISTINCT ON (maquina) *
FROM dw.v_rt_hora
ORDER BY maquina, ts DESC;

-- Umbral de alerta por máquina: percentil 25 de su propio OEE por turno (2024 en adelante,
-- turnos con >= 6 h planificadas). La alerta dispara cuando el OEE reciente de una máquina
-- cae al peor cuartil de SU historia: así Vinilos_1 (crónicamente baja) no vive en alerta
-- y Vinilos_3 (normalmente alta) sí avisa cuando algo anormal le pasa.
CREATE OR REPLACE VIEW dw.v_umbral_alerta_oee AS
SELECT m.cod_maquina AS maquina,
       percentile_cont(0.25) WITHIN GROUP (ORDER BY f.tiempo_ideal_h / f.tiempo_planificado_h) AS umbral_oee,
       percentile_cont(0.50) WITHIN GROUP (ORDER BY f.tiempo_ideal_h / f.tiempo_planificado_h) AS mediana_oee,
       COUNT(*) AS turnos_base
FROM dw.fact_produccion_turno f
JOIN dw.dim_maquina m USING (sk_maquina)
WHERE f.es_valido_oee AND f.sk_fecha >= 20240101 AND f.tiempo_planificado_h >= 6
GROUP BY m.cod_maquina;
