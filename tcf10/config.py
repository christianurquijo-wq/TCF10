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
HORAS_SINCRONICAS = 31.5                            # 35 %: Sincrónico (asistencia), solo docentes
HORAS_ASINCRONICAS = 58.5                           # 65 %: Asincrónico (contenidos), plataforma + gestores
ETQ_SINC = "Sincrónico (asistencia)"                # nombres de las modalidades (cuadro Kuepa EduTech, nov-2026)
ETQ_ASINC = "Asincrónico (contenidos)"
UMBRAL_CULMINACION = 0.70                           # culmina con >= 70 % de las 90 h
HORAS_CULMINACION = HORAS_TOTALES * UMBRAL_CULMINACION  # 63 h
USUARIOS_PRUEBA = (3172, 2980)  # incremental de cuentas de prueba del SIS (se excluyen de todo)
HORAS_POR_SESION = 4.0  # horas sincrónicas que acredita cada sesión asistida (confirmado nov-2026)
DIAS_SIN_PLATAFORMA = 7  # caso crítico: 0 h en plataforma (con el grupo iniciado hace 7+ días) o 7+ días sin ingresar
# Tipificación de la ruta para llegar al 70 % (63 h) con la plataforma al 100 % (58,5 h): las clases que faltan.
TIPOS_RUTA = ["No alcanza", "2 clases + plataforma", "1 clase + plataforma", "Solo plataforma", "Ya aprobó"]

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
# El SIS guarda la hora de inicio de las sesiones (session_start_date) 5 horas atrás de la hora real de clase
# (confirmado nov-2026): hora real = hora de BigQuery + 5. Solo afecta la franja de cada grupo.
DESFASE_HORA_SIS = 5

# ------------------------------------------------------------------ feedbacks
# Componentes «Feedback 1» … «Feedback 8» de VTD10_student_progress_detail (is_completed = TRUE). Meta: un Feedback
# por clase dictada al grupo (las clases de días anteriores; la de hoy aún no cuenta), hasta 8.
FEEDBACKS_TOTAL = 8
FEEDBACK_ATRASO_CRITICO = 2   # pendientes a partir de los cuales el estudiante pasa a «caso crítico»
ESTADOS_FEEDBACK = ["3 o más pendientes", "2 pendientes", "1 pendiente", "Al día", "Aún no aplica"]
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

# ------------------------------------------------------------------ estados del participante (cuadro Kuepa, nov-2026)
# ESTADO FORMACIÓN (grupo en curso, sin llegar aún al 70 %): según el ICP (ver LINEA_BASE). Mínimo >= y máximo <.
EN_FORMACION, EN_SEGUIMIENTO = "En Formación", "En Seguimiento"
RIESGO_BAJO, RIESGO_ALTO, INACTIVO = "Riesgo Deserción Bajo", "Riesgo Deserción Alto", "Matriculado Inactivo"
ESTADOS_FORMACION = [  # (estado, ICP mínimo)
    (EN_FORMACION, 0.75), (EN_SEGUIMIENTO, 0.60), (RIESGO_BAJO, 0.40), (RIESGO_ALTO, 0.10), (INACTIVO, 0.0)]
EN_CURSO = [e for e, _ in ESTADOS_FORMACION]
# ESTADO FINAL: Aprobado apenas supera el 70 % (63 h válidas); No aprobado / Abandono al cerrar su grupo.
APROBADO, NO_APROBADO, ABANDONO = "Aprobado Operador", "No Aprobado", "Abandono de Formación"
ESTADOS_FINALES = [APROBADO, NO_APROBADO, ABANDONO]
POR_INICIAR, NO_FORMALIZADO = "Por iniciar", "No formalizado"
ORDEN_ESTADOS = EN_CURSO + ESTADOS_FINALES + [POR_INICIAR, NO_FORMALIZADO]
CONCEPTO_FINAL = {APROBADO: "Supera el 70 %", NO_APROBADO: "No supera el 70 %",
                  ABANDONO: "Voluntaria o no realiza la formación"}


# ------------------------------------------------------------------ ICP (Índice de Cumplimiento del Plan)
# Hoja «Líneas Base - Consolidada» de la DB Formación TCF10: % del curso (horas planeadas acumuladas ÷ 90 h) que el
# plan cubre al terminar cada semana 1…8, por curso y nivel. Sale de «Líneas Base - Detalle» (cada sesión sincrónica
# y cada recurso asincrónico con su semana y duración; 31,5 + 58,5 h por curso y nivel). Verificado nov-2026.
# ICP = (horas válidas ÷ 90 h) ÷ línea base de la semana en curso del grupo (interpolada día a día).
LINEA_BASE = {
    ("Auxiliar", "Básico"): [0.23449, 0.43770, 0.68381, 0.89805, 0.93920, 0.96627, 0.97556, 1.0],
    ("Auxiliar", "Intermedio"): [0.18750, 0.40696, 0.62331, 0.84469, 0.88821, 0.92413, 0.95987, 1.0],
    ("Auxiliar", "Avanzado"): [0.21139, 0.40759, 0.61250, 0.81833, 0.85667, 0.92426, 0.96519, 1.0],
    ("Marketing", "Básico"): [0.20847, 0.43024, 0.64478, 0.87626, 0.91131, 0.94372, 0.97163, 1.0],
    ("Marketing", "Intermedio"): [0.20792, 0.42321, 0.62459, 0.86902, 0.89867, 0.92675, 0.96309, 1.0],
    ("Marketing", "Avanzado"): [0.20183, 0.39406, 0.62643, 0.82987, 0.88232, 0.90861, 0.94677, 1.0],
}
SEMANAS_PLAN = 8
# Sin curso o nivel reconocible: promedio de las 6 curvas.
LINEA_BASE_PROMEDIO = [sum(v[i] for v in LINEA_BASE.values()) / len(LINEA_BASE) for i in range(SEMANAS_PLAN)]


def _curso_plan(perfil: str) -> str | None:
    t = str(perfil or "").lower()
    if "auxiliar" in t:
        return "Auxiliar"
    if "marketing" in t or "oficinista" in t:
        return "Marketing"
    return None


def _nivel_plan(nivel: str) -> str | None:
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFKD", str(nivel or "")) if not unicodedata.combining(c)).lower()
    return {"basico": "Básico", "intermedio": "Intermedio", "avanzado": "Avanzado"}.get(t.strip())


def linea_base(perfil: str, nivel: str, dias: float) -> float:
    """Fracción del curso (0-1) que el plan espera cubierta a `dias` días del inicio del grupo. Entre semanas se
    interpola día a día: día 0 = 0 %, día 7 = semana 1, …, día 56 en adelante = 100 %."""
    if dias is None or dias != dias or dias <= 0:
        return 0.0
    curva = LINEA_BASE.get((_curso_plan(perfil), _nivel_plan(nivel)), LINEA_BASE_PROMEDIO)
    semana = min(float(dias) / 7.0, SEMANAS_PLAN)
    k = int(semana)
    previo = curva[k - 1] if k >= 1 else 0.0
    if k >= SEMANAS_PLAN:
        return curva[-1]
    return previo + (curva[k] - previo) * (semana - k)


def estado_por_avance(pct: float) -> str:
    """ICP → estado de formación (75 / 60 / 40 / 10 %)."""
    for estado, minimo in ESTADOS_FORMACION:
        if pct >= minimo - 1e-9:
            return estado
    return INACTIVO


def rango_estado(estado: str) -> str:
    """«60 % a < 75 %» para mostrar en tablas y leyendas."""
    for i, (e, minimo) in enumerate(ESTADOS_FORMACION):
        if e == estado:
            maximo = ESTADOS_FORMACION[i - 1][1] if i else 1.0
            return f"{minimo * 100:.0f} % a < {maximo * 100:.0f} %" if i else f"≥ {minimo * 100:.0f} %"
    return CONCEPTO_FINAL.get(estado, "")
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
# Probabilidad de aprobar según el estado de formación, para la proyección de pagos (supuesto ajustable).
PROB_CULMINAR = {EN_FORMACION: 0.90, EN_SEGUIMIENTO: 0.75, RIESGO_BAJO: 0.50, RIESGO_ALTO: 0.20, INACTIVO: 0.05}

ESTADOS_ACTIVOS = {"Enrolado", "Activo"}
ESTADOS = ["Enrolado", "Activo", "Culminado", "Retirado"]
