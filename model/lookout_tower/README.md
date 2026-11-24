# 缠魂塔 SOUL SPIRE

幽夜游乐场 · 眺望塔资产：铁艺桁架笼架 + 外露螺旋梯 + 升降梯，主平台 40m，全园制高点（过山车最高点 25.3m，摩天轮顶 36.25m）。
原点建模，游戏落位 app (17.5, 0, -30.5) = 过山车「地面灯环」圆心；它将取代 roller_coaster.py 里的旧版 A6「俯冲谷观景台」。

## 重建

```bash
/e/blender/blender.exe --background --python model/lookout_tower/lookout_tower.py   # 约 8 秒
node scripts/verify_tower_colliders.mjs      # 碰撞表离线校验 31 项，任一 FAIL 则 exit 1
```

产出：`lookout_tower.blend` / `lookout_tower.glb`（约 11.8 万三角面，材质与节点 `TW_` 前缀）/
`colliders_tower.json`（app 坐标）/ `preview/*.png`（夜景 7 张 + 实体检视 5 张）。

- 脚本顶部 params 段是全部尺寸的唯一来源；.blend 只是产物，手改会被重跑覆盖
- .blend 内另有 `README_缠魂塔` 文本块和 14 个 `TW_Cam*` 机位；`REF` 集合（地面灯环、相机、灯光）不导出
- 实机取证（不入库）：起 dev server 后 `GAME_URL=http://127.0.0.1:8765 node scripts/verify_tower_shots.mjs shots/tower/v3/E`
  （临时加载 glb 摆到塔位，42 机位），配 `node scripts/tower_pixel_stats.mjs <目录>` 看过曝 / 近黑占比

## 设计参数（用户 2026-11-24 拍板）

- 造型 B「缠旋铁塔」；螺旋梯与升降梯都做；主平台 40m
- 评审修复批：入口整体转 90° 朝南（真实来向是南侧草坪，西侧被过山车回流沟护栏隔开）、
  橙色缠带 + 细白扶手、环廊家具内移成环
- 方向契约见 `.impeccable/surfaces/model-lookout-tower-lookout-tower-py.md`

## 布局

方位一律 app 方位 α = atan2(z, x)：东 0° / 南 90° / 西 180° / 北 270°（Blender 局部点 = (r cos α, −r sin α, z)）。

| 部位 | 尺寸 / 方位 |
|---|---|
| 核心笼 | r 1.62，24 根笼柱；底门朝南 90°、顶门朝北 270°，各带一道滑移层门 |
| 螺旋梯 | r 1.72–3.36，242 级 × 4.8 圈；首 4 级半高 0.083，其余 0.167；梯口东南 58°，俯视逆时针盘升，到顶 130°（面向摩天轮） |
| 缠带 / 扶手 | 踏步外缘橙色发光弦带 r 3.36–3.42（`TW_Ribbon` 1.6 档，铺到第 239 级）；细白扶手 r 3.39（`TW_Rail` 1.0 档） |
| 桁架 | 8 主柱（22.5°+45°k）+ 8 副柱，r 3.80→3.68；首层开敞开间 22.5°–112.5°（梯口 + 门厅）与 157.5°–202.5°（西侧第二入口） |
| 环廊 | r 3.38–5.6 @ 40m，两段长椅（贴内栏杆）、打卡南瓜灯（162°，到达口尽头）、三块方位牌；栈桥朝北接笼顶门 |
| 塔冠 | 玻璃灯室 Ø4.16 @ 42.8–46.0，南瓜形灯芯 + 灵火珠；宝顶、尖顶到约 50.4m，乌鸦风向标 |

发光分档：`TW_Glow` 2.6 只给关节灯珠；`TW_Ribbon` 1.6；`TW_Rail` 1.0；`TW_StepGlow` 1.1（踏前缘）；`TW_FloorGlow` 0.7（踢脚线、地面光带）；
`TW_LampCore` 2.2；`TW_SignGlow` 1.3。幡旗挂在中横杆上，让出 0.6–1.17m 的视线带。

## 碰撞表语义（`colliders_tower.json` v3，游戏接入时控制器须照此实现）

- `floors`：叠层地面。落点处只取「高度 ≤ 脚底 + 步高 0.35」的最高一块为支撑；高度落在 (脚底+0.35, 脚底+1.8] 的当墙；更高的可从下方走过。
  形状 `helix`（带逐级踏面高 `h[k]`）、`sector`、`rect`、`circle`
- `circles`：带 `y0/y1` 的圆，仅脚底高度落在带内才推挤，推挤半径 = r + 0.38
- `lift`：轿厢地面 / 轿壁与轿门高度带随轿厢平移（`wallBand` 相对轿底）；层门 `gateBottom/gateTop` 在轿厢不在该站时闭合
- `pois`：塔顶打卡点带高度 `y`，交互判定须比较高度
- 参考实现：`scripts/lib_tower_sim.mjs`（离线模拟器）

校验结果（2026-11-24）：进梯带 0.81m，出梯带 0.67–0.85m，环廊成环且最窄 0.65m，轿厢门洞 0.66m；
地面 → 梯 → 环廊 → 栈桥 → 顶层轿厢全程可达；环廊与梯上泛洪无漏点。

## 运行时节点契约（游戏接入用）

- `TW_Lift`：轿厢根，z = 轿底，停靠 0.06（底层）↔ 39.92（顶层，轿厢地面 40.0）
- `TW_GateB` / `TW_GateT`：轿厢两扇滑门（轿厢子节点），开 = 平移 `lift.gateB.open`（three.js 节点局部，Y up）
- `TW_LGateB` / `TW_LGateT`：两站层门，常闭，轿厢到位时滑开 `lift.lgateB.open`
- `TW_CallLamp_B` / `TW_CallLamp_T`：呼梯灯，独立材质，游戏侧改自发光色
- `TW_FlameAnchor`：灯室鬼火锚点；`TW_CrowPivot`：乌鸦风向标转轴（绕竖轴慢转）
- 材质 `TW_` 自发光件随设置面板联动；玻璃 `TW_Glass` / `TW_CabGlass` 为 alpha BLEND

## 游戏接入（待做）

控制器叠层地面语义、升降梯逻辑（自动呼梯 / 进厢按 E / 层门联动）、`sync-assets.mjs` 与 main.js 接线、
设置项、塔顶打卡点、移除旧 A6 观景台。注意 `ferris.setHold` 目前只看玩家高度，玩家站上塔会让摩天轮刹停，接入时需限定到登舱站台范围。
