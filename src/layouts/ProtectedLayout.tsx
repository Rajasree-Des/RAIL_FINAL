import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { RailMadadLogo } from "@/components/branding/RailMadadLogo";
import { Spinner } from "@/components/ui/Spinner";

function LoadingScreen() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-surface">
      <RailMadadLogo size="lg" />
      <Spinner size="lg" className="mt-6" />
      <p className="mt-4 text-sm text-slate-600">Loading RailMadad Report Center…</p>
    </div>
  );
}

export function ProtectedLayout() {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}
