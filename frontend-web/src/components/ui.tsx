import type { ButtonHTMLAttributes, InputHTMLAttributes, LabelHTMLAttributes, ReactNode } from "react";
import { LoaderCircle } from "lucide-react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-border bg-card p-6 shadow-[var(--sombra)] ${className}`}>{children}</div>
  );
}

export function CardTitulo({
  icone,
  titulo,
  descricao,
  acao,
}: {
  icone?: ReactNode;
  titulo: string;
  descricao?: string;
  acao?: ReactNode;
}) {
  return (
    <div className="mb-5 flex items-start justify-between gap-4">
      <div className="flex items-start gap-3">
        {icone && (
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            {icone}
          </span>
        )}
        <div>
          <h2 className="font-heading text-base font-semibold">{titulo}</h2>
          {descricao && <p className="mt-0.5 text-sm text-muted">{descricao}</p>}
        </div>
      </div>
      {acao}
    </div>
  );
}

export function PageHeader({ titulo, descricao, acao }: { titulo: string; descricao?: string; acao?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-heading text-2xl font-bold tracking-tight sm:text-[28px]">{titulo}</h1>
        {descricao && <p className="mt-1 text-sm text-muted">{descricao}</p>}
      </div>
      {acao}
    </div>
  );
}

export function Field({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`flex flex-col gap-1.5 ${className}`}>{children}</div>;
}

export function Label({ className = "", ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={`text-sm font-medium text-foreground/90 ${className}`} {...props} />;
}

const estiloCampo =
  "w-full rounded-xl border border-border bg-card px-3.5 py-2.5 text-[15px] text-foreground outline-none transition placeholder:text-muted focus:border-primary focus:ring-4 focus:ring-primary/15";

export function Input({
  className = "",
  icone,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { icone?: ReactNode }) {
  if (!icone) return <input className={`${estiloCampo} ${className}`} {...props} />;
  return (
    <div className="relative">
      <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted">{icone}</span>
      <input className={`${estiloCampo} pl-10 ${className}`} {...props} />
    </div>
  );
}

export function Select({ className = "", ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`${estiloCampo} ${className}`} {...props} />;
}

export function Button({
  className = "",
  variant = "primary",
  carregando = false,
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "dark"; carregando?: boolean }) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-[15px] font-semibold transition focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/25 disabled:cursor-not-allowed disabled:opacity-60";
  const estilos = {
    primary: "bg-primary text-primary-foreground shadow-sm shadow-primary/30 hover:brightness-105 active:brightness-95",
    ghost: "border border-border bg-card text-foreground hover:border-primary/50 hover:text-primary",
    dark: "bg-petroleo text-white hover:bg-petroleo-escuro dark:bg-white dark:text-petroleo dark:hover:bg-white/90",
  }[variant];
  return (
    <button className={`${base} ${estilos} ${className}`} disabled={disabled || carregando} {...props}>
      {carregando && <LoaderCircle size={16} className="animate-spin" />}
      {children}
    </button>
  );
}

export function ErrorText({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <p role="alert" className="rounded-xl border border-primary/20 bg-primary/10 px-3.5 py-2.5 text-sm text-primary">
      {children}
    </p>
  );
}

export function StatCard({
  rotulo,
  valor,
  corValor,
  icone,
  detalhe,
}: {
  rotulo: string;
  valor: string;
  corValor?: string;
  icone?: ReactNode;
  detalhe?: string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-[var(--sombra)]">
      <div className="flex items-center justify-between">
        <p className="text-[13px] font-medium text-muted">{rotulo}</p>
        {icone && <span className="text-muted">{icone}</span>}
      </div>
      <p
        className="mt-2 font-heading text-[26px] font-bold leading-none tracking-tight"
        style={corValor ? { color: corValor } : undefined}
      >
        {valor}
      </p>
      {detalhe && <p className="mt-2 text-xs text-muted">{detalhe}</p>}
    </div>
  );
}

export function Segmentado<T extends string | number>({
  opcoes,
  valor,
  aoMudar,
}: {
  opcoes: { valor: T; rotulo: string }[];
  valor: T;
  aoMudar: (v: T) => void;
}) {
  return (
    <div className="inline-flex gap-1 rounded-xl border border-border bg-card p-1">
      {opcoes.map((o) => (
        <button
          key={String(o.valor)}
          type="button"
          onClick={() => aoMudar(o.valor)}
          className={`rounded-lg px-3.5 py-1.5 text-sm font-medium transition ${
            valor === o.valor ? "bg-petroleo text-white dark:bg-white dark:text-petroleo" : "text-muted hover:text-foreground"
          }`}
        >
          {o.rotulo}
        </button>
      ))}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-foreground/[0.07] ${className}`} />;
}

export function Vazio({ icone, titulo, texto }: { icone: ReactNode; titulo: string; texto?: string }) {
  return (
    <div className="flex flex-col items-center px-4 py-8 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-surface text-muted">{icone}</span>
      <p className="mt-3 text-sm font-medium">{titulo}</p>
      {texto && <p className="mt-1 max-w-sm text-sm text-muted">{texto}</p>}
    </div>
  );
}
