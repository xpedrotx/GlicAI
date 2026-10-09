"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { IdCard } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { mascararCpf, somenteDigitos } from "@/lib/mascaras";
import { Button, ErrorText, Field, Input, Label } from "@/components/ui";
import { CampoSenha } from "@/components/campo-senha";

export default function LoginPage() {
  const router = useRouter();
  const [cpf, setCpf] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  async function aoEnviar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro("");
    setCarregando(true);
    try {
      await api.login(somenteDigitos(cpf), senha);
      router.push("/dashboard");
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui entrar agora. Tenta de novo.");
      setCarregando(false);
    }
  }

  return (
    <div>
      <h1 className="font-heading text-[28px] font-bold tracking-tight">Bem-vindo de volta</h1>
      <p className="mt-1.5 text-[15px] text-muted">Entre para acompanhar sua glicemia e seus relatórios.</p>

      <form onSubmit={aoEnviar} className="mt-8 flex flex-col gap-5">
        <Field>
          <Label htmlFor="cpf">CPF</Label>
          <Input
            id="cpf"
            inputMode="numeric"
            autoComplete="username"
            placeholder="000.000.000-00"
            value={cpf}
            onChange={(e) => setCpf(mascararCpf(e.target.value))}
            icone={<IdCard size={17} />}
            required
          />
        </Field>

        <Field>
          <div className="flex items-center justify-between">
            <Label htmlFor="senha">Senha</Label>
            <Link href="/criar-senha" className="text-sm font-medium text-primary hover:underline">
              Esqueci a senha
            </Link>
          </div>
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
        Ainda não tem senha?{" "}
        <Link href="/criar-senha" className="font-semibold text-primary hover:underline">
          Fazer primeiro acesso
        </Link>
      </p>
    </div>
  );
}
