import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";

const COLORS = ["#0f172a", "#1f2937", "#334155", "#475569", "#64748b"];

const VALUE_PRIORITY = [
  "total",
  "total_spend",
  "total_revenue",
  "amount",
  "avg",
  "average",
  "sum",
  "count",
];

const LABEL_PRIORITY = [
  "label",
  "month",
  "date",
  "region",
  "name",
  "cost_center",
  "cost_center_name",
  "id",
];

const pickValueKey = (row: any) => {
  if (!row) return null;
  const numericKeys = Object.keys(row).filter((k) => {
    const v = row[k];
    return typeof v === "number" && Number.isFinite(v);
  });
  for (const key of VALUE_PRIORITY) {
    if (numericKeys.includes(key)) return key;
  }
  return numericKeys[0] || null;
};

const pickNumericKeys = (row: any) => {
  if (!row) return [];
  return Object.keys(row).filter((k) => {
    const v = row[k];
    return typeof v === "number" && Number.isFinite(v);
  });
};

const pickLabelKey = (row: any) => {
  if (!row) return null;
  for (const key of LABEL_PRIORITY) {
    if (key in row) return key;
  }
  return Object.keys(row)[0] || null;
};

const truncateLabel = (value: any, max = 14) => {
  const str = String(value ?? "");
  if (str.length <= max) return str;
  return `${str.slice(0, max - 1)}…`;
};

const formatNumber = (value: any, currency?: string) => {
  if (typeof value !== "number") return value;
  try {
    if (currency) {
      return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency,
        maximumFractionDigits: 2,
      }).format(value);
    }
    return new Intl.NumberFormat("en-US", {
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return value;
  }
};

export const ChartPanel = ({ result }: any) => {
  if (!result || result?.chart_type === "none") return null;
  const rawData = Array.isArray(result?.data) ? result.data : [];
  if (rawData.length === 0) return null;
  if (rawData.length < 2) return null;

  const valueKey = pickValueKey(rawData[0]);
  if (!valueKey) return null;
  const numericKeys = pickNumericKeys(rawData[0]);

  const labelKey = pickLabelKey(rawData[0]);
  if (!labelKey) return null;
  const currency =
    typeof rawData[0].currency === "string" ? rawData[0].currency : undefined;

  // Heuristic: chart only aggregated data (avoid long audit lists)
  const hasDescription = "description" in rawData[0];
  const hasGroupingKey = ["region", "month", "name", "cost_center", "cost_center_name"].some(
    (k) => k in rawData[0],
  );
  if (!hasGroupingKey && hasDescription) return null;

  // Limit rows for readability (top-N by value)
  let data = rawData;
  if (rawData.length > 12 && result.chart_type !== "line") {
    data = [...rawData]
      .filter((d) => typeof d[valueKey] === "number")
      .sort((a, b) => (b[valueKey] as number) - (a[valueKey] as number))
      .slice(0, 12);
  } else if (rawData.length > 30 && result.chart_type === "line") {
    data = rawData.slice(-30);
  }

  return (
    <div className="mt-10 p-6 rounded-2xl border border-slate-200 bg-white">
      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500 mb-4">
        Visual Summary
      </div>

      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          {result.chart_type === "bar" && (
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis
                dataKey={labelKey}
                tick={{ fontSize: 11 }}
                angle={-20}
                textAnchor="end"
                height={50}
                tickFormatter={(v) => truncateLabel(v)}
              />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(v: any) => formatNumber(v as number, currency)}
                labelFormatter={(v: any) => truncateLabel(v, 24)}
              />
              {numericKeys.length >= 2 ? (
                <>
                  <Bar dataKey={numericKeys[0]} fill="#0f172a" radius={[6, 6, 0, 0]} />
                  <Bar dataKey={numericKeys[1]} fill="#64748b" radius={[6, 6, 0, 0]} />
                </>
              ) : (
                <Bar dataKey={valueKey} fill="#0f172a" radius={[6, 6, 0, 0]} />
              )}
            </BarChart>
          )}

          {result.chart_type === "line" && (
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey={labelKey} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(v: any) => formatNumber(v as number, currency)}
              />
              <Line
                type="monotone"
                dataKey={valueKey}
                stroke="#0f172a"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          )}

          {result.chart_type === "pie" && (
            <PieChart>
              <Tooltip
                formatter={(v: any) => formatNumber(v as number, currency)}
                labelFormatter={(v: any) => truncateLabel(v, 24)}
              />
              <Pie
                data={data}
                dataKey={valueKey}
                nameKey={labelKey}
                outerRadius={90}
              >
                {data.map((_: any, idx: number) => (
                  <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                ))}
              </Pie>
            </PieChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
};
