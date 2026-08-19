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
      <body className="bg-[#0a0f1c] text-white flex h-screen overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-8 relative">
          {children}
        </main>
      </body>
    </html>
  );
}
