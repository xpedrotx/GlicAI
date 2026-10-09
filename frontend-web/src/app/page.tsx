import Link from "next/link";
import {
  ArrowRight,
  BellRing,
  Calculator,
  ChartLine,
  ChevronRight,
  CircleCheck,
  Clock,
  FileText,
  Lock,
  MessageCircle,
  Package,
  ShieldCheck,
  Smartphone,
  Stethoscope,
  Users,
} from "lucide-react";
import { Logo } from "@/components/logo";
import { SiteHeader } from "@/components/landing/site-header";
import { PhoneMockup } from "@/components/landing/phone-mockup";
import { PainelPreview } from "@/components/landing/painel-preview";
import { ASSINAR_EXTERNO, LINK_ASSINAR } from "@/lib/site";

const propsAssinar = ASSINAR_EXTERNO ? { target: "_blank", rel: "noopener noreferrer" } : {};

const PASSOS = [
  {
    icone: MessageCircle,
    titulo: "Cadastro pela conversa",
    texto:
      "O GlicAI pergunta sua meta, fator de sensibilidade, relação insulina:carboidrato e horários de basal. Leva poucos minutos.",
  },
  {
    icone: Smartphone,
    titulo: "Fale do seu jeito",
    texto:
      "“tá 180”, “vou comer 40g”, “apliquei 6”. O GlicAI entende linguagem natural e confirma com você antes de registrar.",
  },
  {
    icone: ChartLine,
    titulo: "Acompanhe e compartilhe",
    texto:
      "Veja tendências no painel, gere o PDF para a consulta e deixe quem cuida de você por perto quando precisar.",
  },
];

const RECURSOS = [
  {
    icone: Calculator,
    titulo: "Cálculo de dose transparente",
    texto: "Carboidrato, correção e insulina ativa: a conta aparece inteira, para você conferir antes de aplicar.",
  },
  {
    icone: BellRing,
    titulo: "Alertas de hipo e hiper",
    texto: "Orientação imediata e lembrete para medir de novo — 15 minutos na hipo, 60 minutos na hiper.",
  },
  {
    icone: Clock,
    titulo: "Lembretes no seu horário",
    texto: "Basal e medições lembrados todos os dias, nos horários que você escolher.",
  },
  {
    icone: Users,
    titulo: "Cuidadores conectados",
    texto: "Pais, parceiros ou responsáveis recebem aviso quando a glicemia sai da faixa segura.",
  },
  {
    icone: FileText,
    titulo: "Relatórios e PDF",
    texto: "Média, tempo no alvo, estimativa de HbA1c e padrões por dia da semana — prontos para levar ao médico.",
  },
  {
    icone: Package,
    titulo: "Controle de insumos",
    texto: "Desconta insulina e fitas automaticamente a cada registro e avisa antes de acabar.",
  },
];

const SEGURANCA = [
  {
    icone: Stethoscope,
    titulo: "A IA não decide sua dose",
    texto:
      "A dose é calculada por regras fixas a partir do seu perfil. A IA só ajuda a entender o que você escreveu, e o GlicAI confirma antes de gravar.",
  },
  {
    icone: ShieldCheck,
    titulo: "Privacidade e LGPD",
    texto:
      "Seus dados de saúde servem só ao seu acompanhamento. Você pode apagar a conta e todo o histórico quando quiser.",
  },
  {
    icone: Lock,
    titulo: "Acesso protegido",
    texto: "Painel com CPF e senha, sessão segura no navegador e bloqueio automático após tentativas erradas.",
  },
];

const DUVIDAS = [
  {
    p: "Preciso instalar algum aplicativo?",
    r: "Não. O GlicAI funciona no WhatsApp que você já usa. O painel web é opcional e abre em qualquer navegador, no celular ou no computador.",
  },
  {
    p: "O GlicAI substitui meu médico?",
    r: "Não. Ele é uma ferramenta de apoio ao autocuidado. As configurações de dose (meta, fator de sensibilidade, relação insulina:carboidrato) devem vir da sua equipe de saúde, e a conta aparece sempre para você conferir.",
  },
  {
    p: "Registrei um valor errado. E agora?",
    r: "É só mandar algo como “apagar glicemia 6” ou “corrigir glicemia 116”. Para doses, “apagar dose 8”. O GlicAI desfaz o registro e, se os cuidadores já tinham sido avisados, manda uma correção para eles.",
  },
  {
    p: "Como acesso o painel?",
    r: "Mande “criar senha” para o GlicAI no WhatsApp. Você recebe um código de 6 dígitos e cria sua senha na aba Primeiro acesso, aqui no site.",
  },
  {
    p: "Quem consegue ver meus dados?",
    r: "Só você. Os cuidadores que você convidar recebem os alertas de glicemia fora da faixa, e você pode removê-los a qualquer momento.",
  },
];

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />

      <main className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden">
          <div className="fundo-pontilhado absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black_30%,transparent_75%)]" />
          <div className="absolute -right-40 -top-40 h-[480px] w-[480px] rounded-full bg-primary/15 blur-3xl" />
          <div className="absolute -left-40 top-60 h-[380px] w-[380px] rounded-full bg-accent/10 blur-3xl" />

          <div className="relative mx-auto grid max-w-6xl items-center gap-14 px-5 pb-20 pt-12 md:pt-20 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="surgir">
              <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs font-semibold text-foreground/80 shadow-sm">
                <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                Feito para quem convive com diabetes tipo 1
              </span>
              <h1 className="mt-5 font-heading text-[40px] font-extrabold leading-[1.05] tracking-tight sm:text-[54px]">
                Seu diabetes tipo 1,{" "}
                <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                  organizado no WhatsApp.
                </span>
              </h1>
              <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted">
                Registre glicemias, calcule a dose de insulina com a conta aberta, receba alertas e lembretes — e
                acompanhe tudo num painel pronto para levar ao médico. Sem aplicativo novo para instalar.
              </p>

              <div className="mt-8 flex flex-wrap gap-3">
                <a
                  href={LINK_ASSINAR}
                  {...propsAssinar}
                  className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 text-[15px] font-semibold text-primary-foreground shadow-lg shadow-primary/30 transition hover:brightness-105"
                >
                  Quero assinar <ArrowRight size={17} />
                </a>
                <Link
                  href="/login"
                  className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-5 py-3 text-[15px] font-semibold transition hover:border-primary/50 hover:text-primary"
                >
                  Já sou cliente
                </Link>
              </div>

              <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-foreground/75">
                {["Sem app para instalar", "Conta da dose sempre visível", "Seus dados sob seu controle"].map((t) => (
                  <li key={t} className="flex items-center gap-1.5">
                    <CircleCheck size={16} className="text-primary" />
                    {t}
                  </li>
                ))}
              </ul>
            </div>

            <PhoneMockup />
          </div>
        </section>

        {/* Como funciona */}
        <section id="como-funciona" className="scroll-mt-20 border-y border-border bg-surface py-20">
          <div className="mx-auto max-w-6xl px-5">
            <Cabecalho
              rotulo="Como funciona"
              titulo="Comece em minutos, sem mudar sua rotina"
              texto="Tudo acontece numa conversa. Você manda mensagens como mandaria para alguém da família — o GlicAI organiza o resto."
            />
            <div className="mt-12 grid gap-5 md:grid-cols-3">
              {PASSOS.map((p, i) => (
                <div key={p.titulo} className="relative rounded-2xl border border-border bg-card p-6 shadow-[var(--sombra)]">
                  <div className="flex items-center justify-between">
                    <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
                      <p.icone size={21} />
                    </span>
                    <span className="font-heading text-4xl font-extrabold text-foreground/[0.07]">0{i + 1}</span>
                  </div>
                  <h3 className="mt-5 font-heading text-lg font-bold">{p.titulo}</h3>
                  <p className="mt-2 text-[15px] leading-relaxed text-muted">{p.texto}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Recursos */}
        <section id="recursos" className="scroll-mt-20 py-20">
          <div className="mx-auto max-w-6xl px-5">
            <Cabecalho
              rotulo="Recursos"
              titulo="Tudo o que o dia a dia com T1D pede"
              texto="Do cálculo do bolus ao controle das fitas, num só lugar — e sempre com você no controle."
            />
            <div className="mt-12 grid gap-px overflow-hidden rounded-3xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
              {RECURSOS.map((r) => (
                <div key={r.titulo} className="bg-card p-7 transition hover:bg-surface">
                  <r.icone size={22} className="text-primary" />
                  <h3 className="mt-4 font-heading text-[17px] font-bold">{r.titulo}</h3>
                  <p className="mt-2 text-[15px] leading-relaxed text-muted">{r.texto}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Painel */}
        <section className="relative overflow-hidden bg-petroleo-escuro py-20 text-white">
          <div className="absolute -right-32 top-0 h-[420px] w-[420px] rounded-full bg-primary/20 blur-3xl" />
          <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-5 lg:grid-cols-2">
            <div>
              <p className="text-sm font-semibold uppercase tracking-wider text-primary">Painel web</p>
              <h2 className="mt-3 font-heading text-3xl font-extrabold tracking-tight sm:text-4xl">
                Veja o que o dia a dia esconde
              </h2>
              <p className="mt-4 text-lg leading-relaxed text-white/70">
                Cada mensagem vira dado organizado. No painel, você enxerga tendências, horários problemáticos e a sua
                evolução ao longo dos meses.
              </p>
              <ul className="mt-7 flex flex-col gap-3 text-[15px] text-white/85">
                {[
                  "Gráfico de tendência com a sua faixa-alvo",
                  "Tempo no alvo, hipos e hipers do período",
                  "Estimativa de HbA1c (GMI) e padrões por dia da semana",
                  "Perfil, cuidadores e estoque editáveis pelo navegador",
                ].map((t) => (
                  <li key={t} className="flex items-start gap-2.5">
                    <CircleCheck size={18} className="mt-0.5 shrink-0 text-primary" />
                    {t}
                  </li>
                ))}
              </ul>
              <Link
                href="/login"
                className="mt-8 inline-flex items-center gap-1.5 text-[15px] font-semibold text-white hover:text-primary"
              >
                Acessar meu painel <ChevronRight size={17} />
              </Link>
            </div>
            <PainelPreview />
          </div>
        </section>

        {/* Segurança */}
        <section id="seguranca" className="scroll-mt-20 py-20">
          <div className="mx-auto max-w-6xl px-5">
            <Cabecalho
              rotulo="Segurança"
              titulo="Feito com o cuidado que a sua saúde exige"
              texto="Insulina não é lugar para chute. Por isso o GlicAI foi desenhado para ser previsível, transparente e seu."
            />
            <div className="mt-12 grid gap-5 md:grid-cols-3">
              {SEGURANCA.map((s) => (
                <div key={s.titulo} className="rounded-2xl border border-border bg-card p-6 shadow-[var(--sombra)]">
                  <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-petroleo text-white dark:bg-white dark:text-petroleo">
                    <s.icone size={21} />
                  </span>
                  <h3 className="mt-5 font-heading text-lg font-bold">{s.titulo}</h3>
                  <p className="mt-2 text-[15px] leading-relaxed text-muted">{s.texto}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Dúvidas */}
        <section id="duvidas" className="scroll-mt-20 border-t border-border bg-surface py-20">
          <div className="mx-auto max-w-3xl px-5">
            <Cabecalho rotulo="Dúvidas" titulo="Perguntas frequentes" />
            <div className="mt-10 flex flex-col gap-3">
              {DUVIDAS.map((d) => (
                <details
                  key={d.p}
                  className="group rounded-2xl border border-border bg-card px-5 py-4 shadow-[var(--sombra)] open:pb-5"
                >
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-heading text-[16px] font-semibold [&::-webkit-details-marker]:hidden">
                    {d.p}
                    <ChevronRight size={18} className="shrink-0 text-muted transition group-open:rotate-90" />
                  </summary>
                  <p className="mt-3 text-[15px] leading-relaxed text-muted">{d.r}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* CTA final */}
        <section className="px-5 py-20">
          <div className="relative mx-auto max-w-5xl overflow-hidden rounded-[2rem] bg-gradient-to-br from-primary to-[#ff8a4c] px-6 py-14 text-center text-white shadow-2xl shadow-primary/30 sm:px-12">
            <div className="fundo-pontilhado absolute inset-0 opacity-30" />
            <div className="relative">
              <h2 className="font-heading text-3xl font-extrabold tracking-tight sm:text-4xl">
                Menos planilha, mais tranquilidade.
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-lg text-white/90">
                Fale com a gente e comece a usar o GlicAI no seu WhatsApp ainda hoje.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <a
                  href={LINK_ASSINAR}
                  {...propsAssinar}
                  className="inline-flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-[15px] font-semibold text-petroleo shadow-lg transition hover:bg-white/90"
                >
                  Quero assinar <ArrowRight size={17} />
                </a>
                <Link
                  href="/login"
                  className="inline-flex items-center rounded-xl border border-white/40 px-5 py-3 text-[15px] font-semibold text-white transition hover:bg-white/10"
                >
                  Entrar no painel
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-5 py-10 md:flex-row md:items-start md:justify-between">
          <div className="max-w-md">
            <Logo />
            <p className="mt-3 text-sm leading-relaxed text-muted">
              O GlicAI é uma ferramenta de apoio ao autocuidado e não substitui a orientação do seu médico ou equipe de
              saúde. Sempre confira a dose antes de aplicar.
            </p>
          </div>
          <div className="flex gap-10 text-sm">
            <div className="flex flex-col gap-2">
              <p className="font-semibold">Produto</p>
              <a href="#como-funciona" className="text-muted hover:text-foreground">
                Como funciona
              </a>
              <a href="#recursos" className="text-muted hover:text-foreground">
                Recursos
              </a>
              <a href="#seguranca" className="text-muted hover:text-foreground">
                Segurança
              </a>
            </div>
            <div className="flex flex-col gap-2">
              <p className="font-semibold">Conta</p>
              <Link href="/login" className="text-muted hover:text-foreground">
                Entrar
              </Link>
              <Link href="/criar-senha" className="text-muted hover:text-foreground">
                Primeiro acesso
              </Link>
            </div>
          </div>
        </div>
        <div className="border-t border-border py-5 text-center text-xs text-muted">
          © {new Date().getFullYear()} GlicAI. Todos os direitos reservados.
        </div>
      </footer>
    </div>
  );
}

function Cabecalho({ rotulo, titulo, texto }: { rotulo: string; titulo: string; texto?: string }) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <p className="text-sm font-semibold uppercase tracking-wider text-primary">{rotulo}</p>
      <h2 className="mt-3 font-heading text-3xl font-extrabold tracking-tight sm:text-4xl">{titulo}</h2>
      {texto && <p className="mt-4 text-lg leading-relaxed text-muted">{texto}</p>}
    </div>
  );
}
