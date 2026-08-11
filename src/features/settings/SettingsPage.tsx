import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bell,
  Download,
  Eraser,
  KeyRound,
  LogOut,
  MonitorCog,
  RefreshCw,
  Save,
  Settings2,
  Upload,
  UserRound,
} from "lucide-react";
import { authApi } from "@/api/auth";
import { SETTINGS_CATEGORY_META, type SettingItem } from "@/api/settings";
import { systemApi, type SystemInfo } from "@/api/system";
import { ApiError } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Spinner } from "@/components/ui/Spinner";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/context/AuthContext";
import { usePermissions } from "@/hooks/usePermissions";
import { cn } from "@/utils/cn";
import { formatDateTime12h } from "@/utils/datetime";
import { SettingField } from "@/features/settings/components/SettingField";
import { useAppSettings } from "@/features/settings/hooks/useAppSettings";
import { clearAnalyticsCache } from "@/features/dashboard/hooks/useDashboardAnalytics";
import { clearDashboardCache } from "@/features/home/hooks/useDashboardSummary";
import { unlockNotificationAudio } from "@/features/notifications/notificationSounds";

type TabSlug = "general" | "notifications" | "account" | "system";

const TAB_ICONS: Record<TabSlug, typeof Settings2> = {
  general: Settings2,
  notifications: Bell,
  account: UserRound,
  system: MonitorCog,
};

const SETTINGS_TABS: TabSlug[] = ["general", "notifications", "account"];

function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function SettingsPage() {
  const { canManageSettings } = usePermissions();
  const [activeTab, setActiveTab] = useState<TabSlug>("general");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isSettingsTab = SETTINGS_TABS.includes(activeTab);
  // The hook requires a settings-backed category; System renders its own data.
  const settingsCategory = isSettingsTab ? activeTab : "general";

  const {
    categories,
    loading,
    saving,
    error,
    hasChanges,
    getValue,
    setValue,
    save,
    resetCategory,
    exportSettings,
    importSettings,
    reload,
  } = useAppSettings(settingsCategory);

  const activeCategory = categories.find((c) => c.slug === activeTab) ?? null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PageHeader
          title="Settings"
          description="Application preferences, notifications, account, and system status"
          breadcrumbs={[{ label: "System" }, { label: "Settings" }]}
        />
        {canManageSettings && isSettingsTab && (
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={saving}
            >
              <Upload className="mr-2 h-4 w-4" />
              Import
            </Button>
            <Button variant="secondary" onClick={() => void exportSettings()} disabled={saving}>
              <Download className="mr-2 h-4 w-4" />
              Export
            </Button>
            <Button
              variant="secondary"
              onClick={() => void resetCategory(activeTab)}
              disabled={saving}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Reset
            </Button>
            <Button onClick={() => void save()} disabled={saving || !hasChanges}>
              <Save className="mr-2 h-4 w-4" />
              {saving ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="application/json,.json"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void importSettings(file);
          e.target.value = "";
        }}
      />

      {!canManageSettings && isSettingsTab && activeTab !== "account" && (
        <Alert variant="info" title="Read-only access">
          You can view settings. Contact an administrator to make changes.
        </Alert>
      )}

      {error && isSettingsTab && activeTab !== "account" && (
        <Alert variant="error" title="Error">
          {error}{" "}
          <button type="button" className="underline" onClick={() => void reload()}>
            Retry
          </button>
        </Alert>
      )}

      <div className="flex flex-col gap-6 lg:flex-row">
        <aside className="w-full shrink-0 lg:w-64">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Categories</CardTitle>
            </CardHeader>
            <CardBody className="space-y-1 p-2">
              {(Object.keys(TAB_ICONS) as TabSlug[]).map((slug) => {
                if (slug === "system" && !canManageSettings) return null;
                const Icon = TAB_ICONS[slug];
                const meta = SETTINGS_CATEGORY_META[slug];
                const isActive = activeTab === slug;
                return (
                  <button
                    key={slug}
                    type="button"
                    onClick={() => setActiveTab(slug)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors",
                      isActive
                        ? "bg-primary/5 font-medium text-primary"
                        : "text-slate-600 hover:bg-slate-50",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span>{meta?.label ?? slug}</span>
                  </button>
                );
              })}
            </CardBody>
          </Card>
        </aside>

        <div className="min-w-0 flex-1 space-y-4">
          {activeTab === "system" ? (
            <SystemTab />
          ) : loading ? (
            <div className="flex justify-center py-16">
              <Spinner size="lg" />
            </div>
          ) : (
            <>
              {activeCategory && activeTab !== "account" && (
                <SettingsCategoryCard
                  slug={activeTab}
                  title={activeCategory.label}
                  description={activeCategory.description}
                  settings={activeCategory.settings}
                  getValue={getValue}
                  setValue={setValue}
                  editable={canManageSettings}
                />
              )}
              {activeTab === "account" && (
                <AccountTab
                  sessionTimeoutCard={
                    activeCategory ? (
                      <SettingsCategoryCard
                        slug="account"
                        title="Session"
                        description="Applies to new sign-ins"
                        settings={activeCategory.settings}
                        getValue={getValue}
                        setValue={setValue}
                        editable={canManageSettings}
                      />
                    ) : null
                  }
                />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function SettingsCategoryCard({
  slug,
  title,
  description,
  settings,
  getValue,
  setValue,
  editable,
}: {
  slug: string;
  title: string;
  description: string | null;
  settings: SettingItem[];
  getValue: (category: string, key: string) => unknown;
  setValue: (category: string, key: string, value: unknown) => void;
  editable: boolean;
}) {
  const notificationsEnabled =
    slug !== "notifications" || Boolean(getValue("notifications", "enable_notifications"));

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardBody>
        <div className="grid gap-6 sm:grid-cols-2">
          {settings.map((setting) => {
            const isChildNotificationToggle =
              slug === "notifications" &&
              setting.key !== "enable_notifications" &&
              !notificationsEnabled;

            return (
              <div
                key={setting.id}
                className={cn(isChildNotificationToggle && "opacity-60 pointer-events-none")}
              >
                <SettingField
                  setting={setting}
                  value={getValue(slug, setting.key)}
                  disabled={!editable || isChildNotificationToggle}
                  onChange={(value) => {
                    if (!editable) return;
                    setValue(slug, setting.key, value);
                    if (
                      slug === "notifications" &&
                      setting.key === "notification_sound" &&
                      value === true
                    ) {
                      unlockNotificationAudio();
                    }
                  }}
                />
                {setting.is_modified && (
                  <p className="mt-1 text-xs text-amber-600">Modified from default</p>
                )}
              </div>
            );
          })}
        </div>
      </CardBody>
    </Card>
  );
}

function AccountTab({ sessionTimeoutCard }: { sessionTimeoutCard: React.ReactNode }) {
  const { user, clearSession } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [changing, setChanging] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  const onChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    if (newPassword.length < 8) {
      setPasswordError("New password must be at least 8 characters");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New passwords do not match");
      return;
    }
    setChanging(true);
    try {
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      showToast("success", "Password changed. Please sign in again.");
      clearSession();
      navigate("/login", { replace: true });
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : "Failed to change password");
    } finally {
      setChanging(false);
    }
  };

  const onLogoutAll = async () => {
    setLoggingOut(true);
    try {
      await authApi.logoutAll();
      showToast("success", "Signed out of all sessions");
      clearSession();
      navigate("/login", { replace: true });
    } catch {
      showToast("error", "Failed to sign out of all sessions");
      setLoggingOut(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Your account details</CardDescription>
        </CardHeader>
        <CardBody className="grid gap-6 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label>Username</Label>
            <Input value={user?.username ?? ""} disabled readOnly />
          </div>
          <div className="space-y-1.5">
            <Label>Email</Label>
            <Input value={user?.email ?? ""} disabled readOnly />
          </div>
          <div className="space-y-1.5">
            <Label>Role</Label>
            <Input value={user?.role ?? ""} disabled readOnly className="capitalize" />
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Change Password</CardTitle>
          <CardDescription>
            All sessions are signed out after a password change
          </CardDescription>
        </CardHeader>
        <CardBody>
          <form className="max-w-md space-y-4" onSubmit={(e) => void onChangePassword(e)}>
            <div className="space-y-1.5">
              <Label htmlFor="current-password">Current password</Label>
              <Input
                id="current-password"
                type="password"
                autoComplete="current-password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new-password">New password</Label>
              <Input
                id="new-password"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="confirm-password">Confirm new password</Label>
              <Input
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>
            {passwordError && <p className="text-sm text-red-600">{passwordError}</p>}
            <Button type="submit" disabled={changing || !currentPassword || !newPassword}>
              <KeyRound className="mr-2 h-4 w-4" />
              {changing ? "Changing..." : "Change Password"}
            </Button>
          </form>
        </CardBody>
      </Card>

      {sessionTimeoutCard}

      <Card>
        <CardHeader>
          <CardTitle>Active Sessions</CardTitle>
          <CardDescription>
            Sign out everywhere — revokes all refresh tokens, including this device
          </CardDescription>
        </CardHeader>
        <CardBody>
          <Button
            variant="secondary"
            className="text-red-600 hover:bg-red-50"
            onClick={() => void onLogoutAll()}
            disabled={loggingOut}
          >
            <LogOut className="mr-2 h-4 w-4" />
            {loggingOut ? "Signing out..." : "Logout All Sessions"}
          </Button>
        </CardBody>
      </Card>
    </div>
  );
}

function SystemTab() {
  const { showToast } = useToast();
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [clearCacheOpen, setClearCacheOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setInfo(await systemApi.info());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load system info");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onExportLogs = async () => {
    setBusy("logs");
    try {
      const { blob, filename } = await systemApi.exportLogs();
      triggerBlobDownload(blob, filename);
      showToast("success", "Administrative logs exported");
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Failed to export logs";
      showToast("error", message);
    } finally {
      setBusy(null);
    }
  };

  const onClearCacheConfirm = async () => {
    setClearCacheOpen(false);
    setBusy("cache");
    try {
      const result = await systemApi.clearCache();
      clearDashboardCache();
      clearAnalyticsCache();
      let message = `Cache cleared — ${result.files_removed} files removed, ${formatBytes(result.bytes_freed)} freed.`;
      if (result.partial) {
        message += " Some locked files were skipped.";
      }
      showToast("success", message);
      await load();
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Failed to clear cache";
      showToast("error", message);
    } finally {
      setBusy(null);
    }
  };

  const statusRow = (label: string, ok: boolean, detail: string | null) => (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 px-4 py-3">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <span className="flex items-center gap-2">
        {detail && <span className="max-w-52 truncate text-xs text-slate-500">{detail}</span>}
        <StatusBadge variant={ok ? "success" : "error"}>
          {ok ? "Online" : "Offline"}
        </StatusBadge>
      </span>
    </div>
  );

  const infoRow = (label: string, value: string) => (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 px-4 py-3">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <span className="text-sm text-slate-600">{value}</span>
    </div>
  );

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-3">
          <div>
            <CardTitle>System Status</CardTitle>
            <CardDescription>Live health of the platform components</CardDescription>
          </div>
          <Button variant="secondary" size="sm" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={cn("mr-1 h-3.5 w-3.5", loading && "animate-spin")} />
            Refresh
          </Button>
        </CardHeader>
        <CardBody>
          {error && (
            <Alert variant="error" title="Error">
              {error}
            </Alert>
          )}
          {loading && !info ? (
            <div className="flex justify-center py-10">
              <Spinner size="lg" />
            </div>
          ) : info ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {statusRow("Backend", info.backend.ok, info.backend.detail)}
              {statusRow("Database", info.database.ok, info.database.detail)}
              {statusRow("Browser (CDP)", info.cdp.ok, info.cdp.detail)}
              {infoRow("Automation", info.automation_status)}
              {infoRow("App Version", info.app_version)}
              {infoRow("Environment", info.environment)}
              {infoRow("Database Type", info.database_type)}
              {infoRow("Storage Used", formatBytes(info.storage_usage_bytes))}
              {infoRow(
                "Last Successful Run",
                info.last_successful_run_at
                  ? formatDateTime12h(info.last_successful_run_at)
                  : "—",
              )}
              {infoRow(
                "Last Failed Run",
                info.last_failed_run_at ? formatDateTime12h(info.last_failed_run_at) : "—",
              )}
            </div>
          ) : null}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Maintenance</CardTitle>
          <CardDescription>Operational actions</CardDescription>
        </CardHeader>
        <CardBody className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            onClick={() => void onExportLogs()}
            disabled={busy === "logs"}
          >
            <Download className="mr-2 h-4 w-4" />
            {busy === "logs" ? "Exporting..." : "Export Logs"}
          </Button>
          <Button
            variant="secondary"
            onClick={() => setClearCacheOpen(true)}
            disabled={busy === "cache"}
          >
            <Eraser className="mr-2 h-4 w-4" />
            {busy === "cache" ? "Clearing..." : "Clear Cache"}
          </Button>
        </CardBody>
      </Card>

      <Dialog open={clearCacheOpen} onOpenChange={setClearCacheOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Clear application cache?</DialogTitle>
            <DialogDescription>
              Generated reports, logs, settings and user data will not be deleted.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setClearCacheOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void onClearCacheConfirm()} disabled={busy === "cache"}>
              Clear Cache
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
