"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Convite, Cuidador, ItemEstoque } from "@/lib/types";
import { Button, Card, ErrorText, Field, Input, Label } from "@/components/ui";

export default function CuidadoresPage() {
  return (
    <div className="flex flex-col gap-8">
      <h1 className="font-heading text-2xl font-semibold">Cuidadores e estoque</h1>
      <SecaoCuidadores />
      <SecaoEstoque />
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
    setErro("");
    try {
      await api.removerCuidador(nome);
      recarregar();
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui remover agora.");
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <h2 className="font-heading text-lg font-semibold">👨‍👩‍👧 Quem acompanha você</h2>

      <Card>
        {lista === null ? (
          <p className="text-sm text-muted">Carregando...</p>
        ) : lista.length === 0 ? (
          <p className="text-sm text-muted">Ninguém acompanhando ainda.</p>
        ) : (
          <ul className="flex flex-col gap-2.5">
            {lista.map((c) => (
              <li key={c.nome} className="flex items-center justify-between text-sm">
                <span>{c.nome}</span>
                <button
                  type="button"
                  onClick={() => remover(c.nome)}
                  className="text-sm font-medium text-primary hover:underline"
                >
                  Remover
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-4 border-t border-border pt-4">
          {convite ? (
            <div className="rounded-lg border border-border bg-background/60 px-4 py-3 text-sm">
              <p>
                Código: <span className="font-heading text-lg font-semibold text-primary">{convite.codigo}</span>
              </p>
              <p className="mt-1 text-foreground/80">
                Manda esse código pra quem você quer que acompanhe sua glicemia. Ela(e) deve mandar pro WhatsApp:{" "}
                <span className="font-medium">vincular {convite.codigo} &lt;nome dela(e)&gt;</span>
              </p>
              <p className="mt-1 text-muted">Vale por {convite.minutos_validade} minutos.</p>
            </div>
          ) : (
            <Button onClick={convidar} disabled={carregandoConvite} className="w-auto px-4">
              {carregandoConvite ? "Gerando..." : "+ Convidar alguém"}
            </Button>
          )}
          <ErrorText>{erro}</ErrorText>
        </div>
      </Card>
    </div>
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
      setErro("Manda uma quantidade válida.");
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
    <div className="flex flex-col gap-3">
      <h2 className="font-heading text-lg font-semibold">💊 Estoque de insumos</h2>

      <Card>
        {itens === null ? (
          <p className="text-sm text-muted">Carregando...</p>
        ) : itens.length === 0 ? (
          <p className="text-sm text-muted">Nada configurado ainda.</p>
        ) : (
          <div className="flex flex-col gap-4">
            {itens.map((item) => {
              const baixo = item.quantidade_atual <= item.limite_alerta;
              const pct = Math.min(100, Math.round((item.quantidade_atual / item.quantidade_por_reposicao) * 100));
              return (
                <div key={item.tipo}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">
                      {baixo ? "🔴" : "🟢"} {item.label}
                    </span>
                    <span className={baixo ? "font-semibold text-primary" : "font-medium"}>
                      {item.quantidade_atual.toFixed(0)} / {item.quantidade_por_reposicao.toFixed(0)}
                    </span>
                  </div>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-border">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${pct}%`, background: baixo ? "var(--vermelho)" : "var(--verde)" }}
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => reabastecer(item)}
                    className="mt-1.5 text-sm font-medium text-primary hover:underline"
                  >
                    Reabastecer
                  </button>
                </div>
              );
            })}
          </div>
        )}

        <div className="mt-4 border-t border-border pt-4">
          {mostrarForm ? (
            <form onSubmit={configurar} className="flex flex-col gap-3">
              <Field>
                <Label htmlFor="tipo">Tipo</Label>
                <select
                  id="tipo"
                  value={tipo}
                  onChange={(e) => setTipo(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-[15px] text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/25"
                >
                  {TIPOS_DISPONIVEIS.map((t) => (
                    <option key={t.valor} value={t.valor}>
                      {t.rotulo}
                    </option>
                  ))}
                </select>
              </Field>
              <Field>
                <Label htmlFor="quantidade">Quantidade por reposição</Label>
                <Input
                  id="quantidade"
                  inputMode="numeric"
                  value={quantidade}
                  onChange={(e) => setQuantidade(e.target.value)}
                  placeholder="300"
                />
              </Field>
              <div className="flex gap-2">
                <Button type="submit" disabled={salvando} className="w-auto px-4">
                  {salvando ? "Salvando..." : "Salvar"}
                </Button>
                <Button type="button" variant="ghost" onClick={() => setMostrarForm(false)} className="w-auto px-4">
                  Cancelar
                </Button>
              </div>
            </form>
          ) : (
            <Button onClick={() => setMostrarForm(true)} className="w-auto px-4">
              + Configurar estoque
            </Button>
          )}
          <ErrorText>{erro}</ErrorText>
        </div>
      </Card>
    </div>
  );
}
