#!/usr/bin/env python3
"""Revisión de fondo de las páginas contra el texto vigente del BOE, sin usos de Claude (créditos de API).

Para una norma que la «Vigilancia del BOE» ha dado por actualizada:
1. Saca de cada página que la cita las frases que la nombran y los artículos citados en ellas.
2. Lee esos artículos del texto consolidado del BOE (API de datos abiertos, documentación oficial
   «APIconsolidada.pdf», apartado 2.2: /id/{id}/texto/indice y /id/{id}/texto/bloque/{id_bloque}),
   con la versión vigente hoy y, si las hay, las versiones con vigencia futura.
3. Pide a Claude (por la API, secreto ANTHROPIC_API_KEY) qué afirmación de cada página ya no casa con
   el texto vigente, con la frase literal de la página y la del BOE. El informe sale en anotaciones.

Lo que dice el modelo es nivel C: cada discrepancia se comprueba en el BOE (puerta 4) antes de tocar nada.
Solo biblioteca estándar de Python. Uso: boe_revisor.py --norma "LIVA" (o «Ley 37/1992», o «BOE-A-1992-28740»).
"""
import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boe  # noqa: E402  (mismas citas, alias e identificadores que la vigilancia)

MODELO = os.environ.get("AVANZA_MODELO_BOE", "claude-opus-5-5")
TOPE_ARTICULO = 45000      # caracteres por artículo (la LIVA 20 o la LIRPF 7 son muy largos)
TOPE_ENCARGO = 400000      # caracteres por llamada (~100-130k tokens)

# Abreviaturas que se usan en la cola de trabajo y no están en los alias de la vigilancia.
EXTRA = {"ET": "Real Decreto Legislativo 2/2015", "TRLGSS": "Real Decreto Legislativo 8/2015"}
INGLES_DE = {"Ley Orgánica": "Organic Law", "Real Decreto-ley": "Royal Decree-Law",
             "Real Decreto Legislativo": "Royal Legislative Decree", "Real Decreto": "Royal Decree", "Ley": "Law"}

RX_ART = re.compile(
    r"\b(?:arts?\.|artículos?|articles?)\s*"
    r"((?:\d{1,4}(?:\s*(?:bis|ter|quater|quinquies|sexies))?(?:\.[0-9A-Za-zºª]+)*\.?(?:\s*(?:,|y|e|and|a|al)\s*)?)+)",
    re.I)
RX_NUM = re.compile(r"(?<!\d)(\d{1,4})(?!\d)(?:\s*(bis|ter|quater|quinquies|sexies))?", re.I)
ENCARGO = """Eres un asesor fiscal y laboral que revisa una web profesional contra el texto vigente del BOE. La web la firma un asesor y la usan abogados: un error publicado es grave, y una falsa alarma hace perder tiempo.

Recibes una norma, las frases de cada página que la citan (con los artículos citados) y el texto consolidado de esos artículos: la versión vigente hoy y, si existen, versiones con vigencia futura (marcadas).

Tu tarea: decir qué afirmación de cada página ya NO casa con el texto vigente (o dejará de casar en una fecha ya publicada).
Reglas:
- Solo señalas lo que puedes sostener con el texto del BOE que se te da. Nada de memoria: si para decidir hace falta un artículo que no se te da, va en «NO COMPROBABLE» con el artículo que faltaría.
- Cada discrepancia: página · frase literal de la página (copiada exacta) · artículo y frase literal del BOE (copiada exacta, con su fecha de vigencia) · por qué no casan · arreglo propuesto en una línea.
- Una cita que solo remite al artículo sin afirmar nada concreto no es discrepancia.
- Una simplificación divulgativa correcta no es discrepancia; una cifra, plazo, porcentaje, umbral, requisito o número de artículo que no coincide, sí.
- Si un artículo citado trata de otra cosa, es discrepancia (cita errónea). Si un artículo no aparece en el índice del BOE de esta norma, puede ser de otra norma de la misma frase (la que se modifica, un reglamento): va en «NO COMPROBABLE», salvo que la frase se lo atribuya sin duda a esta norma.

La PRIMERA línea es exactamente «VEREDICTO: DESFASE» si hay al menos una discrepancia, o «VEREDICTO: CASA» si no la hay. Después: «DISCREPANCIAS» (numeradas), «CAMBIOS FUTUROS» (versiones ya publicadas con vigencia posterior a hoy que afectan a lo que dice la página) y «NO COMPROBABLE». Sin preámbulo ni resumen. En español."""


def limpio(texto):
    return re.sub(r"(?m)^\s*::", ": :", str(texto))


def di(texto):
    print(limpio(texto))


def anota(nivel, texto):
    texto = limpio(texto)
    t = texto.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::{nivel}::{t}")


FALLOS_XML = [0]


def pide_xml(url):
    req = urllib.request.Request(url, headers={"Accept": "application/xml", "User-Agent": "AvanzaRevisionBOE/1.0"})
    if FALLOS_XML[0] >= 3:
        raise boe.SinRespuesta("el BOE no contesta (tres fallos seguidos)")
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                FALLOS_XML[0] = 0
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            ultimo = e
            if 400 <= e.code < 500:
                break
        except Exception as e:
            ultimo = e
        if i < 2:
            time.sleep(5 * (i + 1))
    FALLOS_XML[0] += 1
    raise boe.SinRespuesta(f"{url}: {ultimo}")


def canonica(entrada):
    e = entrada.strip()
    if boe.RX_ID.fullmatch(e):
        inverso = {v: k for k, v in boe.SEMILLA.items()}
        if e in inverso:
            return inverso[e], e
        titulo = boe.ficha(e)["titulo"]
        m = boe.RX_NORMA.match(titulo.strip())
        if not m:
            raise LookupError(f"{e}: no se sabe con qué nombre la citan las páginas («{titulo[:90]}»)")
        return f"{boe.canon_tipo(m.group(1))} {m.group(2)}/{m.group(3)}", e
    m = re.fullmatch(r"RDL\s+(\d+/\d{4})", e, re.I)
    if m:
        e = f"Real Decreto-ley {m.group(1)}"
    e = EXTRA.get(e, boe.ALIAS.get(e, e))
    m = boe.RX_NORMA.fullmatch(e)
    if m:
        e = f"{boe.canon_tipo(m.group(1))} {m.group(2)}/{m.group(3)}"
    ident = boe.SEMILLA.get(e)
    if not ident:
        ident, motivo = boe.resuelve(e)
        if not ident:
            raise LookupError(f"{entrada}: {motivo}")
    return e, ident


def nombres_de(canon, ident, citas):
    """Todas las formas con que las páginas pueden nombrar la norma."""
    nombres = {ident}
    if canon:
        nombres.add(canon)
        nombres |= {k for k, v in {**boe.ALIAS, **EXTRA}.items() if v == canon}
        m = boe.RX_NORMA.fullmatch(canon)
        if m:
            nombres.add(f"{INGLES_DE.get(boe.canon_tipo(m.group(1)), m.group(1))} {m.group(2)}/{m.group(3)}")
            if boe.canon_tipo(m.group(1)) == "Real Decreto-ley":
                nombres.add(f"RDL {m.group(2)}/{m.group(3)}")
    paginas = set()
    for clave, pags in citas.items():
        if clave in nombres:
            paginas |= pags
    return nombres, sorted(paginas)


def frases(texto):
    return [f.strip() for f in re.split(r"(?<=[.;:?!])\s+(?=[A-ZÁÉÍÓÚÑ¿«(])|\n+", texto) if f.strip()]


def articulos(frase, propia=None):
    """Artículos citados en la frase. Con `propia` (regex de la norma), solo los que se refieren a ella:
    el artículo es de la primera norma que lo sigue en la frase («art. 104 TRLRHL») o, si no la hay, de la anterior."""
    marcas = []
    if propia is not None:
        for rx in (boe.RX_NORMA, boe.RX_INGLES, boe.RX_ALIAS, boe.RX_ID, propia):
            marcas += [(m.start(), bool(propia.fullmatch(m.group(0)))) for m in rx.finditer(frase)]
        marcas.sort()
    salida = []
    for m in RX_ART.finditer(frase):
        if marcas:
            despues = [es for pos, es in marcas if pos >= m.end() - 1]
            antes = [es for pos, es in marcas if pos < m.start()]
            if not (despues[0] if despues else (antes[-1] if antes else False)):
                continue
        for n in RX_NUM.finditer(m.group(1)):
            # «20.Uno.23.º» -> 20; los números que siguen a un punto son apartados, no artículos
            if m.group(1)[:n.start()].rstrip().endswith("."):
                continue
            salida.append((n.group(1) + (" " + n.group(2).lower() if n.group(2) else "")).strip())
    return list(dict.fromkeys(salida))


def citas_en_pagina(pagina, nombres):
    with open(pagina, encoding="utf-8") as f:
        crudo = re.sub(r"</?(?:p|li|h[1-6]|div|section|summary|details|dt|dd|tr|td|th|br|blockquote)\b[^>]*>", "\n", f.read(), flags=re.I)
        texto = boe.normaliza_html(crudo)
    rx = re.compile(r"(?<![\w/])(" + "|".join(re.escape(n) for n in sorted(nombres, key=len, reverse=True)) + r")(?![\w/])")
    halladas = []
    lista = frases(texto)
    for i, fr in enumerate(lista):
        if rx.search(fr):
            arts = articulos(fr, rx)
            if not arts and i > 0:          # «… del artículo 104. Según la LIRPF, …»: mira la frase anterior
                arts = articulos(lista[i - 1], rx)
            halladas.append((fr[:900], arts))
    return halladas


def texto_bloque(ident, id_bloque, hoy):
    xml = pide_xml(f"{boe.API}/id/{ident}/texto/bloque/{id_bloque}")
    raiz = ET.fromstring(xml)
    versiones = raiz.findall(".//version")
    if not versiones:
        raise ValueError("el BOE no devuelve versiones de este bloque")
    def fecha(v):
        return v.get("fecha_vigencia") or v.get("fecha_publicacion") or ""
    pasadas = [v for v in versiones if fecha(v) <= hoy]
    futuras = sorted((v for v in versiones if fecha(v) > hoy), key=fecha)
    vigente = max(pasadas, key=fecha) if pasadas else None
    partes, recortado = [], False
    for etiqueta, v, tope in ([("VIGENTE HOY", vigente, TOPE_ARTICULO)] if vigente is not None else []) + \
            [("VIGENCIA FUTURA", f, TOPE_ARTICULO // 2) for f in futuras]:
        cuerpo = "\n".join(" ".join("".join(p.itertext()).split()) for p in v.iter("p"))
        if len(cuerpo) > tope:
            cuerpo, recortado = cuerpo[:tope] + "\n[VERSIÓN RECORTADA]", True
        partes.append(f"[{etiqueta} · desde {fecha(v)} · norma {v.get('id_norma')}]\n{cuerpo}")
    return "\n\n".join(partes), recortado


def llama(clave, contenido):
    cuerpo = json.dumps({"model": MODELO, "max_tokens": 16000, "system": ENCARGO,
                         "messages": [{"role": "user", "content": contenido}]}).encode()
    msg = ""
    for _ in range(2):
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=cuerpo, method="POST",
                                     headers={"x-api-key": clave, "anthropic-version": "2023-06-01",
                                              "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                return json.loads(r.read().decode("utf-8")), ""
        except urllib.error.HTTPError as e:
            msg = f"La API de Claude respondió {e.code}: {e.read().decode('utf-8', 'replace')[:400]}"
            if e.code not in (429, 500, 502, 503, 529):
                break
        except Exception as e:
            return None, f"La API de Claude no contestó: {type(e).__name__} (no se reintenta: podría estar facturado)"
        time.sleep(30)
    return None, msg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--norma", required=True)
    ap.add_argument("--raiz", default=".")
    ap.add_argument("--prueba", action="store_true", help="arma el encargo sin llamar a la API")
    a = ap.parse_args()
    gha = bool(os.environ.get("GITHUB_ACTIONS"))
    hoy = datetime.datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y%m%d")

    try:
        canon, ident = canonica(a.norma)
        fi = boe.ficha(ident)
        if canon and not boe.es_esa_norma(canon, fi["titulo"]):
            raise LookupError(f"{a.norma}: {ident} no es esa norma («{fi['titulo'][:90]}»)")
        nombres, paginas = nombres_de(canon, ident, boe.citas_de(a.raiz))
        if not paginas:
            msg = f"{a.norma} ({ident}): ninguna página la cita. Nada que revisar."
            di(msg)
            if gha:
                anota("notice", msg)
            return 0
        indice = boe.pide(f"{boe.API}/id/{ident}/texto/indice")
        bloques = indice["data"][0]["bloque"] if isinstance(indice["data"], list) else indice["data"]["bloque"]
        por_titulo = {re.sub(r"\s+", " ", b.get("titulo", "")).strip().lower(): b["id"] for b in bloques}
    except (LookupError, boe.SinRespuesta, KeyError, IndexError, TypeError, ValueError) as e:
        msg = f"Revisión BOE de {a.norma}: no se pudo preparar ({type(e).__name__}: {e})"
        di(msg)
        if gha:
            anota("error", msg)
        return 1

    secciones, pedidos, sin_articulo = [], [], 0
    for p in paginas:
        citas = citas_en_pagina(os.path.join(a.raiz, p), nombres)
        if not citas:
            continue
        lineas = []
        for fr, arts in citas:
            lineas.append(f"- «{fr}»" + (f"  [artículos: {', '.join(arts)}]" if arts else "  [sin artículo]"))
            sin_articulo += not arts
            pedidos += arts
        secciones.append(f"=== Página {p} ===\n" + "\n".join(lineas))
    pedidos = list(dict.fromkeys(pedidos))
    textos, no_hallados, fallos, recortes = [], [], [], []
    for art in pedidos:
        idb = por_titulo.get(f"artículo {art}")
        if not idb:
            no_hallados.append(art)
            continue
        try:
            t, rec = texto_bloque(ident, idb, hoy)
            textos.append(f"=== Artículo {art} ({ident}, bloque {idb}) ===\n{t}")
            if rec:
                recortes.append(art)
        except (boe.SinRespuesta, ET.ParseError, ValueError) as e:
            fallos.append(f"{art} ({e})")
    if fallos:
        msg = f"Revisión BOE de {a.norma}: no se pudieron leer del BOE los artículos {'; '.join(fallos)[:600]}. No se llama al modelo."
        di(msg)
        if gha:
            anota("error", msg)
        return 1
    cabeza = (f"NORMA: {canon or ident} · {ident} · «{fi['titulo'][:160]}» · última actualización {fi['actualizacion'][:8]} · hoy {hoy}\n"
              + (f"Artículos citados que no existen en el índice del BOE: {', '.join(no_hallados)}\n" if no_hallados else ""))
    contenido = cabeza + "\n\n" + "\n\n".join(secciones) + "\n\n=== TEXTO DEL BOE ===\n\n" + "\n\n".join(textos)
    if len(contenido) > TOPE_ENCARGO:
        contenido = contenido[:TOPE_ENCARGO] + "\n[ENCARGO RECORTADO]"
        recortes.append("encargo entero")
    if recortes and gha:
        anota("warning", f"Revisión BOE de {a.norma}: texto recortado ({', '.join(recortes)}); lo recortado se revisa a mano.")
    resumen = (f"{canon or ident} ({ident}): {len(paginas)} páginas, {len(pedidos)} artículos citados "
               f"({len(no_hallados)} no hallados), {sin_articulo} frases sin artículo, {len(contenido)} caracteres")
    if a.prueba:
        di(resumen + (f" · recortes: {recortes}" if recortes else "") + "\n\n" + contenido[:4000])
        return 0
    clave = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not clave:
        msg = "Sin clave de API (ANTHROPIC_API_KEY): no se ha revisado nada; la revisión contra el BOE la hace la pasada."
        di(msg)
        if gha:
            anota("error", msg)
        return 1
    if not textos:
        msg = (f"{resumen}. No hay texto del BOE que comparar (ningún artículo citado de esta norma se ha encontrado): "
               "no está revisada; la pasada mira las frases a mano.")
        todo = "\n\n".join(secciones)
        di(msg + "\n\n" + todo)
        if gha:
            anota("error", msg)
            for n, i in enumerate(range(0, min(len(todo), 28000), 3500), 1):
                anota("notice", f"Frases de {a.norma} ({n}):\n{todo[i:i + 3500]}")
        return 1
    datos, msg = llama(clave, contenido)
    if datos is None:
        di(msg)
        if gha:
            anota("error", f"Revisión BOE de {a.norma}: {msg}")
        return 1
    informe = "".join(b.get("text", "") for b in datos.get("content", []) if b.get("type") == "text").strip()
    if not informe or datos.get("stop_reason") not in ("end_turn", "stop_sequence"):
        msg = f"Revisión BOE de {a.norma} incompleta: stop_reason={datos.get('stop_reason')}. No vale."
        di(msg)
        if gha:
            anota("error", msg)
        return 1
    uso = datos.get("usage", {})
    cab = f"BOE — {MODELO} sobre {resumen} (entrada {uso.get('input_tokens', '?')}, salida {uso.get('output_tokens', '?')} tokens)"
    di(cab + "\n\n" + informe)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(f"# {cab}\n\n~~~~\n{informe.replace('~~~~', '~ ~ ~ ~')}\n~~~~\n")
    m = re.search(r"VEREDICTO:\s*\**\s*(DESFASE|CASA)", informe[:300], re.I)
    discrepancias = re.search(r"DISCREPANCIAS\W*\n+\s*(?:\**\s*1[.)]|[-*•])", informe)
    if not m:
        estado = "SIN VEREDICTO"
    elif m.group(1).upper() == "DESFASE" or discrepancias:
        estado = "DESFASE"
    else:
        estado = "CASA"
    if gha:
        anota("notice" if estado == "CASA" else "error",
              f"Revisión BOE de {a.norma}: {estado}"
              + (" (dice CASA pero lista discrepancias)" if estado == "DESFASE" and m and m.group(1).upper() == "CASA" else "")
              + ". Cada discrepancia se comprueba en el BOE antes de tocar nada.")
        trozos = [informe[i:i + 3500] for i in range(0, len(informe), 3500)]
        for n, t in enumerate(trozos[:9], 1):
            anota("notice", f"{cab} — parte {n}/{len(trozos)}\n\n{t}")
        if len(trozos) > 9:
            anota("warning", f"Informe de {a.norma} truncado en las anotaciones ({len(trozos)} partes): el resto, en el resumen del trabajo.")
    return 0 if estado == "CASA" else 1


if __name__ == "__main__":
    sys.exit(main())
