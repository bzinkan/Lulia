import './globals.css';
import Sidebar from '@/components/Sidebar';

export const metadata = {
  title: 'Lulia — AI-Powered LMS',
  description: 'AI teaching partner that generates standards-aligned content',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="font-sans bg-gray-50 text-gray-800">
        <Sidebar />
        {/* Main content area */}
        <main className="md:ml-64 pt-14 md:pt-0 min-h-screen">
          <div className="p-6">
            {children}
          </div>
        </main>
      </body>
    </html>
  );
}
