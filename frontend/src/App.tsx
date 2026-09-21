import { useEffect, useState } from 'react';
import { 
  RefreshCw,
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
} from 'lucide-react';
import { api, UserInfo, OrgInfo, UploadJob } from './api/client';
import { UploadZone } from './components/UploadZone';
import { RecordTable } from './components/RecordTable';
import { UploadHistory } from './components/UploadHistory';
import { AuthModal } from './components/AuthModal';

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
  const [activeTab, setActiveTab] = useState<'overview' | 'upload' | 'records' | 'history'>('upload');
  const [uploadCategory, setUploadCategory] = useState<'invoices' | 'gateway' | 'settlements' | 'bank'>('invoices');
  const [recordCategory, setRecordCategory] = useState<'invoices' | 'gateway-txns' | 'settlements' | 'bank-credits'>('invoices');

  const [records, setRecords] = useState<any[]>([]);
  const [loadingRecords, setLoadingRecords] = useState(false);
  const [uploadJobs, setUploadJobs] = useState<UploadJob[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);

  // Load session on startup
  const refreshSession = async () => {
    try {
      const data = await api.getMe();
      setCurrentUser(data.user);
      setCurrentOrg(data.organisation);
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
      if (activeTab === 'records') {
        loadRecords(recordCategory);
      } else if (activeTab === 'history') {
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
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-emerald-500 selection:text-white">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="h-9 w-9 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-lg">
              R
            </div>
            <div>
              <span className="font-semibold text-lg tracking-tight">Rekon</span>
              <span className="ml-2 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full font-mono">
                Phase 1 Verified
              </span>
            </div>
          </div>

          {/* User Session & Tenant Status */}
          <div className="flex items-center space-x-3 text-xs">
            {currentOrg ? (
              <div className="flex items-center space-x-3">
                <div className="flex items-center space-x-2 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg">
                  <Building2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="font-medium text-white">{currentOrg.name}</span>
                  <span className="text-slate-500 font-mono text-[10px]">({currentOrg.slug})</span>
                  {currentUser && (
                    <span className="text-slate-400 font-sans text-[11px] border-l border-slate-800 pl-2">
                      {currentUser.email}
                    </span>
                  )}
                </div>
                <button
                  onClick={handleLogout}
                  className="p-1.5 text-slate-400 hover:text-rose-400 rounded-lg hover:bg-slate-900 transition"
                  title="Sign Out"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <button
                onClick={() => setAuthModalOpen(true)}
                className="inline-flex items-center space-x-1.5 bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold px-3 py-1.5 rounded-lg transition"
              >
                <LogIn className="w-3.5 h-3.5" />
                <span>Sign In / Demo Tenant</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Navigation Sub-bar */}
      <div className="border-b border-slate-800 bg-slate-900/30">
        <div className="max-w-6xl mx-auto px-6 flex space-x-1">
          <button
            onClick={() => setActiveTab('upload')}
            className={`px-4 py-3 text-xs font-medium border-b-2 flex items-center space-x-2 transition ${
              activeTab === 'upload'
                ? 'border-emerald-400 text-emerald-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <UploadCloud className="w-4 h-4" />
            <span>CSV Ingestion Hub</span>
          </button>

          <button
            onClick={() => setActiveTab('records')}
            className={`px-4 py-3 text-xs font-medium border-b-2 flex items-center space-x-2 transition ${
              activeTab === 'records'
                ? 'border-emerald-400 text-emerald-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <FileSpreadsheet className="w-4 h-4" />
            <span>Records Explorer</span>
          </button>

          <button
            onClick={() => setActiveTab('history')}
            className={`px-4 py-3 text-xs font-medium border-b-2 flex items-center space-x-2 transition ${
              activeTab === 'history'
                ? 'border-emerald-400 text-emerald-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <History className="w-4 h-4" />
            <span>Upload Audit Log</span>
          </button>

          <button
            onClick={() => setActiveTab('overview')}
            className={`px-4 py-3 text-xs font-medium border-b-2 flex items-center space-x-2 transition ${
              activeTab === 'overview'
                ? 'border-emerald-400 text-emerald-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>Architecture Overview</span>
          </button>
        </div>
      </div>

      {/* Main Content Body */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-8 space-y-8">
        {!currentOrg && (
          <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs text-emerald-300">
            <div className="flex items-center space-x-2">
              <Building2 className="w-4 h-4 flex-shrink-0 text-emerald-400" />
              <span>
                You are currently in guest mode. <strong>Sign in</strong> or click <strong>One-Click Demo Session</strong> to experience multi-tenant data isolation.
              </span>
            </div>
            <button
              onClick={() => setAuthModalOpen(true)}
              className="px-3 py-1.5 bg-emerald-500 text-slate-950 font-semibold rounded-lg hover:bg-emerald-400 transition"
            >
              Sign In
            </button>
          </div>
        )}

        {/* --- TAB 1: CSV INGESTION HUB --- */}
        {activeTab === 'upload' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-white">CSV Ingestion Hub</h2>
              <p className="text-xs text-slate-400 mt-1">
                Upload raw financial data from your billing engine, payment gateways, and bank accounts.
              </p>
            </div>

            {/* Category Sub-Navigation */}
            <div className="flex flex-wrap gap-2 text-xs">
              <button
                onClick={() => setUploadCategory('invoices')}
                className={`px-3 py-1.5 rounded-lg font-medium flex items-center space-x-2 transition ${
                  uploadCategory === 'invoices'
                    ? 'bg-slate-800 text-white border border-slate-700'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                }`}
              >
                <FileText className="w-3.5 h-3.5 text-blue-400" />
                <span>1. Subscription Invoices</span>
              </button>

              <button
                onClick={() => setUploadCategory('gateway')}
                className={`px-3 py-1.5 rounded-lg font-medium flex items-center space-x-2 transition ${
                  uploadCategory === 'gateway'
                    ? 'bg-slate-800 text-white border border-slate-700'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                }`}
              >
                <CreditCard className="w-3.5 h-3.5 text-purple-400" />
                <span>2. Gateway Charges (Razorpay / Stripe)</span>
              </button>

              <button
                onClick={() => setUploadCategory('settlements')}
                className={`px-3 py-1.5 rounded-lg font-medium flex items-center space-x-2 transition ${
                  uploadCategory === 'settlements'
                    ? 'bg-slate-800 text-white border border-slate-700'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                }`}
              >
                <FileSpreadsheet className="w-3.5 h-3.5 text-amber-400" />
                <span>3. Settlement Payouts</span>
              </button>

              <button
                onClick={() => setUploadCategory('bank')}
                className={`px-3 py-1.5 rounded-lg font-medium flex items-center space-x-2 transition ${
                  uploadCategory === 'bank'
                    ? 'bg-slate-800 text-white border border-slate-700'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                }`}
              >
                <Landmark className="w-3.5 h-3.5 text-emerald-400" />
                <span>4. Bank Statement Credits</span>
              </button>
            </div>

            {/* Active Category Upload Zone */}
            {uploadCategory === 'invoices' && (
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

            {uploadCategory === 'gateway' && (
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

            {uploadCategory === 'settlements' && (
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

            {uploadCategory === 'bank' && (
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

        {/* --- TAB 2: RECORDS EXPLORER --- */}
        {activeTab === 'records' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold text-white">Ingested Records Explorer</h2>
                <p className="text-xs text-slate-400 mt-1">
                  Inspect normalized records currently stored in your tenant database partition.
                </p>
              </div>

              <button
                onClick={() => loadRecords(recordCategory)}
                disabled={loadingRecords}
                className="inline-flex items-center space-x-1.5 text-xs bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 px-3 py-1.5 rounded-lg transition"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loadingRecords ? 'animate-spin' : ''}`} />
                <span>Refresh Data</span>
              </button>
            </div>

            {/* Sub-Tabs for Record Categories */}
            <div className="flex flex-wrap gap-2 text-xs">
              <button
                onClick={() => setRecordCategory('invoices')}
                className={`px-3 py-1.5 rounded-lg font-medium transition ${
                  recordCategory === 'invoices'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                }`}
              >
                Invoices ({recordCategory === 'invoices' ? records.length : '...'})
              </button>
              <button
                onClick={() => setRecordCategory('gateway-txns')}
                className={`px-3 py-1.5 rounded-lg font-medium transition ${
                  recordCategory === 'gateway-txns'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                }`}
              >
                Gateway Transactions
              </button>
              <button
                onClick={() => setRecordCategory('settlements')}
                className={`px-3 py-1.5 rounded-lg font-medium transition ${
                  recordCategory === 'settlements'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                }`}
              >
                Settlement Batches
              </button>
              <button
                onClick={() => setRecordCategory('bank-credits')}
                className={`px-3 py-1.5 rounded-lg font-medium transition ${
                  recordCategory === 'bank-credits'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                }`}
              >
                Bank Credits
              </button>
            </div>

            <RecordTable category={recordCategory} records={records} loading={loadingRecords} />
          </div>
        )}

        {/* --- TAB 3: UPLOAD AUDIT LOG --- */}
        {activeTab === 'history' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold text-white">Upload Job Audit Log</h2>
                <p className="text-xs text-slate-400 mt-1">
                  Full history of batch ingestion jobs, valid row counts, duplicate deduplications, and parsing diagnostics.
                </p>
              </div>
              <button
                onClick={loadUploadJobs}
                disabled={loadingJobs}
                className="inline-flex items-center space-x-1.5 text-xs bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 px-3 py-1.5 rounded-lg transition"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loadingJobs ? 'animate-spin' : ''}`} />
                <span>Refresh Log</span>
              </button>
            </div>

            <UploadHistory jobs={uploadJobs} loading={loadingJobs} />
          </div>
        )}

        {/* --- TAB 4: ARCHITECTURE OVERVIEW --- */}
        {activeTab === 'overview' && (
          <div className="space-y-8">
            <div className="space-y-3">
              <h2 className="text-xl font-bold text-white">The Three-Layer Reconciliation Pipeline</h2>
              <p className="text-xs text-slate-400 leading-relaxed max-w-3xl">
                Rekon guarantees financial correctness by linking subscription invoices to charges, charges to settlement payout batches, and batches to actual bank account deposits.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-2">
                <div className="text-xs font-mono text-blue-400">Layer 1: Input</div>
                <div className="font-semibold text-white text-sm">Subscription System</div>
                <p className="text-xs text-slate-400">Chargebee / Zoho invoices, plans, proration, due dates.</p>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-2">
                <div className="text-xs font-mono text-purple-400">Layer 1 ↔ 2: Gateway</div>
                <div className="font-semibold text-white text-sm">Gateway Transactions</div>
                <p className="text-xs text-slate-400">Razorpay & Stripe charges, MDR fees, GST, UPI/Card/eNACH.</p>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-2">
                <div className="text-xs font-mono text-amber-400">Layer 2 ↔ 3: Settlement</div>
                <div className="font-semibold text-white text-sm">Settlement Batches</div>
                <p className="text-xs text-slate-400">T+n batch payouts, net deduplication, adjustments, refunds.</p>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-2">
                <div className="text-xs font-mono text-emerald-400">Layer 3: Cash</div>
                <div className="font-semibold text-white text-sm">Bank Statement Credits</div>
                <p className="text-xs text-slate-400">Verified cash deposit in bank, UTR numbers, zero variance.</p>
              </div>
            </div>

            {/* Architecture Card Status */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-4">
              <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-300">Phase 1: Foundation</span>
                  <span className="text-xs text-emerald-400 font-mono">100% Complete</span>
                </div>
                <p className="text-xs text-slate-400">Scaffold, Database models, Multi-tenant Auth, Ingestion API & UI.</p>
              </div>

              <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-300">Phase 2: Next</span>
                  <span className="text-xs text-slate-500 font-mono">Upcoming</span>
                </div>
                <p className="text-xs text-slate-400">3-Layer matching engine, tolerance thresholds, reconciliation runs.</p>
              </div>

              <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-300">Phase 3: Fee Audit</span>
                  <span className="text-xs text-slate-500 font-mono">Upcoming</span>
                </div>
                <p className="text-xs text-slate-400">MDR rate card verification and 18% GST audit rules.</p>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Auth Modal */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onSuccess={(auth) => {
          setCurrentUser(auth.user);
          setCurrentOrg(auth.organisation);
        }}
      />

      {/* Footer */}
      <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-500">
        Rekon SaaS Payment & Settlement Reconciliation Engine • Phase 1 Complete
      </footer>
    </div>
  );
}
