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
    seis = False

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.datos = self.raiz / "motor"
        self.datos.mkdir()
        self.recibo = self.raiz / "recibo.json"
        self.urls = list(be.URLS_SEIS_AUTORIZADAS if self.seis else be.URLS_AUTORIZADAS)
        self.nombre = be.LOTE_SEIS_AUTORIZADO if self.seis else be.LOTE_AUTORIZADO
        self.manifiesto_attr = "MANIFIESTO_SEIS_AUTORIZADO" if self.seis else "MANIFIESTO_AUTORIZADO"
        self.html = {u: ("<html>" + u + "</html>\n").encode() for u in self.urls}
        self.huellas = {u: be.digest(b) for u, b in self.html.items()}
        self.hist = be.serializa({"urls": [indexa.BASE + "antigua.html"]})
        self.lote = {"version": 1, "siteUrl": indexa.BASE, "urlList": self.urls, "sha256": self.huellas,
                     "historial": {"archivo": "historial.json", "sha256": be.digest(self.hist)}}
        if self.seis:
            self.lote.update(version=2, fuente_commit=be.FUENTE_SEIS_AUTORIZADA)
        self.git = {"HEAD:.github/motor/lotes/" + self.nombre: be.serializa(self.lote),
                    "HEAD:.github/motor/lotes/historial.json": self.hist}
        self.git.update({"HEAD:" + indexa.fichero_de(u): b for u, b in self.html.items()})
        if self.seis:
            sitemap = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
                       ''.join('<url><loc>' + u + '</loc></url>' for u in self.urls) + '</urlset>').encode()
            self.git.update({be.FUENTE_SEIS_AUTORIZADA + ":" + indexa.fichero_de(u): b
                             for u, b in self.html.items()})
            self.git.update({"HEAD:sitemap.xml": sitemap, be.FUENTE_SEIS_AUTORIZADA + ":sitemap.xml": sitemap})
        self.estado = {"otro": {"preservar": True}, "piezas": {"indexacion": {
            "sha": "sha-anterior", "urls": [indexa.BASE], "gsc": {"preservar": True},
            "yandex": {"preservar": True}, "bing": {"enviadas": {indexa.BASE: "2026-11-01"},
            "enviadas_hoy": {dt.datetime.now(dt.timezone.utc).date().isoformat(): 48},
            "pendientes": [self.urls[0], indexa.BASE + "otra.html"]}}}}
        self.escribe_estado(self.estado)
        self.env = {"BING_API_KEY": "CLAVE-NO-PUBLICAR", "GITHUB_ACTIONS": "true",
                    "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
                    "GITHUB_SHA": "a" * 40, "BING_REVISION": "a" * 40}
        self.peticiones = []
        self.cuota = {"DailyQuota": len(self.urls), "MonthlyQuota": 10}
        self.post = (200, {"d": None})
        self.remoto = None
        self.controles_main = 0
        self.controles_remoto = 0
        self.falla_main = self.falla_remoto = None
        # Bytes de fixture deliberadamente distintos de producción; la política real se contrasta aparte.
        for p in (mock.patch.object(be, "git_bytes", side_effect=lambda raiz, ref: self.git[ref]),
                  mock.patch.object(be, self.manifiesto_attr, be.digest(be.serializa(self.lote))),
                  mock.patch.object(indexa, "urls_sitemap", return_value=self.urls),
                  mock.patch.object(be.subprocess, "run", return_value=SimpleNamespace(returncode=0)),
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
        self.controles_remoto += 1
        if self.controles_remoto == self.falla_remoto or self.remoto != estado:
            raise be.Bloqueado("Reserva remota diferente")

    def main_vigente(self, raiz, env):
        self.controles_main += 1
        be.propietario(env)
        if self.controles_main == self.falla_main or env.get("GITHUB_SHA") != env.get("BING_REVISION"):
            raise be.Bloqueado("main diferente")
        return env["GITHUB_SHA"]

    def fase(self, fase, env=None):
        return be.ejecuta(fase, self.raiz, self.datos, self.nombre, self.recibo,
                          self.env if env is None else env, self.abre, self.confirma, self.main_vigente)

    def reserva(self):
        self.assertEqual(self.fase("reservar"), 0)
        self.remoto = copy.deepcopy(self.lee_estado())  # push confirmado simulado
        self.assertEqual(self.fase("armar"), 0)
        self.remoto = copy.deepcopy(self.lee_estado())  # segunda publicación confirmada, antes de POST
        self.peticiones.clear()
        self.controles_main = self.controles_remoto = 0

    def posts(self):
        return [p for p in self.peticiones if p[0] == "POST"]

    def test_comprobacion_no_modifica_estado_ni_envia(self):
        original = (self.datos / "estado.json").read_bytes()
        self.assertEqual(self.fase("comprobar"), 0)
        self.assertEqual((self.datos / "estado.json").read_bytes(), original)
        self.assertEqual(self.posts(), [])
        r = json.loads(self.recibo.read_bytes())
        self.assertEqual((r["resultado"], r["cuota"]["DailyQuota"], len(r["web"])),
                         ("comprobado_sin_envio", len(self.urls), len(self.urls)))

    def test_cuota_restante_no_se_resta_dos_veces_y_solo_acepta_lote_exacto(self):
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
        self.assertEqual(b["enviadas_hoy"], {dt.datetime.now(dt.timezone.utc).date().isoformat(): 48 + len(self.urls), "2020-01-01": 9})
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
        self.cuota["DailyQuota"] = len(self.urls) - 1
        self.assertEqual(self.fase("reservar"), 1)
        self.assertNotIn("lotes_exactos", self.lee_bing())
        self.cuota["DailyQuota"] = len(self.urls)
        self.reserva()
        self.cuota["MonthlyQuota"] = 0
        self.assertEqual(self.fase("enviar"), 1)
        self.assertEqual(self.posts(), [])
        self.assertEqual(next(iter(self.lee_bing()["lotes_exactos"].values()))["estado"], "intento_registrado")

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
        ref = "HEAD:.github/motor/lotes/" + self.nombre
        self.git[ref] += b" "
        self.assertEqual(self.fase("enviar"), 1)
        self.git[ref] = be.serializa(self.lote)
        self.git["HEAD:" + indexa.fichero_de(self.urls[0])] += b"cambio"
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
                          (200, b'{"d":"error","d":null}'), (200, b'{"d":null,"d":null}'),
                          (200, b'{"d":null}\xff'), (200, '{"d":null}'.encode('utf-16')),
                          (200, b"no JSON"), (302, {"d": None}), (400, {"ErrorCode": 1}),
                          (500, {"Message": "privado"}),
                          urllib.error.URLError("https://api/?apikey=CLAVE-NO-PUBLICAR")):
            with self.subTest(respuesta=respuesta):
                self.escribe_estado(original)
                self.cuota = {"DailyQuota": len(self.urls), "MonthlyQuota": 10}
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
        self.assertEqual(next(iter(self.remoto["piezas"]["indexacion"]["bing"]["lotes_exactos"].values()))["estado"], "intento_registrado")
        self.assertEqual(self.fase("enviar", dict(self.env, GITHUB_RUN_ATTEMPT="2")), 1)
        self.assertEqual(len(self.posts()), 1)

    def test_manifiesto_rechaza_duplicados_ajenos_huellas_historial_y_rutas(self):
        ref = "HEAD:.github/motor/lotes/" + self.nombre
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
            with self.subTest(modo=modo), mock.patch.object(be, self.manifiesto_attr, be.digest(self.git[ref])), self.assertRaises(be.Bloqueado):
                be.carga_lote(self.raiz, self.nombre)
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

    def test_main_y_datos_cambiados_en_cada_frontera_impiden_post(self):
        for fuente, fronteras in (("main", 4), ("remoto", 4)):
            for frontera in range(1, fronteras + 1):
                with self.subTest(fuente=fuente, frontera=frontera):
                    self.escribe_estado(self.estado)
                    self.falla_main = self.falla_remoto = None
                    self.reserva()
                    setattr(self, "falla_" + fuente, frontera)
                    self.assertEqual(self.fase("enviar"), 1)
                    self.assertEqual(self.posts(), [])
                    self.assertEqual(json.loads(self.recibo.read_bytes())["post_intentados"], 0)

    def test_marca_no_publicada_y_corte_de_ejecutor_dejan_cuarentena(self):
        self.assertEqual(self.fase("reservar"), 0)
        self.remoto = copy.deepcopy(self.lee_estado())
        self.assertEqual(self.fase("enviar"), 1)  # falta armar
        self.assertEqual(self.fase("armar"), 0)
        self.assertEqual(self.fase("enviar"), 1)  # marca solo local
        self.assertEqual(self.posts(), [])
        self.remoto = copy.deepcopy(self.lee_estado())
        original = self.abre
        def corte(req, timeout):
            if req.get_method() == "POST":
                self.peticiones.append(("POST", req.full_url, req.data))
                raise SystemExit("ejecutor destruido después de iniciar POST")
            return original(req, timeout)
        with mock.patch.object(self, "abre", side_effect=corte), self.assertRaises(SystemExit):
            self.fase("enviar")
        self.assertEqual(len(self.posts()), 1)
        # Solo sobreviven los bytes remotos, sin recibo ni estado local de resultado.
        self.escribe_estado(self.remoto)
        self.assertEqual(self.fase("enviar", dict(self.env, GITHUB_RUN_ATTEMPT="2")), 1)
        self.assertEqual(self.fase("reservar", dict(self.env, GITHUB_RUN_ID="124")), 1)
        self.assertEqual(len(self.posts()), 1)
        self.assertEqual(next(iter(self.lee_bing()["lotes_exactos"].values()))["estado"], "intento_registrado")

    def test_verifica_main_exige_revision_checkout_y_remoto_coincidentes(self):
        ok = SimpleNamespace(returncode=0, stdout="a" * 40 + "\n")
        remoto = SimpleNamespace(returncode=0, stdout="a" * 40 + "\trefs/heads/main\n")
        mal = SimpleNamespace(returncode=0, stdout="b" * 40 + "\n")
        for env, respuestas in ((dict(self.env, BING_REVISION=""), []),
                                 (dict(self.env, GITHUB_SHA="b" * 40), []),
                                 (self.env, [mal]), (self.env, [ok, mal])):
            with mock.patch.object(be.subprocess, "run", side_effect=respuestas), self.assertRaises(be.Bloqueado):
                be.verifica_main(self.raiz, env)
        with mock.patch.object(be.subprocess, "run", side_effect=[ok, remoto]):
            self.assertEqual(be.verifica_main(self.raiz, self.env), "a" * 40)

    def test_otro_manifiesto_y_lista_ampliada_no_tienen_via_ejecutable(self):
        with self.assertRaises(be.Bloqueado):
            be.carga_lote(self.raiz, "otro-lote.json")
        lote = copy.deepcopy(self.lote)
        lote["urlList"].append(indexa.BASE + "quinta.html")
        self.git["HEAD:.github/motor/lotes/" + self.nombre] = be.serializa(lote)
        # Aun si se actualizara solo la huella, sigue fijada la lista exacta del lote.
        with mock.patch.object(be, self.manifiesto_attr, be.digest(be.serializa(lote))), self.assertRaises(be.Bloqueado):
            be.carga_lote(self.raiz, self.nombre)

    def test_cuota_json_duplicada_o_utf8_invalido_impide_reservar(self):
        for raw in (b'{"d":{"DailyQuota":4,"DailyQuota":4}}', b'{"d":{"DailyQuota":4}}\xff'):
            def abre(req, timeout):
                if "GetUrlSubmissionQuota?" in req.full_url:
                    return Respuesta(raw, 200, req.full_url)
                return self.abre(req, timeout)
            with mock.patch.object(be, "red_segura", return_value=abre):
                rc = be.ejecuta("reservar", self.raiz, self.datos, self.nombre, self.recibo, self.env,
                                confirma_main=self.main_vigente)
            self.assertEqual(rc, 1)
            self.assertNotIn("lotes_exactos", self.lee_bing())
            self.assertEqual(self.posts(), [])


class ExactoSeis(Exacto):
    """Repite todos los escenarios de reserva, dedup y fallo con las seis URL exactas."""
    seis = True

    def test_fuente_distinta_ausente_o_fuera_del_historial_bloquea_sin_red(self):
        ref = "HEAD:.github/motor/lotes/" + self.nombre
        for fuente in ("0" * 40, "HEAD", "--help", None):
            lote = dict(self.lote, fuente_commit=fuente)
            self.git[ref] = be.serializa(lote)
            with self.subTest(fuente=fuente), mock.patch.object(be, self.manifiesto_attr, be.digest(self.git[ref])):
                self.assertEqual(self.fase("reservar"), 1)
                self.assertEqual(self.peticiones, [])
        self.git[ref] = be.serializa(self.lote)
        with mock.patch.object(be.subprocess, "run", return_value=SimpleNamespace(returncode=1)):
            self.assertEqual(self.fase("reservar"), 1)
        fuente_html = be.FUENTE_SEIS_AUTORIZADA + ":" + indexa.fichero_de(self.urls[0])
        del self.git[fuente_html]
        self.assertEqual(self.fase("reservar"), 1)
        self.assertEqual(self.peticiones, [])

    def test_sitemap_git_actual_y_fuente_deben_incluir_todas_las_url(self):
        for revision in (be.FUENTE_SEIS_AUTORIZADA, "HEAD"):
            ref = revision + ":sitemap.xml"
            original = self.git[ref]
            for raw in (b"<roto", b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"/>',
                        original.replace(self.urls[-1].encode(), (indexa.BASE + "ajena.html").encode())):
                with self.subTest(revision=revision, raw=raw):
                    self.git[ref] = raw
                    self.assertEqual(self.fase("reservar"), 1)
                    self.assertEqual(self.peticiones, [])
            self.git[ref] = original

    def test_fuente_html_distinta_no_se_oculta_con_head_correcto(self):
        ref = be.FUENTE_SEIS_AUTORIZADA + ":" + indexa.fichero_de(self.urls[0])
        self.git[ref] += b"cambio"
        self.assertEqual(self.fase("reservar"), 1)
        self.assertEqual(self.peticiones, [])

    def test_conserva_lote_anterior_y_acredita_intento_durable_antes_del_unico_post(self):
        bing = self.estado["piezas"]["indexacion"]["bing"]
        anterior = {"estado": "aceptado", "urlList": list(be.URLS_AUTORIZADAS), "respuesta": {"http": 200}}
        bing["lotes_exactos"] = {be.MANIFIESTO_AUTORIZADO: copy.deepcopy(anterior)}
        bing["enviadas"].update({u: "2026-11-05" for u in be.URLS_AUTORIZADAS})
        bing["huellas_aceptadas"] = {u: "b" * 64 for u in be.URLS_AUTORIZADAS}
        self.escribe_estado(self.estado)
        self.reserva()
        original = self.abre
        def comprueba(req, timeout):
            if req.get_method() == "POST":
                huella = be.digest(be.serializa(self.lote))
                remoto = self.remoto["piezas"]["indexacion"]["bing"]["lotes_exactos"][huella]
                self.assertEqual(remoto["estado"], "intento_registrado")
                self.assertEqual(self.lee_bing()["lotes_exactos"][huella]["estado"], "enviando")
                self.assertEqual(json.loads(self.recibo.read_bytes())["post_intentados"], 1)
                self.assertEqual(json.loads(req.data)["urlList"], self.urls)
                self.assertEqual(len(self.urls), 6)
            return original(req, timeout)
        with mock.patch.object(self, "abre", side_effect=comprueba):
            self.assertEqual(self.fase("enviar"), 0)
        self.assertEqual(len(self.posts()), 1)
        final = self.lee_bing()
        self.assertEqual(final["lotes_exactos"][be.MANIFIESTO_AUTORIZADO], anterior)
        for u in be.URLS_AUTORIZADAS:
            self.assertEqual(final["enviadas"][u], "2026-11-05")
            self.assertEqual(final["huellas_aceptadas"][u], "b" * 64)
        self.assertEqual(json.loads(self.recibo.read_bytes())["fuente_commit"], be.FUENTE_SEIS_AUTORIZADA)

    def test_comprobar_solo_seis_get_web_y_un_get_cuota_sin_reservar(self):
        anterior = (self.datos / "estado.json").read_bytes()
        self.assertEqual(self.fase("comprobar"), 0)
        self.assertEqual(len(self.peticiones), 7)
        self.assertTrue(all(p[0] == "GET" for p in self.peticiones))
        self.assertEqual([p[1] for p in self.peticiones[:-1]], self.urls)
        self.assertIn("GetUrlSubmissionQuota?", self.peticiones[-1][1])
        self.assertEqual((self.datos / "estado.json").read_bytes(), anterior)


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
                self.assertEqual(posts, [])
                self.assertEqual(b["pendientes"], [otra] if modo == "aceptado" else [u, otra])

    def test_cambio_real_posterior_no_se_oculta_por_huella_antigua(self):
        u = indexa.BASE + "a.html"
        b = {"huellas_aceptadas": {u: be.digest(b"anterior")}}
        with mock.patch.object(indexa.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=b"cambiado")):
            self.assertEqual(indexa.bing_protegidas(b, "raiz"), (set(), set()))

    def test_git_no_verificable_aplaza_y_conserva_pendiente_sin_declarar_identidad(self):
        u = indexa.BASE + "a.html"
        b = {"huellas_aceptadas": {u: be.digest(b"anterior")}, "pendientes": [u], "enviadas": {}}
        self.assertEqual(indexa.bing_protegidas(b), ({u}, set()))
        with mock.patch.object(indexa.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout=b"")):
            self.assertEqual(indexa.bing_protegidas(b, "raiz"), ({u}, set()))
            self.assertEqual(self.simula(b, git_codigo=1), [])
        self.assertEqual(b["pendientes"], [u])

    def simula(self, b, dias=8, contenido=b"igual", cuota=100, cambios=(), git_codigo=0):
        u = indexa.BASE + "a.html"
        posts = []
        def abre(req, timeout):
            if req.get_method() == "POST":
                posts.append(json.loads(req.data)); d = None
            elif "GetUrlSubmissionQuota" in req.full_url:
                d = {"DailyQuota": cuota}
            elif "GetUrlInfo" in req.full_url:
                d = {}
            else:
                d = []
            return Respuesta(be.serializa({"d": d}), 200, req.full_url)
        hoy = dt.date(2026, 11, 5)
        c = SimpleNamespace(hoy=hoy, aviso=lambda *a, **k: None, revisada=lambda *a: None)
        with mock.patch.object(indexa.subprocess, "run", return_value=SimpleNamespace(returncode=git_codigo, stdout=contenido)):
            indexa.bing(c, [u], list(cambios), b, {}, "SIMULADA", abre, "raiz")
        return posts

    def test_recrawl_6_7_8_dias_huella_rastreo_y_reservas(self):
        u = indexa.BASE + "a.html"
        for dias in (6, 7, 8):
            for igual in (True, False):
                for rastreo in ("sin_rastrear", "rastreada", "error"):
                    for reserva in (None, "reservado", "intento_registrado", "incierto", "aceptado"):
                        with self.subTest(dias=dias, igual=igual, rastreo=rastreo, reserva=reserva):
                            b = {"enviadas": {u: (dt.date(2026,11,5)-dt.timedelta(days=dias)).isoformat()},
                                 "huellas_aceptadas": {u: be.digest(b"igual")},
                                 "rastreo": {u: {"rastreo": "2026-01-01" if rastreo == "rastreada" else "",
                                                 "error": rastreo == "error"}}}
                            if reserva:
                                b["lotes_exactos"] = {"r": {"estado": reserva, "urlList": [u]}}
                            posts = self.simula(b, contenido=b"igual" if igual else b"cambiado")
                            self.assertEqual(posts, [])

    def test_pendiente_sobrevive_reserva_cuota_cero_y_conciliacion(self):
        u = indexa.BASE + "a.html"
        for cambiado in (True, False):
            for modo in ("reservado", "intento_registrado", "incierto"):
                with self.subTest(cambiado=cambiado, modo=modo):
                    b = {"enviadas": {}, "lotes_exactos": {"r": {"estado": modo,"urlList": [u]}}}
                    self.assertEqual(self.simula(b, cuota=0, cambios=[u]), [])
                    self.assertEqual(b["pendientes"], [u])
                    # El SHA global ya puede avanzar: la siguiente ejecución no trae cambios nuevos.
                    self.assertEqual(self.simula(b, cuota=100, cambios=[]), [])
                    self.assertEqual(b["pendientes"], [u])
                    b["lotes_exactos"]["r"]["estado"] = "aceptado"
                    b["huellas_aceptadas"] = {u: be.digest(b"anterior" if cambiado else b"igual")}
                    self.assertEqual(self.simula(b, cambios=[]), [])
                    self.assertEqual(b["pendientes"], [u] if cambiado else [])


class Workflow(unittest.TestCase):
    def test_exacto_exige_pruebas_reserva_remota_y_no_reintenta_post(self):
        workflow = (Path(__file__).resolve().parents[2] / "workflows/vigia.yml").read_text(encoding="utf-8")
        exacto = workflow.split("  bing-exacto:\n", 1)[1]
        self.assertIn("if: github.event_name == 'workflow_dispatch' &&", exacto)
        self.assertIn("if: github.event.inputs.bing_enviar == 'true' && steps.intento.outcome == 'success'", exacto)
        self.assertNotIn("continue-on-error", exacto)
        self.assertNotIn("git pull", exacto)
        self.assertNotIn("GSC_KEY", exacto)
        self.assertEqual(exacto.count("--fase enviar"), 1)
        self.assertLess(exacto.index("Pruebas obligatorias"), exacto.index("--fase \"$FASE\""))
        self.assertLess(exacto.index("git -C datos push"), exacto.index("--fase enviar"))
        self.assertIn("steps.bloqueo.outcome == 'success'", exacto)
        self.assertIn("if: always()", exacto)
        self.assertIn("queue: max", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("BING_REVISION: ${{ github.event.inputs.bing_revision }}", exacto)
        self.assertIn("steps.intento.outcome == 'success'", exacto)
        self.assertLess(exacto.index("--fase armar"), exacto.index("id: intento"))
        self.assertLess(exacto.index("id: intento"), exacto.index("--fase enviar"))

    def test_politica_de_produccion_fija_las_cuatro_url_y_manifiesto(self):
        ruta = Path(__file__).resolve().parents[1] / "lotes" / be.LOTE_AUTORIZADO
        raw = ruta.read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(be.digest(raw), be.MANIFIESTO_AUTORIZADO)
        self.assertEqual(tuple(json.loads(raw)["urlList"]), be.URLS_AUTORIZADAS)
        self.assertEqual(len(be.URLS_AUTORIZADAS), 4)


    def test_segundo_lote_fija_seis_url_fuente_huella_y_guard_del_workflow(self):
        ruta = Path(__file__).resolve().parents[1] / "lotes" / be.LOTE_SEIS_AUTORIZADO
        raw = ruta.read_bytes().replace(b"\r\n", b"\n")
        lote = json.loads(raw)
        self.assertEqual(be.digest(raw), be.MANIFIESTO_SEIS_AUTORIZADO)
        self.assertEqual(tuple(lote["urlList"]), be.URLS_SEIS_AUTORIZADAS)
        self.assertEqual(len(be.URLS_SEIS_AUTORIZADAS), 6)
        self.assertFalse(set(be.URLS_AUTORIZADAS) & set(be.URLS_SEIS_AUTORIZADAS))
        self.assertEqual(lote["version"], 2)
        self.assertEqual(lote["fuente_commit"], be.FUENTE_SEIS_AUTORIZADA)
        self.assertEqual(be.FUENTE_SEIS_AUTORIZADA, "f7401c3d20ebde1f085db3b5f141b80561d8d6a9")
        workflow = (Path(__file__).resolve().parents[2] / "workflows/vigia.yml").read_text(encoding="utf-8")
        guard = workflow.split('case "$LOTE" in\n', 1)[1].split('          esac', 1)[0]
        self.assertEqual(guard.splitlines(), [
            "            " + be.LOTE_AUTORIZADO + "|" + be.LOTE_SEIS_AUTORIZADO + ") ;;",
            '            *) echo "::error::Solo los dos lotes cerrados revisados"; exit 1 ;;'])


if __name__ == "__main__":
    unittest.main()
