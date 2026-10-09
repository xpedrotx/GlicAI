#!/usr/bin/env bash
# Configura a chave do Resend (envio de e-mail) no servidor de producao.
#
# Uso (Git Bash, na raiz do repo):
#   bash scripts/configurar-resend.sh
#
# Pergunta a chave com a digitacao oculta, grava em backend-python/.env no
# servidor (por SSH, mandando o valor pela entrada padrao: nunca aparece na
# lista de processos nem no historico do shell), reinicia o backend e confere
# se o Resend aceita a chave.
#
# Como criar a chave: https://resend.com/api-keys > "Create API Key"
#   - Name: glicai    - Permission: Sending access    - Domain: pedrotx.com.br
# O Resend mostra o valor (re_...) UMA vez so: copie na hora.
set -euo pipefail

SERVIDOR="${GLICAI_SERVIDOR:-root@179.199.154.194}"
PASTA="${GLICAI_PASTA:-/root/glic.ia}"

# Roda no servidor: le linhas CHAVE=VALOR da entrada padrao e grava/substitui no .env.
read -r -d '' REMOTO <<'EOF' || true
set -e
f="${ENV_FILE:?}"
[ -f "$f" ] || { echo "nao achei $f" >&2; exit 1; }
cp "$f" "$f.bak"; chmod 600 "$f.bak"
if [ -n "$(tail -c1 "$f")" ]; then echo >> "$f"; fi
while IFS= read -r linha; do
  [ -n "$linha" ] || continue
  chave="${linha%%=*}"
  sed -i "/^${chave}=/d" "$f"
  printf '%s\n' "$linha" >> "$f"
done
chmod 600 "$f"
EOF

if [ "${1:-}" = "--aplicar-local" ]; then
  bash -c "$REMOTO"   # uso interno dos testes: mesma logica num arquivo local
  exit 0
fi

echo "Chave do Resend -> $SERVIDOR (a digitacao fica oculta)"
read -r -s -p "Chave (re_...): " chave; echo
chave="$(printf '%s' "$chave" | tr -d '[:space:]')"
if [[ ! "$chave" =~ ^re_[A-Za-z0-9_]{20,}$ ]]; then
  echo "Isso nao parece uma chave do Resend (deve comecar com re_). Nada foi alterado." >&2
  exit 1
fi

echo "Gravando no servidor..."
printf 'RESEND_API_KEY=%s\n' "$chave" | ssh -o BatchMode=yes "$SERVIDOR" "ENV_FILE='$PASTA/backend-python/.env' bash -c $(printf '%q' "$REMOTO")"

echo "Reiniciando o backend..."
ssh -o BatchMode=yes "$SERVIDOR" "cd '$PASTA' && docker compose up -d --force-recreate backend-python 2>&1 | tail -1"
sleep 6

# 401 = chave invalida. Chave so de envio nao pode listar dominios e responde 403,
# o que tambem prova que a chave existe e e valida.
codigo=$(ssh -o BatchMode=yes "$SERVIDOR" "cd '$PASTA' && docker compose exec -T backend-python python -c \"
import httpx
from app.config import settings
print(httpx.get('https://api.resend.com/domains', headers={'Authorization': 'Bearer ' + settings.resend_api_key}, timeout=10).status_code)
\"" | tail -1)
case "$codigo" in
  200|403) echo "OK: o Resend aceitou a chave (HTTP $codigo). O cadastro de medico ja pode enviar o codigo por e-mail." ;;
  401)     echo "O Resend AINDA recusa a chave (401). Confira se copiou inteira e se nao foi apagada." >&2; exit 1 ;;
  *)       echo "Resposta inesperada do Resend: $codigo" >&2; exit 1 ;;
esac
