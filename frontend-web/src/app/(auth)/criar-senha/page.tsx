"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { IdCard, KeyRound, MessageCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { mascararCpf, somenteDigitos } from "@/lib/mascaras";
import { Button, ErrorText, Field, Input, Label } from "@/components/ui";
import { CampoSenha } from "@/components/campo-senha";

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
      setCarregando(false);
    }
  }

  return (
    <div>
      <h1 className="font-heading text-[28px] font-bold tracking-tight">Primeiro acesso</h1>
      <p className="mt-1.5 text-[15px] text-muted">Crie sua senha para acessar o painel. Também serve para trocar a senha.</p>

      <div className="mt-6 flex gap-3 rounded-xl border border-border bg-surface px-4 py-3.5 text-sm leading-relaxed text-foreground/85">
        <MessageCircle size={18} className="mt-0.5 shrink-0 text-primary" />
        <p>
          No WhatsApp, mande <span className="font-semibold text-foreground">criar senha</span> para o GlicAI. Você
          recebe um código de 6 dígitos — digite ele aqui.
        </p>
      </div>

      <form onSubmit={aoEnviar} className="mt-6 flex flex-col gap-5">
        <Field>
          <Label htmlFor="codigo">Código recebido no WhatsApp</Label>
          <Input
            id="codigo"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            placeholder="000000"
            value={codigo}
            onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))}
            icone={<KeyRound size={17} />}
            className="tracking-[0.3em]"
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
            icone={<IdCard size={17} />}
            required
          />
        </Field>

        <Field>
          <Label htmlFor="senha">Nova senha</Label>
          <CampoSenha
            id="senha"
            autoComplete="new-password"
            minLength={8}
            placeholder="Mínimo de 8 caracteres"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            required
          />
        </Field>

        <Field>
          <Label htmlFor="confirmar-senha">Confirmar senha</Label>
          <CampoSenha
            id="confirmar-senha"
            autoComplete="new-password"
            minLength={8}
            placeholder="Repita a senha"
            value={confirmarSenha}
            onChange={(e) => setConfirmarSenha(e.target.value)}
            required
          />
        </Field>

        <ErrorText>{erro}</ErrorText>

        <Button type="submit" carregando={carregando} className="mt-1 w-full py-3">
          {carregando ? "Confirmando..." : "Criar senha e entrar"}
        </Button>
      </form>
    </div>
  );
}
