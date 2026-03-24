import { Database } from "lucide-react";

export const Header = () => (
  <div className="flex items-center justify-between mb-10">
    <div className="flex items-center gap-3">
      <div className="bg-slate-900 text-white p-2.5 rounded-xl">
        <Database className="w-4 h-4" />
      </div>
      <div className="leading-tight">
        <p className="text-[11px] uppercase tracking-[0.3em] text-slate-500">
          Northstar
        </p>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Finance Intelligence
        </h1>
      </div>
    </div>
    <div className="hidden md:block text-[11px] uppercase tracking-[0.3em] text-slate-400">
      BETA
    </div>
  </div>
);
