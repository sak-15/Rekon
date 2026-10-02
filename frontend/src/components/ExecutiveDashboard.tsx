import React, {useState, useEffect} from "react";
import {
  Calendar,
  ChevronDown,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Wallet,
  Receipt,
  Percent,
  ShieldCheck,
} from "lucide-react";
import {api, ExecutiveDashboardResponse} from "../api/client";

interface ExecutiveDashboardProps {
  onNavigate: (tab: string) => void;
  orgName?: string;
}

type PresetFilter =
  | "all"
  | "this_month"
  | "last_month"
  | "last_30"
  | "fy_25_26"
  | "month_picker"
  | "custom";

export const ExecutiveDashboard: React.FC<ExecutiveDashboardProps> = ({
  onNavigate,
  orgName = "Organization",
}) => {
  const [data, setData] = useState<ExecutiveDashboardResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Date Filter State
  const [filterType, setFilterType] = useState<PresetFilter>("all");
  const [customStart, setCustomStart] = useState<string>("");
  const [customEnd, setCustomEnd] = useState<string>("");
  const [selectedMonth, setSelectedMonth] = useState<string>("2026-05"); // YYYY-MM
  const [showDatePicker, setShowDatePicker] = useState<boolean>(false);
  const [activeDateLabel, setActiveDateLabel] = useState<string>("All Time");

  const computeDateRange = (
    type: PresetFilter,
    monthVal?: string,
    startVal?: string,
    endVal?: string
  ): {startDate?: string; endDate?: string; label: string} => {
    const now = new Date(2026, 4, 15); // Anchor to May 2026 for sample data

    if (type === "all") {
      return {label: "All Time"};
    }

    if (type === "this_month") {
      const year = now.getFullYear();
      const month = now.getMonth();
      const firstDay = new Date(year, month, 1).toISOString();
      const lastDay = new Date(year, month + 1, 0, 23, 59, 59).toISOString();
      return {
        startDate: firstDay,
        endDate: lastDay,
        label: "May 2026 (Current)",
      };
    }

    if (type === "last_month") {
      const year = now.getFullYear();
      const month = now.getMonth() - 1;
      const firstDay = new Date(year, month, 1).toISOString();
      const lastDay = new Date(year, month + 1, 0, 23, 59, 59).toISOString();
      return {startDate: firstDay, endDate: lastDay, label: "April 2026"};
    }

    if (type === "last_30") {
      const past30 = new Date(now);
      past30.setDate(past30.getDate() - 30);
      return {
        startDate: past30.toISOString(),
        endDate: now.toISOString(),
        label: "Last 30 Days",
      };
    }

    if (type === "fy_25_26") {
      const fyStart = new Date(2025, 3, 1).toISOString(); // 1 April 2025
      const fyEnd = new Date(2026, 2, 31, 23, 59, 59).toISOString(); // 31 March 2026
      return {startDate: fyStart, endDate: fyEnd, label: "FY 2025–26"};
    }

    if (type === "month_picker" && monthVal) {
      const [y, m] = monthVal.split("-").map(Number);
      const firstDay = new Date(y, m - 1, 1).toISOString();
      const lastDay = new Date(y, m, 0, 23, 59, 59).toISOString();
      const monthName = new Date(y, m - 1, 1).toLocaleString("default", {
        month: "long",
        year: "numeric",
      });
      return {startDate: firstDay, endDate: lastDay, label: monthName};
    }

    if (type === "custom" && startVal && endVal) {
      const s = new Date(startVal).toISOString();
      const e = new Date(`${endVal}T23:59:59`).toISOString();
      return {startDate: s, endDate: e, label: `${startVal} to ${endVal}`};
    }

    return {label: "All Time"};
  };

  const loadData = async (type: PresetFilter = filterType) => {
    try {
      setLoading(true);
      setError(null);
      const range = computeDateRange(
        type,
        selectedMonth,
        customStart,
        customEnd
      );
      setActiveDateLabel(range.label);

      const params: {start_date?: string; end_date?: string} = {};
      if (range.startDate) params.start_date = range.startDate;
      if (range.endDate) params.end_date = range.endDate;

      const res = await api.getExecutiveDashboard(params);
      setData(res);
    } catch (err: any) {
      console.error("Failed to load dashboard:", err);
      setError(err?.message || "Failed to load dashboard.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(filterType);
  }, [filterType]);

  const handleApplyCustomRange = () => {
    if (!customStart || !customEnd) return;
    setFilterType("custom");
    setShowDatePicker(false);
    loadData("custom");
  };

  const handleSelectMonth = (monthStr: string) => {
    setSelectedMonth(monthStr);
    setFilterType("month_picker");
    setShowDatePicker(false);
  };

  const formatINR = (val: number | string | undefined | null): string => {
    const num = Number(val || 0);
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(num);
  };

  if (loading && !data) {
    return (
      <div className="relative min-h-[460px] flex flex-col items-center justify-center p-8">
        <div className="absolute inset-0 bg-linear-to-tr from-indigo-500/10 via-sky-400/5 to-emerald-400/10 blur-3xl pointer-events-none -z-10" />
        <div className="w-12 h-12 rounded-2xl bg-white/80 dark:bg-slate-800/80 backdrop-blur-xl border border-white/60 dark:border-white/10 shadow-xl flex items-center justify-center text-indigo-600 animate-pulse">
          <RefreshCw className="w-6 h-6 animate-spin text-indigo-600" />
        </div>
        <p className="mt-4 text-xs font-semibold tracking-wider uppercase text-slate-500">
          Synthesizing Real-time Cash Flows...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="relative p-6 rounded-2xl backdrop-blur-xl bg-rose-50/80 dark:bg-rose-950/40 border border-rose-200/80 dark:border-rose-900/50 shadow-lg my-6 max-w-2xl mx-auto">
        <div className="flex items-center space-x-3">
          <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0" />
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-rose-950 dark:text-rose-200">
              Unable to load metrics
            </h3>
            <p className="text-xs text-rose-700 dark:text-rose-300 mt-0.5">
              {error}
            </p>
          </div>
          <button
            onClick={() => loadData(filterType)}
            className="px-3 py-1.5 rounded-xl bg-rose-600 text-white text-xs font-medium hover:bg-rose-700 transition"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const {summary, waterfall, gateway_comparison, actionable_alerts} = data;
  const topAlert = actionable_alerts.length > 0 ? actionable_alerts[0] : null;

  return (
    <div className="relative space-y-6 pb-12">
      {/* Ambient glowing mesh gradients for realistic glassmorphism depth */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-indigo-400/10 dark:bg-indigo-600/10 rounded-full blur-3xl pointer-events-none -z-10" />
      <div className="absolute top-40 right-10 w-80 h-80 bg-emerald-400/10 dark:bg-emerald-600/10 rounded-full blur-3xl pointer-events-none -z-10" />

      {/* 1. Header & Flexible Timeline Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-2">
        <div>
          <div className="flex items-center space-x-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
              Executive Cockpit
            </h1>
            <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold backdrop-blur-md bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20 shadow-xs">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>{summary.health_score}% Financial Health</span>
            </div>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Realized cash liquidity, gateway leakages, and audit health for{" "}
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              {orgName}
            </span>
          </p>
        </div>

        {/* Timeline & Custom Range Controls */}
        <div className="relative flex flex-wrap items-center gap-2">
          {/* Preset Pills */}
          <div className="inline-flex p-1 rounded-xl backdrop-blur-xl bg-white/70 dark:bg-slate-900/60 border border-white/60 dark:border-white/10 shadow-sm text-xs font-medium text-slate-600 dark:text-slate-300">
            <button
              onClick={() => setFilterType("all")}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                filterType === "all"
                  ? "bg-slate-900 dark:bg-white text-white dark:text-slate-900 shadow-xs font-semibold"
                  : "hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              All Time
            </button>
            <button
              onClick={() => setFilterType("this_month")}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                filterType === "this_month"
                  ? "bg-slate-900 dark:bg-white text-white dark:text-slate-900 shadow-xs font-semibold"
                  : "hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              This Month
            </button>
            <button
              onClick={() => setFilterType("last_30")}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                filterType === "last_30"
                  ? "bg-slate-900 dark:bg-white text-white dark:text-slate-900 shadow-xs font-semibold"
                  : "hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              Last 30 Days
            </button>
          </div>

          {/* Month & Custom Popover Trigger */}
          <div className="relative">
            <button
              onClick={() => setShowDatePicker(!showDatePicker)}
              className={`inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold backdrop-blur-xl border transition-all shadow-sm ${
                filterType === "month_picker" || filterType === "custom"
                  ? "bg-indigo-600 text-white border-indigo-500 shadow-indigo-500/20"
                  : "bg-white/70 dark:bg-slate-900/60 text-slate-700 dark:text-slate-200 border-white/60 dark:border-white/10 hover:bg-white"
              }`}
            >
              <Calendar className="w-3.5 h-3.5" />
              <span>{activeDateLabel}</span>
              <ChevronDown className="w-3.5 h-3.5 opacity-60" />
            </button>

            {/* Custom Date Range & Month Dropdown Popover */}
            {showDatePicker && (
              <div className="absolute right-0 mt-2 w-72 p-4 rounded-2xl backdrop-blur-2xl bg-white/90 dark:bg-slate-900/90 border border-white/80 dark:border-white/10 shadow-2xl z-50 space-y-4 animate-in fade-in zoom-in-95 duration-150">
                <div>
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1.5">
                    Pick a Month
                  </label>
                  <select
                    value={selectedMonth}
                    onChange={(e) => handleSelectMonth(e.target.value)}
                    className="w-full text-xs font-medium px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="2026-05">May 2026 (Live Sample)</option>
                    <option value="2026-04">April 2026</option>
                    <option value="2026-03">March 2026</option>
                    <option value="2026-02">February 2026</option>
                    <option value="2026-01">January 2026</option>
                    <option value="2025-12">December 2025</option>
                  </select>
                </div>

                <div className="pt-2 border-t border-slate-200/80 dark:border-slate-800">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1.5">
                    Custom Date Window
                  </label>
                  <div className="space-y-2">
                    <div>
                      <span className="text-[10px] text-slate-400 block">
                        From:
                      </span>
                      <input
                        type="date"
                        value={customStart}
                        onChange={(e) => setCustomStart(e.target.value)}
                        className="w-full text-xs px-2.5 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200"
                      />
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 block">
                        To:
                      </span>
                      <input
                        type="date"
                        value={customEnd}
                        onChange={(e) => setCustomEnd(e.target.value)}
                        className="w-full text-xs px-2.5 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200"
                      />
                    </div>
                    <button
                      onClick={handleApplyCustomRange}
                      disabled={!customStart || !customEnd}
                      className="w-full mt-2 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700 disabled:opacity-50 transition shadow-sm"
                    >
                      Apply Custom Range
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          <button
            onClick={() => loadData(filterType)}
            title="Refresh Metrics"
            className="p-2 rounded-xl backdrop-blur-xl bg-white/70 dark:bg-slate-900/60 border border-white/60 dark:border-white/10 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition shadow-sm"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${
                loading ? "animate-spin text-indigo-600" : ""
              }`}
            />
          </button>
        </div>
      </div>

      {/* 2. Top Sleek Alert Banner (Dismissible / Compact) */}
      {topAlert && (
        <div className="relative overflow-hidden rounded-2xl backdrop-blur-xl bg-linear-to-r from-amber-50/80 via-white/80 to-amber-50/80 dark:from-amber-950/30 dark:via-slate-900/70 dark:to-amber-950/30 border border-amber-200/80 dark:border-amber-900/50 p-3.5 shadow-sm flex items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-xl bg-amber-100 dark:bg-amber-900/50 flex items-center justify-center text-amber-700 dark:text-amber-400 font-bold shrink-0">
              <AlertTriangle className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs font-bold text-amber-950 dark:text-amber-200">
                {topAlert.title}
              </div>
              <p className="text-[11px] text-amber-800 dark:text-amber-300/90 leading-tight">
                {topAlert.description}
              </p>
            </div>
          </div>
          {topAlert.action_label && topAlert.action_target && (
            <button
              onClick={() => onNavigate(topAlert.action_target!)}
              className="shrink-0 px-3 py-1.5 rounded-xl bg-white dark:bg-slate-800 border border-amber-300 dark:border-amber-800 text-xs font-semibold text-amber-900 dark:text-amber-200 hover:bg-amber-50 transition shadow-xs flex items-center space-x-1"
            >
              <span>{topAlert.action_label}</span>
              <ArrowRight className="w-3 h-3 ml-0.5" />
            </button>
          )}
        </div>
      )}

      {/* 3. Four Core Glassmorphic Hero Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Net Cleared Cash in Bank (Primary Hero) */}
        <div className="relative overflow-hidden rounded-2xl backdrop-blur-xl bg-white/70 dark:bg-slate-900/60 border border-white/60 dark:border-white/10 p-5 shadow-lg shadow-emerald-500/5 hover:shadow-xl hover:-translate-y-0.5 transition-all duration-300">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">
            <span className="flex items-center space-x-1.5">
              <Wallet className="w-3.5 h-3.5 text-emerald-600" />
              <span>Net Bank Cash</span>
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
              Cleared & Verified
            </span>
          </div>
          <div className="text-2xl font-extrabold text-emerald-700 dark:text-emerald-400 tracking-tight font-mono">
            {formatINR(summary.net_settled_cash)}
          </div>
          <div className="mt-2 text-[11px] text-slate-500 dark:text-slate-400 flex items-center justify-between">
            <span>{summary.bank_credit_count} deposits credited</span>
            <span className="font-semibold text-emerald-600">
              {summary.settled_batches_pct}% settled
            </span>
          </div>
        </div>

        {/* Card 2: Gross Invoiced MRR */}
        <div className="relative overflow-hidden rounded-2xl backdrop-blur-xl bg-white/70 dark:bg-slate-900/60 border border-white/60 dark:border-white/10 p-5 shadow-lg shadow-slate-500/5 hover:shadow-xl hover:-translate-y-0.5 transition-all duration-300">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">
            <span className="flex items-center space-x-1.5">
              <Receipt className="w-3.5 h-3.5 text-indigo-600" />
              <span>Gross Invoiced</span>
            </span>
            <span className="text-[10px] font-medium text-slate-400">
              Billing Source
            </span>
          </div>
          <div className="text-2xl font-extrabold text-slate-900 dark:text-white tracking-tight font-mono">
            {formatINR(summary.gross_billed_amount)}
          </div>
          <div className="mt-2 text-[11px] text-slate-500 dark:text-slate-400 flex items-center justify-between">
            <span>{summary.invoice_count} invoices raised</span>
            <span className="font-semibold text-indigo-600">
              {summary.matched_invoices_pct}% matched
            </span>
          </div>
        </div>

        {/* Card 3: True Gateway Take-Rate */}
        <div className="relative overflow-hidden rounded-2xl backdrop-blur-xl bg-white/70 dark:bg-slate-900/60 border border-white/60 dark:border-white/10 p-5 shadow-lg shadow-slate-500/5 hover:shadow-xl hover:-translate-y-0.5 transition-all duration-300">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">
            <span className="flex items-center space-x-1.5">
              <Percent className="w-3.5 h-3.5 text-sky-600" />
              <span>Gateway Take-Rate</span>
            </span>
            <span
              className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                summary.blended_take_rate_pct <= 2.2
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : "bg-amber-50 text-amber-700 border-amber-200"
              }`}
            >
              {summary.blended_take_rate_pct <= 2.2 ? "Optimal" : "Elevated"}
            </span>
          </div>
          <div className="text-2xl font-extrabold text-slate-900 dark:text-white tracking-tight font-mono">
            {summary.blended_take_rate_pct.toFixed(2)}%
          </div>
          <div className="mt-2 text-[11px] text-slate-500 dark:text-slate-400 flex items-center justify-between">
            <span>MDR + 18% GST cost:</span>
            <span className="font-semibold text-slate-700 dark:text-slate-300 font-mono">
              {formatINR(summary.total_gateway_deductions)}
            </span>
          </div>
        </div>

        {/* Card 4: Recovered Overcharges & Unresolved Exposure */}
        <div className="relative overflow-hidden rounded-2xl backdrop-blur-xl bg-white/70 dark:bg-slate-900/60 border border-white/60 dark:border-white/10 p-5 shadow-lg shadow-slate-500/5 hover:shadow-xl hover:-translate-y-0.5 transition-all duration-300">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">
            <span>Audit Overcharges</span>
            <button
              onClick={() => onNavigate("fee-audit")}
              className="text-[10px] font-semibold text-indigo-600 hover:text-indigo-800 transition"
            >
              Dispute Claim &rarr;
            </button>
          </div>
          <div className="text-2xl font-extrabold text-indigo-700 dark:text-indigo-400 tracking-tight font-mono">
            {formatINR(summary.fee_leakage_detected)}
          </div>
          <div className="mt-2 text-[11px] flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span>{summary.overcharged_txns_count} violations caught</span>
            {summary.unresolved_exposure > 0 && (
              <span
                onClick={() => onNavigate("exceptions")}
                className="cursor-pointer text-rose-600 font-semibold hover:underline"
              >
                {formatINR(summary.unresolved_exposure)} at risk
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 4. Sleek Cashflow Realization Flow (Glass Waterfall) */}
      <div className="rounded-2xl backdrop-blur-xl bg-white/70 dark:bg-slate-900/60 border border-white/60 dark:border-white/10 p-6 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white">
              Revenue-to-Bank Cashflow Journey
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Step-by-step conversion from invoiced subscription revenue to
              cleared funds
            </p>
          </div>
          <div className="text-xs font-semibold px-3 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 self-start">
            {summary.matched_invoices_pct}% Invoices Cleared
          </div>
        </div>

        {/* Clean Stepper Cards */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 pt-2">
          {waterfall.map((step, idx) => {
            const isStarting = step.step_type === "starting";
            const isEnding = step.step_type === "net_realized";

            return (
              <div
                key={step.step_key}
                className={`p-4 rounded-xl backdrop-blur-md border transition-all ${
                  isEnding
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-950 dark:text-emerald-200"
                    : isStarting
                    ? "bg-indigo-500/5 border-indigo-500/20 text-slate-900 dark:text-white"
                    : "bg-white/40 dark:bg-slate-800/40 border-white/40 dark:border-white/5 text-slate-700 dark:text-slate-300"
                }`}
              >
                <div className="flex items-center justify-between text-[11px] font-bold opacity-60 mb-1">
                  <span>STEP 0{idx + 1}</span>
                  <span>{step.percentage_of_gross.toFixed(1)}%</span>
                </div>
                <div
                  className="text-xs font-semibold truncate"
                  title={step.label}
                >
                  {step.label}
                </div>
                <div
                  className={`text-lg font-extrabold font-mono mt-1 ${
                    isEnding
                      ? "text-emerald-600 dark:text-emerald-400"
                      : isStarting
                      ? "text-slate-900 dark:text-white"
                      : "text-rose-600 dark:text-rose-400"
                  }`}
                >
                  {!isStarting && !isEnding && "-"}
                  {formatINR(step.amount)}
                </div>
                <p className="text-[10px] text-slate-400 mt-1 line-clamp-2 leading-tight">
                  {step.description}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* 5. Gateway Breakdown & Quick Operational Shortcuts */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Gateway Comparison (8 cols) */}
        <div className="lg:col-span-8 rounded-2xl backdrop-blur-xl bg-white/70 dark:bg-slate-900/60 border border-white/60 dark:border-white/10 p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                Payment Gateway Performance & Take-Rate
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Volume processed, total deductions, and fee overcharges detected
              </p>
            </div>
            <button
              onClick={() => onNavigate("fee-audit")}
              className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
            >
              Rate Cards &rarr;
            </button>
          </div>

          {gateway_comparison.length === 0 ? (
            <div className="p-12 text-center text-slate-400 text-xs">
              No gateway transactions ingested yet.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
              {gateway_comparison.map((gw) => (
                <div
                  key={gw.gateway}
                  className="p-4 rounded-xl backdrop-blur-md bg-white/40 dark:bg-slate-800/40 border border-white/60 dark:border-white/5 space-y-3 shadow-xs"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-sm text-slate-900 dark:text-white">
                        {gw.gateway}
                      </span>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-200/70 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                        {gw.volume_share_pct.toFixed(0)}% Share
                      </span>
                    </div>
                    <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800">
                      {gw.effective_take_rate_pct.toFixed(2)}% take-rate
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-slate-200/60 dark:border-slate-700/60">
                    <div>
                      <span className="text-slate-400 text-[10px] uppercase font-bold block">
                        Volume
                      </span>
                      <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                        {formatINR(gw.gross_volume)}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400 text-[10px] uppercase font-bold block">
                        Deductions
                      </span>
                      <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                        {formatINR(gw.total_deductions)}
                      </span>
                    </div>
                  </div>

                  {gw.overcharge_amount > 0 ? (
                    <div className="flex items-center justify-between p-2 rounded-lg bg-rose-50/80 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 text-[11px] border border-rose-200/60 dark:border-rose-900/50">
                      <span>Fee Leakage Flagged:</span>
                      <span className="font-bold font-mono">
                        {formatINR(gw.overcharge_amount)}
                      </span>
                    </div>
                  ) : (
                    <div className="flex items-center space-x-1 text-[11px] text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>All MDR fees & GST compliant</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Quick Operations Shortcuts (4 cols) */}
        <div className="lg:col-span-4 rounded-2xl backdrop-blur-xl bg-white/70 dark:bg-slate-900/60 border border-white/60 dark:border-white/10 p-6 shadow-xl space-y-4 flex flex-col justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white">
              Operations Hubs
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Jump directly to specific financial workbenches
            </p>
          </div>

          <div className="space-y-2">
            <button
              onClick={() => onNavigate("reconcile")}
              className="w-full flex items-center justify-between p-3 rounded-xl backdrop-blur-md bg-white/50 dark:bg-slate-800/50 hover:bg-indigo-50 dark:hover:bg-indigo-950/30 border border-white/60 dark:border-white/5 text-xs font-semibold text-slate-800 dark:text-slate-200 transition group"
            >
              <span>3-Layer Reconciliation Engine</span>
              <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-indigo-600 group-hover:translate-x-0.5 transition" />
            </button>

            <button
              onClick={() => onNavigate("exceptions")}
              className="w-full flex items-center justify-between p-3 rounded-xl backdrop-blur-md bg-white/50 dark:bg-slate-800/50 hover:bg-indigo-50 dark:hover:bg-indigo-950/30 border border-white/60 dark:border-white/5 text-xs font-semibold text-slate-800 dark:text-slate-200 transition group"
            >
              <div className="flex items-center space-x-2">
                <span>Resolution Queue</span>
                {summary.open_exceptions_count > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-rose-500 text-white font-mono">
                    {summary.open_exceptions_count}
                  </span>
                )}
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-indigo-600 group-hover:translate-x-0.5 transition" />
            </button>

            <button
              onClick={() => onNavigate("fee-audit")}
              className="w-full flex items-center justify-between p-3 rounded-xl backdrop-blur-md bg-white/50 dark:bg-slate-800/50 hover:bg-indigo-50 dark:hover:bg-indigo-950/30 border border-white/60 dark:border-white/5 text-xs font-semibold text-slate-800 dark:text-slate-200 transition group"
            >
              <span>MDR & 18% GST Fee Audit</span>
              <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-indigo-600 group-hover:translate-x-0.5 transition" />
            </button>

            <button
              onClick={() => onNavigate("upload")}
              className="w-full flex items-center justify-between p-3 rounded-xl backdrop-blur-md bg-white/50 dark:bg-slate-800/50 hover:bg-indigo-50 dark:hover:bg-indigo-950/30 border border-white/60 dark:border-white/5 text-xs font-semibold text-slate-800 dark:text-slate-200 transition group"
            >
              <span>Ingest New Bank Statements</span>
              <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-indigo-600 group-hover:translate-x-0.5 transition" />
            </button>
          </div>

          <div className="p-3 rounded-xl bg-slate-50/80 dark:bg-slate-800/40 text-[11px] text-slate-400 flex items-center justify-between">
            <span>Rekon Engine Active</span>
            <span className="font-mono">v2.0</span>
          </div>
        </div>
      </div>
    </div>
  );
};
