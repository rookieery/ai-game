---
name: 幽夜游乐场 — 降神之夜 The Séance
description: 绒布与鎏金的通灵道具：午夜显灵板上的第一人称游乐场界面
colors:
  velvet-0: "#0b0813"
  velvet-1: "#14101f"
  velvet-2: "#201936"
  velvet-glass: "rgba(20, 16, 31, 0.62)"
  gold: "#c9a227"
  gold-bright: "#e3b93e"
  gold-dim: "rgba(201, 162, 39, 0.55)"
  ivory: "#ede3cb"
  ivory-dim: "rgba(237, 227, 203, 0.72)"
  violet: "#7a4fa8"
  spirit: "#8fe3d9"
typography:
  display:
    fontFamily: "Georgia, STZhongsong, STSong, SimSun, serif"
    fontSize: "clamp(56px, 9.2vw, 94px)"
    fontWeight: 600
    letterSpacing: "0.3em"
  headline:
    fontFamily: "Georgia, STZhongsong, STSong, SimSun, serif"
    fontSize: "28px"
    fontWeight: 400
    letterSpacing: "0.22em"
  title:
    fontFamily: "Georgia, STZhongsong, STSong, SimSun, serif"
    fontSize: "26px"
    fontWeight: 400
    letterSpacing: "0.18em"
  body:
    fontFamily: "Georgia, STZhongsong, STSong, SimSun, serif"
    fontSize: "24px"
    fontWeight: 400
    letterSpacing: "0.62em"
  label:
    fontFamily: "Georgia, STZhongsong, STSong, SimSun, serif"
    fontSize: "22px"
    fontWeight: 400
    letterSpacing: "0.1em"
rounded:
  sm: "4px"
  md: "6px"
  board: "26px"
  pill: "40px"
  circle: "50%"
spacing:
  xs: "8px"
  sm: "10px"
  md: "14px"
  lg: "22px"
  edge: "28px"
components:
  button-pentagram:
    backgroundColor: "{colors.gold}"
    size: "62px 60px"
  button-moon-toggle:
    backgroundColor: "{colors.velvet-glass}"
    size: "52px"
    rounded: "{rounded.circle}"
  panel-hud:
    backgroundColor: "{colors.velvet-glass}"
    textColor: "{colors.ivory}"
    rounded: "{rounded.md}"
    padding: "10px 16px"
  panel-plaque:
    backgroundColor: "rgba(20, 16, 31, 0.66)"
    textColor: "{colors.ivory-dim}"
    rounded: "{rounded.sm}"
    padding: "14px 20px"
  prompt-pill:
    backgroundColor: "rgba(20, 16, 31, 0.78)"
    textColor: "{colors.ivory}"
    rounded: "{rounded.pill}"
    padding: "13px 30px 13px 22px"
  keycap:
    backgroundColor: "rgba(201, 162, 39, 0.1)"
    textColor: "{colors.ivory}"
    rounded: "{rounded.sm}"
    padding: "4px 10px"
---

# Design System: 幽夜游乐场 — 降神之夜 The Séance

## Overview

**Creative North Star: "绒布与鎏金的通灵道具"**

整个 DOM 界面是一场午夜降神会桌面上的道具阵列：加载是一块铺开的显灵板（字母弧 + 灵摆指针 + 五芒星入园键），园中交互由灵摆指向，打卡是逐一点亮的星图，声音是月相表盘。UI 不是"半透明卡片 + 发光描边"的品类默认 HUD 拼盘，而是平时退后、只在关键节点现身的通灵道具——3D 乐园是主角，道具为它服务。

材质立场：绒布黑紫的放射状桌面上（radial-gradient 三级绒布 + 3% 金色暗纹），一切可见之物都是平的金色线稿与象牙实体——月相、星芒、灵摆皆由 SVG path 描线画出，五芒星与指针由 clip-path 剪出。零位图、零字体文件、零外部素材。辉光只作为"焦点之火"出现（全部零偏移），从不作为环境氛围。

字面立场：全站一副衬线嗓（Georgia / STZhongsong / STSong / SimSun 栈），中英同框（「幽夜游乐场 / HOLLOW NIGHT CARNIVAL」），层级只靠字号、宽字距与颜色区分，不换字体、不加字重。文案全部中文；桌面 1080p 优先，无移动断点。

注：PRODUCT.md 品牌承诺里的嘉年华参考色板（南瓜橙 / 暗夜紫 / 磷光绿 / 暖白）属于 3D 场景氛围层；DOM 界面层按方向契约「降神之夜 The Séance」执行本文件的绒布鎏金系统——构建即事实。

**Key Characteristics:**
- 平的金色线稿世界：双金线 inset 框 + SVG 描线符号，无 CSS 浮雕 / 斜面
- 零偏移辉光严格留给焦点与活性元素，绝不环境化
- 灵火青 = 进度 / 活性专属色；velvet 玻璃面板退后衬底
- 一副衬线嗓，宽字距 0.1–0.62em 定层级
- 全中文文案；零图片、零字体资产
- 尊重 prefers-reduced-motion（动画全关，过渡压至 0.01s）

## Colors

整个色板是一张烛光下的绒布牌桌：三种深浅的绒布黑紫做底，鎏金做骨，象牙做肉，灵火青是唯一会"活"的颜色。已验证对比度（对 #14101F）：鎏金 7.7:1，象牙 14.6:1，灵火青 12.6:1。

### Primary
- **鎏金 Gilded Gold**（#c9a227；亮态 #e3b93e；暗态 rgba(201, 162, 39, 0.55)）：结构线与标题的专属色。板框、面板描边、键帽描边、星图计数、主标题、月相描线、五芒星实体——金色是"画在绒布上的线"，不是大面积填充。亮金 #e3b93e 只出现在焦点环、铭牌设施名、活性脉冲峰值；暗金 rgba(…, 0.55) 承担次要描线（弧字母、待机描边、退后面板框线）。

### Secondary
- **灵火青 Spirit-Fire**（#8fe3d9）：进度与活性专属。弧字母点亮（.lit）、星图点亮、灵摆瞳点、召灵文案、加载星尘。它亮起的瞬间，就是"正在显灵"的瞬间。

### Tertiary
- **幽紫 Ghost Violet**（#7a4fa8）：仅作文字选区底色（::selection background rgba(122, 79, 168, 0.55)）。不参与任何组件配色。

### Neutral
- **绒布黑紫 Velvet**（三级：#0b0813 / #14101f / #201936）：#0b0813 页面底色，#14101f 中层（板内衬、转场遮罩、玻璃面板基色），#201936 放射光心与板面亮端。玻璃态面板 = #14101F 以 62%–78% 透明度浮在画面上（键位条 / 星图 / 开关 0.62，铭牌 0.66，提示 pill 0.78）。
- **显灵板象牙 Séance Ivory**（#ede3cb；暗态 rgba(237, 227, 203, 0.72)）：正文与可交互主体的字色、灵摆锤与指针板面的实体色；暗象牙只用于键位标签与铭牌提示。

### Named Rules
**金线为骨 Rule.** 金色只做结构线与标题，象牙只做正文与可交互文字，灵火青只做进度与活性——这条三分法直接写在样式表头部，任何新组件先归位再动手。
**灵火不常亮 Rule.** 灵火青与它的辉光只允许出现在 lit / active / 进度状态；常亮的青色即违例。
**辉光只给焦点 Rule.** 零偏移辉光（0 0 Npx）严格保留给焦点 / 活性元素：就绪的五芒星、点亮的星、开启的月相、点亮的弧字母。环境永远无光。

## Typography

**Display Font:** Georgia / STZhongsong / STSong / SimSun 衬线栈（--font-serif），全站唯一字体族
**Body Font:** 同上（无独立正文字体）
**Label/Mono Font:** 无独立标签字体——标签与正文同族，靠 22px + 0.1em 宽字距识别

**Character:** 一副中西合璧的老衬线嗓：拉丁走 Georgia 的书卷气，中文落中宋 / 宋体的笔画终端；层级全部靠字号（94 → 28 → 26 → 24 → 22px）与宽字距（0.1–0.62em）撑开，字重只有 400 与 600 两档。

### Hierarchy
- **Display** (600, clamp(56px, 9.2vw, 94px), 0.3em)：显灵板主标题「幽夜游乐场」，鎏金 + 26px 零偏移光晕，配等值 text-indent 0.3em 找中。
- **Headline** (400, 28px, 0.22em)：乘坐铭牌设施名（亮金）。
- **Title** (400, 26px, 0.14–0.18em)：灵摆提示文案、召灵文案「灵摆引路 · 唤你入园」、弧字母（26px，靠 margin 分隔不压字距）。
- **Body** (400, 24px, 0.3–0.62em)：板面拉丁副题「HOLLOW NIGHT CARNIVAL」（0.62em）与入园提示「点五芒星 · 入园」（0.3em）——本系统没有段落正文，24px 档只承担短语副题。
- **Label** (400, 22px, 0.1–0.12em)：键帽、键位标签、星图计数、铭牌提示——HUD 的一切常驻文字。

### Named Rules
**宽字距 Rule.** 展示与标签文字一律 0.1em 起步的 letter-spacing；居中排的宽字距文本必须配等值 text-indent 找中（标题 0.3em/0.3em、副题 0.62em/0.62em、入园提示 0.3em/0.3em），否则视觉偏心。
**单声部 Rule.** 全站一个衬线栈；层级只准用字号、字距、颜色（金 / 亮金 / 象牙 / 暗象牙）表达，不得引入第二字体或第三档字重。

## Layout

全视口固定舞台：html / body / #app 100% × 100%、overflow hidden，#game-canvas 铺满；#HUD 以 absolute inset:0 覆盖并 pointer-events:none（子组件按需 opt-in，如月相开关）。桌面 1080p 优先，无响应式断点（手机端明确不做）；唯一的媒体查询是 prefers-reduced-motion。

HUD 锚点：左 / 上 / 右边 28px 锚距，底边 26px。键位条居左下（28 / 26），星图叠其上方（bottom 96px），月相开关居右下（28 / 26），乘坐铭牌居左上（28 / 28），灵摆提示水平居中（bottom 110px）。显灵板 min(980px, 92vw)、980/640 恒比例，grid 居中，四周绒布留白。

间距台阶：8 / 10 / 14 / 22 / 28px（键组内距 8、面板内距 10–14、板心纵向节奏 22、屏幕锚距 28）。密度立场：常驻 HUD 只有键位条 + 星图 + 开关三件，其余全部按需现身。

## Elevation & Depth

平的世界，明说了：这套系统不靠阴影造深度。深度来自三件事——绒布桌面的放射式压暗（radial-gradient #201936 → #14101f → #0b0813 + 3% 金暗纹）、线稿式的金 inset 框（它们是"画上去的线"，不是投影）、以及全场唯一的主漂浮影：显灵板底下的 0 30px 80px。指针与提示 pill 各带一枚轻浮动影，让道具读作"搁在板面上方的实物"。辉光全部零偏移——那是烛火之光，不是阴影。

### Shadow Vocabulary
- **板面浮影 board-float** (`0 30px 80px rgba(0, 0, 0, 0.6)`)：仅显灵板使用，全场唯一的主漂浮影。
- **道具搁影 object-lift** (`drop-shadow(0 10px 24px rgba(0, 0, 0, 0.55))`)：灵摆指针浮于板面之上时。
- **浮牌影 pill-float** (`0 12px 34px rgba(0, 0, 0, 0.45)`)：灵摆提示 pill 现身时。
- **焦点金辉 glow-gold** (`drop-shadow(0 0 10–22px rgba(201, 162, 39, 0.4–0.75))`；标题 text-shadow `0 0 26px rgba(201, 162, 39, 0.4)`)：就绪五芒星脉冲、开启月相、入园一闪；零偏移，只给焦点。
- **活性灵辉 glow-spirit** (`drop-shadow(0 0 6–18px rgba(143, 227, 217, 0.5–0.7))`)：点亮的弧字母 / 星图 / 灵摆瞳点 / 星尘；零偏移，只给活性。

### Named Rules
**平铺 Rule.** 表面默认是平的；全系统只允许显灵板一块"浮"起来，其余道具至多带搁影。inset box-shadow 只用于金线框（线稿语法），不得当作深度手段。

## Shapes

小圆角的线稿世界：面板 4–6px（键帽 / 铭牌 4px，键位条 6px），显灵板 26px，提示 pill 一律 40px 通长胶囊，月相开关整圆。描边一律 1px 实线；板框加厚为 2px。现身提示件用全金描边（铭牌、提示 pill），常驻退后件用暗金描边（键位条、星图、月相开关）。双金线框公式：1px 描边 + inset 0 0 0 3px <面板底色> + inset 0 0 0 4px 金（透明度分级：键位条 0.28、铭牌 0.4、提示 pill 0.45；板面放大为 inset 10px 绒布 + 11.5px 暗金；星图与月相开关保持单线不双框）。符号皆剪影：五芒星按钮与灵摆指针由 clip-path polygon 剪出，月相 / 星芒 / 灵摆链锤由 SVG path 以 1.4–1.7 描宽画出——符号是画出来的，不是字符。

### Named Rules
**双金线 Rule.** 现身的指示性浮层（铭牌、提示 pill、键位条）用"描边 + 深色隔离层 + 内圈金线"的双框语法，内圈金线按重要度取 0.28 / 0.4 / 0.45；常驻退后件（星图、月相开关）只留单线。

## Components

### 加载显灵板（签名组件 Séance Board）
- **构图：** min(980px, 92vw) × 980/640 板面，26px 圆角，160deg 绒布渐变板面，2px 金框 + 双金 inset 框 + 30px/80px 浮影；四周绒布留白由全屏放射 veil（ellipse 85% 75% at 50% 46%）+ 3% 金暗纹提供。
- **板面元素：** 顶部字母弧（A–P 间夹「幽夜游乐场」五字金色高亮，进度掠过逐字点亮成象牙 + 灵辉）；左右下角「显灵中 / N%」（27px，0.28em，金，0.78 透明）；中央鎏金标题 + 0.62em 拉丁副题 + 340px 金色渐变分隔线（transparent → gold → transparent）+ 灵火青召灵文案；象牙 clip-path 指针沿弧滑行（left 12% → 74%，0.5s --ease-seance），瞳点为灵火青 18px 辉光；两枚 2.8s 交替闪烁的星芒。
- **入园：** 板底居中五芒星按钮（62×60，gold 实体），就绪后 2.4s 金辉脉冲 + hover 1.12 缩放；点击触发 0.7s 板面一闪（内圈金线转亮金 + 90px 外溢光），420ms 后回调入园；下方 24px / 0.3em 提示文字 0.6s 淡入。
- **状态：** .hidden（0.9s 淡出）→ .gone（visibility 移出无障碍树，五芒星不再可聚焦）。

### 五芒星按钮（Pentagram Button）
- **Shape:** clip-path 十点星形（62×60px），无圆角，无描边。
- **Primary:** gold 实体填充；disabled 态 0.35 透明、去辉光。
- **Hover / Focus:** ready 态 2.4s 金辉脉冲（10 → 22px），hover 放大 1.12；:focus-visible 全站统一 2px 亮金 outline + 4px offset。

### 灵摆提示（Spirit Prompt）
- **Shape:** 40px 胶囊 pill，1px 全金描边双框（内圈 0.45）+ 浮牌影。
- **内容：** 22×30 灵摆 SVG（金链 + 象牙锤 + 灵火青瞳点）→ E 键帽 → 26px / 0.14em 提示文案；现身时灵摆 0.3s 从 -14° 摆入，随后 ±3.5° / 3s 待机摆。
- **状态：** opacity 0 ↔ 1（.show）；pointer-events 恒 none，纯提示不拦截操作。

### 键位条（Keys Bar）与键帽（Keycap）
- **条：** velvet 玻璃（0.62）+ 1px 暗金描边双框（内圈 0.28），6px 圆角，10×16 内距，flex gap 10。
- **键帽：** min-width 34px，4px 圆角，rgba(201, 162, 39, 0.1) 金染底 + 暗金描边，22px 象牙字；标签 22px 暗象牙 0.12em。
- **状态：** 入园后 0.8s 淡入，6s 后减淡至 0.4（.dim），hover / Alt 恢复。

### 星图（Star Map）
- **Style:** 同键位条面板底（0.62 玻璃、暗金描边、6px 圆角、10×14 内距）；一排 22px 描线星（1.4 描宽，暗金）+ 22px / 0.1em 金色计数「N / M」。
- **State:** 未收 = 描线；已收（.lit）= 灵火青填充 + 描边 + 8px 灵辉；0.4s 过渡。

### 月相开关（Moon Toggle）
- **Shape:** 52px 整圆，velvet 玻璃底，1px 暗金描边；26px 月相 SVG（1.7 描宽）。
- **State:** on = 金描边 + 6px 亮金辉光；off = 暗金描边 + 斜杠线现形；hover 描边转亮金 + 16px 金辉。
- **行为：** 常驻 HUD 中唯一可点组件（pointer-events:auto），状态落 localStorage。

### 乘坐铭牌（Ride Plaque）
- **Style:** 左上 28 / 28，14×20 内距，0.66 玻璃底，1px 全金描边双框（0.4），4px 圆角。
- **字：** 设施名 28px 亮金 0.22em；提示 22px 暗象牙 0.1em。opacity 0 ↔ 1（0.5s）。

### 转场遮罩（Fade Veil）
- 全屏 velvet-1 纯色（z-index 90，在加载屏之下），opacity 0.4s；转场协议：淡入 420ms → 回调切换 → 120ms 后淡出。

### 动效语法（全局）
- 缓动：--ease-seance = cubic-bezier(0.22, 0.9, 0.34, 1)，用于滑行 / 摆入 / 板面过渡；普通淡变用 ease。
- 时值：板面淡出 0.9s；滑行与现身 0.4–0.5s；键位条 0.8s；转场节拍 420ms / 120ms；一闪 0.7s。
- 待机微摆：±3°（指针 / 星芒 / 灵摆，3s ease-in-out alternate）——道具"活着"但不动场。
- prefers-reduced-motion：动画全关，过渡压至 0.01s。

## Do's and Don'ts

### Do:
- **Do** 先归位再动手：金 = 结构线 / 标题、象牙 = 正文 / 可交互、灵火青 = 进度 / 活性（样式表头部契约），新组件三选一。
- **Do** 用双金线框公式（1px 描边 + 3px 底色隔离层 + 4px 内圈金线）包任何现身浮层；内圈金线按重要度取 0.28 / 0.4 / 0.45。
- **Do** 符号全部手绘：SVG path 描线（1.4–1.7 描宽）或 clip-path 剪影；图标 22–34px。
- **Do** 辉光零偏移且只给焦点 / 活性（0 0 6–26px）；待机微摆语法 ±3° / 3s alternate。
- **Do** 居中宽字距文本配等值 text-indent 找中。
- **Do** 保留 prefers-reduced-motion 降级与 :focus-visible 亮金 2px / 4px 焦点环。
- **Do** 全中文文案；拉丁仅作板面副题与字母弧装饰。

### Don't:
- **Don't** 环境辉光 / 常亮辉光：零偏移光只属于焦点与活性元素；静态装饰不得发光。
- **Don't** 品类默认的半透明白卡片 + 发光描边 HUD 拼盘（方向契约明确拒绝）；面板一律 velvet 玻璃底。
- **Don't** 引入图片、字体或音频文件——零外部素材是产品立场；符号用 SVG / clip-path。
- **Don't** 用字符当图标（字符星、字符月）；亦禁图标字体。
- **Don't** 为状态引入第二活动色；灵火青是唯一的"活"色，幽紫只许做选区底。
- **Don't** 做移动端断点或触控适配（桌面键鼠，明确不做）。
- **Don't** 引入第二字体族或 400 / 600 以外的字重。
