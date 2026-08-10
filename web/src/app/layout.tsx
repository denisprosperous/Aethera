import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AETHERA — Sovereign Computational Geometry Platform",
  description: "Absolute Geometric Substrate — No hardcoded areas, no coordinate bias",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body style={{ margin: 0, padding: 0, background: '#000', color: '#fff', fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif' }}>
        {children}
      </body>
    </html>
  );
}
