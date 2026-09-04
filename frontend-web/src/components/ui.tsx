import type { ButtonHTMLAttributes, InputHTMLAttributes, LabelHTMLAttributes } from "react";

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-2xl border border-border bg-card p-8 shadow-[0_1px_2px_rgba(27,58,75,0.04),0_8px_24px_rgba(27,58,75,0.06)] ${className}`}
    >
      {children}
    </div>
  );
}

export function Field({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`flex flex-col gap-1.5 ${className}`}>{children}</div>;
}

export function Label({ className = "", ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={`text-sm font-medium text-foreground/90 ${className}`} {...props} />;
}

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-[15px] text-foreground outline-none transition placeholder:text-muted focus:border-primary focus:ring-2 focus:ring-primary/25 ${className}`}
      {...props}
    />
  );
}

export function Button({
  className = "",
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" }) {
  const base =
    "inline-flex w-full items-center justify-center rounded-lg px-4 py-2.5 text-[15px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-60";
  const estilos =
    variant === "primary"
      ? "bg-primary text-primary-foreground hover:brightness-105 active:brightness-95"
      : "border border-border text-foreground hover:border-primary hover:text-primary";
  return <button className={`${base} ${estilos} ${className}`} {...props} />;
}

export function ErrorText({ children }: { children: React.ReactNode }) {
  if (!children) return null;
  return <p className="rounded-lg bg-primary/10 px-3.5 py-2.5 text-sm text-primary">{children}</p>;
}

export function StatCard({
  rotulo,
  valor,
  corValor,
}: {
  rotulo: string;
  valor: string;
  corValor?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card px-4 py-3.5">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{rotulo}</p>
      <p className="mt-1 font-heading text-2xl font-semibold" style={corValor ? { color: corValor } : undefined}>
        {valor}
      </p>
    </div>
  );
}
