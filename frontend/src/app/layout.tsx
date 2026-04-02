import type { Metadata } from "next";
import { JetBrains_Mono, Space_Grotesk } from "next/font/google";
import Script from "next/script";
import { AppHeader } from "@/components/layout/AppHeader";
import { AuroraBackground } from "@/components/layout/AuroraBackground";
import { ClientProviders } from "@/components/layout/ClientProviders";
import "./globals.css";

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
});

export const metadata: Metadata = {
  title: "AgentForge | Engineering the future of autonomous intelligence",
  description: "Build, red-team & ship LLM agents",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&display=swap"
        />
      </head>
      <body
        className={`${jetbrains.variable} ${spaceGrotesk.variable} min-h-screen bg-af-bg font-mono antialiased`}
      >
        <Script src="/theme-init.js" strategy="beforeInteractive" />
        <AuroraBackground />
        <AppHeader />
        <ClientProviders>
          <div className="relative z-10 pt-16">{children}</div>
        </ClientProviders>
      </body>
    </html>
  );
}
