import React from "react";

interface RecordTableProps {
  category: "invoices" | "gateway-txns" | "settlements" | "bank-credits";
  records: any[];
  loading: boolean;
}

export const RecordTable: React.FC<RecordTableProps> = ({
  category,
  records,
  loading,
}) => {
  if (loading) {
    return (
      <div className="p-12 text-center text-slate-500 dark:text-slate-400 text-xs font-mono">
        Loading records from database...
      </div>
    );
  }

  if (records.length === 0) {
    return (
      <div className="p-10 text-center bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 text-xs shadow-sm">
        No records ingested yet in this category. Upload a CSV or load sample
        data.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
      <table className="w-full text-left text-xs">
        <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 font-medium uppercase text-[10px] tracking-wider border-b border-slate-200 dark:border-slate-800">
          {category === "invoices" && (
            <tr>
              <th className="px-5 py-3">Invoice No</th>
              <th className="px-5 py-3">Customer</th>
              <th className="px-5 py-3">Plan</th>
              <th className="px-5 py-3">Amount</th>
              <th className="px-5 py-3">Tax</th>
              <th className="px-5 py-3">Date</th>
              <th className="px-5 py-3">Status</th>
              <th className="px-5 py-3">Reconciliation</th>
            </tr>
          )}

          {category === "gateway-txns" && (
            <tr>
              <th className="px-5 py-3">Txn ID</th>
              <th className="px-5 py-3">Gateway</th>
              <th className="px-5 py-3">Rail</th>
              <th className="px-5 py-3">Invoice Ref</th>
              <th className="px-5 py-3">Gross</th>
              <th className="px-5 py-3">MDR Fee</th>
              <th className="px-5 py-3">GST (18%)</th>
              <th className="px-5 py-3">Net</th>
              <th className="px-5 py-3">Status</th>
            </tr>
          )}

          {category === "settlements" && (
            <tr>
              <th className="px-5 py-3">Batch ID</th>
              <th className="px-5 py-3">Gateway</th>
              <th className="px-5 py-3">Date</th>
              <th className="px-5 py-3">Gross</th>
              <th className="px-5 py-3">Total Fees</th>
              <th className="px-5 py-3">Total GST</th>
              <th className="px-5 py-3">Net Payout</th>
              <th className="px-5 py-3">UTR Reference</th>
            </tr>
          )}

          {category === "bank-credits" && (
            <tr>
              <th className="px-5 py-3">Date</th>
              <th className="px-5 py-3">Bank</th>
              <th className="px-5 py-3">Narration</th>
              <th className="px-5 py-3">Reference / UTR</th>
              <th className="px-5 py-3">Credit (INR)</th>
              <th className="px-5 py-3">Reconciliation</th>
            </tr>
          )}
        </thead>

        <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-300 font-mono">
          {records.map((r, i) => (
            <tr
              key={i}
              className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors"
            >
              {category === "invoices" && (
                <>
                  <td className="px-5 py-3.5 font-semibold text-slate-900 dark:text-white">
                    {r.invoice_no}
                  </td>
                  <td className="px-5 py-3.5 font-sans text-slate-700 dark:text-slate-300">
                    <div>{r.customer_name || r.customer_id}</div>
                  </td>
                  <td className="px-5 py-3.5 font-sans text-slate-500 dark:text-slate-400">
                    {r.plan_name || "—"}
                  </td>
                  <td className="px-5 py-3.5 font-semibold text-slate-900 dark:text-white">
                    ₹{Number(r.amount).toLocaleString("en-IN")}
                  </td>
                  <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400">
                    ₹{Number(r.tax_amount || 0).toLocaleString("en-IN")}
                  </td>
                  <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400">
                    {r.invoice_date?.slice(0, 10)}
                  </td>
                  <td className="px-5 py-3.5 font-sans">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                      {r.status}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 font-sans">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                        r.reconciliation_status === "matched"
                          ? "bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800"
                          : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
                      }`}
                    >
                      {r.reconciliation_status || "unmatched"}
                    </span>
                  </td>
                </>
              )}

              {category === "gateway-txns" && (
                <>
                  <td className="px-5 py-3.5 font-semibold text-slate-900 dark:text-white">
                    {r.txn_id}
                  </td>
                  <td className="px-5 py-3.5 font-sans">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-sky-50 dark:bg-sky-950 text-sky-600 dark:text-sky-400 border border-sky-200 dark:border-sky-800 uppercase">
                      {r.gateway}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 font-sans">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-purple-50 dark:bg-purple-950 text-purple-600 dark:text-purple-400 border border-purple-200 dark:border-purple-800 uppercase">
                      {r.payment_method}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400">
                    {r.invoice_ref || "—"}
                  </td>
                  <td className="px-5 py-3.5 font-semibold text-slate-900 dark:text-white">
                    ₹{Number(r.amount).toLocaleString("en-IN")}
                  </td>
                  <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400">
                    ₹{Number(r.gateway_fee).toFixed(2)}
                  </td>
                  <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400">
                    ₹{Number(r.gateway_fee_gst).toFixed(2)}
                  </td>
                  <td className="px-5 py-3.5 font-semibold text-emerald-600 dark:text-emerald-400">
                    ₹{Number(r.net_amount).toLocaleString("en-IN")}
                  </td>
                  <td className="px-5 py-3.5 font-sans">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                      {r.status}
                    </span>
                  </td>
                </>
              )}

              {category === "settlements" && (
                <>
                  <td className="px-5 py-3.5 font-semibold text-slate-900 dark:text-white">
                    {r.batch_id}
                  </td>
                  <td className="px-5 py-3.5 font-sans">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-sky-50 dark:bg-sky-950 text-sky-600 dark:text-sky-400 border border-sky-200 dark:border-sky-800 uppercase">
                      {r.gateway}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400">
                    {r.settlement_date?.slice(0, 10)}
                  </td>
                  <td className="px-5 py-3.5 text-slate-700 dark:text-slate-300">
                    ₹{Number(r.gross_amount).toLocaleString("en-IN")}
                  </td>
                  <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400">
                    ₹{Number(r.total_fees).toFixed(2)}
                  </td>
                  <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400">
                    ₹{Number(r.total_gst).toFixed(2)}
                  </td>
                  <td className="px-5 py-3.5 font-bold text-emerald-600 dark:text-emerald-400">
                    ₹{Number(r.net_amount).toLocaleString("en-IN")}
                  </td>
                  <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400">
                    {r.utr_number || "—"}
                  </td>
                </>
              )}

              {category === "bank-credits" && (
                <>
                  <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400">
                    {r.transaction_date?.slice(0, 10)}
                  </td>
                  <td className="px-5 py-3.5 font-sans text-slate-500 dark:text-slate-400">
                    {r.bank_name || "Bank"}
                  </td>
                  <td className="px-5 py-3.5 font-sans text-slate-700 dark:text-slate-200 max-w-xs truncate">
                    {r.narration}
                  </td>
                  <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400 font-mono">
                    {r.reference_no || "—"}
                  </td>
                  <td className="px-5 py-3.5 font-bold text-emerald-600 dark:text-emerald-400">
                    ₹{Number(r.credit_amount).toLocaleString("en-IN")}
                  </td>
                  <td className="px-5 py-3.5 font-sans">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                        r.reconciliation_status === "matched"
                          ? "bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800"
                          : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
                      }`}
                    >
                      {r.reconciliation_status || "unmatched"}
                    </span>
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
