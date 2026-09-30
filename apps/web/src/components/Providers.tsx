"use client";

import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { I18nProvider } from "@/i18n/context";
import type { Locale } from "@/i18n/locale";
import { ApiError } from "@/lib/api";

export function Providers({ children, locale }: { children: ReactNode; locale: Locale }) {
  const router = useRouter();
  const [client] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({
          onError: (err) => {
            if (err instanceof ApiError && err.status === 401) {
              const next = window.location.pathname + window.location.search;
              router.replace(`/login?next=${encodeURIComponent(next)}`);
            }
          },
        }),
        defaultOptions: {
          queries: {
            retry: (n, err) => !(err instanceof ApiError && err.status < 500) && n < 2,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );
  return (
    <I18nProvider locale={locale}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </I18nProvider>
  );
}
