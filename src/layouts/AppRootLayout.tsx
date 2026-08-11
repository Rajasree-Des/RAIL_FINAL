import { Outlet } from "react-router-dom";
import { SessionExpiredDialog } from "@/components/SessionExpiredDialog";

/** Root layout: keeps global UI inside the router context. */
export function AppRootLayout() {
  return (
    <>
      <Outlet />
      <SessionExpiredDialog />
    </>
  );
}
