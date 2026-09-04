#!/bin/sh
# Quando o container é recriado (redeploy, restart), o Chromium não sai de
# forma limpa e deixa arquivos de trava de instância única na sessão
# persistida (volume wwebjs_auth). Sem isso, o próximo Chromium se recusa a
# abrir achando que outro processo ainda está usando o profile.
find /app/.wwebjs_auth -iname 'Singleton*' -delete 2>/dev/null

exec "$@"
