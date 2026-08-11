import type { ReactNode } from "react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";

type WorkflowSectionCardProps = {
  title: string;
  description?: string;
  children: ReactNode;
  action?: ReactNode;
  id?: string;
};

export function WorkflowSectionCard({
  title,
  description,
  children,
  action,
  id,
}: WorkflowSectionCardProps) {
  const headingId = id ? `${id}-heading` : undefined;

  return (
    <Card aria-labelledby={headingId}>
      <CardHeader>
        <div>
          <CardTitle id={headingId}>{title}</CardTitle>
          {description ? (
            <p className="mt-0.5 text-sm text-slate-500">{description}</p>
          ) : null}
        </div>
        {action}
      </CardHeader>
      <CardBody>{children}</CardBody>
    </Card>
  );
}
