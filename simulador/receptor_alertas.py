"""Receptor mínimo de notificaciones (webhook) de Grafana.

Grafana envía aquí cada alerta (contact point 'webhook-planta'); el servicio la
imprime en su log. Así se demuestra en la sustentación que la notificación sale:
    docker compose logs -f alertas
En una planta real este webhook sería Teams, Slack, correo o WhatsApp Business.
"""
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        cuerpo = self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0)
        try:
            data = json.loads(cuerpo or b"{}")
        except ValueError:
            data = {}
        for a in data.get("alerts", []):
            et = a.get("labels", {})
            print(f"[{datetime.now():%H:%M:%S}] {a.get('status', '?').upper():8} "
                  f"{et.get('alertname', '')} · máquina={et.get('maquina', '-')} · "
                  f"{a.get('annotations', {}).get('summary', '')}", flush=True)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):  # silenciar el log HTTP por defecto
        pass


if __name__ == "__main__":
    print("Receptor de alertas escuchando en :8080", flush=True)
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
