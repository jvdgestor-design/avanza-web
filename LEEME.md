# ENCARGO de revisión · herencia EN, dos ejemplos de competencia y opción normativa (19/11/2026)

Para: ChatGPT/Codex (paso 2, revisión en el chat con Jose; no al vigilante automático).
Redactor: Claude (Opus). Rama de trabajo `claude/herencia-en-dos-ejemplos`, commit `2f5ffc000e288959cff41fcb95695ede1e539347`, sobre main `233f6d4`. Sin PR todavía.

## Qué cambia
Solo `inheritance-spain-non-resident-heir.html`, sección «What is taxed in Spain, and under which rules»: cuatro párrafos nuevos tras el párrafo de la opción (DA 2ª). Diff en `cambio.diff`; versión exacta en `inheritance-spain-non-resident-heir.html.txt`; base en `base-...html.txt`; huellas en `huellas.txt`.

No se toca: title, meta, og, H1, JSON-LD, fechas, la 210 (#123), la sección «Inheritance law and inheritance tax» (Reglamento 650/2012), herencia ES/DE/FR/RU. Sin CTA nuevo (el bloque de encargo y el CTA final ya están en la página). Sin cifras, tipos, precios ni promesa de ahorro.

## Afirmaciones a revisar (tabla)
| # | Afirmación del texto | Fuente |
|---|---|---|
| 1 | La residencia en una comunidad se fija por el mayor número de días de los cinco años anteriores | Ley 29/1987 DA 2ª.Uno.2 |
| 2 | Heredero no residente: el impuesto no se cede a la comunidad; modelo 650 ante la AEAT | Ley 22/2009 art. 32.2 (cesión solo para sujetos pasivos residentes); cuadro AEAT fila residente/no residente: ESTATAL |
| 3 | Causante residente en la Comunitat, heredero no residente: puede optar por la normativa valenciana en vez de la estatal | DA 2ª.Uno.1.b; cuadro AEAT «Opción: ESTATAL / CC. AA. de residencia causante» |
| 4 | Reino Unido fuera de la UE no impide la opción | FAQ AEAT no residentes: «Pueden optar por la normativa autonómica, tanto los residentes en la Unión Europea y el Espacio Económico Europeo, como los residentes en países terceros» |
| 5 | Ambos no residentes: 650 ante la AEAT; tributa solo por lo situado en España | Cuadro AEAT fila no residente/no residente: ESTATAL; Ley 29/1987 art. 7 |
| 6 | Opción por la comunidad con el mayor valor de todos los bienes y derechos del caudal relicto situados en España, no solo la vivienda ni solo el lote del heredero | DA 2ª.Uno.1.a («caudal relicto situados en España») |
| 7 | Es opción, no obligación; se calcula con ambas antes de elegir | Cuadro AEAT («Opción»); FAQ AEAT («será por la que opte el sujeto pasivo») |
| 8 | Valencia y Madrid son régimen común (fuera de País Vasco y Navarra) | Ya en la página, sección «Who deals with it» |

## Fuentes leídas hoy (19/11/2026)
- Ley 29/1987, DA 2ª, texto consolidado BOE (versión vigente desde 11/07/2021, BOE-A-2021-11473), consultado 22:18: https://www.boe.es/buscar/act.php?id=BOE-A-1987-28141#segunda
  - Uno.1.a literal: «si el causante hubiera sido no residente en España, los contribuyentes tendrán derecho a la aplicación de la normativa propia aprobada por la Comunidad Autónoma en donde se encuentre el mayor valor de los bienes y derechos del caudal relicto situados en España».
  - Uno.1.b literal: «si el causante hubiera sido residente en una Comunidad Autónoma, los contribuyentes no residentes tendrán derecho a la aplicación de la normativa propia aprobada por dicha Comunidad Autónoma».
  - Uno.2 literal: «cuando permanezcan en su territorio un mayor número de días del período de los cinco años inmediatos anteriores, contados de fecha a fecha, que finalice el día anterior al de devengo».
- Ley 22/2009, art. 32.2, BOE consolidado (vigente desde 20/12/2009), consultado 22:18: https://www.boe.es/buscar/act.php?id=BOE-A-2009-20375#a32 — literal: «Se considera producido en el territorio de una Comunidad Autónoma el rendimiento del Impuesto sobre Sucesiones y Donaciones de los sujetos pasivos residentes en España».
- AEAT, cuadro de delimitación de competencias (Sucesiones, régimen común), leído en Chrome el 19/11: filas RESIDENTE/NO RESIDENTE «ESTATAL · Opción: ESTATAL / CC. AA. de residencia causante» y NO RESIDENTE/NO RESIDENTE «ESTATAL · Opción: ESTATAL / CC. AA. con el mayor valor de los bienes situados en España».
- AEAT, FAQ no residentes ISD, pregunta «¿Puedo aplicar la normativa autonómica…?», leída en Chrome el 19/11 (frase literal en la fila 4).
- Ley 29/1987 art. 7: no releído hoy; el texto ya estaba en la página y la cita es la misma que el párrafo anterior.

## Pruebas
- `salud.py --raiz .`: 194 URL, errores 0, avisos 0.
- `pytest .github/motor/tests`: 214 passed.
- Parser HTML sin errores. Términos vetados (lawyer, solicitor, chartered, €): 0 en el añadido.
- No medido: render a 390 px (solo párrafos de texto dentro de `.prose`).

## Cerrojo
La sección «ley de la sucesión» (Reglamento 650/2012) se fusionó el 17/11 y no se toca; el cambio va en otra sección. #123 sin tocar.

## Qué se pide
Repaso con la tabla en SÍ/NO sobre la versión exacta (md5 `356d922212e872e61f72660b1fe19154`). Si VERDE, Claude escribe la última mirada y el REPASO-CLAUDE, sella y fusiona. Sin envío de indexación.
