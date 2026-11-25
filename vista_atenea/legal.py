"""Textos legales de la app (aviso de privacidad, términos de uso, cookies y terceros, derechos y eliminación,
créditos y licencias). nov-2026.

BORRADOR PARA VALIDACIÓN JURÍDICA de Atenea y Kuepa: los textos se apoyan en la Ley 1581 de 2012, el Decreto 1377
de 2013 (compilado en el Decreto 1074 de 2015) y la Política de Tratamiento y Protección de Datos Personales de
Atenea (PO3_DE, versión 2, adoptada por la Resolución DG-062 de 2025). Al cambiar los Términos, sube VERSION_TERMINOS:
el registro de accesos guarda qué versión aceptó cada usuario.
"""
from __future__ import annotations

import streamlit as st

VERSION_TERMINOS = "v2 · 2026-11-25 (borrador)"
BORRADOR = True  # False cuando jurídica apruebe los textos (quita el aviso de borrador)

ATENEA = {
    "nombre": "Agencia Distrital para la Educación Superior, la Ciencia y la Tecnología «Atenea»",
    "nit": "901.508.361-4",
    "domicilio": "Bogotá D.C., Colombia",
    "telefono": "(601) 6660006",
    "web": "https://www.agenciaatenea.gov.co",
    "correo": "atencionalciudadano@agenciaatenea.gov.co",
    "pqr": "https://siga.agenciaatenea.gov.co//WebSigaPQR/#!/radicacionPQR",
    "politica": "app/static/docs/Atenea_PO3_DE_Politica_Tratamiento_Datos_V2.pdf",
}
KUEPA = {
    "nombre": "Kuepa EduTech",
    "correo": "contactotalentocapital@kuepa.com",
    "whatsapp": "+1 (555) 980-3272",
}
CONTRATO = "ATENEA-497-2026"
PROGRAMA = "Talento Capital Formación 10"


def _wa() -> str:
    digitos = "".join(c for c in KUEPA["whatsapp"] if c.isdigit())
    return f"https://wa.me/{digitos}"


def canales_md() -> str:
    return (f"- **Kuepa EduTech (operador):** correo [{KUEPA['correo']}](mailto:{KUEPA['correo']}) · "
            f"WhatsApp [{KUEPA['whatsapp']}]({_wa()})\n"
            f"- **Atenea (responsable del tratamiento):** ventanilla única de PQR [{ATENEA['pqr']}]({ATENEA['pqr']}) · "
            f"[{ATENEA['correo']}](mailto:{ATENEA['correo']}) · teléfono {ATENEA['telefono']}")


def _aviso_borrador() -> None:
    if BORRADOR:
        st.info("Borrador para validación jurídica de Atenea y Kuepa. Versión " + VERSION_TERMINOS + ".",
                icon=":material/gavel:")


# ------------------------------------------------------------------ textos
AVISO_CORTO = (
    "Esta herramienta muestra datos personales de los participantes de " + PROGRAMA + " (nombre, documento y "
    "avance académico) para el seguimiento del contrato " + CONTRATO + ". **Atenea** es la responsable del "
    "tratamiento y **Kuepa EduTech** lo realiza como encargado. Al ingresar se registran tu usuario, la fecha y hora "
    "y las descargas que hagas.")


def aviso_privacidad_md() -> str:
    return f"""
### Aviso de privacidad

**Responsable del tratamiento.** {ATENEA['nombre']}, NIT {ATENEA['nit']}, domicilio en {ATENEA['domicilio']},
teléfono {ATENEA['telefono']}, [{ATENEA['web']}]({ATENEA['web']}).

**Encargado del tratamiento.** {KUEPA['nombre']}, operador de {PROGRAMA} en virtud del contrato {CONTRATO}, que
trata los datos por cuenta de Atenea y siguiendo sus instrucciones.

**Para qué se usa esta herramienta.** Seguimiento de la ejecución del contrato: asistencia, progreso académico,
estado de formación y cumplimiento de metas de los participantes. No se usa para fines comerciales ni publicitarios.

**Datos de los participantes que se muestran.** Nombre, tipo y número de documento, cohorte, grupo, jornada, programa
y nivel, estado en el programa, asistencia, horas de formación, interacciones en la plataforma y fecha de última
actividad. Provienen de la base de formalización del programa y de la plataforma académica (SIS) del operador. No se
muestran datos sensibles. La página «Participantes» permite además descargar las vistas del SIS en crudo (CSV), que incluyen
los datos de contacto y el detalle de actividad registrados en la plataforma; cada descarga queda registrada.

**Datos de quienes usan la herramienta.** Usuario o correo con el que ingresas, fecha y hora de ingreso y salida,
descargas realizadas y la versión de los términos aceptada. Se usan solo para seguridad y auditoría del acceso. No se
guardan contraseñas (solo una huella cifrada), direcciones IP ni datos de navegación.

**Derechos de los titulares.** Conocer, actualizar, rectificar y suprimir sus datos, solicitar prueba de la
autorización, ser informados del uso de sus datos, revocar la autorización cuando no exista un deber legal o
contractual de conservarlos y presentar quejas ante la Superintendencia de Industria y Comercio (art. 8, Ley 1581 de
2012). Las consultas se responden en máximo 10 días hábiles y los reclamos en máximo 15 días hábiles, prorrogables en
los términos de la política de Atenea.

**Canales.**
{canales_md()}

**Política completa.** [Política de Tratamiento y Protección de Datos Personales de Atenea (PO3_DE, v2,
Resolución DG-062 de 2025)]({ATENEA['politica']}).
"""


def terminos_md() -> str:
    return f"""
### Términos de uso

1. **Quién puede usarla.** Solo personas autorizadas por Atenea o por Kuepa EduTech para el seguimiento del contrato
   {CONTRATO}. Las credenciales son personales e intransferibles.
2. **Uso permitido.** Consultar el avance del programa y de sus participantes para fines de supervisión, interventoría,
   gestión académica y rendición de cuentas del contrato. Cualquier otro uso está prohibido.
3. **Confidencialidad.** La información es reservada. No la compartas, publiques ni reenvíes a terceros no
   autorizados, ni la uses para contactar a los participantes por fuera de los canales del programa.
4. **Descargas.** Los archivos descargados llevan tu usuario y la fecha. Guárdalos solo en equipos y cuentas
   institucionales, elimínalos cuando ya no los necesites y no los compartas por canales públicos.
5. **Registro de actividad.** Se registran los ingresos, salidas, intentos fallidos y descargas para auditoría. La sesión
   se cierra tras 30 minutos sin actividad y el usuario se bloquea 15 minutos tras 5 intentos fallidos de contraseña.
6. **Exactitud de los datos.** Las cifras se calculan con la información disponible en la fecha de corte indicada en
   cada página; pueden cambiar cuando las fuentes se actualizan. La sección «Cómo se calcula» explica cada indicador.
7. **Incidentes.** Si sospechas un acceso indebido o pierdes un archivo descargado, avísalo de inmediato a
   [{KUEPA['correo']}](mailto:{KUEPA['correo']}).
8. **Suspensión del acceso.** Kuepa EduTech o Atenea pueden suspender el acceso de quien incumpla estos términos y
   el acceso termina al finalizar el contrato.
9. **Normas aplicables.** Ley 1581 de 2012, Decreto 1074 de 2015, la Política de Tratamiento de Datos de Atenea y las
   cláusulas de confidencialidad y protección de datos del contrato {CONTRATO}.
"""


TERCEROS = [
    # (servicio, para qué, qué datos recibe, dónde)
    ("Streamlit Community Cloud (Snowflake Inc.)", "Alojamiento de la aplicación",
     "Los datos que muestra la app mientras se usa; cookies técnicas de sesión", "Estados Unidos"),
    ("Google Cloud — BigQuery y Google Sheets", "Fuentes de datos (plataforma académica, base de formalización) y "
     "registro de accesos", "Datos de los participantes; registro de accesos", "Estados Unidos / multirregión"),
    ("Google (inicio de sesión con Google)", "Autenticación de cuentas institucionales",
     "Correo y nombre de la cuenta que inicia sesión", "Estados Unidos"),
    ("Looker Studio (Google)", "Tablero complementario, solo si el usuario pulsa «Cargar tablero»",
     "Cookies y datos de navegación propios de Google", "Estados Unidos"),
]
NO_USA = ("No se usan herramientas de analítica, publicidad, píxeles de seguimiento ni fuentes externas: la "
          "tipografía se sirve desde la propia aplicación y la telemetría de Streamlit está desactivada.")


def cookies_md() -> str:
    return """
### Cookies y servicios de terceros

**Cookies que usa la herramienta.** Solo cookies técnicas, necesarias para que funcione y no requieren
consentimiento:

| Cookie | Para qué | Duración |
|---|---|---|
| `_streamlit_xsrf` | Protección contra falsificación de solicitudes | Sesión |
| `_streamlit_user` | Mantener el inicio de sesión con Google (cifrada) | Hasta cerrar sesión o 30 días |
| Cookies de la plataforma de alojamiento | Funcionamiento y seguridad de Streamlit Community Cloud | Las define el proveedor |

**Contenido de terceros.** La página «Tablero Looker» no se carga hasta que pulsas «Cargar tablero». Al hacerlo, tu
navegador se conecta a Google, que puede usar sus propias cookies según su política de privacidad.

**Transferencia internacional.** La herramienta y sus fuentes se alojan en servicios en la nube ubicados fuera de
Colombia (ver tabla). La transmisión de datos a estos proveedores se rige por el contrato y por la política de Atenea
(capítulo 7).
"""


def eliminacion_md() -> str:
    return f"""
### Conservación y eliminación de datos

- **La herramienta no guarda datos de los participantes.** Los consulta en las fuentes del programa y los mantiene en
  memoria unos minutos para responder más rápido; al cerrar la sesión o reiniciar la app se borran.
- **Corrección o supresión de datos de un participante.** Se tramita como reclamo ante Atenea (responsable) o ante
  Kuepa EduTech (encargado), por los canales de abajo. Kuepa corrige la fuente y el cambio se ve en la siguiente
  actualización.
- **Registro de accesos.** Se conserva durante la ejecución del contrato y el tiempo que exijan las Tablas de
  Retención Documental de Atenea; después se elimina.
- **Al terminar el contrato,** Kuepa EduTech: (1) desactiva todos los usuarios y el inicio con Google; (2) elimina la
  aplicación y sus secretos; (3) entrega a Atenea o elimina, según instrucción escrita de Atenea, las copias de datos
  en sus sistemas (BigQuery, Google Sheets, Drive) y (4) deja constancia escrita de la eliminación.
- **Archivos descargados.** Son responsabilidad de quien los descarga (Términos de uso, punto 4).

**Canales.**
{canales_md()}
"""


CREDITOS = [
    ("Logos de la Agencia Atenea", "Propiedad de Atenea; uso autorizado para la ejecución del contrato "
     + CONTRATO + " según su manual de marca"),
    ("Logo de Kuepa EduTech", "Propiedad de Kuepa EduTech"),
    ("Tipografía Barlow Semi Condensed", "SIL Open Font License 1.1 (Jeremy Tribby) · servida desde la app"),
    ("Íconos Material Symbols", "Google · Apache License 2.0 (incluidos en Streamlit)"),
    ("Streamlit, Plotly, pandas", "Apache 2.0 · MIT · BSD-3 (software de código abierto)"),
]


# ------------------------------------------------------------------ vistas
def _tabla_terceros() -> None:
    import pandas as pd
    st.dataframe(pd.DataFrame(TERCEROS, columns=["Servicio", "Para qué", "Qué datos recibe", "Ubicación"]),
                 hide_index=True, width="stretch")
    st.caption(NO_USA)


def mostrar(seccion: str) -> None:
    """Dibuja una sección: 'privacidad', 'terminos', 'cookies', 'eliminacion' o 'creditos'."""
    _aviso_borrador()
    if seccion == "privacidad":
        st.markdown(aviso_privacidad_md())
    elif seccion == "terminos":
        st.markdown(terminos_md())
    elif seccion == "cookies":
        st.markdown(cookies_md())
        _tabla_terceros()
    elif seccion == "eliminacion":
        st.markdown(eliminacion_md())
    elif seccion == "creditos":
        import pandas as pd
        st.markdown("### Créditos y licencias")
        st.dataframe(pd.DataFrame(CREDITOS, columns=["Recurso", "Licencia o titular"]), hide_index=True,
                     width="stretch")


@st.dialog("Términos y privacidad", width="large")
def dialogo() -> None:
    t = st.tabs(["Aviso de privacidad", "Términos de uso", "Cookies y terceros", "Eliminación de datos"])
    for tab, sec in zip(t, ["privacidad", "terminos", "cookies", "eliminacion"]):
        with tab:
            mostrar(sec)
