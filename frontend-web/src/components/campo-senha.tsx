"use client";

import { useState, type InputHTMLAttributes } from "react";
import { Eye, EyeOff, Lock } from "lucide-react";
import { Input } from "./ui";

export function CampoSenha(props: InputHTMLAttributes<HTMLInputElement>) {
  const [visivel, setVisivel] = useState(false);
  return (
    <div className="relative">
      <Input {...props} type={visivel ? "text" : "password"} icone={<Lock size={17} />} className="pr-11" />
      <button
        type="button"
        onClick={() => setVisivel(!visivel)}
        aria-label={visivel ? "Esconder senha" : "Mostrar senha"}
        className="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-muted transition hover:text-foreground"
      >
        {visivel ? <EyeOff size={17} /> : <Eye size={17} />}
      </button>
    </div>
  );
}
