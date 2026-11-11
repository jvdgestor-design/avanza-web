"""Comprueba que buscadores y rastreadores de IA reciben la web entera (sin IA, sin dependencias).

Para cada user-agent pide unas páginas clave y exige: código 200, el mismo HTML que recibe un
navegador normal y el texto del <h1> dentro del HTML (sin ejecutar JavaScript). Mira también
a qué servidores apunta el dominio (GitHub Pages o un cortafuegos delante, como Cloudflare).
Salida: una línea ::notice:: o ::error:: por comprobación (se leen como anotaciones del run).
"""
import hashlib
import re
import socket
import sys
import urllib.error
import urllib.request

UAS = {
    "Navegador": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Bingbot": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "OAI-SearchBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot",
    "ChatGPT-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot",
    "GPTBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.1; +https://openai.com/gptbot",
    "PerplexityBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
    "Perplexity-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)",
    "ClaudeBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
    "Claude-SearchBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-SearchBot/1.0; +https://www.anthropic.com)",
    "Claude-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0; +https://www.anthropic.com)",
    "Applebot": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15 (Applebot/0.1; +http://www.apple.com/go/applebot)",
    "DuckDuckBot": "DuckDuckBot/1.1; (+http://duckduckgo.com/duckduckbot.html)",
}
BASE = "https://grupoavanzaconsultores.es/"
RUTAS = ["", "en.html", "modelo-210-non-resident-tax-spain.html", "fr.html", "de.html",
         "fiscalidad-no-residentes-y-extranjeros.html", "robots.txt", "sitemap.xml", "llms.txt"]
GITHUB_PAGES = ("185.199.108.", "185.199.109.", "185.199.110.", "185.199.111.")


def pedir(url, ua):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read(), r.headers.get("Server", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b"", e.headers.get("Server", "")
    except Exception as e:  # red, TLS, tiempo
        return 0, str(e).encode(), ""


def main():
    fallos = 0
    for host in ("grupoavanzaconsultores.es", "www.grupoavanzaconsultores.es"):
        try:
            ips = sorted({a[4][0] for a in socket.getaddrinfo(host, 443, socket.AF_INET)})
        except Exception as e:
            ips = [f"sin resolver: {e}"]
        delante = "GitHub Pages" if ips and all(i.startswith(GITHUB_PAGES) for i in ips) else "OTRO (revisar cortafuegos)"
        print(f"::notice title=DNS {host}::{', '.join(ips)} -> {delante}")
        if delante != "GitHub Pages":
            fallos += 1
    for ruta in RUTAS:
        url = BASE + ruta
        st0, ref, srv = pedir(url, UAS["Navegador"])
        h_ref = hashlib.sha256(ref).hexdigest()[:12]
        m = re.search(rb"<h1[^>]*>(.*?)</h1>", ref, re.S)
        h1 = re.sub(rb"<[^>]+>|\s+", b" ", m.group(1)).strip()[:60] if m else b""
        print(f"::notice title=Referencia /{ruta}::{st0} · {len(ref)} bytes · sha {h_ref} · servidor {srv} · h1 «{h1.decode('utf-8', 'replace')}»")
        malos = []
        for nombre, ua in UAS.items():
            if nombre == "Navegador":
                continue
            st, cuerpo, _ = pedir(url, ua)
            ok = st == 200 and hashlib.sha256(cuerpo).hexdigest()[:12] == h_ref and (not h1 or h1 in cuerpo)
            if not ok:
                malos.append(f"{nombre}={st}/{len(cuerpo)}b")
        if st0 != 200 or malos:
            fallos += 1
            print(f"::error title=Rastreadores /{ruta}::{'; '.join(malos) or 'el navegador tampoco recibe 200'}")
        else:
            print(f"::notice title=Rastreadores /{ruta}::{len(UAS) - 1} user-agents: 200 y el mismo HTML que un navegador")
    print(f"::notice title=Resultado::{'TODO BIEN' if not fallos else str(fallos) + ' fallos'}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
