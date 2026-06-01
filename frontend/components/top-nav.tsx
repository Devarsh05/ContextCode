import Link from "next/link";
import { Boxes } from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";

/**
 * Minimal top navigation — wordmark left, theme toggle right, hairline border.
 */
export function TopNav() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/60 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center justify-between">
        <Link
          href="/"
          className="group flex items-center gap-2 font-semibold tracking-tight"
        >
          <Boxes className="size-5 text-primary transition-transform group-hover:scale-110" />
          <span>
            Context<span className="text-primary">Code</span>
          </span>
        </Link>
        <nav className="flex items-center gap-1">
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
