"use client";

import { useMemo } from "react";
import { EmbeddedCheckout, EmbeddedCheckoutProvider } from "@stripe/react-stripe-js";
import { loadStripe } from "@stripe/stripe-js";

/**
 * Formulário de pagamento do Stripe montado dentro da própria página — os
 * dados do cartão vão direto do navegador pro Stripe, nunca passam pelo
 * nosso servidor. Ao concluir, o Stripe redireciona pro return_url definido
 * no backend (/dashboard/assinatura?sessao=...).
 */
export function CheckoutEmbutido({ clientSecret, publishableKey }: { clientSecret: string; publishableKey: string }) {
  const stripe = useMemo(() => loadStripe(publishableKey), [publishableKey]);

  return (
    <div className="overflow-hidden rounded-2xl">
      <EmbeddedCheckoutProvider stripe={stripe} options={{ clientSecret }}>
        <EmbeddedCheckout />
      </EmbeddedCheckoutProvider>
    </div>
  );
}
