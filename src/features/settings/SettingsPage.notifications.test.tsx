import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { SettingsPage } from "./SettingsPage";

vi.mock("@/hooks/usePermissions", () => ({
  usePermissions: () => ({ canManageSettings: true }),
}));

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: { username: "admin", email: "admin@example.com", role: "admin" },
    clearSession: vi.fn(),
  }),
}));

vi.mock("@/features/notifications/notificationSounds", () => ({
  unlockNotificationAudio: vi.fn(),
}));

const mockSave = vi.fn();
const mockSetValue = vi.fn();
const mockGetValue = vi.fn((category: string, key: string) => {
  const values: Record<string, unknown> = {
    "notifications.enable_notifications": true,
    "notifications.notify_on_completion": true,
    "notifications.notify_on_failure": true,
    "notifications.notification_sound": false,
  };
  return values[`${category}.${key}`];
});

vi.mock("@/features/settings/hooks/useAppSettings", () => ({
  useAppSettings: () => ({
    categories: [
      {
        slug: "notifications",
        label: "Notifications",
        description: "Alerts",
        settings: [
          {
            id: "1",
            category: "notifications",
            key: "enable_notifications",
            label: "Enable Notifications",
            description: null,
            value_type: "boolean",
            value: true,
            default_value: true,
            validation: null,
            options: null,
            sort_order: 1,
            is_editable: true,
            is_modified: false,
          },
          {
            id: "2",
            category: "notifications",
            key: "notify_on_completion",
            label: "Notify on Report Completion",
            description: null,
            value_type: "boolean",
            value: true,
            default_value: true,
            validation: null,
            options: null,
            sort_order: 2,
            is_editable: true,
            is_modified: false,
          },
          {
            id: "3",
            category: "notifications",
            key: "notify_on_failure",
            label: "Notify on Report Failure",
            description: null,
            value_type: "boolean",
            value: true,
            default_value: true,
            validation: null,
            options: null,
            sort_order: 3,
            is_editable: true,
            is_modified: false,
          },
          {
            id: "4",
            category: "notifications",
            key: "notification_sound",
            label: "Notification Sound",
            description: null,
            value_type: "boolean",
            value: false,
            default_value: false,
            validation: null,
            options: null,
            sort_order: 4,
            is_editable: true,
            is_modified: false,
          },
        ],
      },
    ],
    loading: false,
    saving: false,
    error: null,
    hasChanges: false,
    getValue: mockGetValue,
    setValue: mockSetValue,
    save: mockSave,
    resetCategory: vi.fn(),
    exportSettings: vi.fn(),
    importSettings: vi.fn(),
    reload: vi.fn(),
  }),
}));

vi.mock("@/components/ui/Toast", () => ({
  useToast: () => ({ showToast: vi.fn() }),
}));

function renderSettingsPage() {
  return render(
    <BrowserRouter>
      <SettingsPage />
    </BrowserRouter>,
  );
}

describe("SettingsPage notifications", () => {
  beforeEach(() => {
    mockGetValue.mockImplementation((category: string, key: string) => {
      const values: Record<string, unknown> = {
        "notifications.enable_notifications": true,
        "notifications.notify_on_completion": true,
        "notifications.notify_on_failure": true,
        "notifications.notification_sound": false,
      };
      return values[`${category}.${key}`];
    });
  });

  it("does not render coming soon or extra channel placeholders", () => {
    renderSettingsPage();
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));

    expect(screen.queryByText("More Channels")).not.toBeInTheDocument();
    expect(screen.queryByText("Email notifications")).not.toBeInTheDocument();
    expect(screen.queryByText("WhatsApp notifications")).not.toBeInTheDocument();
    expect(screen.queryByText("Coming Soon")).not.toBeInTheDocument();
    expect(screen.queryByText("Desktop Notifications")).not.toBeInTheDocument();
  });

  it("disables child toggles when master notifications are off", () => {
    mockGetValue.mockImplementation((category: string, key: string) => {
      if (category === "notifications" && key === "enable_notifications") return false;
      return true;
    });

    renderSettingsPage();
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));

    expect(screen.getByLabelText("Notify on Report Completion")).toBeDisabled();
    expect(screen.getByLabelText("Notify on Report Failure")).toBeDisabled();
    expect(screen.getByLabelText("Notification Sound")).toBeDisabled();
  });
});
