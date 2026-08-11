import { useState } from "react";
import { Play } from "lucide-react";
import { summaryApi } from "@/api/summary";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Textarea";
import { Spinner } from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/Toast";

const SAMPLE_DATASET = [
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
    division: "HYB",
    train_number: "12616",
    complaint_type: "Water Supply",
    complaint_count: 32,
    status: "Pending",
    resolved_count: 20,
    unsatisfactory_count: 5,
  },
];

interface PromptTestPanelProps {
  templateId: string;
}

export function PromptTestPanel({ templateId }: PromptTestPanelProps) {
  const { showToast } = useToast();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string>("");
  const [renderedPrompt, setRenderedPrompt] = useState<string>("");

  async function handleTest() {
    setLoading(true);
    try {
      const response = await summaryApi.testTemplate(templateId, {
        sample_dataset: SAMPLE_DATASET,
        sample_metadata: {
          report_name: "Test Report",
          report_period: new Date().toISOString().split("T")[0],
        },
      });
      setResult(response.content);
      setRenderedPrompt(response.rendered_user_prompt);
      showToast("success", "Test completed", `${response.generation_time_ms.toFixed(0)}ms`);
    } catch {
      showToast("error", "Test failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Test Prompt</CardTitle>
            <Button onClick={handleTest} disabled={loading}>
              {loading ? (
                <Spinner size="sm" />
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4" />
                  Run Test
                </>
              )}
            </Button>
          </div>
          <p className="text-sm text-slate-500">
            Tests with sample dataset ({SAMPLE_DATASET.length} rows). Uses mock LLM if no API key.
          </p>
        </CardHeader>
        <CardBody className="space-y-4">
          {renderedPrompt ? (
            <div>
              <p className="mb-2 text-sm font-medium text-slate-700">Rendered User Prompt</p>
              <Textarea
                readOnly
                value={renderedPrompt}
                className="min-h-32 font-mono text-xs bg-slate-50"
              />
            </div>
          ) : null}
          {result ? (
            <div>
              <p className="mb-2 text-sm font-medium text-slate-700">Generated Output</p>
              <Textarea readOnly value={result} className="min-h-48 bg-slate-50" />
            </div>
          ) : null}
        </CardBody>
      </Card>
    </div>
  );
}
