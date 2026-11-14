"""Pruebas del aviso de gasto del motor de visibilidad: proyección, fechas límite y no duplicar la línea."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("visibilidad", Path(__file__).resolve().parents[1] / "visibilidad.py")
vis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vis)

URGENTE = ("# Cola de trabajo del motor\n\nCabecera.\n\n## {hoy}\n\n(nada nuevo)\n\n## 2026-11-13\n\n(nada nuevo)\n")


class AvisoGasto(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.motor = self.tmp.name
        self.carpeta = os.path.join(self.motor, "visibilidad")
        os.makedirs(self.carpeta)
        self.p_tope = mock.patch.object(vis, "TOPE_TOKENS", 1500000)
        self.p_tope.start()
        self.p_env = mock.patch.dict(os.environ, {}, clear=False)
        self.p_env.start()
        os.environ.pop("AVANZA_AVISO_FICHERO", None)

    def tearDown(self):
        self.p_env.stop()
        self.p_tope.stop()
        self.tmp.cleanup()

    def prepara(self, hoy, historico, tokens_hoy=0):
        with open(os.path.join(self.motor, "urgente.md"), "w", encoding="utf-8") as f:
            f.write(URGENTE.format(hoy=hoy))
        with open(os.path.join(self.motor, "web.json"), "w", encoding="utf-8") as f:
            json.dump({"avisos": {}, "cola": {hoy: []}, "piezas": {}}, f)
        with mock.patch.object(vis, "ahora", return_value=vis.datetime.strptime(hoy, "%Y-%m-%d")):
            e = vis.Estado(os.path.join(self.carpeta, "estado.json"))
        e.d["historico"] = historico
        e.d["tokens"] = tokens_hoy
        return e

    def urgente(self):
        with open(os.path.join(self.motor, "urgente.md"), encoding="utf-8") as f:
            return f.read()

    def cola(self, hoy):
        with open(os.path.join(self.motor, "web.json"), encoding="utf-8") as f:
            return json.load(f)["cola"][hoy]

    def test_por_encima_baja_tope_y_avisa(self):
        e = self.prepara("2026-11-14", [{"dia": "2026-11-13", "tokens": 1500000, "busquedas": 10}], 100000)
        vis.vigila_gasto(e, self.carpeta)
        self.assertEqual(vis.TOPE_TOKENS, 600000)
        self.assertEqual(self.urgente().count("AVISO GASTO MOTOR"), 1)
        self.assertNotIn("## 2026-11-14\n\n(nada nuevo)", self.urgente())
        self.assertEqual(len(self.cola("2026-11-14")), 1)
        self.assertEqual(e.d["aviso_gasto"], "2026-11-14")

    def test_por_debajo_no_toca_nada(self):
        e = self.prepara("2026-11-14", [{"dia": "2026-11-13", "tokens": 118930, "busquedas": 6}], 188745)
        vis.vigila_gasto(e, self.carpeta)
        self.assertEqual(vis.TOPE_TOKENS, 1500000)
        self.assertNotIn("AVISO GASTO MOTOR", self.urgente())
        self.assertEqual(self.cola("2026-11-14"), [])

    def test_sin_historico(self):
        e = self.prepara("2026-11-14", [], 0)
        vis.vigila_gasto(e, self.carpeta)
        self.assertEqual(vis.TOPE_TOKENS, 1500000)
        e = self.prepara("2026-11-14", [], 1000000)   # solo hoy: 16 US$/día × 32 días > 200
        vis.vigila_gasto(e, self.carpeta)
        self.assertEqual(vis.TOPE_TOKENS, 600000)

    def test_15_12_cuenta_y_16_12_no(self):
        hist = [{"dia": "2026-11-13", "tokens": 12000000, "busquedas": 0}]   # 192 US$ ya gastados
        e = self.prepara("2026-12-15", hist, 1000000)                          # +16 US$ hoy > 200
        vis.vigila_gasto(e, self.carpeta)
        self.assertEqual(vis.TOPE_TOKENS, 600000)
        vis.TOPE_TOKENS = 1500000
        e = self.prepara("2026-12-16", hist, 1000000)
        vis.vigila_gasto(e, self.carpeta)
        self.assertEqual(vis.TOPE_TOKENS, 1500000)
        self.assertNotIn("AVISO GASTO MOTOR", self.urgente())

    def test_no_duplica_el_mismo_dia(self):
        e = self.prepara("2026-11-14", [{"dia": "2026-11-13", "tokens": 1500000, "busquedas": 10}], 100000)
        vis.vigila_gasto(e, self.carpeta)
        e.d["tokens"] = 500000
        vis.vigila_gasto(e, self.carpeta)
        self.assertEqual(vis.TOPE_TOKENS, 600000)
        self.assertEqual(self.urgente().count("AVISO GASTO MOTOR"), 1)
        self.assertEqual(len(self.cola("2026-11-14")), 1)

    def test_aviso_gasto_no_guardado_no_duplica_con_otra_cifra(self):
        e = self.prepara("2026-11-14", [{"dia": "2026-11-13", "tokens": 1500000, "busquedas": 10}], 100000)
        vis.vigila_gasto(e, self.carpeta)
        primera = self.urgente()
        e.d.pop("aviso_gasto")            # el estado.json no llegó a guardarse
        e.d["tokens"] = 900000            # otra cifra en la línea nueva
        vis.vigila_gasto(e, self.carpeta)
        self.assertEqual(self.urgente(), primera)
        self.assertEqual(len(self.cola("2026-11-14")), 1)

    def test_aviso_de_otro_dia_no_bloquea(self):
        e = self.prepara("2026-11-14", [{"dia": "2026-11-13", "tokens": 1500000, "busquedas": 10}], 100000)
        with open(os.path.join(self.motor, "urgente.md"), "a", encoding="utf-8") as f:
            f.write("- AVISO GASTO MOTOR: viejo · 2026-11-13\n")
        vis.vigila_gasto(e, self.carpeta)
        self.assertEqual(self.urgente().count("AVISO GASTO MOTOR"), 2)

    def test_fichero_para_el_flujo_y_reaplicar(self):
        fichero = os.path.join(self.motor, "aviso.txt")
        os.environ["AVANZA_AVISO_FICHERO"] = fichero
        e = self.prepara("2026-11-14", [{"dia": "2026-11-13", "tokens": 1500000, "busquedas": 10}], 100000)
        vis.vigila_gasto(e, self.carpeta)
        hoy, linea = open(fichero, encoding="utf-8").read().split("\n")[:2]
        self.assertEqual(hoy, "2026-11-14")
        self.assertTrue(linea.startswith(vis.AVISO_PREFIJO))
        self.prepara("2026-11-14", [])    # versión remota sin el aviso (vigia la rehízo)
        vis.aplica_aviso(self.motor, hoy, linea)
        vis.aplica_aviso(self.motor, hoy, linea)
        self.assertEqual(self.urgente().count("AVISO GASTO MOTOR"), 1)
        self.assertEqual(len(self.cola("2026-11-14")), 1)


if __name__ == "__main__":
    unittest.main()
