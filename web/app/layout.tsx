import type { Metadata } from "next"
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google"
import type { ReactNode } from "react"
import "./globals.css"

const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
})

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
})

export const metadata: Metadata = {
  title: "Anodet",
  description: "Your machines generate data. Your technicians generate knowledge. Anodet connects the two.",
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en">
      <body className={`${sans.variable} ${mono.variable} font-sans antialiased text-foam`}>
        {children}
      </body>
    </html>
  )
}

interface RootLayoutProps {
  children: ReactNode
}
