# Motor de posicionamiento: diagnóstico y revisión verificables

PROVISIONAL, pendiente de revisión de Claude. Preparado el 20-10-2026.

## Método conservado

Estudiados MOTOR-AVANZA, METODOS, PANEL-MOTOR, ESTADO-VIVO y COLA-PULSO, además de los programas y flujos de .github/motor. Se conserva su prioridad: A autoridad y menciones útiles; B rastreo/indexación; C presencia local; D citas en IA; E contacto; F contenido justificado. No se crean tareas programadas que compitan con las pasadas de Claude.

Una oportunidad GSC solo propone estudiar intención y resultado. No autoriza escribir por volumen. Se conserva el umbral del método: al menos 20 impresiones en 28 días y posición entre 5 y 30 para esta vía de contenido. Las correcciones, revisiones y necesidades de una fuente externa siguen su procedimiento propio. La variación de visibilidad exige comparar períodos y no atribuir automáticamente los cambios a una acción.

## Ejecutar una pasada sin API de modelos

Desde la raíz del repositorio, con Python 3:

    python3 -B .github/motor/pulso.py --salida /ruta/externa/informe
    python3 -B .github/motor/pulso.py --vivo --salida /ruta/externa/informe-vivo

En Windows, usar la ruta al Python disponible y una carpeta de salida externa. En vivo solo hace lecturas HTTP. No presenta formularios ni solicita indexación.

El informe JSON y Markdown incluye HEAD, estado del árbol, huella del programa, huellas HTML, salud, idioma, distancias desde portada y portada de idioma, y camino hasta una página con formulario o enlace de contacto. Solo cuenta anclas HTML; no confunde canonical, hreflang o sitemap con navegación. No demuestra que un contacto se haya recibido.

La cola propone acciones por prioridad y bucle. No modifica la cola de Claude ni inicia las acciones propuestas. Las menciones externas, conversiones, citas de IA, móvil y vigencia normativa permanecen NO MEDIDO si no se han comprobado. El impacto en posicionamiento es NO CALCULABLE sin datos comparables.

## GSC opcional

    python3 -B .github/motor/pulso.py --gsc /ruta/exportacion.json --salida /ruta/externa/informe

Formato:

    {
      "siteUrl": "https://grupoavanzaconsultores.es/",
      "startDate": "2026-09-20",
      "endDate": "2026-10-17",
      "dimensions": ["page"],
      "dataState": "final",
      "rows": [
        {"page": "https://grupoavanzaconsultores.es/en.html", "impressions": 20, "position": 12.4}
      ]
    }

Sustituir las fechas por una ventana reciente de 28 días completos: fin entre 3 y 14 días antes de ejecutar. Admite también sc-domain:grupoavanzaconsultores.es. Rechaza propiedad ajena, consultas mezcladas con páginas, fechas no asentadas, duplicados, URL fuera del sitemap y métricas no finitas. Importación PROVISIONAL: el formato no certifica quién produjo el fichero ni que contenga todas las filas. No incorporar datos personales.

## Puerta 5

    python3 -B .github/motor/revisor.py --base origin/main --prueba --informe /ruta/externa/plan
    python3 -B .github/motor/revisor.py --base origin/main --informe /ruta/externa/revision

--prueba no llama a la API y SOLO_PLAN nunca es un dictamen. La llamada real conserva el uso ya previsto del secreto ANTHROPIC_API_KEY en el flujo existente; no se añade una llamada periódica.

Solo estado SIGUE, revision_valida=true, pendientes=[] y HEAD exacto acreditan esta revisión. SIN_CAMBIOS y SOLO_PLAN no acreditan revisión jurídica. BLOQUEA puede tener cobertura completa y sigue cerrando la puerta.

- Falta de clave, error de API, veredicto mal formado, respuesta truncada o copia modificada: salida de error.
- Veredicto exacto en primera línea y stop_reason=end_turn. No se configura stop_sequence.
- Divide lotes grandes sin recortar contenido; si una unidad excede el límite, no llama a la API y deja pendiente división/revisión manual.
- Incluye altas, modificaciones, eliminaciones y cambios de tipo. Resuelve parejas hreflang con comillas simples y orden variable; excluye otros dominios y rutas ascendentes.
- JSON/Markdown completos: base, HEAD, huella de cada encargo, cobertura, tokens conocidos y pendientes. Conserva comprobantes parciales entre llamadas.
- Límites preventivos por defecto: 2 HTML/lote, 160000 caracteres/encargo, 80000 de diff, 30 lotes y 1500000 caracteres totales. No son tokens ni estimaciones de euros. Se pueden bajar con argumentos; aumentar exige criterio sobre cobertura y gasto.
- No reintenta errores de transporte ambiguos, que podrían haber sido facturados. Mantiene un reintento limitado de ciertos códigos HTTP transitorios.
- Conserva las otras puertas: fuentes oficiales del día, segunda revisión independiente cuando proceda, móvil, hermanas de idioma, salud y cotejo de producción.

Cierre por respuestas incompletas: [documentación oficial de Anthropic](https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons), consulta 20-10-2026. end_turn indica final natural; max_tokens indica corte. Una respuesta terminada no demuestra corrección jurídica.

## Vigilancia BOE

boe_revisor.py no llama al modelo si un artículo o el encargo han sido recortados. Sale con error y exige dividir o revisar el original completo. Exige primera línea exacta y final end_turn. No se modifica Avanza Memoria ni se presume una validación jurídica integral.

## Verificación y adopción

    python3 -B -m unittest discover -s .github/motor/tests -v

motor-pruebas.yml ejecuta pruebas y diagnóstico sin secretos. Conserva el informe como artefacto fuera de la web. revision.yml conserva el dictamen completo incluso cuando falla y activa también cambios de robots.txt.

Integrar mediante revisión y PR. Claude debe revisar estos cambios antes de main. Al combinar con ramas de contenido, conservar sus fuentes-revision.json y mejoras posteriores: este cambio parte de main y no incluye modificaciones aún pendientes en otras ramas. Un SIGUE antiguo no se hereda después de resolver conflictos o cambiar contenido.

No sustituye el panel fijo de consultas de IA ni demuestra recomendaciones reales. No se instala suscripción, publicidad, compra de enlaces o solicitudes automáticas.

## Huellas en Windows

salud.py normaliza CRLF a LF para el cotejo en vivo solo si git ls-files --eol acredita i/lf y w/crlf. Conserva los bytes de binarios, contenido no versionado y archivos que ya usan CRLF en el propio repositorio. Así la conversión local de Windows no dispara una alarma falsa de despliegue. Las huellas por página del diagnóstico siguen identificando los bytes locales. La comprobación de publicación compara contra los bytes publicables.
