import { createClient } from "@/lib/supabase/server";
import { LegalFormsClient } from "./LegalFormsClient";

const PAGE_SIZE = 100;

type SearchParams = {
  page?: string;
  keyword?: string;
  sources?: string;
  format?: string;
  cl?: string;   // cat_large
  cm?: string;   // cat_medium
  cs?: string;   // cat_small
  tag?: string;  // 태그 (#포함)
};

export default async function LegalPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const page = Math.max(1, parseInt(params.page ?? "1"));
  const keyword = params.keyword ?? "";
  const sourceList = params.sources ? params.sources.split(",").filter(Boolean) : [];
  const format = params.format ?? "";
  const catLarge = params.cl ?? "";
  const catMedium = params.cm ?? "";
  const catSmall = params.cs ?? "";
  const tag = params.tag ?? "";

  const supabase = await createClient();
  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  let query = supabase
    .from("unified_forms")
    .select("uid, source_name, form_title, doc_format, download_url, collected_at", { count: "exact" });

  if (keyword) query = query.ilike("form_title", `%${keyword}%`);
  if (sourceList.length > 0) query = query.in("source_name", sourceList);
  if (format) query = query.eq("doc_format", format);
  if (catLarge) query = query.eq("cat_large", catLarge);
  if (catMedium) query = query.eq("cat_medium", catMedium);
  if (catSmall) query = query.eq("cat_small", catSmall);
  if (tag) query = query.or(`tag1.eq.${tag},tag2.eq.${tag},tag3.eq.${tag}`);

  const [
    { data, count },
    { data: sourcesRaw },
    { data: formatsRaw },
    { data: catHierarchyRaw },
    { data: tagsRaw },
  ] = await Promise.all([
    query.order("collected_at", { ascending: false }).range(from, to),
    supabase.from("unified_forms").select("source_name").order("source_name").limit(50000),
    supabase.from("unified_forms").select("doc_format").limit(50000),
    // 카테고리 계층 (법률서식에만 존재)
    supabase
      .from("legal_forms")
      .select("cat_large,cat_medium,cat_small")
      .not("cat_large", "is", null)
      .limit(10000),
    // 태그 (tag1, tag2, tag3 합산)
    supabase
      .from("legal_forms")
      .select("tag1,tag2,tag3")
      .not("tag1", "is", null)
      .limit(10000),
  ]);

  const sources = [...new Set(sourcesRaw?.map((d) => d.source_name).filter(Boolean) ?? [])].sort() as string[];
  const formats = [...new Set(formatsRaw?.map((d) => d.doc_format).filter(Boolean) ?? [])].sort() as string[];

  // 카테고리 계층 구조 구성
  type CatCombo = { cat_large: string; cat_medium: string; cat_small: string };
  const catCombos: CatCombo[] = (catHierarchyRaw ?? [])
    .filter((r) => r.cat_large)
    .map((r) => ({
      cat_large: r.cat_large!,
      cat_medium: r.cat_medium ?? "",
      cat_small: r.cat_small ?? "",
    }));

  // 고유 태그 수집
  const allTags = new Set<string>();
  for (const row of tagsRaw ?? []) {
    if (row.tag1) allTags.add(row.tag1);
    if (row.tag2) allTags.add(row.tag2);
    if (row.tag3) allTags.add(row.tag3);
  }
  const tags = [...allTags].sort();

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">서식 목록</h1>
        <p className="text-sm text-gray-500">법률서식 및 정부부처 표준계약서 통합 데이터</p>
      </div>
      <LegalFormsClient
        initialData={data ?? []}
        totalCount={count ?? 0}
        page={page}
        pageSize={PAGE_SIZE}
        sources={sources}
        formats={formats}
        catCombos={catCombos}
        tags={tags}
        filters={{ keyword, sources: sourceList, format, catLarge, catMedium, catSmall, tag }}
      />
    </div>
  );
}
