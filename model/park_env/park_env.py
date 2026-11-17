# -*- coding: utf-8 -*-
"""
Park Environment - "幽夜游乐场" Halloween night park (game-ready glTF asset)
Run: blender --background --python park_env.py

布局 (Blender 坐标, +Y=北):
  - 摩天轮在原点 (轮盘资产独立), 登舱台阶在 -Y 侧
  - 南入口大门 (0,-84) -> 石板主路 -> 中央广场 (r17.5)
  - 西侧市集亭 x3 / 东南墓园角落 / 东北旋转木马+过山车剪影 (占位)
  - 围墙铁艺栅栏 r84 + 维多利亚路灯 x12 + 跨路灯串 ~15 条
  - 枯树 x15 / 缠灯松树 x5 / 南瓜灯 ~20 / 长椅/木桶/干草
  - 远景: 山脊剪影环 + 城市灯火点阵
输出: park_env.glb (按材质合并) + colliders.json (app 坐标) + preview/
"""
import bpy
import bmesh
import json
import random
from math import radians, pi, cos, sin, atan2
from pathlib import Path
import numpy as np
from mathutils import Vector

random.seed(11)

P = {
    "park_r": 88.0,
    "fence_r": 84.0,
    "plaza_r": 17.5,
    "res_still": (1600, 900),
}

HEX = {
    "orange": "#FFA53B",
    "violet": "#9B5BFF",
    "green":  "#8CFF4A",
    "red":    "#C43B3B",
    "warm":   "#FFE9C4",
    "cream":  "#E8D9B8",
    "metal":  "#3A4152",
    "iron":   "#23273A",
    "metal_d": "#1E2330",
    "stone":  "#3A3F4C",
    "wood":   "#4A3526",
    "straw":  "#8A6A2E",
    "ground": "#0B0F14",
    "path":   "#262B36",
    "night":  "#060913",
    "ridge":  "#0F1422",
    "pumpkin":"#C87419",
    "pumpface":"#FFC46B",
    "grass":  "#10151A",
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
def sock(node, ident):
    for s in node.inputs:
        if s.identifier == ident:
            return s
    return None

def make_mat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    s = sock(p, "Base Color")
    if s: s.default_value = (*hex_lin(color)[:3], 1.0)
    s = sock(p, "Metallic")
    if s: s.default_value = metal
    s = sock(p, "Roughness")
    if s: s.default_value = rough
    if emit:
        s = sock(p, "Emission Color")
        if s: s.default_value = hex_lin(emit)
        s = sock(p, "Emission Strength")
        if s: s.default_value = strength
    return m

def smooth(ob):
    for poly in ob.data.polygons:
        poly.use_smooth = True

def add_cyl(name, r, depth, loc, rot=(0, 0, 0), mat=None, verts=12, sm=True):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, vertices=verts,
                                        location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    if mat: ob.data.materials.append(mat)
    if sm: smooth(ob)
    return ob

def cyl_between(name, p1, p2, r, mat, verts=6, sm=True):
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

def add_torus(name, R, tube, loc, rot=(0, 0, 0), mat=None, ms=64, ns=8, scale=(1, 1, 1)):
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
    """水平圆环按局部角度开缺口: 删 [center-half, center+half] 区间的顶点。
    用于广场发光环在摩天轮登舱台阶走廊断开 (角度 270° = blender -y = 台阶侧)。"""
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

def add_cone(name, r, depth, loc, mat=None, verts=4, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(radius1=r, depth=depth, vertices=verts,
                                    location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    if mat: ob.data.materials.append(mat)
    smooth(ob)
    return ob

def add_sphere(name, r, loc, mat=None, seg=10, ring=6, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=seg, ring_count=ring,
                                         location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    if mat: ob.data.materials.append(mat)
    smooth(ob)
    return ob

def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

COLLIDERS = []   # (x, y, r[, h]) blender 坐标, 导出时转 app 坐标
COLLIDER_RECTS = []  # (x, y, hw, hd) blender 坐标 — 轴对齐盒墙(可推挤), 用于贴近邻件的建筑
POIS = []        # (x, y, label)

def collider(x, y, r, h=None):
    """h = 顶面高度（blender z, 可选）：有 h 的圆顶面可站立（跳跃/台阶吸附）,
    无 h 的圆为无限高阻挡。app 侧语义见 src/player/controller.js groundAt()"""
    COLLIDERS.append({"x": round(x, 2), "y": round(y, 2), "r": round(r, 2), "h": h})

def collider_rect(x, y, hw, hd):
    """轴对齐盒墙（半宽/半深）：圆形罩会封掉紧邻可站物（如亭旁木桶）的上空时改用"""
    COLLIDER_RECTS.append({"x": round(x, 2), "y": round(y, 2),
                           "hw": round(hw, 2), "hd": round(hd, 2)})

# ---------------------------------------------------------------- build ----
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
col = bpy.data.collections.new("ParkEnv")
sc.collection.children.link(col)

DOTS = [HEX["warm"], HEX["orange"], HEX["violet"], HEX["green"]]

m_ground  = make_mat("PE_Ground", HEX["ground"], rough=0.95)
m_grass   = make_mat("PE_Grass", HEX["grass"], rough=0.95)
m_path    = make_mat("PE_Path", HEX["path"], rough=0.8, metal=0.05)
m_iron    = make_mat("PE_Iron", HEX["iron"], rough=0.55, metal=0.8)
m_metal_d = make_mat("PE_MetalDark", HEX["metal_d"], rough=0.6, metal=0.7)
m_stone   = make_mat("PE_Stone", HEX["stone"], rough=0.85)
m_wood    = make_mat("PE_Wood", HEX["wood"], rough=0.85)
m_straw   = make_mat("PE_Straw", HEX["straw"], rough=0.9)
m_ridge   = make_mat("PE_Ridge", HEX["ridge"], rough=1.0)
m_warm    = make_mat("PE_EmitWarm", HEX["warm"], emit=HEX["warm"], strength=2.6)
m_orange  = make_mat("PE_EmitOrange", HEX["orange"], emit=HEX["orange"], strength=2.4)
m_violet  = make_mat("PE_EmitViolet", HEX["violet"], emit=HEX["violet"], strength=2.2)
m_green   = make_mat("PE_EmitGreen", HEX["green"], emit=HEX["green"], strength=2.2)
m_red     = make_mat("PE_EmitRed", HEX["red"], emit=HEX["red"], strength=2.2)
m_dot     = [make_mat(f"PE_Dot{i}", c, emit=c, strength=2.6) for i, c in enumerate(DOTS)]
m_pump    = make_mat("PE_Pumpkin", HEX["pumpkin"], rough=0.5, emit=HEX["pumpkin"], strength=0.5)
m_pumpface= make_mat("PE_PumpFace", HEX["pumpface"], emit=HEX["pumpface"], strength=3.0)
m_stem    = make_mat("PE_Stem", "#3E5230", rough=0.8)
m_trunk   = make_mat("PE_Trunk", "#2E2620", rough=0.9)
m_sign_g  = make_mat("PE_SignGate", HEX["violet"], emit=HEX["violet"], strength=1.8)

def at(name, ob):
    ob.name = name
    return ob

# ---------------- 地面 / 广场 / 道路 ----------------
add_cyl("PE_GroundDisc", P["park_r"], 0.2, (0, 0, -0.15), mat=m_ground, verts=64)
add_cyl("PE_PlazaDisc", P["plaza_r"], 0.1, (0, 0, -0.02), mat=m_path, verts=64)
# 广场双发光环: 南向 ±13° 断弧 —— 摩天轮登舱台阶占据南向走廊 (r9~16.2, 半宽 2.2),
# 全圆环会从台阶中段下方穿过/与末级台阶相交, 制造台阶悬浮错觉 (v2.3)
add_torus("PE_PlazaRing1", 15.5, 0.14, (0, 0, 0.07), mat=m_orange, ms=96, ns=6, scale=(1, 1, 0.12))
torus_gap(bpy.data.objects["PE_PlazaRing1"], gap_half_deg=13.0, gap_center_deg=270.0)
add_torus("PE_PlazaRing2", 13.0, 0.10, (0, 0, 0.07), mat=m_violet, ms=96, ns=6, scale=(1, 1, 0.12))
torus_gap(bpy.data.objects["PE_PlazaRing2"], gap_half_deg=13.0, gap_center_deg=270.0)

# 主路 (南入口 -> 广场), 分 4 段
for k, yc in enumerate((-27.5, -45.0, -62.5, -78.0)):
    add_box(f"PE_MainPath{k}", (4.8, 18.5, 0.12), (0, yc, -0.02), mat=m_path)
# 环路
add_torus("PE_LoopPath", 34.0, 1.9, (0, 0, -0.04), mat=m_path, ms=96, ns=10, scale=(1, 1, 0.05))
# 支路: 墓园 (东) / 市集 (西)
add_box("PE_PathGrave", (33.0, 3.0, 0.12), (17.0, -40.0, -0.02), mat=m_path)
add_box("PE_PathStall", (31.0, 3.0, 0.12), (-16.0, -32.0, -0.02), mat=m_path)
# 路缘草皮环 (广场外圈草地色带, 打破纯黑)
add_torus("PE_GrassBand", 24.0, 3.2, (0, 0, -0.06), mat=m_grass, ms=96, ns=10, scale=(1, 1, 0.06))
add_torus("PE_GrassBand2", 44.0, 5.0, (0, 0, -0.06), mat=m_grass, ms=96, ns=10, scale=(1, 1, 0.06))

# ---------------- 入口大门 ----------------
gx = 3.4
for sx in (1, -1):
    add_box(f"PE_GatePillar{sx}", (1.7, 1.7, 7.6), (sx * gx, -84.0, 3.8), mat=m_stone)
    add_cone(f"PE_GateTip{sx}", 1.15, 1.3, (sx * gx, -84.0, 8.15), mat=m_metal_d, verts=4,
             rot=(0, 0, radians(45)))
    add_sphere(f"PE_GateLamp{sx}", 0.26, (sx * gx, -84.0, 8.95), mat=m_warm, seg=12, ring=8)
    collider(sx * gx, -84.0, 1.2)
add_box("PE_GateArch", (8.9, 1.1, 1.0), (0, -84.0, 7.0), mat=m_stone)
add_box("PE_GateSign", (4.4, 0.22, 1.5), (0, -84.0, 5.6), mat=m_sign_g)
for k in range(3):
    add_sphere(f"PE_GateDot{k}", 0.14, (-1.3 + k * 1.3, -84.0, 6.4),
               mat=m_dot[k % 4], seg=10, ring=6)
POIS.append((0, -80.0, "entrance"))

# ---------------- 围墙铁艺栅栏 ----------------
n_post = 220
for k in range(n_post):
    th = k * 2 * pi / n_post
    x, y = P["fence_r"] * cos(th), P["fence_r"] * sin(th)
    if y < -82.0 and abs(x) < 5.0:   # 大门开口
        continue
    add_box(f"PE_FencePost{k}", (0.15, 0.15, 2.5), (x, y, 1.25), mat=m_iron)
    add_cone(f"PE_FenceTip{k}", 0.10, 0.4, (x, y, 2.68), mat=m_iron, verts=6)
for rz in (1.15, 1.95):
    add_torus(f"PE_FenceRail{rz}", P["fence_r"], 0.055, (0, 0, rz), mat=m_iron, ms=160, ns=6)

# ---------------- 维多利亚路灯 x12 ----------------
lamp_positions = []
for k in range(4):
    lamp_positions.append((4.4, -24.0 - k * 14.0))
    lamp_positions.append((-4.4, -24.0 - k * 14.0))
for th in (radians(45), radians(135), radians(225), radians(315)):
    lamp_positions.append((15.0 * cos(th), 15.0 * sin(th)))

for i, (lx, ly) in enumerate(lamp_positions):
    add_cyl(f"PE_LampBase{i}", 0.24, 0.5, (lx, ly, 0.25), mat=m_iron, verts=10)
    add_cyl(f"PE_LampPole{i}", 0.08, 3.3, (lx, ly, 2.0), mat=m_iron, verts=8)
    add_sphere(f"PE_LampGlass{i}", 0.27, (lx, ly, 3.75), mat=m_warm, seg=12, ring=8)
    add_cone(f"PE_LampCap{i}", 0.34, 0.35, (lx, ly, 4.12), mat=m_metal_d, verts=6)
    collider(lx, ly, 0.4)

# ---------------- 跨路灯串 ----------------
def string_lights(name, p1, p2, sag=0.55, step=0.55):
    """悬链线灯串: p1/p2 = (x, y, z), 灯珠循环四色."""
    p1, p2 = Vector(p1), Vector(p2)
    L = (p2 - p1).length
    n = max(int(L / step), 3)
    prev = None
    for k in range(n + 1):
        t = k / n
        pt = p1.lerp(p2, t)
        pt.z -= sag * 4 * t * (1 - t)
        if prev is not None:
            cyl_between(f"{name}_c{k}", prev, pt, 0.015, m_iron, verts=5)
        if k % 1 == 0:
            add_sphere(f"{name}_b{k}", 0.055, (pt.x, pt.y, pt.z - 0.09),
                       mat=m_dot[k % 4], seg=8, ring=5)
        prev = pt

runs = []
# 主路灯杆之间 (双侧)
for k in range(3):
    runs.append(((4.4, -24.0 - k * 14.0, 3.6), (4.4, -38.0 - k * 14.0, 3.6)))
    runs.append(((-4.4, -24.0 - k * 14.0, 3.6), (-4.4, -38.0 - k * 14.0, 3.6)))
# 大门 -> 第一对灯杆
runs.append(((3.4, -84.0, 7.2), (4.4, -66.0, 3.6)))
runs.append(((-3.4, -84.0, 7.2), (-4.4, -66.0, 3.6)))
# 路灯 -> 广场灯 (斜拉)
runs.append(((4.4, -24.0, 3.6), (10.6, -10.6, 3.6)))
runs.append(((-4.4, -24.0, 3.6), (-10.6, -10.6, 3.6)))
# 广场对角
runs.append(((10.6, -10.6, 3.6), (10.6, 10.6, 3.6)))
runs.append(((-10.6, -10.6, 3.6), (-10.6, 10.6, 3.6)))
# 市集上空 / 墓园 / 旋转木马
runs.append(((-24.0, -26.0, 3.2), (-40.0, -30.0, 3.2)))
runs.append(((26.0, -34.0, 3.2), (40.0, -44.0, 3.2)))
runs.append(((41.0, 14.0, 4.2), (49.0, 22.0, 4.2)))
for i, (a, b) in enumerate(runs):
    string_lights(f"PE_Str{i}", a, b)

# ---------------- 枯树 x15 (递归分枝) ----------------
def spooky_tree(name, x, y, scale=1.0):
    h = 2.8 * scale
    r0 = 0.30 * scale
    add_cyl(f"{name}_trunk", r0, h, (x, y, h / 2), mat=m_trunk, verts=7)
    top = Vector((x, y, h))
    dirs = []
    for b in range(3):
        ang = random.uniform(0, 2 * pi)
        tilt = random.uniform(0.6, 1.1)
        d = Vector((cos(ang) * tilt, sin(ang) * tilt, 1.0)).normalized()
        dirs.append(d)
    for b, d in enumerate(dirs):
        blen = 1.7 * scale
        mid = top + d * (blen * 0.5)
        end = top + d * blen
        cyl_between(f"{name}_b{b}", top, end, 0.09 * scale, m_trunk, verts=5)
        for s in range(2):
            ang2 = random.uniform(0, 2 * pi)
            d2 = (d + Vector((cos(ang2) * 0.7, sin(ang2) * 0.7, 0.9))).normalized()
            e2 = end + d2 * (1.05 * scale)
            cyl_between(f"{name}_b{b}s{s}", end, e2, 0.045 * scale, m_trunk, verts=5)

tree_spots = []
while len(tree_spots) < 15:
    ang = random.uniform(0, 2 * pi)
    rr = random.uniform(26, 74)
    x, y = rr * cos(ang), rr * sin(ang)
    if abs(y + 40) < 8 and x > 8:      continue   # 墓园区
    if abs(y + 30) < 7 and x < -8:     continue   # 市集区
    if abs(x) < 7 and y < -18:         continue   # 主路
    if any((tx - x) ** 2 + (ty - y) ** 2 < 64 for tx, ty in tree_spots):
        continue
    tree_spots.append((x, y))
for i, (x, y) in enumerate(tree_spots):
    spooky_tree(f"PE_Tree{i}", x, y, scale=random.uniform(0.85, 1.35))
    collider(x, y, 0.6)

# ---------------- 缠灯松树 x5 (广场外圈) ----------------
for i in range(5):
    th = i * 2 * pi / 5 + 0.4
    x, y = 21.5 * cos(th), 21.5 * sin(th)
    for li, (cr, cz) in enumerate(((1.7, 1.4), (1.25, 2.6), (0.8, 3.7))):
        add_cone(f"PE_Pine{i}_{li}", cr, 1.7, (x, y, cz + 0.6), mat=m_trunk, verts=8)
    add_cyl(f"PE_PineTrunk{i}", 0.14, 1.2, (x, y, 0.6), mat=m_trunk, verts=6)
    for k in range(9):
        th2 = k * 2 * pi / 9
        dx, dy = 1.45 * cos(th2 + i), 1.45 * sin(th2 + i)
        add_sphere(f"PE_PineDot{i}_{k}", 0.07, (x + dx, y + dy, 1.6 + (k % 3) * 0.9),
                   mat=m_dot[k % 4], seg=8, ring=5)
    collider(x, y, 1.0)

# ---------------- 南瓜灯 ~20 ----------------
def jack_o_lantern(name, x, y, z=0.0, ry=0.0, s=1.0):
    body = add_sphere(f"{name}_body", 0.34 * s, (x, y, z + 0.26 * s), mat=m_pump,
                      seg=12, ring=8, scale=(1.0, 1.0, 0.78))
    body.rotation_euler.z = ry
    add_cyl(f"{name}_stem", 0.05 * s, 0.16 * s, (x, y, z + 0.56 * s), mat=m_stem, verts=6)
    # 脸 (朝向 ry): 两眼三角 + 三段嘴, 自发光, 略凸出球面
    fx = 0.34 * s
    ca, sa = cos(ry), sin(ry)
    def face_pos(off_x, off_z):
        return (x + ca * fx, y + sa * fx, z + off_z * s)
    for ex in (-0.11, 0.11):
        px_, py_, pz_ = face_pos(ex, 0.34)
        add_cone(f"{name}_eye{ex}", 0.095 * s, 0.14 * s, (px_, py_, pz_),
                 mat=m_pumpface, verts=3,
                 rot=(radians(90), 0, ry + radians(90)))
    for mk in (-0.1, 0.0, 0.1):
        px_, py_, pz_ = face_pos(mk, 0.12)
        add_box(f"{name}_mouth{mk}", (0.11 * s, 0.09 * s, 0.08 * s),
                (px_, py_, pz_), rot=(0, 0, ry), mat=m_pumpface)

pump_spots = []
pump_plan = [
    (2.9, -21.0, 0.0), (-3.1, -23.5, 0.0), (3.0, -35.0, 0.0), (-2.9, -37.5, 0.0),
    (2.8, -49.0, 0.0), (-3.2, -51.5, 0.0), (2.9, -63.0, 0.0), (-3.0, -65.5, 0.0),
    (1.2, -81.5, 0.0), (-1.4, -81.5, 0.0),
    (12.0, -12.0, 0.0), (-12.0, -12.0, 0.0), (13.5, 8.0, 0.0), (-13.0, 6.0, 0.0),
    (30.5, -36.5, 0.0), (24.0, -43.0, 0.0),
    (-22.0, -28.5, 0.0), (-29.0, -33.0, 0.0),
    (16.5, 13.0, 0.0), (-16.0, 14.0, 0.0),
]
for i, (x, y, _) in enumerate(pump_plan):
    ry = random.uniform(0, 2 * pi)
    jack_o_lantern(f"PE_Pump{i}", x, y, 0.0, ry=ry, s=random.uniform(0.9, 1.25))
    pump_spots.append((x, y))
    collider(x, y, 0.55)
# 打卡点: 5 个南瓜簇 (app 坐标在导出时换算)
POIS.extend([
    (pump_plan[2][0], pump_plan[2][1], "pumpkin_path_s"),
    (pump_plan[10][0], pump_plan[10][1], "pumpkin_plaza_e"),
    (pump_plan[11][0], pump_plan[11][1], "pumpkin_plaza_w"),
    (pump_plan[14][0], pump_plan[14][1], "pumpkin_grave"),
    (pump_plan[16][0], pump_plan[16][1], "pumpkin_stall"),
])

# ---------------- 墓园角落 (东) ----------------
gx0, gy0 = 34.0, -41.0
add_cyl("PE_GravePatch", 8.5, 0.08, (gx0, gy0, -0.03), mat=m_grass, verts=32)
stone_off = [(-3.2, 1.8, 6, 0.0), (-1.6, -2.2, -7, 8.0), (0.2, 2.6, 4, -6.0),
             (2.1, -1.8, -5, 0.0), (3.6, 2.2, 8, 10.0), (-4.4, -0.6, -4, 5.0),
             (1.2, 0.4, 7, -9.0), (-0.8, -3.6, -6, 3.0), (4.6, -0.4, 5, 0.0)]
for i, (ox, oy, tilt, rotz) in enumerate(stone_off):
    x, y = gx0 + ox, gy0 + oy
    add_box(f"PE_Grave{i}", (0.72, 0.2, 1.05), (x, y, 0.52),
            rot=(radians(tilt * 0.4), radians(tilt * 0.3), radians(rotz)), mat=m_stone)
    add_cyl(f"PE_GraveCap{i}", 0.36, 0.2, (x, y, 1.05), rot=(radians(90), 0, radians(rotz)),
            mat=m_stone, verts=12)
    collider(x, y, 0.75)
# 十字架 x2
for i, (ox, oy) in enumerate(((-2.6, 3.4), (3.2, -3.4))):
    x, y = gx0 + ox, gy0 + oy
    add_box(f"PE_CrossV{i}", (0.16, 0.14, 1.5), (x, y, 0.75), mat=m_wood)
    add_box(f"PE_CrossH{i}", (0.7, 0.14, 0.16), (x, y, 1.05), mat=m_wood)
    collider(x, y, 0.5)
# 墓园矮栅栏 (背面弧)
for k in range(10):
    th = radians(-80 + k * 16)
    fx, fy = gx0 + 8.2 * cos(th), gy0 + 8.2 * sin(th) - 2.0
    add_box(f"PE_GFence{k}", (0.12, 0.12, 1.1), (fx, fy, 0.55), mat=m_iron)
add_cyl("PE_GraveLantern", 0.16, 0.5, (gx0, gy0 + 4.6, 0.35), mat=m_iron, verts=8)
add_sphere("PE_GraveFlame", 0.12, (gx0, gy0 + 4.6, 0.72), mat=m_violet, seg=10, ring=6)
spooky_tree("PE_GraveTree", gx0 + 5.4, gy0 + 3.2, scale=1.2)
collider(gx0 + 5.4, gy0 + 3.2, 0.7)

# ---------------- 市集亭 x3 (西) ----------------
stall_defs = [(-25.0, -27.5, HEX["orange"], "treats"),
              (-31.5, -30.5, HEX["green"], "candy"),
              (-38.0, -33.5, HEX["red"], "brew")]
for i, (sx, sy, c, _label) in enumerate(stall_defs):
    add_box(f"PE_StallBody{i}", (2.7, 2.0, 2.3), (sx, sy, 1.15), mat=m_wood)
    # 条纹雨棚 (斜面 + 交替色条): 暖白与亭色相间
    sign_mats = {HEX["orange"]: m_orange, HEX["green"]: m_green, HEX["red"]: m_red}
    aw_z = 2.75
    for st in range(7):
        off = -0.95 + st * 0.32
        add_box(f"PE_StallStripe{i}_{st}", (0.32, 1.35, 0.06),
                (sx + off, sy - 0.62, aw_z - 0.30 + 0.02 * st),
                rot=(radians(-14), 0, 0),
                mat=(m_warm if st % 2 == 0 else sign_mats[c]))
    add_box(f"PE_StallCounter{i}", (2.5, 0.3, 0.09), (sx, sy - 1.05, 1.25), mat=m_wood)
    add_box(f"PE_StallSign{i}", (1.5, 0.08, 0.55), (sx, sy - 1.06, 2.15),
            mat=(m_orange if c == HEX["orange"] else m_green if c == HEX["green"] else m_red))
    add_cyl(f"PE_StallPost{i}L", 0.05, 1.5, (sx - 1.25, sy - 1.15, 2.05), mat=m_iron, verts=6)
    add_cyl(f"PE_StallPost{i}R", 0.05, 1.5, (sx + 1.25, sy - 1.15, 2.05), mat=m_iron, verts=6)
    # 亭体用精确盒墙而非罩圆: r2.0 罩圆会把亭旁木桶(top 0.955 可站)上空整体封死
    collider_rect(sx, sy, 1.35, 1.0)
    # 亭边木桶 + 干草
    add_cyl(f"PE_Barrel{i}", 0.42, 0.95, (sx + 2.0, sy + 0.6, 0.48), mat=m_wood, verts=12)
    collider(sx + 2.0, sy + 0.6, 0.6, h=0.955)  # 桶顶可站 (0.48+0.95/2)

# 干草堆 x3 (南瓜坐上面)
for i, (hx, hy) in enumerate(((26.0, -36.0), (12.5, -11.2), (-11.8, -11.5))):
    add_box(f"PE_Hay{i}", (1.35, 1.0, 0.75), (hx, hy, 0.37), rot=(0, 0, random.uniform(0, 1.5)),
            mat=m_straw)
    collider(hx, hy, 1.0, h=0.745)  # 垛顶可站 (0.37+0.75/2)

# 长椅 x6 (主路+广场)
bench_spots = [(5.6, -31.0, 90), (-5.6, -45.0, 90), (5.6, -59.0, 90),
               (9.5, -9.5, 45), (-9.5, 9.5, 225), (13.0, 0.0, -90)]
for i, (bx, by, rotz) in enumerate(bench_spots):
    rz = radians(rotz)
    add_box(f"PE_BenchSeat{i}", (1.7, 0.45, 0.09), (bx, by, 0.62), rot=(0, 0, rz), mat=m_wood)
    add_box(f"PE_BenchBack{i}", (1.7, 0.08, 0.5), (bx + 0.22 * sin(rz), by - 0.22 * cos(rz), 0.92),
            rot=(0, 0, rz), mat=m_wood)
    for lx in (-0.7, 0.7):
        lx_ = bx + lx * cos(rz)
        ly_ = by + lx * sin(rz)
        add_box(f"PE_BenchLeg{i}_{lx}", (0.08, 0.4, 0.58), (lx_, ly_, 0.29),
                rot=(0, 0, rz), mat=m_iron)
    collider(bx, by, 0.9, h=0.665)  # 座面可站 (0.62+0.09/2)

# ---------------- 旋转木马 (东北) ----------------
# 真实资产 = model/carousel/carousel.glb, app 侧由 main.js 摆到 (45, 0, -18)。
# 本文件不再生成占位几何 (2026-11-17 起以 glb 替代; park_env.blend 中 PE_Car* 已删除重导出)。
# 碰撞约定: 平台/中柱/台阶圆在 colliders.json 手工维护 (勿重跑本文件, 随机件会漂移);
#           骑乘位/铜杆为旋转件, 由 src/rides/carousel.js 每帧动态驱动碰撞圆。
mx, my = 45.0, 18.0
POIS.append((mx, my, "carousel"))

# ---------------- 过山车剪影 (远东北, 占位) ----------------
cpts = []
for k in range(47):
    t = k / 46
    cx_ = 42.0 + t * 42.0
    cy_ = 32.0 + t * 24.0
    cz_ = 2.4 + 3.2 * sin(t * 9.0) + t * 2.5
    cpts.append(Vector((cx_, cy_, cz_)))
for k in range(46):
    cyl_between(f"PE_Coast{k}", cpts[k], cpts[k + 1], 0.15, m_metal_d, verts=5)
for k in range(0, 46, 4):
    p = cpts[k]
    add_cyl(f"PE_CoastSup{k}", 0.1, p.z - 0.1, (p.x, p.y, (p.z - 0.1) / 2), mat=m_iron, verts=6)
    if k % 12 == 0:
        collider(p.x, p.y, 1.4)
for k in range(6, 46, 10):
    add_sphere(f"PE_CoastDot{k}", 0.12, (cpts[k].x, cpts[k].y, cpts[k].z + 0.25),
               mat=m_dot[2], seg=8, ring=5)

# ---------------- 远景: 山脊 + 城市灯火 ----------------
for i in range(12):
    th = i * 2 * pi / 12 + 0.26
    rr = random.uniform(240, 285)
    add_cone(f"PE_Ridge{i}", random.uniform(45, 75), random.uniform(48, 90),
             (rr * cos(th), rr * sin(th), -3.0), mat=m_ridge, verts=7)
for i in range(70):
    th = random.uniform(0, 2 * pi)
    rr = random.uniform(150, 215)
    add_sphere(f"PE_City{i}", 0.5, (rr * cos(th), rr * sin(th), random.uniform(1.0, 9.0)),
               mat=m_dot[random.randrange(4)], seg=6, ring=4)

# ---------------- 灯光 / 相机 / bloom ----------------
bpy.ops.object.light_add(type="SUN", location=(40, -50, 70))
sun = bpy.context.active_object
sun.data.energy = 2.3
sun.data.color = hex_lin("#B4C7FF")[:3]
sun.data.angle = radians(6)
look_at(sun, (0, 0, 5))

bpy.ops.object.light_add(type="AREA", location=(0, -20, 26))
fill = bpy.context.active_object
fill.data.energy = 4200
fill.data.size = 55
fill.data.color = hex_lin("#FF9A5C")[:3]
look_at(fill, (0, 0, 2))

w = bpy.data.worlds.new("Night")
sc.world = w
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = hex_lin(HEX["night"])
bg.inputs[1].default_value = 0.55

def add_cam(name, loc, target, lens=35):
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.active_object
    cam.name = name
    cam.data.lens = lens
    look_at(cam, target)
    return cam

cam_aerial = add_cam("PE_CamAerial", (95, -95, 72), (0, 0, 4), lens=32)
cam_street = add_cam("PE_CamStreet", (0.0, -46.0, 1.75), (0, 8, 8.0), lens=30)
cam_corner = add_cam("PE_CamCorner", (22.0, -50.0, 2.2), (36.0, -40.0, 1.2), lens=38)

sc.view_settings.view_transform = "Standard"
sc.view_settings.exposure = 0.35

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

# ---------------- 按材质合并 (压 draw call) ----------------
bpy.ops.object.select_all(action="DESELECT")
groups = {}
for ob in list(bpy.context.scene.objects):
    if ob.type != "MESH":
        continue
    mat = ob.data.materials[0].name if ob.data.materials else "NONE"
    groups.setdefault(mat, []).append(ob)
print(f"JOIN groups={len(groups)}")
for mat_name, obs in groups.items():
    # 关键: 每组合并前清空选择, 否则 join 会吞掉上组选中结果滚雪球
    bpy.ops.object.select_all(action="DESELECT")
    for ob in obs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    if len(obs) > 1:
        bpy.ops.object.join()
    bpy.context.view_layer.objects.active.name = f"PE_{mat_name}"
print("JOINED")

# ---------------- 导出 ----------------
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "park_env.blend"))
print("BLEND_SAVED")

try:
    bpy.ops.export_scene.gltf(filepath=str(OUT / "park_env.glb"),
                              export_format="GLB", export_apply=True)
except (TypeError, RuntimeError):
    bpy.ops.export_scene.gltf(filepath=str(OUT / "park_env.glb"),
                              export_format="GLB")
print("GLB_EXPORTED")

# colliders.json (转 app 坐标: app_x = blender_x, app_z = -blender_y)
manifest = {
    "version": 1,
    "note": "坐标为 glTF/app 空间 (x, z); 由 park_env.py 自动生成",
    "boundaryR": 82.5,
    "spawn": {"x": 0.0, "z": 80.0},
    "boarding": {"x": 0.0, "z": 16.4},
    "pois": [{"x": round(x, 2), "z": round(-y, 2), "label": lb} for x, y, lb in POIS],
    "rects": [
        {"x": r_["x"], "z": round(-r_["y"], 2), "hw": r_["hw"], "hd": r_["hd"]}
        for r_ in COLLIDER_RECTS
    ],
    "circles": [
        ({"x": c["x"], "z": round(-c["y"], 2), "r": c["r"],
          **({"h": round(c["h"], 3)} if c["h"] is not None else {})})
        for c in COLLIDERS
    ],
}
(OUT / "colliders.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
print(f"COLLIDERS circles={len(manifest['circles'])} pois={len(manifest['pois'])}")

# ---------------- 渲染预览 ----------------
def brightness(path):
    try:
        img = bpy.data.images.load(str(path))
        w_, h_ = img.size
        px = np.empty(w_ * h_ * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        mean = float(px.reshape(h_, w_, 4)[..., :3].mean())
        bpy.data.images.remove(img)
        return mean
    except Exception as e:
        print("CHECK_ERR", type(e).__name__, str(e)[:80])
        return -1.0

def render_still(name, cam):
    sc.camera = cam
    path = PREV / name
    sc.render.image_settings.media_type = "IMAGE"
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = str(path)
    sc.render.resolution_x, sc.render.resolution_y = P["res_still"]
    try:
        bpy.ops.render.render(write_still=True)
    except Exception as e:
        print("RENDER_FAIL", name, type(e).__name__, str(e)[:120])
        return False
    print("CHECK", name, f"mean={brightness(path):.4f}")
    return True

PREV.mkdir(exist_ok=True)
sc.render.engine = "BLENDER_EEVEE"
try:
    sc.eevee.taa_render_samples = 48
except Exception:
    pass

for name, cam in (("01_aerial.png", cam_aerial),
                  ("02_street.png", cam_street),
                  ("03_corner.png", cam_corner)):
    render_still(name, cam)

tris = 0
for ob in bpy.context.scene.objects:
    if ob.type == "MESH":
        me = ob.data
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
print(f"SUMMARY tris={tris}")
print("DONE")
