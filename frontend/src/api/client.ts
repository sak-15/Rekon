/**
 * Centralized API Client for Rekon Frontend.
 * Automatically injects JWT Bearer tokens from localStorage.
 */

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface AuthTokens {
  access_token: string;
  token_type: string;
}

export interface UserInfo {
  id: string;
  org_id: string;
  email: string;
  full_name?: string;
  role: string;
  is_active: boolean;
}

export interface OrgInfo {
  id: string;
  name: string;
  slug: string;
  currency: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
  organisation: OrgInfo;
}

export interface UploadJob {
  id: string;
  org_id: string;
  file_type: string;
  filename: string;
  status: string;
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  error_details?: Array<{row: number; field: string; message: string}>;
  created_at: string;
}

export interface UploadResult {
  message: string;
  upload_job: UploadJob;
}

export interface ReconciliationRuleConfig {
  amount_tolerance?: string | number;
  layer_1_date_window_days?: number;
  layer_3_bank_window_days?: number;
  enable_fuzzy_matching?: boolean;
  min_fuzzy_confidence?: string | number;
}

export interface ReconciliationRun {
  id: string;
  org_id: string;
  status: "pending" | "running" | "completed" | "failed";
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  rule_config?: Record<string, any>;

  total_invoices: number;
  matched_invoices: number;
  unmatched_invoices: number;

  total_txns: number;
  matched_txns: number;
  unmatched_txns: number;

  total_settlements: number;
  matched_settlements: number;
  unmatched_settlements: number;

  total_bank_credits: number;
  matched_bank_credits: number;
  unmatched_bank_credits: number;

  invoiced_amount: string | number;
  collected_amount: string | number;
  settled_amount: string | number;
  bank_credited_amount: string | number;
  discrepancy_amount: string | number;

  created_at: string;
}

export interface ReconciliationMatch {
  id: string;
  run_id: string;
  org_id: string;
  layer: "layer_1" | "layer_2" | "layer_3";

  invoice_id?: string;
  gateway_txn_id?: string;
  settlement_line_id?: string;
  settlement_batch_id?: string;
  bank_credit_id?: string;

  match_type: "exact" | "fuzzy" | "manual";
  confidence_score: string | number;
  status: "matched" | "partial" | "discrepancy";
  amount_difference: string | number;
  match_details?: Record<string, any>;
  created_at: string;
}

class ApiClient {
  private getToken(): string | null {
    return localStorage.getItem("rekon_token");
  }

  public setToken(token: string) {
    localStorage.setItem("rekon_token", token);
  }

  public clearToken() {
    localStorage.removeItem("rekon_token");
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorData = await response
        .json()
        .catch(() => ({detail: response.statusText}));
      throw new Error(
        errorData.detail || `Request failed with status ${response.status}`
      );
    }

    return response.json();
  }

  // --- Auth Endpoints ---
  public async register(payload: {
    org_name: string;
    org_slug: string;
    email: string;
    password: string;
    full_name?: string;
    currency?: string;
  }): Promise<AuthResponse> {
    const data = await this.request<AuthResponse>("/api/auth/register", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    this.setToken(data.access_token);
    return data;
  }

  public async login(email: string, password: string): Promise<AuthResponse> {
    const data = await this.request<AuthResponse>("/api/auth/login", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({email, password}),
    });
    this.setToken(data.access_token);
    return data;
  }

  public async getMe(): Promise<{user: UserInfo; organisation: OrgInfo}> {
    return this.request<{user: UserInfo; organisation: OrgInfo}>(
      "/api/auth/me"
    );
  }

  // --- Upload Endpoints ---
  public async uploadCsv(
    endpoint: string,
    file: File,
    additionalParams: Record<string, string> = {}
  ): Promise<UploadResult> {
    const formData = new FormData();
    formData.append("file", file);

    const queryParams = new URLSearchParams(additionalParams).toString();
    const url = `${endpoint}${queryParams ? `?${queryParams}` : ""}`;

    return this.request<UploadResult>(url, {
      method: "POST",
      body: formData,
    });
  }

  // --- Upload Jobs Audit Endpoints ---
  public async listUploads(): Promise<{items: UploadJob[]; total: number}> {
    return this.request<{items: UploadJob[]; total: number}>("/api/uploads");
  }

  // --- Records Explorer Endpoints ---
  public async getRecords<T>(
    category: string,
    page = 1,
    pageSize = 20
  ): Promise<{items: T[]; total: number}> {
    return this.request<{items: T[]; total: number}>(
      `/api/records/${category}?page=${page}&page_size=${pageSize}`
    );
  }

  // --- Reconciliation Endpoints ---
  public async triggerReconciliation(
    ruleConfig?: ReconciliationRuleConfig
  ): Promise<ReconciliationRun> {
    return this.request<ReconciliationRun>("/api/reconcile", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(ruleConfig ? {rule_config: ruleConfig} : {}),
    });
  }

  public async listReconciliationRuns(
    limit = 20,
    offset = 0
  ): Promise<{items: ReconciliationRun[]; total: number}> {
    return this.request<{items: ReconciliationRun[]; total: number}>(
      `/api/reconcile?limit=${limit}&offset=${offset}`
    );
  }

  public async getReconciliationRun(runId: string): Promise<ReconciliationRun> {
    return this.request<ReconciliationRun>(`/api/reconcile/${runId}`);
  }

  public async getReconciliationMatches(
    runId: string,
    layer?: string,
    matchStatus?: string,
    limit = 50,
    offset = 0
  ): Promise<{
    items: ReconciliationMatch[];
    total: number;
    limit: number;
    offset: number;
  }> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });
    if (layer) params.append("layer", layer);
    if (matchStatus) params.append("status", matchStatus);

    return this.request<{
      items: ReconciliationMatch[];
      total: number;
      limit: number;
      offset: number;
    }>(`/api/reconcile/${runId}/matches?${params.toString()}`);
  }
  // --- Rate Cards Endpoints ---
  public async listRateCards(
    gateway?: string
  ): Promise<{items: RateCard[]; total: number}> {
    const q = gateway ? `?gateway=${gateway}` : "";
    return this.request<{items: RateCard[]; total: number}>(
      `/api/rate-cards${q}`
    );
  }

  public async createRateCard(payload: Partial<RateCard>): Promise<RateCard> {
    return this.request<RateCard>("/api/rate-cards", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
  }

  public async updateRateCard(
    id: string,
    payload: Partial<RateCard>
  ): Promise<RateCard> {
    return this.request<RateCard>(`/api/rate-cards/${id}`, {
      method: "PUT",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
  }

  public async deleteRateCard(id: string): Promise<void> {
    const token = this.getToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE_URL}/api/rate-cards/${id}`, {
      method: "DELETE",
      headers,
    });
    if (!res.ok) {
      throw new Error(`Failed to delete rate card: ${res.statusText}`);
    }
  }

  public async resetRateCards(
    gateway = "razorpay"
  ): Promise<{items: RateCard[]; total: number}> {
    return this.request<{items: RateCard[]; total: number}>(
      `/api/rate-cards/reset-benchmarks?gateway=${gateway}`,
      {
        method: "POST",
      }
    );
  }

  public async calculateCharges(
    grossAmount: number,
    rateCardId?: string
  ): Promise<{
    gross_amount: number;
    expected_fee: number;
    expected_gst: number;
    expected_total_deduction: number;
    expected_net_amount: number;
    effective_take_rate_pct: number;
  }> {
    return this.request("/api/rate-cards/calculate", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        gross_amount: grossAmount,
        rate_card_id: rateCardId,
      }),
    });
  }

  // --- Fee Audit Endpoints ---
  public async getFeeAudit(params?: {
    gateway?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<FeeAuditReportData> {
    const query = new URLSearchParams();
    if (params?.gateway) query.append("gateway", params.gateway);
    if (params?.start_date) query.append("start_date", params.start_date);
    if (params?.end_date) query.append("end_date", params.end_date);
    const qStr = query.toString();
    return this.request<FeeAuditReportData>(
      `/api/fee-audit${qStr ? `?${qStr}` : ""}`
    );
  }

  public getDisputeExportUrl(gateway?: string): string {
    const q = gateway ? `?gateway=${gateway}` : "";
    return `${API_BASE_URL}/api/fee-audit/export${q}`;
  }

  public async downloadDisputeExport(gateway?: string): Promise<void> {
    const token = this.getToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const q = gateway ? `?gateway=${gateway}` : "";
    const res = await fetch(`${API_BASE_URL}/api/fee-audit/export${q}`, {
      headers,
    });
    if (!res.ok) throw new Error("Failed to download dispute claim CSV");
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `rekon_fee_disputes_${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  }

  // --- Exception Resolution Queue Endpoints ---
  public async listExceptions(params?: {
    status?: ResolutionStatus;
    exception_type?: ExceptionType;
    severity?: ExceptionSeverity;
    run_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<{
    items: ReconciliationException[];
    total: number;
    limit: number;
    offset: number;
  }> {
    const query = new URLSearchParams();
    if (params?.status) query.append("status", params.status);
    if (params?.exception_type)
      query.append("exception_type", params.exception_type);
    if (params?.severity) query.append("severity", params.severity);
    if (params?.run_id) query.append("run_id", params.run_id);
    if (params?.limit) query.append("limit", params.limit.toString());
    if (params?.offset !== undefined)
      query.append("offset", params.offset.toString());
    const qStr = query.toString();
    return this.request<{
      items: ReconciliationException[];
      total: number;
      limit: number;
      offset: number;
    }>(`/api/exceptions${qStr ? `?${qStr}` : ""}`);
  }

  public async getExceptionSummary(): Promise<ExceptionSummary> {
    return this.request<ExceptionSummary>("/api/exceptions/summary");
  }

  public async manualMatchException(
    exceptionId: string,
    payload: {
      target_entity_type: string;
      target_entity_id: string;
      notes?: string;
    }
  ): Promise<ReconciliationException> {
    return this.request<ReconciliationException>(
      `/api/exceptions/${exceptionId}/manual-match`,
      {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      }
    );
  }

  public async writeOffException(
    exceptionId: string,
    payload: {notes?: string; max_allowed?: number} = {}
  ): Promise<ReconciliationException> {
    return this.request<ReconciliationException>(
      `/api/exceptions/${exceptionId}/write-off`,
      {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      }
    );
  }

  public async batchWriteOffExceptions(
    payload: {max_threshold?: number} = {max_threshold: 5.0}
  ): Promise<ReconciliationException[]> {
    return this.request<ReconciliationException[]>(
      "/api/exceptions/batch-write-off",
      {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      }
    );
  }

  public async updateExceptionStatus(
    exceptionId: string,
    payload: {status: ResolutionStatus; notes?: string}
  ): Promise<ReconciliationException> {
    return this.request<ReconciliationException>(
      `/api/exceptions/${exceptionId}/status`,
      {
        method: "PUT",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      }
    );
  }

  public async getExecutiveDashboard(params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<ExecutiveDashboardResponse> {
    const query = new URLSearchParams();
    if (params?.start_date) query.append("start_date", params.start_date);
    if (params?.end_date) query.append("end_date", params.end_date);
    const qStr = query.toString();
    return this.request<ExecutiveDashboardResponse>(
      `/api/analytics/dashboard${qStr ? `?${qStr}` : ""}`
    );
  }
}

export interface RateCard {
  id: string;
  org_id: string;
  gateway: "razorpay" | "stripe" | "cashfree" | "payu";
  payment_method: "upi" | "card" | "enach" | "netbanking" | "wallet" | "other";
  card_network: string;
  is_international: boolean;
  rate_type: "percentage" | "flat" | "hybrid";
  percentage_rate: string | number;
  flat_fee: string | number;
  gst_rate: string | number;
  cap_min_fee?: string | number | null;
  cap_max_fee?: string | number | null;
  is_active: boolean;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuditedTransactionItem {
  txn_id: string;
  gateway: string;
  payment_method: string;
  card_network: string;
  is_international: boolean;
  captured_at: string | null;
  gross_amount: number;
  actual_fee: number;
  actual_gst: number;
  actual_total_deduction: number;
  expected_fee: number;
  expected_gst: number;
  expected_total_deduction: number;
  fee_variance: number;
  gst_variance: number;
  total_overcharge: number;
  audit_status: "verified" | "overcharged" | "undercharged";
  dispute_category: string;
  explanation: string;
  rate_card_applied?: string;
}

export interface FeeAuditReportData {
  total_audited: number;
  total_gross_volume: number;
  total_actual_fees: number;
  total_expected_fees: number;
  total_actual_gst: number;
  total_expected_gst: number;
  total_overcharged_amount: number;
  total_undercharged_amount: number;
  net_variance: number;
  verified_count: number;
  overcharged_count: number;
  undercharged_count: number;
  discrepancies_by_category: Record<string, {count: number; amount: number}>;
  items: AuditedTransactionItem[];
}

export type ExceptionType =
  | "timing_difference"
  | "missing_bank_credit"
  | "unbilled_charge"
  | "unidentified_bank_deposit"
  | "paisa_rounding_delta"
  | "amount_mismatch"
  | "gateway_fee_discrepancy";

export type ExceptionSeverity = "low" | "medium" | "high" | "critical";

export type ResolutionStatus =
  | "open"
  | "investigating"
  | "resolved"
  | "written_off"
  | "disputed";

export type ResolutionAction =
  | "manual_match"
  | "write_off"
  | "batch_write_off"
  | "timing_cleared"
  | "status_update";

export interface ReconciliationException {
  id: string;
  org_id: string;
  run_id?: string;
  exception_type: ExceptionType;
  severity: ExceptionSeverity;
  status: ResolutionStatus;
  invoice_id?: string;
  gateway_txn_id?: string;
  settlement_batch_id?: string;
  settlement_line_id?: string;
  bank_credit_id?: string;
  entity_reference?: string;
  customer_info?: string;
  expected_amount: number;
  actual_amount: number;
  discrepancy_amount: number;
  title: string;
  root_cause_explanation: string;
  suggested_action?: string;
  resolution_action?: ResolutionAction;
  resolution_notes?: string;
  resolved_by?: string;
  resolved_at?: string;
  created_at: string;
  updated_at: string;
}

export interface ExceptionSummary {
  total_exceptions: number;
  open_count: number;
  investigating_count: number;
  resolved_count: number;
  written_off_count: number;
  total_unresolved_exposure: number;
  severity_breakdown: Record<string, number>;
  type_breakdown: Record<string, {count: number; amount: number}>;
}

export interface CashflowWaterfallStep {
  step_key: string;
  label: string;
  amount: number;
  percentage_of_gross: number;
  step_type: "starting" | "deduction" | "net_realized";
  description: string;
}

export interface GatewayPerformanceItem {
  gateway: string;
  transaction_count: number;
  gross_volume: number;
  total_fee: number;
  total_gst: number;
  total_deductions: number;
  effective_take_rate_pct: number;
  discrepancy_count: number;
  overcharge_amount: number;
  volume_share_pct: number;
}

export interface ExecutiveAlertItem {
  id: string;
  severity: "critical" | "warning" | "info" | "success";
  title: string;
  description: string;
  action_label?: string | null;
  action_target?: string | null;
}

export interface ExecutiveKPISummary {
  gross_billed_amount: number;
  invoice_count: number;
  gross_gateway_volume: number;
  gateway_txn_count: number;
  net_settled_cash: number;
  bank_credit_count: number;
  total_gateway_fees: number;
  total_gateway_gst: number;
  total_gateway_deductions: number;
  blended_take_rate_pct: number;
  fee_leakage_detected: number;
  overcharged_txns_count: number;
  unresolved_exposure: number;
  open_exceptions_count: number;
  health_score: number;
  health_status: "EXCELLENT" | "GOOD" | "NEEDS_ATTENTION" | "CRITICAL";
  matched_invoices_pct: number;
  settled_batches_pct: number;
}

export interface ExecutiveDashboardResponse {
  summary: ExecutiveKPISummary;
  waterfall: CashflowWaterfallStep[];
  gateway_comparison: GatewayPerformanceItem[];
  actionable_alerts: ExecutiveAlertItem[];
  last_updated: string;
}

export const api = new ApiClient();
