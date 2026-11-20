import type { Metadata, Viewport } from "next";
import { DM_Mono, Inter_Tight, Poppins } from "next/font/google";
import "./globals.css";

// Fonts and colors come from the Stage references (D049): Poppins UI, DM Mono labels, Inter Tight on Cinema.
const poppins = Poppins({ subsets: ["latin"], weight: ["300", "400", "500", "600"], variable: "--f-ui" });
const mono = DM_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--f-mono" });
const inter = Inter_Tight({ subsets: ["latin"], weight: ["300", "400", "500", "600"], variable: "--f-cin" });

export const metadata: Metadata = {
  title: "Clipp",
  description: "Private clip review",
  robots: { index: false, follow: false },
  icons: { icon: "/icon.svg" },
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Clipp", statusBarStyle: "black-translucent" },
};

export const viewport: Viewport = { themeColor: "#000002", width: "device-width", initialScale: 1, viewportFit: "cover" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${poppins.variable} ${mono.variable} ${inter.variable}`}>
      <body>{children}</body>
    </html>
  );
}
