import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Patient",
  description: "A linked patient's readings, latest result and history.",
};

export default function Layout({ children }: LayoutProps<"/doctor/[id]">) {
  return children;
}
