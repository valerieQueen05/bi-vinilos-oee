-- =============================================================================
-- 04_indices.sql  ·  Índices justificados por el patrón de consulta analítico
-- Las consultas de BI casi siempre: (1) filtran por rango de fechas,
-- (2) agrupan por máquina / código, (3) unen hechos con dimensiones por sk_*.
-- El volumen histórico es pequeño (~5 mil turnos, ~15 mil paros), así que no
-- se indexa "todo": cada índice responde a una consulta concreta.
-- =============================================================================

-- fact_produccion_turno ------------------------------------------------------
-- Tablero de Power BI y consultas de comparativo: WHERE fecha BETWEEN .. GROUP BY máquina.
-- Índice compuesto (máquina, fecha): sirve para filtrar una máquina en un rango
-- y para las funciones de ventana PARTITION BY máquina ORDER BY fecha.
CREATE INDEX ix_fpt_maquina_fecha ON dw.fact_produccion_turno (sk_maquina, sk_fecha);
CREATE INDEX ix_fpt_fecha         ON dw.fact_produccion_turno (sk_fecha);
CREATE INDEX ix_fpt_referencia    ON dw.fact_produccion_turno (sk_referencia);
CREATE INDEX ix_fpt_turno         ON dw.fact_produccion_turno (sk_turno);

-- fact_paro ------------------------------------------------------------------
-- Pareto de causas: GROUP BY sk_causa con filtro de fecha/máquina.
CREATE INDEX ix_fp_causa_fecha    ON dw.fact_paro (sk_causa, sk_fecha);
CREATE INDEX ix_fp_maquina_fecha  ON dw.fact_paro (sk_maquina, sk_fecha);
-- Drill-across paro -> registro de turno
CREATE INDEX ix_fp_registro       ON dw.fact_paro (id_registro) WHERE id_registro IS NOT NULL;

-- fact_tiempo_no_programado ---------------------------------------------------
CREATE INDEX ix_ftnp_maquina_fecha ON dw.fact_tiempo_no_programado (sk_maquina, sk_fecha);

-- fact_produccion_hora (Grafana) ---------------------------------------------
-- Grafana siempre pregunta "las últimas N horas" ($__timeFilter(ts)).
-- Tabla de solo-inserción ordenada por tiempo -> BRIN es diminuto y eficiente
-- para rangos; el B-tree (máquina, ts DESC) resuelve "último valor por máquina"
-- (panel de estado actual) con un index-scan.
CREATE INDEX ix_fph_ts_brin        ON dw.fact_produccion_hora USING BRIN (ts);
CREATE INDEX ix_fph_maquina_ts     ON dw.fact_produccion_hora (sk_maquina, ts DESC);

-- dimensiones -----------------------------------------------------------------
-- Búsquedas por llave natural durante el ETL / simulador
CREATE INDEX ix_dim_fecha_anio_mes ON dw.dim_fecha (anio, mes_num);
CREATE INDEX ix_dim_causa_codigo   ON dw.dim_causa_paro (cod_codigo);
