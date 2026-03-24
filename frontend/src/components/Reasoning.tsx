import { ChevronDown, ChevronUp, Code2, FileText } from "lucide-react";

export const Reasoning = ({ result, show, setShow }: any) => (
  <div className="mt-10 pt-6 border-t border-slate-200">
    <button
      onClick={() => setShow(!show)}
      className="flex items-center gap-2 text-slate-400 hover:text-slate-700 transition-all text-[10px] font-semibold uppercase tracking-[0.3em]"
    >
      {show ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      Engine Reasoning & Audit Trail
    </button>

    {show && (
      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4 animate-in fade-in slide-in-from-top-2 duration-500">
        <div className="p-5 bg-slate-950 rounded-2xl border border-slate-900">
          <div className="flex items-center gap-2 text-slate-300 text-[9px] font-semibold uppercase mb-3 tracking-[0.2em]">
            <Code2 size={12} /> SQL Discovery
          </div>
          <code className="text-slate-300 text-xs font-mono leading-relaxed block overflow-x-auto whitespace-pre">
            {result?.sql}
          </code>
        </div>
        <div className="p-5 bg-white rounded-2xl border border-slate-200">
          <div className="flex items-center gap-2 text-slate-700 text-[9px] font-semibold uppercase mb-3 tracking-[0.2em]">
            <FileText size={12} /> Policy Context
          </div>
          <p className="text-slate-600 text-xs leading-relaxed">
            "{result?.policy || "No policy constraints applied to this query."}"
          </p>
        </div>
      </div>
    )}
  </div>
);
