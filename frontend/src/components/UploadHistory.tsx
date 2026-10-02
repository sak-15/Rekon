import React from "react";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  FileSpreadsheet,
} from "lucide-react";
import {UploadJob} from "../api/client";

interface UploadHistoryProps {
  jobs: UploadJob[];
  loading: boolean;
}

export const UploadHistory: React.FC<UploadHistoryProps> = ({
  jobs,
  loading,
}) => {
  if (loading) {
    return (
      <div className="p-12 text-center text-slate-500 dark:text-slate-400 text-xs font-mono">
        Loading upload audit log...
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="p-10 text-center bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 text-xs shadow-sm">
        No CSV upload jobs recorded for this organisation yet.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
      <table className="w-full text-left text-xs">
        <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 font-medium uppercase text-[10px] tracking-wider border-b border-slate-200 dark:border-slate-800">
          <tr>
            <th className="px-5 py-3">Timestamp</th>
            <th className="px-5 py-3">File Category</th>
            <th className="px-5 py-3">Filename</th>
            <th className="px-5 py-3">Status</th>
            <th className="px-5 py-3">Total Rows</th>
            <th className="px-5 py-3">Valid Rows</th>
            <th className="px-5 py-3">Exceptions / Dups</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-300 font-mono">
          {jobs.map((job) => (
            <tr
              key={job.id}
              className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors"
            >
              <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400">
                {job.created_at?.slice(0, 19).replace("T", " ")}
              </td>
              <td className="px-5 py-3.5 font-sans">
                <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                  {job.file_type}
                </span>
              </td>
              <td className="px-5 py-3.5 font-sans text-slate-900 dark:text-white flex items-center space-x-2">
                <FileSpreadsheet className="w-4 h-4 text-sky-500" />
                <span className="font-medium">{job.filename}</span>
              </td>
              <td className="px-5 py-3.5 font-sans">
                {job.status === "completed" && (
                  <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                    <CheckCircle2 className="w-3 h-3" />
                    <span>Completed</span>
                  </span>
                )}
                {job.status === "partial_success" && (
                  <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-50 dark:bg-amber-950 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
                    <AlertTriangle className="w-3 h-3" />
                    <span>Partial</span>
                  </span>
                )}
                {job.status === "failed" && (
                  <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-rose-50 dark:bg-rose-950 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-800">
                    <XCircle className="w-3 h-3" />
                    <span>Failed</span>
                  </span>
                )}
                {job.status === "processing" && (
                  <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-sky-50 dark:bg-sky-950 text-sky-600 dark:text-sky-400 border border-sky-200 dark:border-sky-800">
                    <Clock className="w-3 h-3 animate-spin" />
                    <span>Processing</span>
                  </span>
                )}
              </td>
              <td className="px-5 py-3.5 text-slate-500 dark:text-slate-400">
                {job.total_rows}
              </td>
              <td className="px-5 py-3.5 font-bold text-emerald-600 dark:text-emerald-400">
                {job.valid_rows}
              </td>
              <td className="px-5 py-3.5 text-amber-600 dark:text-amber-400 font-medium">
                {job.error_rows}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
