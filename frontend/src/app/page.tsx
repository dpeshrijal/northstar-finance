"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { askAgent } from "@/services/api";
import { Header } from "@/components/Header";
import { ChatInput } from "@/components/ChatInput";
import { Reasoning } from "@/components/Reasoning";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

export default function Home() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [showReasoning, setShowReasoning] = useState(false);

  const handleAsk = async () => {
    setLoading(true);
    setResult(null);
    setShowReasoning(false);
    try {
      const data = await askAgent(question);
      setResult(data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  return (
    <main className="min-h-screen bg-[#fcfcfd] p-6 md:p-16 text-slate-900 selection:bg-blue-100">
      <div className="max-w-4xl mx-auto">
        <Header />

        <ChatInput
          question={question}
          setQuestion={setQuestion}
          handleAsk={handleAsk}
          loading={loading}
        />

        <AnimatePresence>
          {result && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-white p-10 rounded-[2.5rem] shadow-[0_32px_64px_-12px_rgba(0,0,0,0.08)] border border-slate-100"
            >
              {/* Report Header */}
              <div className="flex flex-col md:flex-row md:items-center justify-between mb-10 gap-4 text-black">
                <div className="max-w-xl">
                  <h2 className="text-3xl font-extrabold tracking-tight mb-3 italic">
                    {result?.title}
                  </h2>
                  <p className="text-slate-500 text-lg leading-relaxed font-medium">
                    {result?.explanation}
                  </p>
                </div>

                {/* DETERMINISTIC BADGE LOGIC */}
                {result?.is_violation ? (
                  <div className="self-start px-5 py-2 bg-red-50 text-red-600 rounded-full text-xs font-black tracking-widest border border-red-100 animate-pulse uppercase">
                    🚩 Violation
                  </div>
                ) : (
                  <div className="self-start px-5 py-2 bg-blue-50 text-blue-600 rounded-full text-xs font-black tracking-widest border border-blue-100 uppercase">
                    ✅ Clean Audit
                  </div>
                )}
              </div>

              {/* Action Recommendation for Violations */}
              {result?.is_violation && (
                <div className="mb-10 p-6 bg-red-50/50 rounded-2xl border border-red-100">
                  <p className="text-red-800 font-bold text-sm uppercase tracking-tight mb-1">
                    Recommended Action:
                  </p>
                  <p className="text-red-700 font-medium">{result?.action}</p>
                </div>
              )}

              <Reasoning
                result={result}
                show={showReasoning}
                setShow={setShowReasoning}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </main>
  );
}
