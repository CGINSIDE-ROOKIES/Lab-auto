"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { useState } from "react";

type GovRow = { id: number; source: string; title: string; file_name: string; file_format: string; download_url: string | null; collected_at: string };
type LegalRow = { id: number; source: string; title: string; file_format: string; download_url: string | null; collected_at: string };
type Filters = { sources: string[]; format: string; keyword: string };
type ColDef = { key: string; label: string; truncate?: boolean; noWrap?: boolean; render?: (val: unknown) => React.ReactNode };

// ─── AdminSection ─────────────────────────────────────────────────────────────

type SectionProps<T extends { id: number; source: string }> = {
  title: string;
  data: T[];
  count: number;
  page: number;
  pageSize: number;
  sources: string[];
  formats: string[];
  filters: Filters;
  searchPlaceholder: string;
  columns: ColDef[];
  deleteApiPath: string;
  onSourcesChange: (s: string[]) => void;
  onFormatChange: (f: string) => void;
  onKeywordChange: (k: string) => void;
  onPageChange: (p: number) => void;
};

function AdminSection<T extends { id: number; source: string }>({
  title, data, count, page, pageSize, sources, formats, filters,
  searchPlaceholder, columns, deleteApiPath,
  onSourcesChange, onFormatChange, onKeywordChange, onPageChange,
}: SectionProps<T>) {
  const [sectionVisible, setSectionVisible] = useState(true);
  const [filterVisible, setFilterVisible] = useState(true);
  const [keyword, setKeyword] = useState(filters.keyword);
  const [selectedSources, setSelectedSources] = useState<string[]>(filters.sources);
  const [rows, setRows] = useState<T[]>(data);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const totalPages = Math.ceil(count / pageSize);
  const startItem = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, count);

  function toggleSource(s: string) {
    const next = selectedSources.includes(s)
      ? selectedSources.filter((x) => x !== s)
      : [...selectedSources, s];
    setSelectedSources(next);
    onSourcesChange(next);
  }

  async function deleteRow(row: T) {
    const label = ((row as Record<string, unknown>).file_name ?? (row as Record<string, unknown>).title ?? row.id) as string;
    if (!confirm(`삭제하시겠습니까?\n\n출처: ${row.source}\n항목: ${label}`)) return;
    setDeletingId(row.id);
    setMessage(null);
    try {
      const res = await fetch(deleteApiPath, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: row.id }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.error);
      setRows((prev) => prev.filter((r) => r.id !== row.id));
      setMessage({ type: "success", text: `삭제 완료: ${label}` });
    } catch (e) {
      setMessage({ type: "error", text: String(e) });
    } finally {
      setDeletingId(null);
    }
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
    <div className="space-y-3">
      {/* 섹션 헤더 */}
      <div className="flex items-center gap-3">
        <h2 className="text-base font-semibold text-gray-800">{title}</h2>
        <span className="text-sm text-gray-400">전체 {count.toLocaleString()}건</span>
        <button
          onClick={() => setSectionVisible((v) => !v)}
          className="ml-auto text-xs text-gray-400 hover:text-gray-600 border border-gray-300 rounded px-2 py-1"
        >
          {sectionVisible ? "숨기기" : "펼치기"}
        </button>
      </div>

      {sectionVisible && (
        <>
          {/* 검색 + 필터 */}
          <div className="bg-white p-3 rounded-lg border border-gray-200 text-sm space-y-2">
            {/* 검색바 */}
            <form
              onSubmit={(e) => { e.preventDefault(); onKeywordChange(keyword); }}
              className="flex flex-wrap items-center gap-3"
            >
              <input
                type="text"
                placeholder={searchPlaceholder}
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                className="border border-gray-300 rounded px-2 py-1 focus:outline-none focus:border-blue-400 min-w-48"
              />
              <button
                type="submit"
                className="bg-blue-600 text-white rounded px-3 py-1 hover:bg-blue-700 font-medium"
              >
                검색
              </button>
              {filters.keyword && (
                <button
                  type="button"
                  onClick={() => { setKeyword(""); onKeywordChange(""); }}
                  className="text-xs text-gray-400 hover:text-gray-600"
                >
                  초기화
                </button>
              )}
            </form>

            {/* 필터 헤더 */}
            <div className="flex items-center gap-2 pt-1 border-t border-gray-100">
              <span className="font-medium text-gray-600">출처 필터</span>
              {filterVisible && selectedSources.length < sources.length && (
                <button
                  onClick={() => { setSelectedSources([...sources]); onSourcesChange([...sources]); }}
                  className="text-xs text-blue-500 hover:underline"
                >
                  전체 선택
                </button>
              )}
              {filterVisible && selectedSources.length > 0 && (
                <button
                  onClick={() => { setSelectedSources([]); onSourcesChange([]); }}
                  className="text-xs text-blue-500 hover:underline"
                >
                  전체 해제
                </button>
              )}
              <select
                value={filters.format}
                onChange={(e) => onFormatChange(e.target.value)}
                className="ml-2 border border-gray-300 rounded px-2 py-0.5 text-xs focus:outline-none"
              >
                <option value="">전체 형식</option>
                {formats.map((f) => <option key={f}>{f}</option>)}
              </select>
              <span className="ml-auto text-gray-400 text-xs">
                {startItem}–{endItem} / {count.toLocaleString()}건
              </span>
              <button
                onClick={() => setFilterVisible((v) => !v)}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                {filterVisible ? "숨기기" : "펼치기"}
              </button>
            </div>

            {/* 출처 체크박스 */}
            {filterVisible && (
              <div className="flex flex-wrap gap-x-4 gap-y-2 pl-1">
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
            )}
          </div>

          {message && (
            <div
              className={`text-sm p-3 rounded-lg border ${
                message.type === "success"
                  ? "bg-green-50 border-green-200 text-green-700"
                  : "bg-red-50 border-red-200 text-red-700"
              }`}
            >
              {message.text}
            </div>
          )}

          {/* 데이터 테이블 */}
          <div className="bg-white rounded-lg border border-gray-200">
            {rows.length === 0 ? (
              <div className="text-center py-12 text-gray-400 text-sm">항목이 없습니다.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-gray-50 border-y border-gray-200">
                      <th className="text-left px-3 py-2 font-medium text-gray-600 whitespace-nowrap">ID</th>
                      {columns.map((col) => (
                        <th key={col.key} className="text-left px-3 py-2 font-medium text-gray-600 whitespace-nowrap">
                          {col.label}
                        </th>
                      ))}
                      <th className="px-3 py-2" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {rows.map((row) => (
                      <tr key={row.id} className="hover:bg-gray-50">
                        <td className="px-3 py-2 text-gray-400 text-xs">{row.id}</td>
                        {columns.map((col) => {
                          const val = (row as Record<string, unknown>)[col.key];
                          return (
                            <td
                              key={col.key}
                              className={`px-3 py-2 text-gray-700 ${
                                col.truncate ? "max-w-xs truncate" : col.noWrap ? "whitespace-nowrap" : ""
                              }`}
                              title={col.truncate ? String(val ?? "") : undefined}
                            >
                              {col.render
                                ? col.render(val)
                                : col.key === "collected_at"
                                ? new Date(val as string).toLocaleDateString("ko-KR")
                                : String(val ?? "—")}
                            </td>
                          );
                        })}
                        <td className="px-3 py-2 whitespace-nowrap">
                          <button
                            onClick={() => deleteRow(row)}
                            disabled={deletingId === row.id}
                            className="text-xs bg-red-50 text-red-600 border border-red-200 rounded px-2 py-1 hover:bg-red-100 disabled:opacity-50"
                          >
                            {deletingId === row.id ? "삭제 중…" : "삭제"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* 페이지네이션 */}
          {totalPages > 1 && (
            <div className="flex justify-center gap-1 text-sm">
              <button
                onClick={() => onPageChange(page - 1)}
                disabled={page === 1}
                className="px-3 py-1 rounded border border-gray-300 disabled:opacity-30 hover:bg-gray-50"
              >
                이전
              </button>
              {pageNums.map((n, i) =>
                n === "..." ? (
                  <span key={`e-${i}`} className="px-3 py-1 text-gray-400">…</span>
                ) : (
                  <button
                    key={n}
                    onClick={() => onPageChange(n as number)}
                    className={`px-3 py-1 rounded border ${
                      page === n ? "bg-blue-600 text-white border-blue-600" : "border-gray-300 hover:bg-gray-50"
                    }`}
                  >
                    {n}
                  </button>
                )
              )}
              <button
                onClick={() => onPageChange(page + 1)}
                disabled={page === totalPages}
                className="px-3 py-1 rounded border border-gray-300 disabled:opacity-30 hover:bg-gray-50"
              >
                다음
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─── AdminClient ──────────────────────────────────────────────────────────────

type Props = {
  govData: GovRow[];
  govCount: number;
  govPage: number;
  govSources: string[];
  govFormats: string[];
  govFilters: Filters;
  legalData: LegalRow[];
  legalCount: number;
  legalPage: number;
  legalSources: string[];
  legalFormats: string[];
  legalFilters: Filters;
  pageSize: number;
};

export function AdminClient({
  govData, govCount, govPage, govSources, govFormats, govFilters,
  legalData, legalCount, legalPage, legalSources, legalFormats, legalFilters,
  pageSize,
}: Props) {
  const router = useRouter();

  function buildUrl(o: {
    govPage?: number; govSources?: string[]; govFormat?: string; govKeyword?: string;
    legalPage?: number; legalSources?: string[]; legalFormat?: string; legalKeyword?: string;
  }) {
    const gp = o.govPage ?? govPage;
    const gs = o.govSources ?? govFilters.sources;
    const gf = o.govFormat !== undefined ? o.govFormat : govFilters.format;
    const gk = o.govKeyword !== undefined ? o.govKeyword : govFilters.keyword;
    const lp = o.legalPage ?? legalPage;
    const ls = o.legalSources ?? legalFilters.sources;
    const lf = o.legalFormat !== undefined ? o.legalFormat : legalFilters.format;
    const lk = o.legalKeyword !== undefined ? o.legalKeyword : legalFilters.keyword;

    const params = new URLSearchParams();
    if (gp > 1) params.set("gp", String(gp));
    if (gs.length > 0) params.set("gs", gs.join(","));
    if (gf) params.set("gf", gf);
    if (gk) params.set("gk", gk);
    if (lp > 1) params.set("lp", String(lp));
    if (ls.length > 0) params.set("ls", ls.join(","));
    if (lf) params.set("lf", lf);
    if (lk) params.set("lk", lk);
    const qs = params.toString();
    return qs ? `/admin?${qs}` : "/admin";
  }

  return (
    <div className="space-y-10">
      <AdminSection<GovRow>
        key={`gov-${govPage}-${govFilters.sources.join()}-${govFilters.format}-${govFilters.keyword}`}
        title="정부부처 계약서 — gov_contracts"
        data={govData}
        count={govCount}
        page={govPage}
        pageSize={pageSize}
        sources={govSources}
        formats={govFormats}
        filters={govFilters}
        searchPlaceholder="파일명 검색"
        columns={[
          { key: "source", label: "출처", noWrap: true },
          { key: "file_name", label: "파일명", truncate: true },
          { key: "title", label: "제목", truncate: true },
          { key: "file_format", label: "형식", noWrap: true },
          { key: "collected_at", label: "수집일", noWrap: true },
          {
            key: "download_url",
            label: "다운로드",
            noWrap: true,
            render: (v) =>
              v ? (
                <a href={v as string} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                  다운로드
                </a>
              ) : (
                <span className="text-gray-300">—</span>
              ),
          },
        ]}
        deleteApiPath="/api/admin/gov-contracts"
        onSourcesChange={(s) => router.push(buildUrl({ govSources: s, govPage: 1 }))}
        onFormatChange={(f) => router.push(buildUrl({ govFormat: f, govPage: 1 }))}
        onKeywordChange={(k) => router.push(buildUrl({ govKeyword: k, govPage: 1 }))}
        onPageChange={(p) => router.push(buildUrl({ govPage: p }))}
      />

      <AdminSection<LegalRow>
        key={`legal-${legalPage}-${legalFilters.sources.join()}-${legalFilters.format}-${legalFilters.keyword}`}
        title="법률서식 — legal_forms"
        data={legalData}
        count={legalCount}
        page={legalPage}
        pageSize={pageSize}
        sources={legalSources}
        formats={legalFormats}
        filters={legalFilters}
        searchPlaceholder="제목 검색"
        columns={[
          { key: "source", label: "출처", noWrap: true },
          { key: "title", label: "제목", truncate: true },
          { key: "file_format", label: "형식", noWrap: true },
          { key: "collected_at", label: "수집일", noWrap: true },
          {
            key: "download_url",
            label: "다운로드",
            noWrap: true,
            render: (v) =>
              v ? (
                <a href={v as string} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                  다운로드
                </a>
              ) : (
                <span className="text-gray-300">—</span>
              ),
          },
        ]}
        deleteApiPath="/api/admin/legal-forms"
        onSourcesChange={(s) => router.push(buildUrl({ legalSources: s, legalPage: 1 }))}
        onFormatChange={(f) => router.push(buildUrl({ legalFormat: f, legalPage: 1 }))}
        onKeywordChange={(k) => router.push(buildUrl({ legalKeyword: k, legalPage: 1 }))}
        onPageChange={(p) => router.push(buildUrl({ legalPage: p }))}
      />
    </div>
  );
}
