---
version: 1
slug: "index-html"
primary_target: "index.html"
related_targets: []
---

# Surface brief — 幽夜游乐场游戏 UI（加载屏 / HUD / 交互层）

Scope: 桌面浏览器全屏游戏界面的 DOM 层（加载屏、HUD、交互提示、乘坐覆盖层、打卡计数、声音开关）。Visitor mode: Experience——3D 世界是主角，UI 是通灵道具，平时退后、关键节点现身。

Audience: 中文玩家，桌面键鼠，夜间独自沉浸。Job: 无门槛入园 → 漫步找到摩天轮 → 乘坐观光 → 顺手打卡。Action: 按 E（一切交互的唯一动词）。

## 方向契约 Direction contract

THESIS: 游乐场是一场午夜降神会；UI 不是"界面"而是通灵道具——显灵板、灵摆、星象图腾。拒绝品类默认的"半透明卡片 + 发光描边"HUD 拼盘。

OWN-WORLD: 绒布黑紫底 #14101F / 鎏金 #C9A227 / 显灵板象牙 #EDE3CB / 幽紫 #7A4FA8 / 灵火青 #8FE3D9。字体：标题衬线小体大写（Georgia / STZhongsong 栈）宽字距；标签细小鎏金。组件语言：双金线 inset 框、字母弧、星芒月相符号、灵摆指针、五芒星按钮；拒绝大圆角白卡片。

STORY: 玩家被显灵板唤醒入园（加载 = 显灵进度），园中由灵摆指引交互（提示 = 指针指向目标），打卡是逐一点亮的星图，声音开关是月相表盘——全程像被一场降神会接待。

FIRST VIEWPORT: 加载屏 = 铺开的显灵板（980×640 居中，四周深紫黑留白）：顶部字母弧（"幽夜游乐场"五字金亮高亮）、中央衬线鎏金标题、象牙指针悬于板面右下、进度文案「显灵中 · 64%」、板底五芒星「入园」按钮。已锁草图：.impeccable/questions/html/seance.html——构建以它为构图契约。

FORM: 方向「降神之夜 The Séance」（用户在决策页从 THE ROLL 之外改选 IMPECCABLE'S PICK，改选已确认）。seed: seed:c54ff40e94394908

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

## 组件清单与约束

- 加载屏（进度 → 点击入园）、交互提示（灵摆指向 pill）、键位说明条、打卡星图计数、月相声音开关、乘坐覆盖层（设施名 + 随时按 E 离开）、淡入淡出转场
- 桌面 1080p 优先；全部 DOM + CSS 实现，零图片资源；中文文案；指针锁定态下仍可读
- 未决事项：无（乘坐规则 / 打卡 / 声音均已在 PRODUCT.md 确认）
