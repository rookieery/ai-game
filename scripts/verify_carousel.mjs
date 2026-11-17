// 显灵木马运行时回归验证
// 前置: npm run dev 已在 http://127.0.0.1:8765
// 断言:
//   资产加载无报错; CR_Spin 旋转 / 马位起伏(±0.22) / 座车不起伏
//   三级台阶逐级走上平台 (y: 0 -> 0.155 -> 0.31 -> 0.465 -> 0.62)
//   平台上静止站立会被经过的马推开 (动态碰撞圆生效)
// 截图: 场外远景 / 盘上第一人称 / 动态碰撞推挤取证
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = process.argv[2] ?? "shots/carousel";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));

const pos = () => page.evaluate(() => {
  const p = window.__game.player.pos;
  return { x: +p.x.toFixed(3), y: +p.y.toFixed(3), z: +p.z.toFixed(3) };
});

await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 60000 });
await page.click("#enter-btn");
await page.waitForTimeout(1200);

const fails = [];
const expect = async (name, cond, detail = "") => {
  const ok = !!cond;
  if (!ok) fails.push(name);
  console.log(`check ${ok ? "ok  " : "FAIL"} : ${name}${detail ? "  " + detail : ""}`);
};

// T0 资产就位
const hasCarousel = await page.evaluate(() => !!window.__game.carousel?.spinRoot);
await expect("carousel 资产加载", hasCarousel);

// T1 机台旋转 (theta 前进)
const th0 = await page.evaluate(() => window.__game.carousel.state.theta);
await page.waitForTimeout(800);
const th1 = await page.evaluate(() => window.__game.carousel.state.theta);
await expect("机台旋转 theta 前进", th1 > th0, `${th0.toFixed(4)} -> ${th1.toFixed(4)}`);

// T2 马位起伏 ±0.22 / 座车静止
const b0 = await page.evaluate(() => window.__game.carousel.rideRoots[1].position.y);
await page.waitForTimeout(700);
const b1 = await page.evaluate(() => window.__game.carousel.rideRoots[1].position.y);
await expect("马位起伏变化", Math.abs(b1 - b0) > 0.05, `${b0.toFixed(3)} -> ${b1.toFixed(3)}`);
const c0 = await page.evaluate(() => window.__game.carousel.rideRoots[0].position.y);
await expect("座车不起伏 (i0)", Math.abs(c0 - 0.62) < 1e-4, `y=${c0}`);

// T3 三级台阶逐级上平台 (入口方位 azimuth 202° -> app 侧台阶在场地西南)
// 台阶圆: (37.27,-14.88,h.465) (36.66,-14.63,h.31) (36.04,-14.37,h.155), 朝平台走 +W
// yaw 换算: forward=(-sin yaw, -cos yaw) -> 面向 dir(dx,dz) 取 yaw=atan2(-dx,-dz)
await page.evaluate(() => {
  window.__game.player.teleport(34.5, -13.8);
  window.__game.player.setView(Math.atan2(-0.928, 0.371), 0); // 面向 (45,-18) 平台中心
});
await page.waitForTimeout(300);
const yStart = (await pos()).y;
await page.keyboard.down("KeyW");
await page.waitForTimeout(900);
const yS1 = (await pos()).y;
await page.waitForTimeout(700);
const yS2 = (await pos()).y;
await page.waitForTimeout(700);
const yS3 = (await pos()).y;
await page.keyboard.up("KeyW");
await page.waitForTimeout(600);
const yEnd = (await pos()).y;
await expect("从地面出发", yStart < 0.05, `y=${yStart}`);
await expect("走上平台顶 0.62", Math.abs(yEnd - 0.62) < 0.03, `${yStart} -> ${yEnd}`);
await page.screenshot({ path: `${outDir}/deck_first_person.png` });

// T4 动态碰撞: 站在马环上 (r6.2, 马位圆 r0.55+PR0.38=0.93) 被经过的马推开
await page.evaluate(() => {
  window.__game.player.teleport(45, -11.8);
  window.__game.player.setView(0, 0);
});
const p0 = await pos();
await page.waitForTimeout(4500);
const p1 = await pos();
const pushed = Math.hypot(p1.x - p0.x, p1.z - p0.z);
await expect("静止站立被马位推开 (动态碰撞)", pushed > 0.3, `dist=${pushed.toFixed(3)}`);
await page.screenshot({ path: `${outDir}/pushed_by_horse.png` });

// T5 骑乘: 盘面按 E 上马 (就近骑乘位) -> 相机随盘旋转 -> E 下马回平台
await page.evaluate(() => {
  window.__game.player.teleport(39.5, -14.5); // 盘面内, 靠近入口位南瓜马车
  window.__game.player.setView(0.9, 0);
});
await page.waitForTimeout(600); // 等 interact 提示生效
await page.keyboard.press("KeyE");
await page.waitForTimeout(900); // 等转场完成
const st = await page.evaluate(() => ({
  state: window.__game.state,
  ride: window.__game.ride,
  mounted: window.__game.carousel.mounted,
  cam: (() => {
    const c = window.__game.camera.position;
    return { x: +c.x.toFixed(2), y: +c.y.toFixed(2), z: +c.z.toFixed(2) };
  })(),
}));
await expect("E 上马进入 riding", st.state === "riding" && st.ride === "carousel" && st.mounted >= 0,
  JSON.stringify(st));
await expect("骑坐眼高在骑乘位上", st.cam.y > 1.8 && st.cam.y < 3.2, `cam.y=${st.cam.y}`);
const cam0 = st.cam;
await page.waitForTimeout(2000);
const cam1 = await page.evaluate(() => {
  const c = window.__game.camera.position;
  return { x: +c.x.toFixed(2), z: +c.z.toFixed(2) };
});
const swung = Math.hypot(cam1.x - cam0.x, cam1.z - cam0.z);
await expect("随盘环游 (相机位移)", swung > 1.2, `dist=${swung.toFixed(2)}`);
await page.screenshot({ path: `${outDir}/mounted_view.png` });
await page.keyboard.press("KeyE");
await page.waitForTimeout(900);
const st2 = await page.evaluate(() => {
  const p = window.__game.player.pos;
  const d = Math.hypot(p.x - 45, p.z + 18);
  return { state: window.__game.state, y: +p.y.toFixed(3), r: +d.toFixed(2) };
});
await expect("E 下马回平台", st2.state === "walk" && Math.abs(st2.y - 0.62) < 0.03
  && Math.abs(st2.r - 7.6) < 0.8, JSON.stringify(st2));

// T5 场外远景截图 (氛围核对)
await page.evaluate(() => {
  window.__game.player.teleport(26, -4);
  window.__game.player.setView(-0.9, -0.02);
});
await page.waitForTimeout(700);
await page.screenshot({ path: `${outDir}/venue_far.png` });

console.log(errors.length ? "CONSOLE_ERRORS:\n" + errors.join("\n") : "no console errors");
console.log(fails.length ? `FAILED: ${fails.join(", ")}` : "ALL_OK");
await browser.close();
process.exit(fails.length || errors.length ? 1 : 0);
