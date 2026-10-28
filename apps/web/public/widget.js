/* Host handles ar-widget:token-request and calls event.detail.respond(shortLivedJwt). */
(() => {
  const current = document.currentScript;
  if (!(current instanceof HTMLScriptElement)) return;
  const integrationId = current.dataset.integration;
  if (!integrationId || !/^[0-9a-f-]{36}$/i.test(integrationId)) return;
  const origin = new URL(current.src).origin;
  const launcher = document.createElement("button");
  launcher.type = "button";
  launcher.textContent = current.dataset.label || "Chat with an agent";
  launcher.setAttribute("aria-expanded", "false");
  launcher.style.cssText =
    "position:fixed;right:20px;bottom:20px;z-index:2147483000;padding:12px 18px;border:1px solid ButtonText;border-radius:28px;background:ButtonFace;color:ButtonText;font:500 14px system-ui;cursor:pointer;box-shadow:0 4px 20px color-mix(in srgb,CanvasText 12%,transparent)";
  let frame;
  let nonce = "";
  function close() {
    if (frame) frame.hidden = true;
    launcher.setAttribute("aria-expanded", "false");
    launcher.focus();
  }
  launcher.addEventListener("click", () => {
    if (!frame) {
      frame = document.createElement("iframe");
      frame.id = `ar-widget-${integrationId}`;
      frame.title = "Agent chat";
      frame.src = `${origin}/widget/${integrationId}`;
      frame.style.cssText =
        "position:fixed;right:20px;bottom:80px;z-index:2147483000;width:min(380px,calc(100vw - 32px));height:min(600px,calc(100dvh - 112px));border:1px solid color-mix(in srgb,CanvasText 18%,transparent);border-radius:16px;background:Canvas;box-shadow:0 12px 48px color-mix(in srgb,CanvasText 16%,transparent)";
      launcher.setAttribute("aria-controls", frame.id);
      document.body.appendChild(frame);
    } else frame.hidden = !frame.hidden;
    launcher.setAttribute("aria-expanded", String(!frame.hidden));
    if (!frame.hidden) frame.focus();
  });
  window.addEventListener("message", (event) => {
    if (
      !frame ||
      event.source !== frame.contentWindow ||
      event.origin !== origin ||
      event.data?.integrationId !== integrationId
    )
      return;
    if (event.data?.type === "ar-widget:close") {
      close();
      return;
    }
    if (event.data?.type !== "ar-widget:ready" || typeof event.data.nonce !== "string") return;
    nonce = event.data.nonce;
    const challenge = nonce;
    let answered = false;
    window.dispatchEvent(
      new CustomEvent("ar-widget:token-request", {
        detail: {
          integrationId,
          respond(token) {
            if (answered || challenge !== nonce || typeof token !== "string") return;
            answered = true;
            frame.contentWindow?.postMessage(
              { type: "ar-widget:authenticate", integrationId, nonce: challenge, token },
              origin,
            );
          },
        },
      }),
    );
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && frame && !frame.hidden) close();
  });
  document.body.appendChild(launcher);
})();
