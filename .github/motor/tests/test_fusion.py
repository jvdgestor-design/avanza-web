"""Pruebas de la fusión automática: cada una debe poder fallar si la puerta deja pasar algo que no debe.
python3 -B -m unittest discover -s .github/motor/tests -p "test_fusion.py"
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fusion  # noqa: E402

P = "a" * 40


def sello(repaso, redactor="Opus", revisado=P):
    return f"Sello\n\nRedactor: {redactor}\nRevisado: {revisado}\n{repaso}\n"


class Mensaje(unittest.TestCase):
    def ok(self, m):
        self.assertTrue(fusion.evaluar_mensaje(m, P)[0], m)

    def no(self, m):
        self.assertFalse(fusion.evaluar_mensaje(m, P)[0], m)

    def test_limpio_pasa(self):
        self.ok(sello("BOE leído el 11/11/2026. Repaso: página X v2 · 6 afirmaciones · 0 reparos · revisor Sonnet · limpio"))

    def test_corregidos_pasa(self):
        self.ok(sello("Repaso: v2 · 1 reparo (coma) corregido · revisor Sonnet · limpio"))

    def test_burlas_no(self):
        for r in ["2 reparos abiertos", "reparos abiertos: 2", "2 reparos", "dos reparos abiertos",
                  "3 reparos sin resolver", "2 reparos pendientes", "No está limpio", "con reparos"]:
            self.no(sello(f"Repaso: v1 · {r} · revisor Sonnet · limpio"))

    def test_sin_tramo_reparos_no(self):
        self.no(sello("Repaso: v1 · revisor Sonnet · limpio"))

    def test_dos_limpio_no(self):
        self.no(sello("Repaso: v1 · limpio · 0 reparos · revisor Sonnet · limpio"))

    def test_no_termina_en_limpio_no(self):
        self.no(sello("Repaso: v1 · 0 reparos · revisor Sonnet · limpio · falta BOE"))

    def test_mismo_modelo_no(self):
        self.no(sello("Repaso: v1 · 0 reparos · revisor Sonnet · limpio", redactor="Sonnet"))

    def test_varios_redactores_no(self):
        self.no(sello("Repaso: v1 · 0 reparos · revisor Sonnet · limpio", redactor="Opus y Sonnet"))

    def test_revisor_inventado_no(self):
        self.no(sello("Repaso: v1 · 0 reparos · revisor sonnetx · limpio"))

    def test_sin_revisor_no(self):
        self.no(sello("Repaso: v1 · 0 reparos · Sonnet · limpio"))

    def test_sin_redactor_no(self):
        self.no(f"x\n\nRevisado: {P}\nRepaso: v1 · 0 reparos · revisor Sonnet · limpio")

    def test_revisado_de_otro_commit_no(self):
        self.no(sello("Repaso: v1 · 0 reparos · revisor Sonnet · limpio", revisado="b" * 40))

    def test_dos_repasos_no(self):
        self.no(sello("Repaso: v1 · 2 reparos abiertos · revisor Sonnet · con reparos\n"
                      "Repaso: v2 · 0 reparos · revisor Sonnet · limpio"))


class Cambios(unittest.TestCase):
    def test_paginas_pasan(self):
        self.assertTrue(fusion.evaluar_cambios(["index.html", "en/x.html", "llms.txt", "sitemap.xml"])[0])

    def test_motor_no(self):
        for f in [".github/workflows/fusion.yml", ".GitHub/x.html", "a/.github/b.html", "CNAME", "docs_fusion.py"]:
            self.assertFalse(fusion.evaluar_cambios(["index.html", f])[0], f)

    def test_vacio_no(self):
        self.assertFalse(fusion.evaluar_cambios([])[0])


class Repositorio(unittest.TestCase):
    """Rutas no ASCII y renombrados desde .github/ (reparos 1 y 2 del repaso v1)."""

    def run_git(self, *a):
        return subprocess.run(["git", "-C", self.d, "-c", "user.name=t", "-c", "user.email=t@t", *a],
                              check=True, capture_output=True, text=True).stdout.strip()

    def preparar(self, cambio):
        self.d = tempfile.mkdtemp()
        self.run_git("init", "-q")
        os.makedirs(os.path.join(self.d, ".github/motor"))
        open(os.path.join(self.d, ".github/motor/f.py"), "w").write("x\n")
        open(os.path.join(self.d, "index.html"), "w").write("<p>a</p>\n")
        self.run_git("add", "-A")
        self.run_git("commit", "-qm", "base")
        base = self.run_git("rev-parse", "HEAD")
        cambio()
        self.run_git("add", "-A")
        self.run_git("commit", "-qm", "cambio")
        padre = self.run_git("rev-parse", "HEAD")
        self.run_git("commit", "-q", "--allow-empty", "-m",
                     sello("Repaso: v1 · 0 reparos · revisor Sonnet · limpio", revisado=padre))
        return subprocess.run([sys.executable, fusion.__file__, "--rama", self.d, "--base", base],
                              capture_output=True, text=True)

    def test_pagina_pasa(self):
        r = self.preparar(lambda: open(os.path.join(self.d, "index.html"), "a").write("<p>b</p>\n"))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_no_ascii_en_github_no(self):
        r = self.preparar(lambda: open(os.path.join(self.d, ".github/motor/ñ.yml"), "w").write("on: push\n"))
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_renombrado_desde_github_no(self):
        r = self.preparar(lambda: self.run_git("mv", ".github/motor/f.py", "f.html"))
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_sello_que_cambia_ficheros_no(self):
        self.d = tempfile.mkdtemp()
        self.run_git("init", "-q")
        open(os.path.join(self.d, "index.html"), "w").write("a\n")
        self.run_git("add", "-A")
        self.run_git("commit", "-qm", "base")
        base = self.run_git("rev-parse", "HEAD")
        open(os.path.join(self.d, "index.html"), "a").write("b\n")
        self.run_git("commit", "-qam", "revisado")
        padre = self.run_git("rev-parse", "HEAD")
        open(os.path.join(self.d, "index.html"), "a").write("cambio tras el repaso\n")
        self.run_git("commit", "-qam", sello("Repaso: v1 · 0 reparos · revisor Sonnet · limpio", revisado=padre))
        r = subprocess.run([sys.executable, fusion.__file__, "--rama", self.d, "--base", base],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout)


if __name__ == "__main__":
    unittest.main()


class Simbolicos(Repositorio):
    def test_enlace_simbolico_no(self):
        r = self.preparar(lambda: os.symlink("/etc/passwd", os.path.join(self.d, "leak.html")))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("simbólicos", r.stdout)


class Barrido(unittest.TestCase):
    """Un PR que no pasa no debe cortar el barrido ni poner el flujo en rojo (reparo 1 de la v2)."""

    def test_pr_malo_no_corta_el_siguiente(self):
        raiz = tempfile.mkdtemp()
        g = lambda d, *a: subprocess.run(["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@t", *a],
                                         check=True, capture_output=True, text=True).stdout.strip()
        origen = os.path.join(raiz, "origen")
        os.makedirs(origen)
        g(origen, "init", "-q", "-b", "main")
        motor = os.path.join(os.path.dirname(__file__), "..")
        os.makedirs(os.path.join(origen, ".github/motor"))
        subprocess.run(["cp", os.path.join(motor, "fusion.py"), os.path.join(origen, ".github/motor")], check=True)
        open(os.path.join(origen, ".github/motor/salud.py"), "w").write("print('Errores: 0')\n")  # la salud real se prueba aparte
        open(os.path.join(origen, "index.html"), "w").write(
            '<!doctype html><html lang="es"><head><title>a</title></head><body><main><h1>a</h1></main></body></html>\n')
        g(origen, "add", "-A")
        g(origen, "commit", "-qm", "base")
        shas = []
        for n, rep in ((1, "2 reparos abiertos"), (2, "0 reparos")):
            g(origen, "checkout", "-q", "-b", f"claude/p{n}", "main")
            open(os.path.join(origen, f"p{n}.txt"), "w").write("x\n")
            g(origen, "add", "-A")
            g(origen, "commit", "-qm", f"p{n}")
            padre = g(origen, "rev-parse", "HEAD")
            g(origen, "commit", "-q", "--allow-empty", "-m",
              sello(f"Repaso: p{n} · {rep} · revisor Sonnet · limpio", revisado=padre))
            shas.append(g(origen, "rev-parse", "HEAD"))
            g(origen, "update-ref", f"refs/pull/{n}/head", "HEAD")
            g(origen, "checkout", "-q", "main")
        subprocess.run(["git", "clone", "-q", origen, os.path.join(raiz, "main")], check=True)
        binario = os.path.join(raiz, "bin")
        os.makedirs(binario)
        gh = os.path.join(binario, "gh")
        open(gh, "w").write(f"#!/bin/sh\nprintf '1 {shas[0]}\\n2 {shas[1]}\\n'\n")
        os.chmod(gh, 0o755)
        env = dict(os.environ, PATH=binario + os.pathsep + os.environ["PATH"], REPO="x/y", ACTIVA="no", GH_TOKEN="x")
        env.pop("SOLO_PR", None)
        r = subprocess.run(["bash", "-e", os.path.join(motor, "fusion_barrido.sh")], cwd=raiz, env=env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PR #1 NO se fusiona", r.stdout)
        self.assertIn("SIMULACIÓN: el PR #2 se fusionaría", r.stdout, r.stdout + r.stderr)
