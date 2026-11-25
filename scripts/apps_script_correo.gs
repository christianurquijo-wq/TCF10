/**
 * Cartero de códigos de la app TCF10 (Atenea · Kuepa EduTech) — nov-2026.
 *
 * Recibe {secreto, para, nombre, codigo, minutos} por POST desde la app de Streamlit y envía el código de 6 dígitos
 * para crear o recuperar contraseña. No guarda nada: solo envía el correo.
 *
 * Instalación (una vez, con la cuenta remitente de Kuepa, p. ej. contactotalentocapital@kuepa.com):
 *  1. script.google.com → Nuevo proyecto → pega este archivo (Código.gs) y guarda.
 *  2. Configuración del proyecto (engranaje) → Propiedades del script → Agregar:
 *       SECRETO = una clave larga aleatoria (la misma que [atenea] correo_secreto en los Secrets de Streamlit).
 *  3. Implementar → Nueva implementación → Tipo: Aplicación web.
 *       Ejecutar como: Yo (la cuenta remitente) · Quién tiene acceso: Cualquier usuario.
 *     Autoriza los permisos (enviar correo como tú) y copia la URL que termina en /exec
 *     → [atenea] correo_url en los Secrets.
 *  4. Prueba: en la app, «Crear o recuperar contraseña» con un correo autorizado.
 *  «Cualquier usuario» es necesario porque la app llama sin sesión de Google; la clave SECRETO es la que impide
 *  que un tercero use el cartero. Si cambias el código, publica una nueva versión de la misma implementación.
 */
function doPost(e) {
  try {
    var datos = JSON.parse(e.postData.contents || '{}');
    var secreto = PropertiesService.getScriptProperties().getProperty('SECRETO');
    if (!secreto || datos.secreto !== secreto) {
      return respuesta_({ok: false, error: 'no autorizado'});
    }
    var para = String(datos.para || '').trim();
    var codigo = String(datos.codigo || '').replace(/\D/g, '');
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(para) || codigo.length !== 6) {
      return respuesta_({ok: false, error: 'datos inválidos'});
    }
    var nombre = String(datos.nombre || '').trim();
    var minutos = Number(datos.minutos) || 15;
    var saludo = nombre ? 'Hola, ' + nombre + ':' : 'Hola:';
    var texto = saludo + '\n\nTu código para crear o recuperar la contraseña del tablero Talento Capital · ' +
        'Formación 10 es: ' + codigo + '\n\nVence en ' + minutos + ' minutos y sirve una sola vez. ' +
        'Si no lo pediste, ignora este mensaje.\n\nKuepa EduTech · Operador del programa';
    var html = '<div style="font-family:Arial,sans-serif;color:#141439;font-size:15px">' +
        '<p>' + saludo + '</p>' +
        '<p>Tu código para crear o recuperar la contraseña del tablero <b>Talento Capital · Formación 10</b> es:</p>' +
        '<p style="font-size:28px;font-weight:bold;letter-spacing:6px">' + codigo + '</p>' +
        '<p>Vence en ' + minutos + ' minutos y sirve una sola vez. Si no lo pediste, ignora este mensaje.</p>' +
        '<p style="color:#4A4F78;font-size:13px">Kuepa EduTech · Operador del programa</p></div>';
    MailApp.sendEmail({
      to: para,
      subject: 'Código de verificación · Talento Capital F10',
      body: texto,
      htmlBody: html,
      name: 'Talento Capital F10 · Kuepa'
    });
    return respuesta_({ok: true});
  } catch (err) {
    return respuesta_({ok: false, error: String(err)});
  }
}

function respuesta_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
