import type { Metadata } from 'next';
import AppShell from '@/components/AppShell';
import './globals.css';

export const metadata: Metadata = {
  title: 'AutoPilot FDE · Operations workspace',
  description: 'An evidence-led workspace for reviewing workflows and exercising synthetic operational examples.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><AppShell>{children}</AppShell></body></html>;
}
