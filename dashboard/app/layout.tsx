import type { Metadata, Viewport } from "next";
import { Inter, Sora } from "next/font/google";
import "./globals.css";

// Broadcast (concept C, D092): Sora for display numerals and headings, Inter for UI text.
const sora = Sora({ subsets: ["latin"], weight: ["300", "400", "600", "700"], variable: "--f-display" });
const inter = Inter({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--f-body" });

export const metadata: Metadata = {
  title: "Clipp",
  description: "Private clip review",
  robots: { index: false, follow: false },
  icons: { icon: "/icon.svg" },
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Clipp", statusBarStyle: "black-translucent" },
};

export const viewport: Viewport = { themeColor: "#0d0e12", width: "device-width", initialScale: 1, viewportFit: "cover" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sora.variable} ${inter.variable}`}>
      <body>{children}</body>
    </html>
  );
}
