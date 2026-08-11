import { type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import type { UserRole } from "@/api/auth";
import { useAuth } from "@/context/AuthContext";

interface RequireRoleProps {
  roles: UserRole[];
  children: ReactNode;
  fallback?: ReactNode;
  redirectTo?: string;
}

export function RequireRole({
  roles,
  children,
  fallback,
  redirectTo = "/dashboard",
}: RequireRoleProps) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return null;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!roles.includes(user.role)) {
    if (fallback) {
      return <>{fallback}</>;
    }
    return <Navigate to={redirectTo} replace />;
  }

  return <>{children}</>;
}

interface RequireAdminProps {
  children: ReactNode;
  fallback?: ReactNode;
}

export function RequireAdmin({ children, fallback }: RequireAdminProps) {
  return (
    <RequireRole roles={["admin"]} fallback={fallback}>
      {children}
    </RequireRole>
  );
}

interface RequireOfficerOrAdminProps {
  children: ReactNode;
  fallback?: ReactNode;
}

export function RequireOfficerOrAdmin({ children, fallback }: RequireOfficerOrAdminProps) {
  return (
    <RequireRole roles={["admin", "officer"]} fallback={fallback}>
      {children}
    </RequireRole>
  );
}
