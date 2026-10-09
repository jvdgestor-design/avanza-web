#!/usr/bin/env python3
"""Después de cada publicación en main, sin gastar usos de Claude:
1. Saca lo que ha cambiado entre la versión anterior y la publicada (páginas, renombradas incluidas,
   y URL nuevas del sitemap).
2. Espera a que GitHub Pages sirva esos ficheros con la misma huella SHA-256 que el repositorio
   (o que la última versión de main, si mientras tanto se ha vuelto a publicar).
3. Avisa a IndexNow (Bing y, a través de él, Copilot, Yandex, Seznam, Naver) solo con esas URL.

Uso: publicacion.py --antes <commit anterior>     (en GitHub Actions: github.event.before)
Sale con 1 si la web no llega a servir lo publicado o IndexNow no acepta el envío.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

DOMINIO = "grupoavanzaconsultores.es"
BASE = f"https://{DOMINIO}/"
ESPERA_MAX = int(os.environ.get("AVANZA_ESPERA_MAX", 15 * 60))  # segundos
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def git(*args, binario=False):
    r = subprocess.run(["git", *args], capture_output=True)
    if r.returncode != 0:
        return None
    return r.stdout if binario else r.stdout.decode("utf-8", "replace")


def locs(xml_texto):
    try:
        raiz = ET.fromstring(xml_texto)
    except ET.ParseError:
        return set()
    return {(x.text or "").strip() for x in raiz.findall("s:url/s:loc", NS)}


def url_de(fichero):
    return BASE if fichero == "index.html" else BASE + fichero


def fichero_de(url):
    ruta = url[len(BASE):] if url.startswith(BASE) else ""
    return ruta or "index.html"


def huella_viva(url):
    req = urllib.request.Request(url + ("&" if "?" in url else "?") + f"v={int(time.time())}",
                                 headers={"User-Agent": "AvanzaPublicacion/1.0", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return hashlib.sha256(r.read()).hexdigest()
    except Exception:
        return None


def anota(nivel, texto):
    """Anotación de GitHub Actions: se lee con la API (check-runs/<job>/annotations), sin descargar logs."""
    t = texto.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::{nivel}::{t}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--antes", default="")
    a = ap.parse_args()
    antes = a.antes
    if not antes or set(antes) == {"0"} or git("cat-file", "-e", antes + "^{commit}") is None:
        antes = "HEAD~1"

    salida = git("diff", "--no-renames", "-z", "--name-only", "--diff-filter=AM", antes, "HEAD") or ""
    cambiados = [f for f in salida.split("\0") if f]
    with open("sitemap.xml", encoding="utf-8") as f:
        sitemap = locs(f.read())
    previo = git("show", f"{antes}:sitemap.xml") or ""
    nuevas_en_sitemap = sitemap - locs(previo) if previo else set()

    urls = sorted({url_de(f) for f in cambiados if f.endswith(".html") and url_de(f) in sitemap}
                  | nuevas_en_sitemap)
    vigilar = sorted({f for f in cambiados if f in ("sitemap.xml", "llms.txt", "robots.txt")}
                     | {fichero_de(u) for u in urls})
    print("Cambiados en esta publicación:", ", ".join(cambiados) or "(ninguno)")
    if not vigilar:
        print("Nada publicado que deba servir la web: no hay espera ni aviso a IndexNow.")
        return 0

    pendientes = set(vigilar)
    inicio = time.time()
    while pendientes:
        git("fetch", "-q", "origin", "main")
        for f in sorted(pendientes):
            validas = set()
            for rev in ("HEAD", "origin/main"):
                contenido = git("show", f"{rev}:{f}", binario=True)
                if contenido is not None:
                    validas.add(hashlib.sha256(contenido).hexdigest())
            if huella_viva(url_de(f)) in validas:
                print(f"Servido con la huella del repositorio: {f}")
                pendientes.discard(f)
        if not pendientes or time.time() - inicio > ESPERA_MAX:
            break
        time.sleep(30)
    if pendientes:
        for f in sorted(pendientes):
            print(f"ERROR: a los {ESPERA_MAX // 60} min la web aún no sirve lo publicado en {f}")
            if os.environ.get("GITHUB_ACTIONS"):
                anota("error", f"La web aún no sirve lo publicado en {f} (huella distinta tras {ESPERA_MAX // 60} min)")
        return 1

    if not urls:
        print("Sin páginas nuevas o cambiadas del sitemap: nada que avisar a IndexNow.")
        return 0
    claves = [f for f in os.listdir(".") if re.fullmatch(r"[0-9a-f]{32}\.txt", f)]
    if not claves:
        print("ERROR: no está el fichero de clave de IndexNow en el repositorio")
        return 1
    cuerpo = json.dumps({"host": DOMINIO, "key": claves[0][:-4], "keyLocation": BASE + claves[0],
                         "urlList": urls}).encode()
    estado = 0
    for intento in range(3):
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=cuerpo, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                estado = r.status
        except urllib.error.HTTPError as e:
            estado = e.code
        except urllib.error.URLError as e:
            print(f"IndexNow sin conexión: {e.reason}")
            estado = 0
        if estado in (200, 202) or estado in (400, 403, 422):
            break
        time.sleep(20 * (intento + 1))
    lineas = [f"IndexNow: {estado or 'sin respuesta'} para {len(urls)} URL"] + [f"- {u}" for u in urls]
    print("\n".join(lineas))
    if os.environ.get("GITHUB_ACTIONS"):
        anota("notice" if estado in (200, 202) else "error", "\n".join(lineas))
    resumen = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumen:
        with open(resumen, "a", encoding="utf-8") as f:
            f.write("\n".join(lineas) + "\n\n")
    return 0 if estado in (200, 202) else 1


if __name__ == "__main__":
    sys.exit(main())
