import { createClient } from "@/lib/supabase/server";
import { ContractsClient } from "./ContractsClient";

export default async function ContractsPage() {
  const supabase = await createClient();
  const { data } = await supabase
    .from("gov_contracts")
    .select("*")
    .order("collected_at", { ascending: false })
    .limit(500);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">정부부처 계약서</h1>
        <p className="text-sm text-gray-500">19개 정부부처 표준계약서·약정서 수집 데이터</p>
      </div>
      <ContractsClient initialData={data ?? []} />
    </div>
  );
}
