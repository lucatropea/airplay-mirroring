const url = document.querySelector(".url")?.textContent?.trim() ?? "";
const copyButton = document.querySelector("[data-copy]");
const warn = document.querySelector("[data-lan-warn]");
const linkState = document.querySelector("[data-link-state]");
const dot = document.querySelector("[data-dot]");
const fps = document.querySelector("[data-capture-fps]");
const size = document.querySelector("[data-size]");
const stopButton = document.querySelector("[data-stop]");
const fullButton = document.querySelector("[data-full]");
const preview = document.querySelector(".preview--live");

if (warn && url.includes("127.0.0.1")) warn.hidden = false;

copyButton?.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(url);
    copyButton.textContent = "Copied";
  } catch {
    copyButton.textContent = "Select link";
  }
  window.setTimeout(() => {
    copyButton.textContent = "Copy link";
  }, 1500);
});

fullButton?.addEventListener("click", () => {
  const target = preview ?? document.documentElement;
  if (document.fullscreenElement) {
    void document.exitFullscreen();
    return;
  }
  const request = target.requestFullscreen?.bind(target);
  void request?.()?.catch(() => {});
});

async function tick() {
  try {
    const response = await fetch("/status", { cache: "no-store" });
    if (!response.ok) return;
    const data = await response.json();
    const live = Boolean(data.sender) || Number(data.fps) > 0;
    if (linkState) {
      linkState.textContent = live ? "iPad sending" : "Waiting for iPad";
    }
    dot?.classList.toggle("on", live);
    if (fps) fps.textContent = String(data.fps);
    if (size) size.textContent = data.width ? `${data.width}×${data.height}` : "—";
  } catch {
    if (linkState) linkState.textContent = "Server stopped";
  }
}

let timer = window.setInterval(() => {
  void tick();
}, 1000);

stopButton?.addEventListener("click", async () => {
  if (!(stopButton instanceof HTMLButtonElement)) return;
  stopButton.disabled = true;
  window.clearInterval(timer);
  try {
    const response = await fetch("/shutdown", { method: "POST" });
    if (!response.ok) throw new Error("stop");
  } catch {
    stopButton.disabled = false;
    timer = window.setInterval(() => {
      void tick();
    }, 1000);
    return;
  }
  document.body.replaceChildren();
  const message = document.createElement("p");
  message.className = "done";
  message.textContent = "Mirror stopped. You can close this tab.";
  document.body.append(message);
});

void tick();
