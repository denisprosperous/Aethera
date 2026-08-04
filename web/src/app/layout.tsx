import './globals.css';
export const metadata = {
  title: 'AETHERA — Consensus Hall of Shame',
  description: 'Strain tensor overlay of scholarly map projections. Pure geometric substrate — no radius, no G, no ephemeris.',
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (<html lang="en"><body>{children}</body></html>);
}
