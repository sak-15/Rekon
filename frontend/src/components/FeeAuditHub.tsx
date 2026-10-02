import {useEffect, useState} from "react";
import {
  Percent,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Download,
  RotateCcw,
  Edit3,
  Trash2,
  Plus,
  Calculator,
  X,
} from "lucide-react";
import {
  api,
  RateCard,
  FeeAuditReportData,
  AuditedTransactionItem,
} from "../api/client";

interface FeeAuditHubProps {
  onRefresh?: () => void;
}

export function FeeAuditHub({onRefresh}: FeeAuditHubProps) {
  const [activeSubTab, setActiveSubTab] = useState<
    "audit" | "rate_cards" | "calculator"
  >("audit");

  // Audit state
  const [auditReport, setAuditReport] = useState<FeeAuditReportData | null>(
    null
  );
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [selectedGateway, setSelectedGateway] = useState<string>("razorpay");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedDisputeItem, setSelectedDisputeItem] =
    useState<AuditedTransactionItem | null>(null);

  // Rate Cards state
  const [rateCards, setRateCards] = useState<RateCard[]>([]);
  const [loadingCards, setLoadingCards] = useState(false);
  const [editingCard, setEditingCard] = useState<RateCard | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editForm, setEditForm] = useState({
    percentage_rate: "0.0200",
    flat_fee: "0.00",
    gst_rate: "0.1800",
    cap_max_fee: "",
    notes: "",
  });
  const [newCardForm, setNewCardForm] = useState({
    gateway: "razorpay",
    payment_method: "card",
    card_network: "credit",
    is_international: false,
    rate_type: "percentage",
    percentage_rate: "0.0200",
    flat_fee: "0.00",
    gst_rate: "0.1800",
    cap_max_fee: "",
    notes: "",
  });

  // Calculator state
  const [calcGross, setCalcGross] = useState<number>(50000);
  const [calcSelectedCardId, setCalcSelectedCardId] = useState<string>("");
  const [calcResult, setCalcResult] = useState<any | null>(null);
  const [loadingCalc, setLoadingCalc] = useState(false);

  // Notification / message
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  // 1. Fetch Fee Audit
  const loadFeeAudit = async () => {
    setLoadingAudit(true);
    try {
      const data = await api.getFeeAudit({gateway: selectedGateway});
      setAuditReport(data);
    } catch (err: any) {
      console.error("Failed to load fee audit", err);
    } finally {
      setLoadingAudit(false);
    }
  };

  // 2. Fetch Rate Cards
  const loadRateCards = async () => {
    setLoadingCards(true);
    try {
      const res = await api.listRateCards(selectedGateway);
      setRateCards(res.items);
      if (res.items.length > 0 && !calcSelectedCardId) {
        setCalcSelectedCardId(res.items[0].id);
      }
    } catch (err: any) {
      console.error("Failed to load rate cards", err);
    } finally {
      setLoadingCards(false);
    }
  };

  useEffect(() => {
    loadFeeAudit();
    loadRateCards();
  }, [selectedGateway]);

  // Handle calculator run
  useEffect(() => {
    if (activeSubTab === "calculator" && calcGross > 0) {
      runCalculator();
    }
  }, [calcGross, calcSelectedCardId, activeSubTab]);

  const runCalculator = async () => {
    setLoadingCalc(true);
    try {
      const res = await api.calculateCharges(
        calcGross,
        calcSelectedCardId || undefined
      );
      setCalcResult(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingCalc(false);
    }
  };

  // Rate card updates
  const handleSaveEdit = async () => {
    if (!editingCard) return;
    try {
      await api.updateRateCard(editingCard.id, {
        percentage_rate: editForm.percentage_rate,
        flat_fee: editForm.flat_fee,
        gst_rate: editForm.gst_rate,
        cap_max_fee: editForm.cap_max_fee ? editForm.cap_max_fee : null,
        notes: editForm.notes,
      });
      setEditingCard(null);
      showToast("Rate card rule updated successfully.");
      loadRateCards();
      loadFeeAudit();
      onRefresh?.();
    } catch (err: any) {
      alert(err.message || "Failed to update rate card");
    }
  };

  const handleCreateRateCard = async () => {
    try {
      await api.createRateCard({
        gateway: newCardForm.gateway as any,
        payment_method: newCardForm.payment_method as any,
        card_network: newCardForm.card_network,
        is_international: newCardForm.is_international,
        rate_type: newCardForm.rate_type as any,
        percentage_rate: newCardForm.percentage_rate,
        flat_fee: newCardForm.flat_fee,
        gst_rate: newCardForm.gst_rate,
        cap_max_fee: newCardForm.cap_max_fee ? newCardForm.cap_max_fee : null,
        notes: newCardForm.notes,
      });
      setShowAddModal(false);
      showToast("New rate card rule created.");
      loadRateCards();
      loadFeeAudit();
      onRefresh?.();
    } catch (err: any) {
      alert(err.message || "Failed to create rate card");
    }
  };

  const handleDeleteCard = async (id: string) => {
    if (!confirm("Are you sure you want to delete this rate card rule?"))
      return;
    try {
      await api.deleteRateCard(id);
      showToast("Rate card rule removed.");
      loadRateCards();
      loadFeeAudit();
      onRefresh?.();
    } catch (err: any) {
      alert(err.message || "Failed to delete rate card");
    }
  };

  const handleResetBenchmarks = async () => {
    if (
      !confirm(
        "Reset all rate cards for this gateway back to standard Indian industry benchmarks (NPCI 0% UPI, RBI ₹20 debit cap, 2% credit)?"
      )
    )
      return;
    try {
      await api.resetRateCards(selectedGateway);
      showToast("Reset to official industry benchmarks.");
      loadRateCards();
      loadFeeAudit();
    } catch (err: any) {
      alert(err.message || "Failed to reset benchmarks");
    }
  };

  const handleExportCSV = async () => {
    try {
      await api.downloadDisputeExport(selectedGateway);
      showToast("Dispute claim CSV downloaded.");
    } catch (err: any) {
      alert("Export failed: " + err.message);
    }
  };

  // Filtered transactions in audit view
  const filteredItems =
    auditReport?.items.filter((item) => {
      if (statusFilter === "all") return true;
      return item.audit_status === statusFilter;
    }) || [];

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toastMsg && (
        <div className="fixed bottom-6 right-6 z-50 bg-slate-900 text-white px-4 py-3 rounded-xl shadow-xl border border-slate-700 flex items-center space-x-2 animate-in fade-in slide-in-from-bottom-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-medium">{toastMsg}</span>
        </div>
      )}

      {/* Header with Subtabs & Gateway Selector */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="p-2 bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 rounded-xl">
                <Percent className="w-5 h-5" />
              </span>
              <div>
                <h1 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white">
                  MDR & 18% GST Fee Audit Engine
                </h1>
                <p className="text-xs text-slate-600 dark:text-slate-300">
                  Mathematical verification of gateway transaction fees, GST
                  deductions, and automated dispute generation.
                </p>
              </div>
            </div>
          </div>

          {/* Controls: Gateway Switcher & Export */}
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-1.5 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
              <button
                onClick={() => setSelectedGateway("razorpay")}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  selectedGateway === "razorpay"
                    ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs"
                    : "text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white"
                }`}
              >
                Razorpay
              </button>
              <button
                onClick={() => setSelectedGateway("stripe")}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  selectedGateway === "stripe"
                    ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs"
                    : "text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white"
                }`}
              >
                Stripe India
              </button>
            </div>

            {auditReport && auditReport.overcharged_count > 0 && (
              <button
                onClick={handleExportCSV}
                className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-xs transition"
              >
                <Download className="w-3.5 h-3.5" />
                <span>
                  Export Dispute Sheet (₹
                  {auditReport.total_overcharged_amount.toFixed(2)})
                </span>
              </button>
            )}
          </div>
        </div>

        {/* Sub-Tabs */}
        <div className="flex items-center space-x-2 mt-5 border-t border-slate-100 dark:border-slate-800 pt-4">
          <button
            onClick={() => setActiveSubTab("audit")}
            className={`px-3.5 py-2 rounded-xl text-xs font-medium transition flex items-center space-x-2 ${
              activeSubTab === "audit"
                ? "bg-sky-50 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800/80"
                : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/50"
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Audit & Discrepancies</span>
            {auditReport && auditReport.overcharged_count > 0 && (
              <span className="px-1.5 py-0.2 bg-rose-500 text-white rounded-full text-[10px] font-bold">
                {auditReport.overcharged_count}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveSubTab("rate_cards")}
            className={`px-3.5 py-2 rounded-xl text-xs font-medium transition flex items-center space-x-2 ${
              activeSubTab === "rate_cards"
                ? "bg-sky-50 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800/80"
                : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/50"
            }`}
          >
            <Percent className="w-3.5 h-3.5" />
            <span>Contracted Rate Cards</span>
            <span className="px-1.5 py-0.2 bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-full text-[10px]">
              {rateCards.length}
            </span>
          </button>

          <button
            onClick={() => setActiveSubTab("calculator")}
            className={`px-3.5 py-2 rounded-xl text-xs font-medium transition flex items-center space-x-2 ${
              activeSubTab === "calculator"
                ? "bg-sky-50 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800/80"
                : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/50"
            }`}
          >
            <Calculator className="w-3.5 h-3.5" />
            <span>MDR & GST Calculator</span>
          </button>
        </div>
      </div>

      {/* TAB 1: AUDIT & DISCREPANCIES VIEW */}
      {activeSubTab === "audit" && (
        <div className="space-y-6">
          {/* 4 Hero Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Card 1: Total Audited */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs">
              <div className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider">
                Audited Volume
              </div>
              <div className="text-xl font-bold text-slate-900 dark:text-white mt-1">
                ₹
                {auditReport
                  ? auditReport.total_gross_volume.toLocaleString("en-IN", {
                      minimumFractionDigits: 2,
                    })
                  : "0.00"}
              </div>
              <div className="text-[11px] text-slate-600 dark:text-slate-300 mt-1 flex items-center space-x-1">
                <span>
                  {auditReport?.total_audited || 0} transactions analyzed
                </span>
              </div>
            </div>

            {/* Card 2: Actual vs Expected MDR */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs">
              <div className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider">
                MDR Fees Deducted
              </div>
              <div className="text-xl font-bold text-slate-900 dark:text-white mt-1">
                ₹
                {auditReport
                  ? auditReport.total_actual_fees.toLocaleString("en-IN", {
                      minimumFractionDigits: 2,
                    })
                  : "0.00"}
              </div>
              <div className="text-[11px] text-slate-600 dark:text-slate-300 mt-1">
                Contracted: ₹
                {auditReport
                  ? auditReport.total_expected_fees.toFixed(2)
                  : "0.00"}
              </div>
            </div>

            {/* Card 3: 18% GST Deducted */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs">
              <div className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider">
                18% GST on Fees
              </div>
              <div className="text-xl font-bold text-slate-900 dark:text-white mt-1">
                ₹
                {auditReport
                  ? auditReport.total_actual_gst.toLocaleString("en-IN", {
                      minimumFractionDigits: 2,
                    })
                  : "0.00"}
              </div>
              <div className="text-[11px] text-slate-600 dark:text-slate-300 mt-1">
                Statutory: ₹
                {auditReport
                  ? auditReport.total_expected_gst.toFixed(2)
                  : "0.00"}
              </div>
            </div>

            {/* Card 4: Recoverable Overcharge (Hero) */}
            <div
              className={`rounded-2xl border p-5 shadow-xs ${
                (auditReport?.total_overcharged_amount || 0) > 0
                  ? "bg-rose-50/70 dark:bg-rose-950/20 border-rose-200 dark:border-rose-900/50"
                  : "bg-emerald-50/70 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-900/50"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider">
                  Recoverable Overcharge
                </div>
                {(auditReport?.total_overcharged_amount || 0) > 0 ? (
                  <span className="p-1 bg-rose-100 dark:bg-rose-900/50 text-rose-600 dark:text-rose-400 rounded-md">
                    <ShieldAlert className="w-3.5 h-3.5" />
                  </span>
                ) : (
                  <span className="p-1 bg-emerald-100 dark:bg-emerald-900/50 text-emerald-600 dark:text-emerald-400 rounded-md">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  </span>
                )}
              </div>
              <div
                className={`text-xl font-bold mt-1 ${
                  (auditReport?.total_overcharged_amount || 0) > 0
                    ? "text-rose-600 dark:text-rose-400"
                    : "text-emerald-600 dark:text-emerald-400"
                }`}
              >
                ₹
                {auditReport
                  ? auditReport.total_overcharged_amount.toLocaleString(
                      "en-IN",
                      {minimumFractionDigits: 2}
                    )
                  : "0.00"}
              </div>
              <div className="text-[11px] text-slate-600 dark:text-slate-300 mt-1">
                {auditReport?.overcharged_count || 0} flagged transactions
              </div>
            </div>
          </div>

          {/* Root-Cause Discrepancy Breakdown Callout */}
          {auditReport && auditReport.overcharged_count > 0 && (
            <div className="bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/50 rounded-2xl p-4">
              <div className="flex items-start space-x-3">
                <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <h3 className="text-xs font-bold text-amber-900 dark:text-amber-300">
                    Discrepancy Root-Cause Analysis
                  </h3>
                  <p className="text-xs text-amber-800/80 dark:text-amber-400/80 mt-0.5">
                    Rekon detected fee variances against your contracted rate
                    card. Below is the breakdown of why each overcharge
                    occurred:
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2.5 mt-3">
                    {Object.entries(auditReport.discrepancies_by_category)
                      .filter(
                        ([key, val]) =>
                          key !== "no_discrepancy" && val.count > 0
                      )
                      .map(([categoryKey, val]) => {
                        const labels: Record<string, string> = {
                          missing_debit_cap: "Missing Debit Card Cap (RBI ₹20)",
                          gst_miscalculation: "18% GST Miscalculation",
                          unauthorized_mdr_markup: "Unauthorized MDR Markup",
                          flat_fee_overcharge: "Flat Fee Delta",
                          gateway_discount: "Gateway Discount",
                        };
                        return (
                          <div
                            key={categoryKey}
                            className="bg-white/80 dark:bg-slate-900/80 p-2.5 rounded-xl border border-amber-200/60 dark:border-amber-900/40"
                          >
                            <div className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 truncate">
                              {labels[categoryKey] || categoryKey}
                            </div>
                            <div className="text-sm font-bold text-slate-900 dark:text-white mt-0.5">
                              ₹{val.amount.toFixed(2)}
                            </div>
                            <div className="text-[10px] text-amber-600 dark:text-amber-400">
                              {val.count} transaction{val.count > 1 ? "s" : ""}
                            </div>
                          </div>
                        );
                      })}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Table of Audited Transactions */}
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">
            {/* Table Header / Filters */}
            <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center space-x-2">
                <span className="text-xs font-bold text-slate-900 dark:text-white">
                  Audited Gateway Transactions
                </span>
                <span className="text-xs text-slate-600 dark:text-slate-300">
                  ({filteredItems.length} records)
                </span>
              </div>

              {/* Status Filter */}
              <div className="flex items-center space-x-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
                <button
                  onClick={() => setStatusFilter("all")}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition ${
                    statusFilter === "all"
                      ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs"
                      : "text-slate-600 dark:text-slate-300"
                  }`}
                >
                  All ({auditReport?.total_audited || 0})
                </button>
                <button
                  onClick={() => setStatusFilter("overcharged")}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition ${
                    statusFilter === "overcharged"
                      ? "bg-rose-50 dark:bg-rose-950 text-rose-600 dark:text-rose-400 font-semibold shadow-xs"
                      : "text-slate-600 dark:text-slate-300"
                  }`}
                >
                  Overcharged ({auditReport?.overcharged_count || 0})
                </button>
                <button
                  onClick={() => setStatusFilter("verified")}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition ${
                    statusFilter === "verified"
                      ? "bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 font-semibold shadow-xs"
                      : "text-slate-600 dark:text-slate-300"
                  }`}
                >
                  Verified ({auditReport?.verified_count || 0})
                </button>
              </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-800 font-semibold">
                  <tr>
                    <th className="py-3 px-4">Transaction</th>
                    <th className="py-3 px-4">Rail</th>
                    <th className="py-3 px-4 text-right">Gross Amount</th>
                    <th className="py-3 px-4 text-right">Expected Fee + GST</th>
                    <th className="py-3 px-4 text-right">Actual Deducted</th>
                    <th className="py-3 px-4 text-right">Variance / Claim</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-center">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {loadingAudit ? (
                    <tr>
                      <td
                        colSpan={8}
                        className="py-8 text-center text-slate-600 dark:text-slate-300"
                      >
                        Running mathematical fee audit...
                      </td>
                    </tr>
                  ) : filteredItems.length === 0 ? (
                    <tr>
                      <td
                        colSpan={8}
                        className="py-8 text-center text-slate-600 dark:text-slate-300"
                      >
                        No transactions found matching criteria. Upload gateway
                        transactions to audit.
                      </td>
                    </tr>
                  ) : (
                    filteredItems.map((item) => (
                      <tr
                        key={item.txn_id}
                        className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition"
                      >
                        <td className="py-3 px-4">
                          <div className="font-mono font-medium text-slate-900 dark:text-white">
                            {item.txn_id}
                          </div>
                          <div className="text-[10px] text-slate-600 dark:text-slate-300">
                            {item.captured_at
                              ? new Date(item.captured_at).toLocaleDateString(
                                  "en-IN"
                                )
                              : "N/A"}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 uppercase">
                            {item.payment_method} • {item.card_network}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right font-medium text-slate-900 dark:text-white">
                          ₹
                          {item.gross_amount.toLocaleString("en-IN", {
                            minimumFractionDigits: 2,
                          })}
                        </td>
                        <td className="py-3 px-4 text-right text-slate-600 dark:text-slate-300">
                          ₹{item.expected_fee.toFixed(2)} + ₹
                          {item.expected_gst.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right font-medium text-slate-900 dark:text-white">
                          ₹{item.actual_fee.toFixed(2)} + ₹
                          {item.actual_gst.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right font-bold">
                          {item.audit_status === "overcharged" ? (
                            <span className="text-rose-600 dark:text-rose-400">
                              +₹{item.total_overcharge.toFixed(2)}
                            </span>
                          ) : item.audit_status === "undercharged" ? (
                            <span className="text-emerald-600 dark:text-emerald-400">
                              -₹{Math.abs(item.total_overcharge).toFixed(2)}
                            </span>
                          ) : (
                            <span className="text-slate-600 dark:text-slate-300">
                              ₹0.00
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          {item.audit_status === "overcharged" ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-900/40">
                              Overcharged
                            </span>
                          ) : item.audit_status === "undercharged" ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-100 dark:bg-blue-950/60 text-blue-700 dark:text-blue-400">
                              Undercharged
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400">
                              Verified
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <button
                            onClick={() => setSelectedDisputeItem(item)}
                            className="text-[11px] text-sky-600 dark:text-sky-400 hover:underline font-medium"
                          >
                            Explore Cause
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: CONTRACTED RATE CARDS VIEW */}
      {activeSubTab === "rate_cards" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                Active Gateway Rate Cards ({selectedGateway.toUpperCase()})
              </h2>
              <p className="text-xs text-slate-600 dark:text-slate-300 mt-0.5">
                Negotiated merchant fee structures per payment rail. Rekon uses
                these rules to audit every transaction down to the paisa.
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={handleResetBenchmarks}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Reset to Industry Benchmarks</span>
              </button>
              <button
                onClick={() => setShowAddModal(true)}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-sky-600 hover:bg-sky-500 text-white transition shadow-xs"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Custom Rate</span>
              </button>
            </div>
          </div>

          {/* Rate Cards Grid / Cards */}
          {loadingCards ? (
            <div className="py-12 text-center text-xs text-slate-500">
              Loading active rate cards...
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {rateCards.map((card) => {
                const pct = (Number(card.percentage_rate) * 100).toFixed(2);
                const flat = Number(card.flat_fee).toFixed(2);
                const gst = (Number(card.gst_rate) * 100).toFixed(0);

                return (
                  <div
                    key={card.id}
                    className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs flex flex-col justify-between hover:border-slate-300 dark:hover:border-slate-700 transition"
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold uppercase bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          {card.payment_method}
                        </span>
                        <div className="flex items-center space-x-1">
                          <button
                            onClick={() => {
                              setEditingCard(card);
                              setEditForm({
                                percentage_rate: String(card.percentage_rate),
                                flat_fee: String(card.flat_fee),
                                gst_rate: String(card.gst_rate),
                                cap_max_fee: card.cap_max_fee
                                  ? String(card.cap_max_fee)
                                  : "",
                                notes: card.notes || "",
                              });
                            }}
                            className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-white rounded-lg transition"
                            title="Edit Rate Rule"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleDeleteCard(card.id)}
                            className="p-1 text-slate-400 hover:text-rose-500 rounded-lg transition"
                            title="Delete Rule"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      <div className="text-base font-bold text-slate-900 dark:text-white mt-2 capitalize">
                        {card.payment_method === "card"
                          ? `${card.card_network} Card`
                          : card.payment_method}
                        {card.is_international && (
                          <span className="ml-1.5 text-[10px] font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 px-1.5 py-0.5 rounded">
                            International
                          </span>
                        )}
                      </div>

                      <div className="mt-3 space-y-1.5 text-xs text-slate-600 dark:text-slate-400">
                        <div className="flex items-center justify-between">
                          <span>Contracted MDR:</span>
                          <span className="font-semibold text-slate-900 dark:text-white">
                            {card.rate_type === "percentage"
                              ? `${pct}%`
                              : card.rate_type === "flat"
                              ? `₹${flat} flat`
                              : `${pct}% + ₹${flat}`}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span>GST Applicability:</span>
                          <span className="font-semibold text-slate-900 dark:text-white">
                            +{gst}% GST
                          </span>
                        </div>
                        {card.cap_max_fee && (
                          <div className="flex items-center justify-between text-amber-600 dark:text-amber-400 font-medium">
                            <span>RBI Regulatory Cap:</span>
                            <span>
                              Max ₹{Number(card.cap_max_fee).toFixed(2)}
                            </span>
                          </div>
                        )}
                      </div>

                      {card.notes && (
                        <p className="mt-3 text-[11px] text-slate-600 dark:text-slate-300 italic bg-slate-50 dark:bg-slate-800/50 p-2 rounded-lg">
                          "{card.notes}"
                        </p>
                      )}
                    </div>

                    <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[10px] text-slate-600 dark:text-slate-300">
                      <span>Tenant-Specific Rule</span>
                      <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                        Active in Engine
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: MDR & GST CALCULATOR SANDBOX */}
      {activeSubTab === "calculator" && (
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-xs space-y-6">
          <div>
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">
              Interactive MDR & 18% GST Fee Calculator
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-300 mt-0.5">
              Simulate customer checkout amounts to see the exact breakdown of
              merchant discount rates, RBI caps, and net bank settlements.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Input Controls */}
            <div className="space-y-4 bg-slate-50 dark:bg-slate-800/40 p-5 rounded-2xl border border-slate-200 dark:border-slate-800">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Customer Invoice / Gross Amount (INR)
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-xs text-slate-400">
                    ₹
                  </span>
                  <input
                    type="number"
                    min="1"
                    step="100"
                    value={calcGross}
                    onChange={(e) => setCalcGross(Number(e.target.value))}
                    className="w-full pl-7 pr-3 py-2 text-sm bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-sky-500 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Applicable Payment Method & Rail
                </label>
                <select
                  value={calcSelectedCardId}
                  onChange={(e) => setCalcSelectedCardId(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-sky-500"
                >
                  {rateCards.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.gateway.toUpperCase()} •{" "}
                      {c.payment_method.toUpperCase()} ({c.card_network}) -{" "}
                      {c.rate_type === "percentage"
                        ? `${(Number(c.percentage_rate) * 100).toFixed(2)}%`
                        : `₹${Number(c.flat_fee).toFixed(2)}`}
                    </option>
                  ))}
                </select>
              </div>

              {/* Preset quick buttons */}
              <div>
                <span className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider block mb-1.5">
                  Quick Presets
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {[1000, 5000, 15000, 50000, 120000].map((amt) => (
                    <button
                      key={amt}
                      onClick={() => setCalcGross(amt)}
                      className={`px-2.5 py-1 text-[11px] rounded-lg border font-mono transition ${
                        calcGross === amt
                          ? "bg-sky-600 text-white border-sky-600"
                          : "bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:bg-slate-100"
                      }`}
                    >
                      ₹{amt.toLocaleString("en-IN")}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Live Calculation Output Card */}
            <div className="bg-slate-900 text-white p-6 rounded-2xl flex flex-col justify-between shadow-md">
              <div>
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <span className="text-xs font-semibold text-slate-400">
                    Net Settlement Breakdown
                  </span>
                  <span className="text-xs font-mono text-sky-400">
                    Take Rate:{" "}
                    {loadingCalc
                      ? "..."
                      : calcResult
                      ? Number(calcResult.effective_take_rate_pct).toFixed(2)
                      : "0.00"}
                    %
                  </span>
                </div>

                <div className="mt-4 space-y-2.5 text-xs">
                  <div className="flex items-center justify-between text-slate-300">
                    <span>Gross Invoice Collected:</span>
                    <span className="font-mono text-white text-sm">
                      ₹
                      {calcGross.toLocaleString("en-IN", {
                        minimumFractionDigits: 2,
                      })}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-rose-300">
                    <span>Contracted Gateway MDR Fee:</span>
                    <span className="font-mono text-sm">
                      - ₹
                      {calcResult
                        ? Number(calcResult.expected_fee).toFixed(2)
                        : "0.00"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-rose-300">
                    <span>18% Statutory GST on Fee:</span>
                    <span className="font-mono text-sm">
                      - ₹
                      {calcResult
                        ? Number(calcResult.expected_gst).toFixed(2)
                        : "0.00"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-slate-400 text-[11px] pt-1">
                    <span>Total Gateway Deductions:</span>
                    <span className="font-mono">
                      - ₹
                      {calcResult
                        ? Number(calcResult.expected_total_deduction).toFixed(2)
                        : "0.00"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-800 flex items-center justify-between">
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
                    Net Cash Landing in Bank
                  </div>
                  <div className="text-2xl font-bold font-mono text-emerald-400 mt-0.5">
                    ₹
                    {calcResult
                      ? Number(calcResult.expected_net_amount).toLocaleString(
                          "en-IN",
                          {minimumFractionDigits: 2}
                        )
                      : "0.00"}
                  </div>
                </div>
                <div className="p-2 bg-emerald-950/80 text-emerald-400 rounded-xl border border-emerald-800/50">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ROOT-CAUSE INVESTIGATION MODAL */}
      {selectedDisputeItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-2.5">
                <span
                  className={`p-2 rounded-xl ${
                    selectedDisputeItem.audit_status === "overcharged"
                      ? "bg-rose-100 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400"
                      : "bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400"
                  }`}
                >
                  <ShieldAlert className="w-5 h-5" />
                </span>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                    Audit Investigation Details
                  </h3>
                  <p className="text-xs text-slate-600 dark:text-slate-300 font-mono">
                    {selectedDisputeItem.txn_id}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedDisputeItem(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-white p-1 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Explanation box */}
            <div className="p-3.5 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/40 rounded-xl text-xs text-rose-800 dark:text-rose-300 leading-relaxed">
              <div className="font-semibold text-rose-900 dark:text-rose-200 mb-1">
                Root-Cause Explanation:
              </div>
              {selectedDisputeItem.explanation}
            </div>

            {/* Side-by-side comparison */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="bg-slate-50 dark:bg-slate-800/50 p-3 rounded-xl border border-slate-200 dark:border-slate-800 space-y-1.5">
                <div className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 uppercase">
                  Contracted / Expected
                </div>
                <div className="flex justify-between text-slate-700 dark:text-slate-300">
                  <span>MDR Fee:</span>
                  <span className="font-medium">
                    ₹{selectedDisputeItem.expected_fee.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between text-slate-700 dark:text-slate-300">
                  <span>18% GST:</span>
                  <span className="font-medium">
                    ₹{selectedDisputeItem.expected_gst.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between font-bold text-slate-900 dark:text-white pt-1 border-t border-slate-200 dark:border-slate-700">
                  <span>Total Deduct:</span>
                  <span>
                    ₹{selectedDisputeItem.expected_total_deduction.toFixed(2)}
                  </span>
                </div>
              </div>

              <div className="bg-slate-50 dark:bg-slate-800/50 p-3 rounded-xl border border-slate-200 dark:border-slate-800 space-y-1.5">
                <div className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 uppercase">
                  Gateway Deducted
                </div>
                <div className="flex justify-between text-slate-700 dark:text-slate-300">
                  <span>Actual Fee:</span>
                  <span className="font-medium">
                    ₹{selectedDisputeItem.actual_fee.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between text-slate-700 dark:text-slate-300">
                  <span>Actual GST:</span>
                  <span className="font-medium">
                    ₹{selectedDisputeItem.actual_gst.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between font-bold text-slate-900 dark:text-white pt-1 border-t border-slate-200 dark:border-slate-700">
                  <span>Total Deduct:</span>
                  <span>
                    ₹{selectedDisputeItem.actual_total_deduction.toFixed(2)}
                  </span>
                </div>
              </div>
            </div>

            {/* Discrepancy Amount & Dispute action */}
            <div className="flex items-center justify-between p-3 bg-slate-100 dark:bg-slate-800 rounded-xl">
              <div>
                <span className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 uppercase">
                  Total Discrepancy Amount
                </span>
                <div className="text-base font-bold text-rose-600 dark:text-rose-400">
                  ₹{selectedDisputeItem.total_overcharge.toFixed(2)}
                </div>
              </div>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(
                    `Transaction ID: ${
                      selectedDisputeItem.txn_id
                    }\nDiscrepancy: ₹${selectedDisputeItem.total_overcharge.toFixed(
                      2
                    )}\nRoot Cause: ${selectedDisputeItem.explanation}`
                  );
                  showToast("Dispute details copied to clipboard!");
                }}
                className="px-3 py-1.5 bg-slate-900 dark:bg-white text-white dark:text-slate-900 rounded-xl text-xs font-medium hover:opacity-90 transition"
              >
                Copy for Ticket
              </button>
            </div>
          </div>
        </div>
      )}

      {/* EDIT RATE CARD MODAL */}
      {editingCard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Edit Rate Rule: {editingCard.payment_method.toUpperCase()} (
                {editingCard.card_network})
              </h3>
              <button
                onClick={() => setEditingCard(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  MDR Percentage (e.g. 0.0200 = 2.0%)
                </label>
                <input
                  type="number"
                  step="0.0001"
                  value={editForm.percentage_rate}
                  onChange={(e) =>
                    setEditForm({...editForm, percentage_rate: e.target.value})
                  }
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-mono"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Flat Fee per Txn (INR)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={editForm.flat_fee}
                  onChange={(e) =>
                    setEditForm({...editForm, flat_fee: e.target.value})
                  }
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-mono"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  GST Rate (Default 0.1800 = 18%)
                </label>
                <input
                  type="number"
                  step="0.0001"
                  value={editForm.gst_rate}
                  onChange={(e) =>
                    setEditForm({...editForm, gst_rate: e.target.value})
                  }
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-mono"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Maximum Fee Cap (e.g. 20.00 for RBI debit card cap)
                </label>
                <input
                  type="number"
                  step="1"
                  placeholder="Optional ceiling cap"
                  value={editForm.cap_max_fee}
                  onChange={(e) =>
                    setEditForm({...editForm, cap_max_fee: e.target.value})
                  }
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-mono"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Commercial Contract Notes
                </label>
                <input
                  type="text"
                  placeholder="e.g. Negotiated enterprise tier with account executive"
                  value={editForm.notes}
                  onChange={(e) =>
                    setEditForm({...editForm, notes: e.target.value})
                  }
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2">
              <button
                onClick={() => setEditingCard(null)}
                className="px-3 py-1.5 rounded-xl text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveEdit}
                className="px-4 py-1.5 rounded-xl text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white shadow-xs"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ADD CUSTOM RATE CARD MODAL */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Add Custom Negotiated Rate Rule
              </h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Gateway
                  </label>
                  <select
                    value={newCardForm.gateway}
                    onChange={(e) =>
                      setNewCardForm({...newCardForm, gateway: e.target.value})
                    }
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                  >
                    <option value="razorpay">Razorpay</option>
                    <option value="stripe">Stripe</option>
                  </select>
                </div>
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Payment Method
                  </label>
                  <select
                    value={newCardForm.payment_method}
                    onChange={(e) =>
                      setNewCardForm({
                        ...newCardForm,
                        payment_method: e.target.value,
                      })
                    }
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                  >
                    <option value="card">Card</option>
                    <option value="upi">UPI</option>
                    <option value="enach">eNACH</option>
                    <option value="netbanking">Netbanking</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Card Rail / Network
                  </label>
                  <input
                    type="text"
                    value={newCardForm.card_network}
                    onChange={(e) =>
                      setNewCardForm({
                        ...newCardForm,
                        card_network: e.target.value,
                      })
                    }
                    placeholder="e.g. credit, debit, amex, all"
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Rate Type
                  </label>
                  <select
                    value={newCardForm.rate_type}
                    onChange={(e) =>
                      setNewCardForm({
                        ...newCardForm,
                        rate_type: e.target.value,
                      })
                    }
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                  >
                    <option value="percentage">Percentage (MDR)</option>
                    <option value="flat">Flat Fee</option>
                    <option value="hybrid">Hybrid</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Percentage (0.0200 = 2%)
                  </label>
                  <input
                    type="number"
                    step="0.0001"
                    value={newCardForm.percentage_rate}
                    onChange={(e) =>
                      setNewCardForm({
                        ...newCardForm,
                        percentage_rate: e.target.value,
                      })
                    }
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-mono"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Flat Fee (INR)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={newCardForm.flat_fee}
                    onChange={(e) =>
                      setNewCardForm({...newCardForm, flat_fee: e.target.value})
                    }
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Cap Max Fee (Optional)
                </label>
                <input
                  type="number"
                  placeholder="e.g. 20.00"
                  value={newCardForm.cap_max_fee}
                  onChange={(e) =>
                    setNewCardForm({
                      ...newCardForm,
                      cap_max_fee: e.target.value,
                    })
                  }
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-mono"
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2">
              <button
                onClick={() => setShowAddModal(false)}
                className="px-3 py-1.5 rounded-xl text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateRateCard}
                className="px-4 py-1.5 rounded-xl text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white shadow-xs"
              >
                Create Rule
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
