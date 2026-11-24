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
| `空格` | 跳跃（长椅/干草堆/木桶/旋转木马平台可跳上；登舱台阶可直接走上去） |
| 鼠标 | 环视（点击画面锁定指针，`Esc` 释放） |
| `E` | 万能交互：登舱/下乘/收集南瓜灯/乘缠魂塔升降梯 |
| `F` | 靠近烟花发射器时单发点射 |
| `O` | 园区设置（灯光/转速/步行速度/烟花/画面等，自动保存） |
| 右下角月相 | 声音开关（满月有声 / 新月静音） |

烟花音效全程序合成：爆裂（裂响→碎裂→轰鸣→滚动尾音）、升空哨音（一路滑到炸点）、按 343 m/s 滞后闪光的声延迟与左右声像；音量、声延迟、升空哨音响量、裂响亮度、碎裂都在园区设置的「烟花」组里调。

流程：点五芒星入园 → 沿主路走到摩天轮站台 → `E` 乘坐（舱内可走动 `WASD`、`C` 坐下起身、360° 环视，75s/圈，随时 `E` 下乘）→ 绕园收集 5 盏南瓜灯点亮星图。

- 登舱台阶可逐级走上 1.55m 站台环视全园；有人站台时摩天轮会缓停并把舱位停靠到最低点，站台旁 `E` 一样可登舱
- 地面的长椅、干草堆、木桶、旋转木马平台都能 `空格` 跳上去站着看风景（舱内净高不足，禁跳）
- 缠魂塔（过山车地面灯环处，环廊 40m 全园制高点）：从南侧草坪进门厅，走近停靠点轿厢自动开来；走进轿厢按 `E` 升到环廊（约 12 秒），或者沿 242 级螺旋梯走上去。环廊上有一盏南瓜灯，塔顶俯瞰摩天轮与过山车

## 项目结构

```
├─ model/                    # Blender 程序化资产源（source of truth）
│  ├─ ferris_wheel/          # 摩天轮 v2（参数化脚本 + glb + 预览）
│  ├─ roller_coaster/        # 幽冥回环过山车（轨道 + 列车 + 站台动线；脚本 + glb + centerline + colliders_coaster.json + 预览）
│  ├─ lookout_tower/         # 缠魂塔 v3（螺旋梯 + 升降梯，环廊 40m；脚本 + glb + colliders_tower.json + 预览；已接入游戏）
│  └─ park_env/              # 园区环境（脚本 + glb + colliders.json + 预览）
├─ public/assets/models/     # 同步产物（npm run assets:sync 生成，不入库）
├─ src/
│  ├─ core/                  # 场景/世界氛围(极光/星空/雾)/输入/程序音频/烟花音色合成器(fw_sound.js)
│  ├─ player/                # 第一人称控制器（碰撞读 colliders*.json；含缠魂塔叠层地面语义）
│  ├─ park/                  # glb 加载
│  ├─ rides/                 # 设施逻辑：摩天轮 / 旋转木马 / 过山车 + 闸机 / 缠魂塔升降梯(tower.js)
│  ├─ interact.js            # 交互系统（登舱/打卡）
│  ├─ fx/postfx.js           # UnrealBloom
│  └─ ui/                    # 「降神之夜」HUD（设计系统见 DESIGN.md）
├─ prototype/fw_sound/       # 烟花音效调参试听页（/prototype/fw_sound/，含接入前旧版音效快照）
├─ scripts/                  # 资产同步 + 无头浏览器验证（截图 / 音频）
├─ PRODUCT.md / DESIGN.md    # 产品事实 / 设计系统（impeccable 工作流产物）
└─ .impeccable/              # 方向契约等设计工件（config.local.json 除外）
```

## 资产管线（全程序化，零外部素材）

```bash
"E:\blender\blender.exe" --background --python model/ferris_wheel/ferris_wheel.py
"E:\blender\blender.exe" --background --python model/park_env/park_env.py
"E:\blender\blender.exe" --background --python model/roller_coaster/roller_coaster.py     # 约 5 秒，顺带渲染预览
"E:\blender\blender.exe" --background --python model/lookout_tower/lookout_tower.py       # 约 8 秒
npm run assets:sync       # 拷贝 glb + colliders*.json 到 public/
```

所有参数在各脚本顶部 `P` 字典（轮径/舱数/转速/色板…），改完重跑即可。**注意**：glb 里空节点本地轴不可靠，旋转轴由几何检测（见 `src/rides/ferris.js`）。

## 性能预算（实测）

draw calls ~90/帧（预算 <300）、渲染三角面 ~16 万/帧、桌面 1080p 远超 60fps。资产按材质分组合并（静组/轮体/每舱）。

## 设计与验证

- UI 设计系统：「降神之夜 The Séance」（DESIGN.md），impeccable 工作流产出并通过 finish review
- 画面验证：`node scripts/screenshot.mjs shots/<名> game|states|spin`
- 烟花音效验证：`node scripts/probe_fw_audio.mjs`（离线渲染出 before/after WAV 与客观指标）、`node scripts/verify_fw_audio.mjs`（游戏内端到端：触发点传参 / 设置项 / 录音分析）；参数表在 `src/core/fw_sound.js` 顶部，调参用试听页 `npm run dev` → `/prototype/fw_sound/`
- 缠魂塔验证：`node scripts/verify_tower_colliders.mjs`（碰撞表离线校验 32 项）→ 起 dev server 后 `GAME_URL=http://127.0.0.1:8767 node scripts/verify_tower_game.mjs`（端到端断言：出生点真键步行进轿厢 / 乘梯上下 / 门洞防挟 / 真键走螺旋梯上下 / 塔顶打卡 / 自动呼梯 / 设置联动 / 摩天轮联锁回归，任一失败 exit 1）；机位截图 `node scripts/verify_tower_shots.mjs`
