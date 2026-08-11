import { apiRequest, setCsrfToken } from "./client";

export type UserRole = "admin" | "officer" | "viewer";

export interface User {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface LoginCredentials {
  username: string;
  password: string;
  remember_me?: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  csrf_token?: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export const authApi = {
  async login(credentials: LoginCredentials): Promise<TokenResponse> {
    const response = await apiRequest<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });

    if (response.csrf_token) {
      setCsrfToken(response.csrf_token);
    }

    return response;
  },

  async logout(): Promise<void> {
    await apiRequest("/auth/logout", { method: "POST" });
    setCsrfToken(null);
  },

  async logoutAll(): Promise<void> {
    await apiRequest("/auth/logout-all", { method: "POST" });
    setCsrfToken(null);
  },

  async getMe(accessToken?: string, skipAuthRetry = false): Promise<User> {
    const headers: Record<string, string> = {};
    if (accessToken) {
      headers.Authorization = `Bearer ${accessToken}`;
    }
    return apiRequest<User>("/auth/me", { headers }, skipAuthRetry);
  },

  async refresh(): Promise<TokenResponse> {
    const response = await apiRequest<TokenResponse>("/auth/refresh", {
      method: "POST",
    });

    if (response.csrf_token) {
      setCsrfToken(response.csrf_token);
    }

    return response;
  },

  async changePassword(request: ChangePasswordRequest): Promise<void> {
    await apiRequest("/auth/change-password", {
      method: "POST",
      body: JSON.stringify(request),
    });
    setCsrfToken(null);
  },

  async forgotPassword(request: ForgotPasswordRequest): Promise<void> {
    await apiRequest("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify(request),
    });
  },
};
