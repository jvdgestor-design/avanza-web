# PROTOCOLO DE CONTROL — CONTENIDO WEB AVANZA

## Objetivo
Publicar contenido útil para captar clientes y ser entendido/citado por buscadores y asistentes de IA sin sacrificar exactitud jurídica, fiscal, laboral ni de datos del despacho.

## Regla principal
Nada se publica por ser una buena oportunidad SEO. Primero tiene que superar las puertas de exactitud y coherencia. Una página con una afirmación material no verificada no pasa a producción.

## Puerta 1 — intención y no canibalización
- Definir la consulta principal y las consultas secundarias.
- Comprobar que no exista ya una URL que responda sustancialmente a la misma intención.
- Si existe una URL cercana, decidir si conviene reforzarla o crear una página distinta.
- No tocar URLs que estén en periodo de medición salvo error material.
- La respuesta principal debe aparecer en las primeras líneas; el title debe corresponder a una consulta real o a una formulación natural de alta intención.

## Puerta 2 — investigación jurídica/fiscal
- Prioridad de fuentes: BOE/DOGV/EUR-Lex, AEAT/ATV/TGSS/Seguridad Social, ministerios/Policía/administraciones competentes, DGT/TEAC/CENDOJ cuando proceda.
- Para cada regla material: norma, artículo o apartado concreto y versión vigente en la fecha relevante.
- No usar como fundamento una cita que no se haya podido verificar en fuente oficial.
- Distinguir: norma expresa / jurisprudencia / doctrina administrativa / interpretación razonable / criterio prudente.
- Si una cuestión depende de hechos (residencia, convenio, actividad en varios países, etc.), decirlo y evitar reglas absolutas.

## Puerta 3 — control de afirmaciones
- Prohibidas afirmaciones de experiencia, volumen, resultados, liderazgo, rapidez o superioridad que no estén acreditadas.
- Prohibidas promesas de resultado.
- Evitar “siempre”, “nunca”, “automáticamente” cuando exista excepción.
- No convertir una recomendación práctica en obligación legal.
- No publicar precios si no están aprobados.
- No atribuir colegiación.
- Datos canónicos del despacho: Grupo Avanza Consultores · 46980 Paterna (Valencia), sin calle pública · 614 365 547 · avanza@grupoavanzaconsultores.es · titular Jose Vicente Díaz Madrid, Diplomado en Ciencias Empresariales, despacho propio desde 2011 · online para toda España · en persona solo con cita · español y ruso.

## Puerta 4 — revisión técnica y de entidad
- Un H1.
- Title y meta description específicos.
- Canonical propio.
- robots index,follow.
- BreadcrumbList.
- FAQPage solo si las FAQ visibles son idénticas en contenido sustancial.
- Article para guías cuando corresponda, con autor y publisher enlazados a los @id canónicos.
- No inventar sameAs.
- NAP y horarios coherentes con la entidad canónica.
- Enlaces internos relevantes y naturales.
- Comprobar que no haya enlaces rotos ni datos contradictorios.

## Puerta 5 — segunda revisión crítica antes de publicar
Método heredado del flujo de Claude:
1. Primera redacción con fuentes primarias.
2. Segunda pasada independiente cuyo objetivo es encontrar errores, exageraciones, excepciones omitidas, citas incorrectas, incompatibilidades entre texto visible y schema y afirmaciones no demostrables.
3. Todo reparo material se corrige o se elimina. Si queda un punto jurídico dudoso, la página no se publica con ese punto como hecho.
4. Repetir la revisión si hubo cambios materiales.

Nota: cuando no esté disponible un segundo modelo distinto (Claude usó Sonnet en varios commits como “Puerta 5”), se hace una segunda pasada separada y adversarial contra las fuentes primarias; no se simula que la revisó otro modelo.

## Puerta 6 — integración del sitio
Cuando se crea una URL nueva:
- añadirla al sitemap.xml;
- añadirla a llms.txt si aporta una entidad/servicio/guía útil;
- actualizar README.md como inventario de contenido;
- añadir enlaces internos desde páginas relacionadas sin alterar URLs congeladas si no es necesario;
- comprobar que la página responde 200 y es indexable después del despliegue.

## Puerta 7 — publicación y medición
- Publicar en rama/revisión cuando sea posible antes de main.
- Tras desplegar, comprobar la URL en vivo.
- Enviar/reenviar sitemap cuando proceda.
- Añadir al seguimiento de Search Console.
- Registrar fecha del cambio y no reescribir la página continuamente: medir antes de una nueva modificación salvo error material.
- Comparar impresiones, clics, CTR, consultas y posición con el periodo anterior.

## Criterio de bloqueo
Bloquean publicación:
- error jurídico/fiscal material;
- fuente primaria no encontrada para una afirmación central;
- dato del despacho contradictorio;
- schema que afirma algo distinto del texto visible;
- solapamiento grave con otra URL;
- afirmación comercial no acreditada;
- contenido generado para SEO sin una respuesta útil y verificable al usuario.
