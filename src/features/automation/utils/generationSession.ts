/** Keys for automation run resume / last-run deep links. */
export const RAILMADAD_LAST_RUN_KEY = "railmadad_last_run_id";
/** Tab-scoped: only resume progress UI if generation was started in this browser tab. */
export const RAILMADAD_ACTIVE_GENERATION_KEY = "railmadad_active_generation";

/** Clear generation UI resume state (call on login/logout so Home shows Generate). */
export function clearGenerationSessionState(): void {
  try {
    sessionStorage.removeItem(RAILMADAD_ACTIVE_GENERATION_KEY);
  } catch {
    // ignore
  }
  try {
    localStorage.removeItem(RAILMADAD_LAST_RUN_KEY);
  } catch {
    // ignore
  }
}

/** Fired after login/logout so Home drops any in-memory progress UI. */
export const CLEAR_GENERATION_UI_EVENT = "railmadad:clear-generation-ui";

export function emitClearGenerationUi(): void {
  clearGenerationSessionState();
  try {
    window.dispatchEvent(new Event(CLEAR_GENERATION_UI_EVENT));
  } catch {
    // ignore (SSR / tests)
  }
}
