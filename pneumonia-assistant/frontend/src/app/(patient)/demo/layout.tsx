import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Demo test",
  description: "Run the pneumonia risk models on a made-up patient. Nothing is saved.",
};

export default function Layout({ children }: LayoutProps<"/demo">) {
  return children;
}
