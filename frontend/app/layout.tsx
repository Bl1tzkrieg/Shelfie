import type { Metadata } from 'next'
// Geist viene en el paquete `geist` (next/font/local): el build no descarga nada de
// internet, así que compila también en una intranet sin salida.
import { GeistSans } from 'geist/font/sans'
import { GeistMono } from 'geist/font/mono'
import { SesionProvider } from '@/components/auth/sesion-provider'
import { Toaster } from '@/components/ui/sonner'
import './globals.css'

export const metadata: Metadata = {
  title: 'Shelfie - Sistema de Biblioteca',
  description: 'Catálogo de la biblioteca',
  icons: {
    icon: [
      {
        url: '/icon-light-32x32.png',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/icon-dark-32x32.png',
        media: '(prefers-color-scheme: dark)',
      },
      {
        url: '/icon.svg',
        type: 'image/svg+xml',
      },
    ],
    apple: '/apple-icon.png',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="es" className="bg-background">
      <body className={`${GeistSans.variable} ${GeistMono.variable} font-sans antialiased`}>
        <SesionProvider>
          {children}
        </SesionProvider>
        <Toaster richColors position="top-right" />
      </body>
    </html>
  )
}
