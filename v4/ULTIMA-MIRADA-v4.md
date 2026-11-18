# Última mirada de Claude · 210 ES y EN «qué declaras según el uso del inmueble» v4 · ANTES del merge (18/11/2026, 16:15 Madrid)

## Versión exacta
- Commit 562df5c9ffa6f2f0455797b0abaff2b0a0b51839 (rama `claude/210-orientacion`; v1 4c402aa → v2 8671a0c → v3 1671288 → sello v3 e1a1504 → v4), base main 3f9135aa14c889a3c4337e49de1daa77ca4dde38. main sigue en 3f9135a a las 16:14 Madrid: las dos páginas no han cambiado desde la base.
- modelo-210-no-residentes.html · blob f8434e47394f101c718105b3fc02d7dceec1f0e3 · MD5 ae22c547e813f543270e903ebc3b5f38 · SHA-256 755fa3628368438bc55c535b9f45a4d9a111947a0fea1ffbbadf5025249d067c
- modelo-210-non-resident-tax-spain.html · blob bb34a5e023b50a74357a098e6950c67329ac5a7f · MD5 a5fe3473a6aa11a4ef04ebc7bf257b7c · SHA-256 189ce3ffdd4c2042b5398b301128ba7d41c11fba41b9f12a7c375ad195154fa8
- MD5 del diff base→v4: 7e121f684aad99d9a562e2c9d04ccaa3. Paquetes v1-v4 en `revision/210-uso-inmueble` (no se fusiona).

## Revisión
- Paso 2 de ChatGPT v4 (16:14 Madrid): «Repaso: Modelo210 uso inmueble v4 · md5 ae22c547e813f543270e903ebc3b5f38 · md5 a5fe3473a6aa11a4ef04ebc7bf257b7c · 0 NO · 0 reparos · revisor ChatGPT»; sello.py comprobar VERDE en los dos (REPASO-CHATGPT_v4.md y v4.SELLO.json, carpeta local de ChatGPT). Sus MD5 coinciden con el commit.
- Puerta 5 del PR #160 sobre v3 (run 44332295814): BLOQUEA por la remisión falsa al cálculo; resuelto en v4 (la remisión al «apartado siguiente» es solo para por qué se declara; porcentajes y proporción por días, a las preguntas frecuentes, comprobado que están allí). Los COMPROBAR (cita AEAT literal, art. 59.2 TRLRHL) están cotejados en fuente; los de la FAQ antigua quedan fuera del cambio.
- Lección: toda remisión interna («apartado siguiente», «más abajo») se contrasta con el contenido real del destino antes de dar la versión por buena.

## Comprobaciones finales
- Fuentes leídas el 18/11/2026: AEAT (índice de tributación de inmuebles, renta imputada, ganancia patrimonial, instrucciones del 210); TRLIRNR 25.2, TRLRHL 59.2 y LIRPF 85.1 en el BOE.
- Congelados intactos: title, meta, H1, entradillas y FAQ. dateModified: ES 2026-11-18 (ya estaba); EN 2026-11-17 → 2026-11-18.
- salud.py 0 errores, 0 avisos; render v4 a 390 y 1366 px sin desborde.
- Se publica: sello sobre 562df5c, fusion.py, Puerta 5 del PR #160 y, si no bloquea por el propio cambio, merge y «Después de publicar». Efecto en visibilidad o citas: NO CALCULABLE.
