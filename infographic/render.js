const path = require("path");
const puppeteer = require("puppeteer");

(async () => {
  const browser = await puppeteer.launch({
    headless: "new",
    defaultViewport: {
      width: 1200,
      height: 3600,
      deviceScaleFactor: 2,
    },
  });

  const page = await browser.newPage();
  const filePath = `file://${path.resolve(__dirname, "infographic.html")}`;
  await page.goto(filePath, { waitUntil: "networkidle0" });

  await page.screenshot({
    path: path.resolve(__dirname, "infographic.png"),
    clip: {
      x: 0,
      y: 0,
      width: 1200,
      height: 3600,
    },
  });

  await browser.close();
})();
