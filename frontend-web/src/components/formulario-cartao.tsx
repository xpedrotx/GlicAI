"use client";

import { useMemo, useState } from "react";
import { CardCvcElement, CardExpiryElement, CardNumberElement, Elements, useElements, useStripe } from "@stripe/react-stripe-js";
import { loadStripe } from "@stripe/stripe-js";
import { useTheme } from "next-themes";
import { Lock } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Plano } from "@/lib/types";
import { Button, ErrorText, Field, Label } from "@/components/ui";

/**
 * Formulário de cartão dentro da nossa página (Stripe Elements). Os três
 * campos são iframes do Stripe: número, validade e CVC vão direto do navegador
 * pro Stripe e nunca passam pelo nosso servidor — a gente só recebe o id do
 * cartão (pm_...) que o Stripe gera, e manda pro backend criar a assinatura.
 */
export function FormularioCartao({
  publishableKey,
  preco,
  aoConcluir,
}: {
  publishableKey: string;
  preco: string;
  aoConcluir: (plano: Plano) => void;
}) {
  const stripe = useMemo(() => loadStripe(publishableKey), [publishableKey]);
  return (
    <Elements stripe={stripe} options={{ locale: "pt-BR" }}>
      <Campos preco={preco} aoConcluir={aoConcluir} />
    </Elements>
  );
}

type Campo = "numero" | "validade" | "cvc";

function Campos({ preco, aoConcluir }: { preco: string; aoConcluir: (plano: Plano) => void }) {
  const stripe = useStripe();
  const elements = useElements();
  const { resolvedTheme } = useTheme();
  const escuro = resolvedTheme === "dark";

  const [completos, setCompletos] = useState<Record<Campo, boolean>>({ numero: false, validade: false, cvc: false });
  const [erros, setErros] = useState<Partial<Record<Campo, string>>>({});
  const [foco, setFoco] = useState<Campo | null>(null);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  // Os campos são iframes: não enxergam as variáveis CSS da página, então as
  // cores precisam ser passadas direto (por isso depende do tema).
  const estilo = {
    style: {
      base: {
        fontSize: "15px",
        fontFamily: "Inter, system-ui, sans-serif",
        color: escuro ? "#f3eee6" : "#1b3a4b",
        iconColor: escuro ? "#f3eee6" : "#1b3a4b",
        "::placeholder": { color: escuro ? "rgba(255,255,255,0.4)" : "rgba(27,58,75,0.4)" },
      },
      invalid: { color: "#e5484d", iconColor: "#e5484d" },
    },
  };

  const pronto = completos.numero && completos.validade && completos.cvc;

  function aoMudar(campo: Campo) {
    return (e: { complete: boolean; error?: { message: string } }) => {
      setCompletos((c) => ({ ...c, [campo]: e.complete }));
      setErros((x) => ({ ...x, [campo]: e.error?.message }));
      setErro("");
    };
  }

  async function aoEnviar(evento: React.FormEvent) {
    evento.preventDefault();
    const numero = elements?.getElement(CardNumberElement);
    if (!stripe || !elements || !numero) return;

    setErro("");
    setEnviando(true);
    try {
      const { paymentMethod, error } = await stripe.createPaymentMethod({
        type: "card",
        card: numero,
        billing_details: { address: { country: "BR" } },
      });
      if (error || !paymentMethod) {
        setErro(error?.message ?? "Não consegui validar o cartão. Confira os dados.");
        return;
      }

      let resultado = await api.assinar(paymentMethod.id);

      if (resultado.status === "requer_acao") {
        // O banco pediu autenticação (3D Secure): o Stripe abre a janela dele
        const { error: erroAutenticacao } = await stripe.confirmCardPayment(resultado.client_secret);
        if (erroAutenticacao) {
          setErro(erroAutenticacao.message ?? "Não foi possível autenticar o pagamento.");
          return;
        }
        const confirmado = await api.confirmarAssinatura(resultado.assinatura_id);
        if (confirmado.status !== "ok") {
          setErro("O pagamento ainda não foi confirmado. Aguarde alguns instantes e atualize a página.");
          return;
        }
        resultado = { ...confirmado, status: "ok" };
      }

      aoConcluir(resultado as Plano);
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não consegui concluir o pagamento agora. Tente de novo.");
    } finally {
      setEnviando(false);
    }
  }

  const caixa = (campo: Campo) =>
    `rounded-xl border bg-card px-3.5 py-3 transition ${
      erros[campo] ? "border-vermelho" : foco === campo ? "border-primary ring-4 ring-primary/15" : "border-border"
    }`;

  return (
    <form onSubmit={aoEnviar} className="flex flex-col gap-4">
      <Field>
        <Label>Número do cartão</Label>
        <div className={caixa("numero")}>
          <CardNumberElement
            options={{ ...estilo, showIcon: true, disableLink: true, placeholder: "1234 1234 1234 1234" }}
            onChange={aoMudar("numero")}
            onFocus={() => setFoco("numero")}
            onBlur={() => setFoco(null)}
          />
        </div>
        {erros.numero && <p className="text-xs text-vermelho">{erros.numero}</p>}
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field>
          <Label>Validade</Label>
          <div className={caixa("validade")}>
            <CardExpiryElement
              options={{ ...estilo, placeholder: "MM / AA" }}
              onChange={aoMudar("validade")}
              onFocus={() => setFoco("validade")}
              onBlur={() => setFoco(null)}
            />
          </div>
          {erros.validade && <p className="text-xs text-vermelho">{erros.validade}</p>}
        </Field>
        <Field>
          <Label>Código de segurança</Label>
          <div className={caixa("cvc")}>
            <CardCvcElement
              options={{ ...estilo, placeholder: "CVC" }}
              onChange={aoMudar("cvc")}
              onFocus={() => setFoco("cvc")}
              onBlur={() => setFoco(null)}
            />
          </div>
          {erros.cvc && <p className="text-xs text-vermelho">{erros.cvc}</p>}
        </Field>
      </div>

      <ErrorText>{erro}</ErrorText>

      <Button type="submit" carregando={enviando} disabled={!stripe || !pronto} className="mt-1 w-full py-3 sm:w-auto sm:self-start">
        {!enviando && <Lock size={16} />}
        {enviando ? "Processando..." : `Assinar por ${preco}`}
      </Button>
    </form>
  );
}
