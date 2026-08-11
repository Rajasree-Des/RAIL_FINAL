import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { AuthProvider } from "@/context/AuthContext";
import { WorkflowSessionProvider } from "@/context/WorkflowSessionContext";
import { ToastProvider } from "@/components/ui/Toast";

type ProvidersProps = {
  children: ReactNode;
};

export function Providers({ children }: ProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
          <WorkflowSessionProvider>
            <ToastProvider>{children}</ToastProvider>
          </WorkflowSessionProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
