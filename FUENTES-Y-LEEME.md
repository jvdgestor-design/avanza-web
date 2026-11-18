# Paquete de revisión · 210 ES y EN «qué declaras según el uso del inmueble» · v1 (18/11/2026)

Versión: rama `claude/210-orientacion`, commit 4c402aa7f5d82b490ef754776ff527e2f76df640, base main 3f9135aa14c889a3c4337e49de1daa77ca4dde38. Sin PR. Huellas en `huellas.txt`; HTML base y resultado como .html.txt (bytes idénticos); vistas a 390 y 1366 px (PNG).

## Hueco detectado (main 3f9135a)
- Ninguna de las dos páginas trata el uso mixto (alquilado solo parte del año): búsqueda de «mixto/mixed/prorrat/parte del año/part of the year» sin resultados sobre ese supuesto.
- Enlaces que faltaban: la ES no enlazaba plusvalia-municipal-no-residente.html ni comprar-inmueble-a-no-residente-modelo-211.html (0 enlaces); la EN no enlazaba plusvalia-tax-spain-non-resident.html (0). El alquiler ES solo estaba enlazado en el pie.
- No había un punto que separe los cuatro usos (propio o vacío, alquiler, alquiler parcial, venta) con su trámite.

## Cambio
- Una sección nueva (h2 + párrafo + lista de 4) justo antes de «El piso vacío también declara» / «An empty property must also be declared». No toca title, meta, H1 ni entradillas (congeladas), ni FAQ.
- EN: dateModified 2026-11-17 → 2026-11-18 (cambia contenido). ES ya tenía 2026-11-18.
- salud.py 0/0; desborde 0 a 390 y 1366 px (Playwright).

## Fuentes (leídas el 18/11/2026)
1. AEAT, «Cuestiones específicas sobre tributación de inmuebles» (índice): https://sede.agenciatributaria.gob.es/Sede/no-residentes/irnr-sin-establecimiento-permanente/cuestiones-especificas-sobre-tributacion-inmuebles.html — apartados «Renta imputada de inmueble urbano para uso propio», «Rendimientos de inmuebles arrendados», «Ganancia patrimonial derivada de la transmisión».
2. AEAT, «Renta imputada de inmueble urbano para uso propio», literal: «El importe resultante se entiende referido a todo el año natural. Se reducirá proporcionalmente al número de días, cuando no haya tenido la titularidad durante todo el año, o cuando durante parte del mismo haya estado arrendado.» https://sede.agenciatributaria.gob.es/Sede/no-residentes/irnr-sin-establecimiento-permanente/cuestiones-especificas-sobre-tributacion-inmuebles/renta-imputada-inmueble-urbano-uso-propio.html (en la EN se enlaza su versión en_gb, que la página ya citaba).
3. AEAT, «Ganancia patrimonial derivada de la transmisión», literal: «resultarán de aplicación la obligación de retención por parte del adquirente del inmueble (a través del modelo 211) así como la de presentación de la declaración (modelo 210 subapartado H) e ingreso de la deuda tributaria correspondiente.»
4. TRLIRNR (RDL 5/2004) art. 25.2, vigente desde 01/01/2015, norma_leer 18/11/2026 15:48: «Tratándose de transmisiones de bienes inmuebles situados en territorio español por contribuyentes que actúen sin establecimiento permanente, el adquirente estará obligado a retener e ingresar el 3 por ciento, o a efectuar el ingreso a cuenta correspondiente, de la contraprestación acordada, en concepto de pago a cuenta del impuesto correspondiente a aquéllos.»
5. TRLRHL (RDL 2/2004) art. 59.2, vigente desde 10/03/2004, norma_leer 18/11/2026 15:50: «Asimismo, los ayuntamientos podrán establecer y exigir el Impuesto sobre Construcciones, Instalaciones y Obras y el Impuesto sobre el Incremento de Valor de los Terrenos de Naturaleza Urbana…».
6. Contexto (no citado en el texto): LIRPF art. 85.1 (vigente desde 02/10/2026; versiones desde 01/01/2027 anotadas en el BOE), norma_leer 18/11/2026 15:48: imputación de inmuebles «ni generadores de rendimientos del capital… determinándose proporcionalmente al número de días que corresponda en cada período impositivo».

Rama de revisión: no se fusiona nunca.
