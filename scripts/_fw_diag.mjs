import { chromium } from "playwright";
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
page.on("pageerror", (e) => console.log("PAGEERROR:", String(e)));
page.on("console", (m) => { if (m.type() === "error") console.log("CONERR:", m.text()); });
await page.goto("http://127.0.0.1:8768/prototype/fw_burst/", { waitUntil: "networkidle" });
await page.waitForTimeout(800);
await page.evaluate(() => window.__fw.auto(false));
await page.evaluate(() => window.__fw.fire("willow", "#FFD9A0"));
for (let k = 0; k < 30; k++) {
  await page.waitForTimeout(300);
  const a = await page.evaluate(() => window.__fw.alive());
  process.stdout.write(`${a} `);
}
console.log("\nDONE");
await browser.close();
