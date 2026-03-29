const COLUMN_PRIORITY = [
  "id",
  "date",
  "amount",
  "currency",
  "description",
  "gl_account_id",
  "cost_center_id",
  "cost_center_name",
  "cost_center",
  "region",
  "name",
];

const pickColumns = (row: any) => {
  if (!row) return [];
  const keys = Object.keys(row).filter((k) => k !== "label");
  const cols: string[] = [];
  for (const key of COLUMN_PRIORITY) {
    if (keys.includes(key)) cols.push(key);
  }
  if (cols.length === 0) return keys.slice(0, 8);
  return cols;
};

const formatCell = (value: any) => {
  if (typeof value === "number") {
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(
      value,
    );
  }
  return String(value);
};

export const ResultsTable = ({ result }: any) => {
  if (!result || result?.status !== "ok") return null;
  if (result?.is_violation) return null;
  if (result?.chart_type !== "none") return null;

  const all = Array.isArray(result?.data) ? result.data : [];
  const data = all.slice(0, 20);
  if (data.length === 0) return null;

  const columns = pickColumns(data[0]);
  if (columns.length === 0) return null;

  return (
    <div className="mt-10 p-6 rounded-2xl border border-slate-200 bg-white">
      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500 mb-4">
        Results (First 20)
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-slate-500 border-b border-slate-200">
              {columns.map((col) => (
                <th key={col} className="text-left py-2 pr-4 font-semibold">
                  {col.replace(/_/g, " ")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row: any, idx: number) => (
              <tr key={idx} className="border-b border-slate-100">
                {columns.map((col) => (
                  <td
                    key={col}
                    className={`py-2 pr-4 text-slate-700 ${
                      col === "id" ? "font-mono" : ""
                    }`}
                  >
                    {formatCell(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {all.length > 20 && (
        <div className="mt-3 text-xs text-slate-400">
          Showing first 20 of {all.length} rows returned.
        </div>
      )}
    </div>
  );
};
