"""Simulador de streaming hora a hora para la capa de monitoreo (Grafana).

Cada TICK_SEGUNDOS inserta, para cada máquina, UNA hora de producción en
dw.fact_produccion_hora (en planta real esta fila la enviaría el PLC/SCADA).
Los valores no son inventados al azar: se muestrean de la distribución
histórica de cada máquina (2024-2025) que ya está en el DW:
  - pérdida de disponibilidad por hora  (media y desviación por máquina)
  - rendimiento                         (media y desviación por máquina)
  - causa principal del paro            (frecuencia histórica de cada código)
  - referencia en producción            (las más fabricadas en esa máquina)

Para demostrar que la alerta reacciona se puede forzar una falla:
    docker compose exec simulador python forzar_falla.py Vinilos_3 6
(la máquina pierde 25-45 min por hora por falla electromecánica durante 6 horas simuladas)
"""
from __future__ import annotations

import json
import os
import random
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2

TICK = float(os.getenv("TICK_SEGUNDOS", "30"))
BACKFILL = int(os.getenv("BACKFILL_HORAS", "40"))
PROB_FALLA = float(os.getenv("PROB_FALLA_ESPONTANEA", "0.01"))
DIR_CONTROL = Path(os.getenv("DIR_CONTROL", "/tmp/control"))
SEMILLA = os.getenv("SEMILLA")
TURNOS = [(6, 14, "T1"), (14, 22, "T2"), (22, 6, "T3")]
PARO_PLANIFICADO_MIN_HORA = 43 / 8          # aseo/alimentación + pausa activa estándar (hoja Registro)


def log(msg: str) -> None:
    print(f"[simulador {datetime.now():%H:%M:%S}] {msg}", flush=True)


def conectar():
    intentos = 0
    while True:
        try:
            c = psycopg2.connect(host=os.getenv("PGHOST", "db"), port=int(os.getenv("PGPORT", "5432")),
                                 dbname=os.getenv("POSTGRES_DB", "bi_vinilos"),
                                 user=os.getenv("SIM_DB_USER", "simulador"),
                                 password=os.getenv("SIM_DB_PASSWORD", ""))
            c.autocommit = True
            return c
        except psycopg2.OperationalError as e:
            intentos += 1
            if intentos > 30:
                raise
            log(f"esperando la base de datos ({e.__class__.__name__})...")
            time.sleep(3)


def cargar_parametros(cur) -> dict:
    cur.execute("SELECT sk_turno, cod_turno FROM dw.dim_turno")
    turnos = {cod: sk for sk, cod in cur.fetchall()}

    cur.execute("""
        WITH t AS (
            SELECT f.sk_maquina,
                   f.horas_paro_disponibilidad / NULLIF(f.tiempo_planificado_h, 0)            AS perdida,
                   f.tiempo_ideal_h / NULLIF(f.tiempo_operativo_h - f.horas_paro_calidad, 0)   AS rend,
                   f.horas_paro_calidad / NULLIF(f.tiempo_operativo_h, 0)                      AS cal
            FROM dw.fact_produccion_turno f
            WHERE f.es_valido_oee AND f.sk_fecha >= 20240101 AND f.tiempo_planificado_h >= 6)
        SELECT m.sk_maquina, m.cod_maquina,
               AVG(perdida), STDDEV(perdida),
               AVG(LEAST(rend, 1.2)), STDDEV(LEAST(rend, 1.2)), AVG(cal)
        FROM t JOIN dw.dim_maquina m USING (sk_maquina)
        WHERE m.es_actual
        GROUP BY m.sk_maquina, m.cod_maquina ORDER BY m.cod_maquina""")
    maquinas = {}
    for sk, cod, pm, ps, rm, rs, cal in cur.fetchall():
        maquinas[cod] = {"sk": sk, "perdida_media": float(pm), "perdida_sd": float(ps or 0.1),
                         "rend_media": float(rm), "rend_sd": float(rs or 0.1), "calidad": float(cal or 0)}

    for cod, p in maquinas.items():
        cur.execute("""
            SELECT f.sk_referencia, e.pacas_hora_ideal, COUNT(*)
            FROM dw.fact_produccion_turno f
            JOIN dw.estandar_produccion e USING (sk_maquina, sk_referencia)
            WHERE f.sk_maquina = %s AND f.sk_referencia > 0 AND f.sk_fecha >= 20240101
            GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 5""", (p["sk"],))
        p["referencias"] = [(r, float(ideal), n) for r, ideal, n in cur.fetchall()]
        cur.execute("""
            SELECT c.sk_causa, SUM(fp.horas_paro)
            FROM dw.fact_paro fp JOIN dw.dim_causa_paro c USING (sk_causa)
            WHERE fp.sk_maquina = %s AND c.categoria_oee = 'Disponibilidad' AND c.nivel_detalle = 1
              AND fp.sk_fecha >= 20240101
            GROUP BY 1""", (p["sk"],))
        p["causas"] = [(sk, float(h)) for sk, h in cur.fetchall()]

    cur.execute("SELECT sk_causa FROM dw.dim_causa_paro WHERE cod_causa = '01|-'")
    falla = cur.fetchone()[0]
    return {"maquinas": maquinas, "turnos": turnos, "causa_falla": falla}


def turno_de(hora: int) -> str:
    for ini, fin, cod in TURNOS:
        if (ini < fin and ini <= hora < fin) or (ini > fin and (hora >= ini or hora < fin)):
            return cod
    return "T1"


def falla_forzada(maquina: str) -> bool:
    """Lee /tmp/control/<maquina>.json (lo escribe forzar_falla.py) y descuenta 1 hora."""
    f = DIR_CONTROL / f"{maquina}.json"
    if not f.exists():
        return False
    try:
        datos = json.loads(f.read_text())
        restantes = int(datos.get("horas", 0))
    except (ValueError, OSError):
        f.unlink(missing_ok=True)
        return False
    if restantes <= 1:
        f.unlink(missing_ok=True)
    else:
        f.write_text(json.dumps({"horas": restantes - 1}))
    return restantes > 0


class Estado:
    def __init__(self):
        self.fallas_espontaneas: dict[str, int] = {}
        self.referencia_actual: dict[str, tuple] = {}


def simular_hora(cod: str, p: dict, prm: dict, hora_sim: int, est: Estado, ts: datetime,
                 en_vivo: bool = True) -> tuple:
    rnd = random
    # cambio de referencia ocasional (~1 de cada 16 horas)
    if cod not in est.referencia_actual or rnd.random() < 1 / 16:
        refs = p["referencias"]
        est.referencia_actual[cod] = rnd.choices(refs, weights=[n for *_, n in refs])[0]
    sk_ref, ideal, _ = est.referencia_actual[cod]

    planificado = min(60.0, max(0.0, 60 - rnd.gauss(PARO_PLANIFICADO_MIN_HORA, 2)))
    perdida = min(0.9, max(0.0, rnd.gauss(p["perdida_media"], p["perdida_sd"] * 0.6)))
    paro_disp = planificado * perdida
    causas = p["causas"]
    causa = rnd.choices([c for c, _ in causas], weights=[h for _, h in causas])[0] if paro_disp > 2 else -1

    forzada = falla_forzada(cod) if en_vivo else False
    if not forzada and cod not in est.fallas_espontaneas and rnd.random() < PROB_FALLA:
        est.fallas_espontaneas[cod] = rnd.randint(2, 4)
    if forzada or est.fallas_espontaneas.get(cod):
        paro_disp = min(planificado, rnd.uniform(25, 45))
        causa = prm["causa_falla"]
        if not forzada:
            est.fallas_espontaneas[cod] -= 1
            if est.fallas_espontaneas[cod] <= 0:
                del est.fallas_espontaneas[cod]

    operativo = planificado - paro_disp
    paro_cal = operativo * p["calidad"]
    rend = min(1.15, max(0.3, rnd.gauss(p["rend_media"], p["rend_sd"] * 0.5)))
    pacas = round(ideal * (operativo - paro_cal) / 60 * rend, 2)
    sk_fecha = int(ts.astimezone().strftime("%Y%m%d"))
    return (ts, sk_fecha, p["sk"], prm["turnos"][turno_de(hora_sim)], sk_ref, causa,
            round(planificado, 2), round(paro_disp, 2), round(paro_cal, 2), max(pacas, 0), ideal)


SQL_INSERT = """INSERT INTO dw.fact_produccion_hora
    (ts, sk_fecha, sk_maquina, sk_turno, sk_referencia, sk_causa_principal, minutos_planificados,
     minutos_paro_disponibilidad, minutos_paro_calidad, pacas_producidas, pacas_hora_ideal)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (sk_maquina, ts) DO NOTHING"""


def main() -> int:
    if SEMILLA:
        random.seed(int(SEMILLA))
    DIR_CONTROL.mkdir(parents=True, exist_ok=True)
    conn = conectar()
    cur = conn.cursor()
    prm = cargar_parametros(cur)
    log(f"máquinas: {', '.join(prm['maquinas'])} · tick = {TICK:g} s (= 1 hora de producción)")
    est = Estado()

    cur.execute("SELECT COUNT(*), MAX(ts) FROM dw.fact_produccion_hora")
    n, ultimo = cur.fetchone()
    hora_sim = datetime.now().hour
    if n == 0 and BACKFILL > 0:
        ahora = datetime.now(timezone.utc)
        for k in range(BACKFILL, 0, -1):
            ts = ahora - timedelta(seconds=TICK * k)
            h = (hora_sim - k) % 24
            for cod, p in prm["maquinas"].items():
                cur.execute(SQL_INSERT, simular_hora(cod, p, prm, h, est, ts, en_vivo=False))
        log(f"historia inicial: {BACKFILL} horas simuladas por máquina")

    corriendo = True

    def parar(*_):
        nonlocal corriendo
        corriendo = False
    signal.signal(signal.SIGTERM, parar)
    signal.signal(signal.SIGINT, parar)

    while corriendo:
        ts = datetime.now(timezone.utc)
        resumen = []
        for cod, p in prm["maquinas"].items():
            fila = simular_hora(cod, p, prm, hora_sim, est, ts)
            cur.execute(SQL_INSERT, fila)
            oee = (fila[9] / fila[10] * 60) / fila[6] if fila[6] else 0
            resumen.append(f"{cod}: OEE {oee:5.1%}" + (" ⚠ falla" if fila[5] == prm["causa_falla"] else ""))
        log(f"hora simulada {hora_sim:02d}:00 ({turno_de(hora_sim)}) · " + " | ".join(resumen))
        hora_sim = (hora_sim + 1) % 24
        for _ in range(int(TICK * 10)):
            if not corriendo:
                break
            time.sleep(0.1)
    log("detenido")
    return 0


if __name__ == "__main__":
    sys.exit(main())
