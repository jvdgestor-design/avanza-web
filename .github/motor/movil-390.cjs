const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

(async () => {
  const xml = fs.readFileSync('sitemap.xml', 'utf8');
  const files = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m => {
    const u = new URL(m[1]);
    if (u.hostname !== 'grupoavanzaconsultores.es') throw new Error('Host inesperado');
    const relative = decodeURIComponent(u.pathname).replace(/^\/+/, '') || 'index.html';
    const resolved = path.resolve(relative);
    if (!resolved.startsWith(process.cwd() + path.sep)) throw new Error('Ruta fuera del repositorio');
    return resolved;
  });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
  const failures = [];
  try {
    for (const file of files) {
      await page.goto(pathToFileURL(file).href, { waitUntil: 'load' });
      await page.evaluate(() => document.fonts.ready);
      const size = await page.evaluate(() => ({ viewport: innerWidth, scroll: document.documentElement.scrollWidth }));
      console.log(JSON.stringify({ file: path.basename(file), ...size }));
      if (size.scroll > size.viewport) failures.push({ file: path.basename(file), ...size });
    }
    console.log(JSON.stringify({ checked: files.length, failures }));
    if (failures.length) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
