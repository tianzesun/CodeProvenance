import './globals.css'

export const metadata = {
  title: 'IntegrityDesk - Code Similarity Detection Platform',
  description: 'Enterprise-grade multi-engine code similarity detection and plagiarism prevention system',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-slate-900 text-white min-h-screen antialiased">
        {children}
      </body>
    </html>
  )
}