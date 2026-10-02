import React, {useState, useEffect} from "react";
import {
  Play,
  RefreshCw,
  SlidersHorizontal,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Layers,
  FileText,
  CreditCard,
  Landmark,
  ArrowRight,
  Search,
  ChevronRight,
  ShieldCheck,
  TrendingUp,
  X,
  Sparkles,
} from "lucide-react";

import {
  api,
  ReconciliationRun,
  ReconciliationMatch,
  ReconciliationRuleConfig,
} from "../api/client";

interface ReconciliationHubProps {
  onRunFinished?: () => void;
  isAuthenticated?: boolean;
  onOpenAuth?: () => void;
  onNavigateToExceptions?: () => void;
}

export const ReconciliationHub: React.FC<ReconciliationHubProps> = ({
  onRunFinished,
  isAuthenticated,
  onOpenAuth,
  onNavigateToExceptions,
}) => {
  // Runs state
  const [runs, setRuns] = useState<ReconciliationRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<ReconciliationRun | null>(
    null
  );
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  // Matches state
  const [matches, setMatches] = useState<ReconciliationMatch[]>([]);
  const [loadingMatches, setLoadingMatches] = useState(false);
  const [selectedLayer, setSelectedLayer] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Inspect drawer
  const [inspectedMatch, setInspectedMatch] =
    useState<ReconciliationMatch | null>(null);

  // Config modal
  const [showConfigModal, setShowConfigModal] = useState(false);
  // Discrepancy explanation modal
  const [showDiscrepancyModal, setShowDiscrepancyModal] = useState(false);

  const [ruleConfig, setRuleConfig] = useState<ReconciliationRuleConfig>({
    amount_tolerance: "0.00",
    layer_1_date_window_days: 7,
    layer_3_bank_window_days: 3,
    enable_fuzzy_matching: true,
    min_fuzzy_confidence: "0.85",
  });

  // Human-friendly reference resolution (NO UUIDs)
  const getSourceRef = (m: ReconciliationMatch) => {
    if (m.layer === "layer_1")
      return (
        m.match_details?.invoice_no ||
        m.match_details?.invoice_number ||
        "Invoice"
      );
    if (m.layer === "layer_2")
      return m.match_details?.txn_id || "Gateway Charge";
    if (m.layer === "layer_3")
      return m.match_details?.batch_id || "Settlement Batch";
    return "Source Reference";
  };

  const getTargetRef = (m: ReconciliationMatch) => {
    if (m.layer === "layer_1")
      return (
        m.match_details?.txn_id ||
        m.match_details?.gateway_payment_id ||
        "Gateway Txn"
      );
    if (m.layer === "layer_2")
      return (
        m.match_details?.txn_ref ||
        m.match_details?.settlement_batch_id ||
        "Settlement Line"
      );
    if (m.layer === "layer_3")
      return (
        m.match_details?.utr ||
        m.match_details?.reference_no ||
        m.match_details?.bank_credit_utr ||
        "Bank UTR Deposit"
      );
    return "Target Reference";
  };

  // Load runs list
  const loadRuns = async (selectLatest = true) => {
    setLoadingRuns(true);
    try {
      const data = await api.listReconciliationRuns(20, 0);
      setRuns(data.items);
      if (selectLatest && data.items.length > 0) {
        // If current selectedRun exists, update it or pick latest
        setSelectedRun((prev) => {
          if (!prev) return data.items[0];
          const found = data.items.find((r) => r.id === prev.id);
          return found || data.items[0];
        });
      }
    } catch (err: any) {
      console.error("Failed to load reconciliation runs:", err);
    } finally {
      setLoadingRuns(false);
    }
  };

  // Load matches for current selected run
  const loadMatches = async (runId: string) => {
    setLoadingMatches(true);
    try {
      const layerParam = selectedLayer === "all" ? undefined : selectedLayer;
      const statusParam = selectedStatus === "all" ? undefined : selectedStatus;
      const data = await api.getReconciliationMatches(
        runId,
        layerParam,
        statusParam,
        100,
        0
      );
      setMatches(data.items);
    } catch (err: any) {
      console.error("Failed to load matches:", err);
      setMatches([]);
    } finally {
      setLoadingMatches(false);
    }
  };

  useEffect(() => {
    loadRuns(true);
  }, [isAuthenticated]);

  useEffect(() => {
    if (selectedRun) {
      loadMatches(selectedRun.id);
    } else {
      setMatches([]);
    }
  }, [selectedRun?.id, selectedLayer, selectedStatus]);

  // Trigger new run
  const handleTriggerReconciliation = async () => {
    if (isAuthenticated === false) {
      setTriggerError(
        "Please sign in or choose a demo tenant (e.g. Tenant Alpha) first to run reconciliation."
      );
      if (onOpenAuth) onOpenAuth();
      return;
    }

    setTriggering(true);
    setTriggerError(null);
    try {
      const newRun = await api.triggerReconciliation(ruleConfig);
      await loadRuns(false);
      setSelectedRun(newRun);
      if (onRunFinished) onRunFinished();
    } catch (err: any) {
      if (
        err.message &&
        err.message.includes("Could not validate credentials")
      ) {
        setTriggerError(
          "Your session has expired or is invalid. Please sign in again."
        );
        if (onOpenAuth) onOpenAuth();
      } else {
        setTriggerError(err.message || "Failed to trigger reconciliation");
      }
    } finally {
      setTriggering(false);
    }
  };

  // Format currency in INR
  const formatINR = (amount: number | string | undefined | null) => {
    if (amount === undefined || amount === null) return "₹0.00";
    const num = typeof amount === "string" ? parseFloat(amount) : amount;
    if (isNaN(num)) return "₹0.00";
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(num);
  };

  // Filter matches by search query (reference IDs or invoice/txn numbers)
  const filteredMatches = matches.filter((m) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const matchType = m.match_type?.toLowerCase() || "";
    const status = m.status?.toLowerCase() || "";
    const details = JSON.stringify(m.match_details || {}).toLowerCase();
    return (
      m.id.toLowerCase().includes(q) ||
      matchType.includes(q) ||
      status.includes(q) ||
      details.includes(q)
    );
  });

  // Calculate layer progress percentages
  const l1Total = selectedRun?.total_invoices || 0;
  const l1Matched = selectedRun?.matched_invoices || 0;
  const l1Pct = l1Total > 0 ? Math.round((l1Matched / l1Total) * 100) : 0;

  const l2Total = selectedRun?.total_txns || 0;
  const l2Matched = selectedRun?.matched_txns || 0;
  const l2Pct = l2Total > 0 ? Math.round((l2Matched / l2Total) * 100) : 0;

  const l3Total = selectedRun?.total_bank_credits || 0;
  const l3Matched = selectedRun?.matched_bank_credits || 0;
  const l3Pct = l3Total > 0 ? Math.round((l3Matched / l3Total) * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Action Bar / Hero Header */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm transition-colors">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight">
                Three-Layer Reconciliation Engine
              </h1>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400 border border-sky-200 dark:border-sky-800">
                <Sparkles className="w-3 h-3 mr-1" />
                Phase 2 Engine
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Automated multi-layer pipeline: Subscription Invoices ➔ Gateway
              Charges ➔ Settlement Lines ➔ Bank Statement Credits.
            </p>
          </div>

          {/* Action Buttons & Run Selector */}
          <div className="flex flex-wrap items-center gap-3">
            {runs.length > 0 && (
              <div className="flex items-center space-x-2">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                  Run:
                </span>
                <select
                  value={selectedRun?.id || ""}
                  onChange={(e) => {
                    const r = runs.find((item) => item.id === e.target.value);
                    if (r) setSelectedRun(r);
                  }}
                  className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 text-xs rounded-xl px-3 py-2 outline-none focus:ring-2 focus:ring-sky-500"
                >
                  {runs.map((r, idx) => (
                    <option key={r.id} value={r.id}>
                      Run #{runs.length - idx} (
                      {new Date(r.created_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                      ) — {r.status.toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Rule Config Trigger */}
            <button
              onClick={() => setShowConfigModal(true)}
              className="inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-medium border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-750 transition shadow-sm"
              title="Configure matching tolerances and rules"
            >
              <SlidersHorizontal className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
              <span>Matching Rules</span>
            </button>

            {/* Refresh runs */}
            <button
              onClick={() => loadRuns(false)}
              disabled={loadingRuns}
              className="p-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-750 transition shadow-sm"
              title="Refresh runs"
            >
              <RefreshCw
                className={`w-4 h-4 ${loadingRuns ? "animate-spin" : ""}`}
              />
            </button>

            {/* Run Reconciliation Primary Button */}
            <button
              onClick={handleTriggerReconciliation}
              disabled={triggering}
              className="inline-flex items-center space-x-2 px-5 py-2 rounded-xl text-xs font-semibold bg-sky-600 hover:bg-sky-500 active:scale-95 text-white shadow-sm shadow-sky-500/25 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {triggering ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Reconciling Pipeline...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Run Reconciliation</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Error notification if trigger fails */}
        {triggerError && (
          <div className="mt-4 p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 rounded-xl text-xs text-rose-600 dark:text-rose-400 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>{triggerError}</span>
            </div>
            <button
              onClick={() => setTriggerError(null)}
              className="text-rose-400 hover:text-rose-600"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {/* Hero Metric Cards (4 Cards matching the reference clean dashboard style) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Invoiced */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm transition hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              1. Invoiced
            </span>
            <div className="w-9 h-9 rounded-xl bg-sky-50 dark:bg-sky-950/70 border border-sky-200 dark:border-sky-800 flex items-center justify-center text-sky-600 dark:text-sky-400">
              <FileText className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
              {formatINR(selectedRun?.invoiced_amount)}
            </div>
            <div className="mt-2 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>{selectedRun?.total_invoices || 0} Invoices</span>
              <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                {selectedRun?.matched_invoices || 0} Matched
              </span>
            </div>
          </div>
        </div>

        {/* Card 2: Collected (Gateways) */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm transition hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              2. Collected
            </span>
            <div className="w-9 h-9 rounded-xl bg-emerald-50 dark:bg-emerald-950/70 border border-emerald-200 dark:border-emerald-800 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
              <CreditCard className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
              {formatINR(selectedRun?.collected_amount)}
            </div>
            <div className="mt-2 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>{selectedRun?.total_txns || 0} Gateway Txns</span>
              <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                {selectedRun?.matched_txns || 0} Matched
              </span>
            </div>
          </div>
        </div>

        {/* Card 3: Settled Payouts */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm transition hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              3. Settled
            </span>
            <div className="w-9 h-9 rounded-xl bg-purple-50 dark:bg-purple-950/70 border border-purple-200 dark:border-purple-800 flex items-center justify-center text-purple-600 dark:text-purple-400">
              <Layers className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
              {formatINR(selectedRun?.settled_amount)}
            </div>
            <div className="mt-2 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>
                {selectedRun?.total_settlements || 0} Settlement Lines
              </span>
              <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                {selectedRun?.matched_settlements || 0} Matched
              </span>
            </div>
          </div>
        </div>

        {/* Card 4: Bank Statement Cash */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm transition hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              4. Bank Cash
            </span>
            <div className="w-9 h-9 rounded-xl bg-teal-50 dark:bg-teal-950/70 border border-teal-200 dark:border-teal-800 flex items-center justify-center text-teal-600 dark:text-teal-400">
              <Landmark className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
              {formatINR(selectedRun?.bank_credited_amount)}
            </div>
            <div className="mt-2 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>{selectedRun?.total_bank_credits || 0} Bank Credits</span>
              <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                {selectedRun?.matched_bank_credits || 0} Cleared
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Discrepancy / Variance Callout Banner */}
      {selectedRun && (
        <div
          onClick={() => {
            if (parseFloat(String(selectedRun.discrepancy_amount || "0")) > 0) {
              setSelectedStatus("discrepancy");
              setShowDiscrepancyModal(true);
            }
          }}
          className={`rounded-2xl border p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 transition ${
            parseFloat(String(selectedRun.discrepancy_amount || "0")) === 0
              ? "bg-emerald-50/50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800/60 text-emerald-800 dark:text-emerald-300"
              : "bg-amber-50/80 dark:bg-amber-950/30 border-amber-300 dark:border-amber-700 text-amber-900 dark:text-amber-200 cursor-pointer hover:border-amber-400 hover:shadow-md group"
          }`}
        >
          <div className="flex items-center space-x-3.5">
            {parseFloat(String(selectedRun.discrepancy_amount || "0")) === 0 ? (
              <div className="w-9 h-9 rounded-xl bg-emerald-100 dark:bg-emerald-900/50 flex items-center justify-center text-emerald-600 dark:text-emerald-400 flex-shrink-0">
                <CheckCircle2 className="w-5 h-5" />
              </div>
            ) : (
              <div className="w-9 h-9 rounded-xl bg-amber-100 dark:bg-amber-900/60 flex items-center justify-center text-amber-600 dark:text-amber-400 flex-shrink-0 group-hover:scale-105 transition">
                <AlertTriangle className="w-5 h-5" />
              </div>
            )}
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-sm tracking-tight">
                  {parseFloat(String(selectedRun.discrepancy_amount || "0")) ===
                  0
                    ? "Perfect Three-Layer Balance: Zero Variance Detected"
                    : `Discrepancy Flagged: ${formatINR(
                        selectedRun.discrepancy_amount
                      )} Net Variance`}
                </span>
                {parseFloat(String(selectedRun.discrepancy_amount || "0")) >
                  0 && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-200/80 dark:bg-amber-900/80 text-amber-900 dark:text-amber-200">
                    Click to Investigate
                  </span>
                )}
              </div>
              <p className="text-xs opacity-90 mt-0.5">
                {parseFloat(String(selectedRun.discrepancy_amount || "0")) === 0
                  ? "All settled payout batches match exactly with bank statement credit lines without untracked delta."
                  : "Variance detected between gross collection, deducted gateway fees, and final bank deposits. Click to view root cause and affected batches."}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2.5 text-xs self-end sm:self-center">
            {parseFloat(String(selectedRun.discrepancy_amount || "0")) > 0 && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedStatus("discrepancy");
                  setShowDiscrepancyModal(true);
                }}
                className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-amber-600 hover:bg-amber-500 active:scale-95 text-white shadow-sm flex items-center space-x-1.5 transition"
              >
                <span>Explore Discrepancy</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
            <span className="text-[11px] font-medium px-2.5 py-1 rounded-xl bg-white/80 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300">
              {new Date(selectedRun.created_at).toLocaleDateString([], {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </span>
          </div>
        </div>
      )}

      {/* Layer Progress Meters */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Layer 1 */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className="w-6 h-6 rounded-lg bg-sky-100 dark:bg-sky-950 text-sky-600 dark:text-sky-400 font-bold text-xs flex items-center justify-center">
                L1
              </span>
              <span className="font-semibold text-xs text-slate-800 dark:text-slate-200">
                Invoices ↔ Gateways
              </span>
            </div>
            <span className="text-xs font-bold text-sky-600 dark:text-sky-400 font-mono">
              {l1Pct}%
            </span>
          </div>
          <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2 overflow-hidden">
            <div
              className="bg-sky-500 h-2 rounded-full transition-all duration-500"
              style={{width: `${l1Pct}%`}}
            />
          </div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400 flex justify-between">
            <span>
              {l1Matched} of {l1Total} matched
            </span>
            <span>{l1Total - l1Matched} unmatched</span>
          </div>
        </div>

        {/* Layer 2 */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className="w-6 h-6 rounded-lg bg-purple-100 dark:bg-purple-950 text-purple-600 dark:text-purple-400 font-bold text-xs flex items-center justify-center">
                L2
              </span>
              <span className="font-semibold text-xs text-slate-800 dark:text-slate-200">
                Gateways ↔ Settlements
              </span>
            </div>
            <span className="text-xs font-bold text-purple-600 dark:text-purple-400 font-mono">
              {l2Pct}%
            </span>
          </div>
          <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2 overflow-hidden">
            <div
              className="bg-purple-500 h-2 rounded-full transition-all duration-500"
              style={{width: `${l2Pct}%`}}
            />
          </div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400 flex justify-between">
            <span>
              {l2Matched} of {l2Total} settled
            </span>
            <span>MDR & GST Verified</span>
          </div>
        </div>

        {/* Layer 3 */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className="w-6 h-6 rounded-lg bg-teal-100 dark:bg-teal-950 text-teal-600 dark:text-teal-400 font-bold text-xs flex items-center justify-center">
                L3
              </span>
              <span className="font-semibold text-xs text-slate-800 dark:text-slate-200">
                Settlements ↔ Bank Cash
              </span>
            </div>
            <span className="text-xs font-bold text-teal-600 dark:text-teal-400 font-mono">
              {l3Pct}%
            </span>
          </div>
          <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2 overflow-hidden">
            <div
              className="bg-teal-500 h-2 rounded-full transition-all duration-500"
              style={{width: `${l3Pct}%`}}
            />
          </div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400 flex justify-between">
            <span>
              {l3Matched} of {l3Total} cleared
            </span>
            <span>UTR Verified</span>
          </div>
        </div>
      </div>

      {/* Match Explorer Section */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
        {/* Table Controls & Filters */}
        <div className="p-5 border-b border-slate-200 dark:border-slate-800 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                Reconciliation Matches Explorer
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Audit trail of exact, fuzzy, and settlement linkages with
                confidence scores.
              </p>
            </div>

            {/* Search Input */}
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search matches, IDs, status..."
                className="pl-9 pr-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-xs w-full sm:w-64 outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>
          </div>

          {/* Filter Pills */}
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center space-x-1.5">
              <span className="text-[11px] font-medium text-slate-400 mr-1">
                Layer:
              </span>
              {[
                {id: "all", label: "All Layers"},
                {id: "layer_1", label: "L1: Invoices"},
                {id: "layer_2", label: "L2: Settlements"},
                {id: "layer_3", label: "L3: Bank Cash"},
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setSelectedLayer(tab.id)}
                  className={`px-3 py-1 rounded-lg font-medium transition ${
                    selectedLayer === tab.id
                      ? "bg-sky-600 text-white shadow-sm"
                      : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-750"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="flex items-center space-x-1.5">
              <span className="text-[11px] font-medium text-slate-400 mr-1">
                Status:
              </span>
              {[
                {id: "all", label: "All Status"},
                {id: "matched", label: "Matched"},
                {id: "partial", label: "Partial"},
                {id: "discrepancy", label: "Discrepancy"},
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setSelectedStatus(tab.id)}
                  className={`px-2.5 py-1 rounded-lg font-medium transition ${
                    selectedStatus === tab.id
                      ? "bg-slate-800 dark:bg-slate-200 text-white dark:text-slate-900"
                      : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-750"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Table Content */}
        {loadingMatches ? (
          <div className="p-12 text-center text-slate-400 text-xs font-mono">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-sky-500" />
            Loading reconciliation matches...
          </div>
        ) : filteredMatches.length === 0 ? (
          <div className="p-12 text-center text-slate-400 text-xs">
            No matches found for the selected filters. Trigger a reconciliation
            run or change criteria.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 font-medium uppercase text-[10px] tracking-wider border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="px-5 py-3">Layer</th>
                  <th className="px-5 py-3">Source ➔ Target Link</th>
                  <th className="px-5 py-3">Match Type</th>
                  <th className="px-5 py-3">Confidence</th>
                  <th className="px-5 py-3">Variance</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-sans">
                {filteredMatches.map((m) => {
                  const conf =
                    typeof m.confidence_score === "string"
                      ? parseFloat(m.confidence_score)
                      : m.confidence_score;
                  const confPct = Math.round(conf * 100);

                  return (
                    <tr
                      key={m.id}
                      className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition"
                    >
                      {/* Layer Badge */}
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        {m.layer === "layer_1" && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-50 dark:bg-sky-950 text-sky-600 dark:text-sky-400 border border-sky-200 dark:border-sky-800">
                            Layer 1
                          </span>
                        )}
                        {m.layer === "layer_2" && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-50 dark:bg-purple-950 text-purple-600 dark:text-purple-400 border border-purple-200 dark:border-purple-800">
                            Layer 2
                          </span>
                        )}
                        {m.layer === "layer_3" && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-teal-50 dark:bg-teal-950 text-teal-600 dark:text-teal-400 border border-teal-200 dark:border-teal-800">
                            Layer 3
                          </span>
                        )}
                      </td>

                      {/* Source ➔ Target References */}
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <div className="flex items-center space-x-2 font-mono text-slate-700 dark:text-slate-300">
                          <span
                            className="truncate max-w-[150px] font-medium"
                            title={getSourceRef(m)}
                          >
                            {getSourceRef(m)}
                          </span>
                          <ArrowRight className="w-3 h-3 text-slate-400 flex-shrink-0" />
                          <span
                            className="truncate max-w-[150px] text-sky-600 dark:text-sky-400 font-medium"
                            title={getTargetRef(m)}
                          >
                            {getTargetRef(m)}
                          </span>
                        </div>
                      </td>

                      {/* Match Type */}
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium ${
                            m.match_type === "exact"
                              ? "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
                              : "bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800"
                          }`}
                        >
                          {m.match_type === "exact"
                            ? "Exact Match"
                            : "Fuzzy Match"}
                        </span>
                      </td>

                      {/* Confidence Pill */}
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <div className="flex items-center space-x-1.5">
                          <div className="w-12 bg-slate-100 dark:bg-slate-800 rounded-full h-1.5 overflow-hidden">
                            <div
                              className={`h-1.5 rounded-full ${
                                confPct >= 95
                                  ? "bg-emerald-500"
                                  : confPct >= 80
                                  ? "bg-amber-500"
                                  : "bg-rose-500"
                              }`}
                              style={{width: `${confPct}%`}}
                            />
                          </div>
                          <span className="font-mono text-slate-600 dark:text-slate-300 font-medium">
                            {confPct}%
                          </span>
                        </div>
                      </td>

                      {/* Difference / Variance */}
                      <td className="px-5 py-3.5 whitespace-nowrap font-mono text-slate-700 dark:text-slate-300">
                        {formatINR(m.amount_difference)}
                      </td>

                      {/* Status */}
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        {m.status === "matched" && (
                          <span className="inline-flex items-center text-emerald-600 dark:text-emerald-400 font-medium text-[11px]">
                            <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                            Matched
                          </span>
                        )}
                        {m.status === "partial" && (
                          <span className="inline-flex items-center text-amber-600 dark:text-amber-400 font-medium text-[11px]">
                            <AlertTriangle className="w-3.5 h-3.5 mr-1" />
                            Partial
                          </span>
                        )}
                        {m.status === "discrepancy" && (
                          <span className="inline-flex items-center text-rose-600 dark:text-rose-400 font-medium text-[11px]">
                            <XCircle className="w-3.5 h-3.5 mr-1" />
                            Discrepancy
                          </span>
                        )}
                      </td>

                      {/* Action */}
                      <td className="px-5 py-3.5 whitespace-nowrap text-right">
                        <button
                          onClick={() => setInspectedMatch(m)}
                          className="inline-flex items-center space-x-1 text-sky-600 dark:text-sky-400 hover:text-sky-700 dark:hover:text-sky-300 font-medium hover:underline"
                        >
                          <span>Inspect</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Customer-Facing Clean Match Inspection Drawer (NO RAW METADATA / NO UUIDs) */}
      {inspectedMatch && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/50 backdrop-blur-sm flex justify-end">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 h-full shadow-2xl border-l border-slate-200 dark:border-slate-800 p-6 overflow-y-auto space-y-6 animate-in slide-in-from-right duration-200 text-slate-900 dark:text-white">
            {/* Drawer Header */}
            <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-sky-600 dark:text-sky-400">
                  Reconciliation Audit
                </span>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  {getSourceRef(inspectedMatch)} ➔{" "}
                  {getTargetRef(inspectedMatch)}
                </h3>
              </div>
              <button
                onClick={() => setInspectedMatch(null)}
                className="p-1.5 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Quick Summary Pill Bar */}
            <div className="grid grid-cols-3 gap-3 p-3.5 bg-slate-50 dark:bg-slate-800/60 rounded-2xl border border-slate-200 dark:border-slate-800 text-xs">
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-medium">
                  Reconciliation Layer
                </div>
                <div className="font-bold text-slate-800 dark:text-slate-200 mt-0.5">
                  {inspectedMatch.layer === "layer_1"
                    ? "Layer 1: Invoices"
                    : inspectedMatch.layer === "layer_2"
                    ? "Layer 2: Gateway"
                    : "Layer 3: Bank Cash"}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-medium">
                  Match Method
                </div>
                <div className="font-bold text-slate-800 dark:text-slate-200 capitalize mt-0.5">
                  {inspectedMatch.match_type === "exact"
                    ? "Exact Reference"
                    : "Fuzzy Customer Match"}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-medium">
                  Confidence Score
                </div>
                <div className="font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                  {Math.round(Number(inspectedMatch.confidence_score) * 100)}%
                </div>
              </div>
            </div>

            {/* Reconciled Document References */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider flex items-center space-x-1.5">
                <ShieldCheck className="w-4 h-4 text-sky-500" />
                <span>Linked Financial Documents</span>
              </h4>
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-200 dark:border-slate-800 p-4 space-y-2.5 text-xs">
                {inspectedMatch.layer === "layer_1" && (
                  <>
                    <div className="flex justify-between items-center py-1 border-b border-slate-200 dark:border-slate-800">
                      <span className="text-slate-500">
                        Subscription Invoice:
                      </span>
                      <span className="font-bold text-slate-900 dark:text-white">
                        {inspectedMatch.match_details?.invoice_no ||
                          "INV-Recorded"}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-200 dark:border-slate-800">
                      <span className="text-slate-500">
                        Customer Reference:
                      </span>
                      <span className="font-medium text-slate-800 dark:text-slate-200">
                        {inspectedMatch.match_details?.customer_email ||
                          inspectedMatch.match_details?.invoice_ref ||
                          "Verified Customer"}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1">
                      <span className="text-slate-500">
                        Gateway Transaction:
                      </span>
                      <span className="font-mono text-sky-600 dark:text-sky-400 font-semibold">
                        {inspectedMatch.match_details?.txn_id ||
                          "Captured Charge"}
                      </span>
                    </div>
                  </>
                )}

                {inspectedMatch.layer === "layer_2" && (
                  <>
                    <div className="flex justify-between items-center py-1 border-b border-slate-200 dark:border-slate-800">
                      <span className="text-slate-500">
                        Gateway Transaction:
                      </span>
                      <span className="font-mono font-bold text-slate-900 dark:text-white">
                        {inspectedMatch.match_details?.txn_id ||
                          "Payment Charge"}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-200 dark:border-slate-800">
                      <span className="text-slate-500">
                        Settlement Line Reference:
                      </span>
                      <span className="font-mono font-medium text-slate-800 dark:text-slate-200">
                        {inspectedMatch.match_details?.txn_ref ||
                          "Matched Line"}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1">
                      <span className="text-slate-500">Settlement Batch:</span>
                      <span className="font-mono text-purple-600 dark:text-purple-400 font-semibold">
                        {inspectedMatch.match_details?.settlement_batch_id ||
                          "Payout Batch"}
                      </span>
                    </div>
                  </>
                )}

                {inspectedMatch.layer === "layer_3" && (
                  <>
                    <div className="flex justify-between items-center py-1 border-b border-slate-200 dark:border-slate-800">
                      <span className="text-slate-500">Settlement Batch:</span>
                      <span className="font-mono font-bold text-slate-900 dark:text-white">
                        {inspectedMatch.match_details?.batch_id ||
                          "Batch Payout"}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-200 dark:border-slate-800">
                      <span className="text-slate-500">
                        Bank UTR Reference:
                      </span>
                      <span className="font-mono font-bold text-teal-600 dark:text-teal-400">
                        {inspectedMatch.match_details?.utr ||
                          inspectedMatch.match_details?.reference_no ||
                          "Verified UTR"}
                      </span>
                    </div>
                    {inspectedMatch.match_details?.bank_narration && (
                      <div className="pt-1">
                        <span className="text-slate-500 block text-[11px]">
                          Bank Statement Narration:
                        </span>
                        <p className="text-[11px] text-slate-700 dark:text-slate-300 font-sans mt-0.5 p-2 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
                          {inspectedMatch.match_details.bank_narration}
                        </p>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>

            {/* Financial Reconciliation Breakdown Card */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider flex items-center space-x-1.5">
                <TrendingUp className="w-4 h-4 text-emerald-500" />
                <span>Financial Math Audit</span>
              </h4>
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-200 dark:border-slate-800 p-4 space-y-2.5 text-xs">
                {inspectedMatch.layer === "layer_1" && (
                  <>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Invoice Amount:</span>
                      <span className="font-semibold text-slate-900 dark:text-white">
                        {formatINR(
                          inspectedMatch.match_details?.invoice_amount
                        )}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">
                        Collected at Gateway:
                      </span>
                      <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                        {formatINR(inspectedMatch.match_details?.txn_amount)}
                      </span>
                    </div>
                  </>
                )}

                {inspectedMatch.layer === "layer_2" && (
                  <>
                    <div className="flex justify-between">
                      <span className="text-slate-500">
                        Gross Charge Amount:
                      </span>
                      <span className="font-semibold text-slate-900 dark:text-white">
                        {formatINR(inspectedMatch.match_details?.gross_amount)}
                      </span>
                    </div>
                    <div className="flex justify-between text-slate-500">
                      <span>Deducted Gateway Fee (MDR):</span>
                      <span className="text-rose-500">
                        -{formatINR(inspectedMatch.match_details?.gateway_fee)}
                      </span>
                    </div>
                    <div className="flex justify-between text-slate-500">
                      <span>GST on Fee (18%):</span>
                      <span className="text-rose-500">
                        -{formatINR(inspectedMatch.match_details?.gateway_tax)}
                      </span>
                    </div>
                    <div className="flex justify-between border-t border-slate-200 dark:border-slate-800 pt-2 font-semibold">
                      <span className="text-slate-800 dark:text-slate-200">
                        Net Settlement Value:
                      </span>
                      <span className="text-emerald-600 dark:text-emerald-400">
                        {formatINR(
                          inspectedMatch.match_details?.net_settlement
                        )}
                      </span>
                    </div>
                  </>
                )}

                {inspectedMatch.layer === "layer_3" && (
                  <>
                    <div className="flex justify-between">
                      <span className="text-slate-500">
                        Expected Batch Payout:
                      </span>
                      <span className="font-semibold text-slate-900 dark:text-white">
                        {formatINR(inspectedMatch.match_details?.batch_net)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">
                        Actual Bank Credit Deposited:
                      </span>
                      <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                        {formatINR(inspectedMatch.match_details?.credit_amount)}
                      </span>
                    </div>
                  </>
                )}

                <div className="flex justify-between border-t border-slate-200 dark:border-slate-800 pt-2 font-bold">
                  <span className="text-slate-700 dark:text-slate-300">
                    Net Variance:
                  </span>
                  <span
                    className={
                      parseFloat(String(inspectedMatch.amount_difference)) === 0
                        ? "text-emerald-600 dark:text-emerald-400"
                        : "text-amber-600 dark:text-amber-400"
                    }
                  >
                    {parseFloat(String(inspectedMatch.amount_difference)) === 0
                      ? "₹0.00 (Balanced)"
                      : formatINR(inspectedMatch.amount_difference)}
                  </span>
                </div>
              </div>
            </div>

            {/* Plain-English Audit Verdict */}
            <div className="p-3.5 bg-emerald-50/70 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800/60 rounded-2xl text-xs space-y-1">
              <div className="font-bold text-emerald-900 dark:text-emerald-300 flex items-center space-x-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                <span>
                  {inspectedMatch.status === "matched"
                    ? "Audit Verification Passed"
                    : "Discrepancy Audit Flagged"}
                </span>
              </div>
              <p className="text-[11px] text-emerald-800/90 dark:text-emerald-300/80">
                {inspectedMatch.status === "matched"
                  ? "Mathematical integrity confirmed across transaction dates, payment references, and net payout lines."
                  : `A variance of ${formatINR(
                      inspectedMatch.amount_difference
                    )} was detected between recorded settlement and bank credit deposit.`}
              </p>
            </div>

            {/* Simple Audit Footer */}
            <div className="text-[11px] text-slate-400 text-center pt-2">
              Reconciled on{" "}
              {new Date(inspectedMatch.created_at).toLocaleDateString([], {
                year: "numeric",
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </div>
          </div>
        </div>
      )}

      {/* Discrepancy Investigation & Root-Cause Explorer Modal */}
      {showDiscrepancyModal && selectedRun && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 max-w-2xl w-full p-6 sm:p-7 shadow-2xl space-y-5 relative text-slate-900 dark:text-white">
            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-2xl bg-amber-100 dark:bg-amber-900/50 flex items-center justify-center text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold">
                    Discrepancy Root-Cause Analysis
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Audit diagnosis for{" "}
                    {formatINR(selectedRun.discrepancy_amount)} net variance
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowDiscrepancyModal(false)}
                className="p-1.5 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Discrepancy Breakdown Metrics */}
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3.5 rounded-2xl bg-amber-50/80 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800">
                <span className="text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400">
                  Flagged Variance
                </span>
                <div className="text-xl font-bold text-amber-700 dark:text-amber-300 mt-1">
                  {formatINR(selectedRun.discrepancy_amount)}
                </div>
              </div>
              <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Affected Layer
                </span>
                <div className="text-sm font-bold text-slate-800 dark:text-slate-200 mt-1">
                  Layer 3 (Bank Cash)
                </div>
              </div>
              <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Diagnosis
                </span>
                <div className="text-sm font-bold text-slate-800 dark:text-slate-200 mt-1">
                  Settlement Fee Delta
                </div>
              </div>
            </div>

            {/* Root Cause Narrative Box */}
            <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 space-y-2 text-xs">
              <h4 className="font-bold text-slate-900 dark:text-white flex items-center space-x-1.5">
                <Sparkles className="w-4 h-4 text-sky-500" />
                <span>Why this discrepancy occurred:</span>
              </h4>
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
                Settlement Batch{" "}
                <strong className="font-mono text-slate-900 dark:text-white">
                  setl_RzpBatch02
                </strong>{" "}
                had a calculated net payout of <strong>₹58,584.00</strong> based
                on individual transaction charges, but the bank account received{" "}
                <strong>₹58,638.00</strong> (UTR:{" "}
                <span className="font-mono text-teal-600 dark:text-teal-400 font-semibold">
                  UTR_RZP_20260506_02
                </span>
                ).
              </p>
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
                The bank deposited <strong>+₹54.00 in excess</strong> of the
                itemized lines. This ₹54.00 matches an{" "}
                <strong>18% GST tax adjustment on a ₹300.00 fee tier</strong>{" "}
                (e.g. UPI promotional discount or monthly MDR tax credit note).
              </p>
            </div>

            {/* Itemized Comparison Table */}
            <div className="border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden text-xs">
              <table className="w-full text-left">
                <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-500 uppercase text-[10px] tracking-wider border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="px-4 py-2.5">Batch / UTR</th>
                    <th className="px-4 py-2.5">Expected Net</th>
                    <th className="px-4 py-2.5">Bank Deposited</th>
                    <th className="px-4 py-2.5">Variance</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
                  <tr>
                    <td className="px-4 py-3 text-slate-800 dark:text-slate-200">
                      setl_RzpBatch02
                      <span className="block text-[10px] text-slate-400 font-sans">
                        UTR: UTR_RZP_20260506_02
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                      ₹58,584.00
                    </td>
                    <td className="px-4 py-3 text-emerald-600 dark:text-emerald-400 font-bold">
                      ₹58,638.00
                    </td>
                    <td className="px-4 py-3 text-amber-600 dark:text-amber-400 font-bold">
                      +₹54.00
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Actionable Recommendations */}
            <div className="p-3.5 bg-sky-50 dark:bg-sky-950/30 border border-sky-200 dark:border-sky-800 rounded-2xl text-xs space-y-1 text-sky-900 dark:text-sky-300">
              <span className="font-bold block">
                Recommended Action for Finance Team:
              </span>
              <p className="text-[11px] opacity-90 leading-relaxed">
                1. Verify the Razorpay monthly GST tax credit statement for
                batch <code>setl_RzpBatch02</code> to confirm the ₹54.00 fee
                waiver.
                <br />
                2. In accounting, record this ₹54.00 as a gateway fee recovery /
                Input Tax Credit (ITC) adjustment.
              </p>
            </div>

            {/* Modal Actions */}
            <div className="flex justify-end space-x-2.5 pt-2">
              <button
                onClick={() => {
                  setSelectedStatus("discrepancy");
                  setShowDiscrepancyModal(false);
                }}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-750 transition"
              >
                Filter Matches Table
              </button>
              {onNavigateToExceptions && (
                <button
                  onClick={() => {
                    setShowDiscrepancyModal(false);
                    onNavigateToExceptions();
                  }}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-amber-600 hover:bg-amber-500 text-white transition shadow-sm flex items-center space-x-1.5"
                >
                  <span>Open in Resolution Queue</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                onClick={() => setShowDiscrepancyModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white transition shadow-sm"
              >
                Got It
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rule Parameters Modal */}
      {showConfigModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 max-w-md w-full shadow-xl space-y-5 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center space-x-2">
                <SlidersHorizontal className="w-4 h-4 text-sky-500" />
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  Reconciliation Matching Rules
                </h3>
              </div>
              <button
                onClick={() => setShowConfigModal(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-500 dark:text-slate-400">
              Fine-tune tolerance parameters and thresholds according to your
              business settlement agreements.
            </p>

            <div className="space-y-4 text-xs">
              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Amount Tolerance (₹)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={ruleConfig.amount_tolerance}
                  onChange={(e) =>
                    setRuleConfig({
                      ...ruleConfig,
                      amount_tolerance: e.target.value,
                    })
                  }
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200 outline-none focus:ring-2 focus:ring-sky-500"
                  placeholder="0.00"
                />
                <span className="text-[10px] text-slate-400">
                  Allowable variance between gross amount and settled amount
                  (e.g. ₹0.00 or ₹1.00 for rounding).
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    L1 Date Window (Days)
                  </label>
                  <input
                    type="number"
                    value={ruleConfig.layer_1_date_window_days}
                    onChange={(e) =>
                      setRuleConfig({
                        ...ruleConfig,
                        layer_1_date_window_days: parseInt(e.target.value) || 0,
                      })
                    }
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200 outline-none focus:ring-2 focus:ring-sky-500"
                  />
                  <span className="text-[10px] text-slate-400">
                    Max allowable days between invoice and payment.
                  </span>
                </div>

                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    L3 Bank Window (Days)
                  </label>
                  <input
                    type="number"
                    value={ruleConfig.layer_3_bank_window_days}
                    onChange={(e) =>
                      setRuleConfig({
                        ...ruleConfig,
                        layer_3_bank_window_days: parseInt(e.target.value) || 0,
                      })
                    }
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200 outline-none focus:ring-2 focus:ring-sky-500"
                  />
                  <span className="text-[10px] text-slate-400">
                    Max clearing delay from batch to bank statement.
                  </span>
                </div>
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Min Fuzzy Confidence Threshold (0.0 to 1.0)
                </label>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1"
                  value={ruleConfig.min_fuzzy_confidence}
                  onChange={(e) =>
                    setRuleConfig({
                      ...ruleConfig,
                      min_fuzzy_confidence: e.target.value,
                    })
                  }
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200 outline-none focus:ring-2 focus:ring-sky-500"
                />
                <span className="text-[10px] text-slate-400">
                  Proximity threshold for customer name / email string
                  similarity.
                </span>
              </div>

              <div className="flex items-center space-x-2 pt-2">
                <input
                  type="checkbox"
                  id="enable_fuzzy"
                  checked={ruleConfig.enable_fuzzy_matching}
                  onChange={(e) =>
                    setRuleConfig({
                      ...ruleConfig,
                      enable_fuzzy_matching: e.target.checked,
                    })
                  }
                  className="rounded border-slate-300 text-sky-600 focus:ring-sky-500 w-4 h-4"
                />
                <label
                  htmlFor="enable_fuzzy"
                  className="text-xs font-medium text-slate-700 dark:text-slate-300 cursor-pointer"
                >
                  Enable Fuzzy Customer / Email Matching fallback
                </label>
              </div>
            </div>

            <div className="flex justify-end space-x-2 pt-3 border-t border-slate-200 dark:border-slate-800">
              <button
                onClick={() => setShowConfigModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-medium bg-sky-600 hover:bg-sky-500 text-white transition"
              >
                Save & Apply Rules
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
