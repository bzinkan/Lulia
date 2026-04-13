import './globals.css';
import Sidebar from '@/components/Sidebar';
import ChatSidebar from '@/components/ChatSidebar';
import AppShell from '@/components/AppShell';
import MainContentShell from '@/components/MainContentShell';

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
        <MainContentShell>
          <AppShell>
            {children}
          </AppShell>
        </MainContentShell>
        <ChatSidebar />
      </body>
    </html>
  );
}
