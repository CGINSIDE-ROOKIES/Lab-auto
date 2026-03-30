import { createClient } from "@/lib/supabase/server";
import { AdminClient } from "./AdminClient";

const PAGE_SIZE = 10;

type SP = {
  gp?: string; gs?: string; gf?: string; gk?: string;
  lp?: string; ls?: string; lf?: string; lk?: string;
};

export default async function AdminPage({ searchParams }: { searchParams: Promise<SP> }) {
  const params = await searchParams;
  const supabase = await createClient();

  const govPage = Math.max(1, parseInt(params.gp ?? "1"));
  const govSourceList = params.gs ? params.gs.split(",").filter(Boolean) : [];
  const govFormat = params.gf ?? "";
  const govKeyword = params.gk ?? "";
  const legalPage = Math.max(1, parseInt(params.lp ?? "1"));
  const legalSourceList = params.ls ? params.ls.split(",").filter(Boolean) : [];
  const legalFormat = params.lf ?? "";
  const legalKeyword = params.lk ?? "";

  let govQuery = supabase
    .from("gov_contracts")
    .select("id, source, title, file_name, file_format, download_url, collected_at", { count: "exact" });
  if (govSourceList.length > 0) govQuery = govQuery.in("source", govSourceList);
  if (govFormat) govQuery = govQuery.eq("file_format", govFormat);
  if (govKeyword) govQuery = govQuery.ilike("file_name", `%${govKeyword}%`);

  let legalQuery = supabase
    .from("legal_forms")
    .select("id, source, title, file_format, download_url, collected_at", { count: "exact" });
  if (legalSourceList.length > 0) legalQuery = legalQuery.in("source", legalSourceList);
  if (legalFormat) legalQuery = legalQuery.eq("file_format", legalFormat);
  if (legalKeyword) legalQuery = legalQuery.ilike("title", `%${legalKeyword}%`);

  const govFrom = (govPage - 1) * PAGE_SIZE;
  const legalFrom = (legalPage - 1) * PAGE_SIZE;

  const [
    { data: govData, count: govCount },
    { data: legalData, count: legalCount },
    { data: govSourcesRaw },
    { data: govFormatsRaw },
    { data: legalSourcesRaw },
    { data: legalFormatsRaw },
  ] = await Promise.all([
    govQuery.order("id", { ascending: false }).range(govFrom, govFrom + PAGE_SIZE - 1),
    legalQuery.order("id", { ascending: false }).range(legalFrom, legalFrom + PAGE_SIZE - 1),
    supabase.from("gov_contracts").select("source").limit(50000),
    supabase.from("gov_contracts").select("file_format").limit(50000),
    supabase.from("legal_forms").select("source").limit(50000),
    supabase.from("legal_forms").select("file_format").limit(50000),
  ]);

  const uniq = <T extends Record<string, string | null>>(arr: T[] | null, key: keyof T) =>
    [...new Set((arr ?? []).map((r) => r[key]).filter(Boolean) as string[])].sort();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold">관리자</h1>
        <p className="text-sm text-gray-500">개별 항목 조회 및 삭제</p>
      </div>
      <AdminClient
        govData={govData ?? []}
        govCount={govCount ?? 0}
        govPage={govPage}
        govSources={uniq(govSourcesRaw, "source")}
        govFormats={uniq(govFormatsRaw, "file_format")}
        govFilters={{ sources: govSourceList, format: govFormat, keyword: govKeyword }}
        legalData={legalData ?? []}
        legalCount={legalCount ?? 0}
        legalPage={legalPage}
        legalSources={uniq(legalSourcesRaw, "source")}
        legalFormats={uniq(legalFormatsRaw, "file_format")}
        legalFilters={{ sources: legalSourceList, format: legalFormat, keyword: legalKeyword }}
        pageSize={PAGE_SIZE}
      />
    </div>
  );
}
