(function () {
  'use strict';

  var campanaHistorica = 'extranjeros_es_historica';
  var recorridos = {
    'index.html': ['contacto.html', 'modelo210_venta_es_piloto', 'modelo210_alquiler_es_piloto', 'modelo210_anual_es_piloto'],
    'herencia-en-espana-heredero-no-residente.html': ['contacto.html', 'herencias_es_piloto'],
    'vender-inmueble-en-espana-no-residente.html': ['contacto.html', 'modelo210_venta_es_piloto'],
    'alquiler-vivienda-espana-no-residente.html': ['contacto.html', 'modelo210_alquiler_es_piloto'],
    'modelo-210-no-residentes.html': ['contacto.html', '210_es_piloto', 'modelo210_anual_es_piloto'],
    'selling-property-spain-non-resident.html': ['en-contact.html', 'venta_en_piloto'],
    'de-immobilie-spanien-verkaufen-ausland.html': ['de-kontakt.html', 'venta_de_piloto'],
    'fr-vendre-bien-immobilier-non-resident.html': ['fr-contact.html', 'venta_fr_piloto'],
    'spanish-gift-tax-return-service.html': ['en-contact.html', 'donacion_en_piloto'],
    'de-geldschenkung-ausland-spanien.html': ['de-kontakt.html', 'donacion_de_piloto', campanaHistorica],
    'fr-donation-argent-etranger.html': ['fr-contact.html', 'donacion_fr_piloto', campanaHistorica],
    'gift-of-money-from-abroad-spain.html': ['en-contact.html', campanaHistorica],
    'fr-modele-210-non-residents.html': ['fr-contact.html', campanaHistorica],
    'de-modelo-210-nichtansaessige.html': ['de-kontakt.html', campanaHistorica],
    'modelo-210-non-resident-tax-spain.html': ['en-contact.html', campanaHistorica, 'modelo210_property_en_piloto']
  };
  var acuses = {
    'index.html': 'gracias.html',
    'contacto.html': 'gracias.html',
    'en-contact.html': 'en-thank-you.html',
    'de-kontakt.html': 'de-danke.html',
    'fr-contact.html': 'fr-merci.html'
  };
  var textos = {
    es: ['Medición de anuncios', 'Si aceptas, usaremos cookies y, al recibir tu consulta, enviaremos a Google Ads el identificador del clic y una referencia técnica para medir el anuncio. Usamos los datos del formulario para atender tu consulta. Puedes enviarlo con cualquiera de las dos opciones.', 'Aceptar', 'Rechazar', 'Política de cookies', 'Opciones de medición', 'cookies.html'],
    en: ['Ad measurement', 'If you accept, we will use cookies and, when we receive your enquiry, send Google Ads the click ID and a technical reference to measure the ad. We use the details you enter to handle your enquiry. You can submit the form with either choice.', 'Accept', 'Reject', 'Cookie policy', 'Ad measurement settings', 'en-privacy.html#cookies'],
    de: ['Messung von Anzeigen', 'Wenn Sie zustimmen, verwenden wir Cookies. Sobald Ihre Anfrage eingeht, senden wir die Klick-ID und eine technische Referenz zur Anzeigenmessung an Google Ads. Ihre Angaben im Formular dienen der Bearbeitung Ihrer Anfrage. Sie können das Formular mit beiden Einstellungen absenden.', 'Akzeptieren', 'Ablehnen', 'Cookie-Hinweise', 'Einstellungen zur Anzeigenmessung', 'de-cookies.html'],
    fr: ['Mesure des annonces', 'Si vous acceptez, nous utiliserons des cookies. À la réception de votre demande, nous transmettrons à Google Ads l’identifiant du clic et une référence technique pour mesurer l’annonce. Les données saisies dans le formulaire servent à traiter votre demande. Vous pouvez envoyer le formulaire quel que soit votre choix.', 'Accepter', 'Refuser', 'Politique de cookies', 'Paramètres de mesure des annonces', 'fr-cookies.html']
  };
  var clave = 'avanza_ads_preferencia';
  var claveRechazo = 'avanza_ads_rechazo';
  var clavePendiente = 'avanza_ads_pendiente';
  var versionPreferencia = 2;
  var vigencia = 180 * 24 * 60 * 60 * 1000;
  var clavesClic = ['gclid', 'gbraid', 'wbraid'];
  var formatoClic = /^[A-Za-z0-9_-]{10,200}$/;
  var formatoRef = /^W[0-9a-f]{12}$/;
  var nombrePublicitario = /^_(?:gcl|gac)_[A-Za-z0-9_-]+$/;
  var accion = 'AW-18575091513';
  var destino = accion + '/rNjHCI-9sb0dELnOpZlF';
  var t = textos[document.documentElement.lang] || textos.es;
  var pagina = location.pathname === '/' ? 'index.html' : location.pathname.split('/').pop();
  var params = new URLSearchParams(location.search);
  var entrada = params.get('avanza_entrada');
  var enlaces = [];
  var panel, invocador, quitarClic;
  var etiquetaIniciada = false;
  var rechazoEnPagina = false;

  function identificador() {
    for (var k of clavesClic) {
      var valores = params.getAll(k);
      if (valores.length === 1 && formatoClic.test(valores[0])) return [k, valores[0]];
    }
    return null;
  }

  function vieneDeAnuncio(p) {
    var ruta = Object.prototype.hasOwnProperty.call(recorridos, p) ? recorridos[p] : null;
    return ruta && params.get('origen') === 'anuncio' && params.get('utm_source') === 'google' &&
      params.get('utm_medium') === 'cpc' && ruta.slice(1).includes(params.get('utm_campaign'));
  }

  var clic = identificador();
  var marcasUnicas = ['origen', 'utm_source', 'utm_medium', 'utm_campaign'].every(function (k) {
    return params.getAll(k).length === 1;
  });
  var esPerfil = Boolean(clic && location.pathname === '/' && location.hash === '#despacho' &&
    !params.has('avanza_entrada') && marcasUnicas && vieneDeAnuncio('index.html'));
  // La portada ordinaria conserva su formulario y no toca preferencias ni almacenamiento de Ads.
  if (pagina === 'index.html' && !esPerfil) return;
  if (esPerfil) {
    window.avanzaPerfilAnuncio = true;
    var nota = document.querySelector('[data-avanza-origen-perfil]');
    if (nota) nota.hidden = false;
  }
  var esEntrada = Boolean(clic && vieneDeAnuncio(pagina));
  var paginaVenta = 'vender-inmueble-en-espana-no-residente.html';
  var esEnlaceVenta = Boolean(clic && pagina === 'contacto.html' && !params.has('avanza_entrada') &&
    params.get('pagina') === paginaVenta && vieneDeAnuncio(paginaVenta) &&
    ['pagina', 'origen', 'utm_source', 'utm_medium', 'utm_campaign'].every(function (k) { return params.getAll(k).length === 1; }));
  var esFormulario = esPerfil || esEnlaceVenta || Boolean(clic && vieneDeAnuncio(entrada) &&
    recorridos[entrada][0] === pagina && (entrada !== 'index.html' || (marcasUnicas &&
      params.getAll('avanza_entrada').length === 1 && params.getAll('pagina').length === 1 && params.get('pagina') === 'index.html')));
  var esAcuse = Object.values(acuses).includes(pagina);

  function preferencia() {
    if (rechazoEnPagina) return 'no';
    try { if (sessionStorage.getItem(claveRechazo)) return 'no'; } catch (e) {}
    try {
      var p = JSON.parse(localStorage.getItem(clave));
      var ahora = Date.now();
      if (p && (p.opcion === 'no' || (p.opcion === 'si' && p.version === versionPreferencia)) && Number.isInteger(p.fecha) &&
          p.fecha > 0 && p.fecha <= ahora && ahora - p.fecha < vigencia) return p.opcion;
    } catch (e) {}
    try { localStorage.removeItem(clave); } catch (e) {}
    return '';
  }

  function borrarPublicidad() {
    try { sessionStorage.removeItem(clavePendiente); } catch (e) {}
    for (var obtener of [function () { return localStorage; }, function () { return sessionStorage; }]) {
      try {
        var almacen = obtener();
        for (var i = almacen.length - 1; i >= 0; i--) {
          var k = almacen.key(i);
          if (k && nombrePublicitario.test(k)) almacen.removeItem(k);
        }
      } catch (e) {}
    }
    document.cookie.split(';').forEach(function (par) {
      var nombre = par.trim().split('=')[0];
      if (!nombrePublicitario.test(nombre)) return;
      var caducada = nombre + '=; Max-Age=0; Path=/';
      document.cookie = caducada;
      if (location.hostname.endsWith('grupoavanzaconsultores.es')) {
        document.cookie = caducada + '; Domain=grupoavanzaconsultores.es';
        document.cookie = caducada + '; Domain=' + location.hostname;
      }
    });
  }

  function limpiarURL(retirada) {
    if (!esFormulario && !(esEntrada && retirada)) return;
    var actual = new URL(location.href);
    ['avanza_entrada'].concat(clavesClic).forEach(function (k) { actual.searchParams.delete(k); });
    // En el enlace directo, la primera elección se hace aquí. El clic sale de la URL
    // y solo queda en memoria mientras la persona decide en esta página.
    if (!(esEnlaceVenta || esPerfil) || retirada) esFormulario = false;
    if (retirada) {
      esEntrada = false;
      clic = null;
    }
    try { if (actual.href !== location.href) history.replaceState(history.state, '', actual.href); } catch (e) {}
  }

  function actualizarEnlaces(permitido) {
    for (var enlace of enlaces) {
      var url = new URL(enlace.href);
      if (esPerfil) {
        ['origen', 'utm_source', 'utm_medium', 'utm_campaign'].forEach(function (k) {
          url.searchParams.set(k, params.get(k));
        });
      }
      if (permitido) {
        url.searchParams.set('avanza_entrada', pagina);
        url.searchParams.set(clic[0], clic[1]);
      } else {
        url.searchParams.delete('avanza_entrada');
        clavesClic.forEach(function (k) { url.searchParams.delete(k); });
      }
      if (enlace.href !== url.href) enlace.href = url.href;
    }
  }

  function cerrarMedicion(retirada) {
    borrarPublicidad();
    limpiarURL(retirada);
    if (etiquetaIniciada) {
      window['ga-disable-' + accion] = true;
      quitarClic();
      location.reload();
    }
  }

  function sincronizar() {
    var opcion = preferencia();
    actualizarEnlaces(esEntrada && opcion === 'si');
    if (opcion !== 'si') cerrarMedicion(opcion === 'no');
    if ((esEntrada || (esEnlaceVenta && esFormulario)) && !opcion && !panel) mostrarOpciones();
    return opcion;
  }

  function boton(texto, fn) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'btn btn--ghost btn--sm';
    b.textContent = texto;
    b.addEventListener('click', fn);
    return b;
  }

  function elegir(opcion) {
    rechazoEnPagina = opcion === 'no';
    try { sessionStorage.removeItem(claveRechazo); } catch (e) {}
    try {
      localStorage.setItem(clave, JSON.stringify({ opcion: opcion, fecha: Date.now(), version: versionPreferencia }));
    } catch (e) {
      if (rechazoEnPagina) {
        try { localStorage.removeItem(clave); } catch (error) {}
        try { sessionStorage.setItem(claveRechazo, 'no'); } catch (error) {}
      } else {
        rechazoEnPagina = true;
      }
    }
    panel.remove();
    panel = null;
    if (invocador) invocador.focus();
    invocador = null;
    // Si el navegador no conserva la elección, no se habilita la medición ni se reabre el aviso.
    if (preferencia()) sincronizar();
    else {
      actualizarEnlaces(false);
      cerrarMedicion(true);
    }
  }

  function mostrarOpciones() {
    if (panel) return;
    panel = document.createElement('section');
    panel.setAttribute('aria-labelledby', 'avanza-opciones-titulo');
    panel.className = 'band--surface';
    var contenido = document.createElement('div');
    contenido.className = 'wrap--narrow prose card';
    var titulo = document.createElement('h2');
    titulo.id = 'avanza-opciones-titulo';
    titulo.tabIndex = -1;
    titulo.textContent = t[0];
    var detalle = document.createElement('p');
    detalle.textContent = t[1];
    var acciones = document.createElement('div');
    acciones.className = 'ctas';
    var politica = document.createElement('a');
    politica.href = t[6];
    politica.textContent = t[4];
    acciones.append(boton(t[2], function () { elegir('si'); }), boton(t[3], function () { elegir('no'); }), politica);
    contenido.append(titulo, detalle, acciones);
    panel.append(contenido);
    var perfil = esPerfil && document.getElementById('despacho');
    var principal = document.querySelector('main');
    if (perfil) perfil.prepend(panel);
    else if (principal) principal.before(panel);
    else document.body.prepend(panel);
    if (invocador) titulo.focus();
  }

  if (esEntrada) {
    enlaces = Array.from(document.querySelectorAll('a[href]')).filter(function (a) {
      var u = new URL(a.href);
      if (esPerfil && (u.pathname !== '/contacto.html' || u.searchParams.get('pagina') !== 'index.html')) return false;
      return u.origin === location.origin && u.pathname.split('/').pop() === recorridos[pagina][0];
    });
  }

  var opciones = Array.from(document.querySelectorAll('[data-avanza-opciones-ads]'));
  if (esEntrada || esFormulario || (esAcuse && preferencia())) {
    var pie = document.querySelector('.foot__legal');
    if (pie) {
      var control = boton(t[5], function () { invocador = control; mostrarOpciones(); });
      control.className = 'btn btn--onnavy btn--sm';
      pie.append(control);
    }
  }
  for (var opcion of opciones) {
    opcion.addEventListener('click', function (e) { invocador = e.currentTarget; mostrarOpciones(); });
  }

  window.addEventListener('storage', function (e) { if (!e.key || e.key === clave) sincronizar(); });
  window.addEventListener('pageshow', sincronizar);

  if (esFormulario) {
    window.avanzaMedicion = { preparar: function (acuse) {
      if (!esFormulario || !acuse || acuse.ok !== true || typeof acuse.ref !== 'string' ||
          !formatoRef.test(acuse.ref) || preferencia() !== 'si') return;
      try {
        sessionStorage.setItem(clavePendiente, JSON.stringify({
          ref: acuse.ref, formulario: pagina, clic: clic, fecha: Date.now()
        }));
      } catch (e) {}
    } };
  }

  function emitirPendiente() {
    var pendiente, envio;
    try {
      var guardada = sessionStorage.getItem(clavePendiente);
      if (!guardada) return;
      sessionStorage.removeItem(clavePendiente);
      pendiente = JSON.parse(guardada);
      envio = JSON.parse(sessionStorage.getItem('avanza_envio'));
    } catch (e) { return; }
    var ref = params.get('ref');
    var ahora = Date.now();
    if (!formatoRef.test(ref) || !envio || envio.ref !== ref || !pendiente || pendiente.ref !== ref ||
        acuses[pendiente.formulario] !== pagina || !Number.isInteger(pendiente.fecha) ||
        pendiente.fecha > ahora || ahora - pendiente.fecha >= 120000 || !Array.isArray(pendiente.clic) ||
        !clavesClic.includes(pendiente.clic[0]) || typeof pendiente.clic[1] !== 'string' ||
        !formatoClic.test(pendiente.clic[1]) || preferencia() !== 'si') return;

    var urlTag = new URL(location.pathname, location.origin);
    urlTag.searchParams.set(pendiente.clic[0], pendiente.clic[1]);
    var formularioTag = new URL(pendiente.formulario, location.origin);
    var acuseConClic = new URL(location.href);
    acuseConClic.searchParams.set(pendiente.clic[0], pendiente.clic[1]);
    try { history.replaceState(history.state, '', acuseConClic.href); } catch (e) { return; }
    var plazo = setTimeout(function () { quitarClic(); }, 10000);
    quitarClic = function () {
      clearTimeout(plazo);
      var actual = new URL(location.href);
      actual.searchParams.delete(pendiente.clic[0]);
      if (actual.href !== location.href) history.replaceState(history.state, '', actual.href);
    };
    window.addEventListener('pagehide', quitarClic, { once: true });

    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    var gtag = window.gtag;
    gtag('consent', 'default', { ad_storage: 'granted', ad_user_data: 'granted', ad_personalization: 'denied', analytics_storage: 'denied' });
    gtag('set', { allow_google_signals: false, allow_ad_personalization_signals: false, page_location: urlTag.href, page_referrer: formularioTag.href });
    gtag('js', new Date());
    gtag('config', accion, { send_page_view: false });
    gtag('event', 'conversion', { send_to: destino, transaction_id: ref, event_callback: quitarClic });
    var script = document.createElement('script');
    script.async = true;
    script.referrerPolicy = 'no-referrer';
    script.src = 'https://www.googletagmanager.com/gtag/js?id=' + accion;
    script.addEventListener('error', quitarClic, { once: true });
    etiquetaIniciada = true;
    document.head.append(script);
  }

  if (sincronizar() === 'si' && esAcuse) emitirPendiente();
})();
