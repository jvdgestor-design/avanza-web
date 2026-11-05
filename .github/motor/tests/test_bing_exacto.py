"""Pruebas de dedup, reserva y aceptación. Todas las respuestas son locales; red prohibida."""
import copy
import datetime as dt
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bing_exacto as be
import indexa


class Respuesta(io.BytesIO):
    def __init__(self, body, status, url):
        super().__init__(body)
        self.status, self.url = status, url

    def geturl(self):
        return self.url


class Exacto(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.datos = self.raiz / "motor"
        self.datos.mkdir()
        self.recibo = self.raiz / "recibo.json"
        self.urls = [indexa.BASE + n + ".html" for n in "abcd"]
        self.html = {u: ("<html>" + u + "</html>\n").encode() for u in self.urls}
        self.huellas = {u: be.digest(b) for u, b in self.html.items()}
        self.hist = be.serializa({"urls": [indexa.BASE + "antigua.html"]})
        self.lote = {"version": 1, "siteUrl": indexa.BASE, "urlList": self.urls, "sha256": self.huellas,
                     "historial": {"archivo": "historial.json", "sha256": be.digest(self.hist)}}
        self.git = {"HEAD:.github/motor/lotes/lote.json": be.serializa(self.lote),
                    "HEAD:.github/motor/lotes/historial.json": self.hist}
        self.git.update({"HEAD:" + indexa.fichero_de(u): b for u, b in self.html.items()})
        self.estado = {"otro": {"preservar": True}, "piezas": {"indexacion": {
            "sha": "sha-anterior", "urls": [indexa.BASE], "gsc": {"preservar": True},
            "yandex": {"preservar": True}, "bing": {"enviadas": {indexa.BASE: "2026-11-01"},
            "enviadas_hoy": {dt.datetime.now(dt.timezone.utc).date().isoformat(): 48},
            "pendientes": [self.urls[0], indexa.BASE + "otra.html"]}}}}
        self.escribe_estado(self.estado)
        self.env = {"BING_API_KEY": "CLAVE-NO-PUBLICAR", "GITHUB_ACTIONS": "true",
                    "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}
        self.peticiones = []
        self.cuota = {"DailyQuota": 4, "MonthlyQuota": 10}
        self.post = (200, {"d": None})
        self.remoto = None
        for p in (mock.patch.object(be, "git_bytes", side_effect=lambda raiz, ref: self.git[ref]),
                  mock.patch.object(indexa, "urls_sitemap", return_value=self.urls),
                  mock.patch.object(socket.socket, "connect", side_effect=AssertionError("Red prohibida"))):
            p.start()
            self.addCleanup(p.stop)

    def escribe_estado(self, estado):
        (self.datos / "estado.json").write_bytes(be.serializa(estado))

    def lee_estado(self):
        return json.loads((self.datos / "estado.json").read_bytes())

    def lee_bing(self):
        return self.lee_estado()["piezas"]["indexacion"]["bing"]

    def abre(self, req, timeout):
        self.peticiones.append((req.get_method(), req.full_url, req.data))
        if req.full_url in self.html:
            return Respuesta(self.html[req.full_url], 200, req.full_url)
        if "GetUrlSubmissionQuota?" in req.full_url:
            return Respuesta(be.serializa({"d": self.cuota}), 200, req.full_url)
        if "SubmitUrlBatch?" in req.full_url:
            if isinstance(self.post, Exception):
                raise self.post
            status, body = self.post
            body = be.serializa(body) if not isinstance(body, bytes) else body
            if status >= 400:
                raise urllib.error.HTTPError(req.full_url, status, "error", {}, io.BytesIO(body))
            return Respuesta(body, status, req.full_url)
        raise AssertionError("Petición no prevista")

    def confirma(self, datos, estado):
        if self.remoto != estado:
            raise be.Bloqueado("Reserva remota diferente")

    def fase(self, fase, env=None):
        return be.ejecuta(fase, self.raiz, self.datos, "lote.json", self.recibo,
                          self.env if env is None else env, self.abre, self.confirma)

    def reserva(self):
        self.assertEqual(self.fase("reservar"), 0)
        self.remoto = copy.deepcopy(self.lee_estado())  # push confirmado simulado
        self.peticiones.clear()

    def posts(self):
        return [p for p in self.peticiones if p[0] == "POST"]

    def test_comprobacion_no_modifica_estado_ni_envia(self):
        original = (self.datos / "estado.json").read_bytes()
        self.assertEqual(self.fase("comprobar"), 0)
        self.assertEqual((self.datos / "estado.json").read_bytes(), original)
        self.assertEqual(self.posts(), [])
        r = json.loads(self.recibo.read_bytes())
        self.assertEqual((r["resultado"], r["cuota"]["DailyQuota"], len(r["web"])),
                         ("comprobado_sin_envio", 4, 4))

    def test_cuota_restante_no_se_resta_dos_veces_y_solo_acepta_cuatro(self):
        self.estado["piezas"]["indexacion"]["bing"]["enviadas_hoy"]["2020-01-01"] = 9
        self.escribe_estado(self.estado)
        self.reserva()
        self.assertEqual(self.fase("enviar"), 0)
        self.assertEqual(len(self.posts()), 1)
        self.assertEqual(json.loads(self.posts()[0][2]), {"siteUrl": indexa.BASE, "urlList": self.urls})
        b = self.lee_bing()
        self.assertTrue(set(self.urls) <= set(b["enviadas"]))
        self.assertEqual(b["huellas_aceptadas"], self.huellas)
        self.assertEqual(b["pendientes"], [indexa.BASE + "otra.html"])
        self.assertEqual(b["enviadas_hoy"], {dt.datetime.now(dt.timezone.utc).date().isoformat(): 52, "2020-01-01": 9})
        actual = self.lee_estado()
        for k in ("sha", "urls", "gsc", "yandex"):
            self.assertEqual(actual["piezas"]["indexacion"][k], self.estado["piezas"]["indexacion"][k])
        self.assertEqual(actual["otro"], self.estado["otro"])
        r = json.loads(self.recibo.read_bytes())
        self.assertEqual(r["respuesta"], {"endpoint": "SubmitUrlBatch", "http": 200,
                         "aceptacion_inequivoca": True, "cuerpo": {"d": None}})
        self.assertEqual(r["aceptadas"], self.urls)
        self.assertNotIn(self.env["BING_API_KEY"], self.recibo.read_text())
        self.assertEqual(self.fase("enviar"), 1)
        self.assertEqual(len(self.posts()), 1)

    def test_cuota_insuficiente_antes_o_despues_de_reservar_cero_post(self):
        self.cuota["DailyQuota"] = 3
        self.assertEqual(self.fase("reservar"), 1)
        self.assertNotIn("lotes_exactos", self.lee_bing())
        self.cuota["DailyQuota"] = 4
        self.reserva()
        self.cuota["MonthlyQuota"] = 0
        self.assertEqual(self.fase("enviar"), 1)
        self.assertEqual(self.posts(), [])
        self.assertEqual(next(iter(self.lee_bing()["lotes_exactos"].values()))["estado"], "reservado")

    def test_cuota_ausente_o_mal_formada_no_se_inventa(self):
        for cuota in ({}, {"DailyQuota": True}, {"DailyQuota": -1}, {"DailyQuota": "10"},
                      {"DailyQuota": 10, "MonthlyQuota": False}):
            with self.subTest(cuota=cuota):
                self.cuota = cuota
                self.assertEqual(self.fase("reservar"), 1)
                self.assertEqual(self.posts(), [])

    def test_duplicados_aceptados_y_reservados_bloquean_sin_red(self):
        for modo in ("enviada", "huella", "reserva"):
            e = copy.deepcopy(self.estado)
            b = e["piezas"]["indexacion"]["bing"]
            if modo == "enviada":
                b["enviadas"][self.urls[1]] = "2026-11-04"
            elif modo == "huella":
                b["huellas_aceptadas"] = {self.urls[1]: self.huellas[self.urls[1]]}
            else:
                b["lotes_exactos"] = {"otro": {"estado": "incierto", "urlList": [self.urls[1]]}}
            self.escribe_estado(e)
            self.assertEqual(self.fase("reservar"), 1)
            self.assertEqual(self.peticiones, [])

    def test_estado_ausente_corrupto_o_contador_invalido_no_se_reinicia(self):
        ruta = self.datos / "estado.json"
        for raw in (b"{", b"{}", b'{"piezas":{},"piezas":{}}'):
            ruta.write_bytes(raw)
            self.assertEqual(self.fase("reservar"), 1)
            self.assertEqual(ruta.read_bytes(), raw)
        ruta.unlink()
        self.assertEqual(self.fase("reservar"), 1)
        self.assertFalse(ruta.exists())
        self.estado["piezas"]["indexacion"]["bing"]["enviadas_hoy"] = {"2026-11-05": "48"}
        self.escribe_estado(self.estado)
        self.assertEqual(self.fase("reservar"), 1)
        self.assertEqual(self.peticiones, [])

    def test_sin_credencial_o_fuera_de_main_no_reserva(self):
        for env in ({}, dict(self.env, GITHUB_REF="refs/heads/otra"), dict(self.env, GITHUB_ACTIONS="false")):
            self.assertEqual(self.fase("reservar", env), 1)
            self.assertNotIn("lotes_exactos", self.lee_bing())
            self.assertEqual(self.posts(), [])

    def test_reserva_repetida_propietario_distinto_y_push_no_confirmado(self):
        self.reserva()
        self.assertEqual(self.fase("reservar"), 1)
        self.assertEqual(self.fase("enviar", dict(self.env, GITHUB_RUN_ATTEMPT="2")), 1)
        self.assertEqual(self.fase("enviar", dict(self.env, GITHUB_RUN_ID="124")), 1)
        self.remoto = None
        self.assertEqual(self.fase("enviar"), 1)
        self.assertEqual(self.posts(), [])

    def test_manifiesto_o_html_alterado_tras_reserva_no_envia(self):
        self.reserva()
        ref = "HEAD:.github/motor/lotes/lote.json"
        self.git[ref] += b" "
        self.assertEqual(self.fase("enviar"), 1)
        self.git[ref] = be.serializa(self.lote)
        self.git["HEAD:a.html"] += b"cambio"
        self.assertEqual(self.fase("enviar"), 1)
        self.assertEqual(self.posts(), [])

    def test_web_distinta_o_redirect_no_se_envia(self):
        self.html[self.urls[0]] += b"cambio"
        self.assertEqual(self.fase("reservar"), 1)
        self.assertEqual(self.posts(), [])
        h = be.SinRedireccion()
        self.assertIsNone(h.redirect_request(None, None, 302, "", {}, "https://otro.example/"))

    def test_respuesta_ambigua_error_y_corte_nunca_se_reintentan(self):
        original = copy.deepcopy(self.estado)
        for respuesta in ((200, {}), (200, {"d": None, "error": "privado"}), (200, b""),
                          (200, b"no JSON"), (302, {"d": None}), (400, {"ErrorCode": 1}),
                          (500, {"Message": "privado"}),
                          urllib.error.URLError("https://api/?apikey=CLAVE-NO-PUBLICAR")):
            with self.subTest(respuesta=respuesta):
                self.escribe_estado(original)
                self.cuota = {"DailyQuota": 4, "MonthlyQuota": 10}
                self.post = respuesta
                self.reserva()
                self.assertEqual(self.fase("enviar"), 1)
                self.assertEqual(len(self.posts()), 1)
                b = self.lee_bing()
                self.assertFalse(set(self.urls).intersection(b["enviadas"]))
                self.assertNotIn("huellas_aceptadas", b)
                self.assertEqual(next(iter(b["lotes_exactos"].values()))["estado"], "incierto")
                self.assertNotIn("CLAVE-NO-PUBLICAR", self.recibo.read_text())
                self.assertNotIn("privado", self.recibo.read_text())
                self.assertEqual(self.fase("enviar"), 1)
                self.assertEqual(len(self.posts()), 1)

    def test_si_falla_guardar_aceptacion_recibo_y_reserva_permiten_conciliar(self):
        self.reserva()
        original = be.guarda
        def guarda(ruta, obj):
            if Path(ruta).name == "estado.json" and any(
                    r["estado"] == "aceptado" for r in obj["piezas"]["indexacion"]["bing"]["lotes_exactos"].values()):
                raise OSError("disco")
            original(ruta, obj)
        with mock.patch.object(be, "guarda", side_effect=guarda):
            self.assertEqual(self.fase("enviar"), 1)
        r = json.loads(self.recibo.read_bytes())
        self.assertEqual((r["resultado"], r["aceptadas"]), ("aceptado", self.urls))
        self.assertEqual(next(iter(self.remoto["piezas"]["indexacion"]["bing"]["lotes_exactos"].values()))["estado"], "reservado")
        self.assertEqual(self.fase("enviar", dict(self.env, GITHUB_RUN_ATTEMPT="2")), 1)
        self.assertEqual(len(self.posts()), 1)

    def test_manifiesto_rechaza_duplicados_ajenos_huellas_historial_y_rutas(self):
        ref = "HEAD:.github/motor/lotes/lote.json"
        for modo in ("duplicada", "otro", "hash", "historial", "historial_hash"):
            lote = copy.deepcopy(self.lote)
            if modo == "duplicada":
                lote["urlList"].append(self.urls[0])
            elif modo == "otro":
                lote["urlList"][0] = "https://otro.example/a.html"
            elif modo == "hash":
                lote["sha256"][self.urls[0]] = "0" * 64
            elif modo == "historial":
                self.git["HEAD:.github/motor/lotes/historial.json"] = be.serializa({"urls": [self.urls[0]]})
                lote["historial"]["sha256"] = be.digest(self.git["HEAD:.github/motor/lotes/historial.json"])
            else:
                lote["historial"]["sha256"] = "0" * 64
            self.git[ref] = be.serializa(lote)
            with self.subTest(modo=modo), self.assertRaises(be.Bloqueado):
                be.carga_lote(self.raiz, "lote.json")
            self.git["HEAD:.github/motor/lotes/historial.json"] = self.hist
        for nombre in ("../lote.json", "/tmp/lote.json", "lote.json;echo", "$(pwd).json"):
            with self.assertRaises(be.Bloqueado):
                be.nombre_lote(nombre)

    def test_verificacion_remota_no_acepta_estado_solo_local(self):
        with mock.patch.object(be.subprocess, "run", return_value=SimpleNamespace(returncode=1)):
            with self.assertRaises(be.Bloqueado):
                be.verifica_remoto(self.datos, self.estado)
        self.git["FETCH_HEAD:motor/estado.json"] = be.serializa({"diferente": True})
        with mock.patch.object(be.subprocess, "run", return_value=SimpleNamespace(returncode=0)):
            with self.assertRaises(be.Bloqueado):
                be.verifica_remoto(self.datos, self.estado)


class Diario(unittest.TestCase):
    def test_diario_no_repite_reserva_ni_cambio_ya_aceptado_y_conserva_ajenos(self):
        u, otra = indexa.BASE + "a.html", indexa.BASE + "otra.html"
        contenido = b"HTML revisado\n"
        for modo in ("reservado", "incierto", "aceptado"):
            with self.subTest(modo=modo):
                posts = []
                def abre(req, timeout):
                    if req.get_method() == "POST":
                        posts.append(json.loads(req.data))
                        d = None
                    elif "GetUrlSubmissionQuota" in req.full_url:
                        d = {"DailyQuota": 100}
                    elif "GetUrlInfo" in req.full_url:
                        d = {"LastCrawledDate": "/Date(1761800000000)/", "HttpStatus": 200}
                    else:
                        d = []
                    return Respuesta(be.serializa({"d": d}), 200, req.full_url)
                hoy = dt.datetime.now(dt.timezone.utc).date()
                b = {"enviadas": {}, "pendientes": [u, otra], "rastreo": {u: {"rastreo": ""}},
                     "lotes_exactos": {"lote": {"estado": modo, "urlList": [u]}}}
                if modo == "aceptado":
                    b.update(enviadas={u: hoy.isoformat()}, huellas_aceptadas={u: be.digest(contenido)})
                c = SimpleNamespace(hoy=hoy, aviso=lambda *args, **kwargs: None, revisada=lambda *a: None)
                with mock.patch.object(indexa.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=contenido)):
                    indexa.bing(c, [u, otra], [u, otra], b, {}, "K", abre, "raiz")
                self.assertEqual(posts, [{"siteUrl": indexa.BASE, "urlList": [otra]}])
                self.assertEqual(b["pendientes"], [])

    def test_cambio_real_posterior_no_se_oculta_por_huella_antigua(self):
        u = indexa.BASE + "a.html"
        b = {"huellas_aceptadas": {u: be.digest(b"anterior")}}
        with mock.patch.object(indexa.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=b"cambiado")):
            self.assertEqual(indexa.bing_protegidas(b, "raiz"), (set(), set()))


class Workflow(unittest.TestCase):
    def test_exacto_exige_pruebas_reserva_remota_y_no_reintenta_post(self):
        workflow = (Path(__file__).resolve().parents[2] / "workflows/vigia.yml").read_text(encoding="utf-8")
        exacto = workflow.split("  bing-exacto:\n", 1)[1]
        self.assertNotIn("continue-on-error", exacto)
        self.assertNotIn("git pull", exacto)
        self.assertNotIn("GSC_KEY", exacto)
        self.assertEqual(exacto.count("--fase enviar"), 1)
        self.assertLess(exacto.index("Pruebas obligatorias"), exacto.index("--fase \"$FASE\""))
        self.assertLess(exacto.index("git -C datos push"), exacto.index("--fase enviar"))
        self.assertIn("steps.bloqueo.outcome == 'success'", exacto)
        self.assertIn("if: always()", exacto)


if __name__ == "__main__":
    unittest.main()
