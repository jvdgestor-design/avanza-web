# Prueba local del acuse FR/DE con el receptor SIMULADO (page.route): no sale ninguna petición
# a script.google.com ni a ningún otro sitio fuera de localhost. Servidor estático en :8765.
import asyncio, json, datetime, sys
from playwright.async_api import async_playwright
BASE = 'http://localhost:8765/'
CASOS = {
  'fr': dict(form='fr-contact.html', gracias='fr-merci.html', btn='Envoyer la demande',
             recibido='Nous avons déjà reçu cette demande', ok_gracias='Nous avons bien reçu votre demande',
             error='Nous ne pouvons pas confirmer'),
  'de': dict(form='de-kontakt.html', gracias='de-danke.html', btn='Anfrage senden',
             recibido='Diese Anfrage ist bereits bei uns eingegangen', ok_gracias='Wir haben Ihre Anfrage erhalten',
             error='Der Eingang Ihrer Anfrage konnte nicht bestätigt werden'),
}
REF = 'W0123456789ab'
async def rellenar(pg, texto='PRUEBA local, no es un cliente'):
    await pg.fill('form.form input[name=nombre]', 'PRUEBA')
    await pg.fill('form.form input[name=contacto]', 'prueba@example.invalid')
    await pg.fill('form.form textarea[name=caso]', texto)

async def caso(b, idioma, c, modo, ancho):
    ctx = await b.new_context(viewport={'width': ancho, 'height': 900})
    pg = await ctx.new_page()
    posts, gets, fuera = [], [], []
    async def ruta(route):
        rq = route.request
        u = rq.url
        if u.startswith(BASE):
            return await route.continue_()
        if 'script.google.com' in u:
            if rq.method == 'POST':
                posts.append(dict(rq.post_data and __import__('urllib.parse').parse.parse_qs(rq.post_data)))
                if modo in ('ok', 'anuncio'):
                    return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'ok': True, 'ref': REF, 'nuevo': True, 'v': 5}))
                if modo == 'mala_ref':
                    return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'ok': True, 'ref': 'ABCDEF'}))
                return await route.fulfill(status=200, content_type='text/html', body='<html>no json</html>')
            gets.append(u)
            if modo == 'recupera':
                return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'ok': True, 'ref': REF, 'v': 5}))
            return await route.fulfill(status=200, content_type='application/json', body=json.dumps({'ok': False, 'v': 5}))
        fuera.append(u)
        return await route.abort()
    await ctx.route('**/*', ruta)
    q = '?pagina=modelo-210-no-residentes.html' + ('&origen=anuncio&utm_source=google&utm_medium=cpc&utm_campaign=prueba_' + idioma if modo == 'anuncio' else '')
    await pg.goto(BASE + c['form'] + q)
    await rellenar(pg)
    r = dict(idioma=idioma, modo=modo, ancho=ancho)
    btn = pg.locator('form.form button[type=submit]')
    r['boton'] = (await btn.text_content()).strip()
    await btn.click()
    if modo in ('ok', 'recupera', 'anuncio'):
        await pg.wait_for_url('**/' + c['gracias'] + '?ref=*', timeout=25000)
        r['url'] = pg.url.replace(BASE, '/')
        r['gracias_visible'] = await pg.locator('[data-recibido]').is_visible()
        r['gracias_texto'] = (await pg.locator('[data-recibido]').text_content()).strip()
        r['sin_ref_oculto'] = not await pg.locator('[data-sin-ref]').is_visible()
        await pg.screenshot(path=f'gracias_{idioma}_{modo}_{ancho}.png', full_page=False)
        # Atrás y mismo texto: no se reenvía
        await pg.go_back(); await pg.wait_for_load_state()
        await pg.wait_for_timeout(500)
        n_antes = len(posts)
        if await pg.locator('form.form textarea[name=caso]').input_value() == '':
            await rellenar(pg)
        await pg.locator('form.form button[type=submit]').click()
        await pg.wait_for_timeout(1500)
        r['reenvio_mismo_texto_posts'] = len(posts) - n_antes
        rec = pg.locator('[data-envio-recibido]')
        r['aviso_ya_recibido'] = await rec.is_visible() and c['recibido'] in (await rec.text_content())
    else:
        await pg.wait_for_timeout(21000)
        er = pg.locator('[data-envio-error]')
        r['aviso_error_visible'] = await er.is_visible()
        r['aviso_error_ok'] = c['error'] in (await er.text_content())
        r['boton_libre'] = await btn.is_enabled() and (await btn.text_content()).strip() == c['btn']
        r['sigue_en_formulario'] = c['form'] in pg.url
        await pg.screenshot(path=f'error_{idioma}_{modo}_{ancho}.png', full_page=False)
    r['posts'] = len(posts)
    r['gets_recuperacion'] = len(gets)
    r['peticiones_fuera_bloqueadas'] = fuera
    if posts:
        p0 = posts[0]
        r['post_campos'] = sorted(p0.keys())
        r['post_formato'] = p0.get('formato')
        r['post_pagina'] = p0.get('pagina')
        r['post_clave_ok'] = bool(p0.get('client_submit_id')) and len(p0['client_submit_id'][0]) == 32
        r['post_utm'] = {k: p0.get(k) for k in ('origen','utm_source','utm_medium','utm_campaign')}
        r['post_linea_origen'] = p0.get('caso', [''])[0].split('\n\n')[-1]
    await ctx.close()
    return r

async def main():
    out = {'fecha_utc': datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds'), 'casos': []}
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
        out['navegador'] = b.version
        for idioma, c in CASOS.items():
            for modo, ancho in [('ok', 390), ('ok', 1280), ('recupera', 390), ('sin_respuesta', 390), ('mala_ref', 1280), ('anuncio', 390)]:
                out['casos'].append(await caso(b, idioma, c, modo, ancho))
        await b.close()
    json.dump(out, open('resultado_prueba.json', 'w'), ensure_ascii=False, indent=1)
    for r in out['casos']:
        print(json.dumps(r, ensure_ascii=False))
asyncio.run(main())
