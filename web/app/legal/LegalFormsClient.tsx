"use client";

import { useState, useMemo } from "react";
import { DataTable, type Column } from "@/components/DataTable";

type LegalForm = {
  id: number;
  source: string;
  category_main: string;
  category_mid: string;
  title: string;
  file_format: string;
  download_url: string;
  collected_at: string;
};

const COLUMNS: Column<LegalForm>[] = [
  { key: "source", label: "수집처" },
  { key: "category_main", label: "대분류" },
  { key: "category_mid", label: "중분류" },
  { key: "title", label: "서식제목" },
  { key: "file_format", label: "형식" },
  {
    key: "collected_at",
    label: "수집일",
    render: (v) => new Date(v as string).toLocaleDateString("ko-KR"),
  },
  {
    key: "download_url",
    label: "다운로드",
    render: (v) =>
      v ? (
        <a
          href={v as string}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:underline"
        >
          다운로드
        </a>
      ) : (
        <span className="text-gray-300">—</span>
      ),
  },
];

export function LegalFormsClient({ initialData }: { initialData: LegalForm[] }) {
  const [keyword, setKeyword] = useState("");
  const [source, setSource] = useState("");
  const [format, setFormat] = useState("");
  const [since, setSince] = useState("");

  const sources = useMemo(
    () => [...new Set(initialData.map((d) => d.source).filter(Boolean))],
    [initialData]
  );
  const formats = useMemo(
    () => [...new Set(initialData.map((d) => d.file_format).filter(Boolean))],
    [initialData]
  );

  const filtered = useMemo(
    () =>
      initialData.filter((d) => {
        if (keyword && !d.title.includes(keyword)) return false;
        if (source && d.source !== source) return false;
        if (format && d.file_format !== format) return false;
        if (since && new Date(d.collected_at) < new Date(since)) return false;
        return true;
      }),
    [initialData, keyword, source, format, since]
  );

  return (
    <div className="space-y-4">
      {/* 필터 */}
      <div className="flex flex-wrap gap-3 bg-white p-3 rounded-lg border border-gray-200 text-sm">
        <input
          type="text"
          placeholder="제목 검색"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          className="border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:border-blue-400"
        />
        <select
          value={source}
          onChange={(e) => setSource(e.target.value)}
          className="border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none"
        >
          <option value="">전체 수집처</option>
          {sources.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select
          value={format}
          onChange={(e) => setFormat(e.target.value)}
          className="border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none"
        >
          <option value="">전체 형식</option>
          {formats.map((f) => <option key={f}>{f}</option>)}
        </select>
        <div className="flex items-center gap-1">
          <span className="text-gray-500">수집일 이후</span>
          <input
            type="date"
            value={since}
            onChange={(e) => setSince(e.target.value)}
            className="border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none"
          />
        </div>
        <span className="ml-auto text-gray-400 self-center">{filtered.length}건</span>
      </div>

      {/* 테이블 */}
      <div className="bg-white rounded-lg border border-gray-200">
        <DataTable columns={COLUMNS} data={filtered} emptyMessage="조건에 맞는 서식이 없습니다." />
      </div>
    </div>
  );
}
