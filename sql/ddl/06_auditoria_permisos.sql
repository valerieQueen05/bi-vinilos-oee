-- =============================================================================
-- 06_auditoria_permisos.sql  ·  Trazabilidad del ETL y seguridad de acceso
-- =============================================================================

CREATE TABLE audit.etl_corrida (
    id_corrida      SERIAL       PRIMARY KEY,
    inicio          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    fin             TIMESTAMPTZ,
    estado          VARCHAR(12)  NOT NULL DEFAULT 'en curso',
    archivo_fuente  TEXT         NOT NULL,
    sha256_fuente   CHAR(64)     NOT NULL,     -- prueba de qué versión del Excel se cargó
    filas_leidas    INTEGER
);

CREATE TABLE audit.regla_calidad (
    id_corrida      INTEGER      NOT NULL REFERENCES audit.etl_corrida(id_corrida),
    orden           SMALLINT     NOT NULL,
    cod_regla       VARCHAR(10)  NOT NULL,
    dimension_dq    VARCHAR(20)  NOT NULL,     -- completitud, validez, consistencia, unicidad, exactitud
    descripcion     TEXT         NOT NULL,
    accion          TEXT         NOT NULL,
    filas_antes     INTEGER      NOT NULL,
    filas_afectadas INTEGER      NOT NULL,
    filas_despues   INTEGER      NOT NULL,
    PRIMARY KEY (id_corrida, orden)
);

CREATE TABLE audit.conciliacion (
    id_corrida      INTEGER      NOT NULL REFERENCES audit.etl_corrida(id_corrida),
    metrica         VARCHAR(120) NOT NULL,
    total_fuente    NUMERIC(14,3) NOT NULL,
    total_dw        NUMERIC(14,3) NOT NULL,
    diferencia      NUMERIC(14,3) NOT NULL,
    pct_diferencia  NUMERIC(8,4),
    explicacion     TEXT         NOT NULL,
    PRIMARY KEY (id_corrida, metrica)
);

-- -----------------------------------------------------------------------------
-- Permisos. Los roles se crean en db/init/00_roles.sh con contraseñas de .env.
--   bi_lector  : Power BI y DBeaver de consulta -> SELECT sobre dw y audit.
--   grafana_ro : Grafana -> SELECT solo sobre las vistas y tablas que necesita.
--   Nadie distinto al dueño (rol del ETL) puede leer priv.* (nombres reales).
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bi_lector') THEN
        GRANT USAGE  ON SCHEMA dw, audit TO bi_lector;
        GRANT SELECT ON ALL TABLES IN SCHEMA dw    TO bi_lector;
        GRANT SELECT ON ALL TABLES IN SCHEMA audit TO bi_lector;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_ro') THEN
        GRANT USAGE  ON SCHEMA dw TO grafana_ro;
        GRANT SELECT ON dw.v_rt_hora, dw.v_rt_estado_actual, dw.fact_produccion_hora, dw.v_umbral_alerta_oee,
                        dw.dim_maquina, dw.dim_turno, dw.dim_causa_paro, dw.dim_referencia,
                        dw.v_kpi_maquina_mes
              TO grafana_ro;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'simulador') THEN
        GRANT USAGE  ON SCHEMA dw TO simulador;
        GRANT SELECT ON ALL TABLES IN SCHEMA dw TO simulador;
        GRANT INSERT ON dw.fact_produccion_hora TO simulador;
        GRANT USAGE  ON SEQUENCE dw.fact_produccion_hora_id_lectura_seq TO simulador;
    END IF;
END $$;

REVOKE ALL ON SCHEMA priv FROM PUBLIC;
