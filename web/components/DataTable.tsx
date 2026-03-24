"use client";

export type Column<T> = {
  key: keyof T;
  label: string;
  render?: (value: T[keyof T], row: T) => React.ReactNode;
};

type Props<T> = {
  columns: Column<T>[];
  data: T[];
  emptyMessage?: string;
};

export function DataTable<T>({ columns, data, emptyMessage = "데이터가 없습니다." }: Props<T>) {
  if (data.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400 text-sm">{emptyMessage}</div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-50 border-y border-gray-200">
            {columns.map((col) => (
              <th
                key={String(col.key)}
                className="text-left px-3 py-2 font-medium text-gray-600 whitespace-nowrap"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {data.map((row, i) => (
            <tr key={i} className="hover:bg-gray-50">
              {columns.map((col) => (
                <td key={String(col.key)} className="px-3 py-2">
                  {col.render
                    ? col.render(row[col.key], row)
                    : String(row[col.key] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
