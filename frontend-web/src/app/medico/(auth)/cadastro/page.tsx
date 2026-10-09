"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, KeyRound, Mail, MailCheck, Stethoscope } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button, ErrorText, Field, Input, Label, Select } from "@/components/ui";
import { CampoSenha } from "@/components/campo-senha";

const UFS = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
  "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
];

const SEGUNDOS_ENTRE_REENVIOS = 60;

export default function CadastroMedicoPage() {
  const router = useRouter();
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [crm, setCrm] = useState("");
  const [uf, setUf] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  // 2ª etapa: confirmação do e-mail
  const [aguardandoCodigo, setAguardandoCodigo] = useState(false);
  const [codigo, setCodigo] = useState("");
  const [espera, setEspera] = useState(0);
  const [reenviado, setReenviado] = useState(false);

  useEffect(() => {
    if (espera <= 0) return;
    const id = setTimeout(() => setEspera((e) => e - 1), 1000);
    return () => clearTimeout(id);
  }, [espera]);

  async function enviarDados(evento: React.FormEvent) {
    evento.preventDefault();
    setErro("");
    setCarregando(true);
    try {
      const r = await api.medicoCadastro({ nome, email, crm, uf, senha });
      setEmail(r.email);
      setCodigo("");
      setReenviado(false);
      setEspera(SEGUNDOS_ENTRE_REENVIOS);
      setAguardandoCodigo(true);
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui criar a conta agora. Tente de novo.");
    } finally {
      setCarregando(false);
    }
  }

  async function confirmar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro("");
    setCarregando(true);
    try {
      await api.medicoConfirmarEmail(email, codigo);
      router.push("/medico/vinculacao");
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui confirmar agora. Tente de novo.");
      setCarregando(false);
    }
  }

  async function reenviar() {
    setErro("");
    setReenviado(false);
    try {
      await api.medicoReenviarCodigo(email);
      setReenviado(true);
      setEspera(SEGUNDOS_ENTRE_REENVIOS);
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui reenviar agora.");
    }
  }

  if (aguardandoCodigo) {
    return (
      <div>
        <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <MailCheck size={24} />
        </span>
        <h1 className="mt-5 font-heading text-[28px] font-bold tracking-tight">Confirme seu e-mail</h1>
        <p className="mt-1.5 text-[15px] leading-relaxed text-muted">
          Enviamos um código de 6 dígitos para <span className="font-semibold text-foreground">{email}</span>. Ele vale por 15
          minutos. Olhe também a caixa de spam.
        </p>

        <form onSubmit={confirmar} className="mt-8 flex flex-col gap-5">
          <Field>
            <Label htmlFor="codigo">Código recebido por e-mail</Label>
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
              autoFocus
              required
            />
          </Field>

          <ErrorText>{erro}</ErrorText>
          {reenviado && !erro && (
            <p className="rounded-xl border border-verde/30 bg-verde/10 px-3.5 py-2.5 text-sm">Enviamos um novo código.</p>
          )}

          <Button type="submit" carregando={carregando} disabled={codigo.length !== 6} className="w-full py-3">
            {carregando ? "Confirmando..." : "Confirmar e criar conta"}
          </Button>
        </form>

        <div className="mt-6 flex flex-col items-center gap-3 text-sm">
          <button
            type="button"
            onClick={reenviar}
            disabled={espera > 0}
            className="font-semibold text-primary hover:underline disabled:cursor-not-allowed disabled:text-muted disabled:no-underline"
          >
            {espera > 0 ? `Reenviar código em ${espera}s` : "Reenviar código"}
          </button>
          <button
            type="button"
            onClick={() => {
              setAguardandoCodigo(false);
              setErro("");
            }}
            className="inline-flex items-center gap-1.5 text-muted transition hover:text-foreground"
          >
            <ArrowLeft size={14} /> Corrigir meus dados
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="font-heading text-[28px] font-bold tracking-tight">Criar conta de médico</h1>
      <p className="mt-1.5 text-[15px] text-muted">
        Leva um minuto. Vamos confirmar seu e-mail e você já recebe seu código de vinculação.
      </p>

      <form onSubmit={enviarDados} className="mt-8 flex flex-col gap-5">
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
          {carregando ? "Enviando código..." : "Continuar"}
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
