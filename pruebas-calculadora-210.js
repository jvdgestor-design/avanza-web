'use strict';
// Pruebas de la calculadora del modelo 210. Ejecutar: node pruebas-calculadora-210.js
// Cada caso lleva la cuenta hecha a mano (importes en euros en el comentario; se comparan en céntimos).
var C = require('./calculadora-210.js');
var total = 0, fallos = [];

function igual(nombre, real, esperado) {
  total++;
  var a = typeof real === 'bigint' ? real.toString() + 'n' : JSON.stringify(real);
  var b = typeof esperado === 'bigint' ? esperado.toString() + 'n' : JSON.stringify(esperado);
  if (a !== b) { fallos.push(nombre + ': esperado ' + b + ', obtenido ' + a); console.log('FALLA  ' + nombre + '  esperado ' + b + '  obtenido ' + a); }
  else { console.log('ok     ' + nombre); }
}
function imp(nombre, entrada, renta, base, cuota) {
  var r = C.calculaImputada(entrada);
  if (!r.ok) { total++; fallos.push(nombre + ': devolvio error ' + JSON.stringify(r.errores)); console.log('FALLA  ' + nombre + '  error inesperado ' + JSON.stringify(r.errores)); return r; }
  igual(nombre + ' [renta]', r.rentaCents, renta);
  igual(nombre + ' [base]', r.baseCents, base);
  igual(nombre + ' [cuota]', r.cuotaCents, cuota);
  return r;
}
function alq(nombre, entrada, base, cuota) {
  var r = C.calculaAlquiler(entrada);
  if (!r.ok) { total++; fallos.push(nombre + ': devolvio error ' + JSON.stringify(r.errores)); console.log('FALLA  ' + nombre + '  error inesperado ' + JSON.stringify(r.errores)); return r; }
  igual(nombre + ' [base]', r.baseCents, base);
  igual(nombre + ' [cuota]', r.cuotaCents, cuota);
  return r;
}
function error(nombre, r, campo) {
  total++;
  var ok = r.ok === false && r.errores.some(function (x) { return x.campo === campo && x.mensaje.length > 5; });
  if (!ok) { fallos.push(nombre + ': se esperaba error en ' + campo + ', salio ' + JSON.stringify(r).slice(0, 200)); console.log('FALLA  ' + nombre); }
  else { console.log('ok     ' + nombre + '  -> ' + r.errores.filter(function (x) { return x.campo === campo; })[0].mensaje); }
}

var base = { anio: 2025, caso: 'normal', valor: '100000', dias: 365, titularidad: '100', residencia: 'OTRO' };
function con(o, cambios) { var r = {}; Object.keys(o).forEach(function (k) { r[k] = o[k]; }); Object.keys(cambios).forEach(function (k) { r[k] = cambios[k]; }); return r; }

console.log('--- (A) renta imputada ---');
// A01: 100.000 x 2 % = 2.000,00; x365/365 = 2.000,00; 100 %: base 2.000,00; 24 %: 480,00
imp('A01 2 % y 24 %', base, 200000n, 200000n, 48000n);
// A02: igual con residente UE: 19 % de 2.000,00 = 380,00
imp('A02 2 % y 19 % (UE)', con(base, { residencia: 'UE' }), 200000n, 200000n, 38000n);
// A03: valor revisado, 1,1 %: 100.000 x 1,1 % = 1.100,00; 24 % = 264,00
imp('A03 1,1 % y 24 %', con(base, { caso: 'revisado' }), 110000n, 110000n, 26400n);
// A04: 1,1 % y 19 %: 1.100,00 x 19 % = 209,00
imp('A04 1,1 % y 19 %', con(base, { caso: 'revisado', residencia: 'UE' }), 110000n, 110000n, 20900n);
// A05: 2024 es bisiesto, 366 días de 366: 2.000,00; 24 % = 480,00
imp('A05 366 dias en 2024', con(base, { anio: 2024, dias: 366 }), 200000n, 200000n, 48000n);
// A06: 2024, 183 días: 2.000,00 x 183/366 = 1.000,00; 19 % = 190,00
imp('A06 183/366 dias', con(base, { anio: 2024, dias: 183, residencia: 'UE' }), 100000n, 100000n, 19000n);
// A07: 1 día en 2025, valor 73.000: 73.000 x 2 % = 1.460,00; /365 = 4,00; 24 % = 0,96
imp('A07 1 dia', con(base, { valor: '73000', dias: 1 }), 400n, 400n, 96n);
// A08: titularidad 50 %: renta 2.000,00; base 1.000,00; 24 % = 240,00
imp('A08 50 % titularidad', con(base, { titularidad: '50' }), 200000n, 100000n, 24000n);
// A09: 12.345,67 x 1,1 % = 135,80237 -> 135,80; 19 % de 135,80 = 25,802 -> 25,80
imp('A09 redondeo 1,1 %', con(base, { valor: '12345,67', caso: 'revisado', residencia: 'UE' }), 13580n, 13580n, 2580n);
// A10: sin valor catastral: mayor valor 200.000 x 50 % = 100.000; x 1,1 % = 1.100,00; 24 % = 264,00
imp('A10 sin valor catastral', con(base, { valor: '200000', caso: 'sinCatastral' }), 110000n, 110000n, 26400n);
// A11: 100 días en 2025: 2.000,00 x 100/365 = 547,945205... -> 547,95; 19 % = 104,1105 -> 104,11
imp('A11 prorrateo 100/365', con(base, { dias: 100, residencia: 'UE' }), 54795n, 54795n, 10411n);
// A12: borde de medio céntimo: 1.000,25 x 2 % = 20,005 -> 20,01 (medio hacia arriba); 24 % de 20,01 = 4,8024 -> 4,80
imp('A12 renta .005 sube', con(base, { valor: '1000,25' }), 2001n, 2001n, 480n);
// A13: titularidad 33,33 %: renta 90.000 x 2 % = 1.800,00; x 33,33 % = 599,94; 24 % = 143,9856 -> 143,99
imp('A13 titularidad 33,33 %', con(base, { valor: '90000', titularidad: '33,33' }), 180000n, 59994n, 14399n);
// A14: base de .005 en cuota: renta 2,50 (125 de valor catastral x 2 % = 2,50) -> 19 % = 0,475 -> 0,48
imp('A14 cuota .005 sube', con(base, { valor: '125', residencia: 'UE' }), 250n, 250n, 48n);
// A15: coma de miles y de decimales: "1.234.567,89" no es válido (dos puntos de miles sin coma única) -> se interpreta con ambos separadores
imp('A15 miles y coma', con(base, { valor: '1.234.567,89' }), 2469136n, 2469136n, 592593n);
// 1.234.567,89 x 2 % = 24.691,3578 -> 24.691,36 (2469136 cént.); x 24 % = 5.925,9264 -> 5.925,93 (592593 cént.)

console.log('--- (B) alquiler ---');
var ba = { anio: 2025, ingresos: '12000', gastos: '3000', titularidad: '100', residencia: 'OTRO' };
// B01: resto del mundo, gastos no se deducen: base 12.000,00; 24 % = 2.880,00
var b1 = alq('B01 resto sin gastos', ba, 1200000n, 288000n);
igual('B01 aviso de gastos no deducidos', b1.avisos.length, 1);
// B02: UE: 12.000 - 3.000 = 9.000,00; 19 % = 1.710,00
alq('B02 UE con gastos', con(ba, { residencia: 'UE' }), 900000n, 171000n);
// B03: gastos mayores que ingresos: base 0, cuota 0, aviso, plazo de cuota cero
var b3 = alq('B03 gastos > ingresos', con(ba, { residencia: 'UE', ingresos: '5000', gastos: '6000' }), 0n, 0n);
igual('B03 aviso presente', b3.avisos.length >= 1, true);
igual('B03 plazo cuota cero', b3.plazo.hasta, '2026-01-20');
// B04: titularidad 50 %: (12.000 - 2.000) = 10.000; base 5.000,00; 19 % = 950,00
alq('B04 UE 50 %', con(ba, { residencia: 'UE', gastos: '2000', titularidad: '50' }), 500000n, 95000n);
// B05: ingresos 2,50: 19 % = 0,475 -> 0,48
alq('B05 cuota .005 sube', con(ba, { residencia: 'UE', ingresos: '2,50', gastos: '0' }), 250n, 48n);
// B06: ingresos 0,03, 24 %: 0,0072 -> 0,01
alq('B06 cuota 0,0072 sube', con(ba, { ingresos: '0,03' }), 3n, 1n);
// B07: EEE deduce gastos: 10.000 - 1.000 = 9.000,00; 19 % = 1.710,00; con aviso del EEE
var b7 = alq('B07 EEE con gastos', con(ba, { residencia: 'EEE', ingresos: '10000', gastos: '1000' }), 900000n, 171000n);
igual('B07 aviso EEE', b7.avisos.some(function (t) { return /intercambio/.test(t); }), true);
// B08: titularidad 0 %: base 0, cuota 0, con aviso
var b8 = alq('B08 titularidad 0', con(ba, { titularidad: '0' }), 0n, 0n);
igual('B08 aviso', b8.avisos.length >= 1, true);
// B09: 1.234,56 x 24 % = 296,2944 -> 296,29
alq('B09 coma y miles', con(ba, { ingresos: '1.234,56' }), 123456n, 29629n);
// B10: gastos vacíos en UE: sin gastos y con aviso; 8.000 x 19 % = 1.520,00
var b10 = alq('B10 gastos vacios', con(ba, { residencia: 'UE', ingresos: '8000', gastos: '' }), 800000n, 152000n);
igual('B10 aviso', b10.avisos.length, 1);
// B11: gastos justo igual a ingresos: base 0 sin aviso de exceso
var b11 = alq('B11 gastos = ingresos', con(ba, { residencia: 'UE', ingresos: '4000', gastos: '4000' }), 0n, 0n);
igual('B11 sin aviso de exceso', b11.avisos.length, 0);
// B12: 24 % sobre 0,02 = 0,0048 -> 0,00
alq('B12 cuota 0,0048 baja', con(ba, { ingresos: '0,02' }), 2n, 0n);

console.log('--- plazos (Orden EHA/3316/2010, art. 5) ---');
// P01: renta imputada de 2025: año natural siguiente (1 enero a 31 diciembre de 2026), según nota AEAT; el plazo de abril solo rige para devengos de 2026
var p1 = C.calculaImputada(base).plazo;
igual('P01 imputada 2025', [p1.desde, p1.hasta], ['2026-01-01', '2026-12-31']);
// P02: alquiler 2025 con cuota a ingresar: 1-20 enero de 2026 si se agrupa (art. 5.c).1.º, redacción HAC/56/2024) o trimestral; último día posible 20/01/2026
var p2 = C.calculaAlquiler(ba).plazo;
igual('P02 alquiler 2025', [p2.hasta, /agrupa/.test(p2.texto), /trimestre/.test(p2.texto)], ['2026-01-20', true, true]);
// P03: alquiler 2024 con cuota cero: 1 a 20 de enero de 2025
var p3 = C.calculaAlquiler(con(ba, { anio: 2024, ingresos: '100', gastos: '200', residencia: 'UE' })).plazo;
igual('P03 alquiler cuota cero', [p3.desde, p3.hasta], ['2025-01-01', '2025-01-20']);

console.log('--- (C) reparo 1: criterio del 1,1 % por año de devengo ---');
var cuenta = function (anioDev, anioRev) { return C.aplica11(anioDev, anioRev) ? 'revisado' : 'normal'; };
// C01: devengo 2025, municipio revisado en 2013: DA 55.ª (desde 01/01/2012) -> 1,1 %: 100.000 x 1,1 % = 1.100,00; 24 % = 264,00
igual('C01 aplica11(2025, 2013)', C.aplica11(2025, 2013), true);
imp('C01 2025 revisado 2013 -> 1,1 %', con(base, { caso: cuenta(2025, 2013) }), 110000n, 110000n, 26400n);
// C02: devengo 2025, revisado en 2010: antes de 2012 -> no aplica el 1,1 %: 2 % = 2.000,00; 24 % = 480,00
igual('C02 aplica11(2025, 2010)', C.aplica11(2025, 2010), false);
imp('C02 2025 revisado 2010 -> 2 %', con(base, { caso: cuenta(2025, 2010) }), 200000n, 200000n, 48000n);
// C03: devengo 2020 (366 días), revisado en 2010: art. 85 (devengo y diez anteriores: 2010 a 2020) -> sí 1,1 %: 1.100,00 x 366/366; 24 % = 264,00
igual('C03 aplica11(2020, 2010)', C.aplica11(2020, 2010), true);
imp('C03 2020 revisado 2010 -> 1,1 %', con(base, { anio: 2020, dias: 366, caso: cuenta(2020, 2010) }), 110000n, 110000n, 26400n);
// C04: devengo 2020, revisado en 2009: fuera de los diez anteriores -> 2 %: 2.000,00; 24 % = 480,00
igual('C04 aplica11(2020, 2009)', C.aplica11(2020, 2009), false);
imp('C04 2020 revisado 2009 -> 2 %', con(base, { anio: 2020, dias: 366, caso: cuenta(2020, 2009) }), 200000n, 200000n, 48000n);
// C05: devengo 2022, revisado en 2012: art. 85 (2012 a 2022) -> 1,1 %: 1.100,00; 24 % = 264,00
igual('C05 aplica11(2022, 2012)', C.aplica11(2022, 2012), true);
imp('C05 2022 revisado 2012 -> 1,1 %', con(base, { anio: 2022, caso: cuenta(2022, 2012) }), 110000n, 110000n, 26400n);
// C06: devengo 2022, revisado en 2011: fuera (2011 < 2012) -> 2 %: 2.000,00; 480,00
igual('C06 aplica11(2022, 2011)', C.aplica11(2022, 2011), false);
imp('C06 2022 revisado 2011 -> 2 %', con(base, { anio: 2022, caso: cuenta(2022, 2011) }), 200000n, 200000n, 48000n);
// C07: devengo 2023, revisado en 2012: DA 55.ª (desde 2012; con la regla de diez años sería 2013) -> 1,1 %: 1.100,00; 264,00
igual('C07 aplica11(2023, 2012)', C.aplica11(2023, 2012), true);
imp('C07 2023 revisado 2012 -> 1,1 %', con(base, { anio: 2023, caso: cuenta(2023, 2012) }), 110000n, 110000n, 26400n);
// C08: devengo 2023, revisado en 2011 -> 2 %: 2.000,00; 480,00
igual('C08 aplica11(2023, 2011)', C.aplica11(2023, 2011), false);
imp('C08 2023 revisado 2011 -> 2 %', con(base, { anio: 2023, caso: cuenta(2023, 2011) }), 200000n, 200000n, 48000n);
igual('C08 aplica11(2023, 2011)', C.aplica11(2023, 2011), false);
// C09: la pregunta cambia con el año
igual('C09 pregunta 2023-2026 menciona 2012', /1 de enero de 2012/.test(C.preguntaRevision(2024)), true);
igual('C09 pregunta 2015-2022 menciona diez anteriores', /diez anteriores/.test(C.preguntaRevision(2022)) && !/2012/.test(C.preguntaRevision(2022)), true);
igual('C09 desde2012 2022/2023/2026/2027', [C.desde2012(2022), C.desde2012(2023), C.desde2012(2026), C.desde2012(2027)], [false, true, true, false]);
// C10: devengo 2024 bisiesto, 183 días, 1,1 %: 100.000 x 1,1 % = 1.100,00 x 183/366 = 550,00; 24 % = 132,00
imp('C10 2024 1,1 % 183 días', con(base, { anio: 2024, dias: 183, caso: 'revisado' }), 55000n, 55000n, 13200n);

console.log('--- (D) reparo 3: Liechtenstein ---');
var li = con(base, { residencia: 'LI' });
// D01: Liechtenstein 2020 (366 días): 24 %: 100.000 x 2 % = 2.000,00; 24 % = 480,00 (no 19 %)
var d1 = imp('D01 LI 2020 imputada 24 %', con(li, { anio: 2020, dias: 366 }), 200000n, 200000n, 48000n);
igual('D01 aviso LI anterior a 11/07/2021', d1.avisos.length === 1 && /11\/07\/2021/.test(d1.avisos[0]), true);
// D02: Liechtenstein 2022: 19 %: 2.000,00 x 19 % = 380,00
imp('D02 LI 2022 imputada 19 %', con(li, { anio: 2022 }), 200000n, 200000n, 38000n);
// D03: Liechtenstein 2021 imputada (devengo 31/12/2021, posterior al 11/07/2021): 19 % = 380,00
imp('D03 LI 2021 imputada 19 %', con(li, { anio: 2021 }), 200000n, 200000n, 38000n);
// D04: Islandia/Noruega 2020: 19 % (sin cambio): 380,00
imp('D04 EEE 2020 imputada 19 %', con(base, { residencia: 'EEE', anio: 2020, dias: 366 }), 200000n, 200000n, 38000n);
// D05: alquiler Liechtenstein 2020: 12.000 íntegros (gastos 3.000 no se deducen); 24 % = 2.880,00
var d5 = alq('D05 LI 2020 alquiler sin gastos 24 %', con(ba, { residencia: 'LI', anio: 2020 }), 1200000n, 288000n);
igual('D05 avisos (gastos no deducidos + LI)', d5.avisos.length, 2);
// D06: alquiler Liechtenstein 2022: 12.000 - 3.000 = 9.000,00; 19 % = 1.710,00
alq('D06 LI 2022 alquiler con gastos 19 %', con(ba, { residencia: 'LI', anio: 2022 }), 900000n, 171000n);
// D07: alquiler Liechtenstein 2021: mezcla de fechas anteriores y posteriores al 11/07/2021: no se calcula
var d7 = C.calculaAlquiler(con(ba, { residencia: 'LI', anio: 2021 }));
error('D07 LI 2021 alquiler no da resultado', d7, 'residencia');
igual('D07 mensaje', /no da resultado/.test(d7.errores[0].mensaje), true);
// D08: alquiler Islandia/Noruega 2020 sigue deduciendo gastos: 12.000 - 3.000 = 9.000,00; 19 % = 1.710,00
alq('D08 EEE 2020 alquiler con gastos', con(ba, { residencia: 'EEE', anio: 2020 }), 900000n, 171000n);
// D09: el aviso del EEE ya no dice que no se comprueba, sino el criterio de la AEAT
var d9 = C.calculaImputada(con(base, { residencia: 'EEE' }));
igual('D09 aviso EEE', /criterio publicado por la Agencia Tributaria/.test(d9.avisos[0]), true);

console.log('--- (E) reparo 2 y 5: plazos por año de devengo ---');
var plz = function (r) { return [r.plazo.desde, r.plazo.hasta]; };
// E01: imputada 2025 -> 01/01/2026 a 31/12/2026 (AEAT: "no varía"); imputada 2024 -> 2025; imputada 2015 se rechaza
igual('E01 imputada 2025', plz(C.calculaImputada(con(base, { anio: 2025 }))), ['2026-01-01', '2026-12-31']);
igual('E01 imputada 2024', plz(C.calculaImputada(con(base, { anio: 2024 }))), ['2025-01-01', '2025-12-31']);
var e1r = C.calculaImputada(con(base, { anio: 2015 }));
error('E01 imputada 2015 se rechaza', e1r, 'anio');
igual('E01 mensaje 2015', e1r.errores[0].mensaje, 'Esta calculadora solo recoge años de devengo desde 2016 (redacción vigente de las normas leídas).');
igual('E01 imputada 2016', plz(C.calculaImputada(con(base, { anio: 2016 }))), ['2017-01-01', '2017-12-31']);
// E02: imputada 2026 -> 01/04/2027 a 31/12/2027 (HAC/623/2026, DF única 2.b)
var e2 = C.calculaImputada(con(base, { anio: 2026 }));
igual('E02 imputada 2026', plz(e2), ['2027-04-01', '2027-12-31']);
igual('E02 artículo cita HAC/623/2026', /HAC\/623\/2026/.test(e2.plazo.articulo), true);
// E03: alquiler 2023: trimestral; último día posible 20/01/2024; texto trimestral
var e3 = C.calculaAlquiler(con(ba, { anio: 2023 }));
igual('E03 alquiler 2023', [e3.plazo.hasta, /trimestre natural/.test(e3.plazo.texto), /agrupa/.test(e3.plazo.texto)], ['2024-01-20', true, false]);
// E04: alquiler 2015 se rechaza; 2016 trimestral (hasta 20/01/2017); 2019 igual
error('E04 alquiler 2015 se rechaza', C.calculaAlquiler(con(ba, { anio: 2015 })), 'anio');
igual('E04 alquiler 2016', C.calculaAlquiler(con(ba, { anio: 2016 })).plazo.hasta, '2017-01-20');
igual('E04 alquiler 2019', C.calculaAlquiler(con(ba, { anio: 2019 })).plazo.hasta, '2020-01-20');
// E05: alquiler 2024 y 2025: 1-20 enero si agrupa, o trimestral (HAC/56/2024)
var e5 = C.calculaAlquiler(con(ba, { anio: 2024 }));
igual('E05 alquiler 2024', [e5.plazo.hasta, /1 al 20 de enero de 2025 si se agrupa/.test(e5.plazo.texto), /HAC\/56\/2024/.test(e5.plazo.articulo)], ['2025-01-20', true, true]);
// E06: alquiler 2026: 1-20 abril de 2027 (agrupada) con la transición de los trimestres primero a tercero
var e6 = C.calculaAlquiler(con(ba, { anio: 2026 }));
igual('E06 alquiler 2026', [plz(e6), /primero a tercero de 2026/.test(e6.plazo.texto), /HAC\/623\/2026/.test(e6.plazo.articulo)], [['2027-04-01', '2027-04-20'], true, true]);
igual('E06 alquiler 2026: cuarto trimestre por separado', /si declara por separado las del cuarto trimestre de 2026/.test(e6.plazo.texto), true);
igual('E06 2015 y 2027 rechazados', [C.ANIO_MIN, C.ANIO_MAX], [2016, 2026]);
// E07: cuota cero igual en todos los años: 1-20 enero siguiente
var cz = con(ba, { residencia: 'UE', ingresos: '100', gastos: '200' });
igual('E07 cuota cero 2019', plz(C.calculaAlquiler(con(cz, { anio: 2019 }))), ['2020-01-01', '2020-01-20']);
igual('E07 cuota cero 2026', plz(C.calculaAlquiler(con(cz, { anio: 2026 }))), ['2027-01-01', '2027-01-20']);
// E08: reparo 5: con plazos trimestrales hasta es el último día posible, para el aviso de "plazo ya terminado" (alquiler 2019: 20/01/2020, pasado)
igual('E08 hasta alquiler 2019 anterior a hoy', C.calculaAlquiler(con(ba, { anio: 2019 })).plazo.hasta < new Date().toISOString().slice(0, 10), true);
// E09: año 2027 se rechaza también en alquiler, con el mensaje de devengos
var e9 = C.calculaAlquiler(con(ba, { anio: 2027 }));
error('E09 alquiler 2027', e9, 'anio');
igual('E09 mensaje', e9.errores[0].mensaje, 'Esta calculadora solo recoge devengos hasta 2026.');

console.log('--- (R) casos del revisor independiente (16/11/2026), con su cuenta a mano ---');
// R01: 2024, 2 %, 100.000, 366/366, 100 %, otro: 2.000,00; 24 % = 480,00
imp('R01', { anio: '2024', residencia: 'OTRO', caso: 'normal', valor: '100000', dias: '366', titularidad: '100' }, 200000n, 200000n, 48000n);
// R02: 1 día de 366: 2.000/366 = 5,4645 -> 5,46; 24 % = 1,3104 -> 1,31
imp('R02', { anio: '2024', residencia: 'OTRO', caso: 'normal', valor: '100000', dias: '1', titularidad: '100' }, 546n, 546n, 131n);
// R03: 2025, 1,1 %, 87.654,32, 365, 33,33 %, UE: 964,1975 -> 964,20; x 33,33 % = 321,3679 -> 321,37; 19 % = 61,0603 -> 61,06
var r03 = imp('R03', { anio: '2025', residencia: 'UE', caso: 'revisado', valor: '87654,32', dias: '365', titularidad: '33,33' }, 96420n, 32137n, 6106n);
igual('R03 plazo 2025', plz(r03), ['2026-01-01', '2026-12-31']);
// R04: alquiler 2026, otro, 9.600 sin gastos: 9.600,00; 24 % = 2.304,00; abril de 2027
var r04 = alq('R04', { anio: '2026', residencia: 'OTRO', ingresos: '9600', gastos: '', titularidad: '100' }, 960000n, 230400n);
igual('R04 plazo', r04.plazo.hasta, '2027-04-20');
// R05: alquiler 2026, UE, 5.000 - 7.000: base 0, cuota cero, 1-20 enero 2027, con aviso
var r05 = alq('R05', { anio: '2026', residencia: 'UE', ingresos: '5000', gastos: '7000', titularidad: '100' }, 0n, 0n);
igual('R05 plazo y aviso', [plz(r05), r05.avisos.length], [['2027-01-01', '2027-01-20'], 1]);
// R06: alquiler 2026, otro, 1.234,56, gastos 500 ignorados: 1.234,56 x 24 % = 296,2944 -> 296,29, con aviso
var r06 = alq('R06', { anio: '2026', residencia: 'OTRO', ingresos: '1.234,56', gastos: '500', titularidad: '100' }, 123456n, 29629n);
igual('R06 aviso', r06.avisos.length, 1);
// R07: todo vacío: seis errores
igual('R07 seis errores', C.calculaImputada({}).errores.length, 6);
// R08: días 0
error('R08 dias 0', C.calculaImputada({ anio: '2025', residencia: 'UE', caso: 'normal', valor: '100000', dias: '0', titularidad: '100' }), 'dias');
// R09: 999.999.999.999,99 x 2 % = 19.999.999.999,9998 -> 20.000.000.000,00; 24 % = 4.800.000.000,00
imp('R09', { anio: '2025', residencia: 'OTRO', caso: 'normal', valor: '999999999999,99', dias: '365', titularidad: '100' }, 2000000000000n, 2000000000000n, 480000000000n);
// R10: 2023, sin catastral, 200.000, 200 días, 50 %, EEE: 1.100 x 200/365 = 602,7397 -> 602,74; 301,37; 19 % = 57,2603 -> 57,26
imp('R10', { anio: '2023', residencia: 'EEE', caso: 'sinCatastral', valor: '200000', dias: '200', titularidad: '50' }, 60274n, 30137n, 5726n);
// R11: titularidad 33,333
error('R11 titularidad 3 decimales', C.calculaImputada({ anio: '2025', residencia: 'UE', caso: 'normal', valor: '100000', dias: '365', titularidad: '33,333' }), 'titularidad');
// R12: 2020 con 366 válido; 2021 con 366 error
imp('R12a 2020 con 366', { anio: '2020', residencia: 'UE', caso: 'normal', valor: '50000', dias: '366', titularidad: '100' }, 100000n, 100000n, 19000n);
error('R12b 2021 con 366', C.calculaImputada({ anio: '2021', residencia: 'UE', caso: 'normal', valor: '50000', dias: '366', titularidad: '100' }), 'dias');
// R13: 2018, Liechtenstein: 24 % (AEAT: 19 % solo desde 11/07/2021): 2.000,00 x 24 % = 480,00
imp('R13', { anio: '2018', residencia: 'LI', caso: 'normal', valor: '100000', dias: '365', titularidad: '100' }, 200000n, 200000n, 48000n);
// R14: alquiler 2025, UE, 12.000 - 3.000 = 9.000,00; 19 % = 1.710,00; plazo 1-20 enero 2026 (agrupación anual) o trimestral
var r14 = alq('R14', { anio: '2025', residencia: 'UE', ingresos: '12000', gastos: '3000', titularidad: '100' }, 900000n, 171000n);
igual('R14 plazo', [r14.plazo.hasta, /1 al 20 de enero de 2026/.test(r14.plazo.texto)], ['2026-01-20', true]);
// R14b: alquiler 2019, otro: plazo trimestral
var r14b = alq('R14b', { anio: '2019', residencia: 'OTRO', ingresos: '12000', gastos: '', titularidad: '100' }, 1200000n, 288000n);
igual('R14b plazo trimestral', /trimestre natural/.test(r14b.plazo.texto), true);
// R15: imputada 2025: 1 enero - 31 diciembre 2026
igual('R15 plazo', plz(C.calculaImputada({ anio: '2025', residencia: 'UE', caso: 'normal', valor: '100000', dias: '365', titularidad: '100' })), ['2026-01-01', '2026-12-31']);
// R16: valor 0,01, 1 día: 0,01 x 2 %/365 = 0,0000005 -> 0,00
imp('R16', { anio: '2025', residencia: 'UE', caso: 'normal', valor: '0,01', dias: '1', titularidad: '100' }, 0n, 0n, 0n);
// R17 / R18: "100.000" y "1.000.000" -> error de formato
error('R17', C.calculaImputada({ anio: '2025', residencia: 'UE', caso: 'normal', valor: '100.000', dias: '365', titularidad: '100' }), 'valor');
error('R18', C.calculaImputada({ anio: '2025', residencia: 'UE', caso: 'normal', valor: '1.000.000', dias: '365', titularidad: '100' }), 'valor');
// R19: espacios: 100.000 x 2 % = 2.000,00; 50 %: 1.000,00; 19 % = 190,00
imp('R19', { anio: '2025', residencia: 'UE', caso: 'normal', valor: '100000', dias: ' 365 ', titularidad: ' 50 ' }, 200000n, 100000n, 19000n);
// R20: números JS: 100000,5 x 2 % = 2.000,01; 19 % = 380,0019 -> 380,00
imp('R20', { anio: 2025, residencia: 'UE', caso: 'normal', valor: 100000.5, dias: 365, titularidad: 100 }, 200001n, 200001n, 38000n);
// R21: "1e5" error; R22: gastos "abc" error; R23: "-0" valor error (valor cero)
error('R21', C.calculaImputada({ anio: '2025', residencia: 'UE', caso: 'normal', valor: '1e5', dias: '365', titularidad: '100' }), 'valor');
error('R22', C.calculaAlquiler({ anio: '2025', residencia: 'OTRO', ingresos: '100', gastos: 'abc', titularidad: '100' }), 'gastos');
error('R23', C.calculaImputada({ anio: '2025', residencia: 'UE', caso: 'normal', valor: '-0', dias: '365', titularidad: '-0' }), 'valor');
// R24: ",5" = 0,50 x 2 % = 0,01; 19 % = 0,0019 -> 0,00
imp('R24', { anio: '2025', residencia: 'UE', caso: 'normal', valor: ',5', dias: '365', titularidad: '100' }, 1n, 1n, 0n);
// R25: alquiler 2026, UE, 0,02: 19 % = 0,0038 -> 0,00; cuota cero
alq('R25', { anio: '2026', residencia: 'UE', ingresos: '0,02', gastos: '', titularidad: '100' }, 2n, 0n);
// R26: 2026, 1,1 %, 120.000: 1.320,00; 19 % = 250,80
imp('R26', { anio: '2026', residencia: 'UE', caso: 'revisado', valor: '120000', dias: '365', titularidad: '100' }, 132000n, 132000n, 25080n);

console.log('--- validacion ---');
error('V01 valor catastral vacio', C.calculaImputada(con(base, { valor: '' })), 'valor');
error('V02 valor negativo', C.calculaImputada(con(base, { valor: '-5' })), 'valor');
error('V03 valor cero', C.calculaImputada(con(base, { valor: '0' })), 'valor');
error('V04 dias 0', C.calculaImputada(con(base, { dias: 0 })), 'dias');
error('V05 366 dias en 2025', C.calculaImputada(con(base, { dias: 366 })), 'dias');
error('V06 dias con decimales', C.calculaImputada(con(base, { dias: '1.5' })), 'dias');
error('V07 dias vacios', C.calculaImputada(con(base, { dias: '' })), 'dias');
error('V08 titularidad 101', C.calculaImputada(con(base, { titularidad: '101' })), 'titularidad');
error('V09 titularidad negativa', C.calculaImputada(con(base, { titularidad: '-1' })), 'titularidad');
error('V10 titularidad vacia', C.calculaImputada(con(base, { titularidad: '' })), 'titularidad');
error('V11 sin residencia', C.calculaImputada(con(base, { residencia: '' })), 'residencia');
error('V12 año 2027', C.calculaImputada(con(base, { anio: 2027 })), 'anio');
error('V13 año 2014', C.calculaImputada(con(base, { anio: 2014 })), 'anio');
error('V14 tres decimales', C.calculaImputada(con(base, { valor: '12,345' })), 'valor');
error('V15 texto en el valor', C.calculaImputada(con(base, { valor: 'abc' })), 'valor');
error('V16 sin caso', C.calculaImputada(con(base, { caso: undefined })), 'caso');
error('V17 alquiler ingresos vacios', C.calculaAlquiler(con(ba, { ingresos: '' })), 'ingresos');
error('V18 alquiler ingresos negativos', C.calculaAlquiler(con(ba, { ingresos: '-100' })), 'ingresos');
error('V19 alquiler gastos negativos', C.calculaAlquiler(con(ba, { gastos: '-1' })), 'gastos');
error('V20 alquiler titularidad 100,01', C.calculaAlquiler(con(ba, { titularidad: '100,01' })), 'titularidad');
error('V21 sin año', C.calculaAlquiler(con(ba, { anio: '' })), 'anio');
error('V22 dos puntos sin coma', C.calculaImputada(con(base, { valor: '1.234.567' })), 'valor');
// V22: "1.234.567" lleva dos puntos iguales: ambiguo, se rechaza en lugar de adivinar

console.log('--- utilidades ---');
// U01-U04: bisiestos: 2024 sí; 2100 no (divisible por 100 y no por 400); 2000 sí; 2025 no
igual('U01 2024', C.diasDelAnio(2024), 366);
igual('U02 2100', C.diasDelAnio(2100), 365);
igual('U03 2000', C.diasDelAnio(2000), 366);
igual('U04 2025', C.diasDelAnio(2025), 365);
// U05-U07: formato
igual('U05 formato 123456', C.formatoEuros(123456n), '1.234,56 €');
igual('U06 formato 5', C.formatoEuros(5n), '0,05 €');
igual('U07 porcentaje 3333', C.formatoPorcentaje(3333n), '33,33 %');
igual('U08 porcentaje 5000', C.formatoPorcentaje(5000n), '50 %');

console.log('');
console.log(total + ' comprobaciones, ' + fallos.length + ' fallos');
if (fallos.length) { process.exit(1); }
