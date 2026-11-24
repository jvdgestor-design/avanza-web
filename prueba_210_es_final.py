# Prueba reproducible (servidor estático del repositorio en :8765, commit 7da03955)
import asyncio, json, datetime
from playwright.async_api import async_playwright
BASE='http://localhost:8765/'
P='modelo-210-no-residentes.html'
SEL='section.cta-final .ctas a[href="contacto.html?pagina=%s"]'%P
async def main():
  out={'fecha_utc':datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds'),'anchos':{}}
  async with async_playwright() as p:
    b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox']); out['navegador']=b.version
    for w in [390,641,900,1024,1280]:
      pg=await b.new_page(viewport={'width':w,'height':900}); await pg.goto(BASE+P)
      r=await pg.evaluate("""(sel)=>{const a=document.querySelector(sel);a.scrollIntoView({block:'center'});const q=a.getBoundingClientRect();const cs=getComputedStyle(a);
        const ctas=[...a.parentElement.querySelectorAll('a')].map(x=>{const r=x.getBoundingClientRect();return {texto:x.textContent.trim(),href:x.getAttribute('href'),target:x.getAttribute('target'),ancho:Math.round(r.width),alto:Math.round(r.height),dentro:r.right<=innerWidth+0.5&&r.left>=-0.5}});
        return {scrollWidth:document.documentElement.scrollWidth,viewport:innerWidth,visible:q.width>0&&q.height>0&&cs.display!=='none'&&cs.visibility!=='hidden',texto_completo:a.scrollWidth<=a.clientWidth+1,botones_bloque_final:ctas}}""",SEL)
      await pg.wait_for_timeout(400)
      await pg.locator('section.cta-final').screenshot(path=f'final_{w}.png')
      await pg.goto(BASE+P)   # recarga antes de recorrer con Tab
      n=0; ok=False
      while n<200:
        await pg.keyboard.press('Tab'); n+=1
        if await pg.evaluate("(sel)=>document.activeElement===document.querySelector(sel)",SEL): ok=True; break
      r['tab_pulsaciones']=n if ok else None
      if ok:
        async with pg.expect_navigation():
          await pg.keyboard.press('Enter')
        r['url_tras_enter']=pg.url.replace(BASE,'/')
        r['form']=await pg.evaluate("()=>({lang:document.documentElement.lang,boton:(document.querySelector('form [type=submit]')||{}).textContent,pagina:new URLSearchParams(location.search).get('pagina'),lee_pagina:[...document.scripts].some(s=>/get\\('pagina'\\)/.test(s.textContent))})")
      out['anchos'][str(w)]=r; await pg.close()
    await b.close()
  json.dump(out,open('resultado_prueba.json','w'),ensure_ascii=False,indent=1)
  for w,r in out['anchos'].items(): print(w,r['scrollWidth'],r['visible'],r['texto_completo'],[(c['texto'][:14],c['ancho'],c['dentro'],(c['href'] or '')[:20]) for c in r['botones_bloque_final']],r['tab_pulsaciones'],r.get('url_tras_enter'),r.get('form'))
asyncio.run(main())
