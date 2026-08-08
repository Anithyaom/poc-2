import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "simgen",
  description: "AI-authored interactive science simulations",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased" suppressHydrationWarning>
      <body className="min-h-full flex flex-col" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
