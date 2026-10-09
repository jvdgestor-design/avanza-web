#!/usr/bin/env python3
"""Salud de grupoavanzaconsultores.es sin gastar usos de Claude.

Comprueba el repositorio (y, con --vivo, la web publicada) contra el
apartado 6 de las instrucciones del proyecto AVANZA WEB:
  - toda URL del sitemap existe (y, en vivo, responde 200 con la misma huella SHA-256 que el repo)
  - un H1 por página, canonical propia, título y descripción sin duplicados
  - JSON-LD que se puede leer; preguntas de FAQPage visibles en la página
  - enlaces internos y anclas que existen
  - hreflang recíproco
  - imágenes con alt
  - robots.txt sin bloqueos y con Sitemap; llms.txt con todas las URL del sitemap
  - normas de contenido que se pueden comprobar con un programa (datos falsos, nombres que no van,
    teléfono de las páginas rusas fuera de ellas, páginas en inglés sin teléfono ni términos vetados)

Errores -> sale con código 1 (GitHub manda el aviso). Avisos -> se listan, sin fallar.
Lo que no mide: el desbordamiento a 390 px (necesita navegador).
Solo usa la biblioteca estándar de Python.
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

DOMINIO = "grupoavanzaconsultores.es"
BASE = f"https://{DOMINIO}/"
TELEFONO_BUENO = "34614365547"
SIN_INDEXAR = {"404.html", "gracias.html"}
LEGALES = {"aviso-legal.html", "cookies.html", "privacidad.html"}  # sin JSON-LD a propósito
BOTS = ["googlebot", "bingbot", "oai-searchbot", "chatgpt-user", "gptbot", "perplexitybot",
        "perplexity-user", "claude-searchbot", "claude-user", "claudebot", "applebot", "*"]

# Datos falsos o vetados (apartados 8 y 11). Se buscan en todo el HTML, código incluido.
VETADOS = [
    (r"Carrer del Castell|C/\s?Castell\b|\bCastell,?\s?(n[ºo]\.?\s?)?4\b", "dirección falsa (Castell 4)"),
    (r"961\s?58\s?56\s?56|961585656", "teléfono falso (961 58 56 56)"),
    (r"grupoavanzaconsultores\.com", "dominio falso (.com)"),
    (r"Cerrado permanentemente", "«Cerrado permanentemente»"),
    (r"\bDaben\b", "Daben Group"),
    (r"clasescontabilidad", "clasescontabilidad.com"),
    (r"gestor administrativo", "«gestor administrativo»"),
    (r"\blicenciad[oa] en", "«licenciado» (es Diplomado)"),
]
VETADOS_EN = [
    (r"\blawyer", "«lawyer» en página inglesa"),
    (r"\bchartered\b", "«chartered» en página inglesa"),
    (r"\bgestor\b", "«gestor» en página inglesa"),
]


class Pagina(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.h1 = 0
        self.title = ""
        self._en_title = False
        self.description = None
        self.canonical = []
        self.alternates = []  # (hreflang, href)
        self.robots = ""
        self.lang = ""
        self.jsonld = []
        self._en_jsonld = False
        self._buf = []
        self._salta = 0  # dentro de script/style
        self.texto = []
        self.hrefs = []
        self.ids = set()
        self.imgs_sin_alt = []
        self.imgs_alt_vacio = 0
        self.imgs = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and "name" in a:
            self.ids.add(a["name"])
        if tag == "html":
            self.lang = a.get("lang", "")
        elif tag == "h1":
            self.h1 += 1
        elif tag == "title":
            self._en_title = True
        elif tag == "meta":
            n = a.get("name", "").lower()
            if n == "description":
                self.description = a.get("content", "")
            elif n == "robots":
                self.robots = a.get("content", "").lower()
        elif tag == "link":
            rel = a.get("rel", "").lower().split()
            if "canonical" in rel:
                self.canonical.append(a.get("href", ""))
            if "alternate" in rel and a.get("hreflang"):
                self.alternates.append((a["hreflang"].lower(), a.get("href", "")))
            if "stylesheet" in rel or "icon" in rel or "manifest" in rel or "apple-touch-icon" in rel:
                self.hrefs.append(a.get("href", ""))
        elif tag == "script":
            self._salta += 1
            if a.get("type", "").lower() == "application/ld+json":
                self._en_jsonld = True
                self._buf = []
            if a.get("src"):
                self.hrefs.append(a["src"])
        elif tag == "style":
            self._salta += 1
        elif tag == "a" and "href" in a:
            self.hrefs.append(a["href"])
        elif tag in ("img", "source"):
            src = a.get("src") or a.get("srcset", "").split(" ")[0]
            if src:
                self.imgs.append(src)
            if tag == "img":
                if "alt" not in a:
                    self.imgs_sin_alt.append(src)
                elif not a["alt"].strip():
                    self.imgs_alt_vacio += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._en_title = False
        elif tag in ("script", "style"):
            self._salta = max(0, self._salta - 1)
            if tag == "script" and self._en_jsonld:
                self.jsonld.append("".join(self._buf))
                self._en_jsonld = False

    def handle_data(self, data):
        if self._en_jsonld:
            self._buf.append(data)
        elif self._en_title:
            self.title += data
        elif not self._salta:
            self.texto.append(data)


def normaliza(t):
    return re.sub(r"\s+", " ", html.unescape(t)).strip().lower()


def fichero_de(url):
    """URL del dominio -> fichero del repo ('' si no es del dominio)."""
    p = urlparse(url)
    if p.netloc and p.netloc not in (DOMINIO, "www." + DOMINIO):
        return ""
    ruta = p.path.lstrip("/")
    return ruta or "index.html"


def lee_sitemap(raiz):
    with open(os.path.join(raiz, "sitemap.xml"), encoding="utf-8") as f:
        return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", f.read())


def recorre_jsonld(nodo, tipos, preguntas):
    if isinstance(nodo, dict):
        t = nodo.get("@type")
        for x in (t if isinstance(t, list) else [t]):
            if x:
                tipos.add(x)
        if nodo.get("@type") == "Question" and isinstance(nodo.get("name"), str):
            preguntas.append(nodo["name"])
        for v in nodo.values():
            recorre_jsonld(v, tipos, preguntas)
    elif isinstance(nodo, list):
        for v in nodo:
            recorre_jsonld(v, tipos, preguntas)


def comprueba_repo(raiz, errores, avisos):
    urls = lee_sitemap(raiz)
    if not urls:
        errores.append("sitemap.xml sin URL")
        return urls, {}
    paginas = {}
    for u in urls:
        fch = fichero_de(u)
        ruta = os.path.join(raiz, fch)
        if not fch or not os.path.isfile(ruta):
            errores.append(f"{u}: está en el sitemap y no existe en el repositorio")
            continue
        with open(ruta, encoding="utf-8") as f:
            crudo = f.read()
        p = Pagina()
        p.feed(crudo)
        p.crudo = crudo
        p.url = u
        p.fichero = fch
        paginas[fch] = p

    # Páginas del repo que no están en el sitemap
    for fch in sorted(os.listdir(raiz)):
        if fch.endswith(".html") and fch not in paginas and fch not in SIN_INDEXAR:
            with open(os.path.join(raiz, fch), encoding="utf-8") as f:
                if "noindex" not in f.read().lower():
                    avisos.append(f"{fch}: página indexable que no está en el sitemap")

    titulos, descripciones = {}, {}
    tel_rusos = set()
    for fch, p in paginas.items():
        if fch.startswith("ru"):
            tel_rusos.update(re.findall(r'href="tel:\+?(\d+)"', p.crudo))
    tel_rusos.discard(TELEFONO_BUENO)

    for fch, p in sorted(paginas.items()):
        u = p.url
        if p.h1 != 1:
            errores.append(f"{fch}: {p.h1} H1 (debe haber uno)")
        if len(p.canonical) != 1:
            errores.append(f"{fch}: {len(p.canonical)} canonical (debe haber una)")
        elif p.canonical[0] != u:
            errores.append(f"{fch}: canonical {p.canonical[0]} distinta de la URL del sitemap {u}")
        if "noindex" in p.robots:
            errores.append(f"{fch}: está en el sitemap con noindex")
        t = normaliza(p.title)
        if not t:
            errores.append(f"{fch}: sin título")
        else:
            titulos.setdefault(t, []).append(fch)
            if len(p.title.strip()) > 60:
                avisos.append(f"{fch}: título de {len(p.title.strip())} caracteres (máximo 60)")
        if p.description is None or not p.description.strip():
            errores.append(f"{fch}: sin meta description")
        else:
            descripciones.setdefault(normaliza(p.description), []).append(fch)
            if len(p.description.strip()) > 160:
                avisos.append(f"{fch}: descripción de {len(p.description.strip())} caracteres (máximo 160)")

        # JSON-LD y FAQ
        tipos, preguntas = set(), []
        if not p.jsonld and fch not in LEGALES:
            avisos.append(f"{fch}: sin JSON-LD")
        for i, bloque in enumerate(p.jsonld, 1):
            try:
                recorre_jsonld(json.loads(bloque), tipos, preguntas)
            except json.JSONDecodeError as e:
                errores.append(f"{fch}: JSON-LD n.º {i} no se puede leer ({e.msg}, línea {e.lineno})")
        if preguntas:
            visible = normaliza(" ".join(p.texto))
            for q in preguntas:
                if normaliza(q) not in visible:
                    errores.append(f"{fch}: pregunta de FAQPage que no se ve en la página: «{q[:70]}»")

        # Enlaces internos y anclas
        for h in p.hrefs:
            h = h.strip()
            if not h or h.startswith(("mailto:", "tel:", "javascript:", "data:", "sms:")) or "wa.me" in h:
                continue
            destino = urljoin(u, h)
            dp = urlparse(destino)
            if dp.scheme not in ("http", "https") or dp.netloc not in (DOMINIO, "www." + DOMINIO):
                continue
            fd = fichero_de(destino)
            if not os.path.exists(os.path.join(raiz, fd)):
                errores.append(f"{fch}: enlace interno roto → {h}")
                continue
            if dp.fragment:
                obj = paginas.get(fd)
                if obj is None and fd.endswith(".html") and os.path.isfile(os.path.join(raiz, fd)):
                    obj = Pagina()
                    with open(os.path.join(raiz, fd), encoding="utf-8") as f:
                        obj.feed(f.read())
                if obj is not None and dp.fragment not in obj.ids:
                    errores.append(f"{fch}: ancla que no existe → {h}")
        for src in p.imgs:
            d = urljoin(u, src)
            if urlparse(d).netloc in (DOMINIO, "www." + DOMINIO) and not os.path.exists(os.path.join(raiz, fichero_de(d))):
                errores.append(f"{fch}: imagen que no existe → {src}")
        for src in p.imgs_sin_alt:
            errores.append(f"{fch}: imagen sin alt → {src}")

        # hreflang recíproco
        propio = [l for l, href in p.alternates if href == u]
        if p.alternates and not propio:
            errores.append(f"{fch}: tiene hreflang pero ninguno apunta a sí misma")
        for lang, href in p.alternates:
            if lang == "x-default" or href == u:
                continue
            otra = paginas.get(fichero_de(href))
            if otra is None:
                errores.append(f"{fch}: hreflang {lang} apunta a {href}, que no está en el sitemap")
                continue
            if not any(h2 == u for _, h2 in otra.alternates):
                errores.append(f"{fch}: hreflang {lang} → {otra.fichero} no es recíproco (esa página no apunta aquí)")

        # Normas de contenido
        for patron, que in VETADOS:
            if re.search(patron, p.crudo, re.I):
                errores.append(f"{fch}: {que}")
        if p.lang.lower().startswith("en") or fch == "en.html":
            if re.search(r'href="tel:', p.crudo):
                errores.append(f"{fch}: página inglesa con enlace de llamada (tel:)")
            visible = " ".join(p.texto)
            for patron, que in VETADOS_EN:
                if re.search(patron, visible, re.I):
                    errores.append(f"{fch}: {que}")
        if not fch.startswith("ru"):
            for tel in tel_rusos:
                cola = tel[-9:]
                if re.search(r"(?<!\d)(?:\+?34[\s.]?|0034[\s.]?)?" + r"[\s.]?".join(cola) + r"(?!\d)", p.crudo):
                    errores.append(f"{fch}: lleva el teléfono de las páginas rusas")

    for t, fchs in titulos.items():
        if len(fchs) > 1:
            errores.append(f"título duplicado en {', '.join(fchs)}")
    for d, fchs in descripciones.items():
        if len(fchs) > 1:
            errores.append(f"descripción duplicada en {', '.join(fchs)}")

    # robots.txt
    try:
        with open(os.path.join(raiz, "robots.txt"), encoding="utf-8") as f:
            robots = f.read()
        bloques = re.split(r"\n\s*\n", robots)
        for b in bloques:
            agentes = [x.strip().lower() for x in re.findall(r"(?im)^user-agent:\s*(.+)$", b)]
            if any(a in BOTS for a in agentes) and re.search(r"(?im)^disallow:\s*/\s*$", b):
                errores.append(f"robots.txt bloquea todo a {', '.join(agentes)}")
        if not re.search(r"(?im)^sitemap:\s*https://" + re.escape(DOMINIO) + r"/sitemap\.xml", robots):
            errores.append("robots.txt sin la línea Sitemap")
    except FileNotFoundError:
        errores.append("falta robots.txt")

    # llms.txt
    try:
        with open(os.path.join(raiz, "llms.txt"), encoding="utf-8") as f:
            llms = f.read()
        for u in urls:
            if u not in llms:
                avisos.append(f"llms.txt: falta {u}")
    except FileNotFoundError:
        errores.append("falta llms.txt")

    # Restos: imágenes que no usa nada
    usados = ""
    for nombre in os.listdir(raiz):
        if nombre.endswith((".html", ".css", ".js", ".webmanifest", ".txt", ".xml")):
            with open(os.path.join(raiz, nombre), encoding="utf-8", errors="ignore") as f:
                usados += f.read()
    if os.path.isdir(os.path.join(raiz, "img")):
        for img in sorted(os.listdir(os.path.join(raiz, "img"))):
            if img not in usados:
                avisos.append(f"img/{img}: no la usa ninguna página, hoja de estilo ni manifiesto")
    return urls, paginas


def descarga(url, intentos=3):
    req = urllib.request.Request(url, headers={"User-Agent": "AvanzaSalud/1.0 (+https://" + DOMINIO + "/)"})
    for i in range(intentos):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read(), r.geturl()
        except urllib.error.HTTPError as e:
            return e.code, b"", url
        except Exception as e:  # red, DNS, tiempo
            if i == intentos - 1:
                return 0, str(e).encode(), url
            time.sleep(5)


def comprueba_vivo(raiz, urls, errores, avisos, base):
    extra = [base + "robots.txt", base + "sitemap.xml", base + "llms.txt"]
    clave = [f for f in os.listdir(raiz) if re.fullmatch(r"[0-9a-f]{32}\.txt", f)]
    extra += [base + c for c in clave]
    distintas = 0
    for u in urls + extra:
        vivo = u.replace(BASE, base)
        estado, cuerpo, final = descarga(vivo)
        if estado != 200:
            errores.append(f"EN VIVO {u}: responde {estado or 'sin conexión'}")
            continue
        if urlparse(final).path != urlparse(vivo).path:
            avisos.append(f"EN VIVO {u}: redirige a {final}")
        fch = fichero_de(u)
        ruta = os.path.join(raiz, fch)
        if os.path.isfile(ruta):
            with open(ruta, "rb") as f:
                local = hashlib.sha256(f.read()).hexdigest()
            if hashlib.sha256(cuerpo).hexdigest() != local:
                distintas += 1
                errores.append(f"EN VIVO {u}: la huella SHA-256 no coincide con el repositorio")
    return distintas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", default=".")
    ap.add_argument("--vivo", action="store_true", help="comprobar también la web publicada")
    ap.add_argument("--base", default=BASE, help="otra base para probar en local")
    a = ap.parse_args()

    errores, avisos = [], []
    urls, paginas = comprueba_repo(a.raiz, errores, avisos)
    if a.vivo:
        comprueba_vivo(a.raiz, urls, errores, avisos, a.base)

    lineas = [f"# Salud de {DOMINIO}", "",
              f"{len(urls)} URL en el sitemap · {len(paginas)} páginas revisadas"
              + (" · comprobada también la web en vivo" if a.vivo else " · solo repositorio"),
              f"Errores: {len(errores)} · Avisos: {len(avisos)}", ""]
    if errores:
        lineas += ["## Errores", ""] + [f"- {e}" for e in errores] + [""]
    if avisos:
        lineas += ["## Avisos", ""] + [f"- {x}" for x in avisos] + [""]
    lineas += ["No medido aquí: desbordamiento a 390 px."]
    salida = "\n".join(lineas)
    print(salida)
    resumen = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumen:
        with open(resumen, "a", encoding="utf-8") as f:
            f.write(salida + "\n")
    sys.exit(1 if errores else 0)


if __name__ == "__main__":
    main()
