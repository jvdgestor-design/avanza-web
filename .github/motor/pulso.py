#!/usr/bin/env python3
"""Pasada de diagnóstico reproducible. Lee la web; no publica ni envía formularios.

Los informes se guardan fuera de la raíz publicada. Solo biblioteca estándar.
"""
import argparse
from collections import Counter, deque
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import subprocess
from urllib.parse import urljoin, urlparse

import salud


def revision(raiz):
    r = subprocess.run(["git", "-C", str(raiz), "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "SIN_COMMIT"


def distancias(grafo, inicio):
    if inicio not in grafo:
        return {}
    d, cola = {inicio: 0}, deque([inicio])
    while cola:
        origen = cola.popleft()
        for destino in sorted(grafo[origen]):
            if destino not in d:
                d[destino] = d[origen] + 1
                cola.append(destino)
    return d


def oportunidades_gsc(fichero, urls, hoy):
    """Contrato explícito: filas página de una ventana completa de 28 días, no sumas de consultas."""
    if not fichero:
        return {"estado": "NO_MEDIDO", "motivo": "Sin exportación GSC verificada"}, []
    raw = Path(fichero).read_bytes()
    datos = json.loads(raw)
    if datos["siteUrl"] not in (salud.BASE, "sc-domain:" + salud.DOMINIO):
        raise ValueError("GSC: propiedad distinta de la web")
    inicio, fin = (dt.date.fromisoformat(datos[k]) for k in ("startDate", "endDate"))
    if (fin - inicio).days != 27 or fin > hoy - dt.timedelta(days=3) or fin < hoy - dt.timedelta(days=14):
        raise ValueError("GSC: se necesitan 28 días completos, asentados y recientes")
    if datos.get("dataState") != "final" or datos.get("dimensions") != ["page"]:
        raise ValueError("GSC: solo exportación final por página")
    vistas, candidatas = set(), []
    for fila in datos["rows"]:
        u = fila["page"]
        if u in vistas or u not in urls:
            raise ValueError("GSC: URL duplicada o fuera del sitemap")
        vistas.add(u)
        imp, pos = float(fila["impressions"]), float(fila["position"])
        if not math.isfinite(imp) or not math.isfinite(pos) or imp < 0 or pos < 1:
            raise ValueError("GSC: métrica inválida")
        if imp >= 20 and 5 <= pos <= 30:
            candidatas.append({"url": u, "impresiones": imp, "posicion": pos})
    return {"estado": "IMPORTADO_PROVISIONAL", "inicio": str(inicio), "fin": str(fin),
            "sha256": hashlib.sha256(raw).hexdigest(), "filas": len(vistas),
            "limite": "No acredita cobertura total, causalidad ni leads"}, sorted(
                candidatas, key=lambda x: (-x["impresiones"], x["url"]))


def diagnosticar(raiz, vivo=False, gsc=None):
    errores, avisos = [], []
    urls, por_fichero = salud.comprueba_repo(str(raiz), errores, avisos)
    paginas = {p.url: p for p in por_fichero.values()}
    if vivo and urls:
        salud.comprueba_vivo(str(raiz), urls, errores, salud.BASE, 0)
    # Se cuentan anclas HTML, no canonical, hreflang, sitemap ni enlaces de llms.txt.
    grafo, contacto = {}, set()
    for url, p in paginas.items():
        grafo[url] = {urljoin(url, h).split("#")[0].split("?")[0] for h in p.hrefs}
        grafo[url] &= set(paginas)
        grafo[url].discard(url)
        if p.forms or any(h.startswith("mailto:") or
                          (urlparse(h).hostname in ("wa.me", "api.whatsapp.com")) for h in p.hrefs):
            contacto.add(url)
    entradas = Counter(v for enlaces in grafo.values() for v in enlaces)
    desde_portada = distancias(grafo, salud.BASE)
    gsc_estado, oportunidades = oportunidades_gsc(gsc, set(urls), dt.date.today())
    cola = []

    def tarea(prioridad, bucle, accion, evidencia):
        cola.append({"prioridad": prioridad, "bucle": bucle, "accion": accion,
                     "evidencia": evidencia, "estado": "PENDIENTE"})

    for e in errores:
        tarea(0, "B", "Corregir el fallo de salud y repetir la comprobación", e)
    detalle = []
    for url, p in sorted(paginas.items()):
        fichero = salud.fichero_de(url)
        idioma = (p.lang or "sin_idioma").split("-")[0]
        hub = salud.BASE + ({"en": "en.html", "ru": "ru.html"}.get(idioma, ""))
        desde_hub = distancias(grafo, hub)
        caminos = distancias(grafo, url)
        pasos_contacto = min((n for u, n in caminos.items() if u in contacto), default=None)
        detalle.append({"url": url, "idioma": idioma, "entradas_html": entradas[url],
                        "pasos_portada": desde_portada.get(url), "pasos_portada_idioma": desde_hub.get(url),
                        "pasos_contacto": pasos_contacto,
                        "sha256": hashlib.sha256((raiz / fichero).read_bytes()).hexdigest()})
        if url not in desde_portada:
            tarea(1, "B", "Añadir un enlace contextual desde una página relacionada accesible", url)
        elif desde_portada[url] > 3:
            tarea(2, "B", "Acercar la página desde una página relacionada", f"{url}: {desde_portada[url]} saltos HTML")
        if idioma in ("en", "ru") and url not in desde_hub:
            tarea(1, "B", "Enlazar desde la portada o guía del mismo idioma", f"{url}: sin camino desde {hub}")
        if pasos_contacto is None:
            tarea(1, "E", "Revisar cómo puede escribir el visitante al despacho", url)
    tarea(2, "A", "Revisar fuentes y menciones gratuitas útiles antes de proponer más contenido",
          "No se han comprobado menciones externas en esta pasada; no equivale a cero menciones")
    if gsc_estado["estado"] == "NO_MEDIDO":
        tarea(2, "B", "Obtener una exportación reciente de Search Console por página",
              "Sin datos de impresiones o posición: no se activa contenido por una supuesta oportunidad")
    for op in oportunidades:
        tarea(3, "F", "Estudiar la intención y el resultado de esta URL antes de proponer cambios",
              op)
    tarea(3, "D", "Completar el panel fijo de consultas ES/EN/RU y guardar respuesta, enlace, modelo y fecha",
          "Citas en IA NO MEDIDAS; permitir un bot no demuestra una recomendación")
    cola.sort(key=lambda t: (t["prioridad"], t["bucle"], str(t["evidencia"])))
    estado_git = subprocess.run(["git", "-C", str(raiz), "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True)
    motor_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return {"arbol_limpio": estado_git.returncode == 0 and not estado_git.stdout.strip(),
            "sha256_motor": motor_sha, "fecha_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "head": revision(raiz),
            "calificacion": "PROVISIONAL, pendiente de revisión de Claude",
            "alcance": "repositorio y huellas en vivo" if vivo else "solo repositorio",
            "salud": {"paginas": len(paginas), "errores": errores, "avisos": avisos},
            "idiomas": dict(Counter(p["idioma"] for p in detalle)), "paginas": detalle,
            "gsc": gsc_estado, "cola": cola,
            "no_medido": ["visibilidad y citas en IA", "leads y conversiones reales", "autoridad externa",
                          "desbordamiento a 390 px", "vigencia jurídica del contenido"],
            "impacto_posicionamiento": "NO CALCULABLE; sin comparación y sin atribución causal"}


def guardar(r, destino):
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "pulso_de-chatgpt.json").write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lineas = ["# Pasada del motor", "", r["calificacion"], "", f"HEAD: {r['head']}",
              f"Árbol limpio: {r['arbol_limpio']}; motor SHA-256: {r['sha256_motor']}",
              f"Fecha UTC: {r['fecha_utc']}", f"Alcance: {r['alcance']}",
              f"Páginas: {r['salud']['paginas']}; errores: {len(r['salud']['errores'])}; avisos: {len(r['salud']['avisos'])}",
              f"Idiomas: {r['idiomas']}", f"GSC: {r['gsc']['estado']}",
              f"Impacto: {r['impacto_posicionamiento']}", "", "## Pendientes por prioridad", ""]
    for t in r["cola"]:
        lineas += [f"- P{t['prioridad']} · {t['bucle']} · {t['accion']}. Evidencia: {t['evidencia']}"]
    lineas += ["", "## Avisos", ""] + [f"- {a}" for a in r["salud"]["avisos"]]
    lineas += ["", "No medido: " + "; ".join(r["no_medido"]),
               "No se publica, no se envían solicitudes y no se modifica la cola de Claude."]
    texto = "\n".join(lineas) + "\n"
    (destino / "pulso_de-chatgpt.md").write_text(texto, encoding="utf-8")
    return texto


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raiz", default=".")
    ap.add_argument("--salida", required=True, help="directorio fuera de la raíz publicada")
    ap.add_argument("--vivo", action="store_true")
    ap.add_argument("--gsc", help="JSON final por página, según el contrato del manual")
    a = ap.parse_args(argv)
    raiz, destino = Path(a.raiz).resolve(), Path(a.salida).resolve()
    if destino == raiz or raiz in destino.parents:
        ap.error("Los informes deben quedar fuera de la raíz publicada")
    try:
        r = diagnosticar(raiz, a.vivo, a.gsc)
    except (OSError, ValueError, KeyError, TypeError) as e:
        ap.error(str(e))
    print(guardar(r, destino))
    return 1 if r["salud"]["errores"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
