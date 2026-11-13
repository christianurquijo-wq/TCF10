# TCF10 · Tablero de seguimiento contractual

Talento Capital Formación 10 · Contrato ATENEA-497-2026 · Kuepa EduTech.
Streamlit + Google Sheet operativo + SIS Kuepa (BigQuery). Costo de infraestructura: $0 (Streamlit Community Cloud + sandbox/cuota gratuita de BigQuery).

## Páginas
| Página | Qué responde |
|---|---|
| Metas y pagos | Cuánto del contrato está asegurado, proyección del pago 2 (por culminado) y estado de los índices de enrolamiento, éxito y TML |
| Avance y riesgo | Horas válidas vs 63 h, riesgo alto/medio/bajo (Anexo 8) y lista priorizada para gestores |
| Cohortes y equipo | Enrolamiento, deserción y culminación por cohorte; topes de 30 activos/grupo, 3 grupos/docente, gestor y 3 franjas |
| Cómo se calcula | Fórmulas y supuestos (salen de `tcf10/config.py`) |

## Correr local
```bash
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
streamlit run app.py          # sin secrets arranca en MODO DEMO (datos sintéticos)
pytest -q
```

## Conectar datos reales
1. Google Sheet con dos pestañas (encabezados tolerantes a mayúsculas/tildes):
   - **BENEFICIARIOS**: id_sis, documento, nombre, cohorte, poblacion (Abierta/Cerrada), perfil, nivel, grupo, docente, gestor, franja, enrolado (SI/NO), estado (Entregado/Enrolado/Activo/Retirado/Culminó), lab_inicio (Desempleado/No formal/Formal), certificado (SI/NO), formal_t3 (SI/NO)
   - **COHORTES**: cohorte, fecha_inicio, fecha_fin, tipo
2. Compartir el Sheet (lector) con la cuenta de servicio y darle `BigQuery Data Viewer` + `Job User` sobre el dataset del SIS.
3. Copiar `.streamlit/secrets.toml.example` → secrets (local) o pegar en Streamlit Cloud › Settings › Secrets.
4. Validar `queries/avance_sis.sql` contra el dataset real y ajustar `horas_por_sesion`.

## Privacidad
La app es pública por enlace: **nunca** muestra nombre, documento, correo ni teléfono; solo ID SIS + iniciales.
`.gitignore` excluye secrets, llaves `.json` y cualquier dato real en `data/` (solo `data/demo/` es versionable).

## Parámetros del contrato
Todo en `tcf10/config.py` (cupos, valor, horas, metas, % de pagos, umbrales de riesgo). Cambiar ahí, no en las páginas.
