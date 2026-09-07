# GlicAI

Assistente de diabetes tipo 1 pelo WhatsApp. Registra glicemia, calcula dose
de bolus, avisa a família quando algo sai da faixa e mantém um histórico
completo — tudo por mensagem de texto, sem app pra instalar.

## Como usar

Manda uma mensagem pro número do bot no WhatsApp — **(44) 92006-0455** — e
segue o cadastro guiado (nome, metas de glicemia, fator de sensibilidade,
relação insulina:carboidrato, basal). Depois disso, pode falar do seu jeito
— tipo *"minha glicose deu 110 em jejum"* ou *"tomei 4 unidades"* — que o
bot entende (usa IA só pra traduzir a frase pro comando certo; quem calcula
dose e registra dado continua sendo sempre o mesmo código determinístico).
Ações que só leem informação (perfil, relatório etc) já respondem na hora;
qualquer coisa que grava dado clínico ou é irreversível (glicemia, dose,
excluir conta) sempre pede confirmação explícita antes.

Se preferir os comandos certinhos, também funcionam:

- `glicemia <valor> [contexto]` — registra uma medição (contexto opcional:
  `jejum`, `pre_refeicao`, `pos_prandial`, `correcao`; mandar só o número
  também funciona). Avisa automaticamente se estiver fora da faixa e já
  sugere a dose de correção quando alta.
- `bolus <carboidratos_g> <glicemia_atual>` — calcula a dose pra uma
  refeição (relação IC do período + correção + modificadores ativos).
- `apliquei <dose> [horario]` — registra a dose que você de fato aplicou
  (esqueceu de avisar na hora? manda o horário junto: `apliquei 6u 12:20`).
- `tratei` — confirma que tratou uma hipoglicemia.
- `perfil` / `basal` — mostra os dados cadastrados.
- `editar <campo> <valor>` — ajusta meta, limites, fator ou nome sem
  recadastrar.
- `modificador ativar/desativar <nome>` — liga/desliga um modificador de
  bolus (ex: exercício físico).
- `tempo_insulina_ativa <horas>` — configura o IOB (insulina ainda ativa no
  corpo), descontado automaticamente do cálculo de correção.
- `lembrete listar/adicionar/remover <horario>` — gerencia lembretes de
  medição.
- `relatorio semana/mes`, `hba1c [dias]`, `padroes [dias]` — resumos e
  estimativas a partir do histórico.
- `exportar [dias]` — manda um PDF do histórico, pra levar na consulta.
- `estoque` — controle de insulina e fitas de dextro, com desconto
  automático e aviso quando está acabando.
- `cuidador convidar/listar/remover <nome>` — convida alguém (esposa, mãe
  etc.) pra acompanhar sua glicemia.
- `criar senha` — gera acesso ao site de acompanhamento.
- `excluir conta` — apaga permanentemente todos os seus dados (pede confirmação antes).
- `ajuda` (ou `oi`) — lista todos os comandos.

### Monitoria familiar

Quando a glicemia vem fora da faixa, o bot sugere a correção (hiper) ou
pede confirmação de tratamento (hipo) e espera você confirmar
(`apliquei`/`tratei`). Sem confirmar em 5 min manda um lembrete pra você; em
mais 5 min (10 no total) avisa os cuidadores cadastrados que a leitura
estava crítica e não foi confirmada. Confirmando a qualquer momento, os
cuidadores recebem o aviso de que foi resolvido.

Pra adicionar um cuidador: manda `cuidador convidar`, repassa o código de 6
dígitos pra pessoa, e ela manda `vincular <código> <nome dela>` pro mesmo
número do bot.

**Limitação conhecida**: um número de telefone é *ou* paciente *ou*
cuidador, não os dois ao mesmo tempo.

### Site de acompanhamento

Além do WhatsApp, o histórico, gráfico de tendência, relatórios, perfil e
cuidadores/estoque também ficam disponíveis num painel web — o acesso
(CPF + senha) é criado a partir do comando `criar senha` no bot.

## Arquitetura

- **bridge-node/** — Node.js + `whatsapp-web.js`: conexão com o WhatsApp,
  repassa mensagens pro backend e expõe `/send` pras respostas.
- **backend-python/** — FastAPI: cadastro, cálculo de bolus, lembretes,
  alertas, relatórios, API do site. Fala com o Supabase (Postgres).
- **frontend-web/** — Next.js: painel de acompanhamento (login CPF/senha).

```
paciente (WhatsApp) <-> bridge-node <-> backend-python <-> Supabase
                                              ^
                                              |
                                        frontend-web
```

## Aviso importante

Este app **não substitui orientação médica**. Todos os parâmetros clínicos
(metas, fator de sensibilidade, relação insulina:carboidrato) devem ser
definidos pelo endocrinologista do paciente, nunca inventados ou ajustados
livremente pelo sistema — e a dose de insulina nunca é decidida por IA, só
por cálculo determinístico revisado pelo médico.

O `whatsapp-web.js` não é a API oficial do WhatsApp — ele automatiza o
WhatsApp Web mesmo, e isso carrega um risco (baixo, mas não nulo) de
banimento por automação.
