/* Interfaz de la calculadora del modelo 210 en inglés y en alemán. Todo el cálculo está en calculadora-210.js;
   aquí solo se traducen sus mensajes por código. El idioma sale del atributo lang de la página.
   No hace llamadas externas, no guarda nada y no usa cookies. */
(function () {
  'use strict';
  var TXT = {
    en: {
      preguntaNueva: 'Have the cadastral values of the municipality been revised, modified or determined through a general collective valuation procedure that came into force on or after 1 January 2012?',
      preguntaAnt: 'Have the cadastral values of the municipality been revised, modified or determined through a general collective valuation procedure that came into force in the tax year or in the ten preceding years?',
      lblValor: 'Cadastral value of the property (euros)',
      lblValorSin: 'The higher of the value checked by the tax authorities for other taxes and the purchase price or acquisition value (euros)',
      campo: {
        valor: ['the cadastral value', 'Cadastral value'],
        valorSin: ['the higher of the value checked by the tax authorities for other taxes and the purchase price or acquisition value', 'Value'],
        ingresos: ['the gross rental income', 'Gross rental income'],
        gastos: ['the deductible expenses', 'Deductible expenses']
      },
      err: {
        vacio: 'Enter {x}.',
        malo: '{X}: use digits only (decimal comma or point).',
        decimales: '{X}: two decimal places at most. Write thousands without a separator (100000) or add the decimals (100,000.00).',
        negativo: '{X} cannot be negative.',
        cero: 'Enter {x} (greater than zero).',
        'titularidad.vacio': 'Enter the ownership percentage (0 to 100).',
        'titularidad.malo': 'Ownership percentage: use digits only (decimal comma or point).',
        'titularidad.decimales': 'Ownership percentage: two decimal places at most.',
        titRango: 'The ownership percentage must be between 0 and 100.',
        anioVacio: 'Select the tax year.',
        anioCifras: 'The tax year must have four digits.',
        anioMax: 'This calculator only covers tax years up to {max}.',
        anioMin: 'This calculator only covers tax years from {min} onwards (current wording of the rules read).',
        residencia: 'Select the owner’s country of tax residence (EU, Iceland or Norway, Liechtenstein, or other).',
        caso: 'Say whether the cadastral values of the municipality were revised on the date that applies to that year (see the question), or whether the property has no notified cadastral value.',
        diasVacio: 'Enter the number of days in the year the property was at your disposal.',
        diasEntero: 'Days must be a whole number (no decimals or sign).',
        diasMin: 'Days must be at least 1.',
        diasMax: '{anio} has {diasAnio} days: you cannot enter {dias}.',
        li2021: 'The calculator gives no result for this case: in 2021, residents of Liechtenstein are taxed at 24% with no expenses on income accrued before 11 July 2021, and at 19% with expenses on later income, and the calculator does not split income by accrual date.'
      },
      aviso: {
        eee: 'Iceland, Norway and Liechtenstein (the latter from 11 July 2021) are taxed at 19% and may deduct expenses, according to the criterion published by the Spanish Tax Agency on the effective exchange of information referred to in Article 25.1.a).',
        liAntes: 'Liechtenstein is taxed at 19% and may deduct expenses only from 11 July 2021: for this year 24% has been applied and no expenses are deducted, as for a resident of any other country.',
        tit0imp: 'With 0% ownership there is no income to impute.',
        tit0alq: 'With 0% ownership there is no income to declare.',
        anioCurso: '{max} was the current tax year on the date the rules were read; check that the final number of days matches what actually happened.',
        gastosNoLI: 'The expenses you entered have not been deducted: until 10 July 2021 a resident of Liechtenstein is treated like a resident of any other country (gross amount, Article 24.1).',
        gastosNo241: 'The expenses you entered have not been deducted: Article 24.1 sets the tax base at the gross amount for anyone not resident in the EU or the EEA.',
        sinGastos: 'You have not entered any expenses: the result is calculated without deducting any.',
        excesoGastos: 'The expenses entered exceed the income: the tax base is zero. The calculator does not carry excess amounts over to other years or other properties; where interest and repair expenses exceed the income, Article 23.1.a).1 of Law 35/2006 provides for them to be applied over the following four years, and that is not calculated here.'
      },
      plazo: {
        impNuevo: ['from 1 April to 31 December {s} (filing and payment)', 'Article 5.b) of Order EHA/3316/2010, as worded by Order HAC/623/2026 (income accrued in 2026)'],
        impAnt: ['from 1 January to 31 December {s} (filing and payment)', 'Article 5.b) of Order EHA/3316/2010, wording prior to Order HAC/623/2026 (the calendar year following accrual)'],
        cero: ['from 1 to 20 January {s} (zero-tax return)', 'Article 5.c).2 of Order EHA/3316/2010'],
        alq2026: ['from 1 to 20 April {s} (filing and payment), if you report the 2026 income grouped together or report the fourth quarter of 2026 separately. Income from the first to third quarters of 2026 reported separately had the quarterly deadline (April, July and October 2026)', 'Article 5.c).1 of Order EHA/3316/2010, as worded by Order HAC/623/2026 (income accrued in 2026)'],
        alq2024: ['from 1 to 20 January {s} if the year is grouped; if reported separately, the first twenty days of April, July, October and January following each quarter', 'Article 5.c).1 of Order EHA/3316/2010, as worded by Order HAC/56/2024'],
        alqTrim: ['quarterly: the first twenty days of April, July, October and January following each calendar quarter', 'Article 5.c).1 of Order EHA/3316/2010, original wording (in force since 2011)']
      },
      r: {
        revise: 'Check these fields:',
        valorSin: 'Value used (higher value entered)', valor: 'Cadastral value',
        pctNuevo: 'Percentage applied (Art. 85.1 and additional provision 55 of Law 35/2006)', pctAnt: 'Percentage applied (Art. 85.1 of Law 35/2006)',
        sobre50: ' of 50% of the value', dias: 'Days at your disposal', de: ' of ',
        renta: 'Imputed income from the property', ingresos: 'Gross income', gastos: 'Expenses deducted',
        rendimiento: 'Net income (income less expenses)', titularidad: 'Ownership', base: 'Tax base of this owner',
        tipo: 'Tax rate (Art. 25.1.a)', cuota: 'Indicative tax for this owner', plazo: 'Filing deadline:',
        segun: 'Under {art}.', vencido: 'That deadline has already passed. This calculator does not work out surcharges, interest or penalties.',
        pie: 'Indicative result, calculated in your browser with the rules as read on {fecha}. It does not replace the tax return.'
      },
      meses: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
      fecha: function (d, m, a, T) { return d + ' ' + T.meses[m - 1] + ' ' + a; },
      euros: function (ent, dec) { return '€' + ent.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + '.' + dec; },
      pct: function (ent, dec) { return ent + (dec ? '.' + dec : '') + '%'; }
    },
    de: {
      preguntaNueva: 'Wurden die Katasterwerte der Gemeinde durch ein allgemeines Verfahren der Kollektivbewertung überprüft, geändert oder festgesetzt, das ab dem 1. Januar 2012 in Kraft getreten ist?',
      preguntaAnt: 'Wurden die Katasterwerte der Gemeinde durch ein allgemeines Verfahren der Kollektivbewertung überprüft, geändert oder festgesetzt, das im Jahr der Steuerentstehung oder in den zehn vorangegangenen Jahren in Kraft getreten ist?',
      lblValor: 'Katasterwert der Immobilie (Euro)',
      lblValorSin: 'Der höhere Wert aus dem von der Verwaltung für andere Steuern geprüften Wert und dem Kaufpreis bzw. Anschaffungswert (Euro)',
      campo: {
        valor: ['den Katasterwert', 'Katasterwert'],
        valorSin: ['den höheren Wert aus dem von der Verwaltung für andere Steuern geprüften Wert und dem Kaufpreis bzw. Anschaffungswert', 'Wert'],
        ingresos: ['die Bruttomieteinnahmen', 'Bruttomieteinnahmen'],
        gastos: ['die abzugsfähigen Ausgaben', 'Abzugsfähige Ausgaben']
      },
      err: {
        vacio: 'Bitte geben Sie {x} an.',
        malo: '{X}: Bitte nur Ziffern eingeben (Dezimalkomma oder -punkt).',
        decimales: '{X}: höchstens zwei Nachkommastellen. Schreiben Sie Tausender ohne Trennzeichen (100000) oder mit Nachkommastellen (100.000,00).',
        negativo: '{X}: Der Betrag darf nicht negativ sein.',
        cero: 'Bitte geben Sie {x} an (größer als null).',
        'titularidad.vacio': 'Bitte geben Sie den Eigentumsanteil in Prozent an (0 bis 100).',
        'titularidad.malo': 'Eigentumsanteil: Bitte nur Ziffern eingeben (Dezimalkomma oder -punkt).',
        'titularidad.decimales': 'Eigentumsanteil: höchstens zwei Nachkommastellen.',
        titRango: 'Der Eigentumsanteil muss zwischen 0 und 100 liegen.',
        anioVacio: 'Bitte wählen Sie das Steuerjahr.',
        anioCifras: 'Das Steuerjahr muss vierstellig sein.',
        anioMax: 'Dieser Rechner erfasst nur Steuerjahre bis {max}.',
        anioMin: 'Dieser Rechner erfasst nur Steuerjahre ab {min} (geltende Fassung der gelesenen Vorschriften).',
        residencia: 'Bitte wählen Sie das Land der steuerlichen Ansässigkeit des Eigentümers (EU, Island oder Norwegen, Liechtenstein oder ein anderes Land).',
        caso: 'Bitte geben Sie an, ob die Katasterwerte der Gemeinde zu dem für dieses Jahr maßgeblichen Zeitpunkt überprüft wurden (siehe Frage) oder ob für die Immobilie kein Katasterwert mitgeteilt wurde.',
        diasVacio: 'Bitte geben Sie an, an wie vielen Tagen des Jahres Ihnen die Immobilie zur Verfügung stand.',
        diasEntero: 'Die Tage müssen eine ganze Zahl sein (ohne Nachkommastellen und Vorzeichen).',
        diasMin: 'Es muss mindestens 1 Tag sein.',
        diasMax: 'Das Jahr {anio} hat {diasAnio} Tage: {dias} ist nicht möglich.',
        li2021: 'Für diesen Fall liefert der Rechner kein Ergebnis: 2021 werden in Liechtenstein Ansässige für vor dem 11.07.2021 entstandene Einkünfte mit 24 % und ohne Ausgabenabzug besteuert, für spätere mit 19 % und mit Ausgabenabzug, und der Rechner teilt die Einnahmen nicht nach dem Entstehungszeitpunkt auf.'
      },
      aviso: {
        eee: 'Island, Norwegen und Liechtenstein (dieses ab dem 11.07.2021) werden mit 19 % besteuert und können Ausgaben abziehen, nach dem von der spanischen Steuerbehörde veröffentlichten Kriterium zum wirksamen Informationsaustausch des Artikels 25.1.a).',
        liAntes: 'Liechtenstein wird erst ab dem 11.07.2021 mit 19 % besteuert und kann erst ab dann Ausgaben abziehen: Für dieses Jahr wurden 24 % angewandt und keine Ausgaben abgezogen, wie bei Ansässigen jedes anderen Landes.',
        tit0imp: 'Bei einem Eigentumsanteil von 0 % gibt es keine zuzurechnenden Einkünfte.',
        tit0alq: 'Bei einem Eigentumsanteil von 0 % gibt es keine zu erklärenden Einkünfte.',
        anioCurso: '{max} war zum Zeitpunkt, zu dem die Vorschriften gelesen wurden, das laufende Steuerjahr; prüfen Sie, ob die endgültige Zahl der Tage den Tatsachen entspricht.',
        gastosNoLI: 'Die angegebenen Ausgaben wurden nicht abgezogen: Bis zum 10.07.2021 wird ein in Liechtenstein Ansässiger wie ein Ansässiger jedes anderen Landes behandelt (Bruttobetrag, Artikel 24.1).',
        gastosNo241: 'Die angegebenen Ausgaben wurden nicht abgezogen: Nach Artikel 24.1 ist die Bemessungsgrundlage der Bruttobetrag für alle, die weder in der EU noch im EWR ansässig sind.',
        sinGastos: 'Sie haben keine Ausgaben angegeben: Es wird ohne Abzug gerechnet.',
        excesoGastos: 'Die angegebenen Ausgaben übersteigen die Einnahmen: Die Bemessungsgrundlage ist null. Der Rechner überträgt keine Überschüsse auf andere Jahre oder andere Immobilien; übersteigen Zins- und Reparaturausgaben die Einnahmen, sieht Artikel 23.1.a).1 des Gesetzes 35/2006 ihre Berücksichtigung in den vier folgenden Jahren vor, was hier nicht berechnet wird.'
      },
      plazo: {
        impNuevo: ['vom 1. April bis 31. Dezember {s} (Abgabe und Zahlung)', 'Artikel 5.b) der Verordnung EHA/3316/2010 in der Fassung der Verordnung HAC/623/2026 (Einkünfte aus 2026)'],
        impAnt: ['vom 1. Januar bis 31. Dezember {s} (Abgabe und Zahlung)', 'Artikel 5.b) der Verordnung EHA/3316/2010, Fassung vor der Verordnung HAC/623/2026 (das auf die Steuerentstehung folgende Kalenderjahr)'],
        cero: ['vom 1. bis 20. Januar {s} (Erklärung mit Steuerbetrag null)', 'Artikel 5.c).2 der Verordnung EHA/3316/2010'],
        alq2026: ['vom 1. bis 20. April {s} (Abgabe und Zahlung), wenn Sie die Einkünfte aus 2026 zusammengefasst erklären oder das vierte Quartal 2026 gesondert erklären. Für gesondert erklärte Einkünfte des ersten bis dritten Quartals 2026 galt die Quartalsfrist (April, Juli und Oktober 2026)', 'Artikel 5.c).1 der Verordnung EHA/3316/2010 in der Fassung der Verordnung HAC/623/2026 (Einkünfte aus 2026)'],
        alq2024: ['vom 1. bis 20. Januar {s}, wenn das Jahr zusammengefasst wird; bei gesonderter Erklärung die ersten zwanzig Tage der Monate April, Juli, Oktober und Januar nach dem jeweiligen Quartal', 'Artikel 5.c).1 der Verordnung EHA/3316/2010 in der Fassung der Verordnung HAC/56/2024'],
        alqTrim: ['quartalsweise: die ersten zwanzig Tage der Monate April, Juli, Oktober und Januar nach dem jeweiligen Kalenderquartal', 'Artikel 5.c).1 der Verordnung EHA/3316/2010, ursprüngliche Fassung (seit 2011 in Kraft)']
      },
      r: {
        revise: 'Bitte prüfen Sie diese Angaben:',
        valorSin: 'Angesetzter Wert (höherer angegebener Wert)', valor: 'Katasterwert',
        pctNuevo: 'Angewandter Prozentsatz (Art. 85.1 und 55. Zusatzbestimmung des Gesetzes 35/2006)', pctAnt: 'Angewandter Prozentsatz (Art. 85.1 des Gesetzes 35/2006)',
        sobre50: ' auf 50 % des Werts', dias: 'Tage zur eigenen Verfügung', de: ' von ',
        renta: 'Zugerechnete Einkünfte aus der Immobilie', ingresos: 'Bruttoeinnahmen', gastos: 'Abgezogene Ausgaben',
        rendimiento: 'Ertrag (Einnahmen abzüglich Ausgaben)', titularidad: 'Eigentumsanteil', base: 'Bemessungsgrundlage dieses Eigentümers',
        tipo: 'Steuersatz (Art. 25.1.a)', cuota: 'Unverbindlicher Steuerbetrag dieses Eigentümers', plazo: 'Abgabefrist:',
        segun: 'Nach {art}.', vencido: 'Diese Frist ist bereits abgelaufen. Dieser Rechner berechnet keine Zuschläge, Zinsen oder Sanktionen.',
        pie: 'Unverbindliches Ergebnis, in Ihrem Browser berechnet, nach den am {fecha} gelesenen Vorschriften. Es ersetzt nicht die Steuererklärung.'
      },
      fecha: function (d, m, a) { return (d < 10 ? '0' : '') + d + '.' + (m < 10 ? '0' : '') + m + '.' + a; },
      euros: function (ent, dec) { return ent.replace(/\B(?=(\d{3})+(?!\d))/g, '.') + ',' + dec + ' €'; },
      pct: function (ent, dec) { return ent + (dec ? ',' + dec : '') + ' %'; }
    }
  };

  function rellena(t, d) { return t.replace(/\{(\w+)\}/g, function (m, k) { return d && d[k] !== undefined && d[k] !== null ? String(d[k]) : m; }); }

  // Traducción de un error, un aviso y un plazo del motor. Si falta un código, se devuelve el texto del motor.
  function textoError(T, e, caso) {
    var propio = T.err[e.campo + '.' + e.codigo];
    if (propio) { return rellena(propio, e.datos); }
    var t = T.err[e.codigo];
    if (!t) { return e.mensaje; }
    var c = T.campo[e.campo === 'valor' && caso === 'sinCatastral' ? 'valorSin' : e.campo];
    var d = {}; var k;
    if (e.datos) { for (k in e.datos) { if (Object.prototype.hasOwnProperty.call(e.datos, k)) { d[k] = e.datos[k]; } } }
    if (c) { d.x = c[0]; d.X = c[1]; }
    return rellena(t, d);
  }
  function textoAviso(T, codigo, original, C) { var t = T.aviso[codigo]; return t ? rellena(t, { max: C.ANIO_MAX }) : original; }
  function textoPlazo(T, p) {
    var t = T.plazo[p.clave];
    return t ? { texto: rellena(t[0], { s: p.anioSiguiente }), articulo: t[1] } : { texto: p.texto, articulo: p.articulo };
  }
  function euros(T, c) {
    var n = BigInt(c), ent = (n / 100n).toString(), dec = (n % 100n).toString();
    if (dec.length < 2) { dec = '0' + dec; }
    return T.euros(ent, dec);
  }
  function porcentaje(T, centesimas) {
    var n = BigInt(centesimas), ent = (n / 100n).toString(), dec = (n % 100n).toString();
    if (dec.length < 2) { dec = '0' + dec; }
    return T.pct(ent, dec.replace(/0+$/, ''));
  }
  function fechaNorma(T, C) { var p = String(C.NORMA_LEIDA).split('/'); return T.fecha(parseInt(p[0], 10), parseInt(p[1], 10), p[2], T); }

  var api = { TXT: TXT, textoError: textoError, textoAviso: textoAviso, textoPlazo: textoPlazo, euros: euros, porcentaje: porcentaje, fechaNorma: fechaNorma };
  if (typeof module === 'object' && module.exports) { module.exports = api; return; }

  var C = window.Calculadora210;
  var f = document.getElementById('calc210');
  if (!C || !f) { return; }
  var T = TXT[(document.documentElement.lang || 'en').slice(0, 2)] || TXT.en;
  var $ = function (id) { return document.getElementById(id); };
  var salida = $('calc-resultado');
  var radios = f.querySelectorAll('input[name="supuesto"]');
  var campos = ['anio', 'residencia', 'caso', 'valor', 'dias', 'titularidad', 'ingresos', 'gastos'];

  function supuesto() { var r = f.querySelector('input[name="supuesto"]:checked'); return r ? r.value : 'A'; }
  function etiquetaValor() { return $('caso').value === 'sinCatastral' ? T.lblValorSin : T.lblValor; }
  function actualizaPregunta() { var a = parseInt($('anio').value, 10); if (a) { $('lbl-caso').textContent = C.desde2012(a) ? T.preguntaNueva : T.preguntaAnt; } }
  function limpiaMarcas() { campos.forEach(function (c) { var e = $(c); if (e) { e.removeAttribute('aria-invalid'); } }); }
  function muestra() {
    var a = supuesto() === 'A';
    $('bloque-A').hidden = !a; $('bloque-B').hidden = a;
    salida.innerHTML = ''; limpiaMarcas();
    $('lbl-valor').textContent = etiquetaValor();
    actualizaPregunta();
  }
  function esc(t) { return String(t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function fila(k, v) { return '<div><dt>' + esc(k) + '</dt><dd>' + esc(v) + '</dd></div>'; }

  function pinta(r) {
    limpiaMarcas();
    if (!r.ok) {
      var h = '<div class="calc-err" role="alert"><p><strong>' + esc(T.r.revise) + '</strong></p><ul>';
      r.errores.forEach(function (e) {
        h += '<li><a href="#' + esc(e.campo) + '">' + esc(textoError(T, e, $('caso').value)) + '</a></li>';
        var el = $(e.campo); if (el) { el.setAttribute('aria-invalid', 'true'); }
      });
      salida.innerHTML = h + '</ul></div>';
      var primero = $(r.errores[0].campo); if (primero) { primero.focus(); }
      return;
    }
    var d = '<dl class="calc-dl">';
    if (r.supuesto === 'imputada') {
      d += fila(r.caso === 'sinCatastral' ? T.r.valorSin : T.r.valor, euros(T, r.valorCents));
      d += fila(r.anio >= 2023 ? T.r.pctNuevo : T.r.pctAnt, T.pct(r.porcentaje.split(',')[0], r.porcentaje.split(',')[1] || '') + (r.caso === 'sinCatastral' ? T.r.sobre50 : ''));
      d += fila(T.r.dias, r.dias + T.r.de + r.diasAnio);
      d += fila(T.r.renta, euros(T, r.rentaCents));
    } else {
      d += fila(T.r.ingresos, euros(T, r.ingresosCents));
      d += fila(T.r.gastos, euros(T, r.gastosAplicadosCents));
      d += fila(T.r.rendimiento, euros(T, r.rendimientoCents));
    }
    d += fila(T.r.titularidad, porcentaje(T, r.titularidadCentesimas));
    d += fila(T.r.base, euros(T, r.baseCents));
    d += fila(T.r.tipo, T.pct(String(r.tipo), ''));
    d += '<div class="calc-total"><dt>' + esc(T.r.cuota) + '</dt><dd>' + esc(euros(T, r.cuotaCents)) + '</dd></div></dl>';
    var p = textoPlazo(T, r.plazo);
    d += '<p><strong>' + esc(T.r.plazo) + '</strong> ' + esc(p.texto) + '. <span class="calc-pe">' + esc(rellena(T.r.segun, { art: p.articulo })) + '</span></p>';
    if (r.plazo.hasta < new Date().toISOString().slice(0, 10)) { d += '<p class="calc-av">' + esc(T.r.vencido) + '</p>'; }
    if (r.avisos.length) {
      d += '<ul class="calc-av">';
      r.avisos.forEach(function (a, i) { d += '<li>' + esc(textoAviso(T, (r.avisosCod || [])[i], a, C)) + '</li>'; });
      d += '</ul>';
    }
    d += '<p class="calc-pe">' + esc(rellena(T.r.pie, { fecha: fechaNorma(T, C) })) + '</p>';
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
  $('anio').addEventListener('change', actualizaPregunta);
  $('caso').addEventListener('change', function () { $('lbl-valor').textContent = etiquetaValor(); });
  muestra();
})();
