# Revisión · EN: botón principal al formulario inglés · v1

Base: origin/main 11d2685 · Versión: rama claude/en-boton-formulario, commit 9a5dac5fdac2ec1f821908ef1a834f928ebe5816 · diff MD5 bbf75f9ab604496172b8cdf8b7c77e99 · 13 ficheros, 13+/13-.

## Diagnóstico del circuito de contacto (repositorio main 11d2685; sin enviar nada)
1. Formularios ES, EN, FR, DE: POST fetch no-cors al mismo Apps Script; al resolverse, redirigen a gracias / en-thank-you / fr-merci / de-danke. Con no-cors la respuesta es opaca: el redireccionamiento solo prueba que la petición salió, no que el backend la aceptó. Si fetch falla o tarda 20 s, sale el aviso «We could not confirm…», el texto se queda en el formulario y se ofrecen WhatsApp y correo.
2. Las cuatro páginas de gracias ya NO prometen recepción: «Esta pantalla no es un acuse de recepción» / «This page is not an acknowledgement of receipt» / «Diese Seite ist keine Eingangsbestätigung» / «Cette page ne constitue pas un accusé de réception», con la vía para confirmar por WhatsApp o correo. Fricción ya resuelta: no se toca.
3. El código del Apps Script no está en el repositorio: su aceptación no se puede auditar desde aquí. Hacerla verificable exigiría cambiar el backend para responder con CORS y leer la respuesta: fuera del repositorio, y probarlo enviaría correo. No se propone.
4. Hueco real: 30 páginas inglesas indexables no enlazan al formulario inglés; su llamada principal es mailto: (en muchos equipos sin cliente de correo no abre nada) o WhatsApp. El formulario es la única vía con atribución («Viene de», «Nos conoció por») y la consulta real de hoy entró por él. Las guías inglesas al formulario con ?pagina= ya estaban anotadas como pendientes en ESTADO-VIVO («Siguiente», punto c).

## La mejora
En 13 guías inglesas fiscales para extranjeros sin enlace al formulario, el primer botón de llamada (el del encabezado; en dutch-pension, form-721 y accounting-tax-service, el de la sección final, que es el único) pasa de mailto: a en-contact.html?pagina=<fichero>. Si el texto decía «by email» o «Email us about…», pasa a «Request a quote» (el mismo texto que ya usan herencia y venta EN); «Ask about my project / case / situation» se quedan. Se conserva el icono cuando lo había.
No cambia: cabecera (topbar), resto de botones de correo y WhatsApp, título, meta, H1, entradillas, FAQ, JSON-LD, fechas (solo contacto: decisión del 17/11) ni diseño (mismas clases). Sin teléfono añadido.
Fuera, a propósito: las páginas en cerrojo del PR #123 (beckham EN, buying-property-spain-foreigner, french y german pension, leaving-spain, tax-representative), las de WhatsApp como llamada principal (italian-pension, gift-of-money, regularising), las de extranjería (NIE, arraigo, nacionalidad, reagrupación, residencias) y el hub en-tramites.

## Puntos para el paso 2
- Cada ?pagina= coincide con su fichero y pasa el filtro ^[a-z0-9-]+\.html$ de en-contact.html.
- Ningún texto prometido por el botón choca con lo que hace (formulario de consulta, respuesta por escrito).
- En accounting-tax-service la entradilla final dice «Email your activity…»: el correo sigue visible justo debajo del botón. Decidid si es reparo.
- En form-721 el mailto llevaba asunto y cuerpo de plantilla; el formulario pide el caso en texto libre.
- Impacto en consultas: NO CALCULABLE; medible por «Viene de:» en los correos del formulario.

Ficheros: cambio.diff, HUELLAS.txt (blob, MD5, SHA-256 de la versión), PRUEBAS.txt, originales/ (main) y version/ (rama), como .html.txt.
