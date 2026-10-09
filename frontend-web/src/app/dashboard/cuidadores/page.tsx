"use client";

import { useEffect, useState } from "react";
import { Package, Plus, RefreshCw, Send, Trash2, Users } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Convite, Cuidador, ItemEstoque } from "@/lib/types";
import { Button, Card, CardTitulo, ErrorText, Field, Input, Label, PageHeader, Select, Skeleton, Vazio } from "@/components/ui";

export default function CuidadoresPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader titulo="Cuidadores e estoque" descricao="Quem acompanha você e os insumos que o GlicAI controla." />
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <SecaoCuidadores />
        <SecaoEstoque />
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------
// Cuidadores
// --------------------------------------------------------------------------

function SecaoCuidadores() {
  const [lista, setLista] = useState<Cuidador[] | null>(null);
  const [convite, setConvite] = useState<Convite | null>(null);
  const [erro, setErro] = useState("");
  const [carregandoConvite, setCarregandoConvite] = useState(false);

  function recarregar() {
    api.cuidadores().then((r) => setLista(r.cuidadores));
  }

  useEffect(recarregar, []);

  async function convidar() {
    setErro("");
    setCarregandoConvite(true);
    try {
      const c = await api.gerarConvite();
      setConvite(c);
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui gerar o convite agora.");
    } finally {
      setCarregandoConvite(false);
    }
  }

  async function remover(nome: string) {
    if (!window.confirm(`Remover ${nome}? Essa pessoa deixa de receber seus alertas.`)) return;
    setErro("");
    try {
      await api.removerCuidador(nome);
      recarregar();
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui remover agora.");
    }
  }

  return (
    <Card>
      <CardTitulo
        icone={<Users size={18} />}
        titulo="Quem acompanha você"
        descricao="Recebem aviso quando sua glicemia sai da faixa segura."
      />

      {lista === null ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      ) : lista.length === 0 ? (
        <Vazio icone={<Users size={20} />} titulo="Ninguém acompanhando ainda" texto="Convide um familiar ou responsável." />
      ) : (
        <ul className="flex flex-col gap-2">
          {lista.map((c) => (
            <li
              key={c.nome}
              className="flex items-center justify-between gap-3 rounded-xl border border-border px-3.5 py-2.5 text-sm"
            >
              <span className="flex items-center gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-surface text-xs font-bold">
                  {c.nome.charAt(0).toUpperCase()}
                </span>
                <span className="font-medium">{c.nome}</span>
              </span>
              <button
                type="button"
                onClick={() => remover(c.nome)}
                aria-label={`Remover ${c.nome}`}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted transition hover:bg-vermelho/10 hover:text-vermelho"
              >
                <Trash2 size={16} />
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-5 border-t border-border pt-5">
        {convite ? (
          <div className="rounded-xl border border-primary/25 bg-primary/[0.06] p-4 text-sm">
            <p className="text-muted">Código de convite</p>
            <p className="mt-1 font-heading text-3xl font-extrabold tracking-[0.2em] text-primary">{convite.codigo}</p>
            <p className="mt-3 leading-relaxed text-foreground/85">
              Envie esse código para quem vai acompanhar você. A pessoa manda para o GlicAI no WhatsApp:{" "}
              <span className="font-semibold">vincular {convite.codigo} &lt;nome dela&gt;</span>
            </p>
            <p className="mt-2 text-xs text-muted">Vale por {convite.minutos_validade} minutos.</p>
          </div>
        ) : (
          <Button onClick={convidar} carregando={carregandoConvite}>
            {!carregandoConvite && <Send size={16} />}
            {carregandoConvite ? "Gerando..." : "Convidar alguém"}
          </Button>
        )}
        <div className="mt-3">
          <ErrorText>{erro}</ErrorText>
        </div>
      </div>
    </Card>
  );
}

// --------------------------------------------------------------------------
// Estoque
// --------------------------------------------------------------------------

const TIPOS_DISPONIVEIS = [
  { valor: "insulina", rotulo: "Insulina" },
  { valor: "fita", rotulo: "Fitas de dextro" },
];

function SecaoEstoque() {
  const [itens, setItens] = useState<ItemEstoque[] | null>(null);
  const [erro, setErro] = useState("");
  const [mostrarForm, setMostrarForm] = useState(false);
  const [tipo, setTipo] = useState("insulina");
  const [quantidade, setQuantidade] = useState("");
  const [salvando, setSalvando] = useState(false);

  function recarregar() {
    api.estoque().then((r) => setItens(r.itens));
  }

  useEffect(recarregar, []);

  async function configurar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro("");
    const numero = Number(quantidade);
    if (!numero || numero <= 0) {
      setErro("Informe uma quantidade válida.");
      return;
    }
    setSalvando(true);
    try {
      await api.configurarEstoque(tipo, numero, null);
      setQuantidade("");
      setMostrarForm(false);
      recarregar();
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui configurar agora.");
    } finally {
      setSalvando(false);
    }
  }

  async function reabastecer(item: ItemEstoque) {
    setErro("");
    try {
      await api.reabastecerEstoque(item.tipo, item.quantidade_por_reposicao);
      recarregar();
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui reabastecer agora.");
    }
  }

  return (
    <Card>
      <CardTitulo
        icone={<Package size={18} />}
        titulo="Estoque de insumos"
        descricao="Descontado a cada registro. Você é avisado antes de acabar."
      />

      {itens === null ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
      ) : itens.length === 0 ? (
        <Vazio icone={<Package size={20} />} titulo="Nada configurado ainda" texto="Configure insulina ou fitas abaixo." />
      ) : (
        <div className="flex flex-col gap-3">
          {itens.map((item) => {
            const baixo = item.quantidade_atual <= item.limite_alerta;
            const pct = Math.min(100, Math.round((item.quantidade_atual / item.quantidade_por_reposicao) * 100));
            const unidade = item.tipo === "insulina" ? "U" : "";
            return (
              <div key={item.tipo} className="rounded-xl border border-border p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold">{item.label}</p>
                    <p className="mt-0.5 text-xs text-muted">
                      {baixo ? "Acabando — hora de repor" : `Aviso abaixo de ${item.limite_alerta.toFixed(0)}${unidade}`}
                    </p>
                  </div>
                  <p className="text-right">
                    <span className="font-heading text-xl font-bold" style={baixo ? { color: "var(--vermelho)" } : undefined}>
                      {item.quantidade_atual.toFixed(0)}
                      {unidade}
                    </span>
                    <span className="text-sm text-muted">
                      {" "}
                      / {item.quantidade_por_reposicao.toFixed(0)}
                      {unidade}
                    </span>
                  </p>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-foreground/[0.07]">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${pct}%`, background: baixo ? "var(--vermelho)" : "var(--verde)" }}
                  />
                </div>
                <button
                  type="button"
                  onClick={() => reabastecer(item)}
                  className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
                >
                  <RefreshCw size={14} /> Reabastecer ({item.quantidade_por_reposicao.toFixed(0)}
                  {unidade})
                </button>
              </div>
            );
          })}
        </div>
      )}

      <div className="mt-5 border-t border-border pt-5">
        {mostrarForm ? (
          <form onSubmit={configurar} className="flex flex-col gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field>
                <Label htmlFor="tipo">Tipo</Label>
                <Select id="tipo" value={tipo} onChange={(e) => setTipo(e.target.value)}>
                  {TIPOS_DISPONIVEIS.map((t) => (
                    <option key={t.valor} value={t.valor}>
                      {t.rotulo}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field>
                <Label htmlFor="quantidade">Quantidade por reposição</Label>
                <Input
                  id="quantidade"
                  inputMode="numeric"
                  value={quantidade}
                  onChange={(e) => setQuantidade(e.target.value)}
                  placeholder={tipo === "insulina" ? "300" : "50"}
                />
              </Field>
            </div>
            <div className="flex gap-2">
              <Button type="submit" carregando={salvando}>
                {salvando ? "Salvando..." : "Salvar"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setMostrarForm(false)}>
                Cancelar
              </Button>
            </div>
          </form>
        ) : (
          <Button variant="ghost" onClick={() => setMostrarForm(true)}>
            <Plus size={16} /> Configurar estoque
          </Button>
        )}
        <div className="mt-3">
          <ErrorText>{erro}</ErrorText>
        </div>
      </div>
    </Card>
  );
}
