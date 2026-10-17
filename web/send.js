const token = document.querySelector("script[data-token]")?.dataset.token ?? "";
const startButton = document.querySelector("[data-start]");
const stopButton = document.querySelector("[data-stop-send]");
const stateNode = document.querySelector("[data-send-state]");
const video = document.querySelector("[data-video]");
const canvas = document.querySelector("[data-canvas]");

const MAX_WIDTH = 1280;
const TARGET_FPS = 18;
const JPEG_QUALITY = 0.55;

let stream = null;
let running = false;
let uploading = false;
let wakeLock = null;

startButton?.addEventListener("click", () => {
  void begin();
});

stopButton?.addEventListener("click", () => {
  stopCapture("Sharing stopped");
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && running) {
    void keepAwake();
  }
});

async function begin() {
  if (!(video instanceof HTMLVideoElement) || !(canvas instanceof HTMLCanvasElement)) return;
  if (!token) {
    setState("Invalid link");
    return;
  }
  if (!navigator.mediaDevices?.getDisplayMedia) {
    setState("Update iPadOS or try Chrome — screen capture is not supported.");
    return;
  }

  startButton.disabled = true;
  setState("Choose what to share…");

  try {
    stream = await navigator.mediaDevices.getDisplayMedia({
      video: { frameRate: { ideal: TARGET_FPS, max: 30 } },
      audio: false,
    });
  } catch {
    setState("Sharing cancelled");
    startButton.disabled = false;
    return;
  }

  video.srcObject = stream;
  await video.play();
  await keepAwake();

  running = true;
  stopButton.hidden = false;
  setState("Sending");
  stream.getVideoTracks()[0]?.addEventListener("ended", () => {
    stopCapture("Sharing ended");
  });

  void captureLoop(video, canvas);
}

async function captureLoop(source, surface) {
  const ctx = surface.getContext("2d", { alpha: false });
  if (!ctx) return;

  while (running) {
    const tickStart = performance.now();
    if (source.videoWidth <= 0) {
      await wait(40);
      continue;
    }

    const scale = Math.min(1, MAX_WIDTH / source.videoWidth);
    const width = Math.max(1, Math.round(source.videoWidth * scale));
    const height = Math.max(1, Math.round(source.videoHeight * scale));
    if (surface.width !== width || surface.height !== height) {
      surface.width = width;
      surface.height = height;
    }
    ctx.drawImage(source, 0, 0, width, height);

    if (!uploading) {
      uploading = true;
      void uploadFrame(surface, width, height).finally(() => {
        uploading = false;
      });
    }

    const pause = 1000 / TARGET_FPS - (performance.now() - tickStart);
    if (pause > 0) await wait(pause);
  }
}

async function uploadFrame(surface, width, height) {
  const blob = await canvasToJpeg(surface);
  if (!blob || !running) return;
  try {
    const response = await fetch(`/push/${token}`, {
      method: "POST",
      headers: {
        "Content-Type": "image/jpeg",
        "X-Frame-Width": String(width),
        "X-Frame-Height": String(height),
      },
      body: blob,
      cache: "no-store",
    });
    if (!response.ok && response.status !== 204) {
      setState("Lost connection to PC");
    }
  } catch {
    setState("Lost connection to PC");
  }
}

function canvasToJpeg(surface) {
  return new Promise((resolve) => {
    surface.toBlob((blob) => resolve(blob), "image/jpeg", JPEG_QUALITY);
  });
}

function stopCapture(message) {
  running = false;
  stopButton.hidden = true;
  startButton.disabled = false;
  stream?.getTracks().forEach((track) => track.stop());
  stream = null;
  void releaseWakeLock();
  setState(message);
}

async function keepAwake() {
  try {
    wakeLock = await navigator.wakeLock?.request("screen");
  } catch {
    /* Wake lock may require a user gesture on iPad. */
  }
}

async function releaseWakeLock() {
  try {
    await wakeLock?.release();
  } catch {
    /* ignored */
  }
  wakeLock = null;
}

function setState(text) {
  if (stateNode) stateNode.textContent = text;
}

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
