import type { Metadata } from "next";
import "./globals.css";
import "./assessment.css";
import "./followup.css";
import "./intelligence.css";
import "./studio.css";

export const metadata: Metadata = {
  title: "Chalkmate · Your teaching workspace",
  description:
    "A considered workspace for classrooms, student records, and the work of teaching.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var p=localStorage.getItem('chalkmate.appearance.v1');document.documentElement.dataset.theme=(p==='light'||p==='dark')?p:(p==='system'?(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'):'dark')}catch(e){document.documentElement.dataset.theme='dark'}})()`,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
