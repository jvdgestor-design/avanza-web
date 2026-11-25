"""Pruebas de claude_plan.py (Claude con el plan, sin API; 25/11/2026) y de su uso en el motor."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

MOTOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOTOR))
import claude_plan  # noqa: E402

spec = importlib.util.spec_from_file_location("visibilidad", MOTOR / "visibilidad.py")
vis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vis)


def flujo(*eventos):
    return "\n".join(json.dumps(e) for e in eventos) + "\n"


BUSQUEDA = flujo(
    {"type": "system", "subtype": "init", "tools": ["WebSearch"]},
    {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "WebSearch",
                                                   "input": {"query": "modelo 210"}}], "stop_reason": None}},
    {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content":
        'Web search results\n\nLinks: [{"title":"AEAT","url":"https://sede.agenciatributaria.gob.es/a.html"},'
        '{"title":"Foro","url":"https://foro.example.com/t/1"}]\n\nResumen'}]}},
    {"type": "assistant", "message": {"content": [{"type": "text", "text":
        "Respuesta. Fuente: [AEAT](https://sede.agenciatributaria.gob.es/a.html) y https://grupoavanzaconsultores.es/x.html."}],
        "stop_reason": None}},
    {"type": "result", "subtype": "success", "is_error": False, "stop_reason": "end_turn", "num_turns": 2,
     "result": "Respuesta.", "usage": {"input_tokens": 4, "output_tokens": 600, "server_tool_use": {"web_search_requests": 0}},
     "modelUsage": {"claude-sonnet-5-5": {"inputTokens": 4, "outputTokens": 600, "cacheReadInputTokens": 1000,
                                          "cacheCreationInputTokens": 3000, "webSearchRequests": 0},
                    "claude-haiku-5-5": {"inputTokens": 15000, "outputTokens": 1100, "webSearchRequests": 1}}})


class Interpreta(unittest.TestCase):
    def test_busqueda_como_la_api(self):
        r = claude_plan.interpreta(BUSQUEDA)
        self.assertEqual(r["stop_reason"], "end_turn")
        self.assertEqual(r["usage"]["server_tool_use"]["web_search_requests"], 1)
        self.assertEqual(r["usage"]["input_tokens"], 15004)
        self.assertEqual(r["usage"]["cache_read_input_tokens"], 1000)
        urls = vis.urls_de(r["content"])
        self.assertEqual(urls, ["https://sede.agenciatributaria.gob.es/a.html", "https://foro.example.com/t/1",
                                "https://grupoavanzaconsultores.es/x.html"])
        self.assertIn("Respuesta.", vis.texto_de(r["content"]))

    def test_error_y_limite(self):
        mal = flujo({"type": "result", "subtype": "success", "is_error": True, "result": "Claude AI usage limit reached"})
        with self.assertRaises(claude_plan.FalloPlan) as cm:
            claude_plan.interpreta(mal)
        self.assertIn("usage limit", str(cm.exception))
        with self.assertRaises(claude_plan.FalloPlan):
            claude_plan.interpreta("no es json\n")

    def test_cortada(self):
        r = claude_plan.interpreta(flujo(
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "VEREDICTO: LIMPIO"}],
                                              "stop_reason": "max_tokens"}},
            {"type": "result", "subtype": "success", "is_error": False, "result": "VEREDICTO: LIMPIO", "usage": {}}))
        self.assertEqual(r["stop_reason"], "max_tokens")
        r = claude_plan.interpreta(flujo({"type": "result", "subtype": "error_max_turns", "is_error": False,
                                          "result": "", "usage": {}}))
        self.assertEqual(r["stop_reason"], "max_turns")


class Seguridad(unittest.TestCase):
    def test_sin_herramientas_y_restringido(self):
        o = claude_plan.orden("claude-sonnet-5-5", "S")
        self.assertEqual(o[o.index("--tools") + 1], "")
        for marca in ("--restricted", "--strict-mcp-config", "--no-session-persistence", "--disable-slash-commands"):
            self.assertIn(marca, o)
        self.assertEqual(o[o.index("--permission-mode") + 1], "dontAsk")
        self.assertNotIn("--allowedTools", o)
        self.assertFalse(any("dangerously" in x or "bypass" in x.lower() for x in o))
        o = claude_plan.orden("m", "S", ("WebSearch",), 6)
        self.assertEqual(o[o.index("--tools") + 1], "WebSearch")
        self.assertEqual(o[o.index("--allowedTools") + 1], "WebSearch")

    def test_entorno_sin_otras_claves(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k", "GH_TOKEN": "g", "GITHUB_TOKEN": "g",
                                          "CLAUDE_CODE_OAUTH_TOKEN": "t"}):
            env = claude_plan._entorno(16000)
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("GH_TOKEN", env)
        self.assertNotIn("GITHUB_TOKEN", env)
        self.assertEqual(env["CLAUDE_CODE_OAUTH_TOKEN"], "t")
        self.assertEqual(env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"], "16000")

    def test_sin_token_no_llama(self):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_OAUTH_TOKEN"}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(claude_plan.subprocess, "run") as run:
            with self.assertRaises(claude_plan.FalloPlan):
                claude_plan.pide("m", "s", "u")
            run.assert_not_called()


class Visibilidad(unittest.TestCase):
    def test_radar_por_el_plan(self):
        estado = vis.Estado("/no/existe/estado.json")
        c = vis.Claude("", estado, plan=True)
        visto = {}

        def falso(modelo, sistema, usuario, **kw):
            visto.update(kw)
            return claude_plan.interpreta(BUSQUEDA)
        with mock.patch.object(claude_plan, "pide", falso):
            bloques = c.pide("claude-sonnet-5-5", "s", "u", herramientas=[
                {"type": "web_search_20250305", "name": "web_search", "max_uses": 4}], busquedas=4)
        self.assertEqual(visto["herramientas"], ("WebSearch",))
        self.assertEqual(visto["max_turnos"], 6)
        self.assertEqual(estado.d["busquedas"], 1)
        self.assertGreater(estado.d["tokens"], 15000)
        self.assertIn("https://foro.example.com/t/1", vis.urls_de(bloques))

    def test_limite_del_plan_para_el_motor(self):
        c = vis.Claude("", vis.Estado("/no/existe/estado.json"), plan=True)
        with mock.patch.object(claude_plan, "pide", side_effect=claude_plan.FalloPlan("Claude AI usage limit reached")):
            with self.assertRaises(vis.SinSaldo):
                c.pide("m", "s", "u")
        with mock.patch.object(claude_plan, "pide", side_effect=claude_plan.FalloPlan("success: algo raro")):
            with self.assertRaises(RuntimeError):
                c.pide("m", "s", "u")


if __name__ == "__main__":
    unittest.main()
