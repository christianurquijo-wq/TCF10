"""
Parámetros contractuales de Talento Capital Formación 10 (contrato ATENEA-497-2026, Kuepa EduTech).

Fuente: Especificaciones Técnicas V2, Anexo 5 (requisitos técnicos), Formato Factor 5 de Kuepa y
Matriz de Criterios TCF10 (nov-2026). Si el contrato firmado o la Adenda 4 cambian algún valor,
se ajusta AQUÍ y toda la app se recalcula: ninguna página debe tener cifras del contrato escritas
a mano.
"""
from __future__ import annotations

# ------------------------------------------------------------------ alcance y valor
CUPOS_CONTRATADOS = 2_599
COSTO_UNITARIO = 1_246_154                         # COP por cupo (oferta Kuepa)
VALOR_CONTRATO = CUPOS_CONTRATADOS * COSTO_UNITARIO  # 3.238.754.246
FIN_CONTRATO = "2027-07-30"

# ------------------------------------------------------------------ formación
HORAS_TOTALES = 90.0
HORAS_SINCRONICAS = 31.5                            # 35 %: solo docentes
HORAS_ASINCRONICAS = 58.5                           # 65 %: plataforma + gestores
UMBRAL_CULMINACION = 0.70                           # culmina con >= 70 % de las 90 h
HORAS_CULMINACION = HORAS_TOTALES * UMBRAL_CULMINACION  # 63 h
USUARIOS_PRUEBA = (3172, 2980)  # incremental de cuentas de prueba del SIS (se excluyen de todo)
HORAS_POR_SESION = 4.0  # horas sincrónicas que acredita cada sesión asistida (confirmado nov-2026)

PERFILES = {
    "Oficinista General": "Marketing digital, finanzas e IA (CUOC 41101)",
    "Auxiliar Informativo": "Servicio al cliente con enfoque en datos e IA generativa (CUOC 42251)",
}
NIVELES = ["Básico", "Intermedio", "Avanzado"]
POBLACIONES = ["Cerrada", "Abierta"]  # Cerrada = Jóvenes con Oportunidades (SDIS); Abierta = convocatoria Atenea

# ------------------------------------------------------------------ equipo
MAX_ACTIVOS_POR_GRUPO = 35          # máximo de activos por grupo (confirmado con Atenea)
MAX_GRUPOS_POR_DOCENTE = 3          # simultáneos, sin cruce de horario
MIN_GESTORES_POR_DOCENTE = 1
MIN_FRANJAS = 3
# Franjas oficiales del programa: (nombre, hora de inicio 0-24, etiqueta). Confirmado nov-2026.
FRANJAS = [("Mañana", 8, "8:00 a. m."), ("Tarde", 13, "1:00 p. m."), ("Noche", 17, "5:00 p. m.")]


def etiqueta_franja(nombre: str) -> str:
    """«Mañana» → «Mañana · 8:00 a. m.»; deja igual lo que no es una franja conocida (p. ej. «Sin dato»)."""
    base = str(nombre or "").split("·")[0].strip().capitalize()
    for n, _, hora in FRANJAS:
        if base == n:
            return f"{n} · {hora}"
    return str(nombre)


def orden_franja(etiqueta: str) -> tuple:
    """Llave para ordenar franjas en el orden del día (Mañana, Tarde, Noche) y lo demás al final."""
    base = str(etiqueta).split("·")[0].strip()
    return next((i for i, (n, _, _) in enumerate(FRANJAS) if n == base), len(FRANJAS)), str(etiqueta)


def franja_de_hora(h: float) -> str:
    """Franja oficial más cercana a la hora de inicio (8, 13 o 17 h)."""
    return min(FRANJAS, key=lambda f: abs(f[1] - h))[0]

# ------------------------------------------------------------------ pagos e índices (Factor 5)
# Cada índice es "todo o nada": si el alcanzado (redondeado a entero) es >= al ofertado, se paga.
PAGOS = {
    "enrolamiento": {
        "nombre": "Pago 1 · Enrolamiento",
        "pct_contrato": 0.03,
        "indice_ofertado": 1.00,
        "formula": "Enrolados de todas las cohortes ÷ cupos contratados "
                   "(o ÷ personas entregadas por Atenea, si fueron menos)",
    },
    "culminacion": {
        "nombre": "Pago 2 · Culminación",
        "pct_costo_unitario": 0.85,
        "formula": "85 % del costo unitario × personas que culminan (≥ 70 % de 90 h), por cohorte, "
                   "hasta el total de cupos",
    },
    "exito": {
        "nombre": "Pago 3 · Índice de éxito",
        "pct_contrato": 0.06,
        "indice_ofertado": 0.60,
        "formula": "Personas con certificación de industria ÷ personas que culminaron",
    },
    "tml": {
        "nombre": "Pago 4 · Tránsito al mercado laboral",
        "pct_contrato": 0.06,
        "indice_ofertado": 0.40,
        "formula": "Solo convocatoria abierta: formales en PILA en t3 ÷ culminaron y empezaron "
                   "desempleados o no formales",
    },
}
VALOR_POR_CULMINADO = PAGOS["culminacion"]["pct_costo_unitario"] * COSTO_UNITARIO  # 1.059.230,9

# ------------------------------------------------------------------ riesgo (Anexo 8)
# Se compara el avance real con el esperado a la fecha según el calendario de la cohorte.
# Valores iniciales propuestos: validar con Atenea y el coordinador académico.
RIESGO = {
    "alto": {"ritmo_menor_a": 0.50, "dias_sin_actividad": 14},
    "medio": {"ritmo_menor_a": 0.80, "dias_sin_actividad": 7},
}
# El ritmo solo se evalúa cuando ya se esperaban al menos estas horas (evita alertas falsas en la
# primera semana de una cohorte, cuando el esperado es casi cero).
RIESGO_MIN_ESPERADO_H = 9.0     # 10 % de la formación
RIESGO_GRACIA_DIAS = 7          # días desde el inicio antes de alertar por inactividad
# Primeras semanas: el ritmo de horas todavía no dice mucho, así que el riesgo se mide por asistencia.
RIESGO_FASE_INICIAL_DIAS = 14   # días desde el inicio del grupo en que manda la asistencia
RIESGO_MIN_SESIONES = 2         # sesiones registradas mínimas para juzgar la asistencia
RIESGO_ASISTENCIA_MEDIO = 0.5   # asistió a menos de la mitad de las sesiones registradas → medio
COHORTE_SEPARACION_DIAS = 21    # sin base de Atenea: grupos que inician con menos de 3 semanas de diferencia = misma cohorte
REGISTRO_GRACIA_HORAS = 24      # una sesión de las últimas 24 h sin asistencia se cuenta como «por registrar»
# Probabilidad de culminar según el nivel de riesgo, para la proyección de pagos (supuesto ajustable).
PROB_CULMINAR = {"Bajo": 0.90, "Medio": 0.60, "Alto": 0.20}

ESTADOS_ACTIVOS = {"Enrolado", "Activo"}
ESTADOS = ["Enrolado", "Activo", "Culminado", "Retirado"]
