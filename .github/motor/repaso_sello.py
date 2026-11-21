#!/usr/bin/env python3
"""Puerta 5 en GitHub sin API (22/11/2026, decisión de COMO FUNCIONAR): la revisión de otro modelo ya la hace ChatGPT
por REVISIONES, en el ordenador del despacho. Aquí solo se comprueba que el sello de la rama la cita y que lo que
ChatGPT revisó es exactamente lo que la rama cambia.

Si la rama cambia páginas (html, txt, xml fuera de .github/), su último commit tiene que ser el sello vacío de
fusion.py (Redactor, Revisado, Repaso … limpio) y llevar además una línea:

  Dictamen: SÍ · REPASO <nombre>_REPASO.md · 0 NO · huella <sha256> · revisor ChatGPT

- «SÍ» y «0 NO» son el dictamen y la cuenta de la línea final del REPASO de ChatGPT (REVISIONES\\de-chatgpt).
- La huella ata ese REPASO a un contenido: es el sha256 de la lista de ficheros que la rama cambia contra main
  (estado, sha256 del contenido y ruta de cada uno; ver `manifiesto`). La calcula este programa, nunca un modelo:
  `repaso_sello.py huella` la da para el encargo de REVISIONES, ChatGPT la vuelve a calcular y la pone en su REPASO,
  y el sello la copia. Si después del repaso cambia un fichero, la huella ya no coincide y la comprobación falla.
- El revisor del dictamen es ChatGPT (chatgpt, gpt o codex) y no puede haber redactado.

Sin sello, sin la línea «Dictamen:», con dictamen NO, con algún NO o con la huella de otro contenido, sale 1 (rojo).
Lo que GitHub no puede ver es el REPASO mismo, que está en el ordenador del despacho: eso lo acredita sello.py allí.

Uso: repaso_sello.py comprobar [--base origin/main] [--rev HEAD]     (sale 0 si vale o no hay páginas, 1 si no)
     repaso_sello.py huella [--base origin/main] [--rev HEAD]        (lista de ficheros y huella, para el encargo)
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fusion  # noqa: E402

CHATGPT = {"chatgpt", "gpt", "codex"}
PAGINAS = (".html", ".txt", ".xml")
NOMBRE_REPASO = re.compile(r"^REPASO\s+([\w .()+-]+_REPASO\.md)$")


class ErrorGit(Exception):
    pass


def git(repo, *args, crudo=False):
    r = subprocess.run(["git", "-c", "core.quotepath=off", "-C", repo, *args], capture_output=True)
    if r.returncode != 0:
        raise ErrorGit(f"git {' '.join(args)}: {r.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return r.stdout if crudo else r.stdout.decode("utf-8", "replace")


def cambios(repo, base, rev):
    """[(estado, ruta, blob nuevo)] de lo que rev cambia respecto del punto en que se separó de base."""
    origen = git(repo, "merge-base", base, rev).strip()
    crudo = git(repo, "diff", "--raw", "-z", "--no-renames", "--no-abbrev", origen, rev).split("\0")
    salida = []
    for cab, ruta in zip(crudo[0::2], crudo[1::2]):
        partes = cab.split()
        salida.append((partes[4][:1], ruta, partes[3]))
    return sorted(salida, key=lambda c: c[1].encode("utf-8"))


def manifiesto(repo, base, rev):
    """Una línea por fichero cambiado: «<estado> <sha256 del contenido en rev, o - si se borra> <ruta>»."""
    lineas = []
    for estado, ruta, blob in cambios(repo, base, rev):
        suma = "-" if estado == "D" else hashlib.sha256(git(repo, "cat-file", "blob", blob, crudo=True)).hexdigest()
        lineas.append(f"{estado} {suma} {ruta}\n")
    return "".join(lineas)


def huella(texto_manifiesto):
    return hashlib.sha256(texto_manifiesto.encode("utf-8")).hexdigest()


def evaluar_dictamen(mensaje, huella_real):
    """(True, motivo) si el sello cita un REPASO de ChatGPT favorable sobre este contenido; (False, motivo) si no."""
    lineas = [l.strip() for l in mensaje.splitlines() if l.strip()]
    dic = [l for l in lineas if re.match(r"(?i)^dictamen\s*:", l)]
    if len(dic) != 1:
        return False, "falta una (y solo una) línea «Dictamen: SÍ · REPASO <nombre>_REPASO.md · 0 NO · huella <sha256> · revisor ChatGPT»"
    tramos = [t.strip() for t in dic[0].split(":", 1)[1].split("·")]
    if len(tramos) != 5:
        return False, f"la línea «Dictamen:» debe tener cinco tramos (dictamen, REPASO, NO, huella y revisor): {dic[0]!r}"
    if tramos[0].upper() not in ("SÍ", "SI"):
        return False, f"el dictamen del REPASO no es favorable: {tramos[0]!r}"
    if not NOMBRE_REPASO.match(tramos[1]):
        return False, f"el segundo tramo debe ser «REPASO <nombre>_REPASO.md», sin ruta: {tramos[1]!r}"
    cuenta = re.match(r"^(\d+)\s+NO$", tramos[2])
    if not cuenta:
        return False, f"el tercer tramo debe ser «N NO»: {tramos[2]!r}"
    if int(cuenta.group(1)) != 0:
        return False, f"el REPASO tiene {int(cuenta.group(1))} NO"
    h = re.match(r"^huella\s+([0-9a-f]{64})$", tramos[3])
    if not h:
        return False, f"el cuarto tramo debe ser «huella <sha256 en minúsculas>»: {tramos[3]!r}"
    if h.group(1) != huella_real:
        return False, (f"la huella del REPASO ({h.group(1)[:12]}…) no es la de los ficheros que cambia la rama "
                       f"({huella_real[:12]}…): el repaso es de otro contenido")
    rev = re.match(r"(?i)^revisor\s+(\S+)$", tramos[4])
    if not rev or rev.group(1).lower() not in CHATGPT:
        return False, f"el revisor del dictamen tiene que ser ChatGPT: {tramos[4]!r}"
    red = [l for l in lineas if re.match(r"(?i)^redactor\s*:", l)]
    if any(fusion._modelos_en(l.split(":", 1)[1]) & CHATGPT for l in red):
        return False, "el redactor es ChatGPT: no puede ser también el revisor del dictamen"
    return True, f"REPASO de ChatGPT favorable ({tramos[1].split(None, 1)[1]}) sobre la huella {huella_real[:12]}…"


def comprobar(repo, base, rev):
    """(código de salida, líneas). 0 si no hay páginas cambiadas o el sello vale; 1 si no."""
    todos = cambios(repo, base, rev)
    paginas = [r for e, r, _ in todos if e in "AM" and r.endswith(PAGINAS) and not r.startswith(".github/")]
    if not paginas:
        return 0, ["Nada que revisar: la rama no cambia páginas."]
    fallos = []
    padres = git(repo, "rev-list", "--parents", "-n", "1", rev).split()[1:]
    padre = padres[0] if padres else None
    if not padre or git(repo, "rev-parse", f"{rev}^{{tree}}") != git(repo, "rev-parse", f"{padre}^{{tree}}"):
        fallos.append("el último commit no es un sello vacío: la rama cambia páginas y no lleva el REPASO de ChatGPT "
                      "(o cambia ficheros después del repaso)")
    else:
        mensaje = git(repo, "log", "-1", "--format=%B", rev)
        ok, motivo = fusion.evaluar_mensaje(mensaje, padre)
        if not ok:
            fallos.append(motivo)
        ok2, motivo2 = evaluar_dictamen(mensaje, huella(manifiesto(repo, base, rev)))
        if not ok2:
            fallos.append(motivo2)
        if not fallos:
            return 0, [f"OK: {motivo}; {motivo2}; {len(paginas)} páginas cambiadas de {len(todos)} ficheros"]
    return 1, ["NO: " + f for f in fallos]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("orden", choices=["comprobar", "huella"])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--rev", default="HEAD")
    a = ap.parse_args()
    try:
        if a.orden == "huella":
            m = manifiesto(a.repo, a.base, a.rev)
            sys.stdout.write(m)
            print(f"HUELLA: {huella(m)}")
            return 0
        codigo, lineas = comprobar(a.repo, a.base, a.rev)
    except ErrorGit as e:
        codigo, lineas = 1, [f"NO: no se pudo leer la rama ({e})"]
    for l in lineas:
        l = l.replace("::", ": :")
        print(l)
        if codigo and os.environ.get("GITHUB_ACTIONS"):
            print("::error::Revisión puerta 5: " + l.replace("%", "%25").replace("\r", " ").replace("\n", " "))
    return codigo


if __name__ == "__main__":
    sys.exit(main())
