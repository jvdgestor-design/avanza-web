# Última mirada de Claude · EN botón al formulario v1 · escrita antes de fusionar

Versión: 9a5dac5fdac2ec1f821908ef1a834f928ebe5816 (rama claude/en-boton-formulario) · base y main actual 11d26856042b5c0efd79718cbeabf740544c65c0 (sin commits nuevos en main, sin solape) · diff MD5 bbf75f9ab604496172b8cdf8b7c77e99.
Paso 2: ChatGPT, REPASO-CHATGPT_v1.md y v1.SELLO.json VERDE para los 13 ficheros (18/11 18:56 Madrid), 10 SÍ, 0 NO, 0 reparos.
Cotejo de Claude: las 13 MD5 del «Repaso:» de ChatGPT coinciden una a una con las de HUELLAS.txt y con los ficheros del commit 9a5dac5 recalculados ahora (huella del listado 9732bd60af1989002de7f42a6c02af56 en los dos lados).
sello.py comprobar no se ha repetido desde aquí: esta sesión no tiene AVANZA COMUN conectada y no se pide el acceso; la línea VERDE es la del sello de ChatGPT sobre estos mismos blobs.
Contenido: solo cambia el href del primer botón de llamada de cada página (más el texto «by email»/«Email us about…» → «Request a quote»); sin normas, cifras ni fechas. Puntos de accounting-tax-service y form-721 aceptados por el revisor sin reparo.
Decisión: se sella y se publica esta versión exacta.

## v2 · última mirada de Claude · escrita antes de fusionar (18/11, ~19:15 Madrid)
Versión: 2898b465accb8391eb41d26881ecefae167d13a3, encima del sello de v1 535ad2b. main sigue en 11d26856042b5c0efd79718cbeabf740544c65c0: sin commits nuevos y sin solape.
Paso 2 de ChatGPT v2: REPASO-CHATGPT_v2.md (SHA-256 aca9741b…e805), 7 SÍ, 0 NO, 0 reparos; v2.SELLO.json VERDE para los 13 ficheros a las 19:10 Madrid (--sin-copia).
Cotejo de Claude: form-720 MD5 cdbfa42d5dbd5f396ba494f7dc4e1356 y form-721 MD5 6a888c91be2206a3a42f36bfd4343a2a coinciden con el repaso. Los otros 11 son idénticos a v1. Huella del listado de los 13: f9eefd4155a05e4d0c75a9c86d8dffb0, igual en HUELLAS-v2 y en el árbol.
Disposición de los reparos de la Puerta 5 del PR #174 (run 44364530419):
- form-721: BLOQUEA porque «Request a quote» chocaba con «Check my form 721». Lo creaba el cambio; CORREGIDO en v2.
- form-720 (run 44362337940): mismo reparo; CORREGIDO en v2 («Write to us about form 720»).
- remote-work: BLOQUEA por fechas de relectura distintas entre ES (18/11) y EN, FR y DE (11/11). Es texto anterior al cambio; no se toca ni se igualan fechas sin relectura. Fuente de la regla: ESTADO-VIVO.md, «Decisiones en vigor», punto «Entradillas X (15/11)»: «Cada página da la fecha real en que se leyeron sus normas, aunque sus parejas digan otra (16/11, PR #117)».
- COMPROBAR de citas en form-721 (Orden HFP/886/2023 art. 4 frente a RD 1065/2007 art. 42 quater.6) y en remote-work (ancla #a7-2 del art. 74 bis de la Ley 14/2013, art. 93 LIRPF, art. 76 RIRPF, listas de artículos entre idiomas): pendientes concretos para la relectura de vigencia. No están certificados como correctos ni como errores.
- CONVIENE/MENOR («quote», plantilla del mailto de form-721, «Tell us» repetido): sin cambio. Lo aceptó el paso 2.
Decisión: se sella v2 y, si la Puerta 5 nueva no da un BLOQUEA creado por el cambio, se fusiona.
