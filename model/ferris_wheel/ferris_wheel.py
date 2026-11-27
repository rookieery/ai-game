# -*- coding: utf-8 -*-
"""
Ferris Wheel v3 - Halloween Night "幽眠摩天轮" (game-ready glTF asset)
Run: blender --background --python ferris_wheel.py
All sizes in meters. Wheel spins about local Y (axle), cabins stay level.
现行尺寸以 params 段的 P 字典为准 (下面 v2 各条是历史记录, 括号里的轮心 / 台面高是当时的值)。

v2 万圣节惊魂夜重做 (初版; 轮心 19m / 台面 1.0m 均已作废):
  - R=16m, 16 cabins  (当时 hub 19m / 登舱平台顶 1.0m)
  - 双弦杆轮缘桁架 + 之字斜撑 + 内环 + 24 辐条 + 细张拉杆
  - 舱体: 弧顶灯笼 + 密分格玻璃带 + 内饰(地板/端墙长椅/中柱/暖光天花墙裙)
    + 南瓜徽牌 + 裙边缓冲 + 门框  (v2.1: 舱内可走动布局)
  - 站台: 雨棚 + 吊灯 + 排队围栏 + 台阶 + 售票亭 + 地面灯环

v2.3 场景贴合修复:
  - 售票亭/排队围栏/矮柱灯落地 (原按站台面标高 1.55 定位, 但平面位置在站台半径外, 悬空)
  - 排队围栏外移 x=±1.5 -> ±2.7 (原位落地会埋进台阶体), 台阶口两侧各补一盏矮柱灯
  - FW_GroundRing1 南向断弧 ±13°, 不再从台阶下方穿过 (悬浮错觉线)
  - 修复 join_group 分组未填充导致合并静默失效 (glb 1266 mesh -> 按材质合并)
  - legacy FW_Ground 地面盘只在 blend/预览保留, glb 导出前移除 (避免盖住公园地坪)

v3 舱体重做 (2026-11-27, 「景版」; 造型语言跟缠魂塔 / 墓园: 黑铁 + 暗夜紫 + 鎏金新月):
  - 真实观光舱尺寸: 外廓 2.20 (沿轮缘) x 1.80 (进深), 净高 2.00; 地板顶相对枢轴 -2.70
    -> 轮心 20.1 -> 20.41, 停靠时舱地板离站台 0.16 (轮顶 36.1 -> 36.4)
  - 下半舱是壳 (四周壁板 + 地板), 窗台 / 窗顶是周边窄框; 玻璃是 4 片单层 (不再是实心盒);
    没有中柱; 窗台离地板 0.40 (坐姿也能俯看); 长椅落地、靠背顶 0.90 (低于坐姿眼位)
  - 登舱侧 (-y = app +z) 整扇玻璃门 + 把手; 门框材质 FW_DoorSignal (运行时停靠舱亮灵火青)
  - 天花: 深色板 + 顶灯 (FW_CabinLamp) + 窗顶内侧光槽 (FW_CoveLight) + 发光盘 (FW_CabinGlow, 远看窗内亮)
  - 舱只建一次, 按材质合并后 16 个舱共用同一套网格 (glb 里 16 个节点引用同一 mesh,
    运行时 ferris.js 合批成 InstancedMesh); 不导出动画 / UV (运行时程序化转轮)

v3 第 2 批 站台成为必经之路 (2026-11-27; 见文件中段「v3 第 2 批」注释块):
  - 动线: 入口门楼 -> 8 级台阶 (铁艺扶手 + 灯笼) -> 站台排队通道 (铁艺围栏) -> 登舱闸 (轮停稳才开) -> 停靠舱
  - 地面登舱点取消 (登舱只在闸内按 E, 由应用端 interact.js 实现); 停靠舱是实体, 走不进去
  - 站台吊灯 x2 (自发光灯芯 + 运行时点光), 通道 / 扶手 / 门楼的灯笼与「站台灯光亮度」联动
  - 停靠舱门前: 渡板 + 地面鎏金登舱标线
  - 旧排队围栏 (FW_QPost / FW_QRail, 台阶两侧 x=±2.7) 换成通长台阶扶手; 最上一级台阶加深到 1.2 m 塞进圆台下面
    (圆台边缘是弧线, 方台阶原先只在正中相接, 偏离中线上下台阶会踩空几帧)

v3 第 3 批 站台与轮体造型 (2026-11-28; 见文件中段「v3 第 3 批」两个注释块):
  - 雨棚: 八瓣椭圆锥薄壳 (半轴 5.9 x 8.6) + 露明椽子 / 檩 / 顶心圈 + 新月吊坠; 封檐板下沿一圈灯带 (与椽头对齐);
    4 根铁柱挪到斜向檐角下; 檐口灯笼 x6; 原 8 盏悬空吊灯删除
  - 支腿: 两榀平面格构 A 字架 (各自在 |y| = 3.0 的平面内), 两榀之间不再有杆件 (原先的 y 向横撑穿过轮辐平面);
    轴承座挪到轮毂盘外侧, 轴接长; 脚改成站台面上的方座 + 钢底板 + 地脚螺栓
  - 轮毂盘外侧加鎏金新月徽 (随轮转); 柱灯顶四色小球换成小南瓜灯; 轮缘灯珠只留暖白 + 暗夜紫两色
"""
import bpy
import bmesh
import math
from math import radians, pi, cos, sin, atan2
from pathlib import Path
import numpy as np
from mathutils import Vector, Matrix

# ---------------------------------------------------------------- params ---
P = {
    "wheel_radius": 16.0,
    "rim_chord_a_r": 16.0,      # 轮缘外弦
    "rim_chord_b_r": 15.25,     # 轮缘内弦 (桁架双弦杆)
    "rim_half_gap": 2.2,        # 轮缘平面 y = +/- gap (2.2: 桁架距舱侧窗 >=1.4m, 避免贴窗穿帮)
    "inner_ring_r": 9.6,
    "hub_z": 20.41,             # v3: 20.1 -> 20.41 (舱变高后停靠地板仍离站台 0.16; 轮顶 36.4 < 缠魂塔 40)
    "platform_r": 9.0,
    "platform_h": 1.55,         # 高站台: v3 停靠时舱地板 1.71, 比台面高 cabin_step 0.16 (见 cabin_step)
    "ground_r": 70.0,
    "cabins": 16,
    "spokes_per_side": 24,
    "lattice_per_side": 48,     # 轮缘桁架之字斜撑数/侧
    "spin_period_s": 28.0,
    "fps": 30,
    "leg_base_x": 6.2,
    "leg_base_y": 3.0,
    "leg_top_x": 0.66,           # v3 第 3 批: 腿顶接轴承座侧面 (座 r 0.62, 在 |y| = 3.0); 原 1.1 接在转动的轮毂盘上
    "leg_top_y": 3.0,            # v3 第 3 批: 两榀 A 字架各在 |y| = 3.0 的平面里 (原 2.2)
    "res_still": (1600, 900),
    "glass_alpha": 0.06,        # v3: 单层单片玻璃, 近乎无色 (0.20 -> 0.06: 不再给夜景压一层深蓝)
    "render_video": False,      # 迭代期 False, 定稿 True
    # v3 舱体 (见文件头说明); 应用端 controller.js 的 CABIN 常量与此严格对应
    "cabin_w": 2.20,            # 外宽 (沿轮缘)
    "cabin_d": 1.80,            # 进深 (沿轮轴; 轮缘在 y = +/- 2.2, 侧窗离轮缘 1.3)
    "cabin_floor_dz": -2.70,    # 地板顶相对枢轴 (停靠时 = 站台 1.55 + 0.16)
    "cabin_h": 2.00,            # 净高 (地板顶 -> 天花底)
    "cabin_sill": 0.40,         # 窗台离地板
    "cabin_step": 0.16,         # 停靠时舱地板高出站台
}

# 万圣节色板
HEX = {
    "orange":  "#FFA53B",   # 南瓜橙
    "violet":  "#9B5BFF",   # 暗夜紫
    "green":   "#8CFF4A",   # 磷光绿
    "red":     "#C43B3B",   # 暗红
    "warm":    "#FFE9C4",   # 暖白灯色
    "metal":   "#3A4152",
    "metal_d": "#1E2330",
    "iron":    "#23273A",
    "ground":  "#0A0D16",
    "platform":"#161B27",
    "night":   "#060913",
    "wood":    "#4A3526",
}

def hex_lin(h, a=1.0):
    """sRGB hex -> linear RGBA tuple (Blender works in linear)."""
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i+2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, a)

ASSET_BLOOM = str(Path(bpy.app.binary_path).parent / "5.3" / "datafiles" /
                  "assets" / "nodes" / "compositing_nodes_essentials.blend")
OUT = Path(__file__).resolve().parent
PREV = OUT / "preview"

# ----------------------------------------------------------------- utils ---
def link_col(ob, col):
    for c in ob.users_collection:
        c.objects.unlink(ob)
    col.objects.link(ob)

def sock(node, ident):
    for s in node.inputs:
        if s.identifier == ident:
            return s
    return None

def make_mat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0,
             coat=0.0, alpha=1.0, single=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    s = sock(p, "Base Color")
    if s: s.default_value = (*hex_lin(color)[:3], alpha)
    if alpha < 1.0:
        s = sock(p, "Alpha")
        if s: s.default_value = alpha
    s = sock(p, "Metallic")
    if s: s.default_value = metal
    s = sock(p, "Roughness")
    if s: s.default_value = rough
    if emit:
        s = sock(p, "Emission Color")
        if s: s.default_value = hex_lin(emit)
        s = sock(p, "Emission Strength")
        if s: s.default_value = strength
    if coat:
        s = sock(p, "Coat Weight")
        if s: s.default_value = coat
    if single:
        # 单面材质 (glTF doubleSided=false): 舱体件法线朝外即可, 玻璃不再被 three 双面画两遍
        m.use_backface_culling = True
    return m

def smooth(ob):
    for poly in ob.data.polygons:
        poly.use_smooth = True

def add_cyl(name, r, depth, loc, rot=(0, 0, 0), mat=None, verts=16, sm=True, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, vertices=verts,
                                        location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    if mat: ob.data.materials.append(mat)
    if sm: smooth(ob)
    return ob

def cyl_between(name, p1, p2, r, mat, verts=10, sm=True):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    L = d.length
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=1.0, vertices=verts,
                                        location=(p1 + p2) / 2)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (1, 1, max(L, 1e-4))
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    if mat: ob.data.materials.append(mat)
    if sm: smooth(ob)
    return ob

def add_torus(name, R, tube, loc, rot=(0, 0, 0), mat=None, ms=64, ns=10):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=tube,
                                     major_segments=ms, minor_segments=ns,
                                     location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    if mat: ob.data.materials.append(mat)
    smooth(ob)
    return ob

def torus_gap(ob, gap_half_deg, gap_center_deg):
    """水平圆环按局部角度开缺口: 删 [center-half, center+half] 区间的顶点。
    用于发光地环在登舱台阶走廊断开 (角度 270° = blender -y = 台阶侧)。"""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lo = radians(gap_center_deg - gap_half_deg) % (2 * pi)
    hi = radians(gap_center_deg + gap_half_deg) % (2 * pi)
    def in_gap(v):
        a = atan2(v.co.y, v.co.x) % (2 * pi)
        return lo <= a <= hi
    doomed = [v for v in bm.verts if in_gap(v)]
    bmesh.ops.delete(bm, geom=doomed, context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return ob

def add_box(name, size, loc, rot=(0, 0, 0), mat=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    if mat: ob.data.materials.append(mat)
    return ob

def add_bevel_box(name, size, loc, mat=None, segments=3, width=0.03, rot=(0, 0, 0)):
    ob = add_box(name, size, loc, rot=rot, mat=mat)
    bev = ob.modifiers.new("Bevel", "BEVEL")
    bev.width = width
    bev.segments = segments
    bev.limit_method = "ANGLE"
    try:
        bev.angle_limit = radians(40)
    except Exception:
        pass
    return ob

def add_cone(name, r, depth, loc, mat=None, verts=4, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(radius1=r, depth=depth, vertices=verts,
                                    location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    if mat: ob.data.materials.append(mat)
    smooth(ob)
    return ob

def add_sphere(name, r, loc, mat=None, seg=16, ring=10, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=seg, ring_count=ring,
                                         location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    if mat: ob.data.materials.append(mat)
    smooth(ob)
    return ob

def add_empty(name, loc):
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.empty_display_size = 0.6
    return ob

def parent_keep(child, parent):
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()

def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

# ---------------------------------------------------------------- build ----
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = P["fps"]
sc.frame_start = 1
sc.frame_end = 1                     # v3: 不烘焙动画, 只留一帧静止姿态

col_static = bpy.data.collections.new("Static")
col_wheel  = bpy.data.collections.new("WheelSpin")
sc.collection.children.link(col_static)
sc.collection.children.link(col_wheel)

DOTS   = [HEX["warm"], HEX["violet"]]   # v3 第 3 批: 轮缘灯珠只留暖白 + 暗夜紫两色 (原橙 / 紫 / 绿 / 红四色)

# materials -------------------------------------------------------------
m_metal    = make_mat("FW_Metal", HEX["metal"], rough=0.45, metal=0.85)
m_metal_d  = make_mat("FW_MetalDark", HEX["metal_d"], rough=0.6, metal=0.7)
# v3: 铁件改喷漆钢 (金属度 0.8 -> 0.25): 场景没有环境贴图, 高金属度在夜里只剩高光点、其余纯黑
m_iron     = make_mat("FW_Iron", "#2E2A38", rough=0.5, metal=0.25)
m_wood     = make_mat("FW_Wood", HEX["wood"], rough=0.85, metal=0.0)
m_ground   = make_mat("FW_Ground", HEX["ground"], rough=0.95)
m_platform = make_mat("FW_Platform", HEX["platform"], rough=0.55, metal=0.1)
m_rim_a    = make_mat("FW_RimAmber", HEX["orange"], rough=0.4, emit=HEX["orange"], strength=2.2)
m_rim_v    = make_mat("FW_RimViolet", HEX["violet"], rough=0.4, emit=HEX["violet"], strength=2.2)
m_dot = [make_mat(f"FW_Dot{i}", c, rough=0.4, emit=c, strength=2.6) for i, c in enumerate(DOTS)]
m_lamp   = make_mat("FW_RoofLamp", HEX["warm"], rough=0.4, emit=HEX["warm"], strength=2.6)
m_edge_c = make_mat("FW_EdgeWarm", HEX["warm"], rough=0.4, emit=HEX["warm"], strength=2.4)
# v3 舱体材质 (全部单面; 自发光 <= 1 的导出时会乘进 emissiveFactor, 运行时按材质名归到
# 「舱内灯光」(CabinGlow / CoveLight / CabinLamp / RoofLamp) 或「装饰灯」(Lacquer / Gold / DoorSignal))
m_lacquer = make_mat("FW_Lacquer", "#5630A6", rough=0.38, metal=0.05,
                     emit="#5630A6", strength=0.30, single=True)
m_gold    = make_mat("FW_Gold", "#C9A227", rough=0.4, metal=0.45,
                     emit="#C9A227", strength=0.55, single=True)
m_velvet  = make_mat("FW_Velvet", "#2C1040", rough=0.95, single=True)
m_ceil    = make_mat("FW_Ceiling", "#17121F", rough=0.9, single=True)
m_glass   = make_mat("FW_Glass", "#B7CDDA", rough=0.05, metal=0.0,
                     alpha=P["glass_alpha"], single=True)
try:
    m_glass.blend_method = "BLEND"
except Exception:
    pass
try:
    m_glass.surface_render_method = "BLENDED"
except Exception:
    pass
# 舱内三档暖光: 顶灯 / 发光盘 (远看窗内是亮的) / 窗顶内侧光槽。强度按默认舱内灯 40% 折算
# (2.4 / 0.84 / 0.26); 基色取暗 (#241C12): 这些件贴着舱内点光, 亮基色会被照白。
# 0.84 < Bloom 阈值 0.85, 发光盘默认不起晕, 调高舱内灯仍能点亮辉光
m_cabglow = make_mat("FW_CabinGlow", "#241C12", rough=0.5, emit=HEX["warm"], strength=2.1, single=True)
m_cove    = make_mat("FW_CoveLight", "#241C12", rough=0.5, emit=HEX["warm"], strength=0.65, single=True)
m_cablamp = make_mat("FW_CabinLamp", "#241C12", rough=0.4, emit=HEX["warm"], strength=6.0, single=True)
# 登舱门框: 平时是喷漆钢色, 运行时停靠且停稳的舱亮灵火青 (ferris.js)
m_signal  = make_mat("FW_DoorSignal", "#2E2A38", rough=0.5, metal=0.25,
                     emit="#8FE3D9", strength=1.1, single=True)
# v3 第 2 批: 站台灯具 (门楼 / 扶手 / 通道围栏 / 吊灯灯芯) —— 随「站台灯光亮度」(ferris.js, 连吊灯点光一起调)。
# 基色取暗: 灯芯贴着吊灯点光, 亮基色会被照白。站台灯具密集 (二十来盏), 强度比舱檐灯线 (2.6) 低一档, 默认辉光下不发闷
m_station = make_mat("FW_StationLamp", "#241C12", rough=0.4, emit=HEX["warm"], strength=2.2, single=True)
# 登舱闸柱灯: 平时是喷漆钢色, 轮停稳、停靠舱吸附到位时亮灵火青 (与停靠舱门框同一个状态, ferris.js)
m_gate_signal = make_mat("FW_GateSignal", "#2E2A38", rough=0.5, metal=0.25,
                         emit="#8FE3D9", strength=1.1, single=True)
# v3 第 3 批: 柱灯顶的小南瓜灯 —— 本体微透光 (夜里看得出是南瓜), 镂空的脸自发光; 都随「装饰灯亮度」
m_pump  = make_mat("FW_Pumpkin", "#C87419", rough=0.45, emit="#FF8A2A", strength=0.55)
m_pface = make_mat("FW_PumpkinFace", "#241C12", rough=0.5, emit=HEX["warm"], strength=2.6)
m_ring_a = make_mat("FW_RingAmber", HEX["orange"], rough=0.4, emit=HEX["orange"], strength=1.8)
m_ring_v = make_mat("FW_RingViolet", HEX["violet"], rough=0.4, emit=HEX["violet"], strength=1.8)
m_hub_g  = make_mat("FW_HubGlow", HEX["warm"], rough=0.4, emit=HEX["warm"], strength=2.6)
m_sign   = make_mat("FW_Sign", HEX["violet"], rough=0.4, emit=HEX["violet"], strength=2.0)

R = P["wheel_radius"]
G = P["rim_half_gap"]
HZ = P["hub_z"]
CA, CB = P["rim_chord_a_r"], P["rim_chord_b_r"]


# ---- 通用小件 (v3 舱体与站台共用): 单面片 / 新月片 / 浅穹顶 / 把对象变换烘进网格 ----
def add_plane(name, w, h, loc, rot=(0, 0, 0), mat=None):
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (w, h, 1.0)
    if mat: ob.data.materials.append(mat)
    return ob


def add_crescent(name, s, loc, rot=(0, 0, 0), mat=None, depth=0.10, seg=28):
    """新月片: 外圆 (R=1) 减内圆 (r=0.88, 圆心偏 0.44) 的轮廓, 沿本地 +Z 拉厚 depth*s。
    平面在本地 XY (y 向上), 上下对称; 贴到哪个面就绕 X / Z 转过去。"""
    R_, r_, cx = 1.0, 0.88, 0.44
    x = (R_ * R_ - r_ * r_ + cx * cx) / (2 * cx)
    y = math.sqrt(max(R_ * R_ - x * x, 0.0))
    a_out = math.atan2(y, x)             # 外圆上的交点角
    a_in = math.atan2(y, x - cx)         # 内圆上的交点角
    pts = []
    for k in range(seg + 1):             # 外圆: 上交点 -> 左侧 -> 下交点
        a = a_out + (2 * pi - 2 * a_out) * k / seg
        pts.append((R_ * cos(a), R_ * sin(a)))
    for k in range(1, seg):              # 内圆: 下交点 -> (-0.44, 0) -> 上交点
        a = -a_in - (2 * pi - 2 * a_in) * k / seg
        pts.append((cx + r_ * cos(a), r_ * sin(a)))
    bm = bmesh.new()
    bm.faces.new([bm.verts.new((px * s, py * s, 0.0)) for px, py in pts])
    res = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    bmesh.ops.translate(bm, vec=(0.0, 0.0, depth * s),
                        verts=[v for v in res["geom"] if isinstance(v, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = rot
    if mat: me.materials.append(mat)
    return ob


def add_half_dome(name, loc, mat, sx, sy, sz):
    """浅穹顶: 单位球裁掉 z<0 的部分, 再按 (sx, sy, sz) 缩放。"""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=32, ring_count=12, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -1e-6], context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.scale = (sx, sy, sz)
    if mat: ob.data.materials.append(mat)
    smooth(ob)
    return ob


def apply_xform(ob):
    """把对象变换烘进网格 (合并前用: 合并结果在舱本地系里变换 = 恒等)。"""
    ob.data.transform(ob.matrix_basis)
    ob.matrix_basis = Matrix.Identity(4)


# ground & platform -----------------------------------------------------
add_cyl("FW_Ground", P["ground_r"], 0.2, (0, 0, -0.1), mat=m_ground, verts=64)
add_cyl("FW_Platform", P["platform_r"], P["platform_h"],
        (0, 0, P["platform_h"] / 2), mat=m_platform, verts=64)
add_torus("FW_EdgeRing", P["platform_r"] - 0.05, 0.06,
          (0, 0, P["platform_h"] + 0.02), mat=m_edge_c, ms=96, ns=8)

# 台阶 (platform -y 侧, 8 级到 1.55 高站台)。v3 第 2 批: 第 0 级 (最上一级) 加深到 1.2, 北端塞进圆台下面 ——
# 圆台边缘是弧线, 4.4 m 宽的方台阶原先只在正中 (x=0) 与圆台相接, 两侧 (x -> ±2.2) 台阶起点离圆台边缘最多差
# 0.28 m, 人偏离中线上下台阶会踩空几帧 (下乘落点走台阶东侧下台, 实测 19 帧腾空)。
# 应用端 controller.js 的台阶矩形 (stepRects 第 0 级) 与此同步。
for k in range(8):
    top_z = P["platform_h"] - (k + 1) * 0.194
    start, depth = (8.70, 1.2) if k == 0 else (9.0 + k * 0.9, 0.9)       # app z 起点 / 进深
    add_box(f"FW_Step{k}", (4.4, depth, 0.194), (0, -(start + depth / 2), top_z - 0.097),
            mat=m_platform)

# 地面灯环 (v2.3: 内环南向断弧 ±13°, 避免发光线从登舱台阶下方穿过造成悬浮错觉)
add_torus("FW_GroundRing1", 12.5, 0.05, (0, 0, 0.03), mat=m_ring_a, ms=96, ns=8)
torus_gap(bpy.data.objects["FW_GroundRing1"], gap_half_deg=13.0, gap_center_deg=270.0)
add_torus("FW_GroundRing2", 16.5, 0.05, (0, 0, 0.03), mat=m_ring_v, ms=96, ns=8)

# 平台矮柱灯 (v2.3: 落地 z=0 起步; 原悬空 1.55 — 平面位置在站台半径外却按站台面标高定位。
# 南向走廊 (blender -y) 让位登舱台阶, 撤掉该处一盏, 在台阶口两侧各补一盏)
bollard_xy = [(10.4 * cos(i * pi / 6), 10.4 * sin(i * pi / 6))
              for i in range(12) if i != 9]
bollard_xy += [(2.69, -10.05), (-2.69, -10.05)]
def pumpkin_body(name, loc, r, h, mat, seg=24, ring=9, lobes=8, amp=0.07):
    """带瓣纹的扁南瓜 (bmesh 直建): 周向 8 道鼓起, 底部略压扁。r = 水平半径, h = 上半高 (下半高 = 0.85 h)。"""
    bm = bmesh.new()
    top = bm.verts.new((loc[0], loc[1], loc[2] + h))
    bot = bm.verts.new((loc[0], loc[1], loc[2] - h * 0.85))
    rows = []
    for j in range(1, ring):
        phi = pi * j / ring
        sp, cp = sin(phi), cos(phi)
        row = []
        for i in range(seg):
            th = 2 * pi * i / seg
            lobe = 1 + amp * (0.5 - 0.5 * cos(lobes * th)) * (sp ** 1.2)
            row.append(bm.verts.new((loc[0] + r * sp * cos(th) * lobe, loc[1] + r * sp * sin(th) * lobe, loc[2] + h * cp * (0.85 if cp < 0 else 1.0))))
        rows.append(row)
    for i in range(seg):
        i2 = (i + 1) % seg
        bm.faces.new((top, rows[0][i2], rows[0][i]))
        bm.faces.new((bot, rows[-1][i], rows[-1][i2]))
    for j in range(len(rows) - 1):
        for i in range(seg):
            i2 = (i + 1) % seg
            bm.faces.new((rows[j][i], rows[j + 1][i], rows[j + 1][i2], rows[j][i2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    me.materials.append(mat)
    smooth(ob)
    return ob


for i, (x, y) in enumerate(bollard_xy):
    add_cyl(f"FW_Bollard{i}", 0.1, 0.5, (x, y, 0.25), mat=m_iron, verts=10)
    # v3 第 3 批: 柱顶小南瓜灯 (原四色小球)。扁南瓜 + 瓜梗, 脸朝灯外; 台阶口那两盏朝南 (面向上台阶的人)
    ry = atan2(y, x) if i < 11 else -pi / 2           # 脸的朝向 (环上的朝外)
    pr, pz = 0.17, 0.125                              # 南瓜水平半径 / 上半高 (瓣纹 ±7%)
    cz = 0.53 + 0.85 * pz                            # 南瓜底坐在柱顶箍上
    add_cyl(f"FW_BollardCollar{i}", 0.125, 0.05, (x, y, 0.505), mat=m_gold, verts=10)
    pumpkin_body(f"FW_BollardPump{i}", (x, y, cz), pr, pz, m_pump)
    add_cyl(f"FW_BollardStem{i}", 0.028, 0.11, (x, y, cz + pz + 0.04), mat=m_metal_d, verts=6)
    ca, sa = cos(ry), sin(ry)
    rr = pr * math.sqrt(1 - (0.035 / pz) ** 2)       # 眼 / 嘴所在高度处南瓜的水平半径
    for ex in (-0.062, 0.062):                       # 两只三角眼: 外面凸出瓜面 11..35 mm (瓣峰 / 瓣谷), 不会被瓜面埋住
        d = rr - 0.012
        add_cone(f"FW_BollardEye{i}_{ex}", 0.052, 0.07, (x + ca * d - sa * ex, y + sa * d + ca * ex, cz + 0.035),
                 mat=m_pface, verts=3, rot=(radians(90), 0, ry + radians(90)))
    for mk in (-0.062, 0.0, 0.062):                  # 三段嘴: 同理
        d = rr - 0.002
        add_box(f"FW_BollardMouth{i}_{mk}", (0.04, 0.05, 0.044), (x + ca * d - sa * mk, y + sa * d + ca * mk, cz - 0.035),
                rot=(0, 0, ry), mat=m_pface)

# ===== v3 第 3 批 (2026-11-28): 雨棚 = 八瓣椭圆锥 + 露明椽子 ==================================
# 原雨棚是方锥 (角在 (±6.22, ±6.22)) 套一个圆环灯带 (R 6.55): 灯带沿轴向外伸 0.33 m、在角上缩进 1.59 m;
# 8 盏吊灯悬在屋面投影外; 棚底一整块平板, 仰视没有椽梁。
# 新雨棚平面是八边形椭圆, 半轴沿轮面 (x) 5.9、垂直轮面 (y) 8.6 —— 沿轮面只能到 5.9: 舱的吊架顶走 R 16.1 的圆,
# x = 5.9 处高 5.64 m, 檐口灯带底 5.88 m, 余量 0.24 m, 再往外吊架会扫穿屋檐。
#   棚面 = 一层薄壳 (仰视看得见壳底和椽檩); 8 根椽子在棱上, 两道檩 + 顶心圈 + 顶心盘 + 新月吊坠;
#   封檐板下沿一圈灯带, 与椽头对齐; 4 根铁柱立在斜向 4 个檐角下 (±4.17, ±6.08);
#   另 4 个檐口中点正好是 A 字支腿穿出屋面处 (不挂灯); 檐口灯笼挂在其余檐口上。
CAN_AX, CAN_AY = 5.90, 8.60                  # 檐口椭圆半轴 (x 沿轮面, y 垂直轮面)
CAN_Z, CAN_T, CAN_TOP = 6.10, 0.06, 7.60     # 棚面底 (檐口) / 棚面厚 / 顶尖
RAF_R = 0.06                                 # 椽子半径
RAF_IN_Z, RAF_OUT_Z = CAN_TOP - CAN_T - RAF_R, CAN_Z - RAF_R   # 椽子轴线: 顶心端 / 檐口端 (上沿贴棚面底)
RHO_IN = 0.55 / CAN_AY                       # 顶心圈处的径向比例
PH = P["platform_h"]
THS8 = [i * pi / 4 for i in range(8)]


def can_pt(th, rho, z):
    return (CAN_AX * rho * cos(th), CAN_AY * rho * sin(th), z)


def rafter_under_z(y):
    """中央椽子 (沿 y 轴, x = 0) 在 (0, y) 处的下沿高度 —— 站台两盏大吊灯的吊杆挂在这里。"""
    rho = abs(y) / CAN_AY
    return RAF_IN_Z + (RAF_OUT_Z - RAF_IN_Z) * (rho - RHO_IN) / (1 - RHO_IN) - RAF_R


def hang_lantern(name, x, y, zc, core_r=0.13, core_h=0.28, rod_top=6.0):
    """吊灯笼: 吊杆 (从 rod_top 垂到灯帽) + 灯帽 + 六棱发光灯芯 + 铁艺竖棱 + 鎏金底环和吊坠。zc = 灯芯中心高。"""
    k = core_r / 0.13
    cap_h = 0.12 * k
    cap_top = zc + core_h / 2 + cap_h
    add_cyl(f"{name}_Drop", 0.015 * k, max(rod_top - cap_top, 0.02), (x, y, (rod_top + cap_top) / 2), mat=m_iron, verts=6)
    add_cone(f"{name}_Cap", core_r * 1.62, cap_h, (x, y, zc + core_h / 2 + cap_h / 2), mat=m_iron, verts=6)
    add_cyl(f"{name}_Core", core_r, core_h, (x, y, zc), mat=m_station, verts=6)
    for j in range(6):
        th = j * pi / 3                      # 竖棱立在六棱灯芯的棱上
        add_cyl(f"{name}_Rib{j}", 0.012 * k, core_h + 0.02,
                (x + (core_r + 0.015) * cos(th), y + (core_r + 0.015) * sin(th), zc), mat=m_iron, verts=6)
    add_torus(f"{name}_Ring", core_r + 0.005, 0.012 * k, (x, y, zc - core_h / 2 - 0.01), mat=m_gold, ms=24, ns=6)
    add_cone(f"{name}_Tip", 0.05 * k, 0.10 * k, (x, y, zc - core_h / 2 - 0.075 * k - 0.005), mat=m_gold, verts=6, rot=(pi, 0, 0))


def _mesh_obj(name, bm, mat):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    me.materials.append(mat)
    return ob


def poly_band(name, pts_lo, pts_hi, mat):
    """闭合竖带 (上下两圈同点数): 封檐板 / 檐口灯带。"""
    bm = bmesh.new()
    lo = [bm.verts.new(p) for p in pts_lo]
    hi = [bm.verts.new(p) for p in pts_hi]
    for i in range(len(lo)):
        j = (i + 1) % len(lo)
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    return _mesh_obj(name, bm, mat)


def roof_shell(name):
    """八瓣椭圆锥薄壳: 上下两层锥面 + 檐口一圈侧带 (闭合实体; 仰视看到的是壳底)。"""
    bm = bmesh.new()
    a_t = bm.verts.new((0, 0, CAN_TOP))
    a_b = bm.verts.new((0, 0, CAN_TOP - CAN_T))
    r_t = [bm.verts.new(can_pt(th, 1.0, CAN_Z + CAN_T)) for th in THS8]
    r_b = [bm.verts.new(can_pt(th, 1.0, CAN_Z)) for th in THS8]
    for i in range(8):
        j = (i + 1) % 8
        bm.faces.new((a_t, r_t[i], r_t[j]))
        bm.faces.new((a_b, r_b[j], r_b[i]))
        bm.faces.new((r_t[i], r_b[i], r_b[j], r_t[j]))
    return _mesh_obj(name, bm, m_metal_d)


roof_shell("FW_CanopyRoof")
# 封檐板 (黑铁) + 檐口灯带 (暖白, 贴在封檐板下沿)
poly_band("FW_CanopyFascia", [can_pt(th, 1.012, CAN_Z - 0.14) for th in THS8], [can_pt(th, 1.012, CAN_Z + 0.05) for th in THS8], m_iron)
poly_band("FW_CanopyEave", [can_pt(th, 1.012, CAN_Z - 0.22) for th in THS8], [can_pt(th, 1.012, CAN_Z - 0.14) for th in THS8], m_edge_c)
# 8 根椽子 (棱上) + 两道檩 (八边形折线, 贴在椽子下沿) + 顶心圈 + 顶心盘 + 鎏金新月吊坠
for i, th in enumerate(THS8):
    cyl_between(f"FW_Rafter{i}", can_pt(th, RHO_IN, RAF_IN_Z), can_pt(th, 0.995, RAF_OUT_Z), RAF_R, m_iron, verts=8)
    cyl_between(f"FW_ApexRing{i}", can_pt(th, RHO_IN, RAF_IN_Z), can_pt(THS8[(i + 1) % 8], RHO_IN, RAF_IN_Z), 0.05, m_iron, verts=6)
for t in (0.40, 0.72):
    rho = RHO_IN + (1 - RHO_IN) * t
    z = RAF_IN_Z + (RAF_OUT_Z - RAF_IN_Z) * t - RAF_R - 0.045
    for i in range(8):
        cyl_between(f"FW_Purlin{int(t * 100)}_{i}", can_pt(THS8[i], rho, z), can_pt(THS8[(i + 1) % 8], rho, z), 0.045, m_iron, verts=6)
add_cyl("FW_ApexPlate", 0.42, 0.10, (0, 0, CAN_TOP - CAN_T - 0.05), mat=m_iron, verts=16)
add_cyl("FW_ApexDrop", 0.015, 0.26, (0, 0, CAN_TOP - CAN_T - 0.23), mat=m_iron, verts=6)
add_crescent("FW_ApexMoon", 0.30, (0, 0, CAN_TOP - CAN_T - 0.66), rot=(pi / 2, 0, 0), mat=m_gold, seg=28)
# 4 根铁柱: 斜向 4 个檐角 (45 度) 下, 从站台面到檐口
for sx in (1, -1):
    for sy in (1, -1):
        cx_, cy_ = CAN_AX * 0.70711 * sx, CAN_AY * 0.70711 * sy
        z0, z1 = PH + 0.30, CAN_Z - 0.22
        add_cyl(f"FW_CanopyBase{sx}_{sy}", 0.21, 0.30, (cx_, cy_, PH + 0.15), mat=m_iron, verts=12)
        add_cyl(f"FW_CanopyCol{sx}_{sy}", 0.14, z1 - z0, (cx_, cy_, (z0 + z1) / 2), mat=m_iron, verts=12)
        add_cyl(f"FW_CanopyRing{sx}_{sy}", 0.165, 0.05, (cx_, cy_, z1 - 0.30), mat=m_gold, verts=12)
        add_cyl(f"FW_CanopyCap{sx}_{sy}", 0.19, 0.10, (cx_, cy_, z1 - 0.05), mat=m_iron, verts=12)
# 檐口灯笼 x6: 正南 / 正北檐角 + 斜向檐口中点 (那 4 个檐口正中的檐口被支腿占着, 不挂灯)
EAVE_LANTERN_Z = 5.30
for k, th in enumerate((pi / 2, 3 * pi / 2)):
    x, y, _ = can_pt(th, 0.975, 0)
    hang_lantern(f"FW_EaveLantern{k}", x, y, EAVE_LANTERN_Z, core_r=0.10, core_h=0.22, rod_top=CAN_Z - 0.22)
for k, th in enumerate((radians(67.5), radians(112.5), radians(247.5), radians(292.5))):
    a, b = can_pt(th - pi / 8, 0.975, 0), can_pt(th + pi / 8, 0.975, 0)
    hang_lantern(f"FW_EaveLantern{2 + k}", (a[0] + b[0]) / 2, (a[1] + b[1]) / 2, EAVE_LANTERN_Z, core_r=0.10, core_h=0.22, rod_top=CAN_Z - 0.22)
print(f"CANOPY ax={CAN_AX} ay={CAN_AY} eave_z={CAN_Z} top={CAN_TOP} columns=({CAN_AX * 0.70711:.3f}, {CAN_AY * 0.70711:.3f})")

# ===== v3 第 2 批 (2026-11-27): 站台成为必经之路 ================================================
# 动线: 南面主路 -> 入口门楼 (app z 17.4) -> 8 级台阶 (两侧铁艺扶手 + 灯笼) -> 站台 ->
#       排队通道 (围栏 x = ±0.8, app z 2.0..8.85; 东侧 z 4.0..6.0 开口, 通东侧观景区 / 下乘落点) ->
#       登舱闸 (app z 1.9, 轮停稳、舱吸附到位才开) -> 渡板 -> 停靠舱南门, 闸内按 E 登舱; 下乘落回站台东侧。
# 坐标: Blender (x, y = -app_z, z 高)。应用端与此对应:
#   controller.js (STATION 常量 + 碰撞) / interact.js (登舱锚点、指路提示) /
#   ferris.js (闸门开合 FW_BoardGate_L|R、闸柱灯 FW_GateSignal、吊灯点光 FW_StationLamp)。
# 落在园区地面的件一律下探到 -0.08 (园区地坪顶在 0 以下), 不靠「正好 0」贴合。
ST_PORTAL_Z = 17.4                   # 入口门楼 (app z)
ST_HR_X = 2.3                        # 台阶扶手 (x; 台阶宽 4.4, 扶手立在台阶两侧的地面)
ST_LANE_X = 0.8                      # 排队通道围栏 (x)
ST_LANE_Z0, ST_LANE_Z1 = 2.0, 8.85   # 通道围栏 app z 范围 (8.85 = 站台南缘, 再往南是台阶口)
ST_GAP_Z = (4.0, 6.0)                # 东侧围栏开口 (app z): 台阶两侧上来的人从这里进通道
ST_GATE_Z = 1.9                      # 登舱闸线 (app z)
ST_PLATE_Z = (0.94, 1.34)            # 渡板 app z 范围: 紧贴停靠舱裙边 (z ±0.93) 外侧, 再往里会插进裙边
ST_LAMPS = [(2.6, 5.18), (5.6, 5.18)]  # 站台吊灯 (app z, 灯心高): 都在中央椽子 (x = 0) 下; 灯芯自发光 + 运行时点光
PH = P["platform_h"]                 # 1.55

# ---- 入口门楼: 两根黑铁柱 (柱箍 / 柱尖鎏金) + 横梁 + 鎏金新月 + 柱内侧灯笼 ----
for sx in (1, -1):
    px, py = sx * 2.5, -ST_PORTAL_Z
    add_box(f"FW_PortalPlinth{sx}", (0.40, 0.40, 0.17), (px, py, 0.005), mat=m_iron)          # 底座 -0.08..0.09
    add_cyl(f"FW_PortalCol{sx}", 0.09, 3.44, (px, py, 0.09 + 1.72), mat=m_iron, verts=12)    # 0.09..3.53
    add_cyl(f"FW_PortalRing{sx}", 0.115, 0.06, (px, py, 2.70), mat=m_gold, verts=12)
    add_cone(f"FW_PortalTip{sx}", 0.10, 0.32, (px, py, 3.69), mat=m_gold, verts=8)           # 3.53..3.85
    lx = sx * 2.28
    cyl_between(f"FW_PortalArm{sx}", (px, py, 2.98), (lx, py, 2.98), 0.015, m_iron, verts=6)
    add_cyl(f"FW_PortalLantern{sx}", 0.10, 0.22, (lx, py, 2.84), mat=m_station, verts=6)
    add_cone(f"FW_PortalCap{sx}", 0.13, 0.08, (lx, py, 2.99), mat=m_iron, verts=6)
add_box("FW_PortalBeam", (5.2, 0.10, 0.14), (0, -ST_PORTAL_Z, 3.46), mat=m_iron)             # 3.39..3.53
add_box("FW_PortalBeamGold", (5.2, 0.112, 0.02), (0, -ST_PORTAL_Z, 3.54), mat=m_gold)
add_cyl("FW_PortalMoonPost", 0.03, 0.40, (0, -ST_PORTAL_Z, 3.73), mat=m_iron, verts=8)        # 3.53..3.93
add_crescent("FW_PortalMoon", 0.42, (0, -ST_PORTAL_Z, 4.34), rot=(pi / 2, 0, 0), mat=m_gold, seg=32)  # 外圆 3.92..4.76

# ---- 台阶扶手: 每侧 4 根立柱 (x = ±2.3, 台阶口那根立在站台面上, 其余落在地面) + 斜扶手 + 中横杆;
#      台阶脚 / 台阶口的柱顶挂灯笼 ----
hr = [(16.5, 1.00), (13.5, 1.582), (10.8, 2.164), (8.6, PH + 1.0)]   # (app z, 扶手顶高)
for sx in (1, -1):
    hx_ = sx * ST_HR_X
    for k, (az, top) in enumerate(hr):
        base = PH - 0.10 if k == len(hr) - 1 else -0.08
        add_cyl(f"FW_HRPost{sx}_{k}", 0.04, top - base, (hx_, -az, (top + base) / 2), mat=m_iron, verts=10)
        add_sphere(f"FW_HRKnob{sx}_{k}", 0.055, (hx_, -az, top + 0.03), mat=m_gold, seg=10, ring=6)
    for k in range(len(hr) - 1):
        (z0, t0), (z1, t1) = hr[k], hr[k + 1]
        cyl_between(f"FW_HRRail{sx}_{k}", (hx_, -z0, t0), (hx_, -z1, t1), 0.03, m_iron, verts=8)
        cyl_between(f"FW_HRRail2{sx}_{k}", (hx_, -z0, t0 - 0.45), (hx_, -z1, t1 - 0.45), 0.018, m_iron, verts=6)
    for k in (0, len(hr) - 1):
        az, top = hr[k]
        add_sphere(f"FW_HRLamp{sx}_{k}", 0.08, (hx_, -az, top + 0.17), mat=m_station, seg=12, ring=8)
        add_cone(f"FW_HRLampCap{sx}_{k}", 0.10, 0.07, (hx_, -az, top + 0.28), mat=m_iron, verts=6)

# ---- 排队通道围栏 (站台面上, x = ±0.8): 西侧通长; 东侧 z 4.0..6.0 留开口, 开口两根柱子加高、挂灯笼 ----
lane_top, lane_mid = PH + 1.02, PH + 0.58
lane_z = {-1: [2.0, 3.14, 4.28, 5.43, 6.57, 7.71, 8.85], 1: [2.0, 3.1, 6.9, 7.88, 8.85]}
lane_seg = {-1: list(zip(lane_z[-1], lane_z[-1][1:])), 1: [(2.0, 4.0), (6.0, 6.9), (6.9, 7.88), (7.88, 8.85)]}
for sx in (1, -1):
    lx_ = sx * ST_LANE_X
    for k, az in enumerate(lane_z[sx]):
        add_cyl(f"FW_LanePost{sx}_{k}", 0.035, 1.08, (lx_, -az, PH + 0.54), mat=m_iron, verts=8)
        add_sphere(f"FW_LaneLamp{sx}_{k}", 0.055, (lx_, -az, PH + 1.15), mat=m_station, seg=10, ring=6)
    for k, (z0, z1) in enumerate(lane_seg[sx]):
        cyl_between(f"FW_LaneRail{sx}_{k}", (lx_, -z0, lane_top), (lx_, -z1, lane_top), 0.03, m_iron, verts=8)
        cyl_between(f"FW_LaneRail2{sx}_{k}", (lx_, -z0, lane_mid), (lx_, -z1, lane_mid), 0.018, m_iron, verts=6)
for k, az in enumerate(ST_GAP_Z):
    add_cyl(f"FW_GapPost{k}", 0.06, 1.55, (ST_LANE_X, -az, PH + 0.775), mat=m_iron, verts=10)
    add_cyl(f"FW_GapRing{k}", 0.075, 0.05, (ST_LANE_X, -az, PH + 1.42), mat=m_gold, verts=10)
    add_sphere(f"FW_GapLamp{k}", 0.09, (ST_LANE_X, -az, PH + 1.66), mat=m_station, seg=12, ring=8)

# ---- 登舱闸: 两根闸柱 (柱顶灯 FW_GateSignal, 轮停稳时亮灵火青) + 对开双扇铁艺闸门 ----
# 闸门扇 = 空节点 FW_BoardGate_L / _R (铰链在柱内侧 x = ∓0.70, app z 1.9, 台面高), 扇面是它的子网格
# (局部坐标以铰链为原点, 沿闸线伸向通道中央)。运行时绕世界竖轴各转 90° 开合, 开位贴回两侧围栏 (往南),
# 不侵入停靠舱。扇面不进静组合并 (静组只收无父网格), 自身按材质合并成 Iron / Gold 两个子网格。
for sx in (1, -1):
    add_cyl(f"FW_GatePost{sx}", 0.055, 1.70, (sx * ST_LANE_X, -ST_GATE_Z, PH + 0.85), mat=m_iron, verts=10)
    add_cyl(f"FW_GateRing{sx}", 0.07, 0.05, (sx * ST_LANE_X, -ST_GATE_Z, PH + 1.50), mat=m_gold, verts=10)
    add_sphere(f"FW_GateLamp{sx}", 0.09, (sx * ST_LANE_X, -ST_GATE_Z, PH + 1.80), mat=m_gate_signal, seg=12, ring=8)
bpy.ops.object.select_all(action="DESELECT")
for side, dir_ in (("L", 1), ("R", -1)):        # L: 西侧铰链, 扇面朝 +x; R: 东侧铰链, 扇面朝 -x
    hinge = Vector((-dir_ * 0.70, -ST_GATE_Z, PH))
    pivot = add_empty(f"FW_BoardGate_{side}", hinge)
    parts = []

    def P3(u, y, z):                              # 扇面局部坐标 -> 世界 (u: 离铰链沿扇面的距离)
        return (hinge.x + dir_ * u, hinge.y + y, hinge.z + z)

    parts.append(cyl_between(f"GP_{side}_Top", P3(0.02, 0, 1.00), P3(0.66, 0, 1.00), 0.022, m_iron, verts=8))
    parts.append(cyl_between(f"GP_{side}_Bot", P3(0.02, 0, 0.12), P3(0.66, 0, 0.12), 0.022, m_iron, verts=8))
    parts.append(cyl_between(f"GP_{side}_StileA", P3(0.02, 0, 0.10), P3(0.02, 0, 1.02), 0.022, m_iron, verts=8))
    parts.append(cyl_between(f"GP_{side}_StileB", P3(0.66, 0, 0.10), P3(0.66, 0, 1.02), 0.022, m_iron, verts=8))
    for k in range(1, 5):
        u = 0.02 + 0.64 * k / 5
        parts.append(cyl_between(f"GP_{side}_Bar{k}", P3(u, 0, 0.12), P3(u, 0, 1.00), 0.012, m_iron, verts=6))
    # 鎏金新月贴在竖条的南侧 (app +z, 通道里的人这一面); R 扇绕竖轴转 180° 与 L 扇镜像
    parts.append(add_crescent(f"GP_{side}_Moon", 0.15, P3(0.34, -0.02 if dir_ > 0 else -0.035, 0.70),
                              rot=(pi / 2, 0, 0 if dir_ > 0 else pi), mat=m_gold, seg=20))
    for ob in parts:
        apply_xform(ob)                               # 对象变换 -> 恒等, 网格顶点 = 世界坐标
        ob.data.transform(Matrix.Translation(-hinge))  # 顶点改成以铰链为原点
        ob.parent = pivot                             # 普通父子 (不设 matrix_parent_inverse): 空节点转, 扇面跟着转
    gate_groups = {}
    for ob in parts:
        gate_groups.setdefault(ob.data.materials[0].name, []).append(ob)
    for mat_name, obs in gate_groups.items():
        bpy.ops.object.select_all(action="DESELECT")
        for ob in obs:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = obs[0]
        if len(obs) > 1:
            bpy.ops.object.join()
        bpy.context.view_layer.objects.active.name = f"FW_BoardGate_{side}_{mat_name.replace('FW_', '', 1)}"
    print(f"GATE_{side} " + ", ".join(sorted(o.name for o in pivot.children)))
bpy.ops.object.select_all(action="DESELECT")

# ---- 渡板: 停靠舱门口的小踏板 (顶 1.69, 比台面高 0.14); 玩家走不进停靠舱, 登舱按 E ----
add_box("FW_GapPlate", (1.0, ST_PLATE_Z[1] - ST_PLATE_Z[0], 0.14),
        (0, -(ST_PLATE_Z[0] + ST_PLATE_Z[1]) / 2, PH + 0.07), mat=m_iron)
add_box("FW_GapPlateGold", (1.0, 0.03, 0.012), (0, -(ST_PLATE_Z[1] - 0.015), PH + 0.146), mat=m_gold)

# ---- 登舱标线: 停靠舱门前地面上一圈鎏金内嵌线 (框住渡板, 「站这里等」) ----
for sx in (1, -1):      # 两侧纵线
    add_box(f"FW_MarkSide{sx}", (0.04, 0.82, 0.006), (sx * 0.66, -1.46, PH + 0.003), mat=m_gold)
add_box("FW_MarkFront", (1.36, 0.04, 0.006), (0, -1.85, PH + 0.003), mat=m_gold)

# ---- 站台吊灯 x2 (v3 第 3 批改挂中央椽子下; 灯心位置不变, 吊杆长度按椽底高度算) ----
for k, (az, lz) in enumerate(ST_LAMPS):
    hang_lantern(f"FW_StationLamp{k}", 0, -az, lz, rod_top=rafter_under_z(-az))
print(f"STATION portal_y={-ST_PORTAL_Z} lane_x=±{ST_LANE_X} gap_z={ST_GAP_Z} gate_z={ST_GATE_Z} lamps={ST_LAMPS}")

# 售票亭 (ticket booth, 右前; v2.3 落地 z=0 起步, 原按站台面标高悬空 1.55)
bx, by = 7.6, -8.2
add_box("FW_BoothBody", (1.7, 1.7, 2.2), (bx, by, 1.1), mat=m_wood)
add_cone("FW_BoothRoof", 1.35, 0.75, (bx, by, 2.55), mat=m_metal_d, verts=4,
         rot=(0, 0, radians(45)))
add_box("FW_BoothSign", (0.95, 0.06, 0.5), (bx, by - 0.88, 1.7), mat=m_sign)
add_box("FW_BoothCounter", (1.1, 0.25, 0.08), (bx, by - 0.78, 1.05), mat=m_wood)

# ===== v3 第 3 批 (2026-11-28): A 字支腿 = 两榀格构柱 + 轴承座 ==================================
# 原支腿是 4 根光圆管: 腿顶接在转动的轮毂盘上, 底板埋在台体里; 两榀之间的 3 道横撑和交叉撑 (y 向) 穿过轮子的
# 辐条平面 (|y| = 2.2), 辐条转过来会从杆件里穿过去。现在:
#   · 两榀 A 字架各在自己的平面里 (|y| = LEG_Y = 3.0): 每根柱 4 根弦杆 + 8 层缀条 + 斜缀条, 截面从脚 0.70
#     收到顶 0.44; 平面内 4 道横撑 + 之字斜撑。两榀之间不再有任何杆件 (轮子扫过的 |y| <= 2.51 里不放静止件)。
#   · 腿顶接轴承座: 座挪到轮毂盘外侧 (|y| 2.70..3.30), 轴接长到 ±3.40 从座里穿过去, 外端加静止端盖。
#   · 脚: 站台面上的方座 + 钢底板 + 4 颗地脚螺栓, 看得见 (原底板在台体里)。
LEG_BASE_X, LEG_Y, LEG_TOP_X = P["leg_base_x"], P["leg_base_y"], P["leg_top_x"]
LEG_Z0, LEG_W0, LEG_W1 = PH + 0.40, 0.70, 0.44        # 弦杆起点高 (底板顶) / 脚部截面宽 / 顶部截面宽
HOUSING_R, HOUSING_D = 0.62, 0.60
NL = 8                                                # 缀条层数 (8 个节间, 每节约 2.3 m)
LEG_FACES = ((0, 2), (1, 3), (0, 1), (2, 3))          # 四个面的角点对: 沿 x 两面 / 沿 y 两面


def leg_corners(a, b, t):
    """格构柱在参数 t 处的 4 个角点: (+n,+y) (-n,+y) (+n,-y) (-n,-y); n = 平面内法向 (x-z)。"""
    axis = (b - a).normalized()
    nrm = Vector((axis.z, 0, -axis.x))
    c = a.lerp(b, t)
    w = LEG_W0 + (LEG_W1 - LEG_W0) * t
    return [c + nrm * (sn * w / 2) + Vector((0, ss * w / 2, 0)) for sn in (1, -1) for ss in (1, -1)]


def leg_x(z):
    """A 字架两条柱的轴线在高度 z 处的 |x|。"""
    return LEG_BASE_X + (LEG_TOP_X - LEG_BASE_X) * (z - LEG_Z0) / (HZ - LEG_Z0)


for sx in (1, -1):
    for sy in (1, -1):
        bx, by = sx * LEG_BASE_X, sy * LEG_Y
        add_box(f"FW_LegPlinth_{sx}_{sy}", (1.14, 1.14, 0.33), (bx, by, PH + 0.165), mat=m_platform)
        add_box(f"FW_LegPlate_{sx}_{sy}", (1.24, 1.24, 0.06), (bx, by, PH + 0.36), mat=m_iron)
        for ix in (1, -1):
            for iy in (1, -1):
                add_cyl(f"FW_LegBolt_{sx}_{sy}_{ix}_{iy}", 0.035, 0.11, (bx + ix * 0.50, by + iy * 0.50, PH + 0.44), mat=m_gold, verts=6)
        a = Vector((bx, by, LEG_Z0))
        b = Vector((sx * LEG_TOP_X, by, HZ))
        c0, c1 = leg_corners(a, b, 0.0), leg_corners(a, b, 1.0)
        for i in range(4):
            cyl_between(f"FW_LegChord_{sx}_{sy}_{i}", c0[i], c1[i], 0.055, m_iron, verts=8)
        for fi, (p, q) in enumerate(LEG_FACES):
            for k in range(NL + 1):
                cs = leg_corners(a, b, k / NL)
                cyl_between(f"FW_LegBat_{sx}_{sy}_{fi}_{k}", cs[p], cs[q], 0.03, m_iron, verts=6)
            for k in range(NL):
                d0, d1 = leg_corners(a, b, k / NL), leg_corners(a, b, (k + 1) / NL)
                u, v = (d0[p], d1[q]) if (k + fi) % 2 == 0 else (d0[q], d1[p])
                cyl_between(f"FW_LegDiag_{sx}_{sy}_{fi}_{k}", u, v, 0.026, m_iron, verts=6)
# 每榀 A 字架平面内 (y = ±LEG_Y): 4 道横撑 + 之字斜撑。最低一道 5.0 m 在雨棚下面, 其余在棚顶 (7.6) 以上
for sy in (1, -1):
    levels = (5.00, 8.80, 13.20, 17.40)
    for z in levels:
        cyl_between(f"FW_ATie_{sy}_{int(z * 10)}", (-leg_x(z), sy * LEG_Y, z), (leg_x(z), sy * LEG_Y, z), 0.07, m_iron, verts=8)
    for i in range(len(levels) - 1):
        z0, z1 = levels[i], levels[i + 1]
        s = 1 if i % 2 == 0 else -1
        cyl_between(f"FW_ADiag_{sy}_{i}", (-s * leg_x(z0), sy * LEG_Y, z0), (s * leg_x(z1), sy * LEG_Y, z1), 0.05, m_iron, verts=6)
    s = 1 if (len(levels) - 1) % 2 == 0 else -1
    cyl_between(f"FW_ADiagTop_{sy}", (-s * leg_x(levels[-1]), sy * LEG_Y, levels[-1]), (s * 0.45, sy * LEG_Y, HZ - 0.22), 0.05, m_iron, verts=6)
    # 轴承座 (静止): 座筒 + 外侧法兰 + 连接两条柱顶的鞍座板 + 端盖
    add_cyl(f"FW_Housing_{sy}", HOUSING_R, HOUSING_D, (0, sy * LEG_Y, HZ), rot=(radians(90), 0, 0), mat=m_metal, verts=24)
    add_cyl(f"FW_HousingFlange_{sy}", HOUSING_R + 0.09, 0.06, (0, sy * (LEG_Y + HOUSING_D / 2 + 0.03), HZ), rot=(radians(90), 0, 0), mat=m_iron, verts=24)
    add_box(f"FW_HousingSaddle_{sy}", (1.74, 0.12, 0.50), (0, sy * LEG_Y, HZ - 0.06), mat=m_iron)
    add_cyl(f"FW_AxleCap_{sy}", 0.36, 0.10, (0, sy * (LEG_Y + HOUSING_D / 2 + 0.11), HZ), rot=(radians(90), 0, 0), mat=m_gold, verts=20)
print(f"LEGS base_x={LEG_BASE_X} y={LEG_Y} top_x={LEG_TOP_X} z0={LEG_Z0:.2f} housing_r={HOUSING_R}")

# wheel (rotating) ---------------------------------------------------------
wheel = add_empty("FW_Wheel", (0, 0, HZ))
link_col(wheel, col_wheel)

def wheel_child(ob):
    parent_keep(ob, wheel)
    link_col(ob, col_wheel)

# axle
ob = add_cyl("FW_Axle", 0.34, 6.8, (0, 0, HZ), rot=(radians(90), 0, 0), mat=m_metal, verts=16)  # v3 第 3 批: 接长到 ±3.4, 穿过轴承座
wheel_child(ob)

# 轮缘桁架: 每侧双弦杆 (外弦发光色, 内弦金属) + 之字斜撑
for sy in (1, -1):
    yy = sy * G
    ob = add_torus(f"FW_RimOuter_{sy}", CA, 0.15, (0, yy, HZ), rot=(radians(90), 0, 0),
                   mat=(m_rim_a if sy > 0 else m_rim_v), ms=96, ns=12)
    wheel_child(ob)
    ob = add_torus(f"FW_RimInner_{sy}", CB, 0.11, (0, yy, HZ), rot=(radians(90), 0, 0),
                   mat=m_metal, ms=96, ns=10)
    wheel_child(ob)
    # 之字斜撑 (桁架腹杆)
    for k in range(P["lattice_per_side"]):
        th1 = k * 2 * pi / P["lattice_per_side"]
        th2 = (k + 0.5) * 2 * pi / P["lattice_per_side"]
        p1 = (CA * cos(th1), yy, HZ + CA * sin(th1))
        p2 = (CB * cos(th2), yy, HZ + CB * sin(th2))
        ob = cyl_between(f"FW_Lattice_{sy}_{k}", p1, p2, 0.035, m_metal, verts=6)
        wheel_child(ob)

# 内环 (structural)
for sy in (1, -1):
    ob = add_torus(f"FW_InnerRing_{sy}", P["inner_ring_r"], 0.13, (0, sy * G, HZ),
                   rot=(radians(90), 0, 0), mat=m_metal, ms=64, ns=10)
    wheel_child(ob)

# 辐条: 24 主辐条 (hub -> 内弦) + 24 细张拉杆 (错半角)
spokes_mid = {}
for sy in (1, -1):
    for k in range(P["spokes_per_side"]):
        th = k * 2 * pi / P["spokes_per_side"]
        ex = CB * cos(th)
        ez = HZ + CB * sin(th)
        ob = cyl_between(f"FW_Spoke_{sy}_{k}", (0, sy * G, HZ), (ex, sy * G, ez),
                         0.09, m_metal, verts=8)
        wheel_child(ob)
        # 细张拉杆 (错半角, 内环 -> 内弦)
        th2 = th + pi / P["spokes_per_side"]
        ir = P["inner_ring_r"]
        ob = cyl_between(f"FW_Tension_{sy}_{k}",
                         (ir * cos(th2), sy * G, HZ + ir * sin(th2)),
                         (CB * cos(th2), sy * G, HZ + CB * sin(th2)),
                         0.028, m_metal, verts=6)
        wheel_child(ob)
        spokes_mid[(sy, k)] = (0.5 * CB * cos(th), sy * G, HZ + 0.5 * CB * sin(th))

# 轮盘面之字斜撑 (两轮缘平面间)
n_sp = P["spokes_per_side"]
for k in range(n_sp):
    p1 = spokes_mid[(1, k)]
    p2 = spokes_mid[(-1, (k + 1) % n_sp)]
    ob = cyl_between(f"FW_BraceSpoke_{k}", p1, p2, 0.045, m_metal, verts=6)
    wheel_child(ob)

# 舱位横连杆 (两轮缘平面之间, 舱角度) + 错位斜撑
for k in range(P["cabins"]):
    th = k * 2 * pi / P["cabins"]
    x, z = R * cos(th), HZ + R * sin(th)
    ob = cyl_between(f"FW_CrossTie_{k}", (x, -G, z), (x, G, z), 0.06, m_metal, verts=8)
    wheel_child(ob)
    th2 = th + pi / P["cabins"]
    x2, z2 = CA * cos(th2), HZ + CA * sin(th2)
    ob = cyl_between(f"FW_CrossBrace_{k}", (x2, -G * 0.6, z2), (x2, G * 0.6, z2), 0.04, m_metal, verts=6)
    wheel_child(ob)

# hub
for sy in (1, -1):
    ob = add_cyl(f"FW_HubDisc_{sy}", 1.35, 0.2, (0, sy * G, HZ),
                 rot=(radians(90), 0, 0), mat=m_metal, verts=24)
    wheel_child(ob)
    ob = add_torus(f"FW_HubGlow_{sy}", 1.2, 0.09, (0, sy * (G + 0.22), HZ),
                   rot=(radians(90), 0, 0), mat=m_hub_g, ms=48, ns=8)
    wheel_child(ob)
    for k in range(8):
        th = k * pi / 4
        x, z = 1.05 * cos(th), HZ + 1.05 * sin(th)
        add_bolt = add_sphere(f"FW_HubBolt_{sy}_{k}", 0.05, (x, sy * (G + 0.12), z),
                              mat=m_metal_d, seg=8, ring=6)
        wheel_child(add_bolt)
    # v3 第 3 批: 盘面鎏金新月徽 (随轮转), 贴在轮毂盘外侧面 (|y| = 2.30..2.385)。外径 1.12 略大于发光环内缘 (1.11):
    # 盘面中心被静止的轴承座 (r 0.62) 挡着, 徽小了只剩边角; 放大后徽身在座的左侧、两只角伸到座的上下
    wheel_child(add_crescent(f"FW_HubMoon_{sy}", 1.12, (0, sy * (G + 0.185), HZ),
                             rot=(pi / 2 if sy > 0 else -pi / 2, 0, 0), mat=m_gold, seg=36))

# 轮缘灯珠 (沿外弦)
n_dots = 40
for sy in (1, -1):
    for k in range(n_dots):
        th = k * 2 * pi / n_dots
        x, z = CA * cos(th), HZ + CA * sin(th)
        ob = add_sphere(f"FW_Dot_{sy}_{k}", 0.11, (x, sy * (G + 0.14), z),
                        mat=m_dot[k % len(m_dot)], seg=10, ring=8)
        wheel_child(ob)

# cabins -------------------------------------------------------------------
# v3 (2026-11-27 重做, 「景版」): 舱退到视野边缘, 把画面让给园子; 主题靠材质 (黑铁 / 暗夜紫 / 鎏金新月)。
# 舱只建一次 (枢轴 = 原点的本地系), 按材质合并; 16 个舱共用同一套网格数据 —— glb 里 16 个节点引用
# 同一个 mesh, 运行时 ferris.js 合批成 InstancedMesh。
# 本地系: x 沿轮缘, +y = 长椅侧 (北, app -z), -y = 登舱门侧 (南, app +z), z 向上 (枢轴为 0)。
#   地板顶 CF / 窗台 SILL / 窗顶 HEAD / 天花底 CEIL; 应用端 controller.js 的 CABIN 常量与此严格对应。
CW, CD = P["cabin_w"], P["cabin_d"]
CF = P["cabin_floor_dz"]
SILL = CF + P["cabin_sill"]
CEIL = CF + P["cabin_h"]
HEAD = CEIL - 0.02
assert abs((HZ - R) + CF - (P["platform_h"] + P["cabin_step"])) < 1e-6, \
    "hub_z 与舱地板 / 站台高不匹配 (停靠时枢轴在 hub_z - R, 舱地板应高出站台 cabin_step)"
assert CD / 2 < P["rim_half_gap"] - 0.5, "舱进深太大: 侧窗离轮缘不足 0.5 m"


def build_cabin_proto():
    """只建一次。所有件都在舱本地系里, 枢轴在原点。返回件列表 (未合并)。"""
    parts = []

    def reg(ob):
        parts.append(ob)
        return ob

    hx, hy = CW / 2, CD / 2
    # ---- 裙边 / 地板 ----
    reg(add_box("CP_Skirt", (CW + 0.06, CD + 0.06, 0.08), (0, 0, CF - 0.06), mat=m_iron))
    reg(add_box("CP_Floor", (CW - 0.10, CD - 0.10, 0.06), (0, 0, CF - 0.03), mat=m_wood))
    # ---- 下体: 壳 (暗夜紫漆面, 四角圆柱倒圆) + 鎏金线 + 新月徽 ----
    for sy in (1, -1):
        reg(add_box("CP_BodyY", (CW - 0.20, 0.05, 0.40), (0, sy * (hy - 0.025), CF + 0.18), mat=m_lacquer))
        reg(add_box("CP_GoldLineY", (CW - 0.20, 0.012, 0.014), (0, sy * (hy + 0.004), CF + 0.385), mat=m_gold))
        reg(add_crescent("CP_CresY", 0.11, (0, sy * (hy + 0.012), CF + 0.20),
                         rot=(-pi / 2 if sy > 0 else pi / 2, 0, 0), mat=m_gold, seg=14))
    for sx in (1, -1):
        reg(add_box("CP_BodyX", (0.05, CD - 0.20, 0.40), (sx * (hx - 0.025), 0, CF + 0.18), mat=m_lacquer))
        reg(add_box("CP_GoldLineX", (0.012, CD - 0.20, 0.014), (sx * (hx + 0.004), 0, CF + 0.385), mat=m_gold))
        reg(add_crescent("CP_CresX", 0.11, (sx * (hx - 0.001), 0, CF + 0.20),
                         rot=(pi / 2, 0, sx * pi / 2), mat=m_gold, seg=14))
        for sy in (1, -1):
            reg(add_cyl("CP_BodyCorner", 0.10, 0.40, (sx * (hx - 0.10), sy * (hy - 0.10), CF + 0.18),
                        mat=m_lacquer, verts=16))
    # ---- 窗台框 / 窗顶框: 周边窄框 (v2 的整截面实心板是「看不见地板」的根因) ----
    for sy in (1, -1):
        reg(add_box("CP_SillY", (CW + 0.06, 0.10, 0.05), (0, sy * (hy - 0.025), SILL + 0.025), mat=m_iron))
        reg(add_box("CP_HeadY", (CW + 0.06, 0.10, 0.06), (0, sy * (hy - 0.025), HEAD + 0.03), mat=m_iron))
    for sx in (1, -1):
        reg(add_box("CP_SillX", (0.10, CD - 0.10, 0.05), (sx * (hx - 0.025), 0, SILL + 0.025), mat=m_iron))
        reg(add_box("CP_HeadX", (0.10, CD - 0.10, 0.06), (sx * (hx - 0.025), 0, HEAD + 0.03), mat=m_iron))
    # ---- 玻璃: 4 片单层, 法线朝外 (单面材质; 两头塞进框和角柱里) ----
    gz0, gz1 = SILL + 0.035, HEAD + 0.015
    for sy in (1, -1):
        reg(add_plane("CP_GlassY", CW - 0.06, gz1 - gz0, (0, sy * (hy - 0.005), (gz0 + gz1) / 2),
                      rot=(-pi / 2 if sy > 0 else pi / 2, 0, 0), mat=m_glass))
    for sx in (1, -1):
        reg(add_plane("CP_GlassX", CD - 0.06, gz1 - gz0, (sx * (hx - 0.005), 0, (gz0 + gz1) / 2),
                      rot=(pi / 2, 0, sx * pi / 2), mat=m_glass))
    # ---- 立柱 / 竖梃: 角柱 r 0.032, 细梃 r 0.013 (没有中柱) ----
    zc = (SILL + 0.05 + HEAD) / 2
    zh = HEAD - SILL - 0.05
    for sx in (1, -1):
        for sy in (1, -1):
            reg(add_cyl("CP_Post", 0.032, HEAD - SILL + 0.11,
                        (sx * (hx - 0.02), sy * (hy - 0.02), (SILL + HEAD) / 2 + 0.025), mat=m_iron, verts=12))
        for my in (0.29, -0.29):
            reg(add_cyl("CP_MullX", 0.013, zh, (sx * (hx - 0.01), my, zc), mat=m_iron, verts=8))
    for mx in (0.37, -0.37):
        reg(add_cyl("CP_MullY", 0.013, zh, (mx, hy - 0.01, zc), mat=m_iron, verts=8))
    # ---- 登舱门 (-y 面): 门框 (FW_DoorSignal) + 无框玻璃门扇 (上下横档) + 外侧把手 ----
    # 门扇不再另立竖梃: 门梃 + 门扇竖梃会并成一根「双棍」(v2 每面墙 5 根棍的同一个毛病)
    for sx in (1, -1):
        reg(add_cyl("CP_DoorJamb", 0.024, HEAD - SILL, (sx * 0.46, -(hy - 0.01), (SILL + HEAD) / 2),
                    mat=m_signal, verts=10))
    reg(add_box("CP_DoorHead", (0.94, 0.03, 0.03), (0, -(hy - 0.01), HEAD - 0.015), mat=m_signal))
    reg(add_box("CP_DoorRailTop", (0.88, 0.03, 0.03), (0, -(hy - 0.015), HEAD - 0.06), mat=m_iron))
    reg(add_box("CP_DoorRailBot", (0.88, 0.035, 0.09), (0, -(hy - 0.015), SILL + 0.075), mat=m_iron))
    # 把手在离地 0.97..1.27 m: 高于舱内扶手 (0.85), 从舱里看两者不叠成十字
    reg(add_cyl("CP_Handle", 0.013, 0.30, (0.36, -(hy + 0.035), CF + 1.12), mat=m_gold, verts=8))
    for dz in (0.12, -0.12):
        reg(add_cyl("CP_HandleStd", 0.008, 0.05, (0.36, -(hy + 0.012), CF + 1.12 + dz),
                    rot=(pi / 2, 0, 0), mat=m_gold, verts=6))
    # ---- 屋顶: 檐板 + 檐口灯线 + 浅穹顶 + 新月顶饰 ----
    reg(add_box("CP_Eave", (CW + 0.14, CD + 0.14, 0.06), (0, 0, CEIL + 0.07), mat=m_lacquer))
    reg(add_box("CP_EaveLight", (CW + 0.17, CD + 0.17, 0.012), (0, 0, CEIL + 0.034), mat=m_lamp))
    reg(add_half_dome("CP_Dome", (0, 0, CEIL + 0.10), m_lacquer, CW / 2 + 0.02, CD / 2 + 0.02, 0.15))
    # 新月顶饰 x2: 贴在穹顶前后两侧 (y = ±0.42), 与 A 臂错开一个平面 —— 立在正中会被两根臂夹住看不清
    for sy in (1, -1):
        fin_z = CEIL + 0.10 + 0.15 * math.sqrt(1.0 - (0.42 / (CD / 2 + 0.02)) ** 2) + 0.10
        reg(add_crescent("CP_Finial", 0.14, (0, sy * 0.42 + 0.007, fin_z), rot=(pi / 2, 0, 0), mat=m_gold, seg=20))
    # ---- 吊架: 枢轴鼓 (套在轮体横连杆外) + 颈 + A 臂 + 鎏金底板 (落在穹顶面上) ----
    reg(add_cyl("CP_HangerDrum", 0.10, 0.34, (0, 0, 0), rot=(pi / 2, 0, 0), mat=m_iron, verts=16))
    reg(add_cyl("CP_HangerNeck", 0.05, 0.14, (0, 0, -0.07), mat=m_iron, verts=12))
    arm_z = CEIL + 0.10 + 0.15 * math.sqrt(1.0 - (0.62 / (CW / 2 + 0.02)) ** 2)   # 穹顶面在 x = 0.62 处的高度
    for sx in (1, -1):
        reg(cyl_between("CP_HangerArm", (0, 0, -0.12), (sx * 0.62, 0, arm_z + 0.13), 0.038, m_iron, verts=10))
        reg(add_box("CP_HangerPlate", (0.22, 0.16, 0.02), (sx * 0.62, 0, arm_z + 0.012), mat=m_gold))
    # ---- 内饰: 天花 / 顶灯 / 发光盘 / 光槽 / 长椅 / 扶手 ----
    reg(add_box("CP_Ceiling", (CW - 0.02, CD - 0.02, 0.04), (0, 0, CEIL + 0.02), mat=m_ceil))
    reg(add_cyl("CP_CeilGlow", 0.26, 0.010, (0, 0, CEIL - 0.002), mat=m_cabglow, verts=28))
    reg(add_cyl("CP_Downlight", 0.075, 0.012, (0, 0, CEIL - 0.008), mat=m_cablamp, verts=20))
    reg(add_torus("CP_LampRing", 0.11, 0.008, (0, 0, CEIL - 0.010), mat=m_gold, ms=32, ns=6))
    for sy in (1, -1):
        reg(add_box("CP_CoveY", (CW - 0.14, 0.02, 0.035), (0, sy * (hy - 0.07), HEAD - 0.05), mat=m_cove))
    for sx in (1, -1):
        reg(add_box("CP_CoveX", (0.02, CD - 0.14, 0.035), (sx * (hx - 0.07), 0, HEAD - 0.05), mat=m_cove))
    by = hy - 0.26                      # 长椅中心线 (座面 y 0.42 .. 0.86)
    for sx in (1, -1):
        reg(add_box("CP_BenchLeg", (0.06, 0.36, 0.42), (sx * 0.82, by, CF + 0.21), mat=m_iron))
    reg(add_box("CP_BenchSeat", (1.92, 0.44, 0.05), (0, by, CF + 0.445), mat=m_wood))
    reg(add_box("CP_Cushion", (1.88, 0.40, 0.07), (0, by - 0.01, CF + 0.505), mat=m_velvet))
    reg(add_box("CP_BenchBack", (1.92, 0.07, 0.36), (0, hy - 0.065, CF + 0.72), mat=m_velvet))   # 顶 0.90
    reg(cyl_between("CP_GrabRail", (-0.95, -(hy - 0.10), CF + 0.85), (0.95, -(hy - 0.10), CF + 0.85),
                    0.016, m_gold, verts=8))                # 门侧黄铜扶手, 离地 0.85
    for sx in (1, -1):
        reg(cyl_between("CP_GrabStd", (sx * 0.95, -(hy - 0.10), CF + 0.85), (sx * 0.95, -(hy - 0.03), CF + 0.85),
                        0.012, m_gold, verts=6))
    return parts


def join_cabin_proto(parts):
    """按材质合并舱体原型 -> 每种材质一个网格 FW_Cabin_<材质名>, 变换恒等。"""
    for ob in parts:
        apply_xform(ob)
    groups = {}
    for ob in parts:
        groups.setdefault(ob.data.materials[0].name, []).append(ob)
    out = []
    for mat_name, obs in groups.items():
        bpy.ops.object.select_all(action="DESELECT")
        for ob in obs:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = obs[0]
        if len(obs) > 1:
            bpy.ops.object.join()
        ob = bpy.context.view_layer.objects.active
        short = mat_name.replace("FW_", "", 1)
        ob.name = f"FW_Cabin_{short}"
        ob.data.name = f"FW_Cabin_{short}"
        out.append(ob)
    bpy.ops.object.select_all(action="DESELECT")
    print(f"CABIN_PROTO {len(out)} meshes: " + ", ".join(sorted(o.data.name for o in out)))
    return out


cabin_parts = join_cabin_proto(build_cabin_proto())
cabin_roots = []
for i in range(P["cabins"]):
    th = i * 2 * pi / P["cabins"]
    px, pz = R * cos(th), HZ + R * sin(th)
    pivot = add_empty(f"FW_Pivot_{i}", (px, 0, pz))
    parent_keep(pivot, wheel)
    link_col(pivot, col_wheel)

    root = add_empty(f"FW_CabinRoot_{i}", (px, 0, pz))
    parent_keep(root, pivot)
    link_col(root, col_wheel)
    cabin_roots.append((root, th))

    for part in cabin_parts:
        short = part.data.name.replace("FW_Cabin_", "", 1)
        if i == 0:
            ob = part                       # 原型对象就是 0 号舱
            ob.name = f"FW_C0_{short}"
        else:
            # 共用网格数据 + 普通父子 (本地变换恒等): glb 里 16 个节点引用同一个 mesh
            ob = bpy.data.objects.new(f"FW_C{i}_{short}", part.data)
        link_col(ob, col_wheel)
        ob.parent = root

# lights, world, camera ------------------------------------------------------
bpy.ops.object.light_add(type="SUN", location=(25, -30, 55))
sun = bpy.context.active_object
sun.data.energy = 2.2
sun.data.color = hex_lin("#B4C7FF")[:3]
sun.data.angle = radians(6)
look_at(sun, (0, 0, 10))
link_col(sun, col_static)

bpy.ops.object.light_add(type="AREA", location=(0, -12, 18))
fill = bpy.context.active_object
fill.data.energy = 180
fill.data.size = 12
fill.data.color = hex_lin("#FF9A5C")[:3]
look_at(fill, (0, 0, 6))
link_col(fill, col_static)

w = bpy.data.worlds.new("Night")
sc.world = w
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = hex_lin(HEX["night"])
bg.inputs[1].default_value = 0.35

def add_cam(name, loc, target, lens=50):
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.active_object
    cam.name = name
    cam.data.lens = lens
    look_at(cam, target)
    link_col(cam, col_static)
    return cam

cam_front = add_cam("FW_CamFront", (0, -64, 18), (0, 1, 17), lens=34)
# v3 第 2 批: 站台正面 (门楼 / 台阶扶手 / 通道 / 登舱闸) 与 站台面上看登舱闸和停靠舱
cam_station = add_cam("FW_CamStation", (0.9, -27.5, 5.2), (0, 0, 3.0), lens=32)
cam_gate = add_cam("FW_CamGate", (2.3, -7.4, 3.25), (0, -1.6, 2.35), lens=30)
# v3 第 3 批: 站台上仰视雨棚 / 轮毂 (南面上方)
cam_canopy = add_cam("FW_CamCanopy", (3.6, -4.6, 3.2), (0, 0.6, 6.9), lens=20)
cam_hub = add_cam("FW_CamHub", (8.5, -10.5, 24.5), (0, -2.4, 20.41), lens=50)
cam_three = add_cam("FW_CamThree", (46, -52, 27), (0, 0, 16), lens=36)
cam_side  = add_cam("FW_CamSide", (70, -5, 19), (0, 0, 17), lens=35)

# 舱体特写: 找最接近 -30 度角的舱
det_th = radians(-30)
def _ang_diff(a, b):
    return abs(((a - b + pi) % (2 * pi)) - pi)
best = min(range(P["cabins"]), key=lambda i: _ang_diff(cabin_roots[i][1], det_th))
cz = HZ + R * sin(cabin_roots[best][1])
cx = R * cos(cabin_roots[best][1])
cam_det = add_cam("FW_CamDetail", (cx + 4.4, -7.6, cz + 1.8), (cx, 0, cz - 1.35), lens=50)

# 舱内第一人称视角 (验证内饰与走道): 找最接近 -90 度(最低点)的舱, 站姿视线
fp_th = radians(-90)
best_fp = min(range(P["cabins"]), key=lambda i: _ang_diff(cabin_roots[i][1], fp_th))
fpz = HZ + R * sin(cabin_roots[best_fp][1])
fpx = R * cos(cabin_roots[best_fp][1])
cam_fp = add_cam("FW_CamInterior", (fpx - 0.42, 0.30, fpz - 1.05),
                 (fpx + 0.5, -3.0, fpz - 1.35), lens=18)   # v3: 站姿眼高 1.65, 朝登舱门

sc.view_settings.view_transform = "Standard"
sc.view_settings.exposure = 0.15

# bloom (compositor effect, 5.3 API) ----------------------------------------
try:
    sc.use_nodes = True
    eff = sc.compositor_effects.new(name="Bloom")
    with bpy.data.libraries.load(ASSET_BLOOM, link=False) as (src, dst):
        dst.node_groups = [n for n in src.node_groups if "Bloom" == n]
    bloom = bpy.data.node_groups.get("Bloom")
    eff.node_group = bloom
    print("BLOOM_OK")
except Exception as e:
    print("BLOOM_FAIL", type(e).__name__, str(e)[:120])

# (v3: 不烘焙旋转动画 —— 运行时 ferris.js 程序化转轮, 导出时不带动画 / UV)

# 按材质分组合并 (压 draw call; 动画节点 FW_Wheel / FW_CabinRoot_i 不动)
def under_root(ob, root_name):
    """祖先链匹配: 全等或 '前缀_' (FW_CabinRoot 匹配 FW_CabinRoot_0..15)"""
    p = ob.parent
    while p:
        if p.name == root_name or p.name.startswith(root_name + "_"):
            return True
        p = p.parent
    return False

def join_group(pred, prefix):
    # v2.3 修复: 原 groups 字典从未填充, 合并静默跳过, glb 实际 1266 个独立 mesh
    groups = {}
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH" or not pred(ob):
            continue
        mat = ob.data.materials[0].name if ob.data.materials else "NONE"
        groups.setdefault(mat, []).append(ob)
    for mat_name, obs in groups.items():
        # 关键: 每组合并前必须清空选择——join 会吞掉所有已选中对象,
        # 上组合并结果保持选中, 不清空会把别的组滚雪球并进来
        bpy.ops.object.select_all(action="DESELECT")
        # 先逐个应用修改器(倒角), 避免 join 后活动对象的修改器参数
        # 被套用到整组几何上
        for ob in obs:
            ob.select_set(True)
            if ob.modifiers:
                bpy.context.view_layer.objects.active = ob
                try:
                    bpy.ops.object.modifier_apply(modifier=ob.modifiers[0].name)
                except Exception as e:
                    print(f"WARN modifier_apply {ob.name}: {type(e).__name__}")
        bpy.context.view_layer.objects.active = obs[0]
        if len(obs) > 1:
            bpy.ops.object.join()
        obs[0].name = f"{prefix}_{mat_name}"
    print(f"JOIN {prefix}: {len(groups)} groups, {sum(len(v) for v in groups.values())} objs")

bpy.ops.object.select_all(action="DESELECT")
join_group(lambda ob: ob.parent is None, "FW_S")                      # 静组 (站台/支架)
join_group(lambda ob: under_root(ob, "FW_Wheel") and not under_root(ob, "FW_CabinRoot"),
           "FW_W")                                                    # 轮体结构
bpy.ops.object.select_all(action="DESELECT")   # 舱体已是共用网格, 不逐舱合并

# save source (预览渲染仍含地面盘; glb 在预览之后单独导出) -----------------------
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "ferris_wheel.blend"))
print("BLEND_SAVED")

# renders ----------------------------------------------------------------------
def brightness(path):
    try:
        img = bpy.data.images.load(str(path))
        w_, h_ = img.size
        px = np.empty(w_ * h_ * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        a = px.reshape(h_, w_, 4)
        mean = float(a[..., :3].mean())
        bpy.data.images.remove(img)
        return mean
    except Exception as e:
        print("CHECK_ERR", type(e).__name__, str(e)[:80])
        return -1.0

def set_engine_cycles(res, samples):
    sc.render.engine = "CYCLES"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    sc.cycles.device = "CPU"
    sc.render.resolution_x, sc.render.resolution_y = res

def render_still(name, cam):
    sc.camera = cam
    path = PREV / name
    sc.render.image_settings.media_type = "IMAGE"
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = str(path)
    sc.render.resolution_x, sc.render.resolution_y = P["res_still"]
    sc.render.resolution_percentage = 100
    try:
        bpy.ops.render.render(write_still=True)
    except Exception as e:
        print("RENDER_FAIL", name, type(e).__name__, str(e)[:120])
        return False
    mean = brightness(path)
    print("CHECK", name, f"mean={mean:.4f}")
    return mean > 0.008

PREV.mkdir(exist_ok=True)
sc.render.engine = "BLENDER_EEVEE"
try:
    sc.eevee.taa_render_samples = 64
except Exception:
    pass

stills = [("01_front.png", cam_front), ("02_three_quarter.png", cam_three),
          ("03_side.png", cam_side), ("04_cabin_detail.png", cam_det),
          ("05_interior_fp.png", cam_fp), ("06_station.png", cam_station),
          ("07_gate.png", cam_gate), ("08_canopy_under.png", cam_canopy),
          ("09_hub.png", cam_hub)]
ok = True
for name, cam in stills:
    if not render_still(name, cam):
        ok = False

if not ok:
    print("FALLBACK_CYCLES")
    set_engine_cycles((1280, 720), 64)
    for name, cam in stills:
        if not render_still(name, cam):
            print("STILL_FAILED_FINAL", name)

# video (可选, 定稿时开)
if P["render_video"]:
    sc.camera = cam_three
    sc.render.image_settings.media_type = "VIDEO"
    sc.render.image_settings.file_format = "FFMPEG"
    sc.render.filepath = str(PREV / "spin_preview.mp4")
    sc.render.ffmpeg.format = "MPEG4"
    sc.render.ffmpeg.codec = "H264"
    try:
        sc.render.ffmpeg.constant_rate_factor = "HIGH"
        sc.render.ffmpeg.ffmpeg_preset = "GOOD"
        sc.render.ffmpeg.audio_codec = "NONE"
    except Exception:
        pass
    if sc.render.engine == "BLENDER_EEVEE":
        sc.render.resolution_x, sc.render.resolution_y = (1280, 720)
        sc.frame_end = 181
    else:
        sc.render.resolution_x, sc.render.resolution_y = (960, 540)
        sc.cycles.samples = 32
        sc.frame_end = 121
    sc.render.filepath = str(PREV / "spin_preview.mp4")
    try:
        bpy.ops.render.render(animation=True)
        print("VIDEO_OK")
    except Exception as e:
        print("VIDEO_FAIL", type(e).__name__, str(e)[:160])

# export glb -------------------------------------------------------------------
# legacy 地面盘 (r70, 顶面 y=0) 仅服务 blender 预览; app 侧地面由 park_env 提供
# (地坪顶 y=-0.05), 不移除会盖住公园地面 —— 预览渲完再删, 然后导出。
# 注意: 上面的按材质合并会把节点改名为 FW_S_<材质>, 所以按材质名查找而不是节点名
ground = next((o for o in bpy.context.scene.objects
               if o.type == "MESH" and o.data.materials
               and o.data.materials[0].name == "FW_Ground"), None)
if ground:
    print("FW_GROUND_REMOVED", ground.name)
    bpy.data.objects.remove(ground, do_unlink=True)
try:
    bpy.ops.export_scene.gltf(filepath=str(OUT / "ferris_wheel.glb"),
                              export_format="GLB", export_animations=False,
                              export_texcoords=False, export_apply=True)
except (TypeError, RuntimeError) as e:
    print("GLTF_KWARG_FALLBACK", type(e).__name__)
    bpy.ops.export_scene.gltf(filepath=str(OUT / "ferris_wheel.glb"),
                              export_format="GLB")
print("GLB_EXPORTED")

# report ------------------------------------------------------------------------
tris = 0
for ob in bpy.context.scene.objects:
    if ob.type == "MESH":
        me = ob.data
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
print(f"SUMMARY tris={tris} fps={P['fps']} frames={sc.frame_start}-{sc.frame_end}")
print("DONE")
