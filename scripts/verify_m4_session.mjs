// M4-B3 乘坐会话取证: 站台联锁 / board→压肩→发车 / 排队下客全链 / 无会话 M3 等价
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
const OUT = ".impeccable/review-coaster";
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => document.getElementById("enter-btn") && !document.getElementById("enter-btn").disabled, { timeout: 120000 });
await page.click("#enter-btn");
await page.waitForTimeout(1500);

const R = {};
const ok = (name, cond, got) => { R[name] = cond ? "PASS" : `FAIL ${JSON.stringify(got)}`; };
const st = () => page.evaluate(() => {
  const c = window.__game.coaster.state;
  return { phase: c.phase, s: +c.s.toFixed(2), dwellT: +c.dwellT.toFixed(2), hold: c.hold, lapbar: +c.session.lapbar.toFixed(3), active: c.session.active, wantOff: c.session.wantOff };
});

// ① 站台联锁: 站上台后 hold 应被 B3 直驱置位并冻结 dwell
await page.evaluate(() => { window.__game.player.teleport(10.4, -60); window.__game.coaster.state.hold = true; });
await page.waitForTimeout(400);
const h0 = await st();
await page.waitForTimeout(2000);
const h1 = await st();
ok("hold_freezes", h0.phase === "dwell" && h1.phase === "dwell" && Math.abs(h1.dwellT - h0.dwellT) < 0.3, { h0, h1 });

// ② hold 直驱解除 + 补偿: dwell <2 时应补到 4 (当前 >2, 只验证恢复倒计时)
await page.evaluate(() => { window.__game.coaster.state.hold = false; window.__game.player.teleport(0, 20); });
await page.waitForTimeout(2000);
const h2 = await st();
ok("hold_release_counts", h2.dwellT < h1.dwellT - 1.5, { h1, h2 });

// ③ board 直调: 压肩闭合(0.8s) → 锁闭后 2.4s 发车
await page.evaluate(() => window.__game.coaster.board());
await page.waitForTimeout(1000);
const b1 = await st();
await page.waitForTimeout(2800);
const b2 = await st();
ok("board_lapbar_closes", b1.active && b1.lapbar >= 0.99, b1);
ok("board_dispatches", b2.phase === "run" && b2.active, b2);

// ④ 排队下客全链: seek 刹车段 → 过缝 crawl → 对位停正 → 压肩开启 → onDisembarkReady
const off = await page.evaluate(() => {
  return new Promise((resolve) => {
    const c = window.__game.coaster;
    let done = false;
    c.onDisembarkReady = () => { if (!done) { done = true; resolve(true); } };
    c.seek(490);
    const queued = c.queueDisembark();
    setTimeout(() => { if (!done) { done = true; resolve({ queued, timeout: true, state: JSON.parse(JSON.stringify({ ...c.state, session: undefined })) }); } }, 30000);
  });
});
const s4 = await st();
ok("queue_full_chain", off === true && s4.phase === "dwell" && s4.lapbar < 0.05 && s4.active, { off, s4 });

// ⑤ disembark 清会话 → 观赏循环恢复 (发车前压肩收拢): 轮询至发车
await page.evaluate(() => window.__game.coaster.disembark());
const s5a = await st();
const s5b = await page.evaluate(() => new Promise((resolve) => {
  const c = window.__game.coaster.state;
  const t0 = Date.now();
  const iv = setInterval(() => {
    if (c.phase === "run") { clearInterval(iv); resolve({ phase: c.phase, lapbar: +c.session.lapbar.toFixed(3) }); }
    else if (Date.now() - t0 > 16000) { clearInterval(iv); resolve({ phase: c.phase, timeout: true }); }
  }, 300);
}));
ok("disembark_resumes_cycle", !s5a.active && s5b.phase === "run" && s5b.lapbar === 1, { s5a, s5b });

// ⑥ 停靠压肩截图 (开启态): 站台东侧看头车
await page.evaluate(() => { window.__game.player.teleport(16.2, -60); window.__game.player.setView(Math.PI / 2, -0.1); });
await page.waitForTimeout(350);
await page.screenshot({ path: `${OUT}/m4_lapbar_view.png` });

console.log(JSON.stringify(R, null, 1));
console.log("ERRORS", JSON.stringify(errors.slice(0, 5)));
await browser.close();
const pass = Object.values(R).every((v) => v === "PASS") && errors.length === 0;
process.exit(pass ? 0 : 1);
