# Prueba reproducible v1c (servidor estático del repositorio en :8765, commit 10651000)
# Para cada botón visible que lleva al formulario con origen: página recargada desde cero,
# Tab real hasta ESE botón (cabecera o sección), Enter, y comprobación del destino.
import asyncio, json, datetime
from playwright.async_api import async_playwright
BASE='http://localhost:8765/'
PAGS=['pension-italiana-residente-en-espana.html','pension-estados-unidos-residente-en-espana.html']
async def main():
  out={'fecha_utc':datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds'),'casos':[]}
  async with async_playwright() as p:
    b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox']); out['navegador']=b.version
    for pag in PAGS:
      dest='contacto.html?pagina='+pag
      for w,h in [(390,844),(1280,900)]:
        pg=await b.new_page(viewport={'width':w,'height':h}); await pg.goto(BASE+pag)
        botones=await pg.evaluate("(d)=>[...document.querySelectorAll('a')].filter(a=>a.getAttribute('href')===d).map((a,i)=>{const q=a.getBoundingClientRect();return {indice:i,zona:a.closest('header,.topbar')?'cabecera':'cuerpo',visible:q.width>0&&q.height>0}})",dest)
        await pg.close()
        for bt in botones:
          caso={'pagina':pag,'ancho':w,'zona':bt['zona'],'visible':bt['visible']}
          if not bt['visible']:
            caso['resultado']='no se muestra en este ancho (no se prueba)'; out['casos'].append(caso); continue
          pg=await b.new_page(viewport={'width':w,'height':h}); await pg.goto(BASE+pag)  # página recargada desde cero
          n=0; ok=False
          while n<250:
            await pg.keyboard.press('Tab'); n+=1
            if await pg.evaluate("([d,i])=>{const l=[...document.querySelectorAll('a')].filter(a=>a.getAttribute('href')===d);return document.activeElement===l[i]}",[dest,bt['indice']]): ok=True; break
          caso['tab_pulsaciones']=n if ok else None
          if ok:
            async with pg.expect_navigation():
              await pg.keyboard.press('Enter')
            caso['url_tras_enter']=pg.url.replace(BASE,'/')
            caso['form']=await pg.evaluate("()=>({lang:document.documentElement.lang,boton:(document.querySelector('form [type=submit]')||{}).textContent,pagina:new URLSearchParams(location.search).get('pagina'),lee_pagina:[...document.scripts].some(s=>/get\\('pagina'\\)/.test(s.textContent))})")
            caso['resultado']='correcto' if caso['url_tras_enter']=='/'+dest and caso['form']['pagina']==pag and caso['form']['lee_pagina'] else 'FALLO'
          else: caso['resultado']='FALLO: no se alcanza con Tab'
          out['casos'].append(caso); await pg.close()
    await b.close()
  json.dump(out,open('resultado_prueba_v1c.json','w'),ensure_ascii=False,indent=1); print(json.dumps(out,ensure_ascii=False,indent=1))
asyncio.run(main())
