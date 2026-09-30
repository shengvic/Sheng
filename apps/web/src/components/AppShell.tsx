"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { LanguageSwitch } from "@/components/LanguageSwitch";
import { useT } from "@/i18n/context";
import { api } from "@/lib/api";
import { CSRF_HEADER } from "@/lib/csrf";

import { Button, cx } from "./ui";

function ThemeToggle() {
  const t = useT();
  const [theme, setTheme] = useState<"light" | "dark" | "system">("system");
  useEffect(() => {
    try {
      const saved = localStorage.getItem("travo.theme");
      if (saved === "light" || saved === "dark") setTheme(saved);
    } catch {
      // Storage blocked (private mode / policy): fall back to system theme.
    }
  }, []);
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("travo.theme", theme);
    } catch {
      // Not persisted; the theme still applies for this page view.
    }
  }, [theme]);
  const next = theme === "system" ? "dark" : theme === "dark" ? "light" : "system";
  return (
    <Button variant="ghost" size="sm" onClick={() => setTheme(next)} aria-label={t.common.theme.label(theme)}>
      {theme === "dark" ? t.common.theme.dark : theme === "light" ? t.common.theme.light : t.common.theme.auto}
    </Button>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const t = useT();
  const router = useRouter();
  const pathname = usePathname();
  // proxy.ts already redirected requests without a session cookie; the API decides validity.
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });

  async function signOut() {
    await fetch("/auth/logout", { method: "POST", headers: { [CSRF_HEADER]: "1" } }).catch(() => null);
    router.replace("/login");
  }

  const nav = [
    { href: "/matters", label: t.nav.matters },
    { href: "/playbooks", label: t.nav.playbooks },
    ...(me.data?.role === "admin" ? [{ href: "/admin", label: t.nav.admin }] : []),
  ];
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-border bg-surface/95 backdrop-blur">
        <div className="mx-auto flex h-12 max-w-[1600px] items-center gap-6 px-4">
          <Link href="/matters" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="grid h-6 w-6 place-items-center rounded bg-accent text-xs text-accent-ink">T</span>
            {t.appName}
          </Link>
          <nav className="flex gap-1" aria-label={t.nav.main}>
            {nav.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className={cx(
                  "rounded-md px-2.5 py-1 text-sm",
                  pathname?.startsWith(n.href) ? "bg-surface-2 font-medium" : "text-muted hover:text-text",
                )}
              >
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <LanguageSwitch />
            <ThemeToggle />
            {me.data && (
              <span className="hidden text-sm text-muted sm:inline" data-testid="whoami">
                {me.data.name} · <span className="capitalize">{me.data.role}</span> · {me.data.tenant_name}
              </span>
            )}
            <Button variant="ghost" size="sm" onClick={signOut}>
              {t.auth.signOut}
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-5">{children}</main>
    </div>
  );
}
