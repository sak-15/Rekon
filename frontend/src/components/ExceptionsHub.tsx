import React, {useState, useEffect} from "react";
import {
  Sparkles,
  AlertTriangle,
  AlertOctagon,
  Clock,
  CheckCircle2,
  RefreshCw,
  Search,
  X,
  ShieldAlert,
  Copy,
  Check,
  ChevronRight,
  Zap,
} from "lucide-react";
import {
  api,
  ReconciliationException,
  ExceptionSummary,
  ExceptionType,
  ExceptionSeverity,
  ResolutionStatus,
} from "../api/client";

interface ExceptionsHubProps {
  onRefreshParent?: () => void;
}

export const ExceptionsHub: React.FC<ExceptionsHubProps> = ({
  onRefreshParent,
}) => {
  // Data states
  const [exceptions, setExceptions] = useState<ReconciliationException[]>([]);
  const [summary, setSummary] = useState<ExceptionSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState<ResolutionStatus | "all">(
    "all"
  );
  const [typeFilter, setTypeFilter] = useState<ExceptionType | "all">("all");
  const [severityFilter, setSeverityFilter] = useState<
    ExceptionSeverity | "all"
  >("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Inspect Drawer
  const [activeException, setActiveException] =
    useState<ReconciliationException | null>(null);

  // Action states inside drawer
  const [actionNotes, setActionNotes] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [copiedDispute, setCopiedDispute] = useState(false);

  // Manual Match State
  const [manualTargetType, setManualTargetType] =
    useState<string>("gateway_txn");
  const [manualTargetId, setManualTargetId] = useState<string>("");

  // Batch action state
  const [batchThreshold, setBatchThreshold] = useState<number>(5.0);
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchModalOpen, setBatchModalOpen] = useState(false);

  // Load summary metrics
  const loadSummary = async () => {
    setSummaryLoading(true);
    try {
      const data = await api.getExceptionSummary();
      setSummary(data);
    } catch (err: any) {
      console.error("Failed to load exception summary:", err);
    } finally {
      setSummaryLoading(false);
    }
  };

  // Load exception queue list
  const loadExceptions = async () => {
    setLoading(true);
    try {
      const params: any = {limit: 100, offset: 0};
      if (statusFilter !== "all") params.status = statusFilter;
      if (typeFilter !== "all") params.exception_type = typeFilter;
      if (severityFilter !== "all") params.severity = severityFilter;

      const data = await api.listExceptions(params);
      setExceptions(data.items);

      // Keep active exception updated if open
      if (activeException) {
        const updated = data.items.find((e) => e.id === activeException.id);
        if (updated) setActiveException(updated);
      }
    } catch (err: any) {
      console.error("Failed to load exceptions:", err);
      setExceptions([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSummary();
  }, []);

  useEffect(() => {
    loadExceptions();
  }, [statusFilter, typeFilter, severityFilter]);

  // Format currency in INR
  const formatINR = (val: number | string | undefined | null) => {
    if (val === undefined || val === null) return "₹0.00";
    const num = typeof val === "string" ? parseFloat(val) : val;
    if (isNaN(num)) return "₹0.00";
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(num);
  };

  // Filtered exceptions by search query
  const filteredExceptions = exceptions.filter((exc) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      exc.title.toLowerCase().includes(q) ||
      exc.root_cause_explanation.toLowerCase().includes(q) ||
      (exc.entity_reference &&
        exc.entity_reference.toLowerCase().includes(q)) ||
      (exc.customer_info && exc.customer_info.toLowerCase().includes(q)) ||
      exc.exception_type.toLowerCase().includes(q) ||
      exc.status.toLowerCase().includes(q)
    );
  });

  // Action: Single Write-Off
  const handleWriteOff = async () => {
    if (!activeException) return;
    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await api.writeOffException(activeException.id, {
        notes: actionNotes || "Written off to Rounding Expense ledger.",
        max_allowed: 50.0,
      });
      setActiveException(updated);
      setActionSuccess("Successfully written off to Rounding Expense ledger.");
      setActionNotes("");
      loadSummary();
      loadExceptions();
      if (onRefreshParent) onRefreshParent();
    } catch (err: any) {
      setActionError(err.message || "Failed to write off exception.");
    } finally {
      setActionLoading(false);
    }
  };

  // Action: Manual Match
  const handleManualMatch = async () => {
    if (!activeException || !manualTargetId.trim()) {
      setActionError("Please enter a valid target record reference or ID.");
      return;
    }
    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await api.manualMatchException(activeException.id, {
        target_entity_type: manualTargetType,
        target_entity_id: manualTargetId.trim(),
        notes: actionNotes || "Manually linked by finance operator.",
      });
      setActiveException(updated);
      setActionSuccess(
        "Successfully matched record and updated reconciliation status."
      );
      setActionNotes("");
      setManualTargetId("");
      loadSummary();
      loadExceptions();
      if (onRefreshParent) onRefreshParent();
    } catch (err: any) {
      setActionError(err.message || "Failed to manually link record.");
    } finally {
      setActionLoading(false);
    }
  };

  // Action: Status Update (Investigating / Disputed / Resolved)
  const handleUpdateStatus = async (newStatus: ResolutionStatus) => {
    if (!activeException) return;
    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await api.updateExceptionStatus(activeException.id, {
        status: newStatus,
        notes: actionNotes || `Status updated to ${newStatus}.`,
      });
      setActiveException(updated);
      setActionSuccess(`Queue status updated to ${newStatus.toUpperCase()}.`);
      setActionNotes("");
      loadSummary();
      loadExceptions();
      if (onRefreshParent) onRefreshParent();
    } catch (err: any) {
      setActionError(err.message || "Failed to update status.");
    } finally {
      setActionLoading(false);
    }
  };

  // Action: 1-Click Batch Write-Off
  const handleBatchWriteOff = async () => {
    setBatchLoading(true);
    try {
      const results = await api.batchWriteOffExceptions({
        max_threshold: batchThreshold,
      });
      setBatchModalOpen(false);
      loadSummary();
      loadExceptions();
      if (onRefreshParent) onRefreshParent();
      alert(
        `Successfully written off ${results.length} minor rounding deltas!`
      );
    } catch (err: any) {
      alert(`Batch write off failed: ${err.message}`);
    } finally {
      setBatchLoading(false);
    }
  };

  // Helper: Copy Dispute Ticket
  const copyDisputeDetails = () => {
    if (!activeException) return;
    const text = `[REKON DISPUTE TICKET]
Issue: ${activeException.title}
Entity: ${activeException.entity_reference || "N/A"}
Customer: ${activeException.customer_info || "N/A"}
Expected: ${formatINR(activeException.expected_amount)}
Actual: ${formatINR(activeException.actual_amount)}
Discrepancy Delta: ${formatINR(activeException.discrepancy_amount)}
Root Cause Diagnosis:
${activeException.root_cause_explanation}
Suggested Resolution:
${activeException.suggested_action || "Investigate with gateway provider."}
Timestamp: ${new Date(activeException.created_at).toLocaleString()}`;

    navigator.clipboard.writeText(text);
    setCopiedDispute(true);
    setTimeout(() => setCopiedDispute(false), 2500);
  };

  // Human-friendly severity badge
  const renderSeverityBadge = (sev: ExceptionSeverity) => {
    switch (sev) {
      case "critical":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-800">
            <AlertOctagon className="w-3 h-3 mr-1" />
            Critical
          </span>
        );
      case "high":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold bg-orange-50 dark:bg-orange-950/60 text-orange-700 dark:text-orange-400 border border-orange-200 dark:border-orange-800">
            <AlertTriangle className="w-3 h-3 mr-1" />
            High
          </span>
        );
      case "medium":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
            Medium
          </span>
        );
      case "low":
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
            Low
          </span>
        );
    }
  };

  // Human-friendly status badge
  const renderStatusBadge = (status: ResolutionStatus) => {
    switch (status) {
      case "open":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-50 dark:bg-rose-950/50 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-800">
            Open
          </span>
        );
      case "investigating":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
            Investigating
          </span>
        );
      case "resolved":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
            <CheckCircle2 className="w-3 h-3 mr-1" />
            Resolved
          </span>
        );
      case "written_off":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-purple-50 dark:bg-purple-950/50 text-purple-600 dark:text-purple-400 border border-purple-200 dark:border-purple-800">
            Written Off
          </span>
        );
      case "disputed":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-sky-50 dark:bg-sky-950/50 text-sky-600 dark:text-sky-400 border border-sky-200 dark:border-sky-800">
            Disputed
          </span>
        );
    }
  };

  // Human-friendly exception type label
  const getTypeName = (type: ExceptionType) => {
    switch (type) {
      case "missing_bank_credit":
        return "Missing Bank Credit";
      case "unbilled_charge":
        return "Unbilled Gateway Charge";
      case "timing_difference":
        return "Clearing Lag (< 48h)";
      case "paisa_rounding_delta":
        return "Paisa Rounding Delta";
      case "amount_mismatch":
        return "Amount Mismatch";
      case "gateway_fee_discrepancy":
        return "Gateway Fee Delta";
      case "unidentified_bank_deposit":
        return "Unidentified Bank Deposit";
      default:
        return type;
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Header & Actions Bar */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm transition-colors">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight">
                Exception Classification & Resolution Queue
              </h1>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
                <ShieldAlert className="w-3 h-3 mr-1" />
                Phase 4 Hub
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Automated root-cause diagnostics, 1-click minor write-offs, manual
              linkage, and dispute exports.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* 1-Click Batch Write-Off Trigger */}
            <button
              onClick={() => setBatchModalOpen(true)}
              className="inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-purple-50 dark:bg-purple-950/60 hover:bg-purple-100 dark:hover:bg-purple-900/60 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800 transition shadow-sm"
              title="Batch write-off minor rounding discrepancies"
            >
              <Zap className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400" />
              <span>Batch Write Off (&le; ₹5)</span>
            </button>

            {/* Refresh Queue */}
            <button
              onClick={() => {
                loadSummary();
                loadExceptions();
              }}
              disabled={loading || summaryLoading}
              className="p-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-750 transition shadow-sm"
              title="Refresh exception queue"
            >
              <RefreshCw
                className={`w-4 h-4 ${
                  loading || summaryLoading ? "animate-spin" : ""
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {/* 2. Hero Metric Cards (4 Cards) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Unresolved Financial Exposure */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm transition hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Unresolved Exposure
            </span>
            <div className="w-9 h-9 rounded-xl bg-rose-50 dark:bg-rose-950/70 border border-rose-200 dark:border-rose-800 flex items-center justify-center text-rose-600 dark:text-rose-400">
              <ShieldAlert className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
              {formatINR(summary?.total_unresolved_exposure || 0)}
            </div>
            <div className="mt-2 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>At-risk variance</span>
              <span className="text-rose-600 dark:text-rose-400 font-medium">
                {summary?.open_count || 0} Open Items
              </span>
            </div>
          </div>
        </div>

        {/* Card 2: Open Exceptions */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm transition hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Active Exceptions
            </span>
            <div className="w-9 h-9 rounded-xl bg-amber-50 dark:bg-amber-950/70 border border-amber-200 dark:border-amber-800 flex items-center justify-center text-amber-600 dark:text-amber-400">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
              {summary?.open_count || 0}
            </div>
            <div className="mt-2 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>
                Critical: {summary?.severity_breakdown?.critical || 0}
              </span>
              <span className="text-amber-600 dark:text-amber-400 font-medium">
                High: {summary?.severity_breakdown?.high || 0}
              </span>
            </div>
          </div>
        </div>

        {/* Card 3: In Investigation */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm transition hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              In Investigation
            </span>
            <div className="w-9 h-9 rounded-xl bg-sky-50 dark:bg-sky-950/70 border border-sky-200 dark:border-sky-800 flex items-center justify-center text-sky-600 dark:text-sky-400">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
              {summary?.investigating_count || 0}
            </div>
            <div className="mt-2 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>Under review</span>
              <span className="text-sky-600 dark:text-sky-400 font-medium">
                Ops Active
              </span>
            </div>
          </div>
        </div>

        {/* Card 4: Resolved & Written Off */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm transition hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Resolved & Balanced
            </span>
            <div className="w-9 h-9 rounded-xl bg-emerald-50 dark:bg-emerald-950/70 border border-emerald-200 dark:border-emerald-800 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
              {(summary?.resolved_count || 0) +
                (summary?.written_off_count || 0)}
            </div>
            <div className="mt-2 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>Resolved: {summary?.resolved_count || 0}</span>
              <span className="text-purple-600 dark:text-purple-400 font-medium">
                Written Off: {summary?.written_off_count || 0}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Filters & Search Section */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">
              Queue Records Filter
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Filter by status, root-cause category, or severity to isolate
              actionable discrepancies.
            </p>
          </div>

          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search reference, customer, title..."
              className="pl-9 pr-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-xs w-full sm:w-64 outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>
        </div>

        {/* Status Filter Tabs */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {[
            {id: "all", label: "All Status"},
            {id: "open", label: "Open"},
            {id: "investigating", label: "Investigating"},
            {id: "resolved", label: "Resolved"},
            {id: "written_off", label: "Written Off"},
            {id: "disputed", label: "Disputed"},
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id as any)}
              className={`px-3 py-1.5 rounded-xl font-medium transition ${
                statusFilter === tab.id
                  ? "bg-sky-600 text-white shadow-sm"
                  : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-750"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Type & Severity Dropdowns */}
        <div className="flex flex-wrap items-center gap-3 pt-1 text-xs">
          <div className="flex items-center space-x-1.5">
            <span className="text-[11px] font-medium text-slate-400">
              Category:
            </span>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as any)}
              className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 rounded-xl px-2.5 py-1 outline-none focus:ring-2 focus:ring-sky-500"
            >
              <option value="all">All Categories</option>
              <option value="missing_bank_credit">Missing Bank Credit</option>
              <option value="unbilled_charge">Unbilled Gateway Charge</option>
              <option value="timing_difference">Clearing Lag (&lt; 48h)</option>
              <option value="paisa_rounding_delta">
                Paisa Rounding (&le; ₹5)
              </option>
              <option value="amount_mismatch">Amount Mismatch</option>
              <option value="gateway_fee_discrepancy">
                Fee / GST Discrepancy
              </option>
              <option value="unidentified_bank_deposit">
                Unidentified Bank Deposit
              </option>
            </select>
          </div>

          <div className="flex items-center space-x-1.5">
            <span className="text-[11px] font-medium text-slate-400">
              Severity:
            </span>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value as any)}
              className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 rounded-xl px-2.5 py-1 outline-none focus:ring-2 focus:ring-sky-500"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
        </div>
      </div>

      {/* 4. Resolution Queue Table */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-slate-400 text-xs font-mono">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-sky-500" />
            Loading exception resolution queue...
          </div>
        ) : filteredExceptions.length === 0 ? (
          <div className="p-12 text-center text-slate-400 text-xs space-y-1">
            <p className="font-medium text-slate-600 dark:text-slate-300">
              No exceptions found matching current filters.
            </p>
            <p className="text-[11px]">
              Run reconciliation to automatically classify discrepancies or
              adjust filter criteria.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 font-medium uppercase text-[10px] tracking-wider border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="px-5 py-3">Severity</th>
                  <th className="px-5 py-3">Exception / Entity Ref</th>
                  <th className="px-5 py-3">Category</th>
                  <th className="px-5 py-3">Customer / Party</th>
                  <th className="px-5 py-3">Discrepancy Delta</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-sans">
                {filteredExceptions.map((exc) => (
                  <tr
                    key={exc.id}
                    onClick={() => {
                      setActiveException(exc);
                      setActionError(null);
                      setActionSuccess(null);
                      setActionNotes("");
                    }}
                    className={`cursor-pointer transition hover:bg-slate-50/70 dark:hover:bg-slate-800/40 ${
                      activeException?.id === exc.id
                        ? "bg-sky-50/50 dark:bg-sky-950/20"
                        : ""
                    }`}
                  >
                    <td className="px-5 py-3.5 whitespace-nowrap">
                      {renderSeverityBadge(exc.severity)}
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="space-y-0.5">
                        <div className="font-semibold text-slate-800 dark:text-slate-100 line-clamp-1 max-w-[280px]">
                          {exc.title}
                        </div>
                        {exc.entity_reference && (
                          <div className="font-mono text-[10px] text-sky-600 dark:text-sky-400">
                            {exc.entity_reference}
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-3.5 whitespace-nowrap">
                      <span className="text-slate-600 dark:text-slate-300 font-medium">
                        {getTypeName(exc.exception_type)}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 whitespace-nowrap">
                      <span className="text-slate-700 dark:text-slate-300 font-mono text-[11px]">
                        {exc.customer_info || "—"}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 whitespace-nowrap font-mono font-bold text-amber-600 dark:text-amber-400">
                      {formatINR(exc.discrepancy_amount)}
                    </td>
                    <td className="px-5 py-3.5 whitespace-nowrap">
                      {renderStatusBadge(exc.status)}
                    </td>
                    <td className="px-5 py-3.5 whitespace-nowrap text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveException(exc);
                          setActionError(null);
                          setActionSuccess(null);
                          setActionNotes("");
                        }}
                        className="inline-flex items-center space-x-1 text-xs font-semibold text-sky-600 dark:text-sky-400 hover:text-sky-700 dark:hover:text-sky-300 transition"
                      >
                        <span>Resolve</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 5. Slide-Over Interactive Resolution Drawer */}
      {activeException && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex justify-end">
          <div className="w-full max-w-xl bg-white dark:bg-slate-900 h-full shadow-2xl border-l border-slate-200 dark:border-slate-800 flex flex-col animate-in slide-in-from-right duration-200">
            {/* Drawer Header */}
            <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-start justify-between">
              <div className="space-y-1.5">
                <div className="flex items-center space-x-2">
                  {renderSeverityBadge(activeException.severity)}
                  {renderStatusBadge(activeException.status)}
                </div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white leading-tight">
                  {activeException.title}
                </h3>
                {activeException.entity_reference && (
                  <p className="font-mono text-xs text-sky-600 dark:text-sky-400 font-medium">
                    {activeException.entity_reference}
                  </p>
                )}
              </div>
              <button
                onClick={() => setActiveException(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="flex-1 p-6 overflow-y-auto space-y-6 text-xs">
              {/* Alert Messages inside Drawer */}
              {actionSuccess && (
                <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl text-emerald-700 dark:text-emerald-300 flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                  <span>{actionSuccess}</span>
                </div>
              )}
              {actionError && (
                <div className="p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 rounded-xl text-rose-700 dark:text-rose-300 flex items-center space-x-2">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                  <span>{actionError}</span>
                </div>
              )}

              {/* Financial Comparison Summary Cards */}
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-800">
                  <span className="text-[10px] uppercase font-semibold text-slate-400 block">
                    Expected
                  </span>
                  <span className="font-mono font-bold text-slate-800 dark:text-slate-200 text-sm">
                    {formatINR(activeException.expected_amount)}
                  </span>
                </div>
                <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-800">
                  <span className="text-[10px] uppercase font-semibold text-slate-400 block">
                    Actual
                  </span>
                  <span className="font-mono font-bold text-slate-800 dark:text-slate-200 text-sm">
                    {formatINR(activeException.actual_amount)}
                  </span>
                </div>
                <div className="p-3 bg-amber-50 dark:bg-amber-950/40 rounded-xl border border-amber-200 dark:border-amber-800">
                  <span className="text-[10px] uppercase font-semibold text-amber-600 dark:text-amber-400 block">
                    Discrepancy Delta
                  </span>
                  <span className="font-mono font-bold text-amber-700 dark:text-amber-300 text-sm">
                    {formatINR(activeException.discrepancy_amount)}
                  </span>
                </div>
              </div>

              {/* Root Cause Forensic Box */}
              <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 space-y-2">
                <h4 className="font-bold text-slate-900 dark:text-white flex items-center space-x-1.5">
                  <Sparkles className="w-4 h-4 text-sky-500" />
                  <span>Why This Happened (Root Cause):</span>
                </h4>
                <p className="text-slate-600 dark:text-slate-300 leading-relaxed font-sans text-xs">
                  {activeException.root_cause_explanation}
                </p>
                {activeException.suggested_action && (
                  <div className="mt-3 pt-3 border-t border-slate-200 dark:border-slate-700">
                    <span className="font-semibold text-slate-800 dark:text-slate-200 block">
                      Suggested Action:
                    </span>
                    <p className="text-slate-500 dark:text-slate-400 text-[11px] mt-0.5">
                      {activeException.suggested_action}
                    </p>
                  </div>
                )}
              </div>

              {/* Resolution Action Section */}
              <div className="space-y-4 pt-2">
                <h4 className="font-bold text-slate-900 dark:text-white flex items-center space-x-1.5">
                  <ShieldAlert className="w-4 h-4 text-purple-500" />
                  <span>Resolution Actions</span>
                </h4>

                {/* Optional Audit Notes input */}
                <div>
                  <label className="block text-[11px] font-medium text-slate-600 dark:text-slate-300 mb-1">
                    Audit Note / Resolution Comment:
                  </label>
                  <input
                    type="text"
                    value={actionNotes}
                    onChange={(e) => setActionNotes(e.target.value)}
                    placeholder="e.g. Verified with bank statement or fee waiver confirmed."
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200 outline-none focus:ring-2 focus:ring-sky-500 text-xs"
                  />
                </div>

                {/* 1. Immaterial Write-off (eligible if delta <= 50.00) */}
                {activeException.discrepancy_amount <= 50.0 &&
                  activeException.status !== "written_off" && (
                    <div className="p-3.5 rounded-xl border border-purple-200 dark:border-purple-800 bg-purple-50/60 dark:bg-purple-950/30 flex items-center justify-between gap-3">
                      <div>
                        <div className="font-semibold text-purple-900 dark:text-purple-200">
                          1-Click Write Off (
                          {formatINR(activeException.discrepancy_amount)})
                        </div>
                        <div className="text-[11px] text-purple-700 dark:text-purple-400 mt-0.5">
                          Delta is immaterial (&le; ₹50). Automatically balance
                          to Rounding Expense ledger.
                        </div>
                      </div>
                      <button
                        onClick={handleWriteOff}
                        disabled={actionLoading}
                        className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-purple-600 hover:bg-purple-500 text-white shadow-sm transition disabled:opacity-50 whitespace-nowrap"
                      >
                        {actionLoading ? "Writing Off..." : "Write Off Delta"}
                      </button>
                    </div>
                  )}

                {/* 2. Manual Match Option */}
                {activeException.status !== "resolved" && (
                  <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-800/40 space-y-3">
                    <div>
                      <div className="font-semibold text-slate-900 dark:text-white">
                        Manual Linkage (100% Match)
                      </div>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                        Link this record to an unmatched charge, invoice, or
                        bank deposit.
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-2">
                      <select
                        value={manualTargetType}
                        onChange={(e) => setManualTargetType(e.target.value)}
                        className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-2.5 py-1.5 text-xs text-slate-800 dark:text-slate-200 outline-none"
                      >
                        <option value="gateway_txn">Gateway Txn</option>
                        <option value="invoice">Invoice</option>
                        <option value="bank_credit">Bank Credit</option>
                      </select>
                      <input
                        type="text"
                        value={manualTargetId}
                        onChange={(e) => setManualTargetId(e.target.value)}
                        placeholder="Target ID or Reference"
                        className="col-span-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-2.5 py-1.5 text-xs text-slate-800 dark:text-slate-200 outline-none"
                      />
                    </div>

                    <button
                      onClick={handleManualMatch}
                      disabled={actionLoading || !manualTargetId.trim()}
                      className="w-full py-1.5 rounded-xl text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white shadow-sm transition disabled:opacity-50"
                    >
                      {actionLoading ? "Linking..." : "Confirm Manual Link"}
                    </button>
                  </div>
                )}

                {/* 3. Status Action Buttons */}
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  {activeException.status !== "investigating" && (
                    <button
                      onClick={() => handleUpdateStatus("investigating")}
                      disabled={actionLoading}
                      className="px-3 py-1.5 rounded-xl text-xs font-medium border border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-950/40 transition"
                    >
                      Mark as Investigating
                    </button>
                  )}

                  {activeException.status !== "disputed" && (
                    <button
                      onClick={() => handleUpdateStatus("disputed")}
                      disabled={actionLoading}
                      className="px-3 py-1.5 rounded-xl text-xs font-medium border border-sky-200 dark:border-sky-800 text-sky-700 dark:text-sky-400 hover:bg-sky-50 dark:hover:bg-sky-950/40 transition"
                    >
                      Mark as Disputed
                    </button>
                  )}

                  {activeException.status !== "resolved" && (
                    <button
                      onClick={() => handleUpdateStatus("resolved")}
                      disabled={actionLoading}
                      className="px-3 py-1.5 rounded-xl text-xs font-medium border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 transition"
                    >
                      Mark as Resolved
                    </button>
                  )}
                </div>

                {/* 4. Copy Dispute Narrative for Ticket */}
                <div className="pt-2 border-t border-slate-200 dark:border-slate-800">
                  <button
                    onClick={copyDisputeDetails}
                    className="w-full py-2 rounded-xl text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition flex items-center justify-center space-x-2"
                  >
                    {copiedDispute ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-500" />
                        <span>Dispute Narrative Copied to Clipboard!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5 text-slate-500" />
                        <span>
                          Copy Dispute Details (for Gateway / Jira Ticket)
                        </span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Prior Resolution Audit Trail if Resolved */}
              {activeException.resolved_at && (
                <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-200 dark:border-slate-800 space-y-1 text-[11px] text-slate-500 dark:text-slate-400">
                  <div className="font-semibold text-slate-700 dark:text-slate-300">
                    Resolution Audit Record:
                  </div>
                  <div>
                    Action:{" "}
                    <span className="font-mono text-slate-800 dark:text-slate-200">
                      {activeException.resolution_action || "Manual Update"}
                    </span>
                  </div>
                  {activeException.resolution_notes && (
                    <div>Note: {activeException.resolution_notes}</div>
                  )}
                  <div>
                    Resolved at:{" "}
                    {new Date(activeException.resolved_at).toLocaleString()}
                  </div>
                </div>
              )}
            </div>

            {/* Drawer Footer */}
            <div className="p-4 border-t border-slate-200 dark:border-slate-800 flex justify-end">
              <button
                onClick={() => setActiveException(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition"
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 6. Batch Write-Off Modal */}
      {batchModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 max-w-md w-full shadow-xl space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center space-x-2">
                <Zap className="w-4 h-4 text-purple-500" />
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  Batch Write Off Minor Rounding Deltas
                </h3>
              </div>
              <button
                onClick={() => setBatchModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              This action will identify all currently <strong>OPEN</strong>{" "}
              minor rounding discrepancies below your threshold and write them
              off to the <strong>Rounding Expense</strong> ledger.
            </p>

            <div className="space-y-1">
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                Maximum Threshold per Item (₹):
              </label>
              <input
                type="number"
                step="0.5"
                min="0.01"
                max="50.0"
                value={batchThreshold}
                onChange={(e) =>
                  setBatchThreshold(parseFloat(e.target.value) || 0)
                }
                className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200 outline-none focus:ring-2 focus:ring-sky-500 text-xs"
              />
              <span className="text-[10px] text-slate-400">
                Recommended threshold: &le; ₹5.00 (standard paisa & tax
                fractional rounding limit).
              </span>
            </div>

            <div className="flex justify-end space-x-2 pt-3 border-t border-slate-200 dark:border-slate-800 text-xs">
              <button
                onClick={() => setBatchModalOpen(false)}
                className="px-4 py-2 rounded-xl font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleBatchWriteOff}
                disabled={batchLoading}
                className="px-4 py-2 rounded-xl font-semibold bg-purple-600 hover:bg-purple-500 text-white shadow-sm transition disabled:opacity-50"
              >
                {batchLoading
                  ? "Processing Batch..."
                  : "Confirm Batch Write Off"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
