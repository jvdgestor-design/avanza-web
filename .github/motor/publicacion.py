#!/usr/bin/env python3
"""Después de cada publicación en main, sin gastar usos de Claude:
1. Espera a que GitHub Pages sirva las páginas cambiadas (misma huella SHA-256 que el repo).
2. Avisa a IndexNow (Bing, y a través de él Copilot, Yandex, Seznam, Naver) solo con esas URL.

Uso: publicacion.py fichero1.html fichero2.html ...   (los ficheros cambiados en el push)
Sale con 1 si la web no llega a servir lo publicado o IndexNow no acepta el envío.
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

DOMINIO = "grupoavanzaconsultores.es"
BASE = f"https://{DOMINIO}/"
ESPERA_MAX = 15 * 60  # segundos


def url_de(fichero):
    return BASE if fichero == "index.html" else BASE + fichero


def en_sitemap():
    with open("sitemap.xml", encoding="utf-8") as f:
        return set(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", f.read()))


def huella_viva(url):
    req = urllib.request.Request(url + ("&" if "?" in url else "?") + f"v={int(time.time())}",
                                 headers={"User-Agent": "AvanzaPublicacion/1.0", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return hashlib.sha256(r.read()).hexdigest()
    except Exception:
        return None


def main():
    cambiados = [f for f in sys.argv[1:] if f.endswith(".html") and os.path.isfile(f)]
    sitemap = en_sitemap()
    urls = [url_de(f) for f in cambiados if url_de(f) in sitemap]
    if not urls:
        print("Ninguna página del sitemap cambiada: no hay nada que avisar a IndexNow.")
        return 0

    pendientes = {}
    for f in cambiados:
        u = url_de(f)
        if u in sitemap:
            with open(f, "rb") as fh:
                pendientes[u] = hashlib.sha256(fh.read()).hexdigest()

    inicio = time.time()
    while pendientes and time.time() - inicio < ESPERA_MAX:
        for u, h in list(pendientes.items()):
            if huella_viva(u) == h:
                print(f"Servida con la huella del repo: {u}")
                del pendientes[u]
        if pendientes:
            time.sleep(30)
    if pendientes:
        for u in pendientes:
            print(f"ERROR: a los {ESPERA_MAX // 60} min la web aún no sirve lo publicado en {u}")
        return 1

    claves = [f for f in os.listdir(".") if re.fullmatch(r"[0-9a-f]{32}\.txt", f)]
    if not claves:
        print("ERROR: no está el fichero de clave de IndexNow en el repositorio")
        return 1
    clave = claves[0][:-4]
    cuerpo = json.dumps({"host": DOMINIO, "key": clave, "keyLocation": BASE + claves[0],
                         "urlList": urls}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=cuerpo, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            estado = r.status
    except urllib.error.HTTPError as e:
        estado = e.code
    print(f"IndexNow: {estado} para {len(urls)} URL")
    for u in urls:
        print(f"  {u}")
    resumen = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumen:
        with open(resumen, "a", encoding="utf-8") as f:
            f.write(f"IndexNow: {estado} para {len(urls)} URL\n\n" + "\n".join(f"- {u}" for u in urls) + "\n")
    return 0 if estado in (200, 202) else 1


if __name__ == "__main__":
    sys.exit(main())
