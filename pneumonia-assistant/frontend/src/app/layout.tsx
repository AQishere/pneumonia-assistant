import type { Metadata } from "next";
import { Inter, Roboto_Mono } from "next/font/google";

import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/lib/auth-context";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const robotoMono = Roboto_Mono({
  variable: "--font-roboto-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  // Pages set their own title; it shows as "Summary · Pneumonia Assistant".
  title: { template: "%s · Pneumonia Assistant", default: "Pneumonia Assistant" },
  description:
    "Home monitoring for chest infection risk: device readings, lab results and an assistant that explains them. Guidance only, not a diagnosis.",
  applicationName: "Pneumonia Assistant",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${robotoMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-background text-foreground">
        <AuthProvider>{children}</AuthProvider>
        <Toaster richColors position="top-center" />
      </body>
    </html>
  );
}
