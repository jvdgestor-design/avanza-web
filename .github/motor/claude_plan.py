#!/usr/bin/env python3
"""Claude con el plan de Claude de Jose, sin créditos de API (25/11/2026, orden de Jose: la API no se recarga).

Llama a Claude Code en modo no interactivo (`claude -p`) con el secreto CLAUDE_CODE_OAUTH_TOKEN (sale de
`claude setup-token`) y devuelve un diccionario con la misma forma que la respuesta de /v1/messages
(«content», «stop_reason», «usage»), para que el motor de visibilidad, la revisión del motor y la revisión contra el
BOE sigan leyendo la respuesta como antes.

Seguridad: Claude Code corre sin ninguna herramienta (salvo WebSearch cuando se pide, para el radar), en modo
restringido (sin ejecutar código, sin WebFetch, sin ajustes de usuario ni de proyecto, sin MCP), sin guardar la
sesión y en una carpeta vacía; el texto va por la entrada estándar y nunca como orden. Al programa solo le llega
el token del plan: la clave de API, los tokens de GitHub y la URL base se quitan de su entorno.
"""
import json
import os
import re
import subprocess
import tempfile
import time

CLI = os.environ.get("AVANZA_CLAUDE_CLI", "claude")
QUITAR = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "GH_TOKEN", "GITHUB_TOKEN",
          "ACTIONS_RUNTIME_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL")
RX_URL_BUSQUEDA = re.compile(r'"url"\s*:\s*"(https?://[^"\s]+)"')
RX_URL_TEXTO = re.compile(r"https?://[^\s<>()\[\]\"'«»`]+")
PASAJERO = ("overloaded", "529", "500", "502", "503", "internal server error", "timed out", "econnreset",
            "socket hang up", "network")


class FalloPlan(RuntimeError):
    """Claude Code no ha dado una respuesta utilizable (sin token, límite de uso del plan, error)."""


def hay_token():
    return bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip())


def _entorno(max_tokens):
    env = {k: v for k, v in os.environ.items() if k not in QUITAR}
    env.update({"CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(max_tokens), "DISABLE_AUTOUPDATER": "1",
                "DISABLE_TELEMETRY": "1", "DISABLE_ERROR_REPORTING": "1", "CLAUDE_CODE_DISABLE_TERMINAL_TITLE": "1"})
    return env


def orden(modelo, sistema, herramientas=(), max_turnos=1):
    """La línea de órdenes de una llamada (aparte, para las pruebas)."""
    herr = ",".join(herramientas)
    args = [CLI, "-p", "--output-format", "stream-json", "--verbose", "--model", modelo, "--system-prompt", sistema,
            "--tools", herr, "--restricted", "--strict-mcp-config", "--no-session-persistence",
            "--disable-slash-commands", "--permission-mode", "dontAsk", "--permission-prompts", "none",
            "--max-turns", str(max_turnos)]
    if herr:
        args += ["--allowedTools", herr]
    return args


def _urls_de_resultado(contenido):
    if isinstance(contenido, list):
        contenido = " ".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in contenido)
    return list(dict.fromkeys(RX_URL_BUSQUEDA.findall(str(contenido or ""))))


def interpreta(salida):
    """Convierte la salida stream-json de `claude -p` en {content, stop_reason, usage, num_turns}.

    Los resultados de WebSearch pasan a bloques «web_search_tool_result» y las URL que el texto cita, a «citations»,
    como en la API, para que urls_de() del radar siga sacando las mismas fuentes."""
    bloques, ids_busqueda, stops, final = [], set(), [], None
    for linea in salida.splitlines():
        linea = linea.strip()
        if not linea.startswith("{"):
            continue
        try:
            ev = json.loads(linea)
        except ValueError:
            continue
        tipo = ev.get("type")
        if tipo == "assistant":
            msg = ev.get("message") or {}
            if msg.get("stop_reason"):
                stops.append(msg["stop_reason"])
            for b in msg.get("content") or []:
                if b.get("type") == "text" and b.get("text"):
                    urls = list(dict.fromkeys(u.rstrip(".,;:") for u in RX_URL_TEXTO.findall(b["text"])))
                    bloques.append({"type": "text", "text": b["text"], "citations": [{"url": u} for u in urls]})
                elif b.get("type") == "tool_use" and b.get("name") == "WebSearch":
                    ids_busqueda.add(b.get("id"))
        elif tipo == "user":
            for b in (ev.get("message") or {}).get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in ids_busqueda:
                    bloques.append({"type": "web_search_tool_result", "content": [
                        {"type": "web_search_result", "url": u} for u in _urls_de_resultado(b.get("content"))]})
        elif tipo == "result":
            final = ev
    if final is None:
        raise FalloPlan("Claude Code no ha devuelto resultado")
    texto_final = str(final.get("result") or "")
    if final.get("is_error") or final.get("subtype") not in ("success", "error_max_turns"):
        raise FalloPlan(f"Claude Code: {final.get('subtype')}: {texto_final[:300]}")
    if final.get("subtype") == "error_max_turns":
        stop = "max_turns"
    elif "max_tokens" in stops or final.get("stop_reason") == "max_tokens" \
            or re.search(r"exceeded the \d+ output token maximum", texto_final):
        stop = "max_tokens"
    else:
        stop = final.get("stop_reason") or "end_turn"
    if not any(b["type"] == "text" for b in bloques) and texto_final:
        bloques.append({"type": "text", "text": texto_final, "citations": []})
    uso = dict(final.get("usage") or {})
    # WebSearch la hace por dentro otro modelo: el tope cuenta los tokens de todos (modelUsage), no solo los del principal
    por_modelo = [m for m in (final.get("modelUsage") or {}).values() if isinstance(m, dict)]
    if por_modelo:
        for clave, campo in (("input_tokens", "inputTokens"), ("output_tokens", "outputTokens"),
                             ("cache_creation_input_tokens", "cacheCreationInputTokens"),
                             ("cache_read_input_tokens", "cacheReadInputTokens")):
            uso[clave] = sum(int(m.get(campo, 0) or 0) for m in por_modelo)
    servidor = dict(uso.get("server_tool_use") or {})
    servidor["web_search_requests"] = max(int(servidor.get("web_search_requests", 0) or 0), len(ids_busqueda),
                                          sum(int(m.get("webSearchRequests", 0) or 0) for m in por_modelo))
    uso["server_tool_use"] = servidor
    return {"content": bloques, "stop_reason": stop, "usage": uso, "num_turns": final.get("num_turns")}


def pide(modelo, sistema, usuario, max_tokens=8000, herramientas=(), max_turnos=1, timeout=900, reintento=True):
    """Una petición a Claude por el plan. Lanza FalloPlan si no hay respuesta utilizable."""
    if not hay_token():
        raise FalloPlan("falta el secreto CLAUDE_CODE_OAUTH_TOKEN (plan de Claude)")
    msg = ""
    for intento in range(2 if reintento else 1):
        with tempfile.TemporaryDirectory(prefix="avanza-claude-") as vacia:
            try:
                r = subprocess.run(orden(modelo, sistema, herramientas, max_turnos), input=usuario.encode("utf-8"),
                                   capture_output=True, cwd=vacia, env=_entorno(max_tokens), timeout=timeout)
            except subprocess.TimeoutExpired:
                raise FalloPlan(f"Claude Code no contestó en {timeout} s")
            except OSError as e:
                raise FalloPlan(f"no se pudo arrancar Claude Code ({type(e).__name__})")
        salida = r.stdout.decode("utf-8", "replace")
        try:
            return interpreta(salida)
        except FalloPlan as e:
            error = (r.stderr.decode("utf-8", "replace").strip().splitlines() or [""])[-1][:200]
            msg = f"{e}" + (f" · {error}" if error else "") + f" (salida {r.returncode})"
        if intento == 0 and reintento and any(p in msg.lower() for p in PASAJERO):
            time.sleep(30)
            continue
        break
    raise FalloPlan(msg)
