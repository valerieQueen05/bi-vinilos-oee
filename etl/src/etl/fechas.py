"""Construcción de la dimensión fecha (dimensión propia, no viene del Excel).

Incluye el cálculo de los festivos de Colombia según la Ley 51 de 1983
("Ley Emiliani"): algunos festivos se trasladan al lunes siguiente y otros
dependen de la fecha de la Pascua.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def domingo_de_pascua(anio: int) -> date:
    """Algoritmo anónimo gregoriano (Meeus/Jones/Butcher)."""
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(anio, mes, dia)


def _siguiente_lunes(d: date) -> date:
    return d + timedelta(days=(7 - d.weekday()) % 7)


def festivos_colombia(anio: int) -> dict[date, str]:
    fijos = {
        date(anio, 1, 1): "Año Nuevo",
        date(anio, 5, 1): "Día del Trabajo",
        date(anio, 7, 20): "Día de la Independencia",
        date(anio, 8, 7): "Batalla de Boyacá",
        date(anio, 12, 8): "Inmaculada Concepción",
        date(anio, 12, 25): "Navidad",
    }
    trasladables = {
        date(anio, 1, 6): "Reyes Magos",
        date(anio, 3, 19): "San José",
        date(anio, 6, 29): "San Pedro y San Pablo",
        date(anio, 8, 15): "Asunción de la Virgen",
        date(anio, 10, 12): "Día de la Raza",
        date(anio, 11, 1): "Todos los Santos",
        date(anio, 11, 11): "Independencia de Cartagena",
    }
    if anio >= 2026:   # ley sancionada en junio de 2026; se traslada al lunes (Ley Emiliani)
        trasladables[date(anio, 7, 9)] = "Virgen de Chiquinquirá"
    pascua = domingo_de_pascua(anio)
    religiosos = {
        pascua - timedelta(days=3): "Jueves Santo",
        pascua - timedelta(days=2): "Viernes Santo",
        pascua + timedelta(days=43): "Ascensión del Señor",
        pascua + timedelta(days=64): "Corpus Christi",
        pascua + timedelta(days=71): "Sagrado Corazón",
    }
    resultado = dict(fijos)
    resultado.update({_siguiente_lunes(d): n for d, n in trasladables.items()})
    resultado.update(religiosos)
    return resultado


def construir_dim_fecha(inicio: date, fin: date) -> pd.DataFrame:
    festivos: dict[date, str] = {}
    for anio in range(inicio.year, fin.year + 1):
        festivos.update(festivos_colombia(anio))

    filas = []
    d = inicio
    while d <= fin:
        iso = d.isocalendar()
        es_festivo = d in festivos
        filas.append({
            "sk_fecha": int(d.strftime("%Y%m%d")),
            "fecha": d,
            "anio": d.year,
            "semestre": 1 if d.month <= 6 else 2,
            "trimestre": (d.month - 1) // 3 + 1,
            "mes_num": d.month,
            "mes_nombre": MESES[d.month - 1],
            "mes_abrev": MESES[d.month - 1][:3],
            "anio_mes": d.strftime("%Y-%m"),
            "dia_mes": d.day,
            "dia_semana_num": iso[2],
            "dia_semana_nombre": DIAS[d.weekday()],
            "semana_iso": iso[1],
            "anio_iso": iso[0],
            "es_fin_de_semana": d.weekday() >= 5,
            "es_festivo": es_festivo,
            "nombre_festivo": festivos.get(d),
            "es_dia_habil": d.weekday() < 6 and not es_festivo,
        })
        d += timedelta(days=1)
    return pd.DataFrame(filas)
