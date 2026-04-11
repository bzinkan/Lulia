import './globals.css';
import Sidebar from '@/components/Sidebar';
import ChatSidebar from '@/components/ChatSidebar';
import AppShell from '@/components/AppShell';

export const metadata = {
  title: 'Lulia Lesson Lab — AI-Powered LMS',
  description: 'AI teaching partner that generates standards-aligned content',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="font-sans bg-warm-bg text-text-dark">
        {/* Retro dot-grid texture overlay */}
        <div className="retro-pattern" />
        <Sidebar />
        {/* Main content area */}
        <main className="md:ml-[240px] pt-14 md:pt-0 min-h-screen relative z-10">
          <AppShell>
            {children}
          </AppShell>
        </main>
        <ChatSidebar />
      </body>
    </html>
  );
}
