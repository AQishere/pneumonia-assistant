import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Assistant",
  description: "Ask the assistant about your readings and what your latest result means.",
};

export default function Layout({ children }: LayoutProps<"/chat">) {
  return children;
}
