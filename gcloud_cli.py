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
    vms create NOME --project ID --yes [opcoes]
                                     cria VM (custo real) -- confirma imagem
                                     Ubuntu contra a API, gera chave SSH,
                                     instala Claude Code/Ollama/Codex/Antigravity
                                     no boot. --yes obrigatorio.
    images list-ubuntu              familias Ubuntu disponiveis agora (checar
                                     antes de usar --image-family)
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
    # full cloud-platform (nao mais read-only): criar VM e escrita, nao leitura
    "https://www.googleapis.com/auth/cloud-platform",
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


def api(method, url, token, query=None, body=None):
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {token}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
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


def cmd_images_list_ubuntu(token, args):
    """Lista as familias de imagem Ubuntu realmente disponiveis agora no
    projeto ubuntu-os-cloud -- checar aqui antes de criar VM evita usar
    um nome de familia (ex.: ubuntu-2604-lts) que ainda nao existe."""
    d = api("GET", "https://compute.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images",
             token, query={"maxResults": 500,
                            "filter": "deprecated.state != DEPRECATED AND name : ubuntu*"})
    fams = sorted({img.get("family") for img in d.get("items", []) if img.get("family")})
    if not fams:
        print("Nenhuma imagem Ubuntu encontrada (inesperado -- verifique a API).")
        return
    for f in fams:
        print(f"  {f}")
    print(f"\n{len(fams)} familias Ubuntu disponiveis agora.")


_STARTUP_SCRIPT_TEMPLATE = """#!/bin/bash
set -e
exec > /var/log/startup-script-tools.log 2>&1
echo "=== inicio $(date) ==="

apt-get update
apt-get install -y curl git build-essential ca-certificates

# a conta {username} e criada pelo guest agent ao processar a chave SSH,
# mas isso e assincrono em relacao ao startup-script -- espera existir
for i in $(seq 1 30); do
    id {username} >/dev/null 2>&1 && break
    sleep 2
done

# Ollama roda como servico de sistema, instala como root
curl -fsSL https://ollama.com/install.sh | sh

# ferramentas de agente sao por usuario (~/.local/bin), roda como {username}
su - {username} -c 'curl -fsSL https://claude.ai/install.sh | bash'
su - {username} -c 'curl -fsSL https://chatgpt.com/codex/install.sh | sh'
su - {username} -c 'curl -fsSL https://antigravity.google/cli/install.sh | bash'

echo "=== fim $(date) ==="
"""


def cmd_vms_create(token, args):
    """Cria uma VM. Custo real e continuo se nao for a e2-micro do Always
    Free -- por isso exige --yes com o valor estimado already visto pelo
    usuario, e sempre confirma a familia de imagem contra a API antes de
    criar (nunca assume que ubuntu-2604-lts existe sem checar)."""
    import subprocess
    import tempfile

    if not args.yes:
        raise SystemExit(
            "Isso cria uma VM de verdade, com custo cobrado na conta enquanto "
            "ela ficar ligada. Rode de novo com --yes para confirmar."
        )

    # confirma que a familia de imagem pedida existe de verdade
    d = api("GET", "https://compute.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images",
             token, query={"maxResults": 500, "filter": "deprecated.state != DEPRECATED"})
    fams = {img.get("family") for img in d.get("items", []) if img.get("family")}
    if args.image_family not in fams:
        raise SystemExit(
            f"Familia '{args.image_family}' nao existe no projeto ubuntu-os-cloud agora.\n"
            f"Rode 'images list-ubuntu' para ver as disponiveis."
        )

    import shutil
    if shutil.which("ssh-keygen") is None:
        raise SystemExit(
            "ssh-keygen nao encontrado. Instale com:\n"
            "  apt-get install -y openssh-client"
        )

    ssh_dir = os.path.expanduser("~/.config/gcloud-cli/ssh")
    os.makedirs(ssh_dir, exist_ok=True)
    key_path = os.path.join(ssh_dir, f"{args.name}_ed25519")
    if not os.path.exists(key_path):
        subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", key_path,
                        "-C", args.username], check=True, capture_output=True)
    with open(key_path + ".pub") as f:
        pubkey = f.read().strip()

    startup_script = _STARTUP_SCRIPT_TEMPLATE.format(username=args.username)

    body = {
        "name": args.name,
        "machineType": f"zones/{args.zone}/machineTypes/{args.machine_type}",
        "disks": [{
            "boot": True,
            "autoDelete": True,
            "initializeParams": {
                "sourceImage": f"projects/ubuntu-os-cloud/global/images/family/{args.image_family}",
                "diskSizeGb": str(args.disk_size),
            },
        }],
        "networkInterfaces": [{
            "network": "global/networks/default",
            "accessConfigs": [{"type": "ONE_TO_ONE_NAT", "name": "External NAT"}],
        }],
        "metadata": {"items": [
            {"key": "ssh-keys", "value": f"{args.username}:{pubkey}"},
            {"key": "startup-script", "value": startup_script},
        ]},
        "tags": {"items": ["ssh"]},
    }

    d = api("POST", f"https://compute.googleapis.com/compute/v1/projects/{args.project}/zones/{args.zone}/instances",
             token, body=body)
    print(f"Criando '{args.name}' -- operacao: {d.get('name')}")
    print(f"Status: {d.get('status')}")
    print()
    print(f"Chave privada SSH: {key_path}")
    print(f"Depois que a VM tiver um IP externo (veja com 'vms list'):")
    print(f"  ssh -i {key_path} {args.username}@<IP_EXTERNO>")
    print()
    print("As ferramentas (Claude Code, Ollama, Codex CLI, Antigravity CLI) sao")
    print("instaladas pelo startup-script no primeiro boot -- leva alguns minutos.")
    print(f"Log de instalacao dentro da VM: /var/log/startup-script-tools.log")


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("authorize")
    sub.add_parser("whoami")

    sub.add_parser("projects").add_subparsers(dest="pj_cmd", required=True).add_parser("list")

    vms = sub.add_parser("vms").add_subparsers(dest="vms_cmd", required=True)
    p = vms.add_parser("list"); p.add_argument("--project", help="ID do projeto (todos, se omitido)")
    p = vms.add_parser("create")
    p.add_argument("name")
    p.add_argument("--project", required=True)
    p.add_argument("--zone", default="us-central1-a")
    p.add_argument("--machine-type", default="e2-micro")
    p.add_argument("--image-family", default="ubuntu-2604-lts")
    p.add_argument("--disk-size", type=int, default=30, help="GB")
    p.add_argument("--username", default="douglas")
    p.add_argument("--yes", action="store_true", help="confirma a criacao (custo real) -- obrigatorio")

    billing = sub.add_parser("billing").add_subparsers(dest="billing_cmd", required=True)
    p = billing.add_parser("info"); p.add_argument("--project", required=True)

    sub.add_parser("images").add_subparsers(dest="img_cmd", required=True).add_parser("list-ubuntu")

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
        ("vms", "create"): cmd_vms_create,
        ("billing", "info"): cmd_billing_info,
        ("images", "list-ubuntu"): cmd_images_list_ubuntu,
    }

    if args.cmd == "projects":
        fn = dispatch[("projects", args.pj_cmd)]
    elif args.cmd == "vms":
        fn = dispatch[("vms", args.vms_cmd)]
    elif args.cmd == "billing":
        fn = dispatch[("billing", args.billing_cmd)]
    elif args.cmd == "images":
        fn = dispatch[("images", args.img_cmd)]
    else:
        fn = dispatch[args.cmd]

    fn(token, args)


if __name__ == "__main__":
    sys.exit(main())
