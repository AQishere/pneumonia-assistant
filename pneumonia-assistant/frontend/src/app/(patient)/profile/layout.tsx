import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Profile",
  description: "Your health details, long-term conditions and linked doctor.",
};

export default function Layout({ children }: LayoutProps<"/profile">) {
  return children;
}
