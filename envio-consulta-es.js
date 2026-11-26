(function(){
  // En portada solo gestiona el formulario de una entrada comprobada por el enlace de perfil.
  if (document.currentScript.hasAttribute('data-solo-perfil') && !window.avanzaPerfilAnuncio) return;
  if (window.__avanzaEnvio) return; window.__avanzaEnvio = 1;
  // Clave aleatoria del envío, sin datos de la consulta. Se reutiliza en cada reintento del mismo texto.
  var CLAVE_ENVIO = 'avanza_envio', REF_VALIDA = /^W[0-9a-f]{12}$/, TEXTO_BOTON = 'Enviar consulta', envioMemoria = null;
  function nuevaClave(){
    var r = '';
    try { var al = new Uint8Array(16); (window.crypto || window.msCrypto).getRandomValues(al); for (var i = 0; i < al.length; i++) r += ('0' + al[i].toString(16)).slice(-2); } catch (err) { while (r.length < 32) r += Math.floor(Math.random() * 16).toString(16); }
    return r;
  }
  function leerEnvio(){
    try { return JSON.parse(sessionStorage.getItem(CLAVE_ENVIO)) || envioMemoria; } catch (err) { return envioMemoria; }
  }
  function guardarEnvio(v){
    envioMemoria = v;
    try { sessionStorage.setItem(CLAVE_ENVIO, JSON.stringify(v)); } catch (err) {}
  }
  // Resumen del texto para distinguir una consulta nueva de un reintento; no guarda el texto.
  function resumen(t){
    var h = 2166136261;
    for (var i = 0; i < t.length; i++) { h ^= t.charCodeAt(i); h = Math.imul(h, 16777619); }
    return (h >>> 0).toString(16) + '-' + t.length;
  }
  function resumenDe(f){
    var d = new FormData(f);
    return resumen([d.get('nombre'), d.get('contacto'), d.get('caso'), d.get('origen') || ''].join('\n'));
  }
  function pintarRecibido(f, ref){
    var r = f.querySelector('[data-envio-recibido]');
    if (!r) return;
    var s = r.querySelector('[data-envio-ref]');
    if (s) s.textContent = ref || '';
    r.hidden = !ref;
  }
  if (!leerEnvio()) guardarEnvio({ id: nuevaClave(), h: '' });
  var enVuelo = false;
  // Al volver con Atrás: el botón queda libre y, si es la misma consulta ya confirmada, se dice.
  window.addEventListener('pageshow', function(){
    if (enVuelo) return;
    var f = document.querySelector('form.form');
    if (!f) return;
    f.removeAttribute('aria-busy');
    var b = f.querySelector('button[type=submit]');
    if (b) { b.disabled = false; b.textContent = TEXTO_BOTON; }
    var envio = leerEnvio();
    pintarRecibido(f, envio && envio.ref && envio.h === resumenDe(f) ? envio.ref : '');
  });
  document.addEventListener('submit', function(e){
    var f = e.target;
    if (!f || !f.classList || !f.classList.contains('form')) return;
    if (!window.fetch || !window.URLSearchParams || !window.FormData) return;
    if (f.action.indexOf('script.google.com') === -1) return;
    e.preventDefault();
    if (f.getAttribute('aria-busy') === 'true') return;
    f.setAttribute('aria-busy', 'true');
    var b = f.querySelector('button[type=submit]');
    var textoBoton = TEXTO_BOTON;
    var aviso = f.querySelector('[data-envio-error]');
    if (aviso) aviso.hidden = true;
    pintarRecibido(f, '');
    if (b) { b.disabled = true; b.textContent = 'Enviando…'; }
    var datos = new FormData(f);
    var conocio = datos.get('origen') || '';
    var h = resumen([datos.get('nombre'), datos.get('contacto'), datos.get('caso'), conocio].join('\n'));
    var envio = leerEnvio() || { id: nuevaClave(), h: '' };
    // Misma consulta ya confirmada: ni se reenvía la clave ni sale otro evento.
    if (envio.ref && envio.h === h) {
      f.removeAttribute('aria-busy');
      if (b) { b.disabled = false; b.textContent = textoBoton; }
      pintarRecibido(f, envio.ref);
      return;
    }
    if (envio.h && envio.h !== h) envio = { id: nuevaClave(), h: h };
    envio.h = h;
    guardarEnvio(envio);
    datos.set('client_submit_id', envio.id);
    datos.set('pagina', window.location.pathname);
    var desde = '';
    try { var q = new URLSearchParams(window.location.search).get('pagina') || ''; if (/^[a-z0-9-]+\.html$/.test(q)) desde = q; } catch (err) {}
    var anuncio = '', campana = '';
    try {
      var qs = new URLSearchParams(window.location.search);
      if (qs.get('origen') === 'anuncio') {
        anuncio = ' · Llegó por: anuncio de Google';
        var marcas = [];
        ['utm_source','utm_medium','utm_campaign','utm_content'].forEach(function(k){
          var v = qs.get(k) || '';
          if (/^[A-Za-z0-9_.-]{1,60}$/.test(v)) { datos.set(k, v); marcas.push(v); }
        });
        campana = marcas.join(' / ');
        datos.set('origen', 'anuncio');
        if (conocio) datos.set('como_nos_conocio', conocio);
      }
    } catch (err) {}
    datos.set('caso', (datos.get('caso') || '') + '\n\n[Página: ' + window.location.pathname + (desde ? ' · Viene de: ' + desde : '') + anuncio + (campana ? ' · Campaña: ' + campana : '') + ' · Nos conoció por: ' + (conocio || 'sin indicar') + ']');
    datos.set('formato', 'json');
    var cuerpo = new URLSearchParams(datos);
    var finalizado = false;
    function mostrarAviso(){
      if (finalizado) return;
      finalizado = true;
      enVuelo = false;
      clearTimeout(espera);
      f.removeAttribute('aria-busy');
      if (b) { b.disabled = false; b.textContent = textoBoton; }
      if (aviso) { aviso.hidden = false; aviso.focus(); }
    }
    var espera = setTimeout(mostrarAviso, 20000);
    var limite = Date.now() + 20000;
    // Respuesta ilegible o que no llega: pudo llegar. Se pregunta a B por la misma clave dentro del plazo de 20 s;
    // lo que vuelva pasa por confirmar(), con sus mismas validaciones.
    var recuperando = false;
    function recuperar(){
      if (recuperando || finalizado) return;
      recuperando = true;
      var pausas = [1500, 3000, 3000, 3000], i = 0;
      var url = f.action + (f.action.indexOf('?') > -1 ? '&' : '?') + 'client_submit_id=' + encodeURIComponent(envio.id);
      function vuelta(){
        if (finalizado) return;
        var pausa = pausas[Math.min(i++, pausas.length - 1)];
        if (Date.now() + pausa >= limite) return;
        setTimeout(function(){
          var resta = limite - Date.now();
          if (finalizado || resta <= 0) return;
          var ctl = window.AbortController ? new AbortController() : null;
          var corte = ctl ? setTimeout(function(){ ctl.abort(); }, Math.min(resta, 5000)) : null;
          fetch(url, { method: 'GET', credentials: 'omit', cache: 'no-store', signal: ctl ? ctl.signal : undefined })
            .then(function(r){ return r.json(); })
            .then(function(j){ clearTimeout(corte); if (j && j.ok === true) confirmar(j); else vuelta(); },
                  function(){ clearTimeout(corte); vuelta(); });
        }, pausa);
      }
      vuelta();
    }
    function confirmar(j){
      if (finalizado) return;
      if (!j || j.ok !== true || !REF_VALIDA.test(j.ref || '') || (envio.ref && envio.ref !== j.ref)) { mostrarAviso(); return; }
      finalizado = true;
      enVuelo = false;
      clearTimeout(espera);
      envio.ref = j.ref;
      guardarEnvio(envio);
      // La página de gracias solo confirma si lee esta ref en la sesión. Si el navegador no deja guardarla,
      // se confirma aquí mismo, en el formulario, con la ref que ya ha dado el receptor.
      var guardada = '';
      try { guardada = (JSON.parse(sessionStorage.getItem(CLAVE_ENVIO)) || {}).ref || ''; } catch (err) { guardada = ''; }
      if (guardada !== j.ref) {
        f.removeAttribute('aria-busy');
        if (b) { b.disabled = false; b.textContent = textoBoton; }
        pintarRecibido(f, j.ref);
        var r = f.querySelector('[data-envio-recibido]');
        if (r) r.focus();
        return;
      }
      if (window.avanzaMedicion) window.avanzaMedicion.preparar(j);
      window.location.href = 'gracias.html?ref=' + encodeURIComponent(j.ref) + (anuncio ? '&origen=anuncio' : '');
    }
    enVuelo = true;
    // POST sin respuesta: a los 6 s se pregunta por la clave sin esperar a que falle. La primera
    // confirmación válida cierra (finalizado); la respuesta tardía del POST ya no hace nada.
    setTimeout(recuperar, 6000);
    fetch(f.action, { method: 'POST', body: cuerpo })
      .then(function(r){ return r.json(); })
      .then(confirmar, recuperar);
  });
})();
