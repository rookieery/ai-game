// 缠魂塔 SOUL SPIRE (M5) —— 资产加载 / 升降梯 / 塔冠动效 / 装饰灯联动
// 数据契约 (model/lookout_tower/, 详见其 README):
//   lookout_tower.glb      原点建模, 摆到 colliders_tower.json 的 place (过山车地面灯环圆心)
//   colliders_tower.json   main.js 在 createPlayer 之前并入 park:
//                          floors(叠层地面) / circles(带高度带 y0,y1) / lift(升降梯动态项) / pois(带高度 y)
// 运行时节点: TW_Lift(轿厢根, y=轿底) / TW_GateB,T(轿厢滑门, 轿厢子节点) / TW_LGateB,T(两站层门)
//            TW_CallLamp_B,T(呼梯灯, 独立材质) / TW_FlameAnchor(灯室鬼火锚点) / TW_CrowPivot(乌鸦风向标转轴)
// 升降梯玩法 (玩家全程是园区步行模式: 轿厢地面是 sticky 叠层地面, controller 贴地分支逐帧跟随):
//   走近任一站的停站点 → 自动呼梯 → 到站后层门、轿门依次滑开 → 走进轿厢按 E → 关门升降 → 到站开门走出
import * as THREE from "three";
import { loadGLB } from "../park/loader.js";

const DOOR_T = 0.9;          // 门开/关时长 s
const V_MAX = 4.5;           // 轿厢峰速 m/s
const ACC = 1.6;             // 加减速度 m/s² (39.86m 行程约 12s)
// 自动呼梯范围 (且人在该站的高度):
//   顶层 = 栈桥上的圆, 半径 2.4m。必须 <= 2.9: 塔顶打卡南瓜灯离停站点 5.1m、打卡半径 2.2m, 再大会让呼梯提示盖掉打卡提示
//   底层 = 南门前的扇区, 门方位 ±28°、r < 5.6m (门厅 + 门廊)。不能用圆: 螺旋梯最下面几级离停站点只有 1.8m,
//          圆形范围会让上下楼梯的人把轿厢叫走 —— 「爬上去、坐梯下来」刚上梯就把轿厢叫下去, 到顶还得空等 14s
const CALL_R = { B: 5.6, T: 2.4 };
const CALL_HALF_B = (28 * Math.PI) / 180;
const DWELL = 0.6;           // 停站且门开满之后, 过这么久才响应下一次呼梯 / 轿内 E s (到站是立刻开门的)
const BLOCK_MAX = 3.0;       // 关门被挡这么久就放弃本次运行 (重新开门) s
const CAB_GATE_OPEN = 0.9;   // 轿门开度到此才撤掉门洞碰撞 (再早人能穿过半开的门扇)
const LGATE_OPEN = 0.6;      // 层门开度到此才撤掉门洞碰撞 (已滑开 0.9m, 够一人过)
const PR = 0.38;             // 玩家碰撞半径 (与 player/controller.js 一致, 只用于「关门被挡」判定)
const CAB_GATE_MARGIN = 0.12; // 轿门防挟余量: 人的碰撞圆离门洞碰撞盘这么近就算挡门 (离门扇约 0.4m, 不夹人)
const LGATE_MARGIN = 0.06;    // 层门防挟余量。不能更大: 轿门关上后乘客可停在内侧 0.84m 处, 离层门盘 0.78m
const ST = ["B", "T"];       // 两站: B 底层 (南门) / T 顶层 (北门)
const LAMP = {               // 呼梯灯色: 绿 = 轿厢在本站 / 琥珀闪 = 正在赶来 / 红 = 不在本站
  here: [0.25, 1.0, 0.42],
  coming: [1.0, 0.62, 0.12],
  away: [1.0, 0.1, 0.1],
};
const toward = (v, target, step) => (v < target ? Math.min(target, v + step) : Math.max(target, v - step));
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

function makeFlameTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(32, 32, 1, 32, 32, 30);
  grad.addColorStop(0, "rgba(236,255,250,1)");
  grad.addColorStop(0.3, "rgba(143,227,217,0.5)");
  grad.addColorStop(1, "rgba(143,227,217,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

export async function createTower(scene, manager, { park, player, hud, audio }) {
  const man = park?.tower ?? {};
  const L = park?.lift ?? null; // colliders_tower.json 的 lift 段; 缺失则升降梯停摆 (不响应呼梯)
  const live = !!L && !!player;
  const place = man.place ?? { x: 17.5, z: -30.5 };
  const root = await loadGLB("/assets/models/lookout_tower.glb", manager);
  root.position.set(place.x, 0, place.z);
  scene.add(root);
  root.updateMatrixWorld(true);

  const node = (name) => root.getObjectByName(name);
  const liftNode = node("TW_Lift");
  const gateNode = { B: node("TW_GateB"), T: node("TW_GateT") };
  const lgateNode = { B: node("TW_LGateB"), T: node("TW_LGateT") };
  const crowPivot = node("TW_CrowPivot");
  const flameAnchor = node("TW_FlameAnchor");
  const missing = Object.entries({ TW_Lift: liftNode, TW_GateB: gateNode.B, TW_GateT: gateNode.T,
    TW_LGateB: lgateNode.B, TW_LGateT: lgateNode.T, TW_CrowPivot: crowPivot, TW_FlameAnchor: flameAnchor })
    .filter(([, o]) => !o).map(([n]) => n);
  if (missing.length) console.warn("[tower] glb 缺节点:", missing.join(", "));

  // ---- 装饰灯材质登记 (设置面板「缠魂塔 · 装饰灯亮度」): 全部 TW_ 自发光材质; 呼梯灯另管 (颜色随状态) ----
  const glowMats = [];
  const lampMats = {};
  root.traverse((o) => {
    const mats = Array.isArray(o.material) ? o.material : (o.material ? [o.material] : []);
    for (const m of mats) {
      if (!m.name || !m.name.startsWith("TW_") || !m.emissive) continue;
      if (m.emissive.r + m.emissive.g + m.emissive.b < 1e-3) continue; // 非自发光
      const base = m.emissiveIntensity ?? 1;
      if (m.name === "TW_CallLamp_B") lampMats.B = { m, base };
      else if (m.name === "TW_CallLamp_T") lampMats.T = { m, base };
      else if (!glowMats.some((g) => g.m === m)) glowMats.push({ m, base });
    }
  });
  let decoK = 1;

  // ---- 几何常量 (全部取自碰撞表, 缺表时用资产契约的兜底值) ----
  const zBottom = L?.zBottom ?? 0.06;
  const zTop = L?.zTop ?? 39.92;
  const floorThk = L?.floorThk ?? 0.08;
  const cabR = L?.cabR ?? 1.3;
  const cx = L?.floor.x ?? place.x;
  const cz = L?.floor.z ?? place.z;
  const stationH = { B: zBottom + floorThk, T: zTop + floorThk };            // 站台地面高
  const spot = { B: L?.spotBottom ?? [place.x, place.z + 2.62], T: L?.spotTop ?? [place.x, place.z - 2.53] };
  const wallBand = L?.wallBand ?? [-0.3, 2.6];
  const openBand = L?.openBand ?? [-5, -4];                                  // 撤掉碰撞用的高度带 (脚底到不了)
  const closedBand = { B: L?.lgateB.closedBand ?? [-1, 2.85], T: L?.lgateT.closedBand ?? [39.5, 42.6] };

  // ---- 动态碰撞: 轿厢地面(sticky 叠层地面) + 轿壁/轿门/层门(带高度带的圆), 每帧改写 y0/y1/h ----
  const floor = L ? { ...L.floor, sticky: true } : { sticky: true };
  const walls = L ? L.walls.map((c) => ({ ...c })) : [];
  const gate = L ? { B: { ...L.gateB.post }, T: { ...L.gateT.post } } : { B: {}, T: {} };
  const lgate = L
    ? { B: L.gateBottom.map((c) => ({ ...c })), T: L.gateTop.map((c) => ({ ...c })) }
    : { B: [], T: [] };
  if (live) {
    player.registerFloors([floor]);
    player.registerCircles([...walls, gate.B, gate.T, ...lgate.B, ...lgate.T]);
  }

  // ---- 门节点: 静止位 (glb 导出 = 关门位) + 开门位移向量 (碰撞表给出, 节点局部 Y-up) ----
  const rest = (n) => (n ? n.position.clone() : new THREE.Vector3());
  const gateRest = { B: rest(gateNode.B), T: rest(gateNode.T) };
  const lgateRest = { B: rest(lgateNode.B), T: rest(lgateNode.T) };
  const openV = {
    B: new THREE.Vector3(...(L?.gateB.open ?? [-1.14, 0, 0])),
    T: new THREE.Vector3(...(L?.gateT.open ?? [1.14, 0, 0])),
  };
  const lopenV = {
    B: new THREE.Vector3(...(L?.lgateB.open ?? [-1.5, 0, 0])),
    T: new THREE.Vector3(...(L?.lgateT.open ?? [1.5, 0, 0])),
  };
  const setBand = (c, b) => { c.y0 = b[0]; c.y1 = b[1]; };

  // ---- 升降梯状态 ----
  const st = {
    y: zBottom,            // 轿底高度
    v: 0,                  // 速度 m/s
    phase: "dwell",        // dwell 停站 | closing 关门 | moving 升降 | opening 开门
    at: "B",               // 所在站 (closing/opening 时 = 正在离开/到达的站)
    target: "T",           // 目标站
    door: { B: 1, T: 0 },  // 轿门开度 0 关 .. 1 开
    lgate: { B: 1, T: 0 }, // 层门开度
    timer: DWELL,          // 停站计时 (到点才响应呼梯 / 轿内 E)
    want: false,           // 轿厢内有人按了 E, 关门后开往另一站
    blockT: 0,             // 关门被挡时长
    laps: 0,               // 运行趟数 (取证用)
    aboard: false,         // 玩家在轿厢内
    moving: false,
  };
  let humOn = false;
  let plaqueOn = false;
  const otherOf = (S) => (S === "B" ? "T" : "B");
  const wrapPi = (a) => Math.atan2(Math.sin(a), Math.cos(a));
  const doorAz = { B: Math.atan2(gate.B.z - cz, gate.B.x - cx), T: Math.atan2(gate.T.z - cz, gate.T.x - cx) }; // 门洞方位 (取自碰撞表的轿门位)
  // 人是否在 S 站的呼梯范围里 (高度 + 平面范围; 指引提示也用它)
  const nearStation = (p, S) => {
    if (Math.abs(p.y - stationH[S]) >= 1.5) return false;
    const dx = p.x - cx, dz = p.z - cz;
    if (S === "T") return Math.hypot(p.x - spot.T[0], p.z - spot.T[1]) < CALL_R.T;
    return Math.abs(wrapPi(Math.atan2(dz, dx) - doorAz.B)) <= CALL_HALF_B && Math.hypot(dx, dz) < CALL_R.B;
  };
  // 轿厢正在开往 S: 关门待发 (目标 S) / 升降中 (目标 S) / 已到 S 正在开门
  const headingTo = (S) =>
    st.phase === "opening" ? st.at === S
      : st.phase !== "dwell" && st.target === S;

  function ride() {
    if (!live || st.phase !== "dwell" || !st.aboard || st.want) return;
    st.want = true;
  }

  function update(dt, elapsed) {
    const pp = player?.pos ?? { x: cx, y: -99, z: cz };
    const floorH = st.y + floorThk;
    const dc = Math.hypot(pp.x - cx, pp.z - cz);
    const near = Math.abs(pp.y - floorH) <= 0.35;              // 脚底贴着轿厢地面
    st.aboard = live && near && dc <= cabR - 0.42;
    st.moving = st.phase === "moving";
    if (live) player.setJumpLock(st.aboard);                   // 轿厢净高 2.6m: 眼高 + 跳高会顶穿轿顶

    if (live) {
      // 「关门被挡」= 人的碰撞圆 (外加防挟余量) 碰到即将生效的门洞碰撞盘 (基础半径与 controller 推挤 r + PR 一致)
      const hit = (c, margin) => Math.hypot(pp.x - c.x, pp.z - c.z) < c.r + PR + margin;
      const straddle = near && dc > cabR - 0.36;               // 脚踩轿厢地面、人却还在门洞里
      const hitLgate = (S) => Math.abs(pp.y - stationH[S]) < 2.0 && lgate[S].some((c) => hit(c, LGATE_MARGIN));

      if (st.phase === "dwell") {
        st.timer -= dt;
        if (st.timer <= 0) {
          const other = otherOf(st.at);
          if (st.want && !st.aboard) st.want = false;          // 按了 E 又走出轿厢 → 取消
          const called = !st.aboard && !straddle && nearStation(pp, other);
          if (st.want || called) {
            st.phase = "closing";
            st.target = other;
            st.blockT = 0;
            if (called) hud?.toast("缠魂塔升降梯正在赶来");
          }
        }
      } else if (st.phase === "closing") {
        const S = st.at;
        let blocked = false;
        // 先关轿门、再关层门; 任一步门洞里有人就停住等 (层门还等人离开轿厢地面圆)
        if (st.door[S] > 0) {
          if (near && hit(gate[S], CAB_GATE_MARGIN)) blocked = true;
          else st.door[S] = Math.max(0, st.door[S] - dt / DOOR_T);
        } else if (st.lgate[S] > 0) {
          if (hitLgate(S) || straddle) blocked = true;
          else st.lgate[S] = Math.max(0, st.lgate[S] - dt / DOOR_T);
        } else if (straddle) blocked = true;
        if (blocked) {
          st.blockT += dt;
          if (st.blockT >= BLOCK_MAX) {                        // 挟持太久: 放弃本次运行, 重新开门
            st.phase = "opening";
            st.want = false;
            if (st.aboard || nearStation(pp, S)) hud?.toast("升降梯门被挡住 · 请走出门口或退回轿厢");
          }
        } else {
          st.blockT = 0;
          if (st.door[S] <= 0 && st.lgate[S] <= 0) {
            st.phase = "moving";
            if (st.aboard) {                                   // 有人乘坐: 乘坐嗡鸣 + 铭牌
              audio?.setRiding(true);
              hud?.showPlaque("缠魂塔", "升降梯行进中 · 到站后走出轿厢");
              humOn = plaqueOn = true;
            }
          }
        }
      } else if (st.phase === "moving") {
        // 梯形速度曲线: 制动限速 sqrt(2·a·剩余距离), 到站吸附
        const yT = st.target === "T" ? zTop : zBottom;
        const dir = yT > st.y ? 1 : -1;
        const vAllow = Math.min(V_MAX, Math.sqrt(2 * ACC * Math.abs(yT - st.y)));
        st.v = toward(st.v, vAllow, ACC * dt);
        const ny = st.y + dir * st.v * dt;
        if ((yT - ny) * dir <= 0) {
          st.y = yT;
          st.v = 0;
          st.at = st.target;
          st.phase = "opening";
          st.laps++;
          if (humOn) audio?.setRiding(false);
          if (plaqueOn) hud?.hidePlaque();
          humOn = plaqueOn = false;
          if (st.aboard) hud?.toast(st.at === "T" ? "已到塔顶 · 环廊海拔 40 米" : "已回到塔底");
          else if (nearStation(pp, st.at)) hud?.toast("升降梯已到站 · 走进轿厢按 E 升降");
        } else st.y = ny;
      } else {
        // opening: 到站先开层门、再开轿门
        const S = st.at;
        if (st.lgate[S] < 1) st.lgate[S] = Math.min(1, st.lgate[S] + dt / DOOR_T);
        else if (st.door[S] < 1) st.door[S] = Math.min(1, st.door[S] + dt / DOOR_T);
        else {
          st.phase = "dwell";
          st.timer = DWELL;
          st.want = false;
        }
      }

      // ---- 碰撞表随轿厢改写 (对象引用已注册进 controller) ----
      const dy = st.y - zBottom;
      const wall = [wallBand[0] + dy, wallBand[1] + dy];
      for (const c of walls) { c.y0 = wall[0]; c.y1 = wall[1]; }
      setBand(gate.B, st.door.B < CAB_GATE_OPEN ? wall : openBand);
      setBand(gate.T, st.door.T < CAB_GATE_OPEN ? wall : openBand);
      for (const c of lgate.B) setBand(c, st.lgate.B < LGATE_OPEN ? closedBand.B : openBand);
      for (const c of lgate.T) setBand(c, st.lgate.T < LGATE_OPEN ? closedBand.T : openBand);
      // 轿厢地面高度取状态机推进「之后」的 st.y。函数开头的 floorH 是推进前的值, 拿它写会让地面比轿厢慢一帧
      // (4.5m/s 下 144fps 差 3cm / 60fps 差 7.5cm: 上升时脚陷进地板, 下降时悬在地板上方)
      floor.h = st.y + floorThk;
    }

    // ---- 节点姿态 ----
    if (liftNode) liftNode.position.y = st.y;
    for (const S of ST) {
      if (gateNode[S]) gateNode[S].position.copy(gateRest[S]).addScaledVector(openV[S], st.door[S]);
      if (lgateNode[S]) lgateNode[S].position.copy(lgateRest[S]).addScaledVector(lopenV[S], st.lgate[S]);
    }

    // ---- 呼梯灯 ----
    for (const S of ST) {
      const lm = lampMats[S];
      if (!lm) continue;
      const here = st.phase === "dwell" && st.at === S;
      let col = LAMP.away;
      let k = 1;
      if (here) col = LAMP.here;
      else if (headingTo(S)) { col = LAMP.coming; k = 0.45 + 0.55 * (0.5 + 0.5 * Math.sin(elapsed * 9)); }
      lm.m.emissive.setRGB(col[0], col[1], col[2]);
      lm.m.emissiveIntensity = lm.base * k * decoK;
    }

    // ---- 塔冠动效: 乌鸦风向标缓摆 + 灯室鬼火绕锚点慢转 ----
    if (crowPivot) {
      crowPivot.rotation.y = 0.9 * Math.sin(elapsed * 0.13) + 0.5 * Math.sin(elapsed * 0.071 + 1.3) + 0.25 * Math.sin(elapsed * 0.31);
    }
    for (const f of flames) {
      const t = elapsed * 0.5 + f.phase;
      f.s.position.set(
        f.c.x + Math.sin(t * 0.55) * 0.75,
        f.c.y + Math.sin(t * 0.9 + 1.3) * 0.25,
        f.c.z + Math.cos(t * 0.42 + 0.7) * 0.75,
      );
      f.s.material.opacity = 0.7 * decoK * (0.6 + 0.4 * Math.sin(t * 1.7 + f.phase * 3.1));
    }
  }

  // ---- 灯室鬼火: 3 颗加色 sprite (与园区幽灵火同款画法; 亮度随「缠魂塔 · 装饰灯」而不随地面漂雾) ----
  const flames = [];
  if (flameAnchor) {
    const tex = makeFlameTexture();
    const c = flameAnchor.getWorldPosition(new THREE.Vector3());
    for (let i = 0; i < 3; i++) {
      const s = new THREE.Sprite(new THREE.SpriteMaterial({
        map: tex, color: "#8FE3D9", blending: THREE.AdditiveBlending, transparent: true, opacity: 0.7, depthWrite: false,
      }));
      s.scale.setScalar(1.1);
      s.frustumCulled = false;
      scene.add(s);
      flames.push({ s, c, phase: i * 2.1 });
    }
  }

  update(0, 0); // 首帧摆位 (轿厢停在底层、南门开)

  return {
    root,
    state: st,
    update,
    getPrompt(p) {
      if (!live) return null;
      if (st.aboard) {
        if (st.phase === "dwell" && st.timer <= 0 && !st.want) {
          return { label: `乘升降梯 · ${st.at === "B" ? "登上塔顶" : "下到塔底"}`, run: ride };
        }
        return null;
      }
      for (const S of ST) {
        if (!nearStation(p, S)) continue;
        const key = S === "B" ? "↑" : "↓";
        if (st.phase === "dwell" && st.at === S) return { label: "走进轿厢 · 按 E 升降", key };
        return { label: "升降梯正在赶来", key };
      }
      return null;
    },
    applySettings(s) {
      decoK = clamp(s.towerDecoLight ?? 100, 0, 200) / 100;
      for (const { m, base } of glowMats) m.emissiveIntensity = base * decoK;
    },
    spotOf: (S) => ({ x: spot[S][0], y: stationH[S], z: spot[S][1] }),
    // 取证钩子: 把轿厢直接摆到高度 y (在站点时门开度 door), 常用于实机截图
    debugPlace(y, door = 0) {
      const S = Math.abs(y - zTop) < 0.01 ? "T" : Math.abs(y - zBottom) < 0.01 ? "B" : null;
      st.y = y;
      st.v = 0;
      st.phase = "dwell";
      st.at = S ?? st.at;
      st.timer = DWELL;
      st.want = false;
      for (const k of ST) { st.door[k] = k === S ? door : 0; st.lgate[k] = k === S ? door : 0; }
      update(0, 0);
    },
  };
}
