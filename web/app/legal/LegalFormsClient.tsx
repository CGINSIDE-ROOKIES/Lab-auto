"use client";

import { useRouter, usePathname } from "next/navigation";
import { useState } from "react";
import { DataTable, type Column } from "@/components/DataTable";

type UnifiedForm = {
  uid: number;
  source_name: string;
  form_title: string;
  doc_format: string;
  download_url: string;
  collected_at: string;
};

type Filters = { keyword: string; sources: string[]; format: string };

type Props = {
  initialData: UnifiedForm[];
  totalCount: number;
  page: number;
  pageSize: number;
  sources: string[];
  formats: string[];
  filters: Filters;
};

const COLUMNS: Column<UnifiedForm>[] = [
  { key: "uid", label: "일련번호" },
  { key: "source_name", label: "출처" },
  { key: "form_title", label: "서식제목" },
  { key: "doc_format", label: "형식" },
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
        <a href={v as string} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
          다운로드
        </a>
      ) : (
        <span className="text-gray-300">—</span>
      ),
  },
];

export function LegalFormsClient({ initialData, totalCount, page, pageSize, sources, formats, filters }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const [keyword, setKeyword] = useState(filters.keyword);
  const [selectedSources, setSelectedSources] = useState<string[]>(filters.sources);
  const totalPages = Math.ceil(totalCount / pageSize);
  const startItem = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, totalCount);

  function buildUrl(overrides: Partial<{ keyword: string; sources: string[]; format: string; page: number }>) {
    const params = new URLSearchParams();
    const kw = overrides.keyword !== undefined ? overrides.keyword : filters.keyword;
    const src = overrides.sources !== undefined ? overrides.sources : selectedSources;
    const fmt = overrides.format !== undefined ? overrides.format : filters.format;
    const pg = overrides.page !== undefined ? overrides.page : page;
    if (kw) params.set("keyword", kw);
    if (src.length > 0) params.set("sources", src.join(","));
    if (fmt) params.set("format", fmt);
    if (pg > 1) params.set("page", String(pg));
    const qs = params.toString();
    return qs ? `${pathname}?${qs}` : pathname;
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    router.push(buildUrl({ keyword, page: 1 }));
  }

  function toggleSource(source: string) {
    const next = selectedSources.includes(source)
      ? selectedSources.filter((s) => s !== source)
      : [...selectedSources, source];
    setSelectedSources(next);
    router.push(buildUrl({ sources: next, page: 1 }));
  }

  const pageNums: (number | "...")[] = [];
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pageNums.push(i);
  } else {
    pageNums.push(1);
    if (page > 3) pageNums.push("...");
    for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) pageNums.push(i);
    if (page < totalPages - 2) pageNums.push("...");
    pageNums.push(totalPages);
  }

  return (
    <div className="space-y-4">
      {/* 검색 바 */}
      <form onSubmit={handleSearch} className="flex flex-wrap gap-3 bg-white p-3 rounded-lg border border-gray-200 text-sm">
        <input
          type="text"
          placeholder="서식제목 검색"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          className="border border-gray-300 rounded px-2 py-1 focus:outline-none focus:border-blue-400"
        />
        <button type="submit" className="bg-blue-600 text-white rounded px-3 py-1 hover:bg-blue-700">
          검색
        </button>
        <select
          value={filters.format}
          onChange={(e) => router.push(buildUrl({ format: e.target.value, page: 1 }))}
          className="border border-gray-300 rounded px-2 py-1 focus:outline-none"
        >
          <option value="">전체 형식</option>
          {formats.map((f) => <option key={f}>{f}</option>)}
        </select>
        <span className="ml-auto text-gray-400 self-center">
          전체 {totalCount.toLocaleString()}건 · {startItem}–{endItem} 표시
        </span>
      </form>

      {/* 출처 체크박스 */}
      <div className="bg-white p-3 rounded-lg border border-gray-200 text-sm">
        <div className="flex items-center gap-2 mb-2">
          <span className="font-medium text-gray-600">출처 필터</span>
          {selectedSources.length < sources.length && (
            <button
              onClick={() => { setSelectedSources([...sources]); router.push(buildUrl({ sources: [...sources], page: 1 })); }}
              className="text-xs text-blue-500 hover:underline"
            >
              전체 선택
            </button>
          )}
          {selectedSources.length > 0 && (
            <button
              onClick={() => { setSelectedSources([]); router.push(buildUrl({ sources: [], page: 1 })); }}
              className="text-xs text-blue-500 hover:underline"
            >
              전체 해제
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-2">
          {sources.map((s) => (
            <label key={s} className="flex items-center gap-1 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={selectedSources.includes(s)}
                onChange={() => toggleSource(s)}
                className="accent-blue-600"
              />
              <span className="text-gray-700">{s}</span>
            </label>
          ))}
        </div>
      </div>

      {/* 테이블 */}
      <div className="bg-white rounded-lg border border-gray-200">
        <DataTable columns={COLUMNS} data={initialData} emptyMessage="조건에 맞는 서식이 없습니다." />
      </div>

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-1 text-sm">
          <button
            onClick={() => router.push(buildUrl({ page: page - 1 }))}
            disabled={page === 1}
            className="px-3 py-1 rounded border border-gray-300 disabled:opacity-30 hover:bg-gray-50"
          >
            이전
          </button>
          {pageNums.map((n, i) =>
            n === "..." ? (
              <span key={`ellipsis-${i}`} className="px-3 py-1 text-gray-400">…</span>
            ) : (
              <button
                key={n}
                onClick={() => router.push(buildUrl({ page: n as number }))}
                className={`px-3 py-1 rounded border ${
                  page === n ? "bg-blue-600 text-white border-blue-600" : "border-gray-300 hover:bg-gray-50"
                }`}
              >
                {n}
              </button>
            )
          )}
          <button
            onClick={() => router.push(buildUrl({ page: page + 1 }))}
            disabled={page === totalPages}
            className="px-3 py-1 rounded border border-gray-300 disabled:opacity-30 hover:bg-gray-50"
          >
            다음
          </button>
        </div>
      )}
    </div>
  );
}
