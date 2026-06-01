import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

import { Providers } from "@/components/providers";
import { TopNav } from "@/components/top-nav";
import { Toaster } from "@/components/ui/sonner";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "ContextCode — Understand any codebase",
  description:
    "Index a public GitHub repo, chat with it via RAG, and visualize its dependency graph with danger-zone analysis.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} min-h-dvh font-sans antialiased`}
      >
        <Providers>
          <div className="flex min-h-dvh flex-col">
            <TopNav />
            <main className="flex-1">{children}</main>
          </div>
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
