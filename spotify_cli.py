#!/usr/bin/env python3
"""
CLI de controle total da conta Spotify: musicas curtidas, playlists
(criar, apagar, adicionar/remover/reordenar faixas), top tracks/artists,
tocadas recentemente.

Autenticacao via Authorization Code (OAuth). Ao contrario de um token
copiado do console de docs (expira em minutos, escopo fixo e minimo),
este fluxo guarda um refresh_token local que renova o acesso sozinho,
sem depender de token colado a cada uso.

Primeiro uso:
    export SPOTIFY_CLIENT_ID=...
    export SPOTIFY_CLIENT_SECRET=...
    python3 spotify_cli.py authorize

Isso abre o navegador, pede as permissoes e grava o refresh_token em
~/.config/spotify-cli/credentials.json (fora do repositorio, permissao
600). Nas proximas execucoes so SPOTIFY_CLIENT_ID/SECRET sao
necessarios -- o script renova o access_token sozinho a cada chamada.

Comandos:
    authorize                                    autoriza e salva as credenciais
    whoami                                        mostra o perfil autenticado
    liked list [--limit N]                        lista musicas curtidas
    liked add <faixa> -- <artista>                curte uma musica (busca por nome)
    liked add --uri spotify:track:...             curte por URI exato
    liked remove <faixa> -- <artista>              descurte
    liked check --uri spotify:track:...           verifica se esta curtida
    liked clear --yes                             remove TODAS as curtidas (destrutivo)
    playlists list                                lista suas playlists
    playlist show <playlist_id>                   lista as faixas de uma playlist
    playlist create <nome> [--public] [--desc D]  cria playlist
    playlist delete <playlist_id>                 apaga (deixa de seguir)
    playlist add <playlist_id> --uri U [--uri U2] adiciona faixas ao fim
    playlist remove <playlist_id> --uri U         remove faixas
    playlist set <playlist_id> --csv arquivo.csv  substitui o conteudo inteiro,
                                                   na ordem exata do CSV
                                                   (colunas: faixa,artista)
    playlist from-liked <nome> [--public]         cria playlist com todas as
                                                   curtidas (copia direta por
                                                   URI, sem busca)
    following artists                             lista artistas que voce segue
    podcasts list                                  lista podcasts salvos/seguidos
    podcasts now                                   mostra episodio tocando agora (se houver)
    podcasts status                                classifica cada um por atividade (ultimo ep.)
    top tracks|artists [--range T] [--limit N]    T = short_term|medium_term|long_term
    recent [--limit N]                            tocadas recentemente

Requer o redirect URI http://127.0.0.1:8888/callback cadastrado no app
em https://developer.spotify.com/dashboard.
"""

import argparse
import base64
import csv
import http.server
import json
import os
import stat
import secrets
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = " ".join([
    "user-read-private", "user-read-email",
    "user-library-read", "user-library-modify",
    "playlist-read-private", "playlist-read-collaborative",
    "playlist-modify-public", "playlist-modify-private",
    "user-top-read", "user-read-recently-played",
    "user-follow-read", "user-follow-modify",
    "user-read-playback-state", "user-modify-playback-state",
    "user-read-currently-playing", "user-read-playback-position",
    "ugc-image-upload",
])
# fora dessa lista de proposito: "streaming" e "app-remote-control" sao para
# apps que embutem um player via SDK (web/mobile), nao fazem sentido pra um
# CLI e podem exigir revisao extra do Spotify sem trazer nenhuma funcao nova.
CRED_PATH = os.path.expanduser("~/.config/spotify-cli/credentials.json")

_auth_result = {}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _auth_result.update({k: v[0] for k, v in params.items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = "code" in params
        msg = "Autorizado. Pode fechar esta aba." if ok else "Falha na autorizacao."
        self.wfile.write(f"<html><body><h2>{msg}</h2></body></html>".encode())

    def log_message(self, *args):
        pass


def api(method, path, token, body=None, query=None):
    url = f"https://api.spotify.com/v1/{path.lstrip('/')}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise SystemExit(f"Erro HTTP {e.code} em {method} {path}\n{detail}")


def _save_credentials(data):
    os.makedirs(os.path.dirname(CRED_PATH), exist_ok=True)
    with open(CRED_PATH, "w") as f:
        json.dump(data, f)
    os.chmod(CRED_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 600 -- so o dono le/escreve


def _load_credentials():
    if not os.path.exists(CRED_PATH):
        return None
    with open(CRED_PATH) as f:
        return json.load(f)


def authorize(client_id, client_secret):
    """Fluxo Authorization Code completo. Salva o refresh_token localmente."""
    state = secrets.token_urlsafe(16)
    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": client_id, "response_type": "code",
        "redirect_uri": REDIRECT_URI, "scope": SCOPES, "state": state,
    })

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
        "https://accounts.spotify.com/api/token", data=payload,
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        tok = json.load(resp)

    _save_credentials({"refresh_token": tok["refresh_token"]})
    print(f"\nAutorizado. Escopos concedidos: {tok.get('scope', '?')}")
    print(f"Credenciais salvas em {CRED_PATH} (permissao 600).")
    return tok["access_token"]


def get_access_token(client_id, client_secret):
    """Renova o access_token a partir do refresh_token salvo."""
    creds = _load_credentials()
    if not creds or "refresh_token" not in creds:
        raise SystemExit(
            "Nenhuma credencial salva. Rode primeiro:\n"
            "  python3 spotify_cli.py authorize"
        )
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    payload = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": creds["refresh_token"],
    }).encode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token", data=payload,
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            tok = json.load(resp)
    except urllib.error.HTTPError as e:
        raise SystemExit(
            f"Falha ao renovar o token ({e.code}): {e.read().decode()}\n"
            "O refresh_token pode ter sido revogado. Rode 'authorize' de novo."
        )
    # o Spotify pode devolver um novo refresh_token; se vier, atualiza
    if "refresh_token" in tok:
        _save_credentials({"refresh_token": tok["refresh_token"]})
    return tok["access_token"]


def resolve_track(token, track, artist):
    for query in (f'track:"{track}" artist:"{artist}"' if artist else track,):
        items = api("GET", "search", token,
                     query={"q": query, "type": "track", "limit": 1}
                     ).get("tracks", {}).get("items", [])
        if items:
            it = items[0]
            return it["id"], it["uri"], it["name"], it["artists"][0]["name"]
    return None, None, None, None


def cmd_whoami(token, args):
    me = api("GET", "me", token)
    print(f"{me['display_name']} (@{me['id']})")
    print(f"  {me['external_urls']['spotify']}")
    print(f"  seguidores: {me.get('followers', {}).get('total', '?')}")


def cmd_liked_list(token, args):
    limit, fetched, offset = args.limit, 0, 0
    while fetched < limit:
        page = api("GET", "me/tracks", token,
                    query={"limit": min(50, limit - fetched), "offset": offset})
        items = page.get("items", [])
        if not items:
            break
        for it in items:
            tr = it["track"]
            artists = ", ".join(a["name"] for a in tr["artists"])
            print(f"  {tr['name']} - {artists}")
        fetched += len(items)
        offset += len(items)
        if page.get("next") is None:
            break
    print(f"\n{fetched} faixas listadas (total na biblioteca: {page.get('total', '?')})")


# Migracao de fevereiro/2026: os endpoints de escrita da biblioteca foram
# consolidados em /me/library (URIs completas na query string, max 40),
# substituindo PUT/DELETE /me/tracks (que aceitavam so IDs no corpo).
# GET /me/tracks para LEITURA nao mudou -- continua igual em cmd_liked_list.
def cmd_liked_add(token, args):
    uris = list(args.uri or [])
    if args.query:
        track, _, artist = " ".join(args.query).partition(" -- ")
        tid, uri, name, art = resolve_track(token, track.strip(), artist.strip())
        if not uri:
            raise SystemExit(f"Nao encontrei: {track} - {artist}")
        print(f"Encontrado: {name} - {art}")
        uris.append(uri)
    if not uris:
        raise SystemExit("Informe --uri ou '<faixa> -- <artista>'.")
    for i in range(0, len(uris), 40):
        api("PUT", "me/library", token, query={"uris": ",".join(uris[i:i + 40])})
    print(f"{len(uris)} faixa(s) curtida(s).")


def cmd_liked_remove(token, args):
    uris = list(args.uri or [])
    if args.query:
        track, _, artist = " ".join(args.query).partition(" -- ")
        tid, uri, name, art = resolve_track(token, track.strip(), artist.strip())
        if not uri:
            raise SystemExit(f"Nao encontrei: {track} - {artist}")
        print(f"Encontrado: {name} - {art}")
        uris.append(uri)
    if not uris:
        raise SystemExit("Informe --uri ou '<faixa> -- <artista>'.")
    for i in range(0, len(uris), 40):
        api("DELETE", "me/library", token, query={"uris": ",".join(uris[i:i + 40])})
    print(f"{len(uris)} faixa(s) removida(s) das curtidas.")


def cmd_liked_clear(token, args):
    """Descurte TODAS as faixas da biblioteca. Destrutivo -- exige --yes."""
    if not args.yes:
        raise SystemExit("Isso remove TODAS as curtidas. Rode de novo com --yes para confirmar.")

    uris, offset = [], 0
    while True:
        page = api("GET", "me/tracks", token, query={"limit": 50, "offset": offset})
        items = page.get("items", [])
        if not items:
            break
        uris += [it["track"]["uri"] for it in items]
        offset += len(items)
        if page.get("next") is None:
            break

    if not uris:
        print("Nenhuma faixa curtida encontrada -- nada a fazer.")
        return

    for i in range(0, len(uris), 40):
        api("DELETE", "me/library", token, query={"uris": ",".join(uris[i:i + 40])})
        print(f"  removidas {min(i + 40, len(uris))}/{len(uris)}")

    print(f"\n{len(uris)} faixa(s) removida(s) das curtidas.")


def cmd_liked_check(token, args):
    result = []
    for i in range(0, len(args.uri), 40):
        chunk = args.uri[i:i + 40]
        result += api("GET", "me/library/contains", token, query={"uris": ",".join(chunk)})
    for uri, saved in zip(args.uri, result):
        print(f"  {'sim' if saved else 'nao':<4} {uri}")


def cmd_playlists_list(token, args):
    me_id = api("GET", "me", token)["id"]
    items, offset = [], 0
    while True:
        page = api("GET", "me/playlists", token, query={"limit": 50, "offset": offset})
        items += page.get("items", [])
        if page.get("next") is None:
            break
        offset += 50
    if not items:
        print("Nenhuma playlist (propria ou seguida).")
    minhas = [p for p in items if p.get("owner", {}).get("id") == me_id]
    seguidas = [p for p in items if p.get("owner", {}).get("id") != me_id]
    for label, group, show_owner in (("SUAS", minhas, False),
                                      ("SEGUIDAS (de outras pessoas)", seguidas, True)):
        if not group:
            continue
        print(f"-- {label} --")
        for p in group:
            vis = "publica" if p["public"] else "privada"
            # a maioria das playlists traz contagem em 'tracks'; algumas (ex.: as
            # criadas pelo playground de docs do Spotify) trazem em 'items'
            count = (p.get("tracks") or p.get("items") or {}).get("total", "?")
            dono = f"  (por {p['owner'].get('display_name') or p['owner']['id']})" if show_owner else ""
            print(f"  {p['id']}  {p['name']!r:<40} {count:>4} faixas  {vis}{dono}")


def cmd_following_artists(token, args):
    # GET /me/following devolve o artista "simplificado" (sem followers/genres),
    # diferente do objeto completo de GET /artists/{id} -- por isso listamos so nome + link.
    after = None
    total_seen = 0
    while True:
        page = api("GET", "me/following", token,
                    query={"type": "artist", "limit": 50, **({"after": after} if after else {})}
                    )["artists"]
        items = page.get("items", [])
        if not items:
            break
        for a in items:
            print(f"  {a['name']:<35} {a['external_urls']['spotify']}")
        total_seen += len(items)
        after = page.get("cursors", {}).get("after")
        if not after:
            break
    print(f"\n{total_seen} artista(s) seguido(s) (total reportado: {page.get('total', '?')}).")


# Migracao de fevereiro/2026: /playlists/{id}/tracks virou /playlists/{id}/items
# em toda a familia (GET/POST/PUT/DELETE); o campo 'track' de cada item virou
# 'item' (mantido tambem como 'track', por ora, entao lemos os dois);
# criar playlist deixou de precisar do user_id no path (POST /me/playlists).
def cmd_playlist_show(token, args):
    tracks, offset = [], 0
    while True:
        page = api("GET", f"playlists/{args.playlist_id}/items", token,
                    query={"limit": 50, "offset": offset,
                           "fields": "total,next,items(item(name,artists(name),uri))"})
        tracks += page.get("items", [])
        if page.get("next") is None:
            break
        offset += 50
    for i, it in enumerate(tracks, 1):
        tr = it.get("item") or it.get("track")
        if not tr:
            continue
        artists = ", ".join(a["name"] for a in tr["artists"])
        print(f"  {i:>3} | {tr['name']} - {artists}")
    print(f"\n{len(tracks)} faixas.")


def cmd_playlist_from_liked(token, args):
    """Cria uma playlist com todas as curtidas, copiando os URIs direto --
    sem passar por busca, entao nao ha risco de vir versao/faixa errada."""
    uris, offset = [], 0
    while True:
        page = api("GET", "me/tracks", token, query={"limit": 50, "offset": offset})
        items = page.get("items", [])
        if not items:
            break
        uris += [it["track"]["uri"] for it in items]
        print(f"  lidas {len(uris)}/{page.get('total', '?')}")
        offset += len(items)
        if page.get("next") is None:
            break

    if not uris:
        raise SystemExit("Nenhuma faixa curtida encontrada.")

    pl = api("POST", "me/playlists", token, {
        "name": args.name, "public": args.public,
        "description": f"Copia das suas {len(uris)} musicas curtidas no Spotify.",
    })
    for i in range(0, len(uris), 100):
        api("POST", f"playlists/{pl['id']}/items", token, {"uris": uris[i:i + 100]})

    print(f"\nCriada: {pl['name']} ({pl['id']}) -- {len(uris)} faixas")
    print(f"  {pl['external_urls']['spotify']}")


def cmd_playlist_create(token, args):
    pl = api("POST", "me/playlists", token, {
        "name": args.name, "public": args.public, "description": args.desc or "",
    })
    print(f"Criada: {pl['name']} ({pl['id']})")
    print(f"  {pl['external_urls']['spotify']}")


def cmd_playlist_delete(token, args):
    api("DELETE", f"playlists/{args.playlist_id}/followers", token)
    print(f"Playlist {args.playlist_id} removida da sua biblioteca.")


def cmd_playlist_add(token, args):
    if not args.uri:
        raise SystemExit("Informe uma ou mais --uri.")
    for i in range(0, len(args.uri), 100):
        api("POST", f"playlists/{args.playlist_id}/items", token,
            {"uris": args.uri[i:i + 100]})
    print(f"{len(args.uri)} faixa(s) adicionada(s).")


def cmd_playlist_remove(token, args):
    if not args.uri:
        raise SystemExit("Informe uma ou mais --uri.")
    items = [{"uri": u} for u in args.uri]
    api("DELETE", f"playlists/{args.playlist_id}/items", token, {"items": items})
    print(f"{len(args.uri)} faixa(s) removida(s).")


def cmd_playlist_set(token, args):
    """Substitui o conteudo inteiro pela ordem exata do CSV (colunas: faixa,artista)."""
    with open(args.csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    uris, missing = [], []
    for r in rows:
        _, uri, name, art = resolve_track(token, r["faixa"], r["artista"])
        if uri:
            uris.append(uri)
            print(f"  [ok] {name} - {art}")
        else:
            missing.append(f"{r['faixa']} - {r['artista']}")
            print(f"  [--] {r['faixa']} - {r['artista']}")

    if not uris:
        raise SystemExit("Nenhuma faixa resolvida -- nada a fazer.")

    # PUT substitui todo o conteudo pelas primeiras 100; POST anexa o resto
    api("PUT", f"playlists/{args.playlist_id}/items", token, {"uris": uris[:100]})
    for i in range(100, len(uris), 100):
        api("POST", f"playlists/{args.playlist_id}/items", token,
            {"uris": uris[i:i + 100]})

    print(f"\nPlaylist substituida: {len(uris)}/{len(rows)} faixas na ordem do CSV.")
    if missing:
        print(f"{len(missing)} nao encontradas:")
        for m in missing:
            print(f"  - {m}")


def cmd_top(token, args):
    page = api("GET", f"me/top/{args.kind}", token,
               query={"time_range": args.range, "limit": args.limit})
    for i, x in enumerate(page.get("items", []), 1):
        if args.kind == "tracks":
            artists = ", ".join(a["name"] for a in x["artists"])
            print(f"  {i:>3} | {x['name']} - {artists}")
        else:
            print(f"  {i:>3} | {x['name']}")


def cmd_recent(token, args):
    page = api("GET", "me/player/recently-played", token, query={"limit": args.limit})
    for it in page.get("items", []):
        tr = it["track"]
        artists = ", ".join(a["name"] for a in tr["artists"])
        print(f"  {it['played_at']}  {tr['name']} - {artists}")


def cmd_podcasts_list(token, args):
    items, offset = [], 0
    while True:
        page = api("GET", "me/shows", token, query={"limit": 50, "offset": offset})
        chunk = page.get("items", [])
        if not chunk:
            break
        items += chunk
        offset += len(chunk)
        if page.get("next") is None:
            break
    if not items:
        print("Nenhum podcast salvo.")
    for it in items:
        s = it["show"]
        # 'publisher' nao vem mais nesse endpoint (confirmado no corpo real da
        # resposta); 'added_at' sim, e e mais util aqui de qualquer forma
        added = it.get("added_at", "")[:10]
        print(f"  {s['name']:<40} {s['total_episodes']:>4} episodios  desde {added}")
    print(f"\n{len(items)} podcast(s) seguido(s).")
    # nota: a API do Spotify nao expoe historico de reproducao de episodios
    # (GET /me/player/recently-played documenta "Currently doesn't support
    # podcast episodes") -- "que ouco" so da pra responder olhando o que
    # esta tocando agora, nao um historico.


def cmd_podcasts_status(token, args):
    """Classifica cada podcast salvo por atividade, olhando a data do ultimo
    episodio publicado. Nao existe um flag "ativo" oficial do Spotify --
    e um heuristico baseado em ha quanto tempo saiu o episodio mais recente."""
    import datetime
    today = datetime.date.today()

    items, offset = [], 0
    while True:
        page = api("GET", "me/shows", token, query={"limit": 50, "offset": offset})
        chunk = page.get("items", [])
        if not chunk:
            break
        items += chunk
        offset += len(chunk)
        if page.get("next") is None:
            break

    rows = []
    for it in items:
        s = it["show"]
        ep = api("GET", f"shows/{s['id']}/episodes", token, query={"limit": 1}).get("items", [])
        if not ep:
            rows.append((s["name"], None, "sem episodios"))
            continue
        rd = ep[0]["release_date"]
        try:
            d = datetime.date.fromisoformat(rd if len(rd) == 10 else f"{rd}-01-01")
        except ValueError:
            rows.append((s["name"], rd, "data invalida"))
            continue
        days = (today - d).days
        if days <= 60:
            status = "ativo"
        elif days <= 365:
            status = "pausado"
        else:
            status = "encerrado/inativo"
        rows.append((s["name"], rd, f"{status} (ultimo ep. ha {days}d)"))

    rows.sort(key=lambda r: r[1] or "0000-00-00", reverse=True)
    for name, rd, status in rows:
        print(f"  {name:<40} {rd or '?':<12} {status}")
    print(f"\n{len(rows)} podcasts avaliados. Corte: ativo <=60d, pausado <=365d, encerrado >365d.")


def cmd_podcasts_unfollow(token, args):
    # mesmo endpoint consolidado dos tracks (migracao fev/2026): DELETE
    # /me/library aceita URIs de qualquer tipo, incluindo spotify:show:...
    uris = [f"spotify:show:{i}" if not i.startswith("spotify:show:") else i
            for i in args.id]
    for i in range(0, len(uris), 40):
        api("DELETE", "me/library", token, query={"uris": ",".join(uris[i:i + 40])})
    print(f"{len(uris)} podcast(s) removido(s) dos seguidos.")


def cmd_podcasts_now(token, args):
    d = api("GET", "me/player/currently-playing", token,
             query={"additional_types": "episode"})
    if not d or not d.get("item"):
        print("Nada tocando agora.")
        return
    item = d["item"]
    if item.get("type") != "episode":
        print(f"Tocando agora nao e podcast: {item.get('name')} ({item.get('type')})")
        return
    print(f"  {item['name']} -- {item['show']['name']}")
    print(f"  {item['show']['publisher']}")


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("authorize")
    sub.add_parser("whoami")

    liked = sub.add_parser("liked").add_subparsers(dest="liked_cmd", required=True)
    p = liked.add_parser("list"); p.add_argument("--limit", type=int, default=50)
    p = liked.add_parser("add"); p.add_argument("query", nargs="*"); p.add_argument("--uri", action="append")
    p = liked.add_parser("remove"); p.add_argument("query", nargs="*"); p.add_argument("--uri", action="append")
    p = liked.add_parser("check"); p.add_argument("--uri", action="append", required=True)
    p = liked.add_parser("clear"); p.add_argument("--yes", action="store_true",
        help="confirma a remocao de TODAS as curtidas -- obrigatorio")

    sub.add_parser("playlists").add_subparsers(dest="pls_cmd", required=True).add_parser("list")

    following = sub.add_parser("following").add_subparsers(dest="following_cmd", required=True)
    following.add_parser("artists")

    podcasts = sub.add_parser("podcasts").add_subparsers(dest="podcasts_cmd", required=True)
    podcasts.add_parser("list")
    podcasts.add_parser("now")
    podcasts.add_parser("status")
    p = podcasts.add_parser("unfollow"); p.add_argument("--id", action="append", required=True,
        help="Spotify show ID (ou URI completa)")

    pl = sub.add_parser("playlist").add_subparsers(dest="pl_cmd", required=True)
    p = pl.add_parser("show"); p.add_argument("playlist_id")
    p = pl.add_parser("create"); p.add_argument("name"); p.add_argument("--public", action="store_true"); p.add_argument("--desc")
    p = pl.add_parser("delete"); p.add_argument("playlist_id")
    p = pl.add_parser("add"); p.add_argument("playlist_id"); p.add_argument("--uri", action="append", required=True)
    p = pl.add_parser("remove"); p.add_argument("playlist_id"); p.add_argument("--uri", action="append", required=True)
    p = pl.add_parser("set"); p.add_argument("playlist_id"); p.add_argument("--csv", required=True)
    p = pl.add_parser("from-liked"); p.add_argument("name"); p.add_argument("--public", action="store_true")

    p = sub.add_parser("top")
    p.add_argument("kind", choices=["tracks", "artists"])
    p.add_argument("--range", dest="range", default="long_term",
                   choices=["short_term", "medium_term", "long_term"])
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("recent"); p.add_argument("--limit", type=int, default=20)

    return ap


def main():
    args = build_parser().parse_args()
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit("Defina SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET.")

    if args.cmd == "authorize":
        authorize(client_id, client_secret)
        return

    token = get_access_token(client_id, client_secret)

    dispatch = {
        "whoami": cmd_whoami,
        ("liked", "list"): cmd_liked_list,
        ("liked", "add"): cmd_liked_add,
        ("liked", "remove"): cmd_liked_remove,
        ("liked", "check"): cmd_liked_check,
        ("liked", "clear"): cmd_liked_clear,
        ("playlists", "list"): cmd_playlists_list,
        ("playlist", "show"): cmd_playlist_show,
        ("playlist", "create"): cmd_playlist_create,
        ("playlist", "delete"): cmd_playlist_delete,
        ("playlist", "add"): cmd_playlist_add,
        ("playlist", "remove"): cmd_playlist_remove,
        ("playlist", "set"): cmd_playlist_set,
        ("playlist", "from-liked"): cmd_playlist_from_liked,
        ("following", "artists"): cmd_following_artists,
        ("podcasts", "list"): cmd_podcasts_list,
        ("podcasts", "now"): cmd_podcasts_now,
        ("podcasts", "status"): cmd_podcasts_status,
        ("podcasts", "unfollow"): cmd_podcasts_unfollow,
        "top": cmd_top,
        "recent": cmd_recent,
    }

    if args.cmd == "liked":
        fn = dispatch[("liked", args.liked_cmd)]
    elif args.cmd == "playlists":
        fn = dispatch[("playlists", args.pls_cmd)]
    elif args.cmd == "playlist":
        fn = dispatch[("playlist", args.pl_cmd)]
    elif args.cmd == "following":
        fn = dispatch[("following", args.following_cmd)]
    elif args.cmd == "podcasts":
        fn = dispatch[("podcasts", args.podcasts_cmd)]
    else:
        fn = dispatch[args.cmd]

    fn(token, args)


if __name__ == "__main__":
    sys.exit(main())
