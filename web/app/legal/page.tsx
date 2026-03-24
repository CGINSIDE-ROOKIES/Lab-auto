import { createClient } from "@/lib/supabase/server";
import { LegalFormsClient } from "./LegalFormsClient";

export default async function LegalPage() {
  const supabase = await createClient();
  const { data } = await supabase
    .from("legal_forms")
    .select("*")
    .order("collected_at", { ascending: false })
    .limit(500);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">법률서식</h1>
        <p className="text-sm text-gray-500">KLAC · 전자소송포털 · 전자공탁 수집 데이터</p>
      </div>
      <LegalFormsClient initialData={data ?? []} />
    </div>
  );
}
