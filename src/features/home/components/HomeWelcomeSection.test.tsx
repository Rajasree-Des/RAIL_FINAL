import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { HomeWelcomeSection } from "./HomeWelcomeSection";

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: { username: "admin" },
  }),
}));

vi.mock("@/layouts/TopBar", () => ({
  getTimeGreeting: () => "Good Morning",
}));

describe("HomeWelcomeSection date range", () => {
  const defaultProps = {
    isAdmin: true,
    isStarting: false,
    onGenerate: vi.fn(),
    dateFrom: "2026-07-27",
    dateTo: "2026-07-28",
    onDateFromChange: vi.fn(),
    onDateToChange: vi.fn(),
    dateRangeError: null,
  };

  it("renders From Date and To Date inputs for admin", () => {
    render(<HomeWelcomeSection {...defaultProps} />);

    expect(screen.getByLabelText("From Date")).toBeInTheDocument();
    expect(screen.getByLabelText("To Date")).toBeInTheDocument();
  });

  it("does not render date inputs for non-admin", () => {
    render(<HomeWelcomeSection {...defaultProps} isAdmin={false} />);

    expect(screen.queryByLabelText("From Date")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("To Date")).not.toBeInTheDocument();
  });

  it("displays default date values", () => {
    render(<HomeWelcomeSection {...defaultProps} />);

    const fromInput = screen.getByLabelText("From Date") as HTMLInputElement;
    const toInput = screen.getByLabelText("To Date") as HTMLInputElement;

    expect(fromInput.value).toBe("2026-07-27");
    expect(toInput.value).toBe("2026-07-28");
  });

  it("calls onDateFromChange when From Date changes", () => {
    const onDateFromChange = vi.fn();
    render(
      <HomeWelcomeSection {...defaultProps} onDateFromChange={onDateFromChange} />,
    );

    const fromInput = screen.getByLabelText("From Date");
    fireEvent.change(fromInput, { target: { value: "2026-07-20" } });

    expect(onDateFromChange).toHaveBeenCalledWith("2026-07-20");
  });

  it("calls onDateToChange when To Date changes", () => {
    const onDateToChange = vi.fn();
    render(
      <HomeWelcomeSection {...defaultProps} onDateToChange={onDateToChange} />,
    );

    const toInput = screen.getByLabelText("To Date");
    fireEvent.change(toInput, { target: { value: "2026-07-30" } });

    expect(onDateToChange).toHaveBeenCalledWith("2026-07-30");
  });

  it("displays date range error message", () => {
    render(
      <HomeWelcomeSection
        {...defaultProps}
        dateRangeError="From Date must not be after To Date."
      />,
    );

    expect(
      screen.getByText("From Date must not be after To Date."),
    ).toBeInTheDocument();
  });

  it("does not display error when dateRangeError is null", () => {
    render(<HomeWelcomeSection {...defaultProps} dateRangeError={null} />);

    expect(
      screen.queryByText("From Date must not be after To Date."),
    ).not.toBeInTheDocument();
  });

  it("disables Generate button when disabled prop is true", () => {
    render(<HomeWelcomeSection {...defaultProps} disabled={true} />);

    const button = screen.getByRole("button", { name: /Generate/i });
    expect(button).toBeDisabled();
  });

  it("enables Generate button when validation passes", () => {
    render(<HomeWelcomeSection {...defaultProps} disabled={false} />);

    const button = screen.getByRole("button", { name: /Generate/i });
    expect(button).not.toBeDisabled();
  });

  it("calls onGenerate when button is clicked", () => {
    const onGenerate = vi.fn();
    render(<HomeWelcomeSection {...defaultProps} onGenerate={onGenerate} />);

    const button = screen.getByRole("button", { name: /Generate/i });
    fireEvent.click(button);

    expect(onGenerate).toHaveBeenCalled();
  });

  it("shows loading state when isStarting is true", () => {
    render(<HomeWelcomeSection {...defaultProps} isStarting={true} />);

    expect(screen.getByText("Starting generation…")).toBeInTheDocument();
  });
});
