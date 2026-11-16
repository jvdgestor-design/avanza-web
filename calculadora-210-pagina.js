/* Interfaz de la calculadora del modelo 210. Todo el cálculo está en calculadora-210.js.
   No hace llamadas externas, no guarda nada y no usa cookies. */
(function () {
  'use strict';
  var C = window.Calculadora210;
  var f = document.getElementById('calc210');
  if (!C || !f) { return; }
  var $ = function (id) { return document.getElementById(id); };
  var salida = $('calc-resultado');
  var radios = f.querySelectorAll('input[name="supuesto"]');
  var campos = ['anio', 'residencia', 'caso', 'valor', 'dias', 'titularidad', 'ingresos', 'gastos'];

  function supuesto() { var r = f.querySelector('input[name="supuesto"]:checked'); return r ? r.value : 'A'; }

  function muestra() {
    var a = supuesto() === 'A';
    $('bloque-A').hidden = !a; $('bloque-B').hidden = a;
    salida.innerHTML = ''; limpiaMarcas();
    $('lbl-valor').textContent = etiquetaValor();
  }
  function etiquetaValor() {
    return $('caso').value === 'sinCatastral'
      ? 'El mayor entre el valor comprobado por la Administración a efectos de otros tributos y el precio o valor de adquisición (euros)'
      : 'Valor catastral del inmueble (euros)';
  }
  function limpiaMarcas() { campos.forEach(function (c) { var e = $(c); if (e) { e.removeAttribute('aria-invalid'); } }); }
  function esc(t) { return String(t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function fila(k, v) { return '<div><dt>' + esc(k) + '</dt><dd>' + esc(v) + '</dd></div>'; }

  function pinta(r) {
    limpiaMarcas();
    if (!r.ok) {
      var h = '<div class="calc-err" role="alert"><p><strong>Revise estos datos:</strong></p><ul>';
      r.errores.forEach(function (e) {
        h += '<li><a href="#' + esc(e.campo) + '">' + esc(e.mensaje) + '</a></li>';
        var el = $(e.campo); if (el) { el.setAttribute('aria-invalid', 'true'); }
      });
      salida.innerHTML = h + '</ul></div>';
      var primero = $(r.errores[0].campo); if (primero) { primero.focus(); }
      return;
    }
    var d = '<dl class="calc-dl">';
    if (r.supuesto === 'imputada') {
      d += fila(r.caso === 'sinCatastral' ? 'Valor tomado (mayor valor indicado)' : 'Valor catastral', C.formatoEuros(r.valorCents));
      d += fila('Porcentaje aplicado (art. 85.1 Ley 35/2006)', r.porcentaje + ' %' + (r.caso === 'sinCatastral' ? ' sobre el 50 % del valor' : ''));
      d += fila('Días a disposición', r.dias + ' de ' + r.diasAnio);
      d += fila('Renta imputada del inmueble', C.formatoEuros(r.rentaCents));
    } else {
      d += fila('Ingresos íntegros', C.formatoEuros(r.ingresosCents));
      d += fila('Gastos deducidos', C.formatoEuros(r.gastosAplicadosCents));
      d += fila('Rendimiento (ingresos menos gastos)', C.formatoEuros(r.rendimientoCents));
    }
    d += fila('Titularidad', C.formatoPorcentaje(r.titularidadCentesimas));
    d += fila('Base imponible de este titular', C.formatoEuros(r.baseCents));
    d += fila('Tipo de gravamen (art. 25.1.a)', r.tipo + ' %');
    d += '<div class="calc-total"><dt>Cuota orientativa de este titular</dt><dd>' + esc(C.formatoEuros(r.cuotaCents)) + '</dd></div></dl>';
    d += '<p><strong>Plazo de presentación:</strong> ' + esc(r.plazo.texto) + '. <span class="calc-pe">Según el ' + esc(r.plazo.articulo) + '.</span></p>';
    var hoy = new Date().toISOString().slice(0, 10);
    if (r.plazo.hasta < hoy) {
      d += '<p class="calc-av">Ese plazo ya ha terminado. Esta calculadora no calcula recargos, intereses ni sanciones.</p>';
    }
    if (r.avisos.length) {
      d += '<ul class="calc-av">'; r.avisos.forEach(function (a) { d += '<li>' + esc(a) + '</li>'; }); d += '</ul>';
    }
    d += '<p class="calc-pe">Resultado orientativo, calculado en su navegador con la norma leída el ' + esc(C.NORMA_LEIDA) + '. No sustituye a la declaración.</p>';
    salida.innerHTML = d;
    salida.setAttribute('tabindex', '-1'); salida.focus();
  }

  function entradas() {
    var v = function (id) { return $(id).value; };
    if (supuesto() === 'A') {
      return { anio: v('anio'), residencia: v('residencia'), caso: v('caso'), valor: v('valor'), dias: v('dias'), titularidad: v('titularidad') };
    }
    return { anio: v('anio'), residencia: v('residencia'), ingresos: v('ingresos'), gastos: v('gastos'), titularidad: v('titularidad') };
  }

  f.addEventListener('submit', function (ev) {
    ev.preventDefault();
    pinta(supuesto() === 'A' ? C.calculaImputada(entradas()) : C.calculaAlquiler(entradas()));
  });
  f.addEventListener('reset', function () { setTimeout(muestra, 0); });
  Array.prototype.forEach.call(radios, function (r) { r.addEventListener('change', muestra); });
  $('caso').addEventListener('change', function () { $('lbl-valor').textContent = etiquetaValor(); });
  muestra();
})();
