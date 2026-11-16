// 设置注册表 + 持久化存储
// 约定：
//   · 灯光/强度类配置存「百分比整数」(100 = 当前基准值)，各系统用自己的基准换算
//   · 周期类存秒，数量类存颗
//   · 几何类参数（舱数量/南瓜灯数量）烘焙在 glb 中，运行时不可调，故不注册

export const SETTINGS_GROUPS = [
  {
    name: "摩天轮",
    items: [
      { key: "ferrisIdlePeriod", label: "待机转速", min: 12, max: 60, step: 1, def: 24, fmt: (v) => `${v} 秒/圈` },
      { key: "ferrisRidePeriod", label: "乘坐转速", min: 40, max: 120, step: 1, def: 75, fmt: (v) => `${v} 秒/圈` },
      { key: "cabinLight", label: "舱内灯光亮度", min: 0, max: 200, step: 5, def: 40, fmt: pct }, // 补光点光 + 舱内自发光面板联动
      { key: "decoLight", label: "装饰灯亮度", min: 0, max: 200, step: 5, def: 100, fmt: pct }, // 轮缘/彩点/轮毂/招牌/站台灯环
    ],
  },
  {
    name: "园区",
    items: [
      { key: "parkLampLight", label: "园区照明亮度", min: 0, max: 200, step: 5, def: 100, fmt: pct },
      { key: "pumpkinGlow", label: "南瓜灯发光亮度", min: 0, max: 200, step: 5, def: 100, fmt: pct },
      { key: "moonLight", label: "月光与环境光", min: 0, max: 200, step: 5, def: 100, fmt: pct },
      { key: "fogDensity", label: "夜雾浓度", min: 0, max: 200, step: 5, def: 100, fmt: pct },
      { key: "starCount", label: "星空数量", min: 200, max: 3000, step: 100, def: 1400, fmt: (v) => `${v} 颗` },
      { key: "starBrightness", label: "星空亮度", min: 0, max: 200, step: 5, def: 100, fmt: pct },
      { key: "auroraLight", label: "极光强度", min: 0, max: 200, step: 5, def: 100, fmt: pct },
      { key: "mistDensity", label: "地面漂雾", min: 0, max: 200, step: 5, def: 100, fmt: pct },
    ],
  },
  {
    name: "画面",
    items: [
      { key: "bloomStrength", label: "辉光强度", min: 0, max: 200, step: 5, def: 100, fmt: pct }, // 基准 0.30
      { key: "bloomThreshold", label: "辉光阈值", min: 0, max: 100, step: 1, def: 85, fmt: pct }, // 绝对值 0-1 (100%=1.0)
      { key: "exposure", label: "整体曝光", min: 30, max: 200, step: 5, def: 100, fmt: pct }, // 基准 0.95 (ACES)
    ],
  },
];

function pct(v) {
  return `${v}%`;
}

const STORE_KEY = "hnc-settings-v1";

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

// 持久化去抖：拖滑杆时 input 事件密集，避免每帧写 localStorage
let saveTimer = null;
function persistSoon(values) {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(values));
    } catch { /* 隐私模式忽略 */ }
  }, 250);
}

export function createSettings() {
  const values = {};
  for (const g of SETTINGS_GROUPS) {
    for (const it of g.items) values[it.key] = it.def;
  }

  // 恢复上次配置（逐项校验类型与范围，防脏数据）
  try {
    const saved = JSON.parse(localStorage.getItem(STORE_KEY) ?? "null");
    if (saved && typeof saved === "object") {
      for (const g of SETTINGS_GROUPS) {
        for (const it of g.items) {
          const v = saved[it.key];
          if (typeof v === "number" && Number.isFinite(v)) {
            values[it.key] = clamp(v, it.min, it.max);
          }
        }
      }
    }
  } catch { /* 损坏的存档按默认处理 */ }

  const listeners = new Set();

  return {
    values,
    get: (k) => values[k],
    set(k, v) {
      values[k] = v;
      persistSoon(values);
      for (const fn of listeners) fn(k, v);
    },
    reset() {
      for (const g of SETTINGS_GROUPS) {
        for (const it of g.items) values[it.key] = it.def;
      }
      persistSoon(values);
      for (const fn of listeners) fn("*", 0);
    },
    onChange(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };
}
