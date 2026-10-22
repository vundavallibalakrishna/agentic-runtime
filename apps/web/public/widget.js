/* Embed: <script src="{origin}/widget.js" data-integration="{id}"></script> */
(() => {
  const current = document.currentScript;
  if (!(current instanceof HTMLScriptElement)) {
    return;
  }
  const integration = current.dataset.integration;
  if (!integration) {
    return;
  }
  const origin = new URL(current.src).origin;
  const frame = document.createElement("iframe");
  frame.title = "Agent";
  frame.src = `${origin}/widget/${integration}`;
  frame.style.cssText =
    "position:fixed;right:16px;bottom:16px;width:360px;height:520px;border:0;border-radius:16px;";
  document.body.appendChild(frame);
})();
