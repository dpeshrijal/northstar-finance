import { Database } from "lucide-react";

export const Header = () => (
  <div className="flex items-center justify-between mb-12">
    <div className="flex items-center gap-3">
      <div className="bg-gradient-to-br from-blue-600 to-indigo-700 p-2.5 rounded-xl shadow-lg shadow-blue-200">
        <Database className="text-white w-5 h-5" />
      </div>
      <h1 className="text-xl font-black tracking-tight text-slate-800 uppercase">
        Northstar <span className="text-blue-600">Finance</span>
      </h1>
    </div>
    <div className="flex gap-4 text-xs font-bold text-slate-400 uppercase tracking-widest">
      <span>Agentic AI v2.0</span>
    </div>
  </div>
);
