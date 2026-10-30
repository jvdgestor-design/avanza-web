"""Indexación y medición por API, sin IA (pieza «indexacion» de vigia.py).

Cada bloque se salta solo si falta su secreto, y lo dice en el registro:
  BING_API_KEY  Bing Webmaster API: SubmitUrlBatch de lo nuevo o cambiado y, con la cuota que sobre,
                de lo que Bing no ha rastreado; cuota, páginas en índice, dominios enlazantes, errores de rastreo.
                Doc: learn.microsoft.com/en-us/bingwebmaster/getting-access y
                learn.microsoft.com/en-us/dotnet/api/microsoft.bing.webmaster.api.interfaces.iwebmasterapi
  GSC_KEY       Search Console API (JSON de cuenta de servicio): inspección de cada URL del sitemap
                (cupo 2.000/día y 600/min por propiedad) y consultas en posición 5-30 → candidatas a título.
                Doc: developers.google.com/webmaster-tools/v1/urlInspection.index/inspect,
                developers.google.com/webmaster-tools/v1/searchanalytics/query, …/webmaster-tools/limits
                La Indexing API de Google NO se usa: es solo para JobPosting y BroadcastEvent.
  YANDEX_TOKEN  Yandex Webmaster API v4: cola de recrawl con lo nuevo o cambiado, hasta la cuota del día.
                Doc: yandex.com/dev/webmaster/doc/en/reference/host-recrawl-post y …/host-recrawl-quota-get
Escribe métricas diarias en motor/metricas.csv (una fila por día).
"""
import datetime as dt
import hashlib
import html
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

DOMINIO = "grupoavanzaconsultores.es"
BASE = f"https://{DOMINIO}/"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
BING = "https://ssl.bing.com/webmaster/api.svc/json/"
YANDEX = "https://api.webmaster.yandex.net/v4"
GSC_INSPECT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
GSC_QUERY = "https://www.googleapis.com/webmasters/v3/sites/{}/searchAnalytics/query"
BING_REVISA_DIA = 30          # GetUrlInfo por día (rota por el sitemap)
REENVIO_DIAS = 7              # una URL no rastreada no se reenvía a Bing antes de 7 días
TITULO_ESPERA = 28            # cuatro semanas desde el último cambio de título o descripción
GSC_MIN_IMPR = 20


class ErrorApi(Exception):
    pass


def pide(url, metodo="GET", cuerpo=None, cabeceras=None, abre=None):
    abre = abre or urllib.request.urlopen
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    h = {"User-Agent": "AvanzaVigia/1.0", "Accept": "application/json"}
    if datos is not None:
        h["Content-Type"] = "application/json; charset=utf-8"
    h.update(cabeceras or {})
    req = urllib.request.Request(url, data=datos, method=metodo, headers=h)
    try:
        with abre(req, timeout=40) as r:
            txt = r.read().decode("utf-8", "replace")
            return getattr(r, "status", 200), (json.loads(txt) if txt.strip() else None)
    except urllib.error.HTTPError as e:
        try:
            cuerpo_err = json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            cuerpo_err = None
        return e.code, cuerpo_err


def fecha_ms(v):
    """Bing serializa DateTime como «/Date(ms±zzzz)/» (WCF; no consta en la doc) o ISO: se aceptan los dos."""
    if not v:
        return None
    m = re.search(r"/Date\((-?\d+)", str(v))
    if m:
        ms = int(m.group(1))
        return None if ms <= 0 else dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date()
    try:
        d = dt.date.fromisoformat(str(v)[:10])
        return None if d.year < 2000 else d
    except ValueError:
        return None


def urls_sitemap(raiz):
    arbol = ET.parse(os.path.join(raiz, "sitemap.xml")).getroot()
    return [(x.text or "").strip() for x in arbol.findall("s:url/s:loc", NS)]


def fichero_de(url):
    return url[len(BASE):] or "index.html"


def git(raiz, *args):
    r = subprocess.run(["git", "-C", raiz, *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def cambiadas(raiz, est, urls):
    """URL nuevas en el sitemap o con su página cambiada desde la última ejecución."""
    previas = set(est.get("urls", []))
    nuevas = [u for u in urls if previas and u not in previas]
    sha = est.get("sha")
    tocadas = []
    if sha and git(raiz, "cat-file", "-e", sha + "^{commit}") is not None:
        ficheros = set((git(raiz, "diff", "--name-only", sha, "HEAD") or "").split("\n"))
        tocadas = [u for u in urls if fichero_de(u) in ficheros]
    return list(dict.fromkeys(nuevas + tocadas))


# ------------------------------------------------------------------ Bing
def bing(cola, urls, cambios, est, metr, clave, abre=None):
    def get(metodo, **q):
        q.update(siteUrl=BASE, apikey=clave)
        st, r = pide(BING + metodo + "?" + urllib.parse.urlencode(q), abre=abre)
        if st != 200:
            raise ErrorApi(f"Bing {metodo}: HTTP {st} {str(r)[:150]}")
        return (r or {}).get("d")

    def envia(lista):
        for i in range(0, len(lista), 500):
            st, r = pide(BING + "SubmitUrlBatch?" + urllib.parse.urlencode({"apikey": clave}), "POST",
                         {"siteUrl": BASE, "urlList": lista[i:i + 500]}, abre=abre)
            if st != 200:
                raise ErrorApi(f"Bing SubmitUrlBatch: HTTP {st} {str(r)[:150]}")

    hoy = cola.hoy
    cuota = (get("GetUrlSubmissionQuota") or {}).get("DailyQuota", 0) or 0
    metr["bing_cuota"] = cuota
    enviadas = est.setdefault("enviadas", {})
    lote = cambios[:cuota]
    # Rastreo: GetUrlInfo de una tanda que rota por el sitemap (LastCrawledDate vacía = no rastreada).
    rastreo = est.setdefault("rastreo", {})
    orden = sorted(urls, key=lambda u: rastreo.get(u, {}).get("mirada", ""))
    for u in orden[:BING_REVISA_DIA]:
        info = get("GetUrlInfo", url=u) or {}
        ult = fecha_ms(info.get("LastCrawledDate"))
        rastreo[u] = {"mirada": hoy.isoformat(), "rastreo": ult.isoformat() if ult else "",
                      "http": info.get("HttpStatus")}
    sin_rastrear = [u for u in urls if u in rastreo and not rastreo[u]["rastreo"]]
    metr["bing_sin_rastrear"] = len(sin_rastrear)
    sobra = cuota - len(lote)
    for u in sin_rastrear:
        if sobra <= 0:
            break
        ult = enviadas.get(u)
        if u not in lote and (not ult or (hoy - dt.date.fromisoformat(ult)).days >= REENVIO_DIAS):
            lote.append(u)
            sobra -= 1
    if lote:
        envia(lote)
        for u in lote:
            enviadas[u] = hoy.isoformat()
        cola.aviso("BING-ENVIO", f"{len(lote)} URL enviadas por API ({len(cambios)} nuevas o cambiadas; "
                   f"cuota del día {cuota})", "Bing Webmaster", clave=f"BING-ENVIO|{hoy}", fuente="bing-envio")
    # Índice y enlaces
    stats = get("GetCrawlStats") or []
    if stats:
        ultimo = max(stats, key=lambda s: fecha_ms(s.get("Date")) or dt.date.min)
        metr["bing_en_indice"] = ultimo.get("InIndex")
        metr["bing_errores_rastreo"] = ultimo.get("CrawlErrors")
    links = (get("GetLinkCounts", page=0) or {}).get("Links") or []
    dominios = sorted({urllib.parse.urlparse(l.get("Url", "")).netloc.lower().removeprefix("www.")
                       for l in links if l.get("Url")} - {"", DOMINIO})
    metr["bing_dominios"] = len(dominios)
    antes = est.get("dominios", [])
    nuevos = [d for d in dominios if d not in antes]
    if antes and nuevos:
        cola.aviso("BING-ENLACE", f"dominio(s) enlazante(s) nuevo(s): {', '.join(nuevos)} (total {len(dominios)})",
                   "Bing Webmaster", clave=f"BING-ENLACE|{','.join(nuevos)}", fuente="bing-enlace")
    est["dominios"] = dominios
    en_ind = metr.get("bing_en_indice") or 0
    if len(dominios) >= 6 or en_ind > len(urls) / 2:
        cola.aviso("CONGELADO", f"se cumple la condición para levantar el congelado de páginas nuevas "
                   f"(dominios enlazantes {len(dominios)}, en índice {en_ind} de {len(urls)}): decide Jose",
                   "Bing Webmaster", clave="CONGELADO|bing", fuente="bing")
    cola.revisada("bing")
    for issue in (get("GetCrawlIssues") or [])[:50]:
        u = issue.get("Url", "")
        if u.startswith(BASE):
            cola.aviso("BING-RASTREO", f"error de rastreo {issue.get('HttpCode')} ({issue.get('Issues')})", u,
                       fuente="bing", clave=f"BING-RASTREO|{u}")


# ------------------------------------------------------------------ Search Console
def token_google(clave_json):
    from google.oauth2 import service_account  # pip install google-auth (solo si hay GSC_KEY)
    import google.auth.transport.requests
    cred = service_account.Credentials.from_service_account_info(
        json.loads(clave_json), scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    cred.refresh(google.auth.transport.requests.Request())
    return cred.token


def huellas_titulo(raiz, est, hoy):
    """titulos.json: desde cuándo lleva cada página su título y descripción actuales."""
    for fch in sorted(os.listdir(raiz)):
        if not fch.endswith(".html"):
            continue
        with open(os.path.join(raiz, fch), encoding="utf-8", errors="replace") as f:
            h = f.read(20000)
        t = re.search(r"<title>(.*?)</title>", h, re.S)
        d = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', h)
        huella = hashlib.sha1(((t.group(1) if t else "") + "|" + (d.group(1) if d else "")).encode()).hexdigest()[:12]
        previo = est.get(fch)
        if not previo or previo["huella"] != huella:
            desde = hoy.isoformat() if previo else (git(raiz, "log", "-1", "--format=%cs", "--", fch) or hoy.isoformat())
            est[fch] = {"huella": huella, "desde": desde,
                        "titulo": html.unescape(t.group(1).strip()) if t else ""}
    return est


def gsc(cola, raiz, urls, est, metr, clave_json, titulos, abre=None, token=None):
    tok = token or token_google(clave_json)
    cab = {"Authorization": f"Bearer {tok}"}
    sitio = os.environ.get("GSC_SITE") or est.get("sitio") or f"sc-domain:{DOMINIO}"
    hoy = cola.hoy
    estados = est.setdefault("indexacion", {})
    no_index = []
    for i, u in enumerate(urls):
        st, r = pide(GSC_INSPECT, "POST", {"inspectionUrl": u, "siteUrl": sitio, "languageCode": "es"}, cab, abre)
        if st == 403 and i == 0 and sitio.startswith("sc-domain:"):
            sitio = BASE   # propiedad de prefijo de URL
            st, r = pide(GSC_INSPECT, "POST", {"inspectionUrl": u, "siteUrl": sitio, "languageCode": "es"}, cab, abre)
        if st != 200:
            raise ErrorApi(f"Search Console inspect: HTTP {st} {str(r)[:200]}")
        res = (r or {}).get("inspectionResult", {}).get("indexStatusResult", {})
        verdicto, cobertura = res.get("verdict", ""), res.get("coverageState", "")
        antes = estados.get(u, {}).get("verdict")
        estados[u] = {"verdict": verdicto, "cobertura": cobertura, "mirada": hoy.isoformat()}
        if verdicto != "PASS":
            no_index.append(u)
            cola.aviso("GSC-NOINDEX", f"Google: {cobertura or verdicto}" + (" (antes indexada)" if antes == "PASS" else ""),
                       u, fuente="gsc", clave=f"GSC-NOINDEX|{u}")
    est["sitio"] = sitio
    metr["gsc_indexadas"] = len(urls) - len(no_index)
    metr["gsc_sin_indexar"] = len(no_index)
    cola.revisada("gsc")
    # Consultas en posición 5-30 → candidatas a título o descripción (regla F), respetando 4 semanas.
    fin = hoy - dt.timedelta(days=3)
    cuerpo = {"startDate": (fin - dt.timedelta(days=27)).isoformat(), "endDate": fin.isoformat(),
              "dimensions": ["query", "page"], "rowLimit": 5000, "type": "web"}
    st, r = pide(GSC_QUERY.format(urllib.parse.quote(sitio, safe="")), "POST", cuerpo, cab, abre)
    if st != 200:
        raise ErrorApi(f"Search Console query: HTTP {st} {str(r)[:200]}")
    por_pagina = {}
    clics = impr = 0
    for fila in (r or {}).get("rows", []):
        consulta, pagina = fila["keys"]
        clics += fila.get("clicks", 0)
        impr += fila.get("impressions", 0)
        if 5 <= fila.get("position", 0) <= 30 and fila.get("impressions", 0) >= GSC_MIN_IMPR:
            por_pagina.setdefault(pagina.split("#")[0].split("?")[0], []).append(fila)
    metr["gsc_clics_28d"], metr["gsc_impr_28d"] = round(clics), round(impr)
    cola.revisada("gsc-titulo")
    for pagina, filas in sorted(por_pagina.items(), key=lambda kv: -sum(f["impressions"] for f in kv[1]))[:10]:
        fch = fichero_de(pagina) if pagina.startswith(BASE) else ""
        reg = titulos.get(fch)
        if not reg:
            continue
        dias = (hoy - dt.date.fromisoformat(reg["desde"])).days
        if dias < TITULO_ESPERA:
            continue
        filas.sort(key=lambda f: -f["impressions"])
        top = "; ".join(f"«{f['keys'][0]}» {round(f['impressions'])} impr. pos. {f['position']:.1f}" for f in filas[:3])
        cola.aviso("GSC-TITULO", f"candidata a título/descripción (regla F; título actual «{reg['titulo'][:70]}», "
                   f"sin cambios desde {reg['desde']}): {top}", fch, fuente="gsc-titulo", clave=f"GSC-TITULO|{fch}")


# ------------------------------------------------------------------ Yandex
def yandex(cola, cambios, est, metr, token, abre=None):
    cab = {"Authorization": f"OAuth {token}"}
    user = est.get("user_id")
    if not user:
        st, r = pide(f"{YANDEX}/user", cabeceras=cab, abre=abre)
        if st != 200:
            raise ErrorApi(f"Yandex user: HTTP {st} {str(r)[:150]}")
        user = r["user_id"]
    host = est.get("host_id")
    if not host:
        st, r = pide(f"{YANDEX}/user/{user}/hosts", cabeceras=cab, abre=abre)
        if st != 200:
            raise ErrorApi(f"Yandex hosts: HTTP {st} {str(r)[:150]}")
        hosts = [h for h in r.get("hosts", []) if DOMINIO in (h.get("ascii_host_url") or "")]
        if not hosts:
            raise ErrorApi(f"Yandex: {DOMINIO} no está entre los sitios de la cuenta")
        host = hosts[0]["host_id"]
    est.update(user_id=user, host_id=host)
    base = f"{YANDEX}/user/{user}/hosts/{urllib.parse.quote(host, safe='')}"
    st, q = pide(f"{base}/recrawl/quota", cabeceras=cab, abre=abre)
    if st != 200:
        raise ErrorApi(f"Yandex quota: HTTP {st} {str(q)[:150]}")
    resto = q.get("quota_remainder", 0)
    metr["yandex_cuota"] = resto
    hechas = 0
    for u in cambios:
        if hechas >= resto:
            break
        st, r = pide(f"{base}/recrawl/queue", "POST", {"url": u}, cab, abre)
        if st in (200, 202):
            hechas += 1
        elif st == 409:   # URL_ALREADY_ADDED
            continue
        elif st == 429:
            break
        else:
            raise ErrorApi(f"Yandex recrawl {u}: HTTP {st} {str(r)[:150]}")
    if hechas:
        cola.aviso("YANDEX-ENVIO", f"{hechas} URL en la cola de recrawl", "Yandex Webmaster",
                   clave=f"YANDEX-ENVIO|{cola.hoy}", fuente="yandex-envio")


# ------------------------------------------------------------------ principal
def guarda_metricas(datos, hoy, metr):
    ruta = os.path.join(datos, "metricas.csv")
    campos = ["fecha", "bing_cuota", "bing_en_indice", "bing_dominios", "bing_sin_rastrear", "bing_errores_rastreo",
              "gsc_indexadas", "gsc_sin_indexar", "gsc_clics_28d", "gsc_impr_28d", "yandex_cuota"]
    filas = []
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            filas = [l.rstrip("\n") for l in f if l.strip()][1:]
    filas = [l for l in filas if not l.startswith(hoy.isoformat())]
    filas.append(",".join([hoy.isoformat()] + [str(metr.get(c, "")) for c in campos[1:]]))
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(",".join(campos) + "\n" + "\n".join(filas) + "\n")


def ejecuta(cola, raiz, entorno=None, abre=None, token_gsc=None):
    env = entorno if entorno is not None else os.environ
    est = cola.pieza("indexacion")
    urls = urls_sitemap(raiz)
    cambios = cambiadas(raiz, est, urls)
    metr = {}
    fallos = []
    titulos = huellas_titulo(raiz, cola.pieza("titulos"), cola.hoy)
    with open(os.path.join(cola.datos, "titulos.json"), "w", encoding="utf-8") as f:
        json.dump(titulos, f, ensure_ascii=False, indent=1, sort_keys=True)
    for nombre, secreto, fn in (
            ("bing", "BING_API_KEY", lambda k: bing(cola, urls, cambios, est.setdefault("bing", {}), metr, k, abre)),
            ("gsc", "GSC_KEY", lambda k: gsc(cola, raiz, urls, est.setdefault("gsc", {}), metr, k, titulos, abre,
                                             token_gsc)),
            ("yandex", "YANDEX_TOKEN", lambda k: yandex(cola, cambios, est.setdefault("yandex", {}), metr, k, abre))):
        k = (env.get(secreto) or "").strip()
        if not k:
            print(f"indexacion: sin {secreto}, se salta {nombre}")
            continue
        try:
            fn(k)
        except Exception as e:
            fallos.append(f"{nombre}: {type(e).__name__}: {str(e)[:200]}")
            cola.aviso("MOTOR", f"{nombre} ha fallado: {str(e)[:200]}", "indexa.py", clave=f"MOTOR|indexa-{nombre}")
    est["urls"] = urls
    sha = git(raiz, "rev-parse", "HEAD")
    if sha:
        est["sha"] = sha
    if metr:
        guarda_metricas(cola.datos, cola.hoy, metr)
    return metr, fallos
