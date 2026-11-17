# -*- coding: utf-8 -*-
"""
烟花发射器 x3 设计预览 (仅渲染预览图, 不导出 glb —— 造型待用户确认后才并入 park_env)
Run: blender --background --python design_preview.py

三台发射器共享家族基因: 木结构 + 铁艺管件 + 点火箱红钮 + 暖光小灯;
以「管口发光环 + 饰色 + 剪影」区分型号:
  A 牡丹发射架 (南瓜橙): 低矮 A 字木架 + 5 管扇形
  B 垂柳塔     (暗夜紫): 四腿收分木塔 + 单口粗臼炮 + 垂链紫灯笼 + 弯月徽
  C 椰芯连环炮 (磷光绿): 双轮手推车 + 6 管转轮缸 + 摇柄齿轮 + 露头弹药箱
配色/材质语法沿用 park_env.py (基础不发光 + 小体量自发光点缀 strength 2.2-2.6)
"""
import bpy
import random
from math import radians, pi, cos, sin
from pathlib import Path
from mathutils import Vector

random.seed(7)

OUT = Path(__file__).resolve().parent
PREV = OUT / "preview"

HEX = {
    "orange": "#FFA53B", "violet": "#9B5BFF", "green": "#8CFF4A",
    "red": "#C43B3B", "warm": "#FFE9C4", "moon": "#EFE6CF",
    "metal": "#3A4152", "iron": "#23273A", "metal_d": "#1E2330",
    "wood": "#4A3526", "wood_d": "#3A2A1D", "straw": "#8A6A2E",
    "ground": "#0B0F14", "night": "#060913",
    "pumpkin": "#C87419", "pumpface": "#FFC46B",
}

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
col = bpy.data.collections.new("LauncherDesign")
sc.collection.children.link(col)

# ----------------------------------------------------------------- utils ---
def sock(node, ident):
    for s in node.inputs:
        if s.identifier == ident:
            return s
    return None

def hex_lin(h, a=1.0):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, a)

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

def _new_obj(name, verts, faces, mat, sm):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate(verbose=False)
    me.update()
    if mat: me.materials.append(mat)
    if sm:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob

def add_cyl(name, r, depth, loc, rot=(0, 0, 0), mat=None, verts=12, sm=True):
    hz = depth / 2
    vs = []
    for i in range(verts):
        a = 2 * pi * i / verts
        vs.append((r * cos(a), r * sin(a), -hz))
    for i in range(verts):
        a = 2 * pi * i / verts
        vs.append((r * cos(a), r * sin(a), hz))
    fs = []
    for i in range(verts):
        j = (i + 1) % verts
        fs.append((i, j, verts + j, verts + i))
    fs.append(tuple(range(verts - 1, -1, -1)))
    fs.append(tuple(range(verts, verts * 2)))
    ob = _new_obj(name, vs, fs, mat, sm)
    ob.location = loc
    ob.rotation_euler = rot
    return ob

def cyl_between(name, p1, p2, r, mat, verts=6, sm=True):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    L = d.length
    ob = add_cyl(name, r, 1.0, ((p1.x + p2.x) / 2, (p1.y + p2.y) / 2, (p1.z + p2.z) / 2),
                 (0, 0, 0), mat, verts, sm)
    ob.scale = (1, 1, max(L, 1e-4))
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    return ob

def add_torus(name, R, tube, loc, rot=(0, 0, 0), mat=None, ms=48, ns=8):
    vs = []
    for i in range(ms):
        a = 2 * pi * i / ms
        ca, sa = cos(a), sin(a)
        for j in range(ns):
            b = 2 * pi * j / ns
            cb, sb = cos(b), sin(b)
            vs.append(((R + tube * cb) * ca, (R + tube * cb) * sa, tube * sb))
    fs = []
    for i in range(ms):
        i2 = (i + 1) % ms
        for j in range(ns):
            j2 = (j + 1) % ns
            fs.append((i * ns + j, i2 * ns + j, i2 * ns + j2, i * ns + j2))
    ob = _new_obj(name, vs, fs, mat, True)
    ob.location = loc
    ob.rotation_euler = rot
    return ob

def torus_gap(ob, gap_half_deg, gap_center_deg):
    import bmesh
    from math import atan2
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
    vs = [(-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
          (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)]
    fs = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    ob = _new_obj(name, vs, fs, mat, False)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = size
    return ob

def add_cone(name, r, depth, loc, mat=None, verts=4, rot=(0, 0, 0)):
    hz = depth / 2
    vs = []
    for i in range(verts):
        a = 2 * pi * i / verts
        vs.append((r * cos(a), r * sin(a), -hz))
    vs.append((0, 0, hz))
    fs = []
    for i in range(verts):
        j = (i + 1) % verts
        fs.append((i, j, verts))
    fs.append(tuple(range(verts - 1, -1, -1)))
    ob = _new_obj(name, vs, fs, mat, True)
    ob.location = loc
    ob.rotation_euler = rot
    return ob

def add_sphere(name, r, loc, mat=None, seg=10, ring=6, scale=(1, 1, 1)):
    vs = [(0, 0, r)]
    for j in range(1, ring):
        phi = pi * j / ring
        sp, cp = sin(phi), cos(phi)
        for i in range(seg):
            th = 2 * pi * i / seg
            vs.append((r * sp * cos(th), r * sp * sin(th), r * cp))
    vs.append((0, 0, -r))
    top_i, bot_i = 0, len(vs) - 1
    fs = []
    for i in range(seg):
        i2 = (i + 1) % seg
        fs.append((top_i, 1 + i, 1 + i2))
    for j in range(ring - 2):
        row0 = 1 + j * seg
        row1 = row0 + seg
        for i in range(seg):
            i2 = (i + 1) % seg
            fs.append((row0 + i, row1 + i, row1 + i2, row0 + i2))
    last_row = 1 + (ring - 2) * seg
    for i in range(seg):
        i2 = (i + 1) % seg
        fs.append((bot_i, last_row + i2, last_row + i))
    ob = _new_obj(name, vs, fs, mat, True)
    ob.location = loc
    ob.scale = scale
    return ob

def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

# -------------------------------------------------------------- materials ---
m_wood   = make_mat("L_Wood", HEX["wood"], rough=0.85)
m_woodd  = make_mat("L_WoodDark", HEX["wood_d"], rough=0.9)
m_iron   = make_mat("L_Iron", HEX["iron"], rough=0.55, metal=0.8)
m_metal  = make_mat("L_Metal", HEX["metal"], rough=0.35, metal=0.9)
m_metald = make_mat("L_MetalDark", HEX["metal_d"], rough=0.6, metal=0.7)
m_warm   = make_mat("L_EmitWarm", HEX["warm"], emit=HEX["warm"], strength=2.6)
m_moon   = make_mat("L_EmitMoon", HEX["moon"], emit=HEX["moon"], strength=1.6)
m_red    = make_mat("L_EmitRed", HEX["red"], emit=HEX["red"], strength=2.2)
m_acc    = {
    "A": make_mat("L_EmitOrange", HEX["orange"], emit=HEX["orange"], strength=2.4),
    "B": make_mat("L_EmitViolet", HEX["violet"], emit=HEX["violet"], strength=2.2),
    "C": make_mat("L_EmitGreen", HEX["green"], emit=HEX["green"], strength=2.2),
}
m_pump   = make_mat("L_Pumpkin", HEX["pumpkin"], rough=0.5, emit=HEX["pumpkin"], strength=0.5)
m_pumpf  = make_mat("L_PumpFace", HEX["pumpface"], emit=HEX["pumpface"], strength=3.0)
m_ground = make_mat("L_Ground", HEX["ground"], rough=0.95)

# 每台发射器: builder 在原点附近建模并收集对象, 之后整体平移到站位
def kit(objs):
    def box(name, size, loc, rot=(0, 0, 0), mat=None):
        o = add_box(name, size, loc, rot, mat); objs.append(o); return o
    def cyl(name, r, depth, loc, rot=(0, 0, 0), mat=None, verts=12):
        o = add_cyl(name, r, depth, loc, rot, mat, verts); objs.append(o); return o
    def tor(name, R, tube, loc, rot=(0, 0, 0), mat=None):
        o = add_torus(name, R, tube, loc, rot, mat); objs.append(o); return o
    def cone(name, r, depth, loc, mat=None, verts=6, rot=(0, 0, 0)):
        o = add_cone(name, r, depth, loc, mat, verts, rot); objs.append(o); return o
    def sph(name, r, loc, mat=None, scale=(1, 1, 1)):
        o = add_sphere(name, r, loc, mat, 10, 6, scale); objs.append(o); return o
    def between(name, p1, p2, r, mat, verts=6):
        o = cyl_between(name, p1, p2, r, mat, verts); objs.append(o); return o
    return box, cyl, tor, cone, sph, between

def fire_box(objs, loc, yaw=0.0):
    """家族基因: 点火箱 + 红蘑菇钮 + 推杆 (所有型号共有)"""
    box, cyl, tor, cone, sph, between = kit(objs)
    box("FB_body", (0.42, 0.3, 0.3), (loc[0], loc[1], loc[2] + 0.15), (0, 0, yaw), m_woodd)
    box("FB_lip", (0.46, 0.34, 0.04), (loc[0], loc[1], loc[2] + 0.31), (0, 0, yaw), m_wood)
    cyl("FB_btn", 0.06, 0.05, (loc[0], loc[1] - 0.1, loc[2] + 0.36), (0, 0, 0), m_red, 10)
    sph("FB_btnCap", 0.055, (loc[0], loc[1] - 0.1, loc[2] + 0.39), m_red, scale=(1, 1, 0.6))
    between("FB_lever", (loc[0] + 0.16, loc[1] + 0.05, loc[2] + 0.3),
            (loc[0] + 0.26, loc[1] + 0.12, loc[2] + 0.5), 0.014, m_iron)

def bulbs(objs, p1, p2, n, acc_mat, r=0.04):
    """横撑小灯串: 暖白与饰色交替 (灯串语法)"""
    _, _, _, _, sph, between = kit(objs)
    p1, p2 = Vector(p1), Vector(p2)
    for k in range(n):
        t = (k + 0.5) / n
        p = p1.lerp(p2, t)
        seg = max((p2 - p1).length, 0.1)
        between("BulbWire", p1.lerp(p2, max(0.0, t - 0.18 / seg)),
                p.lerp(p2, 0.05), 0.006, m_iron)
        sph("Bulb", r, (p.x, p.y, p.z - 0.055),
            acc_mat if k % 2 else m_warm)

# ------------------------------------------------- A 牡丹发射架 (南瓜橙) ---
def build_A():
    objs = []
    box, cyl, tor, cone, sph, between = kit(objs)
    # 滑橇底座 + 甲板板条
    for sx in (-1.05, 1.05):
        box("A_runner", (2.6, 0.14, 0.1), (sx, 0, 0.05), (0, 0, 0), m_woodd)
    for k in range(5):
        box("A_plank", (2.4, 0.2, 0.05), (0, -0.55 + k * 0.28, 0.13), (0, 0, 0), m_wood)
    # A 字双榀 + 顶轴 (低矮宽三角)
    for sx in (-1.05, 1.05):
        between("A_legF", (sx, -0.62, 0.15), (sx * 0.42, -0.1, 1.42), 0.06, m_wood)
        between("A_legB", (sx, 0.62, 0.15), (sx * 0.42, -0.1, 1.42), 0.06, m_wood)
        between("A_brace", (sx * 0.66, -0.66, 0.62), (sx * 0.66, 0.66, 0.62), 0.03, m_iron)
    between("A_axle", (-1.0, -0.1, 1.42), (1.0, -0.1, 1.42), 0.04, m_iron)
    # 5 管扇形 (仰角 52°, 方位 ±8° 扇开): 亮钢炮管 + 双箍带, 管口橙环 = 型号识别
    import mathutils
    elev = radians(52)
    for k in range(5):
        az = (k - 2) * radians(8)
        tx = (k - 2) * 0.25
        cyl("A_tube", 0.15, 0.62, (tx, -0.12, 1.42), (elev, 0, az), m_metal, 12)
        q = mathutils.Euler((elev, 0, az), "XYZ").to_matrix()
        fwd = q @ Vector((0, 0, 1))
        base = Vector((tx, -0.12, 1.42))
        tor("A_ring", 0.115, 0.024, tuple(base + fwd * 0.34), (elev, 0, az), m_acc["A"])
        tor("A_band1", 0.165, 0.02, tuple(base + fwd * 0.2), (elev, 0, az), m_metald)
        tor("A_band2", 0.165, 0.02, tuple(base + fwd * 0.05), (elev, 0, az), m_metald)
        sph("A_fuse", 0.03, tuple(base - fwd * 0.33), m_warm)
    # 横撑灯串
    bulbs(objs, (-0.66, -0.66, 0.68), (0.66, -0.66, 0.68), 4, m_acc["A"])
    # 点火箱 + 弹药箱 + 南瓜灯 (脸朝 -Y 观察侧)
    fire_box(objs, (0.95, 0.42, 0.16), yaw=radians(-20))
    box("A_crate", (0.52, 0.5, 0.42), (-0.92, 0.42, 0.37), (0, 0, radians(8)), m_woodd)
    box("A_crate2", (0.36, 0.34, 0.26), (-0.88, 0.46, 0.72), (0, 0, radians(24)), m_wood)
    sph("A_pump", 0.2, (0.35, 0.62, 0.34), m_pump, scale=(1, 0.85, 0.78))
    cyl("A_stem", 0.025, 0.09, (0.35, 0.62, 0.56), (0, 0, 0), m_woodd, 6)
    box("A_eyeL", (0.055, 0.02, 0.06), (0.27, 0.46, 0.4), (0, 0, radians(15)), m_pumpf)
    box("A_eyeR", (0.055, 0.02, 0.06), (0.43, 0.46, 0.4), (0, 0, radians(-15)), m_pumpf)
    box("A_mouth", (0.14, 0.02, 0.05), (0.35, 0.46, 0.29), (0, 0, 0), m_pumpf)
    return objs

# --------------------------------------------------- B 垂柳塔 (暗夜紫) -----
def build_B():
    objs = []
    box, cyl, tor, cone, sph, between = kit(objs)
    # 四腿收分塔架 (地 ±0.85 -> 台 ±0.5 @2.3)
    g = 0.85; t = 0.5; H = 2.3
    for sx in (-1, 1):
        for sy in (-1, 1):
            between("B_leg", (sx * g, sy * g, 0.04), (sx * t, sy * t, H), 0.06, m_wood)
    # 两层 X 斜撑 (前后两立面)
    for zz in (0.75, 1.5):
        w = g + (t - g) * zz / H
        for sy in (-1, 1):
            between("B_x1", (-w, sy * w, zz), (w, sy * w, zz + 0.55), 0.028, m_iron)
            between("B_x2", (w, sy * w, zz), (-w, sy * w, zz + 0.55), 0.028, m_iron)
    # 平台 + 栏杆
    box("B_deck", (1.3, 1.3, 0.09), (0, 0, H + 0.045), (0, 0, 0), m_woodd)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cyl("B_post", 0.025, 0.3, (sx * 0.6, sy * 0.6, H + 0.24), (0, 0, 0), m_wood, 8)
    for sy in (-1, 1):
        between("B_rail", (-0.6, sy * 0.6, H + 0.36), (0.6, sy * 0.6, H + 0.36), 0.02, m_wood)
    for sx in (-1, 1):
        between("B_rail", (sx * 0.6, -0.6, H + 0.36), (sx * 0.6, 0.6, H + 0.36), 0.02, m_wood)
    # 单口粗臼炮: 加长炮身 + 口部外扩 + 双箍, 口内紫环 (型号识别)
    import mathutils
    elev = radians(76)
    cyl("B_mortar", 0.27, 0.88, (0, 0.1, H + 0.5), (elev, 0, 0), m_metal, 14)
    q = mathutils.Euler((elev, 0, 0), "XYZ").to_matrix()
    fwd = q @ Vector((0, 0, 1))
    base = Vector((0, 0.1, H + 0.5))
    tor("B_band1", 0.285, 0.026, tuple(base - fwd * 0.25), (elev, 0, 0), m_metald)
    tor("B_band2", 0.29, 0.026, tuple(base + fwd * 0.05), (elev, 0, 0), m_metald)
    cyl("B_lip", 0.32, 0.12, tuple(base + fwd * 0.42), (elev, 0, 0), m_metal, 14)
    tor("B_rim", 0.32, 0.024, tuple(base + fwd * 0.46), (elev, 0, 0), m_metald)
    tor("B_ring", 0.24, 0.03, tuple(base + fwd * 0.5), (elev, 0, 0), m_acc["B"])
    box("B_mount", (0.72, 0.72, 0.22), (0, 0.1, H + 0.24), (0, 0, 0), m_iron)
    # 檐角垂链灯笼 x4, 前角错落长链 (垂柳意象)
    for cx, cy, L in ((-0.6, -0.6, 0.72), (0.6, -0.6, 0.5), (-0.6, 0.6, 0.4), (0.6, 0.6, 0.4)):
        between("B_chain", (cx, cy, H + 0.34), (cx, cy, H + 0.34 - L), 0.011, m_iron)
        lz = H + 0.34 - L
        sph("B_lantern", 0.095, (cx, cy, lz - 0.11), m_acc["B"], scale=(1, 1, 1.2))
        cone("B_cap", 0.075, 0.08, (cx, cy, lz - 0.005), m_metald, 12)
    # 弯月徽 (前面板, 缺口偏右上宽开 = 新月, 暖象牙)
    mo = tor("B_moon", 0.22, 0.026, (0, -0.72, 1.35), (radians(90), 0, 0), m_moon)
    torus_gap(mo, 48, 60)
    objs.append(mo)
    # 塔脚: 木桶 x2 + 点火箱
    cyl("B_barrel", 0.26, 0.5, (-1.0, 0.35, 0.25), (0, 0, 0), m_woodd, 12)
    tor("B_bband", 0.265, 0.02, (-1.0, 0.35, 0.25), (0, 0, 0), m_iron)
    cyl("B_barrel2", 0.22, 0.42, (-0.85, -0.6, 0.21), (0, 0, 0), m_wood, 12)
    tor("B_bband2", 0.225, 0.02, (-0.85, -0.6, 0.21), (0, 0, 0), m_iron)
    fire_box(objs, (0.9, -0.55, 0.02), yaw=radians(15))
    return objs

# ------------------------------------------------- C 椰芯连环炮 (磷光绿) ---
def build_C():
    objs = []
    box, cyl, tor, cone, sph, between = kit(objs)
    # 车架: 甲板 + 侧缘 + 拽杆 + 支腿
    box("C_deck", (2.2, 1.1, 0.1), (0, 0, 0.6), (0, 0, 0), m_wood)
    box("C_railF", (2.2, 0.06, 0.12), (0, 0.52, 0.71), (0, 0, 0), m_woodd)
    box("C_railB", (2.2, 0.06, 0.12), (0, -0.52, 0.71), (0, 0, 0), m_woodd)
    for sy in (-1, 1):
        between("C_shaft", (1.05, sy * 0.28, 0.58), (1.95, sy * 0.34, 0.12), 0.035, m_wood)
        between("C_grip", (1.95, sy * 0.34, 0.12), (2.1, sy * 0.34, 0.3), 0.03, m_iron)
    cyl("C_leg", 0.04, 0.55, (-0.85, 0, 0.28), (0, 0, 0), m_wood, 8)
    # 大辐条轮 x2 (中央轮位) + 轮箍 + 毂盖
    for sy in (-1, 1):
        cy = sy * 0.62
        tor("C_felly", 0.4, 0.055, (-0.25, cy, 0.44), (radians(90), 0, 0), m_woodd)
        cyl("C_hub", 0.08, 0.12, (-0.25, cy, 0.44), (radians(90), 0, 0), m_iron, 10)
        sph("C_hubcap", 0.1, (-0.25, cy + sy * 0.06, 0.44), m_iron, scale=(1, 0.5, 1))
        for k in range(8):
            a = k * pi / 4
            between("C_spoke", (-0.25, cy, 0.44),
                    (-0.25, cy + 0.36 * cos(a), 0.44 + 0.36 * sin(a)), 0.018, m_wood)
    between("C_axle", (-0.25, -0.62, 0.44), (-0.25, 0.62, 0.44), 0.035, m_iron)
    # 转轮缸: 中轴立柱 + 6 管放射 (轴向仰 45°, 管间留缝) + 前后堵盘 + 尾部齿盘摇柄
    import mathutils
    elev = radians(45)
    pivot = Vector((-0.2, 0, 0.92))
    cyl("C_pivot", 0.09, 0.55, (pivot.x, pivot.y, pivot.z - 0.27), (0, 0, 0), m_iron, 10)
    q = mathutils.Euler((elev, 0, 0), "XYZ").to_matrix()
    fwd = q @ Vector((0, 0, 1))
    ux = q @ Vector((1, 0, 0))
    uy = q @ Vector((0, 1, 0))
    cyl("C_hubcyl", 0.12, 0.72, tuple(pivot + fwd * 0.12), (elev, 0, 0), m_metald, 12)
    tor("C_hband", 0.125, 0.022, tuple(pivot + fwd * 0.12), (elev, 0, 0), m_acc["C"])
    for k in range(6):
        a = k * pi / 3 + radians(30)
        off = ux * (cos(a) * 0.26) + uy * (sin(a) * 0.26)
        c = pivot + fwd * 0.2 + off
        cyl("C_tube", 0.075, 0.62, tuple(c), (elev, 0, 0), m_metal, 10)
        tor("C_ring", 0.062, 0.022, tuple(c + fwd * 0.31), (elev, 0, 0), m_acc["C"])
    cyl("C_plF", 0.3, 0.05, tuple(pivot + fwd * 0.36), (elev, 0, 0), m_metal, 14)
    cyl("C_plB", 0.3, 0.05, tuple(pivot - fwd * 0.16), (elev, 0, 0), m_metal, 14)
    # 尾部齿盘 + 径向销齿 + 摇柄 (机械机能读点)
    gc = pivot - fwd * 0.26
    cyl("C_gear", 0.2, 0.045, tuple(gc), (elev, 0, 0), m_metald, 16)
    for k in range(12):
        a = k * pi / 6
        r1, r2 = 0.2, 0.27
        between("C_pin", gc + (ux * cos(a) + uy * sin(a)) * r1,
                gc + (ux * cos(a) + uy * sin(a)) * r2, 0.02, m_metald)
    knob = gc + (ux * cos(0.9) + uy * sin(0.9)) * 0.24 - fwd * 0.1
    between("C_crank", gc - fwd * 0.02, knob, 0.014, m_iron)
    sph("C_knob", 0.05, tuple(knob - fwd * 0.03), m_warm)
    # 敞口弹药箱: 低墙敞箱, 3 发绿尖弹 proudly 露头 (型号识别)
    bx = 0.72
    box("C_crateF", (0.5, 0.06, 0.18), (bx, 0, 0.77), (0, 0, 0), m_woodd)
    for sy in (-1, 1):
        box("C_crateS", (0.06, 0.44, 0.18), (bx, sy * 0.22, 0.77), (0, 0, 0), m_woodd)
    for k, sy in enumerate((-0.12, 0.02, 0.16)):
        cyl("C_shell", 0.066, 0.2, (bx - 0.05 + k * 0.05, sy, 0.78), (radians(-12), 0, 0), m_metal, 10)
        cone("C_tip", 0.066, 0.12, (bx - 0.05 + k * 0.05, sy - 0.012, 0.94), m_acc["C"], 10)
    # 车尾标识灯杆 (绿球) + 点火箱
    cyl("C_pole", 0.02, 0.4, (-1.0, -0.4, 0.85), (0, 0, 0), m_iron, 8)
    sph("C_lamp", 0.07, (-1.0, -0.4, 1.08), m_acc["C"])
    fire_box(objs, (-0.95, 0.32, 0.66), yaw=radians(-90))
    return objs

# ----------------------------------------------------------------- 场景 ---
stations = {"A": build_A(), "B": build_B(), "C": build_C()}
POS = {"A": (-5.6, 0.0), "B": (0.0, 0.0), "C": (5.6, 0.0)}
for key, objs in stations.items():
    ox, oy = POS[key]
    for o in objs:
        o.location.x += ox
        o.location.y += oy

# 地台 + 夜色世界
add_box("Ground", (46, 30, 0.2), (0, 0, -0.1), (0, 0, 0), m_ground)
w = bpy.data.worlds.new("Night")
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = hex_lin(HEX["night"])
bg.inputs[1].default_value = 1.0
sc.world = w

def add_light(name, kind, loc, energy, color, size=None, target=None):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = hex_lin(color)[:3]
    if kind == "SUN":
        ld.angle = radians(4)
    if kind == "AREA" and size:
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = size
    ob = bpy.data.objects.new(name, ld)
    col.objects.link(ob)
    ob.location = loc
    if target:
        look_at(ob, target)
    return ob

add_light("MoonSun", "SUN", (-9, 7, 10), 1.4, "#b4c7ff", target=(0, 0, 0))
add_light("KeyWarm", "AREA", (2.5, -7.5, 4.6), 1500, HEX["warm"], size=(15, 3.2), target=(0, 0, 1.0))
add_light("FillCool", "AREA", (-1.5, -6.5, 3.6), 280, "#8FA3C8", size=(12, 2.5), target=(0, 0, 1))
add_light("RimViolet", "POINT", (0, 7.5, 3.2), 110, HEX["violet"])

# -------------------------------------------------------------- 相机/渲染 ---
def add_cam(name, loc, target, lens=45):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    ob = bpy.data.objects.new(name, cd)
    col.objects.link(ob)
    ob.location = loc
    look_at(ob, target)
    return ob

A, B, C = (Vector((POS[k][0], POS[k][1], 0)) for k in "ABC")
cams = [
    ("00_group", add_cam("cam_group", (1.5, -13.5, 3.4), (0, 0, 1.15), 32)),
    ("01_peony_rack", add_cam("cam_A", tuple(A + Vector((2.7, -3.3, 2.0))), (A.x, A.y, 0.95), 42)),
    ("02_willow_tower", add_cam("cam_B", tuple(B + Vector((3.4, -4.3, 1.9))), (B.x, B.y, 1.9), 34)),
    ("03_crossette_cart", add_cam("cam_C", tuple(C + Vector((2.8, -3.4, 1.9))), (C.x, C.y, 0.85), 42)),
    ("04_det_muzzles", add_cam("cam_dA", tuple(A + Vector((1.6, -2.0, 2.1))), (A.x - 0.1, A.y - 0.15, 1.55), 50)),
    ("05_det_lanterns", add_cam("cam_dB", tuple(B + Vector((1.9, -2.3, 2.9))), (B.x, B.y - 0.1, 2.35), 48)),
    ("06_det_rotary", add_cam("cam_dC", tuple(C + Vector((1.7, -2.0, 1.7))), (C.x - 0.2, C.y, 1.0), 50)),
]

try:
    sc.view_settings.view_transform = "Standard"
except Exception:
    pass

def brightness(path):
    import numpy as np
    img = bpy.data.images.load(str(path))
    w_, h_ = img.size
    px = np.empty(w_ * h_ * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    a = px.reshape(h_, w_, 4)
    mean = float(a[..., :3].mean())
    bpy.data.images.remove(img)
    return mean

PREV.mkdir(exist_ok=True)
sc.render.image_settings.file_format = "PNG"
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.render.resolution_percentage = 100

engine_ok = False
for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        sc.render.engine = eng
        try:
            sc.eevee.taa_render_samples = 64
        except Exception:
            pass
        engine_ok = True
        break
    except Exception:
        continue
if not engine_ok:
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    sc.cycles.device = "CPU"
print("ENGINE", sc.render.engine, flush=True)

failed = []
for name, cam in cams:
    sc.camera = cam
    sc.render.filepath = str(PREV / f"{name}.png")
    try:
        bpy.ops.render.render(write_still=True)
        mean = brightness(PREV / f"{name}.png")
        print(f"CHECK {name} mean={mean:.4f}", flush=True)
        if mean < 0.008:
            failed.append(name)
    except Exception as e:
        print(f"RENDER_FAIL {name} {type(e).__name__}: {str(e)[:120]}", flush=True)
        failed.append(name)

if failed and sc.render.engine != "CYCLES":
    print("FALLBACK_CYCLES", flush=True)
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    sc.cycles.device = "CPU"
    for name, cam in cams:
        if name not in failed:
            continue
        sc.camera = cam
        sc.render.filepath = str(PREV / f"{name}.png")
        try:
            bpy.ops.render.render(write_still=True)
            print(f"CHECK {name} mean={brightness(PREV / f'{name}.png'):.4f}", flush=True)
        except Exception as e:
            print(f"STILL_FAILED {name} {type(e).__name__}: {str(e)[:120]}", flush=True)

print("DONE preview ->", PREV, flush=True)
