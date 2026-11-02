#!/bin/bash
# Se ejecuta UNA sola vez, cuando el volumen pgdata está vacío.
# Crea los roles de mínimo privilegio. Las contraseñas vienen de .env.
#   bi_lector  -> Power BI / DBeaver de consulta (SELECT sobre dw y audit)
#   grafana_ro -> Grafana (SELECT solo sobre las vistas de monitoreo)
#   simulador  -> inserta lecturas en dw.fact_produccion_hora
# Los GRANT se aplican en sql/ddl/06_auditoria_permisos.sql en cada corrida del ETL.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE bi_lector  LOGIN PASSWORD '${BI_LECTOR_PASSWORD}';
    CREATE ROLE grafana_ro LOGIN PASSWORD '${GRAFANA_DB_PASSWORD}';
    CREATE ROLE simulador  LOGIN PASSWORD '${SIM_DB_PASSWORD}';
    ALTER ROLE bi_lector  SET default_transaction_read_only = on;
    ALTER ROLE grafana_ro SET default_transaction_read_only = on;
    ALTER ROLE grafana_ro CONNECTION LIMIT 10;
    REVOKE CREATE ON SCHEMA public FROM PUBLIC;
    REVOKE ALL ON DATABASE "${POSTGRES_DB}" FROM PUBLIC;
    GRANT CONNECT ON DATABASE "${POSTGRES_DB}" TO bi_lector, grafana_ro, simulador;
EOSQL
echo "Roles de solo lectura creados."
