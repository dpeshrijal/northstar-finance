"use client";
import { useState } from "react";
import { askAgent } from "./services/api";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
  Legend,
} from "recharts";
import {
  Database,
  ChevronDown,
  ChevronUp,
  Sparkles,
  FileText,
  Code2,
} from "lucide-react";

export default function Home() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [showReasoning, setShowReasoning] = useState(false);

  const handleAsk = async () => {
    setLoading(true);
    setResult(null);
    try {
      const data = await askAgent(question);
      setResult(data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const getNumberKey = (dataObj: any) => {
    if (!dataObj) return "";
    return (
      Object.keys(dataObj).find(
        (key) =>
          (typeof dataObj[key] === "number" ||
            !isNaN(parseFloat(dataObj[key]))) &&
          key !== "id",
      ) || ""
    );
  };

  const getLabelKey = (dataObj: any) => {
    if (!dataObj) return "";
    const numKey = getNumberKey(dataObj);
    return (
      Object.keys(dataObj).find((key) => key !== numKey && key !== "id") ||
      numKey
    );
  };

  return (
    <main className="min-h-screen bg-[#f8fafc] p-4 md:p-12 text-slate-900 font-sans">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <div className="bg-blue-600 p-2 rounded-xl shadow-lg shadow-blue-200">
            <Database className="text-white w-6 h-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-800">
            Northstar <span className="text-blue-600">Finance AI</span>
          </h1>
        </div>

        {/* Input Area */}
        <div className="bg-white p-2 rounded-2xl shadow-sm border border-slate-200 flex items-center">
          <input
            className="flex-1 p-4 text-lg bg-transparent outline-none"
            placeholder="Search transactions or ask about policy violations..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAsk()}
          />
          <button
            onClick={handleAsk}
            disabled={loading}
            className="bg-blue-600 text-white px-8 py-3 rounded-xl font-semibold hover:bg-blue-700 disabled:bg-slate-300 transition-all flex items-center gap-2"
          >
            {loading ? (
              "Analyzing..."
            ) : (
              <>
                <Sparkles size={18} /> Analyze
              </>
            )}
          </button>
        </div>

        {/* Results Section */}
        {result && (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-700 space-y-6">
            <div className="bg-white p-8 rounded-3xl shadow-xl shadow-slate-200/50 border border-slate-100">
              <div className="flex items-start justify-between mb-8">
                <div className="space-y-2">
                  <h2 className="text-2xl font-bold text-slate-800 leading-tight">
                    {result.title}
                  </h2>
                  <p className="text-slate-500 leading-relaxed max-w-2xl text-lg">
                    {result.explanation}
                  </p>
                </div>
                {result.explanation.toLowerCase().includes("violation") ||
                result.explanation.toLowerCase().includes("flag") ? (
                  <div className="bg-red-50 text-red-700 px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider border border-red-100">
                    🚩 Policy Flag
                  </div>
                ) : (
                  <div className="bg-blue-50 text-blue-700 px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider border border-blue-100">
                    AI Insight
                  </div>
                )}
              </div>

              {/* Chart Rendering */}
              {result.data &&
              result.data.length > 0 &&
              result.data.length < 15 ? (
                <div className="h-[400px] w-full mt-10 rounded-2xl bg-slate-50/50 p-4 border border-slate-50">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={result.data}
                      margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                        stroke="#e2e8f0"
                      />
                      <XAxis
                        dataKey={getLabelKey(result.data[0])}
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: "#64748b", fontSize: 12 }}
                        dy={10}
                      />
                      <YAxis
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: "#64748b", fontSize: 12 }}
                      />
                      <Tooltip
                        cursor={{ fill: "#f1f5f9" }}
                        contentStyle={{
                          borderRadius: "16px",
                          border: "none",
                          boxShadow: "0 20px 25px -5px rgb(0 0 0 / 0.1)",
                        }}
                      />
                      <Bar
                        dataKey={getNumberKey(result.data[0])}
                        fill="#3b82f6"
                        radius={[8, 8, 0, 0]}
                        barSize={60}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : result.data && result.data.length >= 15 ? (
                /* Table View for large datasets (Like Audit lists) */
                <div className="mt-8 overflow-hidden rounded-xl border border-slate-200">
                  <table className="w-full text-left border-collapse">
                    <thead className="bg-slate-50 text-slate-500 text-xs uppercase font-bold">
                      <tr>
                        {Object.keys(result.data[0])
                          .slice(0, 5)
                          .map((key) => (
                            <th
                              key={key}
                              className="px-6 py-3 border-b border-slate-200"
                            >
                              {key.replace("_", " ")}
                            </th>
                          ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-sm">
                      {result.data.slice(0, 10).map((row: any, i: number) => (
                        <tr
                          key={i}
                          className="hover:bg-slate-50/50 transition-colors"
                        >
                          {Object.values(row)
                            .slice(0, 5)
                            .map((val: any, j: number) => (
                              <td key={j} className="px-6 py-4 text-slate-600">
                                {val?.toString()}
                              </td>
                            ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="p-3 bg-slate-50 text-center text-xs text-slate-400">
                    Showing first 10 rows
                  </div>
                </div>
              ) : null}

              {/* Reasoning Toggle */}
              <div className="mt-10 pt-6 border-t border-slate-100">
                <button
                  onClick={() => setShowReasoning(!showReasoning)}
                  className="flex items-center gap-2 text-slate-400 hover:text-blue-600 transition-all text-xs font-bold tracking-widest"
                >
                  {showReasoning ? (
                    <ChevronUp size={14} />
                  ) : (
                    <ChevronDown size={14} />
                  )}
                  SHOW ENGINE REASONING
                </button>

                {showReasoning && (
                  <div className="mt-6 space-y-4 animate-in fade-in zoom-in-95 duration-300">
                    {/* SQL Section */}
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-slate-500 text-[10px] font-bold uppercase tracking-tighter">
                        <Code2 size={12} /> SQL Query (Structured ERP Data)
                      </div>
                      <div className="p-5 bg-slate-900 rounded-2xl shadow-inner border border-slate-800">
                        <code className="text-blue-400 text-sm font-mono block overflow-x-auto whitespace-pre">
                          {result.sql}
                        </code>
                      </div>
                    </div>

                    {/* Policy Section */}
                    {result.policy && (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2 text-slate-500 text-[10px] font-bold uppercase tracking-tighter">
                          <FileText size={12} /> Policy Context (Unstructured
                          Knowledge)
                        </div>
                        <div className="p-5 bg-blue-50/50 rounded-2xl border border-blue-100">
                          <p className="text-blue-800 text-sm italic leading-relaxed">
                            "{result.policy}"
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
