import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";

type GovRow = {
  id: number;
  source: string;
  file_name: string;
  file_format: string;
  title: string;
  collected_at: string;
};

export async function GET() {
  const supabase = createAdminClient();

  const { data, error } = await supabase
    .from("gov_contracts")
    .select("id, source, file_name, file_format, title, collected_at")
    .order("id", { ascending: true })
    .range(0, 9999);

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const groups = new Map<string, GovRow[]>();
  for (const row of (data ?? []) as GovRow[]) {
    const key = `${row.source}|||${row.file_name}|||${row.file_format}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(row);
  }

  const duplicates = [...groups.values()]
    .filter((rows) => rows.length > 1)
    .map((rows) => ({
      source: rows[0].source,
      file_name: rows[0].file_name,
      file_format: rows[0].file_format,
      cnt: rows.length,
      keep_id: rows[0].id,
      delete_ids: rows.slice(1).map((r) => r.id),
    }))
    .sort((a, b) => b.cnt - a.cnt)
    .slice(0, 30);

  return NextResponse.json({ duplicates, total_rows: data?.length ?? 0 });
}

export async function DELETE(req: NextRequest) {
  const body = await req.json();
  const ids: number[] = body.ids;

  if (!Array.isArray(ids) || ids.length === 0) {
    return NextResponse.json({ error: "ids 배열이 필요합니다." }, { status: 400 });
  }

  const supabase = createAdminClient();
  const { error, count } = await supabase
    .from("gov_contracts")
    .delete({ count: "exact" })
    .in("id", ids);

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ deleted: count });
}
