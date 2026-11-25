// 幽夜游乐场 — 入口与游戏编排
import { createScene, startLoop } from "./core/scene.js";
import { createWorld } from "./core/world.js";
import { createInput } from "./core/input.js";
import { createPlayer } from "./player/controller.js";
import { createInteract } from "./interact.js";
import { createAudio } from "./core/audio.js";
import { loadGLB, createLoadingManager } from "./park/loader.js";
import { createFerrisWheel } from "./rides/ferris.js";
import { createCarousel } from "./rides/carousel.js";
import { createCoaster } from "./rides/coaster.js";
import { createCoasterGate } from "./rides/coasterGate.js";
import { createTower } from "./rides/tower.js";
import { createPostFX } from "./fx/postfx.js";
import { createMist } from "./fx/mist.js";
import { createFireworks } from "./fx/fireworks.js";
import { createFireworkDirector } from "./fx/fw_director.js";
import { createWisps } from "./fx/wisps.js";
import { createWind } from "./fx/wind.js";
import { createHUD } from "./ui/hud.js";
import { createSettings } from "./core/config.js";
import { createSettingsPanel } from "./ui/settings.js";

const canvas = document.getElementById("game-canvas");

const { renderer, scene, camera } = createScene(canvas);
const world = createWorld(scene);
const mist = createMist(scene, world);
const postfx = createPostFX(renderer, scene, camera);
const input = createInput(canvas);
const hud = createHUD();
const audio = createAudio(hud);
window.__hud = hud; // 截图验证钩子（开发用）
// 烟花（地面 6 站发射器锚点由 colliders.json 注入, 见 boot() 内 setLaunchers; 音效走 audio → core/fw_sound.js）+ 幽灵火
const fireworks = createFireworks(scene, { camera, audio, renderer });
const wisps = createWisps(scene);

// ---------- 游戏状态 ----------
const game = { state: "boot", ride: null }; // boot -> walk -> boarding -> riding -> exiting -> walk; ride = ferris|carousel
let player = null;
let ferris = null;
let carousel = null;
let coaster = null;
let coasterGate = null;
let tower = null;
let fwDirector = null;
let interact = null;
let wind = null;
let entered = false;

// ---------- 设置面板 ----------
const settings = createSettings();
const settingsUI = createSettingsPanel(settings, {
  // 开合影响视角锁定提示的显隐，关面板时若仍未锁定则恢复提示
  onOpenChange: (open) => {
    if (!open) hud.setLookHint(entered && !input.locked);
  },
});
window.__settings = { store: settings, ui: settingsUI }; // 截图/排错钩子（开发用）

function applyAllSettings() {
  world.applySettings(settings.values);
  mist.applySettings(settings.values);
  postfx.applySettings(settings.values);
  fireworks.applySettings(settings.values);
  wisps.applySettings(settings.values);
  if (player) player.applySettings(settings.values);
  if (ferris) ferris.applySettings(settings.values);
  if (carousel) carousel.applySettings(settings.values);
  if (coaster) coaster.applySettings(settings.values);
  if (tower) tower.applySettings(settings.values); // 缠魂塔装饰灯 (含呼梯灯)
  if (wind) wind.applySettings(settings.values); // 风摆强度 + 南瓜灯亮度联动
  audio.setBGM(settings.values.bgmOn !== false); // 背景音乐开关 (音频未启动时只记意图)
  audio.setFireworks(settings.values); // 烟花音量 / 声延迟 / 升空哨音响量 / 裂响亮度 / 碎裂 (音频未启动时只记意图)
}
applyAllSettings(); // 恢复持久化配置（含舱内灯光默认 40%）
settings.onChange(applyAllSettings);

// 「就绪」= 加载管理器的资源全部到位 且 boot() 收尾完毕（交互 / 键盘回调都已注册），两个条件都满足才放开入园按钮。
// LoadingManager 在「已加载数 == 已登记数」时触发 onLoad —— boot 里资源是逐个 await 串行加载的，第一个 glb 下完的
// 那一刻两个数恰好相等，onLoad 会提前约 1.5s 触发：按钮可点而入园回调还没注册，点了没反应（自动取证首击必空）。
// 同理不用它的进度（第一个文件下完就是 100%，进度条会先冲顶再掉回），加载进度只认 boot 里各阶段的手动刻度。
let assetsLoaded = false;
let bootDone = false;
const tryReady = () => { if (assetsLoaded && bootDone) hud.setReady(); };
const manager = createLoadingManager({
  onLoad: () => { assetsLoaded = true; tryReady(); },
});

const updates = [world, mist, fireworks, wisps];

async function boot() {
  // 碰撞与玩法锚点
  let park = null;
  try {
    park = await (await fetch("/assets/models/colliders.json")).json();
  } catch {
    console.warn("[park] colliders.json 加载失败, 使用空碰撞");
  }
  window.__park = park;
  // 第 7 座发射架 (过山车提升顶旁的垂柳塔, 地标礼花用; 独立小资产 salute_launcher.glb):
  // 锚点须在 setLaunchers 之前并入, 碰撞圆须在下方 createPlayer 拷贝碰撞表之前并入
  try {
    const sl = await (await fetch("/assets/models/colliders_salute_launcher.json")).json();
    if (park) {
      park.launchers = [...(park.launchers ?? []), ...sl.launchers];
      park.circles = [...(park.circles ?? []), ...sl.circles];
    }
  } catch {
    console.warn("[park] colliders_salute_launcher.json 加载失败, 过山车顶无礼花发射架");
  }
  fireworks.setLaunchers(park?.launchers); // 地面 6 站 + 垂柳塔 { id, kind, x, z, dx, dz, mz }

  // 过山车碰撞表 (M3): 合并进 park (rects=盒墙 / circles=柱 / steps=台阶顶面由控制器接管)
  try {
    const cc = await (await fetch("/assets/models/colliders_coaster.json")).json();
    park.rects = [...(park?.rects ?? []), ...cc.rects];
    park.circles = [...(park?.circles ?? []), ...cc.circles];
    park.steps = cc.steps ?? [];
  } catch {
    console.warn("[park] colliders_coaster.json 加载失败, 过山车区无碰撞");
  }
  // M4 登车动线碰撞 (须在 createPlayer 拷贝 rects 前注入; tag/blockFrom 字段随 spread 带入控制表):
  //  ① 闸线 rect 打 tag (坐标唯一匹配, epsilon 防浮点表示差异) —— 闸机开闸时经 setRectDisabled 禁用
  const gateRect = park.rects?.find((r) => Math.abs(r.x - 9.4) < 1e-6 && Math.abs(r.z + 40.4) < 1e-6);
  if (gateRect) gateRect.tag = "coasterGate";
  else console.warn("[coaster] 未找到闸线碰撞 rect (9.4,-40.4), 开闸将不生效");
  // ② 东槽单向墙: 只挡走廊侧 -z 北上逆爬 (移动方向判定见 controller.tryMove), 下行 +z 畅通, 跳跃无效
  park.rects.push({ x: 13.6, z: -40.45, hw: 0.85, hd: 0.12, blockFrom: "z+" });
  // ③ 站台内缘防坠墙 x2: 堵双 deck 间轨道凹坑 (已核对不挡双槽动线与登车交互半径)
  park.rects.push({ x: 10.75, z: -55, hw: 0.12, hd: 11.2 }, { x: 12.25, z: -55, hw: 0.12, hd: 11.2 });

  // 缠魂塔碰撞表 (M5): 须在 createPlayer 拷贝碰撞表之前并入 park ——
  //   floors = 叠层地面(螺旋梯/环廊/栈桥, controller 塔语义接管) / circles = 带高度带 y0,y1 的圆 /
  //   lift = 升降梯动态项 (rides/tower.js 每帧驱动) / pois = 带高度 y 的打卡点
  try {
    const tc = await (await fetch("/assets/models/colliders_tower.json")).json();
    park.floors = tc.floors ?? [];
    park.circles = [...(park?.circles ?? []), ...(tc.circles ?? [])];
    park.lift = tc.lift;
    park.pois = [...(park?.pois ?? []), ...(tc.pois ?? [])];
    park.tower = tc;
  } catch {
    console.warn("[park] colliders_tower.json 加载失败, 缠魂塔无碰撞且升降梯停摆");
  }

  player = createPlayer(camera, input, park);
  player.applySettings(settings.values); // 恢复持久化步速（applyAllSettings 初次执行时 player 尚未创建）

  // 资产
  hud.setLoadingProgress(0.3); // 布场
  const parkRoot = await loadGLB("/assets/models/park_env.glb", manager);
  hud.setLoadingProgress(0.6); // 铺路
  scene.add(parkRoot);
  // 过山车提升顶旁的垂柳塔发射架 (第 7 座, 地标礼花): 小资产, 不等它; 加载失败只是少一件道具
  loadGLB("/assets/models/salute_launcher.glb", manager)
    .then((root) => scene.add(root))
    .catch(() => console.warn("[park] salute_launcher.glb 加载失败, 垂柳塔发射架不可见"));
  wind = createWind(parkRoot); // 风摆 (草/柳/松/枯梢) + 南瓜灯发光联动
  wind.applySettings(settings.values);
  updates.push(wind);

  const wheelRoot = await loadGLB("/assets/models/ferris_wheel.glb", manager);
  hud.setLoadingProgress(0.85); // 召轮
  // 注: legacy FW_Ground 地面盘已在 Blender 管线导出前移除 (ferris_wheel.py v2.3),
  // app 侧地面由 park_env.glb 提供
  scene.add(wheelRoot);
  ferris = createFerrisWheel(wheelRoot);
  ferris.applySettings(settings.values); // 摩天轮就位后补应用（含持久化配置）
  updates.push(ferris);

  // 显灵木马: 原点建模资产摆到东北园区 (blender (45,18) -> app (45,-18));
  // 平台/中柱/台阶/围栏碰撞为静态表 (colliders.json), 骑乘位/铜杆由 carousel.js 动态驱动
  const carouselRoot = await loadGLB("/assets/models/carousel.glb", manager);
  hud.setLoadingProgress(0.9); // 请灵
  carouselRoot.position.set(45, 0, -18);
  scene.add(carouselRoot);
  carousel = createCarousel(carouselRoot, { player });
  carousel.applySettings(settings.values);
  updates.push(carousel);

  // 幽冥回环 (M3): 静态件恒等放置(与园区共享原点) + 中心线驱动列车观赏运行
  hud.setLoadingProgress(0.93); // 起环
  coaster = await createCoaster(scene, manager);
  coaster.applySettings(settings.values); // 过山车就位后补应用（含持久化配置）
  updates.push(coaster);

  // 验票闸机 (M4): 闸翼转子开合动画 + 闸线碰撞随开合禁用 (coaster.staticRoot 内解析 NL_Gate_*)
  coasterGate = createCoasterGate(coaster.staticRoot, {
    player,
    onSolid: (passable) => player.setRectDisabled("coasterGate", passable),
  });
  updates.push(coasterGate);

  // 缠魂塔 (M5): 资产 + 升降梯 + 塔冠动效; 碰撞表已在上方并入 park。
  // 更新序须排在玩家之前 (轿厢地面高度 / 轿壁高度带每帧先写, 控制器后读)
  hud.setLoadingProgress(0.95); // 缠魂
  tower = await createTower(scene, manager, { park, player, hud, audio });
  tower.applySettings(settings.values);
  updates.push(tower);

  // 交互
  let camMode = "pov"; // M4 过山车乘坐视角: pov | chase
  interact = createInteract({
    input, hud, audio,
    player, park, fireworks,
    coaster, coasterGate, tower, carousel,
    getState: () => game.state,
    onOpenGate() {
      if (game.state !== "walk") return;
      coasterGate.tryOpen();
    },
    onBoardCoaster() {
      if (game.state !== "walk" || coaster.state.phase !== "dwell" || coaster.state.session.active) return;
      game.state = "boarding";
      game.ride = "coaster";
      audio.setRiding(true);
      camMode = "pov";
      coaster.setRideCam("pov");
      hud.transition(() => {
        coaster.board();
        player.enterRide((dt) => coaster.getRideFrame(camMode, dt));
        hud.showPlaque("幽冥回环", "自由环视 · V 切换追逐镜头 · R 回正视角 · E 排队下车");
        game.state = "riding";
      });
    },
    onBoard() {
      if (game.state !== "walk") return;
      game.state = "boarding";
      game.ride = "ferris";
      audio.setRiding(true);
      hud.transition(() => {
        ferris.board();
        player.enterCabin(() => ferris.getRideFrame());
        hud.showPlaque("幽眠摩天轮", "高空观光 · WASD 舱内走动 · C 坐下起身 · E 随时下乘");
        game.state = "riding";
      });
    },
    onBoardCarousel() {
      if (game.state !== "walk") return;
      game.state = "boarding";
      game.ride = "carousel";
      audio.setRiding(true);
      hud.transition(() => {
        const idx = carousel.board();
        const fr = carousel.getMountFrame();
        player.enterMount(() => carousel.getMountFrame());
        player.setView(fr.yaw, -0.04); // 初始视线 = 灵兽行进方向
        hud.showPlaque(carousel.nameOf(idx), "显灵木马 · 灵兽环游 · 自由环视 · E 随时下乘"); // 铭牌报坐骑名
        game.state = "riding";
      });
    },
    onCollect(poi, got, total) {
      if (got === total) hud.setStars(total, total);
    },
  });
  updates.push(interact);

  // 乘坐中 E 下客（按 ride 分流: 过山车=排队下一站下车; 摩天轮回地面登舱点 / 木马下马回平台）
  input.onPress("KeyE", () => {
    if (game.state !== "riding") return;
    if (game.ride === "coaster") {
      if (coaster.state.session.wantOff) {
        if (coaster.cancelDisembark()) {
          hud.showPlaque("幽冥回环", "自由环视 · V 切换追逐镜头 · R 回正视角 · E 排队下车");
          hud.toast("已取消下车排队");
        }
      } else if (coaster.queueDisembark()) {
        hud.showPlaque("幽冥回环", "已排队下车 · 到站自动下客 · 再按 E 取消");
      }
      return;
    }
    const kind = game.ride;
    game.state = "exiting";
    audio.setRiding(false);
    hud.transition(() => {
      if (kind === "carousel") {
        const drop = carousel.dismountPoint();
        player.exitMount();
        carousel.dismount();
        player.teleport(drop.x, drop.z); // 平台上落点, y 由地面支撑接管
      } else {
        player.exitCabin();
        ferris.disembark();
        // 统一送回地面登舱点（站台登舱后避免落在站台投影内；淡入淡出掩盖位移）
        player.teleport(park?.boarding?.x ?? 0, park?.boarding?.z ?? 16.4);
      }
      game.ride = null;
      hud.hidePlaque();
      game.state = "walk";
    });
  });

  // 烟花发射器：靠近时按 F 单发点射（interact.update 提供就近判定与提示）
  input.onPress("KeyF", () => {
    if (game.state !== "walk") return;
    const lid = interact.nearLauncher();
    if (lid >= 0) fireworks.fire(lid);
  });

  // M4: V 键切换过山车乘坐视角 (POV ↔ 第三人称追逐; 切换重置阻尼起点与视线偏移防甩镜)
  input.onPress("KeyV", () => {
    if (game.state !== "riding" || game.ride !== "coaster") return;
    camMode = camMode === "pov" ? "chase" : "pov";
    coaster.setRideCam(camMode);
    player.resetRideView();
    hud.toast(camMode === "pov" ? "第一人称 · 车长位" : "第三人称 · 追逐镜头");
  });

  // M4: R 键回正视角 (自由环视后回到主视角; 强阻尼平滑归位, POV/追逐通用)
  input.onPress("KeyR", () => {
    if (game.state !== "riding" || game.ride !== "coaster") return;
    player.resetRideView();
  });

  // M4: 到站停稳 + 压肩开启 → 自动下客 (黑幕转场送东 deck, 玩家步行东阶下场)
  coaster.onDisembarkReady = () => {
    if (game.state !== "riding") return;
    game.state = "exiting";
    audio.setRiding(false);
    hud.transition(() => {
      player.exitRide();
      coaster.disembark();
      const drop = coaster.getDropSpot();
      player.teleport(drop.x, drop.z); // 首帧 groundAt 吸附 deck 顶 2.38
      game.ride = null;
      hud.hidePlaque();
      game.state = "walk";
    });
  };

  // 指针锁定（面板打开时不出「点击画面」提示，避免与抽屉重叠）
  input.onLockChange((locked) => hud.setLookHint(entered && !locked && !settingsUI.isOpen));
  canvas.addEventListener("click", () => {
    if (entered && !input.locked) input.requestLock();
  });

  hud.onEnter(() => {
    entered = true;
    hud.enterPark();
    input.requestLock(); // 用户手势内申请指针锁定
    audio.ensure();      // 音频图需用户手势启动
    game.state = "walk";
    hud.toast("欢迎来到幽夜游乐场 · 空格跳跃");
  });

  // 玩家每帧：园区行走或舱内走动（舱内相机由玩家控制器挂舱，ferris.update 先行）
  updates.push({
    update(dt) {
      // 站台安全联锁：站在摩天轮登舱站台（台面 1.55, 半径 9）时轮体缓停吸附舱位。
      // 只看高度会误伤：站上缠魂塔 / 过山车站台都会把轮刹停，所以同时限定到站台圆内
      ferris.setHold(
        game.state === "walk" && player.pos.y > 1.4 && player.pos.y < 2.2 &&
        Math.hypot(player.pos.x, player.pos.z) < 9.8,
      );
      // M4 过山车站台联锁: walk 态站上站台时列车保持停靠 (乘坐中 state≠walk 自然放行)
      coaster.setHold(
        game.state === "walk" && player.pos.y > 2.0 &&
        player.pos.z < -43.5 && player.pos.x > 7.5 && player.pos.x < 15.5,
      );
      player.update(dt);
      interact.update();
    },
  });

  // 地标礼花导演: 三处炸点 (缠魂塔环廊 / 摩天轮顶舱 / 过山车提升顶) + 到顶准点触发。
  // 排在玩家更新之后 (读的是本帧的脚高/乘坐状态); 礼花入列后在下一帧 fireworks.update 出膛
  fwDirector = createFireworkDirector({ fireworks, player, ferris, coaster, park, getState: () => game.state });
  updates.push(fwDirector);

  game.state = "loading";
}

boot().then(() => {
  bootDone = true;
  tryReady(); // 与 LoadingManager 的 onLoad 汇合后才 setReady（见上方 tryReady 注释）
}).catch((err) => {
  console.error("[boot] 启动中断", err);
  bootDone = true;
  tryReady();
});

// ---------- 主循环 ----------
const clock = { last: performance.now() };
renderer.setAnimationLoop(() => {
  const now = performance.now();
  const dt = Math.min((now - clock.last) / 1000, 0.1);
  clock.last = now;
  const elapsed = now / 1000;
  for (const cb of updates) cb.update(dt, elapsed);
  postfx.render();
});

// 调试钩子（截图/排错/性能核对）
window.__game = {
  get state() { return game.state; },
  get ride() { return game.ride; },
  get player() { return player; },
  get ferris() { return ferris; },
  get carousel() { return carousel; },
  get coaster() { return coaster; },
  get coasterGate() { return coasterGate; },
  get tower() { return tower; },
  get interact() { return interact; },
  get audio() { return audio; },
  get fireworks() { return fireworks; },
  get fwDirector() { return fwDirector; },
  get camera() { return camera; },
  renderer,
  scene,
};
