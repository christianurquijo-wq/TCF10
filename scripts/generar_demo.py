"""
Genera los datos de DEMOSTRACIÓN de data/demo/ (sintéticos, sin personas reales).

    python scripts/generar_demo.py

Simula las 3 cohortes con la estructura que tendrá el Sheet real: C1 en curso cerca del cierre,
C2 recién iniciada y C3 por iniciar. Incluye a propósito un grupo con más de 30 activos y un docente
con 4 grupos simultáneos para que se vean las alertas del equipo.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(10)
SALIDA = Path(__file__).resolve().parent.parent / "data" / "demo"
HOY = pd.Timestamp("2026-11-13")

COHORTES = [
    # cohorte, inicio, fin, personas, población
    ("Cohorte 1", "2026-09-21", "2026-11-30", 870, "Cerrada"),
    ("Cohorte 2", "2026-11-03", "2027-01-30", 900, "Mixta"),
    ("Cohorte 3", "2027-02-15", "2027-04-30", 829, "Mixta"),
]
PERFILES = ["Oficinista General", "Auxiliar Informativo"]
NIVELES = ["Básico", "Intermedio", "Avanzado"]
FRANJAS = ["Mañana", "Tarde", "Noche"]


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    filas, avance, cid = [], [], 100_000
    docente_n = 0
    for coh, ini, fin, n, pob in COHORTES:
        ini, fin = pd.Timestamp(ini), pd.Timestamp(fin)
        avance_cal = float(np.clip((HOY - ini).days / (fin - ini).days, 0, 1))
        grupo_n = 0
        restantes = n
        while restantes > 0:
            tam = min(restantes, int(rng.integers(26, 31)))
            grupo_n += 1
            if coh == "Cohorte 1" and grupo_n == 3:
                tam = 36  # demo: grupo por encima de 30
            if (grupo_n - 1) % 3 == 0:
                docente_n += 1
            docente = f"Docente {docente_n:02d}"
            if coh == "Cohorte 2" and grupo_n in (4, 5, 6, 7):
                docente = "Docente 40"  # demo: 4 grupos simultáneos
            perfil = PERFILES[grupo_n % 2]
            nivel = NIVELES[(grupo_n // 2) % 3]
            for _ in range(tam):
                cid += 1
                poblacion = pob if pob != "Mixta" else ("Abierta" if rng.random() < 0.45 else "Cerrada")
                enrolado = HOY >= ini - pd.Timedelta(days=10) and rng.random() < 0.985
                perfil_alumno = rng.choice(["constante", "medio", "flojo", "inactivo"], p=[0.55, 0.22, 0.13, 0.10])
                retiro = enrolado and avance_cal > 0.2 and rng.random() < 0.06
                factor = {"constante": rng.uniform(0.85, 1.25), "medio": rng.uniform(0.6, 0.9),
                          "flojo": rng.uniform(0.3, 0.6), "inactivo": rng.uniform(0.0, 0.3)}[perfil_alumno]
                esperado = 90 * avance_cal
                total = max(0.0, esperado * factor) if enrolado else 0.0
                sinc = min(31.5, total * rng.uniform(0.30, 0.42))
                asinc = max(0.0, total - sinc)
                dias_inactivo = {"constante": rng.integers(0, 4), "medio": rng.integers(2, 9),
                                 "flojo": rng.integers(5, 16), "inactivo": rng.integers(12, 40)}[perfil_alumno]
                ultima = (HOY - pd.Timedelta(days=int(dias_inactivo))) if (enrolado and HOY > ini) else None
                if ultima is not None and ultima < ini:
                    ultima = ini
                filas.append({
                    "ID SIS": cid, "Documento": str(1_000_000_000 + cid), "Nombre": f"Beneficiario {cid}",
                    "Cohorte": coh, "Población": poblacion, "Perfil": perfil, "Nivel": nivel,
                    "Grupo": f"{coh[-1]}-{perfil[:3].upper()}-{grupo_n:02d}", "Docente": docente,
                    "Gestor": f"Gestor {docente[-2:]}", "Franja": FRANJAS[grupo_n % 3],
                    "Enrolado": "SI" if enrolado else "",
                    "Estado": "Retirado" if retiro else ("Activo" if enrolado and HOY >= ini else "Enrolado"),
                    "Situación laboral inicio": (rng.choice(["Desempleado", "No formal", "Formal"], p=[0.55, 0.3, 0.15])
                                                 if poblacion == "Abierta" else ""),
                    "Certificado industria": "", "Formal t3": "",
                })
                if enrolado and HOY > ini:
                    avance.append({"id_sis": cid, "horas_sinc": round(sinc, 1), "horas_asinc": round(asinc, 1),
                                   "ultima_actividad": None if ultima is None else ultima.date().isoformat()})
            restantes -= tam
    pd.DataFrame(filas).to_csv(SALIDA / "beneficiarios.csv", index=False)
    pd.DataFrame(avance).to_csv(SALIDA / "avance.csv", index=False)
    pd.DataFrame([{"Cohorte": c, "Fecha inicio": i, "Fecha fin": f} for c, i, f, _, _ in COHORTES]).to_csv(
        SALIDA / "cohortes.csv", index=False)
    print(f"Demo: {len(filas)} beneficiarios, {len(avance)} con avance → {SALIDA}")


if __name__ == "__main__":
    main()
