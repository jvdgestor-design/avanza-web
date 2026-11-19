/* Atribución de anuncios sin cookies ni almacenamiento: si la visita llega con
   ?origen=anuncio (sufijo de URL de la campaña de Google Ads), se pasa ese dato
   a los enlaces del formulario de contacto y se añade «(ref. Ads)» al texto
   precargado de WhatsApp (solo a los enlaces que ya traen texto). No hace nada en las visitas que no vienen de un anuncio. */
(function () {
  try {
    if (new URLSearchParams(window.location.search).get('origen') !== 'anuncio') return;
    var contacto = /^(contacto|en-contact|fr-contact|de-kontakt)\.html/;
    var marca = encodeURIComponent(' (ref. Ads)');
    Array.prototype.forEach.call(document.querySelectorAll('a[href]'), function (a) {
      var h = a.getAttribute('href');
      if (contacto.test(h)) {
        var u = new URL(h, window.location.href);
        u.searchParams.set('origen', 'anuncio');
        a.setAttribute('href', u.pathname.split('/').pop() + u.search + u.hash);
      } else if (/^https:\/\/wa\.me\/34614365547/.test(h) && h.indexOf('ref.%20Ads') === -1) {
        if (/[?&]text=[^&#]*$/.test(h)) a.setAttribute('href', h + marca);
      }
    });
  } catch (e) {}
})();
