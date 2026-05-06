const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");
const puppeteer = require("puppeteer");

const WIDTH = 1200;
const HEIGHT = 3600;
const DEVICE_SCALE_FACTOR = 2;
const FPS = 30;
const SETTLE_MS = 6000;
const RECORD_MS = 8000;
const TARGET_FRAMES = FPS * (RECORD_MS / 1000);

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function hasFfmpeg() {
  const result = spawnSync("ffmpeg", ["-version"], { stdio: "ignore" });
  return result.status === 0;
}

async function loadPage(browser, fileUrl) {
  const page = await browser.newPage();
  await page.goto(fileUrl, { waitUntil: "networkidle0" });
  await sleep(SETTLE_MS);
  return page;
}

async function captureFrames(page, framesDir) {
  const client = await page.target().createCDPSession();
  let frameIndex = 0;
  let resolveDone;
  const done = new Promise((resolve) => {
    resolveDone = resolve;
  });

  client.on("Page.screencastFrame", async (event) => {
    const frameNumber = frameIndex;
    frameIndex += 1;
    const filename = path.join(
      framesDir,
      `frame-${String(frameNumber).padStart(5, "0")}.png`
    );
    fs.writeFileSync(filename, Buffer.from(event.data, "base64"));
    await client.send("Page.screencastFrameAck", { sessionId: event.sessionId });
    if (frameIndex >= TARGET_FRAMES) resolveDone();
  });

  await client.send("Page.startScreencast", {
    format: "png",
    quality: 100,
    everyNthFrame: 1,
  });

  await Promise.race([done, sleep(RECORD_MS)]);
  await client.send("Page.stopScreencast");
  return frameIndex;
}

(async () => {
  const browser = await puppeteer.launch({
    headless: "new",
    defaultViewport: {
      width: WIDTH,
      height: HEIGHT,
      deviceScaleFactor: DEVICE_SCALE_FACTOR,
    },
  });

  try {
    const fileUrl = `file://${path.resolve(__dirname, "infographic.html")}`;

    // ── 1. Static PNG capture (animations paused) ─────────────────────
    const pngPage = await loadPage(browser, fileUrl);
    await pngPage.evaluate(() => {
      // Halt every running SVG animation so the PNG is a clean still frame.
      document.querySelectorAll("animate, animateMotion, animateTransform").forEach((node) => {
        try {
          node.endElement?.();
        } catch (_) {
          /* ignore — node may not be an SMIL element */
        }
      });
      // Disable all CSS animations & transitions via a body-level class.
      document.body.classList.add("no-anim");
    });
    // Give the browser a frame to apply the no-anim class before the snapshot.
    await sleep(150);

    const pngPath = path.resolve(__dirname, "infographic.png");
    await pngPage.screenshot({
      path: pngPath,
      clip: { x: 0, y: 0, width: WIDTH, height: HEIGHT },
    });
    await pngPage.close();
    console.log(`PNG exported: ${pngPath}`);

    // ── 2. MP4 capture (fresh page, animations live) ──────────────────
    if (!hasFfmpeg()) {
      console.log(
        "ffmpeg was not found, so the MP4 export was skipped. Install ffmpeg, then run `node render.js` again."
      );
      return;
    }

    const mp4Page = await loadPage(browser, fileUrl);

    const framesDir = fs.mkdtempSync(
      path.join(os.tmpdir(), "lakehouse-infographic-")
    );
    const framesCaptured = await captureFrames(mp4Page, framesDir);
    if (framesCaptured === 0) {
      console.log("No screencast frames were captured. PNG export still completed.");
      return;
    }

    const mp4Path = path.resolve(__dirname, "infographic.mp4");
    const ffmpegResult = spawnSync(
      "ffmpeg",
      [
        "-y",
        "-r",
        String(FPS),
        "-i",
        path.join(framesDir, "frame-%05d.png"),
        "-pix_fmt",
        "yuv420p",
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        mp4Path,
      ],
      { stdio: "inherit" }
    );

    if (ffmpegResult.status !== 0) {
      console.log("ffmpeg failed while assembling the MP4. PNG export still completed.");
      return;
    }

    fs.rmSync(framesDir, { recursive: true, force: true });
    console.log(`MP4 exported: ${mp4Path}`);
  } finally {
    await browser.close();
  }
})();
