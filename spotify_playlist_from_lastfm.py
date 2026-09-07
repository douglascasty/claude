#!/usr/bin/env python3
"""
Cria uma playlist no Spotify a partir do CSV exportado do Last.fm,
inserindo as faixas por URI na ordem exata do ranking.

Diferente do conector de chat, que interpreta uma descricao em linguagem
natural, aqui cada faixa e resolvida por busca e inserida pelo seu URI --
a ordem e o conteudo sao exatamente os do CSV.

Uso:
    export SPOTIFY_CLIENT_ID=...
    export SPOTIFY_CLIENT_SECRET=...
    python3 spotify_playlist_from_lastfm.py [--limit 100] [--name "Top 100 Last.fm"]

Requer que o app tenha o redirect URI http://127.0.0.1:8888/callback
cadastrado em https://developer.spotify.com/dashboard
"""

import argparse
import base64
import csv
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = "playlist-modify-private playlist-modify-public"
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "top100_lastfm_whocasty.csv")

_auth_result = {}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        _auth_result.update({k: v[0] for k, v in params.items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = "code" in params
        msg = "Autorizado. Pode fechar esta aba." if ok else "Falha na autorizacao."
        self.wfile.write(f"<html><body><h2>{msg}</h2></body></html>".encode())

    def log_message(self, *args):
        pass  # silencia o log do servidor


def api(method, url, token=None, body=None, headers=None):
    """Chamada HTTP a API do Spotify. Levanta em erro, devolve dict."""
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json"}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise SystemExit(f"Erro HTTP {e.code} em {method} {url}\n{detail}")


def authorize(client_id, client_secret):
    """Fluxo Authorization Code: abre o navegador e espera o callback local."""
    state = secrets.token_urlsafe(16)
    params = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
    })
    auth_url = f"https://accounts.spotify.com/authorize?{params}"

    server = http.server.HTTPServer(("127.0.0.1", 8888), _CallbackHandler)
    threading.Thread(target=server.handle_request, daemon=True).start()

    print("Abrindo o navegador para autorizacao...")
    print(f"Se nao abrir, cole esta URL manualmente:\n{auth_url}\n")
    webbrowser.open(auth_url)

    while "code" not in _auth_result and "error" not in _auth_result:
        threading.Event().wait(0.3)

    if "error" in _auth_result:
        raise SystemExit(f"Autorizacao negada: {_auth_result['error']}")
    if _auth_result.get("state") != state:
        raise SystemExit("State divergente -- possivel CSRF. Abortado.")

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    payload = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": _auth_result["code"],
        "redirect_uri": REDIRECT_URI,
    }).encode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=payload,
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)["access_token"]
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Falha ao trocar o code por token: {e.read().decode()}")


def resolve(token, track, artist):
    """Busca a faixa e devolve (uri, nome_encontrado, artista_encontrado)."""
    for query in (f'track:"{track}" artist:"{artist}"', f"{track} {artist}"):
        url = ("https://api.spotify.com/v1/search?"
               + urllib.parse.urlencode({"q": query, "type": "track", "limit": 1}))
        items = api("GET", url, token).get("tracks", {}).get("items", [])
        if items:
            it = items[0]
            return it["uri"], it["name"], it["artists"][0]["name"]
    return None, None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100, help="quantas faixas usar")
    ap.add_argument("--name", default="Top 100 Last.fm", help="nome da playlist")
    ap.add_argument("--public", action="store_true", help="criar publica")
    ap.add_argument("--csv", default=CSV_PATH)
    args = ap.parse_args()

    cid = os.environ.get("SPOTIFY_CLIENT_ID")
    secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not cid or not secret:
        raise SystemExit("Defina SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET.")

    with open(args.csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))[: args.limit]
    print(f"{len(rows)} faixas lidas de {os.path.basename(args.csv)}")

    token = authorize(cid, secret)
    user_id = api("GET", "https://api.spotify.com/v1/me", token)["id"]
    print(f"Autenticado como: {user_id}\n")

    uris, missing, swapped = [], [], []
    for r in rows:
        uri, got_t, got_a = resolve(token, r["faixa"], r["artista"])
        if not uri:
            missing.append(f"#{r['rank']} {r['faixa']} - {r['artista']}")
            print(f"  [--] #{r['rank']:>3} {r['faixa']} - {r['artista']}")
            continue
        uris.append(uri)
        # sinaliza quando o titulo/artista devolvido difere do pedido
        if got_t.lower() != r["faixa"].lower() or got_a.lower() != r["artista"].lower():
            swapped.append(f"#{r['rank']} pedido '{r['faixa']} - {r['artista']}' "
                           f"=> obtido '{got_t} - {got_a}'")
            print(f"  [~ ] #{r['rank']:>3} {got_t} - {got_a}")
        else:
            print(f"  [ok] #{r['rank']:>3} {got_t} - {got_a}")

    if not uris:
        raise SystemExit("Nenhuma faixa resolvida -- nada a criar.")

    pl = api("POST", f"https://api.spotify.com/v1/users/{user_id}/playlists", token,
             {"name": args.name,
              "public": args.public,
              "description": "Ranking de escuta do Last.fm (whocasty), por playcount."})

    # a API aceita no maximo 100 URIs por requisicao
    for i in range(0, len(uris), 100):
        api("POST", f"https://api.spotify.com/v1/playlists/{pl['id']}/tracks",
            token, {"uris": uris[i:i + 100]})

    print(f"\n{'=' * 60}")
    print(f"Playlist criada: {pl['external_urls']['spotify']}")
    print(f"Inseridas {len(uris)}/{len(rows)} faixas, na ordem do ranking.")
    if swapped:
        print(f"\n{len(swapped)} com titulo/artista divergente:")
        for s in swapped:
            print(f"  - {s}")
    if missing:
        print(f"\n{len(missing)} nao encontradas:")
        for m in missing:
            print(f"  - {m}")


if __name__ == "__main__":
    sys.exit(main())
