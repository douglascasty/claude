#!/usr/bin/env python3
"""
CLI de leitura da conta Google Cloud: lista projetos e VMs (Compute Engine).

Nao cobre saldo de creditos de trial -- a Cloud Billing API nao expoe isso
(confirmado na documentacao oficial: so metodos de conta/projeto/IAM/SKU,
nada de saldo). Isso so aparece no Console:
  https://console.cloud.google.com/billing

Autenticacao via Authorization Code (OAuth), igual ao spotify_cli.py:
autoriza uma vez, o refresh_token renova sozinho depois.

Primeiro uso:
    1. https://console.cloud.google.com/apis/credentials
       -> selecione ou crie um projeto
       -> "Create Credentials" > "OAuth client ID" > tipo "Desktop app"
       -> nao precisa configurar redirect URI, o tipo Desktop cuida disso
       -> copie o Client ID e o Client Secret
    2. Na mesma tela de APIs, ative (API Library):
       - Compute Engine API
       - Cloud Resource Manager API
    3. Configure a "OAuth consent screen" como "External", adicione seu
       proprio e-mail em "Test users" (obrigatorio mesmo sendo o dono)

    export GCLOUD_CLIENT_ID=...
    export GCLOUD_CLIENT_SECRET=...
    python3 gcloud_cli.py authorize

Comandos:
    authorize                       autoriza e salva as credenciais
    whoami                          mostra a conta Google autenticada
    projects list                   lista projetos acessiveis
    vms list [--project ID]         lista VMs (todos os projetos se omitido)
    billing info --project ID       mostra a conta de billing vinculada
                                     (nao mostra saldo -- isso e so no Console)
"""

import argparse
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

REDIRECT_URI = "http://localhost:8888/"
SCOPES = " ".join([
    "https://www.googleapis.com/auth/cloud-platform.read-only",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
])
CRED_PATH = os.path.expanduser("~/.config/gcloud-cli/credentials.json")

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


def api(method, url, token, query=None):
    if query:
        url += "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, method=method,
                                  headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise SystemExit(f"Erro HTTP {e.code} em {method} {url}\n{detail}")


def _save_credentials(data):
    os.makedirs(os.path.dirname(CRED_PATH), exist_ok=True)
    with open(CRED_PATH, "w") as f:
        json.dump(data, f)
    os.chmod(CRED_PATH, stat.S_IRUSR | stat.S_IWUSR)


def _load_credentials():
    if not os.path.exists(CRED_PATH):
        return None
    with open(CRED_PATH) as f:
        return json.load(f)


def authorize(client_id, client_secret):
    state = secrets.token_urlsafe(16)
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id, "response_type": "code",
        "redirect_uri": REDIRECT_URI, "scope": SCOPES, "state": state,
        "access_type": "offline", "prompt": "consent",
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

    payload = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": _auth_result["code"],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        tok = json.load(resp)

    if "refresh_token" not in tok:
        raise SystemExit(
            "Google nao devolveu refresh_token (geralmente porque essa conta ja "
            "autorizou este app antes). Revogue o acesso em "
            "https://myaccount.google.com/permissions e rode 'authorize' de novo."
        )

    _save_credentials({"refresh_token": tok["refresh_token"]})
    print(f"\nAutorizado. Escopos concedidos: {tok.get('scope', '?')}")
    print(f"Credenciais salvas em {CRED_PATH} (permissao 600).")
    return tok["access_token"]


def get_access_token(client_id, client_secret):
    creds = _load_credentials()
    if not creds or "refresh_token" not in creds:
        raise SystemExit(
            "Nenhuma credencial salva. Rode primeiro:\n"
            "  python3 gcloud_cli.py authorize"
        )
    payload = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": creds["refresh_token"],
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)["access_token"]
    except urllib.error.HTTPError as e:
        raise SystemExit(
            f"Falha ao renovar o token ({e.code}): {e.read().decode()}\n"
            "O refresh_token pode ter sido revogado. Rode 'authorize' de novo."
        )


def cmd_whoami(token, args):
    d = api("GET", "https://www.googleapis.com/oauth2/v2/userinfo", token)
    print(f"{d.get('name', '?')} <{d.get('email', '?')}>")


def _list_projects(token):
    projects, token_page = [], None
    while True:
        q = {"pageSize": 100}
        if token_page:
            q["pageToken"] = token_page
        d = api("GET", "https://cloudresourcemanager.googleapis.com/v3/projects:search",
                 token, query=q)
        projects += d.get("projects", [])
        token_page = d.get("nextPageToken")
        if not token_page:
            break
    return projects


def cmd_projects_list(token, args):
    projects = _list_projects(token)
    if not projects:
        print("Nenhum projeto acessivel com esta conta.")
    for p in projects:
        print(f"  {p['projectId']:<30} {p.get('displayName', ''):<35} {p.get('state', '?')}")
    print(f"\n{len(projects)} projeto(s).")


def cmd_vms_list(token, args):
    projects = [args.project] if args.project else [p["projectId"] for p in _list_projects(token)]
    total = 0
    for pid in projects:
        d = api("GET", f"https://compute.googleapis.com/compute/v1/projects/{pid}/aggregated/instances",
                 token, query={"maxResults": 500})
        zones = d.get("items", {})
        found_in_project = False
        for zone_path, zone_data in zones.items():
            for inst in zone_data.get("instances", []):
                found_in_project = True
                total += 1
                zone = zone_path.split("/")[-1]
                machine = inst.get("machineType", "").split("/")[-1]
                print(f"  [{pid}] {inst['name']:<30} {zone:<18} {machine:<20} {inst.get('status')}")
        if not found_in_project and args.project:
            print(f"  (nenhuma VM em {pid})")
    print(f"\n{total} VM(s) no total, em {len(projects)} projeto(s).")


def cmd_billing_info(token, args):
    d = api("GET", f"https://cloudbilling.googleapis.com/v1/projects/{args.project}/billingInfo", token)
    print(f"Projeto: {d.get('projectId')}")
    print(f"Conta de billing: {d.get('billingAccountName', '(nenhuma vinculada)')}")
    print(f"Billing habilitado: {d.get('billingEnabled', False)}")
    print()
    print("Saldo de creditos NAO esta disponivel por API (Cloud Billing API nao expoe")
    print("isso -- confirmado na documentacao oficial). Ver em:")
    print("  https://console.cloud.google.com/billing")


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("authorize")
    sub.add_parser("whoami")

    sub.add_parser("projects").add_subparsers(dest="pj_cmd", required=True).add_parser("list")

    vms = sub.add_parser("vms").add_subparsers(dest="vms_cmd", required=True)
    p = vms.add_parser("list"); p.add_argument("--project", help="ID do projeto (todos, se omitido)")

    billing = sub.add_parser("billing").add_subparsers(dest="billing_cmd", required=True)
    p = billing.add_parser("info"); p.add_argument("--project", required=True)

    return ap


def main():
    args = build_parser().parse_args()
    client_id = os.environ.get("GCLOUD_CLIENT_ID")
    client_secret = os.environ.get("GCLOUD_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit("Defina GCLOUD_CLIENT_ID e GCLOUD_CLIENT_SECRET.")

    if args.cmd == "authorize":
        authorize(client_id, client_secret)
        return

    token = get_access_token(client_id, client_secret)

    dispatch = {
        "whoami": cmd_whoami,
        ("projects", "list"): cmd_projects_list,
        ("vms", "list"): cmd_vms_list,
        ("billing", "info"): cmd_billing_info,
    }

    if args.cmd == "projects":
        fn = dispatch[("projects", args.pj_cmd)]
    elif args.cmd == "vms":
        fn = dispatch[("vms", args.vms_cmd)]
    elif args.cmd == "billing":
        fn = dispatch[("billing", args.billing_cmd)]
    else:
        fn = dispatch[args.cmd]

    fn(token, args)


if __name__ == "__main__":
    sys.exit(main())
