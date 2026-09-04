const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');

const PYTHON_WEBHOOK_URL = process.env.PYTHON_WEBHOOK_URL;
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY;

// LocalAuth salva a sessão em disco (./.wwebjs_auth) para não precisar
// escanear o QR code toda vez que o processo reiniciar.
const client = new Client({
  authStrategy: new LocalAuth(),
  puppeteer: {
    headless: true,
    // Em produção (Docker) usamos o Chromium do sistema em vez do que o
    // Puppeteer baixaria sozinho — ver PUPPETEER_EXECUTABLE_PATH no
    // Dockerfile. Localmente (sem essa env var) cai no Chromium que o
    // Puppeteer já baixa via npm install.
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      // Container costuma limitar /dev/shm a 64MB, pouco pro Chromium —
      // sem essa flag ele trava/crasha aleatoriamente rodando em Docker.
      '--disable-dev-shm-usage',
    ]
  }
});

client.on('qr', (qr) => {
  console.log('Escaneie o QR code abaixo com o WhatsApp do número do bot:');
  qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
  console.log('[glicai-bridge] WhatsApp conectado e pronto.');
});

client.on('auth_failure', (msg) => {
  console.error('[glicai-bridge] Falha na autenticação:', msg);
});

client.on('disconnected', (reason) => {
  console.warn('[glicai-bridge] Desconectado:', reason, '— encerrando pra o Docker reiniciar o container.');
  // Mais confiável reiniciar o processo inteiro (Puppeteer novo, conexão
  // nova) do que tentar recuperar a sessão em memória. O restart_policy do
  // docker-compose (unless-stopped) sobe o container de novo automaticamente.
  process.exit(1);
});

// Toda mensagem recebida é repassada pro backend Python, que decide o que fazer.
client.on('message', async (message) => {
  // Ignora mensagens de grupos por enquanto — o GlicAI é 1:1 com o paciente.
  if (message.from.endsWith('@g.us')) return;

  try {
    await axios.post(
      PYTHON_WEBHOOK_URL,
      {
        telefone: message.from,       // formato: 5545999999999@c.us
        mensagem: message.body,
        timestamp: message.timestamp
      },
      {
        headers: { 'x-internal-api-key': INTERNAL_API_KEY },
        // O Python só responde esse POST depois de já ter mandado a resposta
        // de volta pro paciente (webhook.py chama enviar_mensagem antes de
        // retornar) — e enviar_mensagem agora inclui os 5-10s de "digitando"
        // simulado. Timeout maior que o teto do lado Python (ver
        // whatsapp_sender.py) pra estourar lá primeiro, com erro mais claro.
        timeout: 45000
      }
    );
  } catch (err) {
    console.error('[glicai-bridge] Erro ao processar mensagem recebida:', err.message);
  }
});

// Retry curto pra um bug conhecido e ainda sem correção do whatsapp-web.js
// (WhatsApp Web removeu uma função interna que a lib usa — ver
// https://github.com/wwebjs/whatsapp-web.js/issues/201761): de vez em quando
// client.sendMessage() quebra com "canCheckStatusRankingPosterGating is not
// a function" mesmo com o cliente conectado e pronto. É intermitente (nunca
// se repete 2x seguidas nos logs), então uma nova tentativa depois de uma
// pequena espera resolve a maioria dos casos. Só 1 retry, de propósito: não
// dá pra confirmar que a mensagem nunca chega a ser entregue antes do erro
// estourar, então mais tentativas aumentariam o risco de duplicar mensagem
// (pior pra um bot de alerta clínico do que raramente perder uma).
async function _enviarComRetry(fn) {
  try {
    return await fn();
  } catch (err) {
    console.warn('[glicai-bridge] Envio falhou, tentando novamente em 5s:', err.message);
    await new Promise((resolve) => setTimeout(resolve, 5000));
    return await fn();
  }
}

const DIGITANDO_MIN_MS = 5000;
const DIGITANDO_MAX_MS = 10000;

// Mostra "digitando..." no chat por alguns segundos antes de mandar a
// mensagem — só pra humanizar (uma resposta instantânea de bot é o que mais
// entrega que é automação). Duração aleatória entre 5-10s, não um valor
// fixo, pelo mesmo motivo. Falha em mostrar o indicador nunca deve impedir
// o envio de verdade — só loga e segue.
async function _simularDigitando(telefone) {
  try {
    const chat = await client.getChatById(telefone);
    await chat.sendStateTyping();
  } catch (err) {
    console.warn('[glicai-bridge] Falha ao simular "digitando":', err.message);
  }
  const esperaMs = DIGITANDO_MIN_MS + Math.random() * (DIGITANDO_MAX_MS - DIGITANDO_MIN_MS);
  await new Promise((resolve) => setTimeout(resolve, esperaMs));
}

// Usado pelo backend Python pra enviar mensagens (respostas, lembretes, alertas).
// "telefone" é sempre o JID completo original (@c.us ou @lid) — nunca reconstruído
// a partir só do número, contas @lid não são endereçáveis via @c.us (e vice-versa).
async function enviarMensagem(telefone, texto) {
  await _simularDigitando(telefone);
  await _enviarComRetry(() => client.sendMessage(telefone, texto));
}

// Usado pelo backend Python pra mandar arquivos (ex: PDF de exportação).
async function enviarArquivo(telefone, nomeArquivo, mimetype, conteudoBase64) {
  await _simularDigitando(telefone);
  const media = new MessageMedia(mimetype, conteudoBase64, nomeArquivo);
  await _enviarComRetry(() => client.sendMessage(telefone, media, { sendMediaAsDocument: true }));
}

module.exports = { client, enviarMensagem, enviarArquivo };
