"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { mascararCpf, somenteDigitos } from "@/lib/mascaras";
import { Button, Card, ErrorText, Field, Input, Label } from "@/components/ui";

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
    } finally {
      setCarregando(false);
    }
  }

  return (
    <Card>
      <h1 className="font-heading text-2xl font-semibold">Entrar</h1>
      <p className="mt-1 text-sm text-muted">Acompanhe sua glicemia e seus relatórios.</p>

      <form onSubmit={aoEnviar} className="mt-6 flex flex-col gap-4">
        <Field>
          <Label htmlFor="cpf">CPF</Label>
          <Input
            id="cpf"
            inputMode="numeric"
            autoComplete="username"
            placeholder="000.000.000-00"
            value={cpf}
            onChange={(e) => setCpf(mascararCpf(e.target.value))}
            required
          />
        </Field>

        <Field>
          <Label htmlFor="senha">Senha</Label>
          <Input
            id="senha"
            type="password"
            autoComplete="current-password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            required
          />
        </Field>

        <ErrorText>{erro}</ErrorText>

        <Button type="submit" disabled={carregando}>
          {carregando ? "Entrando..." : "Entrar"}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted">
        Primeiro acesso ou esqueceu a senha?{" "}
        <Link href="/criar-senha" className="font-medium text-primary hover:underline">
          Criar senha
        </Link>
      </p>
    </Card>
  );
}
