import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI カルテ生成システム",
  description: "ローカル LLM によるカルテ下書き生成",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
