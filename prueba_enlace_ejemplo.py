# Prueba reproducible (servidor estático del repositorio en :8765, commit 17f01a80)
import asyncio, json, datetime
from playwright.async_api import async_playwright
U='http://localhost:8765/selling-property-spain-non-resident.html'
async def main():
  out={'fecha_utc':datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds')}
  async with async_playwright() as p:
    b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    out['navegador']=b.version
    for name,w,h in [('movil390',390,844),('escritorio1280',1280,900)]:
      pg=await b.new_page(viewport={'width':w,'height':h},device_scale_factor=2 if w<500 else 1)
      await pg.goto(U)
      a=pg.locator('a[href="#sale-tax-example"]')
      r={'enlaces':await a.count(),'texto':await a.first.inner_text(),'scrollWidth':await pg.evaluate('document.documentElement.scrollWidth'),'viewport':w}
      bb=await a.first.bounding_box(); r['caja_enlace']={k:round(v) for k,v in bb.items()}
      await pg.locator('section.pagehead').screenshot(path=f'{name}_cabecera.png')
      # teclado: llegar al enlace con Tab y pulsar Enter
      await pg.focus('section.pagehead p.lead strong') if False else None
      await pg.evaluate("document.querySelector('a[href=\"#sale-tax-example\"]').focus()")
      r['foco']=await pg.evaluate('document.activeElement.getAttribute("href")')
      await pg.keyboard.press('Enter'); await pg.wait_for_timeout(5000)
      r['hash']=await pg.evaluate('location.hash')
      r['h3_top_tras_salto']=await pg.evaluate("Math.round(document.getElementById('sale-tax-example').getBoundingClientRect().top)")
      r['h3_texto']=await pg.evaluate("document.getElementById('sale-tax-example').textContent")
      r['ids_repetidos']=await pg.evaluate("document.querySelectorAll('#sale-tax-example').length")
      await pg.screenshot(path=f'{name}_tras_salto.png')
      r['botones_cabecera']=await pg.evaluate("[...document.querySelectorAll('section.pagehead .ctas a')].map(x=>x.textContent.trim()+' -> '+x.getAttribute('href').slice(0,60))")
      out[name]=r
    await b.close()
  json.dump(out,open('resultado_prueba.json','w'),ensure_ascii=False,indent=1); print(json.dumps(out,ensure_ascii=False,indent=1))
asyncio.run(main())
