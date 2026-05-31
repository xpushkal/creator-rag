import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "creator-rag",
  description: "Compare two short-form videos and ask why one outperformed the other.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans bg-neutral-950 text-neutral-50 antialiased selection:bg-indigo-500/30`}>
        {children}
      </body>
    </html>
  );
}
