/* Shows a Web Push. The payload is JSON {title, body} when the push is encrypted. */
self.addEventListener("push", (event) => {
  let title = "Agentic Runtime";
  let body = "";
  if (event.data) {
    try {
      const payload = event.data.json();
      title = payload.title || title;
      body = payload.body || "";
    } catch (_error) {
      body = event.data.text();
    }
  }
  event.waitUntil(self.registration.showNotification(title, { body }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
});
