"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Mail, Stethoscope } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button, ErrorText, Field, Input, Label, Select } from "@/components/ui";
import { CampoSenha } from "@/components/campo-senha";

const UFS = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
  "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
];

export default function CadastroMedicoPage() {
  const router = useRouter();
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [crm, setCrm] = useState("");
  const [uf, setUf] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  async function aoEnviar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro("");
    setCarregando(true);
    try {
      await api.medicoCadastro({ nome, email, crm, uf, senha });
      router.push("/medico/vinculacao");
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui criar a conta agora. Tente de novo.");
      setCarregando(false);
    }
  }

  return (
    <div>
      <h1 className="font-heading text-[28px] font-bold tracking-tight">Criar conta de médico</h1>
      <p className="mt-1.5 text-[15px] text-muted">Leva um minuto. Você recebe seu código de vinculação na hora.</p>

      <form onSubmit={aoEnviar} className="mt-8 flex flex-col gap-5">
        <Field>
          <Label htmlFor="nome">Nome completo</Label>
          <Input
            id="nome"
            autoComplete="name"
            placeholder="Como você quer aparecer para o paciente"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            icone={<Stethoscope size={17} />}
            required
          />
        </Field>

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

        <div className="grid grid-cols-[1fr_96px] gap-4">
          <Field>
            <Label htmlFor="crm">CRM</Label>
            <Input
              id="crm"
              inputMode="numeric"
              placeholder="Somente números"
              value={crm}
              onChange={(e) => setCrm(e.target.value.replace(/\D/g, "").slice(0, 8))}
              required
            />
          </Field>
          <Field>
            <Label htmlFor="uf">UF</Label>
            <Select id="uf" value={uf} onChange={(e) => setUf(e.target.value)} required>
              <option value="" disabled>
                UF
              </option>
              {UFS.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <Field>
          <Label htmlFor="senha">Senha</Label>
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

        <ErrorText>{erro}</ErrorText>

        <Button type="submit" carregando={carregando} className="mt-1 w-full py-3">
          {carregando ? "Criando conta..." : "Criar conta"}
        </Button>

        <p className="text-center text-xs leading-relaxed text-muted">
          Seu nome e CRM aparecem para o paciente quando ele for vincular você, para ele conferir que é o médico certo.
        </p>
      </form>

      <p className="mt-6 text-center text-sm text-muted">
        Já tem conta?{" "}
        <Link href="/medico/entrar" className="font-semibold text-primary hover:underline">
          Entrar
        </Link>
      </p>
    </div>
  );
}
