import { useSyncExternalStore } from "react";
import {
  getDisplayPrefs,
  subscribeDisplayPrefs,
  type DisplayPrefs,
} from "@/utils/displayPrefs";

/** Reactive display preferences (org name, formats, page size, notifications). */
export function useDisplayPrefs(): DisplayPrefs {
  return useSyncExternalStore(subscribeDisplayPrefs, getDisplayPrefs);
}
