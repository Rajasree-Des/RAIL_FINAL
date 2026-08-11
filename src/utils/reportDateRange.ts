const IST_TIMEZONE = "Asia/Kolkata";

function istCalendarParts(offsetDays = 0): { year: number; month: number; day: number } {
  const now = new Date();
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: IST_TIMEZONE,
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).formatToParts(now);
  const year = Number(parts.find((part) => part.type === "year")?.value ?? 0);
  const month = Number(parts.find((part) => part.type === "month")?.value ?? 0);
  const day = Number(parts.find((part) => part.type === "day")?.value ?? 0);
  const utc = Date.UTC(year, month - 1, day + offsetDays);
  const shifted = new Date(utc);
  return {
    year: shifted.getUTCFullYear(),
    month: shifted.getUTCMonth() + 1,
    day: shifted.getUTCDate(),
  };
}

function toIsoDate({ year, month, day }: { year: number; month: number; day: number }): string {
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function defaultReportDateFrom(): string {
  return toIsoDate(istCalendarParts(-1));
}

export function defaultReportDateTo(): string {
  return toIsoDate(istCalendarParts(0));
}

export function validateReportDateRange(
  dateFrom: string,
  dateTo: string,
): string | null {
  if (!dateFrom.trim() || !dateTo.trim()) {
    return "From Date and To Date are required.";
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateFrom) || !/^\d{4}-\d{2}-\d{2}$/.test(dateTo)) {
    return "Dates must use YYYY-MM-DD format.";
  }
  if (dateFrom > dateTo) {
    return "From Date must not be after To Date.";
  }
  return null;
}

export function formatReportDateLabel(dateFrom: string, dateTo: string): string {
  if (dateFrom === dateTo) {
    return dateFrom.split("-").reverse().join("-");
  }
  return `${dateFrom.split("-").reverse().join("-")} to ${dateTo.split("-").reverse().join("-")}`;
}
