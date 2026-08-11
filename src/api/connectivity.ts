/**
 * Local service connectivity checks before automation.
 */

const BACKEND_HEALTH_URL = "/api/v1/health";
const BACKEND_DIRECT_URL = "http://127.0.0.1:8000/api/v1/health";

export interface ServiceCheckResult {
  ok: boolean;
  message: string;
}

async function probeUrl(url: string, timeoutMs = 5000): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      method: "GET",
      credentials: "include",
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function checkBackendHealth(): Promise<ServiceCheckResult> {
  try {
    let response = await probeUrl(BACKEND_HEALTH_URL);
    if (!response.ok && response.status >= 500) {
      response = await probeUrl(BACKEND_DIRECT_URL);
    }
    if (response.ok) {
      return { ok: true, message: "Backend API is available." };
    }
    return {
      ok: false,
      message:
        `Backend API returned HTTP ${response.status}. ` +
        "Ensure FastAPI is running on http://127.0.0.1:8000.",
    };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return {
        ok: false,
        message:
          "Backend API timed out at http://127.0.0.1:8000/api/v1/health. " +
          "Start it with: cd backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000",
      };
    }
    return {
      ok: false,
      message:
        "Cannot reach the backend API at http://127.0.0.1:8000. " +
        "Start PostgreSQL and Redis locally, then start the backend server.",
    };
  }
}

export async function checkFrontendOrigin(): Promise<ServiceCheckResult> {
  const expectedOrigin = "http://127.0.0.1:5173";
  const currentOrigin = window.location.origin;
  if (currentOrigin === expectedOrigin || currentOrigin === "http://localhost:5173") {
    return { ok: true, message: "Frontend is served from the expected dev URL." };
  }
  return {
    ok: false,
    message:
      `Open the app at ${expectedOrigin} (current: ${currentOrigin}). ` +
      "Vite is pinned to port 5173 and will not switch ports automatically.",
  };
}

export async function checkServicesBeforeAutomation(): Promise<ServiceCheckResult> {
  const frontend = await checkFrontendOrigin();
  if (!frontend.ok) {
    return frontend;
  }
  return checkBackendHealth();
}
