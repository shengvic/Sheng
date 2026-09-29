import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Providers } from "@/components/Providers";

import "./globals.css";

export const metadata: Metadata = {
  title: "Travo",
  description: "Contract review for Southeast Asian law firms",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Apply the saved theme before paint to avoid a flash. */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{var t=localStorage.getItem('travo.theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t)}catch(e){}",
          }}
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
