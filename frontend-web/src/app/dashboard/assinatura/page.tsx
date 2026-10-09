"use client";

import { useEffect, useState } from "react";
import { BadgeCheck, Check, CreditCard, FileText, Receipt, Sparkles, TriangleAlert } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { DadosPagamento, Plano } from "@/lib/types";
import { Button, Card, CardTitulo, ErrorText, PageHeader, Skeleton } from "@/components/ui";
import { FormularioCartao, FormularioTrocaCartao } from "@/components/formulario-cartao";

const BENEFICIOS = [
  "Registros de glicemia ilimitados no WhatsApp",
  "Lembretes de basal, medições e remedição",
  "Relatórios, gráficos e PDF para o médico",
  "Cancele quando quiser",
];

function formatarData(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
}

export default function AssinaturaPage() {
  const [plano, setPlano] = useState<Plano | null>(null);
  const [erro, setErro] = useState("");
  const [recemAssinou, setRecemAssinou] = useState(false);

  useEffect(() => {
    api
      .plano()
      .then(setPlano)
      .catch(() => setErro("Não consegui carregar sua assinatura agora. Tente de novo em instantes."));
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader titulo="Assinatura" descricao="Seu plano e pagamento." />

      {recemAssinou && (
        <div className="flex items-start gap-3 rounded-2xl border border-verde/30 bg-verde/10 px-5 py-4 text-sm">
          <BadgeCheck size={20} className="mt-0.5 shrink-0 text-verde" />
          <p>
            <span className="font-semibold">Pagamento confirmado!</span> O GlicAI Pro já está liberado: registros
            ilimitados e lembretes de volta.
          </p>
        </div>
      )}

      <ErrorText>{erro}</ErrorText>

      {!plano && !erro && <Skeleton className="h-[420px] max-w-2xl" />}

      {plano?.plano === "pro" && <CartaoPro plano={plano} aoAtualizar={setPlano} />}

      {plano && plano.tem_cliente_stripe && (
        <PagamentoEFaturas plano={plano} podeTrocarCartao={plano.plano === "pro" && !plano.cortesia} />
      )}

      {plano && plano.plano !== "pro" && (
        <Card className="w-full max-w-2xl border-primary/30">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-heading text-base font-bold text-primary">GlicAI Pro</p>
            {plano.plano === "trial" ? (
              <span className="rounded-full bg-accent/15 px-3 py-1 text-xs font-semibold text-accent">
                Teste grátis: {plano.dias_restantes_teste === 1 ? "termina hoje" : `${plano.dias_restantes_teste} dias restantes`}
              </span>
            ) : (
              <span className="rounded-full bg-surface px-3 py-1 text-xs font-semibold text-muted">
                Você está no plano gratuito
              </span>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
            <p className="font-heading text-5xl font-extrabold tracking-tight">
              R$ 9,90<span className="text-lg font-medium text-muted"> /mês</span>
            </p>
            <p className="flex items-center gap-1.5 pb-1.5 text-sm text-muted">
              <CreditCard size={15} /> Por pessoa. Cartão de crédito.
            </p>
          </div>

          <ul className="mt-6 flex flex-col gap-2.5 text-[15px]">
            {BENEFICIOS.map((b) => (
              <li key={b} className="flex items-start gap-2.5">
                <Check size={18} className="mt-0.5 shrink-0 text-primary" />
                {b}
              </li>
            ))}
          </ul>

          <div className="mt-7 border-t border-border pt-7">
            {plano.pagamentos_disponiveis && plano.publishable_key ? (
              <FormularioCartao
                publishableKey={plano.publishable_key}
                preco="R$ 9,90/mês"
                aoConcluir={(novo) => {
                  setPlano(novo);
                  setRecemAssinou(true);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              />
            ) : (
              <p className="flex items-center gap-2 text-sm text-muted">
                <TriangleAlert size={16} /> Pagamentos indisponíveis no momento.
              </p>
            )}
          </div>

          <div className="mt-6 flex flex-col gap-2 text-xs leading-relaxed text-muted">
            {plano.plano === "trial" && (
              <p>Seu teste grátis termina em {formatarData(plano.teste_termina_em)}. A assinatura começa assim que você pagar.</p>
            )}
            <p>
              Os dados do cartão vão direto para o Stripe, dentro dos campos acima: o nosso servidor nunca vê o número do
              cartão. A cobrança é mensal e você cancela quando quiser, aqui mesmo.
            </p>
            <p>Seus dados de pagamento ficam com o Stripe. Aqui guardamos só o status da assinatura.</p>
          </div>
        </Card>
      )}
    </div>
  );
}

function CartaoPro({ plano, aoAtualizar }: { plano: Plano; aoAtualizar: (p: Plano) => void }) {
  const [confirmando, setConfirmando] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");

  const detalhe = plano.cortesia
    ? "Cortesia — tudo liberado."
    : plano.assinatura_status === "past_due"
      ? "Não conseguimos cobrar sua última fatura. Atualize o cartão para não perder o acesso."
      : plano.cancela_no_fim
        ? `Cancelamento agendado — você tem acesso até ${formatarData(plano.renova_em)}.`
        : plano.renova_em
          ? `Renova em ${formatarData(plano.renova_em)} · ${plano.preco}`
          : plano.preco;

  async function alterar(cancelar: boolean) {
    setErro("");
    setOcupado(true);
    try {
      aoAtualizar(cancelar ? await api.cancelarAssinatura() : await api.reativarAssinatura());
      setConfirmando(false);
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui concluir agora. Tente de novo.");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <Card className="w-full max-w-2xl border-primary/30">
      <div className="flex items-start gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-accent text-white">
          <Sparkles size={20} />
        </span>
        <div>
          <p className="font-heading text-xl font-bold">GlicAI Pro</p>
          <p className="mt-0.5 text-sm text-muted">{detalhe}</p>
        </div>
      </div>

      <ul className="mt-6 flex flex-col gap-2.5 border-t border-border pt-6 text-[15px]">
        {BENEFICIOS.map((b) => (
          <li key={b} className="flex items-start gap-2.5">
            <Check size={18} className="mt-0.5 shrink-0 text-primary" />
            {b}
          </li>
        ))}
      </ul>

      {!plano.cortesia && (
        <div className="mt-6 border-t border-border pt-6">
          {plano.cancela_no_fim ? (
            <div className="flex flex-col gap-4">
              <p className="text-sm leading-relaxed text-muted">
                Você não será mais cobrado. Depois de {formatarData(plano.renova_em)}, sua conta volta para o plano gratuito
                (1 medição por dia e sem lembretes). Mudou de ideia? Dá para reativar até lá, sem perder nada.
              </p>
              <Button onClick={() => alterar(false)} carregando={ocupado} className="w-full sm:w-auto sm:self-start">
                Reativar assinatura
              </Button>
            </div>
          ) : confirmando ? (
            <div className="rounded-xl border border-vermelho/25 bg-vermelho/[0.06] p-4">
              <p className="font-heading text-base font-bold">Cancelar o GlicAI Pro?</p>
              <p className="mt-2 text-sm leading-relaxed text-foreground/85">
                Você continua com tudo liberado até <span className="font-semibold">{formatarData(plano.renova_em)}</span> e
                não será cobrado de novo. Depois disso, a conta volta para o plano gratuito: 1 medição por dia e sem
                lembretes.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button variant="perigo" onClick={() => alterar(true)} carregando={ocupado}>
                  Sim, cancelar assinatura
                </Button>
                <Button variant="ghost" onClick={() => setConfirmando(false)} disabled={ocupado}>
                  Manter assinatura
                </Button>
              </div>
            </div>
          ) : (
            <Button variant="ghost" onClick={() => setConfirmando(true)}>
              Cancelar assinatura
            </Button>
          )}

          <div className="mt-3">
            <ErrorText>{erro}</ErrorText>
          </div>
        </div>
      )}
    </Card>
  );
}

const MARCAS: Record<string, string> = {
  visa: "Visa",
  mastercard: "Mastercard",
  amex: "American Express",
  elo: "Elo",
  diners: "Diners",
  discover: "Discover",
  hipercard: "Hipercard",
};

const STATUS_FATURA: Record<string, { rotulo: string; cor: string }> = {
  paga: { rotulo: "Paga", cor: "text-verde bg-verde/10" },
  em_aberto: { rotulo: "Em aberto", cor: "text-accent bg-accent/15" },
  nao_paga: { rotulo: "Não paga", cor: "text-vermelho bg-vermelho/10" },
  cancelada: { rotulo: "Cancelada", cor: "text-muted bg-surface" },
  outra: { rotulo: "—", cor: "text-muted bg-surface" },
};

function PagamentoEFaturas({ plano, podeTrocarCartao }: { plano: Plano; podeTrocarCartao: boolean }) {
  const [dados, setDados] = useState<DadosPagamento | null>(null);
  const [falhou, setFalhou] = useState(false);
  const [trocando, setTrocando] = useState(false);
  const [aviso, setAviso] = useState("");

  useEffect(() => {
    api
      .dadosPagamento()
      .then(setDados)
      .catch(() => setFalhou(true));
  }, []);

  async function recarregar() {
    setDados(await api.dadosPagamento().catch(() => dados));
  }

  if (falhou) return null;
  if (!dados) return <Skeleton className="h-[160px] max-w-2xl" />;

  const cartao = dados.cartao;
  const marca = cartao?.marca ? (MARCAS[cartao.marca] ?? cartao.marca) : "Cartão";

  return (
    <>
      {(cartao || podeTrocarCartao) && (
        <Card className="w-full max-w-2xl">
          <CardTitulo icone={<CreditCard size={18} />} titulo="Forma de pagamento" descricao="Cartão usado nas cobranças mensais." />

          {cartao && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border px-4 py-3.5">
              <div>
                <p className="font-semibold">
                  {marca} •••• {cartao.final}
                </p>
                {cartao.mes && cartao.ano && (
                  <p className="text-xs text-muted">
                    Vence em {String(cartao.mes).padStart(2, "0")}/{cartao.ano}
                  </p>
                )}
              </div>
              {podeTrocarCartao && !trocando && (
                <Button
                  variant="ghost"
                  onClick={() => {
                    setAviso("");
                    setTrocando(true);
                  }}
                >
                  Trocar cartão
                </Button>
              )}
            </div>
          )}

          {aviso && <p className="mt-4 rounded-xl border border-verde/30 bg-verde/10 px-3.5 py-2.5 text-sm">{aviso}</p>}

          {trocando && plano.publishable_key && (
            <div className="mt-5 border-t border-border pt-5">
              <p className="mb-4 text-sm text-muted">
                Digite o novo cartão. Ele passa a valer para as próximas cobranças e o cartão antigo é removido.
              </p>
              <FormularioTrocaCartao
                publishableKey={plano.publishable_key}
                aoCancelar={() => setTrocando(false)}
                aoConcluir={() => {
                  setTrocando(false);
                  setAviso("Cartão atualizado com sucesso.");
                  recarregar();
                }}
              />
            </div>
          )}
        </Card>
      )}

      <Card className="w-full max-w-2xl p-0">
        <div className="px-6 pt-6">
          <CardTitulo icone={<Receipt size={18} />} titulo="Faturas" descricao="Seu histórico de cobranças." />
        </div>
        {dados.faturas.length === 0 ? (
          <p className="px-6 pb-6 text-sm text-muted">Nenhuma fatura ainda.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-y border-border text-left text-xs font-medium text-muted">
                  <th className="px-6 py-3 font-medium">Data</th>
                  <th className="px-4 py-3 font-medium">Valor</th>
                  <th className="px-4 py-3 font-medium">Situação</th>
                  <th className="px-6 py-3 text-right font-medium">Comprovante</th>
                </tr>
              </thead>
              <tbody>
                {dados.faturas.map((f) => {
                  const st = STATUS_FATURA[f.status] ?? STATUS_FATURA.outra;
                  const link = f.pdf ?? f.url;
                  return (
                    <tr key={f.id} className="border-b border-border last:border-0">
                      <td className="whitespace-nowrap px-6 py-3">{formatarData(f.data)}</td>
                      <td className="whitespace-nowrap px-4 py-3 font-medium">
                        {f.valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${st.cor}`}>{st.rotulo}</span>
                      </td>
                      <td className="px-6 py-3 text-right">
                        {link ? (
                          <a
                            href={link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 font-medium text-primary hover:underline"
                          >
                            <FileText size={14} /> PDF
                          </a>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
