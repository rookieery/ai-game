// 设置注册表 + 持久化存储
// 约定：
//   · 灯光/强度类配置存「百分比整数」(100 = 当前基准值)，各系统用自己的基准换算
//   · 周期类存秒，数量类存颗，速度类存米/秒
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
    name: "显灵木马",
    items: [
      { key: "carouselSpinPeriod", label: "旋转转速", min: 10, max: 40, step: 1, def: 18, fmt: (v) => `${v} 秒/圈` },
    ],
  },
  {
    name: "过山车",
    items: [
      { key: "coasterFeel", label: "乘坐体感强度", min: 0, max: 100, step: 5, def: 60,
        fmt: (v) => (v === 0 ? "关闭" : `${v}%`) }, // POV 速度 FOV 拉伸 + 高频震动总开关; banking 侧倾随轨道天然存在
      { key: "coasterDecoLight", label: "装饰灯亮度", min: 0, max: 200, step: 5, def: 100, fmt: pct }, // 磷光描边/南瓜灯串/站牌/灯环/列车车灯
    ],
  },
  {
    name: "缠魂塔",
    items: [
      { key: "towerDecoLight", label: "装饰灯亮度", min: 0, max: 200, step: 5, def: 100, fmt: pct }, // 橙色缠带/扶手/关节灯/灯室/招牌/轿厢灯/呼梯灯
    ],
  },
  {
    name: "园区",
    items: [
      { key: "bgmOn", label: "背景音乐", type: "switch", def: true, fmt: (v) => (v ? "开" : "关") }, // 八音盒 BGM 总闸 (环境风/乘坐嗡鸣/风铃不受控)
      { key: "walkSpeed", label: "步行速度", min: 2, max: 16, step: 1, def: 4, fmt: (v) => `${v} 米/秒` }, // 疾走 = 步速 ×1.8
      { key: "parkLampLight", label: "园区照明亮度", min: 0, max: 200, step: 5, def: 100, fmt: pct },
      { key: "pumpkinGlow", label: "南瓜灯发光亮度", min: 0, max: 200, step: 5, def: 100, fmt: pct },
      { key: "moonLight", label: "月光与环境光", min: 0, max: 200, step: 5, def: 100, fmt: pct },
      { key: "fogDensity", label: "夜雾浓度", min: 0, max: 200, step: 5, def: 100, fmt: pct },
      { key: "starCount", label: "星空数量", min: 200, max: 3000, step: 100, def: 1400, fmt: (v) => `${v} 颗` },
      { key: "starBrightness", label: "星空亮度", min: 0, max: 200, step: 5, def: 100, fmt: pct },
      { key: "auroraLight", label: "极光强度", min: 0, max: 200, step: 5, def: 100, fmt: pct },
      { key: "mistDensity", label: "地面漂雾", min: 0, max: 200, step: 5, def: 100, fmt: pct },
      { key: "windStrength", label: "风摆强度", min: 0, max: 200, step: 5, def: 100, fmt: pct }, // 草/柳/松梢顶点着色器风摆
    ],
  },
  {
    name: "烟花",
    items: [
      { key: "fireworkPeriod", label: "自动烟花间隔", min: 10, max: 120, step: 5, def: 30, fmt: (v) => `${v} 秒/轮` },
      { key: "fireworkBright", label: "烟花亮度", min: 0, max: 200, step: 5, def: 100, fmt: pct }, // 粒子亮度 + 爆裂闪光联动
      { key: "fireworkHeight", label: "地面炸点高度", min: 25, max: 90, step: 5, def: 55, fmt: (v) => `${v} 米` }, // 地面各站的炸点海拔; 壳体初速按 v0y=√(2gh) 反解
      // 地标礼花: 缠魂塔环廊 / 摩天轮顶舱 / 过山车提升顶 旁的三处炸点 (fx/fw_director.js)
      { key: "fireworkSalute", label: "到顶礼花", type: "switch", def: true, fmt: (v) => (v ? "开" : "关") }, // 乘坐/登顶时准点放 + 常规秀穿插; 关 = 三处炸点全停
      { key: "fireworkSaluteHeight", label: "地标炸点高度", min: -20, max: 40, step: 5, def: 0,
        fmt: (v) => (v === 0 ? "眼位同高" : `${v > 0 ? "+" : ""}${v} 米`) }, // 相对各处观景眼位: 正 = 仰视, 负 = 俯视
      // 音效 (音色与空间播放见 core/fw_sound.js; 这里的取值口径须与 audio.js setFireworks 一致)
      { key: "fireworkVolume", label: "烟花音量", min: 0, max: 200, step: 5, def: 100, fmt: pct },
      { key: "fireworkSoundDelay", label: "真实声延迟", type: "switch", def: true, fmt: (v) => (v ? "开" : "关") }, // 声音按 343m/s 滞后闪光; 关 = 声画同时到
      { key: "fireworkAscentVolume", label: "升空哨音响量", min: 50, max: 200, step: 5, def: 100, fmt: pct }, // 100% = 基准响度
      { key: "fireworkCrisp", label: "裂响亮度", min: 50, max: 200, step: 5, def: 100, fmt: pct }, // 100% = 标准; 每 +50% 把 2.6kHz 以上高架 +4dB
      { key: "fireworkCrackle", label: "碎裂噼啪", type: "switch", def: true, fmt: (v) => (v ? "开" : "关") }, // 爆裂后 0.03-0.2s 的一小串高频碎裂
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
          if (it.type === "switch") {
            if (typeof v === "boolean") values[it.key] = v;
          } else if (typeof v === "number" && Number.isFinite(v)) {
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
