import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SectionedPreviewTable } from "@/components/workflow/SectionedPreviewTable";
import type { SectionPreview } from "@/api/reports";

const sections: SectionPreview[] = [
  { title: "Security", headers: ["Train Name", "Received"], rows: [["A", "10"]], empty: false },
  { title: "Coach Cleanliness", headers: ["Train Name", "Received"], rows: [], empty: true },
  { title: "Bedroll", headers: ["Train Name", "Received"], rows: [["B", "5"]], empty: false },
  { title: "Water Availability", headers: ["Train Name", "Received"], rows: [], empty: false },
  { title: "Electrical Equipment", headers: ["Train Name", "Received"], rows: [], empty: false },
  { title: "Catering and Vending Services", headers: ["Train Name", "Received"], rows: [], empty: false },
  { title: "Coach Maintenance", headers: ["Train Name", "Received"], rows: [], empty: false },
];

describe("SectionedPreviewTable", () => {
  it("renders all seven section headings", () => {
    render(<SectionedPreviewTable sections={sections} />);
    for (const section of sections) {
      expect(screen.getByText(section.title)).toBeInTheDocument();
    }
  });
});
