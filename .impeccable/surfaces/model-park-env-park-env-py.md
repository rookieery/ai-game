---
version: 1
slug: "model-park-env-park-env-py"
primary_target: "model/park_env/park_env.py"
related_targets: ["model/park_env/park_env.glb","model/park_env/colliders.json"]
---

# Surface brief — 园中墓园 The Retired Rest（东南空地上的园中园）

Scope: `model/park_env/park_env.py` 墓园段产出的全部几何（前庭草皮盘 `PE_GraveForecourt`、新址椭圆草皮盘 `PE_GravePatch`、走道 `PE_PathGraveN/W/A/S/F`、门 `PE_Gate*`、围栏 `PE_GPost*/PE_GRail*/PE_GPicket*`、碑 `PE_Grave*`、守墓灯 `PE_GraveLantern*`、枯树 `PE_GraveTree`、彼岸花 `PE_Higan*`）及其碰撞表、清单灯，加运行时的灵火 / 漂雾簇。Visitor mode: Experience——3D 乐园是主角，墓园是东南空地上一处可以走进去、绕一圈再出来的园中园。

Audience: 中文玩家，桌面键鼠。Job: 从主路拐上支路或从横路进前庭，被门口的灯勾着走进来 → 沿走道看两侧成行的碑 → 在东端焦点前停留 → 在北门里收下南瓜灯 → 从另一个门出去。Action: 走进；靠近南瓜灯按 E。

## 方向契约 Direction contract

THESIS: 这是「这座园子自己的墓园」——退役的游乐设施在这里安息：碑是拿设施零件做的（半埋的摩天轮舱、木马头、过山车轮对），只用造型、不出文字。拒绝「圆头碑 + 木十字 + 塑料骷髅」的通用万圣节墓园默认。

OWN-WORLD: 暖白守墓灯 #FFD9A8 点光 + 紫火尖 #9B5BFF / 墓碑石 #565D6E→#8A93A6 / 铁艺深灰蓝 / 彼岸花暗红 #8A1E1E→#FF4A4A / 灵火青 #8FE3D9 / 鎏金 #C9A227（门徽与焦点，带微光）/ 暖白 + 紫的灯串。造型语言：椭圆草皮盘外一圈尖桩铁艺围栏，两个门都是石门柱 + 铁艺拱 + 新月星徽 + 门柱顶石像鬼；东西主走道从西门通到东端焦点，北门下来一条南北走道接上主走道（丁字）；碑排成规整的行，宽面朝着走道，碑身各自歪几度；冷的过山车绿灯带只作北门外的远景。

STORY: 玩家从主路拐上支路，西门拱上的新月先亮起来。进门是一条被灯串和守墓灯照亮的走道，碑在两侧排成行，尽头是东端的焦点碑。北走道通到北门，门外是前庭和更远的摩天轮。在北门里收下南瓜灯，从北门出去经前庭回横路，或原路回主路。

FIRST VIEWPORT: 西门内 1 m、眼高 1.65、朝东：主走道居中，消失在东端焦点碑；最近的两对碑隔着走道两两相对（x 25 / 29），两盏守墓灯分列走道两侧、以中脊为轴错开（27.4 南 / 42.6 北），灯串逐跨斜过头顶、横贯上 1/3，枯树冠在左上（树在走道北侧，枝梢探到走道上空），围栏尖桩沿椭圆收边；回头（朝西）是门内的挑臂灯与主路路灯。（2026-11-26 更正：原文写「守墓灯等距排在两侧 / 枯树冠在右上」，与实机左右不符，且两盏灯并不等距。）

FORM: 既有世界「降神之夜 The Séance」内的新场地。用户拍板：2026-11-26 评审四问（缺陷 + 提升 24 项 / 退役设施墓园、只用造型不出文字 / 相邻三处一并处理 / 暖光为主）；选址四问（椭圆 36×24 m 心 app (37,58) / 前庭 + 主路支路两个门 / 搬迁与布局分两批 / 逐批提交）；布局两问（丁字一轴一脊 / 规整行列）；批次 4 两问（东端焦点 = 新月方尖碑：3 m 四棱塔、鎏金星尖、四面月相；碑的配比 = 六成设施碑〔半埋摩天轮舱 / 木马头 / 过山车轮对〕+ 四成石碑〔圆弧顶 / 哥特尖 / 平顶〕）。seed: none (pinned) — 世界由既有 DESIGN.md 钉死。

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.
