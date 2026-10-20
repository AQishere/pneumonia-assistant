import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Set up your profile",
  description: "Tell us about yourself once so the risk check can use it.",
};

export default function Layout({ children }: LayoutProps<"/onboarding">) {
  return children;
}
