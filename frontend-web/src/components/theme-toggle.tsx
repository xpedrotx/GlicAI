"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  // next-themes só sabe o tema real depois de montar no client (evita
  // mismatch de hidratação entre servidor e navegador) — até lá, renderiza
  // um placeholder do mesmo tamanho pra não pular o layout.
  const [montado, setMontado] = useState(false);
  useEffect(() => setMontado(true), []);

  if (!montado) {
    return <div className="h-9 w-9" />;
  }

  const escuro = resolvedTheme === "dark";

  return (
    <button
      type="button"
      onClick={() => setTheme(escuro ? "light" : "dark")}
      aria-label={escuro ? "Mudar para modo claro" : "Mudar para modo escuro"}
      className="flex h-9 w-9 items-center justify-center rounded-full border border-border text-foreground/80 transition hover:border-primary hover:text-primary"
    >
      {escuro ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}
