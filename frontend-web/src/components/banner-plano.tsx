"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, Gift, Lock } from "lucide-react";
import { api } from "@/lib/api";
import type { Plano } from "@/lib/types";

/** Faixa no topo do painel lembrando do teste grátis / plano gratuito — some pra quem já é Pro. */
export function BannerPlano() {
  const pathname = usePathname();
  const [plano, setPlano] = useState<Plano | null>(null);

  useEffect(() => {
    api.plano().then(setPlano).catch(() => {});
  }, []);

  if (!plano || plano.plano === "pro" || pathname === "/dashboard/assinatura") return null;

  const teste = plano.plano === "trial";
  const dias = plano.dias_restantes_teste ?? 0;

  return (
    <Link
      href="/dashboard/assinatura"
      className={`mb-6 flex items-center justify-between gap-3 rounded-2xl border px-4 py-3 text-sm transition hover:brightness-105 sm:px-5 ${
        teste ? "border-accent/30 bg-accent/10" : "border-primary/25 bg-primary/10"
      }`}
    >
      <span className="flex items-center gap-2.5">
        {teste ? <Gift size={18} className="shrink-0 text-accent" /> : <Lock size={18} className="shrink-0 text-primary" />}
        <span>
          {teste ? (
            <>
              <span className="font-semibold">Teste grátis:</span> {dias === 1 ? "termina hoje" : `${dias} dias restantes`}
            </>
          ) : (
            <>
              <span className="font-semibold">Plano gratuito:</span> 1 medição por dia e sem lembretes
            </>
          )}
        </span>
      </span>
      <span className="flex shrink-0 items-center gap-1 font-semibold text-primary">
        {teste ? "Ver planos" : "Assinar Pro"} <ArrowRight size={15} />
      </span>
    </Link>
  );
}
