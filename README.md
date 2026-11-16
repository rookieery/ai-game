# 幽夜游乐场 · Hollow Night Carnival

万圣节惊魂夜主题的第一人称 3D 网页游乐场（Three.js）。夜色 + 极光 + 南瓜灯 + 灯串的园子里漫步，登上「幽眠摩天轮」在高空俯瞰全园，顺手收集 5 盏南瓜灯。

![类型](https://img.shields.io/badge/%E4%BA%92%E5%8A%A8-%E7%AC%AC%E4%B8%80%E4%BA%BA%E7%A7%B0-orange) ![栈](https://img.shields.io/badge/Three.js-Vite-blue)

## 运行

```bash
npm install
npm run dev          # http://127.0.0.1:8765
```

首次克隆后先同步资产（Blender 产物不入库副本）：`npm run assets:sync`

## 玩法（桌面浏览器 + 键鼠）

| 按键 | 作用 |
|---|---|
| `W A S D` | 移动 |
| `Shift` | 疾走 |
| 鼠标 | 环视（点击画面锁定指针，`Esc` 释放） |
| `E` | 万能交互：登舱/下乘/收集南瓜灯 |
| 右下角月相 | 声音开关（满月有声 / 新月静音） |

流程：点五芒星入园 → 沿主路走到摩天轮站台 → `E` 乘坐（舱内可走动 `WASD`、`C` 坐下起身、360° 环视，75s/圈，随时 `E` 下乘）→ 绕园收集 5 盏南瓜灯点亮星图。

## 项目结构

```
├─ model/                    # Blender 程序化资产源（source of truth）
│  ├─ ferris_wheel/          # 摩天轮 v2（参数化脚本 + glb + 预览）
│  └─ park_env/              # 园区环境（脚本 + glb + colliders.json + 预览）
├─ public/assets/models/     # 同步产物（npm run assets:sync 生成，不入库）
├─ src/
│  ├─ core/                  # 场景/世界氛围(极光/星空/雾)/输入/程序音频
│  ├─ player/                # 第一人称控制器（碰撞读 colliders.json）
│  ├─ park/                  # glb 加载
│  ├─ rides/                 # 摩天轮逻辑（程序化旋转+舱体水平+乘坐状态机）
│  ├─ interact.js            # 交互系统（登舱/打卡）
│  ├─ fx/postfx.js           # UnrealBloom
│  └─ ui/                    # 「降神之夜」HUD（设计系统见 DESIGN.md）
├─ scripts/                  # 资产同步 + 无头浏览器截图验证
├─ PRODUCT.md / DESIGN.md    # 产品事实 / 设计系统（impeccable 工作流产物）
└─ .impeccable/              # 方向契约等设计工件（config.local.json 除外）
```

## 资产管线（全程序化，零外部素材）

```bash
"E:\blender\blender.exe" --background --python model/ferris_wheel/ferris_wheel.py
"E:\blender\blender.exe" --background --python model/park_env/park_env.py
npm run assets:sync       # 拷贝 glb + colliders.json 到 public/
```

所有参数在各脚本顶部 `P` 字典（轮径/舱数/转速/色板…），改完重跑即可。**注意**：glb 里空节点本地轴不可靠，旋转轴由几何检测（见 `src/rides/ferris.js`）。

## 性能预算（实测）

draw calls ~90/帧（预算 <300）、渲染三角面 ~16 万/帧、桌面 1080p 远超 60fps。资产按材质分组合并（静组/轮体/每舱）。

## 设计与验证

- UI 设计系统：「降神之夜 The Séance」（DESIGN.md），impeccable 工作流产出并通过 finish review
- 画面验证：`node scripts/screenshot.mjs shots/<名> game|states|spin`
