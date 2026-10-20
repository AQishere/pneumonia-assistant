import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to keep an eye on your chest health with your devices and lab results.",
};

export default function Layout({ children }: LayoutProps<"/login">) {
  return children;
}
