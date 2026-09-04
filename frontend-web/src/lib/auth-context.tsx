"use client";

import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

type Usuario = { nome: string | null; telefone: string };

const AuthContext = createContext<Usuario | null>(null);

/** Confere a sessão uma vez (via cookie httpOnly) e disponibiliza o usuário
 * pras páginas do dashboard — redireciona pro login se não tiver sessão
 * válida. Todas as rotas de /dashboard ficam atrás disso (ver layout.tsx). */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    api
      .eu()
      .then(setUsuario)
      .catch(() => router.replace("/login"))
      .finally(() => setCarregando(false));
  }, [router]);

  if (carregando || !usuario) {
    return null;
  }

  return <AuthContext.Provider value={usuario}>{children}</AuthContext.Provider>;
}

export function useUsuario(): Usuario | null {
  return useContext(AuthContext);
}
