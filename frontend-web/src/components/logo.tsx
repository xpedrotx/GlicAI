export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`font-heading text-2xl font-semibold tracking-tight ${className}`}>
      Insu<span className="text-primary">leve</span>
    </span>
  );
}
