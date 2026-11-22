/* Atribución de anuncios sin cookies ni almacenamiento: si la visita llega con
   ?origen=anuncio (sufijo de URL de la campaña de Google Ads), se pasa ese dato
   a los enlaces del formulario de contacto (al español, también el nombre de la
   campaña: utm_source, utm_campaign y utm_content) y se añade «(ref. Ads)» al texto
   precargado de WhatsApp (Avanza y Anna; solo a los enlaces que ya traen texto)
   y al asunto de los enlaces de correo. No hace nada en las visitas que no vienen de un anuncio. */
(function () {
  try {
    var q = new URLSearchParams(window.location.search);
    if (q.get('origen') !== 'anuncio') return;
    var utm = [];
    ['utm_source', 'utm_campaign', 'utm_content'].forEach(function (k) {
      var v = q.get(k); if (v && /^[A-Za-z0-9_.-]{1,60}$/.test(v)) utm.push([k, v]);
    });
    var contacto = /^(contacto|en-contact|fr-contact|de-kontakt)\.html/;
    var marca = encodeURIComponent(' (ref. Ads)');
    Array.prototype.forEach.call(document.querySelectorAll('a[href]'), function (a) {
      var h = a.getAttribute('href');
      if (contacto.test(h)) {
        var u = new URL(h, window.location.href);
        u.searchParams.set('origen', 'anuncio');
        if (/^contacto\.html/.test(h)) utm.forEach(function (kv) { u.searchParams.set(kv[0], kv[1]); });
        a.setAttribute('href', u.pathname.split('/').pop() + u.search + u.hash);
      } else if (/^https:\/\/wa\.me\/(34614365547|34642457458)/.test(h) && h.indexOf('ref.%20Ads') === -1) {
        if (/[?&]text=[^&#]*$/.test(h)) a.setAttribute('href', h + marca);
      } else if (/^mailto:/.test(h) && h.indexOf('ref.%20Ads') === -1) {
        if (/[?&]subject=/.test(h)) a.setAttribute('href', h.replace(/([?&]subject=[^&#]*)/, '$1' + marca));
        else a.setAttribute('href', h + (h.indexOf('?') === -1 ? '?' : '&') + 'subject=' + marca.replace(/^%20/, ''));
      }
    });
  } catch (e) {}
})();
