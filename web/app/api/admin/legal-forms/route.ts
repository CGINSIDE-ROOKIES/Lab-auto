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
    .from("legal_forms")
    .select("id, source, title, file_format, collected_at", { count: "exact" });

  if (keyword) query = query.ilike("title", `%${keyword}%`);
  if (source) query = query.eq("source", source);
  if (format) query = query.eq("file_format", format);

  const { data, count, error } = await query
    .order("id", { ascending: false })
    .range(from, from + PAGE_SIZE - 1);

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ data, count });
}

export async function DELETE(req: NextRequest) {
  const { id } = await req.json();
  if (!id) return NextResponse.json({ error: "id 필요" }, { status: 400 });

  const supabase = createAdminClient();
  const { error } = await supabase.from("legal_forms").delete().eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ deleted: 1 });
}
