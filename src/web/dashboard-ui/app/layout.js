import { Manrope, Space_Grotesk } from 'next/font/google';

import { ThemeProvider } from '@/components/ThemeProvider';
import './globals.css';

const bodyFont = Manrope({
  subsets: ['latin'],
  variable: '--font-body',
});

const displayFont = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-display',
});

/** @type {import('next').Metadata} */
export const metadata = {
  title: 'IntegrityDesk | Academic Integrity Platform',
  description: 'Professional code similarity detection and academic integrity analysis',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning data-theme="light">
      <body className={`${bodyFont.variable} ${displayFont.variable} antialiased`}>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
