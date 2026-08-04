import './globals.css';

export const metadata = {
  title: 'AETHERA — Projection Distortion Atlas',
  description: 'Explore how map projections reshape our understanding of the world. Compare physical truth against cartographic convention.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
