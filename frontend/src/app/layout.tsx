import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AgentForge",
  description: "Build, red-team & ship LLM agents",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} min-h-screen font-sans antialiased`}
      >
        <header className="border-b border-neutral-800 bg-neutral-950/80 backdrop-blur">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
            <Link href="/" className="text-lg font-semibold tracking-tight text-cyan-400">
              AgentForge
            </Link>
            <nav className="flex gap-4 text-sm text-neutral-400">
              <Link href="/agents" className="hover:text-white">
                Agents
              </Link>
              <Link href="/sandbox" className="hover:text-white">
                Sandbox
              </Link>
              <Link href="/campaigns" className="hover:text-white">
                Campaigns
              </Link>
              <Link href="/skills" className="hover:text-white">
                Skills
              </Link>
              <Link href="/finetune" className="hover:text-white">
                Finetune
              </Link>
              <Link href="/login" className="hover:text-white">
                Login
              </Link>
              <Link href="/register" className="hover:text-white">
                Register
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
