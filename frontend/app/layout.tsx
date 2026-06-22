import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  applicationName: "Memory Guardian",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Memory Guardian"
  },
  title: "Afferens Memory Guardian",
  description: "Evidence-backed home memory assistance for patient and caregiver review.",
  manifest: "/manifest.webmanifest"
};

export const viewport: Viewport = {
  themeColor: "#11695f",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover"
};

type RootLayoutProps = {
  children: React.ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
