export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function isAbortError(err: unknown): boolean {
  if (err instanceof DOMException && err.name === "AbortError") {
    return true;
  }
  return err instanceof ApiError && err.code === "TIMEOUT";
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
export { API_BASE };
export const API_TIMEOUT_MS = 15_000;
export const PREVIEW_TIMEOUT_MS = 30_000;
export const AUTOMATION_START_TIMEOUT_MS = 900_000;

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init?: RequestInit,
  timeoutMs = API_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const externalSignal = init?.signal;

  if (externalSignal?.aborted) {
    controller.abort(externalSignal.reason);
  } else if (externalSignal) {
    externalSignal.addEventListener(
      "abort",
      () => controller.abort(externalSignal.reason),
      { once: true },
    );
  }

  const timeoutId = window.setTimeout(() => {
    controller.abort(new DOMException("Request timed out", "TimeoutError"));
  }, timeoutMs);

  try {
    return await fetch(input, {
      ...init,
      signal: controller.signal,
    });
  } catch (err) {
    if (
      isAbortError(err) &&
      controller.signal.reason instanceof DOMException &&
      controller.signal.reason.name === "TimeoutError"
    ) {
      throw new ApiError("Request timed out", 408, "TIMEOUT");
    }
    throw err;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

let csrfToken: string | null = null;
let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

async function tryRefreshToken(): Promise<boolean> {
  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }

  isRefreshing = true;
  refreshPromise = (async () => {
    try {
      const response = await fetchWithTimeout(`${API_BASE}/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: {
          Accept: "application/json",
        },
      });

      if (response.ok) {
        const data = await response.json();
        if (data.csrf_token) {
          setCsrfToken(data.csrf_token);
        }
        return true;
      }
      return false;
    } catch {
      return false;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

function isMutatingMethod(method?: string): boolean {
  return !!method && ["POST", "PUT", "DELETE", "PATCH"].includes(method);
}

function needsCsrfProtection(path: string, method?: string): boolean {
  if (!isMutatingMethod(method)) {
    return false;
  }
  const exemptPaths = ["/auth/login", "/auth/register", "/auth/refresh", "/auth/csrf"];
  return !exemptPaths.some((prefix) => path.startsWith(prefix));
}

export async function ensureCsrfToken(): Promise<boolean> {
  if (csrfToken) {
    return true;
  }

  if (await tryRefreshToken() && csrfToken) {
    return true;
  }

  try {
    const data = await apiRequest<{ csrf_token: string }>(
      "/auth/csrf",
      { method: "POST" },
      true,
      API_TIMEOUT_MS,
      true,
    );
    if (data.csrf_token) {
      setCsrfToken(data.csrf_token);
      return true;
    }
  } catch {
    return false;
  }

  return false;
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
  skipAuthRetry = false,
  timeoutMs = API_TIMEOUT_MS,
  skipCsrfRetry = false,
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };

  if (init?.headers) {
    const initHeaders = init.headers as Record<string, string>;
    Object.assign(headers, initHeaders);
  }

  if (init?.body && typeof init.body === "string") {
    headers["Content-Type"] = "application/json";
  }

  if (needsCsrfProtection(path, init?.method)) {
    await ensureCsrfToken();
    if (csrfToken) {
      headers["X-CSRF-Token"] = csrfToken;
    }
  }

  const response = await fetchWithTimeout(`${API_BASE}${path}`, {
    credentials: "include",
    ...init,
    headers,
  }, timeoutMs);

  if (response.status === 401 && !skipAuthRetry && !path.includes("/auth/login") && !path.includes("/auth/refresh")) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      return apiRequest(path, init, true, timeoutMs, skipCsrfRetry);
    }

    window.dispatchEvent(new window.CustomEvent("auth:session-expired"));
    throw new ApiError("Session expired", 401);
  }

    if (!response.ok) {
    let message: string;
    let code: string | undefined;
    try {
      const errorData = await response.json();
      const detail = errorData.detail;
      if (typeof detail === "object" && detail !== null) {
        message =
          typeof detail.message === "string"
            ? detail.message
            : JSON.stringify(detail);
        code = typeof detail.code === "string" ? detail.code : code;
      } else {
        message = detail || errorData.message || JSON.stringify(errorData);
      }
      code = code ?? (typeof errorData.code === "string" ? errorData.code : undefined);
    } catch {
      message = await response.text() || `Request failed with status ${response.status}`;
    }

    if (
      !skipCsrfRetry &&
      response.status === 422 &&
      message.toLowerCase().includes("csrf") &&
      needsCsrfProtection(path, init?.method)
    ) {
      setCsrfToken(null);
      if (await ensureCsrfToken()) {
        return apiRequest(path, init, skipAuthRetry, timeoutMs, true);
      }
    }

    throw new ApiError(message, response.status, code);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export { buildQueryString } from "./query";
