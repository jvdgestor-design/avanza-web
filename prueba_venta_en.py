# Prueba reproducible: python3 prueba_venta_en.py  (servidor estático del repositorio en :8765, commit 742f7d29)
import asyncio, json, datetime
from playwright.async_api import async_playwright
BASE='http://localhost:8765/'
async def main():
  out={'fecha_utc':datetime.datetime.utcnow().isoformat(timespec='seconds')}
  async with async_playwright() as p:
    b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    out['navegador']=b.version
    for name,w,h in [('movil390',390,844),('escritorio1280',1280,900)]:
      pg=await b.new_page(viewport={'width':w,'height':h},device_scale_factor=2 if w<500 else 1)
      await pg.goto(BASE+'selling-property-spain-non-resident.html')
      sec=pg.locator('section.cta-final'); await sec.scroll_into_view_if_needed()
      r=await pg.evaluate("""()=>{const s=document.querySelector('section.cta-final');return {lang:document.documentElement.lang,scrollWidth:document.documentElement.scrollWidth,viewport:innerWidth,
        botones:[...s.querySelectorAll('.ctas a')].map(a=>{const r=a.getBoundingClientRect();return {texto:a.textContent.trim(),x:Math.round(r.left),y:Math.round(r.top),ancho:Math.round(r.width),alto:Math.round(r.height),href:a.getAttribute('href'),clase:a.className}})}}""")
      await sec.screenshot(path=f'{name}.png')
      await pg.focus('section.cta-final .ctas a'); orden=[await pg.evaluate('document.activeElement.textContent.trim()')]
      for _ in range(2):
        await pg.keyboard.press('Tab'); orden.append(await pg.evaluate('document.activeElement.textContent.trim()'))
      r['tabulador']=orden; out[name]=r
    pg=await b.new_page(viewport={'width':390,'height':844})
    await pg.goto(BASE+'en-contact.html?pagina=selling-property-spain-non-resident.html')
    out['formulario']=await pg.evaluate("""()=>({lang:document.documentElement.lang,titulo:document.title,h1:(document.querySelector('h1')||{}).textContent,
      campos:[...document.querySelectorAll('form input,form textarea,form select')].map(e=>({nombre:e.name||e.id,tipo:e.type,etiqueta:(e.labels&&e.labels[0]?e.labels[0].textContent.trim().slice(0,60):'')}))})""")
    # recogida de pagina: se intercepta el envío sin mandar nada
    out['recogida_pagina']=await pg.evaluate("""()=>{const q=new URLSearchParams(location.search).get('pagina')||'';return {valor:q,cumple_regex:/^[a-z0-9-]+\\.html$/.test(q)}}""")
    pg2=await b.new_page(viewport={'width':390,'height':844})
    await pg2.goto(BASE+'selling-property-spain-non-resident.html?origen=anuncio'); await pg2.wait_for_timeout(500)
    out['con_origen_anuncio']=await pg2.evaluate("""()=>[...document.querySelectorAll('section.cta-final .ctas a')].map(a=>a.getAttribute('href'))""")
    await b.close()
  json.dump(out,open('resultado_prueba.json','w'),ensure_ascii=False,indent=1); print(json.dumps(out,ensure_ascii=False,indent=1)[:3000])
asyncio.run(main())
