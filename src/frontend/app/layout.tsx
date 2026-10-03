import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';
import { Manrope, Space_Grotesk } from 'next/font/google';

import { AuthProvider } from '@/components/AuthProvider';
import { ThemeProvider } from '@/components/ThemeProvider';
import './globals.css';

const bodyFont = Manrope({
  subsets: ['latin'],
  variable: '--font-body',
  display: 'swap',
});

const displayFont = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap',
});

// A plain export instead of generateViewport(): nothing here is computed. Zoom is deliberately not
// restricted (no maximumScale / userScalable), so people can still pinch-zoom.
export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  // Browser UI colour (mobile address bar) follows the OS theme; the values match the page backgrounds.
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#020617' },
  ],
};

export const metadata: Metadata = {
  // `template` gives every page that sets its own title (for example "Compare Tools") the product name.
  // Without it those pages replaced the whole title and lost "IntegrityDesk" from the tab.
  title: {
    default: 'IntegrityDesk | Academic Integrity Platform',
    template: '%s | IntegrityDesk',
  },
  description: 'Professional code similarity detection and academic integrity analysis',
  applicationName: 'IntegrityDesk',
  // Private academic tool: keep it out of search indexes and caches. (The string form 'noindex, nofollow'
  // only covered generic crawlers; this also states it for Googlebot and asks not to cache pages.)
  robots: {
    index: false,
    follow: false,
    nocache: true,
    googleBot: { index: false, follow: false, noimageindex: true, nocache: true },
  },
  // Links to other sites (public-source matches, vendor docs) get no Referer. That keeps page URLs, and
  // anything carried in them such as a reset or verification token, from reaching third parties. Requests to
  // this app still receive it. If your API checks the Referer header, change this to
  // 'strict-origin-when-cross-origin'.
  referrer: 'same-origin',
  // Stops iOS from turning numbers in tables (submission counts, ids) into phone-number links.
  formatDetection: { telephone: false, email: false, address: false },
};

interface RootLayoutProps {
  children: ReactNode;
}

export default function RootLayout({ children }: Readonly<RootLayoutProps>) {
  return (
    // en-CA: Canadian English for screen-reader pronunciation and spell-check.
    // suppressHydrationWarning is needed because ThemeProvider sets the theme class on <html>.
    <html lang="en-CA" suppressHydrationWarning>
      <body className={`${bodyFont.variable} ${displayFont.variable} antialiased`}>
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
