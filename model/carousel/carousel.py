# -*- coding: utf-8 -*-
"""
Séance Carousel 显灵木马 - Halloween Night (game-ready glTF asset)
Run: blender --background --python carousel.py
All sizes in meters. Modeled at ORIGIN (app 侧由 main.js 摆到 (45, 0, -18)).
Blender Z-up: 入口方位 azimuth 202° = 世界坐标里从 (45,18) 指向园区中心的方向.

降神之夜 The Séance:
  - 大型场地: 平台 R8.0 / 骑乘环 R6.2, 10 位 = 8 马 + 2 座车 (弧间距 ~3.9m)
  - 三灵坐骑: 象牙鎏金木马 (ivory) / 灵火幽灵马 (ghost) / 南瓜稻草马 (pumpkin)
  - 座车: 南瓜马车 (入口位, i0) + 鎏金座车 (对位, i5)
  - 机台: 锥顶帐篷 + 波浪裙边灯串 + 新月星芒顶饰 + 铜杆 + 法阵内环
  - 场地: 铺装星徽 / 断弧地灯环 / 排队围栏 / 入口台阶 / 新月招牌
节点约定 (运行时驱动, 与 ferris.js 同套路):
  CR_Spin    —— 机台旋转总根 (平台/顶棚/骑乘/铜杆随转)
  CR_Ride_i  —— 每骑乘位起伏根 (马 bob, 座车静止; 挂在 CR_Spin 下)
  静态场地不入根 (铺装/围栏/台阶/招牌/地灯)
"""
import bpy
import bmesh
import math
from math import radians, degrees, pi, cos, sin, atan2
from pathlib import Path
import numpy as np
from mathutils import Vector

# ---------------------------------------------------------------- params ---
P = {
    "platform_r": 8.0,       # 平台半径
    "ride_r": 6.2,           # 骑乘环半径 (10 位, 弧间距 ~3.9m)
    "deck_top": 0.62,        # 平台顶面标高 (collider h 由 phase B 手工同步)
    "canopy_z": 5.60,        # 顶棚檐口高
    "roof_r": 9.4,
    "roof_h": 2.75,
    "rides": 10,
    "bob_amp": 0.22,
    "bob_period_s": 3.0,
    "spin_period_s": 18.0,
    "entrance_deg": 202.0,   # 入口方位 (指向园区中心)
    "fps": 30,
    "res_still": (1600, 900),
    "render_video": False,   # 定稿 True
}
E = radians(P["entrance_deg"])
DIR_E = (cos(E), sin(E))                     # 入口方向单位向量 (Blender XY)
RIDE_R = P["ride_r"]
DECK = P["deck_top"]

# 降神之夜色板 (DESIGN.md) × 万圣夜园区色板 (PRODUCT.md)
HEX = {
    "gold":      "#C9A227",
    "gold_br":   "#E3B93E",
    "gold_deep": "#8A6A1F",
    "ivory":     "#EDE3CB",
    "velvet":    "#5A4390",
    "velvet_d":  "#3A2E56",
    "violet":    "#7A4FA8",
    "violet_g":  "#9B5BFF",
    "spirit":    "#8FE3D9",
    "pumpkin":   "#FFA53B",
    "pump_body": "#C97A32",
    "vine":      "#4E7A3A",
    "warm":      "#FFE9C4",
    "metal":     "#3A4152",
    "iron":      "#23273A",
    "wood":      "#4A382A",
    "wood_d":    "#33271D",
    "roof":      "#2A2140",
    "skirt":     "#171226",
    "stone":     "#1B1826",
    "stone_d":   "#16131F",
    "hoof":      "#241C16",
    "eye_red":   "#5A1F1F",
    "night":     "#060913",
    "ground":    "#060911",
}

def hex_lin(h, a=1.0):
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
             coat=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    s = sock(p, "Base Color")
    if s: s.default_value = (*hex_lin(color)[:3], alpha)
    if alpha < 1.0:
        s = sock(p, "Alpha")
        if s: s.default_value = alpha
        try:
            m.blend_method = "BLEND"
            m.surface_render_method = "BLENDED"
        except Exception:
            pass
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

def cyl_between(name, p1, p2, r, mat, verts=8, sm=True):
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

def add_torus(name, R, tube, loc, rot=(0, 0, 0), mat=None, ms=48, ns=8, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=tube,
                                     major_segments=ms, minor_segments=ns,
                                     location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    if mat: ob.data.materials.append(mat)
    smooth(ob)
    return ob

def torus_gap(ob, gap_half_deg, gap_center_deg):
    """水平圆环按局部角度开缺口: 删 [center-half, center+half] 顶点 (入口断弧用)。"""
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

def add_cone(name, r, depth, loc, mat=None, verts=12, rot=(0, 0, 0), r2=0.0, sm=True):
    bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=r2, depth=depth, vertices=verts,
                                    location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    if mat: ob.data.materials.append(mat)
    if sm: smooth(ob)
    return ob

def add_sphere(name, r, loc, mat=None, seg=16, ring=10, scale=(1, 1, 1), rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=seg, ring_count=ring,
                                         location=loc, rotation=rot)
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

def obj_fcurves(ob):
    fcs = []
    ad = ob.animation_data
    if not ad or not ad.action:
        return fcs
    act = ad.action
    try:
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    fcs.extend(cb.fcurves)
    except Exception as e:
        print("WARN fcurve access fallback:", type(e).__name__)
        try:
            fcs.extend(act.fcurves)
        except Exception:
            pass
    return fcs

def ang_diff(a, b):
    return abs(((a - b + pi) % (2 * pi)) - pi)

# ---------------------------------------------------------------- build ----
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = P["fps"]
sc.frame_start = 1
spin_frames = int(P["spin_period_s"] * P["fps"])
sc.frame_end = spin_frames

col_static = bpy.data.collections.new("Static")
col_spin   = bpy.data.collections.new("Spin")
sc.collection.children.link(col_static)
sc.collection.children.link(col_spin)

# materials (CR_ 前缀 = 显灵木马) --------------------------------------------
m_metal    = make_mat("CR_Metal", HEX["metal"], rough=0.45, metal=0.85)
m_gold_br  = make_mat("CR_GoldBright", HEX["gold_br"], rough=0.25, metal=1.0)
m_gold_dp  = make_mat("CR_GoldDeep", HEX["gold_deep"], rough=0.4, metal=0.9)
m_iron     = make_mat("CR_Iron", HEX["iron"], rough=0.55, metal=0.8)
m_wood     = make_mat("CR_Wood", HEX["wood"], rough=0.85)
m_wood_d   = make_mat("CR_WoodDark", HEX["wood_d"], rough=0.85)
m_roof     = make_mat("CR_Roof", HEX["roof"], rough=0.88)
m_skirt    = make_mat("CR_Skirt", HEX["skirt"], rough=0.7, metal=0.2)
m_velvet   = make_mat("CR_Velvet", HEX["velvet"], rough=0.9)
m_velvet_d = make_mat("CR_VelvetDark", HEX["velvet_d"], rough=0.85, metal=0.05)
m_pain_v   = make_mat("CR_PaintViolet", HEX["violet"], rough=0.5)
m_pain_o   = make_mat("CR_PaintOrange", HEX["pumpkin"], rough=0.5)
m_pain_i   = make_mat("CR_PaintIvory", HEX["ivory"], rough=0.5)
m_bulb     = make_mat("CR_WarmBulb", HEX["warm"], rough=0.4, emit=HEX["warm"], strength=2.6)
m_glow_v   = make_mat("CR_GlowViolet", HEX["violet_g"], rough=0.4, emit=HEX["violet_g"], strength=2.2)
m_glow_g   = make_mat("CR_GlowGold", HEX["gold_br"], rough=0.4, emit=HEX["gold_br"], strength=2.2)
m_spirit   = make_mat("CR_GlowSpirit", HEX["spirit"], rough=0.45, emit=HEX["spirit"], strength=1.5)
m_glow_p   = make_mat("CR_GlowPumpkin", HEX["pumpkin"], rough=0.4, emit=HEX["pumpkin"], strength=2.2)
m_blkt_p   = make_mat("CR_BlanketPumpkin", HEX["pumpkin"], rough=0.5, emit=HEX["pumpkin"], strength=1.2)
m_canopy   = make_mat("CR_CanopyGlow", "#FFD9A8", rough=0.5, emit="#FFD9A8", strength=1.2)
m_ghost    = make_mat("CR_GhostBody", HEX["spirit"], rough=0.5, emit=HEX["spirit"],
                      strength=0.1, alpha=0.66)
m_wisp     = make_mat("CR_Wisp", HEX["spirit"], rough=0.45, emit=HEX["spirit"],
                      strength=1.1, alpha=0.5)
m_ivory    = make_mat("CR_IvoryBody", HEX["ivory"], rough=0.42, coat=0.35)
m_gmane    = make_mat("CR_GoldMane", HEX["gold_br"], rough=0.35, metal=0.6,
                      emit=HEX["gold_br"], strength=0.9)
m_hoof     = make_mat("CR_Hoof", HEX["hoof"], rough=0.6)
m_eye_r    = make_mat("CR_EyeDark", HEX["eye_red"], rough=0.3)
m_eye_w    = make_mat("CR_EyeWarm", "#FFD9A0", rough=0.3, emit="#FFD9A0", strength=2.2)
m_pump     = make_mat("CR_PumpBody", HEX["pump_body"], rough=0.55)
m_vine     = make_mat("CR_Vine", HEX["vine"], rough=0.7)
m_pump_e   = make_mat("CR_PumpkinEmit", "#FF9A3B", rough=0.45, emit="#FF9A3B", strength=1.2)
m_stone    = make_mat("CR_Stone", HEX["stone"], rough=0.9)
m_stone_d  = make_mat("CR_StoneDark", HEX["stone_d"], rough=0.92)
m_inlay    = make_mat("CR_InlayGold", HEX["gold"], rough=0.4, metal=0.6,
                      emit=HEX["gold"], strength=1.0)

# ================================ 静态场地 ==================================
# 预览地面盘 (导出前移除, app 侧地面由 park_env 提供)
m_ground = make_mat("CR_GroundPreview", HEX["ground"], rough=0.95)
add_cyl("CR_GroundPreview", 42, 0.1, (0, 0, -0.05), mat=m_ground, verts=48)

# 铺装 (venue pavement, 属于设施的一部分)
add_cyl("CR_Pave", 12.6, 0.16, (0, 0, -0.04), mat=m_stone_d, verts=64)
# 入口星徽: 法阵环 + 八向星芒 (断弧走廊内)
sx, sy = 9.6 * DIR_E[0], 9.6 * DIR_E[1]
add_torus("CR_StarRing", 0.85, 0.018, (sx, sy, 0.045), mat=m_inlay, ms=48, ns=6)
for k in range(8):
    a = k * pi / 4 + pi / 8
    add_box(f"CR_StarSpoke{k}", (0.62, 0.05, 0.018),
            (sx + 0.62 * cos(a), sy + 0.62 * sin(a), 0.045),
            rot=(0, 0, a), mat=m_inlay)

# 入口台阶 (三级: 0.155/0.31/0.465, 顶接平台 0.62, 面向入口方位)
for k, (rr, h) in enumerate(((8.33, 0.465), (9.0, 0.31), (9.67, 0.155))):
    add_box(f"CR_Step{k}", (0.67, 2.8, h), (rr * DIR_E[0], rr * DIR_E[1], h / 2),
            rot=(0, 0, E), mat=m_stone)
# 台阶扶手: 每侧两柱一杆
for sgn in (-1, 1):
    a1 = E + sgn * radians(11)
    for rr, base_z in ((8.25, 0.465), (9.75, 0.155)):
        px, py = rr * cos(a1), rr * sin(a1)
        add_cyl(f"CR_StepPost{sgn}_{rr}", 0.04, 0.62, (px, py, base_z + 0.31),
                mat=m_gold_dp, verts=8)
        add_sphere(f"CR_StepPostTop{sgn}_{rr}", 0.06, (px, py, base_z + 0.65),
                   mat=m_bulb, seg=10, ring=6)
    p1 = (8.25 * cos(a1), 8.25 * sin(a1), 0.465 + 0.62)
    p2 = (9.75 * cos(a1), 9.75 * sin(a1), 0.155 + 0.62)
    cyl_between(f"CR_StepRail{sgn}", p1, p2, 0.035, m_wood_d, verts=8)

# 排队围栏 r10.7: 立柱 12° 一根, 入口 ±15° 断开; 双层横杆 torus_gap ±14°
FR = 10.7
for k in range(30):
    th = k * pi / 15
    if ang_diff(th, E) < radians(15):
        continue
    px, py = FR * cos(th), FR * sin(th)
    add_cyl(f"CR_FencePost{k}", 0.04, 0.92, (px, py, 0.46), mat=m_gold_dp, verts=8)
    add_sphere(f"CR_FenceTop{k}", 0.065, (px, py, 0.96), mat=m_bulb, seg=10, ring=6)
torus_gap(add_torus("CR_FenceRail1", FR, 0.028, (0, 0, 0.55), mat=m_wood_d, ms=64, ns=6),
          14, degrees(E))
torus_gap(add_torus("CR_FenceRail2", FR, 0.028, (0, 0, 0.80), mat=m_wood_d, ms=64, ns=6),
          14, degrees(E))

# 断弧地灯环
torus_gap(add_torus("CR_GroundRing", 11.9, 0.05, (0, 0, 0.05), mat=m_bulb, ms=72, ns=6),
          18, degrees(E))

# 入口新月招牌: 双柱 + 小型绒面板 (深底鎏金新月徽, 不再整板发光)
for sgn in (-1, 1):
    a = E + sgn * radians(12)
    px, py = 12.4 * cos(a), 12.4 * sin(a)
    add_cyl(f"CR_SignPost{sgn}", 0.06, 2.8, (px, py, 1.4), mat=m_gold_dp, verts=10)
    add_sphere(f"CR_SignPostTop{sgn}", 0.08, (px, py, 2.84), mat=m_bulb, seg=10, ring=6)
bx, by = 12.4 * DIR_E[0], 12.4 * DIR_E[1]
add_box("CR_SignBoard", (0.10, 2.2, 0.62), (bx, by, 2.55), rot=(0, 0, E), mat=m_velvet_d)
add_box("CR_SignTrimT", (0.11, 2.2, 0.035), (bx, by, 2.84), rot=(0, 0, E), mat=m_glow_g)
add_box("CR_SignTrimB", (0.11, 2.2, 0.035), (bx, by, 2.26), rot=(0, 0, E), mat=m_glow_g)
add_torus("CR_SignMoon", 0.16, 0.045, (bx + 0.07 * DIR_E[0], by + 0.07 * DIR_E[1], 2.64),
          rot=(radians(90), 0, E + pi / 2), mat=m_glow_g, ms=32, ns=6)
torus_gap(bpy.data.objects["CR_SignMoon"], 70, 90)   # 开口朝上
add_sphere("CR_SignStar", 0.055, (bx + 0.07 * DIR_E[0], by + 0.07 * DIR_E[1], 2.86),
           mat=m_bulb, seg=10, ring=6, scale=(0.45, 0.45, 1.3))
for k in range(5):
    add_sphere(f"CR_SignDot{k}", 0.025,
               (bx + 0.07 * DIR_E[0] + (k - 2) * 0.16 * -sin(E),
                by + 0.07 * DIR_E[1] + (k - 2) * 0.16 * cos(E), 2.40),
               mat=m_pain_i, seg=8, ring=5)

# ================================ 机台 CR_Spin ==============================
spin = add_empty("CR_Spin", (0, 0, 0))
link_col(spin, col_spin)

def S(ob):
    ob.parent = spin   # 直接挂根: 子物体 location 即 spin 本地坐标 (spin 在原点无旋转)
    return ob

# 平台甲板 + 木纹内环 + 鎏金唇缘
S(add_cyl("CR_Deck", P["platform_r"], 0.18, (0, 0, DECK - 0.09), mat=m_wood, verts=64))
S(add_cyl("CR_DeckRingA", 5.55, 0.02, (0, 0, DECK + 0.005), mat=m_wood_d, verts=56))
S(add_cyl("CR_DeckRingB", 3.1, 0.02, (0, 0, DECK + 0.012), mat=m_wood, verts=48))
S(add_torus("CR_DeckRim", 7.95, 0.055, (0, 0, DECK), mat=m_gold_br, ms=64, ns=8))
# 裙板 + 裙顶暖光灯带
S(add_cone("CR_Skirt", 7.15, 0.44, (0, 0, 0.22), mat=m_skirt, verts=64, r2=7.92))
S(add_torus("CR_SkirtGlow", 7.9, 0.04, (0, 0, 0.445), mat=m_bulb, ms=72, ns=6))
# 甲板法阵: 内环金线 + 十方位金点
S(add_torus("CR_DeckCircle", 4.3, 0.025, (0, 0, DECK + 0.012), mat=m_inlay, ms=56, ns=6))
for i in range(P["rides"]):
    th = E + i * 2 * pi / P["rides"]
    S(add_sphere(f"CR_DeckDot{i}", 0.06, (5.6 * cos(th), 5.6 * sin(th), DECK + 0.01),
                 mat=m_glow_g, seg=8, ring=6))

# 中柱: 柱芯 + 竖肋 + 金箍 + 幽紫灵光带 + 柱头
S(add_cyl("CR_Column", 0.5, 5.0, (0, 0, DECK + 2.5), mat=m_velvet_d, verts=24))
for k in range(10):
    th = k * 2 * pi / 10 + 0.31
    S(add_box(f"CR_ColRib{k}", (0.07, 0.05, 4.9),
              (0.52 * cos(th), 0.52 * sin(th), DECK + 2.45), rot=(0, 0, th), mat=m_gold_dp))
for z in (1.3, 2.6, 3.9):
    S(add_torus(f"CR_ColBand{z}", 0.56, 0.05, (0, 0, z), mat=m_gold_br, ms=32, ns=6))
S(add_cyl("CR_ColGlow", 0.53, 0.22, (0, 0, 4.6), mat=m_glow_v, verts=24))
S(add_cyl("CR_ColCapital", 0.78, 0.3, (0, 0, P["canopy_z"] - 0.05), mat=m_gold_dp, verts=24))

# 顶棚: 锥顶帐篷 + 12 鎏金肋 + 檐口金环
roof_z = P["canopy_z"] + P["roof_h"] / 2
S(add_cone("CR_Roof", P["roof_r"], P["roof_h"], (0, 0, roof_z), mat=m_roof, verts=48))
# 顶棚下暖光天花盘 (asset 自发光, 运行时靠 Bloom 提亮机台内部)
S(add_cyl("CR_CanopyGlow", 7.2, 0.05, (0, 0, P["canopy_z"] - 0.06), mat=m_canopy, verts=64))
for k in range(12):
    th = k * pi / 6 + 0.26
    S(cyl_between(f"CR_RoofRib{k}",
                  (0.85 * cos(th), 0.85 * sin(th), roof_z + P["roof_h"] / 2 - 0.25),
                  (9.28 * cos(th), 9.28 * sin(th), P["canopy_z"] + 0.10),
                  0.055, m_gold_dp, verts=6))
S(add_torus("CR_RoofRim", 9.35, 0.07, (0, 0, P["canopy_z"] + 0.06), mat=m_gold_br, ms=72, ns=8))

# 波浪裙边: 36 瓣交叠 (紫/橙/象牙轮换) + 裙沿金杆 + 瓣间暖光灯珠
NS = 36
for k in range(NS):
    th = k * 2 * pi / NS
    mat = (m_pain_v, m_pain_o, m_pain_i)[k % 3]
    S(add_sphere(f"CR_Scallop{k}", 1.0, (9.15 * cos(th), 9.15 * sin(th), P["canopy_z"] - 0.36),
                 mat=mat, seg=14, ring=8, scale=(0.155, 0.85, 0.42), rot=(0, 0, th)))
S(add_torus("CR_ScallopRod", 9.15, 0.02, (0, 0, P["canopy_z"] - 0.02), mat=m_gold_br, ms=64, ns=6))
for k in range(NS):
    th = k * 2 * pi / NS
    S(add_sphere(f"CR_ValanceBulb{k}", 0.075, (9.15 * cos(th), 9.15 * sin(th), P["canopy_z"] - 0.86),
                 mat=m_bulb, seg=10, ring=6))

# 新月星芒顶饰: 竖直新月 (开口朝入口, 大开度读出 C 形) + 挑杆 + 开口处星 + 环绕灵珠
apz = roof_z + P["roof_h"] / 2 + 0.46
S(cyl_between("CR_FinialRod", (0, 0, roof_z + P["roof_h"] / 2 - 0.1), (0, 0, apz - 0.2),
              0.05, m_gold_dp, verts=8))
moon = add_torus("CR_FinialMoon", 0.58, 0.12, (0, 0, apz), rot=(radians(90), 0, E + pi / 2),
                 mat=m_glow_g, ms=40, ns=8)
torus_gap(moon, 70, 90)   # 开口朝上: 入口视角读到角朝上的经典月牙
S(add_sphere("CR_FinialStar", 0.11, (0, 0, apz + 0.40),
             mat=m_bulb, seg=10, ring=6, scale=(0.5, 0.5, 1.35)))
for k in range(3):
    th = E + (k - 1) * radians(50)
    S(add_sphere(f"CR_FinialOrb{k}", 0.055, (0.95 * cos(th), 0.95 * sin(th), apz - 0.3),
                 mat=m_spirit, seg=8, ring=6))

# 铜杆: 10 根 (甲板套管 -> 顶棚), 杆顶固定环
for i in range(P["rides"]):
    th = E + i * 2 * pi / P["rides"]
    px, py = RIDE_R * cos(th), RIDE_R * sin(th)
    S(add_cyl(f"CR_Pole{i}", 0.055, 4.75, (px, py, DECK + 2.5), mat=m_gold_br, verts=10))
    S(add_cyl(f"CR_PoleCap{i}", 0.1, 0.12, (px, py, P["canopy_z"] - 0.04), mat=m_gold_dp, verts=10))

# ================================ 骑乘位 ====================================
def child(root, ob):
    ob.parent = root   # 无补偿挂父: ob.location 即 root 本地坐标
    return ob

# ---------------- 马体: 放样建模 (解剖写实) ----------------
def loft(name, pts, rad, mat, seg=12, smooth_sh=True):
    """沿 3D 折线放样变截面椭圆管. pts: [(x,y,z)], rad: [(rx, rz)...] 与 pts 等长.
    侧向轴恒为 +Y, 环面⊥切向, 端面封口 — 用于马躯干(口鼻->头->颈->背->臀)与腿."""
    bm = bmesh.new()
    P = [Vector(p) for p in pts]
    n = len(P)
    rings = []
    for i in range(n):
        if i == 0:
            t = P[1] - P[0]
        elif i == n - 1:
            t = P[-1] - P[-2]
        else:
            t = P[i + 1] - P[i - 1]
        t.normalize()
        up = t.cross(Vector((0, 1, 0)))
        if up.length < 1e-5:
            up = Vector((0, 0, 1))
        up.normalize()
        rx, rz = rad[i]
        ring = []
        for k in range(seg):
            a = 2 * pi * k / seg
            ring.append(bm.verts.new(
                P[i] + Vector((0, rx * cos(a), 0)) + up * (rz * sin(a))))
        rings.append(ring)
    for i in range(n - 1):
        for k in range(seg):
            k2 = (k + 1) % seg
            bm.faces.new((rings[i][k], rings[i][k2],
                          rings[i + 1][k2], rings[i + 1][k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    if mat:
        me.materials.append(mat)
    if smooth_sh:
        for poly in me.polygons:
            poly.use_smooth = True
    return ob

def _refine(chain, per=3):
    """关节链细分: 每段插 per 个中间环 (位置线性, 半径 smoothstep) -> 平滑弯腿."""
    out = [chain[0]]
    for i in range(len(chain) - 1):
        a, b = chain[i], chain[i + 1]
        last = (i == len(chain) - 2)
        for j in range(1, per + 1):
            if last and j == per:
                continue
            t = j / per
            e = t * t * (3 - 2 * t)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t,
                        a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * e))
    return out

# 躯干轮廓: 口鼻 -> 头 -> 颈 -> 鬐甲 -> 背胸腹 -> 臀 -> 尾根 (x, z_center, 侧向rx, 垂直rz)
BODY = [
    (1.74, 1.86, 0.050, 0.060),   # 口鼻端
    (1.67, 1.87, 0.066, 0.076),   # 鼻孔
    (1.58, 1.89, 0.086, 0.096),   # 口鼻
    (1.50, 1.91, 0.110, 0.120),   # 颊
    (1.42, 1.93, 0.130, 0.146),   # 眶后/颌
    (1.34, 1.95, 0.124, 0.140),   # 颅
    (1.25, 1.94, 0.104, 0.116),   # 枕
    (1.15, 1.89, 0.085, 0.112),   # 喉
    (1.04, 1.79, 0.110, 0.156),   # 颈下段
    (0.92, 1.62, 0.150, 0.200),   # 颈中
    (0.78, 1.40, 0.186, 0.240),   # 颈基
    (0.61, 1.18, 0.230, 0.260),   # 鬐甲
    (0.41, 1.05, 0.266, 0.288),   # 肩
    (0.19, 0.98, 0.284, 0.303),   # 前胸
    (-0.05, 0.95, 0.290, 0.310),  # 胸腹最深
    (-0.29, 0.97, 0.284, 0.303),  # 腹
    (-0.51, 1.01, 0.270, 0.298),  # 后腹
    (-0.67, 1.08, 0.248, 0.296),  # 胁
    (-0.81, 1.15, 0.220, 0.293),  # 髋结节
    (-0.91, 1.21, 0.173, 0.283),  # 臀
    (-0.97, 1.26, 0.108, 0.213),  # 尾根
]

# 支撑腿 (前后各一, 左侧 +y; 右侧镜像 y): 肩/髋 -> 肘/股 -> 膝/飞节 -> 系 -> 蹄基
LEG_F_SUP = [(0.34, 0.20, 0.88, 0.115), (0.40, 0.22, 0.66, 0.095),
             (0.46, 0.22, 0.48, 0.062), (0.48, 0.22, 0.36, 0.050),
             (0.48, 0.22, 0.32, 0.044)]
LEG_H_SUP = [(-0.58, 0.20, 0.92, 0.150), (-0.62, 0.22, 0.72, 0.115),
             (-0.72, 0.23, 0.50, 0.075), (-0.82, 0.23, 0.36, 0.052),
             (-0.82, 0.23, 0.31, 0.046)]

def _mir(chain):
    return [(x, -y, z, r) for (x, y, z, r) in chain]

# 四套姿态 (关键: 最低蹄基 z>=0.31, bob 最低点仍不触甲板)
POSES = [
    # P0 扬蹄: 左前高举折收, 右前支撑, 左后支撑, 右后后蹬
    {
        "FL": [(0.34, 0.20, 0.88, 0.115), (0.48, 0.24, 0.72, 0.095),
               (0.60, 0.26, 0.60, 0.062), (0.50, 0.26, 0.54, 0.050),
               (0.44, 0.26, 0.54, 0.044)],
        "FR": _mir(LEG_F_SUP),
        "HL": LEG_H_SUP,
        "HR": [(-0.58, -0.20, 0.92, 0.150), (-0.70, -0.22, 0.74, 0.115),
               (-0.88, -0.23, 0.54, 0.075), (-1.04, -0.24, 0.38, 0.052),
               (-1.04, -0.24, 0.33, 0.046)],
    },
    # P1 奔驰: 双前探伸, 双后蹬展
    {
        "FL": [(0.34, 0.20, 0.88, 0.115), (0.54, 0.23, 0.74, 0.095),
               (0.72, 0.24, 0.60, 0.062), (0.86, 0.25, 0.44, 0.050),
               (0.86, 0.25, 0.38, 0.044)],
        "FR": [(0.34, -0.20, 0.88, 0.115), (0.54, -0.23, 0.74, 0.095),
               (0.72, -0.24, 0.60, 0.062), (0.86, -0.25, 0.44, 0.050),
               (0.86, -0.25, 0.38, 0.044)],
        "HL": [(-0.58, 0.20, 0.92, 0.150), (-0.72, 0.22, 0.76, 0.115),
               (-0.92, 0.23, 0.58, 0.075), (-1.10, 0.24, 0.42, 0.052),
               (-1.10, 0.24, 0.36, 0.046)],
        "HR": [(-0.58, -0.20, 0.92, 0.150), (-0.72, -0.22, 0.76, 0.115),
               (-0.92, -0.23, 0.58, 0.075), (-1.10, -0.24, 0.42, 0.052),
               (-1.10, -0.24, 0.36, 0.046)],
    },
    # P2 飞跃: 双前收拢于胸下, 左后大展, 右后低拂
    {
        "FL": [(0.34, 0.20, 0.88, 0.115), (0.46, 0.24, 0.74, 0.095),
               (0.52, 0.26, 0.62, 0.062), (0.42, 0.26, 0.56, 0.050),
               (0.36, 0.26, 0.56, 0.044)],
        "FR": [(0.34, -0.20, 0.88, 0.115), (0.46, -0.24, 0.74, 0.095),
               (0.52, -0.26, 0.62, 0.062), (0.42, -0.26, 0.56, 0.050),
               (0.36, -0.26, 0.56, 0.044)],
        "HL": [(-0.58, 0.20, 0.92, 0.150), (-0.76, 0.24, 0.76, 0.115),
               (-0.98, 0.26, 0.56, 0.075), (-1.18, 0.27, 0.40, 0.052),
               (-1.18, 0.27, 0.35, 0.046)],
        "HR": [(-0.58, -0.20, 0.92, 0.150), (-0.74, -0.22, 0.72, 0.115),
               (-0.96, -0.23, 0.50, 0.075), (-1.20, -0.24, 0.36, 0.052),
               (-1.20, -0.24, 0.32, 0.046)],
    },
    # P3 行进: 左前半抬, 其余支撑, 右后轻蹬
    {
        "FL": [(0.34, 0.20, 0.88, 0.115), (0.46, 0.23, 0.70, 0.095),
               (0.54, 0.24, 0.56, 0.062), (0.56, 0.24, 0.44, 0.050),
               (0.56, 0.24, 0.40, 0.044)],
        "FR": _mir(LEG_F_SUP),
        "HL": LEG_H_SUP,
        "HR": [(-0.58, -0.20, 0.92, 0.150), (-0.68, -0.22, 0.72, 0.115),
               (-0.84, -0.23, 0.50, 0.075), (-0.98, -0.24, 0.36, 0.052),
               (-0.98, -0.24, 0.32, 0.046)],
    },
]

# 鬃嵴曲线: 枕部 -> 鬐甲 (古典雕花波浪: 沿曲线的扁长叶片, 随切向倾斜+波浪前倾)
CREST_P, CREST_Q = (1.28, 2.03), (0.62, 1.45)

def build_leg(root, tag, chain, mat, hoof_mat, ghost):
    ref = _refine(chain)
    pts = [(p[0], p[1], p[2]) for p in ref]
    rad = [(p[3], p[3]) for p in ref]
    child(root, loft(f"{tag}Leg", pts, rad, mat, seg=10))
    ex, ey, ez, er = chain[-1]
    if ghost:   # 幽灵马: 系部以下化作垂焰
        child(root, add_cone(f"{tag}Wisp", er * 1.15, 0.30, (ex, ey, ez - 0.12),
                             mat=m_wisp, verts=8, rot=(pi, 0, 0)))
    else:
        child(root, add_cone(f"{tag}Hoof", 0.052, 0.095, (ex, ey, ez - 0.05),
                             mat=hoof_mat, verts=10, r2=er * 1.05))

def horse(root, style, pose_idx):
    """解剖写实木马: 放样躯干+颈+头一体, 四关节渐变腿, 雕花波浪鬃, 华丽鞍具.
    本地 +X = 行进方向, z=0 为平台面; 体尺: 鬐甲高 ~1.44, 鼻尖->尾梢 ~3.0."""
    if style == "ghost":
        m_body, m_man, m_eye = m_ghost, m_spirit, m_spirit
        m_blkt, m_seat, leg_hoof = m_gold_br, m_gold_br, None
    elif style == "pumpkin":
        m_body, m_man, m_eye = m_pump, m_vine, m_eye_w
        m_blkt, m_seat, leg_hoof = m_blkt_p, m_wood_d, m_hoof
    else:  # ivory
        m_body, m_man, m_eye = m_ivory, m_gmane, m_eye_r
        m_blkt, m_seat, leg_hoof = m_velvet, m_gold_br, m_hoof

    # 躯干+颈+头 一体放样
    child(root, loft("HBody", [(x, 0, z) for (x, z, _, _) in BODY],
                     [(rx, rz) for (_, _, rx, rz) in BODY], m_body, seg=12))
    # 眼 / 鼻孔 / 耳
    for sgn in (-1, 1):
        child(root, add_sphere(f"HEye{sgn}", 0.042, (1.46, sgn * 0.128, 1.97), m_eye,
                               seg=10, ring=8))
        child(root, add_sphere(f"HNostril{sgn}", 0.016, (1.70, sgn * 0.052, 1.885),
                               m_hoof, seg=8, ring=6))
        child(root, add_cone(f"HEar{sgn}", 0.048, 0.20, (1.32, sgn * 0.075, 2.08),
                             m_body, verts=8, rot=(sgn * radians(9), radians(-14), 0)))
    # 古典雕花波浪鬃: 沿颈嵴 9 叶扁长球, 随切向倾斜 + 正弦波浪
    cdx, cdz = CREST_Q[0] - CREST_P[0], CREST_Q[1] - CREST_P[1]
    for t_i in range(9):
        tt = t_i / 8
        bx = CREST_P[0] + cdx * tt
        bz = CREST_P[1] + cdz * tt + 0.04 * sin(tt * pi)   # 嵴线弓度
        wv = sin(tt * 3 * pi)
        phi = atan2(cdx, cdz) + 0.22 * wv                  # 叶片顺颈向 + 波浪前倾
        child(root, add_sphere(f"HMane{t_i}", 0.13 - 0.02 * abs(wv),
                               (bx + 0.04 * wv, 0, bz + 0.02), m_man,
                               seg=10, ring=8, scale=(0.95, 0.42, 1.6),
                               rot=(0, phi, 0)))
    # 额前刘海 (覆额三叶)
    for k, (fx, fz, fr) in enumerate(((1.36, 2.02, 0.10), (1.31, 1.96, 0.085),
                                      (1.27, 1.90, 0.07))):
        child(root, add_sphere(f"HForelock{k}", fr, (fx, 0, fz), m_man,
                               seg=10, ring=8, scale=(0.85, 0.40, 1.15)))
    if style == "pumpkin":   # 鬃间小南瓜
        for t_i in (2, 4, 6):
            tt = t_i / 8
            child(root, add_sphere(f"HPump{t_i}", 0.06,
                                   (CREST_P[0] + cdx * tt - 0.05,
                                    0, CREST_P[1] + cdz * tt + 0.10),
                                   m_pump_e, seg=10, ring=8))
    # 尾: S 形细锥束放样 + 发梢团
    TAIL = [(-0.95, 1.29, 0.075), (-1.10, 1.10, 0.062), (-1.24, 0.88, 0.048),
            (-1.34, 0.66, 0.034), (-1.40, 0.50, 0.022)]
    child(root, loft("HTail", [(x, 0, z) for (x, z, _) in TAIL],
                     [(r, r * 0.9) for (_, _, r) in TAIL], m_man, seg=10))
    child(root, add_sphere("HTailTip", 0.062, (-1.42, 0, 0.47), m_man, seg=10, ring=8,
                           scale=(1.3, 0.55, 0.9)))
    # 四腿 (姿态表轮换)
    pose = POSES[pose_idx % len(POSES)]
    ghost = (style == "ghost")
    for tag in ("FL", "FR", "HL", "HR"):
        build_leg(root, f"H{tag}", pose[tag], m_body, leg_hoof, ghost)
    # 华丽鞍具: 鞍毯+金缘+流苏 / 座 / 前桥 / 后桥 / 肚带 / 胸带 / 尾带
    child(root, add_bevel_box("HBlanket", (0.60, 0.74, 0.055), (0.02, 0, 1.30),
                              mat=m_blkt, width=0.02))
    child(root, add_box("HBlanketTrim", (0.63, 0.77, 0.02), (0.02, 0, 1.285), mat=m_gold_dp))
    for k, (tx, ty) in enumerate(((0.30, 0.34), (0.30, -0.34), (-0.26, 0.34),
                                  (-0.26, -0.34), (0.30, 0))):
        child(root, add_cone(f"HTassel{k}", 0.028, 0.09, (0.02 + tx, ty, 1.23),
                             mat=m_gold_dp, verts=6, rot=(pi, 0, 0)))
    child(root, add_sphere("HSeat", 0.24, (0.06, 0, 1.40), m_seat, seg=14, ring=10,
                           scale=(1.15, 1.05, 0.45)))
    child(root, add_sphere("HPommel", 0.08, (0.26, 0, 1.53), m_seat, seg=10, ring=8))
    child(root, add_bevel_box("HCantle", (0.08, 0.30, 0.11), (-0.17, 0, 1.47),
                              mat=m_seat, width=0.03))
    child(root, add_torus("HGirth", 0.40, 0.024, (0.05, 0, 0.95),
                          rot=(0, radians(90), 0), mat=m_gold_dp, ms=24, ns=5))
    for sgn in (-1, 1):   # 胸带: 鬐甲两侧 -> 前胸肚带
        child(root, cyl_between(f"HBreast{sgn}", (0.48, sgn * 0.10, 1.24),
                                (0.32, sgn * 0.12, 0.86), 0.02, m_gold_dp, verts=6))
        child(root, add_sphere(f"HBreastRos{sgn}", 0.035, (0.48, sgn * 0.10, 1.24),
                               m_gold_br, seg=8, ring=6))
    child(root, add_torus("HCrupper", 0.115, 0.016, (-0.93, 0, 1.28),
                          rot=(0, radians(80), 0), mat=m_gold_dp, ms=20, ns=5))
    # 缰辔: 眉带 + 鼻带 + 颊带 + 双缰至前桥
    child(root, add_torus("HBrowband", 0.10, 0.015, (1.29, 0, 1.99),
                          rot=(0, radians(90), 0), mat=m_gold_dp, ms=20, ns=5))
    child(root, add_torus("HNoseband", 0.10, 0.015, (1.58, 0, 1.90),
                          rot=(0, radians(90), 0), mat=m_gold_dp, ms=20, ns=5))
    for sgn in (-1, 1):
        child(root, cyl_between(f"HCheek{sgn}", (1.29, sgn * 0.095, 1.99),
                                (1.58, sgn * 0.09, 1.88), 0.014, m_gold_dp, verts=6))
        child(root, cyl_between(f"HRein{sgn}", (1.58, sgn * 0.10, 1.86),
                                (0.28, sgn * 0.09, 1.52), 0.014, m_gold_dp, verts=6))

def pumpkin_carriage(root):
    """南瓜马车: 南瓜壳座斗 + 金肋 + 藤蔓卷须 + 内悬灯, 本地 +X = 行进方向."""
    child(root, add_sphere("PCShell", 0.95, (0, 0, 0.34), m_pain_o, seg=24, ring=16,
                           scale=(0.92, 0.60, 0.72)))
    for k in range(9):
        a = -pi / 2 + k * pi / 8
        child(root, add_box(f"PCRib{k}", (0.035, 0.035, 0.58),
                            (0.80 * cos(a), 0.52 * sin(a), 0.62), rot=(0, 0, a),
                            mat=m_gold_dp))
    child(root, add_torus("PCRim", 0.66, 0.045, (0, 0, 0.92), mat=m_gold_br,
                          ms=32, ns=6, scale=(1.32, 0.78, 1)))
    child(root, cyl_between("PCStemA", (0.92, 0, 0.92), (1.05, 0, 1.08), 0.05, m_vine, verts=8))
    child(root, cyl_between("PCStemB", (1.05, 0, 1.08), (0.98, 0, 1.22), 0.04, m_vine, verts=8))
    child(root, add_sphere("PCStemTip", 0.07, (0.97, 0, 1.24), m_vine, seg=10, ring=8))
    child(root, add_box("PCSeat", (1.30, 0.55, 0.14), (0.05, 0, 0.55), mat=m_velvet))
    child(root, add_box("PCBack", (0.12, 0.55, 0.55), (-0.52, 0, 0.80), mat=m_velvet))
    child(root, add_cyl("PCLanternRod", 0.018, 0.24, (0, 0, 1.02), mat=m_gold_dp, verts=6))
    child(root, add_sphere("PCLantern", 0.09, (0, 0, 0.86), m_bulb, seg=10, ring=8))

def gilded_carriage(root):
    """鎏金座车: 绒面座斗 + 鎏金框角 + 象牙腰线 + 卷草饰 + 顶灯, 本地 +X = 行进方向."""
    child(root, add_bevel_box("GCTub", (1.75, 1.10, 0.72), (0, 0, 0.36), mat=m_velvet_d,
                              width=0.045))
    for sgn in (-1, 1):
        child(root, add_box(f"GCRimX{sgn}", (1.79, 0.07, 0.07), (0, sgn * 0.535, 0.72),
                            mat=m_gold_br))
        child(root, add_box(f"GCRimY{sgn}", (0.07, 1.14, 0.07), (sgn * 0.875, 0, 0.72),
                            mat=m_gold_br))
        child(root, add_sphere(f"GCCorner{sgn}A", 0.075, (sgn * 0.875, 0.535, 0.72),
                               m_gold_br, seg=10, ring=8))
        child(root, add_sphere(f"GCCorner{sgn}B", 0.075, (sgn * 0.875, -0.535, 0.72),
                               m_gold_br, seg=10, ring=8))
    child(root, add_box("GCTrim", (1.77, 1.12, 0.05), (0, 0, 0.58), mat=m_pain_i))
    for sgn in (-1, 1):
        for lx in (-0.30, 0.30):
            child(root, add_sphere(f"GCScroll{sgn}_{lx}", 0.10, (lx, sgn * 0.56, 0.40),
                                   m_gold_dp, seg=10, ring=8, scale=(1.3, 0.5, 1.0)))
    child(root, add_box("GCSeat", (1.30, 0.50, 0.16), (0.15, 0, 0.50), mat=m_velvet))
    child(root, add_box("GCBack", (0.14, 0.55, 0.62), (-0.52, 0, 0.62), mat=m_velvet))
    child(root, add_cyl("GCLampRod", 0.018, 0.26, (0, 0, 0.85), mat=m_gold_dp, verts=6))
    child(root, add_sphere("GCLamp", 0.08, (0, 0, 0.94), m_bulb, seg=10, ring=8))

STYLE = {1: "ghost", 2: "ivory", 3: "pumpkin", 4: "ghost",
         6: "ivory", 7: "pumpkin", 8: "ghost", 9: "ivory"}
POSE_IDX = {1: 0, 2: 1, 3: 2, 4: 3, 6: 1, 7: 2, 8: 3, 9: 0}   # 相邻位姿态不同
ride_roots = []
bob_idx = []
for i in range(P["rides"]):
    th = E + i * 2 * pi / P["rides"]
    root = add_empty(f"CR_Ride_{i}", (RIDE_R * cos(th), RIDE_R * sin(th), DECK))
    root.rotation_euler = (0, 0, th + pi / 2)   # 本地 +X = 行进切向
    link_col(root, col_spin)
    child(spin, root)
    ride_roots.append(root)
    if i in (0, 5):
        if i == 0:
            pumpkin_carriage(root)
        else:
            gilded_carriage(root)
    else:
        horse(root, STYLE[i], POSE_IDX[i])
        bob_idx.append(i)

# lights, world, camera ------------------------------------------------------
bpy.ops.object.light_add(type="SUN", location=(25, -30, 55))
sun = bpy.context.active_object
sun.data.energy = 1.4
sun.data.color = hex_lin("#B4C7FF")[:3]
sun.data.angle = radians(6)
def _look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
_look_at(sun, (0, 0, 6))
link_col(sun, col_static)

bpy.ops.object.light_add(type="AREA", location=(-20 * DIR_E[0], -20 * DIR_E[1], 14))
fill = bpy.context.active_object
fill.data.energy = 240
fill.data.size = 14
fill.data.color = hex_lin("#FF8A4C")[:3]
_look_at(fill, (0, 0, 4))
link_col(fill, col_static)

# 顶棚下暖光点灯 ×3 (仅预览照明用, 导出前移除; 运行时由 app 侧点灯)
for k in range(3):
    a = E + k * 2 * pi / 3
    bpy.ops.object.light_add(type="POINT", location=(4.5 * cos(a), 4.5 * sin(a), 4.6))
    lamp = bpy.context.active_object
    lamp.name = f"CR_PvLight{k}"
    lamp.data.energy = 110
    lamp.data.color = hex_lin("#FFD9A8")[:3]
    lamp.data.shadow_soft_size = 0.6
    link_col(lamp, col_static)

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
    _look_at(cam, target)
    link_col(cam, col_static)
    return cam

# 预览机位 (origin 建模, 入口方位 E = 202°)
d = DIR_E
perp = (-sin(E), cos(E))
cam_front = add_cam("CR_CamFront", (19.0 * d[0], 19.0 * d[1], 2.6), (0, 0, 2.9), lens=42)
cam_three = add_cam("CR_CamThree",
                    (23 * d[0] + 3 * perp[0], 23 * d[1] + 3 * perp[1], 7.0),
                    (0, 0, 3.6), lens=34)
cam_side  = add_cam("CR_CamSide", (21 * perp[0], 21 * perp[1], 6.5), (0, 0, 3.4), lens=36)
# 幽灵马特写 (i1, θ=E+36°): 退到围栏外, 沿马环切向偏 25° 拍全身侧像
th1 = E + 2 * pi / P["rides"]
hx, hy = RIDE_R * cos(th1), RIDE_R * sin(th1)
thc = th1 - radians(25)
cam_det = add_cam("CR_CamDetail", (11.0 * cos(thc), 11.0 * sin(thc), 2.35),
                  (hx, hy, 1.95), lens=40)
# 平台第一人称 (入口侧上盘, 斜向看向马环避开中柱)
cam_fp = add_cam("CR_CamInterior",
                 (7.0 * cos(E + radians(28)), 7.0 * sin(E + radians(28)), DECK + 1.62),
                 (4.5 * cos(E - radians(70)), 4.5 * sin(E - radians(70)), 1.8), lens=21)

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

# animation -------------------------------------------------------------------
spin.rotation_euler.z = 0.0
spin.keyframe_insert("rotation_euler", frame=1)
spin.rotation_euler.z = 2 * pi
spin.keyframe_insert("rotation_euler", frame=1 + spin_frames)

bob_frames = int(P["bob_period_s"] * P["fps"])
for i in bob_idx:
    root = ride_roots[i]
    phase = i * 0.7
    f = 1
    while f <= 1 + spin_frames:
        z = DECK + P["bob_amp"] * sin(2 * pi * (f - 1) / bob_frames + phase)
        root.location.z = z
        root.keyframe_insert("location", frame=f)
        f += 5

def finalize_curves(ob):
    for fc in obj_fcurves(ob):
        if fc.data_path == "rotation_euler":
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        try:
            mod = fc.modifiers.new("CYCLES")
        except Exception:
            pass

finalize_curves(spin)
for i in bob_idx:
    finalize_curves(ride_roots[i])

# 按材质分组合并 (压 draw call; 动画根 CR_Spin / CR_Ride_i 不动) ----------------
def under_root(ob, root_name):
    p = ob.parent
    while p:
        if p.name == root_name or p.name.startswith(root_name + "_"):
            return True
        p = p.parent
    return False

def join_group(pred, prefix):
    groups = {}
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH" or not pred(ob):
            continue
        mat = ob.data.materials[0].name if ob.data.materials else "NONE"
        groups.setdefault(mat, []).append(ob)
    for mat_name, obs in groups.items():
        bpy.ops.object.select_all(action="DESELECT")
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
join_group(lambda ob: ob.parent is None, "CR_S")                       # 静态场地
join_group(lambda ob: under_root(ob, "CR_Spin") and
           not any(under_root(ob, f"CR_Ride_{i}") for i in range(P["rides"])),
           "CR_P")                                                     # 机台随转件
for i in range(P["rides"]):                                            # 每骑乘位
    join_group(lambda ob, i=i: under_root(ob, f"CR_Ride_{i}"), f"CR_R{i}")
bpy.ops.object.select_all(action="DESELECT")

# save source -----------------------------------------------------------------
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "carousel.blend"))
print("BLEND_SAVED")

# renders ---------------------------------------------------------------------
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
          ("03_side.png", cam_side), ("04_ghost_detail.png", cam_det),
          ("05_deck_fp.png", cam_fp)]
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
    sc.render.resolution_x, sc.render.resolution_y = (1280, 720)
    sc.frame_end = 181
    try:
        bpy.ops.render.render(animation=True)
        print("VIDEO_OK")
    except Exception as e:
        print("VIDEO_FAIL", type(e).__name__, str(e)[:160])

# export glb -------------------------------------------------------------------
# 预览地面盘与预览灯仅服务 blender 预览; app 侧地面由 park_env 提供, 导出前移除
ground = next((o for o in bpy.context.scene.objects
               if o.type == "MESH" and o.data.materials
               and o.data.materials[0].name == "CR_GroundPreview"), None)
if ground:
    print("CR_GROUND_REMOVED", ground.name)
    bpy.data.objects.remove(ground, do_unlink=True)
for ob in [o for o in bpy.context.scene.objects if o.name.startswith("CR_PvLight")]:
    print("PV_LIGHT_REMOVED", ob.name)
    bpy.data.objects.remove(ob, do_unlink=True)
try:
    bpy.ops.export_scene.gltf(filepath=str(OUT / "carousel.glb"),
                              export_format="GLB", export_animations=True,
                              export_apply=True)
except (TypeError, RuntimeError) as e:
    print("GLTF_KWARG_FALLBACK", type(e).__name__)
    bpy.ops.export_scene.gltf(filepath=str(OUT / "carousel.glb"),
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
