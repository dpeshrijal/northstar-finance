const COLUMN_PRIORITY = [
  "id",
  "date",
  "amount",
  "currency",
  "description",
  "gl_account_id",
  "cost_center_id",
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
  if (cols.length === 0) return keys.slice(0, 6);
  return cols;
};

export const ViolationsTable = ({ result }: any) => {
  if (!result?.is_violation) return null;
  const all = Array.isArray(result?.data) ? result.data : [];
  const data = all.slice(0, 10);
  if (data.length === 0) return null;

  const columns = pickColumns(data[0]);
  if (columns.length === 0) return null;

  return (
    <div className="mt-10 p-6 rounded-2xl border border-slate-200 bg-white">
      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500 mb-4">
        Violations (Top 10)
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
                    {String(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {all.length > 10 && (
        <div className="mt-3 text-xs text-slate-400">
          Showing first 10 of {all.length} rows.
        </div>
      )}
    </div>
  );
};
