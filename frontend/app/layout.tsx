import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Afferens Memory Guardian",
  description: "Live physical-perception dashboard for evidence-backed home assistance."
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
