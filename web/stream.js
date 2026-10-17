const canvas = document.querySelector("canvas[data-stream]");
if (canvas instanceof HTMLCanvasElement) {
  void start(canvas);
}

async function start(surface) {
  const streamUrl = surface.dataset.stream;
  const frameUrl = surface.dataset.frame;
  const ctx = surface.getContext("2d", { alpha: false });
  if (!streamUrl || !ctx) return;

  const view = createView(surface, ctx);
  try {
    await playStream(view, streamUrl);
  } catch {
    if (!frameUrl) {
      view.setState("Connection failed");
      return;
    }
    await playPoll(view, frameUrl);
  }
}

function createView(surface, ctx) {
  const fpsNode = document.querySelector("[data-fps]");
  const stateNode = document.querySelector("[data-stream-state]");
  let frames = 0;
  let windowStarted = performance.now();

  return {
    draw(bytes) {
      return drawJpeg(ctx, surface, bytes);
    },
    noteFrame() {
      frames += 1;
      const now = performance.now();
      if (now - windowStarted < 1000 || !fpsNode) return;
      fpsNode.textContent = String(Math.round((frames * 1000) / (now - windowStarted)));
      frames = 0;
      windowStarted = now;
    },
    setState(text) {
      if (stateNode) stateNode.textContent = text;
    },
  };
}

async function playStream(view, url) {
  let failures = 0;
  for (;;) {
    let response;
    try {
      response = await fetch(url, { cache: "no-store" });
    } catch {
      failures += 1;
      if (failures >= 3) throw new Error("stream");
      view.setState("Reconnecting…");
      await wait(400);
      continue;
    }
    if (!response.ok || !response.body) {
      failures += 1;
      if (failures >= 3) throw new Error("stream");
      view.setState("Reconnecting…");
      await wait(400);
      continue;
    }
    failures = 0;
    view.setState("Live");
    try {
      await readFrames(view, response.body.getReader());
    } catch {
      /* socket closed — retry below */
    }
    view.setState("Reconnecting…");
    await wait(300);
  }
}

async function readFrames(view, reader) {
  let buffer = new Uint8Array(0);
  for (;;) {
    const { done, value } = await reader.read();
    if (done) return;
    buffer = concat(buffer, value);
    const drained = drain(buffer);
    buffer = drained.rest;
    const latest = drained.frames.at(-1);
    if (!latest) continue;
    try {
      await view.draw(latest);
      view.noteFrame();
    } catch {
      /* skip corrupt frame */
    }
  }
}

async function playPoll(view, url) {
  let failures = 0;
  view.setState("Live");
  for (;;) {
    const started = performance.now();
    try {
      const response = await fetch(`${url}?t=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error("frame");
      failures = 0;
      await view.draw(new Uint8Array(await response.arrayBuffer()));
      view.noteFrame();
    } catch {
      failures += 1;
      view.setState(failures >= 3 ? "Connection failed" : "Reconnecting…");
      if (failures >= 3) return;
    }
    const pause = 40 - (performance.now() - started);
    if (pause > 0) await wait(pause);
  }
}

async function drawJpeg(ctx, surface, bytes) {
  const bitmap = await createImageBitmap(new Blob([bytes], { type: "image/jpeg" }));
  paint(ctx, surface, bitmap);
  bitmap.close();
}

function paint(ctx, surface, bitmap) {
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const width = Math.max(1, Math.round(surface.clientWidth * ratio));
  const height = Math.max(1, Math.round(surface.clientHeight * ratio));
  if (surface.width !== width || surface.height !== height) {
    surface.width = width;
    surface.height = height;
  }
  const scale = Math.min(surface.width / bitmap.width, surface.height / bitmap.height);
  const drawWidth = bitmap.width * scale;
  const drawHeight = bitmap.height * scale;
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, surface.width, surface.height);
  ctx.drawImage(
    bitmap,
    (surface.width - drawWidth) / 2,
    (surface.height - drawHeight) / 2,
    drawWidth,
    drawHeight,
  );
}

function drain(buffer) {
  const frames = [];
  let offset = 0;
  while (buffer.length - offset >= 4) {
    const size = buffer[offset] * 16777216
      + buffer[offset + 1] * 65536
      + buffer[offset + 2] * 256
      + buffer[offset + 3];
    if (size < 100 || size > 5_000_000) {
      offset += 1;
      continue;
    }
    if (buffer.length - offset < 4 + size) break;
    frames.push(buffer.slice(offset + 4, offset + 4 + size));
    offset += 4 + size;
  }
  return { frames, rest: buffer.subarray(offset) };
}

function concat(buffer, chunk) {
  if (buffer.length === 0) return chunk;
  const next = new Uint8Array(buffer.length + chunk.length);
  next.set(buffer, 0);
  next.set(chunk, buffer.length);
  return next;
}

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
