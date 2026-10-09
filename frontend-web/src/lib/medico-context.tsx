"use client";

import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { LoaderCircle } from "lucide-react";
import { api } from "./api";
import type { MedicoEu } from "./types";

const MedicoContext = createContext<MedicoEu | null>(null);

/** Confere a sessão do médico (cookie httpOnly) e libera o painel — sem sessão válida, vai pro login do médico. */
export function MedicoProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [medico, setMedico] = useState<MedicoEu | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    api
      .medicoEu()
      .then(setMedico)
      .catch(() => router.replace("/medico/entrar"))
      .finally(() => setCarregando(false));
  }, [router]);

  if (carregando || !medico) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoaderCircle size={28} className="animate-spin text-primary" aria-label="Carregando" />
      </div>
    );
  }

  return <MedicoContext.Provider value={medico}>{children}</MedicoContext.Provider>;
}

export function useMedico(): MedicoEu {
  const medico = useContext(MedicoContext);
  if (!medico) throw new Error("useMedico fora do MedicoProvider");
  return medico;
}
