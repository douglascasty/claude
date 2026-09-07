#!/usr/bin/env python3
"""
Exporta estatisticas da conta Steam: biblioteca com horas jogadas,
atividade recente e progressao de conquistas.

Uso:
    export STEAM_API_KEY=...
    python3 steam_stats.py --user whocasty          # vanity URL ou SteamID64
    python3 steam_stats.py --user 7656119...  --achievements 10

Requer perfil e "Detalhes do jogo" publicos em
https://steamcommunity.com/my/edit/settings -- caso contrario a API
responde 200 com corpo vazio, sem avisar que o motivo foi privacidade.
"""

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.steampowered.com"


def call(iface, method, version, key, **params):
    """Chama a Steam Web API. Devolve o dict de 'response'/'playerstats' ou {}."""
    params = {k: v for k, v in params.items() if v is not None}
    url = (f"{BASE}/{iface}/{method}/v{version}/?"
           + urllib.parse.urlencode({"key": key, **params}))
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        # 403 costuma ser perfil privado; 400, parametro invalido
        print(f"  ! HTTP {e.code} em {iface}/{method}", file=sys.stderr)
        return {}
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"  ! falha em {iface}/{method}: {e}", file=sys.stderr)
        return {}
    return data.get("response", data.get("playerstats", {}))


def resolve_steamid(key, user):
    """Aceita SteamID64 (17 digitos) ou vanity URL; devolve o SteamID64."""
    if user.isdigit() and len(user) == 17:
        return user
    r = call("ISteamUser", "ResolveVanityURL", 1, key, vanityurl=user)
    if r.get("success") == 1:
        return r["steamid"]
    raise SystemExit(f"Nao consegui resolver '{user}' para um SteamID64.")


def hrs(minutes):
    return round(minutes / 60, 1)


def show_profile(key, sid):
    players = call("ISteamUser", "GetPlayerSummaries", 2, key,
                   steamids=sid).get("players", [])
    if not players:
        print("Perfil nao retornado (provavelmente privado).")
        return None
    p = players[0]
    visibility = {1: "privado", 2: "so amigos", 3: "publico"}.get(
        p.get("communityvisibilitystate"), "?")
    print(f"  Nome:        {p.get('personaname')}")
    print(f"  SteamID64:   {sid}")
    print(f"  Perfil:      {visibility}")
    print(f"  URL:         {p.get('profileurl')}")
    if visibility != "publico":
        print("\n  AVISO: perfil nao publico -- as consultas abaixo tendem a vir vazias.")
    return p


def owned_games(key, sid, out_csv):
    r = call("IPlayerService", "GetOwnedGames", 1, key, steamid=sid,
             include_appinfo=1, include_played_free_games=1)
    games = r.get("games", [])
    if not games:
        print("  Nenhum jogo retornado (biblioteca privada ou vazia).")
        return []

    games.sort(key=lambda g: g.get("playtime_forever", 0), reverse=True)
    played = [g for g in games if g.get("playtime_forever", 0) > 0]
    total_h = hrs(sum(g.get("playtime_forever", 0) for g in games))

    print(f"  {len(games)} jogos na biblioteca | {len(played)} jogados | "
          f"{len(games) - len(played)} nunca abertos")
    print(f"  {total_h}h no total")
    if played:
        print(f"  Media entre os jogados: {round(total_h / len(played), 1)}h\n")
        print("  Top 15 por horas:")
        for i, g in enumerate(games[:15], 1):
            print(f"    {i:>2}. {g.get('name', '?')[:45]:<45} {hrs(g['playtime_forever']):>8}h")

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "appid", "jogo", "horas", "horas_2semanas"])
        for i, g in enumerate(games, 1):
            w.writerow([i, g.get("appid"), g.get("name", ""),
                        hrs(g.get("playtime_forever", 0)),
                        hrs(g.get("playtime_2weeks", 0))])
    print(f"\n  CSV: {out_csv}")
    return games


def recent(key, sid):
    r = call("IPlayerService", "GetRecentlyPlayedGames", 1, key, steamid=sid)
    games = r.get("games", [])
    if not games:
        print("  Nada jogado nas ultimas 2 semanas.")
        return
    for g in games:
        print(f"    {g.get('name', '?')[:45]:<45} {hrs(g.get('playtime_2weeks', 0)):>7}h"
              f"  (total {hrs(g.get('playtime_forever', 0))}h)")


def achievements(key, sid, games, top_n):
    """Progressao nos top_n jogos, com a raridade global de cada conquista."""
    for g in games[:top_n]:
        appid, name = g.get("appid"), g.get("name", "?")
        st = call("ISteamUserStats", "GetPlayerAchievements", 1, key,
                  steamid=sid, appid=appid)
        ach = st.get("achievements")
        if not ach:
            continue  # jogo sem sistema de conquistas, ou stats privados

        done = [a for a in ach if a.get("achieved")]
        pct = 100 * len(done) / len(ach)
        bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
        print(f"\n  {name[:50]}")
        print(f"    [{bar}] {len(done)}/{len(ach)} ({pct:.0f}%)")

        if len(done) == len(ach):
            print("    Completo.")
            continue

        # raridade global: qual das que faltam e a mais rara
        glob = call("ISteamUserStats", "GetGlobalAchievementPercentagesForApp", 2,
                    key, gameid=appid).get("achievements", [])
        rates = {a["name"]: a["percent"] for a in glob}
        missing = sorted(
            ((a, rates.get(a.get("apiname"), 100.0)) for a in ach if not a.get("achieved")),
            key=lambda x: x[1])
        print("    Faltam (da mais rara):")
        for a, pc in missing[:5]:
            label = a.get("name") or a.get("apiname")
            print(f"      - {label[:40]:<40} {pc:>5.1f}% dos jogadores tem")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True, help="SteamID64 ou vanity URL")
    ap.add_argument("--achievements", type=int, default=5,
                    help="quantos jogos do topo analisar (0 desliga)")
    ap.add_argument("--csv", default="steam_biblioteca.csv")
    args = ap.parse_args()

    key = os.environ.get("STEAM_API_KEY")
    if not key:
        raise SystemExit("Defina STEAM_API_KEY (https://steamcommunity.com/dev/apikey).")

    sid = resolve_steamid(key, args.user)

    print("=" * 64); print("PERFIL"); print("=" * 64)
    show_profile(key, sid)

    print("\n" + "=" * 64); print("BIBLIOTECA E HORAS"); print("=" * 64)
    games = owned_games(key, sid, args.csv)

    print("\n" + "=" * 64); print("ULTIMAS 2 SEMANAS"); print("=" * 64)
    recent(key, sid)

    if games and args.achievements > 0:
        print("\n" + "=" * 64)
        print(f"CONQUISTAS (top {args.achievements} por horas)")
        print("=" * 64)
        achievements(key, sid, games, args.achievements)


if __name__ == "__main__":
    sys.exit(main())
