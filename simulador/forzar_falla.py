"""Fuerza una falla en una máquina durante N horas simuladas (para la demo de la alerta).

Uso:  docker compose exec simulador python forzar_falla.py Vinilos_3 6
"""
import json
import os
import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("Uso: python forzar_falla.py <Vinilos_N> [horas=6]")
    sys.exit(1)

maquina = sys.argv[1]
horas = int(sys.argv[2]) if len(sys.argv) > 2 else 6
d = Path(os.getenv("DIR_CONTROL", "/tmp/control"))
d.mkdir(parents=True, exist_ok=True)
(d / f"{maquina}.json").write_text(json.dumps({"horas": horas}))
print(f"Falla forzada en {maquina} durante {horas} horas simuladas.")
