import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Claude",
  description:
    "Claude is Anthropic's AI, built for problem solvers. Tackle complex challenges, analyze data, write code, and think through tough problems.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full antialiased">{children}</body>
    </html>
  );
}
