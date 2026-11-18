# Última mirada de Claude · 210 ES y EN · punto «Heredado» v1 · ANTES del merge (18/11/2026, ~17:45 Madrid)

## Versión exacta
- Contenido revisado: commit 41bcc0992f6a829c8d5c303ace0cc5599a67180f, base 3e8596361120721bb8d84338f4996b134c5f68a3. Integrado main 873b8d5 con el commit de fusión 29ebaffb2dd5b4e82044e682f59d28c05668ff9f: main solo había cambiado de-immobilie-spanien-verkaufen-ausland.html y fr-vendre-bien-immobilier-non-resident.html; los dos blobs revisados no cambian.
- modelo-210-no-residentes.html · blob fc871ebb787cb8796723a7ce7dfac5f6a4fb6d38 · MD5 1ddaafabd99df8fc1be9ff16217aa817 · SHA-256 eb2fb73dd973d74b077db8cfd7b13f2975a7d21fbb2ef804c515e7f10805635c
- modelo-210-non-resident-tax-spain.html · blob 6207af01d35ca27e3d2d98194dd4f94ac91e33c3 · MD5 bee31637c8abf007090917b81b7719fb · SHA-256 1a4441b9d8da4457510d07dc7a5a9e2a47a81713f822a35a3d65691dd8f29d1a
- Paquete de revisión: `revision/210-puente-herencia` 97ebb19 (no se fusiona).

## Criterio
- Inserción pura de un <li> por idioma (comprobado: resultado − <li> = base). Sin tocar title, meta, H1, entradillas, FAQ, fechas, JSON-LD ni los cuatro puntos de la v4. EN conserva el pie NL.
- Fuente: Ley 29/1987, art. 3.1.a (norma_leer 18/11/2026 17:31); ChatGPT cotejó además el art. 7 (obligación real).
- Los enlaces llevan a las guías cuyo H1 es el texto del enlace; las dos guías ya enlazan al 210.
- salud.py 0/0; render a 390 y 1366 px sin desborde.
- Se publica: sello sobre el commit de fusión, fusion.py, PR, Puerta 5; si no bloquea por el propio cambio, merge y «Después de publicar». Efecto en citas o posiciones: NO CALCULABLE.

## Repaso de ChatGPT, literal (paso 2; VERDE de sello.py comprobar en los dos HTML a las 17:38; REPASO-CHATGPT_v1.md SHA-256 0a1da5111e2b4dcbb838c6ffb40f5b2a0c5278c52442713d18bbda784b76d032)

# Grupo Avanza Consultores · Revisión de 210 y herencia · v1

Proyecto de destino: AVANZA WEB. Revisor: ChatGPT/Codex. Autor: Claude (Opus). Fecha: 18/11/2026. Estado del contenido: revisión independiente completada sin reparos; falta última mirada de Claude y controles de publicación.

Versión exacta: contenido 41bcc0992f6a829c8d5c303ace0cc5599a67180f, base 3e8596361120721bb8d84338f4996b134c5f68a3. Paquete original 97ebb19cfc502636f9245627008bb2fa7be0a80a (rama de revisión, no fusionar). Destinos públicos: https://grupoavanzaconsultores.es/modelo-210-no-residentes.html y https://grupoavanzaconsultores.es/modelo-210-non-resident-tax-spain.html. Sin destinatarios privados ni adjuntos a terceros. Solo dos HTML; sin coste ni alta de servicios.

Huellas calculadas localmente sobre los originales descargados:
- ES: 41189 bytes; MD5 1ddaafabd99df8fc1be9ff16217aa817; SHA256 eb2fb73dd973d74b077db8cfd7b13f2975a7d21fbb2ef804c515e7f10805635c.
- EN: 41528 bytes; MD5 bee31637c8abf007090917b81b7719fb; SHA256 1a4441b9d8da4457510d07dc7a5a9e2a47a81713f822a35a3d65691dd8f29d1a.

| Control | Evidencia y criterio | Estado |
|---|---|---|
| Identidad de la versión | Base, resultado, diff, huellas y LEEME descargados del commit de revisión; bytes y huellas finales coinciden con el contenido propuesto. | SÍ |
| Alcance del cambio | Comparación independiente: única adición de un li por idioma y espacios de formato. Al retirarlo se obtiene la base; ningún texto previo cambia. | SÍ |
| Norma aplicable | BOE, Ley 29/1987, art. 3.1.a: adquisición mortis causa sujeta a Sucesiones. Art. 7: obligación real por bienes y derechos situados en España. Consultado 18/11/2026: https://www.boe.es/buscar/act.php?id=BOE-A-1987-28141#a3 y #a7. El contexto identifica persona física no residente e inmueble en España. | SÍ |
| Separación de obligaciones | El nuevo punto distingue adquisición por herencia y declaraciones posteriores del 210 según el uso; no asigna al 210 la adquisición hereditaria ni inventa plazo o tipo. | SÍ |
| Traducción y alcance EN | Herencia, impuesto y uso posterior equivalentes al ES, con la misma fuente y guía en inglés. | SÍ |
| Promesa del enlace ES | Original de herencia ES, blob 3c2e446aa4ceff9b52e7f279812a63ae767d0e27: H1 coincide y explica Sucesiones para herederos no residentes; su cuerpo también orienta al 210 posterior. | SÍ |
| Promesa del enlace EN | Original de herencia EN, blob e722c03b365ff517c526eee9d786ee1cab31f4dc: H1 coincide y explica el impuesto de la herencia; cuerpo enlaza al 210 posterior. No promete cálculo individual. | SÍ |
| Conservación de la versión publicada | Cuatro usos anteriores íntegros. Comparación programática de title, meta description, H1, og y JSON-LD sin diferencias. EN conserva pie NL de la base. | SÍ |
| Resultado visible | Inspección directa de las cuatro imágenes 390/1366 px: punto nuevo visible completo, enlaces legibles, sin recortes. Salud 0 errores/0 avisos y desborde 0: comprobación técnica declarada por Claude en LEEME, a completar con CI del PR. | SÍ |
| Utilidad y límites | Enlace contextual en el cuerpo hacia la guía correcta, cita oficial y relación con el inmueble heredado. Mejora concreta de acceso y comprensión. Efecto en posiciones/citas de ChatGPT NO CALCULABLE; no se promete inclusión. | SÍ |

Confirmación posterior al sellado (18/11/2026): releídas ambas inserciones y recalculadas sus huellas MD5; coinciden con la versión revisada y sellada. Sin cambios de contenido ni nuevos reparos.

Dictamen: 10 SÍ, 0 NO, 0 reparos materiales. Se devuelve a Claude para su última mirada de esta misma versión, sellado, Puerta 5, CI y publicación autorizada en AVANZA WEB. Cualquier cambio material requiere revisar lo afectado. No es una autorización para gastos ni correos. Falta verificar públicamente los bytes después de publicar.

Buscado en: paquete de revisión indicado; HTML base y final; originales de ambas guías de herencia del repositorio; BOE consolidado; cuatro vistas de móvil y escritorio. No se ha medido un cambio de visibilidad atribuible a esta inserción.

Repaso: 210 puente herencia v1 · md5 1ddaafabd99df8fc1be9ff16217aa817 · md5 bee31637c8abf007090917b81b7719fb · 0 NO · 0 reparos · revisor ChatGPT
