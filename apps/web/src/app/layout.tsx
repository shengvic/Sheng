import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import type { ReactNode } from "react";

import { Providers } from "@/components/Providers";
import { LOCALE_COOKIE, parseLocale } from "@/i18n/locale";

import "./globals.css";

export const metadata: Metadata = {
  title: "Travo",
  description: "Contract review for Southeast Asian law firms",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  const fallback = parseLocale(process.env.TRAVO_DEFAULT_LOCALE);
  const locale = parseLocale((await cookies()).get(LOCALE_COOKIE)?.value, fallback);
  return (
    <html lang={locale} suppressHydrationWarning>
      <head>
        {/* Apply the saved theme before paint to avoid a flash (allowed by the CSP nonce). */}
        <script
          nonce={nonce}
          dangerouslySetInnerHTML={{
            __html:
              "try{var t=localStorage.getItem('travo.theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t)}catch(e){}",
          }}
        />
      </head>
      <body>
        <Providers locale={locale}>{children}</Providers>
      </body>
    </html>
  );
}
