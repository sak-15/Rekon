import React from 'react';
import { CheckCircle2, AlertTriangle, XCircle, Clock, FileSpreadsheet } from 'lucide-react';
import { UploadJob } from '../api/client';

interface UploadHistoryProps {
  jobs: UploadJob[];
  loading: boolean;
}

export const UploadHistory: React.FC<UploadHistoryProps> = ({ jobs, loading }) => {
  if (loading) {
    return (
      <div className="p-8 text-center text-slate-500 text-xs font-mono">
        Loading upload audit log...
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="p-8 text-center bg-slate-900/40 rounded-xl border border-slate-800 text-slate-400 text-xs">
        No CSV upload jobs recorded for this organisation yet.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/50">
      <table className="w-full text-left text-xs">
        <thead className="bg-slate-900 text-slate-400 font-medium uppercase text-[10px] tracking-wider border-b border-slate-800">
          <tr>
            <th className="px-4 py-3">Timestamp</th>
            <th className="px-4 py-3">File Category</th>
            <th className="px-4 py-3">Filename</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Total Rows</th>
            <th className="px-4 py-3">Valid Rows</th>
            <th className="px-4 py-3">Exceptions / Dups</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800 text-slate-300 font-mono">
          {jobs.map((job) => (
            <tr key={job.id} className="hover:bg-slate-800/40 transition-colors">
              <td className="px-4 py-3 text-slate-400">{job.created_at?.slice(0, 19).replace('T', ' ')}</td>
              <td className="px-4 py-3 font-sans">
                <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 border border-slate-700">
                  {job.file_type}
                </span>
              </td>
              <td className="px-4 py-3 font-sans text-white flex items-center space-x-1.5">
                <FileSpreadsheet className="w-3.5 h-3.5 text-slate-400" />
                <span>{job.filename}</span>
              </td>
              <td className="px-4 py-3 font-sans">
                {job.status === 'completed' && (
                  <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <CheckCircle2 className="w-3 h-3" />
                    <span>Completed</span>
                  </span>
                )}
                {job.status === 'partial_success' && (
                  <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    <AlertTriangle className="w-3 h-3" />
                    <span>Partial</span>
                  </span>
                )}
                {job.status === 'failed' && (
                  <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] bg-rose-500/10 text-rose-400 border border-rose-500/20">
                    <XCircle className="w-3 h-3" />
                    <span>Failed</span>
                  </span>
                )}
                {job.status === 'processing' && (
                  <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20">
                    <Clock className="w-3 h-3 animate-spin" />
                    <span>Processing</span>
                  </span>
                )}
              </td>
              <td className="px-4 py-3 text-slate-400">{job.total_rows}</td>
              <td className="px-4 py-3 font-bold text-emerald-400">{job.valid_rows}</td>
              <td className="px-4 py-3 text-amber-400">{job.error_rows}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
