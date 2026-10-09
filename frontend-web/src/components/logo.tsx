import Link from "next/link";
import { Droplet } from "lucide-react";

export function Logo({ className = "", href = "/" }: { className?: string; href?: string }) {
  return (
    <Link href={href} className={`inline-flex items-center gap-2 ${className}`} aria-label="GlicAI — início">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-accent text-white shadow-sm">
        <Droplet size={17} strokeWidth={2.5} fill="currentColor" fillOpacity={0.25} />
      </span>
      <span className="font-heading text-xl font-bold tracking-tight">
        Glic<span className="text-primary">AI</span>
      </span>
    </Link>
  );
}
