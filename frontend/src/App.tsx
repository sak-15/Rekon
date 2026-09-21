import {useEffect, useState} from "react";
import {
  CheckCircle2,
  Activity,
  Server,
  Database,
  Layout,
  RefreshCw,
  Layers,
} from "lucide-react";

interface HealthStatus {
  status: string;
  service: string;
  environment: string;
  version: string;
}

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const checkHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/health");
      if (!res.ok) {
        throw new Error(`HTTP error ${res.status}`);
      }
      const data = await res.json();
      setHealth(data);
    } catch (err: any) {
      setError(err.message || "Unable to connect to backend");
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-emerald-500 selection:text-white">
      {/* Top Navigation */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="h-9 w-9 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-lg">
              R
            </div>
            <div>
              <span className="font-semibold text-lg tracking-tight">
                Rekon
              </span>
              <span className="ml-2 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full font-mono">
                v0.1.0 • Step 1.1
              </span>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <button
              onClick={checkHealth}
              disabled={loading}
              className="inline-flex items-center space-x-2 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 px-3 py-1.5 rounded-md transition disabled:opacity-50"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`}
              />
              <span>Ping Backend</span>
            </button>
            <div className="flex items-center space-x-2 text-xs text-slate-400 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-md">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>Dev Environment</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-10 space-y-10">
        {/* Hero Section */}
        <div className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
            SaaS Payment & Settlement Reconciliation Engine
          </h1>
          <p className="text-slate-400 text-base max-w-3xl leading-relaxed">
            Automating the three-layer reconciliation loop across{" "}
            <span className="text-slate-200 font-medium">
              Subscription Invoices
            </span>
            ,{" "}
            <span className="text-slate-200 font-medium">Payment Gateways</span>{" "}
            (Razorpay, Stripe), and{" "}
            <span className="text-slate-200 font-medium">Bank Settlements</span>{" "}
            with multi-tenant isolation and fee audibility.
          </p>
        </div>

        {/* System Health / Component Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Frontend Card */}
          <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div className="p-2 bg-blue-500/10 text-blue-400 rounded-lg">
                <Layout className="w-5 h-5" />
              </div>
              <span className="flex items-center text-xs text-emerald-400 font-medium bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                <CheckCircle2 className="w-3 h-3 mr-1" /> Ready
              </span>
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">
                Frontend UI
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                React 18 + Vite + TypeScript + Tailwind CSS
              </p>
            </div>
            <div className="pt-2 border-t border-slate-800 text-xs font-mono text-slate-400">
              Port: 5173 • Host: localhost
            </div>
          </div>

          {/* Backend Card */}
          <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div className="p-2 bg-emerald-500/10 text-emerald-400 rounded-lg">
                <Server className="w-5 h-5" />
              </div>
              {health ? (
                <span className="flex items-center text-xs text-emerald-400 font-medium bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                  <CheckCircle2 className="w-3 h-3 mr-1" /> Connected
                </span>
              ) : error ? (
                <span className="flex items-center text-xs text-amber-400 font-medium bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
                  Offline / Pending
                </span>
              ) : (
                <span className="flex items-center text-xs text-slate-400 font-medium bg-slate-800 px-2 py-0.5 rounded-full">
                  Checking...
                </span>
              )}
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">
                Backend API
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                FastAPI + Python 3.12 (Pydantic v2)
              </p>
            </div>
            <div className="pt-2 border-t border-slate-800 text-xs font-mono text-slate-400">
              {health ? (
                <span className="text-emerald-400 font-sans">
                  Status: {health.status} ({health.environment})
                </span>
              ) : (
                <span>Endpoint: http://localhost:8000/health</span>
              )}
            </div>
          </div>

          {/* Database Card */}
          <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div className="p-2 bg-purple-500/10 text-purple-400 rounded-lg">
                <Database className="w-5 h-5" />
              </div>
              <span className="flex items-center text-xs text-purple-300 font-medium bg-purple-500/10 border border-purple-500/20 px-2 py-0.5 rounded-full">
                PostgreSQL 16
              </span>
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">
                Multi-tenant DB
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                ACID transactions, org-level isolation
              </p>
            </div>
            <div className="pt-2 border-t border-slate-800 text-xs font-mono text-slate-400">
              Port: 5432 • Schema ready for Step 1.2
            </div>
          </div>
        </div>

        {/* Conceptual Reconciliation Pipeline Visualizer */}
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white flex items-center space-x-2">
                <Layers className="w-5 h-5 text-emerald-400" />
                <span>The Three-Layer Reconciliation Pipeline</span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                How money and verification signals flow through Rekon
              </p>
            </div>
            <span className="text-xs text-slate-400 bg-slate-800 px-2.5 py-1 rounded">
              Architecture Overview
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 relative">
            {/* Step 1 */}
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-2">
              <div className="text-xs font-mono text-emerald-400">
                Layer 1: Input
              </div>
              <div className="font-semibold text-white text-sm">
                Subscription System
              </div>
              <p className="text-xs text-slate-400">
                Chargebee / Zoho invoices, plans, proration, due dates.
              </p>
            </div>

            {/* Step 2 */}
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-2">
              <div className="text-xs font-mono text-emerald-400">
                Layer 1 ↔ 2: Gateway
              </div>
              <div className="font-semibold text-white text-sm">
                Gateway Transactions
              </div>
              <p className="text-xs text-slate-400">
                Razorpay & Stripe charges, MDR fees, GST, UPI/Card/eNACH.
              </p>
            </div>

            {/* Step 3 */}
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-2">
              <div className="text-xs font-mono text-emerald-400">
                Layer 2 ↔ 3: Settlement
              </div>
              <div className="font-semibold text-white text-sm">
                Settlement Batches
              </div>
              <p className="text-xs text-slate-400">
                T+n batch payouts, net deduplication, adjustments, refunds.
              </p>
            </div>

            {/* Step 4 */}
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-2">
              <div className="text-xs font-mono text-emerald-400">
                Layer 3: Cash
              </div>
              <div className="font-semibold text-white text-sm">
                Bank Statement Credits
              </div>
              <p className="text-xs text-slate-400">
                Verified cash deposit in bank, UTR numbers, zero variance.
              </p>
            </div>
          </div>
        </div>

        {/* Phase 1 Roadmap Progress Tracker */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-4">
          <h2 className="text-base font-semibold text-white flex items-center space-x-2">
            <Activity className="w-4 h-4 text-emerald-400" />
            <span>Phase 1 Progress Tracker</span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 text-xs">
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg space-y-1">
              <div className="flex items-center text-emerald-400 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Step 1.1 Active
              </div>
              <div className="text-slate-300 font-semibold">
                Project Scaffold
              </div>
              <div className="text-slate-400 text-[11px]">
                Docker, FastAPI, React, DB config
              </div>
            </div>

            <div className="p-3 bg-slate-900 border border-slate-800 rounded-lg space-y-1 opacity-75">
              <div className="text-slate-400 font-medium">Next: Step 1.2</div>
              <div className="text-slate-300 font-semibold">DB Schema v1</div>
              <div className="text-slate-400 text-[11px]">
                Alembic & Multi-tenant models
              </div>
            </div>

            <div className="p-3 bg-slate-900 border border-slate-800 rounded-lg space-y-1 opacity-75">
              <div className="text-slate-400 font-medium">
                Upcoming: Step 1.3
              </div>
              <div className="text-slate-300 font-semibold">
                Auth & Org Isolation
              </div>
              <div className="text-slate-400 text-[11px]">
                JWT, Register, Login API
              </div>
            </div>

            <div className="p-3 bg-slate-900 border border-slate-800 rounded-lg space-y-1 opacity-75">
              <div className="text-slate-400 font-medium">
                Upcoming: Step 1.4
              </div>
              <div className="text-slate-300 font-semibold">CSV Upload API</div>
              <div className="text-slate-400 text-[11px]">
                Razorpay, Stripe, Chargebee
              </div>
            </div>

            <div className="p-3 bg-slate-900 border border-slate-800 rounded-lg space-y-1 opacity-75">
              <div className="text-slate-400 font-medium">
                Upcoming: Step 1.5
              </div>
              <div className="text-slate-300 font-semibold">
                Upload & Table UI
              </div>
              <div className="text-slate-400 text-[11px]">
                Interactive CSV validation
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-500">
        Rekon SaaS Reconciliation Engine • Built with best practices & verified
        incrementally.
      </footer>
    </div>
  );
}
