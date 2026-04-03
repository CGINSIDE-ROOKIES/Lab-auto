"use client";

import { useRouter, usePathname } from "next/navigation";
import { useState } from "react";
import { DataTable, type Column } from "@/components/DataTable";

const LEGAL_SOURCES = ["대한법률구조공단", "전자소송포털"];

type UnifiedForm = {
  uid: string;
  source_name: string;
  form_title: string;
  doc_format: string;
  download_url: string;
  collected_at: string;
};

type CatCombo = { cat_large: string; cat_medium: string; cat_small: string };

type Filters = {
  keyword: string;
  sources: string[];
  format: string;
  catLarge: string;
  catMedium: string;
  catSmall: string;
  tag: string;
};

type Props = {
  initialData: UnifiedForm[];
  totalCount: number;
  page: number;
  pageSize: number;
  sources: string[];
  formats: string[];
  catCombos: CatCombo[];
  tags: string[];
  filters: Filters;
};

const COLUMNS: Column<UnifiedForm>[] = [
  { key: "uid", label: "일련번호" },
  { key: "source_name", label: "출처", style: { whiteSpace: "nowrap", width: "1%" } },
  { key: "form_title", label: "서식제목" },
  { key: "doc_format", label: "형식" },
  {
    key: "collected_at",
    label: "수집일",
    render: (v) => new Date(v as string).toLocaleDateString("ko-KR"),
    style: { whiteSpace: "nowrap", width: "1%" },
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

export function LegalFormsClient({
  initialData,
  totalCount,
  page,
  pageSize,
  sources,
  formats,
  catCombos,
  tags,
  filters,
}: Props) {
  const router = useRouter();
  const pathname = usePathname();

  const [keyword, setKeyword] = useState(filters.keyword);
  const [selectedSources, setSelectedSources] = useState<string[]>(filters.sources);
  const [filterVisible, setFilterVisible] = useState(true);
  const [tagVisible, setTagVisible] = useState(true);

  const totalPages = Math.ceil(totalCount / pageSize);
  const startItem = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, totalCount);

  // 카테고리 계층 파생
  const largeOptions = [...new Set(catCombos.map((c) => c.cat_large))].sort();
  const mediumOptions = [...new Set(
    catCombos
      .filter((c) => !filters.catLarge || c.cat_large === filters.catLarge)
      .map((c) => c.cat_medium)
      .filter(Boolean)
  )].sort();
  const smallOptions = [...new Set(
    catCombos
      .filter(
        (c) =>
          (!filters.catLarge || c.cat_large === filters.catLarge) &&
          (!filters.catMedium || c.cat_medium === filters.catMedium)
      )
      .map((c) => c.cat_small)
      .filter(Boolean)
  )].sort();

  function buildUrl(overrides: Partial<{
    keyword: string;
    sources: string[];
    format: string;
    catLarge: string;
    catMedium: string;
    catSmall: string;
    tag: string;
    page: number;
  }>) {
    const params = new URLSearchParams();
    const kw  = overrides.keyword    !== undefined ? overrides.keyword    : filters.keyword;
    const src = overrides.sources    !== undefined ? overrides.sources    : selectedSources;
    const fmt = overrides.format     !== undefined ? overrides.format     : filters.format;
    const cl  = overrides.catLarge   !== undefined ? overrides.catLarge   : filters.catLarge;
    const cm  = overrides.catMedium  !== undefined ? overrides.catMedium  : filters.catMedium;
    const cs  = overrides.catSmall   !== undefined ? overrides.catSmall   : filters.catSmall;
    const tg  = overrides.tag        !== undefined ? overrides.tag        : filters.tag;
    const pg  = overrides.page       !== undefined ? overrides.page       : page;
    if (kw) params.set("keyword", kw);
    if (src.length > 0) params.set("sources", src.join(","));
    if (fmt) params.set("format", fmt);
    if (cl) params.set("cl", cl);
    if (cm) params.set("cm", cm);
    if (cs) params.set("cs", cs);
    if (tg) params.set("tag", tg);
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

  function handleCatLarge(val: string) {
    router.push(buildUrl({ catLarge: val, catMedium: "", catSmall: "", page: 1 }));
  }
  function handleCatMedium(val: string) {
    router.push(buildUrl({ catMedium: val, catSmall: "", page: 1 }));
  }
  function handleCatSmall(val: string) {
    router.push(buildUrl({ catSmall: val, page: 1 }));
  }
  function handleTag(val: string) {
    router.push(buildUrl({ tag: filters.tag === val ? "" : val, page: 1 }));
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

  const legalSources = sources.filter((s) => LEGAL_SOURCES.includes(s));
  const govSources   = sources.filter((s) => !LEGAL_SOURCES.includes(s));
  const allLegalSelected = legalSources.length > 0 && legalSources.every((s) => selectedSources.includes(s));
  const allGovSelected   = govSources.length > 0   && govSources.every((s) => selectedSources.includes(s));

  function toggleGroup(groupSources: string[], selectAll: boolean) {
    const next = selectAll
      ? [...new Set([...selectedSources, ...groupSources])]
      : selectedSources.filter((s) => !groupSources.includes(s));
    setSelectedSources(next);
    router.push(buildUrl({ sources: next, page: 1 }));
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

        {/* 카테고리 드롭다운 */}
        <select
          value={filters.catLarge}
          onChange={(e) => handleCatLarge(e.target.value)}
          className="border border-gray-300 rounded px-2 py-1 focus:outline-none"
        >
          <option value="">전체 대분류</option>
          {largeOptions.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select
          value={filters.catMedium}
          onChange={(e) => handleCatMedium(e.target.value)}
          disabled={mediumOptions.length === 0}
          className="border border-gray-300 rounded px-2 py-1 focus:outline-none disabled:opacity-40"
        >
          <option value="">전체 중분류</option>
          {mediumOptions.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select
          value={filters.catSmall}
          onChange={(e) => handleCatSmall(e.target.value)}
          disabled={smallOptions.length === 0}
          className="border border-gray-300 rounded px-2 py-1 focus:outline-none disabled:opacity-40"
        >
          <option value="">전체 소분류</option>
          {smallOptions.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>

        <span className="ml-auto text-gray-400 self-center">
          전체 {totalCount.toLocaleString()}건 · {startItem}–{endItem} 표시
        </span>
      </form>

      {/* 출처 + 태그 필터 패널 */}
      <div className="bg-white p-3 rounded-lg border border-gray-200 text-sm space-y-3">
        {/* 출처 헤더 */}
        <div className="flex items-center gap-2">
          <span className="font-medium text-gray-600">출처 필터</span>
          {filterVisible && selectedSources.length < sources.length && (
            <button
              onClick={() => { setSelectedSources([...sources]); router.push(buildUrl({ sources: [...sources], page: 1 })); }}
              className="text-xs text-blue-500 hover:underline"
            >
              전체 선택
            </button>
          )}
          {filterVisible && selectedSources.length > 0 && (
            <button
              onClick={() => { setSelectedSources([]); router.push(buildUrl({ sources: [], page: 1 })); }}
              className="text-xs text-blue-500 hover:underline"
            >
              전체 해제
            </button>
          )}
          <button
            onClick={() => setFilterVisible((v) => !v)}
            className="ml-auto text-xs text-gray-400 hover:text-gray-600"
          >
            {filterVisible ? "숨기기" : "펼치기"}
          </button>
        </div>

        {/* 법률서식 그룹 */}
        {filterVisible && legalSources.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-1">
              <button
                onClick={() => toggleGroup(legalSources, !allLegalSelected)}
                className={`text-xs px-2 py-0.5 rounded border font-medium ${
                  allLegalSelected
                    ? "bg-indigo-100 border-indigo-300 text-indigo-700"
                    : "border-gray-300 text-gray-500 hover:bg-gray-50"
                }`}
              >
                법률서식
              </button>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-2 pl-1">
              {legalSources.map((s) => (
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
        )}

        {/* 정부부처 그룹 */}
        {filterVisible && govSources.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-1">
              <button
                onClick={() => toggleGroup(govSources, !allGovSelected)}
                className={`text-xs px-2 py-0.5 rounded border font-medium ${
                  allGovSelected
                    ? "bg-indigo-100 border-indigo-300 text-indigo-700"
                    : "border-gray-300 text-gray-500 hover:bg-gray-50"
                }`}
              >
                정부부처
              </button>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-2 pl-1">
              {govSources.map((s) => (
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
        )}

        {/* 구분선 */}
        {tags.length > 0 && <hr className="border-gray-100" />}

        {/* 태그 필터 */}
        {tags.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="font-medium text-gray-600">태그 필터</span>
              {filters.tag && (
                <button
                  onClick={() => router.push(buildUrl({ tag: "", page: 1 }))}
                  className="text-xs text-blue-500 hover:underline"
                >
                  초기화
                </button>
              )}
              <button
                onClick={() => setTagVisible((v) => !v)}
                className="ml-auto text-xs text-gray-400 hover:text-gray-600"
              >
                {tagVisible ? "숨기기" : "펼치기"}
              </button>
            </div>
            {tagVisible && (
              <div className="flex flex-wrap gap-1.5 max-h-40 overflow-y-auto pr-1">
                {tags.map((t) => (
                  <button
                    key={t}
                    onClick={() => handleTag(t)}
                    className={`text-xs px-2 py-0.5 rounded-full border transition-colors ${
                      filters.tag === t
                        ? "bg-blue-600 text-white border-blue-600"
                        : "border-gray-300 text-gray-600 hover:border-blue-400 hover:text-blue-600"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
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
