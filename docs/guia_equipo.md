# Guía del equipo: commits, PDF y sustentación

## Historial de commits: los dos integrantes deben aparecer

Cada persona configura su identidad **en su propio equipo** (`git config user.name` / `user.email` con el correo de su cuenta de GitHub) y sube sus propios commits. Ejemplo de reparto con mensajes descriptivos:

| # | Quién | Mensaje sugerido | Archivos |
|---|---|---|---|
| 1 | Integrante 1 | `chore: estructura del repositorio, .gitignore y .env.example` | raíz |
| 2 | Integrante 2 | `docs: stakeholders, preguntas de negocio y diagnóstico de la fuente` | docs/01, 02 |
| 3 | Integrante 1 | `feat(sql): DDL del modelo estrella, índices y vistas de OEE` | sql/ddl |
| 4 | Integrante 1 | `feat(etl): extracción y reglas de calidad R01-R20` | etl/ |
| 5 | Integrante 2 | `feat(etl): conciliación de totales y diccionario de datos` | etl/src/etl/conciliacion.py, diccionario.py, docs/05, 06 |
| 6 | Integrante 2 | `docs: catálogo de indicadores y modelo dimensional` | docs/03, 04 |
| 7 | Integrante 1 | `feat(sql): consultas analíticas con funciones de ventana` | sql/consultas |
| 8 | Integrante 2 | `feat(grafana): provisioning, tablero y regla de alerta` | grafana/ |
| 9 | Integrante 1 | `feat(sim): simulador hora a hora y receptor de alertas` | simulador/ |
| 10 | Integrante 2 | `feat(docker): docker-compose con healthchecks y roles` | docker-compose.yml, db/ |
| 11 | Ambos | `feat(powerbi): proyecto PBIP con modelo y medidas` | powerbi/ |
| 12 | Ambos | `docs: arquitectura, seguridad, hallazgos y README` | docs/07, 08, README |

Conviene trabajar en ramas (`feature/etl`, `feature/grafana`…) y unirlas con *pull requests* revisados por el otro integrante: así queda evidencia de colaboración.

## Checklist del PDF `BI_ProyectoFinal_Apellido1_Apellido2.pdf`

- [ ] Portada: nombres de los integrantes, curso, docente, fecha y **enlace al repositorio**
- [ ] Secciones 1 a 8 de `docs/` (se pueden copiar casi tal cual)
- [ ] Capturas: DBeaver (esquemas y diagrama ER que genera DBeaver), salida del ETL, `audit.conciliacion`, las páginas de Power BI y Grafana (estado normal y con la alerta en *Firing*), `docker compose ps`
- [ ] Diagrama de arquitectura (`docs/img/arquitectura.png`)

## Antes de la sustentación

```bash
docker compose down -v && docker compose up -d --build    # demostrar que levanta desde cero
```

Ensayar en vivo:
1. DBeaver: `SELECT * FROM audit.conciliacion;` y una consulta con funciones de ventana (Q3, Pareto).
2. Power BI: actualizar, navegar por las páginas, hacer drill-down en la jerarquía de causas.
3. Grafana: filtrar por máquina y turno; `forzar_falla.py`, ver la alerta pasar a *Firing* y la notificación en `docker compose logs alertas`.

Cambios que el docente puede pedir en vivo:
- **Nueva medida DAX**: OEE del trimestre anterior → `CALCULATE([OEE], DATEADD(dim_fecha[fecha], -1, QUARTER))`.
- **Nuevo panel en Grafana**: como el tablero es de solo lectura (aprovisionado), se puede *Save as* una copia y agregar el panel, o editar el JSON del repositorio (Grafana lo recarga en 30 s).
- **Cambiar una consulta**: por ejemplo, la alerta en `grafana/provisioning/alerting/alertas.yaml` (pasar a un umbral fijo con `AVG(r.oee)` y `params: [0.6]`, o usar el P10 en `dw.v_umbral_alerta_oee`) y luego `docker compose restart grafana`.
- **Cambiar una regla de negocio**: reclasificar un código en `etl/config/clasificacion_codigos.csv` y luego `docker compose run --rm etl`.
