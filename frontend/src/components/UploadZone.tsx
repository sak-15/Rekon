import React, { useState, useRef } from 'react';
import { 
  UploadCloud, 
  FileText, 
  CheckCircle2, 
  AlertCircle, 
  ChevronDown, 
  ChevronUp, 
  Sparkles,
  RefreshCw 
} from 'lucide-react';
import { api, UploadResult } from '../api/client';

interface UploadZoneProps {
  title: string;
  description: string;
  endpoint: string;
  acceptedFormat: string;
  sampleCsv: string;
  sampleFilename: string;
  additionalParams?: Record<string, string>;
  onUploadSuccess: () => void;
}

export const UploadZone: React.FC<UploadZoneProps> = ({
  title,
  description,
  endpoint,
  acceptedFormat,
  sampleCsv,
  sampleFilename,
  additionalParams = {},
  onUploadSuccess,
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showErrorDetails, setShowErrorDetails] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.uploadCsv(endpoint, file, additionalParams);
      setResult(res);
      onUploadSuccess();
    } catch (err: any) {
      setError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(true);
  };

  const onDragLeave = () => {
    setDragActive(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleUpload(e.dataTransfer.files[0]);
    }
  };

  const handleSampleUpload = () => {
    const blob = new Blob([sampleCsv.trim()], { type: 'text/csv' });
    const file = new File([blob], sampleFilename, { type: 'text/csv' });
    handleUpload(file);
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
            <FileText className="w-5 h-5 text-emerald-400" />
            <span>{title}</span>
          </h3>
          <p className="text-xs text-slate-400 mt-1">{description}</p>
        </div>
        <button
          onClick={handleSampleUpload}
          disabled={uploading}
          className="inline-flex items-center space-x-1.5 text-xs font-medium bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-3 py-1.5 rounded-lg transition disabled:opacity-50 self-start sm:self-auto"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>Load Sample Data</span>
        </button>
      </div>

      {/* Drag & Drop Area */}
      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
          dragActive
            ? 'border-emerald-500 bg-emerald-500/5'
            : 'border-slate-800 hover:border-slate-700 bg-slate-950/50'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              handleUpload(e.target.files[0]);
            }
          }}
        />
        <div className="flex flex-col items-center space-y-3">
          <div className="p-3 bg-slate-800/80 text-emerald-400 rounded-full">
            {uploading ? (
              <RefreshCw className="w-6 h-6 animate-spin" />
            ) : (
              <UploadCloud className="w-6 h-6" />
            )}
          </div>
          <div>
            <span className="text-sm font-medium text-slate-200">
              {uploading ? 'Parsing and validating records...' : 'Drop your CSV file here, or browse'}
            </span>
            <p className="text-xs text-slate-500 mt-1">Accepted format: {acceptedFormat}</p>
          </div>
        </div>
      </div>

      {/* Upload Error Banner */}
      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-lg flex items-start space-x-3 text-rose-400 text-xs">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold">Upload Failed</div>
            <p className="mt-0.5 text-rose-300">{error}</p>
          </div>
        </div>
      )}

      {/* Upload Success Feedback Card */}
      {result && (
        <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-emerald-400 text-xs font-semibold">
              <CheckCircle2 className="w-4 h-4" />
              <span>{result.message}</span>
            </div>
            <span className={`text-[11px] font-mono px-2 py-0.5 rounded-full ${
              result.upload_job.status === 'completed'
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
            }`}>
              {result.upload_job.status}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-3 text-xs pt-2 border-t border-slate-800/60 font-mono">
            <div>
              <span className="text-slate-500 block">Total Rows</span>
              <span className="text-slate-200 font-semibold">{result.upload_job.total_rows}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Ingested Valid</span>
              <span className="text-emerald-400 font-semibold">{result.upload_job.valid_rows}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Exceptions / Duplicates</span>
              <span className="text-amber-400 font-semibold">{result.upload_job.error_rows}</span>
            </div>
          </div>

          {/* Expandable Error Log */}
          {result.upload_job.error_details && result.upload_job.error_details.length > 0 && (
            <div className="pt-2">
              <button
                onClick={() => setShowErrorDetails(!showErrorDetails)}
                className="text-xs text-slate-400 hover:text-slate-200 flex items-center space-x-1"
              >
                <span>Audit Details ({result.upload_job.error_details.length})</span>
                {showErrorDetails ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>
              {showErrorDetails && (
                <div className="mt-2 p-3 bg-slate-900 rounded border border-slate-800 max-h-40 overflow-y-auto text-xs space-y-1">
                  {result.upload_job.error_details.map((item, idx) => (
                    <div key={idx} className="text-slate-300 font-mono text-[11px] flex items-center justify-between">
                      <span className="text-amber-400">Row {item.row} [{item.field}]:</span>
                      <span className="text-slate-400">{item.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
