import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "creator-rag",
  description: "Compare two short-form videos and ask why one outperformed the other.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
