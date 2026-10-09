"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Mail } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button, ErrorText, Field, Input, Label } from "@/components/ui";
import { CampoSenha } from "@/components/campo-senha";

export default function EntrarMedicoPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  async function aoEnviar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro("");
    setCarregando(true);
    try {
      await api.medicoLogin(email, senha);
      router.push("/medico");
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui entrar agora. Tente de novo.");
      setCarregando(false);
    }
  }

  return (
    <div>
      <h1 className="font-heading text-[28px] font-bold tracking-tight">Painel do médico</h1>
      <p className="mt-1.5 text-[15px] text-muted">Entre para acompanhar os pacientes que vincularam você.</p>

      <form onSubmit={aoEnviar} className="mt-8 flex flex-col gap-5">
        <Field>
          <Label htmlFor="email">E-mail</Label>
          <Input
            id="email"
            type="email"
            autoComplete="username"
            placeholder="voce@clinica.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            icone={<Mail size={17} />}
            required
          />
        </Field>

        <Field>
          <Label htmlFor="senha">Senha</Label>
          <CampoSenha
            id="senha"
            autoComplete="current-password"
            placeholder="Sua senha"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            required
          />
        </Field>

        <ErrorText>{erro}</ErrorText>

        <Button type="submit" carregando={carregando} className="mt-1 w-full py-3">
          {carregando ? "Entrando..." : "Entrar"}
        </Button>
      </form>

      <p className="mt-8 text-center text-sm text-muted">
        Ainda não tem conta?{" "}
        <Link href="/medico/cadastro" className="font-semibold text-primary hover:underline">
          Criar conta de médico
        </Link>
      </p>
      <p className="mt-3 text-center text-sm text-muted">
        É paciente?{" "}
        <Link href="/login" className="font-semibold text-primary hover:underline">
          Entrar como paciente
        </Link>
      </p>
    </div>
  );
}
