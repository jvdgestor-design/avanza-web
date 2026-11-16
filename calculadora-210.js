/*
 * Calculadora orientativa del modelo 210 (IRNR, persona física sin establecimiento permanente).
 * Funciones puras, sin dependencias, sin acceso al DOM, a la red ni a cookies.
 * Norma aplicada (texto consolidado del BOE, leído el 16/11/2026):
 *   TRLIRNR (RDLeg 5/2004) arts. 24.1, 24.5, 24.6 y 25.1.a
 *   LIRPF (Ley 35/2006) art. 85 (redacción vigente a 16/11/2026) y art. 11.3
 *   Orden EHA/3316/2010, art. 5 (redacción de la Orden HAC/623/2026)
 * Aritmética exacta en céntimos con BigInt; redondeo a céntimos, medio céntimo hacia arriba,
 * en cada etapa (renta o rendimiento, base por titular, cuota).
 */
(function (raiz, fabrica) {
  'use strict';
  var api = fabrica();
  if (typeof module === 'object' && module.exports) { module.exports = api; }
  else { raiz.Calculadora210 = api; }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var ANIO_MIN = 2015; // el art. 85 y el art. 24.6 se leen en su redacción vigente desde 01/01/2015
  var ANIO_MAX = 2026; // el art. 85 cambia desde 01/01/2027 (escala): fuera de esta calculadora
  var NORMA_LEIDA = '16/11/2026';
  var MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
    'septiembre', 'octubre', 'noviembre', 'diciembre'];

  function esBisiesto(a) { return (a % 4 === 0 && a % 100 !== 0) || a % 400 === 0; }
  function diasDelAnio(a) { return esBisiesto(a) ? 366 : 365; }

  // División entera con redondeo de medio hacia arriba (solo no negativos).
  function divRedondeo(num, den) { return (num * 2n + den) / (2n * den); }

  // Convierte texto o número a un entero escalado (céntimos si decimales = 2).
  // Acepta coma o punto decimal; si hay ambos, el último es el decimal y el otro es de miles.
  function leeDecimal(valor, decimales) {
    if (valor === null || valor === undefined) { return { vacio: true }; }
    var t = String(valor).replace(/[\s €%]/g, '');
    if (t === '') { return { vacio: true }; }
    var signo = 1;
    if (t.charAt(0) === '-') { signo = -1; t = t.slice(1); }
    else if (t.charAt(0) === '+') { t = t.slice(1); }
    var uc = t.lastIndexOf(','), up = t.lastIndexOf('.');
    var sep = Math.max(uc, up), ent, dec;
    if (uc >= 0 && up >= 0) {
      ent = t.slice(0, sep).replace(/[.,]/g, ''); dec = t.slice(sep + 1);
    } else if (sep >= 0) {
      if (t.indexOf(t.charAt(sep)) !== sep) { return { malo: true }; } // dos separadores iguales
      ent = t.slice(0, sep); dec = t.slice(sep + 1);
    } else { ent = t; dec = ''; }
    if (!/^\d*$/.test(ent) || !/^\d*$/.test(dec) || (ent === '' && dec === '')) { return { malo: true }; }
    if (dec.length > decimales) { return { demasiadosDecimales: true }; }
    while (dec.length < decimales) { dec += '0'; }
    return { n: BigInt(ent === '' ? '0' : ent) * (10n ** BigInt(decimales)) + BigInt(dec === '' ? '0' : dec), signo: signo };
  }

  function importe(valor, etiqueta, errores, campo, opciones) {
    var r = leeDecimal(valor, 2);
    if (r.vacio) {
      if (opciones && opciones.opcional) { return 0n; }
      errores.push({ campo: campo, mensaje: 'Indique ' + etiqueta + '.' }); return null;
    }
    if (r.malo) { errores.push({ campo: campo, mensaje: etiqueta.charAt(0).toUpperCase() + etiqueta.slice(1) + ': escriba solo números (coma o punto decimal).' }); return null; }
    if (r.demasiadosDecimales) { errores.push({ campo: campo, mensaje: etiqueta.charAt(0).toUpperCase() + etiqueta.slice(1) + ': como máximo dos decimales. Si ha escrito los miles con punto (100.000), escríbalos sin él (100000) o añada los decimales (100.000,00).' }); return null; }
    if (r.signo < 0 && r.n !== 0n) { errores.push({ campo: campo, mensaje: etiqueta.charAt(0).toUpperCase() + etiqueta.slice(1) + ' no puede ser negativo.' }); return null; }
    if (opciones && opciones.positivo && r.n === 0n) { errores.push({ campo: campo, mensaje: 'Indique ' + etiqueta + ' (mayor que cero).' }); return null; }
    return r.n;
  }

  function anioValido(v, errores) {
    var s = String(v === null || v === undefined ? '' : v).trim();
    if (s === '') { errores.push({ campo: 'anio', mensaje: 'Indique el año de devengo.' }); return null; }
    if (!/^\d{4}$/.test(s)) { errores.push({ campo: 'anio', mensaje: 'El año de devengo debe tener cuatro cifras.' }); return null; }
    var a = parseInt(s, 10);
    if (a > ANIO_MAX) {
      errores.push({ campo: 'anio', mensaje: 'Esta calculadora solo recoge años de devengo hasta ' + ANIO_MAX + ': la redacción del artículo 85 de la Ley 35/2006 cambia desde el 01/01/2027 y no se aplica aquí.' });
      return null;
    }
    if (a < ANIO_MIN) {
      errores.push({ campo: 'anio', mensaje: 'Esta calculadora solo recoge años de devengo desde ' + ANIO_MIN + ' (redacción vigente de las normas leídas).' });
      return null;
    }
    return a;
  }

  function titularidadValida(v, errores) {
    var r = leeDecimal(v, 2);
    if (r.vacio) { errores.push({ campo: 'titularidad', mensaje: 'Indique el porcentaje de titularidad (de 0 a 100).' }); return null; }
    if (r.malo) { errores.push({ campo: 'titularidad', mensaje: 'Porcentaje de titularidad: escriba solo números (coma o punto decimal).' }); return null; }
    if (r.demasiadosDecimales) { errores.push({ campo: 'titularidad', mensaje: 'Porcentaje de titularidad: como máximo dos decimales.' }); return null; }
    if ((r.signo < 0 && r.n !== 0n) || r.n > 10000n) { errores.push({ campo: 'titularidad', mensaje: 'El porcentaje de titularidad debe estar entre 0 y 100.' }); return null; }
    return r.n; // centésimas de por ciento: 0..10000
  }

  function residenciaValida(v, errores) {
    if (v === 'UE' || v === 'EEE' || v === 'OTRO') { return v; }
    errores.push({ campo: 'residencia', mensaje: 'Indique el país de residencia fiscal (UE, Islandia/Noruega/Liechtenstein, u otro).' });
    return null;
  }

  function tipoGravamen(res) { return res === 'OTRO' ? 24 : 19; } // art. 25.1.a

  function fechaTexto(d, m, a) { return d + ' de ' + MESES[m - 1] + ' de ' + a; }

  // Orden EHA/3316/2010, art. 5 (redacción de la Orden HAC/623/2026).
  function plazo(supuesto, anio, cuotaCents) {
    var s = anio + 1;
    if (supuesto === 'imputada') { // art. 5.b)
      return { desde: s + '-04-01', hasta: s + '-12-31',
        texto: 'del 1 de abril al 31 de diciembre de ' + s + ' (presentación e ingreso)',
        articulo: 'artículo 5.b) de la Orden EHA/3316/2010' };
    }
    if (cuotaCents > 0n) { // art. 5.c).1.º, segundo inciso: inmuebles arrendados con resultado a ingresar
      return { desde: s + '-04-01', hasta: s + '-04-20',
        texto: 'del 1 al 20 de abril de ' + s + ' (presentación e ingreso)',
        articulo: 'artículo 5.c).1.º de la Orden EHA/3316/2010' };
    }
    return { desde: s + '-01-01', hasta: s + '-01-20', // art. 5.c).2.º, cuota cero
      texto: 'del 1 al 20 de enero de ' + s + ' (autoliquidación de cuota cero)',
      articulo: 'artículo 5.c).2.º de la Orden EHA/3316/2010' };
  }

  var AVISO_EEE = 'Se ha aplicado el 19 % por residir en Islandia, Noruega o Liechtenstein (EEE). El artículo 25.1.a) lo condiciona a que exista un efectivo intercambio de información tributaria con España y esta calculadora no lo comprueba: confírmelo antes de contar con este tipo.';

  function calculaImputada(e) {
    e = e || {};
    var errores = [], avisos = [];
    var anio = anioValido(e.anio, errores);
    var residencia = residenciaValida(e.residencia, errores);
    var caso = e.caso;
    if (caso !== 'normal' && caso !== 'revisado' && caso !== 'sinCatastral') {
      errores.push({ campo: 'caso', mensaje: 'Indique si el valor catastral fue revisado en el plazo que fija la norma, o si el inmueble no tiene valor catastral notificado.' });
      caso = null;
    }
    var valor = importe(e.valor, caso === 'sinCatastral'
      ? 'el mayor entre el valor comprobado por la Administración a efectos de otros tributos y el precio o valor de adquisición'
      : 'el valor catastral', errores, 'valor', { positivo: true });
    var tit = titularidadValida(e.titularidad, errores);
    var dias = null, dAnio = anio ? diasDelAnio(anio) : null;
    var sd = String(e.dias === null || e.dias === undefined ? '' : e.dias).trim();
    if (sd === '') { errores.push({ campo: 'dias', mensaje: 'Indique los días del año en que el inmueble estuvo a su disposición.' }); }
    else if (!/^\d+$/.test(sd)) { errores.push({ campo: 'dias', mensaje: 'Los días deben ser un número entero (sin decimales ni signo).' }); }
    else {
      dias = parseInt(sd, 10);
      if (dias < 1) { errores.push({ campo: 'dias', mensaje: 'Los días deben ser al menos 1.' }); dias = null; }
      else if (dAnio !== null && dias > dAnio) {
        errores.push({ campo: 'dias', mensaje: 'El año ' + anio + ' tiene ' + dAnio + ' días: no puede indicar ' + dias + '.' }); dias = null;
      }
    }
    if (errores.length) { return { ok: false, errores: errores }; }

    var sin = caso === 'sinCatastral';
    var pctBp = caso === 'normal' ? 200n : 110n; // art. 85.1: 2 % o 1,1 %, en centésimas de por ciento
    var den = 10000n * BigInt(dAnio) * (sin ? 2n : 1n); // en el caso sin valor catastral se toma el 50 %
    var renta = divRedondeo(valor * pctBp * BigInt(dias), den);
    var base = divRedondeo(renta * tit, 10000n);
    var tipo = tipoGravamen(residencia);
    var cuota = divRedondeo(base * BigInt(tipo), 100n);
    if (residencia === 'EEE') { avisos.push(AVISO_EEE); }
    if (tit === 0n) { avisos.push('Con una titularidad del 0 % no hay renta que imputar.'); }
    if (e.anio !== undefined && anio === ANIO_MAX) {
      avisos.push('El año ' + ANIO_MAX + ' es el ejercicio en curso a la fecha de la norma leída; compruebe que el resultado final de los días coincide con la realidad.');
    }
    return {
      ok: true, supuesto: 'imputada', anio: anio, caso: caso, porcentaje: caso === 'normal' ? '2' : '1,1',
      valorCents: valor, dias: dias, diasAnio: dAnio, rentaCents: renta, titularidadCentesimas: tit,
      baseCents: base, tipo: tipo, cuotaCents: cuota, plazo: plazo('imputada', anio, cuota), avisos: avisos
    };
  }

  function calculaAlquiler(e) {
    e = e || {};
    var errores = [], avisos = [];
    var anio = anioValido(e.anio, errores);
    var residencia = residenciaValida(e.residencia, errores);
    var ingresos = importe(e.ingresos, 'los ingresos íntegros', errores, 'ingresos', { positivo: true });
    var gastosVacios = (e.gastos === undefined || e.gastos === null || String(e.gastos).trim() === '');
    var gastos = importe(e.gastos, 'los gastos deducibles', errores, 'gastos', { opcional: true });
    var tit = titularidadValida(e.titularidad, errores);
    if (errores.length) { return { ok: false, errores: errores }; }

    var deduce = residencia === 'UE' || residencia === 'EEE'; // art. 24.6; resto, art. 24.1 sin gastos
    var gastosAplicados = deduce ? gastos : 0n;
    if (!deduce && gastos > 0n) {
      avisos.push('Los gastos que ha indicado no se han deducido: el artículo 24.1 fija la base en el importe íntegro para quien no reside en la UE ni en el EEE.');
    }
    if (deduce && gastosVacios) { avisos.push('No ha indicado gastos: se calcula sin deducir ninguno.'); }
    var neto = ingresos - gastosAplicados;
    if (neto < 0n) {
      neto = 0n;
      avisos.push('Los gastos indicados superan a los ingresos: la base resulta cero. La calculadora no traslada excesos a otros años ni a otros inmuebles; si los gastos de intereses y reparación exceden de los ingresos, el artículo 23.1.a).1.º de la Ley 35/2006 prevé su aplicación en los cuatro años siguientes y aquí no se calcula.');
    }
    var base = divRedondeo(neto * tit, 10000n);
    var tipo = tipoGravamen(residencia);
    var cuota = divRedondeo(base * BigInt(tipo), 100n);
    if (residencia === 'EEE') { avisos.push(AVISO_EEE); }
    if (tit === 0n) { avisos.push('Con una titularidad del 0 % no hay renta que declarar.'); }
    return {
      ok: true, supuesto: 'alquiler', anio: anio, ingresosCents: ingresos, gastosAplicadosCents: gastosAplicados,
      rendimientoCents: neto, titularidadCentesimas: tit, baseCents: base, tipo: tipo, cuotaCents: cuota,
      plazo: plazo('alquiler', anio, cuota), avisos: avisos
    };
  }

  // 123456 -> "1.234,56 €" (solo enteros no negativos en céntimos).
  function formatoEuros(c) {
    var n = BigInt(c), ent = (n / 100n).toString(), dec = (n % 100n).toString();
    if (dec.length < 2) { dec = '0' + dec; }
    ent = ent.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return ent + ',' + dec + ' €';
  }
  function formatoPorcentaje(centesimas) {
    var n = BigInt(centesimas), ent = (n / 100n).toString(), dec = (n % 100n).toString();
    if (dec.length < 2) { dec = '0' + dec; }
    dec = dec.replace(/0+$/, '');
    return ent + (dec ? ',' + dec : '') + ' %';
  }

  return {
    ANIO_MIN: ANIO_MIN, ANIO_MAX: ANIO_MAX, NORMA_LEIDA: NORMA_LEIDA,
    esBisiesto: esBisiesto, diasDelAnio: diasDelAnio, leeDecimal: leeDecimal,
    calculaImputada: calculaImputada, calculaAlquiler: calculaAlquiler,
    formatoEuros: formatoEuros, formatoPorcentaje: formatoPorcentaje
  };
});
