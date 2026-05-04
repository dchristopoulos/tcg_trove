(() => {
  const endpoint = "/api/ux-events";
  const queue = [];
  let flushTimer = null;
  let hasSentPageView = false;
  let clsValue = 0;
  let inpValue = 0;

  function enqueue(event) {
    queue.push({
      ...event,
      path: window.location.pathname,
      ts: Date.now(),
    });
    scheduleFlush();
  }

  function scheduleFlush() {
    if (flushTimer) return;
    flushTimer = window.setTimeout(flush, 2500);
  }

  function flush() {
    if (!queue.length) {
      flushTimer = null;
      return;
    }
    const payload = JSON.stringify({ events: queue.splice(0, 25) });
    flushTimer = null;
    if (navigator.sendBeacon) {
      navigator.sendBeacon(endpoint, new Blob([payload], { type: "application/json" }));
      return;
    }
    fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
      keepalive: true,
      credentials: "same-origin",
    }).catch(() => {});
  }

  function sendPageView() {
    if (hasSentPageView) return;
    hasSentPageView = true;
    enqueue({
      name: "page_view",
      value: performance.now(),
      unit: "ms",
      severity: "info",
      meta: { title: document.title.slice(0, 120) },
    });
  }

  window.addEventListener("load", sendPageView, { once: true });
  window.addEventListener("beforeunload", flush);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      flush();
    }
  });

  window.addEventListener("error", (event) => {
    enqueue({
      name: "frontend_error",
      severity: "high",
      meta: {
        message: String(event.message || "").slice(0, 220),
        source: String(event.filename || "").slice(0, 220),
        line: event.lineno || 0,
        col: event.colno || 0,
      },
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    enqueue({
      name: "unhandled_rejection",
      severity: "high",
      meta: { reason: String(event.reason || "").slice(0, 220) },
    });
  });

  if ("PerformanceObserver" in window) {
    try {
      new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const entry = entries[entries.length - 1];
        if (!entry) return;
        enqueue({ name: "web_vital_lcp", value: Math.round(entry.startTime), unit: "ms", severity: "info" });
      }).observe({ type: "largest-contentful-paint", buffered: true });
    } catch (_) {}

    try {
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!entry.hadRecentInput) clsValue += entry.value;
        }
        enqueue({
          name: "web_vital_cls",
          value: Number(clsValue.toFixed(4)),
          unit: "score",
          severity: clsValue > 0.25 ? "high" : clsValue > 0.1 ? "medium" : "low",
        });
      }).observe({ type: "layout-shift", buffered: true });
    } catch (_) {}

    try {
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.interactionId && entry.duration > inpValue) {
            inpValue = entry.duration;
          }
        }
        if (inpValue > 0) {
          enqueue({
            name: "web_vital_inp",
            value: Math.round(inpValue),
            unit: "ms",
            severity: inpValue > 500 ? "high" : inpValue > 200 ? "medium" : "low",
          });
        }
      }).observe({ type: "event", buffered: true, durationThreshold: 40 });
    } catch (_) {}
  }
})();
