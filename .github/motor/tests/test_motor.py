import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import sys
import tempfile
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import revisor
import pulso
import boe_revisor


def respuesta(veredicto="SIGUE", parada="end_turn", entrada=10):
    return {"content": [{"type": "text", "text": f"VEREDICTO: {veredicto}\nInforme"}],
            "stop_reason": parada, "usage": {"input_tokens": entrada, "output_tokens": 4}}


class Revision(unittest.TestCase):
    def ejecutar(self, respuestas=None, clave="", prueba=False, sucio=False, cambia_head=False):
        self.destino = Path(tempfile.mkdtemp(prefix="avanza-test-"))

        lecturas_head = 0
        def git(*args):
            nonlocal lecturas_head
            if args[:2] == ("rev-parse", "HEAD"):
                lecturas_head += 1
                return ("c" if cambia_head and lecturas_head > 1 else "a") * 40
            if args[0] in ("rev-parse", "merge-base"):
                return "b" * 40
            if args[0] == "status":
                return " M a.html" if sucio else ""
            if "--name-only" in args:
                return "a.html\0b.html\0"
            return "diff completo"

        with patch.object(revisor, "git", side_effect=git), \
             patch.object(revisor, "planificar", return_value=[(["a.html"], "uno"), (["b.html"], "dos")]), \
             patch.object(revisor, "llamar", side_effect=respuestas or []) as api, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": clave}, clear=True), \
             contextlib.redirect_stdout(io.StringIO()):
            codigo = revisor.main(["--informe", str(self.destino)] + (["--prueba"] if prueba else []))
        return codigo, json.loads((self.destino / "revision_de-chatgpt.json").read_text(encoding="utf-8")), api.call_count

    def test_sin_clave_falla_y_deja_todo_pendiente(self):
        codigo, r, llamadas = self.ejecutar()
        self.assertEqual((codigo, llamadas, r["estado"]), (1, 0, "INCOMPLETO"))
        self.assertEqual(r["pendientes"], ["a.html", "b.html"])

    def test_plan_no_es_dictamen(self):
        codigo, r, llamadas = self.ejecutar(prueba=True)
        self.assertEqual((codigo, llamadas, r["estado"], r["revision_valida"]), (0, 0, "SOLO_PLAN", False))

    def test_sigue_solo_con_todos_los_lotes(self):
        codigo, r, llamadas = self.ejecutar([(respuesta(), ""), (respuesta(), "")], "ficticia")
        self.assertEqual((codigo, llamadas, r["estado"], r["pendientes"]), (0, 2, "SIGUE", []))
        self.assertTrue(r["revision_valida"])

    def test_max_tokens_con_sigue_no_vale_y_cuenta_consumo(self):
        codigo, r, _ = self.ejecutar([(respuesta(), ""), (respuesta(parada="max_tokens", entrada=17), "")], "ficticia")
        self.assertEqual(codigo, 1)
        self.assertEqual(r["estado"], "INCOMPLETO")
        self.assertEqual(r["pendientes"], ["b.html"])
        self.assertEqual(r["uso"]["input_tokens"], 27)

    def test_bloqueo_no_es_exito(self):
        codigo, r, _ = self.ejecutar([(respuesta("BLOQUEA"), ""), (respuesta(), "")], "ficticia")
        self.assertEqual((codigo, r["estado"]), (1, "BLOQUEA"))

    def test_error_api_no_se_presenta_como_revision(self):
        codigo, r, llamadas = self.ejecutar([(None, "red")], "ficticia")
        self.assertEqual((codigo, llamadas, r["revision_valida"]), (1, 1, False))

    def test_arbol_sucio_no_llama_api(self):
        codigo, r, llamadas = self.ejecutar(clave="ficticia", sucio=True)
        self.assertEqual((codigo, llamadas, r["estado"]), (1, 0, "INCOMPLETO"))

    def test_veredicto_tiene_que_ser_primera_linea_exacta(self):
        for texto in ("Hola\nVEREDICTO: SIGUE", "VEREDICTO: SIGUE extra", "**VEREDICTO: SIGUE**", ""):
            r = respuesta()
            r["content"][0]["text"] = texto
            self.assertEqual(revisor.valida_respuesta(r)[1], "INCOMPLETO")

    def test_cambio_de_head_durante_revision_invalida_dictamen(self):
        codigo, r, llamadas = self.ejecutar([(respuesta(), ""), (respuesta(), "")], "ficticia", cambia_head=True)
        self.assertEqual((codigo, llamadas, r["revision_valida"]), (1, 2, False))
        self.assertEqual(r["pendientes"], ["a.html", "b.html"])

    def test_hreflang_admite_orden_y_comillas_sin_salir_del_dominio(self):
        carpeta = Path(tempfile.mkdtemp(prefix="avanza-hreflang-"))
        (carpeta / "a.html").write_text("<link href='b.html' hreflang='en'><link hreflang='ru' href='https://otro.es/c.html'>", encoding="utf-8")
        (carpeta / "b.html").write_text("pareja", encoding="utf-8")
        anterior = Path.cwd()
        try:
            os.chdir(carpeta)
            self.assertEqual(revisor.parejas("a.html"), ["b.html"])
        finally:
            os.chdir(anterior)

    def test_stop_sequence_inesperado_no_vale(self):
        self.assertEqual(revisor.valida_respuesta(respuesta(parada="stop_sequence"))[1], "INCOMPLETO")

    def test_lote_grande_se_divide_sin_omitir_archivos(self):
        with patch.object(revisor, "git", return_value="diff"), \
             patch.object(revisor, "armar", side_effect=lambda lote, *_: "X" * len(lote) * 10):
            r = revisor.planificar(["a.html", "b.html", "sitemap.xml"], "base", 2, 15)
        self.assertEqual([lote for lote, _ in r], [["a.html"], ["b.html"], ["sitemap.xml"]])

    def test_pagina_indivisible_excesiva_bloquea_no_recorta(self):
        with patch.object(revisor, "git", return_value="diff"), patch.object(revisor, "armar", return_value="X" * 30):
            with self.assertRaises(revisor.EncargoExcesivo):
                revisor.planificar(["a.html"], "base", 2, 15)

    def test_diff_excesivo_tambien_bloquea(self):
        with patch.object(revisor, "git", return_value="X" * 30), patch.object(revisor, "armar", return_value="corto"):
            with self.assertRaises(revisor.EncargoExcesivo):
                revisor.planificar(["a.html"], "base", max_diff=15)


class BOE(unittest.TestCase):
    def test_no_paga_revision_si_falta_texto_por_recorte(self):
        for recortado, tope, prueba in ((True, 400000, False), (False, 1, False), (True, 400000, True)):
            with self.subTest(recortado=recortado, tope=tope, prueba=prueba):
                with patch.object(sys, "argv", ["boe_revisor.py", "--norma", "prueba"] + (["--prueba"] if prueba else [])), \
                     patch.object(boe_revisor, "ZoneInfo", return_value=dt.timezone.utc), \
                     patch.object(boe_revisor, "canonica", return_value=("Ley prueba", "BOE-PRUEBA")), \
                     patch.object(boe_revisor.boe, "ficha", return_value={"titulo": "Ley prueba", "actualizacion": "20261020"}), \
                     patch.object(boe_revisor.boe, "es_esa_norma", return_value=True), \
                     patch.object(boe_revisor.boe, "citas_de", return_value=[]), \
                     patch.object(boe_revisor, "nombres_de", return_value=(["Ley prueba"], ["a.html"])), \
                     patch.object(boe_revisor.boe, "pide", return_value={"data": {"bloque": [{"titulo": "Artículo 1.", "id": "a1"}]}}), \
                     patch.object(boe_revisor, "citas_en_pagina", return_value=[("Ley prueba art. 1", ["1"])]), \
                     patch.object(boe_revisor, "texto_bloque", return_value=("Texto oficial", recortado)), \
                     patch.object(boe_revisor, "TOPE_ENCARGO", tope), \
                     patch.object(boe_revisor, "llama") as api, \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(boe_revisor.main(), 1)
                    api.assert_not_called()


class Huellas(unittest.TestCase):
    def test_normaliza_solo_conversion_de_git_acreditada(self):
        raiz = Path(tempfile.mkdtemp(prefix="avanza-eol-"))
        datos = b"contenido\r\ncon cambio\r\n"
        (raiz / "pagina.html").write_bytes(datos)
        for estado, esperado in (("i/lf    w/crlf attr/\tpagina.html", datos.replace(b"\r\n", b"\n")),
                                 ("i/crlf w/crlf attr/\tpagina.html", datos),
                                 ("i/-text w/-text attr/\tpagina.html", datos), ("", datos)):
            with self.subTest(estado=estado), patch.object(pulso.salud.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=estado)):
                self.assertEqual(pulso.salud.contenido_publicable(raiz, "pagina.html"), esperado)

    def test_error_git_no_oculta_diferencias(self):
        raiz = Path(tempfile.mkdtemp(prefix="avanza-eol-"))
        (raiz / "pagina.html").write_bytes(b"cambio real\r\n")
        with patch.object(pulso.salud.subprocess, "run", side_effect=OSError("sin git")):
            self.assertEqual(pulso.salud.contenido_publicable(raiz, "pagina.html"), b"cambio real\r\n")


class Pulso(unittest.TestCase):
    def test_ciclos_y_aisladas(self):
        g = {"a": {"b"}, "b": {"a", "c"}, "c": set(), "aislada": set()}
        self.assertEqual(pulso.distancias(g, "a"), {"a": 0, "b": 1, "c": 2})

    def test_sin_gsc_no_inventa_oportunidades(self):
        estado, filas = pulso.oportunidades_gsc(None, set(), dt.date(2026, 10, 20))
        self.assertEqual((estado["estado"], filas), ("NO_MEDIDO", []))

    def gsc(self, **cambios):
        u = pulso.salud.BASE
        d = {"siteUrl": u, "startDate": "2026-09-20", "endDate": "2026-10-17",
             "dimensions": ["page"], "dataState": "final", "rows": [{"page": u, "impressions": 20, "position": 5}]}
        d.update(cambios)
        p = Path(tempfile.mkdtemp(prefix="avanza-gsc-test-")) / "datos.json"
        p.write_text(json.dumps(d), encoding="utf-8")
        return pulso.oportunidades_gsc(p, {u}, dt.date(2026, 10, 20))

    def test_umbral_gsc_exactamente_20_y_5(self):
        self.assertEqual(len(self.gsc()[1]), 1)

    def test_datos_no_asentados_y_propiedad_ajena_se_rechazan(self):
        for cambio in ({"endDate": "2026-10-20"}, {"siteUrl": "https://otro.es/"}, {"dataState": "all"},
                       {"dimensions": ["query"]}, {"endDate": "2026-09-01"}):
            with self.assertRaises(ValueError):
                self.gsc(**cambio)

    def test_nan_y_url_ajena_se_rechazan(self):
        for fila in ({"page": pulso.salud.BASE, "impressions": float("nan"), "position": 8},
                     {"page": "https://otro.es/", "impressions": 100, "position": 8}):
            with self.assertRaises(ValueError):
                self.gsc(rows=[fila])

    def test_diagnostico_integra_urls_y_detecta_pagina_aislada(self):
        raiz = Path(tempfile.mkdtemp(prefix="avanza-grafo-"))
        paginas = {}
        for fichero, enlaces in (("index.html", ["contacto.html"]), ("contacto.html", []), ("aislada.html", [])):
            (raiz / fichero).write_text("<html></html>", encoding="utf-8")
            paginas[fichero] = SimpleNamespace(url=pulso.salud.BASE + ("" if fichero == "index.html" else fichero),
                                              lang="es", hrefs=enlaces, forms=fichero == "contacto.html")
        with patch.object(pulso.salud, "comprueba_repo", return_value=([p.url for p in paginas.values()], paginas)):
            r = pulso.diagnosticar(raiz)
        aislada = next(p for p in r["paginas"] if p["url"].endswith("aislada.html"))
        self.assertIsNone(aislada["pasos_portada"])
        self.assertIsNone(aislada["pasos_contacto"])
        self.assertEqual(len([t for t in r["cola"] if t["prioridad"] == 1]), 2)
        portada = next(p for p in r["paginas"] if p["url"] == pulso.salud.BASE)
        self.assertEqual(portada["pasos_contacto"], 1)

    def test_informe_no_puede_guardarse_en_web(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            pulso.main(["--salida", str(Path.cwd() / "informe-privado")])


if __name__ == "__main__":
    unittest.main()
