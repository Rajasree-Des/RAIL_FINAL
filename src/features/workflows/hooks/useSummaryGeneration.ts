import { useCallback, useEffect, useState } from "react";
import {
  summaryApi,
  SUMMARY_TYPE_LABELS,
  type GeneratedSummaryResult,
  type PromptTemplateListItem,
  type SummaryType,
} from "@/api/summary";
import { useToast } from "@/components/ui/Toast";
import { useWorkflowSession } from "@/context/WorkflowSessionContext";
import type { GeneratedSummary, ReportSourceId } from "@/types/workflow";

const REPORT_OPTIONS: { id: ReportSourceId; label: string }[] = [
  { id: "division", label: "Division Report" },
  { id: "train", label: "Train Report" },
  { id: "types", label: "Type Report" },
  { id: "scr-train", label: "SCR Train" },
  { id: "scr-station", label: "SCR Station" },
];

const SUMMARY_TYPES: SummaryType[] = [
  "executive",
  "whatsapp",
  "email",
  "daily_highlights",
  "key_observations",
];

function buildSampleDataset(): Record<string, unknown>[] {
  return [
    {
      division: "SCR",
      train_number: "12724",
      complaint_type: "Electrical Equipment",
      complaint_count: 45,
      status: "Resolved",
      resolved_count: 38,
      unsatisfactory_count: 3,
    },
    {
      division: "SCR",
      train_number: "12616",
      complaint_type: "Water Supply",
      complaint_count: 32,
      status: "Pending",
      resolved_count: 20,
      unsatisfactory_count: 5,
    },
    {
      division: "HYB",
      train_number: "17233",
      complaint_type: "Cleanliness",
      complaint_count: 28,
      status: "Resolved",
      resolved_count: 25,
      unsatisfactory_count: 2,
    },
    {
      division: "SC",
      train_number: "12704",
      complaint_type: "Electrical Equipment",
      complaint_count: 22,
      status: "Closed",
      resolved_count: 22,
      unsatisfactory_count: 1,
    },
    {
      division: "SCR",
      train_number: "12713",
      complaint_type: "Food Quality",
      complaint_count: 15,
      status: "Pending",
      resolved_count: 8,
      unsatisfactory_count: 4,
    },
  ];
}

function mapResultToSection(
  summaries: Partial<Record<SummaryType, GeneratedSummaryResult>>,
): GeneratedSummary | null {
  if (Object.keys(summaries).length === 0) return null;
  const first = Object.values(summaries)[0];
  return {
    id: first?.id ?? "",
    executive: summaries.executive?.content ?? "",
    whatsapp: summaries.whatsapp?.content ?? "",
    email: summaries.email?.content ?? "",
    dailyHighlights: summaries.daily_highlights?.content ?? "",
    keyObservations: summaries.key_observations?.content ?? "",
    statistics: first?.statistics as unknown as Record<string, unknown>,
    generatedAt: first?.created_at,
  };
}

export function useSummaryGeneration() {
  const { completedReports, generatedSummary, setGeneratedSummary } =
    useWorkflowSession();
  const { showToast } = useToast();

  const [selected, setSelected] = useState<ReportSourceId[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [templates, setTemplates] = useState<PromptTemplateListItem[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("");
  const [selectedSummaryType, setSelectedSummaryType] =
    useState<SummaryType>("executive");
  const [sectionResults, setSectionResults] = useState<
    Partial<Record<SummaryType, GeneratedSummaryResult>>
  >({});

  useEffect(() => {
    summaryApi
      .listTemplates({ is_enabled: true })
      .then((res) => setTemplates(res.templates))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setSelected((current) => {
      const fromSession = REPORT_OPTIONS.filter((o) =>
        completedReports.has(o.id),
      ).map((o) => o.id);
      const merged = new Set([
        ...current.filter((id) => completedReports.has(id)),
        ...fromSession,
      ]);
      return Array.from(merged);
    });
  }, [completedReports]);

  const toggleReport = useCallback(
    (id: ReportSourceId) => {
      if (!completedReports.has(id)) return;
      setSelected((current) =>
        current.includes(id)
          ? current.filter((item) => item !== id)
          : [...current, id],
      );
    },
    [completedReports],
  );

  const generateOne = useCallback(
    async (summaryType: SummaryType, regenerate = false) => {
      const reportNames = selected
        .map((id) => REPORT_OPTIONS.find((o) => o.id === id)?.label ?? id)
        .join(", ");

      const payload = {
        summary_type: summaryType,
        prompt_template_id: selectedTemplateId || undefined,
        dataset: buildSampleDataset(),
        metadata: {
          report_name: "Railway Intelligence Summary",
          report_period: new Date().toISOString().split("T")[0],
          included_reports: reportNames ? reportNames.split(", ") : [],
        },
        regenerate,
      };

      return summaryApi.generate(payload);
    },
    [selected, selectedTemplateId],
  );

  const handleGenerate = useCallback(async () => {
    if (selected.length === 0) {
      showToast("warning", "Select reports", "Choose at least one completed report.");
      return;
    }

    setIsGenerating(true);
    try {
      const typesToGenerate = selectedTemplateId
        ? [selectedSummaryType]
        : SUMMARY_TYPES;

      const results: Partial<Record<SummaryType, GeneratedSummaryResult>> = {};

      for (const type of typesToGenerate) {
        const result = await generateOne(type);
        results[type] = result;
      }

      setSectionResults(results);
      const mapped = mapResultToSection(results);
      setGeneratedSummary(mapped);
      showToast("success", "Summary generated");
    } catch {
      showToast("error", "Generation failed", "Could not generate summary.");
    } finally {
      setIsGenerating(false);
    }
  }, [
    selected,
    selectedTemplateId,
    selectedSummaryType,
    generateOne,
    setGeneratedSummary,
    showToast,
  ]);

  const handleRegenerate = useCallback(
    async (summaryType: SummaryType) => {
      setIsGenerating(true);
      try {
        const result = await generateOne(summaryType, true);
        setSectionResults((prev) => {
          const next = { ...prev, [summaryType]: result };
          setGeneratedSummary(mapResultToSection(next));
          return next;
        });
        showToast("success", "Regenerated", SUMMARY_TYPE_LABELS[summaryType]);
      } catch {
        showToast("error", "Regeneration failed");
      } finally {
        setIsGenerating(false);
      }
    },
    [generateOne, setGeneratedSummary, showToast],
  );

  const handleReset = useCallback(() => {
    setSelected(Array.from(completedReports));
    setGeneratedSummary(null);
    setSectionResults({});
  }, [completedReports, setGeneratedSummary]);

  const handleCopy = useCallback(
    async (text: string) => {
      await navigator.clipboard.writeText(text);
      showToast("success", "Copied to clipboard");
    },
    [showToast],
  );

  const handleDownload = useCallback(
    (content: string, filename: string) => {
      const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      showToast("success", "Download started");
    },
    [showToast],
  );

  const handleDownloadAll = useCallback(() => {
    if (!generatedSummary) return;
    const content = [
      "=== EXECUTIVE SUMMARY ===",
      generatedSummary.executive,
      "",
      "=== WHATSAPP SUMMARY ===",
      generatedSummary.whatsapp,
      "",
      "=== OFFICIAL EMAIL ===",
      generatedSummary.email,
      "",
      "=== DAILY HIGHLIGHTS ===",
      generatedSummary.dailyHighlights,
      "",
      "=== KEY OBSERVATIONS ===",
      generatedSummary.keyObservations,
    ].join("\n");
    handleDownload(content, "railway-summary.txt");
  }, [generatedSummary, handleDownload]);

  return {
    reportOptions: REPORT_OPTIONS,
    selected,
    completedReports,
    generatedSummary,
    sectionResults,
    isGenerating,
    templates,
    selectedTemplateId,
    setSelectedTemplateId,
    selectedSummaryType,
    setSelectedSummaryType,
    summaryTypes: SUMMARY_TYPES,
    summaryTypeLabels: SUMMARY_TYPE_LABELS,
    toggleReport,
    handleGenerate,
    handleRegenerate,
    handleReset,
    handleCopy,
    handleDownload,
    handleDownloadAll,
  };
}
