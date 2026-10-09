#!/usr/bin/env python3
"""Vigilancia del BOE para las páginas de grupoavanzaconsultores.es, sin usos de Claude.

1. Saca de cada página las normas que cita: por número («Ley 35/2006», «Orden HAC/623/2026»,
   también en inglés, «Royal Decree 439/2007»), por sigla («LIRPF»), por nombre («Ley General
   Tributaria», «Código Civil») y por enlace a boe.es («BOE-A-2006-20764»).
2. Para cada norma pide al BOE (API de datos abiertos, legislación consolidada) su ficha: comprueba que el
   identificador es de verdad esa norma (el título del BOE empieza por ella; si hay dos normas con el mismo
   número, error de ambigüedad) y lee su fecha de última actualización y si está derogada.
3. Compara con la ejecución anterior (estado en la caché de GitHub Actions). Si una norma citada ha cambiado,
   sale en rojo con las páginas que la citan, y sigue en rojo cada día hasta que se marque como revisada
   (`gh workflow run boe.yml -f revisado="Ley 35/2006"`).

También sale en rojo si el BOE no contesta, si una cita no se puede identificar o si se ha perdido el estado
anterior: un verde tiene que significar que todo lo citado está vigilado y sin cambios.
Solo biblioteca estándar de Python.
"""
import argparse
import glob
import html as htmlmod
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://www.boe.es/datosabiertos/api/legislacion-consolidada"

# Sigla o nombre -> norma. Solo equivalencias fijas; el identificador siempre se comprueba en el BOE.
ALIAS = {
    "LIRPF": "Ley 35/2006", "Ley del IRPF": "Ley 35/2006", "Ley del Impuesto sobre la Renta de las Personas Físicas": "Ley 35/2006",
    "RIRPF": "Real Decreto 439/2007", "Reglamento del IRPF": "Real Decreto 439/2007",
    "Reglamento del Impuesto sobre la Renta de las Personas Físicas": "Real Decreto 439/2007",
    "LIVA": "Ley 37/1992", "Ley del IVA": "Ley 37/1992", "Ley del Impuesto sobre el Valor Añadido": "Ley 37/1992",
    "RIVA": "Real Decreto 1624/1992", "Reglamento del IVA": "Real Decreto 1624/1992",
    "Reglamento del Impuesto sobre el Valor Añadido": "Real Decreto 1624/1992",
    "LGT": "Ley 58/2003", "Ley General Tributaria": "Ley 58/2003",
    "LIS": "Ley 27/2014", "Ley del Impuesto sobre Sociedades": "Ley 27/2014",
    "LISD": "Ley 29/1987", "Ley del Impuesto sobre Sucesiones y Donaciones": "Ley 29/1987",
    "RISD": "Real Decreto 1629/1991", "Reglamento del Impuesto sobre Sucesiones y Donaciones": "Real Decreto 1629/1991",
    "Reglamento del ISD": "Real Decreto 1629/1991",
    "LITPAJD": "Real Decreto Legislativo 1/1993",
    "Ley del Impuesto sobre el Patrimonio": "Ley 19/1991",
    "TRLRHL": "Real Decreto Legislativo 2/2004", "Ley de Haciendas Locales": "Real Decreto Legislativo 2/2004",
    "Ley Reguladora de las Haciendas Locales": "Real Decreto Legislativo 2/2004",
    "LIRNR": "Real Decreto Legislativo 5/2004", "TRLIRNR": "Real Decreto Legislativo 5/2004",
    "Ley del Impuesto sobre la Renta de no Residentes": "Real Decreto Legislativo 5/2004",
    "LGSS": "Real Decreto Legislativo 8/2015", "TRLGSS": "Real Decreto Legislativo 8/2015",
    "Ley General de la Seguridad Social": "Real Decreto Legislativo 8/2015",
    "Estatuto de los Trabajadores": "Real Decreto Legislativo 2/2015",
    "LSC": "Real Decreto Legislativo 1/2010", "Ley de Sociedades de Capital": "Real Decreto Legislativo 1/2010",
    "Ley Concursal": "Real Decreto Legislativo 1/2020",
    "LETA": "Ley 20/2007", "Estatuto del Trabajo Autónomo": "Ley 20/2007",
    "RGAT": "Real Decreto 1065/2007", "RGR": "Real Decreto 939/2005", "Reglamento General de Recaudación": "Real Decreto 939/2005",
    "LPAC": "Ley 39/2015", "Código Civil": "Código Civil", "Código de Comercio": "Código de Comercio",
}
# Identificadores conocidos (todos se comprueban contra el título del BOE en cada ejecución).
SEMILLA = {
    "Ley 35/2006": "BOE-A-2006-20764", "Real Decreto 439/2007": "BOE-A-2007-6820",
    "Ley 37/1992": "BOE-A-1992-28740", "Real Decreto 1624/1992": "BOE-A-1992-28925",
    "Ley 58/2003": "BOE-A-2003-23186", "Ley 27/2014": "BOE-A-2014-12328",
    "Ley 29/1987": "BOE-A-1987-28141", "Real Decreto Legislativo 1/1993": "BOE-A-1993-25359",
    "Real Decreto Legislativo 2/2004": "BOE-A-2004-4214", "Real Decreto Legislativo 5/2004": "BOE-A-2004-4527",
    "Real Decreto Legislativo 8/2015": "BOE-A-2015-11724", "Real Decreto Legislativo 2/2015": "BOE-A-2015-11430",
    "Real Decreto Legislativo 1/2010": "BOE-A-2010-10544", "Ley 20/2007": "BOE-A-2007-13409",
    "Real Decreto 1065/2007": "BOE-A-2007-15984", "Real Decreto 939/2005": "BOE-A-2005-14803",
    "Ley 39/2015": "BOE-A-2015-10565",
    "Código Civil": "BOE-A-1889-4763", "Código de Comercio": "BOE-A-1885-6627",
}
# Emisor que tiene que tener la norma (departamento del BOE).
DEPARTAMENTO_ESPERADO = {"Ley 5/2026": "valenciana", "Ley 13/1997": "valenciana"}
# Normas cuyo título del BOE no empieza por su nombre corto: se comprueba este comienzo.
TITULO_ESPERADO = {
    "Código Civil": "Real Decreto de 24 de julio de 1889",
    "Código de Comercio": "Real Decreto de 22 de agosto de 1885",
}
# Normas con el mismo número que otra (estatal y autonómica, por ejemplo): lo que tiene que decir su título
# para ser la que citan las páginas (comprobado en el contexto de cada cita).
TITULO_CONTIENE = {
    "Ley 12/2002": "concierto económico",      # art. 25: Concierto con el País Vasco (no la del transporte por cable)
    "Ley 14/2013": "emprendedores",            # art. 18: legalización de libros (no la valenciana de 26/12/2013)
    "Ley 13/1997": "tramo autonómico",         # Generalitat Valenciana
    "Ley 28/1990": "convenio económico",       # Navarra
    "Ley 22/2009": "financiación",
}
# Citas que se sabe que no están en legislación consolidada (no se vigilan, se dice por qué).
NO_VIGILABLES = {
    "Orden HAC/623/2026": "orden de modelos sin texto consolidado en el BOE; su vigencia la mira la pasada",
    # Ley 5/2026, de 31 de julio, de la Generalitat (BOE-A-2026-19331), que modifica la Ley 13/1997; la Ley 5/2026
    # de la Comunidad de Madrid es otra. No tiene texto consolidado propio: sus cambios se ven en la Ley 13/1997.
    "Ley 5/2026": "ley valenciana de modificación (BOE-A-2026-19331) sin texto consolidado propio; se vigila en la Ley 13/1997",
}

TIPOS = r"(Ley Orgánica|Real Decreto-ley|Real Decreto Legislativo|Real Decreto|Decreto Legislativo|Decreto-ley|Decreto|Ley)"
INGLES = {"Organic Law": "Ley Orgánica", "Royal Decree-Law": "Real Decreto-ley",
          "Royal Legislative Decree": "Real Decreto Legislativo", "Royal Decree": "Real Decreto", "Law": "Ley"}
RX_NORMA = re.compile(r"\b" + TIPOS + r"\s+(\d{1,4})/(\d{4})", re.I)
RX_INGLES = re.compile(r"\b(Organic Law|Royal Decree-Law|Royal Legislative Decree|Royal Decree|Law)\s+(\d{1,4})/(\d{4})")
RX_ORDEN = re.compile(r"\bOrden\s+([A-Z]{2,5})/(\d{1,5})/(\d{4})")
RX_ID = re.compile(r"BOE-A-\d{4}-\d+")
RX_ALIAS = re.compile(r"\b(" + "|".join(re.escape(s) for s in sorted(ALIAS, key=len, reverse=True)) + r")\b")


def canon_tipo(t):
    for c in ("Ley Orgánica", "Real Decreto-ley", "Real Decreto Legislativo", "Real Decreto", "Decreto Legislativo",
              "Decreto-ley", "Decreto", "Ley"):
        if t.lower() == c.lower():
            return c
    return t


def normaliza_html(s):
    """Texto plano de la página, con los href conservados (para los enlaces BOE-A)."""
    hrefs = " ".join(re.findall(r'href="([^"]*boe\.es[^"]*)"', s))
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = htmlmod.unescape(s).replace(" ", " ").replace(" ", " ")
    s = re.sub(r"[‐‑‒–—]", "-", s)
    return re.sub(r"[ \t]+", " ", s) + " " + hrefs


class SinRespuesta(Exception):
    pass


FALLOS_RED = [0]


def pide(url):
    if FALLOS_RED[0] >= 3:
        raise SinRespuesta("el BOE no contesta (tres fallos de red seguidos)")
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "AvanzaVigilanciaBOE/1.0"})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                FALLOS_RED[0] = 0
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:
                raise LookupError(f"{e.code}")
            ultimo = e
        except Exception as e:
            ultimo = e
        if i < 2:
            time.sleep(5 * (i + 1))
    FALLOS_RED[0] += 1
    raise SinRespuesta(f"{url}: {ultimo}")


def busca(nodo, claves):
    if isinstance(nodo, dict):
        for k, v in nodo.items():
            if any(c in k.lower() for c in claves):
                if isinstance(v, (str, int)):
                    return str(v)
                if isinstance(v, dict) and isinstance(v.get("texto"), str):
                    return v["texto"]
        for v in nodo.values():
            r = busca(v, claves)
            if r:
                return r
    elif isinstance(nodo, list):
        for v in nodo:
            r = busca(v, claves)
            if r:
                return r
    return None


def lista_resultados(datos):
    if isinstance(datos, dict):
        for k in ("data", "items", "resultados", "results"):
            if isinstance(datos.get(k), list):
                return datos[k]
        for v in datos.values():
            r = lista_resultados(v)
            if r:
                return r
    if isinstance(datos, list) and datos and isinstance(datos[0], dict):
        return datos
    return []


def es_esa_norma(norma, titulo):
    t = re.sub(r"\s+", " ", titulo).strip().lower()
    esperado = TITULO_ESPERADO.get(norma, norma).lower()
    if not (t.startswith(esperado + ",") or t.startswith(esperado + " ")):
        return False
    return TITULO_CONTIENE.get(norma, "") in t


def ficha(boe_id):
    datos = pide(f"{API}/id/{boe_id}/metadatos")
    return {
        "titulo": busca(datos, ["titulo"]) or "",
        "actualizacion": busca(datos, ["fecha_actualizacion"]) or "",
        "departamento": busca(datos, ["departamento"]) or "",
        "derogada": (busca(datos, ["estatus_derogacion"]) or "").upper() in ("S", "SI", "TRUE", "1"),
        "agotada": (busca(datos, ["vigencia_agotada"]) or "").upper() in ("S", "SI", "TRUE", "1"),
        "crudo": datos,
    }


def resuelve(norma):
    """Identificador de una norma citada por número. Devuelve (id, None) o (None, motivo)."""
    halladas = {}
    for q in (f'titulo:"{norma}"', f'"{norma}"'):
        consulta = json.dumps({"query": {"query_string": {"query": q}}})
        datos = pide(f"{API}?query={urllib.parse.quote(consulta)}&limit=50")
        for item in lista_resultados(datos):
            ident = busca(item, ["identificador"]) or ""
            titulo = busca(item, ["titulo"]) or ""
            if RX_ID.fullmatch(ident) and es_esa_norma(norma, titulo):
                halladas[ident] = titulo
        if halladas:
            break
    if len(halladas) > 1:
        return None, "ambigua, hay varias normas con ese número: " + " | ".join(
            f"{i} «{t[:70]}»" for i, t in sorted(halladas.items()))
    if halladas:
        return next(iter(halladas)), None
    return None, "no aparece en la legislación consolidada del BOE"


def citas_de(raiz):
    citas = {}
    for ruta in sorted(glob.glob(os.path.join(raiz, "*.html"))):
        pagina = os.path.basename(ruta)
        if pagina in ("404.html", "gracias.html"):
            continue
        with open(ruta, encoding="utf-8") as f:
            texto = normaliza_html(f.read())
        claves = set()
        claves |= {f"{canon_tipo(m.group(1))} {m.group(2)}/{m.group(3)}" for m in RX_NORMA.finditer(texto)}
        claves |= {f"{INGLES[m.group(1)]} {m.group(2)}/{m.group(3)}" for m in RX_INGLES.finditer(texto)}
        claves |= {f"Orden {m.group(1)}/{m.group(2)}/{m.group(3)}" for m in RX_ORDEN.finditer(texto)}
        claves |= {ALIAS[m.group(1)] for m in RX_ALIAS.finditer(texto)}
        claves |= {m.group(0) for m in RX_ID.finditer(texto)}
        for c in claves:
            citas.setdefault(c, set()).add(pagina)
    return citas


def anota(nivel, texto):
    t = texto.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::{nivel}::{t}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", default=".")
    ap.add_argument("--estado", default="boe-estado.json")
    ap.add_argument("--revisado", default="",
                    help="normas ya revisadas (nombre o BOE-A), separadas por «;»; «todo» para todas")
    ap.add_argument("--pendientes-desde", default="",
                    help="AAAAMMDD: las normas actualizadas desde esa fecha quedan pendientes de revisión (en rojo) "
                         "hasta que se marquen como revisadas; para cuando no consta que se revisaran")
    ap.add_argument("--inicial", action="store_true",
                    help="no hay estado anterior a propósito (primera ejecución): se toma como punto de partida")
    a = ap.parse_args()

    citas = citas_de(a.raiz)
    previo = {}
    if os.path.isfile(a.estado):
        with open(a.estado, encoding="utf-8") as f:
            previo = json.load(f)
    revisado = {x.strip() for x in a.revisado.split(";") if x.strip()}

    errores, cambios, avisos = [], [], []
    por_id = {}  # BOE-A -> {"claves": set, "paginas": set, "ficha": dict}
    previo_por_id = {v.get("id"): v for v in previo.values() if isinstance(v, dict) and v.get("id")}

    for clave, paginas in sorted(citas.items()):
        if clave in NO_VIGILABLES:
            avisos.append(f"{clave}: no se vigila ({NO_VIGILABLES[clave]})")
            continue
        candidatos = [clave] if RX_ID.fullmatch(clave) else [SEMILLA.get(clave), "BUSCAR"]
        guardado = None if RX_ID.fullmatch(clave) else (previo.get(clave) or {}).get("id")
        hallado, motivo = None, ""
        try:
            for cand in dict.fromkeys(c for c in candidatos if c):
                if cand == "BUSCAR":
                    try:
                        cand, motivo = resuelve(clave)
                    except SinRespuesta:
                        if not guardado:
                            raise
                        cand, motivo = guardado, ""
                        avisos.append(f"{clave}: buscador del BOE caído; se usa el identificador guardado {guardado}")
                    if not cand:
                        break
                if cand in por_id:
                    hallado = cand
                    break
                try:
                    fi = ficha(cand)
                except LookupError as e:
                    motivo = f"{cand} no está en la legislación consolidada ({e})"
                    continue
                if not fi["titulo"]:
                    motivo = f"la ficha {cand} no trae título. Muestra: {json.dumps(fi['crudo'])[:300]}"
                    continue
                if not RX_ID.fullmatch(clave) and not es_esa_norma(clave, fi["titulo"]):
                    motivo = f"{cand} no es esa norma (BOE: «{fi['titulo'][:90]}»)"
                    continue
                if DEPARTAMENTO_ESPERADO.get(clave, "") not in fi["departamento"].lower():
                    motivo = f"{cand} es de otro emisor ({fi['departamento']}), no de la {DEPARTAMENTO_ESPERADO[clave]}"
                    continue
                if not fi["actualizacion"]:
                    motivo = f"la ficha {cand} no trae fecha de actualización"
                    continue
                por_id[cand] = {"claves": set(), "paginas": set(), "ficha": fi}
                hallado = cand
                break
        except SinRespuesta as e:
            errores.append(f"{clave}: {e}")
            continue
        if not hallado:
            errores.append(f"{clave} ({', '.join(sorted(paginas))}): {motivo or 'sin identificar'}")
            continue
        por_id[hallado]["claves"].add(clave)
        por_id[hallado]["paginas"] |= paginas

    nuevo, vigiladas = {}, []
    for boe_id, info in sorted(por_id.items()):
        fi = info["ficha"]
        nombres = " = ".join(sorted(info["claves"], key=lambda c: (c.startswith("BOE-A-"), c)))
        paginas = ", ".join(sorted(info["paginas"]))
        antes = (previo_por_id.get(boe_id) or {}).get("actualizacion")
        guardar = fi["actualizacion"]
        if fi["derogada"] or fi["agotada"]:
            errores.append(f"{nombres} ({boe_id}): el BOE la da por {'derogada' if fi['derogada'] else 'con vigencia agotada'}. Revisar: {paginas}")
        if a.pendientes_desde and fi["actualizacion"][:8] >= a.pendientes_desde and not (
                "todo" in revisado or boe_id in revisado or info["claves"] & revisado):
            antes = "pendiente de revisión"
        if antes and fi["actualizacion"] != antes:
            if "todo" in revisado or boe_id in revisado or info["claves"] & revisado:
                avisos.append(f"{nombres} ({boe_id}): actualizada ({fi['actualizacion']}), marcada como revisada")
            else:
                guardar = antes  # sigue en rojo cada día hasta que se marque como revisada
                cambios.append(f"{nombres} ({boe_id}): actualizada el {fi['actualizacion'][:8]} (antes: {antes[:20]}). "
                               f"Revisar contra el BOE: {paginas}")
        for c in info["claves"]:
            nuevo[c] = {"id": boe_id, "actualizacion": guardar, "titulo": fi["titulo"][:160]}
        vigiladas.append(f"{nombres} ({boe_id}) · {fi['actualizacion'][:8]} · {fi['departamento'][:40]} · «{fi['titulo'][:80]}»")

    sin_estado = not previo
    if sin_estado and not a.inicial:
        errores.append("ESTADO PERDIDO: no hay estado de la ejecución anterior (caché caducada o rama nueva). "
                       "Si es la primera ejecución, lanzar `gh workflow run boe.yml -f inicial=true`.")
    with open(a.estado, "w", encoding="utf-8") as f:
        json.dump({**{k: v for k, v in previo.items() if k not in nuevo}, **nuevo}, f, ensure_ascii=False, indent=1)

    cab = ["# Vigilancia del BOE", "",
           f"{len(vigiladas)} normas vigiladas · {len(cambios)} cambiadas sin revisar · {len(errores)} errores"
           + (" · punto de partida (primera ejecución)" if sin_estado and a.inicial else ""), ""]
    if cambios:
        cab += ["## Normas actualizadas: revisar las páginas", "",
                "Sigue en rojo cada día hasta que, revisadas las páginas contra el BOE, se lance "
                "`gh workflow run boe.yml --ref main -f revisado=\"<norma>;<norma>\"`.", ""] + [f"- {x}" for x in cambios] + [""]
    if errores:
        cab += ["## Errores", ""] + [f"- {x}" for x in errores] + [""]
    if avisos:
        cab += ["## Avisos", ""] + [f"- {x}" for x in avisos] + [""]
    cabeza = "\n".join(cab)
    salida = cabeza + "\n## Vigiladas\n\n" + "\n".join(f"- {x}" for x in vigiladas)
    print(salida)
    if os.environ.get("GITHUB_ACTIONS"):
        anota("notice", cabeza)
        trozo, trozos = "", []
        for linea in vigiladas:
            if len(trozo) + len(linea) > 3500:
                trozos.append(trozo)
                trozo = ""
            trozo += linea + "\n"
        trozos.append(trozo)
        for n, t in enumerate(trozos[:4], 1):
            anota("notice", f"Vigiladas ({n}/{len(trozos)}):\n{t}")
        for e in (cambios + errores)[:9]:
            anota("error", e)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(salida + "\n")
    sys.exit(1 if (cambios or errores) else 0)


if __name__ == "__main__":
    main()
