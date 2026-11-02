-- =============================================================================
-- 01_esquemas.sql
-- Crea (desde cero) los esquemas del repositorio analítico.
--   stg   : zona de aterrizaje (staging) con los datos crudos del Excel, tal cual.
--   dw    : modelo dimensional (estrella) que consumen Power BI y Grafana.
--   priv  : datos personales identificables (nombres reales). Acceso restringido.
--   audit : bitácora del ETL, reglas de calidad y conciliación de totales.
-- El ETL ejecuta este archivo en cada corrida: el proceso es reproducible desde cero.
-- =============================================================================

DROP SCHEMA IF EXISTS dw    CASCADE;
DROP SCHEMA IF EXISTS stg   CASCADE;
DROP SCHEMA IF EXISTS priv  CASCADE;
DROP SCHEMA IF EXISTS audit CASCADE;

CREATE SCHEMA stg;
CREATE SCHEMA dw;
CREATE SCHEMA priv;
CREATE SCHEMA audit;

COMMENT ON SCHEMA stg   IS 'Staging: copia cruda del libro SEGUIMIENTO TEMPERAS Y VINILOS (.xlsm)';
COMMENT ON SCHEMA dw    IS 'Data warehouse: modelo dimensional de producción y paros (OEE)';
COMMENT ON SCHEMA priv  IS 'Datos personales (Ley 1581 de 2012). Solo rol ETL/administrador';
COMMENT ON SCHEMA audit IS 'Trazabilidad del ETL: corridas, reglas de calidad y conciliación';
