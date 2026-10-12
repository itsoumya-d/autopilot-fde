import type { Metadata } from 'next';
import Sidebar from '@/components/Sidebar';
import './globals.css';

export const metadata: Metadata = {
  title: 'AutoPilot FDE',
  description: 'Your AI Forward Deployed Engineer',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#0a0f1c] text-white flex h-dvh flex-col md:flex-row">
        <Sidebar />
        <main className="relative min-h-0 min-w-0 flex-1 overflow-auto p-4 sm:p-6 lg:p-8 [overflow-wrap:anywhere]">
          {children}
        </main>
      </body>
    </html>
  );
}
