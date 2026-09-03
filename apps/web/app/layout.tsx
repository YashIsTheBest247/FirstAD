import type { Metadata } from "next";
import { Archivo, DM_Sans, Instrument_Serif, JetBrains_Mono } from "next/font/google";
import "./globals.css";

/* Heavy grotesk for the headline blocks. Archivo holds up at 800 in caps
   without the width distortion a condensed face gets at poster sizes. */
const grotesk = Archivo({
  subsets: ["latin"],
  weight: ["500", "600", "700", "800"],
  variable: "--font-grotesk",
  display: "swap",
});

/* The interruption inside a headline. High contrast, italic only. */
const serif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: "italic",
  variable: "--font-serif",
  display: "swap",
});

const body = DM_Sans({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});

/* Scene numbers, page eighths, call times and money all have to align in a
   column, so they are all set in the mono face. */
const data = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-data",
  display: "swap",
});

export const metadata: Metadata = {
  title: "First AD · Script to shooting schedule",
  description:
    "A 1st Assistant Director for your screenplay. Nine Gemini agents turn a script into a stripboard, a clearance report, a budget, and call sheets.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body
        className={`${grotesk.variable} ${serif.variable} ${body.variable} ${data.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
