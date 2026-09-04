"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { Button, Input } from "./ui";

/**
 * Campo com "clique pra editar" — chama PUT /api/dashboard/perfil pra um
 * campo por vez, mesma granularidade do comando *editar* no WhatsApp
 * (ver app/services/perfil.py: mesmas regras de validação dos dois lados).
 */
export function EditableField({
  campo,
  rotulo,
  valorAtual,
  sufixo = "",
  onSalvo,
}: {
  campo: string;
  rotulo: string;
  valorAtual: string;
  sufixo?: string;
  onSalvo: (novoValor: string) => void;
}) {
  const [editando, setEditando] = useState(false);
  const [valor, setValor] = useState(valorAtual);
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);

  async function salvar() {
    setErro("");
    setSalvando(true);
    try {
      await api.atualizarPerfil(campo, valor);
      onSalvo(valor);
      setEditando(false);
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui salvar agora.");
    } finally {
      setSalvando(false);
    }
  }

  function cancelar() {
    setValor(valorAtual);
    setErro("");
    setEditando(false);
  }

  return (
    <div className="flex flex-col gap-1.5 border-b border-border py-3 last:border-0">
      <span className="text-xs font-medium uppercase tracking-wide text-muted">{rotulo}</span>

      {!editando ? (
        <div className="flex items-center justify-between gap-3">
          <span className="font-medium">
            {valorAtual || "—"}
            {valorAtual ? sufixo : ""}
          </span>
          <button
            type="button"
            onClick={() => setEditando(true)}
            className="shrink-0 text-sm font-medium text-primary hover:underline"
          >
            Editar
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap gap-2">
            <Input
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              className="max-w-[160px]"
              autoFocus
            />
            <Button onClick={salvar} disabled={salvando} className="w-auto px-4">
              {salvando ? "Salvando..." : "Salvar"}
            </Button>
            <Button variant="ghost" onClick={cancelar} className="w-auto px-4">
              Cancelar
            </Button>
          </div>
          {erro && <p className="text-sm text-primary">{erro}</p>}
        </div>
      )}
    </div>
  );
}
