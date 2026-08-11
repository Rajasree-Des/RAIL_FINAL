import { ChevronRight, Home } from "lucide-react";
import { Link } from "react-router-dom";

interface Breadcrumb {
  label: string;
  href?: string;
}

interface PageHeaderProps {
  title: string;
  description?: string;
  breadcrumbs?: Breadcrumb[];
}

export function PageHeader({ title, description, breadcrumbs }: PageHeaderProps) {
  return (
    <div className="mb-8">
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav aria-label="Breadcrumb" className="mb-4">
          <ol className="flex items-center gap-1 text-sm">
            <li>
              <Link
                to="/home"
                className="flex items-center text-slate-400 transition-colors hover:text-slate-600"
              >
                <Home className="h-3.5 w-3.5" />
              </Link>
            </li>
            {breadcrumbs.map((crumb, index) => (
              <li key={index} className="flex items-center gap-1">
                <ChevronRight className="h-3.5 w-3.5 text-slate-300" />
                {crumb.href ? (
                  <Link
                    to={crumb.href}
                    className="text-slate-500 transition-colors hover:text-slate-700"
                  >
                    {crumb.label}
                  </Link>
                ) : (
                  <span className="font-medium text-slate-700">{crumb.label}</span>
                )}
              </li>
            ))}
          </ol>
        </nav>
      )}
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
      {description && (
        <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-slate-500">{description}</p>
      )}
    </div>
  );
}
