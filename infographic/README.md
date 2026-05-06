# Azure E-Commerce Lakehouse Infographic

Three deliverables, one source of truth (`infographic.html`):

| Output                | What it is                                    | Where to use it                                              |
|-----------------------|-----------------------------------------------|--------------------------------------------------------------|
| `infographic.html`    | Live, animated single-file page (1200×3600)   | Host on GitHub Pages, link from your LinkedIn bio            |
| `infographic.png`     | Clean static still frame (Retina, 2400×7200)  | Drop into the repository README and Twitter image previews   |
| `infographic.mp4`     | 8-second animated loop                        | Post directly to LinkedIn / Twitter for autoplay-on-scroll   |

## Build

Prerequisites: `node`, `npm`, and (for the MP4 export) `ffmpeg` on `PATH`.

```bash
cd infographic
npm install puppeteer
node render.js
```

What `render.js` does:

1. Loads `infographic.html` in headless Chromium.
2. Lets the animations settle for 6 seconds.
3. **Pauses every SMIL and CSS animation**, then captures `infographic.png` — a clean static frame with no mid-animation glitches.
4. Reloads the page (animations live), records 8 seconds at 30 fps via the Chrome DevTools `Page.startScreencast` API, and assembles `infographic.mp4` with `ffmpeg`.

If `ffmpeg` is missing, the PNG is still produced and the script exits cleanly with an install hint.

## Animations baked into the page

- Pass particles (green) flowing Bronze → DQ gate → Silver → Gold on the main spine.
- Three blue particles fanning out from Gold to DuckDB, Power BI, and Synapse Serverless.
- A red Fail particle showing the rare quarantine path (DQ-failure → Rejected zone).
- Floating row-count labels (`+1 row`, `+1 clean`, `−1 rejected`) locked to the matching particles.
- Data-quality gate pulse synced to the particle cadence.
- Headline metric count-up (0 → 1,550,922 / 25 / 9 / 137,234) on page load.
- Card reveal-on-scroll via `IntersectionObserver`.
- Mart sweep highlight cycling all nine Gold marts on a 6.3-second loop, in medallion gold (`#B8860B`).
- CI/CD flow dots and an OIDC handshake pulse ring.
- Subtle hero-grid drift and a "Scroll for full architecture" bouncing hint.

All animations respect `prefers-reduced-motion: reduce`.
