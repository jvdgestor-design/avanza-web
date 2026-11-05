"""Lote Bing exacto: comprobar, reservar y enviar una sola vez por Actions.

La reserva debe estar publicada en datos-motor ANTES de llamar a enviar.
No reintenta POST ni libera reservas: un resultado incierto exige conciliación.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request

import indexa


class Bloqueado(Exception):
    pass


def ahora():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(datos):
    return hashlib.sha256(datos).hexdigest()


def serializa(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def guarda(ruta, obj):
    ruta = Path(ruta)
    temporal = ruta.with_name(ruta.name + ".tmp")
    with temporal.open("wb") as f:
        f.write(serializa(obj))
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporal, ruta)


def git_bytes(raiz, referencia):
    p = subprocess.run(["git", "-C", str(raiz), "show", referencia], capture_output=True)
    if p.returncode:
        raise Bloqueado("No se puede leer la versión Git requerida")
    return p.stdout


def lee_json(datos, origen):
    def pares(items):
        resultado = {}
        for k, v in items:
            if k in resultado:
                raise ValueError("clave duplicada")
            resultado[k] = v
        return resultado
    try:
        return json.loads(datos, object_pairs_hook=pares)
    except (ValueError, UnicodeError):
        raise Bloqueado(f"JSON inválido: {origen}") from None


def nombre_lote(nombre):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.json", nombre):
        raise Bloqueado("Nombre de lote no válido")
    return ".github/motor/lotes/" + nombre


def carga_lote(raiz, nombre):
    raw = git_bytes(raiz, "HEAD:" + nombre_lote(nombre))
    lote = lee_json(raw, "lote")
    if not isinstance(lote, dict) or set(lote) != {"version", "siteUrl", "urlList", "sha256", "historial"}:
        raise Bloqueado("Estructura de lote no válida")
    urls, huellas = lote["urlList"], lote["sha256"]
    if type(lote["version"]) is not int or lote["version"] != 1 or lote["siteUrl"] != indexa.BASE:
        raise Bloqueado("Versión o propiedad incorrectas")
    if not isinstance(urls, list) or not 1 <= len(urls) <= 500 or not all(isinstance(u, str) for u in urls):
        raise Bloqueado("La lista exacta debe contener entre 1 y 500 URL")
    if len(set(urls)) != len(urls) or not isinstance(huellas, dict) or set(huellas) != set(urls):
        raise Bloqueado("URL repetida o huellas incompletas")
    sitemap = set(indexa.urls_sitemap(raiz))
    for u in urls:
        if not re.fullmatch(re.escape(indexa.BASE) + r"[a-z0-9][a-z0-9-]*\.html", u) or u not in sitemap:
            raise Bloqueado("URL fuera de la propiedad o del sitemap")
        if not isinstance(huellas[u], str) or not re.fullmatch(r"[0-9a-f]{64}", huellas[u]):
            raise Bloqueado("Huella no válida")
        if digest(git_bytes(raiz, "HEAD:" + indexa.fichero_de(u))) != huellas[u]:
            raise Bloqueado("El contenido Git ya no coincide con el lote revisado")
    h = lote["historial"]
    if not isinstance(h, dict) or set(h) != {"archivo", "sha256"}:
        raise Bloqueado("Falta el historial de deduplicación")
    hraw = git_bytes(raiz, "HEAD:" + nombre_lote(h["archivo"]))
    if digest(hraw) != h["sha256"]:
        raise Bloqueado("Ha cambiado la huella del historial")
    historial = lee_json(hraw, "historial")
    if not isinstance(historial, dict) or not isinstance(historial.get("urls"), list):
        raise Bloqueado("Historial no válido")
    if any(u in historial["urls"] for u in urls):
        raise Bloqueado("El lote incluye URL ya enviadas en el historial acreditado")
    return lote, digest(raw)


def carga_estado(datos):
    ruta = Path(datos) / "estado.json"
    try:
        estado = lee_json(ruta.read_bytes(), "estado existente")
        bing = estado["piezas"]["indexacion"]["bing"]
        if not isinstance(bing, dict) or not isinstance(bing["enviadas"], dict):
            raise ValueError()
        for clave, tipo in (("pendientes", list), ("enviadas_hoy", dict),
                            ("huellas_aceptadas", dict), ("lotes_exactos", dict)):
            if clave in bing and not isinstance(bing[clave], tipo):
                raise ValueError()
        if not isinstance(estado["piezas"], dict):
            raise ValueError()
        if any(type(n) is not int or n < 0 for n in bing.get("enviadas_hoy", {}).values()):
            raise ValueError()
    except (OSError, KeyError, TypeError, ValueError):
        raise Bloqueado("Falta el estado Bing existente o está mal formado; no se reinicia") from None
    return estado, bing


def sin_duplicados(bing, urls, propio=None):
    if any(u in bing["enviadas"] or u in bing.get("huellas_aceptadas", {}) for u in urls):
        raise Bloqueado("Hay URL ya aceptadas por Bing")
    for clave, reserva in bing.get("lotes_exactos", {}).items():
        if not isinstance(reserva, dict) or not isinstance(reserva.get("urlList"), list):
            raise Bloqueado("Reserva previa mal formada")
        if clave != propio and set(urls).intersection(reserva["urlList"]):
            raise Bloqueado("Hay URL con reserva previa; conciliar sin reenviar")


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def red_segura():
    return urllib.request.build_opener(SinRedireccion()).open


def cuota(clave, abre):
    import urllib.parse
    st, respuesta = indexa.pide(indexa.BING + "GetUrlSubmissionQuota?" + urllib.parse.urlencode(
        {"siteUrl": indexa.BASE, "apikey": clave}), abre=abre)
    d = respuesta.get("d") if isinstance(respuesta, dict) else None
    if st != 200 or not isinstance(d, dict):
        raise Bloqueado(f"Cuota Bing no verificable (HTTP {st})")
    diaria, mensual = d.get("DailyQuota"), d.get("MonthlyQuota")
    if type(diaria) is not int or diaria < 0 or (mensual is not None and (type(mensual) is not int or mensual < 0)):
        raise Bloqueado("Cuota Bing incompleta o no válida")
    # Bing documenta DailyQuota como saldo restante, no volver a restar enviadas_hoy.
    # https://blogs.bing.com/webmaster/2019/11/Accessing-Bing-webmaster-tools-api-using-cURL/
    return {"DailyQuota": diaria, "MonthlyQuota": mensual, "consultada_utc": ahora()}


def comprueba_cuota(q, numero):
    valores = [q["DailyQuota"]] + ([q["MonthlyQuota"]] if q["MonthlyQuota"] is not None else [])
    if min(valores) < numero:
        raise Bloqueado("Cuota insuficiente para el lote completo; cero POST y sin sustituciones")


def publica(lote, abre):
    pruebas = []
    for u in lote["urlList"]:
        req = urllib.request.Request(u, headers={"User-Agent": "AvanzaVigia/1.0"})
        with abre(req, timeout=40) as r:
            contenido = r.read()
            status = getattr(r, "status", None)
            final = r.geturl()
        if status != 200 or final != u or digest(contenido) != lote["sha256"][u]:
            raise Bloqueado("La web pública no coincide con el HTML revisado (200 y SHA-256)")
        pruebas.append({"url": u, "http": status, "sha256": digest(contenido), "consultada_utc": ahora()})
    return pruebas


def propietario(env):
    if env.get("GITHUB_ACTIONS") != "true" or env.get("GITHUB_REF") != "refs/heads/main":
        raise Bloqueado("Reservar/enviar solo se permite desde el workflow publicado en main")
    run, intento = env.get("GITHUB_RUN_ID", ""), env.get("GITHUB_RUN_ATTEMPT", "")
    if not run.isdigit() or not intento.isdigit():
        raise Bloqueado("Falta la identidad de ejecución")
    return run + "." + intento


def verifica_remoto(datos, estado):
    repo = Path(datos).parent
    p = subprocess.run(["git", "-C", str(repo), "fetch", "--quiet", "origin", "datos-motor"], capture_output=True)
    if p.returncode:
        raise Bloqueado("No se confirma la reserva publicada; cero POST")
    remoto = lee_json(git_bytes(repo, "FETCH_HEAD:motor/estado.json"), "reserva remota")
    if remoto != estado:
        raise Bloqueado("La reserva publicada difiere del estado local; cero POST")


def ejecuta(fase, raiz, datos, nombre, salida, env=None, abre=None, confirma_remoto=verifica_remoto):
    env = os.environ if env is None else env
    recibo = {"entidad": "Grupo Avanza Consultores", "fase": fase, "inicio_utc": ahora(),
              "resultado": "bloqueado", "post_intentados": 0, "aceptadas": []}
    estado = bing = reserva = None
    try:
        clave = (env.get("BING_API_KEY") or "").strip()
        if not clave:
            raise Bloqueado("Falta la credencial existente BING_API_KEY")
        abre = abre or red_segura()
        lote, huella = carga_lote(raiz, nombre)
        estado, bing = carga_estado(datos)
        recibo.update(manifiesto_sha256=huella, urlList=lote["urlList"], sha256=lote["sha256"])
        sin_duplicados(bing, lote["urlList"], huella if fase == "enviar" else None)
        reservas = bing.get("lotes_exactos", {})
        if fase != "enviar" and huella in reservas:
            raise Bloqueado("Este lote ya tiene reserva; no se reejecuta")
        if fase == "enviar":
            reserva = reservas.get(huella)
            esperado = {"propietario": propietario(env), "estado": "reservado", "urlList": lote["urlList"],
                        "sha256": lote["sha256"]}
            if not isinstance(reserva, dict) or any(reserva.get(k) != v for k, v in esperado.items()):
                raise Bloqueado("Reserva ajena, alterada o ya utilizada; conciliar sin reenviar")
            confirma_remoto(datos, estado)
        recibo["web"] = publica(lote, abre)
        recibo["cuota"] = cuota(clave, abre)
        comprueba_cuota(recibo["cuota"], len(lote["urlList"]))
        payload = {"siteUrl": lote["siteUrl"], "urlList": lote["urlList"]}
        recibo["payload"] = payload
        if fase == "comprobar":
            recibo["resultado"] = "comprobado_sin_envio"
        elif fase == "reservar":
            reserva = {"propietario": propietario(env), "estado": "reservado", "urlList": lote["urlList"],
                       "sha256": lote["sha256"], "creada_utc": ahora(), "cuota": recibo["cuota"]}
            bing.setdefault("lotes_exactos", {})[huella] = reserva
            guarda(Path(datos) / "estado.json", estado)
            recibo["resultado"] = "reservado_sin_envio"
        elif fase == "enviar":
            import urllib.parse
            # Se deja huella local antes de POST: nunca se relanza automáticamente.
            reserva["estado"] = "enviando"
            guarda(Path(datos) / "estado.json", estado)
            recibo.update(resultado="incierto", post_intentados=1)
            guarda(salida, recibo)
            st, respuesta = indexa.pide(indexa.BING + "SubmitUrlBatch?" + urllib.parse.urlencode({"apikey": clave}),
                                       "POST", payload, abre=abre)
            recibo["respuesta"] = {"endpoint": "SubmitUrlBatch", "http": st,
                                    "aceptacion_inequivoca": st == 200 and respuesta == {"d": None}}
            if st != 200 or respuesta != {"d": None}:
                raise Bloqueado(f"Respuesta Bing no acredita aceptación (HTTP {st}); no reintentar")
            # El recibo se conserva ANTES del estado: permite conciliar si guardar/push falla.
            recibo.update(resultado="aceptado", aceptadas=list(lote["urlList"]), fin_utc=ahora())
            recibo["respuesta"]["cuerpo"] = {"d": None}
            guarda(salida, recibo)
            fecha = dt.datetime.now(dt.timezone.utc).date().isoformat()
            bing["enviadas"].update({u: fecha for u in lote["urlList"]})
            bing.setdefault("huellas_aceptadas", {}).update(lote["sha256"])
            bing["pendientes"] = [u for u in bing.get("pendientes", []) if u not in lote["urlList"]]
            contador = bing.get("enviadas_hoy", {}).get(fecha, 0)
            bing.setdefault("enviadas_hoy", {})[fecha] = contador + len(lote["urlList"])
            reserva.update(estado="aceptado", aceptada_utc=recibo["fin_utc"])
            guarda(Path(datos) / "estado.json", estado)
        else:
            raise Bloqueado("Fase desconocida")
        recibo["fin_utc"] = ahora()
        guarda(salida, recibo)
        return 0
    except Exception as e:
        # Nunca str de errores de transporte: puede contener apikey o datos de respuesta.
        recibo["error"] = str(e) if isinstance(e, Bloqueado) else "Fallo controlado: " + type(e).__name__
        if recibo["post_intentados"] and recibo["resultado"] != "aceptado" and reserva is not None:
            reserva["estado"] = "incierto"
            try:
                guarda(Path(datos) / "estado.json", estado)
            except OSError:
                pass  # La reserva ya publicada sigue bloqueando el lote.
        recibo["fin_utc"] = ahora()
        guarda(salida, recibo)
        return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fase", choices=("comprobar", "reservar", "enviar"), required=True)
    ap.add_argument("--raiz", default=".")
    ap.add_argument("--datos", default="datos/motor")
    ap.add_argument("--lote", required=True, help="Nombre del manifiesto ya publicado bajo .github/motor/lotes/")
    ap.add_argument("--salida", default="bing-exacto-recibo.json")
    a = ap.parse_args()
    resultado = ejecuta(a.fase, a.raiz, a.datos, a.lote, a.salida)
    print("Bing exacto: recibo guardado; " + ("comprobación correcta" if resultado == 0 else "detenido"))
    return resultado


if __name__ == "__main__":
    raise SystemExit(main())
