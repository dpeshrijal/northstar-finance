import { Sparkles, Loader2 } from "lucide-react";

export const ChatInput = ({
  question,
  setQuestion,
  handleAsk,
  loading,
}: any) => (
  <div className="bg-white/80 backdrop-blur-md sticky top-6 z-10 p-2 rounded-2xl shadow-2xl shadow-blue-100 border border-slate-200 flex items-center mb-10 transition-all focus-within:ring-4 focus-within:ring-blue-500/10">
    <input
      className="flex-1 p-4 text-lg bg-transparent outline-none text-slate-700 placeholder:text-slate-400"
      placeholder="Ask Northstar about spend, audits, or policies..."
      value={question}
      onChange={(e) => setQuestion(e.target.value)}
      onKeyDown={(e) => e.key === "Enter" && handleAsk()}
    />
    <button
      onClick={handleAsk}
      disabled={loading || !question}
      className="bg-blue-600 text-white px-8 py-3 rounded-xl font-bold hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400 transition-all flex items-center gap-2 shadow-lg shadow-blue-200 active:scale-95"
    >
      {loading ? (
        <Loader2 className="animate-spin" size={18} />
      ) : (
        <Sparkles size={18} />
      )}
      {loading ? "Analyzing..." : "Analyze"}
    </button>
  </div>
);
