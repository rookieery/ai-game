// 缠魂塔 · 实机取证（只读, 不接入游戏）: 临时加载 lookout_tower.glb 摆到绿圈圆心, 按机位表批量截图
// 用法: 先起 dev server, 再 GAME_URL=http://127.0.0.1:8765 node scripts/verify_tower_shots.mjs [输出目录] [F01,F02,...]
//   默认输出 shots/tower/v3/E, 42 机位: 来路 F01-F13 / 门厅与梯口 F14-F18 / 梯上 F19-F24 / 环廊 F25-F34 /
//   轿厢与栈桥 F35-F38 / 塔冠 F39-F40 / 仰视与俯视 F41-F42
// 配套: scripts/tower_pixel_stats.mjs (过曝/近黑占比), scripts/verify_tower_colliders.mjs (碰撞表离线校验)
import { mkdirSync, readFileSync } from "node:fs";
import { openGame } from "./lib_tower_shots.mjs";

const OUT = process.argv[2] ?? "shots/tower/v3/E";
const ONLY = process.argv[3] ? process.argv[3].split(",") : null;
mkdirSync(OUT, { recursive: true });
const SITE = [17.5, -30.5];
const man = JSON.parse(readFileSync("model/lookout_tower/colliders_tower.json", "utf8"));
const HX = man.floors.find((f) => f.shape === "helix");
const A0 = (HX.a0 * 180) / Math.PI, DA = (HX.da * HX.dir * 180) / Math.PI;
const pol = (aDeg, r, y = 0) => [SITE[0] + r * Math.cos((aDeg * Math.PI) / 180), y, SITE[1] + r * Math.sin((aDeg * Math.PI) / 180)];
const stepA = (k) => A0 + DA * k;
const stepH = (k) => HX.h[k];

// [编号, 说明, 相机, 目标, fov, 轿厢节点高度(可选)]
const VIEWS = [
  ["F01", "南侧来路 · 塔南 11m 人眼", [17.5, 1.65, -19.5], [17.5, 9, -30.5], 75],
  ["F02", "东南 10m · 两个入口同框", pol(75, 10, 1.65), [17.5, 4, -30.5], 80],
  ["F03", "广场东缘人眼仰望", [24, 1.65, -4], [17.5, 21, -30.5], 80],
  ["F04", "东草坪人眼仰望", [42, 1.65, -30], [17.5, 21, -30.5], 80],
  ["F05", "西来路(排队口)望塔", [6.5, 1.65, -30], [17.5, 12, -30.5], 75],
  ["F06", "东南远处 70m", [70, 1.65, 5], [17.5, 24, -30.5], 60],
  ["F07", "正南 60m", [17.5, 1.65, 29.5], [17.5, 24, -30.5], 60],
  ["F08", "摩天轮顶舱高度看塔", [0, 35, 2.4], [17.5, 40, -30.5], 70],
  ["F09", "过山车提升顶看塔", [28.7, 26.1, -115.4], [17.5, 38, -30.5], 60],
  ["F10", "过山车东站台面南望", [13.6, 4.03, -47], [17.5, 16, -30.5], 80],
  ["F11", "回流沟轨道旁 6m 看塔", [11.5, 3.0, -22], [17.5, 25, -30.5], 60],
  ["F12", "高空鸟瞰", [62, 58, 8], [17.5, 21, -30.5], 50],
  ["F13", "120m 外天际线", [60, 1.65, 40], [17.5, 28, -30.5], 40],
  ["F14", "门厅 9m 外人眼", [17.5, 1.65, -21.0], [17.5, 2.8, -29.0], 75],
  ["F15", "门厅笼门前", [17.5, 1.65, -28.6], [17.5, 1.6, -30.5], 75],
  ["F16", "梯口", pol(70, 4.6, 1.65), pol(58, 1.5, 1.6), 75],
  ["F17", "西侧第二入口(护栏东侧)", [13.4, 1.65, -30.3], [17.5, 2.8, -30.5], 75],
  ["F18", "西侧 10m 望第二入口", [9.0, 1.65, -30.0], [17.5, 8, -30.5], 75],
  ["F19", "梯上第 1 级 · 沿梯向上看", pol(stepA(1) + 2, 2.5, stepH(1) + 1.65), pol(stepA(6), 2.5, stepH(6) + 4.5), 75],
  ["F20", "梯中第 60 级 · 向外看", pol(stepA(60) + 2, 2.6, stepH(60) + 1.65), pol(stepA(60) + 2, 14, stepH(60) - 0.5), 75],
  ["F21", "梯上第 55 级 · 望高度标记", pol(stepA(55) + 2, 2.6, stepH(55) + 1.65), pol(stepA(60) - 1, 1.9, stepH(60) + 1.9), 75],
  ["F22", "梯上第 200 级 · 沿梯向上看", pol(stepA(200) + 2, 2.6, stepH(200) + 1.65), pol(stepA(215), 2.6, stepH(215) + 1.3), 75],
  ["F23", "到顶 · 迈上环廊", pol(145, 2.54, stepH(240) + 1.65), pol(145, 8, 40.6), 75],
  ["F24", "沿末级走到尽头(护栏)", pol(140, 2.4, 40 + 1.65), pol(130, 2.4, 40.8), 75],
  ["F25", "环廊外圈北望(提升段)", pol(300, 4.7, 41.65), [28.7, 25, -115.4], 70],
  ["F26", "环廊外圈望摩天轮", pol(120, 4.7, 41.65), [0, 22, 0], 70],
  ["F27", "环廊外圈东望", pol(25, 4.7, 41.65), [60, 20, -30.5], 70],
  ["F28", "环廊外圈南望(入口)", pol(80, 4.7, 41.65), [10, 18, 40], 70],
  ["F29", "环廊望栈桥口与刀牌", pol(225, 4.8, 41.65), pol(270, 3.6, 41.2), 75],
  ["F30", "打卡南瓜灯近景(自到达口, 正对脸)", pol(150.2, 4.28, 40.95), pol(162, 3.72, 40.36), 50],
  ["F31", "长椅近景", pol(0, 5.2, 41.3), pol(0, 3.8, 40.4), 55],
  ["F32", "环廊内看梯井", pol(340, 5.0, 41.65), [17.5, 40.6, -30.5], 80],
  ["F33", "俯身越过栏杆下看", pol(60, 4.9, 41.65), pol(60, 9, 20), 70],
  ["F34", "方位牌(摩天轮)", pol(120, 4.6, 41.65), pol(120, 5.5, 40.9), 50],
  ["F35", "轿厢内(底层)朝南门", [17.3, 1.79, -30.3], [17.5, 1.8, -27], 75],
  ["F36", "轿厢内(半程 20m)向外看", [17.6, 21.79, -30.2], [5, 20, -15], 75, 20.0],
  ["F37", "轿厢内(顶层)朝北门", [17.6, 41.79, -30.3], [17.5, 41.2, -34], 75, 39.92],
  ["F38", "栈桥上朝笼顶门", pol(270, 4.4, 41.65), pol(270, 1.7, 41.2), 75],
  ["F39", "环廊上仰看灯室", pol(45, 4.8, 41.65), [17.5, 44.3, -30.5], 60],
  ["F40", "塔冠近景", [30, 52, -12], [17.5, 43, -30.5], 45],
  ["F41", "塔基地面仰看", pol(30, 2.0, 1.65), [17.5, 39.5, -30.5], 80],
  ["F42", "正上方俯视环廊", [17.5, 70, -30.4], [17.5, 40, -30.5], 35],
];

const { browser, page, errors } = await openGame(OUT, { width: 1600, height: 900 });
await page.addStyleTag({ content: "#hud, #hud *{visibility:hidden!important}" });
await page.evaluate(async () => {
  const { loadGLB } = await import("/src/park/loader.js");
  const root = await loadGLB("/model/lookout_tower/lookout_tower.glb");
  root.position.set(17.5, 0, -30.5);
  window.__game.scene.add(root);
  window.__tw = root;
});
await page.evaluate(() => {
  const d = document.createElement("div");
  d.id = "__lbl";
  d.style.cssText = "position:fixed;left:24px;top:20px;z-index:99999;font:600 26px/1.35 'Microsoft YaHei',sans-serif;color:#fff;" +
    "text-shadow:0 0 12px rgba(0,0,0,.95),0 2px 4px #000;pointer-events:none;padding:10px 16px;background:rgba(10,8,19,.66);border-radius:6px";
  document.body.appendChild(d);
});
await page.evaluate(() => { window.__game.player.update = () => {}; });

for (const [id, title, p, t, fov, liftY] of VIEWS) {
  if (ONLY && !ONLY.includes(id)) continue;
  await page.evaluate(([p, t, fov, liftY, txt]) => {
    const g = window.__game;
    g.player.update = () => {};
    if (window.__tw) window.__tw.getObjectByName("TW_Lift").position.y = liftY ?? 0.06;
    const c = g.camera;
    c.fov = fov; c.updateProjectionMatrix();
    c.position.set(p[0], p[1], p[2]);
    c.lookAt(t[0], t[1], t[2]);
    document.getElementById("__lbl").textContent = txt;
  }, [p, t, fov, liftY, `${id} · ${title}`]);
  await page.waitForTimeout(450);
  await page.screenshot({ path: `${OUT}/${id}.png` });
  console.log("shot", id, title);
}
console.log("console-errors:", errors.length ? JSON.stringify(errors.slice(0, 8), null, 1) : "none");
await browser.close();
