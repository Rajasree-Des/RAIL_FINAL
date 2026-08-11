/**
 * App-wide notification runtime.
 *
 * Mounted once in AppShell: listens to the live activity stream and, based on
 * notification settings, shows in-app toasts and optional Web Audio tones.
 */

import { useEffect, useRef } from "react";
import { subscribeActivity } from "@/api/activity";
import { useToast } from "@/components/ui/Toast";
import { getDisplayPrefs } from "@/utils/displayPrefs";
import {
  createNotificationCoordinatorState,
  disposeNotificationCoordinatorState,
  handleNotificationActivity,
} from "./notificationHandler";
import {
  playCompletionSound,
  playFailureSound,
} from "./notificationSounds";

export function useNotificationRuntime(): void {
  const { showToast } = useToast();
  const coordinatorRef = useRef(createNotificationCoordinatorState());

  useEffect(() => {
    coordinatorRef.current = createNotificationCoordinatorState();
    const coordinator = coordinatorRef.current;

    const subscription = subscribeActivity({
      onEvent: (entry) => {
        handleNotificationActivity(
          entry,
          getDisplayPrefs().notifications,
          {
            showToast,
            playCompletionSound,
            playFailureSound,
          },
          coordinator,
        );
      },
    });

    return () => {
      subscription.close();
      disposeNotificationCoordinatorState(coordinator);
    };
  }, [showToast]);
}
