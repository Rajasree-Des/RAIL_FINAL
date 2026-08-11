import { Link } from "react-router-dom";
import { Home, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/Button";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-surface px-4">
      <div className="text-center">
        <p className="text-6xl font-bold text-primary">404</p>
        <h1 className="mt-4 text-2xl font-semibold text-slate-900">Page not found</h1>
        <p className="mt-2 text-base text-slate-600">
          Sorry, we couldn&apos;t find the page you&apos;re looking for.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Button variant="primary" asChild>
            <Link to="/home">
              <Home size={16} />
              Go to Home
            </Link>
          </Button>
          <Button variant="secondary" onClick={() => window.history.back()}>
            <ArrowLeft size={16} />
            Go Back
          </Button>
        </div>
      </div>
    </div>
  );
}
