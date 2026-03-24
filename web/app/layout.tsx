import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "법률서식 데이터 플랫폼",
  description: "법률서식 및 정부부처 계약서 수집 데이터 조회",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="min-h-screen bg-gray-50 text-gray-900">
        <nav className="bg-white border-b border-gray-200 px-6 py-3 flex gap-6 text-sm font-medium">
          <a href="/" className="text-blue-600 hover:text-blue-800">홈</a>
          <a href="/legal" className="hover:text-blue-600">법률서식</a>
          <a href="/contracts" className="hover:text-blue-600">정부부처 계약서</a>
        </nav>
        <main className="max-w-7xl mx-auto px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
