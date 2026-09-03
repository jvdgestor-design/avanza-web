/* Contador del próximo vencimiento fiscal.
   Se calcula en el navegador del visitante; no envía ni guarda nada. */
(function () {
  var RULES = [
    { m: 0, d: 20,    items: ['Retenciones del 4.º trimestre (111 y 115)'] },
    { m: 0, d: 30,    items: ['IVA del 4.º trimestre (303)', 'Pago fraccionado de IRPF (130 o 131)', 'Resumen anual de IVA (390)'] },
    { m: 0, d: 31,    items: ['Resúmenes anuales de retenciones (190 y 180)'] },
    { m: 1, d: 'fin', items: ['Operaciones con terceros (347)'] },
    { m: 3, d: 20,    items: ['IVA del 1.er trimestre (303)', 'Pago fraccionado de IRPF (130 o 131)', 'Retenciones (111 y 115)'] },
    { m: 5, d: 30,    items: ['Fin de la campaña de la Renta (100)'] },
    { m: 6, d: 20,    items: ['IVA del 2.º trimestre (303)', 'Pago fraccionado de IRPF (130 o 131)', 'Retenciones (111 y 115)'] },
    { m: 6, d: 25,    items: ['Impuesto sobre Sociedades (200)'] },
    { m: 9, d: 20,    items: ['IVA del 3.er trimestre (303)', 'Pago fraccionado de IRPF (130 o 131)', 'Retenciones (111 y 115)'] }
  ];
  var MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
               'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  var FESTIVOS = ['01-01', '01-06', '05-01', '08-15', '10-12', '11-01', '12-06', '12-08', '12-25'];

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function inhabil(d) {
    var w = d.getDay();
    if (w === 0 || w === 6) return true;
    return FESTIVOS.indexOf(pad(d.getMonth() + 1) + '-' + pad(d.getDate())) !== -1;
  }
  function habil(d) {
    var out = new Date(d.getTime()), guard = 0;
    while (inhabil(out) && guard++ < 10) { out.setDate(out.getDate() + 1); }
    return out;
  }

  var nEl = document.getElementById('dl-days');
  if (!nEl) return;
  var uEl = document.getElementById('dl-unit');
  var dEl = document.getElementById('dl-date');
  var wEl = document.getElementById('dl-what');

  var now = new Date();
  var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  var next = null;
  for (var y = 0; y < 2 && !next; y++) {
    for (var i = 0; i < RULES.length; i++) {
      var r = RULES[i];
      var yr = today.getFullYear() + y;
      var day = r.d === 'fin' ? new Date(yr, r.m + 1, 0).getDate() : r.d;
      var dt = habil(new Date(yr, r.m, day));
      if (dt >= today) { next = { date: dt, rule: r }; break; }
    }
  }
  if (!next) return;

  var days = Math.round((next.date - today) / 86400000);
  if (days === 0) {
    nEl.textContent = 'Hoy';
    nEl.style.fontSize = '42px';
    if (uEl) uEl.textContent = 'es el último día';
  } else {
    nEl.textContent = days;
    if (uEl) uEl.textContent = days === 1 ? 'día' : 'días';
  }
  if (dEl) {
    dEl.textContent = next.date.getDate() + ' de ' + MESES[next.date.getMonth()] +
                      ' de ' + next.date.getFullYear();
  }
  if (wEl) { wEl.textContent = next.rule.items.join(' · '); }
})();
