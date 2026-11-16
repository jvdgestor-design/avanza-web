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
// P01: renta imputada de 2025: 1 abril a 31 diciembre del año siguiente (2026)
var p1 = C.calculaImputada(base).plazo;
igual('P01 imputada 2025', [p1.desde, p1.hasta], ['2026-04-01', '2026-12-31']);
// P02: alquiler 2025 con cuota a ingresar: 1 a 20 de abril de 2026
var p2 = C.calculaAlquiler(ba).plazo;
igual('P02 alquiler a ingresar', [p2.desde, p2.hasta], ['2026-04-01', '2026-04-20']);
// P03: alquiler 2024 con cuota cero: 1 a 20 de enero de 2025
var p3 = C.calculaAlquiler(con(ba, { anio: 2024, ingresos: '100', gastos: '200', residencia: 'UE' })).plazo;
igual('P03 alquiler cuota cero', [p3.desde, p3.hasta], ['2025-01-01', '2025-01-20']);

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
