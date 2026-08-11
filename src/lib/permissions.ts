import type { UserRole } from "@/api/auth";

export type Permission =
  | "manage_users"
  | "manage_settings"
  | "manage_templates"
  | "manage_rules"
  | "view_logs"
  | "upload_reports"
  | "generate_reports"
  | "download_reports"
  | "view_reports";

const rolePermissions: Record<UserRole, Permission[]> = {
  admin: [
    "manage_users",
    "manage_settings",
    "manage_templates",
    "manage_rules",
    "view_logs",
    "upload_reports",
    "generate_reports",
    "download_reports",
    "view_reports",
  ],
  officer: [
    "upload_reports",
    "generate_reports",
    "download_reports",
    "view_reports",
  ],
  viewer: ["view_reports"],
};

export function hasPermission(role: UserRole | undefined, permission: Permission): boolean {
  if (!role) return false;
  return rolePermissions[role]?.includes(permission) ?? false;
}

export function hasAnyPermission(role: UserRole | undefined, permissions: Permission[]): boolean {
  if (!role) return false;
  return permissions.some((p) => hasPermission(role, p));
}

export function hasAllPermissions(role: UserRole | undefined, permissions: Permission[]): boolean {
  if (!role) return false;
  return permissions.every((p) => hasPermission(role, p));
}

export const permissions = {
  canManageUsers: (role: UserRole | undefined) => hasPermission(role, "manage_users"),
  canManageSettings: (role: UserRole | undefined) => hasPermission(role, "manage_settings"),
  canManageTemplates: (role: UserRole | undefined) => hasPermission(role, "manage_templates"),
  canManageRules: (role: UserRole | undefined) => hasPermission(role, "manage_rules"),
  canViewLogs: (role: UserRole | undefined) => hasPermission(role, "view_logs"),
  canUploadReports: (role: UserRole | undefined) => hasPermission(role, "upload_reports"),
  canGenerateReports: (role: UserRole | undefined) => hasPermission(role, "generate_reports"),
  canDownloadReports: (role: UserRole | undefined) => hasPermission(role, "download_reports"),
  canViewReports: (role: UserRole | undefined) => hasPermission(role, "view_reports"),
  
  isAdmin: (role: UserRole | undefined) => role === "admin",
  isOfficer: (role: UserRole | undefined) => role === "officer",
  isViewer: (role: UserRole | undefined) => role === "viewer",
  isOfficerOrAdmin: (role: UserRole | undefined) => role === "admin" || role === "officer",
};
