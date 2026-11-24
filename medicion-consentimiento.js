/* Medición de anuncios con consentimiento (modo básico). Sin aceptar no se carga gtag.js
   ni se hace ninguna petición a Google. La elección se guarda solo como preferencia técnica
   y se vuelve a leer al restaurar la página y cuando cambia en otra pestaña.
   La etiqueta solo se carga en contacto.html, al confirmarse una consulta del recorrido validado:
   con la medición ya aceptada en la página de venta, un botón de esa carga con origen=anuncio lleva
   el identificador de clic y un testigo de un solo uso que contacto comprueba y borra. Antes de
   aceptar, el identificador solo está en memoria. Aceptar por primera vez en contacto no atribuye.
   Nada del recorrido se deduce de una carga anterior. */
(function () {
  if (window.avanzaMedicion) return;
  var CUENTA = 'AW-18575091513', ACCION = 'AW-18575091513/rNjHCI-9sb0dELnOpZlF';
  var CLAVE = 'avanza_medicion', MARCADAS = 'avanza_medicion_refs', VIGENCIA = 365 * 864e5;
  var CLIC = ['gclid', 'gbraid', 'wbraid'];
  var CONCEDIDO = { ad_storage: 'granted', ad_user_data: 'granted', ad_personalization: 'denied', analytics_storage: 'denied' };
  var DENEGADO = { ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied', analytics_storage: 'denied' };
  var TEXTOS = {
    es: { region: 'Preferencias de cookies', texto: 'Con tu permiso, usamos cookies de Google para medir las consultas que llegan desde nuestros anuncios de Google, con un identificador del clic. No se personalizan anuncios, no se envían los datos del formulario y no se usan conversiones mejoradas. El formulario funciona igual elijas lo que elijas.', politica: 'Política de cookies', url: 'cookies.html', aceptar: 'Aceptar medición', rechazar: 'Rechazar', si: 'Medición aceptada.', no: 'Medición rechazada.', nada: 'Todavía no has elegido.' },
    en: { region: 'Cookie preferences', texto: 'With your permission, we use Google cookies to measure the enquiries that come from our Google ads, using a click identifier. Ads are not personalised, form data is not sent and enhanced conversions are not used. The form works the same whatever you choose.', politica: 'Cookie information', url: 'en-privacy.html#cookies', aceptar: 'Accept measurement', rechazar: 'Reject', si: 'Measurement accepted.', no: 'Measurement rejected.', nada: 'You have not chosen yet.' },
    de: { region: 'Cookie-Einstellungen', texto: 'Mit Ihrer Einwilligung verwenden wir Google-Cookies, um anhand einer Klick-Kennung die Anfragen zu messen, die über unsere Google-Anzeigen eingehen. Anzeigen werden nicht personalisiert, Formulardaten werden nicht übermittelt und erweiterte Conversions werden nicht verwendet. Das Formular funktioniert unabhängig von Ihrer Wahl.', politica: 'Cookie-Hinweise', url: 'de-cookies.html', aceptar: 'Messung akzeptieren', rechazar: 'Ablehnen', si: 'Messung akzeptiert.', no: 'Messung abgelehnt.', nada: 'Sie haben noch nicht gewählt.' },
    fr: { region: 'Préférences de cookies', texto: 'Avec votre accord, nous utilisons des cookies de Google pour mesurer, à l’aide d’un identifiant de clic, les demandes issues de nos annonces Google. Les annonces ne sont pas personnalisées, les données du formulaire ne sont pas envoyées et les conversions améliorées ne sont pas utilisées. Le formulaire fonctionne de la même façon quel que soit votre choix.', politica: 'Politique relative aux cookies', url: 'fr-cookies.html', aceptar: 'Accepter la mesure', rechazar: 'Refuser', si: 'Mesure acceptée.', no: 'Mesure refusée.', nada: 'Vous n’avez pas encore choisi.' }
  };
  var yo = document.currentScript;
  var limpia = !!(yo && yo.hasAttribute('data-medicion-limpia'));
  var ATRIBUCION = ['origen', 'pagina', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content'], CLAVE_ATRIB = 'avanza_medicion_atrib';
  var VENTA = 'vender-inmueble-en-espana-no-residente.html', CLAVE_TESTIGO = 'avanza_medicion_testigo', VIDA_TESTIGO = 30 * 6e4;
  var cargada = false, retirada = false, enMemoria = null, marcadasMemoria = [], aviso = null, atribMemoria = null, recorridoCarga = null, recorridoContacto = null;

  function textos() {
    var l = (document.documentElement.getAttribute('lang') || 'es').slice(0, 2).toLowerCase();
    return TEXTOS[l] || TEXTOS.es;
  }
  // Si el almacenamiento se puede leer manda él: un valor borrado en otra pestaña no revive desde la memoria.
  function leer() {
    try {
      var c = localStorage.getItem(CLAVE);
      return c ? JSON.parse(c) : null;
    } catch (e) { return enMemoria; }
  }
  // Una preferencia sin fecha válida (falta, no es número o es futura) no cuenta: se vuelve a preguntar.
  function valida(v) {
    return !!v && (v.e === 'aceptada' || v.e === 'rechazada') && typeof v.t === 'number' && isFinite(v.t) && v.t > 0 && v.t <= Date.now() + 3e5;
  }
  function caducada(v) { return valida(v) && Date.now() - v.t > VIGENCIA; }
  function estado() {
    var v = leer();
    return valida(v) && !caducada(v) ? v.e : '';
  }
  function guardar(e) {
    enMemoria = { e: e, t: Date.now() };
    try { localStorage.setItem(CLAVE, JSON.stringify(enMemoria)); } catch (err) {}
  }
  function gtag() { window.dataLayer = window.dataLayer || []; window.dataLayer.push(arguments); }

  // La atribución interna se lee de aquí: la dirección, o lo guardado si esta misma página ya se limpió.
  function parametros() {
    if (atribMemoria !== null) return new URLSearchParams(atribMemoria);
    var q = new URLSearchParams(location.search);
    try {
      var nav = performance.getEntriesByType('navigation')[0], g;
      if (limpia && nav && (nav.type === 'reload' || nav.type === 'back_forward') && !ATRIBUCION.some(function (k) { return q.has(k); })) {
        g = JSON.parse(sessionStorage.getItem(CLAVE_ATRIB));
        if (g && g.p === location.pathname) return new URLSearchParams(g.q);
      }
    } catch (e) {}
    return q;
  }
  // Antes de la etiqueta: se guarda la atribución y en la dirección solo queda un identificador de clic válido.
  function limpiarUrl() {
    if (!limpia) return;
    try {
      var o = parametros(), a = new URLSearchParams(), c = new URLSearchParams(), q = new URLSearchParams(location.search), s;
      ATRIBUCION.forEach(function (k) { if (o.has(k)) a.set(k, o.get(k)); });
      atribMemoria = a.toString();
      try { sessionStorage.setItem(CLAVE_ATRIB, JSON.stringify({ p: location.pathname, q: atribMemoria })); } catch (e) {}
      CLIC.forEach(function (k) { var v = q.get(k); if (v && /^[A-Za-z0-9_-]{10,200}$/.test(v)) c.set(k, v); });
      s = c.toString();
      history.replaceState(history.state, '', location.pathname + (s ? '?' + s : ''));
    } catch (e) {}
  }

  function cargar() {
    limpiarUrl();
    window['ga-disable-' + CUENTA] = false;
    retirada = false;
    if (cargada) {
      gtag('consent', 'update', CONCEDIDO);
      return;
    }
    cargada = true;
    gtag('consent', 'default', DENEGADO);
    gtag('consent', 'update', CONCEDIDO);
    gtag('js', new Date());
    gtag('config', CUENTA, { send_page_view: false, allow_ad_personalization_signals: false, page_location: location.origin + location.pathname });
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + CUENTA;
    document.head.appendChild(s);
  }

  // El identificador de clic solo sigue el recorrido con la medición aceptada.
  function quitarClicDeUrl() {
    try {
      var u = new URL(location.href), habia = false;
      CLIC.forEach(function (k) { if (u.searchParams.has(k)) { u.searchParams.delete(k); habia = true; } });
      if (habia) history.replaceState(history.state, '', u.pathname + u.search + u.hash);
    } catch (e) {}
  }
  function quitarClicDeEnlaces() {
    try {
      Array.prototype.forEach.call(document.querySelectorAll('a[href]'), function (a) {
        var h = a.getAttribute('href');
        if (!/^contacto\.html/.test(h)) return;
        var u = new URL(h, location.href);
        CLIC.forEach(function (k) { u.searchParams.delete(k); });
        a.setAttribute('href', u.pathname.split('/').pop() + u.search + u.hash);
      });
    } catch (e) {}
  }

  function cookiesGcl() {
    return document.cookie.split(';').map(function (c) { return c.split('=')[0].trim(); })
      .filter(function (n) { return /^_gcl_/.test(n); });
  }
  function borrarCookiesGcl() {
    var partes = location.hostname.split('.'), dominios = [''];
    for (var i = 0; i < partes.length - 1; i++) {
      var d = partes.slice(i).join('.');
      dominios.push(';domain=' + d, ';domain=.' + d);
    }
    cookiesGcl().forEach(function (n) {
      dominios.forEach(function (d) { document.cookie = n + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/' + d; });
    });
    return cookiesGcl();
  }
  // Lo que la medición o gtag.js dejan en el navegador (por ejemplo _gcl_ls) se borra; la preferencia se queda.
  function borrarAlmacenPublicidad() {
    [function () { return localStorage; }, function () { return sessionStorage; }].forEach(function (f) {
      try {
        var al = f(), n, i;
        for (i = al.length - 1; i >= 0; i--) {
          n = al.key(i);
          if (n && (/^_gcl/.test(n) || n === CLAVE_TESTIGO || n === MARCADAS || n === CLAVE_ATRIB)) al.removeItem(n);
        }
      } catch (e) {}
    });
  }
  // Deja la página sin permiso: nada nuevo hacia Google, sin cookies _gcl_* y sin identificador de clic.
  function retirar() {
    window['ga-disable-' + CUENTA] = true;
    if (cargada && !retirada) gtag('consent', 'update', DENEGADO);
    retirada = true;
    var quedan = borrarCookiesGcl();
    recorridoCarga = recorridoContacto = null;
    marcadasMemoria = [];
    borrarAlmacenPublicidad();
    quitarClicDeUrl();
    quitarClicDeEnlaces();
    return quedan;
  }

  function aceptar() {
    guardar('aceptada');
    cerrarAviso();
    pintarPreferencias();
  }
  function rechazar() {
    guardar('rechazada');
    var quedan = retirar();
    cerrarAviso();
    pintarPreferencias();
    return quedan;
  }
  // Al volver con Atrás o si cambia en otra pestaña. Aceptar fuera de esta página no carga nada ni dispara eventos.
  function aplicarEstado() {
    var v = leer(), e = estado();
    if (e === 'aceptada') cerrarAviso();
    else if (e === 'rechazada') { retirar(); cerrarAviso(); }
    else {
      if (cargada || caducada(v)) retirar();
      abrir();
    }
    pintarPreferencias();
  }

  function marcadas() {
    try { return JSON.parse(sessionStorage.getItem(MARCADAS)) || marcadasMemoria; } catch (e) { return marcadasMemoria; }
  }
  function marcar(ref) {
    var l = marcadas().concat([ref]);
    marcadasMemoria = l;
    try { sessionStorage.setItem(MARCADAS, JSON.stringify(l)); } catch (e) {}
  }
  function paginaActual() {
    var n = location.pathname.split('/').pop();
    return /\.html$/.test(n) ? n : n + '.html';
  }
  // La marca de recorrido vive solo en esta carga de la página de venta y solo si la carga trae origen=anuncio.
  function anotarRecorrido() {
    try {
      if (paginaActual() !== VENTA || estado() === 'rechazada') return;
      var nav = performance.getEntriesByType('navigation')[0], q = new URLSearchParams(location.search), clic = {};
      if ((nav && (nav.type === 'reload' || nav.type === 'back_forward')) || q.get('origen') !== 'anuncio') return;
      CLIC.forEach(function (k) { var v = q.get(k); if (v && /^[A-Za-z0-9_-]{10,200}$/.test(v)) clic[k] = v; });
      recorridoCarga = { clic: clic };
    } catch (e) {}
  }
  function nuevoTestigo() {
    var al = new Uint8Array(16), r = '';
    window.crypto.getRandomValues(al);
    for (var i = 0; i < al.length; i++) r += ('0' + al[i].toString(16)).slice(-2);
    return r;
  }
  // Al pulsar «Consultar mi caso» en esa carga, solo con la medición aceptada y un identificador válido:
  // el enlace lleva el identificador y un testigo de un solo uso. En cualquier otro caso, ninguno de los dos.
  function ponerTestigo(ev) {
    var a = ev.target.closest && ev.target.closest('a[href^="contacto.html"]');
    if (!a || paginaActual() !== VENTA) return;
    try {
      var u = new URL(a.getAttribute('href'), location.href), r;
      u.searchParams.delete('r');
      CLIC.forEach(function (k) { u.searchParams.delete(k); });
      if (recorridoCarga && Object.keys(recorridoCarga.clic).length && u.searchParams.get('pagina') === VENTA && estado() === 'aceptada' && !ev.ctrlKey && !ev.metaKey && !ev.shiftKey) {
        r = nuevoTestigo();
        sessionStorage.setItem(CLAVE_TESTIGO, JSON.stringify({ r: r, t: Date.now(), clic: recorridoCarga.clic }));
        CLIC.forEach(function (k) { if (recorridoCarga.clic[k]) u.searchParams.set(k, recorridoCarga.clic[k]); });
        u.searchParams.set('r', r);
      }
      a.setAttribute('href', u.pathname.split('/').pop() + u.search + u.hash);
    } catch (e) {}
  }
  // En contacto el testigo se borra al leerlo, antes de cargar nada, se cumplan o no las condiciones.
  function leerTestigo() {
    if (paginaActual() !== 'contacto.html') return;
    var g = null, u = new URL(location.href), r = u.searchParams.get('r'), edad;
    try {
      g = JSON.parse(sessionStorage.getItem(CLAVE_TESTIGO));
      sessionStorage.removeItem(CLAVE_TESTIGO);
    } catch (e) { return; }
    if (u.searchParams.has('r')) {
      u.searchParams.delete('r');
      try { history.replaceState(history.state, '', u.pathname + u.search + u.hash); } catch (e) {}
    }
    if (!g || !g.clic || !r || g.r !== r || u.searchParams.get('pagina') !== VENTA || estado() !== 'aceptada') return;
    // La dirección debe traer exactamente el identificador validado en venta.
    if (!CLIC.some(function (k) { return !!g.clic[k]; }) || !CLIC.every(function (k) { return (u.searchParams.get(k) || '') === (g.clic[k] || ''); })) return;
    edad = Date.now() - g.t;
    if (edad >= 0 && edad < VIDA_TESTIGO) recorridoContacto = { clic: g.clic };
  }
  // Ninguna dirección que la etiqueta pueda leer lleva un identificador distinto del validado.
  function direccionesLimpias(clic) {
    var urls = [location.href];
    if (window.navigation) {
      if (navigation.entries) navigation.entries().forEach(function (x) { if (x.url) urls.push(x.url); });
      if (navigation.activation && navigation.activation.from && navigation.activation.from.url) urls.push(navigation.activation.from.url);
    }
    return urls.every(function (h) {
      var q = new URL(h).searchParams;
      return CLIC.every(function (k) { return !q.has(k) || q.get(k) === clic[k]; });
    });
  }
  // La cookie _gcl_aw, si existe, debe traer el identificador validado.
  function cookieCoincide(clic) {
    return document.cookie.split(';').map(function (c) { return c.trim(); })
      .filter(function (c) { return c.indexOf('_gcl_aw=') === 0; })
      .every(function (c) { var p = c.slice(8).split('.'); return p.length >= 3 && !!clic.gclid && p.slice(2).join('.') === clic.gclid; });
  }
  function recorridoValido() {
    try {
      if (paginaActual() !== 'contacto.html' || !recorridoContacto) return false;
      var p = parametros();
      if (p.get('origen') !== 'anuncio' || p.get('pagina') !== VENTA) return false;
      return direccionesLimpias(recorridoContacto.clic) && cookieCoincide(recorridoContacto.clic);
    } catch (e) { return false; }
  }

  // Un solo evento por referencia. Si la medición falla, la consulta sigue recibida.
  function conversion(ref, seguir) {
    var hecho = false;
    function fin() { if (hecho) return; hecho = true; seguir(); }
    try {
      if (estado() !== 'aceptada' || !recorridoValido() || marcadas().indexOf(ref) !== -1) return fin();
      marcar(ref);
      recorridoContacto = null;
      cargar();
      gtag('event', 'conversion', { send_to: ACCION, transaction_id: ref, event_callback: fin, event_timeout: 1000 });
      setTimeout(fin, 1000);
    } catch (e) { fin(); }
  }

  function estilos() {
    if (document.getElementById('avisoMedicionCss')) return;
    var c = document.createElement('style');
    c.id = 'avisoMedicionCss';
    c.textContent = '.aviso-med{position:fixed;left:0;right:0;bottom:0;z-index:60;background:var(--raised);color:var(--ink);border-top:2px solid var(--gold);box-shadow:0 -6px 24px rgba(15,29,54,.18)}' +
      '.aviso-med__in{max-width:1080px;margin:0 auto;padding:16px 20px;display:flex;gap:20px;align-items:center;justify-content:space-between}' +
      '.aviso-med p{margin:0;font-size:.92rem;line-height:1.5;color:var(--ink-soft)}.aviso-med a{color:var(--navy);text-decoration:underline}' +
      '.aviso-med__bt{display:flex;gap:10px;flex:none}.aviso-med button{width:176px;min-height:44px;padding:10px 16px;border:1px solid var(--navy);border-radius:0;background:var(--raised);color:var(--navy);font:inherit;font-size:.92rem;font-weight:600;cursor:pointer}' +
      '.aviso-med button:hover,.aviso-med button:focus-visible{background:var(--surface);outline:2px solid var(--navy);outline-offset:1px}' +
      '@media(max-width:720px){.aviso-med__in{display:block;padding:14px 16px}.aviso-med__bt{margin-top:12px}.aviso-med button{flex:1 1 0;width:auto;min-width:0}}';
    document.head.appendChild(c);
  }
  function cerrarAviso() { if (aviso) { aviso.parentNode.removeChild(aviso); aviso = null; } }
  function abrir() {
    if (aviso) return;
    var t = textos();
    estilos();
    aviso = document.createElement('div');
    aviso.className = 'aviso-med';
    aviso.setAttribute('role', 'region');
    aviso.setAttribute('aria-label', t.region);
    aviso.innerHTML = '<div class="aviso-med__in"><p>' + t.texto + ' <a href="' + t.url + '">' + t.politica + '</a>.</p>' +
      '<div class="aviso-med__bt"><button type="button" data-med="aceptar">' + t.aceptar + '</button><button type="button" data-med="rechazar">' + t.rechazar + '</button></div></div>';
    aviso.querySelector('[data-med=aceptar]').addEventListener('click', aceptar);
    aviso.querySelector('[data-med=rechazar]').addEventListener('click', rechazar);
    document.body.appendChild(aviso);
  }
  function pintarPreferencias() {
    var el = document.querySelector('[data-estado-medicion]');
    if (!el) return;
    var e = estado(), t = textos();
    el.textContent = e === 'aceptada' ? t.si : e === 'rechazada' ? t.no : t.nada;
  }

  // Un identificador inválido no se queda en el historial, de donde la etiqueta podría leerlo en la página siguiente.
  function quitarClicInvalido() {
    try {
      var u = new URL(location.href), habia = false;
      CLIC.forEach(function (k) {
        var v = u.searchParams.get(k);
        if (u.searchParams.has(k) && !/^[A-Za-z0-9_-]{10,200}$/.test(v || '')) { u.searchParams.delete(k); habia = true; }
      });
      if (habia) history.replaceState(history.state, '', u.pathname + u.search + u.hash);
    } catch (e) {}
  }
  if (limpia) { anotarRecorrido(); leerTestigo(); quitarClicInvalido(); }

  window.avanzaMedicion = { estado: estado, aceptar: aceptar, rechazar: rechazar, abrir: abrir, conversion: conversion, parametros: parametros };

  // cookies.html no carga la medición: su enlace trae aquí, con #preferencias, para decidir.
  // Se abre una sola vez y tras el primer pageshow, que cerraría el aviso si ya hay una decisión.
  var pedirPreferencias = location.hash === '#preferencias';
  function iniciar() {
    document.addEventListener('click', function (ev) {
      var a = ev.target.closest && ev.target.closest('[data-preferencias-cookies]');
      if (!a) return;
      ev.preventDefault();
      abrir();
    });
    if (limpia) document.addEventListener('click', ponerTestigo, true);
    window.addEventListener('pageshow', function (ev) {
      // Una página restaurada es una carga anterior: no conserva el recorrido.
      if (ev.persisted) recorridoCarga = recorridoContacto = null;
      aplicarEstado();
      if (pedirPreferencias) { pedirPreferencias = false; abrir(); }
    });
    window.addEventListener('storage', function (ev) {
      if (ev.key === CLAVE || ev.key === null) aplicarEstado();
    });
    aplicarEstado();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
