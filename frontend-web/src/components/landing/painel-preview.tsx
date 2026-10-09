/** Prévia ilustrativa do painel — números e curva fictícios, só pra vitrine. */
const PONTOS = [142, 118, 96, 128, 176, 151, 109, 88, 74, 112, 134, 121, 98, 186, 160, 127, 104, 115, 92, 138];

export function PainelPreview() {
  const largura = 460;
  const altura = 150;
  const min = 50;
  const max = 220;
  const y = (v: number) => altura - ((v - min) / (max - min)) * altura;
  const x = (i: number) => (i / (PONTOS.length - 1)) * largura;
  const caminho = PONTOS.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");

  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4 shadow-2xl backdrop-blur sm:p-5">
      <div className="grid grid-cols-3 gap-3">
        {[
          { r: "Média", v: "124", s: "mg/dL" },
          { r: "No alvo", v: "72%", s: "da semana", verde: true },
          { r: "GMI", v: "6.3%", s: "estimado" },
        ].map((c) => (
          <div key={c.r} className="rounded-2xl bg-white/[0.06] p-3.5">
            <p className="text-[11px] font-medium text-white/60">{c.r}</p>
            <p className={`mt-1 font-heading text-xl font-bold ${c.verde ? "text-[#6fd3a0]" : "text-white"}`}>{c.v}</p>
            <p className="text-[11px] text-white/50">{c.s}</p>
          </div>
        ))}
      </div>

      <div className="mt-3 rounded-2xl bg-white/[0.06] p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-xs font-semibold text-white/80">Tendência — 7 dias</p>
          <p className="text-[11px] text-white/50">faixa 70–180</p>
        </div>
        <svg viewBox={`0 0 ${largura} ${altura}`} className="h-auto w-full" role="img" aria-label="Gráfico ilustrativo">
          <rect x="0" y={y(180)} width={largura} height={y(70) - y(180)} fill="#3fa672" opacity="0.12" rx="6" />
          <path d={caminho} fill="none" stroke="white" strokeOpacity="0.55" strokeWidth="1.6" strokeLinejoin="round" />
          {PONTOS.map((v, i) => (
            <circle
              key={i}
              cx={x(i)}
              cy={y(v)}
              r="3.2"
              fill={v < 70 || v > 180 ? "#ff7b80" : "#6fd3a0"}
              stroke="#10252f"
              strokeWidth="1.2"
            />
          ))}
        </svg>
      </div>
    </div>
  );
}
