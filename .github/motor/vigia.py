#!/usr/bin/env python3
"""Vigía del motor sin consumo (capa 0): vigila, mide y avisa sin IA, en GitHub Actions.

Escribe en la rama `datos-motor`, carpeta motor/:
  cola-trabajo.md  solo lo NUEVO del día, una línea por aviso: «- TIPO · qué · dónde · AAAA-MM-DD»
  estado.json      lo ya visto, para no repetir: un aviso vuelve a salir solo si sigue sin resolver a los 7 días
Lee de esa misma carpeta: fichas.txt, listados.txt, ignorar.txt (claves silenciadas a mano).

Piezas (cada una se puede lanzar sola con --piezas):
  fichas     nuestras fichas en directorios: datos falsos (Castell 4, 961 58 56 56, .com,
             «Cerrado permanentemente»), falta de nombre o teléfono bueno, ficha caída
  presencia  listados de directorios: avisa solo cuando pasamos a salir o dejamos de salir
  caducados  fechas y plazos de la web ya vencidos o que vencen en 30 días
  sitemap    lastmod del sitemap frente a la fecha del último commit, y llms.txt frente al sitemap
  boe        normas actualizadas según la última «Vigilancia del BOE» → páginas a revisar
  menciones  RSS de Google Alerts (variable ALERTA_RSS): menciones nuevas con datos malos o sin enlace
  web        portada, formulario y sitemap en vivo (cada hora); caída = URGENTE
  indexacion Bing Webmaster, Search Console y Yandex (indexa.py), solo con sus secretos

Respeta robots.txt y pide como mucho UNA página por sitio y día (si un sitio tiene varias,
rota entre días). Sale con 1 si hay algo URGENTE (GitHub manda el correo del fallo).
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

DOMINIO = "grupoavanzaconsultores.es"
BASE = f"https://{DOMINIO}/"
UA = f"AvanzaVigia/1.0 (+https://{DOMINIO}/; vigilancia de datos propios)"
REPITE_DIAS = 7
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# --- datos buenos y malos (NAP-ENTIDAD.md) ---
MALOS = [
    ("Castell 4", re.compile(r"castell\W{0,3}(?:n[º.o]\s*)?4\b", re.I)),
    ("961 58 56 56", re.compile(r"(?:\+?34[\s.\-]?)?961[\s.\-]?58[\s.\-]?56[\s.\-]?56")),
    ("grupoavanzaconsultores.com", re.compile(r"grupoavanzaconsultores\.com", re.I)),
    ("«Cerrado permanentemente»", re.compile(r"cerrado\s+permanentemente|permanently\s+closed|"
                                            r"definitivamente\s+cerrado", re.I)),
]
NOMBRE = re.compile(r"grupo\W{0,3}avanza", re.I)
TEL_BUENO = re.compile(r"(?:\+?34[\s.\-]?)?614[\s.\-]?365[\s.\-]?547")
ESTAMOS = re.compile(r"grupo\W{0,3}avanza\W{0,3}consultores|grupoavanzaconsultores\.es", re.I)


def hoy_madrid():
    # Sin zoneinfo garantizado en el runner: UTC+1 basta para fechar el día (las piezas corren de día).
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).date()


def anota(nivel, texto):
    t = texto.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::{nivel}::{t}")


def limpia(t):
    t = re.sub(r"\s+", " ", t or "").strip()
    return t.replace("·", "-")


# ------------------------------------------------------------------ cola y estado
class Cola:
    def __init__(self, datos, hoy):
        self.datos = datos
        self.hoy = hoy
        self.ruta_estado = os.path.join(datos, "estado.json")
        self.ruta_cola = os.path.join(datos, "cola-trabajo.md")
        try:
            with open(self.ruta_estado, encoding="utf-8") as f:
                self.estado = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.estado = {}
        self.estado.setdefault("avisos", {})
        self.estado.setdefault("piezas", {})
        self.ignorar = set()
        try:
            with open(os.path.join(datos, "ignorar.txt"), encoding="utf-8") as f:
                self.ignorar = {l.split("#")[0].strip() for l in f if l.split("#")[0].strip()}
        except FileNotFoundError:
            pass
        self.vistos = {}          # clave -> línea, encontrados en esta ejecución
        self.fuentes_revisadas = set()
        self.nuevas = []
        self.urgente = False
        self.sitios_hoy = set()   # una petición por sitio y día entre fichas y presencia

    def pieza(self, nombre):
        return self.estado["piezas"].setdefault(nombre, {})

    def revisada(self, fuente):
        self.fuentes_revisadas.add(fuente)

    def aviso(self, tipo, que, donde, fuente=None, clave=None, urgente=False):
        clave = clave or f"{tipo}|{donde}|{que}"
        if clave in self.ignorar:
            return
        linea = f"- {tipo} · {limpia(que)} · {limpia(donde)} · {self.hoy.isoformat()}"
        self.vistos[clave] = (linea, fuente or donde)
        if urgente:
            self.urgente = True

    def cierra(self):
        avisos = self.estado["avisos"]
        hoy = self.hoy.isoformat()
        for clave, (linea, fuente) in self.vistos.items():
            previo = avisos.get(clave)
            if previo is None:
                emitir = True
            else:
                ultimo = dt.date.fromisoformat(previo["avisado"])
                emitir = (self.hoy - ultimo).days >= REPITE_DIAS
            if emitir:
                self.nuevas.append(linea if previo is None else linea + f" (sigue desde {previo['primera']})")
            avisos[clave] = {
                "primera": previo["primera"] if previo else hoy,
                "avisado": hoy if emitir else previo["avisado"],
                "visto": hoy,
                "fuente": fuente,
            }
        # Resueltos: solo los de fuentes revisadas hoy que ya no aparecen.
        for clave in list(avisos):
            v = avisos[clave]
            if clave not in self.vistos and v.get("fuente") in self.fuentes_revisadas:
                tipo, donde = clave.split("|")[0], v.get("fuente", "")
                if not tipo.startswith(("WEB-",)):
                    self.nuevas.append(f"- RESUELTO · ya no aparece: {limpia(clave.split('|', 2)[-1])} · "
                                       f"{limpia(donde)} · {hoy}")
                del avisos[clave]
            elif clave not in self.vistos and (self.hoy - dt.date.fromisoformat(v["visto"])).days > 60:
                del avisos[clave]  # hechos puntuales viejos (cambios de presencia…)
        self._escribe_cola()
        with open(self.ruta_estado, "w", encoding="utf-8") as f:
            json.dump(self.estado, f, ensure_ascii=False, indent=1, sort_keys=True)
        return self.nuevas

    def _escribe_cola(self):
        hoy = self.hoy.isoformat()
        previas = []
        try:
            with open(self.ruta_cola, encoding="utf-8") as f:
                texto = f.read()
            if f"<!-- dia {hoy} -->" in texto:
                previas = [l for l in texto.splitlines() if l.startswith("- ")]
        except FileNotFoundError:
            pass
        lineas = previas + [l for l in self.nuevas if l not in previas]
        cabecera = (f"<!-- dia {hoy} -->\n# Cola de trabajo del motor — {hoy}\n\n"
                    "Solo lo nuevo de hoy (o lo que sigue sin resolver a los 7 días). "
                    "Formato: TIPO · qué · dónde · fecha. Lo escribe vigia.py (GitHub Actions, sin IA).\n\n")
        with open(self.ruta_cola, "w", encoding="utf-8") as f:
            f.write(cabecera + ("\n".join(lineas) + "\n" if lineas else "(nada nuevo)\n"))


# ------------------------------------------------------------------ red
_robots = {}


def descarga(url, intentos=2, abre=None):
    """(estado HTTP, texto, error). abre= para pruebas."""
    abre = abre or urllib.request.urlopen
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
    ultimo = (0, "", "")
    for i in range(intentos):
        try:
            with abre(req, timeout=25) as r:
                datos = r.read(3_000_000)
                cs = r.headers.get_content_charset() if hasattr(r, "headers") and r.headers else None
                return getattr(r, "status", 200), datos.decode(cs or "utf-8", "replace"), ""
        except urllib.error.HTTPError as e:
            ultimo = (e.code, "", f"HTTP {e.code}")
            if e.code not in (429, 500, 502, 503, 504):
                return ultimo
        except Exception as e:
            ultimo = (0, "", str(e)[:120])
        if i + 1 < intentos:
            time.sleep(8)
    return ultimo


def robots_permite(url, abre=None):
    p = urlparse(url)
    sitio = f"{p.scheme}://{p.netloc}"
    if sitio not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        st, txt, _ = descarga(sitio + "/robots.txt", intentos=1, abre=abre)
        if st == 200:
            rp.parse(txt.splitlines())
        elif st in (401, 403):
            rp.disallow_all = True
        else:
            rp.allow_all = True
        _robots[sitio] = rp
    return _robots[sitio].can_fetch(UA, url)


def reparte_por_sitio(urls, pieza, hoy, usados=None):
    """Una URL por sitio y día (entre todas las piezas): la que lleva más tiempo sin mirar."""
    usados = usados if usados is not None else set()
    ultimas = pieza.setdefault("ultima_mirada", {})
    por_sitio = {}
    for u in urls:
        por_sitio.setdefault(urlparse(u).netloc.lower().removeprefix("www."), []).append(u)
    elegidas = []
    for sitio, lista in por_sitio.items():
        if sitio in usados:
            continue
        usados.add(sitio)
        lista.sort(key=lambda u: (ultimas.get(u, ""), u))
        elegidas.append(lista[0])
        ultimas[lista[0]] = hoy.isoformat()
    return elegidas


def lee_lista(ruta):
    """Líneas «URL | opción | opción»; # comenta."""
    filas = []
    try:
        with open(ruta, encoding="utf-8") as f:
            for l in f:
                l = l.split(" #")[0].strip()
                if not l or l.startswith("#"):
                    continue
                partes = [p.strip() for p in l.split("|")]
                filas.append((partes[0], partes[1:]))
    except FileNotFoundError:
        pass
    return filas


# ------------------------------------------------------------------ piezas
def problemas_ficha(texto, opciones=()):
    """Lista de problemas en el HTML (con JSON-LD) de una ficha propia."""
    problemas = [f"dato falso: {n}" for n, rx in MALOS if rx.search(texto)]
    if "sin-nombre" not in opciones and not NOMBRE.search(texto):
        problemas.append("falta el nombre «Grupo Avanza»")
    otros_tel = [o[4:] for o in opciones if o.startswith("tel=")]
    if "sin-tel" not in opciones:
        buenos = [TEL_BUENO] + [re.compile(r"[\s.\-]?".join(re.escape(c) for c in re.sub(r"\D", "", t)))
                                for t in otros_tel]
        if not any(rx.search(texto) for rx in buenos):
            problemas.append("falta el teléfono bueno 614 365 547")
    return problemas


def pieza_fichas(cola, datos, abre=None):
    filas = lee_lista(os.path.join(datos, "fichas.txt"))
    ops = {u: o for u, o in filas}
    pieza = cola.pieza("fichas")
    for url in reparte_por_sitio([u for u, _ in filas], pieza, cola.hoy, cola.sitios_hoy):
        if not robots_permite(url, abre):
            cola.revisada(url)
            cola.aviso("FICHA-ILEGIBLE", "robots.txt no deja leerla: comprobar a mano", url, fuente=url)
            continue
        st, txt, err = descarga(url, abre=abre)
        cola.revisada(url)
        if st in (401, 403, 429, 503) and not txt:
            cola.aviso("FICHA-ILEGIBLE", f"el sitio no deja leerla desde GitHub ({err}): comprobar a mano",
                       url, fuente=url)
            continue
        if st in (404, 410):
            cola.aviso("FICHA-CAIDA", f"la ficha ya no existe (HTTP {st})", url, fuente=url)
            continue
        if st != 200:
            cola.aviso("FICHA-ILEGIBLE", f"no se pudo leer ({err or st}): comprobar a mano si se repite", url,
                       fuente=url)
            continue
        for p in problemas_ficha(txt, ops.get(url, ())):
            cola.aviso("FICHA", p, url, fuente=url)


def pieza_presencia(cola, datos, abre=None):
    filas = lee_lista(os.path.join(datos, "listados.txt"))
    pieza = cola.pieza("presencia")
    salimos = pieza.setdefault("salimos", {})
    for url in reparte_por_sitio([u for u, _ in filas], pieza, cola.hoy, cola.sitios_hoy):
        if not robots_permite(url, abre):
            cola.revisada(url)
            cola.aviso("PRESENCIA-ILEGIBLE", "robots.txt no deja leer el listado: comprobar a mano", url,
                       fuente=url)
            continue
        st, txt, err = descarga(url, abre=abre)
        cola.revisada(url)
        if st != 200 or not txt:
            cola.aviso("PRESENCIA-ILEGIBLE", f"el listado no se puede leer ({err or st})", url, fuente=url)
            continue
        ahora = bool(ESTAMOS.search(txt))
        antes = salimos.get(url)
        salimos[url] = ahora
        if antes is None:
            print(f"presencia: línea base {url} → {'salimos' if ahora else 'no salimos'}")
        elif antes != ahora:
            # Clave con fecha: un cambio es un hecho puntual, no un problema que se resuelva.
            cola.aviso("PRESENCIA", "PASAMOS A SALIR en el listado" if ahora else "DEJAMOS DE SALIR del listado",
                       url, clave=f"PRESENCIA|{url}|{ahora}|{cola.hoy}", fuente=f"presencia-cambio:{url}")


MESES = {
    # es
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    # en
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    # fr
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
    "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
    # de
    "januar": 1, "jänner": 1, "februar": 2, "märz": 3, "maerz": 3, "juni": 6, "juli": 7,
    "oktober": 10, "dezember": 12,
    # ru (genitivo)
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
_MES = "|".join(sorted(MESES, key=len, reverse=True))
FECHA = re.compile(
    rf"(?P<d1>\d{{1,2}})\.?(?:\s+de|\s+of)?\s+(?P<m1>{_MES})(?:\s+de|,)?\s+(?:del?\s+)?(?P<a1>20\d\d)"
    rf"|(?P<m2>{_MES})\s+(?P<d2>\d{{1,2}}),?\s+(?P<a2>20\d\d)"
    r"|(?P<d3>\d{1,2})[/.\-](?P<m3>\d{1,2})[/.\-](?P<a3>20\d\d)", re.I)
PLAZO = re.compile(
    r"(hasta(?:\s+el)?|antes\s+del?|plazo|vence|vencimiento|finaliza|termina|último\s+día|ultimo\s+dia|"
    r"a\s+más\s+tardar|fecha\s+límite|vigente\s+hasta|caduca|until|deadline|expires?|no\s+later\s+than|"
    r"jusqu['’]au|avant\s+le|date\s+limite|au\s+plus\s+tard|spätestens|frist|не\s+позднее|срок)\W[^.;:!?]{0,70}$",
    re.I)
# Palabras cortas que solo cuentan pegadas a la fecha («by 30 June», «до 30 июня», «bis 30. Juni»).
PEGADA = re.compile(r"(?:\bby|\bbis(?:\s+zum)?|(?<!\w)до)\s+$", re.I)
# Fecha que no es un plazo: de consulta o actualización, de entrada en vigor, o ya contada en pasado.
NO_PLAZO = re.compile(
    r"(consultad|consulted|checked|comprobad|revisad|actualizad|updated|проверен|leíd|\bfrom\b|desde|since|"
    r"a\s+partir|\bab\b|depuis|introduced|boletín|\bboe\b|\bwas\b|\bera\b|\bfue\b|истёк|истек|\bwar\b|était|"
    r"expired|venció|terminó|finalizó)[^.;:!?]{0,30}$", re.I)
RENTA = re.compile(r"(?:campaña\s+de\s+(?:la\s+)?renta|renta)\s+(20\d\d)\b", re.I)


def fecha_de(m):
    try:
        if m.group("a1"):
            return dt.date(int(m.group("a1")), MESES[m.group("m1").lower()], int(m.group("d1")))
        if m.group("a2"):
            return dt.date(int(m.group("a2")), MESES[m.group("m2").lower()], int(m.group("d2")))
        return dt.date(int(m.group("a3")), int(m.group("m3")), int(m.group("d3")))
    except (ValueError, KeyError):
        return None


def texto_visible(h):
    h = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", h)
    h = re.sub(r"(?s)<!--.*?-->", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(h))


def caducados_en(texto, hoy, margen=30):
    """[(fecha, frase, estado)] de plazos vencidos o que vencen en `margen` días."""
    hallados = []
    for m in FECHA.finditer(texto):
        f = fecha_de(m)
        if not f or f > hoy + dt.timedelta(days=margen):
            continue
        antes = texto[max(0, m.start() - 90):m.start()]
        if not (PLAZO.search(antes) or PEGADA.search(antes)) or NO_PLAZO.search(antes):
            continue
        if f < hoy - dt.timedelta(days=365):  # fecha de corte histórica de una norma, no un plazo vivo
            continue
        cortes = [antes.rfind(x) for x in (". ", "; ", "? ", "! ")]
        ini = max(cortes) + 2 if max(cortes) >= 0 else antes.find(" ") + 1
        frase = (antes[ini:] + texto[m.start():m.end()]).strip()
        resto = re.split(r"(?<=[.;!?])\s", texto[m.end():m.end() + 80], maxsplit=1)[0]
        frase = (frase + resto)[:200]
        hallados.append((f, frase, "VENCIDO" if f < hoy else f"vence en {(f - hoy).days} días"))
    for m in RENTA.finditer(texto):
        a = int(m.group(1))
        if a + 2 <= hoy.year:
            frase = texto[max(0, m.start() - 60):m.end() + 40].strip()
            hallados.append((dt.date(a, 12, 31), frase[:180], f"Renta {a}: campaña de hace dos años o más"))
    return hallados


def pieza_caducados(cola, raiz):
    for nombre in sorted(os.listdir(raiz)):
        if not nombre.endswith(".html"):
            continue
        ruta = os.path.join(raiz, nombre)
        if os.path.getsize(ruta) < 2000:  # redirecciones (zh/ar…)
            continue
        with open(ruta, encoding="utf-8", errors="replace") as f:
            texto = texto_visible(f.read())
        fuente = f"pagina:{nombre}"
        cola.revisada(fuente)
        for fecha, frase, estado in caducados_en(texto, cola.hoy):
            cola.aviso("CADUCADO", f"{estado} ({fecha.strftime('%d/%m/%Y')}): «{frase}»", nombre, fuente=fuente,
                       clave=f"CADUCADO|{nombre}|{hashlib.sha1(frase.encode()).hexdigest()[:10]}")


def git_fecha(raiz, fichero):
    r = subprocess.run(["git", "-C", raiz, "log", "-1", "--format=%cs", "--", fichero],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def pieza_sitemap(cola, raiz):
    try:
        arbol = ET.parse(os.path.join(raiz, "sitemap.xml")).getroot()
    except (ET.ParseError, FileNotFoundError) as e:
        cola.aviso("SITEMAP", f"sitemap.xml ilegible ({e})", "sitemap.xml", urgente=True)
        return
    superficial = subprocess.run(["git", "-C", raiz, "rev-parse", "--is-shallow-repository"],
                                 capture_output=True, text=True).stdout.strip() == "true"
    desfasadas, urls = [], []
    for nodo in arbol.findall("s:url", NS):
        loc = (nodo.findtext("s:loc", default="", namespaces=NS) or "").strip()
        urls.append(loc)
        fch = (loc[len(BASE):] or "index.html") if loc.startswith(BASE) else ""
        if not fch or superficial:
            continue
        real = git_fecha(raiz, fch)
        lm = (nodo.findtext("s:lastmod", default="", namespaces=NS) or "")[:10]
        if real and lm and real > lm:
            desfasadas.append(f"{fch} ({lm}→{real})")
    cola.revisada("sitemap.xml")
    cola.revisada("llms.txt")
    if desfasadas:
        cola.aviso("SITEMAP", f"{len(desfasadas)} URL con lastmod anterior al último commit: "
                   + ", ".join(desfasadas[:6]) + (" …" if len(desfasadas) > 6 else "")
                   + " — arreglo: vigia.py --reescribe-sitemap en un PR", "sitemap.xml",
                   clave=f"SITEMAP|lastmod|{len(desfasadas)}", fuente="sitemap.xml")
    try:
        with open(os.path.join(raiz, "llms.txt"), encoding="utf-8") as f:
            llms = f.read()
        faltan = [u for u in urls if u not in llms and not re.search(r"(aviso-legal|privacidad|cookies|gracias)", u)]
        if faltan:
            cola.aviso("LLMS", f"{len(faltan)} URL del sitemap sin entrada en llms.txt: "
                       + ", ".join(u[len(BASE):] or "/" for u in faltan[:6]) + (" …" if len(faltan) > 6 else ""),
                       "llms.txt", clave=f"LLMS|faltan|{len(faltan)}", fuente="llms.txt")
    except FileNotFoundError:
        pass


def reescribe_sitemap(raiz):
    """lastmod = fecha del último commit de cada página. Para un PR; no publica nada."""
    ruta = os.path.join(raiz, "sitemap.xml")
    with open(ruta, encoding="utf-8") as f:
        xml = f.read()

    def cambia(m):
        bloque = m.group(0)
        loc = re.search(r"<loc>([^<]+)</loc>", bloque).group(1)
        fch = loc[len(BASE):] or "index.html"
        real = git_fecha(raiz, fch)
        if not real:
            return bloque
        if "<lastmod>" in bloque:
            return re.sub(r"<lastmod>[^<]*</lastmod>", f"<lastmod>{real}</lastmod>", bloque)
        return bloque.replace("</loc>", f"</loc><lastmod>{real}</lastmod>", 1)

    nuevo = re.sub(r"<url>.*?</url>", cambia, xml, flags=re.S)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(nuevo)
    return nuevo != xml


def pieza_boe(cola):
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not (repo and os.environ.get("GH_TOKEN")):
        print("boe: sin GH_TOKEN/GITHUB_REPOSITORY, se salta")
        return

    def gh(ruta):
        r = subprocess.run(["gh", "api", ruta], capture_output=True, text=True)
        return json.loads(r.stdout) if r.returncode == 0 else None

    runs = gh(f"repos/{repo}/actions/workflows/boe.yml/runs?status=completed&per_page=1")
    if not runs or not runs.get("workflow_runs"):
        return
    run = runs["workflow_runs"][0]
    cola.revisada("boe")
    for job in (gh(f"repos/{repo}/actions/runs/{run['id']}/jobs") or {}).get("jobs", []):
        for an in gh(f"repos/{repo}/check-runs/{job['id']}/annotations?per_page=100") or []:
            msg = an.get("message") or ""
            if an.get("annotation_level") == "failure" and "actualizada el" in msg:
                cola.aviso("NORMA", msg.splitlines()[0][:400], f"Vigilancia del BOE run {run['id']}",
                           fuente="boe", clave=f"NORMA|{hashlib.sha1(msg.encode()).hexdigest()[:12]}")


def pieza_menciones(cola, abre=None):
    rss = os.environ.get("ALERTA_RSS", "").strip()
    if not rss:
        print("menciones: sin ALERTA_RSS, se salta")
        return
    st, txt, err = descarga(rss, abre=abre)
    if st != 200:
        cola.aviso("MENCION-ILEGIBLE", f"el RSS de Google Alerts no responde ({err or st})", "ALERTA_RSS")
        return
    pieza = cola.pieza("menciones")
    vistas = set(pieza.setdefault("vistas", []))
    try:
        raiz = ET.fromstring(txt)
    except ET.ParseError:
        cola.aviso("MENCION-ILEGIBLE", "el RSS de Google Alerts no es XML", "ALERTA_RSS")
        return
    atom = "{http://www.w3.org/2005/Atom}"
    nuevas = []
    for e in raiz.iter(f"{atom}entry"):
        enlace = e.find(f"{atom}link")
        href = enlace.get("href") if enlace is not None else ""
        m = re.search(r"[?&]url=([^&]+)", href)
        destino = urllib.request.unquote(m.group(1)) if m else href
        if destino and destino not in vistas:
            nuevas.append((destino, texto_visible(e.findtext(f"{atom}title") or "")))
    sitios_hoy = set()
    for destino, titulo in nuevas:
        sitio = urlparse(destino).netloc
        if sitio in sitios_hoy or urlparse(destino).netloc.endswith(DOMINIO):
            continue
        sitios_hoy.add(sitio)
        vistas.add(destino)
        estado = "sin leer (robots)"
        if robots_permite(destino, abre):
            st, pag, _ = descarga(destino, intentos=1, abre=abre)
            if st == 200:
                malos = [n for n, rx in MALOS if rx.search(pag)]
                enlaza = DOMINIO in pag
                estado = ("DATOS MALOS: " + ", ".join(malos) + "; " if malos else "") + \
                         ("enlaza a la web" if enlaza else "SIN ENLACE a la web")
            else:
                estado = f"no se pudo leer ({st})"
        cola.aviso("MENCION", f"{titulo[:120]} — {estado}", destino, clave=f"MENCION|{destino}",
                   fuente=f"mencion:{destino}")
    pieza["vistas"] = sorted(vistas)[-500:]


def pieza_web(cola, raiz, abre=None):
    """Cada hora: portada, formulario y sitemap en vivo; huella del sitemap igual a la del repositorio."""
    pieza = cola.pieza("web")
    fallos = []
    st, txt, err = descarga(BASE, intentos=3, abre=abre)
    if st != 200 or "Grupo Avanza" not in txt:
        fallos.append(("portada", f"portada {err or st}"))
    st, txt, err = descarga(BASE + "contacto.html", intentos=3, abre=abre)
    if st != 200 or "<form" not in txt:
        fallos.append(("formulario", f"contacto.html sin formulario ({err or st})"))
    elif "script.google.com/macros" not in txt:
        fallos.append(("formulario", "contacto.html: el formulario ya no apunta al script de Google"))
    st, txt, err = descarga(BASE + "sitemap.xml", intentos=3, abre=abre)
    with open(os.path.join(raiz, "sitemap.xml"), "rb") as f:
        repo = hashlib.sha256(f.read()).hexdigest()
    vivo = hashlib.sha256(txt.encode("utf-8")).hexdigest() if st == 200 else ""
    distinto = pieza.get("sitemap_distinto", 0)
    if st != 200:
        fallos.append(("sitemap", f"sitemap.xml {err or st}"))
    elif vivo != repo:
        distinto += 1
        if distinto >= 2:  # una publicación tarda unos minutos en servirse: dos horas seguidas = problema
            fallos.append(("sitemap", f"huella del sitemap en vivo ({vivo[:8]}) distinta de la del repositorio "
                                      f"({repo[:8]}) dos horas seguidas"))
    else:
        distinto = 0
    pieza["sitemap_distinto"] = distinto
    pieza["ultima"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
    cola.revisada("web")
    for parte, texto in fallos:
        cola.aviso("WEB-URGENTE", texto, BASE, fuente="web", clave=f"WEB-URGENTE|{parte}", urgente=True)
    return fallos


# ------------------------------------------------------------------ principal
DIARIAS = ["fichas", "presencia", "caducados", "sitemap", "boe", "menciones", "indexacion"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", default=".")
    ap.add_argument("--datos", default="datos/motor")
    ap.add_argument("--piezas", default=",".join(DIARIAS), help="lista separada por comas, o «web»")
    ap.add_argument("--hoy", default="")
    ap.add_argument("--reescribe-sitemap", action="store_true")
    a = ap.parse_args(argv)
    if a.reescribe_sitemap:
        print("sitemap cambiado" if reescribe_sitemap(a.raiz) else "sitemap ya al día")
        return 0
    hoy = dt.date.fromisoformat(a.hoy) if a.hoy else hoy_madrid()
    os.makedirs(a.datos, exist_ok=True)
    cola = Cola(a.datos, hoy)
    piezas = [p.strip() for p in a.piezas.split(",") if p.strip()]
    for p in piezas:
        try:
            if p == "fichas":
                pieza_fichas(cola, a.datos)
            elif p == "presencia":
                pieza_presencia(cola, a.datos)
            elif p == "caducados":
                pieza_caducados(cola, a.raiz)
            elif p == "sitemap":
                pieza_sitemap(cola, a.raiz)
            elif p == "boe":
                pieza_boe(cola)
            elif p == "menciones":
                pieza_menciones(cola)
            elif p == "web":
                pieza_web(cola, a.raiz)
            elif p == "indexacion":
                import indexa
                indexa.ejecuta(cola, a.raiz)
            else:
                anota("warning", f"pieza desconocida: {p}")
        except Exception as e:  # una pieza rota no tumba las demás, pero se ve
            anota("error", f"pieza {p} ha fallado: {type(e).__name__}: {e}")
            cola.aviso("MOTOR", f"la pieza {p} ha fallado: {type(e).__name__}: {str(e)[:150]}", "vigia.py",
                       clave=f"MOTOR|{p}")
    nuevas = cola.cierra()
    for l in nuevas:
        anota("error" if "URGENTE" in l else "notice", l[2:])
    print(f"{len(nuevas)} línea(s) nuevas en la cola")
    return 1 if cola.urgente else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())
