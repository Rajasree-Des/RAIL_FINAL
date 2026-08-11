import { createContext, useContext, type ReactNode } from "react";
import { cn } from "@/utils/cn";

interface TabsContextValue {
  value: string;
  onValueChange: (value: string) => void;
}

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabsContext() {
  const context = useContext(TabsContext);
  if (!context) {
    throw new Error("Tabs components must be used within a Tabs provider");
  }
  return context;
}

interface TabsProps {
  value: string;
  onValueChange: (value: string) => void;
  children: ReactNode;
  className?: string;
}

export function Tabs({ value, onValueChange, children, className }: TabsProps) {
  return (
    <TabsContext.Provider value={{ value, onValueChange }}>
      <div className={cn("w-full", className)}>{children}</div>
    </TabsContext.Provider>
  );
}

interface TabsListProps {
  children: ReactNode;
  className?: string;
}

export function TabsList({ children, className }: TabsListProps) {
  return (
    <div
      className={cn(
        "inline-flex h-10 items-center justify-start rounded-lg bg-slate-100 p-1",
        className,
      )}
      role="tablist"
    >
      {children}
    </div>
  );
}

interface TabsTriggerProps {
  value: string;
  children: ReactNode;
  className?: string;
  disabled?: boolean;
}

export function TabsTrigger({ value, children, className, disabled }: TabsTriggerProps) {
  const context = useTabsContext();
  const isActive = context.value === value;

  return (
    <button
      type="button"
      role="tab"
      aria-selected={isActive}
      disabled={disabled}
      onClick={() => context.onValueChange(value)}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-all",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2",
        "disabled:pointer-events-none disabled:opacity-50",
        isActive
          ? "bg-white text-slate-900 shadow-sm"
          : "text-slate-500 hover:text-slate-900",
        className,
      )}
    >
      {children}
    </button>
  );
}

interface TabsContentProps {
  value: string;
  children: ReactNode;
  className?: string;
}

export function TabsContent({ value, children, className }: TabsContentProps) {
  const context = useTabsContext();

  if (context.value !== value) {
    return null;
  }

  return (
    <div
      role="tabpanel"
      className={cn("mt-2 focus-visible:outline-none", className)}
    >
      {children}
    </div>
  );
}

interface SimpleTabsProps {
  tabs: string[];
  active: string;
  onChange: (tab: string) => void;
}

export function SimpleTabs({ tabs, active, onChange }: SimpleTabsProps) {
  return (
    <div
      className="border-b border-slate-200"
      role="tablist"
      aria-label="Output tabs"
    >
      <div className="flex gap-1">
        {tabs.map((tab) => {
          const isActive = active === tab;
          return (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls={`tabpanel-${tab.toLowerCase().replace(/\s+/g, "-")}`}
              onClick={() => onChange(tab)}
              className={cn(
                "relative px-4 py-2.5 text-sm font-medium",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2",
                isActive
                  ? "text-primary"
                  : "text-slate-500 hover:text-slate-700",
              )}
            >
              {tab}
              {isActive ? (
                <span
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary"
                  aria-hidden="true"
                />
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
