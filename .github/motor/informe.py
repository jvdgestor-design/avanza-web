"""Informe semanal del motor sin consumo (pieza «semanal» de vigia.py), sin IA.

Lo lanza la ejecución diaria de los lunes (hora de Madrid) o a mano con piezas=semanal. Deja en datos-motor:
  motor/informe-semanal.md          el último informe (lo lee la pasada del lunes en vez de medir a mano)
  motor/informes/AAAA-MM-DD.md      el histórico, uno por semana
Fuentes, cada una se salta sola si falta su secreto, y lo dice en el informe:
  GSC_KEY       Search Console searchAnalytics.query: 7 días cerrados frente a los 7 anteriores (totales del
                sitio, que incluyen las consultas anonimizadas; consultas y páginas, que no las incluyen).
                Los datos de los últimos 3 días no están completos: la semana termina hace 3 días.
                Doc: developers.google.com/webmaster-tools/v1/searchanalytics/query
  BING_API_KEY  Bing Webmaster GetQueryStats: consultas por las que Bing nos enseña, en cubos semanales
                (sin parámetros de fecha; devuelve todo lo que tiene). La posición se copia tal como la da la API.
  metricas.csv  páginas en índice (Bing, Google), dominios enlazantes: hoy frente a hace 7 días.
  consultas.txt consultas objetivo (una por línea; # comenta): se buscan dentro de las consultas de Search
                Console, sin acentos ni mayúsculas, y se dan sus impresiones, clics y posición de la semana.
Nada de terceros se copia salvo las consultas de búsqueda y nuestras URL. La rama es pública: no van cifras
que no estén ya en el panel de Search Console o Bing de la propia web.
"""
import datetime as dt
import json
import os
import unicodedata
import urllib.parse

import indexa

MIN_IMPR = 5          # una consulta con menos impresiones en las dos semanas no entra en suben/bajan
TOP = 15


def _llano(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn").strip()


def periodos(hoy):
    fin = hoy - dt.timedelta(days=3)
    ini = fin - dt.timedelta(days=6)
    return (ini, fin), (ini - dt.timedelta(days=7), ini - dt.timedelta(days=1))


def _gsc_consulta(sitio, cab, ini, fin, dims, abre, limite=1000):
    cuerpo = {"startDate": ini.isoformat(), "endDate": fin.isoformat(), "dimensions": dims,
              "rowLimit": limite, "searchType": "web"}
    st, r = indexa.pide(indexa.GSC_QUERY.format(urllib.parse.quote(sitio, safe="")), "POST", cuerpo, cab, abre)
    if st != 200:
        raise indexa.ErrorApi(f"Search Console query: HTTP {st} {indexa.codigo(r)}".strip())
    return (r or {}).get("rows", [])


def _num(v, dec=0):
    s = f"{v:,.{dec}f}" if isinstance(v, (int, float)) else str(v)
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _delta(a, b, dec=0, menos_es_mejor=False):
    if a is None or b is None:
        return "—"
    d = a - b
    if abs(d) < (0.05 if dec else 0.5):
        return "="
    txt = ("+" if d > 0 else "−") + _num(abs(d), dec)
    if menos_es_mejor:
        txt += " (mejor)" if d < 0 else " (peor)"
    return txt


def _filas(rows, clave=0):
    out = {}
    for f in rows:
        k = f["keys"][clave] if f.get("keys") else "(total)"
        out[k] = {"clics": f.get("clicks", 0), "impr": f.get("impressions", 0),
                  "ctr": f.get("ctr", 0), "pos": f.get("position", 0)}
    return out


def seccion_gsc(sitio, cab, hoy, consultas_obj, abre):
    (i1, f1), (i0, f0) = periodos(hoy)
    lineas = [f"## Google (Search Console) — {i1:%d/%m} a {f1:%d/%m} frente a {i0:%d/%m} a {f0:%d/%m}", ""]
    tot1 = _filas(_gsc_consulta(sitio, cab, i1, f1, [], abre)).get("(total)", {})
    tot0 = _filas(_gsc_consulta(sitio, cab, i0, f0, [], abre)).get("(total)", {})
    g = lambda d, k: d.get(k) if d else None
    lineas += [
        "| | Esta semana | Anterior | Cambio |", "|---|---|---|---|",
        f"| Clics | {_num(g(tot1,'clics') or 0)} | {_num(g(tot0,'clics') or 0)} | {_delta(g(tot1,'clics') or 0, g(tot0,'clics') or 0)} |",
        f"| Impresiones | {_num(g(tot1,'impr') or 0)} | {_num(g(tot0,'impr') or 0)} | {_delta(g(tot1,'impr') or 0, g(tot0,'impr') or 0)} |",
        f"| CTR | {_num(100 * (g(tot1,'ctr') or 0), 1)} % | {_num(100 * (g(tot0,'ctr') or 0), 1)} % | |",
        f"| Posición media | {_num(g(tot1,'pos') or 0, 1)} | {_num(g(tot0,'pos') or 0, 1)} | "
        f"{_delta(g(tot1,'pos'), g(tot0,'pos'), 1, menos_es_mejor=True) if tot1 and tot0 else '—'} |", ""]
    q1 = _filas(_gsc_consulta(sitio, cab, i1, f1, ["query"], abre))
    q0 = _filas(_gsc_consulta(sitio, cab, i0, f0, ["query"], abre))
    p1 = _filas(_gsc_consulta(sitio, cab, i1, f1, ["page"], abre))
    p0 = _filas(_gsc_consulta(sitio, cab, i0, f0, ["page"], abre))

    if consultas_obj:
        lineas += ["### Consultas objetivo (suma de las consultas que las contienen)", "",
                   "| Consulta objetivo | Impr. | Clics | Posición | Impr. anterior | Variantes |", "|---|---|---|---|---|---|"]
        for obj in consultas_obj:
            o = _llano(obj)
            m1 = {k: v for k, v in q1.items() if o in _llano(k)}
            m0 = {k: v for k, v in q0.items() if o in _llano(k)}
            impr = sum(v["impr"] for v in m1.values())
            pos = (sum(v["pos"] * v["impr"] for v in m1.values()) / impr) if impr else None
            lineas.append(f"| {obj} | {_num(impr)} | {_num(sum(v['clics'] for v in m1.values()))} | "
                          f"{_num(pos, 1) if pos else 'no sale'} | {_num(sum(v['impr'] for v in m0.values()))} | {len(m1)} |")
        lineas.append("")

    nuevas = sorted(((k, v) for k, v in q1.items() if k not in q0 and v["impr"] >= MIN_IMPR),
                    key=lambda kv: -kv[1]["impr"])[:TOP]
    lineas += ["### Consultas nuevas (no salían la semana anterior)", ""]
    lineas += [f"- «{k}» — {_num(v['impr'])} impr., pos. {_num(v['pos'], 1)}" for k, v in nuevas] or ["- Ninguna"]
    comunes = [(k, q1[k], q0[k]) for k in q1 if k in q0 and max(q1[k]["impr"], q0[k]["impr"]) >= MIN_IMPR]
    suben = sorted((c for c in comunes if c[2]["pos"] - c[1]["pos"] >= 1), key=lambda c: c[1]["pos"] - c[2]["pos"])[:TOP]
    bajan = sorted((c for c in comunes if c[1]["pos"] - c[2]["pos"] >= 1), key=lambda c: c[2]["pos"] - c[1]["pos"])[:TOP]
    perdidas = sorted(((k, v) for k, v in q0.items() if k not in q1 and v["impr"] >= MIN_IMPR),
                      key=lambda kv: -kv[1]["impr"])[:TOP]
    lineas += ["", "### Consultas que suben de posición", ""]
    lineas += [f"- «{k}» — pos. {_num(b['pos'], 1)} → {_num(a['pos'], 1)}; {_num(b['impr'])} → {_num(a['impr'])} impr."
               for k, a, b in suben] or ["- Ninguna"]
    lineas += ["", "### Consultas que bajan de posición", ""]
    lineas += [f"- «{k}» — pos. {_num(b['pos'], 1)} → {_num(a['pos'], 1)}; {_num(b['impr'])} → {_num(a['impr'])} impr."
               for k, a, b in bajan] or ["- Ninguna"]
    lineas += ["", "### Consultas que dejan de salir", ""]
    lineas += [f"- «{k}» — tenía {_num(v['impr'])} impr., pos. {_num(v['pos'], 1)}" for k, v in perdidas] or ["- Ninguna"]
    lineas += ["", f"### Páginas con más impresiones (top {TOP})", "",
               "| Página | Impr. | Antes | Clics | Posición | Antes |", "|---|---|---|---|---|---|"]
    for url, v in sorted(p1.items(), key=lambda kv: -kv[1]["impr"])[:TOP]:
        b = p0.get(url, {})
        nombre = (url[len(indexa.BASE):] or "/") if url.startswith(indexa.BASE) else url
        lineas.append(f"| {nombre} | {_num(v['impr'])} | {_num(b.get('impr', 0))} | {_num(v['clics'])} | "
                      f"{_num(v['pos'], 1)} | {_num(b['pos'], 1) if b else '—'} |")
    sin = sorted(set(p0) - set(p1))
    if sin:
        lineas += ["", f"Páginas que tenían impresiones y esta semana no: {len(sin)} — "
                   + ", ".join((u[len(indexa.BASE):] or "/") for u in sin[:10]) + (" …" if len(sin) > 10 else "")]
    resumen = {"clics": g(tot1, "clics") or 0, "impr": g(tot1, "impr") or 0, "nuevas": len(nuevas),
               "suben": len(suben), "bajan": len(bajan)}
    return lineas + [""], resumen


def seccion_bing(clave, abre):
    st, r = indexa.pide(indexa.BING + "GetQueryStats?" + urllib.parse.urlencode(
        {"siteUrl": indexa.BASE, "apikey": clave}), abre=abre)
    if st != 200:
        raise indexa.ErrorApi(f"Bing GetQueryStats: HTTP {st} {indexa.codigo(r)}".strip())
    filas = (r or {}).get("d") or []
    cubos = {}
    for f in filas:
        d = indexa.fecha_ms(f.get("Date"))
        if d:
            cubos.setdefault(d, []).append(f)
    lineas = ["## Bing (consultas por las que nos enseña)", ""]
    if not cubos:
        return lineas + ["- Bing no devuelve consultas todavía (sin impresiones registradas).", ""], {"bing_consultas": 0}
    fechas = sorted(cubos)
    ult = cubos[fechas[-1]]
    ant = {f.get("Query"): f for f in cubos[fechas[-2]]} if len(fechas) > 1 else {}
    imp = sum(f.get("Impressions", 0) for f in ult)
    cli = sum(f.get("Clicks", 0) for f in ult)
    imp0 = sum(f.get("Impressions", 0) for f in ant.values()) if ant else None
    lineas.append(f"Semana de Bing que termina el {fechas[-1]:%d/%m/%Y}: {len(ult)} consultas, {_num(imp)} impresiones, "
                  f"{_num(cli)} clics" + (f" (semana anterior: {len(ant)} consultas, {_num(imp0)} impresiones)" if ant else "")
                  + ". Posición tal como la da la API (sin comprobar su escala frente al panel).")
    lineas += ["", "| Consulta | Impr. | Clics | Posición (API) | Nueva |", "|---|---|---|---|---|"]
    for f in sorted(ult, key=lambda f: -f.get("Impressions", 0))[:TOP]:
        lineas.append(f"| {f.get('Query', '')} | {_num(f.get('Impressions', 0))} | {_num(f.get('Clicks', 0))} | "
                      f"{f.get('AvgImpressionPosition', '')} | {'sí' if ant and f.get('Query') not in ant else ''} |")
    return lineas + [""], {"bing_consultas": len(ult)}


def seccion_metricas(datos, hoy):
    ruta = os.path.join(datos, "metricas.csv")
    if not os.path.exists(ruta):
        return ["## Índices y enlaces", "", "- Sin metricas.csv todavía.", ""]
    with open(ruta, encoding="utf-8") as f:
        filas = [l.rstrip("\n").split(",") for l in f if l.strip()]
    cab, filas = filas[0], filas[1:]
    por = {f[0]: dict(zip(cab, f)) for f in filas}
    actual = por.get(max((k for k in por if k <= hoy.isoformat()), default=""), {})
    hace = max((k for k in por if k <= (hoy - dt.timedelta(days=7)).isoformat()), default=None)
    previo = por.get(hace, {}) if hace else {}
    nombres = [("bing_en_indice", "Bing: páginas en índice"), ("bing_dominios", "Bing: dominios enlazantes (API)"),
               ("gsc_indexadas", "Google: URL del sitemap indexadas"), ("gsc_sin_indexar", "Google: sin indexar")]
    lineas = ["## Índices y enlaces (metricas.csv)", "",
              f"| | {actual.get('fecha', '—')} | {hace or 'sin dato de hace 7 días'} |", "|---|---|---|"]
    for k, n in nombres:
        v = actual.get(k) or "NO CALCULABLE"
        lineas.append(f"| {n} | {v} | {previo.get(k) or '—'} |")
    return lineas + ["", "Dominios enlazantes de Bing: la API da 0 o vacío cuando el panel muestra otra cifra "
                     "(30/10): vale la del panel.", ""]


def lee_consultas(datos):
    try:
        with open(os.path.join(datos, "consultas.txt"), encoding="utf-8") as f:
            return [l.split("#")[0].strip() for l in f if l.split("#")[0].strip()]
    except FileNotFoundError:
        return []


def ejecuta(cola, raiz, entorno=None, abre=None, token_gsc=None):
    env = entorno if entorno is not None else os.environ
    hoy = cola.hoy
    partes = [f"# Informe semanal del motor — {hoy:%d/%m/%Y}", "",
              "Lo genera GitHub Actions sin IA. Cifras de las API de Search Console y Bing: FIRMES como lectura de "
              "la API en la fecha de arriba; las de consultas y páginas no incluyen las anonimizadas.", ""]
    fallos, resumen = [], {}
    est = cola.pieza("indexacion").get("gsc", {})
    clave = (env.get("GSC_KEY") or "").strip()
    if clave:
        try:
            tok = token_gsc or indexa.token_google(clave)
            sitio = env.get("GSC_SITE") or est.get("sitio") or f"sc-domain:{indexa.DOMINIO}"
            lin, res = seccion_gsc(sitio, {"Authorization": f"Bearer {tok}"}, hoy, lee_consultas(cola.datos), abre)
            partes += lin
            resumen.update(res)
        except Exception as e:
            fallos.append("gsc")
            partes += ["## Google (Search Console)", "", f"- NO CALCULABLE: {type(e).__name__}: {str(e)[:150]}", ""]
    else:
        partes += ["## Google (Search Console)", "", "- Sin GSC_KEY: no se mide.", ""]
    clave = (env.get("BING_API_KEY") or "").strip()
    if clave:
        try:
            lin, res = seccion_bing(clave, abre)
            partes += lin
            resumen.update(res)
        except Exception as e:
            fallos.append("bing")
            partes += ["## Bing", "", f"- NO CALCULABLE: {type(e).__name__}: {str(e)[:150]}", ""]
    else:
        partes += ["## Bing", "", "- Sin BING_API_KEY: no se mide.", ""]
    partes += seccion_metricas(cola.datos, hoy)
    partes += ["## Lo que no da ninguna API (sigue a mano o por ChatGPT)", "",
               "- Bing AI Performance (Copilot), posición real en google.es desde Valencia, Brave site:, LinkedIn y la "
               "medición de IA.", ""]
    texto = "\n".join(partes)
    os.makedirs(os.path.join(cola.datos, "informes"), exist_ok=True)
    for ruta in (os.path.join(cola.datos, "informe-semanal.md"),
                 os.path.join(cola.datos, "informes", f"{hoy.isoformat()}.md")):
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(texto)
    que = (f"informe de la semana listo en motor/informe-semanal.md: {_num(resumen.get('impr', 0))} impr. y "
           f"{_num(resumen.get('clics', 0))} clics en Google, {resumen.get('nuevas', 0)} consultas nuevas, "
           f"{resumen.get('suben', 0)} suben y {resumen.get('bajan', 0)} bajan"
           + (f"; NO CALCULABLE: {', '.join(fallos)}" if fallos else ""))
    cola.aviso("INFORME", que, "motor/informe-semanal.md", fuente="informe", clave=f"INFORME|{hoy.isoformat()}")
    cola.revisada("informe")
    return texto, fallos
