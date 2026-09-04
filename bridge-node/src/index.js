require('dotenv').config();
const express = require('express');
const { client, enviarMensagem, enviarArquivo } = require('./whatsappClient');

const PORT = process.env.PORT || 3000;
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY;

// Rede de segurança: o whatsapp-web.js roda em cima do puppeteer e volta e
// meia lança erros instáveis do próprio WhatsApp Web (ex: getChat() em chats
// novos). Sem isso, uma rejeição de Promise não tratada em qualquer lugar
// derruba o processo inteiro e todo mundo para de receber mensagens.
process.on('unhandledRejection', (err) => {
  console.error('[glicai-bridge] Rejeição de Promise não tratada:', err);
});

const app = express();
// Limite padrão do Express é 100kb — pequeno demais pra um PDF em base64
// (exportação de histórico, ver /send-arquivo).
app.use(express.json({ limit: '15mb' }));

// Middleware simples de autenticação entre backend Python <-> bridge Node.js
function checarChaveInterna(req, res, next) {
  if (req.headers['x-internal-api-key'] !== INTERNAL_API_KEY) {
    return res.status(401).json({ erro: 'Chave interna inválida' });
  }
  next();
}

// O backend Python chama este endpoint para enviar uma mensagem ao paciente
// (resposta a um comando, lembrete de medição, alerta de hipo/hiperglicemia, etc.)
app.post('/send', checarChaveInterna, async (req, res) => {
  const { telefone, mensagem } = req.body;

  if (!telefone || !mensagem) {
    return res.status(400).json({ erro: 'Campos "telefone" e "mensagem" são obrigatórios' });
  }

  try {
    await enviarMensagem(telefone, mensagem);
    res.json({ status: 'enviado' });
  } catch (err) {
    console.error('[glicai-bridge] Erro ao enviar mensagem:', err.message);
    res.status(500).json({ erro: 'Falha ao enviar mensagem via WhatsApp' });
  }
});

// O backend Python chama isso pra mandar um arquivo (ex: PDF de exportação
// do histórico) como documento no WhatsApp.
app.post('/send-arquivo', checarChaveInterna, async (req, res) => {
  const { telefone, nome_arquivo, mimetype, conteudo_base64 } = req.body;

  if (!telefone || !nome_arquivo || !mimetype || !conteudo_base64) {
    return res.status(400).json({
      erro: 'Campos "telefone", "nome_arquivo", "mimetype" e "conteudo_base64" são obrigatórios',
    });
  }

  try {
    await enviarArquivo(telefone, nome_arquivo, mimetype, conteudo_base64);
    res.json({ status: 'enviado' });
  } catch (err) {
    console.error('[glicai-bridge] Erro ao enviar arquivo:', err.message);
    res.status(500).json({ erro: 'Falha ao enviar arquivo via WhatsApp' });
  }
});

app.get('/health', (req, res) => res.json({ status: 'ok' }));

app.listen(PORT, () => {
  console.log(`[glicai-bridge] Servidor HTTP escutando na porta ${PORT}`);
});

client.initialize();
