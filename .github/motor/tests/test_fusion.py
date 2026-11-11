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

    def test_a_mano_no(self):
        for f in [".github/workflows/fusion.yml", ".github/workflows/revision-motor.yml", ".GITHUB/WORKFLOWS/x.yml",
                  ".github/Workflows/x.yml", ".GitHub/motor/x.py", ".github/actions/x/action.yml", ".github/CODEOWNERS",
                  ".github/dependabot.yml", "a/.github/b.html", "a/.github/motor/x.py", "CNAME", "cname", "docs_fusion.py",
                  ".github/motor/a\nb.py", ".github/motor/@jose.py", ".github/motor/a`b.py", "x`y.html"]:
            self.assertFalse(fusion.evaluar_cambios(["index.html", f])[0], f)

    def test_motor_pasa_y_se_avisa(self):
        ok, texto = fusion.evaluar_cambios(["index.html", ".github/motor/fusion.py", ".github/motor/datos/x.json"])
        self.assertTrue(ok)
        self.assertIn("2 del motor", texto)
        self.assertTrue(fusion.es_motor(".github/motor/salud.py"))
        self.assertFalse(fusion.es_motor(".github/workflows/fusion.yml"))
        self.assertFalse(fusion.es_motor(".github/CODEOWNERS"))

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
        os.makedirs(os.path.join(self.d, ".github/workflows"))
        open(os.path.join(self.d, ".github/motor/f.py"), "w").write("x\n")
        open(os.path.join(self.d, ".github/workflows/w.yml"), "w").write("on: push\n")
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

    def test_no_ascii_en_workflows_no(self):
        r = self.preparar(lambda: open(os.path.join(self.d, ".github/workflows/ñ.yml"), "w").write("on: push\n"))
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_renombrado_desde_workflows_no(self):
        r = self.preparar(lambda: self.run_git("mv", ".github/workflows/w.yml", "w.html"))
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_motor_pasa_con_aviso(self):
        r = self.preparar(lambda: open(os.path.join(self.d, ".github/motor/f.py"), "a").write("y\n"))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("MOTOR: 1 ficheros: .github/motor/f.py", r.stdout)

    def test_pagina_sin_aviso(self):
        r = self.preparar(lambda: open(os.path.join(self.d, "index.html"), "a").write("<p>b</p>\n"))
        self.assertNotIn("MOTOR:", r.stdout)

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
        for f in ("fusion.py", "fusion_barrido.sh"):
            subprocess.run(["cp", os.path.join(motor, f), os.path.join(origen, ".github/motor")], check=True)
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


class AvisoMotor(unittest.TestCase):
    """Cambios del motor: solo se fusionan con «Revisión del motor» bien en GitHub sobre ese commit, uno por vuelta,
    y dejan aviso para Jose; los de la web no necesitan esa revisión ni dejan aviso."""

    def barrer(self, ficheros, runs="", prs=1, borra=False):
        raiz = tempfile.mkdtemp()
        g = lambda d, *a: subprocess.run(["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@t", *a],
                                         check=True, capture_output=True, text=True).stdout.strip()
        origen = os.path.join(raiz, "origen")
        os.makedirs(os.path.join(origen, ".github/motor"))
        g(origen, "init", "-q", "-b", "main")
        motor = os.path.join(os.path.dirname(__file__), "..")
        for f in ("fusion.py", "fusion_barrido.sh"):
            subprocess.run(["cp", os.path.join(motor, f), os.path.join(origen, ".github/motor")], check=True)
        open(os.path.join(origen, ".github/motor/salud.py"), "w").write("print('Errores: 0')\n")
        open(os.path.join(origen, "index.html"), "w").write("<p>a</p>\n")
        g(origen, "add", "-A")
        g(origen, "commit", "-qm", "base")
        base = g(origen, "rev-parse", "HEAD")
        lista = []
        for n in range(1, prs + 1):
            g(origen, "checkout", "-q", "-b", f"claude/m{n}", "main")
            for fichero in ficheros:
                open(os.path.join(origen, fichero), "a").write(f"# cambio {n}\n")
            g(origen, "add", "-A")
            g(origen, "commit", "-qm", f"Cambio de regla {n}")
            padre = g(origen, "rev-parse", "HEAD")
            g(origen, "commit", "-q", "--allow-empty", "-m",
              sello("Repaso: regla v1 · 0 reparos · revisor Sonnet · limpio", revisado=padre))
            sha = g(origen, "rev-parse", "HEAD")
            g(origen, "update-ref", f"refs/pull/{n}/head", "HEAD")
            g(origen, "checkout", "-q", "main")
            lista.append(f"{n} {sha}")
        subprocess.run(["git", "clone", "-q", origen, os.path.join(raiz, "main")], check=True)
        binario = os.path.join(raiz, "bin")
        os.makedirs(binario)
        aviso = os.path.join(raiz, "aviso_enviado.txt")
        open(os.path.join(raiz, "runs.txt"), "w").write(runs)
        open(os.path.join(binario, "gh"), "w").write(
            "#!/bin/bash\n"
            "case \"$1 $2\" in\n"
            "  'pr list') printf '" + "\\n".join(lista) + "\\n';;\n"
            f"  'api repos/x/y/git/ref/heads/main') echo '{base}';;\n"
            f"  'api repos/x/y/actions/'*) cat {os.path.join(raiz, 'runs.txt')};;\n"
            "  'api -X') [ -n \"${BORRA_TRAS_FUSIONAR:-}\" ] && rm -f main/.github/motor/fusion.py main/.github/motor/salud.py;;\n"
            "  'pr comment') while [ $# -gt 0 ]; do [ \"$1\" = --body-file ] && cp \"$2\" " + aviso + "; shift; done;;\n"
            "esac\nexit 0\n")
        os.chmod(os.path.join(binario, "gh"), 0o755)
        env = dict(os.environ, PATH=binario + os.pathsep + os.environ["PATH"], REPO="x/y", ACTIVA="si", GH_TOKEN="x")
        env.pop("SOLO_PR", None)
        env.pop("FUSION_COPIA", None)
        if borra:
            env["BORRA_TRAS_FUSIONAR"] = "1"
        r = subprocess.run(["bash", os.path.join(motor, "fusion_barrido.sh")], cwd=raiz, env=env,
                           capture_output=True, text=True)
        texto = open(aviso).read() if os.path.exists(aviso) else None
        return r.stdout + r.stderr, texto

    OK = "completed success 1 https://x/run/1\n"

    def test_motor_revisado_se_fusiona_y_avisa(self):
        salida, texto = self.barrer([".github/motor/fusion.py"], self.OK)
        self.assertIn("PR #1 fusionado en main", salida, salida)
        self.assertIn("Cambio de regla 1", texto)
        self.assertIn("https://x/run/1", texto)
        self.assertIn(".github/motor/fusion.py", texto)

    def test_motor_sin_revision_no(self):
        salida, texto = self.barrer([".github/motor/fusion.py"], "")
        self.assertNotIn("fusionado en main", salida)
        self.assertIn("no hay revisión del motor", salida)
        self.assertIsNone(texto)

    def test_motor_con_un_fallo_previo_no(self):
        salida, _ = self.barrer([".github/motor/fusion.py"], "completed failure 1 https://x/run/1\n" + self.OK)
        self.assertNotIn("fusionado en main", salida)

    def test_motor_reejecutado_no(self):
        salida, _ = self.barrer([".github/motor/fusion.py"], "completed success 2 https://x/run/1\n")
        self.assertNotIn("fusionado en main", salida)

    def test_motor_en_marcha_no(self):
        salida, _ = self.barrer([".github/motor/fusion.py"], "in_progress null 1 https://x/run/2\n" + self.OK)
        self.assertNotIn("fusionado en main", salida)

    def test_cancelada_no_cuenta(self):
        salida, _ = self.barrer([".github/motor/fusion.py"], "completed cancelled 1 https://x/run/0\n" + self.OK)
        self.assertIn("PR #1 fusionado en main", salida, salida)

    def test_un_motor_por_vuelta(self):
        salida, _ = self.barrer([".github/motor/fusion.py"], self.OK, prs=2)
        self.assertIn("PR #1 fusionado en main", salida, salida)
        self.assertNotIn("PR #2", salida)

    def test_web_sin_revision_ni_aviso(self):
        salida, texto = self.barrer(["index.html"], "")
        self.assertIn("PR #1 fusionado en main", salida, salida)
        self.assertIsNone(texto)

    def test_barrido_corre_desde_copia(self):
        """Lo que cambia en main tras fusionar no cambia lo que ejecuta la vuelta en curso (reparo 2 del repaso v1):
        si tras el primer PR desaparecen los programas de main, el segundo se sigue juzgando con la copia."""
        salida, _ = self.barrer(["index.html"], "", prs=2, borra=True)
        self.assertIn("PR #1 fusionado en main", salida, salida)
        self.assertIn("PR #2 fusionado en main", salida, salida)


class RevisorMotor(unittest.TestCase):
    """El revisor del motor solo da por buena una revisión con «VEREDICTO: LIMPIO» en la primera línea."""

    def setUp(self):
        import revisor_motor
        self.rm = revisor_motor

    def test_limpio_pasa(self):
        self.assertTrue(self.rm.veredicto("VEREDICTO: LIMPIO\n")[0])
        self.assertTrue(self.rm.veredicto("**VEREDICTO: LIMPIO**")[0])

    def test_lo_demas_no(self):
        for r in ["", None, "VEREDICTO: REPAROS\n1. x", "Todo bien.\nVEREDICTO: LIMPIO", "VEREDICTO: LIMPIO salvo x",
                  "veredicto: limpio", "VEREDICTO: LIMPIO?"]:
            self.assertFalse(self.rm.veredicto(r)[0], r)

    def test_sin_clave_no(self):
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        r = subprocess.run([sys.executable, self.rm.__file__, "--repo", ".", "--base", "x", "--cabeza", "y"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ANTHROPIC_API_KEY", r.stdout)
