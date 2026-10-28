"""Pruebas de la vigilancia: un cambio o una fuente incompleta nunca producen verde."""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("boe", Path(__file__).resolve().parents[1] / "boe.py")
boe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boe)
IDENT = "BOE-A-2023-25416"
XML = b'''<documento fecha_actualizacion="20251220175601"><metadatos>
<identificador>BOE-A-2023-25416</identificador>
<titulo>Orden HFP/1338/2023, de 13 de diciembre, modelo 151.</titulo>
<departamento>Ministerio de Hacienda</departamento>
<estatus_derogacion>N</estatus_derogacion><vigencia_agotada>N</vigencia_agotada>
<judicialmente_anulada>N</judicialmente_anulada></metadatos>
<texto><p>Articulo 1. Se aprueba el modelo 151.</p></texto>
<analisis><referencias_posteriores/></analisis></documento>'''


class FichaXML(unittest.TestCase):
    def ficha(self, xml=XML):
        with mock.patch.object(boe, "pide", return_value=xml):
            return boe.ficha(IDENT)

    def test_xml_oficial_proporciona_identidad_fecha_y_huella(self):
        fi = self.ficha()
        self.assertEqual(fi["actualizacion"], "20251220175601")
        self.assertEqual(len(fi["huella"]), 64)
        self.assertEqual(fi["fuente"], "https://www.boe.es/diario_boe/xml.php?id=" + IDENT)
        self.assertFalse(fi["derogada"])

    def test_huella_incluye_texto_y_referencias_posteriores_sin_cambiar_fecha(self):
        inicial = self.ficha()["huella"]
        for xml in (XML.replace(b"Se aprueba", b"Se modifica"),
                    XML.replace(b"<referencias_posteriores/>", b"<referencias_posteriores><p>Correccion posterior</p></referencias_posteriores>"),
                    XML.replace(b"<estatus_derogacion>N", b"<estatus_derogacion>S")):
            with self.subTest(xml=xml):
                self.assertNotEqual(self.ficha(xml)["huella"], inicial)

    def test_identidad_o_fuente_incompleta_fallan(self):
        for xml in (b"<html>Error</html>", b"<documento>",
                    XML.replace(IDENT.encode(), b"BOE-A-2023-1"),
                    XML.replace(b"modelo 151", b"modelo 999"),
                    XML.replace(b"Ministerio de Hacienda", b"Comunidad de Madrid"),
                    XML.replace(b'fecha_actualizacion="20251220175601"', b'fecha_actualizacion=""'),
                    XML.replace(b"<texto><p>Articulo 1. Se aprueba el modelo 151.</p></texto>", b"<texto/>"),
                    XML.replace(b"<analisis><referencias_posteriores/></analisis>", b""),
                    XML.replace(b"<vigencia_agotada>N</vigencia_agotada>", b"")):
            with self.subTest(xml=xml), self.assertRaises(LookupError):
                self.ficha(xml)

    def test_documento_desconocido_no_pasa_silenciosamente_a_xml(self):
        with mock.patch.object(boe, "pide", side_effect=LookupError("404")) as pedir:
            with self.assertRaises(LookupError):
                boe.ficha("BOE-A-2026-999999")
            self.assertIn("legislacion-consolidada", pedir.call_args.args[0])

    def test_se_conserva_la_ficha_consolidada(self):
        with mock.patch.object(boe, "pide", return_value={"titulo": "Ley 5/2022, asimetrias", "fecha_actualizacion": "20251220T151301Z"}):
            fi = boe.ficha("BOE-A-2022-3712")
        self.assertNotIn("huella", fi)
        self.assertEqual(fi["actualizacion"], "20251220T151301Z")


class FlujoVigilancia(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="avanza_boe_prueba_")
        self.addCleanup(self.tmp.cleanup)
        self.estado = str(Path(self.tmp.name) / "estado.json")

    def ejecutar(self, xml=XML, extra=(), citas=None, error=None):
        salida = io.StringIO()
        with mock.patch.object(sys, "argv", ["boe.py", "--estado", self.estado, *extra]), \
             mock.patch.object(boe, "citas_de", return_value=citas or {IDENT: {"beckham-law-spain-special-tax-regime.html"}}), \
             mock.patch.object(boe, "pide", return_value=xml, side_effect=error), \
             mock.patch.object(boe, "resuelve", return_value=(None, "sin identificar")), \
             mock.patch.dict(boe.os.environ, {"GITHUB_ACTIONS": "", "GITHUB_STEP_SUMMARY": ""}), \
             contextlib.redirect_stdout(salida), self.assertRaises(SystemExit) as fin:
            boe.main()
        return fin.exception.code, salida.getvalue()

    def test_cambio_de_texto_sigue_rojo_hasta_revision_explicita(self):
        self.assertEqual(self.ejecutar(extra=("--inicial",))[0], 0)
        self.assertEqual(self.ejecutar()[0], 0)
        cambio = XML.replace(b"Se aprueba", b"Se modifica")
        for _ in range(2):
            codigo, salida = self.ejecutar(cambio)
            self.assertEqual(codigo, 1)
            self.assertIn("1 cambiadas sin revisar", salida)
            self.assertIn("beckham-law-spain-special-tax-regime.html", salida)
        self.assertEqual(self.ejecutar(cambio, ("--revisado", IDENT))[0], 0)
        self.assertEqual(self.ejecutar(cambio)[0], 0)

    def test_nueva_fecha_sigue_rojo_hasta_revision(self):
        self.ejecutar(extra=("--inicial",))
        cambio = XML.replace(b"20251220175601", b"20261024120000")
        self.assertEqual(self.ejecutar(cambio)[0], 1)
        self.assertEqual(self.ejecutar(cambio)[0], 1)
        self.assertEqual(self.ejecutar(cambio, ("--revisado", "todo"))[0], 0)

    def test_red_o_xml_incompleto_dan_error_con_estado_anterior_intacto(self):
        self.ejecutar(extra=("--inicial",))
        anterior = Path(self.estado).read_text(encoding="utf-8")
        for opciones in ({"error": boe.SinRespuesta("fallo de red")}, {"xml": b"<html>Error</html>"}):
            codigo, salida = self.ejecutar(**opciones)
            self.assertEqual(codigo, 1)
            self.assertIn("1 errores", salida)
            self.assertEqual(Path(self.estado).read_text(encoding="utf-8"), anterior)

    def test_derogacion_agotamiento_o_anulacion_siempre_dan_error(self):
        self.ejecutar(extra=("--inicial",))
        for indicador in ("estatus_derogacion", "vigencia_agotada", "judicialmente_anulada"):
            xml = XML.replace(("<" + indicador + ">N").encode(), ("<" + indicador + ">S").encode())
            codigo, salida = self.ejecutar(xml, ("--revisado", "todo"))
            self.assertEqual(codigo, 1)
            self.assertIn("1 errores", salida)

    def test_perder_estado_no_da_verde(self):
        for _ in range(2):
            codigo, salida = self.ejecutar()
            self.assertEqual(codigo, 1)
            self.assertIn("ESTADO PERDIDO", salida)
            self.assertFalse(Path(self.estado).exists())
        self.assertEqual(self.ejecutar(extra=("--inicial",))[0], 0)
        self.assertEqual(self.ejecutar()[0], 0)

    def test_pendientes_desde_no_se_limpia_solo(self):
        self.ejecutar(extra=("--inicial",))
        self.assertEqual(self.ejecutar(extra=("--pendientes-desde", "20250101"))[0], 1)
        self.assertEqual(self.ejecutar()[0], 1)
        self.assertEqual(self.ejecutar(extra=("--revisado", IDENT))[0], 0)

    def test_alias_no_puede_saltar_la_comprobacion_de_identidad(self):
        with mock.patch.dict(boe.SEMILLA, {"Ley 5/2022": IDENT}):
            codigo, salida = self.ejecutar(extra=("--inicial",), citas={IDENT: {"a.html"}, "Ley 5/2022": {"b.html"}})
        self.assertEqual(codigo, 1)
        self.assertIn("Ley 5/2022", salida)


    def test_licencia_identifica_las_tres_leyes_sin_ocultar_emisor_incorrecto(self):
        casos = (
            ("Ley 14/2010", "BOE-A-2010-20014", "Ley 14/2010, de 3 de diciembre, de espectáculos públicos, actividades recreativas y establecimientos públicos.", "Comunitat Valenciana"),
            ("Ley 6/2014", "BOE-A-2014-9626", "Ley 6/2014, de 25 de julio, de Prevención, Calidad y Control ambiental de Actividades en la Comunitat Valenciana.", "Comunitat Valenciana"),
            ("Ley 7/1985", "BOE-A-1985-5392", "Ley 7/1985, de 2 de abril, Reguladora de las Bases del Régimen Local.", "Jefatura del Estado"),
        )
        for norma, ident, titulo, departamento in casos:
            for emisor, esperado in ((departamento, 0), ("Otro emisor", 1)):
                with self.subTest(norma=norma, emisor=emisor):
                    ficha = {"titulo": titulo, "fecha_actualizacion": "20261028T080000Z",
                             "departamento": emisor, "estatus_derogacion": "N", "vigencia_agotada": "N"}
                    codigo, salida = self.ejecutar(xml=ficha, extra=("--inicial",),
                                                  citas={norma: {"licencia-de-actividad-cambio-de-titularidad.html"}})
                    self.assertEqual(codigo, esperado)
                    self.assertEqual(boe.SEMILLA[norma], ident)
                    if esperado:
                        self.assertIn("1 errores", salida)


class Transporte(unittest.TestCase):
    def setUp(self):
        self.anterior = boe.FALLOS_RED[0]
        boe.FALLOS_RED[0] = 0
        self.addCleanup(boe.FALLOS_RED.__setitem__, 0, self.anterior)

    def test_fallo_de_red_no_se_interpreta_como_documento_inexistente(self):
        with mock.patch.object(boe.urllib.request, "urlopen", side_effect=TimeoutError("sin respuesta")) as abrir, \
             mock.patch.object(boe.time, "sleep"):
            with self.assertRaises(boe.SinRespuesta):
                boe.pide("https://www.boe.es/diario_boe/xml.php?id=" + IDENT, formato="xml")
        self.assertEqual(abrir.call_count, 3)
        self.assertEqual(boe.FALLOS_RED[0], 1)

    def test_404_es_error_y_no_una_excepcion_excluida(self):
        error = boe.urllib.error.HTTPError("https://www.boe.es/", 404, "No encontrado", {}, None)
        with mock.patch.object(boe.urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(LookupError):
                boe.pide("https://www.boe.es/diario_boe/xml.php?id=" + IDENT, formato="xml")


class IdentificacionNormas(unittest.TestCase):
    def test_ley_52022_se_desambigua_por_materia(self):
        buena = "Ley 5/2022, de 9 de marzo, en relacion con las asimetr\u00edas h\u00edbridas."
        self.assertTrue(boe.es_esa_norma("Ley 5/2022", buena))
        self.assertFalse(boe.es_esa_norma("Ley 5/2022", "Ley 5/2022, de la Comunidad de Madrid, de tributos cedidos."))

    def test_licencia_rechaza_leyes_homonimas_de_otra_materia(self):
        for norma, titulo in (
            ("Ley 14/2010", "Ley 14/2010, de 5 de julio, sobre las infraestructuras y los servicios de información geográfica en España."),
            ("Ley 6/2014", "Ley 6/2014, de 7 de abril, por la que se modifica el texto articulado de la Ley sobre Tráfico, Circulación de Vehículos a Motor y Seguridad Vial."),
            ("Ley 7/1985", "Ley 7/1985, de 14 de mayo, de ordenación de la función pública."),
        ):
            with self.subTest(norma=norma):
                self.assertFalse(boe.es_esa_norma(norma, titulo))

    def test_extranjeria_es_organica_y_no_ley_ordinaria(self):
        titulo = "Ley Org\u00e1nica 4/2000, de 11 de enero, sobre extranjeros."
        self.assertTrue(boe.es_esa_norma("Ley Org\u00e1nica 4/2000", titulo))
        self.assertFalse(boe.es_esa_norma("Ley 4/2000", titulo))
        self.assertEqual(boe.SEMILLA["Ley Org\u00e1nica 4/2000"], "BOE-A-2000-544")
        self.assertEqual([m.group(1) for m in boe.RX_NORMA.finditer(titulo)], ["Ley Org\u00e1nica"])


if __name__ == "__main__":
    unittest.main()
