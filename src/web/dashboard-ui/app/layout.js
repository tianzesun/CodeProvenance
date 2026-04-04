import './globals.css';

/** @type {import('next').Metadata} */
export const metadata = {
  title: 'IntegrityDesk | Academic Integrity Platform',
  description: 'Professional code similarity detection and academic integrity analysis',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
