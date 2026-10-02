import {useEffect, useState} from "react";
import {
  Sparkles,
  Layers,
  UploadCloud,
  FileSpreadsheet,
  History,
  Building2,
  LogIn,
  LogOut,
  CreditCard,
  Landmark,
  FileText,
  Sun,
  Moon,
  RefreshCw,
  Percent,
  ShieldAlert,
  LayoutDashboard,
} from "lucide-react";

import {api, UserInfo, OrgInfo, UploadJob} from "./api/client";
import {UploadZone} from "./components/UploadZone";
import {RecordTable} from "./components/RecordTable";
import {UploadHistory} from "./components/UploadHistory";
import {AuthModal} from "./components/AuthModal";
import {ReconciliationHub} from "./components/ReconciliationHub";
import {FeeAuditHub} from "./components/FeeAuditHub";
import {ExceptionsHub} from "./components/ExceptionsHub";
import {ExecutiveDashboard} from "./components/ExecutiveDashboard";

// Sample CSV templates for instant 1-click testing
const SAMPLE_INVOICES_CSV = `Invoice Number,Customer ID,Customer Name,Customer Email,Plan Name,Total,Tax Amount,Status,Invoice Date,Due Date
INV-2026-001,cust_101,Acme Corp,billing@acmecorp.in,Enterprise Annual,120000.00,21600.00,Paid,2026-05-01,2026-05-15
INV-2026-002,cust_102,Zeta Software,finance@zetasoft.io,Pro Monthly,15000.00,2700.00,Paid,2026-05-02,2026-05-16
INV-2026-003,cust_103,Nexus AI,admin@nexus.ai,Startup Annual,45000.00,8100.00,Paid,2026-05-03,2026-05-17
INV-2026-004,cust_104,CloudVibe,payments@cloudvibe.com,Pro Monthly,15000.00,2700.00,Paid,2026-05-04,2026-05-18
`;

const SAMPLE_RAZORPAY_TXNS_CSV = `payment_id,amount,status,method,fee,tax,created_at,email,contact,order_id
pay_Rzp001,120000.00,captured,upi,2400.00,432.00,2026-05-01 10:15:00,billing@acmecorp.in,9876543210,INV-2026-001
pay_Rzp002,15000.00,captured,card,300.00,54.00,2026-05-02 11:30:00,finance@zetasoft.io,9876543211,INV-2026-002
pay_Rzp003,45000.00,captured,enach,900.00,162.00,2026-05-03 14:00:00,admin@nexus.ai,9876543212,INV-2026-003
pay_Rzp004,15000.00,captured,upi,300.00,54.00,2026-05-04 16:45:00,payments@cloudvibe.com,9876543213,INV-2026-004
`;

const SAMPLE_SETTLEMENTS_CSV = `settlement_id,entity_id,amount,fee,tax,type,utr,date
setl_RzpBatch01,pay_Rzp001,120000.00,2400.00,432.00,payment,UTR_RZP_20260505_01,2026-05-05
setl_RzpBatch01,pay_Rzp002,15000.00,300.00,54.00,payment,UTR_RZP_20260505_01,2026-05-05
setl_RzpBatch02,pay_Rzp003,45000.00,900.00,162.00,payment,UTR_RZP_20260506_02,2026-05-06
setl_RzpBatch02,pay_Rzp004,15000.00,300.00,54.00,payment,UTR_RZP_20260506_02,2026-05-06
`;

const SAMPLE_BANK_CSV = `Transaction Date,Narration,Credit Amount,Debit Amount,Chq / Ref No
05/05/2026,CMS/RAZORPAY SETTLEMENT BATCH 01 / UTR_RZP_20260505_01,131814.00,0.00,UTR_RZP_20260505_01
06/05/2026,CMS/RAZORPAY SETTLEMENT BATCH 02 / UTR_RZP_20260506_02,58638.00,0.00,UTR_RZP_20260506_02
`;

export default function App() {
  const [currentUser, setCurrentUser] = useState<UserInfo | null>(null);
  const [currentOrg, setCurrentOrg] = useState<OrgInfo | null>(null);
  const [activeTab, setActiveTab] = useState<
    | "overview"
    | "reconcile"
    | "fee_audit"
    | "exceptions"
    | "upload"
    | "records"
    | "history"
    | "specs"
  >("overview");
  const [uploadCategory, setUploadCategory] = useState<
    "invoices" | "gateway" | "settlements" | "bank"
  >("invoices");
  const [recordCategory, setRecordCategory] = useState<
    "invoices" | "gateway-txns" | "settlements" | "bank-credits"
  >("invoices");

  const [records, setRecords] = useState<any[]>([]);
  const [loadingRecords, setLoadingRecords] = useState(false);
  const [uploadJobs, setUploadJobs] = useState<UploadJob[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [openExceptionsCount, setOpenExceptionsCount] = useState<number>(0);

  // Theme state: default to 'light'
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const saved = localStorage.getItem("rekon_theme");
    return saved === "dark" ? "dark" : "light";
  });

  useEffect(() => {
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
    localStorage.setItem("rekon_theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  };

  const refreshExceptionCount = async () => {
    try {
      const sum = await api.getExceptionSummary();
      setOpenExceptionsCount(sum.open_count);
    } catch {
      setOpenExceptionsCount(0);
    }
  };

  // Load session on startup
  const refreshSession = async () => {
    try {
      const data = await api.getMe();
      setCurrentUser(data.user);
      setCurrentOrg(data.organisation);
      refreshExceptionCount();
    } catch {
      setCurrentUser(null);
      setCurrentOrg(null);
    }
  };

  const loadRecords = async (category = recordCategory) => {
    setLoadingRecords(true);
    try {
      const data = await api.getRecords(category);
      setRecords(data.items);
    } catch {
      setRecords([]);
    } finally {
      setLoadingRecords(false);
    }
  };

  const loadUploadJobs = async () => {
    setLoadingJobs(true);
    try {
      const data = await api.listUploads();
      setUploadJobs(data.items);
    } catch {
      setUploadJobs([]);
    } finally {
      setLoadingJobs(false);
    }
  };

  useEffect(() => {
    refreshSession();
  }, []);

  useEffect(() => {
    if (currentOrg) {
      if (activeTab === "records") {
        loadRecords(recordCategory);
      } else if (activeTab === "history") {
        loadUploadJobs();
      }
    }
  }, [activeTab, recordCategory, currentOrg]);

  const handleLogout = () => {
    api.clearToken();
    setCurrentUser(null);
    setCurrentOrg(null);
  };

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-slate-950 text-slate-800 dark:text-slate-100 transition-colors duration-150">
      {/* 1. SIGNATURE DARK LEFT NAVIGATION RAIL (#0f172a / slate-900) */}
      <aside className="w-64 bg-slate-900 border-r border-slate-800 text-slate-300 flex flex-col flex-shrink-0 select-none">
        {/* Brand Header */}
        <div className="h-16 px-6 flex items-center space-x-3 border-b border-slate-800/80">
          <div className="w-8 h-8 rounded-xl bg-sky-600 text-white font-bold text-sm flex items-center justify-center shadow-md shadow-sky-600/30">
            R
          </div>
          <div>
            <div className="font-bold text-base tracking-tight text-white flex items-center space-x-1.5">
              <span>Rekon</span>
              <span className="text-[10px] font-semibold text-sky-400 bg-sky-950 px-1.5 py-0.5 rounded border border-sky-800/60">
                v2.0
              </span>
            </div>
            <div className="text-[10px] text-slate-400 -mt-0.5">
              Reconciliation Engine
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex-1 px-3 py-5 space-y-1 overflow-y-auto">
          <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Executive
          </div>

          {/* 0. Executive Overview */}
          <button
            onClick={() => setActiveTab("overview")}
            className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition ${
              activeTab === "overview"
                ? "bg-sky-600 text-white shadow-sm shadow-sky-500/20"
                : "text-slate-300 hover:text-white hover:bg-slate-800/60"
            }`}
          >
            <div className="flex items-center space-x-3">
              <LayoutDashboard className="w-4 h-4" />
              <span>Executive Overview</span>
            </div>
            <span
              className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${
                activeTab === "overview"
                  ? "bg-white/20 text-white"
                  : "bg-slate-800 text-slate-400"
              }`}
            >
              Cockpit
            </span>
          </button>

          <div className="pt-3 px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Core Engine
          </div>

          {/* 1. Reconciliation Hub */}
          <button
            onClick={() => setActiveTab("reconcile")}
            className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition ${
              activeTab === "reconcile"
                ? "bg-sky-600 text-white shadow-sm shadow-sky-500/20"
                : "text-slate-300 hover:text-white hover:bg-slate-800/60"
            }`}
          >
            <div className="flex items-center space-x-3">
              <Sparkles className="w-4 h-4" />
              <span>Reconciliation Hub</span>
            </div>
            <span
              className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${
                activeTab === "reconcile"
                  ? "bg-white/20 text-white"
                  : "bg-slate-800 text-slate-400"
              }`}
            >
              Active
            </span>
          </button>

          {/* 1b. Fee Audit & Rates */}
          <button
            onClick={() => setActiveTab("fee_audit")}
            className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition ${
              activeTab === "fee_audit"
                ? "bg-sky-600 text-white shadow-sm shadow-sky-500/20"
                : "text-slate-300 hover:text-white hover:bg-slate-800/60"
            }`}
          >
            <div className="flex items-center space-x-3">
              <Percent className="w-4 h-4" />
              <span>Fee Audit & Rates</span>
            </div>
            <span
              className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${
                activeTab === "fee_audit"
                  ? "bg-white/20 text-white"
                  : "bg-slate-800 text-slate-400"
              }`}
            >
              18% GST
            </span>
          </button>

          {/* 1c. Resolution Queue */}
          <button
            onClick={() => setActiveTab("exceptions")}
            className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition ${
              activeTab === "exceptions"
                ? "bg-sky-600 text-white shadow-sm shadow-sky-500/20"
                : "text-slate-300 hover:text-white hover:bg-slate-800/60"
            }`}
          >
            <div className="flex items-center space-x-3">
              <ShieldAlert className="w-4 h-4" />
              <span>Resolution Queue</span>
            </div>
            {openExceptionsCount > 0 ? (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-rose-500 text-white font-mono">
                {openExceptionsCount}
              </span>
            ) : (
              <span
                className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${
                  activeTab === "exceptions"
                    ? "bg-white/20 text-white"
                    : "bg-slate-800 text-slate-400"
                }`}
              >
                Queue
              </span>
            )}
          </button>

          {/* 2. CSV Ingestion Hub */}
          <button
            onClick={() => setActiveTab("upload")}
            className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition ${
              activeTab === "upload"
                ? "bg-sky-600 text-white shadow-sm shadow-sky-500/20"
                : "text-slate-300 hover:text-white hover:bg-slate-800/60"
            }`}
          >
            <div className="flex items-center space-x-3">
              <UploadCloud className="w-4 h-4" />
              <span>Data Ingestion</span>
            </div>
          </button>

          {/* 3. Records Explorer */}
          <button
            onClick={() => setActiveTab("records")}
            className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition ${
              activeTab === "records"
                ? "bg-sky-600 text-white shadow-sm shadow-sky-500/20"
                : "text-slate-300 hover:text-white hover:bg-slate-800/60"
            }`}
          >
            <div className="flex items-center space-x-3">
              <FileSpreadsheet className="w-4 h-4" />
              <span>Raw Records</span>
            </div>
          </button>

          {/* 4. Upload Audit Log */}
          <button
            onClick={() => setActiveTab("history")}
            className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition ${
              activeTab === "history"
                ? "bg-sky-600 text-white shadow-sm shadow-sky-500/20"
                : "text-slate-300 hover:text-white hover:bg-slate-800/60"
            }`}
          >
            <div className="flex items-center space-x-3">
              <History className="w-4 h-4" />
              <span>Upload Audit Log</span>
            </div>
          </button>

          <div className="pt-4 px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            System & Specs
          </div>

          {/* 5. Architecture Specs */}
          <button
            onClick={() => setActiveTab("specs")}
            className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition ${
              activeTab === "specs"
                ? "bg-sky-600 text-white shadow-sm shadow-sky-500/20"
                : "text-slate-300 hover:text-white hover:bg-slate-800/60"
            }`}
          >
            <div className="flex items-center space-x-3">
              <Layers className="w-4 h-4" />
              <span>Architecture Specs</span>
            </div>
          </button>
        </nav>

        {/* Tenant Profile Footer in Sidebar */}
        <div className="p-3 border-t border-slate-800 bg-slate-950/40">
          {currentOrg ? (
            <div className="p-2.5 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 truncate">
                  <Building2 className="w-4 h-4 text-sky-400 flex-shrink-0" />
                  <span className="font-semibold text-xs text-white truncate">
                    {currentOrg.name}
                  </span>
                </div>
                <button
                  onClick={handleLogout}
                  className="text-slate-400 hover:text-rose-400 p-1 rounded transition"
                  title="Sign Out"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
                <span>{currentOrg.currency || "INR"}</span>
                <span className="truncate max-w-[120px]">
                  {currentUser?.email}
                </span>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setAuthModalOpen(true)}
              className="w-full flex items-center justify-center space-x-2 py-2 px-3 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-semibold shadow-sm transition"
            >
              <LogIn className="w-3.5 h-3.5" />
              <span>Sign In / Demo</span>
            </button>
          )}
        </div>
      </aside>

      {/* 2. MAIN WORKSPACE CANVAS */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header Bar */}
        <header className="h-16 border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur sticky top-0 z-30 px-6 flex items-center justify-between transition-colors">
          {/* Breadcrumb / Page Title */}
          <div className="flex items-center space-x-2 text-xs">
            <span className="text-slate-400">Workspace</span>
            <span className="text-slate-300 dark:text-slate-600">/</span>
            <span className="font-semibold text-slate-800 dark:text-white capitalize">
              {activeTab === "overview"
                ? "Executive Overview"
                : activeTab === "reconcile"
                ? "Reconciliation Hub"
                : activeTab === "fee_audit"
                ? "Fee Audit & Rates"
                : activeTab === "exceptions"
                ? "Exception Resolution Queue"
                : activeTab === "upload"
                ? "Data Ingestion"
                : activeTab === "records"
                ? "Raw Records Explorer"
                : activeTab === "history"
                ? "Upload Audit Log"
                : "Architecture Specs"}
            </span>
          </div>

          {/* Right Header Actions */}
          <div className="flex items-center space-x-3">
            {/* Theme Toggle Button */}
            <button
              onClick={toggleTheme}
              className="p-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition shadow-sm"
              title={`Switch to ${theme === "light" ? "Dark" : "Light"} mode`}
            >
              {theme === "light" ? (
                <Moon className="w-4 h-4 text-slate-700" />
              ) : (
                <Sun className="w-4 h-4 text-amber-400" />
              )}
            </button>

            {/* Tenant status badge */}
            {currentOrg && (
              <div className="hidden sm:flex items-center space-x-2 px-3 py-1.5 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-xs font-medium text-slate-700 dark:text-slate-300">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>{currentOrg.name}</span>
                <span className="text-[10px] font-mono text-slate-400">
                  [{currentOrg.currency}]
                </span>
              </div>
            )}
          </div>
        </header>

        {/* Content Body */}
        <main className="flex-1 p-6 lg:p-8 space-y-6 overflow-y-auto">
          {/* Guest notification if unauthenticated */}
          {!currentOrg && (
            <div className="p-4 bg-sky-50 dark:bg-sky-950/40 border border-sky-200 dark:border-sky-800 rounded-2xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs text-sky-900 dark:text-sky-300">
              <div className="flex items-center space-x-2">
                <Building2 className="w-4 h-4 flex-shrink-0 text-sky-600 dark:text-sky-400" />
                <span>
                  You are currently in guest mode. <strong>Sign in</strong> or
                  click <strong>One-Click Demo Session</strong> to experience
                  multi-tenant reconciliation.
                </span>
              </div>
              <button
                onClick={() => setAuthModalOpen(true)}
                className="px-3.5 py-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold rounded-xl shadow-sm transition self-start sm:self-auto"
              >
                Sign In / Demo
              </button>
            </div>
          )}

          {/* --- TAB 0: FOUNDER EXECUTIVE DASHBOARD --- */}
          {activeTab === "overview" && (
            <ExecutiveDashboard
              onNavigate={(target) => {
                if (target === "fee-audit") setActiveTab("fee_audit");
                else if (target === "exceptions") setActiveTab("exceptions");
                else if (target === "reconcile") setActiveTab("reconcile");
                else if (target === "upload") setActiveTab("upload");
              }}
              orgName={currentOrg?.name}
            />
          )}

          {/* --- TAB 1: RECONCILIATION HUB --- */}
          {activeTab === "reconcile" && (
            <ReconciliationHub
              isAuthenticated={!!currentOrg}
              onOpenAuth={() => setAuthModalOpen(true)}
              onNavigateToExceptions={() => setActiveTab("exceptions")}
              onRunFinished={() => {
                loadRecords();
                loadUploadJobs();
                refreshExceptionCount();
              }}
            />
          )}

          {/* --- TAB 1b: MDR & 18% GST FEE AUDIT HUB --- */}
          {activeTab === "fee_audit" && (
            <FeeAuditHub
              onRefresh={() => {
                loadRecords();
              }}
            />
          )}

          {/* --- TAB 1c: EXCEPTION RESOLUTION QUEUE --- */}
          {activeTab === "exceptions" && (
            <ExceptionsHub
              onRefreshParent={() => {
                loadRecords();
                refreshExceptionCount();
              }}
            />
          )}

          {/* --- TAB 2: DATA INGESTION HUB --- */}
          {activeTab === "upload" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                  CSV Ingestion Hub
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  Upload raw financial data from your billing engine, payment
                  gateways, and bank accounts.
                </p>
              </div>

              {/* Category Sub-Navigation */}
              <div className="flex flex-wrap gap-2 text-xs">
                <button
                  onClick={() => setUploadCategory("invoices")}
                  className={`px-3 py-1.5 rounded-xl font-medium flex items-center space-x-2 transition ${
                    uploadCategory === "invoices"
                      ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-white border border-slate-200 dark:border-slate-700 shadow-sm"
                      : "bg-slate-100 dark:bg-slate-900 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
                  }`}
                >
                  <FileText className="w-3.5 h-3.5 text-sky-500" />
                  <span>1. Subscription Invoices</span>
                </button>

                <button
                  onClick={() => setUploadCategory("gateway")}
                  className={`px-3 py-1.5 rounded-xl font-medium flex items-center space-x-2 transition ${
                    uploadCategory === "gateway"
                      ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-white border border-slate-200 dark:border-slate-700 shadow-sm"
                      : "bg-slate-100 dark:bg-slate-900 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
                  }`}
                >
                  <CreditCard className="w-3.5 h-3.5 text-emerald-500" />
                  <span>2. Gateway Charges (Razorpay / Stripe)</span>
                </button>

                <button
                  onClick={() => setUploadCategory("settlements")}
                  className={`px-3 py-1.5 rounded-xl font-medium flex items-center space-x-2 transition ${
                    uploadCategory === "settlements"
                      ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-white border border-slate-200 dark:border-slate-700 shadow-sm"
                      : "bg-slate-100 dark:bg-slate-900 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
                  }`}
                >
                  <FileSpreadsheet className="w-3.5 h-3.5 text-purple-500" />
                  <span>3. Settlement Payouts</span>
                </button>

                <button
                  onClick={() => setUploadCategory("bank")}
                  className={`px-3 py-1.5 rounded-xl font-medium flex items-center space-x-2 transition ${
                    uploadCategory === "bank"
                      ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-white border border-slate-200 dark:border-slate-700 shadow-sm"
                      : "bg-slate-100 dark:bg-slate-900 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
                  }`}
                >
                  <Landmark className="w-3.5 h-3.5 text-teal-500" />
                  <span>4. Bank Statement Credits</span>
                </button>
              </div>

              {/* Active Category Upload Zone */}
              {uploadCategory === "invoices" && (
                <UploadZone
                  title="Subscription Invoices Ingestion"
                  description="Ingests customer plan billings from Chargebee, Zoho Subscriptions, or canonical CSV exports."
                  endpoint="/api/uploads/invoices"
                  acceptedFormat="Chargebee export (.csv)"
                  sampleCsv={SAMPLE_INVOICES_CSV}
                  sampleFilename="chargebee_invoices_sample.csv"
                  onUploadSuccess={() => {
                    loadUploadJobs();
                  }}
                />
              )}

              {uploadCategory === "gateway" && (
                <UploadZone
                  title="Gateway Transactions Ingestion"
                  description="Auto-detects Razorpay or Stripe transaction reports. Normalizes gross charges, MDR fees, and 18% GST."
                  endpoint="/api/uploads/gateway-txns"
                  acceptedFormat="Razorpay payments or Stripe charges (.csv)"
                  sampleCsv={SAMPLE_RAZORPAY_TXNS_CSV}
                  sampleFilename="razorpay_payments_sample.csv"
                  onUploadSuccess={() => {
                    loadUploadJobs();
                  }}
                />
              )}

              {uploadCategory === "settlements" && (
                <UploadZone
                  title="Settlement Payouts Ingestion"
                  description="Ingests payout batches with gross totals, deducted MDR, GST, refunds, and UTR reference codes."
                  endpoint="/api/uploads/settlements"
                  acceptedFormat="Gateway settlement report (.csv)"
                  sampleCsv={SAMPLE_SETTLEMENTS_CSV}
                  sampleFilename="settlement_batches_sample.csv"
                  onUploadSuccess={() => {
                    loadUploadJobs();
                  }}
                />
              )}

              {uploadCategory === "bank" && (
                <UploadZone
                  title="Bank Statement Credits Ingestion"
                  description="Ingests bank deposit lines, transaction dates, and UTR narrations from HDFC, ICICI, Axis, etc."
                  endpoint="/api/uploads/bank-statements"
                  acceptedFormat="Bank statement export (.csv)"
                  sampleCsv={SAMPLE_BANK_CSV}
                  sampleFilename="hdfc_bank_statement_sample.csv"
                  onUploadSuccess={() => {
                    loadUploadJobs();
                  }}
                />
              )}
            </div>
          )}

          {/* --- TAB 3: RECORDS EXPLORER --- */}
          {activeTab === "records" && (
            <div className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                    Ingested Records Explorer
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    Inspect normalized records currently stored in your tenant
                    database partition.
                  </p>
                </div>

                <button
                  onClick={() => loadRecords(recordCategory)}
                  disabled={loadingRecords}
                  className="inline-flex items-center space-x-1.5 text-xs bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 px-3.5 py-2 rounded-xl transition shadow-sm"
                >
                  <RefreshCw
                    className={`w-3.5 h-3.5 ${
                      loadingRecords ? "animate-spin" : ""
                    }`}
                  />
                  <span>Refresh Data</span>
                </button>
              </div>

              {/* Sub-Tabs for Record Categories */}
              <div className="flex flex-wrap gap-2 text-xs">
                <button
                  onClick={() => setRecordCategory("invoices")}
                  className={`px-3 py-1.5 rounded-xl font-medium transition ${
                    recordCategory === "invoices"
                      ? "bg-white dark:bg-slate-800 text-sky-600 dark:text-sky-400 border border-slate-200 dark:border-slate-700 shadow-sm"
                      : "bg-slate-100 dark:bg-slate-900 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
                  }`}
                >
                  Invoices (
                  {recordCategory === "invoices" ? records.length : "..."})
                </button>
                <button
                  onClick={() => setRecordCategory("gateway-txns")}
                  className={`px-3 py-1.5 rounded-xl font-medium transition ${
                    recordCategory === "gateway-txns"
                      ? "bg-white dark:bg-slate-800 text-sky-600 dark:text-sky-400 border border-slate-200 dark:border-slate-700 shadow-sm"
                      : "bg-slate-100 dark:bg-slate-900 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
                  }`}
                >
                  Gateway Transactions
                </button>
                <button
                  onClick={() => setRecordCategory("settlements")}
                  className={`px-3 py-1.5 rounded-xl font-medium transition ${
                    recordCategory === "settlements"
                      ? "bg-white dark:bg-slate-800 text-sky-600 dark:text-sky-400 border border-slate-200 dark:border-slate-700 shadow-sm"
                      : "bg-slate-100 dark:bg-slate-900 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
                  }`}
                >
                  Settlement Batches
                </button>
                <button
                  onClick={() => setRecordCategory("bank-credits")}
                  className={`px-3 py-1.5 rounded-xl font-medium transition ${
                    recordCategory === "bank-credits"
                      ? "bg-white dark:bg-slate-800 text-sky-600 dark:text-sky-400 border border-slate-200 dark:border-slate-700 shadow-sm"
                      : "bg-slate-100 dark:bg-slate-900 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
                  }`}
                >
                  Bank Credits
                </button>
              </div>

              <RecordTable
                category={recordCategory}
                records={records}
                loading={loadingRecords}
              />
            </div>
          )}

          {/* --- TAB 4: UPLOAD AUDIT LOG --- */}
          {activeTab === "history" && (
            <div className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                    Upload Job Audit Log
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    Full history of batch ingestion jobs, valid row counts,
                    duplicate deduplications, and parsing diagnostics.
                  </p>
                </div>
                <button
                  onClick={loadUploadJobs}
                  disabled={loadingJobs}
                  className="inline-flex items-center space-x-1.5 text-xs bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 px-3.5 py-2 rounded-xl transition shadow-sm"
                >
                  <RefreshCw
                    className={`w-3.5 h-3.5 ${
                      loadingJobs ? "animate-spin" : ""
                    }`}
                  />
                  <span>Refresh Log</span>
                </button>
              </div>

              <UploadHistory jobs={uploadJobs} loading={loadingJobs} />
            </div>
          )}

          {/* --- TAB 5: ARCHITECTURE SPECS --- */}
          {activeTab === "specs" && (
            <div className="space-y-8">
              <div className="space-y-2">
                <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                  The Three-Layer Reconciliation Pipeline
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed max-w-3xl">
                  Rekon guarantees financial correctness by linking subscription
                  invoices to charges, charges to settlement payout batches, and
                  batches to actual bank account deposits.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 space-y-2 shadow-sm">
                  <div className="text-xs font-mono text-sky-600 dark:text-sky-400 font-bold">
                    Layer 1: Input
                  </div>
                  <div className="font-semibold text-slate-900 dark:text-white text-sm">
                    Subscription Invoices
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Chargebee / Zoho invoices, plans, proration, due dates.
                  </p>
                </div>

                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 space-y-2 shadow-sm">
                  <div className="text-xs font-mono text-purple-600 dark:text-purple-400 font-bold">
                    Layer 1 ↔ 2: Gateway
                  </div>
                  <div className="font-semibold text-slate-900 dark:text-white text-sm">
                    Gateway Charges
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Razorpay & Stripe charges, MDR fees, GST, UPI/Card/eNACH.
                  </p>
                </div>

                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 space-y-2 shadow-sm">
                  <div className="text-xs font-mono text-purple-600 dark:text-purple-400 font-bold">
                    Layer 2 ↔ 3: Settlement
                  </div>
                  <div className="font-semibold text-slate-900 dark:text-white text-sm">
                    Settlement Batches
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    T+n batch payouts, net deduplication, adjustments, refunds.
                  </p>
                </div>

                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 space-y-2 shadow-sm">
                  <div className="text-xs font-mono text-teal-600 dark:text-teal-400 font-bold">
                    Layer 3: Cash
                  </div>
                  <div className="font-semibold text-slate-900 dark:text-white text-sm">
                    Bank Statement Credits
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Verified cash deposit in bank, UTR numbers, zero variance.
                  </p>
                </div>
              </div>

              {/* Status Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 space-y-2 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                      Phase 1: Ingestion & Auth
                    </span>
                    <span className="text-xs text-emerald-600 dark:text-emerald-400 font-mono font-bold">
                      100% Complete
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Multi-tenant data isolation, canonical normalization, CSV
                    parsers.
                  </p>
                </div>

                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 space-y-2 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                      Phase 2: Reconciliation
                    </span>
                    <span className="text-xs text-emerald-600 dark:text-emerald-400 font-mono font-bold">
                      100% Complete
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Three-layer matching engines, orchestrator, tolerance
                    configuration, dashboard.
                  </p>
                </div>

                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 space-y-2 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                      Phase 3: Fee Audit & Rates
                    </span>
                    <span className="text-xs text-emerald-600 dark:text-emerald-400 font-mono font-bold">
                      100% Complete
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    MDR rate cards, 18% GST audit rules, and claim CSV export.
                  </p>
                </div>

                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 space-y-2 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                      Phase 4: Resolution Queue
                    </span>
                    <span className="text-xs text-emerald-600 dark:text-emerald-400 font-mono font-bold">
                      100% Complete
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Auto-classification, 1-click write-offs, manual link &
                    dispute tickets.
                  </p>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Auth Modal */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onSuccess={(auth) => {
          setCurrentUser(auth.user);
          setCurrentOrg(auth.organisation);
        }}
      />
    </div>
  );
}
