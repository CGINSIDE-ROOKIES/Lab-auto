import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";

const PAGE_SIZE = 30;

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const keyword = searchParams.get("keyword") ?? "";
  const source = searchParams.get("source") ?? "";
  const format = searchParams.get("format") ?? "";
  const page = Math.max(1, parseInt(searchParams.get("page") ?? "1"));
  const from = (page - 1) * PAGE_SIZE;

  const supabase = createAdminClient();
  let query = supabase
    .from("gov_contracts")
    .select("id, source, title, file_name, file_format, collected_at", { count: "exact" });

  if (keyword) query = query.ilike("file_name", `%${keyword}%`);
  if (source) query = query.eq("source", source);
  if (format) query = query.eq("file_format", format);

  const { data, count, error } = await query
    .order("id", { ascending: false })
    .range(from, from + PAGE_SIZE - 1);

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ data, count });
}

export async function DELETE(req: NextRequest) {
  const { id, reason } = await req.json();
  if (!id) return NextResponse.json({ error: "id 필요" }, { status: 400 });

  const supabase = createAdminClient();

  // 블랙리스트 기록용 행 조회
  const { data: row, error: fetchError } = await supabase
    .from("gov_contracts")
    .select("download_url, source, file_name, file_format")
    .eq("id", id)
    .single();
  if (fetchError) return NextResponse.json({ error: fetchError.message }, { status: 500 });

  // deleted_forms에 기록 (download_url이 없는 행은 스킵)
  if (row.download_url) {
    const { error: blacklistError } = await supabase.from("deleted_forms").upsert({
      download_url: row.download_url,
      source_name: row.source,
      form_title: row.file_name,
      doc_format: row.file_format,
      reason: reason ?? null,
    });
    if (blacklistError) return NextResponse.json({ error: blacklistError.message }, { status: 500 });
  }

  const { error } = await supabase.from("gov_contracts").delete().eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ deleted: 1 });
}
