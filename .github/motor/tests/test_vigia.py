"""Pruebas del motor sin consumo: cada una debe poder fallar si la pieza deja de avisar.
python3 -B -m unittest discover -s .github/motor/tests -p "test_vigia.py"
"""
import datetime as dt
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import indexa  # noqa: E402
import vigia  # noqa: E402

HOY = dt.date(2026, 10, 30)

FICHA_MALA = """<html><head><script type="application/ld+json">{"@type":"LocalBusiness","name":"Grupo Avanza
Consultores","address":{"streetAddress":"Carrer del Castell, 4"},"telephone":"961 58 56 56",
"url":"https://grupoavanzaconsultores.com"}</script></head><body>Cerrado permanentemente</body></html>"""
FICHA_BUENA = """<html><body><h1>GRUPO AVANZA CONSULTORES</h1><p>46980 Paterna (Valencia)</p>
<p>Tel. +34 614 365 547</p><a href="https://grupoavanzaconsultores.es">web</a></body></html>"""


class Resp(io.BytesIO):
    def __init__(self, texto, status=200):
        super().__init__(texto.encode("utf-8") if isinstance(texto, str) else texto)
        self.status = status
        self.headers = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def red(mapa):
    """urlopen falso: URL → (status, texto). robots.txt ausente = 404 (todo permitido)."""
    llamadas = []

    def abre(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        llamadas.append((getattr(req, "method", "GET"), url, getattr(req, "data", None)))
        for clave, (st, txt) in mapa.items():
            if url.startswith(clave):
                if st >= 400:
                    raise urllib.error.HTTPError(url, st, "x", {}, io.BytesIO(txt.encode()))
                return Resp(txt, st)
        raise urllib.error.HTTPError(url, 404, "no", {}, io.BytesIO(b""))
    abre.llamadas = llamadas
    return abre


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        vigia._robots.clear()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def cola(self, hoy=HOY):
        return vigia.Cola(self.dir, hoy)

    def lineas(self):
        with open(os.path.join(self.dir, "cola-trabajo.md"), encoding="utf-8") as f:
            return [l for l in f.read().splitlines() if l.startswith("- ")]


class Fichas(Base):
    def test_ficha_con_datos_falsos_da_cuatro_avisos(self):
        with open(os.path.join(self.dir, "fichas.txt"), "w") as f:
            f.write("https://dir.example/ficha-mala\n")
        c = self.cola()
        vigia.pieza_fichas(c, self.dir, abre=red({"https://dir.example/ficha-mala": (200, FICHA_MALA)}))
        c.cierra()
        texto = "\n".join(self.lineas())
        for falso in ("Castell 4", "961 58 56 56", "grupoavanzaconsultores.com", "Cerrado permanentemente",
                      "falta el teléfono bueno"):
            self.assertIn(falso, texto)

    def test_ficha_buena_no_avisa(self):
        with open(os.path.join(self.dir, "fichas.txt"), "w") as f:
            f.write("https://dir.example/buena\n")
        c = self.cola()
        vigia.pieza_fichas(c, self.dir, abre=red({"https://dir.example/buena": (200, FICHA_BUENA)}))
        self.assertEqual(c.cierra(), [])

    def test_telefono_de_anna_admitido_por_opcion(self):
        txt = FICHA_BUENA.replace("614 365 547", "642 457 458")
        self.assertIn("falta el teléfono bueno 614 365 547", vigia.problemas_ficha(txt))
        self.assertEqual(vigia.problemas_ficha(txt, ["tel=642457458"]), [])

    def test_ficha_caida_y_robots(self):
        with open(os.path.join(self.dir, "fichas.txt"), "w") as f:
            f.write("https://caida.example/x\nhttps://prohibe.example/x\n")
        c = self.cola()
        vigia.pieza_fichas(c, self.dir, abre=red({
            "https://prohibe.example/robots.txt": (200, "User-agent: *\nDisallow: /\n")}))
        c.cierra()
        texto = "\n".join(self.lineas())
        self.assertIn("FICHA-CAIDA · la ficha ya no existe (HTTP 404)", texto)
        self.assertIn("robots.txt no deja leerla", texto)

    def test_una_peticion_por_sitio_y_dia(self):
        with open(os.path.join(self.dir, "fichas.txt"), "w") as f:
            f.write("https://dir.example/a\nhttps://dir.example/b\n")
        abre = red({"https://dir.example/": (200, FICHA_BUENA)})
        c = self.cola()
        vigia.pieza_fichas(c, self.dir, abre=abre)
        paginas = [u for _, u, _ in abre.llamadas if not u.endswith("robots.txt")]
        self.assertEqual(paginas, ["https://dir.example/a"])
        c.cierra()
        c2 = self.cola(HOY + dt.timedelta(days=1))
        vigia.pieza_fichas(c2, self.dir, abre=abre)
        paginas = [u for _, u, _ in abre.llamadas if not u.endswith("robots.txt")]
        self.assertEqual(paginas[-1], "https://dir.example/b")


class ColaYEstado(Base):
    def test_no_repite_hasta_siete_dias_y_resuelve(self):
        for dia, esperadas in ((0, 1), (1, 0), (6, 0), (7, 1)):
            c = self.cola(HOY + dt.timedelta(days=dia))
            c.revisada("f")
            c.aviso("FICHA", "dato falso: Castell 4", "https://x", fuente="f")
            self.assertEqual(len(c.cierra()), esperadas, f"día +{dia}")
        c = self.cola(HOY + dt.timedelta(days=8))
        c.revisada("f")
        nuevas = c.cierra()
        self.assertEqual(len(nuevas), 1)
        self.assertTrue(nuevas[0].startswith("- RESUELTO"))

    def test_no_resuelve_lo_que_hoy_no_se_ha_mirado(self):
        c = self.cola()
        c.revisada("f")
        c.aviso("FICHA", "x", "https://x", fuente="f")
        c.cierra()
        c = self.cola(HOY + dt.timedelta(days=1))
        self.assertEqual(c.cierra(), [])

    def test_ignorar(self):
        with open(os.path.join(self.dir, "ignorar.txt"), "w") as f:
            f.write("FICHA|https://x|x  # falso positivo\n")
        c = self.cola()
        c.aviso("FICHA", "x", "https://x")
        self.assertEqual(c.cierra(), [])

    def test_formato_de_linea(self):
        c = self.cola()
        c.aviso("CADUCADO", "a · b", "p.html")
        self.assertEqual(c.cierra(), ["- CADUCADO · a - b · p.html · 2026-10-30"])


class Presencia(Base):
    def test_avisa_solo_al_cambiar(self):
        with open(os.path.join(self.dir, "listados.txt"), "w") as f:
            f.write("https://lista.example/paterna\n")
        sin = red({"https://lista.example/paterna": (200, "<li>Otra Gestoría</li>")})
        con = red({"https://lista.example/paterna": (200, "<li>Grupo Avanza Consultores</li>")})
        for dia, abre, esperado in ((0, sin, []), (1, sin, []), (2, con, ["PASAMOS A SALIR"]),
                                    (3, con, []), (4, sin, ["DEJAMOS DE SALIR"])):
            c = self.cola(HOY + dt.timedelta(days=dia))
            vigia.pieza_presencia(c, self.dir, abre=abre)
            nuevas = c.cierra()
            self.assertEqual(len(nuevas), len(esperado), f"día +{dia}: {nuevas}")
            for e in esperado:
                self.assertIn(e, nuevas[0])


class Caducados(Base):
    def test_fecha_vencida_y_proxima(self):
        t = ("La solicitud se presenta hasta el 31 de octubre de 2026 inclusive. "
             "El plazo vence el 15/10/2026. Apply by 20 November 2026. Срок подачи — до 1 ноября 2026 года.")
        h = vigia.caducados_en(t, HOY)
        estados = sorted(e for _, _, e in h)
        self.assertEqual(len(h), 4, h)
        self.assertIn("VENCIDO", estados)
        self.assertIn("vence en 1 días", estados)

    def test_no_avisa_de_fechas_que_no_son_plazos(self):
        t = ("Texto consultado el 24 de octubre de 2026. Updated 27 October 2026. "
             "Desde el 11 de agosto de 2026 se aplica. Si empezaste a cobrar antes del 31 de diciembre de 2014. "
             "El plazo era el 20 de octubre de 2026. Ley 13/1997, de 23 de diciembre. "
             "Se presenta hasta el 30 de junio de 2027.")
        self.assertEqual(vigia.caducados_en(t, HOY), [])

    def test_renta_de_hace_dos_campanas(self):
        self.assertTrue(vigia.caducados_en("Campaña de la Renta 2024: novedades.", HOY))
        self.assertFalse(vigia.caducados_en("Campaña de la Renta 2025: novedades.", HOY))

    def test_pagina_inventada_da_aviso(self):
        raiz = os.path.join(self.dir, "web")
        os.makedirs(raiz)
        with open(os.path.join(raiz, "prueba.html"), "w") as f:
            f.write("<html><body>" + "x " * 1200 + "<p>Ayuda: hasta el 15 de octubre de 2026.</p>"
                    "<script>var f='hasta el 1 de enero de 2026'</script></body></html>")
        c = self.cola()
        vigia.pieza_caducados(c, raiz)
        nuevas = c.cierra()
        self.assertEqual(len(nuevas), 1, nuevas)
        self.assertIn("prueba.html", nuevas[0])


class WebViva(Base):
    def test_caida_es_urgente_y_huella(self):
        raiz = os.path.join(self.dir, "web")
        os.makedirs(raiz)
        with open(os.path.join(raiz, "sitemap.xml"), "w") as f:
            f.write("<urlset/>")
        vigia.time.sleep = lambda s: None
        c = self.cola()
        fallos = vigia.pieza_web(c, raiz, abre=red({vigia.BASE + "sitemap.xml": (200, "<urlset/>")}))
        self.assertTrue(c.urgente)
        self.assertEqual({p for p, _ in fallos}, {"portada", "formulario"})
        ok = red({vigia.BASE + "contacto.html": (200, '<form action="https://script.google.com/macros/s/x">'),
                  vigia.BASE + "sitemap.xml": (200, "<urlset>otro</urlset>"),
                  vigia.BASE: (200, "Grupo Avanza")})
        c = self.cola()
        self.assertEqual(vigia.pieza_web(c, raiz, abre=ok), [])   # 1.ª hora distinta: aún no
        c.cierra()
        c = self.cola()
        self.assertEqual([p for p, _ in vigia.pieza_web(c, raiz, abre=ok)], ["sitemap"])


SITEMAP = """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://grupoavanzaconsultores.es/</loc></url>
<url><loc>https://grupoavanzaconsultores.es/a.html</loc></url>
<url><loc>https://grupoavanzaconsultores.es/b.html</loc></url></urlset>"""


class Indexacion(Base):
    def web(self):
        raiz = os.path.join(self.dir, "web")
        os.makedirs(raiz, exist_ok=True)
        with open(os.path.join(raiz, "sitemap.xml"), "w") as f:
            f.write(SITEMAP)
        for n, t in (("index.html", "Portada"), ("a.html", "Página A"), ("b.html", "Página B")):
            with open(os.path.join(raiz, n), "w") as f:
                f.write(f'<title>{t}</title><meta name="description" content="d {t}">')
        return raiz

    def test_sin_secretos_no_llama_a_nada(self):
        raiz = self.web()
        abre = red({})
        c = self.cola()
        metr, fallos = indexa.ejecuta(c, raiz, entorno={}, abre=abre)
        self.assertEqual((metr, fallos, abre.llamadas), ({}, [], []))

    def test_bing_envia_lo_no_rastreado_y_mide(self):
        raiz = self.web()
        b = indexa.BING
        abre = red({
            b + "GetUrlSubmissionQuota": (200, json.dumps({"d": {"DailyQuota": 2, "MonthlyQuota": 50}})),
            b + "GetUrlInfo?url=https%3A%2F%2Fgrupoavanzaconsultores.es%2Fa.html":
                (200, json.dumps({"d": {"LastCrawledDate": "/Date(-62135596800000)/", "HttpStatus": 0}})),
            b + "GetUrlInfo": (200, json.dumps({"d": {"LastCrawledDate": "/Date(1761800000000-0700)/",
                                                      "HttpStatus": 200}})),
            b + "SubmitUrlBatch": (200, json.dumps({"d": None})),
            b + "GetCrawlStats": (200, json.dumps({"d": [{"Date": "/Date(1761700000000)/", "InIndex": 1},
                                                         {"Date": "/Date(1761800000000)/", "InIndex": 2}]})),
            b + "GetLinkCounts": (200, json.dumps({"d": {"Links": [{"Url": "https://www.expat.com/x", "Count": 1},
                                                                   {"Url": "https://dameunaasesoria.com/y"}]}})),
            b + "GetCrawlIssues": (200, json.dumps({"d": [{"Url": indexa.BASE + "b.html", "HttpCode": 404,
                                                           "Issues": 1}]})),
        })
        c = self.cola()
        metr, fallos = indexa.ejecuta(c, raiz, entorno={"BING_API_KEY": "K"}, abre=abre)
        self.assertEqual(fallos, [])
        envio = [json.loads(d) for m, u, d in abre.llamadas if "SubmitUrlBatch" in u]
        self.assertEqual(envio, [{"siteUrl": indexa.BASE, "urlList": [indexa.BASE + "a.html"]}])
        self.assertEqual((metr["bing_cuota"], metr["bing_en_indice"], metr["bing_dominios"]), (2, 2, 2))
        texto = "\n".join(c.cierra())
        self.assertIn("BING-RASTREO", texto)
        self.assertIn("CONGELADO", texto)   # 2 de 3 URL en índice: más de la mitad

    def test_gsc_noindex_y_candidata_a_titulo(self):
        raiz = self.web()
        respuestas = {
            indexa.GSC_INSPECT: (200, json.dumps({"inspectionResult": {"indexStatusResult": {
                "verdict": "NEUTRAL", "coverageState": "Discovered - currently not indexed"}}})),
            "https://www.googleapis.com/webmasters/v3/sites/": (200, json.dumps({"rows": [
                {"keys": ["asesoria paterna", indexa.BASE + "a.html"], "clicks": 1, "impressions": 80, "position": 12.3},
                {"keys": ["otra", indexa.BASE + "b.html"], "clicks": 0, "impressions": 5, "position": 9}]})),
        }
        c = self.cola()
        c.pieza("titulos")["a.html"] = {"huella": "vieja", "desde": "2026-09-01", "titulo": "x"}
        metr, fallos = indexa.ejecuta(c, raiz, entorno={"GSC_KEY": "{}"}, abre=red(respuestas), token_gsc="T")
        self.assertEqual(fallos, [])
        texto = "\n".join(c.cierra())
        self.assertEqual(metr["gsc_sin_indexar"], 3)
        self.assertIn("GSC-NOINDEX", texto)
        # a.html: el título cambia hoy (huella distinta) → aún no es candidata; b.html: pocas impresiones
        self.assertNotIn("GSC-TITULO", texto)
        c = self.cola(HOY + dt.timedelta(days=29))
        metr, fallos = indexa.ejecuta(c, raiz, entorno={"GSC_KEY": "{}"}, abre=red(respuestas), token_gsc="T")
        self.assertIn("GSC-TITULO · candidata", "\n".join(c.cierra()))

    def test_yandex_recrawl_hasta_la_cuota(self):
        raiz = self.web()
        c = self.cola()
        est = c.pieza("indexacion")
        est["urls"] = [indexa.BASE]   # ejecución anterior: solo la portada → a y b son nuevas
        y = indexa.YANDEX
        abre = red({y + "/user/7/hosts/": (200, "{}"), y + "/user/": (200, "{}"), y + "/user": (200, '{"user_id": 7}')})
        mapa = {
            y + "/user/7/hosts/https%3Agrupoavanzaconsultores.es%3A443/recrawl/quota":
                (200, json.dumps({"daily_quota": 20, "quota_remainder": 1})),
            y + "/user/7/hosts/https%3Agrupoavanzaconsultores.es%3A443/recrawl/queue":
                (202, json.dumps({"task_id": "u", "quota_remainder": 0})),
            y + "/user/7/hosts": (200, json.dumps({"hosts": [{"host_id": "https:grupoavanzaconsultores.es:443",
                                                              "ascii_host_url": "https://grupoavanzaconsultores.es/"}]})),
            y + "/user": (200, json.dumps({"user_id": 7})),
        }
        abre = red(mapa)
        metr, fallos = indexa.ejecuta(c, raiz, entorno={"YANDEX_TOKEN": "T"}, abre=abre)
        self.assertEqual(fallos, [])
        colas = [u for m, u, d in abre.llamadas if u.endswith("/recrawl/queue")]
        self.assertEqual(len(colas), 1)
        self.assertIn("YANDEX-ENVIO", "\n".join(c.cierra()))

    def test_fecha_bing(self):
        self.assertEqual(indexa.fecha_ms("/Date(1761800000000-0700)/"), dt.date(2025, 10, 30))
        self.assertIsNone(indexa.fecha_ms("/Date(-62135596800000)/"))
        self.assertIsNone(indexa.fecha_ms("0001-01-01T00:00:00"))


if __name__ == "__main__":
    unittest.main()
