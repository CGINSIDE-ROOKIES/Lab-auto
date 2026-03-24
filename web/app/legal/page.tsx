import { createClient } from "@/lib/supabase/server";
import { LegalFormsClient } from "./LegalFormsClient";

const PAGE_SIZE = 100;

type SearchParams = {
  page?: string;
  keyword?: string;
  sources?: string;
  format?: string;
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

  const supabase = await createClient();
  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  let query = supabase
    .from("unified_forms")
    .select("uid, source_name, form_title, doc_format, download_url, collected_at", { count: "exact" });

  if (keyword) query = query.ilike("form_title", `%${keyword}%`);
  if (sourceList.length > 0) query = query.in("source_name", sourceList);
  if (format) query = query.eq("doc_format", format);

  const [{ data, count }, { data: sourcesRaw }, { data: formatsRaw }] = await Promise.all([
    query.order("collected_at", { ascending: false }).range(from, to),
    supabase.from("unified_forms").select("source_name").order("source_name").limit(50000),
    supabase.from("unified_forms").select("doc_format").limit(50000),
  ]);

  const sources = [...new Set(sourcesRaw?.map((d) => d.source_name).filter(Boolean) ?? [])].sort() as string[];
  const formats = [...new Set(formatsRaw?.map((d) => d.doc_format).filter(Boolean) ?? [])].sort() as string[];

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
        filters={{ keyword, sources: sourceList, format }}
      />
    </div>
  );
}
