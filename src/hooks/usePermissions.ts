import { useMemo } from "react";
import { useAuth } from "@/context/AuthContext";
import { permissions, type Permission, hasPermission, hasAnyPermission, hasAllPermissions } from "@/lib/permissions";

export function usePermissions() {
  const { user } = useAuth();
  const role = user?.role;

  return useMemo(
    () => ({
      canManageUsers: permissions.canManageUsers(role),
      canManageSettings: permissions.canManageSettings(role),
      canManageTemplates: permissions.canManageTemplates(role),
      canManageRules: permissions.canManageRules(role),
      canViewLogs: permissions.canViewLogs(role),
      canUploadReports: permissions.canUploadReports(role),
      canGenerateReports: permissions.canGenerateReports(role),
      canDownloadReports: permissions.canDownloadReports(role),
      canViewReports: permissions.canViewReports(role),
      
      isAdmin: permissions.isAdmin(role),
      isOfficer: permissions.isOfficer(role),
      isViewer: permissions.isViewer(role),
      isOfficerOrAdmin: permissions.isOfficerOrAdmin(role),

      hasPermission: (permission: Permission) => hasPermission(role, permission),
      hasAnyPermission: (perms: Permission[]) => hasAnyPermission(role, perms),
      hasAllPermissions: (perms: Permission[]) => hasAllPermissions(role, perms),
    }),
    [role],
  );
}
