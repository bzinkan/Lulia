import './globals.css';
import Sidebar from '@/components/Sidebar';
import ChatSidebar from '@/components/ChatSidebar';
import AppShell from '@/components/AppShell';
import MainContentShell from '@/components/MainContentShell';
import QueryProvider from '@/components/QueryProvider';

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
        {/* QueryProvider wraps everything so any descendant that opts into
            TanStack Query (starting with the dashboard home page) shares
            one client + cache. Pages that don't use Query are unaffected. */}
        <QueryProvider>
          <Sidebar />
          <MainContentShell>
            <AppShell>
              {children}
            </AppShell>
          </MainContentShell>
          <ChatSidebar />
        </QueryProvider>
      </body>
    </html>
  );
}
