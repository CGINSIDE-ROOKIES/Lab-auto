"use client";

import { useState, useMemo } from "react";
import { DataTable, type Column } from "@/components/DataTable";

type GovContract = {
  id: number;
  ministry: string;
  title: string;
  file_name: string;
  file_ext: string;
  department: string;
  registered_date: string;
  source_url: string;
  download_url: string;
  collected_at: string;
};

const COLUMNS: Column<GovContract>[] = [
  { key: "ministry", label: "부처" },
  { key: "title", label: "서식제목" },
  { key: "file_name", label: "파일명" },
  { key: "file_ext", label: "형식" },
  { key: "department", label: "담당부서" },
  { key: "registered_date", label: "등록일" },
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

export function ContractsClient({ initialData }: { initialData: GovContract[] }) {
  const [keyword, setKeyword] = useState("");
  const [ministry, setMinistry] = useState("");
  const [since, setSince] = useState("");

  const ministries = useMemo(
    () => [...new Set(initialData.map((d) => d.ministry).filter(Boolean))].sort(),
    [initialData]
  );

  const filtered = useMemo(
    () =>
      initialData.filter((d) => {
        if (keyword && !d.title.includes(keyword) && !d.file_name?.includes(keyword))
          return false;
        if (ministry && d.ministry !== ministry) return false;
        if (since && new Date(d.collected_at) < new Date(since)) return false;
        return true;
      }),
    [initialData, keyword, ministry, since]
  );

  return (
    <div className="space-y-4">
      {/* 필터 */}
      <div className="flex flex-wrap gap-3 bg-white p-3 rounded-lg border border-gray-200 text-sm">
        <input
          type="text"
          placeholder="제목 / 파일명 검색"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          className="border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:border-blue-400"
        />
        <select
          value={ministry}
          onChange={(e) => setMinistry(e.target.value)}
          className="border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none"
        >
          <option value="">전체 부처</option>
          {ministries.map((m) => <option key={m}>{m}</option>)}
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
        <DataTable columns={COLUMNS} data={filtered} emptyMessage="조건에 맞는 계약서가 없습니다." />
      </div>
    </div>
  );
}
