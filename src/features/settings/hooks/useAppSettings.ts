import { useCallback, useEffect, useMemo, useState } from "react";
import {
  settingsApi,
  type SettingCategory,
  type SettingItem,
  type SettingUpdateItem,
} from "@/api/settings";
import { useToast } from "@/components/ui/Toast";
import { unlockNotificationAudio } from "@/features/notifications/notificationSounds";
import { loadDisplayPrefs } from "@/utils/displayPrefs";

function buildDraftMap(categories: SettingCategory[]): Record<string, unknown> {
  const draft: Record<string, unknown> = {};
  for (const cat of categories) {
    for (const setting of cat.settings) {
      draft[`${cat.slug}.${setting.key}`] = setting.value;
    }
  }
  return draft;
}

function buildUpdates(
  categories: SettingCategory[],
  draft: Record<string, unknown>,
): SettingUpdateItem[] {
  const updates: SettingUpdateItem[] = [];
  for (const cat of categories) {
    for (const setting of cat.settings) {
      const compound = `${cat.slug}.${setting.key}`;
      const draftValue = draft[compound];
      const original = JSON.stringify(setting.value);
      const current = JSON.stringify(draftValue);
      if (original !== current) {
        updates.push({
          category: cat.slug,
          key: setting.key,
          value: draftValue,
        });
      }
    }
  }
  return updates;
}

export function useAppSettings(activeCategory?: string | null, searchQuery?: string) {
  const { showToast } = useToast();
  const [categories, setCategories] = useState<SettingCategory[]>([]);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await settingsApi.get({
        category: activeCategory ?? undefined,
        search: searchQuery || undefined,
      });
      setCategories(response.categories);
      setDraft(buildDraftMap(response.categories));
    } catch {
      setError("Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, [activeCategory, searchQuery]);

  useEffect(() => {
    void load();
  }, [load]);

  const hasChanges = useMemo(() => {
    return buildUpdates(categories, draft).length > 0;
  }, [categories, draft]);

  const setValue = useCallback((category: string, key: string, value: unknown) => {
    setDraft((prev) => ({ ...prev, [`${category}.${key}`]: value }));
  }, []);

  const getValue = useCallback(
    (category: string, key: string) => draft[`${category}.${key}`],
    [draft],
  );

  const save = useCallback(async () => {
    const updates = buildUpdates(categories, draft);
    if (updates.length === 0) {
      showToast("info", "No changes to save");
      return;
    }
    setSaving(true);
    try {
      await settingsApi.update(updates);
      showToast("success", "Settings saved");
      if (Boolean(draft["notifications.notification_sound"])) {
        unlockNotificationAudio();
      }
      await load();
      void loadDisplayPrefs();
    } catch {
      showToast("error", "Failed to save settings");
    } finally {
      setSaving(false);
    }
  }, [categories, draft, load, showToast]);

  const resetCategory = useCallback(
    async (category: string) => {
      setSaving(true);
      try {
        await settingsApi.resetCategory(category);
        showToast("success", "Category reset to defaults");
        await load();
        void loadDisplayPrefs();
      } catch {
        showToast("error", "Failed to reset category");
      } finally {
        setSaving(false);
      }
    },
    [load, showToast],
  );

  const exportSettings = useCallback(async () => {
    try {
      const data = await settingsApi.export();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `app-settings-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showToast("success", "Settings exported");
    } catch {
      showToast("error", "Export failed");
    }
  }, [showToast]);

  const importSettings = useCallback(
    async (file: File) => {
      try {
        const text = await file.text();
        const parsed = JSON.parse(text) as {
          settings?: Record<string, unknown>;
          merge?: boolean;
        };
        if (!parsed.settings) {
          showToast("error", "Invalid settings file");
          return;
        }
        const result = await settingsApi.import({
          settings: parsed.settings,
          merge: parsed.merge ?? true,
        });
        if (result.errors.length > 0) {
          showToast(
            "warning",
            `Imported ${result.imported}, skipped ${result.skipped}`,
          );
        } else {
          showToast("success", `Imported ${result.imported} settings`);
        }
        await load();
        void loadDisplayPrefs();
      } catch {
        showToast("error", "Import failed");
      }
    },
    [load, showToast],
  );

  return {
    categories,
    draft,
    loading,
    saving,
    error,
    hasChanges,
    setValue,
    getValue,
    save,
    resetCategory,
    exportSettings,
    importSettings,
    reload: load,
  };
}

export type { SettingItem, SettingCategory };
