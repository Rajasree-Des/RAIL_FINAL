import { useEffect, useState } from "react";
import { automationApi } from "@/api/automation";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";

export interface PdfPreviewModalProps {
  /** Authenticated API preview URL (relative or absolute). */
  apiUrl: string | null;
  onClose: () => void;
  title?: string;
}

export function PdfPreviewModal({
  apiUrl,
  onClose,
  title = "PDF Review",
}: PdfPreviewModalProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiUrl) {
      setBlobUrl(null);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    let objectUrl: string | null = null;

    const loadPreview = async () => {
      setLoading(true);
      setError(null);
      setBlobUrl(null);
      try {
        objectUrl = await automationApi.fetchPreviewBlobUrl(apiUrl);
        if (cancelled) {
          URL.revokeObjectURL(objectUrl);
          return;
        }
        setBlobUrl(objectUrl);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load PDF preview");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadPreview();

    return () => {
      cancelled = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [apiUrl]);

  if (!apiUrl) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="text-sm font-semibold leading-snug break-words text-slate-900">{title}</h2>
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
        <div className="relative flex flex-1 flex-col">
          {loading ? (
            <div className="flex flex-1 items-center justify-center">
              <Spinner size="lg" className="text-slate-400" />
            </div>
          ) : null}
          {error ? (
            <div className="flex flex-1 items-center justify-center px-4">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          ) : null}
          {blobUrl ? (
            <iframe title="PDF preview" src={blobUrl} className="h-full w-full flex-1" />
          ) : null}
        </div>
      </div>
    </div>
  );
}
