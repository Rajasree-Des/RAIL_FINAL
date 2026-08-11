import { Spinner } from "@/components/ui/Spinner";

interface LoadingOverlayProps {
  message?: string;
  progress?: number;
}

export function LoadingOverlay({
  message = "Loading...",
  progress,
}: LoadingOverlayProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/80 backdrop-blur-sm">
      <div className="flex flex-col items-center gap-4">
        <Spinner size="lg" />
        <p className="text-sm font-medium text-slate-700">{message}</p>
        {progress !== undefined && (
          <div className="w-48">
            <div className="h-2 overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
              />
            </div>
            <p className="mt-1 text-center text-xs text-slate-500">{progress}%</p>
          </div>
        )}
      </div>
    </div>
  );
}
