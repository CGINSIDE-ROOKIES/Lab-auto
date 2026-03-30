import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";

export async function DELETE(req: NextRequest) {
  const { uid, reason } = await req.json();
  if (!uid) return NextResponse.json({ error: "uid 필요" }, { status: 400 });

  // uid 파싱: "legal_3787" → legal_forms / "gov_12" → gov_contracts
  const match = (uid as string).match(/^(legal|gov)_(\d+)$/);
  if (!match) return NextResponse.json({ error: "잘못된 uid 형식" }, { status: 400 });

  const table = match[1] === "legal" ? "legal_forms" : "gov_contracts";
  const id = parseInt(match[2]);

  const supabase = createAdminClient();

  let formTitle: string | null = null;
  let downloadUrl: string | null = null;
  let source: string | null = null;
  let docFormat: string | null = null;

  if (table === "legal_forms") {
    const { data: row, error: fetchError } = await supabase
      .from("legal_forms")
      .select("download_url, source, title, file_format")
      .eq("id", id)
      .single();
    if (fetchError) return NextResponse.json({ error: fetchError.message }, { status: 500 });
    downloadUrl = row.download_url;
    source = row.source;
    formTitle = row.title;
    docFormat = row.file_format;
  } else {
    const { data: row, error: fetchError } = await supabase
      .from("gov_contracts")
      .select("download_url, source, file_name, file_format")
      .eq("id", id)
      .single();
    if (fetchError) return NextResponse.json({ error: fetchError.message }, { status: 500 });
    downloadUrl = row.download_url;
    source = row.source;
    formTitle = row.file_name;
    docFormat = row.file_format;
  }

  if (downloadUrl) {
    const { error: blacklistError } = await supabase.from("deleted_forms").upsert({
      download_url: downloadUrl,
      source_name: source,
      form_title: formTitle,
      doc_format: docFormat,
      reason: reason ?? null,
    });
    if (blacklistError) return NextResponse.json({ error: blacklistError.message }, { status: 500 });
  }

  const { error } = await supabase.from(table).delete().eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ deleted: 1 });
}
