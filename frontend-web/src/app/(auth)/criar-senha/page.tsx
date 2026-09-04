"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { mascararCpf, somenteDigitos } from "@/lib/mascaras";
import { Button, Card, ErrorText, Field, Input, Label } from "@/components/ui";

export default function CriarSenhaPage() {
  const router = useRouter();
  const [codigo, setCodigo] = useState("");
  const [cpf, setCpf] = useState("");
  const [senha, setSenha] = useState("");
  const [confirmarSenha, setConfirmarSenha] = useState("");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  async function aoEnviar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro("");
    if (senha !== confirmarSenha) {
      setErro("As senhas não são iguais.");
      return;
    }
    setCarregando(true);
    try {
      await api.confirmarCodigo({ codigo: codigo.trim(), cpf: somenteDigitos(cpf), senha });
      router.push("/dashboard");
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui confirmar agora. Tenta de novo.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <Card>
      <h1 className="font-heading text-2xl font-semibold">Criar senha</h1>

      <div className="mt-4 rounded-lg border border-border bg-background/60 px-4 py-3 text-sm text-foreground/90">
        No seu WhatsApp, manda a mensagem <span className="font-semibold text-primary">criar senha</span> pro
        GlicAI. Você recebe um código de 6 dígitos — cola ele aqui embaixo.
      </div>

      <form onSubmit={aoEnviar} className="mt-6 flex flex-col gap-4">
        <Field>
          <Label htmlFor="codigo">Código recebido no WhatsApp</Label>
          <Input
            id="codigo"
            inputMode="numeric"
            maxLength={6}
            placeholder="000000"
            value={codigo}
            onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))}
            required
          />
        </Field>

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
            autoComplete="new-password"
            minLength={8}
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            required
          />
        </Field>

        <Field>
          <Label htmlFor="confirmar-senha">Confirmar senha</Label>
          <Input
            id="confirmar-senha"
            type="password"
            autoComplete="new-password"
            minLength={8}
            value={confirmarSenha}
            onChange={(e) => setConfirmarSenha(e.target.value)}
            required
          />
        </Field>

        <ErrorText>{erro}</ErrorText>

        <Button type="submit" disabled={carregando}>
          {carregando ? "Confirmando..." : "Criar senha e entrar"}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted">
        Já tem senha?{" "}
        <Link href="/login" className="font-medium text-primary hover:underline">
          Entrar
        </Link>
      </p>
    </Card>
  );
}
