// 交互系统：距离检测 -> 灵摆提示 -> E 触发（登舱 / 上马 / 打卡收集 / 缠魂塔升降梯）+ F 烟花发射器
import { KIND_NAME } from "./fx/fireworks.js";
import { STATION } from "./player/controller.js";

export function createInteract({
  input, player, park, hud, getState, onBoard, onBoardCarousel, onCollect, audio, fireworks,
  coaster, coasterGate, onOpenGate, onBoardCoaster, tower, carousel, ferris,
}) {
  // 显灵木马平台 (45,-18) r8.0: 台面上 (y≈0.62) 靠近中柱侧 r<7.6 出提示
  const carouselCenter = { x: 45, z: -18 };
  // 烟花发射器 x6: 就近出「按 F 点射」提示（E 不响应, 不与打卡/乘坐冲突）
  const launchers = fireworks?.getLaunchers() ?? [];
  const pois = (park?.pois ?? []).filter((p) => String(p.label).startsWith("pumpkin"));
  const collected = new Set();
  let active = null; // { label, run }
  let nearLauncher = -1; // 就近发射器下标, -1 = 无

  const dist2 = (ax, az, bx, bz) => Math.hypot(ax - bx, az - bz);

  function collect(poi) {
    if (collected.has(poi.label)) return;
    collected.add(poi.label);
    hud.setStars(collected.size, pois.length);
    audio.chime(collected.size);
    if (collected.size === pois.length) hud.toast("星图圆满 · 幽夜向你低语 ✦");
    else hud.toast(`收下了第 ${collected.size} 盏南瓜灯`);
    if (onCollect) onCollect(poi, collected.size, pois.length);
  }

  input.onPress("KeyE", () => {
    if (getState() !== "walk" || !active) return;
    active.run();
  });

  return {
    collectedCount: () => collected.size,
    poiTotal: () => pois.length,
    nearLauncher: () => nearLauncher,
    debugCollect(n) {
      for (const p of pois) {
        if (collected.size >= n) break;
        collect(p);
      }
    },
    update() {
      if (getState() !== "walk") {
        hud.hidePrompt();
        active = null;
        nearLauncher = -1;
        return;
      }
      const p = player.pos;
      active = null;
      nearLauncher = -1;
      let label = "";

      // M4 座位登车: 站台上靠近停靠头车车长位 (列车 dwell 停靠且无乘坐会话)
      const bSpot = coaster?.getBoardSpot?.();
      if (bSpot && p.y > 2.0 && coaster.state.phase === "dwell" && !coaster.state.session.active &&
          dist2(p.x, p.z, bSpot.x, bSpot.z) < 1.9) {
        active = { run: onBoardCoaster };
        label = "登上幽冥回环 · 车长位";
      }
      // M4 过山车闸机: 走廊内侧靠近提示开闸 (p.z<-39.35 限走廊带内, 防提示隔南墙泄漏;
      // 站台侧不出提示 = 西口只进不出)
      const gSpot = coasterGate?.getSpot?.();
      if (!active && gSpot && p.y < 0.6 && p.z > -40.2 && p.z < -39.35 && coasterGate.isClosed() &&
          dist2(p.x, p.z, gSpot.x, gSpot.z) < 2.4) {
        active = { run: onOpenGate };
        label = "开闸进站";
      }
      // M4 指路: 走廊南墙外侧 (广场侧) 靠近闸机 —— 该处无入口, 指向迷宫东口 (纯指引, 无 E 动作)
      if (!active && gSpot && p.y < 0.6 && p.z > -39.0 &&
          dist2(p.x, p.z, gSpot.x, gSpot.z) < 5.0) {
        hud.showPrompt("排队请走迷宫入口 · 沿光带护栏向西南", "↙");
        return;
      }
      // M5 缠魂塔升降梯: 轿厢内按 E 升降 (E 动作); 停靠点旁只出指引 (键帽用 ↑↓ 箭头, 同走廊指路口径)
      const tw = tower?.getPrompt?.(p);
      if (tw) {
        hud.showPrompt(tw.label, tw.key ?? "E");
        if (tw.run) active = { run: tw.run };
        return;
      }
      // 登舱（v3 第 2 批 2026-11-27：站台是必经之路）—— 三个条件同时满足才出「乘坐摩天轮」：
      //   ① 在站台上（脚高 > 1.4）  ② 到了闸口（z < GATE_Z + 0.4：站在开着的闸门口或已过闸）且离登舱锚点 1.0 m 内
      //   ③ 轮已停稳、停靠舱吸附到位（登舱闸也只在此时开，见 rides/ferris.js）
      // z 上限取闸口里侧而不是闸线: 人走到闸门口就停步也算到了。闸关着时人被挡在 z ≥ 2.33 以外,
      // 加上条件 ③, 不会隔着闸出提示。地面不再有登舱点: 台阶脚门楼附近只出指路提示（函数末尾，无 E 动作）
      const b = STATION.BOARD;
      if (p.y > 1.4 && p.z < STATION.GATE_Z + 0.4 &&
          dist2(p.x, p.z, b.x, b.z) < b.r && ferris?.isDocked()) {
        active = { run: onBoard };
        label = "乘坐摩天轮";
      } else {
        // 打卡点排在上马提示之前 (2026-11-26): 盘心祭坛的南瓜灯就落在上马范围 (盘面 r<7.6) 里,
        // 排在后面的话站在它旁边永远只会出「骑上…」
        for (const poi of pois) {
          if (collected.has(poi.label)) continue;
          if (poi.y !== undefined && Math.abs(p.y - poi.y) > 2.5) continue; // 塔顶打卡点: 人得在那一层
          if (dist2(p.x, p.z, poi.x, poi.z) < 2.2) {
            active = { run: () => collect(poi) };
            label = `收集南瓜灯（${collected.size + 1}/${pois.length}）`;
            break;
          }
        }
        // 显灵木马盘面: 就近上马, 提示报出坐骑名 (旧版恒为「骑上显灵木马」)
        if (!active &&
            p.y > 0.4 && p.y < 1.2 &&
            dist2(p.x, p.z, carouselCenter.x, carouselCenter.z) < 7.6) {
          active = { run: onBoardCarousel };
          label = `骑上${carousel?.nameOf(carousel.nearest()) ?? "显灵木马"}`;
        }
        // 烟花发射器：E 槽位空闲时才提示（不与打卡/乘坐抢交互）; 键位徽标用 F
        if (!active && launchers.length) {
          let best = -1;
          let bestD = 3.2;
          for (let i = 0; i < launchers.length; i++) {
            const d = dist2(p.x, p.z, launchers[i].x, launchers[i].z);
            if (d < bestD) { bestD = d; best = i; }
          }
          if (best >= 0) {
            nearLauncher = best;
            label = fireworks.isReady(best)
              ? `${KIND_NAME[launchers[best].kind] ?? "烟花发射器"} · F 点射`
              : "烟花装填中…";
            hud.showPrompt(label, "F");
            return;
          }
        }
      }

      if (active) hud.showPrompt(label);
      // 摩天轮指路（纯指引，无 E 动作）：站在台阶脚门楼附近的地面上 —— 登舱要上站台、过登舱闸
      else if (p.y < 0.6 && dist2(p.x, p.z, STATION.PORTAL.x, STATION.PORTAL.z) < STATION.PORTAL.r) {
        hud.showPrompt("乘坐摩天轮 · 请上站台", "↑");
      } else hud.hidePrompt();
    },
  };
}
