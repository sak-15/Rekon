import React from 'react';

interface RecordTableProps {
  category: 'invoices' | 'gateway-txns' | 'settlements' | 'bank-credits';
  records: any[];
  loading: boolean;
}

export const RecordTable: React.FC<RecordTableProps> = ({ category, records, loading }) => {
  if (loading) {
    return (
      <div className="p-8 text-center text-slate-500 text-xs font-mono">
        Loading records from database...
      </div>
    );
  }

  if (records.length === 0) {
    return (
      <div className="p-8 text-center bg-slate-900/40 rounded-xl border border-slate-800 text-slate-400 text-xs">
        No records ingested yet in this category. Upload a CSV or click "Load Sample Data".
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/50">
      <table className="w-full text-left text-xs">
        <thead className="bg-slate-900 text-slate-400 font-medium uppercase text-[10px] tracking-wider border-b border-slate-800">
          {category === 'invoices' && (
            <tr>
              <th className="px-4 py-3">Invoice No</th>
              <th className="px-4 py-3">Customer</th>
              <th className="px-4 py-3">Plan</th>
              <th className="px-4 py-3">Amount</th>
              <th className="px-4 py-3">Tax</th>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Reconciliation</th>
            </tr>
          )}

          {category === 'gateway-txns' && (
            <tr>
              <th className="px-4 py-3">Txn ID</th>
              <th className="px-4 py-3">Gateway</th>
              <th className="px-4 py-3">Rail</th>
              <th className="px-4 py-3">Invoice Ref</th>
              <th className="px-4 py-3">Gross</th>
              <th className="px-4 py-3">MDR Fee</th>
              <th className="px-4 py-3">GST (18%)</th>
              <th className="px-4 py-3">Net</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          )}

          {category === 'settlements' && (
            <tr>
              <th className="px-4 py-3">Batch ID</th>
              <th className="px-4 py-3">Gateway</th>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Gross</th>
              <th className="px-4 py-3">Total Fees</th>
              <th className="px-4 py-3">Total GST</th>
              <th className="px-4 py-3">Net Payout</th>
              <th className="px-4 py-3">UTR Reference</th>
            </tr>
          )}

          {category === 'bank-credits' && (
            <tr>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Bank</th>
              <th className="px-4 py-3">Narration</th>
              <th className="px-4 py-3">Reference / UTR</th>
              <th className="px-4 py-3">Credit (INR)</th>
              <th className="px-4 py-3">Reconciliation</th>
            </tr>
          )}
        </thead>

        <tbody className="divide-y divide-slate-800 text-slate-300 font-mono">
          {records.map((r, i) => (
            <tr key={i} className="hover:bg-slate-800/40 transition-colors">
              {category === 'invoices' && (
                <>
                  <td className="px-4 py-3 font-semibold text-white">{r.invoice_no}</td>
                  <td className="px-4 py-3 font-sans text-slate-300">
                    <div>{r.customer_name || r.customer_id}</div>
                  </td>
                  <td className="px-4 py-3 font-sans text-slate-400">{r.plan_name || '—'}</td>
                  <td className="px-4 py-3 font-semibold text-white">₹{Number(r.amount).toLocaleString('en-IN')}</td>
                  <td className="px-4 py-3 text-slate-400">₹{Number(r.tax_amount || 0).toLocaleString('en-IN')}</td>
                  <td className="px-4 py-3 text-slate-400">{r.invoice_date?.slice(0, 10)}</td>
                  <td className="px-4 py-3 font-sans">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      {r.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-sans">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400">
                      {r.reconciliation_status}
                    </span>
                  </td>
                </>
              )}

              {category === 'gateway-txns' && (
                <>
                  <td className="px-4 py-3 font-semibold text-white">{r.txn_id}</td>
                  <td className="px-4 py-3 font-sans">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20">
                      {r.gateway}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-sans">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-purple-500/10 text-purple-400 border border-purple-500/20 uppercase">
                      {r.payment_method}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{r.invoice_ref || '—'}</td>
                  <td className="px-4 py-3 font-semibold text-white">₹{Number(r.amount).toLocaleString('en-IN')}</td>
                  <td className="px-4 py-3 text-slate-400">₹{Number(r.gateway_fee).toFixed(2)}</td>
                  <td className="px-4 py-3 text-slate-400">₹{Number(r.gateway_fee_gst).toFixed(2)}</td>
                  <td className="px-4 py-3 font-semibold text-emerald-400">₹{Number(r.net_amount).toLocaleString('en-IN')}</td>
                  <td className="px-4 py-3 font-sans">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      {r.status}
                    </span>
                  </td>
                </>
              )}

              {category === 'settlements' && (
                <>
                  <td className="px-4 py-3 font-semibold text-white">{r.batch_id}</td>
                  <td className="px-4 py-3 font-sans">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20 uppercase">
                      {r.gateway}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{r.settlement_date?.slice(0, 10)}</td>
                  <td className="px-4 py-3 text-slate-300">₹{Number(r.gross_amount).toLocaleString('en-IN')}</td>
                  <td className="px-4 py-3 text-slate-400">₹{Number(r.total_fees).toFixed(2)}</td>
                  <td className="px-4 py-3 text-slate-400">₹{Number(r.total_gst).toFixed(2)}</td>
                  <td className="px-4 py-3 font-bold text-emerald-400">₹{Number(r.net_amount).toLocaleString('en-IN')}</td>
                  <td className="px-4 py-3 text-slate-400">{r.utr_number || '—'}</td>
                </>
              )}

              {category === 'bank-credits' && (
                <>
                  <td className="px-4 py-3 text-slate-400">{r.transaction_date?.slice(0, 10)}</td>
                  <td className="px-4 py-3 font-sans text-slate-400">{r.bank_name || 'Bank'}</td>
                  <td className="px-4 py-3 font-sans text-slate-200 max-w-xs truncate">{r.narration}</td>
                  <td className="px-4 py-3 text-slate-400">{r.reference_no || '—'}</td>
                  <td className="px-4 py-3 font-bold text-emerald-400">₹{Number(r.credit_amount).toLocaleString('en-IN')}</td>
                  <td className="px-4 py-3 font-sans">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400">
                      {r.reconciliation_status}
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
