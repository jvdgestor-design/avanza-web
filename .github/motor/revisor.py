#!/usr/bin/env python3
"""Puerta 5 en GitHub: otro modelo (Sonnet, por la API de Claude) intenta tumbar los cambios de una rama
antes de que entren en la bandeja. Se paga con los créditos de API del plan, no con el uso de Claude.

Recibe el diff de la rama contra main y el texto visible de las páginas tocadas y de sus parejas de idioma,
y devuelve los reparos. El informe sale como anotaciones del trabajo (legibles por la API de GitHub).
Sin la clave ANTHROPIC_API_KEY no hace nada y lo dice: la revisión la sigue haciendo la pasada.

Lo que dice el revisor es nivel C: cada reparo de derecho se contrasta en el BOE antes de tocar nada.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser

MODELO = os.environ.get("AVANZA_MODELO_REVISOR", "claude-sonnet-5-5")
DOMINIO = "grupoavanzaconsultores.es"

NORMAS = """Normas de la web (proyecto AVANZA WEB de Grupo Avanza Consultores, asesoría fiscal, contable y laboral):
- Titular: Jose Vicente Díaz Madrid, Diplomado en Ciencias Empresariales (nunca «licenciado»), despacho propio desde 2011. Nunca «gestor administrativo». No se atribuye ninguna titulación ni colegiación.
- Datos buenos: Grupo Avanza Consultores · 46980 Paterna (Valencia), sin calle · 614 365 547 · avanza@grupoavanzaconsultores.es · grupoavanzaconsultores.es. Online para toda España; en persona, solo con cita.
- Prohibido: precios u honorarios, ofertas, descuentos, urgencias comerciales, pedir reseñas, «el mejor», «lo hacemos todo», frases de agencia, relleno, «el despacho firma». Ni Daben Group ni clasescontabilidad.com. El teléfono de Anna solo en las páginas rusas.
- Páginas en inglés: solo atención por escrito (WhatsApp y correo), sin teléfono visible ni enlace de llamada; «tax and accounting adviser», nunca lawyer, chartered ni gestor.
- Cada página de servicio responde en sus primeras líneas: qué hacemos, para quién, dónde, cómo se trabaja y cómo contactar. Las guías explican qué decide el resultado (plazos, orden, excepciones), no el paso a paso.
- Toda norma, plazo, porcentaje o umbral tiene que ser exacto y vigente hoy (con su artículo); las FAQ visibles tienen que coincidir con el FAQPage; lo nuevo no puede contradecir otra página.
- Estilo: español correcto y directo, sin erratas, sin tono comercial."""

ENCARGO = """Eres el revisor adversarial (puerta 5). No has escrito este cambio: tu trabajo es intentar tumbarlo antes de que se publique con el nombre de un asesor fiscal que firma lo que publica.

Revisa el diff y el texto de las páginas. Para cada problema da: gravedad (BLOQUEA / CONVIENE / MENOR), la página y la frase literal afectada, por qué está mal y el arreglo concreto.

Busca sobre todo:
1. Afirmaciones de derecho, plazos, porcentajes, umbrales o artículos que puedan ser falsos, estar desfasados o tener excepciones omitidas. No tienes acceso al BOE: no afirmes que algo es correcto; lista cada afirmación jurídica que haya que comprobar en la fuente oficial, con el artículo que la sostendría y la duda concreta.
2. Contradicciones entre la página cambiada y su pareja de idioma u otra página incluida.
3. Incumplimientos de las normas de la web que se te dan.
4. FAQ visible distinta de su FAQPage, datos de contacto distintos, enlaces que apunten a otro sitio.
5. Erratas, frases confusas o con tono comercial.

La PRIMERA línea de tu respuesta es exactamente «VEREDICTO: BLOQUEA» si hay al menos un problema de gravedad BLOQUEA, o «VEREDICTO: SIGUE» si no lo hay. Después, los problemas ordenados de más a menos grave. Si algo que sospechabas está bien, no lo menciones. Sin preámbulos ni resumen final. En español."""


class Texto(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes, self._salta = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._salta += 1
        if tag in ("p", "li", "h1", "h2", "h3", "h4", "tr", "br", "div", "section", "summary", "dt", "dd"):
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._salta = max(0, self._salta - 1)

    def handle_data(self, data):
        if not self._salta:
            self.partes.append(data)


def texto_visible(html_txt):
    p = Texto()
    p.feed(html_txt)
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t]+", " ", "".join(p.partes))).strip()


class ErrorGit(Exception):
    pass


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True)
    if r.returncode != 0:
        raise ErrorGit(f"git {' '.join(args)}: {r.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return r.stdout.decode("utf-8", "replace")


def limpio(texto):
    """Que nada del informe del modelo pueda leerse como orden del runner (líneas que empiezan por «::»)."""
    return re.sub(r"(?m)^\s*::", ": :", texto)


def anota(nivel, texto):
    texto = limpio(texto)
    t = texto.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::{nivel}::{t}")


def parejas(fichero):
    """Páginas enlazadas por hreflang desde la página dada."""
    try:
        with open(fichero, encoding="utf-8") as f:
            s = f.read()
    except OSError:
        return []
    salida = []
    for href in re.findall(r'<(?:link|a)\b[^>]*hreflang="[^"]+"[^>]*href="(?:https://' + re.escape(DOMINIO) + r')?/?([^"#?]*)"', s):
        salida.append(href or "index.html")
    return [p for p in dict.fromkeys(salida) if p != fichero and os.path.isfile(p)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--prueba", action="store_true", help="arma el encargo y lo cuenta, sin llamar a la API")
    a = ap.parse_args()

    try:
        git("rev-parse", "--verify", a.base)
        cambiados = [f for f in git("diff", "--no-renames", "--name-only", "--diff-filter=AM", f"{a.base}...HEAD").split()
                     if f.endswith((".html", ".txt", ".xml")) and not f.startswith(".github/")]
        if not cambiados:
            print("Nada que revisar: la rama no cambia páginas.")
            return 0
        diff = git("diff", "--no-renames", "--unified=3", f"{a.base}...HEAD", "--", *cambiados)
    except ErrorGit as e:
        print(f"ERROR: {e}")
        if os.environ.get("GITHUB_ACTIONS"):
            anota("error", f"Revisión puerta 5: no se pudo sacar el cambio ({e})")
        return 1
    if len(diff) > 120000:
        diff = diff[:120000] + "\n[DIFF RECORTADO: el revisor no ve el resto]"
    paginas = list(dict.fromkeys(cambiados + [p for f in cambiados if f.endswith(".html") for p in parejas(f)]))
    bloques = []
    for p in paginas:
        if p.endswith(".html") and os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                crudo = f.read()
            cabeza = ""
            if p in cambiados:
                titulo = re.search(r"<title>(.*?)</title>", crudo, re.S)
                desc = re.search(r'<meta name="description" content="([^"]*)"', crudo)
                ld = re.findall(r'<script type="application/ld\+json">(.*?)</script>', crudo, re.S)
                hrefs = sorted(set(re.findall(r'href="([^"]+)"', crudo)))
                cabeza = (f"Título: {titulo.group(1).strip() if titulo else '(sin título)'}\n"
                          f"Descripción: {desc.group(1) if desc else '(sin descripción)'}\n"
                          f"JSON-LD:\n{chr(10).join(x.strip() for x in ld)}\n"
                          f"Enlaces: {' '.join(hrefs)}\n--- Texto visible ---\n")
            bloques.append(f"=== {p} ({'cambiada' if p in cambiados else 'pareja de idioma'}) ===\n"
                           + cabeza + texto_visible(crudo))
    contenido = f"{NORMAS}\n\n=== DIFF contra main ===\n{diff}\n\n" + "\n\n".join(bloques)
    if len(contenido) > 400000:
        contenido = contenido[:400000] + "\n[ENCARGO RECORTADO: faltan páginas al final; revísalas aparte]"

    if a.prueba:
        print(f"Páginas: {', '.join(paginas)} · {len(contenido)} caracteres (~{len(contenido) // 4} tokens)")
        return 0
    clave = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not clave:
        msg = "Sin clave de API (secreto ANTHROPIC_API_KEY): la revisión de la puerta 5 la hace la pasada con un subagente."
        print(msg)
        if os.environ.get("GITHUB_ACTIONS"):
            anota("warning", msg)
        return 0

    cuerpo = json.dumps({"model": MODELO, "max_tokens": 16000, "system": ENCARGO,
                         "messages": [{"role": "user", "content": contenido}]}).encode()
    datos, msg = None, ""
    for intento in range(2):
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=cuerpo, method="POST",
                                     headers={"x-api-key": clave, "anthropic-version": "2023-06-01",
                                              "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                datos = json.loads(r.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            msg = f"La API de Claude respondió {e.code}: {e.read().decode('utf-8', 'replace')[:400]}"
            if e.code not in (429, 500, 502, 503, 529):
                break
        except Exception as e:  # tiempo, red
            msg = f"La API de Claude no contestó: {type(e).__name__}"
        time.sleep(30)
    if datos is None:
        print(msg)
        if os.environ.get("GITHUB_ACTIONS"):
            anota("error", msg)
        return 1
    informe = "".join(b.get("text", "") for b in datos.get("content", []) if b.get("type") == "text").strip()
    parada = datos.get("stop_reason")
    if not informe or parada not in ("end_turn", "stop_sequence"):
        msg = f"Revisión puerta 5 incompleta: stop_reason={parada}, {len(informe)} caracteres. No vale como revisión."
        print(msg + ("\n\n" + limpio(informe) if informe else ""))
        if os.environ.get("GITHUB_ACTIONS"):
            anota("error", msg)
        return 1
    uso = datos.get("usage", {})
    cabecera = (f"Puerta 5 — revisión de {MODELO} sobre {', '.join(cambiados)} "
                f"(entrada {uso.get('input_tokens', '?')}, salida {uso.get('output_tokens', '?')} tokens)")
    print(limpio(cabecera + "\n\n" + informe))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(f"# {cabecera}\n\n{informe}\n")
    if os.environ.get("GITHUB_ACTIONS"):
        trozos = [informe[i:i + 3500] for i in range(0, len(informe), 3500)]
        total = len(trozos)
        for n, t in enumerate(trozos[:8], 1):
            anota("notice", f"{cabecera} — parte {n}/{total}" + (" (recortado: el resto, en el resumen del trabajo)" if total > 8 and n == 8 else "") + f"\n\n{t}")
    bloquea = informe.splitlines()[0].strip().upper().startswith("VEREDICTO: BLOQUEA")
    if bloquea and os.environ.get("GITHUB_ACTIONS"):
        anota("error", "Puerta 5: el revisor BLOQUEA. Ver los reparos en las anotaciones; cada uno se contrasta en la fuente.")
    return 1 if bloquea else 0


if __name__ == "__main__":
    sys.exit(main())
