import { createClient } from "@/lib/supabase/server";

export default async function HomePage() {
  const supabase = await createClient();

  const [{ count: legalCount }, { count: govCount }] = await Promise.all([
    supabase.from("legal_forms").select("*", { count: "exact", head: true }),
    supabase.from("gov_contracts").select("*", { count: "exact", head: true }),
  ]);

  const { data: recentGov } = await supabase
    .from("gov_contracts")
    .select("ministry, title, collected_at")
    .order("collected_at", { ascending: false })
    .limit(5);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold mb-1">법률서식 데이터 플랫폼</h1>
        <p className="text-gray-500 text-sm">자동 수집된 법률서식 및 정부부처 표준계약서 데이터를 조회하고 다운로드하세요.</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <a href="/legal" className="block p-6 bg-white rounded-lg border border-gray-200 hover:border-blue-400 transition-colors">
          <div className="text-3xl font-bold text-blue-600">{legalCount?.toLocaleString() ?? "—"}</div>
          <div className="text-sm text-gray-600 mt-1">법률서식 (KLAC · ECFS · EKT)</div>
        </a>
        <a href="/contracts" className="block p-6 bg-white rounded-lg border border-gray-200 hover:border-blue-400 transition-colors">
          <div className="text-3xl font-bold text-blue-600">{govCount?.toLocaleString() ?? "—"}</div>
          <div className="text-sm text-gray-600 mt-1">정부부처 계약서 (19개 부처)</div>
        </a>
      </div>

      <div>
        <h2 className="text-lg font-semibold mb-3">최근 수집 현황</h2>
        <div className="bg-white rounded-lg border border-gray-200 divide-y divide-gray-100">
          {recentGov?.map((item, i) => (
            <div key={i} className="px-4 py-3 flex justify-between text-sm">
              <span>
                <span className="font-medium text-gray-700">{item.ministry}</span>
                <span className="text-gray-500 ml-2">{item.title}</span>
              </span>
              <span className="text-gray-400 whitespace-nowrap ml-4">
                {new Date(item.collected_at).toLocaleDateString("ko-KR")}
              </span>
            </div>
          ))}
          {!recentGov?.length && (
            <div className="px-4 py-6 text-center text-gray-400 text-sm">수집된 데이터가 없습니다.</div>
          )}
        </div>
      </div>
    </div>
  );
}
