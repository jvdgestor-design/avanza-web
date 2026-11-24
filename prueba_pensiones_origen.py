# Prueba reproducible (servidor estático del repositorio en :8765, commit 10651000)
import asyncio, json, datetime
from playwright.async_api import async_playwright
BASE='http://localhost:8765/'
CASOS=[('pension-italiana-residente-en-espana.html',['header','main']),('pension-estados-unidos-residente-en-espana.html',['header'])]
async def main():
  out={'fecha_utc':datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds')}
  async with async_playwright() as p:
    b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox']); out['navegador']=b.version
    for pag,zonas in CASOS:
      dest='contacto.html?pagina='+pag; R={}
      for w,h in [(390,844),(1280,900)]:
        pg=await b.new_page(viewport={'width':w,'height':h},device_scale_factor=2 if w<500 else 1)
        await pg.goto(BASE+pag)
        r={'scrollWidth':await pg.evaluate('document.documentElement.scrollWidth'),
           'enlaces_al_destino':await pg.evaluate("(d)=>[...document.querySelectorAll('a')].filter(a=>a.getAttribute('href')===d).map(a=>{const q=a.getBoundingClientRect();return {texto:a.textContent.trim(),en_cabecera:!!a.closest('header,.topbar'),visible:q.width>0&&q.height>0&&getComputedStyle(a).visibility!=='hidden',ancho:Math.round(q.width)}})",dest),
           'contacto_sin_origen':await pg.evaluate("[...document.querySelectorAll('a')].filter(a=>a.getAttribute('href')==='contacto.html').map(a=>a.textContent.trim())")}
        n=0; hallados=[]
        while n<250:
          await pg.keyboard.press('Tab'); n+=1
          if await pg.evaluate("(d)=>document.activeElement.getAttribute('href')===d",dest):
            hallados.append({'pulsacion':n,'en_cabecera':await pg.evaluate("!!document.activeElement.closest('header,.topbar')")})
            if len(hallados)==sum(1 for e in r['enlaces_al_destino'] if e['visible']): break
        r['tab_real']=hallados
        await pg.screenshot(path=f"{pag.split('-')[1]}_{w}.png")
        async with pg.expect_navigation():
          await pg.keyboard.press('Enter')
        r['tras_enter']=pg.url.replace(BASE,'/')
        r['form']=await pg.evaluate("()=>({lang:document.documentElement.lang,boton:(document.querySelector('form [type=submit]')||{}).textContent,pagina:new URLSearchParams(location.search).get('pagina'),lee_pagina:[...document.scripts].some(s=>/get\\('pagina'\\)/.test(s.textContent))})")
        R[str(w)]=r
      out[pag]=R
    await b.close()
  json.dump(out,open('resultado_prueba.json','w'),ensure_ascii=False,indent=1); print(json.dumps(out,ensure_ascii=False,indent=1))
asyncio.run(main())
