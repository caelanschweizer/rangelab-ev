import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

const title = "RangeLab EV | Bolt telemetry, explained";
const description =
  "A privacy-first EV telemetry lab with trip analytics, data-quality checks, and an honest arrival-charge forecast.";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host =
    requestHeaders.get("x-forwarded-host") ??
    requestHeaders.get("host") ??
    "localhost:3000";
  const protocol =
    requestHeaders.get("x-forwarded-proto") ??
    (host.startsWith("localhost") ? "http" : "https");
  const origin = protocol + "://" + host;
  const socialImage = origin + "/og.png";

  return {
    metadataBase: new URL(origin),
    title,
    description,
    openGraph: {
      title,
      description,
      type: "website",
      url: origin,
      images: [
        {
          url: socialImage,
          width: 1792,
          height: 914,
          alt: "RangeLab EV — Bolt telemetry, explained.",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [socialImage],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
