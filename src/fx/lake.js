// 迷魂湖 v4：反射水面(三 Water) + 幻彩涟漪叠加层 + 灯笼海(实例化) + 灯下光柱 + 许愿脉冲
//  - 水面：park_env.glb 节点 PE_LakeWater 的椭圆几何替换为 Water 平面反射
//    (真实倒影：灯笼/极光天穹/烟花/栈桥全反射；雾潭/灵火在层 1 不进反射)
//  - 法线贴图：周期值噪声高度场程序生成 (零外部素材)
//  - 幻彩涟漪：噪声等值线细带 青->紫相移, 叠加在水面上方 4cm (加色)
//  - 灯笼海：PE_LakeLanternA/B/C 提取几何 -> 3 个 InstancedMesh (1 drawcall/档),
//    顶点注入浮沉摆动 (customProgramCacheKey 必配, 见 wind.js 踩坑)
//  - 灯下光柱：实例化扁光带, 顶点着色器从灯位向相机方向拉伸, fbm 闪烁碎光
//  - 许愿脉冲：栈桥尽头 E 触发扩散涟漪圈 (叠加层亮环 + 光柱随圈增亮)
import * as THREE from "three";
import { Water } from "three/addons/objects/Water.js";

// 湖体参数 (与 park_env.py LAKE_* / colliders.json lake 字段一致, app 坐标; +0.5 = 水盘外扩)
const LAKE = { cx: 105, cz: 66, rx: 44.5, rz: 42.5 };
const PIER_TIP = { x: 90.7, z: 57.4 };   // 许愿触发点 (栈桥尽头水面侧, 避开 poi 提示半径)
const LANTERN_N = 640;                   // 灯笼总数 (A/B/C = 45%/35%/20%; v4.1 湖扩容等比加密)
const REFLECT_RT = 1024;                 // 反射 RT 分辨率 (性能降级阶梯第一档: 调小)

// 西岸栈桥视角构图优先: 密度沿「湖心->栈桥」方向轴衰减 (东岸留稀), 中环留航道
const PIER_DIR = (() => {
  const x = (PIER_TIP.x - LAKE.cx) / LAKE.rx, z = (PIER_TIP.z - LAKE.cz) / LAKE.rz;
  const l = Math.hypot(x, z) || 1;
  return { x: x / l, z: z / l };
})();
const CHANNEL = { lo: 0.3, hi: 0.56, dim: 0.4 }; // 航道稀疏带 (下一版游船环线)

function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---- GLSL 公共段 (噪声 + 场景雾一致, 与 mist.js/world.js 同风格) ----
const GLSL_NOISE = /* glsl */ `
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

// ---- 程序生成可平铺水面法线贴图 (整数倍频保证周期无缝) ----
function makeWaterNormalTexture(size = 256) {
  const L = 48;
  const rnd = mulberry32(20261118);
  const lat = new Float32Array(L * L);
  for (let i = 0; i < lat.length; i++) lat[i] = rnd();
  const val = (u, v, f, ox, oy) => {
    const gx = (u * f + ox) * L, gy = (v * f + oy) * L;
    const x0 = Math.floor(gx) % L, y0 = Math.floor(gy) % L;
    const x1 = (x0 + 1) % L, y1 = (y0 + 1) % L;
    const fx = gx - Math.floor(gx), fy = gy - Math.floor(gy);
    const uu = fx * fx * (3 - 2 * fx), vv = fy * fy * (3 - 2 * fy);
    const a = lat[y0 * L + x0], b = lat[y0 * L + x1];
    const c = lat[y1 * L + x0], d = lat[y1 * L + x1];
    return a + (b - a) * uu + (c - a) * vv + (a - b - c + d) * uu * vv;
  };
  const hgt = new Float32Array(size * size);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const u = x / size, v = y / size;
      hgt[y * size + x] =
        0.58 * val(u, v, 3, 0, 0) +
        0.28 * val(u, v, 7, 0.17, 0.31) +
        0.14 * val(u, v, 17, 0.53, 0.61);
    }
  }
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const g2 = c.getContext("2d");
  const img = g2.createImageData(size, size);
  const str = 2.4;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const xm = (x - 1 + size) % size, xp = (x + 1) % size;
      const ym = (y - 1 + size) % size, yp = (y + 1) % size;
      const dx = (hgt[y * size + xp] - hgt[y * size + xm]) * str;
      const dy = (hgt[yp * size + x] - hgt[ym * size + x]) * str;
      const nz = 1 / Math.hypot(dx, dy, 1);
      const i = (y * size + x) * 4;
      img.data[i] = (-dx * nz * 0.5 + 0.5) * 255;
      img.data[i + 1] = (-dy * nz * 0.5 + 0.5) * 255;
      img.data[i + 2] = nz * 255;
      img.data[i + 3] = 255;
    }
  }
  g2.putImageData(img, 0, 0);
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.colorSpace = THREE.NoColorSpace;
  return tex;
}

// ---- 灯笼分布: 泊松.reject + 密度权重 (西岸密/东岸疏 + 中环航道留稀) ----
function planLanterns() {
  const rnd = mulberry32(20261118);
  const out = [];
  let tries = 0;
  while (out.length < LANTERN_N && tries < 14000) {
    tries += 1;
    const nx = rnd() * 2 - 1, nz = rnd() * 2 - 1;
    const n = Math.hypot(nx, nz);
    if (n > 0.9) continue;
    const t = nx * PIER_DIR.x + nz * PIER_DIR.z;           // -1 东远 .. +1 栈桥侧
    let w = 0.38 + 0.54 * (t * 0.5 + 0.5);
    if (n > CHANNEL.lo && n < CHANNEL.hi) w *= CHANNEL.dim; // 航道
    if (rnd() > w) continue;
    const x = LAKE.cx + nx * LAKE.rx;
    const z = LAKE.cz + nz * LAKE.rz;
    if (Math.hypot(x - PIER_TIP.x, z - PIER_TIP.z) < 3.2) continue; // 让开栈桥平台
    const roll = rnd();
    const variant = roll < 0.45 ? 0 : roll < 0.8 ? 1 : 2;
    const colorRoll = rnd();
    const color = colorRoll < 0.45 ? "#FFE9C4" : colorRoll < 0.8 ? "#FFA53B"
      : colorRoll < 0.92 ? "#FF9E9E" : "#C43B3B";
    out.push({
      x, z,
      variant,
      scale: 0.75 + rnd() * 0.5,
      yaw: rnd() * Math.PI,
      phase: rnd(),
      color: new THREE.Color(color),
      bright: 0.75 + rnd() * 0.4,
    });
  }
  return out;
}

const PROTO_NAMES = ["PE_LakeLanternA", "PE_LakeLanternB", "PE_LakeLanternC"];
const PROTO_R = [0.30, 0.24, 0.18]; // 与 park_env.py 原型半径一致 (吃水/浮高计算用)
// 不进湖面反射的大件 (远景植被/地斑: 映在深色湖面不可见, 剔除省 ~70% 反射三角面):
// 层 2 = 主相机可见 (camera.layers.enable(2)), 反射虚拟相机只看层 0 -> 自动剔除
const NO_REFLECT = new Set([
  "PE_PE_Twig", "PE_PE_Trunk", "PE_PE_PineFoliage", "PE_PE_WillowFiber",
  "PE_PE_GrassTuft", "PE_PE_GroundMoss", "PE_PE_LeafLitter",
  "PE_PE_PumpkinDeep", "PE_PE_PumpCavity", "PE_PE_StrawV", "PE_PE_Hay",
]);

export function createLake(scene, parkRoot, { audio }) {
  const uTime = { value: 0 };
  const uPulse = { value: new THREE.Vector4(PIER_TIP.x, PIER_TIP.z, -100, 0) };
  const uFogColor = { value: new THREE.Color("#0a0c1e") };
  const uFogDensity = { value: 0.0055 };
  let flowScale = 1;
  let glowScale = 1;

  // ---------- 水面: PE_LakeWater 椭圆 -> Water 平面反射 ----------
  // 远景植被等移到层 2 (主相机 enable(2), 反射相机只看层 0 -> 反射 pass 瘦身)
  parkRoot.traverse((o) => {
    if (NO_REFLECT.has(o.name)) o.layers.set(2);
  });

  const waterNode = parkRoot.getObjectByName("PE_LakeWater");
  if (!waterNode) {
    console.warn("[lake] PE_LakeWater 节点缺失, 湖面降级为静态材质");
    return { update() {}, applySettings() {}, pulse: () => false };
  }
  waterNode.parent.remove(waterNode); // 占位面移除
  // glTF 管线烘焙的椭圆几何躺在 XZ 平面 (y≈0.055, 法线 +Y) 且无 uv。
  // Water(Reflector) 约定局部 XY 平面 + 法线 +Z + mesh.rotation.x=-π/2:
  // 顶点 (x, y, z) -> (x, -z, y) 使世界位置不变, 并按包围盒补平面 uv (法线采样用)
  const lakeGeoXY = waterNode.geometry.clone();
  lakeGeoXY.computeBoundingBox();
  const bb = lakeGeoXY.boundingBox;
  const wpos = lakeGeoXY.attributes.position;
  const spanX = Math.max(1e-3, bb.max.x - bb.min.x);
  const spanZ = Math.max(1e-3, bb.max.z - bb.min.z);
  const uvArr = new Float32Array(wpos.count * 2);
  for (let i = 0; i < wpos.count; i++) {
    const x = wpos.getX(i), y = wpos.getY(i), z = wpos.getZ(i);
    wpos.setXYZ(i, x, -z, y);
    uvArr[i * 2] = (x - bb.min.x) / spanX;
    uvArr[i * 2 + 1] = (z - bb.min.z) / spanZ;
  }
  wpos.needsUpdate = true;
  lakeGeoXY.setAttribute("uv", new THREE.BufferAttribute(uvArr, 2));
  const water = new Water(lakeGeoXY, {
    textureWidth: REFLECT_RT,
    textureHeight: REFLECT_RT,
    waterColor: 0x0a0f24,
    sunColor: 0xb4c7ff,
    sunDirection: new THREE.Vector3(-0.459, 0.397, -0.794).normalize(), // 月盘方向
    distortionScale: 1.1,
    clipBias: 0.08,
    size: 4.0,
  });
  water.rotation.x = -Math.PI / 2; // Water 约定: 局部 XY + 法线 +Z -> 世界 XZ
  water.renderOrder = 1;
  scene.add(water);

  // ---------- 幻彩涟漪叠加层 (噪声等值线, 青->紫) ----------
  const overlayUni = {
    uTime, uPulse, uFogColor, uFogDensity,
    uSheen: { value: 0.14 },
  };
  const overlay = new THREE.Mesh(
    waterNode.geometry, // 原始 XZ 椭圆几何 (shader 只用世界坐标, 无需 uv)
    new THREE.ShaderMaterial({
      uniforms: overlayUni,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      vertexShader: /* glsl */ `
        varying vec3 vWp;
        void main() {
          vec4 wp = modelMatrix * vec4(position, 1.0);
          vWp = wp.xyz;
          gl_Position = projectionMatrix * viewMatrix * wp;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform float uTime; uniform float uSheen;
        uniform vec4 uPulse;
        uniform vec3 uFogColor; uniform float uFogDensity;
        varying vec3 vWp;
        ${GLSL_NOISE}
        void main() {
          vec2 q = vWp.xz;
          // 两条错相噪声等值线 = 参考图的幻彩细带
          float n1 = fbm(q * 0.23 + vec2(uTime * 0.055, uTime * 0.021));
          float n2 = fbm(q * 0.15 - vec2(uTime * 0.028, uTime * 0.047) + 4.7);
          float line = smoothstep(0.03, 0.0, abs(n1 - 0.52)) * 0.62
                     + smoothstep(0.04, 0.0, abs(n2 - 0.47)) * 0.42;
          float hue = fbm(q * 0.05 + vec2(uTime * 0.018, -uTime * 0.012));
          vec3 tint = mix(vec3(0.13, 0.80, 0.55), vec3(0.48, 0.32, 0.95), hue);
          float a = line * uSheen * (0.65 + 0.35 * fbm(q * 0.6 + uTime * 0.1));
          // 许愿脉冲: 白核亮环 + 暖晕扩散
          float pr = (uTime - uPulse.z) * 7.0;
          float pd = distance(q, uPulse.xz);
          float band = abs(pd - pr);
          float ring = smoothstep(2.2, 0.0, band) * uPulse.w;
          float core = smoothstep(0.6, 0.0, band) * uPulse.w;
          // 注意: Additive 混合输出 = rgb × alpha, col 不可再预乘 a (否则 a² 衰减到隐形)
          vec3 col = tint * 2.0 + vec3(1.0, 0.85, 0.55) * ring * 1.2 + vec3(1.0, 0.95, 0.8) * core * 2.0;
          float dist = distance(vWp, cameraPosition);
          float fogF = 1.0 - exp(-uFogDensity * uFogDensity * dist * dist);
          gl_FragColor = vec4(col, min(1.0, a * 2.0 + ring * 1.0 + core * 0.9) * (1.0 - fogF));
        }
      `,
    })
  );
  overlay.position.y = 0.04; // 叠加在烘焙水面 (y≈0.055) 上方 4cm, 避免共面 z-fight
  overlay.renderOrder = 2;
  scene.add(overlay);

  // ---------- 灯笼海: 提取原型 -> InstancedMesh x3 ----------
  const placed = planLanterns();
  const lanterns = [];   // { mesh, baseColors, brights }
  const bobMat = () => {
    const mat = new THREE.MeshBasicMaterial({ color: 0xffffff, fog: true });
    mat.onBeforeCompile = (shader) => {
      shader.uniforms.uTime = uTime;
      shader.vertexShader = shader.vertexShader
        .replace("#include <common>",
          "#include <common>\nuniform float uTime;\nattribute float aPhase;")
        .replace("#include <begin_vertex>", `
          #include <begin_vertex>
          transformed.y += sin(uTime * (0.55 + fract(aPhase * 0.173) * 0.4) + aPhase * 6.2832) * 0.05;
          transformed.x += sin(uTime * 0.37 + aPhase * 9.7) * 0.018;
          transformed.z += cos(uTime * 0.31 + aPhase * 7.1) * 0.018;
        `);
    };
    mat.customProgramCacheKey = () => "lakeBob"; // 同源注入共享一段编译产物 (刻意共用)
    return mat;
  };
  const m4 = new THREE.Matrix4();
  const q = new THREE.Quaternion();
  const e = new THREE.Euler();
  const vPos = new THREE.Vector3();
  const vScl = new THREE.Vector3();
  const streakData = { pos: [], col: [], phase: [] };
  for (let vi = 0; vi < 3; vi++) {
    const proto = parkRoot.getObjectByName(PROTO_NAMES[vi]);
    if (!proto) { console.warn(`[lake] ${PROTO_NAMES[vi]} 缺失`); continue; }
    proto.visible = false; // 原型藏地下, 提取几何后不再渲染
    const geo = proto.geometry.clone();
    // 原型按世界坐标烘焙在湖心 z=-8: 居中化, 实例矩阵即最终位姿
    geo.computeBoundingBox();
    const ctr = new THREE.Vector3();
    geo.boundingBox.getCenter(ctr);
    geo.translate(-ctr.x, -ctr.y, -ctr.z);
    const mine = placed.filter((p) => p.variant === vi);
    const n = mine.length;
    const phases = new Float32Array(n);
    const colors = new Float32Array(n * 3);
    const mesh = new THREE.InstancedMesh(geo, bobMat(), n);
    mesh.frustumCulled = false;
    mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(n * 3), 3);
    mine.forEach((p, i) => {
      phases[i] = p.phase;
      e.set(0, p.yaw, 0);
      q.setFromEuler(e);
      // 吃水 ~25%: 灯笼中心 y = 0.75·r·scale (读作完整球体坐水, 非半球)
      m4.compose(vPos.set(p.x, 0.75 * PROTO_R[vi] * p.scale - 0.02, p.z), q,
        vScl.set(p.scale, p.scale, p.scale));
      mesh.setMatrixAt(i, m4);
      const boost = p.bright * 2.2 * glowScale;
      colors[i * 3] = p.color.r * boost;
      colors[i * 3 + 1] = p.color.g * boost;
      colors[i * 3 + 2] = p.color.b * boost;
      streakData.pos.push(p.x, 0.1, p.z);
      streakData.col.push(p.color.r, p.color.g, p.color.b);
      streakData.phase.push(p.phase);
    });
    mesh.geometry.setAttribute("aPhase", new THREE.InstancedBufferAttribute(phases, 1));
    mesh.instanceColor.array.set(colors);
    mesh.instanceColor.needsUpdate = true;
    mesh.renderOrder = 2;
    scene.add(mesh);
    lanterns.push({ mesh, mine, boostBase: 2.2 });
  }

  // ---------- 灯下光柱: 实例化扁光带, 顶点着色器向相机拉伸 ----------
  const sN = streakData.pos.length / 3;
  const sGeo = new THREE.InstancedBufferGeometry();
  const quad = new THREE.PlaneGeometry(1, 1);
  sGeo.index = quad.index;
  sGeo.setAttribute("position", quad.attributes.position);
  sGeo.setAttribute("uv", quad.attributes.uv);
  sGeo.instanceCount = sN;
  sGeo.setAttribute("aLPos", new THREE.InstancedBufferAttribute(new Float32Array(streakData.pos), 3));
  sGeo.setAttribute("aLCol", new THREE.InstancedBufferAttribute(new Float32Array(streakData.col), 3));
  sGeo.setAttribute("aLPhase", new THREE.InstancedBufferAttribute(new Float32Array(streakData.phase), 1));
  const streakUni = {
    uTime, uPulse, uFogColor, uFogDensity,
    uGain: { value: 0.4 },
  };
  const streaks = new THREE.Mesh(
    sGeo,
    new THREE.ShaderMaterial({
      uniforms: streakUni,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
      vertexShader: /* glsl */ `
        uniform float uTime;
        attribute vec3 aLPos; attribute vec3 aLCol; attribute float aLPhase;
        varying vec2 vUv; varying vec3 vCol; varying float vPh; varying vec3 vWp;
        varying float vCd;
        void main() {
          vUv = uv; vCol = aLCol; vPh = aLPhase;
          vec2 toCam = cameraPosition.xz - aLPos.xz;
          float cd = length(toCam);
          vCd = cd;
          vec2 dir = cd > 1e-3 ? toCam / cd : vec2(1.0, 0.0);
          float len = clamp(cd * 0.30, 1.6, 6.5);
          float w = 0.26;
          vec2 xz = aLPos.xz + dir * (uv.x * len) + vec2(-dir.y, dir.x) * (uv.y - 0.5) * w;
          vec3 wp = vec3(xz.x, 0.085 + sin(uTime * 0.8 + aLPhase * 6.28) * 0.012, xz.y);
          vWp = wp;
          gl_Position = projectionMatrix * viewMatrix * vec4(wp, 1.0);
        }
      `,
      fragmentShader: /* glsl */ `
        uniform float uTime; uniform float uGain;
        uniform vec4 uPulse;
        uniform vec3 uFogColor; uniform float uFogDensity;
        varying vec2 vUv; varying vec3 vCol; varying float vPh; varying vec3 vWp;
        varying float vCd;
        ${GLSL_NOISE}
        void main() {
          float taper = pow(1.0 - vUv.x, 2.4);           // 灯端亮 -> 远端散 (收拢光柱)
          float edge = 1.0 - abs(vUv.y - 0.5) * 2.0;
          float shim = 0.55 + 0.45 * fbm(vec2(vUv.x * 6.0 - uTime * 0.9 + vPh * 7.0, vPh * 3.1));
          float near = smoothstep(1.6, 4.0, vCd);        // 贴脸灯的光柱淡出, 防巨团糊屏
          float a = taper * edge * edge * shim * uGain * near;
          // 许愿脉冲: 圈过灯位时整条光柱增亮
          float pd = distance(vWp.xz, uPulse.xz);
          float pr = (uTime - uPulse.z) * 7.0;
          a += smoothstep(2.2, 0.0, abs(pd - pr)) * 1.4 * uPulse.w * taper * near;
          float dist = distance(vWp, cameraPosition);
          float fogF = 1.0 - exp(-uFogDensity * uFogDensity * dist * dist);
          gl_FragColor = vec4(vCol * 1.3, a * (1.0 - fogF));
        }
      `,
    })
  );
  streaks.frustumCulled = false;
  streaks.renderOrder = 3;
  scene.add(streaks);

  // ---------- 设置 / 主循环 ----------
  function retint() {
    for (const l of lanterns) {
      const arr = l.mesh.instanceColor.array;
      l.mine.forEach((p, i) => {
        const b = p.bright * l.boostBase * glowScale;
        arr[i * 3] = p.color.r * b;
        arr[i * 3 + 1] = p.color.g * b;
        arr[i * 3 + 2] = p.color.b * b;
      });
      l.mesh.instanceColor.needsUpdate = true;
    }
  }

  function applySettings(s) {
    glowScale = Math.min(2, Math.max(0.2, (s.lakeGlow ?? 100) / 100));
    flowScale = Math.min(2.5, Math.max(0.2, (s.waterFlow ?? 100) / 100));
    streakUni.uGain.value = Math.min(0.4, 0.16 * glowScale);
    retint();
  }

  function pulse() {
    const now = uTime.value;
    if (now - uPulse.value.z < 2.5) return false;
    uPulse.value.set(PIER_TIP.x, PIER_TIP.z, now, 1);
    return true;
  }

  let audioTick = 0;
  function update(dt, elapsed, playerPos) {
    uTime.value = elapsed;
    if (uPulse.value.w > 0 && elapsed - uPulse.value.z > 2.8) uPulse.value.w = 0;
    water.material.uniforms.time.value += dt * flowScale;
    uFogDensity.value = (scene.fog?.density ?? 0.0055);
    if (uFogColor.value && scene.fog?.color) uFogColor.value.copy(scene.fog.color);
    // 水声随距湖衰减 (每 0.2s 结算一次)
    audioTick += dt;
    if (audioTick > 0.2 && playerPos && audio?.setLakeNear) {
      audioTick = 0;
      const enx = (playerPos.x - LAKE.cx) / LAKE.rx;
      const enz = (playerPos.z - LAKE.cz) / LAKE.rz;
      const outer = Math.hypot(enx, enz);          // 椭圆归一化半径
      const meters = Math.max(0, (outer - 1) * LAKE.rz); // 距岸近似米数
      const g = Math.min(1, Math.max(0, 1 - meters / 48));
      audio.setLakeNear(g);
    }
  }

  return { update, applySettings, pulse, water, overlay, streaks, lanternCount: placed.length };
}
