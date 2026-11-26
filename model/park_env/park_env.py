# -*- coding: utf-8 -*-
"""
Park Environment v3 - "幽夜游乐场" Halloween night park (game-ready glTF asset)
Run: blender --background --python park_env.py

布局 v3 (Blender 坐标, +Y=北, r150 扩园):
  - 摩天轮在原点 (轮盘资产独立), 登舱台阶在 -Y 侧, 中央广场 r17.5
  - 南入口大门 (0,-146) -> 石板主路 (7 段, 中途二道门牌楼 y=-60) -> 广场
  - 路网: 内环 r34 / 外环 r90 / 四条放射支路 (东北过山车 78°, 东南秘境 -32°,
          西南幽灵港 217.6°, 西北许愿池 147°) + 木马支路 22° / 墓园·市集横路
  - 墓园 v4 (2026-11-26): 旧址 (34,-41) 改作入口前庭, 新址 = 椭圆 36x24 心 (37,-58) (app (37,58)),
          北侧接路 (前庭 -> 新址) + 西侧支路 (主路 -> 新址); 第三批: 丁字走道 (东西主走道 + 北脊) + 两个门
          (石门柱 / 铁艺拱 / 新月星徽 / 石像鬼) + 一圈尖桩铁艺围栏 + 碑成行
  - 预留区 (围挡+敬请期待牌): 北 过山车 x[-30,60] y[70,130];
          西南 幽灵港(海盗船) x[-88,-52] y[-55,-35]; 东南 秘境 x[78,112] y[-78,-42]
  - 烟花发射器 x6 (三型×2: A 牡丹架 广场东北+木马缘 / B 垂柳塔 墓园东+许愿池 /
          C 椰芯炮 市集南+南瓜田, 炮口朝园心) / 许愿池 (-57,38) / 石像鬼 x2 / 稻草人 x2 / 花藤拱门 x3
  - 植被: 枯树 v2 x22 (螺旋/双干/垂枝) / 缠灯松 x12 (高瘦/矮胖/歪脖) / 垂柳 x4
          草丛 ~600 / 发光蘑菇圈 x8 / 路缘花带 (紫郁金香+橙万寿菊) / 彼岸花 x4 (墓园)
  - 家具变体: 长椅 x12 (铁艺卷草/木条/南瓜背/简约) / 路灯 x28 (球灯/南瓜顶/双头提灯)
          木桶加铁箍 / 南瓜灯 x39 (高/扁体形)
  - 围墙铁艺栅栏 r146 (~380 柱) + 维多利亚路灯 + 灯串 + 彩旗串
  - 远景: 山脊剪影环 (420-470) + 城市灯火点阵 (300-390)
输出: park_env.glb (按材质合并) + colliders.json (app 坐标, 含 launchers 锚点) + preview/
"""
import bpy
import bmesh
import json
import random
import time
from math import radians, pi, cos, sin, atan2, hypot
from pathlib import Path
import numpy as np
from mathutils import Vector, Quaternion, Euler

random.seed(11)
T0 = time.time()
def tmark(label):
    print(f"[t={time.time()-T0:7.1f}s] {label}", flush=True)

P = {
    "park_r": 150.0,
    "fence_r": 146.0,
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
    "grass2": "#1B2B25",
    "petv":   "#B26BFF",
    "peto":   "#FFB347",
    "mush":   "#C9A7FF",
    "mushstem":"#D8CFE2",
    "water":  "#141B33",
    "cloth":  "#4A3A5A",
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

# ---- 网格直建 helper (bpy.data, 零 bpy.ops): 逐 op 依赖图更新是数千对象时的性能杀手 ----
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
    fs.append(tuple(range(verts - 1, -1, -1)))   # 底盖 (-z)
    fs.append(tuple(range(verts, verts * 2)))    # 顶盖 (+z)
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

def add_torus(name, R, tube, loc, rot=(0, 0, 0), mat=None, ms=64, ns=8, scale=(1, 1, 1)):
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
    ob.scale = scale
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
    vs.append((0, 0, hz))   # 锥尖 (+z)
    fs = []
    for i in range(verts):
        j = (i + 1) % verts
        fs.append((i, j, verts))
    fs.append(tuple(range(verts - 1, -1, -1)))   # 底盖
    ob = _new_obj(name, vs, fs, mat, True)
    ob.location = loc
    ob.rotation_euler = rot
    return ob

def add_sphere(name, r, loc, mat=None, seg=10, ring=6, scale=(1, 1, 1)):
    vs = [(0, 0, r)]   # 顶极
    for j in range(1, ring):
        phi = pi * j / ring
        sp, cp = sin(phi), cos(phi)
        for i in range(seg):
            th = 2 * pi * i / seg
            vs.append((r * sp * cos(th), r * sp * sin(th), r * cp))
    vs.append((0, 0, -r))   # 底极
    top_i = 0
    bot_i = len(vs) - 1
    fs = []
    for i in range(seg):
        i2 = (i + 1) % seg
        fs.append((top_i, 1 + i, 1 + i2))                     # 顶三角带
    for j in range(ring - 2):
        row0 = 1 + j * seg
        row1 = row0 + seg
        for i in range(seg):
            i2 = (i + 1) % seg
            fs.append((row0 + i, row1 + i, row1 + i2, row0 + i2))
    last_row = 1 + (ring - 2) * seg
    for i in range(seg):
        i2 = (i + 1) % seg
        fs.append((bot_i, last_row + i2, last_row + i))       # 底三角带
    ob = _new_obj(name, vs, fs, mat, True)
    ob.location = loc
    ob.scale = scale
    return ob

def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

def seg_dist(px, py, ax, ay, bx, by):
    """点到线段距离 (路径排除用)"""
    abx, aby = bx - ax, by - ay
    L2 = abx * abx + aby * aby
    t = 0.0 if L2 < 1e-9 else max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / L2))
    return hypot(px - (ax + abx * t), py - (ay + aby * t))

COLLIDERS = []   # (x, y, r[, h]) blender 坐标, 导出时转 app 坐标
COLLIDER_RECTS = []  # (x, y, hw, hd) blender 坐标 — 轴对齐盒墙(可推挤)
POIS = []        # (x, y, label)

def collider(x, y, r, h=None):
    """h = 顶面高度（blender z, 可选）：有 h 的圆顶面可站立（跳跃/台阶吸附）,
    无 h 的圆为无限高阻挡。app 侧语义见 src/player/controller.js groundAt()"""
    COLLIDERS.append({"x": round(x, 2), "y": round(y, 2), "r": round(r, 2), "h": h})

def collider_rect(x, y, hw, hd):
    """轴对齐盒墙（半宽/半深）：圆形罩会封掉紧邻可站物（如亭旁木桶）的上空时改用"""
    COLLIDER_RECTS.append({"x": round(x, 2), "y": round(y, 2),
                           "hw": round(hw, 2), "hd": round(hd, 2)})

PARK_LIGHTS = []   # 园区脚本登记的真实点光（blender x, y, z + 参数）, 导出时转 app 坐标写进 colliders.json 的 lights

def park_light(x, y, z, color, intensity, distance, decay=2, tag="", key="parkLampLight"):
    """登记一盏由游戏运行时创建的真实点光（src/core/world.js 按清单建灯, 位置与模型同源）。
    key = 控制它的设置面板滑杆键名（默认「园区照明亮度」parkLampLight）。"""
    PARK_LIGHTS.append({"x": x, "y": y, "z": z, "color": color, "intensity": intensity,
                        "distance": distance, "decay": decay, "tag": tag, "key": key})

# ---------------- v3 植被 helper (弯叶/变径管/顶点色/雕空) ----------------
def make_vcol_mat(name, color, rough=0.5, emit=None, strength=0.0):
    """顶点色材质: Base = 颜色 × COLOR_0 (three.js vertexColors 同语义, 白底=色全靠顶点色)"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "Col"
    if color.upper() in ("#FFFFFF", "WHITE"):
        nt.links.new(attr.outputs["Color"], p.inputs["Base Color"])
    else:
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = 'RGBA'
        mix.blend_type = 'MULTIPLY'
        mix.inputs[6].default_value = hex_lin(color)
        nt.links.new(attr.outputs["Color"], mix.inputs[7])
        nt.links.new(mix.outputs[2], p.inputs["Base Color"])
    for ident, val in (("Roughness", rough),):
        for s in p.inputs:
            if s.identifier == ident:
                s.default_value = val
    if emit:
        for s in p.inputs:
            if s.identifier == "Emission Color":
                s.default_value = hex_lin(emit)
            if s.identifier == "Emission Strength":
                s.default_value = strength
    return m


def set_vcol(ob, colors):
    """每顶点 (r,g,b) LINEAR → COLOR_0"""
    me = ob.data
    flat = []
    for c in colors:
        flat += [c[0], c[1], c[2], 1.0]
    attr = me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
    attr.data.foreach_set("color", flat)
    try:
        me.color_attributes.active_color = attr
    except Exception:
        pass
    return ob


def set_vcol_uniform(ob, g):
    """无 vcol 网格补常数灰 (防 join 进 vcol 组后变黑块)"""
    n = len(ob.data.vertices)
    set_vcol(ob, [(g, g, g)] * n)


def tube_frustum(name, pts, radii, mat, sides=8, sm=True, cap_end_fan=True):
    """平行输运标架变径管: 有机弯曲枝干/蒂/藤"""
    pts = [Vector(p) for p in pts]
    rings = []
    up0 = Vector((0, 0, 1))
    d0 = (pts[1] - pts[0]).normalized()
    dcur = d0
    n = up0 if abs(d0.z) > 0.93 else up0.cross(d0).normalized()
    n = (n - d0 * n.dot(d0)).normalized()
    for i, p in enumerate(pts):
        if i > 0:
            dprev = (pts[i] - pts[i - 1]).normalized()
            dcur = (pts[min(i + 1, len(pts) - 1)] - pts[i]).normalized() if i < len(pts) - 1 else dprev
            q = dprev.rotation_difference(dcur)
            n = q @ n
        nn = (n - dcur * n.dot(dcur)).normalized()
        r = radii[i]
        ring = []
        for k in range(sides):
            a = 2 * pi * k / sides
            ring.append(p + (nn * cos(a) + dcur.cross(nn) * sin(a)) * r)
        rings.append(ring)
    vs = [v for ring in rings for v in ring]
    fs = []
    for i in range(len(rings) - 1):
        b0, b1 = i * sides, (i + 1) * sides
        for k in range(sides):
            k2 = (k + 1) % sides
            fs.append((b0 + k, b0 + k2, b1 + k2, b1 + k))
    if cap_end_fan:
        tip = pts[-1] + (pts[-1] - pts[-2]).normalized() * radii[-1] * 2.2
        vs.append(tuple(tip))
        ti = len(vs) - 1
        b = (len(rings) - 1) * sides
        for k in range(sides):
            fs.append((b + k, b + (k + 1) % sides, ti))
    return _new_obj(name, vs, fs, mat, sm)


def blade(prefix, base, length, width, yaw, bend, mat, root_c, tip_c,
          segs=5, lean=0.2, twist=0.0):
    """弯曲锥形草叶: 弧线积分 + 尖部收窄 + 顶点色渐变"""
    base = Vector(base)
    d0 = Vector((cos(yaw) * lean, sin(yaw) * lean, 1.0)).normalized()
    outw = Vector((cos(yaw), sin(yaw), 0.0))
    axis = d0.cross(Vector((0, 0, 1))).normalized()
    if (Quaternion(axis, 0.2) @ d0).dot(outw) < d0.dot(outw):
        axis = -axis
    lft = axis.copy()
    p = base.copy()
    rows = []
    step = length / segs
    for i in range(segs + 1):
        t = i / segs
        th = bend * (t ** 1.3)
        d = (Quaternion(axis, th) @ d0).normalized()
        lft2 = Quaternion(d, twist * t) @ lft if twist else lft
        w = width * (1 - t) ** 1.15 + 0.0012   # 全宽 (勿再乘0.5, 会细成线)
        rows.append((p - lft2 * w, p + lft2 * w, t))
        p = p + d * step
    vs = []
    vcol = []
    for l, r, t in rows:
        vs += [tuple(l), tuple(r)]
        tt = t ** 0.85
        c = [root_c[k] + (tip_c[k] - root_c[k]) * tt for k in range(3)]
        vcol += [c, c]
    fs = []
    for i in range(segs):
        a, b = i * 2, i * 2 + 1
        fs.append((a, b, b + 2))
        fs.append((a, b + 2, a + 2))
    ob = _new_obj(prefix, vs, fs, mat, False)
    set_vcol(ob, vcol)
    return ob


def blade_tone():
    """草叶三色系: 常规橄榄 / 偏暗 / 枯黄"""
    kind = random.random()
    root = hex_lin("#14281C")[:3]
    if kind < 0.62:
        tip = hex_lin("#5A7A3A")[:3]
    elif kind < 0.85:
        tip = hex_lin("#46603A")[:3]
    else:
        tip = hex_lin("#98823E")[:3]
    return root, tip


def ground_patch(name, x, y, r, mat, tone_lo=0.62, tone_hi=1.0):
    """有机边缘地斑 (打破纯黑地面): 波形圆盘 + 顶点色斑驳"""
    vs = [(x, y, 0.011)]
    fs = []
    nseg = 22
    wob = [(random.uniform(-1, 1), random.uniform(-1, 1)) for _ in range(3)]
    ring = []
    for k in range(nseg):
        a = 2 * pi * k / nseg
        rr = r * (1 + 0.22 * wob[0][0] * sin(3 * a + wob[0][1] * 6.28)
                  + 0.12 * wob[1][0] * sin(7 * a + wob[1][1] * 6.28))
        ring.append((x + rr * cos(a), y + rr * sin(a), 0.011))
    vs += ring
    for k in range(nseg):
        fs.append((0, 1 + k, 1 + (k + 1) % nseg))
    ob = _new_obj(name, vs, fs, mat, False)
    vcol = []
    for i in range(len(vs)):
        d = hypot(vs[i][0] - x, vs[i][1] - y) / max(r, 1e-4)
        g = tone_hi - (tone_hi - tone_lo) * d * random.uniform(0.6, 1.1)
        g = max(tone_lo, min(tone_hi, g))
        vcol.append((g, g, g))
    set_vcol(ob, vcol)
    return ob


def litter_at(name, x, y, r=0.55):
    """树脚落叶圈: 腐叶地斑 + 散叶小片 (小片补常数vcol防join黑块)"""
    ground_patch(f"{name}_patch", x, y, r, m_litter, 0.5, 0.95)
    for k in range(5):
        a = random.uniform(0, 2 * pi)
        rr = random.uniform(0.25, 0.9) * r
        px_, py_ = x + rr * cos(a), y + rr * sin(a)
        ob = add_box(f"{name}_leaf{k}", (0.09, 0.06, 0.004), (px_, py_, 0.016),
                     rot=(random.uniform(-0.15, 0.15), random.uniform(-0.15, 0.15),
                          random.uniform(0, pi)), mat=m_litter)
        set_vcol_uniform(ob, random.uniform(0.55, 0.95))


def prism(name, poly2d, origin, fdir, rt, up, near, far):
    """棱柱切割器: 强制 CCW (镜像件 CW 会崩坏 EXACT 求解器)"""
    n = len(poly2d)
    area2 = sum(poly2d[i][0] * poly2d[(i + 1) % n][1]
                - poly2d[(i + 1) % n][0] * poly2d[i][1] for i in range(n))
    if area2 < 0:
        poly2d = poly2d[::-1]
    o = Vector(origin)
    vs = []
    for rr, uu in poly2d:
        vs.append(tuple(o + fdir * near + rt * rr + up * uu))
    for rr, uu in poly2d:
        vs.append(tuple(o + fdir * far + rt * rr + up * uu))
    fs = []
    for i in range(n):
        j = (i + 1) % n
        fs.append((i, j, n + j, n + i))
    fs.append(tuple(range(n - 1, -1, -1)))
    fs.append(tuple(range(n, 2 * n)))
    return _new_obj(name, vs, fs, None, False)


def bowl(name, C, R, phi_lo, phi_hi, mat, seg=16, ring=5):
    """开口碗面 (南瓜暗腔/内焰): 绕 +f 轴的球带"""
    vs = []
    for j in range(ring + 1):
        phi = phi_lo + (phi_hi - phi_lo) * j / ring
        sp, cp = sin(phi), cos(phi)
        for i in range(seg):
            az = 2 * pi * i / seg
            d = f_axis * cp + (up_axis * cos(az) + rt_axis * sin(az)) * sp
            vs.append((C[0] + d.x * R, C[1] + d.y * R, C[2] + d.z * R))
    fs = []
    for j in range(ring):
        r0, r1 = j * seg, (j + 1) * seg
        for i in range(seg):
            i2 = (i + 1) % seg
            fs.append((r0 + i, r1 + i, r1 + i2, r0 + i2))
    return _new_obj(name, vs, fs, mat, True)


def pumpkin_body(name, C, rx, rz, seg, ring, mat, lobes=8, amp=0.075):
    """瓣纹南瓜体: 正弦瓣 + 底压扁 + 顶肩内收 + 瓣谷顶点色压暗"""
    vs, vcol = [], []
    for j in range(ring + 1):
        phi = pi * j / ring
        sp, cp = sin(phi), cos(phi)
        for i in range(seg):
            th = 2 * pi * i / seg
            lobe = 1 + amp * sin(lobes * th) * (sp ** 1.4)
            px_ = rx * sp * cos(th) * lobe
            py_ = rx * sp * sin(th) * lobe
            pz_ = rz * cp
            if pz_ < 0:
                pz_ *= 0.8
            if phi < 0.42:
                pz_ *= 0.94
            vs.append((C[0] + px_, C[1] + py_, C[2] + pz_))
            g = 0.85 + 0.40 * ((0.5 + 0.5 * sin(lobes * th)) ** 0.65)
            g *= 0.8 if cp < -0.2 else 1.0
            g *= random.uniform(0.96, 1.04)
            vcol.append((g, g, g))
    fs = []
    for j in range(ring):
        r0, r1 = j * seg, (j + 1) * seg
        for i in range(seg):
            i2 = (i + 1) % seg
            fs.append((r0 + i, r1 + i, r1 + i2, r0 + i2))
    ob = _new_obj(name, vs, fs, mat, True)
    set_vcol(ob, vcol)
    return ob


def leaf(name, base, yaw, size=0.16):
    """弯拱叶片: 复用草叶弯带 (自建拱带会渲成小帐篷)"""
    rc = hex_lin("#1E3618")[:3]
    tc = hex_lin("#4E7A32")[:3]
    return blade(name, base, size, size * 0.3, yaw, random.uniform(0.65, 0.95),
                 m_leaf, rc, tc, lean=0.75, twist=random.uniform(-0.35, 0.35))


def vine_link(name, p1, p2, s=1.0, leaves=2):
    """藤蔓: 贴地起伏管 + 嫩叶 (南瓜簇连接)"""
    p1, p2 = Vector(p1), Vector(p2)
    pts = []
    for k in range(6):
        t = k / 5
        p = p1.lerp(p2, t)
        p.z = 0.015 + 0.035 * sin(t * pi)
        perp = Vector((-(p2.y - p1.y), p2.x - p1.x, 0)).normalized()
        p = p + perp * (0.06 * sin(t * 6.28))
        pts.append(p)
    tube_frustum(f"{name}_vine", pts, [0.018 * s] * 6, m_pstem, sides=5, cap_end_fan=False)
    for k in range(leaves):
        t = 0.25 + 0.5 * k
        lp = pts[1 + int(min(t, 0.98) * 4)]
        a = random.uniform(0, 2 * pi)
        leaf(f"{name}_lf{k}", lp, a, 0.3 * s)


def mushroom_v2(name, x, y, s=1.0):
    """发光蘑菇 v2: 波缘伞盖 + 菌褶发光底盘 + 弯柄 + 苔盘小草 (荧光逻辑: 光从褶下漏)"""
    ground_patch(f"{name}_moss", x, y, 0.45 * s, m_moss, 0.6, 1.0)
    tilt = random.uniform(-0.2, 0.2)
    add_cyl(f"{name}_st", 0.035 * s, 0.26 * s, (x + tilt * 0.3, y, 0.13 * s),
            rot=(tilt, 0, 0), mat=m_mushstem, verts=7)
    capC = Vector((x + tilt * 0.55, y, 0.3 * s))
    vs, fs = [], []
    seg, ring = 14, 4
    ph = random.uniform(0, pi)
    for j in range(ring + 1):
        t = j / ring
        phi = pi * 0.5 * (0.25 + 0.75 * t)
        for i in range(seg):
            a = 2 * pi * i / seg + ph
            rr_ = 0.17 * s * sin(phi) * (1 + 0.14 * sin(5 * a))
            vs.append((capC.x + rr_ * cos(a), capC.y + rr_ * sin(a),
                       capC.z + 0.17 * s * cos(phi) * 0.6))
    for j in range(ring):
        r0, r1 = j * seg, (j + 1) * seg
        for i in range(seg):
            i2 = (i + 1) % seg
            fs.append((r0 + i, r1 + i, r1 + i2, r0 + i2))
    _new_obj(f"{name}_cap", vs, fs, m_mush, True)
    add_cyl(f"{name}_gill", 0.15 * s, 0.014 * s, tuple(capC - Vector((0, 0, 0.012 * s))),
            mat=m_mushgill, verts=14)
    for k in range(3):
        a = random.uniform(0, 2 * pi)
        add_sphere(f"{name}_spot{k}", 0.016 * s,
                   tuple(capC + Vector((0.1 * s * cos(a), 0.1 * s * sin(a), 0.06 * s))),
                   mat=m_mushspot, seg=6, ring=4)
    tuft_v3(f"{name}_t0", x + 0.35 * s, y + 0.2 * s, 0.5, n=3)


def haystack_v2(name, hx, hy):
    """干草堆 v2: 瓣纹圆垛 (稻草本色×灰阶vcol) + 外露草叶 + 顶部草束"""
    ground_patch(f"{name}_g", hx, hy, 1.15, m_litter, 0.55, 0.9)
    pumpkin_body(f"{name}_dome", (hx, hy, 0.36), 0.82, 0.42, 18, 8, m_hay,
                 lobes=6, amp=0.1)
    for k in range(20):
        a = random.uniform(0, 2 * pi)
        rr_ = random.uniform(0.55, 0.85)
        px_, py_ = hx + rr_ * cos(a), hy + rr_ * sin(a)
        tone = random.uniform(0.7, 1.3)
        c_lo = tuple(c * tone for c in hex_lin("#8A6A30")[:3])
        c_hi = tuple(c * tone for c in hex_lin("#D2A85C")[:3])
        blade(f"{name}_s{k}", (px_, py_, random.uniform(0.15, 0.5)),
              random.uniform(0.25, 0.45), 0.018, a + random.uniform(-0.6, 0.6),
              random.uniform(0.5, 1.0), m_strawv, c_lo, c_hi,
              lean=random.uniform(0.4, 0.8))
    for k in range(4):
        a = k * pi / 2 + 0.4
        blade(f"{name}_top{k}", (hx + 0.2 * cos(a), hy + 0.2 * sin(a), 0.72),
              0.4, 0.02, a, 0.8, m_strawv, c_lo, c_hi, lean=0.5)


def add_cone_hat(name, x, y):
    """稻草人帽: 檐 + 锥顶"""
    add_cyl(f"{name}_hatbrim", 0.34, 0.03, (x, y, 2.17), mat=m_cloth, verts=10)
    hz = 0.13
    vs = []
    for i in range(8):
        a = 2 * pi * i / 8
        vs.append((0.3 * cos(a), 0.3 * sin(a), -hz))
    vs.append((0, 0, hz))
    fs = [(i, (i + 1) % 8, 8) for i in range(8)]
    ob = _new_obj(f"{name}_hat", vs, fs, m_cloth, True)
    ob.location = (x, y, 2.3)


def scarecrow(name, x, y, ry=0.0):
    """稻草人 v2: 原骨架 + 弯叶草束袖口/头顶草簇 + 脚下落叶圈"""
    add_cyl(f"{name}_pole", 0.06, 2.0, (x, y, 1.0), mat=m_wood, verts=6)
    add_box(f"{name}_arms", (1.2, 0.07, 0.07), (x, y, 1.5), rot=(0, 0, ry), mat=m_wood)
    add_sphere(f"{name}_head", 0.2, (x, y, 2.05), mat=m_haysolid, seg=10, ring=7)
    add_cone_hat(name, x, y)
    add_box(f"{name}_body", (0.55, 0.3, 0.75), (x, y, 1.15), rot=(0, 0, ry), mat=m_cloth)
    for as_ in (-1, 1):
        px_ = x + cos(ry) * as_ * 0.6
        py_ = y + sin(ry) * as_ * 0.6
        for k in range(5):
            a = random.uniform(0, 2 * pi)
            tone = random.uniform(0.75, 1.2)
            lo = tuple(c * tone for c in hex_lin("#6E5426")[:3])
            hi = tuple(c * tone for c in hex_lin("#B8924A")[:3])
            blade(f"{name}_cuff{as_}_{k}", (px_, py_, 1.44),
                  random.uniform(0.28, 0.4), 0.016, a, random.uniform(0.7, 1.1),
                  m_strawv, lo, hi, lean=0.5)
    for k in range(4):
        a = k * pi / 2 + 0.5
        blade(f"{name}_hair{k}", (x + 0.12 * cos(a), y + 0.12 * sin(a), 2.2),
              0.3, 0.015, a, 0.9, m_strawv, lo, hi, lean=0.6)
    litter_at(f"{name}_lit", x, y, 0.7)
    collider(x, y, 0.5)


def flower_v3(name, x, y, violet=True, s=1.0):
    """花 v3: 弯茎 + 弯拱叶 + 杯形6瓣 (顶点色渐变) + 暖芯 (夜读作灯笼花)"""
    h = 0.22 * s
    sway = random.uniform(-0.3, 0.3)
    tube_frustum(f"{name}_st", [(x, y, 0.01), (x + sway * 0.4, y, h * 0.5),
                                (x + sway, y + sway * 0.3, h)],
                 [0.013 * s, 0.01 * s, 0.007 * s], m_stem, sides=5)
    leaf(f"{name}_lf0", (x + sway * 0.2, y, h * 0.42), random.uniform(0, 2 * pi), 0.15 * s)
    head = Vector((x + sway, y + sway * 0.3, h))
    for k in range(6):
        a = k * 2 * pi / 6 + random.uniform(-0.08, 0.08)
        outw = Vector((cos(a), sin(a), 0))
        d0 = (outw * 0.55 + Vector((0, 0, 1)) * 0.8).normalized()
        axis = d0.cross(Vector((0, 0, 1))).normalized()
        rows = []
        p = head.copy()
        step = 0.055 * s
        for i in range(3):
            t = i / 2
            dd = (outw * (0.5 - 0.62 * t) + Vector((0, 0, 1)) * (0.7 + 0.5 * t)).normalized()
            w = 0.05 * s * (1 - t * 0.4)
            rows.append((p - axis * w, p + axis * w, t))
            p = p + dd * step
        if violet:
            rc, tc = hex_lin("#6A3BB0")[:3], hex_lin("#B57BFF")[:3]
        else:
            rc, tc = hex_lin("#C4701F")[:3], hex_lin("#FFB347")[:3]
        vs = []
        vcol = []
        for l, r, t in rows:
            vs += [tuple(l), tuple(r)]
            tt = t ** 0.9
            c = [rc[k2] + (tc[k2] - rc[k2]) * tt for k2 in range(3)]
            vcol += [c, c]
        fs = []
        for i in range(2):
            a_, b_ = i * 2, i * 2 + 1
            fs.append((a_, b_, b_ + 2))
            fs.append((a_, b_ + 2, a_ + 2))
        ob = _new_obj(f"{name}_p{k}", vs, fs, m_petal, False)
        set_vcol(ob, vcol)
    add_sphere(f"{name}_ct", 0.028 * s, tuple(head + Vector((0, 0, 0.015))), mat=m_core,
               seg=7, ring=4)


# ---------------------------------------------------------------- build ----
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
col = bpy.data.collections.new("ParkEnv")
sc.collection.children.link(col)

DOTS = [HEX["warm"], HEX["orange"], HEX["violet"], HEX["green"]]
tmark("materials ready")

m_ground  = make_mat("PE_Ground", HEX["ground"], rough=0.95)
m_grass   = make_mat("PE_Grass", HEX["grass"], rough=0.95)
m_tuft    = make_vcol_mat("PE_GrassTuft", "#FFFFFF", rough=1.0)  # v3 弯叶 (顶点色渐变)
m_path    = make_mat("PE_Path", HEX["path"], rough=0.8, metal=0.05)
m_iron    = make_mat("PE_Iron", HEX["iron"], rough=0.55, metal=0.8)
m_metal_d = make_mat("PE_MetalDark", HEX["metal_d"], rough=0.6, metal=0.7)
m_steel   = make_mat("PE_Steel", "#3A4152", rough=0.35, metal=0.9)   # 发射器亮钢炮管
m_wood_d  = make_mat("PE_WoodDark", "#3A2A1D", rough=0.9)            # 发射器深木件
m_stone   = make_mat("PE_Stone", HEX["stone"], rough=0.85)
# 墓碑专用顶点色材质 (2026-11-26 墓园 v4): 原 PE_Stone #3A3F4C 在夜园里被月光照到的面只有 2-5/255。
# 下暗上亮的渐变约等于原石材的 2.5-6 倍反照率; 许愿池 / 石像鬼 / 路障仍用 PE_Stone, 不受影响。
m_grst    = make_vcol_mat("PE_GraveStone", "#FFFFFF", rough=0.8)
GV_STONE_LO = hex_lin("#565D6E")[:3]
GV_STONE_HI = hex_lin("#8A93A6")[:3]
# 墓园铁件 (第三批): 电介质深灰蓝。场景没有环境贴图, metalness 0.8 的 PE_Iron 只剩点光高光, 在夜色里是纯黑 ——
# 围栏 / 门拱 / 灯笼挂在灯下也看不出形。园内其余铁件仍用 PE_Iron (全园铁艺材质另行处理)
m_grv_iron = make_mat("PE_GraveIron", "#3A3F52", rough=0.6, metal=0.15)
m_grv_gold = make_mat("PE_GraveGold", "#C9A227", rough=0.45, metal=0.5, emit="#C9A227", strength=0.35)  # 鎏金: 门徽 / 月盘
m_wood    = make_mat("PE_Wood", HEX["wood"], rough=0.85)
m_straw   = make_mat("PE_Straw", HEX["straw"], rough=0.9)
m_cloth   = make_mat("PE_Cloth", HEX["cloth"], rough=0.95)
m_ridge   = make_mat("PE_Ridge", HEX["ridge"], rough=1.0)
m_warm    = make_mat("PE_EmitWarm", HEX["warm"], emit=HEX["warm"], strength=2.6)
m_warm_s  = make_mat("PE_EmitWarmSoft", HEX["warm"], emit=HEX["warm"], strength=1.5)  # 守墓灯烛芯: 近景不糊 bloom (同发射器型别环的 soft 系列)
m_orange  = make_mat("PE_EmitOrange", HEX["orange"], emit=HEX["orange"], strength=2.4)
m_violet  = make_mat("PE_EmitViolet", HEX["violet"], emit=HEX["violet"], strength=2.2)
m_green   = make_mat("PE_EmitGreen", HEX["green"], emit=HEX["green"], strength=2.2)
m_orange_s = make_mat("PE_EmitOrangeSoft", HEX["orange"], emit=HEX["orange"], strength=1.3)  # 发射器型别环: 近景不糊 bloom
m_violet_s = make_mat("PE_EmitVioletSoft", HEX["violet"], emit=HEX["violet"], strength=1.2)
m_green_s  = make_mat("PE_EmitGreenSoft", HEX["green"], emit=HEX["green"], strength=1.2)
m_red     = make_mat("PE_EmitRed", HEX["red"], emit=HEX["red"], strength=2.2)
m_dot     = [make_mat(f"PE_Dot{i}", c, emit=c, strength=2.6) for i, c in enumerate(DOTS)]
m_balloon = [make_mat(f"PE_Balloon{i}", c, emit=c, strength=1.1) for i, c in enumerate(DOTS)]  # 近景不糊 bloom
m_pump    = make_vcol_mat("PE_Pumpkin", "#C87419", rough=0.42)          # v3: 本体不发光, 瓣谷顶点色压暗
m_pump_deep = make_vcol_mat("PE_PumpkinDeep", "#A8541E", rough=0.42)
m_pump_pale = make_vcol_mat("PE_PumpkinPale", "#D9C9A8", rough=0.5)
m_pumpface= make_mat("PE_PumpFace", HEX["pumpface"], emit=HEX["pumpface"], strength=3.0)  # 路灯南瓜顶用
m_cavity  = make_mat("PE_PumpCavity", "#100A06", rough=1.0)
m_glow    = make_mat("PE_PumpGlow", "#2A1608", rough=0.8, emit="#FFC46B", strength=7.0)
m_pstem   = make_mat("PE_PumpStem", "#4A4030", rough=0.9)               # 南瓜蒂/藤蔓
m_stem    = make_mat("PE_Stem", "#3E5230", rough=0.8)                   # 花茎 (绿)
m_trunk   = make_mat("PE_Trunk", "#2E2620", rough=0.9)
m_twig    = make_mat("PE_Twig", "#2A2420", rough=0.9)                   # 枯树细枝 (风摆分层)
m_pinefol = make_vcol_mat("PE_PineFoliage", "#142A24", rough=0.9)  # 广场灯浴下再压暗一档       # v3 修复: 叶层曾有树皮色 bug
m_willow  = make_vcol_mat("PE_WillowFiber", "#FFFFFF", rough=0.95)      # 垂柳飘带 (顶点色渐变)
m_sign_g  = make_mat("PE_SignGate", HEX["violet"], emit=HEX["violet"], strength=1.8)
m_petal   = make_vcol_mat("PE_Petal", "#FFFFFF", rough=0.55)            # 花瓣 (顶点色渐变)
m_leaf    = make_vcol_mat("PE_VineLeaf", "#FFFFFF", rough=0.75)         # 藤叶/草叶 (顶点色渐变)
m_core    = make_mat("PE_FlowerCore", "#2A1608", rough=0.8, emit="#FFE9C4", strength=1.4)
m_mush    = make_mat("PE_MushCap", "#6E5AA6", rough=0.75)
m_mushgill= make_mat("PE_MushGill", "#6B4FA8", rough=0.8, emit="#B08BFF", strength=0.5)
m_mushspot= make_mat("PE_MushSpot", "#6B4FA8", rough=0.8, emit="#B08BFF", strength=0.35)
m_mushstem= make_mat("PE_MushStem", "#B8B0C6", rough=0.85)
m_moss    = make_vcol_mat("PE_GroundMoss", "#1B2E22", rough=1.0)        # 地表苔斑
m_litter  = make_vcol_mat("PE_LeafLitter", "#4E3822", rough=1.0)        # 落叶圈
m_strawv  = make_vcol_mat("PE_StrawV", "#FFFFFF", rough=0.95)           # 草束/干草叶 (顶点色)
m_hay     = make_vcol_mat("PE_Hay", "#A8823A", rough=0.95)              # 干草垛穹体
m_haysolid= make_mat("PE_HaySolid", "#8A6A2E", rough=0.95)              # 稻草人头 (无vcol, 防join黑块)
m_water   = make_mat("PE_WellWater", HEX["water"], rough=0.25, metal=0.4,
                     emit="#4A3A8A", strength=0.8)

# ------------------------------------------------------------ 布局锚点 ----
PLAZA_R = P["plaza_r"]
RING_IN = 34.0          # 内环
RING_OUT = 90.0         # 外环
# 放射支路: (角° blender, r_from, r_to)
SPOKES = [
    (78.0,   30.0, 33.0),    # 东北 -> 过山车排队口 (M3: 预留区拆除, 支路截短到迷宫口)
    (-32.3,  30.0, 95.0),    # 东南 -> 秘境预留区
    (217.6,  30.0, 58.0),    # 西南 -> 幽灵港 (对准东缘缺口 y[-43,-37])
    (146.8,  30.0, 67.0),    # 西北 -> 许愿池
]
CAR_SPUR = (21.8, 19.0, 33.0)   # 木马支路
ZONE_BAY   = (-88, -52, -55, -35)
ZONE_THIRD = (78, 112, -78, -42)
LAUNCHER = (22.0, -22.0)
# 烟花发射器 6 站 (id, kind, blender x,y): A 牡丹×2 / B 垂柳×2 / C 椰芯×2, 炮口朝园心
LAUNCHER_SITES = [
    ("L1", "A", (22.0, -22.0)),    # 广场东北 (原释放器位)
    ("L2", "A", (56.0, 30.0)),     # 木马广场东南缘
    ("L3", "B", (43.5, -45.0)),    # 墓园东缘
    ("L4", "B", (-55.0, 30.0)),    # 许愿池旁
    ("L5", "C", (-30.0, -24.0)),   # 西市集南端
    ("L6", "C", (11.0, -84.0)),    # 南瓜田
]
WELL = (-57.0, 38.0)

def on_path(x, y, margin=0.0):
    """是否落在路面/广场/预留区/设施禁布区 (margin 外扩)"""
    r = hypot(x, y)
    if r < PLAZA_R + 1.0 + margin:                      return True
    if abs(r - RING_IN) < 2.7 + margin:                 return True
    if abs(r - RING_OUT) < 2.8 + margin:                return True
    if abs(x) < 2.4 + margin and -147.5 < y < -17.0:    return True   # 主路
    for ang, r0, r1 in SPOKES:
        a = radians(ang)
        ax, ay = r0 * cos(a), r0 * sin(a)
        bx, by = r1 * cos(a), r1 * sin(a)
        if seg_dist(x, y, ax, ay, bx, by) < 1.5 + margin: return True
    a = radians(CAR_SPUR[0])
    if seg_dist(x, y, CAR_SPUR[1] * cos(a), CAR_SPUR[1] * sin(a),
                CAR_SPUR[2] * cos(a), CAR_SPUR[2] * sin(a)) < 1.5 + margin: return True
    if seg_dist(x, y, 0, -40, 34, -40) < 1.5 + margin:  return True    # 墓园横路
    if seg_dist(x, y, -31.5, -32, -0.5, -32) < 1.5 + margin: return True  # 市集横路
    for x0, x1, y0, y1 in (ZONE_BAY, ZONE_THIRD):
        if x0 - margin < x < x1 + margin and y0 - margin < y < y1 + margin: return True
    # 过山车地面结构 (M3: 站台+排队 / 南瓜田 / 观景塔 / 回流沟)
    if 1.5 - margin < x < 17.5 + margin and 26 - margin < y < 68 + margin: return True
    if 77 - margin < x < 87 + margin and 6 - margin < y < 19 + margin:     return True
    if 76 - margin < x < 88 + margin and 94 - margin < y < 108 + margin:   return True
    if 10 - margin < x < 13 + margin and 12 - margin < y < 45 + margin:    return True
    if hypot(x - 45, y - 18) < 13.5 + margin:           return True   # 木马
    if hypot(x - 34, y + 41) < 9.5 + margin:            return True   # 墓园草皮
    for _lid, _kd, (lx_, ly_) in LAUNCHER_SITES:
        if hypot(x - lx_, y - ly_) < 2.6 + margin: return True   # 发射器禁布区
    if hypot(x - WELL[0], y - WELL[1]) < 2.8 + margin:  return True
    if abs(r - P["fence_r"]) < 2.2 + margin:            return True   # 围墙
    return False

# ---------------- 地面 / 广场 / 道路 ----------------
add_cyl("PE_GroundDisc", P["park_r"], 0.2, (0, 0, -0.15), mat=m_ground, verts=64)
add_cyl("PE_PlazaDisc", PLAZA_R, 0.1, (0, 0, -0.02), mat=m_path, verts=64)
# 广场双发光环: 南向 ±13° 断弧 —— 摩天轮登舱台阶占据南向走廊 (r9~16.2, 半宽 2.2),
# 全圆环会从台阶中段下方穿过/与末级台阶相交, 制造台阶悬浮错觉 (v2.3)
add_torus("PE_PlazaRing1", 15.5, 0.14, (0, 0, 0.07), mat=m_orange, ms=96, ns=6, scale=(1, 1, 0.12))
torus_gap(bpy.data.objects["PE_PlazaRing1"], gap_half_deg=13.0, gap_center_deg=270.0)
add_torus("PE_PlazaRing2", 13.0, 0.10, (0, 0, 0.07), mat=m_violet, ms=96, ns=6, scale=(1, 1, 0.12))
torus_gap(bpy.data.objects["PE_PlazaRing2"], gap_half_deg=13.0, gap_center_deg=270.0)

# 主路 (南入口 -> 广场), 7 段
for k in range(7):
    add_box(f"PE_MainPath{k}", (4.8, 18.5, 0.12), (0, -27.5 - k * 18.4, -0.02), mat=m_path)
# 环路 (内 + 外)
add_torus("PE_LoopPathIn", RING_IN, 1.9, (0, 0, -0.04), mat=m_path, ms=96, ns=10, scale=(1, 1, 0.05))
add_torus("PE_LoopPathOut", RING_OUT, 2.0, (0, 0, -0.04), mat=m_path, ms=128, ns=10, scale=(1, 1, 0.05))
# 放射支路
for i, (ang, r0, r1) in enumerate(SPOKES):
    a = radians(ang)
    add_box(f"PE_Spoke{i}", (r1 - r0 + 4.0, 3.0, 0.12),
            ((r0 + r1) / 2 * cos(a), (r0 + r1) / 2 * sin(a), -0.02),
            rot=(0, 0, a), mat=m_path)
a = radians(CAR_SPUR[0])
add_box("PE_SpokeCarousel", (CAR_SPUR[2] - CAR_SPUR[1] + 4.0, 3.0, 0.12),
        ((CAR_SPUR[1] + CAR_SPUR[2]) / 2 * cos(a), (CAR_SPUR[1] + CAR_SPUR[2]) / 2 * sin(a), -0.02),
        rot=(0, 0, a), mat=m_path)
# 支路: 墓园 (东) / 市集 (西)
add_box("PE_PathGrave", (33.0, 3.0, 0.12), (17.0, -40.0, -0.02), mat=m_path)
add_box("PE_PathStall", (31.0, 3.0, 0.12), (-16.0, -32.0, -0.02), mat=m_path)
# 路缘草皮环 (广场外圈草地色带, 打破纯黑)
# z 向压扁 0.06 -> 0.014 (2026-11-26): 0.06 时三圈环顶分别高出地面 +0.13 / +0.24 / +0.30 m, 而所有路面顶只有 +0.04,
# 主路 / 支路 / 墓园横路穿过这三圈时整段被草皮盖住 (墓园横路 33 m 只剩最后 6 m 可见)。0.014 后环顶 -0.015 / +0.01 / +0.024,
# 仍高于地坪顶 (-0.05) 所以色带还在, 但不再盖住任何路面。
for i, (rr, w) in enumerate(((24.0, 3.2), (44.0, 5.0), (68.0, 6.0))):
    add_torus(f"PE_GrassBand{i}", rr, w, (0, 0, -0.06), mat=m_grass, ms=96, ns=10, scale=(1, 1, 0.014))

# 木马场地 (45,18) r14.6 内把草皮色带压到铺装面以下。2026-11-25 评审时色带顶最高 +0.24, 高过木马铺装 (顶 0.04)
# 与地灯环 (顶 0.10), 从西北 / 东南两侧各盖住约 25° 的地灯环; 2026-11-26 起三条色带全园压扁 (z 向 0.014, 顶最高 +0.024),
# 这段压平保留, 保证场地圆内色带顶不高于 -0.02。压平范围比铺装 (r12.6) 多出 2m: 眼高 1.65m 在
# 16.5m 外看环, 环外 0.3m 处只要高出 0.16m 就挡住视线, 回弹斜坡必须离环 >=2.7m。只压落在场地圆内的顶点,
# 外侧留出一个主分段 (~2.9m) 的斜坡。重跑园区后必须跟 scripts/patch_carousel_colliders.mjs。
def sink_under(ob, cx, cy, r_site, z_max):
    """把 ob 落在 (cx,cy) 半径 r_site 圆内、世界高度高于 z_max 的顶点压到 z_max (ob 无旋转)。"""
    zl = (z_max - ob.location.z) / ob.scale.z
    n = 0
    for v in ob.data.vertices:
        if (v.co.x - cx) ** 2 + (v.co.y - cy) ** 2 < r_site * r_site and v.co.z > zl:
            v.co.z = zl
            n += 1
    ob.data.update()
    return n

for i in range(3):
    print("GRASSBAND_SINK", i, sink_under(bpy.data.objects[f"PE_GrassBand{i}"], 45.0, 18.0, 14.6, -0.02))

tmark("ground/paths done")

# ---------------- 入口大门 (南 r146) ----------------
def park_gate(name, gx, gy, scale=1.0):
    """石造牌楼: 双柱 + 尖顶 + 门楣 + 发光招牌 + 彩点 (scale=1 主门, 0.9 二道门)"""
    s = scale
    px = 3.4 * s
    for sx in (1, -1):
        add_box(f"{name}_Pillar{sx}", (1.7 * s, 1.7 * s, 7.6 * s), (gx + sx * px, gy, 3.8 * s), mat=m_stone)
        add_cone(f"{name}_Tip{sx}", 1.15 * s, 1.3 * s, (gx + sx * px, gy, 8.15 * s), mat=m_metal_d,
                 verts=4, rot=(0, 0, radians(45)))
        add_sphere(f"{name}_Lamp{sx}", 0.26 * s, (gx + sx * px, gy, 8.95 * s), mat=m_warm, seg=12, ring=8)
        collider(gx + sx * px, gy, 1.2 * s)
    add_box(f"{name}_Arch", (8.9 * s, 1.1 * s, 1.0 * s), (gx, gy, 7.0 * s), mat=m_stone)
    add_box(f"{name}_Sign", (4.4 * s, 0.22 * s, 1.5 * s), (gx, gy, 5.6 * s), mat=m_sign_g)
    for k in range(3):
        add_sphere(f"{name}_Dot{k}", 0.14 * s, (gx - 1.3 * s + k * 1.3 * s, gy, 6.4 * s),
                   mat=m_dot[k % 4], seg=10, ring=6)

park_gate("PE_Gate", 0, -146.0, 1.0)
POIS.append((0, -142.0, "entrance"))

# 二道门 (主路中途 y=-60)
park_gate("PE_Gate2", 0, -60.0, 0.88)

# ---------------- 围墙铁艺栅栏 r146 ----------------
n_post = 380
for k in range(n_post):
    th = k * 2 * pi / n_post
    x, y = P["fence_r"] * cos(th), P["fence_r"] * sin(th)
    if y < -143.0 and abs(x) < 5.0:   # 大门开口
        continue
    add_box(f"PE_FencePost{k}", (0.15, 0.15, 2.5), (x, y, 1.25), mat=m_iron)
    add_cone(f"PE_FenceTip{k}", 0.10, 0.4, (x, y, 2.68), mat=m_iron, verts=6)
for rz in (1.15, 1.95):
    add_torus(f"PE_FenceRail{rz}", P["fence_r"], 0.055, (0, 0, rz), mat=m_iron, ms=256, ns=6)

tmark("gate/fence done")

# ---------------- 维多利亚路灯 x28 (三种款式) ----------------
def pumpkin_face(name, x, y, z, ry, s=1.0):
    """南瓜脸: 两眼三角 + 三段嘴 (自发光), 朝向 ry"""
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

lamp_positions = []   # (x, y, face_ry) face_ry = 灯头朝向
for k in range(8):                        # 主路双侧 16
    lamp_positions.append((4.4, -24.0 - k * 14.0, pi))
    lamp_positions.append((-4.4, -24.0 - k * 14.0, 0.0))
for th in (radians(45), radians(135), radians(225), radians(315)):   # 广场对角 4
    lamp_positions.append((15.0 * cos(th), 15.0 * sin(th), th + pi))
for k in range(8):                        # 外环 8 (朝向园心)
    th = radians(22.5 + k * 45.0)
    lx, ly = 96.0 * cos(th), 96.0 * sin(th)
    lamp_positions.append((lx, ly, atan2(-ly, -lx)))

for i, (lx, ly, fry) in enumerate(lamp_positions):
    variant = i % 3
    add_cyl(f"PE_LampBase{i}", 0.24, 0.5, (lx, ly, 0.25), mat=m_iron, verts=10)
    add_cyl(f"PE_LampPole{i}", 0.08, 3.3, (lx, ly, 2.0), mat=m_iron, verts=8)
    if variant == 0:      # 经典球灯
        add_sphere(f"PE_LampGlass{i}", 0.27, (lx, ly, 3.75), mat=m_warm, seg=12, ring=8)
        add_cone(f"PE_LampCap{i}", 0.34, 0.35, (lx, ly, 4.12), mat=m_metal_d, verts=6)
    elif variant == 1:    # 南瓜顶灯
        add_sphere(f"PE_LampPump{i}", 0.30, (lx, ly, 3.72), mat=m_pump,
                   seg=12, ring=8, scale=(1.0, 1.0, 0.72))
        add_cyl(f"PE_LampStem{i}", 0.05, 0.14, (lx, ly, 4.02), mat=m_stem, verts=6)
        # 脸基面取 center-0.17: 眼落在 center+0.04 (不糊顶缘)
        pumpkin_face(f"PE_LampFace{i}", lx, ly, 3.55, fry, s=0.62)
    else:                 # 双头提灯
        add_box(f"PE_LampArm{i}", (0.9, 0.07, 0.07), (lx, ly, 3.6),
                rot=(0, 0, fry + pi / 2), mat=m_iron)
        for sx in (-1, 1):
            hx = lx + sx * 0.4 * cos(fry + pi / 2)
            hy = ly + sx * 0.4 * sin(fry + pi / 2)
            add_cyl(f"PE_LampHang{i}_{sx}", 0.015, 0.22, (hx, hy, 3.45), mat=m_iron, verts=5)
            add_box(f"PE_LampBox{i}_{sx}", (0.17, 0.17, 0.24), (hx, hy, 3.2), mat=m_warm)
            add_cone(f"PE_LampBoxCap{i}_{sx}", 0.15, 0.12, (hx, hy, 3.4), mat=m_metal_d, verts=4)
        add_sphere(f"PE_LampGlass{i}", 0.2, (lx, ly, 3.85), mat=m_warm, seg=10, ring=6)
    collider(lx, ly, 0.4)

# ---------------- 跨路灯串 ----------------
def string_lights(name, p1, p2, sag=0.55, step=0.55, mats=None):
    """悬链线灯串: p1/p2 = (x, y, z), 灯珠循环四色 (mats 可指定循环材质表, 如墓园段只用暖白 + 紫)."""
    p1, p2 = Vector(p1), Vector(p2)
    L = (p2 - p1).length
    n = max(int(L / step), 3)
    cyc = mats or m_dot
    prev = None
    for k in range(n + 1):
        t = k / n
        pt = p1.lerp(p2, t)
        pt.z -= sag * 4 * t * (1 - t)
        if prev is not None:
            cyl_between(f"{name}_c{k}", prev, pt, 0.015, m_iron, verts=5)
        add_sphere(f"{name}_b{k}", 0.055, (pt.x, pt.y, pt.z - 0.09),
                   mat=cyc[k % len(cyc)], seg=8, ring=5)
        prev = pt

def light_pole(name, x, y, h=4.0, attach=None):
    """灯串挂杆: 落地基座 + 铁杆 + 挂环 + 暖白顶珠 (灯串两端没有灯杆 / 树可挂时用; attach = 挂点高度, 默认杆顶下 0.3)"""
    add_cyl(f"{name}_base", 0.17, 0.3, (x, y, 0.15), mat=m_grv_iron, verts=10)
    add_cyl(f"{name}_pole", 0.055, h, (x, y, h / 2), mat=m_grv_iron, verts=8)
    az = attach if attach is not None else h - 0.3
    add_torus(f"{name}_ring", 0.07, 0.016, (x, y, az), mat=m_grv_iron, ms=14, ns=5)
    add_sphere(f"{name}_top", 0.07, (x, y, h + 0.03), mat=m_warm, seg=8, ring=5)
    collider(x, y, 0.2)

def bunting(name, p1, p2, sag=0.6, step=0.5):
    """悬链彩旗串: 三角旗循环四色."""
    p1, p2 = Vector(p1), Vector(p2)
    L = (p2 - p1).length
    n = max(int(L / step), 3)
    prev = None
    for k in range(n + 1):
        t = k / n
        pt = p1.lerp(p2, t)
        pt.z -= sag * 4 * t * (1 - t)
        if prev is not None:
            cyl_between(f"{name}_c{k}", prev, pt, 0.012, m_iron, verts=5)
        if k > 0 and k < n:
            add_cone(f"{name}_f{k}", 0.15, 0.05, (pt.x, pt.y, pt.z - 0.14),
                     mat=m_dot[k % 4], verts=3, rot=(radians(180), 0, random.uniform(0, pi)))
        prev = pt

runs = []
for k in range(7):   # 主路灯杆之间 (双侧)
    runs.append(((4.4, -24.0 - k * 14.0, 3.6), (4.4, -38.0 - k * 14.0, 3.6)))
    runs.append(((-4.4, -24.0 - k * 14.0, 3.6), (-4.4, -38.0 - k * 14.0, 3.6)))
runs.append(((3.4, -146.0, 7.2), (4.4, -122.0, 3.6)))    # 大门 -> 最近灯杆
runs.append(((-3.4, -146.0, 7.2), (-4.4, -122.0, 3.6)))
runs.append(((4.4, -24.0, 3.6), (10.6, -10.6, 3.6)))     # 路灯 -> 广场灯 (斜拉)
runs.append(((-4.4, -24.0, 3.6), (-10.6, -10.6, 3.6)))
runs.append(((10.6, -10.6, 3.6), (10.6, 10.6, 3.6)))     # 广场对角
runs.append(((-10.6, -10.6, 3.6), (-10.6, 10.6, 3.6)))
runs.append(((-24.0, -26.0, 3.2), (-40.0, -30.0, 3.2)))  # 市集上空
runs.append(((26.0, -34.0, 3.7), (40.0, -44.0, 3.7)))    # 墓园 (两端挂灯杆, 见下; 2026-11-26 由 3.2 抬到 3.7)
GRAVE_RUN = len(runs) - 1
# (41,14)->(49,22) 「旋转木马」灯串已于 2026-11-25 删除: 它横穿木马盘面上空 (高 3.56–4.11m),
# 每次重跑园区都会再生成 (11-17 的 strip 脚本只删过一次), 骑乘 / 盘面仰视时是一条穿过天花的黑线
for i, (a_, b_) in enumerate(runs):
    if i == GRAVE_RUN:
        string_lights(f"PE_Str{i}", a_, b_, mats=[m_warm, m_violet])   # 墓园段只留暖白 + 紫
    else:
        string_lights(f"PE_Str{i}", a_, b_)
# 墓园灯串两端挂杆 (2026-11-26): 原先两端悬空在 3.2 m (没有任何杆 / 树 / 门柱), 站在线下看像一串升空的烟花;
# 抬到 3.7 m 后最低珠底离地 3.0 m, 跳起 (眼高 2.84) 不再穿过
light_pole("PE_StrPoleGraveW", 26.0, -34.0)
light_pole("PE_StrPoleGraveE", 40.0, -44.0)

# 主路横跨彩旗 (每对灯杆之间) x8 + 外环灯间彩旗弦 x8
bun_i = 0
for k in range(8):
    yy = -24.0 - k * 14.0
    bunting(f"PE_Bun{bun_i}", (-4.4, yy, 3.6), (4.4, yy, 3.6), sag=0.7, step=0.5)
    bun_i += 1
ring_lamps = [(96.0 * cos(radians(22.5 + k * 45)), 96.0 * sin(radians(22.5 + k * 45)))
              for k in range(8)]
for k in range(8):
    ax, ay = ring_lamps[k]
    bx, by = ring_lamps[(k + 1) % 8]
    bunting(f"PE_Bun{bun_i}", (ax, ay, 3.6), (bx, by, 3.6), sag=2.2, step=0.85)
    bun_i += 1

tmark("lamps/strings/bunting done")

# ---------------- 气球束 x5 ----------------
def balloon_bunch(name, x, y, z0=0.0):
    add_box(f"{name}_w", (0.22, 0.22, 0.3), (x, y, z0 + 0.15), mat=m_wood)   # 配重木座
    tops = []
    for k in range(5):
        bx = x + random.uniform(-0.45, 0.45)
        by = y + random.uniform(-0.45, 0.45)
        bz = z0 + random.uniform(1.9, 2.6)
        add_sphere(f"{name}_b{k}", 0.26, (bx, by, bz), mat=m_balloon[k % 4],
                   seg=10, ring=7, scale=(1.0, 1.0, 1.25))
        cyl_between(f"{name}_s{k}", (x, y, z0 + 0.3), (bx, by, bz - 0.3), 0.012, m_iron, verts=4)
        tops.append((bx, by, bz))
    return tops

for i, (bx, by) in enumerate(((5.5, -143.5), (-5.5, -143.5),
                              (-22.5, -25.5), (-39.5, -35.0), (23.5, -20.5))):
    balloon_bunch(f"PE_Balloon{i}", bx, by)
    collider(bx, by, 0.45)

# ---------------- 枯树 v2 x22 (螺旋/双干/垂枝, 递归分枝 + 根部外扩) ----------------
def spooky_tree(name, x, y, scale=1.0, variant=None):
    """枯树 v3: S弯多段锥干 + 板根 + 递归弯枝(连续变径+尖梢), 主干/细枝分材质 (风摆分层)"""
    variant = variant or random.choice(("spiral", "fork", "weep"))
    h = 3.1 * scale

    def curve_pts(base, dirv, length, segs, drift=0.5):
        pts = [Vector(base)]
        d = Vector(dirv).normalized()
        p = pts[0].copy()
        for _ in range(segs):
            d = (d + Vector((random.uniform(-drift, drift) * 0.4,
                             random.uniform(-drift, 0) * 0.4,
                             random.uniform(-0.12, 0.10)))).normalized()
            d.z = max(d.z, -0.2)
            p = p + d * (length / segs)
            pts.append(p.copy())
        return pts

    # 板根 x5
    for rf in range(5):
        a = rf * 2 * pi / 5 + random.uniform(-0.3, 0.3)
        outw = Vector((cos(a), sin(a), 0))
        base = Vector((x, y, 0)) + outw * 0.1
        end = Vector((x, y, 0)) + outw * random.uniform(0.7, 1.0) * scale + Vector((0, 0, -0.02))
        mid = Vector((x, y, 0.5 * scale)).lerp(end, 0.55)
        mid.z = 0.16 * scale
        tube_frustum(f"{name}_root{rf}", [base, mid, end],
                     [0.14 * scale, 0.08 * scale, 0.02 * scale], m_trunk, sides=6)

    # 主干 S 弯 7 段
    lean = 0.22 if variant == "spiral" else 0.12
    a0 = random.uniform(0, 2 * pi)
    trunk_pts = curve_pts((x, y, 0), (cos(a0) * lean, sin(a0) * lean, 1.0), h, 7, drift=0.45)
    r0 = 0.26 * scale
    radii = [r0 * (0.82 ** i) for i in range(len(trunk_pts))]
    tube_frustum(f"{name}_trunk", trunk_pts, radii, m_trunk, sides=8)

    def grow(prefix, base, dirv, length, radius, depth, weep):
        pts = curve_pts(base, dirv, length, 3 if depth >= 2 else 2, drift=0.7)
        radii = [radius * (0.72 ** i) for i in range(len(pts))]
        tube_frustum(f"{prefix}", pts, radii, m_trunk if depth >= 2 else m_twig,
                     sides=7 if depth >= 2 else 5)
        if depth == 0:
            return
        tip = pts[-1]
        dlast = (pts[-1] - pts[-2]).normalized()
        n_child = 2 if depth <= 1 else random.randint(2, 3)
        for k in range(n_child):
            a = random.uniform(0, 2 * pi)
            tilt = random.uniform(0.45, 0.85)
            nd = (dlast + Vector((cos(a) * tilt, sin(a) * tilt,
                                  random.uniform(-0.15, 0.55)))).normalized()
            if weep and depth <= 1:
                nd = (nd + Vector((0, 0, -1.1))).normalized()
            grow(f"{prefix}_{k}", tip, nd, length * random.uniform(0.58, 0.74),
                 radius * 0.52, depth - 1, weep)

    top = trunk_pts[-1]
    n_primary = 4 if variant != "fork" else 2
    for b in range(n_primary):
        a = b * 2 * pi / n_primary + random.uniform(-0.5, 0.5)
        d = Vector((cos(a) * 0.7, sin(a) * 0.7, random.uniform(0.8, 1.3))).normalized()
        grow(f"{name}_b{b}", top, d, 1.7 * scale, 0.085 * scale, 3, variant == "weep")
    if variant == "fork":   # 双干: 中上部再立两根斜干
        for b in range(2):
            a = random.uniform(0, 2 * pi)
            d = Vector((cos(a) * 0.5, sin(a) * 0.5, 1.0)).normalized()
            grow(f"{name}_f{b}", trunk_pts[4], d, 1.5 * scale, 0.09 * scale, 3, False)
    for b in range(2):      # 中干侧枝
        a = random.uniform(0, 2 * pi)
        d = Vector((cos(a) * 0.9, sin(a) * 0.9, random.uniform(0.3, 0.7))).normalized()
        grow(f"{name}_m{b}", trunk_pts[3 + b], d, 1.0 * scale, 0.05 * scale, 2, variant == "weep")
    litter_at(f"{name}_lit", x, y, 0.9 * scale)
    for t_ in range(random.randint(2, 3)):
        a = random.uniform(0, 2 * pi)
        rr = random.uniform(0.5, 1.0) * scale
        tuft_v3(f"{name}_t{t_}", x + rr * cos(a), y + rr * sin(a), 0.8)
    collider(x, y, 0.65)


def pine_tree(name, x, y, variant="tall", lit=True):
    """缠灯松 v2: 锯齿噪声锥层 (独立针叶材质) + 底缘裙边下垂; 修复叶层曾有树皮色 bug"""
    if variant == "tall":
        layers = ((1.9, 1.7), (1.5, 2.6), (1.15, 3.5), (0.8, 4.35), (0.45, 5.1))
    elif variant == "fat":
        layers = ((2.5, 1.5), (1.9, 2.45), (1.25, 3.3), (0.7, 4.0))
    else:
        layers = ((2.0, 1.6), (1.55, 2.5), (1.05, 3.35), (0.6, 4.1))
    lean_a = random.uniform(0, 2 * pi)
    lean = 0.2 if variant == "crooked" else 0.0
    add_cyl(f"{name}_trunk", 0.15, 2.4, (x, y, 1.2), mat=m_trunk, verts=7)
    ph = random.uniform(0, pi)
    for li, (cr, cz) in enumerate(layers):
        ox, oy = lean * cz * cos(lean_a), lean * cz * sin(lean_a)
        seg, ring, hl = 14, 5, 1.55
        vs, vcol = [], []
        for j in range(ring + 1):
            t = j / ring
            for i in range(seg):
                a = 2 * pi * i / seg + li * 0.6 + ph
                rr_ = cr * (1 - t * 0.96) * (1 + 0.14 * sin(7 * a + li * 1.7))
                if j == 0:
                    rr_ *= 1.12
                vs.append((x + ox + rr_ * cos(a), y + oy + rr_ * sin(a),
                           cz + 0.1 + t * hl + 0.3 * cr * (t - 1)))
                g = 0.55 + 0.45 * t
                vcol.append((g, g, g))
        fs = []
        for j in range(ring):
            r0, r1 = j * seg, (j + 1) * seg
            for i in range(seg):
                i2 = (i + 1) % seg
                if j == ring - 1:
                    fs.append((r0 + i, r1 + i, r1 + i2))
                else:
                    fs.append((r0 + i, r1 + i, r1 + i2, r0 + i2))
        ob = _new_obj(f"{name}_l{li}", vs, fs, m_pinefol, True)
        set_vcol(ob, vcol)
    if lit:
        for k in range(10):
            th2 = k * 2 * pi / 10
            li = k % len(layers)
            cr, cz = layers[li]
            rr_ = cr * 0.85
            t_d = (1 - 0.85) / 0.96
            pz_ = cz + 0.1 + t_d * 1.55 + 0.3 * cr * (t_d - 1)
            ox, oy = lean * cz * cos(lean_a), lean * cz * sin(lean_a)
            add_sphere(f"{name}_dot{k}", 0.07,
                       (x + ox + rr_ * cos(th2), y + oy + rr_ * sin(th2), pz_),
                       mat=m_dot[k % 4], seg=8, ring=5)
    tuft_v3(f"{name}_t0", x + 0.9, y - 0.4, 0.75)
    litter_at(f"{name}_lit", x, y, 0.7)
    collider(x, y, 1.0)


def willow_tree(name, x, y, scale=1.0):
    """垂柳 v2: 弯 lean 干 + 沿上干分布的锥形垂飘带 (顶点色渐变, 材质独立供风摆)"""
    h = 3.3 * scale
    lean_a = random.uniform(0, 2 * pi)
    ld = Vector((cos(lean_a) * 0.4, sin(lean_a) * 0.4, 1)).normalized()
    pts = [Vector((x, y, 0))]
    p = pts[0].copy()
    for _ in range(4):
        ld = (ld + Vector((random.uniform(-0.1, 0.1), random.uniform(-0.1, 0.1), 0))).normalized()
        p = p + ld * (h / 4)
        pts.append(p.copy())
    tube_frustum(f"{name}_trunk", pts,
                 [0.2 * scale, 0.165 * scale, 0.13 * scale, 0.1 * scale, 0.07 * scale],
                 m_trunk, sides=8)
    crown = pts[-1]
    for b in range(3):
        a = random.uniform(0, 2 * pi)
        d = Vector((cos(a), sin(a), 0.9)).normalized()
        tube_frustum(f"{name}_up{b}", [crown, crown + d * (1.0 * scale)],
                     [0.05 * scale, 0.015 * scale], m_trunk, sides=5)
    anchors = [pts[2] + Vector((0, 0, 0.1)), pts[3] + Vector((0, 0, 0.05)), crown]
    for s_ in range(36):
        a = random.uniform(0, 2 * pi)
        anchor = anchors[s_ % len(anchors)]
        rr_ = random.uniform(0.1, 0.5) * scale
        base = anchor + Vector((cos(a) * rr_, sin(a) * rr_, random.uniform(0.0, 0.3)))
        d = Vector((cos(a) * 0.85, sin(a) * 0.85, random.uniform(0.05, 0.25))).normalized()
        segs = 8
        step = random.uniform(0.22, 0.32) * scale
        rows = []
        p = base.copy()
        axis = d.cross(Vector((0, 0, 1))).normalized()
        for i in range(segs + 1):
            t = i / segs
            dd = (d + Vector((0, 0, -2.2 * t ** 1.1))).normalized()
            w = 0.045 * scale * (1 - t) ** 0.8 + 0.004
            rows.append((p - axis * w, p + axis * w, t))
            p = p + dd * step
        vs = []
        vcol = []
        rc = hex_lin("#233629")[:3]
        tc = hex_lin("#4E6845")[:3]
        for l, r, t in rows:
            vs += [tuple(l), tuple(r)]
            tt = t ** 0.8
            c = [rc[k] + (tc[k] - rc[k]) * tt for k in range(3)]
            vcol += [c, c]
        fs = []
        for i in range(segs):
            a_, b_ = i * 2, i * 2 + 1
            fs.append((a_, b_, b_ + 2))
            fs.append((a_, b_ + 2, a_ + 2))
        ob = _new_obj(f"{name}_w{s_}", vs, fs, m_willow, False)
        set_vcol(ob, vcol)
    litter_at(f"{name}_lit", x, y, 0.8 * scale)
    collider(x, y, 0.8)


FACES = {
    "classic": {
        "eyes": [[(-0.155, 0.045), (-0.055, 0.045), (-0.105, 0.15)],
                 [(0.155, 0.045), (0.055, 0.045), (0.105, 0.15)]],
        "mouth": [(-0.17, -0.02), (-0.125, 0.05), (-0.08, -0.01), (-0.04, 0.05),
                  (0.0, -0.01), (0.04, 0.05), (0.08, -0.01), (0.125, 0.05),
                  (0.17, -0.02), (0.11, -0.115), (-0.11, -0.115)],
    },
    "scowl": {
        "eyes": [[(-0.17, 0.02), (-0.06, 0.09), (-0.16, 0.12)],
                 [(0.17, 0.02), (0.06, 0.09), (0.16, 0.12)]],
        "mouth": [(-0.15, -0.02), (-0.10, -0.075), (-0.05, -0.03), (0.0, -0.075),
                  (0.05, -0.03), (0.10, -0.075), (0.15, -0.02), (0.08, -0.13),
                  (-0.08, -0.13)],
    },
    "cute": {
        "eyes": [[(-0.15, 0.06), (-0.07, 0.06), (-0.055, 0.10), (-0.13, 0.10)],
                 [(0.15, 0.06), (0.07, 0.06), (0.055, 0.10), (0.13, 0.10)]],
        "mouth": [(cos(2 * pi * k / 8) * 0.062, sin(2 * pi * k / 8) * 0.055 - 0.055)
                  for k in range(8)],
    },
}


def tuft_v3(name, x, y, scale=1.0, n=None):
    """草丛 v3: 根盘 + 7±2 弯曲叶 (风摆目标材质 PE_GrassTuft)"""
    add_sphere(f"{name}_root", 0.1 * scale, (x, y, 0.012), mat=m_ground, seg=8, ring=4,
               scale=(1.0, 1.0, 0.24))
    n = n or random.randint(6, 9)
    for b in range(n):
        a = random.uniform(0, 2 * pi)
        blen = random.uniform(0.26, 0.48) * scale
        if random.random() < 0.16:
            blen *= 1.5   # 抽穗长叶
        bw = random.uniform(0.028, 0.042) * scale
        bend = random.uniform(0.55, 1.15)
        root, tip = blade_tone()
        blade(f"{name}_b{b}", (x, y, 0.01), blen, bw, a, bend, m_tuft,
              root, tip, lean=random.uniform(0.12, 0.32), twist=random.uniform(-0.5, 0.5))


def jack_o_lantern(name, x, y, z=0.0, ry=0.0, s=1.0, shape=None):
    """南瓜 v3: 瓣纹体(不发光) + EXACT 真雕空脸(贯通切割) + 暗腔 + 内焰 + S弯蒂; 三色三脸谱"""
    global f_axis, rt_axis, up_axis
    shape = shape or random.choice(("round", "round", "tall", "flat"))
    sz = {"round": 0.86, "tall": 1.06, "flat": 0.68}[shape]
    roll = random.random()
    if roll < 0.68:
        mat, face = m_pump, "classic"
    elif roll < 0.88:
        mat, face = m_pump_deep, "scowl"
    else:
        mat, face = m_pump_pale, "cute"
    C = Vector((x, y, z + 0.34 * s * sz * 0.92))
    rx, rz = 0.34 * s, 0.34 * s * sz
    body_ob = pumpkin_body(f"{name}_body", C, rx, rz, 20, 12, mat)
    tint = random.uniform(0.9, 1.04)   # 逐实例明度差
    attr = body_ob.data.color_attributes[0]
    buf = [0.0] * (len(attr.data) * 4)
    attr.data.foreach_get("color", buf)
    attr.data.foreach_set("color", [c * tint if i % 4 < 3 else 1.0
                                    for i, c in enumerate(buf)])

    f_axis = Vector((cos(ry), sin(ry), 0.0))
    rt_axis = Vector((-sin(ry), cos(ry), 0.0))
    up_axis = Vector((0, 0, 1))
    spec = FACES[face]
    cutters = []
    ci = 0
    for poly in spec["eyes"]:
        ci += 1
        prism(f"{name}_cut_e{ci}", [(r_ * s, u_ * s) for r_, u_ in poly],
              C, f_axis, rt_axis, up_axis, -0.6 * s, 0.5 * s)
        cutters.append(col.objects[f"{name}_cut_e{ci}"])
    ci += 1
    prism(f"{name}_cut_m", [(r_ * s, u_ * s) for r_, u_ in spec["mouth"]],
          C, f_axis, rt_axis, up_axis, -0.6 * s, 0.5 * s)
    cutters.append(col.objects[f"{name}_cut_m"])

    # 逐个 EXACT 雕刻 — 合并多腔切割器会让求解器崩坏; 贯通切割(near<0)让内焰可见
    for cob in cutters:
        mod = body_ob.modifiers.new("carve", 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.solver = 'EXACT'
        mod.object = cob
        dg = bpy.context.evaluated_depsgraph_get()
        me_new = bpy.data.meshes.new_from_object(body_ob.evaluated_get(dg))
        body_ob.modifiers.remove(mod)
        old = body_ob.data
        body_ob.data = me_new
        bpy.data.meshes.remove(old)
        bpy.data.objects.remove(cob, do_unlink=True)

    bowl(f"{name}_cav", C, 0.30 * s * min(sz, 1.0), radians(72), radians(180), m_cavity, 18, 6)
    bowl(f"{name}_flame", C, 0.283 * s * min(sz, 1.0), radians(95), radians(178), m_glow, 14, 4)

    top = C + Vector((0, 0, rz * 0.96))
    sway = Vector((cos(ry + pi / 2), sin(ry + pi / 2), 0))
    pts = [top + Vector((0, 0, 0.015 * s)),
           top + sway * 0.03 * s + Vector((0, 0, 0.055 * s)),
           top + sway * 0.07 * s + Vector((0, 0, 0.09 * s)),
           top + sway * 0.11 * s + Vector((0, 0, 0.115 * s))]
    tube_frustum(f"{name}_stem", pts,
                 [0.042 * s, 0.036 * s, 0.028 * s, 0.02 * s], m_pstem, sides=7)


# ---------------- 南瓜灯放置 (布局不变) + v3 瓜簇/藤蔓 ----------------
pump_plan = [
    # 主路纵列
    (2.9, -21.0), (-3.1, -23.5), (3.0, -35.0), (-2.9, -37.5),
    (2.8, -49.0), (-3.2, -51.5), (2.9, -63.0), (-3.0, -65.5),
    (1.2, -81.5), (-1.4, -81.5),
    (2.9, -93.0), (-3.1, -95.5), (2.9, -107.0), (-3.2, -109.5),
    (2.8, -121.0), (-3.2, -123.5), (2.9, -135.0), (-3.0, -137.5),
    # 广场两翼
    (12.0, -12.0), (-12.0, -12.0), (13.5, 8.0), (-13.0, 6.0),
    (16.5, 13.0), (-16.0, 14.0),
    # 墓园/市集
    (30.5, -36.5), (24.0, -43.0), (-22.0, -28.5), (-29.0, -33.0),
    # 新分区入口
    (13.5, 68.5), (18.5, 67.0),           # 过山车
    (-50.0, -38.5), (-54.5, -41.5),       # 幽灵港
    (79.0, -52.5), (81.5, -56.0),         # 秘境
    (18.8, -18.4), (24.5, -24.5),         # 烟花释放器
    (-55.2, 35.2),                        # 许愿池
    # 外环
    (91.6, 16.2), (-16.2, 91.6), (-91.6, -16.2), (16.2, -91.6),
]
pump_spots = []
for i, (x, y) in enumerate(pump_plan):
    jack_o_lantern(f"PE_Pump{i}", x, y, 0.0, ry=random.uniform(0, 2 * pi),
                   s=random.uniform(0.9, 1.25))
    pump_spots.append((x, y))
    collider(x, y, 0.55)
    # v3 瓜簇: 每 3 盏带 1-2 只伴生小瓜 (挡路则省略) + 藤蔓相连
    if i % 3 == 0:
        for c in range(random.choice((1, 2))):
            a2 = random.uniform(0, 2 * pi)
            cx2, cy2 = x + 0.62 * cos(a2), y + 0.62 * sin(a2)
            if on_path(cx2, cy2, 0.5):
                continue
            jack_o_lantern(f"PE_PumpC{i}_{c}", cx2, cy2, 0.0, ry=random.uniform(0, 2 * pi),
                           s=random.uniform(0.42, 0.62))
            collider(cx2, cy2, 0.38)
            vine_link(f"PE_PumpV{i}_{c}", (x, y, 0), (cx2, cy2, 0), s=1.0, leaves=2)

# 打卡点: 10 个南瓜簇 (app 坐标在导出时换算)
POIS.extend([
    (3.0, -35.0, "pumpkin_path_s"),
    (12.0, -12.0, "pumpkin_plaza_e"),
    (-12.0, -12.0, "pumpkin_plaza_w"),
    (30.5, -36.5, "pumpkin_grave"),
    (-22.0, -28.5, "pumpkin_stall"),
    (5.5, 27.0, "pumpkin_coast"),    # M3: 原位 (13.5,68.5) 落入站台区 -> 迁排队迷宫口
    (-50.0, -38.5, "pumpkin_bay"),
    (79.0, -52.5, "pumpkin_east"),
    (-55.2, 35.2, "pumpkin_well"),
    (16.2, -91.6, "pumpkin_field"),
])

# ---------------- 草丛 ~600 (v3 弯叶, 风摆目标) ----------------
tufts = []
tries = 0
while len(tufts) < 600 and tries < 4000:
    tries += 1
    ang = random.uniform(0, 2 * pi)
    rr = 138.0 * random.random() ** 0.72   # 靠外略密
    x, y = rr * cos(ang), rr * sin(ang)
    if on_path(x, y, 1.6):
        continue
    ok = True
    for px_, py_ in pump_spots:
        if (px_ - x) ** 2 + (py_ - y) ** 2 < 2.2 ** 2:
            ok = False
            break
    if not ok:
        continue
    tufts.append((x, y))
for i, (x, y) in enumerate(tufts):
    tuft_v3(f"PE_Tuft{i}", x, y, scale=random.uniform(0.85, 1.2))

# ---------------- 地表杂色地斑 (苔藓/腐叶, 打破纯黑地面) ----------------
patch_spots = []
tries = 0
while len(patch_spots) < 55 and tries < 3000:
    tries += 1
    ang = random.uniform(0, 2 * pi)
    rr = 136.0 * random.random() ** 0.7
    x, y = rr * cos(ang), rr * sin(ang)
    if on_path(x, y, 2.2):
        continue
    ok = True
    for px_, py_ in patch_spots:
        if (px_ - x) ** 2 + (py_ - y) ** 2 < 7.0 ** 2:
            ok = False
            break
    if not ok:
        continue
    patch_spots.append((x, y))
    if random.random() < 0.7:
        ground_patch(f"PE_GP{len(patch_spots)}", x, y, random.uniform(1.6, 3.6), m_moss)
    else:
        ground_patch(f"PE_GP{len(patch_spots)}", x, y, random.uniform(1.2, 2.4), m_litter, 0.5, 0.95)

# ---------------- 发光蘑菇圈 x8 (v2 波缘伞盖 + 菌褶底发光) ----------------
mush_circles = [(12, -50.5), (38, -44), (60, 45), (-15, -70), (-75, 10),
                (30, -80), (75, -20), (-40, 80)]
for ci, (cx, cy) in enumerate(mush_circles):
    n_m = random.randint(5, 8)
    ring_r = random.uniform(0.8, 1.3)
    for k in range(n_m):
        a = k * 2 * pi / n_m + random.uniform(-0.2, 0.2)
        mx = cx + ring_r * cos(a) + random.uniform(-0.15, 0.15)
        my = cy + ring_r * sin(a) + random.uniform(-0.15, 0.15)
        ms_ = random.uniform(0.7, 1.3)
        mushroom_v2(f"PE_Mush{ci}_{k}", mx, my, ms_)
    # 第一圈原在 (30,-38) 横路路口北侧, 碰撞圆挤窄了进墓园的路 (2026-11-26 第三批挪到西支路北侧 app (12,50.5) 引路)
    # 碰撞圆 = 蘑菇圈本身 (2026-11-26 由 ring_r + 0.5 收回): 旧圆的隐形墙比可见蘑菇圈外扩 0.4-0.5 m,
    # 菇体就长在 ring_r 上 (±0.15 抖动, 伞盖半径 <= 0.22), 加玩家半径 0.38 后人仍进不到圈里
    collider(cx, cy, ring_r)


def flower(name, x, y, violet=True, s=1.0):
    flower_v3(name, x, y, violet, s)   # v3: 杯形瓣+暖芯 (见 helper 区)

flower_spots = []
row = 0
for yy in [(-30.0 - k * 5.5) for k in range(21)]:
    for sx in (1, -1):
        cx = sx * 3.5 + random.uniform(-0.25, 0.25)
        cy = yy + random.uniform(-0.5, 0.5)
        violet = (row + (sx > 0)) % 2 == 0
        for f in range(4):
            fx = cx + random.uniform(-0.4, 0.4)
            fy = cy + random.uniform(-0.4, 0.4)
            flower(f"PE_Flower{row}_{sx}_{f}", fx, fy, violet,
                   s=random.uniform(0.8, 1.2))
        flower_spots.append((cx, cy))
    row += 1
# 广场外圈花床 x6
for k, th in enumerate((radians(10), radians(70), radians(130),
                        radians(190), radians(310), radians(350))):
    cx, cy = 20.8 * cos(th), 20.8 * sin(th)
    for f in range(5):
        fx = cx + random.uniform(-0.5, 0.5)
        fy = cy + random.uniform(-0.5, 0.5)
        flower(f"PE_FlowerPlaza{k}_{f}", fx, fy, f % 2 == 0, s=random.uniform(0.9, 1.25))
    flower_spots.append((cx, cy))

def gv_lantern_head(name, x, y, cz0, cz1, cr):
    """灯头 (守墓灯 / 门柱灯共用): 六棱铁笼 + 暖白烛芯 + 紫火尖。cz0 / cz1 = 笼的上下环高, cr = 六边形外接圆半径"""
    for czn in (cz0, cz1):
        add_torus(f"{name}_ring{czn:.2f}", cr, 0.016, (x, y, czn), mat=m_grv_iron, ms=6, ns=5)
    for k in range(6):
        a = k * pi / 3
        cyl_between(f"{name}_bar{k}", (x + cr * cos(a), y + cr * sin(a), cz0),
                    (x + cr * cos(a), y + cr * sin(a), cz1), 0.012, m_grv_iron, verts=4)
    add_cone(f"{name}_cap", cr + 0.06, 0.17, (x, y, cz1 + 0.095), mat=m_grv_iron, verts=6)
    add_sphere(f"{name}_finial", 0.03, (x, y, cz1 + 0.20), mat=m_violet, seg=8, ring=5)
    add_cyl(f"{name}_candle", 0.075, 0.22, (x, y, cz0 + 0.17), mat=m_warm_s, verts=8)
    add_sphere(f"{name}_flame", 0.06, (x, y, cz0 + 0.34), mat=m_violet, seg=8, ring=5, scale=(1, 1, 1.35))

def grave_lantern(name, x, y):
    """守墓灯 v2 (2026-11-26): 落地铁柱 (两道箍) + 六棱铁笼 + 暖白烛芯 + 紫火尖, 灯头中心离地约 2.1 m。
    真实点光不烘进 glb —— 由 park_light 登记进 colliders.json 的 lights, 运行时 (src/core/world.js) 按清单建灯。
    高度与强度是配套的: 点光是平方反比, 灯头 1.44 m 时 1.4 m 外的碑过曝成白块; 抬到 2.1 m、强度 40 cd 后
    2 m 外的碑面约 170/255、5 m 外约 60、8 m 外约 30, 都在辉光阈值以下 —— 所以碑要离灯 >= 2 m。"""
    add_cyl(f"{name}_base", 0.17, 0.07, (x, y, 0.035), mat=m_grv_iron, verts=10)
    add_cyl(f"{name}_base2", 0.11, 0.10, (x, y, 0.12), mat=m_grv_iron, verts=10)
    cz0, cz1 = 1.90, 2.32
    add_cyl(f"{name}_post", 0.05, cz0 - 0.17, (x, y, (cz0 + 0.17) / 2), mat=m_grv_iron, verts=8)
    for hz in (0.6, 1.5):
        add_torus(f"{name}_hoop{hz:.2f}", 0.063, 0.014, (x, y, hz), mat=m_grv_iron, ms=14, ns=5)
    gv_lantern_head(f"{name}_head", x, y, cz0, cz1, 0.17)
    collider(x, y, 0.2)
    park_light(x, y, cz0 + 0.24, "#FFD9A8", 40, 22, decay=2, tag=name, key="graveyardLight")

def gv_gargoyle(name, x, y, z, ry, s):
    """门柱顶石像鬼 (2026-11-26 第三批第二版): 蹲姿 —— 底座 + 圆盘 + 拱背的躯干 (后半身用一个大半重叠的椭球撑宽) + 前腿 (贴圆盘前伸) +
    头 (吻部 / 双角 / 紫眼) + 每侧三片翼 (主翼 / 竖起的肘翼 / 前小叶)。x / y = Blender 坐标, z = 底座底高, ry = 前向 (头朝哪边),
    s = 缩放 (门柱顶 0.4, 通高约 0.78 m)。每个件都要带顶点色 (墓碑石是顶点色材质)。
    第一版照搬园里 gargoyle() 的三棱锥翼 (园大门那两尊是 1:1), 缩到 0.4 以后翼片与躯干之间露天空, 从每条来路看都像「球 + 几片
    飘着的纸飞机」; 臀部 / 前爪单独用球也会读成挂在身侧的球。所以翼片改成四面体: 翼根两点都埋在躯干里, 不可能有悬空件。
    造型沙盒 (同款图元 + 门灯位置, 几秒一轮): shots/graveyard_review/b3/garg_test.py + garg_new.py"""
    def L_(da, db):
        return (x + cos(ry) * da - sin(ry) * db, y + sin(ry) * da + cos(ry) * db)
    def vc(ob, hc):
        gv_stone_vcol(ob, lambda v: v.co.z + hc)
    cx_, cy_ = L_(0, 0)
    vc(add_box(f"{name}_ped", (1.1 * s, 1.1 * s, 0.5 * s), (cx_, cy_, z + 0.25 * s), rot=(0, 0, ry), mat=m_grst), z + 0.25 * s)
    vc(add_cyl(f"{name}_pedtop", 0.5 * s, 0.22 * s, (cx_, cy_, z + 0.6 * s), mat=m_grst, verts=8), z + 0.6 * s)
    vc(add_sphere(f"{name}_body", 0.46 * s, (cx_, cy_, z + 1.0 * s), mat=m_grst, seg=12, ring=8, scale=(1.08, 0.92, 1.0)), z + 1.0 * s)
    rx_, ry_ = L_(-0.16, 0)                                               # 后半身: 大半重叠在躯干里, 把背撑成拱起的卵形 (单独的球会读成挂着的球)
    vc(add_sphere(f"{name}_rump", 0.44 * s, (rx_, ry_, z + 0.98 * s), mat=m_grst, seg=12, ring=8, scale=(1.0, 1.04, 0.98)), z + 0.98 * s)
    for hs in (-1, 1):
        px_, py_ = L_(0.52, hs * 0.26)                                     # 前腿: 贴着圆盘往前伸 (扁长椭球, 后端埋在躯干里, 底面落在圆盘顶 0.71s 上)
        vc(add_sphere(f"{name}_fore{hs}", 0.13 * s, (px_, py_, z + 0.80 * s), mat=m_grst, seg=8, ring=6, scale=(2.3, 0.85, 0.72)), z + 0.80 * s)
    hx_, hy_ = L_(0.38, 0)
    vc(add_sphere(f"{name}_head", 0.27 * s, (hx_, hy_, z + 1.38 * s), mat=m_grst, seg=10, ring=7), z + 1.38 * s)
    sx_, sy_ = L_(0.62, 0)
    vc(add_box(f"{name}_snout", (0.24 * s, 0.18 * s, 0.16 * s), (sx_, sy_, z + 1.3 * s), rot=(0, 0, ry), mat=m_grst), z + 1.3 * s)
    for hs in (-1, 1):
        px_, py_ = L_(0.22, hs * 0.17)
        vc(add_cone(f"{name}_horn{hs}", 0.07 * s, 0.32 * s, (px_, py_, z + 1.68 * s), mat=m_grst, verts=5, rot=(radians(-20), 0, ry)), z + 1.68 * s)
        px_, py_ = L_(0.56, hs * 0.1)
        add_sphere(f"{name}_eye{hs}", 0.036 * s, (px_, py_, z + 1.42 * s), mat=m_violet, seg=6, ring=4)
    for hs in (-1, 1):
        def W_(da, db, dz):
            wx_, wy_ = L_(da, db)
            return (wx_, wy_, z + dz * s)
        r1, r2 = W_(0.30, hs * 0.20, 1.20), W_(-0.34, hs * 0.16, 1.10)     # 主翼翼根 (两点都在躯干里)
        t1, t2 = W_(-0.44, hs * 0.86, 1.72), W_(-0.33, hs * 0.88, 1.72)      # 主翼 (外段) 翼尖
        f1, f2 = W_(0.14, hs * 0.62, 1.52), W_(0.20, hs * 0.64, 1.52)       # 前小叶翼尖
        e1, e2 = W_(-0.20, hs * 0.50, 1.86), W_(-0.12, hs * 0.52, 1.86)     # 肘翼 (竖起的中段) 翼尖
        for tag, vs in (("wing", [r1, r2, t1, t2]), ("wingf", [r1, W_(-0.05, hs * 0.30, 1.22), f1, f2]),
                        ("winge", [W_(0.05, hs * 0.28, 1.24), W_(-0.22, hs * 0.24, 1.16), e1, e2])):
            ob = _new_obj(f"{name}_{tag}{hs}", vs, [(0, 1, 2), (1, 0, 3), (0, 3, 2), (1, 2, 3)], m_grst, False)
            gv_stone_vcol(ob, lambda v: v.co.z)


# ---------------- 墓园 v4: 入口前庭 (旧址) + 园中墓园 (南迁新址) + 彼岸花 x4 ----------------
# 第一批 (2026-11-26 评审后): 墓碑专用提亮材质 / 碰撞改盒墙 / 守墓灯 x2 (真实点光)。
# 第二批 (用户选定): 旧址 (34,-41) r8.5 离过山车太近, 南迁到空地 —— 新址 = 椭圆 36x24 m (半轴 18 / 12),
#   心 app (37,58) = blender (37,-58), 边到轨道 22 m; 旧址草皮盘保留作入口前庭; 北侧接路 (前庭 -> 新址北缘)
#   + 西侧支路 (主路东缘 -> 新址西缘)。
# 第三批 (用户选定「丁字一轴一脊 / 规整行列」): 两个门 (石门柱 + 铁艺拱 + 新月星徽 + 柱顶石像鬼, 门洞挂真实点光) /
#   一圈尖桩铁艺围栏 (铁柱 + 双横杆 + 尖桩, 只在两个门处断开) / 园内走道 (东西主走道: 西门 -> 东端焦点庭;
#   北脊: 北门 -> 主走道) / 碑按行重排 (宽面朝走道, 碑身带倾角) / 守墓灯挪到走道两侧 / 灯串在主走道上空之字形横跨 /
#   蘑菇圈挪到西支路旁 / 稻草人守在北门外 / 长椅转向北门。碑型重做、加碑、焦点碑、地面与主题造型留给第四批。
# 随机流约定: 这一段新增的随机一律走墓园自己的 rgv; 全局 random 在段内只保留「改造前就有」的消耗
#   (枯树 spooky_tree 内部 + 段末 GV_LEGACY_DRAWS 占位)。段内也不改 on_path / pump_plan / tree_extras ——
#   那些规则决定其后的散布 (南瓜伴生 / 草丛 / 地斑 / 树) 哪些候选被舍弃, 一改全园就重新随机。
#   所以: 新址 / 新路上原有的散布件在段末按位置确定性清掉; 要挪的固定件 (打卡南瓜) 建完后整体平移;
#   树若落进新址则在树段里确定性推出 (现在无一落入)。
rgv = random.Random(20261126)
GV_EX, GV_EY, GV_EA, GV_EB = 37.0, -58.0, 18.0, 12.0   # 新址椭圆: 心与半轴 (blender x / y)

def gv_inside(x, y, ga=GV_EA, gb=GV_EB):
    """blender (x, y) 是否落在新址椭圆内 (ga / gb = 外扩后的半轴)"""
    return ((x - GV_EX) / ga) ** 2 + ((y - GV_EY) / gb) ** 2 <= 1.0

def gv_on_new_paths(x, y, m=0.0):
    """是否落在园外两条通路上 (blender 坐标, m = 外扩)"""
    return ((33.5 - m < x < 36.5 + m and -48.0 - m < y < -40.0 + m) or
            (2.25 - m < x < 20.25 + m and -56.2 - m < y < -53.2 + m))

def gva(t):
    """新址椭圆上参数角 t 的点, app (x, z): x = 37 + 18 cos t, z = 58 + 12 sin t"""
    return (GV_EX + GV_EA * cos(t), -GV_EY + GV_EB * sin(t))

# 入口前庭 = 旧址草皮盘 (位置尺寸不变); 新墓园草皮盘 = 椭圆。两者重叠 3 m: 同材质、同高度 (+0.01) 的顶面重叠不出痕迹
add_cyl("PE_GraveForecourt", 8.5, 0.08, (34.0, -41.0, -0.03), mat=m_grass, verts=32)
gp = add_cyl("PE_GravePatch", 1.0, 0.08, (GV_EX, GV_EY, -0.03), mat=m_grass, verts=64)
gp.scale = (GV_EA, GV_EB, 1.0)

# 园外通路: 北接路 (app x 33.5..36.5, z 40..48) 与西支路 (app x 2.25..20.25, z 53.2..56.2)。西支路 z 不能取 58:
#   主路东侧 z 52..66 排着路灯 (4.4,52) / 指示牌 (2.3,57.3) / 长椅 (5.6,59) / 二道门牌楼柱 (+-2.99,60),
#   只有 z 52.4..58.9 一条空档 —— 落在路灯与指示牌之间
add_box("PE_PathGraveN", (3.0, 8.0, 0.12), (35.0, -44.0, -0.02), mat=m_path)
add_box("PE_PathGraveW", (18.0, 3.0, 0.12), (11.25, -54.7, -0.02), mat=m_path)
# 园内走道 (第三批): 东西主走道 (中线 = 西支路中线 app z 54.7, 宽 2.4) / 北脊 (中线 app x 35) / 东端焦点庭 (r2.4)
GV_AZ, GV_AW = 54.7, 2.4
GV_GATE_LIGHT_H, GV_GATE_CD = 2.6, 26   # 门的真实点光: 门洞正中的挂高 (m) 与强度 (cd), 由来见 gv_gate 末尾
add_box("PE_PathGraveA", (28.9, GV_AW, 0.12), (33.95, -GV_AZ, -0.02), mat=m_path)
add_box("PE_PathGraveS", (GV_AW, 8.9, 0.12), (35.0, -50.25, -0.02), mat=m_path)
add_cyl("PE_PathGraveF", 2.4, 0.12, (50.4, -GV_AZ, -0.02), mat=m_path, verts=32)

def gv_stone_vcol(ob, height_of):
    """墓碑件顶点色: height_of(v) = 该顶点离地高度 -> 自下而上 GV_STONE_LO -> GV_STONE_HI (1.05 m 处到顶色)"""
    set_vcol(ob, [tuple(GV_STONE_LO[k] + (GV_STONE_HI[k] - GV_STONE_LO[k]) * min(1.0, max(0.0, height_of(v) / 1.05))
                        for k in range(3)) for v in ob.data.vertices])

def gv_gate(name, pa, pb, out_n):
    """墓园的门 (两个门同款): 两根石门柱 (pa / pb = 柱心, app 坐标) + 铁艺拱 (主拱 + 副拱 + 7 根立撑) +
    新月星徽 (拱顶下, 鎏金) + 柱顶石像鬼 + 柱内外两面各一盏挑臂灯头 (只发光); 真实点光挂在门洞正中、离地 2.6 m。
    out_n = 朝园外的单位法向 (app)。
    返回拱顶的 app 坐标 (给灯串挂)"""
    ax, az = pa
    L_ = hypot(pb[0] - ax, pb[1] - az)
    ux, uz = (pb[0] - ax) / L_, (pb[1] - az) / L_     # 门轴方向 a -> b (app)
    phi = atan2(-uz, ux)                             # 门轴在 Blender 里的方位角
    ry = atan2(-out_n[1], out_n[0])                   # 石像鬼前向 (Blender): 朝园外
    ix, iz = -out_n[0], -out_n[1]                     # 朝园内 (走道一侧)
    psi = atan2(ix, iz)                               # 横放圆柱的朝向: rot=(90,0,psi) 后轴向指向园内
    def at(s, h):
        return (ax + ux * s, -(az + uz * s), h)
    for k, s in enumerate((0.0, L_)):
        px, py, _ = at(s, 0.0)
        o = add_box(f"{name}_plinth{k}", (0.66, 0.66, 0.22), (px, py, 0.11), rot=(0, 0, phi), mat=m_grst)
        gv_stone_vcol(o, lambda v: v.co.z + 0.11)
        o = add_box(f"{name}_shaft{k}", (0.42, 0.42, 2.70), (px, py, 1.57), rot=(0, 0, phi), mat=m_grst)
        gv_stone_vcol(o, lambda v: v.co.z + 1.57)
        o = add_box(f"{name}_cap{k}", (0.56, 0.56, 0.12), (px, py, 2.98), rot=(0, 0, phi), mat=m_grst)
        gv_stone_vcol(o, lambda v: v.co.z + 2.98)
        mx, my = px + ix * 0.225, py - iz * 0.225      # 内外面的鎏金小月盘
        add_cyl(f"{name}_moon{k}", 0.11, 0.03, (mx, my, 2.25), rot=(radians(90), 0, psi), mat=m_grv_gold, verts=16)
        add_cyl(f"{name}_moono{k}", 0.11, 0.03, (px - ix * 0.225, py + iz * 0.225, 2.25), rot=(radians(90), 0, psi), mat=m_grv_gold, verts=16)
        gv_gargoyle(f"{name}_garg{k}", px, py, 3.04, ry, 0.4)
        # 柱面挑臂 + 灯头 x2: 柱内侧、朝来路的外侧各一盏 (2.2 m 以上; 只发光 —— 每个门那一盏真实点光在门洞正中, 见函数末尾)。
        # 第一版只装在内侧: 从来路走近只看见黑壳, 找不到亮着的灯, 「被门口的灯勾着走进来」不成立 (独立审阅意见)
        for sd_ in ("i", "o"):
            ox_, oz_ = (ix, iz) if sd_ == "i" else (-ix, -iz)
            b0 = (px + ox_ * 0.21, py - oz_ * 0.21, 2.74)
            b1 = (px + ox_ * 0.66, py - oz_ * 0.66, 2.74)
            cyl_between(f"{name}_arm{k}{sd_}", b0, b1, 0.022, m_grv_iron, verts=5)
            cyl_between(f"{name}_drop{k}{sd_}", b1, (b1[0], b1[1], 2.66), 0.012, m_grv_iron, verts=4)
            gv_lantern_head(f"{name}_lamp{k}{sd_}", b1[0], b1[1], 2.22, 2.52, 0.14)
        collider(px, py, 0.35)
    # 铁艺拱: 过 (±半跨, 3.04) 与 (0, 3.95) 的圆弧; 副拱低 0.20 m, 两端插进门柱
    half = L_ / 2
    c = (6.3609 - half * half) / 1.82
    R = 3.95 - c
    th = atan2(half, (R * R - half * half) ** 0.5)
    def archpt(t_, R_):
        return at(half + R_ * sin(t_), c + R_ * cos(t_))
    NS = 12
    for k in range(NS):
        a0 = -th + 2 * th * k / NS
        a1 = -th + 2 * th * (k + 1) / NS
        cyl_between(f"{name}_arch{k}", archpt(a0, R), archpt(a1, R), 0.045, m_grv_iron, verts=6)
    R2 = R - 0.20
    c2 = (2.86 - c) / R2
    th2 = atan2((1.0 - c2 * c2) ** 0.5, c2)
    for k in range(NS):
        a0 = -th2 + 2 * th2 * k / NS
        a1 = -th2 + 2 * th2 * (k + 1) / NS
        cyl_between(f"{name}_arch2_{k}", archpt(a0, R2), archpt(a1, R2), 0.022, m_grv_iron, verts=5)
    for k in range(7):
        a = -th * 0.72 + 2 * th * 0.72 * k / 6
        cyl_between(f"{name}_strut{k}", archpt(a, R), archpt(a, R2), 0.014, m_grv_iron, verts=4)
    # 新月星徽: 拱顶下, 与门同平面
    ex, ey, _ = at(half, 0.0)
    ez = 3.42
    moon = add_torus(f"{name}_emblem", 0.30, 0.035, (ex, ey, ez), rot=(radians(90), 0, phi), mat=m_grv_gold, ms=36, ns=7)
    torus_gap(moon, 52, 60)   # 缺口在局部 +x / +y 之间 = 新月
    add_sphere(f"{name}_star", 0.055, (ex, ey, ez), mat=m_grv_gold, seg=8, ring=6)
    for k, (dv, rr) in enumerate((((0, 0, 1), (0, 0, 0)), ((0, 0, -1), (pi, 0, 0)),
                                  ((ux, -uz, 0), (0, radians(90), phi)), ((-ux, uz, 0), (0, radians(-90), phi)))):
        add_cone(f"{name}_spike{k}", 0.02, 0.22, (ex + dv[0] * 0.15, ey + dv[1] * 0.15, ez + dv[2] * 0.15),
                 mat=m_grv_gold, verts=4, rot=rr)
    # 真实点光挂在门洞正中、离地 2.6 m (两盏挑臂灯头之间), 不挂在新月徽上: 70 cd 贴着月徽时, 离灯 0.2-0.9 m 的月徽星点 /
    # 拱顶铁件 / 柱顶石像鬼全被削顶, 默认辉光下整座门糊成一团白光 (西门外机位近白像素 1.47%)。灯是运行时对象, 改高度 / 强度
    # 不必重跑模型 —— 页面里试了 7 组, 定在门洞正中 2.6 m (同机位近白 0.04%, 门外 / 门内 / 北门三个机位新月徽都读得出新月加星;
    # 标定图 shots/graveyard_review/b3/calib/: 3.45m/70cd 1.47%, 3.0/30 0.12%, 3.2/25 0.13%, 2.6/30 0.04%)。柱面挑臂灯头内外各一盏,
    # 点光就落在四盏灯头之间; 强度 30 -> 26 cd 是为了压一下柱内侧面的刺白 (独立审阅意见)
    park_light((ax + pb[0]) / 2, -(az + pb[1]) / 2, GV_GATE_LIGHT_H, "#FFD9A8", GV_GATE_CD, 22, decay=2, tag=name, key="graveyardLight")
    return (ax + ux * half, az + uz * half)

GV_GATE_N = gv_gate("PE_GateN", (33.2, 46.1), (36.8, 46.1), (0.0, -1.0))    # 北门: 北接路的园外段宽 3 m, 门洞同宽
GV_GATE_W = gv_gate("PE_GateW", (19.9, 52.9), (19.9, 56.5), (-1.0, 0.0))   # 西门: 正对主走道轴线

# ---------------- 围栏: 一圈尖桩铁艺, 只在两个门处断开 ----------------
# 折线取自椭圆 (按弧长等分), 两端收到石门柱上; 西门两根门柱取同一个 x (正对主走道), 所以离椭圆略有进出,
# 首尾一跨的横杆斜着接过去。碰撞圆沿同一条折线铺 —— 碰撞与可见围栏同线。
def gv_arc_points(t0, t1, n):
    """椭圆上从参数角 t0 到 t1 (t1 > t0 为 t 增方向, 反之为减方向) 按弧长 n 等分, 返回 n+1 个点 (app)"""
    samples = []
    prev = gva(t0)
    s = 0.0
    samples.append((0.0, prev))
    N = 2400
    for k in range(1, N + 1):
        cur = gva(t0 + (t1 - t0) * k / N)
        s += hypot(cur[0] - prev[0], cur[1] - prev[1])
        samples.append((s, cur))
        prev = cur
    out = []
    j = 0
    for k in range(n + 1):
        sk = s * k / n
        while j < N and samples[j + 1][0] < sk:
            j += 1
        s0, p0 = samples[j]
        s1, p1 = samples[min(j + 1, N)]
        u = 0.0 if s1 <= s0 else (sk - s0) / (s1 - s0)
        out.append((p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u))
    return out

def gv_t(px, pz):
    """椭圆上离 app 点 (px, pz) 最近的参数角 (按归一化坐标取角)"""
    return atan2((pz + GV_EY) / GV_EB, (px - GV_EX) / GV_EA)

gv_fence_posts, gv_fence_circles, gv_fence_pickets = 0, 0, 0
def gv_fence(name, pts):
    """一段围栏。pts = 柱位 (app), 首尾是石门柱 (不立铁柱, 只把横杆接过去)。
    中间每点: 铁柱 (1.5 m) + 箍 + 四棱尖头; 相邻柱间: 两道横杆 + 约 0.2 m 一根的细尖桩; 碰撞: 沿折线每 <=0.4 m 一个 r0.22 圆"""
    global gv_fence_posts, gv_fence_circles, gv_fence_pickets
    n = len(pts) - 1
    for k in range(n + 1):
        px, py = pts[k][0], -pts[k][1]
        if 0 < k < n:
            add_box(f"{name}_post{k}", (0.14, 0.14, 1.5), (px, py, 0.75), mat=m_grv_iron)
            add_torus(f"{name}_collar{k}", 0.105, 0.022, (px, py, 1.40), mat=m_grv_iron, ms=10, ns=5)
            add_cone(f"{name}_tip{k}", 0.085, 0.24, (px, py, 1.62), mat=m_grv_iron, verts=4)
            gv_fence_posts += 1
        if k < n:
            qx, qy = pts[k + 1][0], -pts[k + 1][1]
            seg = hypot(qx - px, qy - py)
            for hz in (0.42, 1.18):
                cyl_between(f"{name}_rail{k}_{hz}", (px, py, hz), (qx, qy, hz), 0.026, m_grv_iron, verts=5)
            m = max(2, round(seg / 0.2))
            for j in range(1, m):
                u = j / m
                bx, by = px + (qx - px) * u, py + (qy - py) * u
                cyl_between(f"{name}_picket{k}_{j}", (bx, by, 0.10), (bx, by, 1.32), 0.015, m_grv_iron, verts=4)
                add_cone(f"{name}_pickettip{k}_{j}", 0.04, 0.14, (bx, by, 1.39), mat=m_grv_iron, verts=4)
                gv_fence_pickets += 1
            c = max(1, int(seg / 0.4 + 0.9999))
            for j in range(c):
                u = (j + 0.5) / c
                collider(px + (qx - px) * u, py + (qy - py) * u, 0.22)
                gv_fence_circles += 1

t_wn, t_nw = gv_t(19.9, 52.9), gv_t(33.2, 46.1)        # 西门北柱 / 北门西柱
tA0, tA1 = min(t_wn, t_nw), max(t_wn, t_nw)            # 西北短弧
tB0, tB1 = gv_t(36.8, 46.1), gv_t(19.9, 56.5)          # 北门东柱 -> 绕东、南到西门南柱
while tB1 <= tB0:
    tB1 += 2 * pi
for nm_, (t0, t1, pa_, pb_) in {"A": (tA0, tA1, (19.9, 52.9), (33.2, 46.1)),
                                "B": (tB0, tB1, (36.8, 46.1), (19.9, 56.5))}.items():
    pts = gv_arc_points(t0, t1, 2400)
    Lf = sum(hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1]) for k in range(2400))
    pts = gv_arc_points(t0, t1, max(2, round(Lf / 2.4)))
    pts[0], pts[-1] = pa_, pb_
    gv_fence(f"PE_GFence{nm_}", pts)
print("GV_FENCE posts", gv_fence_posts, "pickets", gv_fence_pickets, "colliders", gv_fence_circles)

# ---------------- 碑: 按行重排, 宽面朝着走道, 碑身带倾角 ----------------
def gv_stone(name, x, z, yaw, lx, ly):
    """墓碑 (v4 第三批): 碑身 + 盖帽同倾角。x / z = 碑底中心的 app 坐标; yaw = 绕竖轴; lx / ly = 前后 / 左右倾角 (rad)。
    盒墙碰撞取整块碑 (含盖帽、含倾斜)的水平包围盒。碑底下沉 2 cm: 倾斜后抬起来的那个角才不会悬空。"""
    base = Vector((x, -z, -0.02))
    R_ = Euler((lx, ly, yaw), "XYZ").to_matrix()
    sb = add_box(f"{name}", (0.72, 0.2, 1.05), tuple(base + R_ @ Vector((0, 0, 0.525))), rot=(lx, ly, yaw), mat=m_grst)
    gv_stone_vcol(sb, lambda v: v.co.z + 0.525)
    cap = add_cyl(f"{name}Cap", 0.365, 0.21, tuple(base + R_ @ Vector((0, 0, 1.05))), rot=(lx + pi / 2, ly, yaw),
                  mat=m_grst, verts=12)
    gv_stone_vcol(cap, lambda v: 1.05 + v.co.y)   # 圆柱绕 X 转 90° 后本地 y 即碑身高度方向
    pts_ = []
    for sx in (-0.36, 0.36):
        for sy in (-0.1, 0.1):
            for sz in (0.0, 1.05):
                pts_.append(base + R_ @ Vector((sx, sy, sz)))
    for a in range(12):
        for sy in (-0.105, 0.105):
            pts_.append(base + R_ @ Vector((0.365 * cos(a * pi / 6), sy, 1.05 + 0.365 * sin(a * pi / 6))))
    mnx, mxx = min(p.x for p in pts_), max(p.x for p in pts_)
    mny, mxy = min(p.y for p in pts_), max(p.y for p in pts_)
    collider_rect((mnx + mxx) / 2, (mny + mxy) / 2, (mxx - mnx) / 2, (mxy - mny) / 2)

# 行 (app z): 北区两行 (z 51.3 / 48.9) 面朝南, 南区五行 (z 58.2 / 60.5 / 62.8 / 65.1 / 67.4) 面朝北。
# x 槽位以中脊为轴每 2 m 一个 (35 +- 2m), 本批隔槽取用 = 4 m 等距: 25 / 29 / 33 / 37 / 41 / 45 / 49 —— 两行同一套槽位,
# 隔着走道两两相对; 夹北脊 (app x 33.8..36.2) 的 33 / 37 放十字架, 十字架的碰撞盒离北脊可走带还有 0.05 m。
# 第一版按 1.9 m 槽位零散取用 (北行间距 3.8 / 1.9 / 1.3 ...), 独立审阅指出读不成「规整行列」。
# 本批只把现有的 9 块碑 + 2 个十字架放进靠走道的两行, 其余槽位留给第四批; 北行 45 让给枯树 (43.6,51.8, 根部外扩约 1 m)。
gv_stone_slots = [(25.0, 51.3), (29.0, 51.3), (41.0, 51.3), (49.0, 51.3),                    # 北一行
                 (25.0, 58.2), (29.0, 58.2), (33.0, 58.2), (37.0, 58.2), (41.0, 58.2)]        # 南一行
for i, (sx, sz) in enumerate(gv_stone_slots):
    yaw = radians(rgv.uniform(-6, 6))
    lx = radians(rgv.uniform(4, 7)) * (1 if rgv.random() < 0.5 else -1)
    ly = radians(rgv.uniform(2, 5)) * (1 if rgv.random() < 0.5 else -1)
    gv_stone(f"PE_Grave{i}", sx, sz, yaw, lx, ly)
for i, (sx, sz) in enumerate(((33.0, 51.3), (37.0, 51.3))):     # 十字架夹着北脊 (槽位 33 / 37), 与北一行同深
    yaw = radians(rgv.uniform(-5, 5))
    x, y = sx, -sz
    add_box(f"PE_CrossV{i}", (0.16, 0.14, 1.5), (x, y, 0.75), rot=(0, 0, yaw), mat=m_wood)
    add_box(f"PE_CrossH{i}", (0.7, 0.14, 0.16), (x, y, 1.05), rot=(0, 0, yaw), mat=m_wood)
    collider_rect(x, y, 0.35 * abs(cos(yaw)) + 0.07 * abs(sin(yaw)), 0.35 * abs(sin(yaw)) + 0.07 * abs(cos(yaw)))

# 守墓灯 x2: 主走道两侧的灯位带 (离走道边 0.45 m), 以中脊为轴对称 (35 +- 7.6), 各在相邻两块碑的正中 (离碑面约 2 m)
grave_lantern("PE_GraveLantern", 27.4, -(GV_AZ + 1.65))
grave_lantern("PE_GraveLanternS", 42.6, -(GV_AZ - 1.65))
# 枯树挪到北脊与主走道的东北角外 (主干离走道边 1.05 m, 树冠探到走道上空); spooky_tree 内部已加碰撞圆 r0.65
spooky_tree("PE_GraveTree", 43.6, -51.8, scale=1.2, variant="weep")

# 彼岸花丛 x4 (墓园 v2: 弯茎 + 放射红蕊弯瓣, m_red 自发光): 行头、枯树下、北门内侧
# 花的摆法与改造前相同: rlg 从「此刻的全局状态」起步取值, 等价于以前直接用全局 random; 段末再把全局流的消耗补回去
rlg = random.Random()
rlg.setstate(random.getstate())
for ci, (cx, cz) in enumerate(((23.3, 51.3), (23.3, 58.2), (45.0, 52.9), (38.3, 47.6))):   # 行头两丛让到首块碑 (x 25) 外侧
    cx, cy = cx, -cz
    for f in range(7):
        fx = cx + rlg.uniform(-0.7, 0.7)
        fy = cy + rlg.uniform(-0.7, 0.7)
        a0 = rlg.uniform(0, 2 * pi)
        bx, by = fx + 0.08 * cos(a0), fy + 0.08 * sin(a0)
        tube_frustum(f"PE_Higan{ci}_{f}_st",
                     [(fx, fy, 0.01), (fx + 0.04 * cos(a0), fy + 0.04 * sin(a0), 0.2),
                      (bx, by, 0.4)],
                     [0.014, 0.01, 0.006], m_stem, sides=5)
        for st in range(6):
            a = st * 2 * pi / 6 + rlg.uniform(-0.2, 0.2)
            blade(f"PE_Higan{ci}_{f}_sp{st}", (bx, by, 0.42), 0.16, 0.02, a,
                  rlg.uniform(0.9, 1.4), m_red,
                  hex_lin("#8A1E1E")[:3], hex_lin("#FF4A4A")[:3], lean=0.5)
        add_sphere(f"PE_Higan{ci}_{f}_hd", 0.03, (bx, by, 0.44), mat=m_red, seg=6, ring=4)
    collider(cx, cy, 0.6)   # 花丛散布半径约 0.7; 旧圆 1.0 在花外 0.4 m 就挡人
# 全局随机流占位: 上面的彼岸花丛改造前直接消耗全局 random —— 4 丛 x 7 株 x 15 次 uniform
# (位置 2 + 朝向 1 + 6 根花丝各 2)。现在花改走 rlg, 这里补回同样的消耗; 以后重写彼岸花也不要动这一行,
# 否则段后园区 (市集 / 长椅 / 枯树 / 远山 / 城市灯火) 会全部重新随机。
GV_LEGACY_DRAWS = 4 * 7 * 15
for _ in range(GV_LEGACY_DRAWS):
    random.random()

# 灯串: 主走道上空之字形横跨 —— 西门拱顶 -> 北侧挂杆 -> 南侧挂杆 -> 北侧挂杆 -> 南侧挂杆 -> 焦点庭北侧挂杆。
# 走在走道上时逐跨从头顶斜着过街 (之字形): 方向契约的首屏是站在走道正中朝东看, 与走道平行的灯串透视成一条短线,
# 横跨走道的才读得出「灯串横贯上 1/3」。
# 挂点离地 3.95 m、垂度 0.40、灯珠再低 0.09: 跨中最低的珠底约 3.4 m (跳跃碰不到)。北侧挂杆让开北脊 (app x 33.8..36.2)、
# 守墓灯 (40.05,53.05) 与枯树 (43.6,51.8)。前庭灯串: 东挂杆顶 -> 北门东柱的拱脚。
# 端点是 Blender 坐标 (x, y, 高度) —— 不是 glTF 的 (x, 高度, -y)。第一版按后者写, 主走道的灯串整串埋到地下 54 m、
# 前庭那串一头挂到 44 m 高空: 灯珠数量照常增加 (数量比对看不出来), 游戏里只是「看不到灯串」, 靠逐网格顶点比对才查出来。
# 下面所以加一条端点高度断言
GV_STR_H = 3.95
gv_str_poles = {"C": (26.5, GV_AZ - 2.2), "A": (33.2, GV_AZ + 2.2), "D": (37.0, GV_AZ - 2.2),
                "B": (44.0, GV_AZ + 2.2), "E": (50.4, GV_AZ - 2.9)}
for nm_, (px_, pz_) in gv_str_poles.items():
    light_pole(f"PE_StrPoleGrave{nm_}", px_, -pz_, h=4.1, attach=GV_STR_H)
gv_str_anchors = [(GV_GATE_W[0], -GV_GATE_W[1], 3.90)] + [(px_, -pz_, GV_STR_H) for px_, pz_ in gv_str_poles.values()]
for k, (sp0_, sp1_) in enumerate(zip(gv_str_anchors, gv_str_anchors[1:])):
    string_lights(f"PE_StrG{k}", sp0_, sp1_, sag=0.40, mats=[m_warm, m_violet])
# 垂度压到 0.12 (0.30 时跨中最低的珠底只有 2.80 m, 低于跳跃眼高 2.84); 东端落在东柱柱帽外 0.3 m 的拱脚, 不把端头灯珠埋进柱帽
gv_str_fore = [(40.0, -44.0, 3.70), (36.8 + 0.3 * 3.2 / 3.83, -46.1 + 0.3 * 2.1 / 3.83, 3.12)]
string_lights("PE_StrG5", gv_str_fore[0], gv_str_fore[1], sag=0.12, mats=[m_warm, m_violet])
for sp_ in gv_str_anchors + gv_str_fore:
    assert 2.5 < sp_[2] < 8.0 and abs(sp_[1]) < 150.0, f"灯串端点应是 Blender 坐标 (x, y, 高度): {sp_}"

# 打卡南瓜 pumpkin_grave: 从旧址西北角 (30.5,-36.5) 挪到北门内、北脊西侧 (32.7,-47.9), 标签不变。
# pump_plan 里的坐标不能动 (它还喂着草丛 / 地斑的避让表, 改了全园散布就变) —— 建完之后整体平移它的几个部件,
# 再改碰撞圆与 POI 记录
GV_POI_FROM, GV_POI_TO = (30.5, -36.5), (32.7, -47.9)
_poi_i = pump_plan.index(GV_POI_FROM)
_pdx, _pdy = GV_POI_TO[0] - GV_POI_FROM[0], GV_POI_TO[1] - GV_POI_FROM[1]
gv_poi_parts = [ob for ob in col.objects if ob.name.startswith(f"PE_Pump{_poi_i}_")]
assert len(gv_poi_parts) >= 4, f"打卡南瓜部件不足: {len(gv_poi_parts)}"
for ob in gv_poi_parts:
    ob.location.x += _pdx
    ob.location.y += _pdy
gv_poi_hits = [c for c in COLLIDERS
               if abs(c["x"] - GV_POI_FROM[0]) < 1e-6 and abs(c["y"] - GV_POI_FROM[1]) < 1e-6]
assert len(gv_poi_hits) == 1, f"打卡南瓜的碰撞圆应恰有 1 条: {len(gv_poi_hits)}"
gv_poi_hits[0].update(x=round(GV_POI_TO[0], 2), y=round(GV_POI_TO[1], 2))
gv_poi_pois = [k for k, p in enumerate(POIS) if p[2] == "pumpkin_grave"]
assert len(gv_poi_pois) == 1, f"POI pumpkin_grave 应恰有 1 条: {len(gv_poi_pois)}"
POIS[gv_poi_pois[0]] = (GV_POI_TO[0], GV_POI_TO[1], "pumpkin_grave")

# 清掉新址 / 通路 / 新落位件上原有的散布件 (草丛 PE_Tuft* / 地斑 PE_GP*): 只删对象, 不动任何随机数
gv_cleared = {"PE_Tuft": 0, "PE_GP": 0}
for ob in list(col.objects):
    pref = "PE_Tuft" if ob.name.startswith("PE_Tuft") else ("PE_GP" if ob.name.startswith("PE_GP") else None)
    if pref is None or ob.type != "MESH" or not len(ob.data.vertices):
        continue
    c = ob.matrix_basis @ (sum((v.co for v in ob.data.vertices), Vector()) / len(ob.data.vertices))
    m = 3.9 if pref == "PE_GP" else 0.3   # 地斑半径最大 3.6 m: 外扩判定, 免得地斑顶面 (0.011) 戳出新草皮盘顶面 (0.01)
    hit = gv_inside(c.x, c.y, GV_EA + m, GV_EB + m) or gv_on_new_paths(c.x, c.y, m)
    # 蘑菇圈挪到西支路旁 (12,-50.5): 圈内与圈缘不留野草; 附近的地斑清掉 (蘑菇自带的苔盘与地斑同高, 会闪)
    dm = hypot(c.x - 12.0, c.y + 50.5)
    hit = hit or (dm < (5.4 if pref == "PE_GP" else 1.5))
    if hit:
        gv_cleared[pref] += 1
        bpy.data.objects.remove(ob, do_unlink=True)
print("GV_CLEARED", gv_cleared, "POI_PARTS", len(gv_poi_parts))

# ---------------- 市集亭 x3 (西) + 新摊车 x2 ----------------
stall_defs = [(-25.0, -27.5, HEX["orange"], "treats"),
              (-31.5, -30.5, HEX["green"], "candy"),
              (-38.0, -33.5, HEX["red"], "brew")]
for i, (sx, sy, c, _label) in enumerate(stall_defs):
    add_box(f"PE_StallBody{i}", (2.7, 2.0, 2.3), (sx, sy, 1.15), mat=m_wood)
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
    collider_rect(sx, sy, 1.35, 1.0)

def barrel(name, x, y, z=0.0):
    """木桶 v2: 桶身 + 上下铁箍 + 板缝棱"""
    add_cyl(f"{name}_body", 0.42, 0.95, (x, y, z + 0.48), mat=m_wood, verts=12)
    for hz in (z + 0.2, z + 0.76):
        add_torus(f"{name}_hoop{hz:.2f}", 0.43, 0.03, (x, y, hz), mat=m_iron, ms=24, ns=5)
    for k in range(8):
        a = k * pi / 4
        cyl_between(f"{name}_stave{k}", (x + 0.42 * cos(a) * 0.99, y + 0.42 * sin(a) * 0.99, z + 0.02),
                    (x + 0.42 * cos(a) * 0.99, y + 0.42 * sin(a) * 0.99, z + 0.94),
                    0.02, m_metal_d, verts=3)
    collider(x, y, 0.6, h=z + 0.955)

for i, (sx, sy, _c, _l) in enumerate(stall_defs):
    barrel(f"PE_Barrel{i}", sx + 2.0, sy + 0.6)

# 爆米花车 (车轮 + 玻璃罩 + 条纹棚)
px_, py_ = -19.5, -28.8
add_box("PE_CartPop_body", (1.9, 1.1, 0.9), (px_, py_, 0.75), mat=m_wood)
add_box("PE_CartPop_counter", (1.9, 0.24, 0.08), (px_, py_ - 0.55, 1.24), mat=m_wood)
for wx_i, wx in enumerate((-0.7, 0.7)):
    add_cyl(f"PE_CartPop_wheel{wx_i}", 0.32, 0.1, (px_ + wx, py_ + 0.62, 0.32),
            rot=(radians(90), 0, 0), mat=m_iron, verts=10)
    add_cyl(f"PE_CartPop_hub{wx_i}", 0.08, 0.14, (px_ + wx, py_ + 0.62, 0.32),
            rot=(radians(90), 0, 0), mat=m_metal_d, verts=6)
for st in range(5):   # 迷你条纹棚
    add_box(f"PE_CartPop_awn{st}", (0.34, 1.3, 0.05), (px_ - 0.68 + st * 0.34, py_ + 0.1, 2.0),
            rot=(radians(-10), 0, 0), mat=(m_warm if st % 2 == 0 else m_red))
add_cyl("PE_CartPop_postL", 0.04, 1.1, (px_ - 0.85, py_ + 0.6, 1.5), mat=m_iron, verts=5)
add_cyl("PE_CartPop_postR", 0.04, 1.1, (px_ + 0.85, py_ + 0.6, 1.5), mat=m_iron, verts=5)
add_sphere("PE_CartPop_glass", 0.42, (px_, py_ - 0.1, 1.62), mat=m_mushstem,
           seg=10, ring=6, scale=(1.0, 0.7, 0.75))
for pk in range(6):   # 爆米花堆
    add_sphere(f"PE_CartPop_puff{pk}", 0.09,
               (px_ + random.uniform(-0.35, 0.35), py_ - 0.1 + random.uniform(-0.15, 0.15), 1.42),
               mat=m_warm, seg=6, ring=4)
collider_rect(px_, py_, 1.05, 0.85)
collider(px_ + 0.7, py_ + 0.62, 0.45, h=0.64)   # 车轮旁可跨? 轮子不可站, 仅阻挡

# 苹果糖摊 (斜面顶棚 + 糖苹果架 + 底桶)
ax_, ay_ = -35.2, -27.8
add_box("PE_CartApple_body", (1.6, 1.0, 0.85), (ax_, ay_, 0.72), mat=m_wood)
add_box("PE_CartApple_roof", (1.9, 1.2, 0.07), (ax_, ay_ + 0.08, 1.9),
        rot=(radians(12), 0, 0), mat=m_red)
add_cyl("PE_CartApple_postL", 0.04, 1.3, (ax_ - 0.7, ay_ + 0.45, 1.35), mat=m_iron, verts=5)
add_cyl("PE_CartApple_postR", 0.04, 1.3, (ax_ + 0.7, ay_ + 0.45, 1.35), mat=m_iron, verts=5)
for ap in range(6):   # 糖苹果: 竹签 + 红糖壳
    apx = ax_ - 0.5 + (ap % 3) * 0.5
    apy = ay_ - 0.28 + (ap // 3) * 0.36
    add_cyl(f"PE_CartApple_stick{ap}", 0.015, 0.22, (apx, apy, 1.36), mat=m_wood, verts=4)
    add_sphere(f"PE_CartApple_ball{ap}", 0.11, (apx, apy, 1.5), mat=m_red, seg=8, ring=5)
barrel("PE_CartApple_barrel", ax_ + 1.15, ay_ + 0.5)
collider_rect(ax_, ay_, 0.9, 0.75)

# ---------------- 干草堆 x3 (v2 圆垛+外露草叶) ----------------
for i, (hx, hy) in enumerate(((26.0, -36.0), (12.5, -11.2), (-11.8, -11.5))):
    haystack_v2(f"PE_Hay{i}", hx, hy)
    collider(hx, hy, 1.0, h=0.78)

# ---------------- 长椅 x12 (四种款式) ----------------
def bench(name, bx, by, rotz_deg, variant=None):
    variant = variant or random.choice(("iron", "slat", "pumpkin", "plain"))
    rz = radians(rotz_deg)
    sinr, cosr = sin(rz), cos(rz)
    def local(ox, oy):
        return (bx + ox * cosr - oy * sinr, by + ox * sinr + oy * cosr)
    if variant == "iron":      # 铁艺卷草纹: 铁架 + 木条座面
        for lx in (-0.75, 0.75):
            lx_, ly_ = local(lx, 0)
            add_cyl(f"{name}_leg{lx}", 0.05, 0.6, (lx_, ly_, 0.3), rot=(0, 0, rz), mat=m_iron, verts=6)
            add_torus(f"{name}_scroll{lx}", 0.13, 0.028, (lx_, ly_, 0.62),
                      rot=(radians(90), 0, rz), mat=m_iron, ms=16, ns=5)   # 扶手涡卷
        for sl in range(3):
            lx_, ly_ = local(0, -0.15 + sl * 0.15)
            add_box(f"{name}_seat{sl}", (1.7, 0.13, 0.05), (lx_, ly_, 0.63), rot=(0, 0, rz), mat=m_wood)
        for bl in range(3):
            lx_, ly_ = local(0, 0.28 - bl * 0.0)
            add_box(f"{name}_back{bl}", (1.7, 0.05, 0.11), (lx_, ly_, 0.78 + bl * 0.17),
                    rot=(radians(-8), 0, rz), mat=m_iron)
    elif variant == "slat":    # 木条椅: 分条座面 + 分条靠背
        for sl in range(5):
            lx_, ly_ = local(0, -0.18 + sl * 0.09)
            add_box(f"{name}_seat{sl}", (1.7, 0.07, 0.045), (lx_, ly_, 0.62), rot=(0, 0, rz), mat=m_wood)
        for bl in range(3):
            lx_, ly_ = local(0, 0.3)
            add_box(f"{name}_back{bl}", (1.7, 0.06, 0.12), (lx_, ly_, 0.82 + bl * 0.18),
                    rot=(radians(-10), 0, rz), mat=m_wood)
        for lx in (-0.7, 0.7):
            lx_, ly_ = local(lx, 0.05)
            add_box(f"{name}_frame{lx}", (0.07, 0.55, 0.6), (lx_, ly_, 0.31), rot=(0, 0, rz), mat=m_wood)
    elif variant == "pumpkin":  # 南瓜靠背椅: 圆靠背 + 藤蔓腿
        for lx in (-0.55, 0.55):
            for ly in (-0.15, 0.15):
                lx_, ly_ = local(lx, ly)
                add_torus(f"{name}_vine{lx}{ly}", 0.09, 0.03, (lx_, ly_, 0.3),
                          rot=(radians(90), 0, rz + (1 if lx > 0 else -1) * 0.3),
                          mat=m_stem, ms=10, ns=5)
        for sl in range(3):
            lx_, ly_ = local(0, -0.15 + sl * 0.15)
            add_box(f"{name}_seat{sl}", (1.5, 0.13, 0.05), (lx_, ly_, 0.62), rot=(0, 0, rz), mat=m_wood)
        lx_, ly_ = local(0, 0.3)
        back_ob = add_sphere(f"{name}_back", 0.42, (lx_, ly_, 1.0), mat=m_pump,
                             seg=12, ring=8, scale=(2.6, 0.35, 1.5))
        back_ob.rotation_euler.z = rz   # 靠背宽轴随座椅朝向
        add_cyl(f"{name}_stem", 0.04, 0.14, (lx_, ly_, 1.62), rot=(0, 0, rz), mat=m_stem, verts=5)
    else:                       # 简约款 (原版)
        sx0, sy0 = local(0, 0)
        add_box(f"{name}_seat", (1.7, 0.45, 0.09), (sx0, sy0, 0.62), rot=(0, 0, rz), mat=m_wood)
        bx2, by2 = local(0, -0.22)   # 背板沿 -local-y 后移 (与 v2 原版一致)
        add_box(f"{name}_back", (1.7, 0.08, 0.5), (bx2, by2, 0.92), rot=(0, 0, rz), mat=m_wood)
        for lx in (-0.7, 0.7):
            lx_, ly_ = local(lx, 0)
            add_box(f"{name}_leg{lx}", (0.08, 0.4, 0.58), (lx_, ly_, 0.29), rot=(0, 0, rz), mat=m_iron)
    collider(bx, by, 0.9, h=0.665)

bench_spots = [(5.6, -31.0, 90), (-5.6, -45.0, 90), (5.6, -59.0, 90),
               (9.5, -9.5, 45), (-9.5, 9.5, 225), (13.0, 0.0, -90),
               (4.6, -72.0, 90), (-4.6, -102.0, 90), (4.6, -128.0, 90),
               (60.0, 60.0, 135), (-67.2, 67.2, 225), (41.3, -44.6, -77)]   # 末张在北门外东侧、面朝北门 (第三批; 原位 (39.5,-45.5,120)。原位离墓园新围栏线只有 0.6 m, 转向正对北门后
                        # 椅身沿南北展开, 南端连靠背南瓜跨在围栏尖桩上 —— 外移到离围栏线约 1 m 处, 与挂杆 / 发射器 L3 / 蘑菇圈都不重叠)
for i, (bx, by, rotz) in enumerate(bench_spots):
    bench(f"PE_Bench{i}", bx, by, rotz)
# 末张长椅 2026-11-26 外移到 (41.3,-44.6); 树的避让表 (下方 tree_extras) 仍按它的原位算 ——
# tree_extras 决定树的候选哪些被否决, 改了它全园的树就可能重新随机 (同稻草人 (40,-47) / 旧蘑菇圈 (26,-36) 的留法)
GV_BENCH_TREE_XY = (39.5, -45.5)

# ---------------- 烟花发射器 x3 型 × 6 站 ----------------
# 造型定稿: model/firework_launcher/design_preview.py (用户已确认)
# 家族基因: 木结构 + 铁艺管件 + 点火箱红钮 + 暖光小灯串
# 型号识别: 管口发光环 + 饰色 + 剪影 (A 牡丹架-橙 / B 垂柳塔-紫 / C 椰芯炮-绿)
def _lw_fwd(elev, az=0.0):
    """局部旋转 (elev, 0, az) 下 +Z 轴方向 (炮口朝 -Y 仰起)"""
    return (sin(az) * sin(elev), -cos(az) * sin(elev), cos(elev))

def _lw_firebox(obs, tag, x, y, z, yaw=0.0):
    """家族基因: 点火箱 + 红蘑菇钮 + 推杆"""
    obs.append(add_box(f"{tag}_FBbody", (0.42, 0.3, 0.3), (x, y, z + 0.15), rot=(0, 0, yaw), mat=m_wood_d))
    obs.append(add_box(f"{tag}_FBlip", (0.46, 0.34, 0.04), (x, y, z + 0.31), rot=(0, 0, yaw), mat=m_wood))
    obs.append(add_cyl(f"{tag}_FBbtn", 0.06, 0.05, (x, y - 0.1, z + 0.36), mat=m_red, verts=10))
    obs.append(add_sphere(f"{tag}_FBcap", 0.055, (x, y - 0.1, z + 0.39), mat=m_red, seg=8, ring=5))
    obs.append(cyl_between(f"{tag}_FBlever", (x + 0.16, y + 0.05, z + 0.3), (x + 0.26, y + 0.12, z + 0.5), 0.014, m_iron))

def _lw_A(tag):
    """牡丹发射架: A 字木架 + 5 管扇形 (仰角 52°), 管口橙环"""
    o = []
    for sx in (-1.05, 1.05):
        o.append(add_box(f"{tag}_runner", (2.6, 0.14, 0.1), (sx, 0, 0.05), mat=m_wood_d))
    for k in range(5):
        o.append(add_box(f"{tag}_plank{k}", (2.4, 0.2, 0.05), (0, -0.55 + k * 0.28, 0.13), mat=m_wood))
    for sx in (-1.05, 1.05):
        o.append(cyl_between(f"{tag}_legF_{sx}", (sx, -0.62, 0.15), (sx * 0.42, -0.1, 1.42), 0.06, m_wood))
        o.append(cyl_between(f"{tag}_legB_{sx}", (sx, 0.62, 0.15), (sx * 0.42, -0.1, 1.42), 0.06, m_wood))
        o.append(cyl_between(f"{tag}_brace_{sx}", (sx * 0.66, -0.66, 0.62), (sx * 0.66, 0.66, 0.62), 0.03, m_iron))
    o.append(cyl_between(f"{tag}_axle", (-1.0, -0.1, 1.42), (1.0, -0.1, 1.42), 0.04, m_iron))
    elev = radians(52)
    for k in range(5):
        az = (k - 2) * radians(8)
        fx, fy, fz = _lw_fwd(elev, az)
        tx = (k - 2) * 0.25
        o.append(add_cyl(f"{tag}_tube{k}", 0.15, 0.62, (tx, -0.12, 1.42), rot=(elev, 0, az), mat=m_steel, verts=12))
        o.append(add_torus(f"{tag}_ring{k}", 0.115, 0.024, (tx + fx * 0.34, -0.12 + fy * 0.34, 1.42 + fz * 0.34),
                           rot=(elev, 0, az), mat=m_orange_s))
        o.append(add_torus(f"{tag}_bandA{k}", 0.165, 0.02, (tx + fx * 0.2, -0.12 + fy * 0.2, 1.42 + fz * 0.2),
                           rot=(elev, 0, az), mat=m_metal_d))
        o.append(add_torus(f"{tag}_bandB{k}", 0.165, 0.02, (tx + fx * 0.05, -0.12 + fy * 0.05, 1.42 + fz * 0.05),
                           rot=(elev, 0, az), mat=m_metal_d))
        o.append(add_sphere(f"{tag}_fuse{k}", 0.03, (tx - fx * 0.33, -0.12 - fy * 0.33, 1.42 - fz * 0.33),
                            mat=m_warm, seg=6, ring=5))
    for k in range(4):   # 横撑灯串 (暖白/橙交替)
        t = (k + 0.5) / 4
        bx = -0.66 + 1.32 * t
        o.append(cyl_between(f"{tag}_bw{k}", (-0.66, -0.66, 0.68), (bx, -0.66, 0.615), 0.006, m_iron))
        o.append(add_sphere(f"{tag}_bulb{k}", 0.04, (bx, -0.66, 0.585),
                            mat=m_orange if k % 2 else m_warm, seg=6, ring=5))
    _lw_firebox(o, tag, 0.95, 0.42, 0.16, yaw=radians(-20))
    o.append(add_box(f"{tag}_crate", (0.52, 0.5, 0.42), (-0.92, 0.42, 0.37), rot=(0, 0, radians(8)), mat=m_wood_d))
    o.append(add_box(f"{tag}_crate2", (0.36, 0.34, 0.26), (-0.88, 0.46, 0.72), rot=(0, 0, radians(24)), mat=m_wood))
    # 内联南瓜灯 (脸朝 -Y; 不用 jack_o_lantern 以便纳入锚点父子)
    o.append(add_sphere(f"{tag}_pump", 0.2, (0.35, 0.62, 0.34), mat=m_pump, seg=10, ring=6, scale=(1, 0.85, 0.78)))
    o.append(add_cyl(f"{tag}_pumpstem", 0.025, 0.09, (0.35, 0.62, 0.56), mat=m_stem, verts=6))
    o.append(add_box(f"{tag}_pumpEyeL", (0.055, 0.02, 0.06), (0.27, 0.46, 0.4), rot=(0, 0, radians(15)), mat=m_pumpface))
    o.append(add_box(f"{tag}_pumpEyeR", (0.055, 0.02, 0.06), (0.43, 0.46, 0.4), rot=(0, 0, radians(-15)), mat=m_pumpface))
    o.append(add_box(f"{tag}_pumpMouth", (0.14, 0.02, 0.05), (0.35, 0.46, 0.29), mat=m_pumpface))
    return o

def _lw_B(tag):
    """垂柳塔: 四腿收分木塔 (H2.3) + 单口粗臼炮 (仰角 76°) + 垂链紫灯笼 x4 + 弯月徽"""
    o = []
    g0, t0, H = 0.85, 0.5, 2.3
    for sx in (-1, 1):
        for sy in (-1, 1):
            o.append(cyl_between(f"{tag}_leg_{sx}{sy}", (sx * g0, sy * g0, 0.04), (sx * t0, sy * t0, H), 0.06, m_wood))
    for zz in (0.75, 1.5):
        w = g0 + (t0 - g0) * zz / H
        for sy in (-1, 1):
            o.append(cyl_between(f"{tag}_x1_{zz}_{sy}", (-w, sy * w, zz), (w, sy * w, zz + 0.55), 0.028, m_iron))
            o.append(cyl_between(f"{tag}_x2_{zz}_{sy}", (w, sy * w, zz), (-w, sy * w, zz + 0.55), 0.028, m_iron))
    o.append(add_box(f"{tag}_deck", (1.3, 1.3, 0.09), (0, 0, H + 0.045), mat=m_wood_d))
    for sx in (-1, 1):
        for sy in (-1, 1):
            o.append(add_cyl(f"{tag}_post_{sx}{sy}", 0.025, 0.3, (sx * 0.6, sy * 0.6, H + 0.24), mat=m_wood, verts=8))
    for sy in (-1, 1):
        o.append(cyl_between(f"{tag}_railX_{sy}", (-0.6, sy * 0.6, H + 0.36), (0.6, sy * 0.6, H + 0.36), 0.02, m_wood))
    for sx in (-1, 1):
        o.append(cyl_between(f"{tag}_railY_{sx}", (sx * 0.6, -0.6, H + 0.36), (sx * 0.6, 0.6, H + 0.36), 0.02, m_wood))
    elev = radians(76)
    fx, fy, fz = _lw_fwd(elev)
    bx, by, bz = 0.0, 0.1, H + 0.5
    o.append(add_cyl(f"{tag}_mortar", 0.27, 0.88, (bx, by, bz), rot=(elev, 0, 0), mat=m_steel, verts=14))
    o.append(add_torus(f"{tag}_band1", 0.285, 0.026, (bx - fx * 0.25, by - fy * 0.25, bz - fz * 0.25),
                       rot=(elev, 0, 0), mat=m_metal_d))
    o.append(add_torus(f"{tag}_band2", 0.29, 0.026, (bx + fx * 0.05, by + fy * 0.05, bz + fz * 0.05),
                       rot=(elev, 0, 0), mat=m_metal_d))
    o.append(add_cyl(f"{tag}_lip", 0.32, 0.12, (bx + fx * 0.42, by + fy * 0.42, bz + fz * 0.42),
                     rot=(elev, 0, 0), mat=m_steel, verts=14))
    o.append(add_torus(f"{tag}_rim", 0.32, 0.024, (bx + fx * 0.46, by + fy * 0.46, bz + fz * 0.46),
                       rot=(elev, 0, 0), mat=m_metal_d))
    o.append(add_torus(f"{tag}_muzzlering", 0.24, 0.03, (bx + fx * 0.5, by + fy * 0.5, bz + fz * 0.5),
                       rot=(elev, 0, 0), mat=m_violet_s))
    o.append(add_box(f"{tag}_mount", (0.72, 0.72, 0.22), (0, 0.1, H + 0.24), mat=m_iron))
    for (cx, cy, L) in ((-0.6, -0.6, 0.72), (0.6, -0.6, 0.5), (-0.6, 0.6, 0.4), (0.6, 0.6, 0.4)):
        lz = H + 0.34 - L
        o.append(cyl_between(f"{tag}_chain_{cx}{cy}", (cx, cy, H + 0.34), (cx, cy, lz), 0.011, m_iron))
        o.append(add_sphere(f"{tag}_lant_{cx}{cy}", 0.095, (cx, cy, lz - 0.11),
                            mat=m_violet, seg=10, ring=6, scale=(1, 1, 1.2)))
        o.append(add_cone(f"{tag}_cap_{cx}{cy}", 0.075, 0.08, (cx, cy, lz - 0.005), mat=m_metal_d, verts=12))
    moon = add_torus(f"{tag}_moon", 0.22, 0.026, (0, -0.72, 1.35), rot=(radians(90), 0, 0), mat=m_warm)
    torus_gap(moon, 48, 60)   # 缺口右上 = 新月
    o.append(moon)
    o.append(add_cyl(f"{tag}_barrel", 0.26, 0.5, (-1.0, 0.35, 0.25), mat=m_wood_d, verts=12))
    o.append(add_torus(f"{tag}_bbarrel", 0.265, 0.02, (-1.0, 0.35, 0.25), mat=m_iron))
    o.append(add_cyl(f"{tag}_barrel2", 0.22, 0.42, (-0.85, -0.6, 0.21), mat=m_wood, verts=12))
    o.append(add_torus(f"{tag}_bbarrel2", 0.225, 0.02, (-0.85, -0.6, 0.21), mat=m_iron))
    _lw_firebox(o, tag, 0.9, -0.55, 0.02, yaw=radians(15))
    return o

def _lw_C(tag):
    """椰芯连环炮: 双辐条轮手推车 + 6 管转轮缸 (仰角 45°) + 齿盘摇柄 + 绿尖弹药"""
    o = []
    o.append(add_box(f"{tag}_deck", (2.2, 1.1, 0.1), (0, 0, 0.6), mat=m_wood))
    o.append(add_box(f"{tag}_railF", (2.2, 0.06, 0.12), (0, 0.52, 0.71), mat=m_wood_d))
    o.append(add_box(f"{tag}_railB", (2.2, 0.06, 0.12), (0, -0.52, 0.71), mat=m_wood_d))
    for sy in (-1, 1):
        o.append(cyl_between(f"{tag}_shaft_{sy}", (1.05, sy * 0.28, 0.58), (1.95, sy * 0.34, 0.12), 0.035, m_wood))
        o.append(cyl_between(f"{tag}_grip_{sy}", (1.95, sy * 0.34, 0.12), (2.1, sy * 0.34, 0.3), 0.03, m_iron))
    o.append(add_cyl(f"{tag}_leg", 0.04, 0.55, (-0.85, 0, 0.28), mat=m_wood, verts=8))
    for sy in (-1, 1):
        cy = sy * 0.62
        o.append(add_torus(f"{tag}_felly_{sy}", 0.4, 0.055, (-0.25, cy, 0.44), rot=(radians(90), 0, 0), mat=m_wood_d))
        o.append(add_cyl(f"{tag}_hub_{sy}", 0.08, 0.12, (-0.25, cy, 0.44), rot=(radians(90), 0, 0), mat=m_iron, verts=10))
        o.append(add_sphere(f"{tag}_hubcap_{sy}", 0.1, (-0.25, cy + sy * 0.06, 0.44),
                            mat=m_iron, seg=8, ring=6, scale=(1, 0.5, 1)))
        for k in range(8):   # 辐条 (轮面 = XZ)
            a = k * pi / 4
            o.append(cyl_between(f"{tag}_spoke_{sy}_{k}", (-0.25, cy, 0.44),
                                 (-0.25 + 0.36 * cos(a), cy, 0.44 + 0.36 * sin(a)), 0.018, m_wood))
    o.append(cyl_between(f"{tag}_axle", (-0.25, -0.62, 0.44), (-0.25, 0.62, 0.44), 0.035, m_iron))
    elev = radians(45)
    fx, fy, fz = _lw_fwd(elev)
    vx, vy, vz = 0.0, cos(elev), sin(elev)   # 局部 Y 轴
    pvx, pvy, pvz = -0.2, 0.0, 0.92
    o.append(add_cyl(f"{tag}_pivot", 0.09, 0.55, (pvx, pvy, pvz - 0.27), mat=m_iron, verts=10))
    o.append(add_cyl(f"{tag}_hubcyl", 0.12, 0.72, (pvx + fx * 0.12, pvy + fy * 0.12, pvz + fz * 0.12),
                     rot=(elev, 0, 0), mat=m_metal_d, verts=12))
    o.append(add_torus(f"{tag}_hband", 0.125, 0.022, (pvx + fx * 0.12, pvy + fy * 0.12, pvz + fz * 0.12),
                       rot=(elev, 0, 0), mat=m_green_s))
    for k in range(6):
        a = k * pi / 3 + radians(30)
        offx = (cos(a) + vx * sin(a)) * 0.26
        offy = (0.0 + vy * sin(a)) * 0.26
        offz = (0.0 + vz * sin(a)) * 0.26
        cx, cyy, cz = pvx + fx * 0.2 + offx, pvy + fy * 0.2 + offy, pvz + fz * 0.2 + offz
        o.append(add_cyl(f"{tag}_tube{k}", 0.075, 0.62, (cx, cyy, cz), rot=(elev, 0, 0), mat=m_steel, verts=10))
        o.append(add_torus(f"{tag}_ring{k}", 0.062, 0.022, (cx + fx * 0.31, cyy + fy * 0.31, cz + fz * 0.31),
                           rot=(elev, 0, 0), mat=m_green_s))
    o.append(add_cyl(f"{tag}_plF", 0.3, 0.05, (pvx + fx * 0.36, pvy + fy * 0.36, pvz + fz * 0.36),
                     rot=(elev, 0, 0), mat=m_steel, verts=14))
    o.append(add_cyl(f"{tag}_plB", 0.3, 0.05, (pvx - fx * 0.16, pvy - fy * 0.16, pvz - fz * 0.16),
                     rot=(elev, 0, 0), mat=m_steel, verts=14))
    gx, gy, gz = pvx - fx * 0.26, pvy - fy * 0.26, pvz - fz * 0.26
    o.append(add_cyl(f"{tag}_gear", 0.2, 0.045, (gx, gy, gz), rot=(elev, 0, 0), mat=m_metal_d, verts=16))
    for k in range(12):
        a = k * pi / 6
        ux_, vx_ = cos(a), sin(a)
        o.append(cyl_between(f"{tag}_pin{k}",
                             (gx + ux_ * 0.2, gy + vx_ * vy * 0.2, gz + vx_ * vz * 0.2),
                             (gx + ux_ * 0.27, gy + vx_ * vy * 0.27, gz + vx_ * vz * 0.27), 0.02, m_metal_d))
    kx = gx + cos(0.9) * 0.24 - fx * 0.1
    ky = gy + sin(0.9) * vy * 0.24 - fy * 0.1
    kz = gz + sin(0.9) * vz * 0.24 - fz * 0.1
    o.append(cyl_between(f"{tag}_crank", (gx - fx * 0.02, gy - fy * 0.02, gz - fz * 0.02), (kx, ky, kz), 0.014, m_iron))
    o.append(add_sphere(f"{tag}_knob", 0.05, (kx - fx * 0.03, ky - fy * 0.03, kz - fz * 0.03), mat=m_warm, seg=8, ring=6))
    bx = 0.72
    o.append(add_box(f"{tag}_crateF", (0.5, 0.06, 0.18), (bx, 0, 0.74), mat=m_wood_d))
    for sy in (-1, 1):
        o.append(add_box(f"{tag}_crateS_{sy}", (0.06, 0.44, 0.18), (bx, sy * 0.22, 0.74), mat=m_wood_d))
    for k, sy in enumerate((-0.12, 0.02, 0.16)):
        o.append(add_cyl(f"{tag}_shell{k}", 0.066, 0.2, (bx - 0.05 + k * 0.05, sy, 0.78),
                         rot=(radians(-12), 0, 0), mat=m_steel, verts=10))
        o.append(add_cone(f"{tag}_tip{k}", 0.066, 0.12, (bx - 0.05 + k * 0.05, sy - 0.012, 0.94), mat=m_green, verts=10))
    o.append(add_cyl(f"{tag}_pole", 0.02, 0.4, (-1.0, -0.4, 0.85), mat=m_iron, verts=8))
    o.append(add_sphere(f"{tag}_lamp", 0.07, (-1.0, -0.4, 1.08), mat=m_green, seg=8, ring=6))
    _lw_firebox(o, tag, -0.95, 0.32, 0.66, yaw=radians(-90))
    return o

BUILDERS = {"A": _lw_A, "B": _lw_B, "C": _lw_C}
LW_COLLIDE = {"A": 1.25, "B": 0.95, "C": 1.2}   # 无限高圆墙 (发射器不可穿行)
for lid, kd, (sx, sy) in LAUNCHER_SITES:
    obs = BUILDERS[kd](f"PE_LW_{lid}")
    anchor = bpy.data.objects.new(f"PE_LW_{lid}_anchor", None)
    col.objects.link(anchor)
    anchor.location = (sx, sy, 0.0)
    anchor.rotation_euler = (0.0, 0.0, atan2(-sx, sy))   # 本地 -Y (炮口) 转向园心
    for ob in obs:
        ob.parent = anchor
    collider(sx, sy, LW_COLLIDE[kd])

# ---------------- 许愿池 (西北外环节点) ----------------
wx, wy = WELL
add_cyl("PE_Well_base", 1.6, 0.35, (wx, wy, 0.18), mat=m_stone, verts=16)
add_cyl("PE_Well_wall", 1.35, 0.75, (wx, wy, 0.6), mat=m_stone, verts=16)
add_torus("PE_Well_rim", 1.38, 0.12, (wx, wy, 0.98), mat=m_stone, ms=32, ns=6)
add_cyl("PE_Well_water", 1.2, 0.06, (wx, wy, 0.82), mat=m_water, verts=16)
for sx in (-1, 1):
    add_cyl(f"PE_Well_post{sx}", 0.09, 1.9, (wx + sx * 1.15, wy, 1.7), mat=m_wood, verts=6)
add_box("PE_Well_roofL", (1.7, 1.5, 0.08), (wx - 0.55, wy, 2.75), rot=(0, radians(24), 0), mat=m_wood)
add_box("PE_Well_roofR", (1.7, 1.5, 0.08), (wx + 0.55, wy, 2.75), rot=(0, radians(-24), 0), mat=m_wood)
add_cyl("PE_Well_rope", 0.02, 0.9, (wx, wy, 2.05), mat=m_straw, verts=4)
add_cyl("PE_Well_bucket", 0.18, 0.26, (wx, wy, 1.5), mat=m_wood, verts=10)
add_torus("PE_Well_bucketHoop", 0.18, 0.02, (wx, wy, 1.42), mat=m_iron, ms=16, ns=4)
add_sphere("PE_Well_wisp", 0.09, (wx, wy + 0.3, 1.15), mat=m_violet, seg=8, ring=5)
collider(wx, wy, 1.7, h=1.06)   # 池沿可站

# ---------------- 石像鬼 x2 ----------------
def gargoyle(name, x, y, ry=0.0):
    add_box(f"{name}_ped", (1.1, 1.1, 0.5), (x, y, 0.25), mat=m_stone)
    add_cyl(f"{name}_pedtop", 0.5, 0.22, (x, y, 0.6), mat=m_stone, verts=8)
    add_sphere(f"{name}_body", 0.44, (x, y, 1.0), mat=m_stone, seg=12, ring=8,
               scale=(1.15, 0.9, 0.85))
    add_sphere(f"{name}_head", 0.26, (x + cos(ry) * 0.3, y + sin(ry) * 0.3, 1.42),
               mat=m_stone, seg=10, ring=7)
    hx = x + cos(ry) * 0.52
    hy = y + sin(ry) * 0.52
    add_box(f"{name}_snout", (0.2, 0.16, 0.14), (hx, hy, 1.38), rot=(0, 0, ry), mat=m_stone)
    for hs in (-1, 1):
        px_ = x + cos(ry) * 0.2 - sin(ry) * hs * 0.16
        py_ = y + sin(ry) * 0.2 + cos(ry) * hs * 0.16
        add_cone(f"{name}_horn{hs}", 0.05, 0.24, (px_, py_, 1.62),
                 mat=m_stone, verts=5, rot=(radians(-15), 0, ry))
    for ws in (-1, 1):   # 折角翼
        wx_ = x - sin(ry) * ws * 0.5
        wy_ = y + cos(ry) * ws * 0.5
        add_cone(f"{name}_wing{ws}", 0.34, 0.06, (wx_, wy_, 1.25),
                 mat=m_stone, verts=3,
                 rot=(radians(55), 0, ry + ws * radians(140)))
    for es in (-1, 1):
        px_ = x + cos(ry) * 0.42 - sin(ry) * es * 0.09
        py_ = y + sin(ry) * 0.42 + cos(ry) * es * 0.09
        add_sphere(f"{name}_eye{es}", 0.035, (px_, py_, 1.46), mat=m_violet, seg=6, ring=4)
    collider(x, y, 1.0)

gargoyle("PE_Gargoyle0", 15.0, -20.0, ry=radians(135))
gargoyle("PE_Gargoyle1", -15.0, -20.0, ry=radians(45))

# ---------------- 稻草人 x2 ----------------
scarecrow("PE_Scarecrow0", 37.6, -44.3, ry=radians(30))   # 守墓人: 北接路东侧、北门外 (第三批; 第二批时在前庭东南角 (38.4,-43.6))
scarecrow("PE_Scarecrow1", -70.0, 20.0, ry=radians(-60))

# ---------------- 花藤拱门 x3 ----------------
def vine_arch(name, cx, cy, along_deg):
    """路径拱门: 半圆藤拱 + 藤叶点 + 3 盏吊灯珠, along_deg = 路径走向"""
    a = radians(along_deg)
    ux, uy = cos(a), sin(a)          # 路径方向
    px_, py_ = -uy, ux               # 垂直方向 (拱跨向)
    R = 2.8
    n_seg = 9
    pts = []
    for k in range(n_seg + 1):
        phi = pi * k / n_seg
        ox, oz = R * cos(phi), R * sin(phi)
        pts.append((cx + px_ * ox, cy + py_ * ox, oz))
    for k in range(n_seg):
        cyl_between(f"{name}_arc{k}", pts[k], pts[k + 1], 0.12, m_wood, verts=5)
    for k in range(0, n_seg + 1, 2):
        vx = pts[k][0] + random.uniform(-0.1, 0.1)
        vy = pts[k][1] + random.uniform(-0.1, 0.1)
        add_sphere(f"{name}_vine{k}", 0.08, (vx, vy, pts[k][2]), mat=m_stem, seg=6, ring=4)
    for k in (2, 4, 6):
        add_sphere(f"{name}_lantern{k}", 0.09,
                   (pts[k][0], pts[k][1], pts[k][2] - 0.22), mat=m_warm, seg=8, ring=5)
    for s_ in (-1, 1):
        collider(cx + px_ * R * s_, cy + py_ * R * s_, 0.3)

vine_arch("PE_Arch0", 0.0, -100.0, 90.0)
vine_arch("PE_Arch1", 12.0, -40.0, 0.0)
vine_arch("PE_Arch2", 29.0, 11.8, 21.8)

# ---------------- 方向指示牌 x4 ----------------
def signpost(name, x, y, arrows):
    """arrows: [(方向角°, dot索引), ...] 每向一块箭头牌"""
    add_cyl(f"{name}_post", 0.06, 2.3, (x, y, 1.15), mat=m_wood, verts=6)
    add_sphere(f"{name}_cap", 0.09, (x, y, 2.34), mat=m_orange, seg=8, ring=5)
    for i, (ang, dot_i) in enumerate(arrows):
        a = radians(ang)
        z = 1.95 - i * 0.42
        bx = x + cos(a) * 0.45
        by = y + sin(a) * 0.45
        add_box(f"{name}_board{i}", (0.85, 0.05, 0.22), (bx, by, z), rot=(0, 0, a), mat=m_wood)
        tx = x + cos(a) * 0.95
        ty = y + sin(a) * 0.95
        add_cone(f"{name}_tip{i}", 0.12, 0.2, (tx, ty, z),
                 mat=m_wood, verts=4, rot=(0, radians(90), a))   # 锥尖指向箭头方向
        add_sphere(f"{name}_dot{i}", 0.055, (x + cos(a) * 0.3, y + sin(a) * 0.3, z + 0.16),
                   mat=m_dot[dot_i], seg=6, ring=4)
    collider(x, y, 0.35)

signpost("PE_Sign0", 4.2, -30.0, [(0, 3), (90, 2)])          # 东墓园 / 北摩天轮
signpost("PE_Sign1", -4.2, -75.0, [(213, 1), (147, 0)])      # 幽灵港 / 许愿池
signpost("PE_Sign2", 2.3, -57.3, [(90, 0), (270, 3), (0, 1)])  # 北园 / 南园 / 东墓园 (第三批: 这块牌正立在墓园西支路口)
signpost("PE_Sign3", 19.6, -20.2, [(0, 0)])                  # 烟花释放器(东)

# ---------------- 三大预留区 (围挡 + 敬请期待牌 + 拱门) ----------------
def zone_fence(name, x0, x1, y0, y1, gap_edge, gap_lo, gap_hi):
    """预留区围挡: 四边立柱 + 双横杆 (缺口断开) + 碰撞矩形 (缺口分段, 厚 0.28)"""
    def make_edge(ax0, ay0, ax1, ay1, vertical, ename):
        L = hypot(ax1 - ax0, ay1 - ay0)
        n = max(int(L / 3.0), 2)
        prev = None
        for k in range(n + 1):
            t = k / n
            fx = ax0 + (ax1 - ax0) * t
            fy = ay0 + (ay1 - ay0) * t
            in_gap = ename == gap_edge and (
                (gap_lo < fy < gap_hi) if vertical else (gap_lo < fx < gap_hi))
            if in_gap:
                prev = None
                continue
            add_box(f"{name}_p_{ename}{k}", (0.16, 0.16, 1.3), (fx, fy, 0.65), mat=m_wood)
            for rz_ in (0.62, 1.12):
                if prev is not None:
                    cyl_between(f"{name}_r_{ename}{k}_{rz_}", (prev[0], prev[1], rz_),
                                (fx, fy, rz_), 0.05, m_iron, verts=4)
            prev = (fx, fy)
        if vertical:
            if ename == gap_edge:
                collider_rect(ax0, (ay0 + gap_lo) / 2, 0.28, (gap_lo - ay0) / 2)
                collider_rect(ax0, (gap_hi + ay1) / 2, 0.28, (ay1 - gap_hi) / 2)
            else:
                collider_rect(ax0, (ay0 + ay1) / 2, 0.28, (ay1 - ay0) / 2)
        else:
            if ename == gap_edge:
                collider_rect((ax0 + gap_lo) / 2, ay0, (gap_lo - ax0) / 2, 0.28)
                collider_rect((gap_hi + ax1) / 2, ay0, (ax1 - gap_hi) / 2, 0.28)
            else:
                collider_rect((ax0 + ax1) / 2, ay0, (ax1 - ax0) / 2, 0.28)
    make_edge(x0, y0, x1, y0, False, "S")
    make_edge(x0, y1, x1, y1, False, "N")
    make_edge(x0, y0, x0, y1, True, "W")
    make_edge(x1, y0, x1, y1, True, "E")

def zone_sign(name, x, y, rot_deg):
    """预留区招牌: 双柱 + 发光横板 + 三彩点; rot 0 = 板面朝南北, rot 90 = 朝东西"""
    a = radians(rot_deg)
    ca, sa = cos(a), sin(a)
    add_box(f"{name}_board", (3.0, 0.14, 1.1), (x, y, 1.7), rot=(0, 0, a), mat=m_sign_g)
    for k in range(3):
        ox = (k - 1) * 1.3
        add_sphere(f"{name}_sd{k}", 0.1, (x + ca * ox, y + sa * ox, 1.7),
                   mat=m_dot[k % 4], seg=8, ring=5)
    for sx_ in (-1, 1):
        px_ = x + ca * sx_ * 1.7
        py_ = y + sa * sx_ * 1.7
        add_cyl(f"{name}_sp{sx_}", 0.08, 2.4, (px_, py_, 1.2), mat=m_wood, verts=6)
        collider(px_, py_, 0.2)

# 过山车预留区 (北): 南边开口 x∈[11,19], 支路 78° 正对缺口
# 幽灵港 (西南): 东边开口 y∈[-43,-37], 支路 217.6° 正对缺口
zone_fence("PE_ZoneBay", -88, -52, -55, -35, "E", -43, -37)
zone_sign("PE_ZoneBay_sign", -51.8, -33.0, 90)

# 秘境预留区 (东南): 西边开口 y∈[-54,-48], 支路 -32.3° 正对缺口
zone_fence("PE_ZoneThird", 78, 112, -78, -42, "W", -54, -48)
zone_sign("PE_ZoneThird_sign", 76.2, -45.5, 90)

tmark(f"props done (grass={len(tufts)} pumps={len(pump_plan)} flowers={len(flower_spots)})")

# ---------------- 园区树木布置 ----------------
tree_extras = (list(pump_spots) + flower_spots +
               [(lx, ly) for lx, ly, _fry in lamp_positions] +
               [(GV_BENCH_TREE_XY if _bi == len(bench_spots) - 1 else (bx, by))
                for _bi, (bx, by, _rz) in enumerate(bench_spots)] +   # 末张长椅按原位 (GV_BENCH_TREE_XY)
               [(15.0, -20.0), (-15.0, -20.0), (40.0, -47.0), (-70.0, 20.0),
                (0.0, -146.0), (0.0, -60.0), (0.0, -100.0), (12.0, -40.0),
                (29.0, 11.8), (15.0, 68.6), (-52.6, -40.0), (77.4, -51.0),
                (26.0, -36.0), (12.5, -11.2), (-11.8, -11.5),
                (34.0, -41.0), (-19.5, -28.8), (-35.2, -27.8)])

def blocked(x, y, margin):
    if on_path(x, y, margin):
        return True
    for px_, py_ in tree_extras:
        if (px_ - x) ** 2 + (py_ - y) ** 2 < (1.8 + margin) ** 2:
            return True
    return False

tree_spots = []
tries = 0
while len(tree_spots) < 22 and tries < 3000:
    tries += 1
    ang = random.uniform(0, 2 * pi)
    rr = random.uniform(26, 135)
    x, y = rr * cos(ang), rr * sin(ang)
    if blocked(x, y, 2.6):
        continue
    if any((tx - x) ** 2 + (ty - y) ** 2 < 64 for tx, ty in tree_spots):
        continue
    tree_spots.append((x, y))
# 墓园新址 (椭圆, 见墓园段) 内不落树。树位是确定性的, 现在无一落在园内 (最近的一棵在 (52.4,-47.6), 园外东北)。
# 万一上游改动后有树落进来: 沿径向确定性推到园外 3 m —— 不重新抽随机数 (那会让其后的树 / 松 / 柳 / 远山全部换位)
GV_TREE_PUSH = []
for _i, (_x, _y) in enumerate(tree_spots):
    if gv_inside(_x, _y, GV_EA + 3.0, GV_EB + 3.0):
        _dx, _dy = _x - GV_EX, _y - GV_EY
        if abs(_dx) < 1e-6 and abs(_dy) < 1e-6:
            _dx = 1.0
        _s = 1.02 / (((_dx / (GV_EA + 3.0)) ** 2 + (_dy / (GV_EB + 3.0)) ** 2) ** 0.5)
        tree_spots[_i] = (GV_EX + _s * _dx, GV_EY + _s * _dy)
        GV_TREE_PUSH.append(_i)
if GV_TREE_PUSH:
    print("GV_TREE_PUSHED", GV_TREE_PUSH)
for i, (x, y) in enumerate(tree_spots):
    spooky_tree(f"PE_Tree{i}", x, y, scale=random.uniform(0.9, 1.4))

# 广场外圈缠灯松 x5 (保留原布局) + 外围松 x7
for i in range(5):
    th = i * 2 * pi / 5 + 0.4
    x, y = 21.5 * cos(th), 21.5 * sin(th)
    pine_tree(f"PE_Pine{i}", x, y, random.choice(("tall", "fat", "crooked")), lit=True)
outer_pines = []
tries = 0
while len(outer_pines) < 7 and tries < 1500:
    tries += 1
    ang = random.uniform(0, 2 * pi)
    rr = random.uniform(100, 128)
    x, y = rr * cos(ang), rr * sin(ang)
    if blocked(x, y, 2.6):
        continue
    if any((tx - x) ** 2 + (ty - y) ** 2 < 100 for tx, ty in outer_pines):
        continue
    outer_pines.append((x, y))
for i, (x, y) in enumerate(outer_pines):
    pine_tree(f"PE_PineO{i}", x, y, random.choice(("tall", "fat", "crooked")), lit=True)

# 垂柳 x4
for i, (x, y) in enumerate(((-45.0, 55.0), (60.0, 20.0), (18.0, 58.0), (-85.0, 15.0))):
    willow_tree(f"PE_Willow{i}", x, y, scale=random.uniform(0.95, 1.25))

tmark("trees done")

# ---------------- 远景: 山脊 + 城市灯火 (随扩园外推) ----------------
for i in range(12):
    th = i * 2 * pi / 12 + 0.26
    rr = random.uniform(420, 470)
    add_cone(f"PE_Ridge{i}", random.uniform(60, 110), random.uniform(70, 130),
             (rr * cos(th), rr * sin(th), -6.0), mat=m_ridge, verts=7)
for i in range(90):
    th = random.uniform(0, 2 * pi)
    rr = random.uniform(300, 390)
    add_sphere(f"PE_City{i}", 0.8, (rr * cos(th), rr * sin(th), random.uniform(2.0, 14.0)),
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

cam_aerial = add_cam("PE_CamAerial", (160, -160, 120), (0, 0, 4), lens=28)
cam_street = add_cam("PE_CamStreet", (0.0, -105.0, 1.75), (0, -45, 5.5), lens=30)
cam_corner = add_cam("PE_CamCorner", (9.5, -51.8, 1.9), (42.0, -56.0, 2.4), lens=30)   # 墓园: 从西支路看西门与主走道 (2026-11-26 第三批; 离门 10 m、略偏北, 整座门 + 园内走道进画面)

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
# v3: bpy.ops.object.join 在 17k 对象上要爬十几分钟 (踩坑: 见 blender-bpydata-fast-helpers),
# 改 bpy.data 直合: 逐对象施矩阵收集顶点/面/顶点色, 一次 from_pydata。
n_mesh = sum(1 for ob in bpy.context.scene.objects if ob.type == "MESH")
tmark(f"scene done ({n_mesh} meshes) -> join")
groups = {}
for ob in list(bpy.context.scene.objects):
    if ob.type != "MESH":
        continue
    mat = ob.data.materials[0].name if ob.data.materials else "NONE"
    groups.setdefault(mat, []).append(ob)
print(f"JOIN groups={len(groups)}")
for mat_name, obs in groups.items():
    vs_all = []
    fs_all = []
    vcol_all = []
    group_vcol = any(len(ob.data.color_attributes) > 0 for ob in obs)
    offset = 0
    # 目标空间 = 世界坐标 (新对象零变换): wind.js 顶点着色器按世界 y/相位计算, 正好需要
    for ob in obs:
        me = ob.data
        mw = ob.matrix_world
        buf = None
        if len(me.color_attributes) > 0:
            attr = me.color_attributes[0]
            buf = [0.0] * (len(me.vertices) * 4)
            attr.data.foreach_get("color", buf)
        for v in me.vertices:
            vs_all.append(tuple(mw @ v.co))
        if buf is not None:
            vcol_all += buf                      # 扁平 RGBA 流 (foreach_set 要求一维)
        elif group_vcol:
            vcol_all += [1.0] * (len(me.vertices) * 4)
        for poly in me.polygons:
            fs_all.append(tuple(i + offset for i in poly.vertices))
        offset = len(vs_all)
        bpy.data.objects.remove(ob, do_unlink=True)
    me_new = bpy.data.meshes.new(f"PE_{mat_name}")
    me_new.from_pydata(vs_all, [], fs_all)
    me_new.validate(verbose=False)
    me_new.update()
    if group_vcol:
        attr = me_new.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
        attr.data.foreach_set("color", vcol_all)
        try:
            me_new.color_attributes.active_color = attr
        except Exception:
            pass
    if me_new.materials:
        pass
    src_mat = None
    for o_ in bpy.data.materials:
        if o_.name == mat_name:
            src_mat = o_
            break
    if src_mat:
        me_new.materials.append(src_mat)
    ob_new = bpy.data.objects.new(f"PE_{mat_name}", me_new)
    col.objects.link(ob_new)
tmark(f"joined ({len(groups)} groups)")

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
# 发射器锚点: dx/dz = 炮口水平朝向单位向量 (朝园心), mz = 管口离地高 (与建模常量一致)
MUZZLE_LOCAL = {"A": (0.0, -0.39, 1.63), "B": (0.0, -0.39, 2.92), "C": (-0.2, -0.36, 1.28)}
manifest_launchers = []
for lid, kd, (sx, sy) in LAUNCHER_SITES:
    lapp = hypot(sx, sy) or 1.0
    manifest_launchers.append({"id": lid, "kind": kd,
                               "x": round(sx, 2), "z": round(-sy, 2),
                               "dx": round(-sx / lapp, 3), "dz": round(sy / lapp, 3),
                               "mz": MUZZLE_LOCAL[kd][2]})
# 园区真实点光 (park_light 登记): blender (x, y, z) -> app (x, z, -y); 运行时 src/core/world.js 按此建灯 (槽位数见 LIGHT_SLOTS)
manifest_lights = [
    {"x": round(l["x"], 2), "y": round(l["z"], 2), "z": round(-l["y"], 2), "color": l["color"],
     "intensity": l["intensity"], "distance": l["distance"], "decay": l["decay"],
     "tag": l["tag"], "key": l["key"]}
    for l in PARK_LIGHTS
]
manifest = {
    "version": 3,
    "note": "坐标为 glTF/app 空间 (x, z); 由 park_env.py v3 自动生成; h = 顶面高度(可站立), 缺省为无限高阻挡; rects = 轴对齐盒墙(可推挤); launchers = 烟花发射器锚点; lights = 园区真实点光 (x, y 高, z; tag = 来源件名, key = 控制它的设置键)",
    "boundaryR": 144.5,
    "spawn": {"x": 0.0, "z": 144.0},
    "boarding": {"x": 0.0, "z": 16.4},
    "launchers": manifest_launchers,
    "lights": manifest_lights,
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
print(f"COLLIDERS circles={len(manifest['circles'])} rects={len(manifest['rects'])} pois={len(manifest['pois'])} lights={len(manifest_lights)}")
tmark("colliders written, rendering previews")

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
tmark("DONE")
print("DONE")
