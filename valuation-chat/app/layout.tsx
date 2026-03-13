import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Item Valuator - Fair Market Value Estimator",
  description:
    "Take a photo of any item and get an instant fair market value estimate powered by AI and real market data.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
