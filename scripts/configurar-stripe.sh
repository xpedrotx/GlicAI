#!/usr/bin/env bash
# Configura as chaves do Stripe no servidor de producao.
#
# Uso (Git Bash, na raiz do repo):
#   bash scripts/configurar-stripe.sh
#
# Pergunta cada chave com a digitacao oculta, grava em
# backend-python/.env no servidor (por SSH, mandando os valores pela entrada
# padrao: nunca aparecem na lista de processos nem no historico do shell) e
# reinicia o backend pra ler os valores novos. Deixar um campo vazio mantem o
# valor que ja esta no servidor.
#
# Onde pegar as chaves (modo teste primeiro, depois repete com as "live"):
#   - sk_ e pk_:  https://dashboard.stripe.com/apikeys
#   - whsec_:     Developers > Webhooks > criar endpoint
#                 https://glicia.pedrotx.com.br/api/stripe/webhook
#                 eventos: customer.subscription.created/updated/deleted,
#                 invoice.paid, invoice.payment_failed
set -euo pipefail

SERVIDOR="${GLICAI_SERVIDOR:-root@49.13.198.178}"
PASTA="${GLICAI_PASTA:-/root/glic.ia}"
SITE="${GLICAI_SITE:-https://glicia.pedrotx.com.br}"

# Roda no servidor: le linhas CHAVE=VALOR da entrada padrao e grava/substitui
# no .env. Separado do restart pra poder ser testado sem Docker.
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
  # uso interno dos testes: aplica a mesma logica num arquivo local
  bash -c "$REMOTO"
  exit 0
fi

pedir() {  # pedir NOME "descricao" prefixo_esperado [obrigatorio]
  local nome="$1" desc="$2" prefixo="$3" valor
  while true; do
    read -r -s -p "$desc (vazio = manter): " valor; echo
    valor="$(printf '%s' "$valor" | tr -d '[:space:]')"
    [ -z "$valor" ] && return 0
    if [[ "$valor" =~ ^($prefixo) ]]; then
      PARES+=("$nome=$valor"); return 0
    fi
    echo "  Isso nao parece uma chave valida (deve comecar com: ${prefixo//|/ ou }). Tenta de novo." >&2
  done
}

PARES=()
echo "Chaves do Stripe -> $SERVIDOR (a digitacao fica oculta)"
echo
pedir STRIPE_SECRET_KEY      "Chave secreta (sk_test_... ou sk_live_...)"          'sk_test_|sk_live_|rk_test_|rk_live_'
pedir STRIPE_PUBLISHABLE_KEY "Chave publicavel (pk_test_... ou pk_live_...)"        'pk_test_|pk_live_'
pedir STRIPE_WEBHOOK_SECRET  "Segredo do webhook (whsec_...)"                       'whsec_'
pedir STRIPE_PRICE_ID        "ID do preco (price_..., opcional: vazio cobra R\$ 9,90 direto)" 'price_'

if [ "${#PARES[@]}" -eq 0 ]; then
  echo "Nada informado, nada alterado."; exit 0
fi

# Avisa se misturou modo teste com modo real (a cobranca falharia)
modos=$(printf '%s\n' "${PARES[@]}" | grep -oE '(sk|pk|rk)_(test|live)_' | grep -oE 'test|live' | sort -u | wc -l)
if [ "$modos" -gt 1 ]; then
  echo "ATENCAO: misturou chaves de teste e de producao (live). Nao vai funcionar." >&2
  read -r -p "Continuar mesmo assim? [s/N] " r; [[ "$r" =~ ^[sS]$ ]] || exit 1
fi

echo
echo "Gravando no servidor: $(printf '%s\n' "${PARES[@]}" | cut -d= -f1 | paste -sd' ' -)"
printf '%s\n' "${PARES[@]}" | ssh -o BatchMode=yes "$SERVIDOR" "ENV_FILE='$PASTA/backend-python/.env' bash -c $(printf '%q' "$REMOTO")"

echo "Reiniciando o backend..."
ssh -o BatchMode=yes "$SERVIDOR" "cd '$PASTA' && docker compose up -d --force-recreate backend-python 2>&1 | tail -1"
sleep 6

# Sem segredo o webhook responde 503; configurado, recusa a chamada sem
# assinatura com 400 -- prova que o backend leu o valor novo.
codigo=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$SITE/api/stripe/webhook" || true)
case "$codigo" in
  400) echo "OK: backend no ar e webhook do Stripe configurado." ;;
  503) echo "Backend no ar, mas o segredo do webhook (whsec_) ainda nao esta configurado." ;;
  *)   echo "Backend respondeu $codigo no webhook -- confira: docker logs glicia-backend-python-1" ;;
esac
