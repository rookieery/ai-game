// 雾潭特效：蓬松雾团（实例化 billboard）+ 贴地雾层（fbm 圆盘）+ 灯光暖晕染色
// 替代旧 world.js 的 9 片竖直雾板：团状、贴地、随风漂移、内部翻滚、越界回绕
import * as THREE from "three";

// ---------- 程序化雾团贴图（零外部素材） ----------
// 512x256，左右两朵不同形态的棉絮（随机小圆斑堆叠 + 径向衰减遮罩），实例按种子取半边
function makePuffAtlas() {
  const W = 512, H = 256;
  const c = document.createElement("canvas");
  c.width = W; c.height = H;
  const g = c.getContext("2d");
  for (let tile = 0; tile < 2; tile++) {
    const cx = W * 0.25 + tile * W * 0.5;
    const blobs = tile === 0 ? 46 : 30;
    for (let i = 0; i < blobs; i++) {
      const ang = Math.random() * Math.PI * 2;
      const rr = Math.pow(Math.random(), 0.72) * 72; // 中心密、外围疏
      const x = cx + Math.cos(ang) * rr;
      const y = H / 2 + Math.sin(ang) * rr * 0.78;   // 略压扁
      const br = 16 + Math.random() * 38;
      const a = 0.10 + Math.random() * 0.15;
      const grad = g.createRadialGradient(x, y, 1, x, y, br);
      grad.addColorStop(0, `rgba(255,255,255,${a.toFixed(3)})`);
      grad.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = grad;
      g.beginPath();
      g.arc(x, y, br, 0, Math.PI * 2);
      g.fill();
    }
    // 径向衰减遮罩：保证 quad 方形轮廓完全不可见
    g.globalCompositeOperation = "destination-in";
    const mask = g.createRadialGradient(cx, H / 2, 24, cx, H / 2, 116);
    mask.addColorStop(0, "rgba(0,0,0,1)");
    mask.addColorStop(0.55, "rgba(0,0,0,0.66)");
    mask.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = mask;
    g.fillRect(cx - 128, 0, 256, H);
    g.globalCompositeOperation = "source-over";
  }
  return new THREE.CanvasTexture(c);
}

// ---------- 共享 GLSL：灯光暖晕 + 场景夜雾一致混合 ----------
const N_TINT = 9;   // 灯染槽数（= 下方 TINT_LIGHTS 的条数，GLSL 数组按它开）；增删灯染源时同步改这里

const LIGHT_TINT_GLSL = /* glsl */ `
  uniform vec3 uLightPos[${N_TINT}];
  uniform vec3 uLightCol[${N_TINT}];
  uniform float uLightR[${N_TINT}];

  vec3 lightTint(vec3 wp) {
    vec3 acc = vec3(0.0);
    for (int i = 0; i < ${N_TINT}; i++) {
      float d = distance(wp, uLightPos[i]);
      acc += uLightCol[i] * smoothstep(uLightR[i], uLightR[i] * 0.12, d);
    }
    return clamp(acc, 0.0, 1.0);
  }
`;

const FOG_MIX_GLSL = /* glsl */ `
  uniform vec3 uFogColor;
  uniform float uFogDensity;

  // 与 scene.fog (FogExp2) 同公式，远处雾体没入夜雾
  vec3 fogMix(vec3 col, float depth) {
    float f = 1.0 - exp(-uFogDensity * uFogDensity * depth * depth);
    return mix(col, uFogColor, clamp(f, 0.0, 1.0));
  }
`;

const NOISE_GLSL = /* glsl */ `
  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x),
               mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
  }
  float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 3; i++) { v += a * vnoise(p); p *= 2.1; a *= 0.5; }
    return v;
  }
`;

// ---------- 雾团 billboard 着色器 ----------
const PUFF_VERT = /* glsl */ `
  uniform float uTime;
  uniform vec2 uWind;
  uniform float uWrap;
  attribute vec3 aOffset;  // 潭心（世界系）
  attribute vec4 aData;    // x,z: 潭内散布 | y: 种子 | w: 个体透明度
  attribute vec2 aScale;   // 宽, 高
  varying vec2 vUv;
  varying float vTile;
  varying float vAlpha;
  varying float vDepth;
  varying vec3 vWorld;

  void main() {
    float t = uTime;
    float seed = aData.y;
    // 风向缓转，雾团有速度差 + 慢摆
    float veer = t * 0.02;
    vec2 dir = vec2(uWind.x * cos(veer) - uWind.y * sin(veer),
                    uWind.x * sin(veer) + uWind.y * cos(veer));
    float sp = 0.55 + fract(seed * 5.7) * 0.9;
    vec2 drift = dir * sp * t * 1.1;
    drift += vec2(sin(t * 0.12 + seed * 17.0), cos(t * 0.1 + seed * 23.0)) * 1.1;
    // 潭内回绕：雾团川流不息而潭形不散
    vec2 j = aData.xy + drift;
    j = mod(j + uWrap, uWrap * 2.0) - uWrap;
    vec3 wp = aOffset + vec3(j.x, sin(t * 0.2 + seed * 30.0) * 0.15, j.y);
    vWorld = wp;
    // 相机对齐 billboard + 慢自转（翻滚感）
    vec4 vp = viewMatrix * vec4(wp, 1.0);
    float rot = (fract(seed * 9.3) - 0.5) * 1.2 + t * (fract(seed * 3.7) - 0.5) * 0.10;
    float ca = cos(rot), sa = sin(rot);
    vp.xy += mat2(ca, -sa, sa, ca) * position.xy * aScale;
    vUv = uv;
    vTile = step(0.5, fract(seed * 13.7)) * 0.5;
    vDepth = -vp.z;
    // 透明度呼吸 + 近相机淡出（穿雾不糊脸）
    vAlpha = aData.w
      * (0.72 + 0.28 * sin(t * (0.22 + fract(seed * 3.1) * 0.18) + seed * 40.0))
      * smoothstep(2.0, 5.5, vDepth);
    gl_Position = projectionMatrix * vp;
  }
`;

const PUFF_FRAG = /* glsl */ `
  uniform sampler2D uMap;
  uniform vec3 uCool;
  uniform vec3 uWarm;
  uniform float uGlobalAlpha;
  varying vec2 vUv;
  varying float vTile;
  varying float vAlpha;
  varying float vDepth;
  varying vec3 vWorld;
  ${LIGHT_TINT_GLSL}
  ${FOG_MIX_GLSL}

  void main() {
    float m = texture2D(uMap, vec2(vUv.x * 0.5 + vTile, vUv.y)).a;
    if (m < 0.004) discard;
    vec3 col = mix(uCool, uWarm, lightTint(vWorld));
    col = fogMix(col, vDepth);
    gl_FragColor = vec4(col, m * vAlpha * uGlobalAlpha);
  }
`;

// ---------- 贴地雾层着色器（高空俯瞰的连绵雾潭） ----------
const GROUND_VERT = /* glsl */ `
  varying vec2 vUv;
  varying vec3 vWorld;
  void main() {
    vUv = uv;
    vec4 wp = modelMatrix * vec4(position, 1.0);
    vWorld = wp.xyz;
    gl_Position = projectionMatrix * viewMatrix * wp;
  }
`;

const GROUND_FRAG = /* glsl */ `
  uniform float uTime;
  uniform vec2 uWind;
  uniform vec2 uSeed;
  uniform float uFlowSign;
  uniform vec3 uCool;
  uniform vec3 uWarm;
  uniform float uGlobalAlpha;
  varying vec2 vUv;
  varying vec3 vWorld;
  ${NOISE_GLSL}
  ${LIGHT_TINT_GLSL}
  ${FOG_MIX_GLSL}

  void main() {
    // domain-warp fbm：同风向缓慢流动的雾形
    vec2 flow = uWind * uTime * 0.0085 * uFlowSign;
    vec2 p = vWorld.xz * 0.042 + uSeed;
    float q = fbm(p * 0.55 + flow * 1.7);
    float f = fbm(p + q * 1.35 - flow);
    float bank = smoothstep(0.40, 0.70, f);
    // 圆盘径向淡出 + 掠射角淡出（贴地视点不穿帮）+ 近距淡出（近景留给雾团，防糊脸色罩）
    float edge = 1.0 - smoothstep(0.55, 0.96, length(vUv - 0.5) * 2.0);
    vec3 toCam = cameraPosition - vWorld;
    float dist = length(toCam);
    // 平视时雾层隐退（贴地视感全权交给雾团），高空/中高俯瞰才显形
    float graze = smoothstep(0.10, 0.30, normalize(toCam).y);
    float near = smoothstep(3.0, 11.0, dist);
    float a = bank * edge * graze * near * uGlobalAlpha * 0.55;
    if (a < 0.004) discard;
    vec3 col = mix(uCool, uWarm, lightTint(vWorld));
    col = fogMix(col, distance(vWorld, cameraPosition));
    gl_FragColor = vec4(col, a);
  }
`;

// ---------- 雾潭分布（v3 r150 扩园; x, z, 潭半径, 团数） ----------
const CLUSTERS = [
  [33.5, 41, 5, 4],     // 墓园入口前庭 (旧址; 2026-11-26 墓园南迁后只留一小片)
  [37, 58, 12, 9],      // 墓园新址 (椭圆 36x24 心 (37,58); 灯染跟随两盏守墓灯)
  [-29.5, 37, 8, 8],    // 摊位后排
  [12.5, 58, 9, 7],     // 入园径东侧
  [-11, 48, 8, 7],      // 入园径西侧（错位不成镜像）
  [30, -30, 10, 9],     // 东南空地树影间
  [44, -11.5, 8, 7],    // 旋转木马旁
  [15, -69, 9, 7],      // 过山车预留区入口
  [-70, 44, 9, 7],      // 幽灵港湾口
  [16, 92, 10, 7],      // 南外环灯下
];

// 灯染源：live 为数字 = 跟随 world.plazaLights 对应下标的实时强度；live 为字符串 = 跟随 colliders.json lights 里
// tag 同名的清单灯（位置取灯本体）；live = -1 为静态南瓜点（随 parkLampLight 总增益）
const TINT_LIGHTS = [
  { pos: [12, 1.2, 12], color: "#ff9a5c", r: 14, live: 0, base: 90, gain: 0.9 },   // 广场东 ↔ plaza1
  { pos: [-12, 1.2, -14], color: "#ff9a5c", r: 14, live: 1, base: 70, gain: 0.5 }, // 广场西 ↔ plaza2
  { pos: [0, 1.2, 146], color: "#ffc46b", r: 20, live: 2, base: 55, gain: 0.55 },  // 大门(v3 r146) ↔ gate
  // 墓园 (2026-11-26): 跟随两盏守墓灯。旧写法是在 (33.5,1.2,40.5) 摆一盏并不存在的「南瓜簇」静态灯染 —— 雾是暖的、地是黑的
  { pos: [0, 0, 0], color: "#ffd9a8", r: 8, live: "PE_GraveLantern", gain: 0.45 },  // 守墓灯 北 (34, 36.4)
  { pos: [0, 0, 0], color: "#ffd9a8", r: 8, live: "PE_GraveLanternS", gain: 0.45 }, // 守墓灯 南 (34, 48)
  { pos: [-25.5, 1.2, 30], color: "#ffa53b", r: 12, live: -1, gain: 0.8 },         // 摊位灯
  { pos: [-70, 1.2, 45], color: "#7fd8c8", r: 14, live: 3, base: 30, gain: 0.8 },  // 幽灵港 ↔ bay
  { pos: [15, 1.2, -100], color: "#ff9a5c", r: 16, live: 4, base: 42, gain: 0.8 }, // 北过山车 ↔ north
  { pos: [95, 1.2, 60], color: "#9b5bff", r: 14, live: 5, base: 26, gain: 0.8 },   // 东南秘境 ↔ east
];
if (TINT_LIGHTS.length > N_TINT) {
  console.warn(`[mist] 灯染源 ${TINT_LIGHTS.length} 条, 超出槽位 ${N_TINT} (改 N_TINT), 多出的未启用`);
  TINT_LIGHTS.length = N_TINT;
}
while (TINT_LIGHTS.length < N_TINT) TINT_LIGHTS.push({ pos: [0, -50, 0], color: "#000000", r: 0.01, live: -1, gain: 0 });

const BASE = { mist: 0.46 }; // mistDensity 100% 基准（旧 0.10 竖板方案的替代标定）

export function createMist(scene, world) {
  const atlas = makePuffAtlas();
  const cool = new THREE.Color("#5e6c96");
  const warm = new THREE.Color("#ffb066");

  // 共享 uniform（雾团与地面层同源，改一处全生效）
  const uni = {
    uTime: { value: 0 },
    uWind: { value: new THREE.Vector2(0.85, 0.52).normalize() },
    uWrap: { value: 12.5 },
    uMap: { value: atlas },
    uCool: { value: cool },
    uWarm: { value: warm },
    uGlobalAlpha: { value: BASE.mist },
    uFogColor: { value: new THREE.Color("#0a0c1e") },
    uFogDensity: { value: 0.0085 },
    uLightPos: { value: TINT_LIGHTS.map((l) => new THREE.Vector3(...l.pos)) },
    uLightCol: { value: TINT_LIGHTS.map((l) => new THREE.Color(l.color)) },
    uLightR: { value: TINT_LIGHTS.map((l) => l.r) },
  };

  // ----- 雾团 InstancedMesh：42 团 1 次 draw call -----
  let n = 0;
  for (const c of CLUSTERS) n += c[3];
  const offsets = new Float32Array(n * 3);
  const data = new Float32Array(n * 4);
  const scales = new Float32Array(n * 2);
  let k = 0;
  for (const [cx, cz, cr, count] of CLUSTERS) {
    for (let i = 0; i < count; i++) {
      const ang = Math.random() * Math.PI * 2;
      // 散布铺满回绕半径：初始分布 = 稳态分布，长跑不稀疏
      const rr = Math.sqrt(Math.random()) * 11.5;
      offsets[k * 3] = cx;
      offsets[k * 3 + 1] = 0.9 + Math.random() * 0.9; // 团心贴地
      offsets[k * 3 + 2] = cz;
      data[k * 4] = Math.cos(ang) * rr;
      data[k * 4 + 1] = Math.sin(ang) * rr;
      data[k * 4 + 2] = Math.random() * 100;          // 种子
      data[k * 4 + 3] = 0.66 + Math.random() * 0.34;  // 个体透明度
      const w = 8 + Math.pow(Math.random(), 1.4) * 10;
      scales[k * 2] = w;
      scales[k * 2 + 1] = w * (0.42 + Math.random() * 0.16); // 扁椭圆团
      k++;
    }
  }
  const base = new THREE.PlaneGeometry(1, 1);
  const geo = new THREE.InstancedBufferGeometry();
  geo.index = base.index;
  geo.setAttribute("position", base.attributes.position);
  geo.setAttribute("uv", base.attributes.uv);
  geo.instanceCount = n;
  geo.setAttribute("aOffset", new THREE.InstancedBufferAttribute(offsets, 3));
  geo.setAttribute("aData", new THREE.InstancedBufferAttribute(data, 4));
  geo.setAttribute("aScale", new THREE.InstancedBufferAttribute(scales, 2));
  const puffs = new THREE.Mesh(
    geo,
    new THREE.ShaderMaterial({
      uniforms: uni,
      vertexShader: PUFF_VERT,
      fragmentShader: PUFF_FRAG,
      transparent: true,
      depthWrite: false,
    })
  );
  puffs.frustumCulled = false;
  scene.add(puffs);

  // ----- 贴地雾层：两层错相圆盘（v3 半径随扩园 85 -> 150） -----
  const discGeo = new THREE.CircleGeometry(150, 64);
  const discs = [];
  for (const cfg of [
    { y: 0.45, seed: [0, 0], sign: 1 },
    { y: 0.95, seed: [7.3, -4.1], sign: -1 },
  ]) {
    const mat = new THREE.ShaderMaterial({
      uniforms: {
        ...uni,
        uSeed: { value: new THREE.Vector2(...cfg.seed) },
        uFlowSign: { value: cfg.sign },
      },
      vertexShader: GROUND_VERT,
      fragmentShader: GROUND_FRAG,
      transparent: true,
      depthWrite: false,
    });
    const d = new THREE.Mesh(discGeo, mat);
    d.rotation.x = -Math.PI / 2;
    d.position.y = cfg.y;
    d.frustumCulled = false;
    scene.add(d);
    discs.push(d);
  }

  // ----- 灯染联动：实体灯取实时强度，静态南瓜点随 parkLampLight 总增益 -----
  const plazaLights = world.plazaLights ?? [];
  const parkLights = world.parkLights ?? [];
  const tmpCol = new THREE.Color();
  let staticGain = 1; // parkLampLight 百分比
  function syncLights() {
    for (let i = 0; i < TINT_LIGHTS.length; i++) {
      const L = TINT_LIGHTS[i];
      if (typeof L.live === "string") {
        // 清单灯：位置与颜色取灯本体，强度按「当前 / 基准」折算（滑杆拉到 0 时灯染同步熄灭）；找不到该灯则不染
        const slot = parkLights.find((s) => s.tag === L.live);
        if (slot) {
          uni.uLightPos.value[i].copy(slot.light.position);
          tmpCol.copy(slot.light.color).multiplyScalar((slot.base > 0 ? slot.light.intensity / slot.base : 0) * L.gain * 1.4);
        } else {
          tmpCol.setRGB(0, 0, 0);
        }
      } else if (L.live >= 0 && plazaLights[L.live]) {
        const pl = plazaLights[L.live];
        tmpCol.copy(pl.color).multiplyScalar((pl.intensity / L.base) * L.gain * 1.4);
      } else {
        tmpCol.set(L.color).multiplyScalar(staticGain * L.gain * 1.4);
      }
      uni.uLightCol.value[i].copy(tmpCol);
    }
  }

  function update(dt, elapsed) {
    uni.uTime.value = elapsed;
    // 与场景夜雾逐帧同源（fogDensity/fogColor 设置改动即时生效）
    if (scene.fog) {
      uni.uFogColor.value.copy(scene.fog.color);
      uni.uFogDensity.value = scene.fog.density;
    }
    syncLights();
  }

  // 应用设置面板（百分比 -> 实际参数；接口与旧雾一致）
  function applySettings(s) {
    const pct = (key) => Math.min(200, Math.max(0, s[key] ?? 100)) / 100;
    uni.uGlobalAlpha.value = BASE.mist * pct("mistDensity");
    staticGain = pct("parkLampLight");
  }

  return { update, applySettings };
}
