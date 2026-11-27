// 地标礼花导演 (2026-11-25): 三处地标炸点表 + 到顶判定与定时触发
// 炸点 = 地标旁的一个水平位置 + 该处观景眼位（站在那里时眼睛的高度）;
// 实际炸点高度 = 眼位 + 设置「地标炸点高度」（相对值, 0 = 平视; 见 fireworks.applySettings）
//
// 什么时候放:
//   到顶准点放（本文件, 受设置「到顶礼花」控制, 与「自动烟花间隔」无关）
//     缠魂塔  玩家站上环廊 2.5s 后第一发（距这个炸点的上一发至少 6s）, 驻留期间每 18s 一发
//     摩天轮  乘坐中所乘舱每次转到最高点时炸 —— 离顶还差一个飞行时长时发射
//     过山车  乘坐中每圈头车到提升平顶中点时炸 —— 链速恒定, 提前一个飞行时长发射
//   常规秀穿插（fireworks.scheduleShow）: 每轮常规秀一半概率补一处, 终曲三处各一发
//
// 炸点放在哪（米, 水平距离; 实拍标定见 shots/fw_salute_plan）:
//   平视画面上缘只有 30° (FOV 60°), 炸点高出眼位一多就出画, 所以默认与眼位同高、水平拉开 11–18m;
//   摩天轮顶舱朝窗外看, 轮缘灯管挡住约 29°–45° 的仰角 → 离得最远 (18m), 仰视上限约 +10m
import * as THREE from "three";
import { EYE, CABIN, STATION } from "../player/controller.js";

const TOWER_FIRST = 2.5;     // 登顶后到第一发的秒数
const TOWER_MIN_GAP = 6;     // 每次登顶的第一发: 距这个炸点上一发（含常规秀穿插的）至少这么久 —— 不让人登顶后空等
const TOWER_INTERVAL = 18;   // 塔顶驻留期间两发的最小间隔（秒, 从该炸点上一发起算, 含常规秀穿插的那发）
const TOWER_R = 6.4;         // 算「在塔顶」的范围: 环廊外缘 5.6m + 余量
const TOWER_OUT = 16;        // 塔顶炸点离塔轴的水平距离（正东: 正对环廊东侧长椅, 也是发射架 L2 所在的方向）
const WHEEL_OUT = 18;        // 摩天轮炸点在顶舱正前方的水平距离
const COASTER_OUT = 16;      // 过山车炸点在平顶中点前方（沿前进方向）的水平距离 —— 须与 salute_launcher.py 一致（那边定炮口朝向）

const UP = new THREE.Vector3(0, 1, 0);

export function createFireworkDirector({ fireworks, player, ferris, coaster, park, getState }) {
  const anchors = [];
  const byId = {};
  const noop = { update() {}, anchors, state: {} };
  if (!fireworks || !player) return noop;
  const lidx = (id) => fireworks.getLaunchers().findIndex((l) => l.id === id);
  const add = (a) => {
    if (a.lid < 0) { console.warn(`[fw_director] 发射架 ${a.need} 缺失, ${a.label}礼花停用`); return; }
    byId[a.id] = a;
    anchors.push(a);
  };

  // 缠魂塔: 塔轴 / 环廊地面高取自碰撞表 (colliders_tower.json); 升降梯到顶时轿厢地面同高, 人还在轿厢里也算在顶
  const place = park?.tower?.place;
  const lift = park?.lift;
  if (place && Number.isFinite(place.x) && Number.isFinite(place.z)) {
    // 高度兜底值与 rides/tower.js 一致 (碰撞表缺字段时塔顶礼花仍放得出, 不至于算出 NaN)
    const floor = (Number.isFinite(lift?.zTop) ? lift.zTop : 39.92) + (Number.isFinite(lift?.floorThk) ? lift.floorThk : 0.08);
    add({
      id: "tower", label: "缠魂塔顶", need: "L2", lid: lidx("L2"),
      x: place.x + TOWER_OUT, z: place.z, eye: floor + EYE,
      cx: place.x, cz: place.z, floor,
    });
  }

  // 摩天轮: 轮心 / 半径取自舱根世界坐标。「正前方」= 轮轴方向里朝登舱区的那一侧（长椅面朝这一侧）
  const hub = new THREE.Vector3();
  const n = new THREE.Vector3();
  const e2 = new THREE.Vector3();
  const rel = new THREE.Vector3();
  if (ferris?.wheelRoot && ferris.cabinRoots?.length && ferris.spinAxis) {
    ferris.wheelRoot.getWorldPosition(hub);
    n.copy(ferris.spinAxis).normalize();
    rel.copy(ferris.cabinRoots[0].getWorldPosition(new THREE.Vector3())).sub(hub);
    const radius = rel.addScaledVector(n, -rel.dot(n)).length();
    // 判定用的定点取入口门楼 (app (0, 17.4))。以前取 colliders.json 的登舱点 (0, 16.4) —— v3 第 2 批 (2026-11-27)
    // 地面登舱点取消, 不再依赖那个字段; 两个定点都在轮心正下方, 判定结果不变
    const side = (STATION.PORTAL.z - hub.z) * n.z >= 0 ? 1 : -1;
    if (Number.isFinite(radius) && radius > 0) {
      add({
        id: "wheel", label: "摩天轮顶", need: "L1", lid: lidx("L1"),
        x: hub.x + n.x * side * WHEEL_OUT, z: hub.z + n.z * side * WHEEL_OUT,
        eye: hub.y + radius + CABIN.FLOOR_Y + CABIN.EYE_STAND,
      });
    }
  }

  // 过山车: 平顶中点 / 前进方向 / 眼高由 coaster.crest 给出（加载时从中心线算好）
  const cr = coaster?.crest;
  if (cr && [cr.s, cr.x, cr.y, cr.z, cr.tx, cr.tz, cr.v].every(Number.isFinite)) {
    add({
      id: "coaster", label: "过山车顶", need: "L7", lid: lidx("L7"),
      x: cr.x + cr.tx * COASTER_OUT, z: cr.z + cr.tz * COASTER_OUT, eye: cr.y + cr.eye,
    });
  }
  fireworks.setAnchors(anchors);

  // 取证可读: wheelT = 所乘舱离「到顶」还有多久; coasterS = 头车弧长; onTop = 是否在塔顶
  const st = { wheelT: null, coasterS: null, onTop: false, topSince: -1 };
  let towerFired = false; // 本次登顶期间已经放过（之后按 18s 间隔, 而不是第一发的 6s）
  let wheelArmed = false;   // 摩天轮: 离顶还远时上膛, 到点放一发后卸膛（舱位转过顶点后 tTop 跳回大值再重新上膛）
  let prevS = -1;           // 过山车: 上一帧头车弧长（-1 = 未在运行）

  function update(dt, elapsed) {
    if (!anchors.length) return;
    const state = getState();

    // 缠魂塔
    st.onTop = false;
    if (byId.tower) {
      const a = byId.tower;
      const p = player.pos;
      const onTop = state === "walk" && p.y >= a.floor - 0.2 && Math.hypot(p.x - a.cx, p.z - a.cz) <= TOWER_R;
      if (onTop) {
        if (st.topSince < 0) {
          st.topSince = elapsed;
          towerFired = false;
        }
        // 间隔从该炸点上一发起算（常规秀穿插的也算）: 第一发只要求 6s, 免得刚有一发之后登顶要空等到 18s
        const gap = elapsed - fireworks.lastSalute("tower");
        if (elapsed - st.topSince >= TOWER_FIRST && gap >= (towerFired ? TOWER_INTERVAL : TOWER_MIN_GAP)) {
          fireworks.salute("tower");
          towerFired = true;
        }
      } else {
        st.topSince = -1;
        towerFired = false;
      }
      st.onTop = onTop;
    }

    // 摩天轮: 舱位相位自「正上方」起、沿转向量, 转到顶还差 tTop = 相位差 / 角速度
    st.wheelT = null;
    if (byId.wheel && state === "riding" && ferris.state.riding) {
      const fr = ferris.getRideFrame();   // 所乘舱根的世界位姿（乘坐中才有）
      const f = fireworks.saluteFlight("wheel");
      if (fr && f) {
        rel.copy(fr.pos).sub(hub);
        rel.addScaledVector(n, -rel.dot(n));             // 投影到轮面（轮轴水平 → 世界 +Y 即「正上方」）
        e2.crossVectors(n, UP);                          // 顶点处的运动方向（绕轮轴正向转）
        const alpha = Math.atan2(rel.dot(e2), rel.y);    // ∈ (−π, π]
        const tTop = (alpha <= 0 ? -alpha : 2 * Math.PI - alpha) / ((2 * Math.PI) / ferris.state.ridePeriod);
        st.wheelT = tTop;
        if (tTop > f.T + 1) wheelArmed = true;
        else if (wheelArmed && tTop <= f.T) {
          wheelArmed = false;
          fireworks.salute("wheel");
        }
      }
    } else {
      wheelArmed = false;
    }

    // 过山车: 头车开到「平顶中点 − 链速 × 飞行时长」时发射, 飞满后头车恰好到平顶中点
    st.coasterS = null;
    if (byId.coaster && state === "riding" && coaster.state.session?.active && coaster.state.phase === "run") {
      const s = coaster.state.s;
      const f = fireworks.saluteFlight("coaster");
      st.coasterS = s;
      if (f) {
        const sFire = cr.s - cr.v * f.T;
        // prevS >= 0 且帧内行程 < 5m: 排除刚上车 / seek 跳变 / 过缝合点回绕
        if (prevS >= 0 && s - prevS < 5 && prevS < sFire && s >= sFire) fireworks.salute("coaster");
      }
      prevS = s;
    } else {
      prevS = -1;
    }
  }

  return { update, anchors, state: st };
}
