-- =============================================================================
-- 02_dimensiones.sql  ·  Dimensiones del modelo estrella (PostgreSQL 16)
-- Convenciones:
--   sk_*  = llave sustituta (surrogate key), entera, generada en el DW.
--   cod_* = llave natural / de negocio que viene de la fuente.
--   Cada dimensión tiene un miembro "desconocido" con sk = -1 para que las
--   tablas de hechos nunca queden con FK nula (integridad referencial total).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- dim_fecha  ·  Dimensión construida por el equipo (no existe en la fuente).
-- Grano: un día calendario. Rango 2022-01-01 .. 2027-12-31.
-- Jerarquía: Año > Semestre > Trimestre > Mes > Día ; Año ISO > Semana ISO > Día
-- Incluye festivos de Colombia (Ley 51 de 1983, "Ley Emiliani") calculados por el ETL.
-- -----------------------------------------------------------------------------
CREATE TABLE dw.dim_fecha (
    sk_fecha            INTEGER      PRIMARY KEY,          -- YYYYMMDD (llave inteligente, estándar Kimball para fechas)
    fecha               DATE         NOT NULL UNIQUE,
    anio                SMALLINT     NOT NULL,
    semestre            SMALLINT     NOT NULL CHECK (semestre BETWEEN 1 AND 2),
    trimestre           SMALLINT     NOT NULL CHECK (trimestre BETWEEN 1 AND 4),
    mes_num             SMALLINT     NOT NULL CHECK (mes_num BETWEEN 1 AND 12),
    mes_nombre          VARCHAR(12)  NOT NULL,
    mes_abrev           CHAR(3)      NOT NULL,
    anio_mes            CHAR(7)      NOT NULL,              -- '2024-03' (orden natural)
    dia_mes             SMALLINT     NOT NULL,
    dia_semana_num      SMALLINT     NOT NULL CHECK (dia_semana_num BETWEEN 1 AND 7), -- 1 = lunes (ISO)
    dia_semana_nombre   VARCHAR(10)  NOT NULL,
    semana_iso          SMALLINT     NOT NULL,
    anio_iso            SMALLINT     NOT NULL,
    es_fin_de_semana    BOOLEAN      NOT NULL,
    es_festivo          BOOLEAN      NOT NULL,
    nombre_festivo      VARCHAR(60),
    es_dia_habil        BOOLEAN      NOT NULL               -- lunes a sábado no festivo (jornada de planta)
);
COMMENT ON TABLE dw.dim_fecha IS 'Dimensión calendario generada por el ETL, con festivos de Colombia';

-- -----------------------------------------------------------------------------
-- dim_maquina  ·  SCD Tipo 2 (bonificación).
-- La velocidad nominal (unidades/minuto) y el factor de eficiencia de cada línea
-- cambian cuando se hace un overhaul o se cambia la dosificadora. Si se
-- sobrescribiera (Tipo 1) se reescribiría el OEE histórico; con Tipo 2 cada
-- registro de hechos queda amarrado a la versión de la máquina vigente ese día.
-- -----------------------------------------------------------------------------
CREATE TABLE dw.dim_maquina (
    sk_maquina              SERIAL       PRIMARY KEY,
    cod_maquina             VARCHAR(20)  NOT NULL,           -- llave natural: 'Vinilos_1'
    nombre_maquina          VARCHAR(40)  NOT NULL,           -- 'Vinilos 1'
    linea                   VARCHAR(40)  NOT NULL,           -- 'Envasado vinilos y témperas'
    velocidad_nominal_upm   NUMERIC(6,1),                    -- unidades por minuto (estándar del Excel)
    factor_eficiencia       NUMERIC(4,3),                    -- factor de la "Calculadora de tiempos"
    valido_desde            DATE         NOT NULL,
    valido_hasta            DATE         NOT NULL DEFAULT DATE '9999-12-31',
    es_actual               BOOLEAN      NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_maquina_vigencia CHECK (valido_hasta >= valido_desde)
);
-- Solo una versión vigente por máquina (índice único parcial)
CREATE UNIQUE INDEX ux_dim_maquina_actual ON dw.dim_maquina (cod_maquina) WHERE es_actual;
CREATE UNIQUE INDEX ux_dim_maquina_version ON dw.dim_maquina (cod_maquina, valido_desde);
COMMENT ON TABLE dw.dim_maquina IS 'Líneas de envasado Vinilos_1..4. SCD Tipo 2 sobre velocidad nominal';

-- -----------------------------------------------------------------------------
-- dim_turno
-- -----------------------------------------------------------------------------
CREATE TABLE dw.dim_turno (
    sk_turno                    SMALLINT     PRIMARY KEY,
    cod_turno                   VARCHAR(10)  NOT NULL UNIQUE,  -- 'T1','T2','T3','TA','TD','TN','NA','SH'
    nombre_turno                VARCHAR(40)  NOT NULL,         -- valor estandarizado
    hora_inicio                 TIME,
    hora_fin                    TIME,
    duracion_h                  NUMERIC(4,1),
    minutos_paro_programado_std SMALLINT,                      -- aseo/alimentación + pausa activa (hoja Registro)
    tipo_jornada                VARCHAR(20)  NOT NULL,         -- '8 h', '10,5 h', '12 h', 'Sin turno'
    franja                      VARCHAR(10)  NOT NULL          -- 'Mañana','Tarde','Noche','Día','N/A'
);

-- -----------------------------------------------------------------------------
-- dim_persona  ·  Dimensión con rol (role-playing): operaria del turno y
-- persona involucrada en el paro. Solo guarda un SEUDÓNIMO; el nombre real
-- vive en priv.persona_identidad (acceso restringido). SCD Tipo 1.
-- -----------------------------------------------------------------------------
CREATE TABLE dw.dim_persona (
    sk_persona      SERIAL       PRIMARY KEY,
    cod_persona     VARCHAR(12)  NOT NULL UNIQUE,   -- seudónimo estable: 'OP-007', 'MT-003'
    rol             VARCHAR(30)  NOT NULL,          -- 'Operaria/o', 'Mantenimiento', 'No aplica'
    alias_publico   VARCHAR(40)  NOT NULL           -- 'Operaria 007' (lo que ven los tableros)
);

CREATE TABLE priv.persona_identidad (
    sk_persona          INTEGER      PRIMARY KEY REFERENCES dw.dim_persona(sk_persona),
    nombre_normalizado  VARCHAR(80)  NOT NULL,
    variantes_origen    TEXT         NOT NULL       -- cómo aparecía escrito en el Excel
);
COMMENT ON TABLE priv.persona_identidad IS 'Dato personal identificable. No conceder a roles de lectura';

-- -----------------------------------------------------------------------------
-- dim_referencia  ·  Producto envasado.
-- Atributos derivados del nombre: marca, tamaño (cc) y número de colores.
-- Jerarquía: Familia (tamaño) > Marca > Referencia
-- -----------------------------------------------------------------------------
CREATE TABLE dw.dim_referencia (
    sk_referencia       SERIAL       PRIMARY KEY,
    cod_referencia      VARCHAR(60)  NOT NULL UNIQUE,  -- nombre normalizado (llave natural)
    nombre_referencia   VARCHAR(60)  NOT NULL,
    marca               VARCHAR(30)  NOT NULL,
    tamano_cc           SMALLINT,
    n_colores           SMALLINT,
    familia_tamano      VARCHAR(20)  NOT NULL          -- '15 cc','22 cc','30 cc','70 cc','125 cc','Otro'
);

-- -----------------------------------------------------------------------------
-- estandar_produccion  ·  Tabla de referencia (no es dimensión de análisis):
-- velocidad ideal por máquina × referencia, base del componente RENDIMIENTO.
-- Viene de las tablas Tabla8/14/15/16 de la hoja "Tablas Desplegables".
-- -----------------------------------------------------------------------------
CREATE TABLE dw.estandar_produccion (
    sk_maquina              INTEGER      NOT NULL REFERENCES dw.dim_maquina(sk_maquina),
    sk_referencia           INTEGER      NOT NULL REFERENCES dw.dim_referencia(sk_referencia),
    unidades_por_paca       NUMERIC(8,1) NOT NULL CHECK (unidades_por_paca > 0),
    unidades_por_minuto     NUMERIC(6,1) NOT NULL CHECK (unidades_por_minuto > 0),
    pacas_hora_ideal        NUMERIC(8,3) NOT NULL CHECK (pacas_hora_ideal > 0),
    origen_estandar         VARCHAR(30)  NOT NULL,   -- tabla_maquina | otra_maquina | imputado_tamano | imputado_mezcla_maquina
    PRIMARY KEY (sk_maquina, sk_referencia)
);

-- -----------------------------------------------------------------------------
-- dim_causa_paro  ·  Jerarquía Código > Sistema > Componente (subcódigo)
-- Se modela APLANADA (estrella, no copo de nieve): un registro por hoja de la
-- jerarquía + un miembro "(sin subcódigo)" por cada código. Así Power BI hace
-- drill-down en una sola tabla y el hecho apunta siempre al nivel más fino
-- conocido. Ver docs/04_modelo_dimensional.md para la justificación.
-- -----------------------------------------------------------------------------
CREATE TABLE dw.dim_causa_paro (
    sk_causa            SERIAL       PRIMARY KEY,
    cod_causa           VARCHAR(20)  NOT NULL UNIQUE,  -- '05|5.2' , '01|1.2.C' , '16|-'
    cod_codigo          CHAR(2)      NOT NULL,         -- '01'..'18'
    codigo_desc         VARCHAR(80)  NOT NULL,         -- '[05] Ajuste operativo'
    area_impacto        VARCHAR(40)  NOT NULL,         -- Mantenimiento / Producción / Calidad / ...
    categoria_oee       VARCHAR(20)  NOT NULL CHECK (categoria_oee IN ('Planificado','Disponibilidad','Calidad')),
    es_planificado      BOOLEAN      NOT NULL,
    cod_sistema         VARCHAR(8),                    -- '1.2'
    sistema_desc        VARCHAR(80)  NOT NULL,         -- 'Sistema de dosificación' o '(sin subcódigo)'
    cod_componente      VARCHAR(8),                    -- '1.2.C'
    componente_desc     VARCHAR(80)  NOT NULL,         -- 'Cambio de válvula' o '(general)'
    nivel_detalle       SMALLINT     NOT NULL CHECK (nivel_detalle BETWEEN 1 AND 3)
);

-- -----------------------------------------------------------------------------
-- dim_motivo_no_programado  ·  Por qué la máquina NO se programó (tiempo fuera
-- del turno: sin demanda, falta de material...). Unifica el catálogo viejo
-- ("17. PARO DE MAQUINA") con el nuevo ("[18] Paro de maquina por ventas").
-- -----------------------------------------------------------------------------
CREATE TABLE dw.dim_motivo_no_programado (
    sk_motivo           SERIAL       PRIMARY KEY,
    cod_motivo          VARCHAR(80)  NOT NULL UNIQUE,  -- motivo_estandar|observacion_estandar
    motivo_estandar     VARCHAR(50)  NOT NULL,         -- 'Sin demanda (ventas)', 'Falta de material', ...
    responsable         VARCHAR(30)  NOT NULL,         -- 'Comercial', 'Planeación', 'Almacén', 'Calidad', 'Mantenimiento', 'Producción'
    observacion         VARCHAR(80)  NOT NULL,         -- observación normalizada
    es_controlable      BOOLEAN      NOT NULL          -- ¿la planta podría haberlo evitado?
);
