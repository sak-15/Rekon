/**
 * Centralized API Client for Rekon Frontend.
 * Automatically injects JWT Bearer tokens from localStorage.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

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
  error_details?: Array<{ row: number; field: string; message: string }>;
  created_at: string;
}

export interface UploadResult {
  message: string;
  upload_job: UploadJob;
}

class ApiClient {
  private getToken(): string | null {
    return localStorage.getItem('rekon_token');
  }

  public setToken(token: string) {
    localStorage.setItem('rekon_token', token);
  }

  public clearToken() {
    localStorage.removeItem('rekon_token');
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorData.detail || `Request failed with status ${response.status}`);
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
    const data = await this.request<AuthResponse>('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    this.setToken(data.access_token);
    return data;
  }

  public async login(email: string, password: string): Promise<AuthResponse> {
    const data = await this.request<AuthResponse>('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    this.setToken(data.access_token);
    return data;
  }

  public async getMe(): Promise<{ user: UserInfo; organisation: OrgInfo }> {
    return this.request<{ user: UserInfo; organisation: OrgInfo }>('/api/auth/me');
  }

  // --- Upload Endpoints ---
  public async uploadCsv(
    endpoint: string,
    file: File,
    additionalParams: Record<string, string> = {}
  ): Promise<UploadResult> {
    const formData = new FormData();
    formData.append('file', file);

    const queryParams = new URLSearchParams(additionalParams).toString();
    const url = `${endpoint}${queryParams ? `?${queryParams}` : ''}`;

    return this.request<UploadResult>(url, {
      method: 'POST',
      body: formData,
    });
  }

  // --- Upload Jobs Audit Endpoints ---
  public async listUploads(): Promise<{ items: UploadJob[]; total: number }> {
    return this.request<{ items: UploadJob[]; total: number }>('/api/uploads');
  }

  // --- Records Explorer Endpoints ---
  public async getRecords<T>(category: string, page = 1, pageSize = 20): Promise<{ items: T[]; total: number }> {
    return this.request<{ items: T[]; total: number }>(`/api/records/${category}?page=${page}&page_size=${pageSize}`);
  }
}

export const api = new ApiClient();
