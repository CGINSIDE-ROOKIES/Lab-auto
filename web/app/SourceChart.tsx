"use client";

type SourceCount = { source_name: string; count: number };

function BarChart({ data, title }: { data: SourceCount[]; title: string }) {
  const max = Math.max(...data.map((d) => d.count), 1);

  return (
    <div className="bg-white p-4 rounded-lg border border-gray-200">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">{title}</h3>
      <div className="space-y-2">
        {data.map(({ source_name, count }) => (
          <div key={source_name} className="flex items-center gap-2 text-sm">
            <span className="text-gray-600 shrink-0 w-36 truncate text-right" title={source_name}>
              {source_name}
            </span>
            <div className="flex-1 flex items-center gap-1.5">
              <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full"
                  style={{ width: `${(count / max) * 100}%` }}
                />
              </div>
              <span className="text-gray-500 tabular-nums w-10 text-right">{count.toLocaleString()}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function SourceCharts({ legal, gov }: { legal: SourceCount[]; gov: SourceCount[] }) {
  return (
    <div className="flex gap-4 items-start">
      <div className="w-72 shrink-0">
        <BarChart data={legal} title="법률서식" />
      </div>
      <div className="flex-1 min-w-0">
        <BarChart data={gov} title="정부부처" />
      </div>
    </div>
  );
}
