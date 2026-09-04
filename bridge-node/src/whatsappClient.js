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
        timeout: 20000
      }
    );
  } catch (err) {
    console.error('[glicai-bridge] Erro ao processar mensagem recebida:', err.message);
  }
});

// Usado pelo backend Python pra enviar mensagens (respostas, lembretes, alertas).
// "telefone" é sempre o JID completo original (@c.us ou @lid) — nunca reconstruído
// a partir só do número, contas @lid não são endereçáveis via @c.us (e vice-versa).
async function enviarMensagem(telefone, texto) {
  await client.sendMessage(telefone, texto);
}

// Usado pelo backend Python pra mandar arquivos (ex: PDF de exportação).
async function enviarArquivo(telefone, nomeArquivo, mimetype, conteudoBase64) {
  const media = new MessageMedia(mimetype, conteudoBase64, nomeArquivo);
  await client.sendMessage(telefone, media, { sendMediaAsDocument: true });
}

module.exports = { client, enviarMensagem, enviarArquivo };
