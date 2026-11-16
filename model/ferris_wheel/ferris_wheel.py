# -*- coding: utf-8 -*-
"""
Ferris Wheel v2 - Halloween Night "幽眠摩天轮" (game-ready glTF asset)
Run: blender --background --python ferris_wheel.py
All sizes in meters. Wheel spins about local Y (axle), cabins stay level.

v2 万圣节惊魂夜重做:
  - R=16m, 16 cabins, hub 19m  (登舱平台顶 1.0m, 舱底地板 ~1.06m 正好踏板)
  - 双弦杆轮缘桁架 + 之字斜撑 + 内环 + 24 辐条 + 细张拉杆
  - 舱体: 弧顶灯笼 + 密分格玻璃带 + 内饰(地板/对坐长椅/中柱扶手/暖光天花)
    + 南瓜徽牌 + 裙边缓冲 + 门框
  - 站台: 雨棚 + 吊灯 + 排队围栏 + 台阶 + 售票亭 + 地面灯环
"""
import bpy
import math
from math import radians, pi, cos, sin
from pathlib import Path
import numpy as np
from mathutils import Vector

# ---------------------------------------------------------------- params ---
P = {
    "wheel_radius": 16.0,
    "rim_chord_a_r": 16.0,      # 轮缘外弦
    "rim_chord_b_r": 15.25,     # 轮缘内弦 (桁架双弦杆)
    "rim_half_gap": 1.25,       # 轮缘平面 y = +/- gap
    "inner_ring_r": 9.6,
    "hub_z": 20.1,
    "platform_r": 9.0,
    "platform_h": 1.55,         # 高站台: 落舱时舱地板(1.76)与站台(1.55)差 0.21 可跨入
    "ground_r": 70.0,
    "cabins": 16,
    "spokes_per_side": 24,
    "lattice_per_side": 48,     # 轮缘桁架之字斜撑数/侧
    "spin_period_s": 28.0,
    "fps": 30,
    "leg_base_x": 6.2,
    "leg_base_y": 3.0,
    "leg_top_x": 1.1,
    "leg_top_y": 2.2,
    "res_still": (1600, 900),
    "glass_alpha": 0.34,
    "render_video": False,      # 迭代期 False, 定稿 True
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
             coat=0.0, alpha=1.0):
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

# ---------------------------------------------------------------- build ----
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = P["fps"]
sc.frame_start = 1
spin_frames = int(P["spin_period_s"] * P["fps"])
sc.frame_end = spin_frames

col_static = bpy.data.collections.new("Static")
col_wheel  = bpy.data.collections.new("WheelSpin")
sc.collection.children.link(col_static)
sc.collection.children.link(col_wheel)

PAINTS = [HEX["orange"], HEX["violet"], HEX["green"], HEX["red"]]
DOTS   = [HEX["warm"], HEX["orange"], HEX["violet"], HEX["green"]]

# materials -------------------------------------------------------------
m_metal    = make_mat("FW_Metal", HEX["metal"], rough=0.45, metal=0.85)
m_metal_d  = make_mat("FW_MetalDark", HEX["metal_d"], rough=0.6, metal=0.7)
m_iron     = make_mat("FW_Iron", HEX["iron"], rough=0.55, metal=0.8)
m_wood     = make_mat("FW_Wood", HEX["wood"], rough=0.85, metal=0.0)
m_ground   = make_mat("FW_Ground", HEX["ground"], rough=0.95)
m_platform = make_mat("FW_Platform", HEX["platform"], rough=0.55, metal=0.1)
m_rim_a    = make_mat("FW_RimAmber", HEX["orange"], rough=0.4, emit=HEX["orange"], strength=2.2)
m_rim_v    = make_mat("FW_RimViolet", HEX["violet"], rough=0.4, emit=HEX["violet"], strength=2.2)
m_dot = [make_mat(f"FW_Dot{i}", c, rough=0.4, emit=c, strength=2.6) for i, c in enumerate(DOTS)]
m_cabin = [make_mat(f"FW_Cabin{i}", c, rough=0.28, metal=0.05, emit=c, strength=0.35,
                    coat=0.6) for i, c in enumerate(PAINTS)]
m_trim  = [make_mat(f"FW_Trim{i}", c, rough=0.4, emit=c, strength=1.5)
           for i, c in enumerate(PAINTS)]
m_glass = make_mat("FW_Glass", "#142A3E", rough=0.06, metal=0.0, alpha=P["glass_alpha"])
try:
    m_glass.blend_method = "BLEND"
except Exception:
    pass
try:
    m_glass.surface_render_method = "BLENDED"
except Exception:
    pass
m_glow   = make_mat("FW_InteriorGlow", HEX["warm"], rough=0.5, emit=HEX["warm"], strength=3.2)
m_bench  = make_mat("FW_Bench", "#4A3A26", rough=0.8)
m_lamp   = make_mat("FW_RoofLamp", HEX["warm"], rough=0.4, emit=HEX["warm"], strength=2.6)
m_pump   = make_mat("FW_Pumpkin", HEX["orange"], rough=0.35, emit=HEX["orange"], strength=2.4)
m_stem   = make_mat("FW_Stem", "#3E5230", rough=0.8)
m_edge_c = make_mat("FW_EdgeWarm", HEX["warm"], rough=0.4, emit=HEX["warm"], strength=2.4)
m_ring_a = make_mat("FW_RingAmber", HEX["orange"], rough=0.4, emit=HEX["orange"], strength=1.8)
m_ring_v = make_mat("FW_RingViolet", HEX["violet"], rough=0.4, emit=HEX["violet"], strength=1.8)
m_hub_g  = make_mat("FW_HubGlow", HEX["warm"], rough=0.4, emit=HEX["warm"], strength=2.6)
m_sign   = make_mat("FW_Sign", HEX["violet"], rough=0.4, emit=HEX["violet"], strength=2.0)

R = P["wheel_radius"]
G = P["rim_half_gap"]
HZ = P["hub_z"]
CA, CB = P["rim_chord_a_r"], P["rim_chord_b_r"]

# ground & platform -----------------------------------------------------
add_cyl("FW_Ground", P["ground_r"], 0.2, (0, 0, -0.1), mat=m_ground, verts=64)
add_cyl("FW_Platform", P["platform_r"], P["platform_h"],
        (0, 0, P["platform_h"] / 2), mat=m_platform, verts=64)
add_torus("FW_EdgeRing", P["platform_r"] - 0.05, 0.06,
          (0, 0, P["platform_h"] + 0.02), mat=m_edge_c, ms=96, ns=8)

# 台阶 (platform -y 侧, 8 级到 1.55 高站台)
for k in range(8):
    top_z = P["platform_h"] - (k + 1) * 0.194
    add_box(f"FW_Step{k}", (4.4, 0.9, 0.194), (0, -(9.45 + k * 0.9), top_z - 0.097),
            mat=m_platform)

# 地面灯环
add_torus("FW_GroundRing1", 12.5, 0.05, (0, 0, 0.03), mat=m_ring_a, ms=96, ns=8)
add_torus("FW_GroundRing2", 16.5, 0.05, (0, 0, 0.03), mat=m_ring_v, ms=96, ns=8)

# 平台矮柱灯
for i in range(12):
    th = i * pi / 6
    x, y = 10.4 * cos(th), 10.4 * sin(th)
    add_cyl(f"FW_Bollard{i}", 0.1, 0.5, (x, y, P["platform_h"] + 0.25), mat=m_iron, verts=10)
    add_sphere(f"FW_BollardTop{i}", 0.1, (x, y, P["platform_h"] + 0.56),
               mat=m_dot[i % len(m_dot)], seg=12, ring=8)

# 雨棚 (canopy): 6 柱六角布置 + 四棱锥尖顶 + 周圈吊灯笼
for i in range(6):
    th = i * pi / 3
    cx_, cy_ = 7.2 * cos(th), 7.2 * sin(th)
    add_cyl(f"FW_CanopyCol{i}", 0.14, 6.0 - P["platform_h"],
            (cx_, cy_, (6.0 + P["platform_h"]) / 2), mat=m_iron, verts=12)
add_cone("FW_CanopyRoof", 8.8, 1.5, (0, 0, 6.75), mat=m_metal_d, verts=4,
         rot=(0, 0, radians(45)))
add_torus("FW_CanopyEave", 6.55, 0.07, (0, 0, 6.06), mat=m_edge_c, ms=64, ns=8)
for i in range(8):
    th = i * pi / 4 + pi / 8
    lx, ly = 7.0 * cos(th), 7.0 * sin(th)
    add_cyl(f"FW_CanDrop{i}", 0.02, 0.4, (lx, ly, 5.8), mat=m_iron, verts=8)
    add_sphere(f"FW_CanLamp{i}", 0.1, (lx, ly, 5.5), mat=m_lamp, seg=12, ring=8)

# 排队围栏 (queue railings, platform -y 侧)
for lane_x in (-1.5, 1.5):
    n_post = 5
    for k in range(n_post):
        y = -10.2 - k * 0.95
        add_cyl(f"FW_QPost{lane_x}_{k}", 0.035, 1.0, (lane_x, y, P["platform_h"] + 0.5),
                mat=m_iron, verts=8)
        add_sphere(f"FW_QPostTop{lane_x}_{k}", 0.05, (lane_x, y, P["platform_h"] + 1.02),
                   mat=m_dot[1], seg=10, ring=6)
    for rz in (0.62, 0.98):
        y0, y1 = -10.2, -10.2 - (n_post - 1) * 0.95
        add_cyl(f"FW_QRail{lane_x}_{rz}", 0.025, abs(y1 - y0),
                (lane_x, (y0 + y1) / 2, P["platform_h"] + rz), rot=(radians(90), 0, 0),
                mat=m_iron, verts=8)

# 售票亭 (ticket booth, 右前)
bx, by = 7.6, -8.2
add_box("FW_BoothBody", (1.7, 1.7, 2.2), (bx, by, P["platform_h"] + 1.1), mat=m_wood)
add_cone("FW_BoothRoof", 1.35, 0.75, (bx, by, P["platform_h"] + 2.55), mat=m_metal_d, verts=4,
         rot=(0, 0, radians(45)))
add_box("FW_BoothSign", (0.95, 0.06, 0.5), (bx, by - 0.88, P["platform_h"] + 1.7), mat=m_sign)
add_box("FW_BoothCounter", (1.1, 0.25, 0.08), (bx, by - 0.78, P["platform_h"] + 1.05), mat=m_wood)

# support structure (static) ---------------------------------------------
lbx, lby, ltx, lty = P["leg_base_x"], P["leg_base_y"], P["leg_top_x"], P["leg_top_y"]
legs = {}
for sx in (1, -1):
    for sy in (1, -1):
        base = (sx * lbx, sy * lby, P["platform_h"])
        top = (sx * ltx, sy * lty, HZ)
        legs[(sx, sy)] = (base, top)
        ob = cyl_between(f"FW_Leg_{sx}_{sy}", base, top, 0.30, m_metal_d)
        link_col(ob, col_static)
        ob = add_cyl(f"FW_Foot_{sx}_{sy}", 0.55, 0.18, (sx * lbx, sy * lby, 0.09),
                     mat=m_metal_d, verts=12)
        link_col(ob, col_static)

def leg_point(sx, sy, t):
    base, top = legs[(sx, sy)]
    return tuple(Vector(base) + (Vector(top) - Vector(base)) * t)

for sy in (1, -1):
    for t, rr in ((0.30, 0.15), (0.58, 0.15)):
        p1 = leg_point(-1, sy, t)
        p2 = leg_point(1, sy, t)
        ob = cyl_between(f"FW_TieX_{sy}_{int(t*100)}", p1, p2, rr, m_metal_d)
        link_col(ob, col_static)

for sx in (1, -1):
    for t in (0.25, 0.5, 0.75):
        p1 = leg_point(sx, 1, t)
        p2 = leg_point(sx, -1, t)
        ob = cyl_between(f"FW_TieY_{sx}_{int(t*100)}", p1, p2, 0.12, m_metal_d)
        link_col(ob, col_static)
    for (t1, t2) in ((0.18, 0.52), (0.52, 0.85)):
        p1 = leg_point(sx, 1, t1)
        p2 = leg_point(sx, -1, t2)
        ob = cyl_between(f"FW_Brace_{sx}_{int(t1*100)}", p1, p2, 0.06, m_metal_d)
        link_col(ob, col_static)

for sy in (1, -1):
    ob = add_cyl(f"FW_Housing_{sy}", 0.6, 0.9, (0, sy * 1.9, HZ),
                 rot=(radians(90), 0, 0), mat=m_metal, verts=20)
    link_col(ob, col_static)

# wheel (rotating) ---------------------------------------------------------
wheel = add_empty("FW_Wheel", (0, 0, HZ))
link_col(wheel, col_wheel)

def wheel_child(ob):
    parent_keep(ob, wheel)
    link_col(ob, col_wheel)

# axle
ob = add_cyl("FW_Axle", 0.34, 4.4, (0, 0, HZ), rot=(radians(90), 0, 0), mat=m_metal, verts=16)
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
        spokes_mid[(sy, k)] = (0.5 * CB * cos(th), sy * G, HZ + 0.5 * (HZ + CB * sin(th)))

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
# 相对 pivot 的 z 布局 (dz) — 真实观光舱比例 (外高 ~2.3m):
#   车顶 -0.50..-0.62 / 玻璃带 -0.70..-1.86 / 舱体 -1.86..-2.42 / 裙边 -2.42..-2.52
#   内部地板顶 -2.34, 坐姿视线 ~ -1.16 (玻璃带中部), 内净高 ~1.56
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

    def cabin_part(ob):
        parent_keep(ob, root)
        link_col(ob, col_wheel)

    ci = i % len(m_cabin)
    paint = m_cabin[ci]
    trim = m_trim[ci]
    Z = lambda dz: pz + dz  # noqa: E731

    # crossbar + joint + A-frame hanger
    ob = cyl_between(f"FW_Crossbar_{i}", (px, -(G + 0.18), pz), (px, G + 0.18, pz),
                     0.06, m_metal, verts=8)
    cabin_part(ob)
    ob = add_cyl(f"FW_Joint_{i}", 0.08, 0.18, (px, 0, Z(-0.08)), mat=m_metal, verts=10)
    cabin_part(ob)
    ob = cyl_between(f"FW_ArmL_{i}", (px, 0, Z(-0.14)), (px - 0.52, 0, Z(-0.50)), 0.048, m_metal)
    cabin_part(ob)
    ob = cyl_between(f"FW_ArmR_{i}", (px, 0, Z(-0.14)), (px + 0.52, 0, Z(-0.50)), 0.048, m_metal)
    cabin_part(ob)

    # roof cap + eave trim + lantern
    ob = add_bevel_box(f"FW_Roof_{i}", (1.78, 1.24, 0.12), (px, 0, Z(-0.56)),
                       mat=paint, segments=4, width=0.04)
    cabin_part(ob)
    ob = add_box(f"FW_RoofTrim_{i}", (1.86, 1.32, 0.05), (px, 0, Z(-0.645)), mat=trim)
    cabin_part(ob)
    ob = add_sphere(f"FW_Lantern_{i}", 0.09, (px, 0, Z(-0.40)), mat=m_lamp, seg=12, ring=8)
    cabin_part(ob)
    ob = add_cyl(f"FW_LanternCap_{i}", 0.05, 0.06, (px, 0, Z(-0.31)), mat=m_metal_d, verts=8)
    cabin_part(ob)

    # glass band (wraparound, 1.16m 高)
    ob = add_bevel_box(f"FW_Glass_{i}", (1.70, 1.18, 1.16), (px, 0, Z(-1.28)),
                       mat=m_glass, segments=3, width=0.035)
    cabin_part(ob)
    # window frame: corner posts
    for sx in (1, -1):
        for sy in (1, -1):
            ob = add_box(f"FW_Post_{i}_{sx}_{sy}", (0.07, 0.07, 1.20),
                         (px + sx * 0.815, sy * 0.555, Z(-1.28)), mat=m_metal)
            cabin_part(ob)
    # mullions: +-z faces x2 each, +-y faces x1 each
    for sz in (1, -1):
        for my in (-0.39, 0.39):
            ob = add_box(f"FW_MullZ_{i}_{sz}_{my}", (0.05, 0.06, 1.16),
                         (px, my, Z(-1.28)), mat=m_metal)
            cabin_part(ob)
    for sy in (1, -1):
        ob = add_box(f"FW_MullY_{i}_{sy}", (0.06, 0.05, 1.16),
                     (px, sy * 0.585, Z(-1.28)), mat=m_metal)
        cabin_part(ob)
    ob = add_box(f"FW_Transom_{i}", (1.72, 1.20, 0.045), (px, 0, Z(-0.92)), mat=m_metal)
    cabin_part(ob)
    ob = add_box(f"FW_Sill_{i}", (1.72, 1.20, 0.05), (px, 0, Z(-1.80)), mat=m_metal)
    cabin_part(ob)
    # door frames (两侧 +-y 开口)
    for sy in (1, -1):
        for sx in (1, -1):
            ob = add_box(f"FW_DoorJamb_{i}_{sy}_{sx}", (0.08, 0.06, 1.16),
                         (px + sx * 0.70, sy * 0.585, Z(-1.28)), mat=m_trim[ci])
            cabin_part(ob)
        ob = add_box(f"FW_DoorHead_{i}_{sy}", (1.48, 0.06, 0.08),
                     (px, sy * 0.585, Z(-0.74)), mat=m_trim[ci])
        cabin_part(ob)

    # interior: floor + glow ceiling + wainscot + benches + pole + rail
    ob = add_box(f"FW_Floor_{i}", (1.58, 1.06, 0.08), (px, 0, Z(-2.38)), mat=m_bench)
    cabin_part(ob)
    ob = add_box(f"FW_GlowCeil_{i}", (1.50, 1.04, 0.04), (px, 0, Z(-0.76)), mat=m_glow)
    cabin_part(ob)
    ob = add_box(f"FW_GlowWall_{i}", (1.50, 0.04, 0.44), (px, 0.52, Z(-2.12)), mat=m_glow)
    cabin_part(ob)
    for sx in (1, -1):
        ob = add_box(f"FW_BenchSeat_{i}_{sx}", (0.46, 0.94, 0.09),
                     (px + sx * 0.50, 0, Z(-1.905)), mat=m_bench)
        cabin_part(ob)
        ob = add_box(f"FW_BenchBack_{i}_{sx}", (0.07, 0.94, 0.50),
                     (px + sx * 0.775, 0, Z(-1.61)), mat=m_bench)
        cabin_part(ob)
        for sy in (1, -1):
            ob = add_box(f"FW_BenchArm_{i}_{sx}_{sy}", (0.42, 0.05, 0.06),
                         (px + sx * 0.50, sy * 0.44, Z(-1.74)), mat=m_wood)
            cabin_part(ob)
    ob = add_cyl(f"FW_Pole_{i}", 0.045, 1.3, (px, 0, Z(-1.52)), mat=m_metal, verts=10)
    cabin_part(ob)
    ob = add_torus(f"FW_Rail_{i}", 0.30, 0.03, (px, 0, Z(-1.12)),
                   rot=(radians(90), 0, 0), mat=m_metal, ms=24, ns=6)
    cabin_part(ob)
    # 舱内真实暖光点光源 (自发光面板不产光, 长椅地板需要它照亮)
    bpy.ops.object.light_add(type="POINT", location=(px, 0, Z(-1.25)))
    lamp = bpy.context.active_object
    lamp.name = f"FW_CabinLight_{i}"
    lamp.data.energy = 12.0
    lamp.data.color = hex_lin(HEX["warm"])[:3]
    lamp.data.shadow_soft_size = 0.15
    cabin_part(lamp)

    # lower body + belt trim + pumpkin emblems(四向) + skirt + bumpers
    ob = add_bevel_box(f"FW_Body_{i}", (1.70, 1.18, 0.56), (px, 0, Z(-2.14)),
                       mat=paint, segments=3, width=0.05)
    cabin_part(ob)
    ob = add_box(f"FW_Belt_{i}", (1.76, 1.24, 0.06), (px, 0, Z(-1.90)), mat=trim)
    cabin_part(ob)
    # +-z 面南瓜 (压扁 z)
    for sz in (1, -1):
        ob = add_sphere(f"FW_Pump_{i}_z{sz}", 0.17, (px, 0, Z(-1.98)),
                        mat=m_pump, seg=14, ring=10, scale=(1.0, 1.0, 0.5))
        cabin_part(ob)
        ob = add_cyl(f"FW_PumpStem_{i}_z{sz}", 0.025, 0.1, (px, 0, Z(-1.84)),
                     mat=m_stem, verts=6)
        cabin_part(ob)
    # +-y 面南瓜 (压扁 y)
    for sy in (1, -1):
        ob = add_sphere(f"FW_Pump_{i}_y{sy}", 0.17, (px, sy * 0.60, Z(-1.98)),
                        mat=m_pump, seg=14, ring=10, scale=(1.0, 0.5, 1.0))
        cabin_part(ob)
        ob = add_cyl(f"FW_PumpStem_{i}_y{sy}", 0.025, 0.1, (px, sy * 0.60, Z(-1.84)),
                     mat=m_stem, verts=6)
        cabin_part(ob)
    ob = add_bevel_box(f"FW_Skirt_{i}", (1.78, 1.26, 0.10), (px, 0, Z(-2.47)),
                       mat=m_metal_d, segments=2, width=0.03)
    cabin_part(ob)
    for sx in (1, -1):
        for sy in (1, -1):
            ob = add_sphere(f"FW_Bumper_{i}_{sx}_{sy}", 0.07,
                            (px + sx * 0.82, sy * 0.56, Z(-2.50)),
                            mat=m_metal, seg=10, ring=6)
            cabin_part(ob)

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
cam_three = add_cam("FW_CamThree", (46, -52, 27), (0, 0, 16), lens=36)
cam_side  = add_cam("FW_CamSide", (70, -5, 19), (0, 0, 17), lens=35)

# 舱体特写: 找最接近 -30 度角的舱
det_th = radians(-30)
def _ang_diff(a, b):
    return abs(((a - b + pi) % (2 * pi)) - pi)
best = min(range(P["cabins"]), key=lambda i: _ang_diff(cabin_roots[i][1], det_th))
cz = HZ + R * sin(cabin_roots[best][1])
cx = R * cos(cabin_roots[best][1])
cam_det = add_cam("FW_CamDetail", (cx + 3.6, -6.6, cz + 2.4), (cx, 0, cz - 1.6), lens=50)

# 舱内第一人称视角 (验证内饰): 找最接近 -90 度(最低点)的舱, 坐姿视线
fp_th = radians(-90)
best_fp = min(range(P["cabins"]), key=lambda i: _ang_diff(cabin_roots[i][1], fp_th))
fpz = HZ + R * sin(cabin_roots[best_fp][1])
fpx = R * cos(cabin_roots[best_fp][1])
cam_fp = add_cam("FW_CamInterior", (fpx + 0.45, 0.20, fpz - 1.16),
                 (fpx - 1.8, -0.05, fpz - 1.02), lens=18)

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
wheel.rotation_euler.y = 0.0
wheel.keyframe_insert("rotation_euler", frame=1)
wheel.rotation_euler.y = 2 * pi
wheel.keyframe_insert("rotation_euler", frame=1 + spin_frames)

for root, _ in cabin_roots:
    root.rotation_euler.y = 0.0
    root.keyframe_insert("rotation_euler", frame=1)
    root.rotation_euler.y = -2 * pi
    root.keyframe_insert("rotation_euler", frame=1 + spin_frames)

def finalize_curves(ob):
    for fc in obj_fcurves(ob):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
        try:
            mod = fc.modifiers.new("CYCLES")
        except Exception:
            pass

finalize_curves(wheel)
for root, _ in cabin_roots:
    finalize_curves(root)

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
    groups = {}
    meshes = [ob for ob in bpy.context.scene.objects
              if ob.type == "MESH" and pred(ob)]
    for mat_name, obs in groups.items():
        # 关键: 每组合并前必须清空选择——join 会吞掉所有已选中对象,
        # 上组合并结果保持选中, 不清空会把别的组滚雪球并进来
        bpy.ops.object.select_all(action="DESELECT")
        for ob in obs:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = obs[0]
        if len(obs) > 1:
            bpy.ops.object.join()
        obs[0].name = f"{prefix}_{mat_name}"
    print(f"JOIN {prefix}: {len(groups)} groups, {sum(len(v) for v in groups.values())} objs")

bpy.ops.object.select_all(action="DESELECT")
join_group(lambda ob: ob.parent is None, "FW_S")                      # 静组 (站台/支架)
join_group(lambda ob: under_root(ob, "FW_Wheel") and not under_root(ob, "FW_CabinRoot"),
           "FW_W")                                                    # 轮体结构
for i in range(P["cabins"]):                                          # 每舱
    join_group(lambda ob, i=i: under_root(ob, f"FW_CabinRoot_{i}"), f"FW_C{i}")
bpy.ops.object.select_all(action="DESELECT")

# save source + export glb -----------------------------------------------------
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "ferris_wheel.blend"))
print("BLEND_SAVED")

try:
    bpy.ops.export_scene.gltf(filepath=str(OUT / "ferris_wheel.glb"),
                              export_format="GLB", export_animations=True,
                              export_apply=True)
except (TypeError, RuntimeError) as e:
    print("GLTF_KWARG_FALLBACK", type(e).__name__)
    bpy.ops.export_scene.gltf(filepath=str(OUT / "ferris_wheel.glb"),
                              export_format="GLB")
print("GLB_EXPORTED")

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
          ("05_interior_fp.png", cam_fp)]
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

# report ------------------------------------------------------------------------
tris = 0
for ob in bpy.context.scene.objects:
    if ob.type == "MESH":
        me = ob.data
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
print(f"SUMMARY tris={tris} fps={P['fps']} frames={sc.frame_start}-{sc.frame_end}")
print("DONE")
