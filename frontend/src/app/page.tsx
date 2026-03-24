"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { askAgent } from "@/services/api";
import { Header } from "@/components/Header";
import { ChatInput } from "@/components/ChatInput";
import { Reasoning } from "@/components/Reasoning";
import { ChartPanel } from "@/components/ChartPanel";
import { ViolationsTable } from "@/components/ViolationsTable";

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
    <main className="relative min-h-screen bg-[#f7f8fb] p-6 md:p-16 text-slate-900 selection:bg-slate-200">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-[radial-gradient(1200px_circle_at_20%_-10%,#e8edf6,transparent_60%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(255,255,255,0.6),rgba(255,255,255,0.2))]" />
      </div>
      <div className="relative max-w-4xl mx-auto">
        <Header />

        <div
          className={
            result
              ? "mb-8"
              : "min-h-[45vh] flex flex-col justify-center mb-10"
          }
        >
          <div className="mb-8 text-center">
            <p className="text-2xl md:text-3xl font-semibold tracking-tight text-slate-900">
              What would you like to analyze today?
            </p>
          </div>
          <ChatInput
            question={question}
            setQuestion={setQuestion}
            handleAsk={handleAsk}
            loading={loading}
          />
        </div>

        <AnimatePresence>
          {result && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-white/90 backdrop-blur p-10 rounded-[2rem] border border-slate-200 shadow-[0_30px_60px_-24px_rgba(15,23,42,0.25)]"
            >
              {result?.status === "error" && (
                <div className="mb-8 p-4 rounded-2xl border border-amber-200 bg-amber-50 text-amber-800 text-sm font-semibold">
                  {result?.error?.code === "OUT_OF_SCOPE" ? (
                    <span>
                      This assistant only answers questions about your finance
                      data and policies. Try asking about spend, revenue,
                      budgets, regions, or compliance.
                    </span>
                  ) : (
                    <span>
                      {result?.error?.code ? `[${result?.error?.code}] ` : ""}
                      {result?.explanation}
                    </span>
                  )}
                </div>
              )}
              {/* Report Header */}
              <div className="flex flex-col md:flex-row md:items-center justify-between mb-10 gap-4 text-black">
                <div className="max-w-xl">
                  <h2 className="text-3xl font-semibold tracking-tight mb-3">
                    {result?.title}
                  </h2>
                  <p className="text-slate-500 text-base leading-relaxed">
                    {result?.explanation}
                  </p>
                </div>

                {/* DETERMINISTIC BADGE LOGIC */}
                {result?.status === "error" ? (
                  <div className="self-start px-4 py-1.5 bg-amber-50 text-amber-700 rounded-full text-[10px] font-semibold tracking-[0.2em] border border-amber-100 uppercase">
                    Out of Scope
                  </div>
                ) : result?.is_violation ? (
                  <div className="self-start px-4 py-1.5 bg-red-50 text-red-600 rounded-full text-[10px] font-semibold tracking-[0.2em] border border-red-100 uppercase">
                    Violation
                  </div>
                ) : (
                  <div className="self-start px-4 py-1.5 bg-emerald-50 text-emerald-700 rounded-full text-[10px] font-semibold tracking-[0.2em] border border-emerald-100 uppercase">
                    Clean Audit
                  </div>
                )}
              </div>

              {/* Action Recommendation for Violations */}
              {result?.is_violation && result?.status !== "error" && (
                <div className="mb-10 p-6 bg-slate-50 rounded-2xl border border-slate-200">
                  <p className="text-slate-800 font-semibold text-xs uppercase tracking-[0.2em] mb-2">
                    Recommended Action:
                  </p>
                  <p className="text-slate-700">{result?.action}</p>
                </div>
              )}

              <Reasoning
                result={result}
                show={showReasoning}
                setShow={setShowReasoning}
              />

              <ViolationsTable result={result} />
              {!result?.is_violation && <ChartPanel result={result} />}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </main>
  );
}
