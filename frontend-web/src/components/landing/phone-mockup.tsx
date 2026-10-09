import { BellRing, CircleCheck, Users } from "lucide-react";

/** Conversa ilustrativa no formato real das respostas do bot (ver bolus.py). */
function Balao({ de, children, hora }: { de: "eu" | "bot"; children: React.ReactNode; hora: string }) {
  const meu = de === "eu";
  return (
    <div className={`flex ${meu ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[84%] rounded-2xl px-3 py-2 text-[12.5px] leading-snug shadow-sm ${
          meu ? "rounded-tr-md bg-[#d9fdd3] text-[#111b21]" : "rounded-tl-md bg-white text-[#111b21]"
        }`}
      >
        {children}
        <span className="mt-0.5 block text-right text-[10px] text-[#667781]">{hora}</span>
      </div>
    </div>
  );
}

export function PhoneMockup() {
  return (
    <div className="relative mx-auto w-full max-w-[330px]">
      <div className="relative rounded-[2.6rem] border-[10px] border-petroleo-escuro bg-petroleo-escuro shadow-2xl shadow-petroleo/30">
        <div className="overflow-hidden rounded-[1.9rem]">
          <div className="flex items-center gap-2.5 bg-[#075e54] px-4 pb-3 pt-5 text-white">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-primary to-accent text-xs font-bold">
              G
            </span>
            <div className="leading-tight">
              <p className="text-sm font-semibold">GlicAI</p>
              <p className="text-[11px] text-white/75">online</p>
            </div>
          </div>

          <div className="flex flex-col gap-2 bg-[#efeae2] px-3 pb-20 pt-4">
            <Balao de="eu" hora="12:38">
              60g de carbo, tá 180
            </Balao>
            <Balao de="bot" hora="12:38">
              <span className="font-semibold">💉 Dose sugerida</span>
              <span className="mt-1 block font-mono text-[11px] text-[#3b4a54]">
                Carboidrato: 60g ÷ 15g/U = 4.0U
                <br />
                Correção: (180 - 100) ÷ 40 = 2.0U
              </span>
              <span className="mt-1 block font-semibold">Dose final: 6U</span>
              <span className="mt-1 block text-[#3b4a54]">
                Quando aplicar, me avisa: <i>apliquei 6</i>
              </span>
            </Balao>
            <Balao de="eu" hora="12:41">
              apliquei 6
            </Balao>
            <Balao de="bot" hora="12:41">
              ✅ Anotei <b>6U</b> às 12:41.
            </Balao>
          </div>
        </div>
      </div>

      <div className="surgir absolute -left-10 top-[104px] hidden items-center gap-2.5 rounded-2xl border border-border bg-card px-3.5 py-2.5 shadow-[var(--sombra)] sm:flex [animation-delay:0.3s]">
        <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent/15 text-accent">
          <BellRing size={16} />
        </span>
        <div className="leading-tight">
          <p className="text-xs font-semibold">Lembrete</p>
          <p className="text-[11px] text-muted">Basal das 22h</p>
        </div>
      </div>

      <div className="surgir absolute -right-10 bottom-5 hidden items-center gap-2.5 rounded-2xl border border-border bg-card px-3.5 py-2.5 shadow-[var(--sombra)] sm:flex [animation-delay:0.5s]">
        <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/12 text-primary">
          <Users size={16} />
        </span>
        <div className="leading-tight">
          <p className="text-xs font-semibold">Cuidador avisado</p>
          <p className="text-[11px] text-muted">Glicemia fora da faixa</p>
        </div>
      </div>

      <div className="surgir absolute -right-4 top-6 hidden items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-semibold shadow-[var(--sombra)] sm:flex [animation-delay:0.7s]">
        <CircleCheck size={14} className="text-verde" />
        72% no alvo esta semana
      </div>
    </div>
  );
}
