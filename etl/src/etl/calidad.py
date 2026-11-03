"""Registro de reglas de calidad de datos (data quality) con conteos antes/después.

Cada regla que aplica el ETL se anota aquí; al final se guarda en
audit.regla_calidad y se publica como reporte en docs/generados/.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Regla:
    cod_regla: str
    dimension_dq: str
    descripcion: str
    accion: str
    filas_antes: int
    filas_afectadas: int
    filas_despues: int


@dataclass
class BitacoraCalidad:
    reglas: list[Regla] = field(default_factory=list)

    def registrar(self, cod: str, dimension: str, descripcion: str, accion: str,
                  antes: int, afectadas: int, despues: int | None = None) -> None:
        self.reglas.append(Regla(cod, dimension, descripcion, accion, int(antes),
                                 int(afectadas), int(antes if despues is None else despues)))

    def como_filas(self) -> list[dict]:
        return [r.__dict__ | {"orden": i + 1} for i, r in enumerate(self.reglas)]

    def imprimir(self) -> None:
        print(f"{'Regla':6} {'Antes':>7} {'Afect.':>7} {'Después':>8}  Descripción")
        for r in self.reglas:
            print(f"{r.cod_regla:6} {r.filas_antes:7d} {r.filas_afectadas:7d} {r.filas_despues:8d}  {r.descripcion}")
