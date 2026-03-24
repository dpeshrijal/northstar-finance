import { Sparkles, Loader2, ArrowUpRight } from "lucide-react";

export const ChatInput = ({
  question,
  setQuestion,
  handleAsk,
  loading,
}: any) => (
  <div className="bg-white/70 backdrop-blur-md sticky top-6 z-10 p-2.5 rounded-2xl border border-slate-200 flex items-center mb-8 transition-all focus-within:ring-4 focus-within:ring-slate-300/20">
    <input
      className="flex-1 px-4 py-3 text-[15px] bg-transparent outline-none text-slate-800 placeholder:text-slate-400"
      placeholder="Ask about spend, audits, anomalies, or policy compliance..."
      value={question}
      onChange={(e) => setQuestion(e.target.value)}
      onKeyDown={(e) => e.key === "Enter" && handleAsk()}
    />
    <button
      onClick={handleAsk}
      disabled={loading || !question}
      className="bg-slate-900 text-white px-5 py-3 rounded-xl text-sm font-semibold hover:bg-slate-800 disabled:bg-slate-200 disabled:text-slate-400 transition-all flex items-center gap-2 active:scale-[0.98]"
    >
      {loading ? (
        <Loader2 className="animate-spin" size={18} />
      ) : (
        <Sparkles size={18} />
      )}
      {loading ? "Analyzing..." : "Analyze"}
      {!loading && <ArrowUpRight size={16} className="opacity-70" />}
    </button>
  </div>
);
