# Prueba reproducible (servidor estático del repositorio en :8765, commit d796685c)
import asyncio, json, datetime
from playwright.async_api import async_playwright
BASE='http://localhost:8765/'
P='amazon-kdp-impuestos-espana.html'
async def main():
  out={'fecha_utc':datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds')}
  async with async_playwright() as p:
    b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    out['navegador']=b.version
    for name,w,h in [('movil390',390,844),('escritorio1280',1280,900)]:
      pg=await b.new_page(viewport={'width':w,'height':h},device_scale_factor=2 if w<500 else 1)
      await pg.goto(BASE+P)
      sec=pg.locator('section.cta-final'); await sec.scroll_into_view_if_needed()
      r=await pg.evaluate("""()=>{const s=document.querySelector('section.cta-final');return {scrollWidth:document.documentElement.scrollWidth,viewport:innerWidth,
        botones:[...s.querySelectorAll('.ctas a')].map(a=>{const q=a.getBoundingClientRect();return {texto:a.textContent.trim(),x:Math.round(q.left),ancho:Math.round(q.width),alto:Math.round(q.height),y:Math.round(q.top),href:a.getAttribute('href').slice(0,70),clase:a.className,target:a.target||''}})}}""")
      await sec.screenshot(path=f'{name}.png')
      # Tab real: foco en el botón de WhatsApp del bloque final y dos Tab reales
      await pg.evaluate("document.querySelector('section.cta-final .ctas a').focus()")
      orden=[await pg.evaluate('document.activeElement.textContent.trim()')]
      for _ in range(2):
        await pg.keyboard.press('Tab'); orden.append(await pg.evaluate('document.activeElement.textContent.trim()'))
      r['tabulador_desde_whatsapp']=orden
      async with pg.expect_navigation():
        await pg.keyboard.press('Enter')
      r['tras_enter_url']=pg.url.replace(BASE,'/')
      out[name]=r
    # recorrido completo con Tab real desde el inicio de la página hasta el botón nuevo
    pg=await b.new_page(viewport={'width':1280,'height':900}); await pg.goto(BASE+P)
    n=0
    while n<200:
      await pg.keyboard.press('Tab'); n+=1
      if await pg.evaluate("(p)=>!!document.activeElement.closest('section.cta-final') && document.activeElement.getAttribute('href')==='contacto.html?pagina='+p", P): break
    out['tab_real_desde_inicio']={'pulsaciones':n,'alcanzado':n<200}
    pg=await b.new_page(viewport={'width':390,'height':844}); await pg.goto(BASE+'contacto.html?pagina='+P)
    out['formulario']=await pg.evaluate("""()=>({lang:document.documentElement.lang,h1:(document.querySelector('h1')||{}).textContent,
      boton:(document.querySelector('form [type=submit]')||{}).textContent,campos:[...document.querySelectorAll('form input,form textarea,form select')].map(e=>e.name||e.id),
      pagina:new URLSearchParams(location.search).get('pagina'),cumple:/^[a-z0-9-]+\\.html$/.test(new URLSearchParams(location.search).get('pagina')||'')})""")
    out['script_formulario_lee_pagina']=await pg.evaluate("[...document.scripts].some(s=>/get\\('pagina'\\)/.test(s.textContent))")
    await b.close()
  json.dump(out,open('resultado_prueba.json','w'),ensure_ascii=False,indent=1); print(json.dumps(out,ensure_ascii=False,indent=1))
asyncio.run(main())
