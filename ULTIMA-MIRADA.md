# REPASO-CLAUDE · Herencia EN dos ejemplos v1 — última mirada ANTES del merge (19/11/2026)

Escrita antes de sellar, abrir el PR y fusionar.

## Versión
Rama `claude/herencia-en-dos-ejemplos`, commit `2f5ffc000e288959cff41fcb95695ede1e539347`, sobre main `233f6d47306de05bd4461aa2a7489d16337027e2` (main no se ha movido desde el paso 2).

| Fichero | MD5 | SHA-256 |
|---|---|---|
| inheritance-spain-non-resident-heir.html | 356d922212e872e61f72660b1fe19154 | a9e6f84e9911b2d14f7b02c62370d4983d0d3050b05b5d840dfe807028d8e87a |

Es el mismo md5 que cotejó ChatGPT en el paso 2.

## Repaso y sello de ChatGPT
- Repaso: `REVISIONES/de-chatgpt/2026-11-19_AVANZA-WEB_Herencia-EN-dos-ejemplos-v1_REPASO.md` (AVANZA COMUN): 10 hechos, 10 documentados, 0 NO, 0 reparos.
- Línea VERDE literal, transmitida por Codex: «VERDE · REVISADO · FALTA TU CRITERIO · Herencia EN dos ejemplos v1 · md5 356d9222 · tabla toda en SÍ, cita el md5 de lo que sale y nada tocado despues · comprobado19/11/2026 22:25».
- Fuentes consultadas por ChatGPT el 19/11: BOE Ley 29/1987 arts. 6, 7 y DA 2ª; Ley 22/2009 arts. 28 y 32; cuadro de competencias y FAQ de no residentes de la AEAT.
- Fuentes leídas por Claude el 19/11: BOE consolidado Ley 29/1987 DA 2ª (vigente desde 11/07/2021) y Ley 22/2009 art. 32 (22:18); cuadro y FAQ AEAT en Chrome. Texto literal en LEEME.md.

## Última mirada (Claude)
- El diff contra main son solo los cuatro párrafos; title, meta, og, H1, JSON-LD, fechas, sección del Reglamento 650/2012 y enlace a la 210 sin cambios.
- Presentación: render local con Chrome a 390 px y a 1366 px, sin desbordamiento horizontal, párrafos justificados, enlace a la AEAT visible (capturas herencia-en-ejemplos-390.png y -1366.png).
- salud.py 0/0; pytest motor 214 pasan.
- Comparar ambas normativas va como recomendación práctica, no como requisito legal ni promesa de ahorro (matiz de Codex, de acuerdo).
- Observación no bloqueante: el párrafo de valoración que sigue a los ejemplos cita «(article 9.3)» sin repetir «Law 29/1987»; el párrafo anterior a él ya no nombra la ley. Se deja para una pasada futura del cuerpo con su propia revisión ligera; no se toca esta versión.
- Puerta 5 del push en rojo solo por falta de créditos de la API (runs 44617771713 y 44617890844): no revisó nada. Se fusiona con el repaso limpio según el punto 6 de las instrucciones del proyecto.

## Fallo comprobado y prevención (de la propuesta, corregido antes de redactar)
1. La propuesta decía que se «aplica» la normativa valenciana por la DA 2ª. Falso en la forma: la DA 2ª.Uno.1 da al no residente derecho a optar («tendrán derecho a la aplicación»); la AEAT lo recoge como «Opción: ESTATAL / CC. AA.». Prevención: en Sucesiones con no residentes, escribir siempre «puede optar» y nunca «se aplica».
2. La propuesta decía que, si el heredero reside en España, gestiona la comunidad. Falso si el causante no residía en España: el cuadro AEAT da competencia ESTATAL en no residente/residente; la cesión del art. 32.2 Ley 22/2009 exige sujeto pasivo residente y punto de conexión en la residencia del causante. Prevención: la competencia se decide con las dos residencias (causante y heredero) a la vez, contra el cuadro de la AEAT, antes de redactar.

## Resultado
Sin reparos pendientes. Se sella sobre el commit 2f5ffc0 y se fusiona sin envío manual de indexación.
