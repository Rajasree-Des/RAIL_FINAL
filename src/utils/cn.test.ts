import { describe, expect, it } from "vitest";
import { cn } from "./cn";

describe("cn utility", () => {
  it("merges class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("handles conditional classes", () => {
    const isHidden = false;
    const isVisible = true;
    expect(cn("base", isHidden && "hidden", isVisible && "visible")).toBe("base visible");
  });

  it("handles arrays", () => {
    expect(cn(["foo", "bar"])).toBe("foo bar");
  });

  it("merges tailwind classes correctly", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
    expect(cn("text-red-500", "text-blue-500")).toBe("text-blue-500");
  });

  it("handles undefined and null", () => {
    expect(cn("foo", undefined, null, "bar")).toBe("foo bar");
  });

  it("handles empty strings", () => {
    expect(cn("foo", "", "bar")).toBe("foo bar");
  });

  it("handles complex tailwind merging", () => {
    expect(cn("p-4 bg-red-500", "p-2 bg-blue-500")).toBe("p-2 bg-blue-500");
  });
});
