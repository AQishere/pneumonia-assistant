import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Summary",
  description: "Your latest device readings, today's risk check and your lab results.",
};

export default function Layout({ children }: LayoutProps<"/dashboard">) {
  return children;
}
