#!/usr/bin/env python3
"""Vigilancia del BOE para las páginas de grupoavanzaconsultores.es, sin usos de Claude.

1. Saca de cada página las normas que cita (por número, «Ley 35/2006», por sigla, «LIRPF», y por
   enlace a boe.es, «BOE-A-2006-20764»).
2. Para cada norma, pide al BOE (API de datos abiertos, legislación consolidada) su ficha y la fecha
   de su última actualización, y comprueba que el identificador corresponde de verdad a esa norma
   (el título del BOE tiene que llevar su número).
3. Compara con la ejecución anterior (estado guardado en la caché de GitHub Actions). Si una norma
   citada se ha actualizado, sale con código 1 y dice qué páginas la citan: hay que revisarlas.

Sale con 1 también si un identificador no cuadra con la norma o el BOE no contesta: un cero en
silencio no vale. Solo biblioteca estándar de Python.
"""
import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

API = "https://www.boe.es/datosabiertos/api/legislacion-consolidada"

# Sigla o nombre corto -> norma. Solo equivalencias fijas; el identificador se comprueba en el BOE.
SIGLAS = {
    "LIRPF": "Ley 35/2006", "RIRPF": "Real Decreto 439/2007", "LIVA": "Ley 37/1992",
    "RIVA": "Real Decreto 1624/1992", "LGT": "Ley 58/2003", "LIS": "Ley 27/2014",
    "LISD": "Ley 29/1987", "LITPAJD": "Real Decreto Legislativo 1/1993",
    "TRLRHL": "Real Decreto Legislativo 2/2004", "LIRNR": "Real Decreto Legislativo 5/2004",
    "TRLIRNR": "Real Decreto Legislativo 5/2004", "LGSS": "Real Decreto Legislativo 8/2015",
    "TRLGSS": "Real Decreto Legislativo 8/2015", "LSC": "Real Decreto Legislativo 1/2010",
    "LETA": "Ley 20/2007", "RGAT": "Real Decreto 1065/2007", "RGR": "Real Decreto 939/2005",
    "LPAC": "Ley 39/2015", "Estatuto de los Trabajadores": "Real Decreto Legislativo 2/2015",
}
# Identificadores conocidos para no depender del buscador. Todos se comprueban contra el título del BOE.
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
}
RX_NORMA = re.compile(r"\b(Ley Orgánica|Ley|Real Decreto-ley|Real Decreto Legislativo|Real Decreto|"
                      r"Decreto Legislativo|Decreto|Orden [A-ZÁÉÍÓÚ]{2,5})\s+(\d{1,4})/(\d{4})")
RX_ID = re.compile(r"BOE-A-\d{4}-\d+")
RX_SIGLA = re.compile(r"\b(" + "|".join(re.escape(s) for s in sorted(SIGLAS, key=len, reverse=True)) + r")\b")


def pide(url, intentos=3):
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "AvanzaVigilanciaBOE/1.0"})
    for i in range(intentos):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            ultimo = e
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"{url}: {ultimo}")


def busca(nodo, claves):
    """Primer valor de una clave (en cualquier nivel) cuyo nombre contenga alguna de las dadas."""
    if isinstance(nodo, dict):
        for k, v in nodo.items():
            if any(c in k.lower() for c in claves) and isinstance(v, (str, int)):
                return str(v)
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


def fecha(texto):
    if not texto:
        return None
    t = re.sub(r"\D", "", texto)[:8]
    try:
        return datetime.strptime(t, "%Y%m%d").date()
    except ValueError:
        return None


def ficha(boe_id):
    datos = pide(f"{API}/id/{boe_id}/metadatos")
    titulo = busca(datos, ["titulo"]) or ""
    act = fecha(busca(datos, ["fecha_actualizacion", "actualizacion"]))
    return titulo, act, datos


def resuelve(norma):
    """Busca en el BOE el identificador de una norma citada por número."""
    tipo, resto = norma.rsplit(" ", 1)
    consultas = [
        json.dumps({"query": {"query_string": {"query": f'titulo:"{norma}"'}}}),
        json.dumps({"query": {"query_string": {"query": f'"{norma}"'}}}),
    ]
    for q in consultas:
        try:
            datos = pide(f"{API}?query={urllib.parse.quote(q)}&limit=20")
        except RuntimeError:
            continue
        for item in lista_resultados(datos):
            ident = busca(item, ["identificador"]) or ""
            titulo = busca(item, ["titulo"]) or ""
            if RX_ID.fullmatch(ident) and titulo.lower().startswith(tipo.lower()) and f" {resto}," in titulo + ",":
                return ident
    return None


def anota(nivel, texto):
    """Anotación de GitHub Actions: se lee con la API (check-runs/<job>/annotations), sin descargar logs."""
    t = texto.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::{nivel}::{t}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", default=".")
    ap.add_argument("--estado", default="boe-estado.json", help="fichero de la ejecución anterior")
    ap.add_argument("--revisado", default="",
                    help="normas ya revisadas tras su cambio, separadas por «;» («todo» para todas): dejan de avisar")
    ap.add_argument("--dias-inicial", type=int, default=21,
                    help="sin estado previo, se avisa de lo actualizado en estos días")
    a = ap.parse_args()

    citas = {}  # clave -> {"paginas": set, "id": str|None}
    for ruta in sorted(glob.glob(os.path.join(a.raiz, "*.html"))):
        pagina = os.path.basename(ruta)
        if pagina in ("404.html", "gracias.html"):
            continue
        with open(ruta, encoding="utf-8") as f:
            texto = f.read()
        for m in RX_NORMA.finditer(texto):
            clave = f"{m.group(1)} {m.group(2)}/{m.group(3)}"
            citas.setdefault(clave, {"paginas": set(), "id": None})["paginas"].add(pagina)
        for m in RX_SIGLA.finditer(texto):
            clave = SIGLAS[m.group(1)]
            citas.setdefault(clave, {"paginas": set(), "id": None})["paginas"].add(pagina)
        for m in RX_ID.finditer(texto):
            citas.setdefault(m.group(0), {"paginas": set(), "id": m.group(0)})["paginas"].add(pagina)

    previo = {}
    if os.path.isfile(a.estado):
        with open(a.estado, encoding="utf-8") as f:
            previo = json.load(f)

    revisado = {x.strip() for x in a.revisado.split(";") if x.strip()}
    errores, cambios, avisos, vigiladas, fuera = [], [], [], [], []
    nuevo = {}
    hoy = date.today()
    for clave, info in sorted(citas.items()):
        boe_id = info["id"] or (previo.get(clave) or {}).get("id") or SEMILLA.get(clave) or resuelve(clave)
        if not boe_id:
            fuera.append(f"{clave} ({', '.join(sorted(info['paginas']))})")
            continue
        try:
            titulo, act, crudo = ficha(boe_id)
        except RuntimeError as e:
            errores.append(f"{clave} → {boe_id}: el BOE no contesta ({e})")
            continue
        if not titulo:
            errores.append(f"{clave} → {boe_id}: la ficha del BOE no trae título. Muestra: {json.dumps(crudo)[:300]}")
            continue
        if not clave.startswith("BOE-A-"):
            numero = clave.rsplit(" ", 1)[1]
            if numero not in titulo:
                errores.append(f"{clave} → {boe_id}: el identificador no es esa norma (BOE: «{titulo[:90]}»)")
                continue
        if act is None:
            errores.append(f"{clave} → {boe_id}: la ficha del BOE no trae fecha de actualización")
            continue
        nuevo[clave] = {"id": boe_id, "actualizada": act.isoformat(), "titulo": titulo[:160]}
        paginas = ", ".join(sorted(info["paginas"]))
        vigiladas.append(f"{clave} ({boe_id}) · actualizada el {act.strftime('%d/%m/%Y')} · {paginas}")
        antes = fecha((previo.get(clave) or {}).get("actualizada"))
        if antes and act > antes:
            if clave in revisado or "todo" in revisado:
                avisos.append(f"{clave} ({boe_id}): actualizada el {act.strftime('%d/%m/%Y')}, revisada: deja de avisar")
            else:
                # Se guarda la fecha anterior: sigue avisando cada día hasta que se marque como revisada.
                nuevo[clave]["actualizada"] = antes.isoformat()
                cambios.append(f"{clave} ({boe_id}): actualizada el {act.strftime('%d/%m/%Y')} "
                               f"(antes {antes.strftime('%d/%m/%Y')}). Revisar: {paginas}")
        elif not previo and act >= hoy - timedelta(days=a.dias_inicial):
            avisos.append(f"{clave} ({boe_id}): actualizada el {act.strftime('%d/%m/%Y')}, "
                          f"en los últimos {a.dias_inicial} días. Comprobar: {paginas}")

    with open(a.estado, "w", encoding="utf-8") as f:
        json.dump({**{k: v for k, v in previo.items() if k not in nuevo}, **nuevo}, f, ensure_ascii=False, indent=1)

    lineas = ["# Vigilancia del BOE", "",
              f"{len(vigiladas)} normas vigiladas · {len(cambios)} actualizadas desde la última vez · "
              f"{len(errores)} errores · {len(fuera)} citadas sin identificar" + ("" if previo else " · primera ejecución"), ""]
    if cambios:
        lineas += ["## Normas actualizadas: revisar las páginas", "",
                   "Sigue en rojo cada día hasta que, revisadas las páginas contra el BOE, se lance el trabajo con "
                   "`gh workflow run boe.yml -f revisado=\"<norma>;<norma>\"`.", ""] + [f"- {x}" for x in cambios] + [""]
    if errores:
        lineas += ["## Errores", ""] + [f"- {x}" for x in errores] + [""]
    if avisos:
        lineas += ["## Avisos", ""] + [f"- {x}" for x in avisos] + [""]
    if fuera:
        lineas += ["## Citadas sin identificador en el BOE (no se vigilan)", ""] + [f"- {x}" for x in fuera] + [""]
    lineas += ["## Vigiladas", ""] + [f"- {x}" for x in vigiladas]
    salida = "\n".join(lineas)
    print(salida)
    if os.environ.get("GITHUB_ACTIONS"):
        anota("notice", salida)
        for e in (cambios + errores)[:9]:
            anota("error", e)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(salida + "\n")
    sys.exit(1 if (cambios or errores) else 0)


if __name__ == "__main__":
    main()
