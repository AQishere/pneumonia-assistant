import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "History",
  description: "Your daily results and the last seven days of device readings.",
};

export default function Layout({ children }: LayoutProps<"/history">) {
  return children;
}
