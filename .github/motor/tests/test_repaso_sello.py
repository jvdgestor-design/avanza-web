"""Pruebas de la puerta 5 por sello: cada una debe poder fallar si la comprobación deja pasar algo que no debe.
python3 -B -m unittest discover -s .github/motor/tests -p "test_repaso_sello.py"
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import repaso_sello  # noqa: E402

H = "a" * 64
P = "b" * 40


def mensaje(dictamen, redactor="Fable", revisor="ChatGPT"):
    return (f"Sello\n\nRedactor: {redactor}\nRevisado: {P}\n"
            f"Repaso: página v1 · 0 reparos · revisor {revisor} · limpio\n{dictamen}\n")


def dictamen(d="SÍ", repaso="2026-11-22_AVANZA-WEB_pagina_v1_REPASO.md", nos="0 NO", huella=H, revisor="ChatGPT"):
    return f"Dictamen: {d} · REPASO {repaso} · {nos} · huella {huella} · revisor {revisor}"


class Dictamen(unittest.TestCase):
    def ok(self, m):
        self.assertTrue(repaso_sello.evaluar_dictamen(m, H)[0], m)

    def no(self, m):
        self.assertFalse(repaso_sello.evaluar_dictamen(m, H)[0], m)

    def test_favorable_pasa(self):
        self.ok(mensaje(dictamen()))
        self.ok(mensaje(dictamen(d="SI", revisor="codex")))

    def test_sin_dictamen_no(self):
        self.no(mensaje(""))

    def test_dictamen_no_no(self):
        for d in ["NO", "SÍ con reparos", "NO VALE", "sí, pero", ""]:
            self.no(mensaje(dictamen(d=d)))

    def test_con_algun_no_no(self):
        for n in ["1 NO", "2 NO", "0 NO y 1 pendiente", "NO"]:
            self.no(mensaje(dictamen(nos=n)))

    def test_otra_huella_no(self):
        self.no(mensaje(dictamen(huella="c" * 64)))
        self.no(mensaje(dictamen(huella=H[:40])))
        self.no(mensaje(dictamen(huella=H.upper())))

    def test_revisor_que_no_es_chatgpt_no(self):
        for r in ["Sonnet", "Opus", "Fable", "chatgptx", "ChatGPT y Sonnet"]:
            self.no(mensaje(dictamen(revisor=r)))

    def test_redactor_chatgpt_no(self):
        self.no(mensaje(dictamen(), redactor="ChatGPT"))
        self.no(mensaje(dictamen(), redactor="Codex"))

    def test_pareja_explicita_y_conversacion_nueva(self):
        for autor, revisor in [("gpt-6.2-sol", "gpt-6.2-astra"), ("gpt-6.2-astra", "gpt-6.2-sol")]:
            sello = mensaje(dictamen(revisor=revisor), autor, revisor) + "Conversación del revisor: nueva\n"
            self.ok(sello)
            for antiguo, nuevo in [("Redactor: " + autor, "Redactor: " + revisor),
                                   ("Redactor: " + autor, "Redactor: Codex"),
                                   ("Redactor: " + autor, "Redactor: " + autor + " y " + revisor),
                                   ("Redactor: " + autor, "Redactor: " + autor + "-max"),
                                   (" · revisor " + revisor + " · limpio", " · revisor Sonnet · limpio"),
                                   (" · revisor " + revisor + " · limpio", " · revisor ChatGPT · limpio"),
                                   ("Conversación del revisor: nueva", ""),
                                   ("Conversación del revisor: nueva", "Conversación del revisor: misma"),
                                   ("Conversación del revisor: nueva", "Conversación del revisor: nueva\nConversación del revisor: nueva"),
                                   ("0 NO", "1 NO"), (H, "c" * 64)]:
                with self.subTest(autor=autor, cambio=nuevo):
                    self.no(sello.replace(antiguo, nuevo))

    def test_repaso_sin_nombre_o_con_ruta_no(self):
        for r in ["", "repaso.md", "..\\otro_REPASO.md", "a/b_REPASO.md", "x_REPASO_NO_VALE.md"]:
            self.no(mensaje(dictamen(repaso=r)))

    def test_dos_dictamenes_no(self):
        self.no(mensaje(dictamen(d="NO") + "\n" + dictamen()))

    def test_tramos_de_mas_no(self):
        self.no(mensaje(dictamen() + " · 2 NO"))


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=prueba", "-c", "user.email=prueba@example.invalid",
                           "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", "-C", repo, *args],
                          check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


class Rama(unittest.TestCase):
    """Ramas de verdad en un repositorio temporal: lo que tiene que quedarse en rojo y lo que pasa."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        git(self.repo, "init", "-q", "-b", "main")
        self.escribe("index.html", "<p>portada</p>\n")
        self.escribe("estilo.css", "p{}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "inicial")
        git(self.repo, "checkout", "-q", "-b", "claude/prueba")
        self.escribe("guia.html", "<p>guía nueva</p>\n")
        self.escribe("index.html", "<p>portada con enlace</p>\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "guía nueva")
        self.huella = repaso_sello.huella(repaso_sello.manifiesto(self.repo, "main", "HEAD"))

    def tearDown(self):
        self.tmp.cleanup()

    def escribe(self, nombre, texto):
        with open(os.path.join(self.repo, nombre), "w", encoding="utf-8", newline="") as f:
            f.write(texto)

    def sella(self, dictamen_linea, redactor="Fable"):
        padre = git(self.repo, "rev-parse", "HEAD")
        m = (f"Sello: guía nueva\n\nRedactor: {redactor}\nRevisado: {padre}\n"
             f"Repaso: guía v1 · 0 reparos · revisor ChatGPT · limpio\n{dictamen_linea}\n")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", m)

    def codigo(self):
        return repaso_sello.comprobar(self.repo, "main", "HEAD")

    def test_sello_con_repaso_favorable_y_su_huella_pasa(self):
        self.sella(dictamen(huella=self.huella))
        c, lineas = self.codigo()
        self.assertEqual(c, 0, lineas)

    def test_sello_de_dos_modelos_openai_en_una_rama(self):
        padre = git(self.repo, "rev-parse", "HEAD")
        sello = mensaje(dictamen(huella=self.huella, revisor="gpt-6.2-astra"),
                        redactor="gpt-6.2-sol", revisor="gpt-6.2-astra").replace(P, padre)
        git(self.repo, "commit", "-q", "--allow-empty", "-m", sello + "Conversación del revisor: nueva")
        codigo, lineas = self.codigo()
        self.assertEqual(codigo, 0, lineas)

    def test_commit_sin_repaso_rojo(self):
        c, lineas = self.codigo()  # la rama acaba en el commit de trabajo, sin sello
        self.assertEqual(c, 1, lineas)

    def test_sello_sin_linea_de_dictamen_rojo(self):
        self.sella("")
        self.assertEqual(self.codigo()[0], 1)

    def test_repaso_de_otra_huella_rojo(self):
        self.sella(dictamen(huella="c" * 64))
        c, lineas = self.codigo()
        self.assertEqual(c, 1, lineas)
        self.assertIn("otro contenido", " ".join(lineas))

    def test_dictamen_no_rojo(self):
        self.sella(dictamen(d="NO", nos="2 NO", huella=self.huella))
        self.assertEqual(self.codigo()[0], 1)

    def test_cambio_despues_del_repaso_rojo(self):
        # El repaso vio la versión anterior: se cambia una página y se sella con la huella vieja.
        self.escribe("guia.html", "<p>guía nueva, retocada después del repaso</p>\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "retoque")
        self.sella(dictamen(huella=self.huella))
        self.assertEqual(self.codigo()[0], 1)

    def test_sello_que_cambia_ficheros_rojo(self):
        # Todo lo demás en regla (Revisado y la huella del contenido final): solo falla que el sello no es vacío.
        padre = git(self.repo, "rev-parse", "HEAD")
        self.escribe("guia.html", "<p>otra cosa</p>\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "provisional")
        nueva = repaso_sello.huella(repaso_sello.manifiesto(self.repo, "main", "HEAD"))
        git(self.repo, "commit", "-q", "--amend", "-m", f"Sello\n\nRedactor: Fable\nRevisado: {padre}\n"
            f"Repaso: v1 · 0 reparos · revisor ChatGPT · limpio\n{dictamen(huella=nueva)}\n")
        c, lineas = self.codigo()
        self.assertEqual(c, 1, lineas)
        self.assertIn("sello vacío", " ".join(lineas))

    def test_revisado_de_otro_commit_rojo(self):
        git(self.repo, "commit", "-q", "--allow-empty", "-m", f"Sello\n\nRedactor: Fable\nRevisado: {P}\n"
            f"Repaso: v1 · 0 reparos · revisor ChatGPT · limpio\n{dictamen(huella=self.huella)}\n")
        self.assertEqual(self.codigo()[0], 1)

    def test_redactor_chatgpt_rojo(self):
        self.sella(dictamen(huella=self.huella), redactor="ChatGPT")
        self.assertEqual(self.codigo()[0], 1)

    def test_rama_sin_paginas_no_pide_sello(self):
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "checkout", "-q", "-b", "claude/solo-estilo")
        self.escribe("estilo.css", "p{margin:0}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "estilo")
        self.assertEqual(self.codigo()[0], 0)

    def test_recursos_publicos_de_codex_en_las_dos_puertas(self):
        programa = os.path.join(os.path.dirname(__file__), "..", "fusion.py")
        for clase, ruta in (("cambio", "estilo.css"), ("alta", "contacto.js"), ("baja", "index.html")):
            with self.subTest(clase=clase):
                git(self.repo, "checkout", "-q", "-b", "codex/" + clase, "main")
                if clase == "baja":
                    git(self.repo, "rm", "-q", ruta)
                else:
                    self.escribe(ruta, "/* versión */\n")
                    git(self.repo, "add", ruta)
                git(self.repo, "commit", "-q", "-m", "recurso")
                padre = git(self.repo, "rev-parse", "HEAD")
                self.assertEqual(self.codigo()[0], 1)
                huella = repaso_sello.huella(repaso_sello.manifiesto(self.repo, "main", padre))
                for d, h, esperado in (("NO", huella, 1), ("SÍ", "a" * 64, 1), ("SÍ", huella, 0)):
                    git(self.repo, "checkout", "-q", "--detach", padre)
                    m = mensaje(dictamen(d=d, huella=h, revisor="gpt-6.1-terra"),
                                redactor="gpt-6.2-sol", revisor="gpt-6.1-terra").replace(P, padre)
                    git(self.repo, "commit", "-q", "--allow-empty", "-m", m + "Conversación del revisor: nueva")
                    self.assertEqual(self.codigo()[0], esperado)
                    r = subprocess.run([sys.executable, "-I", programa, "--rama", self.repo, "--base", "main"],
                                       capture_output=True)
                    self.assertEqual(r.returncode, esperado, r.stdout + r.stderr)

    def test_la_huella_no_cambia_si_main_avanza_en_otros_ficheros(self):
        git(self.repo, "checkout", "-q", "main")
        self.escribe("otra.html", "<p>otra</p>\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "main avanza")
        git(self.repo, "checkout", "-q", "claude/prueba")
        git(self.repo, "rebase", "-q", "main")
        self.assertEqual(repaso_sello.huella(repaso_sello.manifiesto(self.repo, "main", "HEAD")), self.huella)

    def test_la_huella_depende_del_contenido_y_de_la_ruta(self):
        m = repaso_sello.manifiesto(self.repo, "main", "HEAD")
        self.assertEqual(sorted(l.split(" ", 2)[2].strip() for l in m.splitlines()), ["guia.html", "index.html"])
        self.assertTrue(m.startswith("A "), m)
        self.escribe("guia.html", "<p>guía nueva.</p>\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "un punto")
        self.assertNotEqual(repaso_sello.huella(repaso_sello.manifiesto(self.repo, "main", "HEAD")), self.huella)

    # Rutas que harían la lista ambigua (repaso de ChatGPT del 22/11/2026, B1): árboles hechos con mktree, porque
    # Windows no deja crear esos nombres en disco.
    def rama_con_rutas(self, *rutas):
        def crudo(*args, entrada=b""):
            return subprocess.run(["git", "-c", "user.name=prueba", "-c", "user.email=prueba@example.invalid",
                                   "-C", self.repo, *args], input=entrada, check=True,
                                  capture_output=True).stdout.strip().decode("ascii")
        blob = crudo("hash-object", "-w", "--stdin", entrada=b"<p>contenido</p>\n")
        arbol = crudo("mktree", "-z", entrada=b"".join(b"100644 blob " + blob.encode() + b"\t" + r + b"\0"
                                                       for r in sorted(rutas)))
        commit = crudo("commit-tree", arbol, "-p", git(self.repo, "rev-parse", "main"), "-m", "rutas raras")
        return commit

    def test_ruta_que_no_es_utf8_se_rechaza(self):
        # a\xfe.html y a\xff.html se leerían igual: no puede haber huella para ninguna de las dos.
        for ruta in (b"a\xfe.html", b"a\xff.html"):
            commit = self.rama_con_rutas(ruta)
            with self.assertRaises(repaso_sello.ErrorGit):
                repaso_sello.manifiesto(self.repo, "main", commit)
            with self.assertRaises(repaso_sello.ErrorGit):
                repaso_sello.comprobar(self.repo, "main", commit)

    def test_ruta_con_salto_de_linea_se_rechaza(self):
        # Una sola ruta «a.html\nA <sha256> b.html» daría la misma lista que las dos rutas a.html y b.html.
        suma = "0" * 64
        for ruta in (b"a.html\nA " + suma.encode() + b" b.html", b"a\r.html"):
            commit = self.rama_con_rutas(ruta)
            with self.assertRaises(repaso_sello.ErrorGit):
                repaso_sello.manifiesto(self.repo, "main", commit)

    def test_ruta_rara_sale_1_por_la_orden(self):
        commit = self.rama_con_rutas(b"a\xfe.html")
        programa = os.path.join(os.path.dirname(__file__), "..", "repaso_sello.py")
        r = subprocess.run([sys.executable, "-B", programa, "comprobar", "--repo", self.repo, "--base", "main",
                            "--rev", commit], capture_output=True)
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_rutas_con_tilde_y_espacio_valen(self):
        commit = self.rama_con_rutas("guía de alquiler.html".encode("utf-8"))
        m = repaso_sello.manifiesto(self.repo, "main", commit)
        self.assertIn(" guía de alquiler.html\n", m)


if __name__ == "__main__":
    unittest.main()
