"use client";

import { useEffect, useState } from "react";
import { Eye, EyeOff, KeyRound, ShieldCheck, Stethoscope, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { MedicoVinculado, PreviaMedico } from "@/lib/types";
import { Button, Card, CardTitulo, ErrorText, Field, Input, Label, PageHeader, Skeleton, Vazio } from "@/components/ui";

export default function MedicosPage() {
  const [lista, setLista] = useState<MedicoVinculado[] | null>(null);
  const [codigo, setCodigo] = useState("");
  const [previa, setPrevia] = useState<PreviaMedico | null>(null);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState("");

  function recarregar() {
    api.medicosVinculados().then((r) => setLista(r.medicos));
  }

  useEffect(recarregar, []);

  async function verificar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro("");
    setAviso("");
    setOcupado(true);
    try {
      const r = await api.vincularMedico(codigo, false);
      setPrevia(r.medico);
    } catch (e) {
      setPrevia(null);
      setErro(e instanceof ApiError ? e.message : "Não consegui verificar o código agora.");
    } finally {
      setOcupado(false);
    }
  }

  async function confirmar() {
    setErro("");
    setOcupado(true);
    try {
      const r = await api.vincularMedico(codigo, true);
      setAviso(
        r.status === "ja_vinculado"
          ? `Você já estava vinculado ao(à) Dr(a). ${r.medico.nome}.`
          : `Pronto! O(A) Dr(a). ${r.medico.nome} agora acompanha seus dados.`,
      );
      setPrevia(null);
      setCodigo("");
      recarregar();
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui vincular agora.");
    } finally {
      setOcupado(false);
    }
  }

  async function remover(m: MedicoVinculado) {
    if (!window.confirm(`Tirar o acesso do(a) Dr(a). ${m.nome}? Ele(a) deixa de ver seus dados.`)) return;
    setErro("");
    setAviso("");
    try {
      await api.removerMedico(m.id);
      recarregar();
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui remover agora.");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader titulo="Médicos" descricao="Quem acompanha seus dados de glicemia. Você controla o acesso." />

      <div className="grid items-start gap-6 lg:grid-cols-2">
        <Card>
          <CardTitulo
            icone={<KeyRound size={18} />}
            titulo="Vincular um médico"
            descricao="Peça o código de vinculação ao seu médico (ex: DR-K7M2QX)."
          />

          {previa ? (
            <div className="rounded-xl border border-primary/25 bg-primary/[0.06] p-4">
              <p className="text-sm text-muted">Você vai liberar seus dados para:</p>
              <p className="mt-1 font-heading text-xl font-bold">Dr(a). {previa.nome}</p>
              <p className="text-sm text-muted">
                CRM {previa.crm}/{previa.uf}
              </p>
              <p className="mt-3 text-sm leading-relaxed">
                Confira se é mesmo o seu médico. Você pode tirar o acesso quando quiser.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button onClick={confirmar} carregando={ocupado}>
                  Confirmar vínculo
                </Button>
                <Button variant="ghost" onClick={() => setPrevia(null)}>
                  Cancelar
                </Button>
              </div>
            </div>
          ) : (
            <form onSubmit={verificar} className="flex flex-col gap-4">
              <Field>
                <Label htmlFor="codigo">Código do médico</Label>
                <Input
                  id="codigo"
                  value={codigo}
                  onChange={(e) => setCodigo(e.target.value.toUpperCase())}
                  placeholder="DR-XXXXXX"
                  autoComplete="off"
                  maxLength={12}
                  className="font-mono tracking-widest"
                  required
                />
              </Field>
              <Button type="submit" carregando={ocupado} disabled={!codigo.trim()} className="w-full sm:w-auto sm:self-start">
                Verificar código
              </Button>
            </form>
          )}

          {aviso && (
            <p className="mt-4 rounded-xl border border-verde/30 bg-verde/10 px-3.5 py-2.5 text-sm">{aviso}</p>
          )}
          <div className="mt-3">
            <ErrorText>{erro}</ErrorText>
          </div>
        </Card>

        <Card>
          <CardTitulo icone={<Stethoscope size={18} />} titulo="Quem acompanha você" />
          {lista === null ? (
            <Skeleton className="h-16" />
          ) : lista.length === 0 ? (
            <Vazio
              icone={<Stethoscope size={20} />}
              titulo="Nenhum médico vinculado"
              texto="Você também pode vincular pelo WhatsApp: mande medico DR-XXXXXX."
            />
          ) : (
            <ul className="flex flex-col gap-2">
              {lista.map((m) => (
                <li key={m.id} className="flex items-center justify-between gap-3 rounded-xl border border-border px-3.5 py-3 text-sm">
                  <span>
                    <span className="font-medium">Dr(a). {m.nome}</span>
                    <span className="block text-xs text-muted">
                      CRM {m.crm}/{m.uf} · desde {new Date(m.vinculado_em).toLocaleDateString("pt-BR")}
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={() => remover(m)}
                    aria-label={`Tirar acesso de ${m.nome}`}
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted transition hover:bg-vermelho/10 hover:text-vermelho"
                  >
                    <Trash2 size={16} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card className="max-w-3xl">
        <CardTitulo icone={<ShieldCheck size={18} />} titulo="O que o médico vê" />
        <ul className="flex flex-col gap-3 text-sm">
          <li className="flex items-start gap-2.5">
            <Eye size={17} className="mt-0.5 shrink-0 text-verde" />
            <span>
              Seu nome, suas glicemias, doses de insulina, relatórios e o seu perfil de dose (meta, limites, fator de
              sensibilidade, relação insulina:carboidrato e basal).
            </span>
          </li>
          <li className="flex items-start gap-2.5">
            <EyeOff size={17} className="mt-0.5 shrink-0 text-vermelho" />
            <span>Nunca seu telefone, seu CPF nem suas conversas com o GlicAI. E o médico não consegue alterar nada.</span>
          </li>
        </ul>
      </Card>
    </div>
  );
}
