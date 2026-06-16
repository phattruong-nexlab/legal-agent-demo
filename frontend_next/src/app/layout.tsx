import type { Metadata } from "next";
import "./globals.css";
import NavSidebar from "@/components/NavSidebar";

export const metadata: Metadata = {
  title: "Legal Knowledge Graph",
  description: "Khám phá đồ thị văn bản pháp luật trên Neo4j Aura",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body>
        <div className="flex min-h-screen">
          <NavSidebar />
          <main className="flex-1 overflow-x-hidden">{children}</main>
        </div>
      </body>
    </html>
  );
}
