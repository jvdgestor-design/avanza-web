"""Indexación y medición por API, sin IA (pieza «indexacion» de vigia.py).

Cada bloque se salta solo si falta su secreto, y lo dice en el registro:
  BING_API_KEY  Bing Webmaster API: SubmitUrlBatch de lo nuevo o cambiado (cola de pendientes que no se pierde)
                y, con la cuota que sobre, de lo que Bing no ha rastreado; cuota, páginas en índice, dominios
                enlazantes (GetLinkCounts → GetUrlLinks), errores de rastreo.
                Doc: learn.microsoft.com/en-us/bingwebmaster/getting-access y
                learn.microsoft.com/en-us/dotnet/api/microsoft.bing.webmaster.api.interfaces.iwebmasterapi
  GSC_KEY       Search Console API (JSON de cuenta de servicio): inspección de cada URL del sitemap
                (cupo 2.000/día y 600/min por propiedad) y consultas en posición 5-30 → candidatas a título.
                Doc: developers.google.com/webmaster-tools/v1/urlInspection.index/inspect,
                developers.google.com/webmaster-tools/v1/searchanalytics/query, …/webmaster-tools/limits
                La Indexing API de Google NO se usa: es solo para JobPosting y BroadcastEvent.
  YANDEX_TOKEN  Yandex Webmaster API v4: cola de recrawl con lo nuevo o cambiado, hasta la cuota del día.
                Doc: yandex.com/dev/webmaster/doc/en/reference/host-recrawl-post y …/host-recrawl-quota-get
Primero se envía y después se mide: un fallo al medir no deja nada sin enviar.
En la cola pública solo van códigos de error, nunca el cuerpo de una respuesta.
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
BING_ENLACES_DIA = 30         # llamadas a GetUrlLinks por día
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


def codigo(r):
    """Solo el código de error de la respuesta (Yandex: error_code; Google: error.status), nunca el cuerpo."""
    if isinstance(r, dict):
        if isinstance(r.get("error"), dict):
            return str(r["error"].get("status") or r["error"].get("code") or "")[:40]
        return str(r.get("error_code") or r.get("ErrorCode") or "")[:40]
    return ""


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


def encola(est, clave, urls, vigentes):
    """Pendientes de envío que sobreviven entre ejecuciones (solo las que siguen en el sitemap)."""
    pend = [u for u in est.get(clave, []) if u in vigentes]
    est[clave] = list(dict.fromkeys(pend + [u for u in urls if u in vigentes]))
    return est[clave]


# ------------------------------------------------------------------ Bing
def bing(cola, urls, cambios, est, metr, clave, abre=None):
    def get(metodo, **q):
        q.update(siteUrl=BASE, apikey=clave)
        st, r = pide(BING + metodo + "?" + urllib.parse.urlencode(q), abre=abre)
        if st != 200:
            raise ErrorApi(f"Bing {metodo}: HTTP {st} {codigo(r)}".strip())
        return (r or {}).get("d")

    hoy = cola.hoy
    vigentes = set(urls)
    pendientes = encola(est, "pendientes", cambios, vigentes)
    # 1) Enviar: cuota del día menos lo que ya enviamos hoy (la doc no dice si DailyQuota es total o resto).
    cuota = (get("GetUrlSubmissionQuota") or {}).get("DailyQuota", 0) or 0
    hoy_iso = hoy.isoformat()
    ya_hoy = est.get("enviadas_hoy", {}).get(hoy_iso, 0)
    disponible = max(0, cuota - ya_hoy)
    metr["bing_cuota"] = cuota
    enviadas = est.setdefault("enviadas", {})
    rastreo = est.setdefault("rastreo", {})
    lote = pendientes[:disponible]
    sobra = disponible - len(lote)
    for u in [u for u in urls if u in rastreo and not rastreo[u]["rastreo"]]:
        if sobra <= 0:
            break
        ult = enviadas.get(u)
        if u not in lote and (not ult or (hoy - dt.date.fromisoformat(ult)).days >= REENVIO_DIAS):
            lote.append(u)
            sobra -= 1
    for i in range(0, len(lote), 500):
        trozo = lote[i:i + 500]
        st, r = pide(BING + "SubmitUrlBatch?" + urllib.parse.urlencode({"apikey": clave}), "POST",
                     {"siteUrl": BASE, "urlList": trozo}, abre=abre)
        if st != 200:
            raise ErrorApi(f"Bing SubmitUrlBatch: HTTP {st} {codigo(r)}".strip())
        for u in trozo:
            enviadas[u] = hoy_iso
        est["pendientes"] = [u for u in est["pendientes"] if u not in trozo]
        est["enviadas_hoy"] = {hoy_iso: ya_hoy + i + len(trozo)}
    if lote:
        cola.aviso("BING-ENVIO", f"{len(lote)} URL enviadas por API (cuota del día {cuota}; quedan "
                   f"{len(est['pendientes'])} pendientes)", "Bing Webmaster", clave=f"BING-ENVIO|{hoy}",
                   fuente="bing-envio")
    # 2) Medir. Rastreo: GetUrlInfo de una tanda que rota por el sitemap.
    orden = sorted(urls, key=lambda u: rastreo.get(u, {}).get("mirada", ""))
    for u in orden[:BING_REVISA_DIA]:
        info = get("GetUrlInfo", url=u) or {}
        ult = fecha_ms(info.get("LastCrawledDate"))
        rastreo[u] = {"mirada": hoy_iso, "rastreo": ult.isoformat() if ult else "", "http": info.get("HttpStatus")}
    if all(u in rastreo for u in urls):   # el dato solo vale cuando la rotación ha pasado por todo el sitemap
        metr["bing_sin_rastrear"] = sum(1 for u in urls if not rastreo[u]["rastreo"])
    stats = get("GetCrawlStats") or []
    if stats:
        ultimo = max(stats, key=lambda s: fecha_ms(s.get("Date")) or dt.date.min)
        metr["bing_en_indice"] = ultimo.get("InIndex")
        metr["bing_errores_rastreo"] = ultimo.get("CrawlErrors")
    # Dominios enlazantes: GetLinkCounts da NUESTRAS páginas con enlaces entrantes; GetUrlLinks, quién enlaza.
    paginas, pagina, total = [], 0, 1
    while pagina < total and pagina < 10:
        lc = get("GetLinkCounts", page=pagina) or {}
        paginas += [l.get("Url") for l in lc.get("Links") or [] if l.get("Url")]
        total = lc.get("TotalPages") or 1
        pagina += 1
    origen = est.setdefault("origen_enlaces", {})
    llamadas = 0
    for p in sorted(paginas, key=lambda u: origen.get(u, {}).get("mirada", "")):
        if llamadas >= BING_ENLACES_DIA:
            break
        dominios, pg, tot = set(), 0, 1
        while pg < tot and llamadas < BING_ENLACES_DIA:
            det = get("GetUrlLinks", link=p, page=pg) or {}
            llamadas += 1
            for d in det.get("Details") or []:
                dom = urllib.parse.urlparse(d.get("Url", "")).netloc.lower().removeprefix("www.")
                if dom and dom != DOMINIO and not dom.endswith("." + DOMINIO):
                    dominios.add(dom)
            tot = det.get("TotalPages") or 1
            pg += 1
        origen[p] = {"mirada": hoy_iso, "dominios": sorted(dominios)}
    for p in list(origen):
        if p not in paginas:
            del origen[p]
    todos = sorted({d for v in origen.values() for d in v["dominios"]})
    metr["bing_dominios"] = len(todos)
    antes = est.get("dominios")
    nuevos = [d for d in todos if antes is not None and d not in antes]
    if nuevos:
        cola.aviso("BING-ENLACE", f"dominio(s) enlazante(s) nuevo(s): {', '.join(nuevos)} (total {len(todos)})",
                   "Bing Webmaster", clave=f"BING-ENLACE|{','.join(nuevos)}", fuente="bing-enlace")
    est["dominios"] = todos
    en_ind = metr.get("bing_en_indice") or 0
    if len(todos) >= 6 or en_ind > len(urls) / 2:
        cola.aviso("CONGELADO", f"se cumple la condición para levantar el congelado de páginas nuevas "
                   f"(dominios enlazantes {len(todos)}, en índice {en_ind} de {len(urls)}): decide Jose",
                   "Bing Webmaster", clave="CONGELADO|bing", fuente="bing")
    issues = [i for i in (get("GetCrawlIssues") or []) if str(i.get("Url", "")).startswith(BASE)]
    if issues:
        ej = ", ".join(f"{fichero_de(i['Url'])} ({i.get('HttpCode')})" for i in issues[:5])
        cola.aviso("BING-RASTREO", f"{len(issues)} URL con errores de rastreo: {ej}" + (" …" if len(issues) > 5 else ""),
                   "Bing Webmaster", clave="BING-RASTREO|resumen", fuente="bing")
    cola.revisada("bing")


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
        t = re.search(r"<title[^>]*>(.*?)</title>", h, re.S | re.I)
        d = None
        for meta in re.findall(r"<meta\b[^>]*>", h, re.I):
            if re.search(r"""name\s*=\s*["']description["']""", meta, re.I):
                d = re.search(r"""content\s*=\s*(["'])(.*?)\1""", meta, re.S | re.I)
                break
        huella = hashlib.sha1(((t.group(1) if t else "") + "|" + (d.group(2) if d else "")).encode()).hexdigest()[:12]
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
    no_index, caidas = [], []
    for i, u in enumerate(urls):
        cuerpo = {"inspectionUrl": u, "siteUrl": sitio, "languageCode": "es"}
        st, r = pide(GSC_INSPECT, "POST", cuerpo, cab, abre)
        if st == 403 and i == 0 and sitio.startswith("sc-domain:"):
            sitio = BASE   # propiedad de prefijo de URL
            st, r = pide(GSC_INSPECT, "POST", dict(cuerpo, siteUrl=sitio), cab, abre)
        if st != 200:
            raise ErrorApi(f"Search Console inspect: HTTP {st} {codigo(r)}".strip())
        res = (r or {}).get("inspectionResult", {}).get("indexStatusResult", {})
        verdicto, cobertura = res.get("verdict", ""), res.get("coverageState", "")
        antes = estados.get(u, {}).get("verdict")
        estados[u] = {"verdict": verdicto, "cobertura": cobertura, "mirada": hoy.isoformat()}
        if verdicto != "PASS":
            no_index.append(u)
            if antes == "PASS":
                caidas.append(u)
                cola.aviso("GSC-NOINDEX", f"Google la ha sacado del índice: {cobertura or verdicto}", u,
                           fuente="gsc", clave=f"GSC-NOINDEX|{u}")
    est["sitio"] = sitio
    metr["gsc_indexadas"] = len(urls) - len(no_index)
    metr["gsc_sin_indexar"] = len(no_index)
    if no_index:
        ej = ", ".join(fichero_de(u) for u in no_index[:5])
        cola.aviso("GSC-SIN-INDEXAR", f"{len(no_index)} de {len(urls)} URL del sitemap sin indexar en Google: {ej}"
                   + (" …" if len(no_index) > 5 else ""), "Search Console", clave="GSC-SIN-INDEXAR|resumen",
                   fuente="gsc")
    cola.revisada("gsc")
    # Consultas en posición 5-30 → candidatas a título o descripción (regla F), respetando 4 semanas.
    fin = hoy - dt.timedelta(days=3)
    cuerpo = {"startDate": (fin - dt.timedelta(days=27)).isoformat(), "endDate": fin.isoformat(),
              "dimensions": ["query", "page"], "rowLimit": 5000, "searchType": "web"}
    st, r = pide(GSC_QUERY.format(urllib.parse.quote(sitio, safe="")), "POST", cuerpo, cab, abre)
    if st != 200:
        raise ErrorApi(f"Search Console query: HTTP {st} {codigo(r)}".strip())
    por_pagina = {}
    clics = impr = 0
    for fila in (r or {}).get("rows", []):
        consulta, pagina = fila["keys"]
        clics += fila.get("clicks", 0)
        impr += fila.get("impressions", 0)
        if 5 <= fila.get("position", 0) <= 30 and fila.get("impressions", 0) >= GSC_MIN_IMPR:
            por_pagina.setdefault(pagina.split("#")[0].split("?")[0], []).append(fila)
    # Suma de filas consulta+página: deja fuera las consultas anonimizadas (menos que el panel).
    metr["gsc_clics_28d"], metr["gsc_impr_28d"] = round(clics), round(impr)
    for pagina, filas in sorted(por_pagina.items(), key=lambda kv: -sum(f["impressions"] for f in kv[1]))[:10]:
        fch = fichero_de(pagina) if pagina.startswith(BASE) else ""
        reg = titulos.get(fch)
        if not reg or (hoy - dt.date.fromisoformat(reg["desde"])).days < TITULO_ESPERA:
            continue
        filas.sort(key=lambda f: -f["impressions"])
        top = "; ".join(f"«{f['keys'][0][:60]}» {round(f['impressions'])} impr. pos. {f['position']:.1f}"
                        for f in filas[:3])
        cola.aviso("GSC-TITULO", f"candidata a título/descripción (regla F; título actual «{reg['titulo'][:70]}», "
                   f"sin cambios desde {reg['desde']}): {top}", fch, fuente="gsc-titulo", clave=f"GSC-TITULO|{fch}")
    cola.revisada("gsc-titulo")


# ------------------------------------------------------------------ Yandex
def yandex(cola, urls, cambios, est, metr, token, abre=None):
    cab = {"Authorization": f"OAuth {token}"}
    user = est.get("user_id")
    if not user:
        st, r = pide(f"{YANDEX}/user", cabeceras=cab, abre=abre)
        if st != 200:
            raise ErrorApi(f"Yandex user: HTTP {st} {codigo(r)}".strip())
        user = r["user_id"]
    host = est.get("host_id")
    if not host:
        st, r = pide(f"{YANDEX}/user/{user}/hosts", cabeceras=cab, abre=abre)
        if st != 200:
            raise ErrorApi(f"Yandex hosts: HTTP {st} {codigo(r)}".strip())
        hosts = [h for h in r.get("hosts", [])
                 if urllib.parse.urlparse(h.get("ascii_host_url") or "").netloc.removeprefix("www.") == DOMINIO]
        if not hosts:
            raise ErrorApi(f"Yandex: {DOMINIO} no está entre los sitios de la cuenta")
        hosts.sort(key=lambda h: (not str(h.get("host_id", "")).startswith("https:"), not h.get("verified", True)))
        host = hosts[0]["host_id"]
    est.update(user_id=user, host_id=host)
    pendientes = encola(est, "pendientes", cambios, set(urls))
    base = f"{YANDEX}/user/{user}/hosts/{urllib.parse.quote(host, safe='')}"
    st, q = pide(f"{base}/recrawl/quota", cabeceras=cab, abre=abre)
    if st != 200:
        raise ErrorApi(f"Yandex quota: HTTP {st} {codigo(q)}".strip())
    resto = q.get("quota_remainder", 0)
    metr["yandex_cuota"] = resto
    hechas, malas = [], []
    for u in list(pendientes):
        if len(hechas) >= resto:
            break
        st, r = pide(f"{base}/recrawl/queue", "POST", {"url": u}, cab, abre)
        if st in (200, 202, 409):          # 409 URL_ALREADY_ADDED: ya está en cola
            hechas.append(u)
        elif st == 429:                    # QUOTA_EXCEEDED: se sigue mañana
            break
        elif st in (400, 404):             # INVALID_URL / HOST_NOT_VERIFIED: esa URL no, las demás sí
            malas.append(f"{fichero_de(u)} ({codigo(r) or st})")
            hechas.append(u)
        else:
            raise ErrorApi(f"Yandex recrawl: HTTP {st} {codigo(r)}".strip())
    est["pendientes"] = [u for u in pendientes if u not in hechas]
    if hechas:
        cola.aviso("YANDEX-ENVIO", f"{len(hechas) - len(malas)} URL en la cola de recrawl; quedan "
                   f"{len(est['pendientes'])} pendientes", "Yandex Webmaster", clave=f"YANDEX-ENVIO|{cola.hoy}",
                   fuente="yandex-envio")
    if malas:
        cola.aviso("MOTOR", f"Yandex rechaza: {', '.join(malas[:5])}", "Yandex Webmaster", clave="MOTOR|yandex-urls")


# ------------------------------------------------------------------ principal
CAMPOS = ["fecha", "bing_cuota", "bing_en_indice", "bing_dominios", "bing_sin_rastrear", "bing_errores_rastreo",
          "gsc_indexadas", "gsc_sin_indexar", "gsc_clics_28d", "gsc_impr_28d", "yandex_cuota"]


def guarda_metricas(datos, hoy, metr):
    ruta = os.path.join(datos, "metricas.csv")
    filas = []
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            filas = [l.rstrip("\n") for l in f if l.strip()][1:]
    filas = [l for l in filas if not l.startswith(hoy.isoformat())]
    filas.append(",".join([hoy.isoformat()] + [str(metr.get(c, "")) for c in CAMPOS[1:]]))
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(",".join(CAMPOS) + "\n" + "\n".join(filas) + "\n")


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
    bloques = (
        ("bing", "BING_API_KEY", lambda k: bing(cola, urls, cambios, est.setdefault("bing", {}), metr, k, abre)),
        ("gsc", "GSC_KEY", lambda k: gsc(cola, raiz, urls, est.setdefault("gsc", {}), metr, k, titulos, abre,
                                         token_gsc)),
        ("yandex", "YANDEX_TOKEN", lambda k: yandex(cola, urls, cambios, est.setdefault("yandex", {}), metr, k, abre)))
    for nombre in ("bing", "yandex"):        # lo cambiado queda en pendientes antes de llamar a nada
        if (env.get({"bing": "BING_API_KEY", "yandex": "YANDEX_TOKEN"}[nombre]) or "").strip():
            encola(est.setdefault(nombre, {}), "pendientes", cambios, set(urls))
    for nombre, secreto, fn in bloques:
        k = (env.get(secreto) or "").strip()
        if not k:
            print(f"indexacion: sin {secreto}, se salta {nombre}")
            continue
        try:
            fn(k)
            cola.revisada(f"indexa:{nombre}")
        except Exception as e:
            fallos.append(f"{nombre}: {type(e).__name__}")
            cola.aviso("MOTOR", f"{nombre} ha fallado: {str(e)[:150]}", "indexa.py",
                       clave=f"MOTOR|indexa-{nombre}", fuente=f"indexa:{nombre}")
    est["urls"] = urls
    sha = git(raiz, "rev-parse", "HEAD")
    if sha:
        est["sha"] = sha        # lo cambiado ya está en las colas de pendientes de cada buscador
    if metr:
        guarda_metricas(cola.datos, cola.hoy, metr)
    return metr, fallos
