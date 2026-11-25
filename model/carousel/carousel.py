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
    "velvet_2":  "#201936",
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
             coat=0.0, alpha=1.0, single=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    if single:
        # 封闭体单面导出 (glTF doubleSided=false): 只用于 Blender 图元 (球/柱/锥/环/盒) 拼成的封闭件;
        # 放样体 (马躯干/腿/尾) 与要看到内面的件 (屋面锥底 = 天花) 保持双面
        try:
            m.use_backface_culling = True
        except Exception:
            pass
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

def wedge(name, r0, r1, a0, a1, z0, z1, mat, arc=3):
    """扇形薄板 (封闭棱柱): 内缘直线弦, 外缘 arc 段折线。用于甲板放射木板 (bpy.data 直建, 不走 op)。"""
    pts = [(r0 * cos(a0), r0 * sin(a0))]
    pts += [(r1 * cos(a0 + (a1 - a0) * k / arc), r1 * sin(a0 + (a1 - a0) * k / arc)) for k in range(arc + 1)]
    pts.append((r0 * cos(a1), r0 * sin(a1)))
    bm = bmesh.new()
    bot = [bm.verts.new((x, y, z0)) for x, y in pts]
    top = [bm.verts.new((x, y, z1)) for x, y in pts]
    bm.faces.new(top)
    bm.faces.new(list(reversed(bot)))
    for k in range(len(pts)):
        k2 = (k + 1) % len(pts)
        bm.faces.new((bot[k], bot[k2], top[k2], top[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    me.materials.append(mat)
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


def _mesh_obj(name, bm, mat, loc=(0, 0, 0), smooth_sh=True):
    # bmesh -> 网格对象 (bpy.data 直建, 不走 op); 法线统一朝外
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    if mat:
        me.materials.append(mat)
    for poly in me.polygons:
        poly.use_smooth = smooth_sh
    return ob


def prism2d(name, pts2d, thick, mat, loc=(0, 0, 0), rot=(0, 0, 0)):
    # 薄棱片: XY 平面内的 (可凹) 多边形沿 Z 挤出 thick —— 招牌上的马首剪影用
    bm = bmesh.new()
    lo = [bm.verts.new((x, y, -thick / 2)) for x, y in pts2d]
    hi = [bm.verts.new((x, y, thick / 2)) for x, y in pts2d]
    caps = [bm.faces.new(lo), bm.faces.new(list(reversed(hi)))]
    bmesh.ops.triangulate(bm, faces=caps)
    for k in range(len(pts2d)):
        k2 = (k + 1) % len(pts2d)
        bm.faces.new((lo[k], lo[k2], hi[k2], hi[k]))
    ob = _mesh_obj(name, bm, mat, loc, smooth_sh=False)
    ob.rotation_euler = rot
    return ob


def swag(name, th0, th1, mat, z_top, d_seam, d_mid, r0, flare, fold,
         v0=0.0, v1=1.0, thick=0.0, nt=8, nv=4):
    # 波浪裙帘的一幅: 沿檐口从 th0 到 th1 的条带 (v 从挂点 0 到下缘 1).
    # 下缘在接缝处垂 d_seam、在瓣心垂 d_mid; 半径随 v 外扩 flare, 瓣心再外鼓 fold.
    # thick=0: 单层薄面 (配双面材质); thick>0: 封闭薄片 (鎏金描边用, 配单面材质).
    def row(vv, dr):
        out = []
        for i in range(nt + 1):
            u = i / nt
            th = th0 + (th1 - th0) * u
            sag = d_seam + (d_mid - d_seam) * sin(pi * u) ** 0.8
            rr = r0 + (flare + fold * sin(pi * u)) * vv + dr
            out.append((rr * cos(th), rr * sin(th), z_top - sag * vv))
        return out
    bm = bmesh.new()
    layers = []
    for dr in ((0.0,) if thick <= 0 else (0.0, -thick)):
        layers.append([[bm.verts.new(pt) for pt in row(v0 + (v1 - v0) * j / nv, dr)]
                       for j in range(nv + 1)])
    for grid in layers:
        for j in range(nv):
            for i in range(nt):
                bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    if thick > 0:
        a, b = layers
        for j in (0, nv):
            for i in range(nt):
                bm.faces.new((a[j][i], a[j][i + 1], b[j][i + 1], b[j][i]))
        for i in (0, nt):
            for j in range(nv):
                bm.faces.new((a[j][i], a[j + 1][i], b[j + 1][i], b[j][i]))
    return _mesh_obj(name, bm, mat)

def lobed(name, r, loc, mat, lobes=8, amp=0.07, sz=0.80, seg=32, ring=14):
    # 瓜体: 带瓣的扁球 (南瓜), bpy.data 直建
    bm = bmesh.new()
    top = bm.verts.new((0, 0, r * sz))
    rows = []
    for j in range(1, ring):
        ph = -pi / 2 + pi * j / ring
        row = []
        for i in range(seg):
            th = 2 * pi * i / seg
            rr = r * cos(ph) * (1 + amp * cos(lobes * th) * (0.35 + 0.65 * cos(ph) ** 2))
            row.append(bm.verts.new((rr * cos(th), rr * sin(th), r * sz * sin(ph))))
        rows.append(row)
    bot = bm.verts.new((0, 0, -r * sz))
    for i in range(seg):
        i2 = (i + 1) % seg
        bm.faces.new((top, rows[0][i2], rows[0][i]))
        bm.faces.new((bot, rows[-1][i], rows[-1][i2]))
    for j in range(len(rows) - 1):
        for i in range(seg):
            i2 = (i + 1) % seg
            bm.faces.new((rows[j][i], rows[j][i2], rows[j + 1][i2], rows[j + 1][i]))
    return _mesh_obj(name, bm, mat, loc)


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
# 夜里场景没有 environment map, 纯金属只剩点光高光 -> 鎏金读成深褐/黑 (2026-11-25 评审 H 组):
# 两种金各带自发光 (运行时随「装饰灯亮度」联动), metalness 略降留一点漫反射响应。
# single=True 见 make_mat。
m_metal    = make_mat("CR_Metal", HEX["metal"], rough=0.45, metal=0.85, single=True)
m_gold_br  = make_mat("CR_GoldBright", HEX["gold_br"], rough=0.28, metal=0.9,
                      emit=HEX["gold_br"], strength=0.55, single=True)
m_gold_dp  = make_mat("CR_GoldDeep", HEX["gold_deep"], rough=0.4, metal=0.8,
                      emit=HEX["gold_br"], strength=0.40, single=True)
m_iron     = make_mat("CR_Iron", HEX["iron"], rough=0.55, metal=0.8, single=True)
m_wood     = make_mat("CR_Wood", HEX["wood"], rough=0.85, single=True)
m_wood_d   = make_mat("CR_WoodDark", HEX["wood_d"], rough=0.85, single=True)
m_roof     = make_mat("CR_Roof", HEX["roof"], rough=0.88)                 # 双面: 锥底面就是天花
m_skirt    = make_mat("CR_Skirt", HEX["skirt"], rough=0.7, metal=0.2, single=True)
m_velvet   = make_mat("CR_Velvet", HEX["velvet"], rough=0.9, single=True)
m_velvet_d = make_mat("CR_VelvetDark", HEX["velvet_d"], rough=0.85, metal=0.05, single=True)
m_pain_o   = make_mat("CR_PaintOrange", HEX["pumpkin"], rough=0.5, single=True)
# 裙帘三色 (E 组, 用户定为契约色: 绒紫为主 + 每 3 幅 1 幅象牙, 鎏金描边; 南瓜橙只留给灯珠).
# 裙帘是单层薄面, 这三种材质保持双面 (CR_PaintIvory 的其余用户是封闭图元, 双面只多一点填充)
m_val_d    = make_mat("CR_ValanceDeep", HEX["velvet_2"], rough=0.92)
m_val_v    = make_mat("CR_ValanceViolet", HEX["velvet_d"], rough=0.88)
m_pain_i   = make_mat("CR_PaintIvory", HEX["ivory"], rough=0.6)
m_bulb     = make_mat("CR_WarmBulb", HEX["warm"], rough=0.4, emit=HEX["warm"], strength=2.6, single=True)
m_glow_v   = make_mat("CR_GlowViolet", HEX["violet_g"], rough=0.4, emit=HEX["violet_g"], strength=2.2, single=True)
m_glow_g   = make_mat("CR_GlowGold", HEX["gold_br"], rough=0.4, emit=HEX["gold_br"], strength=2.2, single=True)
m_spirit   = make_mat("CR_GlowSpirit", HEX["spirit"], rough=0.45, emit=HEX["spirit"], strength=1.5)
m_glow_p   = make_mat("CR_GlowPumpkin", HEX["pumpkin"], rough=0.4, emit=HEX["pumpkin"], strength=2.2, single=True)
m_blkt_p   = make_mat("CR_BlanketPumpkin", HEX["pumpkin"], rough=0.5, emit=HEX["pumpkin"], strength=1.2, single=True)
m_ghost    = make_mat("CR_GhostBody", HEX["spirit"], rough=0.5, emit=HEX["spirit"],
                      strength=0.1, alpha=0.66)
m_wisp     = make_mat("CR_Wisp", HEX["spirit"], rough=0.45, emit=HEX["spirit"],
                      strength=1.1, alpha=0.5)
m_ivory    = make_mat("CR_IvoryBody", HEX["ivory"], rough=0.42, coat=0.35,
                      emit=HEX["ivory"], strength=0.12)                 # 夜里读出象牙色而不是灰褐
m_gmane    = make_mat("CR_GoldMane", HEX["gold_br"], rough=0.35, metal=0.6,
                      emit=HEX["gold_br"], strength=0.9)
m_hoof     = make_mat("CR_Hoof", HEX["hoof"], rough=0.6, single=True)
m_eye_r    = make_mat("CR_EyeDark", HEX["eye_red"], rough=0.3, single=True)
m_eye_w    = make_mat("CR_EyeWarm", "#FFD9A0", rough=0.3, emit="#FFD9A0", strength=2.2, single=True)
m_pump     = make_mat("CR_PumpBody", HEX["pump_body"], rough=0.55)
m_vine     = make_mat("CR_Vine", HEX["vine"], rough=0.7, single=True)
m_pump_e   = make_mat("CR_PumpkinEmit", "#FF9A3B", rough=0.45, emit="#FF9A3B", strength=1.2, single=True)
m_pump_sh  = make_mat("CR_PumpkinShell", HEX["pumpkin"], rough=0.55, emit=HEX["pumpkin"], strength=0.22, single=True)
m_stone    = make_mat("CR_Stone", HEX["stone"], rough=0.9, single=True)
m_stone_d  = make_mat("CR_StoneDark", HEX["stone_d"], rough=0.92, single=True)
m_inlay    = make_mat("CR_InlayGold", HEX["gold"], rough=0.4, metal=0.6,
                      emit=HEX["gold"], strength=1.0, single=True)
# B 组 (甲板): 放射木板的浅色档 + 三灵灵光池 (贴地圆盘, 低强度自发光)
m_wood_l   = make_mat("CR_WoodLight", "#5C4636", rough=0.85, single=True)
m_pool_s   = make_mat("CR_PoolSpirit", HEX["spirit"], rough=0.6, emit=HEX["spirit"], strength=0.45, single=True)
m_pool_g   = make_mat("CR_PoolGold", HEX["gold"], rough=0.6, emit=HEX["gold"], strength=0.45, single=True)
m_pool_p   = make_mat("CR_PoolPumpkin", HEX["pumpkin"], rough=0.6, emit=HEX["pumpkin"], strength=0.45, single=True)

# ================================ 静态场地 ==================================
# 预览地面盘 (导出前移除, app 侧地面由 park_env 提供)
m_ground = make_mat("CR_GroundPreview", HEX["ground"], rough=0.95)
add_cyl("CR_GroundPreview", 42, 0.1, (0, 0, -0.05), mat=m_ground, verts=48)

# 铺装 (venue pavement, 属于设施的一部分)
add_cyl("CR_Pave", 12.6, 0.16, (0, 0, -0.04), mat=m_stone_d, verts=64)
# 入口星徽 (G 组, 2026-11-25 重做): 法阵环 + 八向星芒, 铺在入口走廊的地面上.
# 旧版圆心在 r9.6 —— 78.7% 的面积压在最下一级台阶 (r9.34-10.0) 下面, 只剩一道金弧;
# 辐条从 0.31m 起画、外端还穿出环外 8cm。新版圆心 r11.1: 台阶外缘 (10.0) 与地灯环 (11.9, 此处是
# 它的入口缺口) 之间, 辐条从芯 (r0.13) 接到环内 (r0.70)。
sx, sy = 11.1 * DIR_E[0], 11.1 * DIR_E[1]
add_torus("CR_StarRing", 0.85, 0.022, (sx, sy, 0.045), mat=m_inlay, ms=48, ns=6)
for k in range(8):
    a = k * pi / 4 + pi / 8
    add_box(f"CR_StarSpoke{k}", (0.58, 0.045, 0.018),
            (sx + 0.41 * cos(a), sy + 0.41 * sin(a), 0.045),
            rot=(0, 0, a), mat=m_inlay)
add_cyl("CR_StarCore", 0.13, 0.02, (sx, sy, 0.046), mat=m_inlay, verts=20)

# 入口台阶 (三级: 0.155/0.31/0.465, 顶接平台 0.62, 面向入口方位)
for k, (rr, h) in enumerate(((8.33, 0.465), (9.0, 0.31), (9.67, 0.155))):
    add_box(f"CR_Step{k}", (0.67, 2.8, h), (rr * DIR_E[0], rr * DIR_E[1], h / 2),
            rot=(0, 0, E), mat=m_stone)
    # 踏步前缘灯边 (G 组): 旧版台阶是暗灰压在黑铺装上, 入口主路看不清级高
    nr_ = rr + 0.305
    add_box(f"CR_StepNose{k}", (0.05, 2.8, 0.016), (nr_ * DIR_E[0], nr_ * DIR_E[1], h - 0.002),
            rot=(0, 0, E), mat=m_inlay)
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

# 排队围栏 r10.7: 立柱 12° 一根, 入口 ±15° 断开; 双层横杆接到缺口两端的两根立柱 (180° / 228°) 上.
# (G 组) 旧版横杆 64 段、缺口按 ±14° 删点, 实际断在 185.6° / 219.4°: 一端越过 180° 柱外伸 1.05m,
# 另一端离 228° 柱还差 1.61m。现在 120 段 (3° 一格, 立柱方位都在格点上), 删 (181°, 227°) 区间的点.
FR = 10.7
for k in range(30):
    th = k * pi / 15
    if ang_diff(th, E) < radians(15):
        continue
    px, py = FR * cos(th), FR * sin(th)
    add_cyl(f"CR_FencePost{k}", 0.04, 0.92, (px, py, 0.46), mat=m_gold_dp, verts=8)
    add_sphere(f"CR_FenceTop{k}", 0.065, (px, py, 0.96), mat=m_bulb, seg=10, ring=6)
torus_gap(add_torus("CR_FenceRail1", FR, 0.028, (0, 0, 0.55), mat=m_wood_d, ms=120, ns=6),
          23, degrees(E) + 2)
torus_gap(add_torus("CR_FenceRail2", FR, 0.028, (0, 0, 0.80), mat=m_wood_d, ms=120, ns=6),
          23, degrees(E) + 2)

# 断弧地灯环
torus_gap(add_torus("CR_GroundRing", 11.9, 0.05, (0, 0, 0.05), mat=m_bulb, ms=72, ns=6),
          18, degrees(E))

# 入口新月招牌 (G 组, 2026-11-25 重做): 旧版板宽 2.2m 横在入口轴正中、两柱相距 5.16m, 板端离柱 1.44m
# 且没有任何连接 (悬空); 从入口轴 12-24m 看正好压住中柱。
# 新版: 两根灯柱保留当门柱 (加高到 3.1m), 招牌板缩成 2.0x0.72 挂在右柱 (方位 E+12°, 来路玩家的右手)
# 外侧的挑臂上, 板面朝来路 —— 入口轴的视线完全让开; 双面同图: 新月星徽 + 三灵剪影
# (幽灵 = 三簇灵火 / 象牙 = 马首 / 南瓜 = 带瓣小瓜), 全部程序化几何, 不造字体。
POST_R, POST_A, POST_H = 12.4, 12.0, 3.10
SIGN_W, SIGN_H, SIGN_T, SIGN_Z, ARM_Z = 2.0, 0.72, 0.08, 2.62, 3.02
_s_t = Vector((-sin(E), cos(E), 0))        # 切向, 指向方位增大一侧 (= 来路玩家的右手)
_s_r = Vector((DIR_E[0], DIR_E[1], 0))     # 径向朝外 (朝来路)
HORSE_HEAD = [(-0.22, -0.50), (0.14, -0.50),              # 颈根
              (0.20, -0.20), (0.26, -0.02),              # 咽喉上行
              (0.40, 0.00), (0.50, 0.02), (0.52, 0.10),   # 颌下 -> 鼻尖 (朝右)
              (0.44, 0.16),                              # 上唇
              (0.26, 0.24), (0.10, 0.34),                # 鼻梁 -> 额
              (0.09, 0.50), (0.03, 0.40),                # 前耳
              (-0.03, 0.54), (-0.08, 0.40),              # 后耳 -> 项
              (-0.20, 0.22), (-0.26, 0.00)]              # 颈嵴
post_xy = {}
for sgn in (-1, 1):
    a = E + sgn * radians(POST_A)
    px, py = POST_R * cos(a), POST_R * sin(a)
    post_xy[sgn] = Vector((px, py, 0))
    add_cyl(f"CR_SignPost{sgn}", 0.06, POST_H, (px, py, POST_H / 2), mat=m_gold_dp, verts=10)
    add_sphere(f"CR_SignPostTop{sgn}", 0.08, (px, py, POST_H + 0.04), mat=m_bulb, seg=10, ring=6)
# 板心: 与右柱同一径向深度, 从柱外侧 0.12m 起向走廊外挂
_bc = _s_r * (POST_R * cos(radians(POST_A))) + _s_t * (POST_R * sin(radians(POST_A)) + 0.12 + SIGN_W / 2)
_bc.z = SIGN_Z
add_box("CR_SignBoard", (SIGN_T, SIGN_W, SIGN_H), _bc, rot=(0, 0, E), mat=m_velvet_d)
for tag, dz in (("T", SIGN_H / 2 - 0.0175), ("B", -SIGN_H / 2 + 0.0175)):
    add_box(f"CR_SignTrim{tag}", (SIGN_T + 0.012, SIGN_W, 0.035), _bc + Vector((0, 0, dz)),
            rot=(0, 0, E), mat=m_glow_g)
# 挑臂 + 两根吊杆 + 斜撑: 板与柱实心相连
_pp = post_xy[1]
_a0 = _pp + Vector((0, 0, ARM_Z))
_a1 = Vector((_bc.x, _bc.y, ARM_Z)) + _s_t * (SIGN_W / 2 - 0.04)
cyl_between("CR_SignArm", _a0, _a1, 0.03, m_gold_dp, verts=8)
cyl_between("CR_SignBrace", _pp + Vector((0, 0, 2.26)), _a0.lerp(_a1, 0.55), 0.022, m_gold_dp, verts=8)
for li, u in enumerate((-SIGN_W / 2 + 0.08, SIGN_W / 2 - 0.08)):
    cyl_between(f"CR_SignLink{li}", _bc + _s_t * u + Vector((0, 0, SIGN_H / 2 - 0.03)),
                _bc + _s_t * u + Vector((0, 0, ARM_Z)), 0.014, m_gold_dp, verts=6)
add_sphere("CR_SignArmTip", 0.05, _a1 + _s_t * 0.06, m_gold_br, seg=10, ring=8)
# 板面图样 (双面): 新月星徽 + 三枚圆牌
for face in (1, -1):                       # +1 = 朝来路的正面; -1 = 背面 (图样左右镜像, 读者都从左读到右)
    tag = "F" if face > 0 else "B"
    nrm = _s_r * face
    rot_p = (radians(90), 0, E + face * pi / 2)   # 本地 X = 该面读者的右方, 本地 Y = 上, 本地 Z = 外法向

    def SP(u, v, w=0.0, _f=face, _n=nrm):
        return _bc + _s_t * (_f * u) + Vector((0, 0, v)) + _n * w

    w0 = SIGN_T / 2
    moon = add_torus(f"CR_SignMoon{tag}", 0.17, 0.045, SP(-0.70, -0.02, w0 + 0.03), rot=rot_p,
                     mat=m_glow_g, ms=32, ns=6)
    torus_gap(moon, 70, 90)                # 开口朝上
    add_sphere(f"CR_SignStar{tag}", 0.05, SP(-0.70, 0.235, w0 + 0.03), mat=m_bulb, seg=10, ring=6,
               scale=(0.5, 0.5, 1.3))
    for mi, (u, kind) in enumerate(((-0.196, "ghost"), (0.274, "ivory"), (0.744, "pumpkin"))):
        add_cyl(f"CR_SignMedal{tag}{mi}", 0.20, 0.035, SP(u, 0, w0 + 0.008), rot=rot_p, mat=m_velvet, verts=24)
        add_torus(f"CR_SignMedalRing{tag}{mi}", 0.20, 0.016, SP(u, 0, w0 + 0.03), rot=rot_p,
                  mat=m_gold_br, ms=28, ns=6)
        if kind == "ghost":
            for j, (du, hh, rr_) in enumerate(((-0.078, 0.13, 0.040), (0.0, 0.21, 0.052), (0.078, 0.12, 0.038))):
                add_cone(f"CR_SignFlame{tag}{j}", rr_, hh, SP(u + du, -0.115 + hh / 2, w0 + 0.034),
                         mat=m_spirit, verts=8, r2=0.004)
        elif kind == "ivory":
            prism2d(f"CR_SignHorse{tag}", [(x * 0.30, y * 0.30) for x, y in HORSE_HEAD], 0.014, m_pain_i,
                    SP(u, 0.0, w0 + 0.034), rot_p)
        else:
            lobed(f"CR_SignPump{tag}", 0.092, SP(u, -0.012, w0 + 0.012), m_pump_sh, lobes=8, amp=0.09, sz=0.80)
            add_cyl(f"CR_SignPumpStem{tag}", 0.012, 0.05, SP(u, 0.084, w0 + 0.012), mat=m_vine, verts=6)

# 盘心祭坛 + 南瓜灯 (L 组, 2026-11-26): 评审指出全园 11 个打卡点没有一个在木马上, 上盘没有「上来的理由」。
# 中柱脚下加一圈静止的矮坛 (不随盘转, 中柱在坛心里转), 坛沿朝入口一侧供一盏雕脸南瓜灯 = 第 12 个打卡点
# (colliders.json 的 pumpkin_carousel, 由 scripts/patch_carousel_colliders.mjs 写入; 坛体碰撞圆 r0.98 h1.08)。
ALT = {"r": 0.98, "top": 1.08}
add_cyl("CR_Altar", ALT["r"], ALT["top"] - DECK, (0, 0, (ALT["top"] + DECK) / 2), mat=m_velvet_d, verts=16)
add_torus("CR_AltarRim", ALT["r"], 0.03, (0, 0, ALT["top"]), mat=m_inlay, ms=48, ns=6)
_apx, _apy = 0.78 * DIR_E[0], 0.78 * DIR_E[1]            # 南瓜灯位置 (朝入口一侧)
add_torus("CR_AltarHalo", 0.27, 0.012, (_apx, _apy, ALT["top"] + 0.006), mat=m_pump_e, ms=32, ns=6)
lobed("CR_AltarPumpkin", 0.22, (_apx, _apy, ALT["top"] + 0.172), m_pump_sh, lobes=8, amp=0.08, sz=0.80)
add_cyl("CR_AltarStem", 0.018, 0.09, (_apx + 0.02 * DIR_E[0], _apy + 0.02 * DIR_E[1], ALT["top"] + 0.37),
        mat=m_vine, verts=6)
# 雕脸 (朝入口): 两只斜挑的「凶」眼 + 一道笑
for sgn in (-1, 1):
    eye = add_sphere(f"CR_AltarEye{sgn}", 1.0,
                     (_apx + 0.225 * DIR_E[0] + sgn * 0.085 * -sin(E),
                      _apy + 0.225 * DIR_E[1] + sgn * 0.085 * cos(E), ALT["top"] + 0.225),
                     m_pump_e, seg=12, ring=8, scale=(0.03, 0.062, 0.034))
    eye.rotation_euler = (radians(-16) * sgn, 0, E)       # 薄轴 = 板面法向, 长轴顺切向并斜挑
smile = add_torus("CR_AltarSmile", 0.085, 0.018,
                  (_apx + 0.225 * DIR_E[0], _apy + 0.225 * DIR_E[1], ALT["top"] + 0.135),
                  rot=(radians(90), 0, E + pi / 2), mat=m_pump_e, ms=28, ns=6)
torus_gap(smile, 70, 90)                                 # 开口朝上 = 笑

# ================================ 机台 CR_Spin ==============================
spin = add_empty("CR_Spin", (0, 0, 0))
link_col(spin, col_spin)

def S(ob):
    ob.parent = spin   # 直接挂根: 子物体 location 即 spin 本地坐标 (spin 在原点无旋转)
    return ob

# 平台甲板 (B 组, 2026-11-25 重做): 底盘 + 36 扇放射木板 (深浅交替, 0.5° 暗缝) + 发光鎏金唇缘。
# 旧版是一块单色平盘加两片「木纹内环」薄盘, 夜里读成黑地板。
S(add_cyl("CR_Deck", P["platform_r"], 0.18, (0, 0, DECK - 0.09), mat=m_wood, verts=64))
for k in range(36):
    a0 = k * pi / 18 + radians(0.25)
    a1 = (k + 1) * pi / 18 - radians(0.25)
    S(wedge(f"CR_Plank{k}", 0.62, 7.88, a0, a1, DECK, DECK + 0.012, m_wood_l if k % 2 else m_wood))
S(add_torus("CR_DeckRim", 7.95, 0.055, (0, 0, DECK), mat=m_inlay, ms=96, ns=8))
# 裙板 + 裙顶暖光灯带
S(add_cone("CR_Skirt", 7.15, 0.44, (0, 0, 0.22), mat=m_skirt, verts=64, r2=7.92))
S(add_torus("CR_SkirtGlow", 7.9, 0.04, (0, 0, 0.445), mat=m_bulb, ms=72, ns=6))
# 甲板法阵 (B 组): 契约 THESIS「鎏金法阵召回灵兽」—— 十个骑乘位就是十芒星的十个角:
# 星形 {10/3} 的顶点落在铜杆脚下 (由甲板套管当角饰), 外环 r7.3 / 灵兽环 r6.2 / 内环 r5.0, 36 道刻线。
# 旧版只有一条 r4.3 金线加 10 颗点。全部挂 CR_Spin。
MC_Z = DECK + 0.04
for nm, rr, ms_ in (("CR_McOuter", 7.3, 96), ("CR_McRide", RIDE_R, 80), ("CR_McInner", 5.0, 72)):
    S(add_torus(nm, rr, 0.03 if nm != "CR_McRide" else 0.022, (0, 0, MC_Z), mat=m_inlay, ms=ms_, ns=6))
for i in range(P["rides"]):
    th1 = E + i * 2 * pi / P["rides"]
    th2 = E + (i + 3) * 2 * pi / P["rides"]
    S(cyl_between(f"CR_McStar{i}", (RIDE_R * cos(th1), RIDE_R * sin(th1), MC_Z),
                  (RIDE_R * cos(th2), RIDE_R * sin(th2), MC_Z), 0.03, m_inlay, verts=6))
for k in range(36):
    th = E + k * pi / 18
    S(add_box(f"CR_McTick{k}", (0.22, 0.05, 0.03), (7.62 * cos(th), 7.62 * sin(th), MC_Z),
              rot=(0, 0, th), mat=m_inlay))

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
S(add_cone("CR_Roof", P["roof_r"], P["roof_h"], (0, 0, roof_z), mat=m_roof, verts=64))
# 天花 (A 组, 2026-11-25 重做): 旧版是一整块 r7.2 自发光盘 (CR_CanopyGlow) —— 资产里最大最亮的面,
# 默认辉光下仰视 68% 画面近白, 而盘下其实没有照明设计。现在天花 = 屋面锥的平底 (绒紫, 不发光),
# 下面挂「鎏金轮盘」内饰 + 3 盏吊灯; 真正照亮灵兽的是吊灯里的点光 (运行时, 见 carousel.js CANOPY_LIGHTS)。
CEIL_Z = P["canopy_z"] - 0.045          # 内饰高度: 锥底 5.60 之下, 与杆帽 (5.50–5.62) 同层不冲突
for k in range(12):                      # 内肋 12 根: 与屋面外肋同方位, 微发光鎏金 (契约「鎏金肋骨」盘内可见)
    th = k * pi / 6 + 0.26
    S(cyl_between(f"CR_CeilRib{k}", (0.95 * cos(th), 0.95 * sin(th), CEIL_Z),
                  (9.28 * cos(th), 9.28 * sin(th), CEIL_Z), 0.035, m_inlay, verts=6))
for i, rr in enumerate((3.0, 5.6, 8.9)):  # 三道金环
    S(add_torus(f"CR_CeilRing{i}", rr, 0.03, (0, 0, CEIL_Z), mat=m_inlay, ms=64 if rr < 8 else 72, ns=6))
S(add_torus("CR_CeilHalo", 1.25, 0.035, (0, 0, CEIL_Z), mat=m_inlay, ms=48, ns=6))    # 柱头光环
for i in range(P["rides"]):              # 十位星图: 每个骑乘位正上方一枚四芒星 (r4.3) + 一颗灯珠 (r7.4)
    th = E + i * 2 * pi / P["rides"]
    S(add_box(f"CR_CeilStar{2 * i}", (0.36, 0.05, 0.02), (4.3 * cos(th), 4.3 * sin(th), CEIL_Z),
              rot=(0, 0, th), mat=m_bulb))
    S(add_box(f"CR_CeilStar{2 * i + 1}", (0.05, 0.36, 0.02), (4.3 * cos(th), 4.3 * sin(th), CEIL_Z),
              rot=(0, 0, th), mat=m_bulb))
    S(add_sphere(f"CR_CeilDot{i}", 0.07, (7.4 * cos(th), 7.4 * sin(th), CEIL_Z), m_bulb, seg=10, ring=6))

# 吊灯 x3: 挂在天花下 (方位 E+18+120k —— 落在铜杆之间, r5.8 马环上方偏内): 黄铜吊杆 + 灯帽 + 暖光灯球。
# 灯球最低点 4.62m, 远高于马耳 3.05 / 骑坐眼 2.86。运行时的 3 盏点光放在灯球心, 与灯同挂 CR_Spin 随屋面转。
LAMP = {"r": 5.8, "az0": P["entrance_deg"] + 18.0, "globe_z": 4.88}
for k in range(3):
    th = radians(LAMP["az0"] + k * 120.0)
    lx, ly = LAMP["r"] * cos(th), LAMP["r"] * sin(th)
    S(add_cyl(f"CR_LampStem{k}", 0.015, P["canopy_z"] - 5.02, (lx, ly, (P["canopy_z"] + 5.02) / 2),
              mat=m_gold_dp, verts=6))
    S(add_cone(f"CR_LampCap{k}", 0.13, 0.09, (lx, ly, 5.03), mat=m_gold_dp, verts=12, r2=0.03))
    S(add_sphere(f"CR_LampGlobe{k}", 0.17, (lx, ly, LAMP["globe_z"]), m_bulb, seg=16, ring=10))
    S(add_cone(f"CR_LampDrop{k}", 0.035, 0.10, (lx, ly, LAMP["globe_z"] - 0.21), mat=m_gold_dp, verts=8,
               rot=(pi, 0, 0)))
# 屋面 (E 组, 2026-11-25): 旧版 12 根肋的轴心贴着锥面 —— 上段大半埋进锥体 (埋深最多 5.2cm / 肋半径
# 5.5cm), 只有靠檐口的下端露出来; 屋面没有任何别的东西, 从摩天轮顶 / 缠魂塔看下来是一个黑盘。
# 现在肋轴沿锥面外法向抬 0.03m (嵌 45% 露 55%), 改用微发光的 CR_InlayGold; 加两道同心金环 (压扁的环面)。


def cone_z(r):
    return roof_z + P["roof_h"] / 2 - (P["roof_h"] / P["roof_r"]) * r      # 锥面在半径 r 处的高度


_nr, _nz = 0.2814, 0.9596                       # 锥面外法向的 (径向, 竖向) 分量
for k in range(12):
    th = k * pi / 6 + 0.26
    S(cyl_between(f"CR_RoofRib{k}",
                  ((0.85 + 0.03 * _nr) * cos(th), (0.85 + 0.03 * _nr) * sin(th), cone_z(0.85) + 0.03 * _nz),
                  ((9.28 + 0.03 * _nr) * cos(th), (9.28 + 0.03 * _nr) * sin(th), cone_z(9.28) + 0.03 * _nz),
                  0.06, m_inlay, verts=8))
for i, rr in enumerate((3.2, 6.4)):
    S(add_torus(f"CR_RoofRing{i}", rr, 0.05, (0, 0, cone_z(rr) + 0.012), mat=m_inlay, ms=80, ns=8,
                scale=(1, 1, 0.4)))
S(add_torus("CR_RoofRim", 9.35, 0.07, (0, 0, P["canopy_z"] + 0.06), mat=m_gold_br, ms=72, ns=8))

# 波浪裙边 (E 组, 2026-11-25 重做; 配色用户定为契约色): 旧版是 36 颗紫/橙/象牙轮换的离散椭球「糖豆」
# (相邻两瓣互穿 10.5cm, 读起来偏儿童乐园)。新版: 36 幅连续垂幔, 每 3 幅 = 象牙 1 幅 + 深绒紫 1 幅 +
# 绒紫 1 幅 (南瓜橙只留给灯珠), 下缘一道鎏金描边, 每幅最低点挂一颗暖光灯珠 —— 灯串跟着波浪走。
NS = 36
VAL = {"z_top": P["canopy_z"] - 0.04, "d_seam": 0.26, "d_mid": 0.66, "r0": 9.16, "flare": 0.13, "fold": 0.03}
for k in range(NS):
    th0, th1 = k * 2 * pi / NS, (k + 1) * 2 * pi / NS
    mat = (m_pain_i, m_val_d, m_val_v)[k % 3]
    S(swag(f"CR_Scallop{k}", th0, th1, mat, VAL["z_top"], VAL["d_seam"], VAL["d_mid"],
           VAL["r0"], VAL["flare"], VAL["fold"]))
    S(swag(f"CR_ScallopTrim{k}", th0, th1, m_inlay, VAL["z_top"], VAL["d_seam"], VAL["d_mid"],
           VAL["r0"], VAL["flare"], VAL["fold"], v0=0.90, v1=1.0, thick=0.014, nv=1))
    thm = 0.5 * (th0 + th1)
    S(add_sphere(f"CR_ValanceBulb{k}", 0.075,
                 ((VAL["r0"] + VAL["flare"] + VAL["fold"]) * cos(thm),
                  (VAL["r0"] + VAL["flare"] + VAL["fold"]) * sin(thm),
                  VAL["z_top"] - VAL["d_mid"] - 0.075), mat=m_bulb, seg=10, ring=6))
S(add_torus("CR_ScallopRod", 9.15, 0.02, (0, 0, P["canopy_z"] - 0.02), mat=m_gold_br, ms=96, ns=6))

# ============================ 新月星芒顶饰 (F 组, 2026-11-25 重做) ============================
# 旧版: 圆环弧月亮 R0.58 —— 眼高平视约 20m 内被自家檐口 (R9.35 @ z5.66) 挡死; 且没挂到旋转根下
# (杆/星/珠转、月不转); 星离最近件 0.43m 悬空。
# 新版: 实心渐缩月牙 (沿竖直圆弧扫掠椭圆截面, 角尖收点; 侧看是渐窄的刃, 不会消失) + 月牙口里一枚
# 立体星芒 (三轴六芒) + 月背三颗灵珠。全部挂 CR_Spin 随屋面转。
# 月心 z10.39: 月背底 8.85 / 角尖 10.95 / 星顶 11.64。眼高 1.65m 平视时檐口视线在轴上的高度
# = 1.65 + 4.01·D/(D−9.35) → 约 17m 露星、19m 露上半轮、21m 整轮可见 (旧版 20m 内全挡)。
def crescent(name, R, horn_deg, rad, lat, mat, steps=56, seg=14):
    """实心新月: 沿竖直圆弧 (本地 XZ 平面, 圆心在原点) 扫掠一个渐缩椭圆截面。
    截面 = 径向半厚 rad × 侧向半宽 lat, 从弧底渐缩到两个角尖的 0 (角尖在水平线以上 horn_deg)。"""
    bm = bmesh.new()
    half = radians(90 + horn_deg)                 # 弧底到角尖的半角
    rows = []
    for i in range(steps + 1):
        a = -pi / 2 - half + 2 * half * i / steps  # 弧角: 从一侧角尖经弧底到另一侧角尖
        da = abs(a + pi / 2) / half                # 0 = 弧底, 1 = 角尖
        s_ = (1 - da * da) ** 0.6 if da < 1 else 0.0
        if s_ < 1e-4:
            rows.append([bm.verts.new((R * cos(a), 0.0, R * sin(a)))])
            continue
        n = Vector((cos(a), 0.0, sin(a)))         # 径向 (弧的法向)
        row = []
        for k in range(seg):
            t = 2 * pi * k / seg
            v = n * (R + rad * s_ * cos(t)) + Vector((0.0, lat * s_ * sin(t), 0.0))
            row.append(bm.verts.new(v))
        rows.append(row)
    for i in range(steps):
        r0, r1 = rows[i], rows[i + 1]
        for k in range(seg):
            k2 = (k + 1) % seg
            if len(r0) == 1:
                bm.faces.new((r0[0], r1[k2], r1[k]))
            elif len(r1) == 1:
                bm.faces.new((r0[k], r0[k2], r1[0]))
            else:
                bm.faces.new((r0[k], r0[k2], r1[k2], r1[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    me.materials.append(mat)
    for poly in me.polygons:
        poly.use_smooth = True
    return ob

FIN = {"moon_z": 10.39, "R": 1.20, "horn_deg": 28.0, "rad": 0.34, "lat": 0.26,   # 月: 底 8.85, 角尖 ±1.06 @ z+0.56
       "star_z": 0.75, "face_deg": P["entrance_deg"]}                            # 星心相对月心
mz = FIN["moon_z"]
S(cyl_between("CR_FinialRod", (0, 0, roof_z + P["roof_h"] / 2 - 0.1), (0, 0, mz - 1.15), 0.06, m_gold_dp, verts=10))
moon = crescent("CR_FinialMoon", FIN["R"], FIN["horn_deg"], FIN["rad"], FIN["lat"], m_glow_g)
moon.location = (0, 0, mz)
moon.rotation_euler = (0, 0, radians(FIN["face_deg"]) - pi / 2)    # 月牙面法线 = 本地 +Y → 转到入口方向
S(moon)
# 星芒: 三轴六根锥刺 (竖长横短) + 中心珠, 从细杆上「长」在月牙口里
sz = mz + FIN["star_z"]
S(cyl_between("CR_FinialPin", (0, 0, mz - FIN["R"] + FIN["rad"] - 0.05), (0, 0, sz), 0.02, m_gold_dp, verts=6))
S(add_sphere("CR_FinialStarCore", 0.13, (0, 0, sz), m_bulb, seg=10, ring=8))
for tag, L, loc, rot in (
        ("Up", 0.50, (0, 0, sz + 0.25), (0, 0, 0)), ("Dn", 0.40, (0, 0, sz - 0.20), (pi, 0, 0)),
        ("Xp", 0.45, (0.225, 0, sz), (0, pi / 2, 0)), ("Xn", 0.45, (-0.225, 0, sz), (0, -pi / 2, 0)),
        ("Yp", 0.30, (0, 0.15, sz), (-pi / 2, 0, 0)), ("Yn", 0.30, (0, -0.15, sz), (pi / 2, 0, 0))):
    S(add_cone(f"CR_FinialStar{tag}", 0.085, L, loc, mat=m_bulb, verts=6, rot=rot))

# 灵珠 x3: 镶在月背外缘 (弧底与 ±38°), 埋进月背 —— 实心连接, 不悬空
_half = radians(90 + FIN["horn_deg"])
_fa = radians(FIN["face_deg"]) - pi / 2
for k, adeg in enumerate((-128.0, -90.0, -52.0)):
    a = radians(adeg)
    da = abs(a + pi / 2) / _half
    rr = FIN["R"] + FIN["rad"] * (1 - da * da) ** 0.6 * 0.92
    S(add_sphere(f"CR_FinialOrb{k}", 0.075,
                 (rr * cos(a) * cos(_fa), rr * cos(a) * sin(_fa), mz + rr * sin(a)),
                 mat=m_spirit, seg=10, ring=8))

# 铜杆: 10 根 (甲板套管 -> 顶棚), 杆顶固定环
for i in range(P["rides"]):
    th = E + i * 2 * pi / P["rides"]
    px, py = RIDE_R * cos(th), RIDE_R * sin(th)
    S(add_cyl(f"CR_Pole{i}", 0.055, 4.75, (px, py, DECK + 2.5), mat=m_gold_br, verts=10))
    S(add_cyl(f"CR_PoleCap{i}", 0.1, 0.12, (px, py, P["canopy_z"] - 0.04), mat=m_gold_dp, verts=10))
    # 甲板套管 (旧版注释写了但没建: 铜杆下端离台面 12.5cm 是一截悬空杆头); 兼作十芒星的角饰
    S(add_cyl(f"CR_PoleSock{i}", 0.115, 0.16, (px, py, DECK + 0.08), mat=m_gold_dp, verts=12))
    S(add_torus(f"CR_PoleSockRing{i}", 0.115, 0.02, (px, py, DECK + 0.16), mat=m_gold_br, ms=16, ns=6))

# ================================ 骑乘位 ====================================
def child(root, ob):
    ob.parent = root   # 无补偿挂父: ob.location 即 root 本地坐标
    return ob

# ---------------- 马体: 放样建模 (C 组, 2026-11-25 深改) ----------------
# 旧版: 躯干+颈+头一体放样 —— 脖子是等粗管子、头只有 0.5m 且没有颊颌 (读成玩具恐龙), 腿是插上去的
# 细管, 尾巴是带球的火柴棍, 三灵共用同一网格只换漆, 肚带环离身 7-11cm。
# 新版: 颈+躯干一体放样 (颈有嵴、颈基深 0.58m), 头单独放样 (长 0.64m、带颊颌、鼻梁收窄、鼻尖朝前下
# 38 度) 埋进颈顶; 腿 7 关节渐变 (上粗/膝细/球节隆起) + 肩/臀/上肢肌肉体, 蹄沿腿端切向; 尾改多股;
# 三灵各有轮廓件: 象牙 = 鎏金卷草鬃 + 体侧卷草, 南瓜 = 缠绕藤蔓 + 真南瓜 + 南瓜鞍, 幽灵 = 灵火鬃尾。
def loft(name, pts, rad, mat, seg=12, smooth_sh=True):
    # 沿 3D 折线放样变截面椭圆管. pts: [(x,y,z)], rad: [(rx, rz)...] 与 pts 等长.
    # 侧向轴恒为 +Y, 环面⊥切向, 端面封口 —— 用于躯干/颈/头/腿/尾股/火舌.
    bm = bmesh.new()
    P_ = [Vector(p) for p in pts]
    n = len(P_)
    rings = []
    for i in range(n):
        if i == 0:
            t = P_[1] - P_[0]
        elif i == n - 1:
            t = P_[-1] - P_[-2]
        else:
            t = P_[i + 1] - P_[i - 1]
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
                P_[i] + Vector((0, rx * cos(a), 0)) + up * (rz * sin(a))))
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
    # 关节链细分: 每段插 per 个中间环 (位置线性, 半径 smoothstep) -> 平滑弯腿.
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


LIFT = 0.07   # 躯干抬升量: 旧版腹底离蹄 0.56m (占身高 47%, 真马约 55%); 抬身后腿变长, 蹄位不动 (起伏下限不变)

# 颈+躯干: (x, z_center, 侧向半宽 rx, 垂直半高 rz)  枕部 -> 颈 -> 鬐甲 -> 背胸腹 -> 臀 -> 尾根 (z 不含 LIFT)
BODY0 = [
    (1.015, 1.870, 0.078, 0.098),   # 颈顶 (枕, 埋进头后)
    (0.965, 1.810, 0.095, 0.125),   # 颈上
    (0.905, 1.730, 0.112, 0.165),
    (0.840, 1.630, 0.128, 0.205),   # 颈中
    (0.770, 1.515, 0.145, 0.240),
    (0.690, 1.385, 0.163, 0.268),   # 颈下
    (0.600, 1.255, 0.182, 0.288),   # 颈基
    (0.505, 1.135, 0.212, 0.292),   # 鬐甲
    (0.360, 1.035, 0.255, 0.288),   # 肩
    (0.180, 0.975, 0.278, 0.300),   # 前胸
    (-0.05, 0.940, 0.284, 0.305),   # 胸腹最深
    (-0.29, 0.950, 0.278, 0.300),   # 腹
    (-0.51, 0.980, 0.268, 0.298),   # 后腹
    (-0.68, 1.045, 0.256, 0.302),   # 胁
    (-0.82, 1.115, 0.236, 0.304),   # 髋
    (-0.93, 1.180, 0.200, 0.290),   # 臀
    (-1.00, 1.230, 0.150, 0.240),
    (-1.045, 1.255, 0.100, 0.165),  # 尾根
]
BODY = [(x, z + LIFT, rx, rz) for (x, z, rx, rz) in BODY0]

# 头: 沿头轴的 (轴向距离 s, 侧向半宽 rx, 半高 rz); 头轴从项点出发指向鼻尖 (前下 38 度)
HEAD_DEG = -38.0
HEAD_N = (1.02, 1.89)            # 项点 (盖住颈的端头)
HEAD_S = [(-0.060, 0.080, 0.100),   # 后项
          (0.000, 0.092, 0.120),    # 项
          (0.070, 0.105, 0.150),    # 颌后
          (0.150, 0.120, 0.175),    # 颊 / 颌 (最深最宽)
          (0.240, 0.118, 0.162),    # 额 / 眼
          (0.320, 0.110, 0.143),
          (0.400, 0.100, 0.123),    # 鼻梁
          (0.470, 0.090, 0.106),
          (0.530, 0.082, 0.094),    # 口鼻
          (0.590, 0.072, 0.082),
          (0.635, 0.045, 0.050)]    # 鼻尖
_h = radians(HEAD_DEG)
H_AX = Vector((cos(_h), 0.0, sin(_h)))     # 头轴 (前下)
H_UP = Vector((-sin(_h), 0.0, cos(_h)))    # 额面法向 (前上), 与头轴垂直


def head_pt(s, up=0.0, side=0.0):
    # 头坐标 -> 马本地坐标: 沿头轴 s, 额侧 up, 侧向 side
    return (HEAD_N[0] + s * H_AX.x + up * H_UP.x, side,
            HEAD_N[1] + LIFT + s * H_AX.z + up * H_UP.z)


def head_rr(s):
    for i in range(len(HEAD_S) - 1):
        a, b = HEAD_S[i], HEAD_S[i + 1]
        if a[0] <= s <= b[0]:
            w = (s - a[0]) / (b[0] - a[0])
            return a[1] + (b[1] - a[1]) * w, a[2] + (b[2] - a[2]) * w
    return HEAD_S[-1][1], HEAD_S[-1][2]


def body_x(x):
    # 躯干环表在 x 处的 (z_center, rx, rz) 线性插值 (BODY 按 x 从头到尾递减)
    for i in range(len(BODY) - 1):
        a, b = BODY[i], BODY[i + 1]
        if b[0] <= x <= a[0]:
            w = (x - a[0]) / (b[0] - a[0])
            return (a[1] + (b[1] - a[1]) * w, a[2] + (b[2] - a[2]) * w, a[3] + (b[3] - a[3]) * w)
    r = BODY[0] if x > BODY[0][0] else BODY[-1]
    return r[1], r[2], r[3]


def body_surf(x, th, off=0.0):
    # 躯干表面点 (贴体的鞍毯/胸带/卷草用): th = 绕躯干轴的角度 (0 = 背脊, ±90 度 = 体侧, ±180 度 = 腹底)
    zc, rx, rz = body_x(x)
    return (x, (rx + off) * sin(th), zc + (rz + off) * cos(th))


def shell(name, x0, x1, half_deg, off, thick, mat, wave=0.10, nx=10, na=12):
    # 贴体薄壳: 沿躯干 x∈[x0,x1]、绕体角 ±half_deg 的封闭薄板 (内外两层 + 四周缝边);
    # wave = 下缘波浪幅度 (弧度, 两缘对称)
    bm = bmesh.new()
    layers = []
    for o in (off, off + thick):
        grid = []
        for i in range(nx + 1):
            u = i / nx
            x = x0 + (x1 - x0) * u
            half = radians(half_deg) + wave * cos(5 * pi * u)
            row = [bm.verts.new(body_surf(x, half * (-1 + 2 * j / na), o)) for j in range(na + 1)]
            grid.append(row)
        layers.append(grid)
    lo, hi = layers
    for i in range(nx):
        for j in range(na):
            bm.faces.new((hi[i][j], hi[i][j + 1], hi[i + 1][j + 1], hi[i + 1][j]))
            bm.faces.new((lo[i][j], lo[i + 1][j], lo[i + 1][j + 1], lo[i][j + 1]))
        bm.faces.new((lo[i][0], hi[i][0], hi[i + 1][0], lo[i + 1][0]))
        bm.faces.new((lo[i][na], lo[i + 1][na], hi[i + 1][na], hi[i][na]))
    for j in range(na):
        bm.faces.new((lo[0][j], lo[0][j + 1], hi[0][j + 1], hi[0][j]))
        bm.faces.new((lo[nx][j], hi[nx][j], hi[nx][j + 1], lo[nx][j + 1]))
    return _mesh_obj(name, bm, mat)


def flame(root, name, base, direction, length, r0, mat, sway=0.0, seg=8):
    # 火舌: 沿 direction 放样, 半径先鼓后收成尖, 末段侧向回勾 (sway = 摆幅)
    d = Vector(direction).normalized()
    side = d.cross(Vector((0, 1, 0)))
    if side.length < 1e-4:
        side = Vector((1, 0, 0))
    side.normalize()
    path, rad = [], []
    for s, v in zip((0.0, 0.22, 0.45, 0.68, 0.86, 1.0), (1.0, 1.18, 1.0, 0.68, 0.36, 0.05)):
        path.append(Vector(base) + d * (length * s) + Vector((0, sway * sin(s * 4.2) * s, 0))
                    + side * (0.012 * sin(s * 6.0)))
        rad.append((r0 * v, r0 * v))
    return child(root, loft(name, path, rad, mat, seg=seg))

# 腿: 5 关节位置链 (肩/髋 -> 膝或飞节 -> 管部 -> 球节 -> 蹄冠), 半径由 leg7 按前后腿给定
FS = [(0.34, 0.20, 0.88), (0.40, 0.22, 0.66), (0.46, 0.22, 0.48), (0.48, 0.22, 0.36), (0.48, 0.22, 0.32)]     # 前腿支撑
HS = [(-0.58, 0.20, 0.92), (-0.62, 0.22, 0.72), (-0.72, 0.23, 0.50), (-0.82, 0.23, 0.36), (-0.82, 0.23, 0.31)]  # 后腿支撑


def _mir(c):
    return [(x, -y, z) for (x, y, z) in c]


# 四套姿态 (最低蹄冠 z>=0.31, bob 最低点仍不触甲板)
POSES = [
    # P0 扬蹄: 左前高举折收, 右前支撑, 左后支撑, 右后后蹬
    {"FL": [(0.34, 0.20, 0.88), (0.48, 0.24, 0.72), (0.60, 0.26, 0.60), (0.50, 0.26, 0.54), (0.44, 0.26, 0.54)],
     "FR": _mir(FS), "HL": HS,
     "HR": [(-0.58, -0.20, 0.92), (-0.70, -0.22, 0.74), (-0.88, -0.23, 0.54), (-1.04, -0.24, 0.38), (-1.04, -0.24, 0.33)]},
    # P1 奔驰: 双前探伸, 双后蹬展
    {"FL": [(0.34, 0.20, 0.88), (0.54, 0.23, 0.74), (0.72, 0.24, 0.60), (0.86, 0.25, 0.44), (0.86, 0.25, 0.38)],
     "FR": None, "HL": [(-0.58, 0.20, 0.92), (-0.72, 0.22, 0.76), (-0.92, 0.23, 0.58), (-1.10, 0.24, 0.42), (-1.10, 0.24, 0.36)],
     "HR": None},
    # P2 飞跃: 双前收拢于胸下, 左后大展, 右后低拂
    {"FL": [(0.34, 0.20, 0.88), (0.46, 0.24, 0.74), (0.52, 0.26, 0.62), (0.42, 0.26, 0.56), (0.36, 0.26, 0.56)],
     "FR": None, "HL": [(-0.58, 0.20, 0.92), (-0.76, 0.24, 0.76), (-0.98, 0.26, 0.56), (-1.18, 0.27, 0.40), (-1.18, 0.27, 0.35)],
     "HR": [(-0.58, -0.20, 0.92), (-0.74, -0.22, 0.72), (-0.96, -0.23, 0.50), (-1.20, -0.24, 0.36), (-1.20, -0.24, 0.32)]}
]
for _p in POSES:
    _p["FR"] = _p["FR"] or _mir(_p["FL"])
    _p["HR"] = _p["HR"] or _mir(_p["HL"])

R_F = (0.108, 0.100, 0.058, 0.042, 0.057, 0.042, 0.047)   # 前腿 7 关节半径: 肩/上臂/膝/管/球节/系/蹄冠
R_H = (0.138, 0.126, 0.066, 0.046, 0.060, 0.044, 0.049)   # 后腿


def leg7(c, front):
    # 5 关节位置链 -> 7 关节 (x,y,z,r): 插入上肢中点与系部; 上端随躯干抬升, 下端不动 (蹄位 = 起伏下限)
    T, K, C, F, E = c
    UM = tuple(T[k] + (K[k] - T[k]) * 0.55 for k in range(3))
    PS = tuple(F[k] + (E[k] - F[k]) * 0.55 for k in range(3))
    R = R_F if front else R_H
    return [(p[0], p[1], p[2] + LIFT * l, r)
            for p, l, r in zip((T, UM, K, C, F, PS, E), (1.0, 0.7, 0.45, 0.0, 0.0, 0.0, 0.0), R)]


def build_leg(root, tag, chain, front, style, m_body, hoof_mat):
    c7 = leg7(chain, front)
    cut = 4 if style == "ghost" else 6          # 幽灵马: 腿到球节为止, 以下化作垂焰
    ref = _refine(c7[:cut + 1], per=3)
    child(root, loft(f"{tag}Leg", [(p[0], p[1], p[2]) for p in ref], [(p[3], p[3]) for p in ref], m_body, seg=8))
    if style == "ghost":
        fx, fy, fz = c7[4][0], c7[4][1], c7[4][2]
        path = [(fx, fy, fz + 0.02), (fx - 0.008, fy, fz - 0.08), (fx - 0.03, fy + 0.012, fz - 0.17),
                (fx - 0.05, fy + 0.025, fz - 0.26), (fx - 0.04, fy + 0.04, fz - 0.335)]
        rad = [(r, r) for r in (0.058, 0.052, 0.038, 0.021, 0.005)]
        child(root, loft(f"{tag}Flame", path, rad, m_wisp, seg=8))
        return
    ex, ey, ez = c7[-1][0], c7[-1][1], c7[-1][2]
    d = Vector((ex - c7[-2][0], ey - c7[-2][1], ez - c7[-2][2]))
    d.normalize()                                # 蹄沿腿端切向 (旧版竖直放, 斜腿时与腿脱开 16-22mm)
    h, rb = 0.085, 0.064
    ob = add_cone(f"{tag}Hoof", rb, h,
                  (ex + d.x * (h / 2 - 0.006), ey + d.y * (h / 2 - 0.006), ez + d.z * (h / 2 - 0.006)),
                  mat=hoof_mat, verts=12, r2=c7[-1][3] * 1.12)
    ob.rotation_euler = (-d).to_track_quat("Z", "Y").to_euler()
    child(root, ob)


def muscle(root, name, a, b, t, sx, sy, sz, mat):
    # 沿 a->b 方向拉长的肌肉体 (椭球), 中心在 a->b 的 t 处
    c = Vector(a).lerp(Vector(b), t)
    ob = add_sphere(name, 1.0, c, mat, seg=10, ring=7, scale=(sx, sy, sz))
    ob.rotation_euler = (Vector(b) - Vector(a)).to_track_quat("Z", "Y").to_euler()
    return child(root, ob)


def tail(root, style, m_man):
    # 尾: 五股渐细的放样束 (旧版是一根带球的火柴棍); 幽灵马改为向后上方飘的灵火
    tx, tz = -1.02, 1.24 + LIFT
    for j in range(5):
        f = (j - 2) / 2
        if style == "ghost":
            path = [(tx, 0.03 * f, tz), (tx - 0.15, 0.07 * f, tz + 0.03), (tx - 0.30, 0.11 * f, tz + 0.15),
                    (tx - 0.43, 0.14 * f, tz + 0.32), (tx - 0.51, 0.16 * f, tz + 0.50 - 0.10 * abs(f))]
            rad = [(r, r) for r in (0.052, 0.056, 0.046, 0.028, 0.005)]
            child(root, loft(f"HTail{j}", path, rad, m_wisp, seg=8))
        else:
            path = [(tx, 0.03 * f, tz), (tx - 0.12, 0.07 * f, tz - 0.15), (tx - 0.23, 0.11 * f, tz - 0.33),
                    (tx - 0.30, 0.14 * f, tz - 0.51), (tx - 0.34, 0.17 * f, tz - 0.69 - 0.08 * abs(f)),
                    (tx - 0.35 - 0.03 * (1 - abs(f)), 0.19 * f, tz - 0.83 - 0.14 * abs(f))]
            rad = [(r, r) for r in (0.040, 0.047, 0.043, 0.033, 0.021, 0.006)]
            child(root, loft(f"HTail{j}", path, rad, m_man, seg=8))


def crest_pts():
    # 颈嵴: BODY 颈部各环的背侧边缘点 + 外法向 (后上) + 切向 (指向头侧), 从颈顶到鬐甲
    out = []
    for i in range(1, 8):
        x, z, rx, rz = BODY[i]
        t = Vector((BODY[i - 1][0] - BODY[i + 1][0], 0, BODY[i - 1][1] - BODY[i + 1][1]))
        t.normalize()
        n = Vector((-t.z, 0, t.x))
        k = 0.90 if i == 7 else 0.97
        out.append((Vector((x, 0, z)) + n * (rz * k), n, t))
    return out


def scroll(name, R, tube, loc, tangent, mat):
    # 卷草: 竖直面里的 270 度圆环弧, 开口顺着 tangent (嵴线切向 / 头轴方向)
    ob = add_torus(name, R, tube, loc, mat=mat, ms=20, ns=6)
    torus_gap(ob, 45, 90)
    ob.rotation_euler = (radians(90), atan2(tangent.x, tangent.z), 0)
    return ob


def mane(root, style):
    cp = crest_pts()
    if style == "ivory":
        # 鎏金卷草鬃: 7 枚大小交替的卷草沿颈嵴排开
        for k, (p, n, t) in enumerate(cp):
            ob = scroll(f"HMane{k}", 0.084 if k % 2 == 0 else 0.070, 0.024, p + n * 0.012, t, m_gmane)
            ob.location.y = 0.018 if k % 2 else -0.018
            child(root, ob)
    elif style == "pumpkin":
        # 缠绕藤蔓 x3 + 鬃间真南瓜 x3 (带瓣, 发光)
        def at(u):
            f_ = u * (len(cp) - 1)
            i = min(int(f_), len(cp) - 2)
            w = f_ - i
            return cp[i][0].lerp(cp[i + 1][0], w), cp[i][1], cp[i][2]
        for j in range(3):
            pts = []
            for q in range(26):
                u = q / 25
                p, n, t = at(u)
                ph = 2 * pi * (j / 3 + 2.2 * u)
                pts.append(p + n * (0.040 * cos(ph)) + Vector((0, 0.040 * sin(ph), 0)))
            child(root, loft(f"HVine{j}", pts, [(0.017, 0.017)] * 26, m_vine, seg=6))
        for k, u in enumerate((0.20, 0.50, 0.80)):
            p, n, t = at(u)
            child(root, lobed(f"HPump{k}", 0.066, p + n * 0.070, m_pump_e, lobes=8, amp=0.07, sz=0.80, seg=14, ring=8))
            child(root, add_cyl(f"HPumpStem{k}", 0.012, 0.05, p + n * 0.135, mat=m_vine, verts=6))
    else:
        # 灵火鬃: 中段每节两束, 沿颈嵴向上后方舔
        for k, (p, n, t) in enumerate(cp):
            for w in ((-1, 1) if 0 < k < 6 else (0,)):
                base = p + n * 0.01 + Vector((0, w * 0.03, 0))
                d = n * 0.55 + Vector((0, 0, 0.85)) + t * (0.10 * w)
                Lf = 0.20 + 0.07 * sin(k * 1.9 + (0.6 if w > 0 else 0.0))
                flame(root, f"HFlame{k}{w}", base, d, Lf, 0.048, m_wisp,
                      sway=0.03 * (1 if (k + (w > 0)) % 2 else -1))


def forelock(root, style, m_man):
    # 额饰: 额面 (头的上缘) 前三环
    for k in range(3):
        s = (0.02, 0.10, 0.19)[k]
        top = Vector(head_pt(s, head_rr(s)[1] * 0.97))
        if style == "ivory":
            child(root, scroll(f"HForelock{k}", 0.048, 0.016, top + H_UP * 0.008, H_AX, m_gmane))
        elif style == "pumpkin":
            if k == 1:
                child(root, lobed("HForePump", 0.056, top + H_UP * 0.050, m_pump_e, lobes=8, amp=0.07, sz=0.80, seg=14, ring=8))
            else:
                child(root, add_sphere(f"HForeLeaf{k}", 1.0, top + H_UP * 0.012, m_vine, seg=8, ring=6,
                                       scale=(0.05, 0.03, 0.012)))
        else:
            flame(root, f"HForeFlame{k}", top, H_UP * 0.9 + Vector((0, 0.25 * (k - 1), 0.35)), 0.13, 0.034, m_wisp)

def horse(root, style, pose_idx):
    # 三灵坐骑. 本地 +X = 行进方向, z=0 为平台面; 体尺: 鬐甲高 ~1.50, 鼻尖->尾根 ~2.57, 头长 0.64.
    # 眼 (骑坐相机在 (0,0,2.24)) 要高于马耳尖 (~2.10) —— 头顶压在 1.96 以下, 否则骑手看出去满脸是耳朵.
    if style == "ghost":
        m_body, m_man, m_blkt, m_seat, hoof = m_ghost, m_wisp, None, m_gold_br, None
    elif style == "pumpkin":
        m_body, m_man, m_blkt, m_seat, hoof = m_pump, m_vine, m_blkt_p, None, m_hoof
    else:  # ivory
        m_body, m_man, m_blkt, m_seat, hoof = m_ivory, m_gmane, m_velvet, m_velvet, m_hoof

    # 躯干+颈 一体放样; 头单独放样 (颈的端头埋在头后)
    child(root, loft("HBody", [(x, 0, z) for (x, z, _, _) in BODY],
                     [(rx, rz) for (_, _, rx, rz) in BODY], m_body, seg=16))
    child(root, loft("HHead", [head_pt(s) for (s, _, _) in HEAD_S],
                     [(rx, rz) for (_, rx, rz) in HEAD_S], m_body, seg=14))
    # 肩 / 臀 体重 + 四肢上肢肌肉体. 幽灵马是半透明的, 叠加的肌肉体会成「套娃」内壳 —— 不加
    solid = style != "ghost"
    if solid:
        for sgn in (-1, 1):
            child(root, add_sphere(f"HShoulder{sgn}", 1.0, (0.40, sgn * 0.176, 1.06 + LIFT), m_body,
                                   seg=10, ring=7, scale=(0.21, 0.076, 0.25)))
            child(root, add_sphere(f"HHaunch{sgn}", 1.0, (-0.76, sgn * 0.150, 1.03 + LIFT), m_body,
                                   seg=10, ring=7, scale=(0.26, 0.105, 0.32)))
    pose = POSES[pose_idx % len(POSES)]
    for tag in ("FL", "FR", "HL", "HR"):
        front = tag[0] == "F"
        build_leg(root, f"H{tag}", pose[tag], front, style, m_body, hoof)
        if solid:
            c7 = leg7(pose[tag], front)
            muscle(root, f"H{tag}Muscle", (c7[0][0], c7[0][1], c7[0][2]), (c7[2][0], c7[2][1], c7[2][2]), 0.40,
                   *((0.118, 0.086, 0.205) if front else (0.150, 0.098, 0.285)), m_body)
    tail(root, style, m_man)
    mane(root, style)
    forelock(root, style, m_man)

    # 耳 / 眼 / 鼻孔
    top = Vector(head_pt(-0.02, 0.112))
    for sgn in (-1, 1):
        base = top + Vector((-0.005, sgn * 0.062, 0.0))
        d = Vector((0.10, sgn * 0.20, 1.0)).normalized()
        ear = add_cone(f"HEar{sgn}", 0.046, 0.17, base + d * 0.075, m_body, verts=10, r2=0.012)
        ear.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
        child(root, ear)
        e = head_pt(0.235, 0.064, sgn * 0.103)
        if style == "ivory":
            child(root, add_sphere(f"HEye{sgn}", 0.036, e, m_eye_r, seg=12, ring=8))          # 深色琉璃眼
            child(root, add_sphere(f"HGlint{sgn}", 0.011, head_pt(0.262, 0.072, sgn * 0.114),  # 一点金瞳
                                   m_glow_g, seg=8, ring=6))
        elif style == "pumpkin":
            eye = add_sphere(f"HEye{sgn}", 1.0, e, m_pump_e, seg=12, ring=8,                  # 雕出来的发光眼缝
                             scale=(0.032, 0.013, 0.022))
            eye.rotation_euler = (0, radians(-HEAD_DEG), 0)
            child(root, eye)
        else:
            child(root, add_sphere(f"HEye{sgn}", 0.040, e, m_spirit, seg=12, ring=8))
        child(root, add_sphere(f"HNostril{sgn}", 0.019, head_pt(0.585, -0.056, sgn * 0.055),
                               m_hoof, seg=8, ring=6))

    # 鞍具: 贴体鞍毯 (下缘金边) / 南瓜鞍或绒面鞍 / 肚带 / 胸带 / 臀带 / 缰辔 —— 都贴着躯干与头的表面
    if m_blkt:
        child(root, shell("HBlanket", -0.27, 0.37, 60, 0.010, 0.014, m_blkt))
        child(root, shell("HBlanketTrim", -0.30, 0.40, 66, 0.004, 0.009, m_gold_dp))
        for sgn in (-1, 1):
            for tx in (-0.24, 0.34):
                tas = add_cone(f"HTassel{sgn}{tx}", 0.030, 0.10, (tx, sgn * 0.258, 1.115 + LIFT),
                               m_gold_dp, verts=6)
                tas.rotation_euler = (pi, 0, 0)
                child(root, tas)
    zc, rx, rz = body_x(0.05)
    child(root, add_torus("HGirth", 1.0, 0.022, (0.05, 0, zc), rot=(0, radians(90), 0), mat=m_gold_dp,
                          ms=28, ns=6, scale=(rz + 0.014, rx + 0.014, 1.0)))
    for sgn in (-1, 1):
        pts = [body_surf(0.50 - 0.45 * q / 5, sgn * radians(38 + 57 * q / 5), 0.012) for q in range(6)]
        child(root, loft(f"HBreast{sgn}", pts, [(0.016, 0.016)] * 6, m_gold_dp, seg=6))
        child(root, add_sphere(f"HBreastRos{sgn}", 0.034, pts[0], m_gold_br, seg=8, ring=6))
    child(root, add_torus("HCrupper", 1.0, 0.014, (-1.035, 0, 1.255 + LIFT), rot=(0, radians(80), 0),
                          mat=m_gold_dp, ms=20, ns=6, scale=(0.175, 0.108, 1.0)))
    if style == "pumpkin":
        child(root, lobed("HSeat", 0.215, (0.05, 0, 1.305 + LIFT), m_pain_o, lobes=8, amp=0.09, sz=0.60, seg=20, ring=10))
        child(root, add_cyl("HSeatStem", 0.016, 0.09, (-0.05, 0, 1.455 + LIFT), mat=m_vine, verts=6))
    else:
        child(root, add_sphere("HSeat", 1.0, (0.05, 0, 1.375 + LIFT), m_seat, seg=16, ring=10,
                               scale=(0.25, 0.165, 0.055)))
    child(root, add_sphere("HPommel", 1.0, (0.285, 0, 1.435 + LIFT), m_gold_br, seg=12, ring=8,
                           scale=(0.055, 0.085, 0.075)))
    child(root, add_sphere("HCantle", 1.0, (-0.165, 0, 1.445 + LIFT), m_gold_br, seg=12, ring=8,
                           scale=(0.05, 0.13, 0.08)))

    def head_ring(nm, s, tube, mat):
        rrx, rrz = head_rr(s)
        return child(root, add_torus(nm, 1.0, tube, head_pt(s), rot=(0, radians(-52), 0), mat=mat,
                                     ms=24, ns=6, scale=(rrz + 0.012, rrx + 0.012, 1.0)))
    head_ring("HBrowband", 0.215, 0.014, m_gold_dp)
    head_ring("HNoseband", 0.545, 0.014, m_gold_dp)
    rb, rn = head_rr(0.215)[0], head_rr(0.545)[0]
    for sgn in (-1, 1):
        child(root, cyl_between(f"HCheek{sgn}", head_pt(0.215, -0.01, sgn * (rb + 0.012)),
                                head_pt(0.545, 0.012, sgn * (rn + 0.012)), 0.012, m_gold_dp, verts=6))
        rein = [head_pt(0.555, 0.012, sgn * 0.092), (1.12, sgn * 0.205, 1.36 + LIFT),
                (0.78, sgn * 0.185, 1.25 + LIFT), (0.45, sgn * 0.135, 1.33 + LIFT),
                (0.30, sgn * 0.10, 1.47 + LIFT)]
        child(root, loft(f"HRein{sgn}", rein, [(0.012, 0.012)] * 5, m_gold_dp, seg=6))

    if style == "ivory":
        # 体侧鎏金卷草 x4: 贴着躯干表面旋入
        for sgn in (-1, 1):
            for (x0, th0, R) in ((0.42, 72, 0.105), (-0.72, 74, 0.12)):
                pts = []
                for q in range(22):
                    u = q / 21
                    ph = u * 1.75 * pi
                    rho = R * (1 - 0.78 * u)
                    pts.append(body_surf(x0 + rho * cos(ph),
                                         sgn * (radians(th0) + rho * sin(ph) / 0.30), 0.012))
                child(root, loft(f"HCurl{x0}{sgn}", pts, [(0.013, 0.013)] * 22, m_gmane, seg=6))

def wheel(root, name, x, y, z, R=0.42):
    # 装饰车轮 (旧版两辆「车」都没有轮子, 读成南瓜篓和首饰盒): 轮缘环 + 毂 + 8 辐 + 内侧木盘, 轴线沿 Y
    child(root, add_torus(f"{name}Rim", R, 0.035, (x, y, z), rot=(radians(90), 0, 0), mat=m_gold_br, ms=20, ns=6))
    child(root, add_cyl(f"{name}Disc", R - 0.05, 0.04, (x, y - 0.04 if y > 0 else y + 0.04, z),
                        rot=(radians(90), 0, 0), mat=m_wood_d, verts=24))
    child(root, add_cyl(f"{name}Hub", 0.07, 0.15, (x, y, z), rot=(radians(90), 0, 0), mat=m_gold_dp, verts=12))
    for k in range(8):
        a = k * pi / 4
        child(root, cyl_between(f"{name}Spoke{k}", (x + 0.06 * cos(a), y, z + 0.06 * sin(a)),
                                (x + (R - 0.03) * cos(a), y, z + (R - 0.03) * sin(a)), 0.016, m_gold_dp, verts=5))


def carriage_kit(root, tag, z_bottom):
    # 座车通用件: 底盘 + 四轮 + 两轴 + 顶上座椅 + 前角灯柱.
    # 鼓身平顶 z1.40 = 碰撞表座车顶面高 (h1.40 可站); 旧版视觉顶只有 1.02, 人「站上去」悬空 38cm.
    # 座椅面 1.49 -> 骑坐眼高 2.22 (carousel.js), 与灵兽 (2.24) 同一视线高度.
    child(root, add_bevel_box(f"{tag}Chassis", (1.56, 0.92, 0.08), (0, 0, z_bottom - 0.01), mat=m_gold_dp, width=0.02))
    for sx in (-1, 1):
        child(root, cyl_between(f"{tag}Axle{sx}", (0.60 * sx, -0.72, 0.42), (0.60 * sx, 0.72, 0.42), 0.03,
                                m_gold_dp, verts=8))
        for sy in (-1, 1):
            wheel(root, f"{tag}Wheel{sx}{sy}", 0.60 * sx, 0.66 * sy, 0.42)
    # 座椅: 绒面座 + 靠背 + 鎏金边与顶珠 (铜杆从座面前部穿过, 骑手看不见 —— 杆在近裁剪面内)
    child(root, add_bevel_box(f"{tag}Seat", (0.56, 0.52, 0.09), (-0.05, 0, 1.445), mat=m_velvet, width=0.02))
    child(root, add_bevel_box(f"{tag}Back", (0.07, 0.52, 0.50), (-0.315, 0, 1.69), mat=m_velvet, width=0.02))
    child(root, add_box(f"{tag}SeatEdge", (0.58, 0.54, 0.018), (-0.05, 0, 1.494), mat=m_gold_br))
    child(root, add_box(f"{tag}BackEdge", (0.09, 0.54, 0.022), (-0.315, 0, 1.95), mat=m_gold_br))
    for sy in (-1, 1):
        child(root, add_sphere(f"{tag}Finial{sy}", 0.05, (-0.315, 0.27 * sy, 2.0), m_gold_br, seg=10, ring=8))
    # 前角灯柱 x2 (旧版南瓜马车的灯封在不透明壳里, 看不见)
    for sy in (-1, 1):
        lx, ly = 0.48, 0.28 * sy
        child(root, add_cyl(f"{tag}LampPost{sy}", 0.016, 0.34, (lx, ly, 1.57), mat=m_gold_dp, verts=6))
        child(root, add_cone(f"{tag}LampCap{sy}", 0.09, 0.07, (lx, ly, 1.775), mat=m_gold_dp, verts=10, r2=0.02))
        child(root, add_sphere(f"{tag}Lamp{sy}", 0.07, (lx, ly, 1.70), m_bulb, seg=12, ring=8))


PDRUM = [(0.20, 0.70), (0.26, 0.86), (0.38, 0.97), (0.56, 1.00), (0.76, 0.985), (0.96, 0.94),
         (1.16, 0.875), (1.30, 0.82), (1.39, 0.79), (1.40, 0.77)]   # (z, 半径系数): 南瓜鼓身, 平顶 1.40
PA, PB = 0.95, 0.55                                            # 鼓身半轴 (行进向 x, 侧向 y)


def drum_scale(th, z):
    # 鼓身瓣: 10 瓣, 上下两端收敛
    for i in range(len(PDRUM) - 1):
        a, b = PDRUM[i], PDRUM[i + 1]
        if a[0] <= z <= b[0]:
            w = (z - a[0]) / (b[0] - a[0])
            return a[1] + (b[1] - a[1]) * w
    return PDRUM[-1][1]


def drum_surf(th, z, off=0.0):
    # 南瓜鼓身表面点 (瓜脸 / 瓜棱线贴面用)
    w = sin(pi * min(max((z - 0.20) / 1.20, 0.0), 1.0)) ** 0.5
    k = drum_scale(th, z) * (1 + 0.05 * cos(10 * th) * w)
    return (PA * cos(th) * k + off * cos(th), PB * sin(th) * k + off * sin(th), z)


def pumpkin_drum(name, mat):
    bm = bmesh.new()
    rows = []
    for (z, _s) in PDRUM:
        rows.append([bm.verts.new(drum_surf(2 * pi * i / 40, z)) for i in range(40)])
    bot = bm.verts.new((0, 0, PDRUM[0][0]))
    top = bm.verts.new((0, 0, PDRUM[-1][0]))
    for i in range(40):
        i2 = (i + 1) % 40
        bm.faces.new((bot, rows[0][i2], rows[0][i]))
        bm.faces.new((top, rows[-1][i], rows[-1][i2]))
    for j in range(len(rows) - 1):
        for i in range(40):
            i2 = (i + 1) % 40
            bm.faces.new((rows[j][i], rows[j][i2], rows[j + 1][i2], rows[j + 1][i]))
    return _mesh_obj(name, bm, mat)


def pumpkin_carriage(root):
    # 南瓜马车 (D 组, 2026-11-25 重做): 旧版 = 橙色椭球 + 9 根从顶上戳出来的竖条, 没有瓜棱和脸,
    # 灯和座椅封在不透明壳里, 瓜蒂悬在骑手视线正中, 没有轮子。
    # 新版 = 带瓣的南瓜鼓身 (平顶 1.40 可站) + 雕空瓜脸 (行进方向) + 四轮 + 顶上座椅。
    # 本地 +X = 行进方向.
    child(root, pumpkin_drum("PCShell", m_pump_sh))
    # 瓜脸: 两只斜挑的发光眼 (落在正前方两侧的瓣脊上) + 贴面的笑弧
    for sy in (-1, 1):
        th = radians(34) * sy
        ex_, ey_, ez_ = drum_surf(th, 0.93, -0.012)
        eye = add_sphere(f"PCEye{sy}", 1.0, (ex_, ey_, ez_), m_pump_e, seg=12, ring=8, scale=(0.022, 0.10, 0.055))
        # 长轴顺鼓身切向 (绕 Z 转法向角), 再绕法向斜挑成「凶」眼
        eye.rotation_euler = (radians(-16) * sy, 0, atan2(PA * sin(th), PB * cos(th)))
        child(root, eye)
    smile = [drum_surf(radians(-19 + 38 * q / 12), 0.56 + 0.13 * (2 * q / 12 - 1) ** 2, 0.012) for q in range(13)]
    child(root, loft("PCSmile", smile, [(0.026, 0.026)] * 13, m_pump_e, seg=6))
    # 瓜蒂: 卷向侧后方 (不挡骑手视线) + 一道藤蔓
    st = [(-0.60, 0.30, 1.39), (-0.70, 0.36, 1.56), (-0.66, 0.42, 1.70), (-0.56, 0.46, 1.76)]
    child(root, loft("PCStem", st, [(0.05, 0.05), (0.044, 0.044), (0.036, 0.036), (0.02, 0.02)], m_vine, seg=8))
    vine = [drum_surf(radians(150 + 60 * q / 10), 1.20 + 0.18 * sin(pi * q / 10), 0.016) for q in range(11)]
    child(root, loft("PCVine", vine, [(0.02, 0.02)] * 11, m_vine, seg=6))
    carriage_kit(root, "PC", 0.20)


def gilded_carriage(root):
    # 鎏金座车 (D 组, 2026-11-25 重做): 旧版 = 紫色实心斗, 座椅埋在斗里, 读成首饰盒, 没有轮子。
    # 新版 = 绒紫凹槽鼓身 (16 根鎏金竖肋) + 金箍 / 象牙腰线 / 角珠 + 木质平顶 (1.40 可站) + 四轮 + 顶上座椅。
    child(root, add_cyl("GCBody", 0.58, 1.20, (0, 0, 0.80), mat=m_velvet_d, verts=40, scale=(1.60, 1.0, 1.0)))
    for k in range(16):
        th = k * pi / 8
        child(root, add_bevel_box(f"GCRib{k}", (0.05, 0.045, 1.19), (0.93 * cos(th), 0.58 * sin(th), 0.80),
                                  mat=m_gold_dp, width=0.012, rot=(0, 0, atan2(0.93 * sin(th), 0.58 * cos(th)))))
    for i, (zz, tube, mm, sx_) in enumerate(((1.40, 0.045, m_gold_br, 0.955), (0.20, 0.045, m_gold_br, 0.955),
                                             (0.80, 0.028, m_pain_i, 0.945))):
        child(root, add_torus(f"GCRing{i}", 1.0, tube, (0, 0, zz), mat=mm, ms=48, ns=6, scale=(sx_, 0.585, 1.0)))
    for k in range(4):
        th = radians(45 + 90 * k)
        child(root, add_sphere(f"GCBoss{k}", 0.085, (0.90 * cos(th), 0.55 * sin(th), 1.42), m_gold_br, seg=12, ring=8))
        nphi = atan2(0.93 * sin(th), 0.58 * cos(th))          # 椭圆法向角: 卷草贴着鼓身侧面
        ob = add_torus(f"GCScroll{k}", 0.15, 0.024,
                       (0.93 * cos(th) + 0.025 * cos(nphi), 0.58 * sin(th) + 0.025 * sin(nphi), 1.05),
                       rot=(radians(90), 0, nphi), mat=m_gold_br, ms=16, ns=6)
        torus_gap(ob, 60, 90)
        child(root, ob)
    child(root, add_cyl("GCDeck", 1.0, 0.012, (0, 0, 1.406), mat=m_wood_l, verts=48, scale=(0.89, 0.54, 1.0)))
    carriage_kit(root, "GC", 0.20)


STYLE = {1: "ghost", 2: "ivory", 3: "pumpkin", 4: "ghost",
         6: "ivory", 7: "pumpkin", 8: "ghost", 9: "ivory"}
# 每种灵兽一个标志性姿态: 幽灵马 = 扬蹄 (P0), 象牙马 = 奔驰 (P1), 南瓜马 = 飞跃 (P2)。
# 相邻位本来就隔着别的灵兽, 姿态仍然不同; 同一种灵兽的几匹几何完全相同 -> glb 里共用一份网格
# (dedupe_rides), 运行时合批成 InstancedMesh (K 组, 2026-11-26)。旧版 4 套姿态轮换。
POSE_IDX = {1: 0, 4: 0, 8: 0, 2: 1, 6: 1, 9: 1, 3: 2, 7: 2}
ride_roots = []
bob_idx = []
for i in range(P["rides"]):
    th = E + i * 2 * pi / P["rides"]
    root = add_empty(f"CR_Ride_{i}", (RIDE_R * cos(th), RIDE_R * sin(th), DECK))
    root.rotation_euler = (0, 0, th + pi / 2)   # 本地 +X = 行进切向
    link_col(root, col_spin)
    child(spin, root)
    ride_roots.append(root)
    # 灵光池: 每个骑乘位正下方一圈贴地圆盘, 按三灵配色 (挂 CR_Spin, 不随起伏) —— 灵兽「被召回」的落点
    _pool = m_pool_g if i == 5 else (m_pool_p if i == 0 else
             {"ghost": m_pool_s, "ivory": m_pool_g, "pumpkin": m_pool_p}[STYLE[i]])
    S(add_cyl(f"CR_Pool{i}", 0.75, 0.008, (RIDE_R * cos(th), RIDE_R * sin(th), DECK + 0.016), mat=_pool, verts=28))
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

# 顶棚吊灯位置的点灯 ×3 (仅预览照明用, 导出前移除; 运行时由 carousel.js CANOPY_LIGHTS 在灯球心点灯)
for k in range(3):
    a = radians(LAMP["az0"] + k * 120.0)
    bpy.ops.object.light_add(type="POINT", location=(LAMP["r"] * cos(a), LAMP["r"] * sin(a), LAMP["globe_z"]))
    lamp = bpy.context.active_object
    lamp.name = f"CR_PvLight{k}"
    lamp.data.energy = 170
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
cam_front = add_cam("CR_CamFront", (19.0 * d[0], 19.0 * d[1], 2.6), (0, 0, 4.6), lens=32)   # 取景含顶饰 (星顶 11.64)
cam_three = add_cam("CR_CamThree",
                    (25 * d[0] + 3 * perp[0], 25 * d[1] + 3 * perp[1], 7.0),
                    (0, 0, 4.8), lens=30)
cam_side  = add_cam("CR_CamSide", (23 * perp[0], 23 * perp[1], 6.5), (0, 0, 4.8), lens=32)
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

# 同款灵兽共用网格数据 (K 组, 2026-11-26): 每种灵兽只保留第一匹建好的网格, 其余同款骑乘位删掉自己的网格,
# 换成母本的链接副本 (对象副本共享 mesh datablock) —— glTF 导出只写一份网格, 多个节点引用。
# 运行时 (src/rides/carousel.js) 再把引用同一网格的骑乘位合批成 InstancedMesh。
def dedupe_rides():
    master = {}
    for i, root in enumerate(ride_roots):
        key = (STYLE.get(i), POSE_IDX.get(i))
        if key[0] is None:            # 座车: 各只有一个
            continue
        meshes = [ob for ob in bpy.context.scene.objects if ob.type == "MESH" and ob.parent is root]
        if key not in master:
            master[key] = (i, meshes)
            continue
        mi, srcs = master[key]
        for ob in meshes:
            bpy.data.objects.remove(ob, do_unlink=True)
        for src in srcs:
            dup = src.copy()          # 共享 src.data
            dup.name = src.name.replace(f"CR_R{mi}_", f"CR_R{i}_", 1)
            dup.parent = root
            bpy.context.scene.collection.objects.link(dup)
        print(f"DEDUPE ride {i}: {len(srcs)} meshes share ride {mi} ({STYLE[i]})")


dedupe_rides()

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
# K 组 (2026-11-26): 导出前清掉旋转 / 起伏的动画数据并把姿态归零 —— 运行时 (src/rides/carousel.js) 自己驱动
# 旋转与起伏, 不用烘焙动画。旧版把 9 条动画导进了 glb (运行时从未播放), 而且 CR_Spin 带着动画外推出来的
# -0.67° 偏转 (theta=0 时骑乘位落在 201.33° 而不是 202°)。.blend 在上一步已经存盘, 里面的动画
# (供可选的预览视频用) 不受影响。
for ob in (spin, *ride_roots):
    ob.animation_data_clear()
spin.rotation_euler = (0.0, 0.0, 0.0)
for root in ride_roots:
    root.location.z = DECK
# 不导出动画 (运行时不播放) 和 UV (全部材质无贴图, UV 是死数据, 占 glb 约 19%)
try:
    bpy.ops.export_scene.gltf(filepath=str(OUT / "carousel.glb"),
                              export_format="GLB", export_apply=True,
                              export_animations=False, export_texcoords=False)
except (TypeError, RuntimeError) as e:
    print("GLTF_KWARG_FALLBACK", type(e).__name__)
    bpy.ops.export_scene.gltf(filepath=str(OUT / "carousel.glb"),
                              export_format="GLB", export_animations=False, export_texcoords=False)
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
