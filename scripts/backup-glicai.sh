#!/usr/bin/env bash
# Backup diario do GlicAI (roda no servidor, via cron as 04:00).
#
# Guarda em /root/backups/glicai (so root le), mantendo os ultimos 7 dias:
#   - wwebjs_auth_<data>.tgz : sessao do WhatsApp (sem os caches do Chromium)
#   - config_<data>.tgz      : .env do backend e do bridge, compose e Caddyfile
#
# Os dados dos pacientes ficam no Supabase, NAO neste servidor -- este backup
# nao os cobre.
#
# Restaurar a sessao do WhatsApp (com o bridge parado):
#   docker compose stop bridge-node
#   docker run --rm -i -v glicia_wwebjs_auth:/v alpine sh -c 'rm -rf /v/* /v/.[!.]*'
#   docker run --rm -i -v glicia_wwebjs_auth:/v alpine tar xzf - --numeric-owner -C /v < wwebjs_auth_<data>.tgz
#   docker compose start bridge-node
#
# Instalar (uma vez):
#   install -m 700 scripts/backup-glicai.sh /root/backup-glicai.sh
#   (crontab -l 2>/dev/null; echo '0 4 * * * /root/backup-glicai.sh >> /var/log/backup-glicai.log 2>&1') | crontab -
set -uo pipefail

PROJETO="${GLICAI_PASTA:-/root/glic.ia}"
DESTINO="${GLICAI_BACKUPS:-/root/backups/glicai}"
DIAS_GUARDADOS=7
DATA="$(date +%Y%m%d_%H%M)"

mkdir -p "$DESTINO"
chmod 700 "$DESTINO"
umask 077
erros=0

conferir() {  # conferir arquivo -- existe, nao esta vazio e o tar le inteiro
  if [ -s "$1" ] && tar tzf "$1" >/dev/null 2>&1; then
    echo "ok   $(basename "$1")  $(du -h "$1" | cut -f1)"
  else
    echo "FALHA $(basename "$1")" >&2
    rm -f "$1"
    erros=$((erros + 1))
  fi
}

echo "== backup GlicAI $DATA"

# Sessao do WhatsApp. Copia com o bot rodando (sem derrubar o atendimento); os
# caches do Chromium ficam de fora -- so engordam o arquivo.
docker run --rm -v glicia_wwebjs_auth:/v:ro alpine tar czf - --numeric-owner \
  --exclude='*/Cache' --exclude='*/Code Cache' --exclude='*/GPUCache' \
  --exclude='*/Service Worker/CacheStorage' -C /v . > "$DESTINO/wwebjs_auth_$DATA.tgz"
conferir "$DESTINO/wwebjs_auth_$DATA.tgz"

# Configuracao e segredos
tar czf "$DESTINO/config_$DATA.tgz" -C "$(dirname "$PROJETO")" \
  "$(basename "$PROJETO")/backend-python/.env" "$(basename "$PROJETO")/bridge-node/.env" \
  "$(basename "$PROJETO")/Caddyfile" "$(basename "$PROJETO")/docker-compose.yml"
conferir "$DESTINO/config_$DATA.tgz"

# Retencao: so apaga os antigos se os de hoje deram certo
if [ "$erros" -eq 0 ]; then
  find "$DESTINO" -name '*.tgz' -mtime +"$DIAS_GUARDADOS" -print -delete | sed 's/^/apagado /'
else
  echo "Houve falhas: backups antigos mantidos." >&2
fi

echo "guardados: $(ls "$DESTINO"/*.tgz | wc -l) arquivos, $(du -sh "$DESTINO" | cut -f1)"
exit "$erros"
