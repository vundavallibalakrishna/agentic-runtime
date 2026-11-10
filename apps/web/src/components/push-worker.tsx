"use client";

import { useEffect } from "react";

/** Register the service worker that displays Web Push notifications. */
export function PushWorker() {
  useEffect(() => {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) {
      return;
    }
    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  }, []);
  return null;
}
