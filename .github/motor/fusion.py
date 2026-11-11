"""Fusión automática de ramas claude/* en main (11/11/2026, encargo de Jose).

La rama termina SIEMPRE en un commit «sello» vacío (git commit --allow-empty) que no cambia ningún fichero y lleva:
  Redactor: <modelo>
  Revisado: <sha completo del commit anterior, el que vio el revisor>
  Repaso: <qué> · 0 reparos · revisor <otro modelo> · limpio
  (o «N reparos corregidos» en vez de «0 reparos» si la versión revisada ya los lleva corregidos)
El repaso cubre el diff completo de la rama contra main en el commit «Revisado». Así el repaso queda atado a un
contenido concreto: si algo cambia después, el sello deja de valer.

Además: la rama no toca .github/ ni CNAME, solo cambia ficheros de la web (html, txt, xml, css, js, imágenes, pdf),
y contiene el main actual. La salud del sitio la comprueba el flujo con el salud.py de main.

Uso: fusion.py --rama <dir del clon de la rama> --base <sha de main>     (sale 0 si se fusiona, 1 si no)
"""
import argparse
import re
import subprocess
import sys

MODELOS = {"opus", "sonnet", "haiku", "fable", "gpt", "chatgpt", "codex", "gemini"}
EXTENSIONES = (".html", ".txt", ".xml", ".css", ".js", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico", ".pdf")
TRAMO_REPAROS = re.compile(r"^(0\s+reparos|[1-9]\d*\s+reparos?(\s+\([^)]*\))?\s+corregidos?)$", re.IGNORECASE)
NEGATIVO = re.compile(r"abiert|pendient|sin\s+resolver|no\s+est|no\s+limpio|falta|con\s+reparos", re.IGNORECASE)


def _modelos_en(texto):
    return {p for p in re.findall(r"[a-záéíóú]+", texto.lower()) if p in MODELOS}


def evaluar_mensaje(mensaje, padre=None):
    """(True, motivo) si el mensaje del sello autoriza la fusión; (False, motivo) si no."""
    lineas = [l.strip() for l in mensaje.splitlines() if l.strip()]
    red = [l for l in lineas if re.match(r"(?i)^redactor\s*:", l)]
    if len(red) != 1:
        return False, "falta una (y solo una) línea «Redactor: <modelo>»"
    redactores = _modelos_en(red[0].split(":", 1)[1])
    if not redactores:
        return False, f"redactor no reconocido: {red[0]!r}"
    if padre is not None:
        rev = [l for l in lineas if re.match(r"(?i)^revisado\s*:", l)]
        if len(rev) != 1 or rev[0].split(":", 1)[1].strip() != padre:
            return False, f"falta «Revisado: {padre}» (el commit que vio el revisor)"
    rep = [l for l in lineas if re.search(r"(?i)(^|\.\s+)repaso\s*:", l)]
    if len(rep) != 1:
        return False, "debe haber exactamente una línea «Repaso: …»"
    repaso = rep[0]
    if NEGATIVO.search(repaso):
        return False, f"el repaso no está limpio: {repaso!r}"
    tramos = [t.strip().rstrip(".") for t in repaso.split("·")]
    if tramos[-1].lower() != "limpio" or sum(t.lower() == "limpio" for t in tramos) != 1:
        return False, f"el repaso debe terminar en un único «limpio»: {repaso!r}"
    con_reparo = [t for t in tramos if re.search(r"(?i)reparo", t)]
    if len(con_reparo) != 1 or not TRAMO_REPAROS.match(con_reparo[0]):
        return False, f"el repaso debe decir «0 reparos» o «N reparos corregidos» en un tramo propio: {repaso!r}"
    t_rev = [t for t in tramos if re.match(r"(?i)^revisor\s+", t)]
    if len(t_rev) != 1:
        return False, "el repaso debe llevar un tramo «revisor <modelo>»"
    nombre = t_rev[0].split(None, 1)[1].strip().lower()
    if nombre not in MODELOS:
        return False, f"revisor no reconocido: {nombre!r}"
    if nombre in redactores:
        return False, f"el revisor ({nombre}) es un modelo que redactó"
    return True, f"repaso limpio de {nombre} sobre texto de {', '.join(sorted(redactores))}"


def evaluar_cambios(ficheros):
    if not ficheros:
        return False, "la rama no cambia nada respecto a main"
    malos = []
    for f in ficheros:
        partes = f.lower().split("/")
        if ".github" in partes or f.upper() == "CNAME" or not f.lower().endswith(EXTENSIONES):
            malos.append(f)
    if malos:
        return False, "ficheros que se fusionan a mano: " + ", ".join(repr(m) for m in malos[:5])
    return True, f"{len(ficheros)} ficheros de la web"


def _git(rama, *args):
    return subprocess.run(["git", "-c", "core.quotepath=off", "-C", rama, *args],
                          check=True, capture_output=True, text=True).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rama", required=True)
    ap.add_argument("--base", required=True)
    a = ap.parse_args()
    fallos = []
    if subprocess.run(["git", "-C", a.rama, "merge-base", "--is-ancestor", a.base, "HEAD"]).returncode != 0:
        fallos.append("la rama no contiene el main actual: hay que hacer rebase y sellar de nuevo")
    padre = _git(a.rama, "rev-parse", "HEAD^").strip()
    if _git(a.rama, "rev-parse", "HEAD^{tree}") != _git(a.rama, "rev-parse", "HEAD^^{tree}"):
        fallos.append("el último commit no es un sello vacío: cambia ficheros después del repaso")
    ok, motivo = evaluar_mensaje(_git(a.rama, "log", "-1", "--format=%B"), padre)
    if not ok:
        fallos.append(motivo)
    crudo = _git(a.rama, "diff", "--raw", "-z", "--no-renames", "--no-abbrev", a.base, "HEAD").split("\0")
    ficheros, modos_malos = [], []
    for cab, ruta in zip(crudo[0::2], crudo[1::2]):
        ficheros.append(ruta)
        if cab.split()[1:2] and cab.split()[1] in ("120000", "160000"):
            modos_malos.append(ruta)
    ok2, motivo2 = evaluar_cambios(ficheros)
    if modos_malos:
        ok2, motivo2 = False, "enlaces simbólicos o submódulos: " + ", ".join(repr(m) for m in modos_malos[:5])
    if not ok2:
        fallos.append(motivo2)
    for f in fallos:
        print("NO: " + f.replace("::", ": :"))
    if not fallos:
        print(f"OK: {motivo}; {motivo2}")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
