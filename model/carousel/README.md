# 显灵木马 The Séance Carousel

幽夜游乐场 · 旋转木马设施资产（继摩天轮后第二个可乘坐设施）。

## 重建

```bash
/e/blender/blender.exe --background --python model/carousel/carousel.py
```

产出：`carousel.blend` / `preview/*.png`（5 张预览）/ `carousel.glb`。
`P.render_video=True` 可渲旋转视频；预览灯 `CR_PvLight*` 与预览地面盘导出前自动移除。

## 设计参数（用户 2026-11-17 三问确认）

- 大型场地：平台 R8.0 / 骑乘环 R6.2（10 位弧间距 ~3.9m）/ 平台顶 0.62
- 三灵坐骑（解剖写实放样建模）：象牙鎏金木马 ×3（i2/6/9）、灵火幽灵马 ×3（i1/4/8，半透明+灵火鬃尾+垂焰腿）、
  南瓜稻草马 ×2（i3/7，藤蔓鬃+小南瓜）；座车 = 南瓜马车（i0 入口位）+ 鎏金座车（i5）
- 马体 = `loft()` 沿 21 环侧轮廓（口鼻→头→颈→鬐甲→背→臀→尾根）扫变径椭圆截面；
  腿 = 5 关节渐变锥链细分放样；4 套姿态表轮换（扬蹄/奔驰/飞跃/行进）；鬃 = 颈嵴雕花波浪叶
- 机台：锥顶帐篷+36 瓣波浪裙边灯串+角朝上新月星芒顶饰+铜杆+甲板法阵内环
- 场地：铺装星徽（入口方位）、断弧地灯环、三级台阶、排队围栏、新月招牌
- 建模在原点，入口方位 azimuth 202°（= 世界 (45,18) 指向园区中心）

## 运行时节点契约（与 ferris.js 同套路，phase B 用）

- `CR_Spin`：机台旋转总根（世界包围盒最薄轴 = 旋转轴，feris 同款几何检测）
- `CR_Ride_0..9`：每骑乘位起伏根（挂 CR_Spin 下，本地 +X = 行进切向；马 bob，座车静止）
- 材质 `CR_*` 自发光件随「装饰灯亮度」联动；幽灵马 `CR_GhostBody/CR_Wisp` 带 alpha BLEND

## Phase B（游戏接入，2026-11-17 完成）

- `sync-assets.mjs` 已加 carousel.glb；main.js 加载并摆到 (45, 0, -18)，`__game.carousel` 钩子
- `src/rides/carousel.js`：CR_Spin 程序化旋转（几何检测轴，ferris 同款）+ 马位 sin 起伏
  + 顶棚补光 ×3（随「舱内灯光」）+ CR_ 自发光随「装饰灯」+ 动态碰撞
- 动态碰撞：骑乘位/铜杆每帧读 CR_Ride_i 世界位置改写碰撞圆（`player.registerCircles`）；
  马 r0.55 无限高 / 座车 r0.85 h1.40（顶缘可跳站，随盘转）/ 铜杆 r0.10；controller 增
  `pushOut()` 静止推挤
- park_env：占位剪影已从 blend 区域级删除重导出（scripts/strip_carousel_placeholder.py，
  圆柱 r7.0 @ (45,18)，同时移除横穿机台的灯串 (41,14)->(49,22)；未重跑 py，随机件不动）
- colliders.json 手工补丁（scripts/patch_carousel_colliders.mjs）：删旧剪影 8 圆，加
  平台 r8 h0.62 / 中柱 r0.5 / 三级台阶 / 围栏柱+横杆 / 招牌柱，共 61 圆
- 设置面板新增「显灵木马 · 旋转转速」（config.js carouselSpinPeriod，默认 18 秒/圈）
- 回归：scripts/verify_carousel.mjs（旋转/起伏/台阶/动态碰撞/骑乘）+ verify_jump.mjs 已更新断言
- 骑乘（2026-11-17，PRODUCT.md 多设施乘坐约束解除）：盘面按 E 上就近灵兽/座车
  （interact.js 盘面区 y∈(0.4,1.2) r<7.6），固定座位随盘环游 + 自由环视
  （controller `enterMount`，马眼高 2.24 / 座车 1.36），E 下马回平台 r7.6 落点
