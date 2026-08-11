import { Outlet } from "react-router-dom";
import { RequireAdmin } from "@/components/RequireRole";

export function AdminLayout() {
  return (
    <RequireAdmin>
      <Outlet />
    </RequireAdmin>
  );
}
