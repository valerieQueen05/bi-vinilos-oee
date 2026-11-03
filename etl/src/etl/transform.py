"""LIMPIEZA y TRANSFORMACIÓN: de la fuente cruda al modelo dimensional.

Cada regla de calidad queda registrada en la bitácora (código Rxx) con sus
conteos. El orden de las funciones sigue el orden en que se ejecutan.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .calidad import BitacoraCalidad
from .extract import Fuente

N_CODIGOS = 18
SUBCOD_COL = {1: "Sub Codigo de paro 1", 3: "Subcodigo 3", 5: "Subcodigo 5"}
NULOS_TEXTO = {"", "nan", "none", "nat"}
FACTOR_ATIPICO = 2.0     # pacas > 2 × lo máximo posible a velocidad ideal => error de digitación


# --------------------------------------------------------------------------- utilidades
def _txt(v) -> str | None:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    s = re.sub(r"\s+", " ", str(v)).strip()
    return None if s.lower() in NULOS_TEXTO else s


def _sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _oracion(s: str) -> str:
    """'SISTEMA DE DOSIFICACIÓN' -> 'Sistema de dosificación'."""
    s = s.strip()
    return s[:1].upper() + s[1:].lower() if s.isupper() else s[:1].upper() + s[1:]


def _num(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(serie, errors="coerce")


@dataclass
class Modelo:
    dim_fecha: pd.DataFrame | None
    dim_maquina: pd.DataFrame
    dim_turno: pd.DataFrame
    dim_persona: pd.DataFrame
    persona_identidad: pd.DataFrame
    dim_referencia: pd.DataFrame
    estandar: pd.DataFrame
    dim_causa: pd.DataFrame
    dim_motivo: pd.DataFrame
    fact_turno: pd.DataFrame
    fact_paro: pd.DataFrame
    fact_tnp: pd.DataFrame
    base_limpia: pd.DataFrame   # para conciliación


# =========================================================================== 1. limpieza base
def limpiar_base(f: Fuente, cfg: Path, dq: BitacoraCalidad) -> pd.DataFrame:
    df = f.base.copy()
    n0 = len(df)

    # R01 filas totalmente vacías
    vacias = df.drop(columns="fila_excel").isna().all(axis=1)
    df = df[~vacias].copy()
    dq.registrar("R01", "completitud", "Filas completamente vacías dentro del rango de la tabla",
                 "Eliminadas", n0, vacias.sum(), len(df))

    # R02 columnas 100 % vacías
    vac_cols = [c for c in df.columns if df[c].isna().all()]
    df = df.drop(columns=vac_cols)
    dq.registrar("R02", "completitud",
                 f"Columnas sin ningún dato: {', '.join(vac_cols)}",
                 "Columnas descartadas del modelo", len(df), 0, len(df))

    # Tipos básicos
    df["fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.date
    df["anio_txt"] = df["Año"].astype(str).str.strip()
    malas_fechas = df["fecha"].isna().sum()
    incoh = (pd.to_datetime(df["fecha"]).dt.year.astype(str) != df["anio_txt"]).sum()
    dq.registrar("R03", "validez",
                 "Año guardado como texto; se valida contra la fecha. Mes en texto se reemplaza por la dimensión fecha",
                 f"Año convertido a entero; fechas inválidas: {malas_fechas}; año≠fecha: {incoh}",
                 len(df), int(malas_fechas + incoh), len(df))

    for c in ["Maquina", "Operario", "Referencia", "Turno", "Tipo de paro", "Observaciones de paro",
              "Personal involucrado", "Área involucrada en subcodigo 5", "Unidad por display"]:
        if c in df.columns:
            df[c] = df[c].map(_txt)
    for c in ["Pacas producidas", "Horas trabajadas", "Horas no trabajadas", "Tiempo de Paro"]:
        df[c] = _num(df[c])
    for i in range(1, N_CODIGOS + 1):
        df[f"Codigo de paro {i}"] = _num(df[f"Codigo de paro {i}"])

    # R04 columna mal rotulada: "Unidad por display" contiene una copia del turno
    turnos = pd.read_csv(cfg / "turnos.csv")
    validos = set(turnos["valor_origen"])
    col = df["Unidad por display"]
    con_valor = col.notna()
    distinto = con_valor & df["Turno"].notna() & (col != df["Turno"])
    mask = df["Turno"].isna() & col.isin(validos)
    df.loc[mask, "Turno"] = col[mask]
    dq.registrar("R04", "validez",
                 f"La columna 'Unidad por display' no trae unidades: en {int(con_valor.sum())} filas tiene una copia "
                 f"del turno ({int(distinto.sum())} escritas distinto, p. ej. '10pm-6am' sin '(Turno 3)')",
                 f"Columna descartada; se usa solo para rellenar Turno vacío ({int(mask.sum())} casos)",
                 len(df), int(con_valor.sum()))

    # R05 estandarizar turno
    mapa = dict(zip(turnos["valor_origen"], turnos["cod_turno"]))
    df["cod_turno"] = df["Turno"].map(mapa)
    hist = df["cod_turno"].isna() & df["Turno"].isna()
    df.loc[hist, "cod_turno"] = "SH"
    raros = df["cod_turno"].isna()
    df.loc[raros, "cod_turno"] = "SR"
    dq.registrar("R05", "consistencia",
                 f"Turno con {df['Turno'].nunique()} escrituras distintas y {hist.sum()} vacíos (registros 2022-2023)",
                 "Mapeado a catálogo dim_turno; vacíos -> 'Sin turno (histórico)'",
                 len(df), int(hist.sum() + raros.sum()))
    return df


# =========================================================================== 2. clasificación de filas
def clasificar_filas(df: pd.DataFrame, dq: BitacoraCalidad) -> pd.DataFrame:
    ht = df["Horas trabajadas"]
    pac = df["Pacas producidas"]
    hnt = df["Horas no trabajadas"].fillna(0)
    paro = df["Tiempo de Paro"].fillna(0)

    tipo = np.select(
        [ht.fillna(0) > 0,
         ht.isna() & pac.notna() & (pac > 0),
         ht.isna() & pac.isna() & (df["cod_turno"] != "SH") & (paro > 0) & (hnt == 0),
         hnt > 0],
        ["produccion", "produccion", "continuacion", "no_programado"],
        default="sin_actividad")
    df["tipo_fila"] = tipo
    cnt = df["tipo_fila"].value_counts().to_dict()
    dq.registrar("R06", "consistencia",
                 "La tabla mezcla 4 tipos de fila: registro de turno ('Ingreso total'), continuación de paros "
                 "('Ingreso subcódigo'), día no programado y filas sin actividad. Conteo: "
                 + ", ".join(f"{k}={v}" for k, v in sorted(cnt.items())),
                 "Cada tipo se enruta a su tabla de hechos", len(df), len(df) - cnt.get("produccion", 0))
    return df


# =========================================================================== 3. duplicados
def quitar_duplicados(df: pd.DataFrame, dq: BitacoraCalidad) -> pd.DataFrame:
    n0 = len(df)
    cols = [c for c in df.columns if c not in ("fila_excel",)]
    dup = df.duplicated(subset=cols, keep="first") & df["tipo_fila"].isin(["produccion", "no_programado"])
    # Las filas de continuación idénticas son paros distintos de igual duración: se conservan
    dup_cont = df.duplicated(subset=cols, keep="first") & (df["tipo_fila"] == "continuacion")
    df = df[~dup].copy()
    dq.registrar("R07", "unicidad",
                 f"Filas idénticas en todos los campos (registros de turno / días no programados). "
                 f"Además hay {int(dup_cont.sum())} filas de continuación idénticas que SÍ se conservan "
                 "(dos paros iguales en el mismo turno son posibles)",
                 "Se conserva la primera aparición", n0, dup.sum(), len(df))
    return df


# =========================================================================== 4. personas
def construir_personas(df: pd.DataFrame, f: Fuente, cfg: Path, dq: BitacoraCalidad):
    alias = dict(pd.read_csv(cfg / "personas_alias.csv").values)
    nulos = {"No aplica", "No"}

    def norm(v):
        v = _txt(v)
        if v is None or v in nulos:
            return None
        return alias.get(v, v)

    variantes: dict[str, set] = {}
    for col in ["Operario", "Personal involucrado"]:
        for v in df[col].dropna().unique():
            n = norm(v)
            if n:
                variantes.setdefault(n, set()).add(v)

    antes = df["Operario"].nunique() + df["Personal involucrado"].nunique()
    df["persona_op"] = df["Operario"].map(norm)
    df["persona_inv"] = df["Personal involucrado"].map(norm)
    cambiadas = sum(1 for n, vs in variantes.items() if vs != {n})
    dq.registrar("R08", "consistencia",
                 "Nombres de personas con variantes ortográficas (p. ej. 'Argüello Molsalve' vs 'Arguello Monsalve', "
                 "'Luis Mercado' vs 'Luis Carlos Mercado Mercado') y valores 'No'/'No aplica'/vacíos. "
                 "Los nombres con inicial distinta ('Marcela' / 'Marcela C.') se tratan como personas diferentes",
                 f"Unificadas con personas_alias.csv; {len(variantes)} personas únicas (antes {antes} escrituras)",
                 antes, cambiadas, len(variantes))

    sin_op = df["tipo_fila"].isin(["produccion", "continuacion"]) & df["persona_op"].isna()
    dq.registrar("R09", "completitud", "Registros de turno/paro sin operaria (mayoría 2022-2023)",
                 "Asignados al miembro -1 'No registrado'", int(df["tipo_fila"].isin(["produccion", "continuacion"]).sum()),
                 sin_op.sum())

    operarias = set(df["persona_op"].dropna())
    mantenimiento = {alias.get(m, m) for m in f.mantenimiento}
    filas, ident = [{"sk_persona": -1, "cod_persona": "NR", "rol": "No aplica",
                     "alias_publico": "No registrado"}], []
    contador = {"OP": 0, "MT": 0, "OT": 0}
    for nombre in sorted(variantes, key=lambda s: _sin_tildes(s).lower()):
        pref = "MT" if nombre in mantenimiento else ("OP" if nombre in operarias else "OT")
        contador[pref] += 1
        cod = f"{pref}-{contador[pref]:03d}"
        rol = {"MT": "Mantenimiento", "OP": "Operaria/o", "OT": "Otro personal"}[pref]
        sk = len(filas)
        filas.append({"sk_persona": sk, "cod_persona": cod, "rol": rol,
                      "alias_publico": f"{rol.split('/')[0]} {contador[pref]:03d}"})
        ident.append({"sk_persona": sk, "nombre_normalizado": nombre,
                      "variantes_origen": " | ".join(sorted(variantes[nombre]))})
    dim = pd.DataFrame(filas)
    idn = pd.DataFrame(ident)
    mapa = dict(zip(idn["nombre_normalizado"], idn["sk_persona"]))
    df["sk_operario"] = df["persona_op"].map(mapa).fillna(-1).astype(int)
    df["sk_persona_inv"] = df["persona_inv"].map(mapa).fillna(-1).astype(int)
    return df, dim, idn


# =========================================================================== 5. referencias
_RE_CC = re.compile(r"(\d+)\s*cc", re.I)
_RE_COL = re.compile(r"\(\s*(\d+)\s*col\s*\)", re.I)


def normalizar_referencia(v) -> str | None:
    v = _txt(v)
    if v is None or v == "No aplica":
        return None
    s = re.sub(r"^Alocdor", "Alocolor", v)
    s = re.sub(r"^(Stilo|Estilo) Kids", "Estilo Kids", s)
    s = _RE_CC.sub(lambda m: f"{m.group(1)}cc", s)
    s = _RE_COL.sub(lambda m: f"({m.group(1)} col)", s)
    return re.sub(r"\s+", " ", s).strip()


def construir_referencias(df: pd.DataFrame, f: Fuente, dq: BitacoraCalidad):
    est = f.estandares.copy()
    est["ref_norm"] = est["referencia"].map(lambda v: normalizar_referencia(_txt(v)))
    df["ref_norm"] = df["Referencia"].map(normalizar_referencia)
    antes = df["Referencia"].nunique()
    cambiadas = (df["Referencia"].notna() & (df["Referencia"] != df["ref_norm"]) &
                 (df["Referencia"] != "No aplica")).sum()
    dq.registrar("R10", "consistencia",
                 "Referencias escritas de varias formas ('Alocdor 22cc (6col)', 'Stilo/Estilo Kids', "
                 "'Klips 15cc (12col)', '15 cc' vs '15cc')",
                 f"Normalizadas: {antes} escrituras -> {df['ref_norm'].nunique()} referencias",
                 len(df), cambiadas)

    nombres = sorted(set(df["ref_norm"].dropna()) | set(est["ref_norm"].dropna()))
    filas = [{"sk_referencia": -1, "cod_referencia": "SIN_REF", "nombre_referencia": "No registrada",
              "marca": "No registrada", "tamano_cc": None, "n_colores": None, "familia_tamano": "Otro"}]
    for i, n in enumerate(nombres, start=1):
        cc = _RE_CC.search(n)
        col = _RE_COL.search(n)
        marca = re.split(r"\s\d|\sx\s", n)[0].strip()
        tam = int(cc.group(1)) if cc else None
        filas.append({"sk_referencia": i, "cod_referencia": n, "nombre_referencia": n,
                      "marca": marca, "tamano_cc": tam,
                      "n_colores": int(col.group(1)) if col else (1 if tam == 125 else None),
                      "familia_tamano": f"{tam} cc" if tam else "Otro"})
    dim = pd.DataFrame(filas)
    mapa = dict(zip(dim["cod_referencia"], dim["sk_referencia"]))
    df["sk_referencia"] = df["ref_norm"].map(mapa).fillna(-1).astype(int)
    sin_ref = df["tipo_fila"].eq("produccion") & df["sk_referencia"].eq(-1)
    dq.registrar("R11", "completitud", "Registros de turno sin referencia (2022-2023 o 'No aplica')",
                 "Miembro -1 'No registrada'; la velocidad ideal se imputa con el promedio de la máquina",
                 int(df["tipo_fila"].eq("produccion").sum()), sin_ref.sum())
    return df, dim, est


# =========================================================================== 6. máquinas y estándares
def construir_maquinas_estandares(df, est, dim_ref, dq: BitacoraCalidad):
    est = est.copy()
    est["unidades_por_paca"] = _num(est["unidades_por_paca"])
    est["unidades_por_minuto"] = _num(est["unidades_por_minuto"])
    n0 = len(est)
    est = est[est["ref_norm"].notna() & (est["unidades_por_paca"] > 0)]
    # velocidad nominal = moda de la tabla de cada máquina (hay una fila de Vinilos_2 dentro de la tabla de Vinilos_1)
    vel = est.groupby("maquina")["unidades_por_minuto"].agg(lambda s: s.mode().iloc[0]).to_dict()
    dup = est.duplicated(["maquina", "ref_norm"])
    est = est[~dup]
    dq.registrar("R12", "unicidad",
                 "Tabla de estándares (Tabla8/14/15/16): filas 'No aplica', referencias repetidas en la misma "
                 "máquina y una fila de Vinilos_2 dentro de la tabla de Vinilos_1",
                 "Se eliminan vacías/duplicadas; la velocidad de cada máquina es la moda de su tabla",
                 n0, n0 - len(est), len(est))

    factor = {"Vinilos_1": 0.93, "Vinilos_2": 0.96, "Vinilos_3": 1.0, "Vinilos_4": 1.0}
    maquinas = sorted(set(df["Maquina"].dropna()) | set(vel))
    dim_maq = pd.DataFrame([{
        "sk_maquina": i, "cod_maquina": m, "nombre_maquina": m.replace("_", " "),
        "linea": "Envasado vinilos y témperas", "velocidad_nominal_upm": vel.get(m),
        "factor_eficiencia": factor.get(m, 1.0), "valido_desde": pd.Timestamp("2022-01-01").date(),
        "valido_hasta": pd.Timestamp("9999-12-31").date(), "es_actual": True} for i, m in enumerate(maquinas, 1)])
    sk_maq = dict(zip(dim_maq["cod_maquina"], dim_maq["sk_maquina"]))
    df["sk_maquina"] = df["Maquina"].map(sk_maq).astype(int)

    # --- estándar por (máquina, referencia) con imputación documentada
    sk_ref = dict(zip(dim_ref["cod_referencia"], dim_ref["sk_referencia"]))
    est["sk_ref"] = est["ref_norm"].map(sk_ref)
    upp_ref = est.groupby("sk_ref")["unidades_por_paca"].median().to_dict()
    ref_attr = dim_ref.set_index("sk_referencia")
    est_attr = est.drop(columns=["n_colores"]).merge(ref_attr[["tamano_cc", "n_colores"]], left_on="sk_ref", right_index=True)
    upp_tam = est_attr.groupby(["tamano_cc", "n_colores"])["unidades_por_paca"].median().to_dict()
    upp_tam_solo = est_attr.groupby("tamano_cc")["unidades_por_paca"].median().to_dict()

    combos = df.loc[df["tipo_fila"] == "produccion", ["Maquina", "sk_referencia"]].drop_duplicates()
    tabla = {(r.maquina, r.sk_ref): r.unidades_por_paca for r in est.itertuples()}

    def upp_conocido(m, r):
        if (m, r) in tabla:
            return tabla[(m, r)], "tabla_maquina"
        if r in upp_ref:
            return upp_ref[r], "otra_maquina"
        if r > 0:
            t, c = ref_attr.loc[r, "tamano_cc"], ref_attr.loc[r, "n_colores"]
            v = upp_tam.get((t, c), upp_tam_solo.get(t))
            if v is not None and not pd.isna(v):
                return v, "imputado_tamano"
        return None, None

    # Velocidad ideal "de mezcla" por máquina para registros sin referencia (2022-2023):
    # pacas totales / horas ideales totales de los turnos CON referencia y estándar de tabla
    # (= media armónica ponderada por la mezcla real de productos de esa máquina).
    prod = df[(df["tipo_fila"] == "produccion") & (df["sk_referencia"] > 0)].copy()
    prod["upp"] = [tabla.get((m, r)) for m, r in zip(prod["Maquina"], prod["sk_referencia"])]
    prod = prod[prod["upp"].notna() & (prod["Pacas producidas"] > 0) & (prod["Horas trabajadas"] > 0)]
    prod["rate"] = 60.0 * prod["Maquina"].map(vel) / prod["upp"]
    prod = prod[prod["Pacas producidas"] <= prod["rate"] * prod["Horas trabajadas"] * FACTOR_ATIPICO]
    mezcla = (prod.groupby("Maquina")["Pacas producidas"].sum()
              / (prod["Pacas producidas"] / prod["rate"]).groupby(prod["Maquina"]).sum()).to_dict()

    filas = []
    for m, r in combos.itertuples(index=False):
        upm = float(vel.get(m))
        upp, origen = upp_conocido(m, r)
        if upp is None:
            upp, origen = 60.0 * upm / mezcla[m], "imputado_mezcla_maquina"
        filas.append({"sk_maquina": sk_maq[m], "sk_referencia": r, "unidades_por_paca": float(upp),
                      "unidades_por_minuto": upm, "pacas_hora_ideal": 60.0 * upm / float(upp),
                      "origen_estandar": origen})
    estandar = pd.DataFrame(filas)
    # El simulador necesita estándar para todas las referencias de la tabla de cada máquina
    extra = []
    for r in est.itertuples():
        if r.maquina in sk_maq and not ((estandar["sk_maquina"] == sk_maq[r.maquina]) &
                                        (estandar["sk_referencia"] == r.sk_ref)).any():
            upm = vel[r.maquina]
            extra.append({"sk_maquina": sk_maq[r.maquina], "sk_referencia": int(r.sk_ref),
                          "unidades_por_paca": float(r.unidades_por_paca), "unidades_por_minuto": float(upm),
                          "pacas_hora_ideal": 60.0 * upm / float(r.unidades_por_paca),
                          "origen_estandar": "tabla_maquina"})
    cnt = estandar["origen_estandar"].value_counts().to_dict()
    estandar = pd.concat([estandar, pd.DataFrame(extra)], ignore_index=True)
    dq.registrar("R13", "completitud",
                 "Combinaciones máquina×referencia producidas sin estándar de velocidad en las tablas del Excel. "
                 "Origen del estándar: " + ", ".join(f"{k}={v}" for k, v in cnt.items()),
                 "Imputación jerárquica: misma referencia en otra máquina -> mediana por tamaño/colores -> "
                 "velocidad de mezcla de la máquina (registros sin referencia). Queda marcado en origen_estandar",
                 len(combos), int(len(combos) - cnt.get("tabla_maquina", 0)))
    return df, dim_maq, estandar


# =========================================================================== 7. causas de paro
_RE_SUB = re.compile(r"^(\d+)\.(\d+)(?:(?:\.|\s*)([A-Z])(?![A-ZÁÉÍÓÚÑ'])|\.(\d+))?")


def normalizar_subcodigo(cod: str, valor: str | None, equiv: pd.DataFrame) -> str | None:
    if valor is None:
        return None
    up = valor.upper().strip()
    m = _RE_SUB.match(up)
    if not m:
        return None
    a, b, letra, num = m.groups()
    token = f"{a}.{b}" + (f".{letra}" if letra else (f".{num}" if num else ""))
    for e in equiv[equiv["cod_codigo"] == cod].itertuples():
        partes = e.valor_origen_normalizado.split("|")
        if token == partes[0] and all(p in up for p in partes[1:]):
            return e.cod_componente_destino
    return token


def construir_causas(f: Fuente, cfg: Path) -> pd.DataFrame:
    clas = pd.read_csv(cfg / "clasificacion_codigos.csv", dtype=str).fillna("")
    cat = f.codigos.copy()
    cat["cod_codigo"] = cat["key"].str.extract(r"(\d+)")[0].str.zfill(2)
    cat = cat.merge(clas, on="cod_codigo", how="right")
    sub = f.subcod_catalogo.copy()
    sub["llave"] = sub["llave"].str.upper()
    sub["desc"] = sub["descripcion"].str.replace(r"^\d+\.\d+(\.\w+)?\s*", "", regex=True).map(_oracion)

    filas = []

    def add(cod, row, cod_sis, sis, cod_comp, comp, nivel):
        desc = row.descripcion_override or re.sub(r"^\[\d+\]\s*", "", str(row.paro))
        filas.append({
            "cod_causa": f"{cod}|{cod_comp or cod_sis or '-'}",
            "cod_codigo": cod, "codigo_desc": f"[{cod}] {desc}",
            "area_impacto": row.area_override or str(row.area_impacto).strip(),
            "categoria_oee": row.categoria_oee, "es_planificado": row.es_planificado == "true",
            "cod_sistema": cod_sis, "sistema_desc": sis, "cod_componente": cod_comp,
            "componente_desc": comp, "nivel_detalle": nivel})

    for row in cat.itertuples():
        cod = row.cod_codigo
        add(cod, row, None, "(sin subcódigo)", None, "(general)", 1)
        s = sub[sub["cod_codigo"] == cod]
        if s.empty:
            continue
        sistemas = s[s["llave"].str.count(r"\.") == 1]
        for sis in sistemas.itertuples():
            add(cod, row, sis.llave, sis.desc, None, "(general)", 2)
            for comp in s[s["llave"].str.startswith(sis.llave + ".")].itertuples():
                add(cod, row, sis.llave, sis.desc, comp.llave, comp.desc, 3)
    dim = pd.DataFrame(filas)
    dim.insert(0, "sk_causa", range(1, len(dim) + 1))
    return dim


# =========================================================================== 8. paros (ancho -> largo)
def construir_paros(df: pd.DataFrame, dim_causa: pd.DataFrame, cfg: Path, dq: BitacoraCalidad):
    equiv = pd.read_csv(cfg / "subcodigos_equivalencias.csv", dtype=str)
    validas = set(dim_causa["cod_causa"])
    sin_cat = 0
    ajustados = 0
    filas = []
    cols_idx = {c: k for k, c in enumerate(df.columns)}
    arr = df.to_numpy(dtype=object)
    for k in range(len(arr)):
        fila = arr[k]
        for i in range(1, N_CODIGOS + 1):
            minutos = fila[cols_idx[f"Codigo de paro {i}"]]
            if minutos is None or pd.isna(minutos) or minutos <= 0:
                continue
            cod = f"{i:02d}"
            comp = None
            if i in SUBCOD_COL and SUBCOD_COL[i] in cols_idx:
                raw = _txt(fila[cols_idx[SUBCOD_COL[i]]])
                comp = normalizar_subcodigo(cod, raw, equiv)
                if raw and comp and not raw.upper().startswith(comp + " "):
                    ajustados += 1
            causa = f"{cod}|{comp or '-'}"
            if causa not in validas:
                # subcódigo no catalogado: subir al sistema (1.2.X -> 1.2) o al código
                padre = f"{cod}|{'.'.join(comp.split('.')[:2])}" if comp else None
                causa = padre if padre in validas else f"{cod}|-"
                sin_cat += 1
            es5 = i == 5
            area = _txt(fila[cols_idx["Área involucrada en subcodigo 5"]]) if es5 else None
            filas.append({
                "fila_origen": int(fila[cols_idx["fila_excel"]]),
                "cod_causa": causa,
                "minutos_paro": float(minutos),
                "sk_persona_involucrada": int(fila[cols_idx["sk_persona_inv"]]) if es5 else -1,
                "area_involucrada": (area or "No aplica").replace("Personal_de_mantenimiento", "Mantenimiento"),
            })
    paros = pd.DataFrame(filas)
    n_celdas = len(df) * N_CODIGOS
    dq.registrar("R14", "consistencia",
                 f"Formato ancho: 18 pares de columnas 'Código N'/'Código N en horas' ({n_celdas} celdas). "
                 "Los minutos coinciden con las horas en el 100 % de las filas y 'Tiempo de Paro' = suma de códigos",
                 "Unpivot a una fila por evento de paro con minutos > 0", n_celdas,
                 n_celdas - len(paros), len(paros))
    dq.registrar("R15", "consistencia",
                 "Subcódigos con dos catálogos (código 5: '4.2 SISTEMA DOSIFICADOR...' vs '5.2 Sistema de "
                 "dosificación...'; código 1: '1.2C' vs '1.2.C', '1.4.3' vs '1.4.C')",
                 f"Normalizados a la llave oficial con subcodigos_equivalencias.csv; {sin_cat} sin catálogo "
                 "subidos al nivel superior", len(paros), ajustados + sin_cat)
    sk = dict(zip(dim_causa["cod_causa"], dim_causa["sk_causa"]))
    paros["sk_causa"] = paros["cod_causa"].map(sk).astype(int)
    paros["horas_paro"] = paros["minutos_paro"] / 60.0
    return paros


# =========================================================================== 9. hechos
def construir_hechos(df, paros, dim_causa, dim_maq, estandar, dq: BitacoraCalidad):
    base = df.copy()
    base["sk_fecha"] = pd.to_datetime(base["fecha"]).dt.strftime("%Y%m%d").astype(int)

    # --- enlazar filas de continuación con su registro de turno
    prod = base[base["tipo_fila"] == "produccion"]
    cont = base[base["tipo_fila"] == "continuacion"]
    k_full = ["fecha", "Maquina", "cod_turno", "sk_operario", "sk_referencia"]
    k_corta = ["fecha", "Maquina", "cod_turno"]

    def enlazar(claves):
        p = prod[claves + ["fila_excel"]].rename(columns={"fila_excel": "registro"})
        c = cont[claves + ["fila_excel"]].merge(p, on=claves, how="inner")
        c["dist"] = (c["fila_excel"] - c["registro"]).abs()
        return c.sort_values("dist").drop_duplicates("fila_excel").set_index("fila_excel")["registro"]

    e1 = enlazar(k_full)
    e2 = enlazar(k_corta)
    enlace = e1.combine_first(e2)
    base["id_registro"] = np.where(base["tipo_fila"] == "produccion", base["fila_excel"],
                                   base["fila_excel"].map(enlace))
    huerfanas = cont["fila_excel"].map(enlace).isna().sum()
    dq.registrar("R16", "integridad",
                 "Filas de continuación ('Ingreso subcódigo') que deben sumarse a su registro de turno. "
                 f"Enlazadas por llave completa: {len(e1)}; por fecha+máquina+turno: {len(enlace) - len(e1)}",
                 "Sus paros se agregan al registro; las no enlazables quedan como paros huérfanos (id_registro NULL)",
                 len(cont), int(huerfanas))

    # --- paros con atributos de la fila de origen
    attrs = base.set_index("fila_excel")[["id_registro", "sk_fecha", "sk_maquina", "cod_turno", "sk_operario",
                                          "sk_referencia", "tipo_fila"]]
    paros = paros.join(attrs, on="fila_origen")
    paros["es_fila_continuacion"] = paros["tipo_fila"].eq("continuacion")
    cat = dim_causa.set_index("sk_causa")["categoria_oee"]
    paros["categoria"] = paros["sk_causa"].map(cat)

    agg = (paros[paros["id_registro"].notna()]
           .pivot_table(index="id_registro", columns="categoria", values="horas_paro", aggfunc="sum", fill_value=0))
    for c in ["Planificado", "Disponibilidad", "Calidad"]:
        if c not in agg:
            agg[c] = 0.0
    n_ev = paros[paros["id_registro"].notna()].groupby("id_registro").size()

    f = prod.copy()
    f["id_registro"] = f["fila_excel"]
    f["sk_fecha"] = pd.to_datetime(f["fecha"]).dt.strftime("%Y%m%d").astype(int)
    f = f.join(agg, on="id_registro").fillna({"Planificado": 0, "Disponibilidad": 0, "Calidad": 0})
    f["n_eventos_paro"] = f["id_registro"].map(n_ev).fillna(0).astype(int)
    f["horas_trabajadas"] = f["Horas trabajadas"].fillna(0)
    f["horas_paro_planificado"] = f["Planificado"]
    f["horas_paro_disponibilidad"] = f["Disponibilidad"]
    f["horas_paro_calidad"] = f["Calidad"]
    f["horas_paro_total"] = f[["Planificado", "Disponibilidad", "Calidad"]].sum(axis=1)
    f["tiempo_planificado_h"] = (f["horas_trabajadas"] - f["horas_paro_planificado"]).clip(lower=0)
    f["tiempo_operativo_h"] = (f["tiempo_planificado_h"] - f["horas_paro_disponibilidad"]).clip(lower=0)
    f["dq_paro_mayor_turno"] = f["horas_paro_total"] > f["horas_trabajadas"] + 1e-6
    dq.registrar("R17", "exactitud",
                 "Registros de turno cuyo tiempo de paro supera las horas trabajadas",
                 "Se marcan (dq_paro_mayor_turno); el tiempo operativo se acota en 0", len(f),
                 f["dq_paro_mayor_turno"].sum())

    # --- estándar y pacas atípicas
    est = estandar.set_index(["sk_maquina", "sk_referencia"])
    idx = list(zip(f["sk_maquina"], f["sk_referencia"]))
    f["pacas_hora_ideal"] = [est.loc[i, "pacas_hora_ideal"] for i in idx]
    f["origen_estandar"] = [est.loc[i, "origen_estandar"] for i in idx]
    fac = dim_maq.set_index("sk_maquina")["factor_eficiencia"]
    pac = f["Pacas producidas"]
    max_posible = f["pacas_hora_ideal"] * f["horas_trabajadas"] * FACTOR_ATIPICO
    f["dq_pacas_atipica"] = pac.notna() & (pac > max_posible.clip(lower=1))
    dq.registrar("R18", "exactitud",
                 f"Pacas imposibles: más de {FACTOR_ATIPICO:g}× lo que la máquina produce a velocidad ideal en las "
                 "horas del turno (p. ej. 4.320 a 9.417 'pacas' en 8 h en Vinilos_1, jul-2023: se digitaron unidades)",
                 "Pacas -> NULL en el hecho (excluidas de rendimiento/OEE); valor original queda en stg",
                 int(pac.notna().sum()), f["dq_pacas_atipica"].sum())
    f["pacas_producidas"] = pac.where(~f["dq_pacas_atipica"])
    f["tiempo_ideal_h"] = f["pacas_producidas"] / f["pacas_hora_ideal"]
    f["pacas_meta"] = f["pacas_hora_ideal"] * f["sk_maquina"].map(fac) * f["tiempo_planificado_h"]
    f["es_registro_historico"] = f["cod_turno"].eq("SH")
    f["es_valido_oee"] = ((f["horas_trabajadas"] > 0) & f["pacas_producidas"].notna()
                          & (f["tiempo_operativo_h"] - f["horas_paro_calidad"] > 0))

    # --- paros: columnas finales
    paros["sk_turno_cod"] = paros["cod_turno"]

    # --- tiempo no programado
    t = base[base["Horas no trabajadas"].fillna(0) > 0].copy()
    t["sk_fecha"] = pd.to_datetime(t["fecha"]).dt.strftime("%Y%m%d").astype(int)
    t["dq_horas_recortadas"] = t["Horas no trabajadas"] > 24
    dq.registrar("R19", "validez", "Horas no trabajadas mayores a 24 en un solo registro (máx. 32)",
                 "Recortadas a 24 h y marcadas", len(t), t["dq_horas_recortadas"].sum())
    t["horas_no_programadas"] = t["Horas no trabajadas"].clip(upper=24)
    return f, paros, t


# =========================================================================== 10. motivos no programados
def construir_motivos(t: pd.DataFrame, cfg: Path, dq: BitacoraCalidad):
    obs = pd.read_csv(cfg / "motivos_no_programado.csv")
    tip = pd.read_csv(cfg / "motivos_tipo_paro.csv")

    def clasificar(r):
        o = _sin_tildes((_txt(r["Observaciones de paro"]) or "").upper())
        for x in obs.itertuples():
            if re.search(_sin_tildes(x.patron_observacion), o):
                return x.motivo_estandar, x.responsable, bool(x.es_controlable), x.observacion_estandar
        tp = _sin_tildes((_txt(r["Tipo de paro"]) or "").upper())
        for x in tip.itertuples():
            if re.search(_sin_tildes(x.patron_tipo_paro), tp):
                return x.motivo_estandar, x.responsable, bool(x.es_controlable), "No especificada"
        return "No especificado", "Sin asignar", False, "No especificada"

    res = t.apply(clasificar, axis=1, result_type="expand")
    t[["motivo_estandar", "responsable", "es_controlable", "observacion"]] = res
    t["cod_motivo"] = t["motivo_estandar"] + "|" + t["observacion"]
    dq.registrar("R20", "consistencia",
                 f"'Tipo de paro' usa dos catálogos (viejo '17. PARO DE MAQUINA' y nuevo '[18] Paro de maquina por "
                 f"ventas'; {t['Tipo de paro'].nunique()} valores) y la observación tiene errores ('FALTADE', "
                 "'RESESO', 'NO SE PROGRAMOS')",
                 f"Unificados en {t['motivo_estandar'].nunique()} motivos estándar con responsable",
                 len(t), int((t["motivo_estandar"] == "No especificado").sum()))
    dim = (t[["cod_motivo", "motivo_estandar", "responsable", "observacion", "es_controlable"]]
           .drop_duplicates("cod_motivo").sort_values("cod_motivo").reset_index(drop=True))
    dim.insert(0, "sk_motivo", range(1, len(dim) + 1))
    t["sk_motivo"] = t["cod_motivo"].map(dict(zip(dim["cod_motivo"], dim["sk_motivo"])))
    return t, dim


# =========================================================================== orquestación
def transformar(fuente: Fuente, cfg: Path, dq: BitacoraCalidad) -> Modelo:
    df = limpiar_base(fuente, cfg, dq)
    df = clasificar_filas(df, dq)
    df = quitar_duplicados(df, dq)
    df, dim_persona, identidad = construir_personas(df, fuente, cfg, dq)
    df, dim_ref, est_raw = construir_referencias(df, fuente, dq)
    df, dim_maq, estandar = construir_maquinas_estandares(df, est_raw, dim_ref, dq)
    dim_causa = construir_causas(fuente, cfg)
    paros = construir_paros(df, dim_causa, cfg, dq)
    fact_turno, fact_paro, tnp = construir_hechos(df, paros, dim_causa, dim_maq, estandar, dq)
    tnp, dim_motivo = construir_motivos(tnp, cfg, dq)

    dim_turno = pd.read_csv(cfg / "dim_turno.csv", dtype={"hora_inicio": str, "hora_fin": str},
                            keep_default_na=False, na_values=[""])
    sk_turno = dict(zip(dim_turno["cod_turno"], dim_turno["sk_turno"]))
    for t in (fact_turno, tnp):
        t["sk_turno"] = t["cod_turno"].map(sk_turno).astype(int)
    fact_paro["sk_turno"] = fact_paro["cod_turno"].map(sk_turno).astype(int)

    return Modelo(dim_fecha=None, dim_maquina=dim_maq, dim_turno=dim_turno, dim_persona=dim_persona,
                  persona_identidad=identidad, dim_referencia=dim_ref, estandar=estandar,
                  dim_causa=dim_causa, dim_motivo=dim_motivo, fact_turno=fact_turno,
                  fact_paro=fact_paro, fact_tnp=tnp, base_limpia=df)
