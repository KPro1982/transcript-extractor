import './globals.css'
import type { Metadata } from 'next'
import { DM_Sans, DM_Serif_Display, JetBrains_Mono } from 'next/font/google'
import { Providers } from './providers'

const dmSans = DM_Sans({ subsets: ['latin'], variable: '--font-sans' })
const dmSerif = DM_Serif_Display({ weight: ['400'], subsets: ['latin'], variable: '--font-serif' })
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' })

export const metadata: Metadata = {
  title: 'DepoDigest - Deposition Summarization',
  description: 'High-performance deposition summarization with AI',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${dmSans.variable} ${dmSerif.variable} ${jetbrainsMono.variable}`}>
      <body className="bg-bg-base text-gray-100 font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}

