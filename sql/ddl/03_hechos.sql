-- =============================================================================
-- 03_hechos.sql  ·  Tablas de hechos
-- Todas las medidas de tiempo se guardan en HORAS (numeric) para que sean
-- aditivas; los porcentajes (OEE, disponibilidad...) NUNCA se guardan: se
-- calculan como cociente de sumas en las vistas / DAX, para que el OEE de un
-- mes no sea el promedio de los OEE de los turnos (error típico).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- fact_produccion_turno
-- GRANO: un registro de turno = una máquina, en una fecha, en un turno, con
--        una operaria y una referencia, tal como se guarda con el botón
--        "Ingreso total" del Excel (fila "encabezado" de la Base De Datos).
--        Los paros de las filas de continuación ("Ingreso subcódigo") del
--        mismo turno se suman a este registro.
-- -----------------------------------------------------------------------------
CREATE TABLE dw.fact_produccion_turno (
    id_registro                 INTEGER      PRIMARY KEY,   -- dimensión degenerada: fila de origen en el Excel
    sk_fecha                    INTEGER      NOT NULL REFERENCES dw.dim_fecha(sk_fecha),
    sk_maquina                  INTEGER      NOT NULL REFERENCES dw.dim_maquina(sk_maquina),
    sk_turno                    SMALLINT     NOT NULL REFERENCES dw.dim_turno(sk_turno),
    sk_operario                 INTEGER      NOT NULL REFERENCES dw.dim_persona(sk_persona),
    sk_referencia               INTEGER      NOT NULL REFERENCES dw.dim_referencia(sk_referencia),
    -- medidas aditivas (horas)
    horas_trabajadas            NUMERIC(9,5) NOT NULL CHECK (horas_trabajadas >= 0),
    horas_paro_planificado      NUMERIC(9,5) NOT NULL DEFAULT 0 CHECK (horas_paro_planificado >= 0),
    horas_paro_disponibilidad   NUMERIC(9,5) NOT NULL DEFAULT 0 CHECK (horas_paro_disponibilidad >= 0),
    horas_paro_calidad          NUMERIC(9,5) NOT NULL DEFAULT 0 CHECK (horas_paro_calidad >= 0),
    horas_paro_total            NUMERIC(9,5) NOT NULL DEFAULT 0 CHECK (horas_paro_total >= 0),
    tiempo_planificado_h        NUMERIC(9,5) NOT NULL,      -- horas_trabajadas - paro planificado
    tiempo_operativo_h          NUMERIC(9,5) NOT NULL,      -- planificado - paro disponibilidad
    tiempo_ideal_h              NUMERIC(10,5),               -- pacas / pacas_hora_ideal (NULL si pacas inválidas)
    -- medidas aditivas (unidades)
    pacas_producidas            NUMERIC(8,1),               -- NULL si se marcó atípica
    pacas_meta                  NUMERIC(8,1),               -- pacas_hora_ideal × tiempo_planificado_h
    n_eventos_paro              SMALLINT     NOT NULL DEFAULT 0,
    -- medida no aditiva (informativa)
    pacas_hora_ideal            NUMERIC(8,3),
    -- banderas de calidad de datos (permiten filtrar en los tableros)
    origen_estandar             VARCHAR(30)  NOT NULL,      -- de dónde salió la velocidad ideal
    es_registro_historico       BOOLEAN      NOT NULL,      -- 2022-2023: sin turno/operaria/referencia
    dq_pacas_atipica            BOOLEAN      NOT NULL DEFAULT FALSE,
    dq_paro_mayor_turno         BOOLEAN      NOT NULL DEFAULT FALSE,
    es_valido_oee               BOOLEAN      NOT NULL,      -- tiene horas > 0, pacas válidas y estándar
    CONSTRAINT ck_tiempos CHECK (tiempo_operativo_h <= tiempo_planificado_h + 0.001)
);
COMMENT ON TABLE dw.fact_produccion_turno IS
 'Grano: 1 fila = 1 registro de turno (máquina × fecha × turno × operaria × referencia)';

-- -----------------------------------------------------------------------------
-- fact_paro
-- GRANO: un evento de paro = una celda "Código N" con minutos > 0 de una fila
--        del Excel (encabezado o continuación). Al pasar de formato ancho
--        (18 pares de columnas) a largo, cada paro es una fila y queda
--        asociado al nivel más fino conocido de la jerarquía código→subcódigo.
-- -----------------------------------------------------------------------------
CREATE TABLE dw.fact_paro (
    id_paro                 BIGSERIAL    PRIMARY KEY,
    id_registro             INTEGER,                    -- degenerada: registro de turno al que pertenece (NULL si huérfano)
    fila_origen             INTEGER      NOT NULL,      -- fila del Excel de donde salió el paro (linaje)
    sk_fecha                INTEGER      NOT NULL REFERENCES dw.dim_fecha(sk_fecha),
    sk_maquina              INTEGER      NOT NULL REFERENCES dw.dim_maquina(sk_maquina),
    sk_turno                SMALLINT     NOT NULL REFERENCES dw.dim_turno(sk_turno),
    sk_operario             INTEGER      NOT NULL REFERENCES dw.dim_persona(sk_persona),
    sk_referencia           INTEGER      NOT NULL REFERENCES dw.dim_referencia(sk_referencia),
    sk_causa                INTEGER      NOT NULL REFERENCES dw.dim_causa_paro(sk_causa),
    sk_persona_involucrada  INTEGER      NOT NULL REFERENCES dw.dim_persona(sk_persona),  -- role-playing
    area_involucrada        VARCHAR(30)  NOT NULL,      -- degenerada: 'Operarios' / 'Mantenimiento' / 'No aplica'
    minutos_paro            NUMERIC(7,2) NOT NULL CHECK (minutos_paro > 0 AND minutos_paro <= 1440),
    horas_paro              NUMERIC(10,6) NOT NULL,     -- 6 decimales: 1/60 h sin sesgo de redondeo
    es_fila_continuacion    BOOLEAN      NOT NULL       -- vino de "Ingreso subcódigo"
);
COMMENT ON TABLE dw.fact_paro IS 'Grano: 1 fila = 1 evento de paro (registro × código/subcódigo)';

-- -----------------------------------------------------------------------------
-- fact_tiempo_no_programado
-- GRANO: un registro de horas no trabajadas = máquina × fecha × motivo (×turno
--        cuando existe). Tiempo en que la línea NO se programó (no entra en OEE,
--        sí en Utilización / TEEP).
-- -----------------------------------------------------------------------------
CREATE TABLE dw.fact_tiempo_no_programado (
    id_registro             INTEGER      PRIMARY KEY,   -- fila de origen
    sk_fecha                INTEGER      NOT NULL REFERENCES dw.dim_fecha(sk_fecha),
    sk_maquina              INTEGER      NOT NULL REFERENCES dw.dim_maquina(sk_maquina),
    sk_turno                SMALLINT     NOT NULL REFERENCES dw.dim_turno(sk_turno),
    sk_motivo               INTEGER      NOT NULL REFERENCES dw.dim_motivo_no_programado(sk_motivo),
    horas_no_programadas    NUMERIC(6,2) NOT NULL CHECK (horas_no_programadas > 0),
    dq_horas_recortadas     BOOLEAN      NOT NULL DEFAULT FALSE  -- venía > 24 h en el día
);
COMMENT ON TABLE dw.fact_tiempo_no_programado IS 'Grano: 1 fila = horas no programadas de una máquina en una fecha por un motivo';

-- -----------------------------------------------------------------------------
-- fact_produccion_hora  ·  capa casi en tiempo real (Grafana)
-- GRANO: una máquina × una hora de producción. La alimenta el simulador
--        (en producción real la alimentaría el PLC/SCADA).
-- -----------------------------------------------------------------------------
CREATE TABLE dw.fact_produccion_hora (
    id_lectura                  BIGSERIAL    PRIMARY KEY,
    ts                          TIMESTAMPTZ  NOT NULL,      -- momento en que se registró la hora
    sk_fecha                    INTEGER      NOT NULL REFERENCES dw.dim_fecha(sk_fecha),
    sk_maquina                  INTEGER      NOT NULL REFERENCES dw.dim_maquina(sk_maquina),
    sk_turno                    SMALLINT     NOT NULL REFERENCES dw.dim_turno(sk_turno),
    sk_referencia               INTEGER      NOT NULL REFERENCES dw.dim_referencia(sk_referencia),
    sk_causa_principal          INTEGER      NOT NULL REFERENCES dw.dim_causa_paro(sk_causa),
    minutos_planificados        NUMERIC(5,2) NOT NULL CHECK (minutos_planificados BETWEEN 0 AND 60),
    minutos_paro_disponibilidad NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (minutos_paro_disponibilidad BETWEEN 0 AND 60),
    minutos_paro_calidad        NUMERIC(5,2) NOT NULL DEFAULT 0,
    pacas_producidas            NUMERIC(7,2) NOT NULL CHECK (pacas_producidas >= 0),
    pacas_hora_ideal            NUMERIC(8,3) NOT NULL CHECK (pacas_hora_ideal > 0),
    origen                      VARCHAR(20)  NOT NULL DEFAULT 'simulador',
    UNIQUE (sk_maquina, ts)
);
COMMENT ON TABLE dw.fact_produccion_hora IS 'Grano: 1 fila = 1 máquina × 1 hora (streaming simulado)';
