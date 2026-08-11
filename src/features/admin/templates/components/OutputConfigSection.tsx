import type { ElementType, ReactNode } from "react";
import { FileSpreadsheet, FileText, Bot, MessageCircle, Mail } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Textarea } from "@/components/ui/Textarea";

interface OutputConfig {
  excel_enabled: boolean;
  excel_config: Record<string, unknown>;
  pdf_enabled: boolean;
  pdf_config: Record<string, unknown>;
  ai_summary_enabled: boolean;
  ai_config: Record<string, unknown>;
  whatsapp_enabled: boolean;
  whatsapp_config: Record<string, unknown>;
  email_enabled: boolean;
  email_config: Record<string, unknown>;
}

interface OutputConfigSectionProps {
  data: OutputConfig;
  onChange: (data: OutputConfig) => void;
}

interface OutputOptionProps {
  icon: ElementType;
  title: string;
  description: string;
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  children?: ReactNode;
}

function OutputOption({
  icon: Icon,
  title,
  description,
  enabled,
  onToggle,
  children,
}: OutputOptionProps) {
  return (
    <div className={`rounded-lg border ${enabled ? "border-primary/20 bg-primary/5" : "border-rail-line bg-white"} p-4`}>
      <div className="flex items-start gap-4">
        <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${enabled ? "bg-primary/10 text-primary" : "bg-slate-100 text-slate-500"}`}>
          <Icon className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="font-medium text-slate-900">{title}</h4>
              <p className="text-sm text-slate-500">{description}</p>
            </div>
            <label className="relative inline-flex cursor-pointer items-center">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => onToggle(e.target.checked)}
                className="peer sr-only"
              />
              <div className="peer h-6 w-11 rounded-full bg-slate-200 after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-all peer-checked:bg-primary peer-checked:after:translate-x-full"></div>
            </label>
          </div>
          {enabled && children && <div className="mt-4 border-t border-slate-200 pt-4">{children}</div>}
        </div>
      </div>
    </div>
  );
}

export function OutputConfigSection({ data, onChange }: OutputConfigSectionProps) {
  const updateConfig = <K extends keyof OutputConfig>(key: K, value: OutputConfig[K]) => {
    onChange({ ...data, [key]: value });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Output Configuration</CardTitle>
        <CardDescription>Configure output formats and delivery options</CardDescription>
      </CardHeader>
      <CardBody>
        <div className="space-y-4">
          <OutputOption
            icon={FileSpreadsheet}
            title="Excel Output"
            description="Generate Excel (.xlsx) file"
            enabled={data.excel_enabled}
            onToggle={(enabled) => updateConfig("excel_enabled", enabled)}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="excel_sheet_name">Sheet Name</Label>
                <Input
                  id="excel_sheet_name"
                  value={(data.excel_config.sheet_name as string) || ""}
                  onChange={(e) =>
                    updateConfig("excel_config", {
                      ...data.excel_config,
                      sheet_name: e.target.value,
                    })
                  }
                  placeholder="Report Data"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Options</Label>
                <div className="space-y-2">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={(data.excel_config.freeze_header as boolean) || false}
                      onChange={(e) =>
                        updateConfig("excel_config", {
                          ...data.excel_config,
                          freeze_header: e.target.checked,
                        })
                      }
                      className="h-4 w-4 rounded border-slate-300"
                    />
                    <span className="text-sm">Freeze header row</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={(data.excel_config.auto_filter as boolean) || false}
                      onChange={(e) =>
                        updateConfig("excel_config", {
                          ...data.excel_config,
                          auto_filter: e.target.checked,
                        })
                      }
                      className="h-4 w-4 rounded border-slate-300"
                    />
                    <span className="text-sm">Enable auto-filter</span>
                  </label>
                </div>
              </div>
            </div>
          </OutputOption>

          <OutputOption
            icon={FileText}
            title="PDF Output"
            description="Generate PDF document"
            enabled={data.pdf_enabled}
            onToggle={(enabled) => updateConfig("pdf_enabled", enabled)}
          >
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label htmlFor="pdf_page_size">Page Size</Label>
                <select
                  id="pdf_page_size"
                  value={(data.pdf_config.page_size as string) || "A4"}
                  onChange={(e) =>
                    updateConfig("pdf_config", {
                      ...data.pdf_config,
                      page_size: e.target.value,
                    })
                  }
                  className="flex h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                >
                  <option value="A4">A4</option>
                  <option value="A3">A3</option>
                  <option value="Letter">Letter</option>
                  <option value="Legal">Legal</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="pdf_orientation">Orientation</Label>
                <select
                  id="pdf_orientation"
                  value={(data.pdf_config.orientation as string) || "portrait"}
                  onChange={(e) =>
                    updateConfig("pdf_config", {
                      ...data.pdf_config,
                      orientation: e.target.value,
                    })
                  }
                  className="flex h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                >
                  <option value="portrait">Portrait</option>
                  <option value="landscape">Landscape</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <Label>Options</Label>
                <label className="flex items-center gap-2 mt-2">
                  <input
                    type="checkbox"
                    checked={(data.pdf_config.include_header as boolean) || false}
                    onChange={(e) =>
                      updateConfig("pdf_config", {
                        ...data.pdf_config,
                        include_header: e.target.checked,
                      })
                    }
                    className="h-4 w-4 rounded border-slate-300"
                  />
                  <span className="text-sm">Include header</span>
                </label>
              </div>
            </div>
          </OutputOption>

          <OutputOption
            icon={Bot}
            title="AI Summary"
            description="Generate AI-powered summary of the report"
            enabled={data.ai_summary_enabled}
            onToggle={(enabled) => updateConfig("ai_summary_enabled", enabled)}
          >
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="ai_prompt">Summary Prompt Template</Label>
                <Textarea
                  id="ai_prompt"
                  value={(data.ai_config.prompt_template as string) || ""}
                  onChange={(e) =>
                    updateConfig("ai_config", {
                      ...data.ai_config,
                      prompt_template: e.target.value,
                    })
                  }
                  placeholder="Summarize the following report data, highlighting key trends and anomalies..."
                  rows={3}
                />
              </div>
            </div>
          </OutputOption>

          <OutputOption
            icon={MessageCircle}
            title="WhatsApp Delivery"
            description="Send report via WhatsApp"
            enabled={data.whatsapp_enabled}
            onToggle={(enabled) => updateConfig("whatsapp_enabled", enabled)}
          >
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="whatsapp_recipients">Recipients (comma-separated)</Label>
                <Input
                  id="whatsapp_recipients"
                  value={(data.whatsapp_config.recipients as string) || ""}
                  onChange={(e) =>
                    updateConfig("whatsapp_config", {
                      ...data.whatsapp_config,
                      recipients: e.target.value,
                    })
                  }
                  placeholder="+91XXXXXXXXXX, +91XXXXXXXXXX"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="whatsapp_message">Message Template</Label>
                <Textarea
                  id="whatsapp_message"
                  value={(data.whatsapp_config.message_template as string) || ""}
                  onChange={(e) =>
                    updateConfig("whatsapp_config", {
                      ...data.whatsapp_config,
                      message_template: e.target.value,
                    })
                  }
                  placeholder="Report generated: {{report_name}} - {{date}}"
                  rows={2}
                />
              </div>
            </div>
          </OutputOption>

          <OutputOption
            icon={Mail}
            title="Email Delivery"
            description="Send report via email"
            enabled={data.email_enabled}
            onToggle={(enabled) => updateConfig("email_enabled", enabled)}
          >
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="email_recipients">Recipients (comma-separated)</Label>
                <Input
                  id="email_recipients"
                  value={(data.email_config.recipients as string) || ""}
                  onChange={(e) =>
                    updateConfig("email_config", {
                      ...data.email_config,
                      recipients: e.target.value,
                    })
                  }
                  placeholder="user@example.com, user2@example.com"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="email_subject">Subject Template</Label>
                <Input
                  id="email_subject"
                  value={(data.email_config.subject_template as string) || ""}
                  onChange={(e) =>
                    updateConfig("email_config", {
                      ...data.email_config,
                      subject_template: e.target.value,
                    })
                  }
                  placeholder="{{report_name}} Report - {{date}}"
                />
              </div>
            </div>
          </OutputOption>
        </div>
      </CardBody>
    </Card>
  );
}
