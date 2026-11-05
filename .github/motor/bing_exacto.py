"""Lote Bing exacto: comprobar, reservar y enviar una sola vez por Actions.

La reserva y la marca de intento deben publicarse en datos-motor ANTES de enviar.
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
import urllib.error
import xml.etree.ElementTree as ET

import indexa

LOTE_AUTORIZADO = "2026-11-05-frde-nuevas.json"
MANIFIESTO_AUTORIZADO = "a6153cf516b6919fc27115f757ed291622fca7f40411bf5e25b7218af595b6bd"
URLS_AUTORIZADAS = tuple(indexa.BASE + n for n in (
    "de-immobilie-spanien-vermieten-nichtansaessig.html",
    "de-kauf-nichtansaessiger-verkaeufer-modelo-211.html",
    "fr-acheter-vendeur-non-resident-modele-211.html",
    "fr-louer-bien-espagne-non-resident.html",
))


# Segundo lote cerrado; el anterior y sus huellas se conservan íntegros.
LOTE_SEIS_AUTORIZADO = "2026-11-05-frde-721-seis.json"
MANIFIESTO_SEIS_AUTORIZADO = "93ca41199dd523626e9102485b2b5918d2ccd3b603604dd7d60ff25d105a5908"
FUENTE_SEIS_AUTORIZADA = "32e613ae0d475cf891dac44def65f5faab399849"
URLS_SEIS_AUTORIZADAS = tuple(indexa.BASE + n for n in (
    "de-erste-steuererklaerung-spanien.html",
    "de-homeoffice-spanien-auslaendischer-arbeitgeber.html",
    "fr-premiere-declaration-revenus-espagne.html",
    "fr-teletravail-espagne-employeur-etranger.html",
    "modelo-721-criptomonedas-extranjero.html",
    "form-721-spain-crypto-abroad.html",
))


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
    if nombre == LOTE_AUTORIZADO:
        manifiesto, autorizadas, version = MANIFIESTO_AUTORIZADO, URLS_AUTORIZADAS, 1
    elif nombre == LOTE_SEIS_AUTORIZADO:
        manifiesto, autorizadas, version = MANIFIESTO_SEIS_AUTORIZADO, URLS_SEIS_AUTORIZADAS, 2
    else:
        raise Bloqueado("Solo están habilitados los dos lotes cerrados revisados")
    raw = git_bytes(raiz, "HEAD:" + nombre_lote(nombre))
    if digest(raw) != manifiesto:
        raise Bloqueado("Ha cambiado el manifiesto autorizado; requiere otra revisión")
    lote = lee_json(raw, "lote")
    campos = {"version", "siteUrl", "urlList", "sha256", "historial"}
    if version == 2:
        campos.add("fuente_commit")
    if not isinstance(lote, dict) or set(lote) != campos:
        raise Bloqueado("Estructura de lote no válida")
    urls, huellas = lote["urlList"], lote["sha256"]
    if type(lote["version"]) is not int or lote["version"] != version or lote["siteUrl"] != indexa.BASE:
        raise Bloqueado("Versión o propiedad incorrectas")
    if not isinstance(urls, list) or tuple(urls) != autorizadas:
        raise Bloqueado("La lista no es exactamente la del lote autorizado")
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
    if version == 2:
        verifica_fuente(raiz, lote)
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


def verifica_fuente(raiz, lote):
    """El lote de seis conserva los bytes y los sitemaps de su commit fuente revisado."""
    fuente = lote["fuente_commit"]
    if fuente != FUENTE_SEIS_AUTORIZADA:
        raise Bloqueado("El commit fuente no es el autorizado para las seis URL")
    p = subprocess.run(["git", "-C", str(raiz), "merge-base", "--is-ancestor", fuente, "HEAD"],
                       capture_output=True)
    if p.returncode:
        raise Bloqueado("El commit fuente no pertenece al historial de esta versión")
    for revision in (fuente, "HEAD"):
        try:
            arbol = ET.fromstring(git_bytes(raiz, revision + ":sitemap.xml"))
        except ET.ParseError:
            raise Bloqueado("Sitemap Git no válido") from None
        sitemap = {(x.text or "").strip() for x in arbol.findall("s:url/s:loc", indexa.NS)}
        if not set(lote["urlList"]) <= sitemap:
            raise Bloqueado("Falta una URL del lote en el sitemap Git de origen o actual")
    for u in lote["urlList"]:
        if digest(git_bytes(raiz, fuente + ":" + indexa.fichero_de(u))) != lote["sha256"][u]:
            raise Bloqueado("La huella HTML no coincide con el commit fuente revisado")


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


def pide_estricto(url, abre, cuerpo=None):
    """Solo JSON UTF-8 inequívoco, también en cuota; nunca registrar cuerpo de error."""
    req = urllib.request.Request(url, data=serializa(cuerpo) if cuerpo is not None else None,
                                 headers={"Accept": "application/json", "Content-Type": "application/json",
                                          "User-Agent": "AvanzaVigia/1.0"})
    try:
        with abre(req, timeout=40) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, None
    # Decodificar explícitamente: json.loads(bytes) también admite UTF-16/32.
    try:
        respuesta = lee_json(raw.decode("utf-8", "strict"), "respuesta Bing")
    except UnicodeError:
        raise Bloqueado("Respuesta Bing no es UTF-8 válido") from None
    return status, respuesta


def cuota(clave, abre):
    import urllib.parse
    st, respuesta = pide_estricto(indexa.BING + "GetUrlSubmissionQuota?" + urllib.parse.urlencode(
        {"siteUrl": indexa.BASE, "apikey": clave}), abre)
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


def verifica_main(raiz, env):
    propietario(env)
    revision = env.get("BING_REVISION", "")
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or env.get("GITHUB_SHA") != revision:
        raise Bloqueado("Falta el commit completo revisado o no coincide con la ejecución")
    p = subprocess.run(["git", "-C", str(raiz), "rev-parse", "HEAD"], capture_output=True, text=True)
    if p.returncode or p.stdout.strip() != revision:
        raise Bloqueado("El checkout difiere del commit revisado")
    p = subprocess.run(["git", "-C", str(raiz), "ls-remote", "--exit-code", "origin", "refs/heads/main"],
                       capture_output=True, text=True)
    if p.returncode or p.stdout.strip() != revision + "\trefs/heads/main":
        raise Bloqueado("main ya no coincide con la versión revisada; cero POST")
    return revision


def ejecuta(fase, raiz, datos, nombre, salida, env=None, abre=None, confirma_remoto=verifica_remoto,
            confirma_main=verifica_main):
    env = os.environ if env is None else env
    recibo = {"entidad": "Grupo Avanza Consultores", "fase": fase, "inicio_utc": ahora(),
              "resultado": "bloqueado", "post_intentados": 0, "aceptadas": []}
    estado = bing = reserva = None
    try:
        clave = (env.get("BING_API_KEY") or "").strip()
        if not clave:
            raise Bloqueado("Falta la credencial existente BING_API_KEY")
        recibo["revision"] = confirma_main(raiz, env)
        abre = abre or red_segura()
        lote, huella = carga_lote(raiz, nombre)
        estado, bing = carga_estado(datos)
        recibo.update(manifiesto_sha256=huella, urlList=lote["urlList"], sha256=lote["sha256"])
        if "fuente_commit" in lote:
            recibo["fuente_commit"] = lote["fuente_commit"]
        sin_duplicados(bing, lote["urlList"], huella if fase in ("armar", "enviar") else None)
        reservas = bing.get("lotes_exactos", {})
        if fase not in ("armar", "enviar") and huella in reservas:
            raise Bloqueado("Este lote ya tiene reserva; no se reejecuta")
        if fase in ("armar", "enviar"):
            reserva = reservas.get(huella)
            esperado = {"propietario": propietario(env), "estado": "reservado" if fase == "armar" else "intento_registrado",
                        "urlList": lote["urlList"], "sha256": lote["sha256"], "revision": recibo["revision"]}
            if not isinstance(reserva, dict) or any(reserva.get(k) != v for k, v in esperado.items()):
                raise Bloqueado("Reserva ajena, alterada o ya utilizada; conciliar sin reenviar")
            confirma_remoto(datos, estado)
        if fase == "armar":
            confirma_main(raiz, env)
            reserva.update(estado="intento_registrado", intento_utc=ahora())
            guarda(Path(datos) / "estado.json", estado)
            recibo["resultado"] = "intento_local_pendiente_de_publicar_sin_post"
            guarda(salida, recibo)
            return 0
        recibo["web"] = publica(lote, abre)
        confirma_main(raiz, env)
        if fase == "enviar":
            confirma_remoto(datos, estado)
        recibo["cuota"] = cuota(clave, abre)
        comprueba_cuota(recibo["cuota"], len(lote["urlList"]))
        confirma_main(raiz, env)
        if fase == "enviar":
            confirma_remoto(datos, estado)
        payload = {"siteUrl": lote["siteUrl"], "urlList": lote["urlList"]}
        recibo["payload"] = payload
        if fase == "comprobar":
            recibo["resultado"] = "comprobado_sin_envio"
        elif fase == "reservar":
            reserva = {"propietario": propietario(env), "estado": "reservado", "urlList": lote["urlList"],
                       "sha256": lote["sha256"], "revision": recibo["revision"],
                       "creada_utc": ahora(), "cuota": recibo["cuota"]}
            bing.setdefault("lotes_exactos", {})[huella] = reserva
            guarda(Path(datos) / "estado.json", estado)
            recibo["resultado"] = "reservado_sin_envio"
        elif fase == "enviar":
            import urllib.parse
            # La marca remota ya existe. El recibo local se escribe antes del último control.
            recibo["resultado"] = "preparado_para_post"
            guarda(salida, recibo)
            confirma_main(raiz, env)
            confirma_remoto(datos, estado)
            # Consumir localmente impide una segunda llamada en este ejecutor. No hay reintentos.
            reserva["estado"] = "enviando"
            guarda(Path(datos) / "estado.json", estado)
            recibo.update(resultado="incierto", post_intentados=1)
            guarda(salida, recibo)
            st, respuesta = pide_estricto(indexa.BING + "SubmitUrlBatch?" + urllib.parse.urlencode({"apikey": clave}),
                                          abre, payload)
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
            reserva.update(estado="aceptado", aceptada_utc=recibo["fin_utc"], respuesta=recibo["respuesta"])
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
    ap.add_argument("--fase", choices=("comprobar", "reservar", "armar", "enviar"), required=True)
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
