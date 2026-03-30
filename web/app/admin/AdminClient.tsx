"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { useState } from "react";

type GovRow = { id: number; source: string; title: string; file_name: string; file_format: string; download_url: string | null; collected_at: string };
type LegalRow = { id: number; source: string; title: string; file_format: string; download_url: string | null; collected_at: string };
type UnifiedRow = { uid: string; source_name: string; form_title: string; doc_format: string; download_url: string | null; collected_at: string };
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
  const [pendingDelete, setPendingDelete] = useState<{ row: T; label: string } | null>(null);
  const [reason, setReason] = useState("");

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

  function openDeleteModal(row: T) {
    const label = ((row as Record<string, unknown>).file_name ?? (row as Record<string, unknown>).title ?? row.id) as string;
    setReason("");
    setPendingDelete({ row, label });
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    const { row, label } = pendingDelete;
    setPendingDelete(null);
    setDeletingId(row.id);
    setMessage(null);
    try {
      const res = await fetch(deleteApiPath, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: row.id, reason: reason.trim() || null }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.error);
      setRows((prev) => prev.filter((r) => r.id !== row.id));
      setMessage({ type: "success", text: `삭제 완료: ${label}` });
    } catch (e) {
      setMessage({ type: "error", text: String(e) });
    } finally {
      setDeletingId(null);
      setReason("");
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
                            onClick={() => openDeleteModal(row)}
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

      {/* 삭제 확인 모달 */}
      {pendingDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4 space-y-4">
            <h3 className="text-base font-semibold text-gray-800">삭제 확인</h3>
            <div className="text-sm text-gray-600 space-y-1">
              <p><span className="font-medium">출처:</span> {pendingDelete.row.source}</p>
              <p><span className="font-medium">항목:</span> {pendingDelete.label}</p>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-gray-700">삭제 사유</label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="사유를 입력하세요 (선택)"
                rows={3}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-400 resize-none"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setPendingDelete(null); setReason(""); }}
                className="px-4 py-2 text-sm rounded border border-gray-300 hover:bg-gray-50"
              >
                취소
              </button>
              <button
                onClick={confirmDelete}
                className="px-4 py-2 text-sm rounded bg-red-600 text-white hover:bg-red-700"
              >
                삭제
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── RecentSection ────────────────────────────────────────────────────────────

type RecentSectionProps = {
  data: UnifiedRow[];
  count: number;
  page: number;
  pageSize: number;
  keyword: string;
  dateFrom: string;
  activeDates: Record<string, number>;
  onKeywordChange: (k: string) => void;
  onDateFromChange: (d: string) => void;
  onPageChange: (p: number) => void;
};

function RecentSection({ data, count, page, pageSize, keyword, dateFrom, activeDates, onKeywordChange, onDateFromChange, onPageChange }: RecentSectionProps) {
  const today = new Date().toISOString().slice(0, 10);
  const week = new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10);
  const month = new Date(Date.now() - 29 * 86400000).toISOString().slice(0, 10);
  const PRESETS: Record<string, string> = { "전체": "", "오늘": today, "최근 1주일": week, "최근 1개월": month };
  const presetValues = Object.values(PRESETS);
  const isInitialCustom = dateFrom !== "" && !presetValues.includes(dateFrom);

  const [sectionVisible, setSectionVisible] = useState(true);
  const [kw, setKw] = useState(keyword);
  const [rows, setRows] = useState<UnifiedRow[]>(data);
  const [customMode, setCustomMode] = useState(isInitialCustom);
  const [deletingUid, setDeletingUid] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [pendingDelete, setPendingDelete] = useState<{ uid: string; source: string; label: string } | null>(null);
  const [reason, setReason] = useState("");

  const totalPages = Math.ceil(count / pageSize);
  const startItem = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, count);

  function openDeleteModal(row: UnifiedRow) {
    setReason("");
    setPendingDelete({ uid: row.uid, source: row.source_name, label: row.form_title });
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    const { uid, label } = pendingDelete;
    setPendingDelete(null);
    setDeletingUid(uid);
    setMessage(null);
    try {
      const res = await fetch("/api/admin/unified", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uid, reason: reason.trim() || null }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.error);
      setRows((prev) => prev.filter((r) => r.uid !== uid));
      setMessage({ type: "success", text: `삭제 완료: ${label}` });
    } catch (e) {
      setMessage({ type: "error", text: String(e) });
    } finally {
      setDeletingUid(null);
      setReason("");
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
      <div className="flex items-center gap-3">
        <h2 className="text-base font-semibold text-gray-800">최근 수집 데이터</h2>
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
          <div className="bg-white p-3 rounded-lg border border-gray-200 text-sm space-y-2">
            <form
              onSubmit={(e) => { e.preventDefault(); onKeywordChange(kw); }}
              className="flex flex-wrap items-center gap-3"
            >
              <input
                type="text"
                placeholder="제목 / 출처 검색"
                value={kw}
                onChange={(e) => setKw(e.target.value)}
                className="border border-gray-300 rounded px-2 py-1 focus:outline-none focus:border-blue-400 min-w-48"
              />
              <button type="submit" className="bg-blue-600 text-white rounded px-3 py-1 hover:bg-blue-700 font-medium">
                검색
              </button>
              {keyword && (
                <button type="button" onClick={() => { setKw(""); onKeywordChange(""); }} className="text-xs text-gray-400 hover:text-gray-600">
                  초기화
                </button>
              )}
            </form>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-1 border-t border-gray-100">
              <span className="font-medium text-gray-600 text-xs shrink-0">수집일</span>
              {(["전체", "오늘", "최근 1주일", "최근 1개월"] as const).map((label) => (
                <label key={label} className="flex items-center gap-1 cursor-pointer select-none text-xs text-gray-700">
                  <input
                    type="radio"
                    name="dateRange"
                    checked={!customMode && dateFrom === PRESETS[label]}
                    onChange={() => { setCustomMode(false); onDateFromChange(PRESETS[label]); }}
                    className="accent-blue-600"
                  />
                  {label}
                </label>
              ))}
              <label className="flex items-center gap-1 cursor-pointer select-none text-xs text-gray-700">
                <input
                  type="radio"
                  name="dateRange"
                  checked={customMode}
                  onChange={() => {
                    setCustomMode(true);
                    const first = Object.keys(activeDates).sort().reverse()[0] ?? "";
                    onDateFromChange(first);
                  }}
                  className="accent-blue-600"
                />
                직접 선택
              </label>
              {customMode && (() => {
                const sortedDates = Object.entries(activeDates).sort((a, b) => b[0].localeCompare(a[0]));
                return (
                  <select
                    value={dateFrom}
                    onChange={(e) => onDateFromChange(e.target.value)}
                    className="border border-gray-300 rounded px-2 py-0.5 text-xs focus:outline-none focus:border-blue-400"
                  >
                    {sortedDates.map(([date, cnt]) => (
                      <option key={date} value={date}>{date} ({cnt.toLocaleString()}건)</option>
                    ))}
                  </select>
                );
              })()}
              <span className="ml-auto text-gray-400 text-xs shrink-0">{startItem}–{endItem} / {count.toLocaleString()}건</span>
            </div>
          </div>

          {message && (
            <div className={`text-sm p-3 rounded-lg border ${message.type === "success" ? "bg-green-50 border-green-200 text-green-700" : "bg-red-50 border-red-200 text-red-700"}`}>
              {message.text}
            </div>
          )}

          <div className="bg-white rounded-lg border border-gray-200">
            {rows.length === 0 ? (
              <div className="text-center py-12 text-gray-400 text-sm">항목이 없습니다.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-gray-50 border-y border-gray-200">
                      <th className="text-left px-3 py-2 font-medium text-gray-600 whitespace-nowrap">출처</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600 whitespace-nowrap">제목</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600 whitespace-nowrap">형식</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600 whitespace-nowrap">수집일</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600 whitespace-nowrap">다운로드</th>
                      <th className="px-3 py-2" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {rows.map((row) => (
                      <tr key={row.uid} className="hover:bg-gray-50">
                        <td className="px-3 py-2 text-gray-700 whitespace-nowrap">{row.source_name}</td>
                        <td className="px-3 py-2 text-gray-700 max-w-xs truncate" title={row.form_title}>{row.form_title}</td>
                        <td className="px-3 py-2 text-gray-700 whitespace-nowrap">{row.doc_format || "—"}</td>
                        <td className="px-3 py-2 text-gray-700 whitespace-nowrap">
                          {row.collected_at ? new Date(row.collected_at).toLocaleDateString("ko-KR") : "—"}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          {row.download_url ? (
                            <a href={row.download_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                              다운로드
                            </a>
                          ) : (
                            <span className="text-gray-300">—</span>
                          )}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <button
                            onClick={() => openDeleteModal(row)}
                            disabled={deletingUid === row.uid}
                            className="text-xs bg-red-50 text-red-600 border border-red-200 rounded px-2 py-1 hover:bg-red-100 disabled:opacity-50"
                          >
                            {deletingUid === row.uid ? "삭제 중…" : "삭제"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {totalPages > 1 && (
            <div className="flex justify-center gap-1 text-sm">
              <button onClick={() => onPageChange(page - 1)} disabled={page === 1} className="px-3 py-1 rounded border border-gray-300 disabled:opacity-30 hover:bg-gray-50">
                이전
              </button>
              {pageNums.map((n, i) =>
                n === "..." ? (
                  <span key={`e-${i}`} className="px-3 py-1 text-gray-400">…</span>
                ) : (
                  <button
                    key={n}
                    onClick={() => onPageChange(n as number)}
                    className={`px-3 py-1 rounded border ${page === n ? "bg-blue-600 text-white border-blue-600" : "border-gray-300 hover:bg-gray-50"}`}
                  >
                    {n}
                  </button>
                )
              )}
              <button onClick={() => onPageChange(page + 1)} disabled={page === totalPages} className="px-3 py-1 rounded border border-gray-300 disabled:opacity-30 hover:bg-gray-50">
                다음
              </button>
            </div>
          )}
        </>
      )}

      {pendingDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4 space-y-4">
            <h3 className="text-base font-semibold text-gray-800">삭제 확인</h3>
            <div className="text-sm text-gray-600 space-y-1">
              <p><span className="font-medium">출처:</span> {pendingDelete.source}</p>
              <p><span className="font-medium">항목:</span> {pendingDelete.label}</p>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-gray-700">삭제 사유</label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="사유를 입력하세요 (선택)"
                rows={3}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-400 resize-none"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => { setPendingDelete(null); setReason(""); }} className="px-4 py-2 text-sm rounded border border-gray-300 hover:bg-gray-50">
                취소
              </button>
              <button onClick={confirmDelete} className="px-4 py-2 text-sm rounded bg-red-600 text-white hover:bg-red-700">
                삭제
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── AdminClient ──────────────────────────────────────────────────────────────

type Props = {
  unifiedData: UnifiedRow[];
  unifiedCount: number;
  unifiedPage: number;
  unifiedKeyword: string;
  unifiedDateFrom: string;
  unifiedActiveDates: Record<string, number>;
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
  unifiedData, unifiedCount, unifiedPage, unifiedKeyword, unifiedDateFrom, unifiedActiveDates,
  govData, govCount, govPage, govSources, govFormats, govFilters,
  legalData, legalCount, legalPage, legalSources, legalFormats, legalFilters,
  pageSize,
}: Props) {
  const router = useRouter();

  function buildUrl(o: {
    unifiedPage?: number; unifiedKeyword?: string; unifiedDateFrom?: string;
    govPage?: number; govSources?: string[]; govFormat?: string; govKeyword?: string;
    legalPage?: number; legalSources?: string[]; legalFormat?: string; legalKeyword?: string;
  }) {
    const up = o.unifiedPage ?? unifiedPage;
    const uk = o.unifiedKeyword !== undefined ? o.unifiedKeyword : unifiedKeyword;
    const ud = o.unifiedDateFrom !== undefined ? o.unifiedDateFrom : unifiedDateFrom;
    const gp = o.govPage ?? govPage;
    const gs = o.govSources ?? govFilters.sources;
    const gf = o.govFormat !== undefined ? o.govFormat : govFilters.format;
    const gk = o.govKeyword !== undefined ? o.govKeyword : govFilters.keyword;
    const lp = o.legalPage ?? legalPage;
    const ls = o.legalSources ?? legalFilters.sources;
    const lf = o.legalFormat !== undefined ? o.legalFormat : legalFilters.format;
    const lk = o.legalKeyword !== undefined ? o.legalKeyword : legalFilters.keyword;

    const params = new URLSearchParams();
    if (up > 1) params.set("up", String(up));
    if (uk) params.set("uk", uk);
    if (ud) params.set("ud", ud);
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
      <RecentSection
        key={`unified-${unifiedPage}-${unifiedKeyword}-${unifiedDateFrom}`}
        data={unifiedData}
        count={unifiedCount}
        page={unifiedPage}
        pageSize={pageSize}
        keyword={unifiedKeyword}
        dateFrom={unifiedDateFrom}
        activeDates={unifiedActiveDates}
        onKeywordChange={(k) => router.push(buildUrl({ unifiedKeyword: k, unifiedPage: 1 }))}
        onDateFromChange={(d) => router.push(buildUrl({ unifiedDateFrom: d, unifiedPage: 1 }))}
        onPageChange={(p) => router.push(buildUrl({ unifiedPage: p }))}
      />

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
