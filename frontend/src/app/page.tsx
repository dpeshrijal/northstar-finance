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
import { Database, ChevronDown, ChevronUp, Sparkles } from "lucide-react";

export default function Home() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [showSql, setShowSql] = useState(false);

  const handleAsk = async () => {
    setLoading(true);
    setResult(null); // Clear previous results
    try {
      const data = await askAgent(question);
      setResult(data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  // Helper to find which key in the data object is the "number" we want to graph
  const getNumberKey = (dataObj: any) => {
    if (!dataObj) return "";
    return (
      Object.keys(dataObj).find(
        (key) =>
          typeof dataObj[key] === "number" || !isNaN(parseFloat(dataObj[key])),
      ) || ""
    );
  };

  // Helper to find the "label" key (e.g., region name or 'Actual/Budget')
  const getLabelKey = (dataObj: any) => {
    if (!dataObj) return "";
    return (
      Object.keys(dataObj).find((key) => key !== getNumberKey(dataObj)) || ""
    );
  };

  const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

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
            placeholder="e.g., Show me total spend by region"
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
                <div className="hidden sm:block bg-blue-50 text-blue-700 px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider border border-blue-100">
                  AI INSIGHT
                </div>
              </div>

              {/* Chart Rendering - FIXED HEIGHT CONTAINER */}
              {result.data && result.data.length > 0 ? (
                <div className="h-[400px] w-full mt-10 rounded-2xl bg-slate-50/50 p-4 border border-slate-50">
                  <ResponsiveContainer width="100%" height="100%">
                    {result.chart_type === "pie" ? (
                      <PieChart>
                        <Pie
                          data={result.data}
                          dataKey={getNumberKey(result.data[0])}
                          nameKey={getLabelKey(result.data[0])}
                          cx="50%"
                          cy="50%"
                          outerRadius={130}
                          fill="#8884d8"
                          label
                        >
                          {result.data.map((entry: any, index: number) => (
                            <Cell
                              key={`cell-${index}`}
                              fill={COLORS[index % COLORS.length]}
                            />
                          ))}
                        </Pie>
                        <Tooltip />
                        <Legend />
                      </PieChart>
                    ) : (
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
                        >
                          {result.data.map((entry: any, index: number) => (
                            <Cell
                              key={`cell-${index}`}
                              fill={entry.is_budget ? "#94a3b8" : "#3b82f6"}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    )}
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="h-40 flex items-center justify-center border-2 border-dashed border-slate-200 rounded-2xl text-slate-400">
                  No data found for this specific query.
                </div>
              )}

              {/* Reasoning Toggle */}
              <div className="mt-10 pt-6 border-t border-slate-100">
                <button
                  onClick={() => setShowSql(!showSql)}
                  className="flex items-center gap-2 text-slate-400 hover:text-blue-600 transition-all text-xs font-bold tracking-widest"
                >
                  {showSql ? (
                    <ChevronUp size={14} />
                  ) : (
                    <ChevronDown size={14} />
                  )}
                  SHOW ENGINE REASONING (POSTGRESQL)
                </button>

                {showSql && (
                  <div className="mt-4 p-6 bg-slate-900 rounded-2xl shadow-inner">
                    <code className="text-blue-400 text-sm font-mono block overflow-x-auto whitespace-pre">
                      {result.sql}
                    </code>
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
