#!/usr/bin/env python3
"""Salud de grupoavanzaconsultores.es sin gastar usos de Claude.

Comprueba el repositorio (y, con --vivo, la web publicada) contra el apartado 6 de las
instrucciones del proyecto AVANZA WEB:
  - sitemap.xml válido y sin duplicados; toda URL existe en el repo y, en vivo, responde 200,
    sin redirigir y con la misma huella SHA-256 que el fichero del repo
  - un H1 con texto por página, <html lang>, canonical propia, título y descripción sin duplicados
  - JSON-LD que se puede leer; preguntas y respuestas de FAQPage visibles en la página
  - enlaces internos, anclas e imágenes (también og:image y los del CSS y el manifiesto) que existen
  - hreflang recíproco, con autorreferencia, código válido e igual a <html lang>
  - imágenes con alt; robots.txt que no bloquea a buscadores ni IA; llms.txt con todas las URL
  - formulario de contacto apuntando a su destino en la portada y en contacto
  - normas de contenido que se pueden comprobar con un programa: datos falsos, nombres que no van,
    solo los teléfonos buenos, el de las páginas rusas solo en ellas, y páginas inglesas sin
    teléfono ni términos vetados

Errores -> código de salida 1 (GitHub manda el aviso). Avisos -> se listan, sin fallar.
No mide el desbordamiento a 390 px (necesita navegador). Solo biblioteca estándar de Python.
"""
import argparse
import concurrent.futures as cf
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse

DOMINIO = "grupoavanzaconsultores.es"
BASE = f"https://{DOMINIO}/"
HOSTS = (DOMINIO, "www." + DOMINIO)
TEL_BUENO = "614365547"
TEL_RUSO = "642457458"  # el de Anna: solo en las páginas rusas
FORM_ACTION = ("https://script.google.com/macros/s/AKfycbyoZqAELFY_A94HTx9YJWfWz2ciYKSTpOVt"
               "-l4uaTbaq355slEA4b8_gP1bRqFfgfsB/exec")
SIN_INDEXAR = {"404.html", "gracias.html"}
LEGALES = {"aviso-legal.html", "cookies.html", "privacidad.html"}  # sin JSON-LD a propósito
BOTS = ["googlebot", "bingbot", "oai-searchbot", "chatgpt-user", "gptbot", "perplexitybot",
        "perplexity-user", "claude-searchbot", "claude-user", "claudebot", "applebot",
        "google-extended", "*"]
OTROS_FICHEROS = ["404.html", "gracias.html", "llms.txt", "vencimientos.js", "site.webmanifest",
                  "robots.txt", "estilo.css"]
EXTRA_VIVO = ["robots.txt", "sitemap.xml", "llms.txt", "gracias.html", "estilo.css",
              "vencimientos.js", "site.webmanifest", "favicon.ico"]

# Datos falsos o vetados (apartados 8 y 11). Se buscan en el HTML entero, código incluido.
VETADOS = [
    (r"Carrer del Castell|C/\s?Castell\b|\bCastell,?\s?(n[ºo]\.?\s?)?4\b", "dirección falsa (Castell 4)"),
    (r"961[\s.\-]?58[\s.\-]?56[\s.\-]?56", "teléfono falso (961 58 56 56)"),
    (r"grupoavanzaconsultores\.com", "dominio falso (.com)"),
    (r"Cerrado permanentemente", "«Cerrado permanentemente»"),
    (r"\bDaben\b", "Daben Group"),
    (r"clasescontabilidad", "clasescontabilidad.com"),
    (r"gestor administrativo", "«gestor administrativo»"),
    (r"\blicenciad[oa] en", "«licenciado» (es Diplomado)"),
]
VETADOS_EN = [
    (r"\blawyers?\b", "«lawyer»"),
    (r"\bchartered\b", "«chartered»"),
    (r"\bgestor\b", "«gestor»"),
]
RE_LANG = re.compile(r"^[a-z]{2}(-[A-Za-z]{2})?$")
RE_TEL = re.compile(r"(?<![\d/])(?:\+|00)?(?:34[\s.\-]?)?([6-9](?:[\s.\-]?\d){8})(?!\d)")
VACIOS = {"meta", "link", "img", "source", "br", "hr", "input", "base", "wbr", "area", "col",
          "embed", "param", "track"}


class Pagina(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.h1 = []
        self._h1 = None
        self.title = None
        self._en_title = False
        self._pila = []
        self.description = None
        self.metas = []
        self.canonical = []
        self.alternates = []
        self.robots = ""
        self.lang = None
        self.jsonld = []
        self._en_jsonld = False
        self._buf = []
        self._salta = 0
        self._oculto = 0
        self.texto = []
        self.hrefs = []
        self.recursos = []
        self.ids = set()
        self.imgs_sin_alt = []
        self.forms = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        if tag not in VACIOS:
            oculto = "hidden" in a or bool(re.search(r"display\s*:\s*none", a.get("style", ""), re.I))
            self._pila.append((tag, oculto))
            if oculto:
                self._oculto += 1
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and "name" in a:
            self.ids.add(a["name"])
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "h1":
            self._h1 = []
        elif tag == "title" and self.title is None:
            self._en_title = True
            self.title = ""
        elif tag == "meta":
            n = (a.get("name") or a.get("property") or "").lower()
            if n == "description":
                self.description = a.get("content", "")
            if n in ("robots", "googlebot", "bingbot"):
                self.robots += " " + a.get("content", "").lower()
            if n in ("og:image", "twitter:image"):
                self.recursos.append(a.get("content", ""))
            if n in ("description", "og:title", "og:description", "twitter:title", "twitter:description"):
                self.metas.append(a.get("content", ""))
        elif tag == "link":
            rel = a.get("rel", "").lower().split()
            if "canonical" in rel:
                self.canonical.append(a.get("href", ""))
            if "alternate" in rel and a.get("hreflang"):
                self.alternates.append((a["hreflang"], a.get("href", "")))
            if set(rel) & {"stylesheet", "icon", "manifest", "apple-touch-icon", "preload"}:
                self.recursos.append(a.get("href", ""))
        elif tag == "script":
            self._salta += 1
            if a.get("type", "").lower() == "application/ld+json":
                self._en_jsonld = True
                self._buf = []
            if a.get("src"):
                self.recursos.append(a["src"])
        elif tag == "style":
            self._salta += 1
        elif tag == "a" and "href" in a:
            self.hrefs.append(a["href"])
        elif tag == "form":
            self.forms.append(a.get("action", ""))
        elif tag in ("img", "source"):
            for parte in (a.get("srcset") or "").split(","):
                if parte.strip():
                    self.recursos.append(parte.strip().split(" ")[0])
            if a.get("src"):
                self.recursos.append(a["src"])
            if tag == "img" and "alt" not in a:
                self.imgs_sin_alt.append(a.get("src", "?"))

    def handle_endtag(self, tag):
        if tag == "title":
            self._en_title = False
        elif tag == "h1" and self._h1 is not None:
            self.h1.append("".join(self._h1).strip())
            self._h1 = None
        elif tag in ("script", "style"):
            self._salta = max(0, self._salta - 1)
            if tag == "script" and self._en_jsonld:
                self.jsonld.append("".join(self._buf))
                self._en_jsonld = False
        for i in range(len(self._pila) - 1, -1, -1):
            if self._pila[i][0] == tag:
                for _, oc in self._pila[i:]:
                    if oc:
                        self._oculto -= 1
                del self._pila[i:]
                break

    def handle_data(self, data):
        if self._en_jsonld:
            self._buf.append(data)
        elif self._en_title:
            self.title += data
        elif not self._salta:
            if self._h1 is not None:
                self._h1.append(data)
            if not self._oculto:
                self.texto.append(data)


def compacta(t):
    """Para comparar textos: sin etiquetas, sin entidades, sin espacios, en minúsculas."""
    t = re.sub(r"<[^>]+>", "", html.unescape(t or ""))
    return re.sub(r"\s+", "", t).lower()


def normaliza(t):
    return re.sub(r"\s+", " ", html.unescape(t or "")).strip().lower()


def fichero_de(url):
    p = urlparse(url)
    if p.netloc and p.netloc not in HOSTS:
        return ""
    ruta = unquote(p.path).lstrip("/")
    return ruta or "index.html"


def existe(raiz, fch):
    return bool(fch) and os.path.isfile(os.path.join(raiz, fch))


def lee_sitemap(raiz, errores):
    try:
        arbol = ET.parse(os.path.join(raiz, "sitemap.xml"))
    except (ET.ParseError, FileNotFoundError) as e:
        errores.append(f"sitemap.xml no se puede leer como XML ({e})")
        return []
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [(x.text or "").strip() for x in arbol.getroot().findall("s:url/s:loc", ns)]
    vistos = set()
    for u in urls:
        if u in vistos:
            errores.append(f"sitemap.xml: URL duplicada {u}")
        vistos.add(u)
        if urlparse(u).netloc != DOMINIO or not u.startswith("https://"):
            errores.append(f"sitemap.xml: URL fuera del dominio o sin https: {u}")
    return list(dict.fromkeys(urls))


def recorre_jsonld(nodo, tipos, faq):
    if isinstance(nodo, dict):
        t = nodo.get("@type")
        for x in (t if isinstance(t, list) else [t]):
            if x:
                tipos.add(x)
        if nodo.get("@type") == "Question" and isinstance(nodo.get("name"), str):
            resp = nodo.get("acceptedAnswer")
            texto = resp.get("text") if isinstance(resp, dict) else None
            faq.append((nodo["name"], texto if isinstance(texto, str) else None))
        for v in nodo.values():
            recorre_jsonld(v, tipos, faq)
    elif isinstance(nodo, list):
        for v in nodo:
            recorre_jsonld(v, tipos, faq)


def reglas_robots(txt):
    grupos, agentes, con_reglas = {}, [], False
    for linea in txt.splitlines():
        linea = linea.split("#")[0].strip()
        if ":" not in linea:
            continue
        k, v = [x.strip() for x in linea.split(":", 1)]
        k = k.lower()
        if k == "user-agent":
            if con_reglas:
                agentes, con_reglas = [], False
            agentes.append(v.lower())
            grupos.setdefault(v.lower(), [])
        elif k in ("allow", "disallow"):
            con_reglas = True
            for ag in agentes:
                grupos[ag].append((k == "allow", v))
    return grupos


def permitido(reglas, ruta):
    mejor = (-1, True)
    for permite, pat in reglas:
        if not pat:
            continue
        rx = "^" + re.escape(pat).replace(r"\*", ".*").replace(r"\$", "$")
        if re.match(rx, ruta):
            if len(pat) > mejor[0] or (len(pat) == mejor[0] and permite):
                mejor = (len(pat), permite)
    return mejor[1]


def telefonos(texto):
    return {re.sub(r"\D", "", m.group(1)) for m in RE_TEL.finditer(texto)}


def es_rusa(fch, p):
    return (p.lang or "").lower().startswith("ru") or fch == "ru.html" or fch.startswith("ru-")


def es_inglesa(fch, p):
    propio = [l.lower() for l, h in p.alternates if h == p.url and l.lower() != "x-default"]
    return (p.lang or "").lower().startswith("en") or any(l.startswith("en") for l in propio)


def comprueba_repo(raiz, errores, avisos):
    urls = lee_sitemap(raiz, errores)
    if not urls:
        errores.append("sitemap.xml sin URL")
        return urls, {}
    paginas = {}
    for u in urls:
        fch = fichero_de(u)
        if not existe(raiz, fch):
            errores.append(f"{u}: está en el sitemap y no existe en el repositorio")
            continue
        with open(os.path.join(raiz, fch), encoding="utf-8") as f:
            crudo = f.read()
        p = Pagina()
        p.feed(crudo)
        p.crudo, p.url, p.fichero = crudo, u, fch
        paginas[fch] = p

    for fch in sorted(os.listdir(raiz)):
        if fch.endswith(".html") and fch not in paginas and fch not in SIN_INDEXAR:
            with open(os.path.join(raiz, fch), encoding="utf-8") as f:
                q = Pagina()
                q.feed(f.read())
            if "noindex" not in q.robots and "none" not in q.robots.split():
                errores.append(f"{fch}: página indexable que no está en el sitemap")

    titulos, descripciones = {}, {}
    rusas = [f for f, p in paginas.items() if es_rusa(f, p)]
    if rusas and not any(TEL_RUSO in re.sub(r"\D", "", paginas[f].crudo) for f in rusas):
        errores.append("el teléfono de las páginas rusas no aparece en ninguna de ellas: revisar TEL_RUSO")

    for fch, p in sorted(paginas.items()):
        u = p.url
        if len(p.h1) != 1:
            errores.append(f"{fch}: {len(p.h1)} H1 (debe haber uno)")
        elif not p.h1[0]:
            errores.append(f"{fch}: H1 vacío")
        if not p.lang:
            errores.append(f"{fch}: <html> sin lang")
        if len(p.canonical) != 1:
            errores.append(f"{fch}: {len(p.canonical)} canonical (debe haber una)")
        elif p.canonical[0] != u:
            errores.append(f"{fch}: canonical {p.canonical[0]} distinta de la URL del sitemap {u}")
        if "noindex" in p.robots or "none" in p.robots.split():
            errores.append(f"{fch}: está en el sitemap con noindex")
        titulo = (p.title or "").strip()
        if not titulo:
            errores.append(f"{fch}: sin título")
        else:
            titulos.setdefault(normaliza(titulo), []).append(fch)
            if len(titulo) > 60:
                avisos.append(f"{fch}: título de {len(titulo)} caracteres (máximo 60)")
        if not (p.description or "").strip():
            errores.append(f"{fch}: sin meta description")
        else:
            descripciones.setdefault(normaliza(p.description), []).append(fch)
            if len(p.description.strip()) > 160:
                avisos.append(f"{fch}: descripción de {len(p.description.strip())} caracteres (máximo 160)")

        # JSON-LD y FAQ
        tipos, faq = set(), []
        if not p.jsonld and fch not in LEGALES:
            avisos.append(f"{fch}: sin JSON-LD")
        for i, bloque in enumerate(p.jsonld, 1):
            try:
                recorre_jsonld(json.loads(bloque), tipos, faq)
            except json.JSONDecodeError as e:
                errores.append(f"{fch}: JSON-LD n.º {i} no se puede leer ({e.msg}, línea {e.lineno})")
        if faq:
            visible = compacta(" ".join(p.texto))
            for q, r in faq:
                if compacta(q) not in visible:
                    errores.append(f"{fch}: pregunta de FAQPage que no se ve en la página: «{q[:70]}»")
                elif r is not None and compacta(r) not in visible:
                    errores.append(f"{fch}: la respuesta de FAQPage no coincide con la visible: «{q[:70]}»")

        # Enlaces, anclas y recursos
        for h in p.hrefs + p.recursos:
            h = (h or "").strip()
            if not h or h.startswith(("mailto:", "tel:", "javascript:", "data:", "sms:", "whatsapp:")):
                continue
            destino = urljoin(u, h)
            dp = urlparse(destino)
            if dp.scheme not in ("http", "https") or dp.netloc not in HOSTS:
                continue
            fd = fichero_de(destino)
            if not existe(raiz, fd):
                errores.append(f"{fch}: enlace o recurso interno roto → {h}")
                continue
            frag = unquote(dp.fragment)
            if frag and frag != "top" and fd.endswith(".html"):
                obj = paginas.get(fd)
                if obj is None:
                    obj = Pagina()
                    with open(os.path.join(raiz, fd), encoding="utf-8") as f:
                        obj.feed(f.read())
                if frag not in obj.ids:
                    errores.append(f"{fch}: ancla que no existe → {h}")
        for src in p.imgs_sin_alt:
            errores.append(f"{fch}: imagen sin alt → {src}")

        # hreflang
        if p.alternates:
            propios = [l for l, h in p.alternates if h == u and l.lower() != "x-default"]
            if not propios:
                errores.append(f"{fch}: tiene hreflang pero ninguno (salvo x-default) apunta a sí misma")
            elif p.lang and propios[0].lower().split("-")[0] != p.lang.lower().split("-")[0]:
                errores.append(f"{fch}: hreflang propio «{propios[0]}» distinto de <html lang=\"{p.lang}\">")
        for lang, href in p.alternates:
            if lang.lower() != "x-default" and not RE_LANG.match(lang):
                errores.append(f"{fch}: código hreflang no válido «{lang}»")
            if href == u:
                continue
            otra = paginas.get(fichero_de(href))
            if otra is None:
                errores.append(f"{fch}: hreflang {lang} apunta a {href}, que no está en el sitemap")
                continue
            if lang.lower() == "x-default":
                continue
            if not any(h2 == u for _, h2 in otra.alternates):
                errores.append(f"{fch}: hreflang {lang} → {otra.fichero} no es recíproco (esa página no apunta aquí)")
            otra_propio = [l for l, h in otra.alternates if h == otra.url and l.lower() != "x-default"]
            if otra_propio and otra_propio[0].lower() != lang.lower():
                errores.append(f"{fch}: llama «{lang}» a {otra.fichero}, que se declara «{otra_propio[0]}»")

        # Normas de contenido
        for patron, que in VETADOS:
            if re.search(patron, p.crudo, re.I):
                errores.append(f"{fch}: {que}")
        visible = " ".join(p.texto)
        tels = telefonos(visible) | {re.sub(r"\D", "", t)[-9:] for t in re.findall(r"tel:([+\d\s.\-]+)", p.crudo)}
        if es_inglesa(fch, p):
            if re.search(r"""href\s*=\s*["']?\s*tel:""", p.crudo, re.I):
                errores.append(f"{fch}: página inglesa con enlace de llamada (tel:)")
            if telefonos(visible):
                errores.append(f"{fch}: página inglesa con teléfono visible ({', '.join(sorted(telefonos(visible)))})")
            buscar = " ".join([visible, p.title or ""] + p.metas + p.jsonld)
            for patron, que in VETADOS_EN:
                if re.search(patron, buscar, re.I):
                    errores.append(f"{fch}: {que} en página inglesa")
        permitidos = {TEL_BUENO} | ({TEL_RUSO} if es_rusa(fch, p) else set())
        for t in sorted(tels - permitidos):
            if t == TEL_RUSO:
                errores.append(f"{fch}: lleva el teléfono de las páginas rusas")
            else:
                errores.append(f"{fch}: teléfono que no es el del despacho: {t}")
        if fch in ("index.html", "contacto.html") and FORM_ACTION not in p.forms:
            errores.append(f"{fch}: el formulario no apunta a su destino (action cambiado o sin <form>)")

    for t, fchs in titulos.items():
        if len(fchs) > 1:
            errores.append(f"título duplicado en {', '.join(fchs)}")
    for d, fchs in descripciones.items():
        if len(fchs) > 1:
            errores.append(f"descripción duplicada en {', '.join(fchs)}")

    # Otros ficheros públicos: datos vetados y teléfonos
    for nombre in OTROS_FICHEROS:
        ruta = os.path.join(raiz, nombre)
        if not os.path.isfile(ruta):
            if nombre in ("404.html", "gracias.html", "llms.txt", "robots.txt"):
                errores.append(f"falta {nombre}")
            continue
        with open(ruta, encoding="utf-8", errors="ignore") as f:
            contenido = f.read()
        for patron, que in VETADOS:
            if re.search(patron, contenido, re.I):
                errores.append(f"{nombre}: {que}")
        if nombre.endswith(".html"):
            q = Pagina()
            q.feed(contenido)
            texto_tel = " ".join(q.texto) + " " + " ".join(re.findall(r"tel:([+\d\s.\-]+)", contenido))
        elif nombre == "llms.txt":
            texto_tel = contenido
        else:
            texto_tel = ""  # CSS, JS y manifiesto: cifras que no son teléfonos
        for t in sorted(telefonos(texto_tel) - {TEL_BUENO}):
            errores.append(f"{nombre}: teléfono que no es el del despacho: {t}")

    # robots.txt
    try:
        with open(os.path.join(raiz, "robots.txt"), encoding="utf-8") as f:
            robots = f.read()
        grupos = reglas_robots(robots)
        rutas = ["/", "/estilo.css", "/sitemap.xml", "/llms.txt"] + ["/" + fichero_de(u) for u in urls]
        for bot in BOTS:
            reglas = grupos.get(bot, grupos.get("*", []))
            malas = [r for r in rutas if not permitido(reglas, r)]
            if malas:
                errores.append(f"robots.txt bloquea a {bot}: {', '.join(malas[:5])}")
        if not re.search(r"(?im)^sitemap:\s*https://" + re.escape(DOMINIO) + r"/sitemap\.xml", robots):
            errores.append("robots.txt sin la línea Sitemap")
    except FileNotFoundError:
        pass

    # llms.txt: todas las URL del sitemap, y nada que no exista
    try:
        with open(os.path.join(raiz, "llms.txt"), encoding="utf-8") as f:
            llms = f.read()
        for u in urls:
            if u not in llms:
                (avisos if fichero_de(u) in LEGALES else errores).append(f"llms.txt: falta {u}")
        for u in set(re.findall(r"https://" + re.escape(DOMINIO) + r"/[^\s)\]>\"']*", llms)):
            if not existe(raiz, fichero_de(u)):
                errores.append(f"llms.txt: enlace a algo que no existe → {u}")
    except FileNotFoundError:
        pass

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
    # Recursos del CSS y del manifiesto
    for nombre, patron in (("estilo.css", r"url\(\s*['\"]?([^'\")]+)"), ("site.webmanifest", r'"src"\s*:\s*"([^"]+)"')):
        ruta = os.path.join(raiz, nombre)
        if os.path.isfile(ruta):
            with open(ruta, encoding="utf-8", errors="ignore") as f:
                for ref in re.findall(patron, f.read()):
                    if not ref.startswith(("data:", "http")) and not existe(raiz, fichero_de(urljoin(BASE, ref))):
                        errores.append(f"{nombre}: recurso que no existe → {ref}")
    return urls, paginas


def descarga(url, intentos=3):
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(url + f"{sep}v={int(time.time())}",
                                 headers={"User-Agent": "AvanzaSalud/1.0 (+https://" + DOMINIO + "/)",
                                          "Cache-Control": "no-cache"})
    ultimo = (0, b"", url, "")
    for i in range(intentos):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, r.read(), r.geturl(), ""
        except urllib.error.HTTPError as e:
            ultimo = (e.code, b"", url, "")
            if e.code not in (429, 500, 502, 503, 504):
                return ultimo
        except Exception as e:  # red, DNS, tiempo
            ultimo = (0, b"", url, str(e))
        time.sleep(5 * (i + 1))
    return ultimo


def comprueba_vivo(raiz, urls, errores, base, espera):
    objetivos = list(urls)
    for f in EXTRA_VIVO:
        if existe(raiz, f):
            objetivos.append(BASE + f)
    objetivos += [BASE + c for c in os.listdir(raiz) if re.fullmatch(r"[0-9a-f]{32}\.txt", c)]
    objetivos = [u for u in dict.fromkeys(objetivos) if existe(raiz, fichero_de(u))]
    huellas = {}
    for u in objetivos:
        with open(os.path.join(raiz, fichero_de(u)), "rb") as f:
            huellas[u] = hashlib.sha256(f.read()).hexdigest()

    limite = time.time() + max(espera, 0) + 8 * 60
    pendientes = set(objetivos)
    resultados = {}
    while pendientes and time.time() < limite:
        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            futuros = {ex.submit(descarga, u.replace(BASE, base)): u for u in pendientes}
            for fu in cf.as_completed(futuros):
                resultados[futuros[fu]] = fu.result()
        pendientes = {u for u in pendientes
                      if resultados[u][0] == 200 and hashlib.sha256(resultados[u][1]).hexdigest() != huellas[u]}
        if not pendientes or espera <= 0 or time.time() + 30 > limite:
            break
        time.sleep(30)

    for u in objetivos:
        if u not in resultados:
            errores.append(f"EN VIVO {u}: sin comprobar (se agotó el tiempo)")
            continue
        estado, cuerpo, final, fallo = resultados[u]
        if estado != 200:
            errores.append(f"EN VIVO {u}: responde {estado or ('sin conexión: ' + fallo[:80])}")
            continue
        vivo = u.replace(BASE, base)
        if urlparse(final)._replace(query="").geturl() != vivo:
            errores.append(f"EN VIVO {u}: redirige a {final}")
        if hashlib.sha256(cuerpo).hexdigest() != huellas[u]:
            errores.append(f"EN VIVO {u}: la huella SHA-256 no coincide con el repositorio")


def anota(nivel, texto):
    """Anotación de GitHub Actions: se lee con la API (check-runs/<job>/annotations), sin descargar logs."""
    t = texto.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::{nivel}::{t}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", default=".")
    ap.add_argument("--vivo", action="store_true", help="comprobar también la web publicada")
    ap.add_argument("--base", default=BASE, help="otra base para probar en local")
    ap.add_argument("--espera", type=int, default=0,
                    help="segundos para reintentar las páginas cuya huella aún no coincide (tras publicar)")
    a = ap.parse_args()

    errores, avisos = [], []
    urls, paginas = comprueba_repo(a.raiz, errores, avisos)
    if a.vivo and urls:
        comprueba_vivo(a.raiz, urls, errores, a.base, a.espera)

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
    if os.environ.get("GITHUB_ACTIONS"):
        anota("notice", salida)
        for e in errores[:9]:
            anota("error", e)
    resumen = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumen:
        with open(resumen, "a", encoding="utf-8") as f:
            f.write(salida + "\n")
    sys.exit(1 if errores else 0)


if __name__ == "__main__":
    main()
