// 交互系统：距离检测 -> 灵摆提示 -> E 触发（登舱 / 上马 / 打卡收集）+ F 烟花发射器
import { KIND_NAME } from "./fx/fireworks.js";

export function createInteract({
  input, player, park, hud, getState, onBoard, onBoardCarousel, onCollect, audio, fireworks,
}) {
  const boarding = park?.boarding ?? { x: 0, z: 16.4 };
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

      // 登舱锚点二选一：地面登舱点；或站台停靠舱旁（脚高 > 1.4 ⇒ 在站台上，
      // 舱位吸附在轮面最低点 = 世界原点附近，锚点取停靠舱侧后 1.6m）
      const onPlat = p.y > 1.4;
      const bx = onPlat ? 0 : boarding.x;
      const bz = onPlat ? 1.6 : boarding.z;
      if (dist2(p.x, p.z, bx, bz) < 2.6) {
        active = { run: onBoard };
        label = "乘坐摩天轮";
      } else if (
        p.y > 0.4 && p.y < 1.2 &&
        dist2(p.x, p.z, carouselCenter.x, carouselCenter.z) < 7.6
      ) {
        // 显灵木马盘面: 就近上马
        active = { run: onBoardCarousel };
        label = "骑上显灵木马";
      } else {
        for (const poi of pois) {
          if (collected.has(poi.label)) continue;
          if (dist2(p.x, p.z, poi.x, poi.z) < 2.2) {
            active = { run: () => collect(poi) };
            label = `收集南瓜灯（${collected.size + 1}/${pois.length}）`;
            break;
          }
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
      else hud.hidePrompt();
    },
  };
}
