# 迷魂湖概念稿 — 湖面/灯笼三变体/栈桥/岸线 构图渲染
# 独立脚本: 只产 preview/concept_lake_*.png, 不产出/不覆盖 park_env.glb
# 确认后把灯笼原型/栈桥/岸线生成器移植进 park_env.py (见会话内迷魂湖方案)
#
# 运行: E:/blender/blender.exe -b -P model/park_env/concept_lake.py
# 材质语义严格对齐 glTF→three.js (同 concept_veg.py 头注)。
# 水面用低粗糙暗色镜面 (Cycles 光线追踪反射) — 预览游戏内 Water 平面反射方案的观感;
# 极光卡 visible_camera=False: 相机拍不到, 只出现在水面反射里 (预览"极光映水")。

import bpy
import random
from math import pi, radians, sin, cos, hypot, atan2
from mathutils import Vector, Quaternion
from pathlib import Path

random.seed(20261118)
OUT = Path(__file__).resolve().parent / "preview"
OUT.mkdir(exist_ok=True)

# 清空默认启动场景 (Cube/灯光/相机): 默认 Cube 会以白方块污染原点簇 (踩坑)
for _o in list(bpy.data.objects):
    bpy.data.objects.remove(_o, do_unlink=True)

sc = bpy.context.scene
col = bpy.data.collections.new("CONCEPT_LAKE")
sc.collection.children.link(col)


def tmark(label):
    print(f"[lake] {label}", flush=True)


# ---------------- 基础 helper (照抄 concept_veg.py / park_env.py) ----------------
def hex_lin(h, a=1.0):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    def f(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (f(r), f(g), f(b), a)


def _new_obj(name, verts, faces, mat, sm):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate(verbose=False)
    me.update()
    if mat:
        me.materials.append(mat)
    if sm:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def set_vcol(ob, colors):
    """colors: 每顶点 (r,g,b) LINEAR 值 → COLOR_0"""
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


def make_mat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    def sock(node, ident):
        for s in node.inputs:
            if s.identifier == ident:
                return s
        return None
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


def make_vcol_mat(name, color, rough=0.5, emit=None, strength=0.0):
    """顶点色材质: Base = 颜色 × COLOR_0"""
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
    for s in p.inputs:
        if s.identifier == "Roughness":
            s.default_value = rough
        if emit and s.identifier == "Emission Color":
            s.default_value = hex_lin(emit)
        if emit and s.identifier == "Emission Strength":
            s.default_value = strength
    return m


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


def add_sphere(name, r, loc, mat=None, seg=10, ring=6, scale=(1, 1, 1), sm=True):
    vs = [(0, 0, r)]
    for j in range(1, ring):
        phi = pi * j / ring
        sp, cp = sin(phi), cos(phi)
        for i in range(seg):
            th = 2 * pi * i / seg
            vs.append((r * sp * cos(th), r * sp * sin(th), r * cp))
    vs.append((0, 0, -r))
    top_i = 0
    bot_i = len(vs) - 1
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
    ob = _new_obj(name, vs, fs, mat, sm)
    ob.location = loc
    ob.scale = scale
    return ob


def blade(prefix, base, length, width, yaw, bend, mat, root_c, tip_c,
          segs=5, lean=0.2, twist=0.0):
    """弯曲锥形草叶 (照抄 park_env.py): 芦苇用"""
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
        w = width * (1 - t) ** 1.15 + 0.0012
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


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


# ---------------------------------------------------------------- 材质 ----
# 迷魂湖色板: 暖白/南瓜橙 主导 (PRODUCT.md 3D 氛围层), 水底深靛蓝 (许愿池 m_water 配方)
m_water   = make_mat("C_LakeWater", "#141B33", rough=0.11, metal=0.2,
                     emit="#4A3A8A", strength=0.15)  # 低粗糙镜面 → 真反射预览 (自发光只留深靛暗示)
m_shore   = make_mat("C_Shore", "#241D14", rough=0.92)
m_grass   = make_mat("C_GrassDark", "#142319", rough=0.95)
m_wood    = make_mat("C_Wood", "#5A4028", rough=0.88)
m_wood_d  = make_mat("C_WoodDark", "#33251A", rough=0.9)
m_iron    = make_mat("C_Iron", "#3A3F4A", rough=0.5, metal=0.8)
m_lamp    = make_mat("C_LampGlass", "#FFE9C4", emit="#FFE9C4", strength=2.6)
m_plaque  = make_mat("C_Plaque", "#9B5BFF", emit="#9B5BFF", strength=1.5)
DOTS = ["#FFE9C4", "#FFA53B", "#9B5BFF"]
m_dot = [make_mat(f"C_Dot{i}", c, emit=c, strength=2.6) for i, c in enumerate(DOTS)]
# 灯笼纸面: Base=Emit (unlit 灯感, 对齐运行时 MeshBasic+instanceColor 语义)
LANTERN_KINDS = [
    ("cream",  "#FFE9C4", 4.2, 0.60),
    ("orange", "#FFA53B", 4.0, 0.25),
    ("pink",   "#FF9E9E", 3.6, 0.10),
    ("red",    "#C43B3B", 3.2, 0.05),
]
m_lantern = {k: make_mat(f"C_Lantern_{k}", c, rough=0.6, emit=c, strength=s)
             for k, c, s, _w in LANTERN_KINDS}
m_reed    = make_vcol_mat("C_Reed", "#FFFFFF", rough=0.9)
m_rock    = make_mat("C_Rock", "#23201C", rough=0.85)
m_sky     = make_mat("C_SkyCard", "#FFFFFF", rough=1.0, emit="#FFFFFF", strength=1.0)

tmark("materials ready")

# ---------------------------------------------------------------- 场景 ----
# 湖体真实比例预览: 椭圆 rx34 / ry27 (方案定稿值), 水面 z=0, 岸唇 z≈0.22
RX, RY = 34.0, 27.0
NSEG = 96


def ellipse_pt(rx_, ry_, a):
    return (rx_ * cos(a), ry_ * sin(a))


# -- 水面 (椭圆扇面盘, sm=False 保平) --
wv = [(0.0, 0.0, 0.0)]
for k in range(NSEG):
    a = 2 * pi * k / NSEG
    x, y = ellipse_pt(RX, RY, a)
    wv.append((x, y, 0.0))
wf = [(0, 1 + k, 1 + (k + 1) % NSEG) for k in range(NSEG)]
_new_obj("C_WaterSurf", wv, wf, m_water, False)

# -- 岸唇带 (内缘椭圆+0.5 外扩, 高 0.22 → 外缘 +6m 落到 -0.02): 斜坡石壤 --
sv, sf = [], []
N_IN, N_OUT = RX + 0.5, RY + 0.5
O_IN, O_OUT = RX + 6.5, RY + 6.5
for k in range(NSEG):
    a = 2 * pi * k / NSEG
    sv.append((N_IN * cos(a), N_OUT * sin(a), 0.22))
for k in range(NSEG):
    a = 2 * pi * k / NSEG
    sv.append((O_IN * cos(a), O_OUT * sin(a), -0.02))
for k in range(NSEG):
    k2 = (k + 1) % NSEG
    sf.append((k, k2, NSEG + k2, NSEG + k))
_new_obj("C_ShoreBand", sv, sf, m_shore, False)

# -- 草地外环 (+6.5 → +13) --
gv, gf = [], []
G_IN, G_OUT = RX + 6.5, RY + 6.5
GX_IN, GX_OUT = RX + 13.0, RY + 13.0
for k in range(NSEG):
    a = 2 * pi * k / NSEG
    gv.append((G_IN * cos(a), G_OUT * sin(a), -0.02))
for k in range(NSEG):
    a = 2 * pi * k / NSEG
    gv.append((GX_IN * cos(a), GX_OUT * sin(a), -0.03))
for k in range(NSEG):
    k2 = (k + 1) % NSEG
    gf.append((k, k2, NSEG + k2, NSEG + k))
_new_obj("C_GrassRing", gv, gf, m_grass, False)

# -- 栈桥 (西岸伸入, x=-4 沿 +y): 桥面顶 z=0.5 宽 2.2, 长 18m --
PIER_X, PIER_Y0, PIER_Y1 = -4.0, -26.5, -8.5
DECK_Z, DECK_W = 0.50, 2.2
plank_n = 31
for k in range(plank_n):
    y = PIER_Y0 + 0.29 + k * ((PIER_Y1 - PIER_Y0 - 0.58) / (plank_n - 1))
    add_box(f"C_Plank{k}", (DECK_W, 0.55, 0.055),
            (PIER_X + random.uniform(-0.012, 0.012), y, DECK_Z - 0.0275),
            rot=(0, 0, random.uniform(-0.012, 0.012)), mat=m_wood)
for sx in (-0.95, 0.95):
    add_box(f"C_Stringer{sx}", (0.13, PIER_Y1 - PIER_Y0, 0.15),
            (PIER_X + sx, (PIER_Y0 + PIER_Y1) / 2, DECK_Z - 0.14), mat=m_wood_d)
POST_YS = [PIER_Y0 + 1.0 + k * 2.6 for k in range(7)]
for y in POST_YS:
    for sx in (-1.02, 1.02):
        add_cyl(f"C_Post{y:.0f}_{sx}", 0.075, 1.9, (PIER_X + sx, y, -0.42),
                mat=m_wood_d, verts=8)
        add_cyl(f"C_RailStub{y:.0f}_{sx}", 0.035, 0.46, (PIER_X + sx, y, DECK_Z + 0.23),
                mat=m_wood_d, verts=5)
for sx in (-1.02, 1.02):
    cyl_between(f"C_RailA{sx}", (PIER_X + sx, PIER_Y0 + 0.4, DECK_Z + 0.44),
                (PIER_X + sx, PIER_Y1 - 0.4, DECK_Z + 0.44), 0.035, m_wood_d, verts=5)
    cyl_between(f"C_RailB{sx}", (PIER_X + sx, PIER_Y0 + 0.4, DECK_Z + 0.20),
                (PIER_X + sx, PIER_Y1 - 0.4, DECK_Z + 0.20), 0.028, m_wood_d, verts=5)
# 入口两级台阶 (对齐运行时 stepRects 语义: h 0.18 / 0.36)
add_box("C_Step0", (2.4, 0.55, 0.18), (PIER_X, PIER_Y0 - 0.32, 0.09), mat=m_wood)
add_box("C_Step1", (2.4, 0.55, 0.36), (PIER_X, PIER_Y0 + 0.28, 0.18), mat=m_wood)

# -- 栈桥灯柱 ×2 (缩比维多利亚路灯: 暖玻璃球 + 锥帽) --
for li, (lx, ly) in enumerate([(PIER_X - 1.02, -22.0), (PIER_X + 1.02, -13.0)]):
    add_cyl(f"C_LampBase{li}", 0.13, 0.1, (lx, ly, DECK_Z + 0.05), mat=m_iron, verts=8)
    add_cyl(f"C_LampPole{li}", 0.045, 1.9, (lx, ly, DECK_Z + 1.0), mat=m_iron, verts=6)
    add_sphere(f"C_LampGlass{li}", 0.2, (lx, ly, DECK_Z + 2.05), mat=m_lamp, seg=10, ring=6)
    add_cone(f"C_LampCap{li}", 0.26, 0.18, (lx, ly, DECK_Z + 2.24), mat=m_iron, verts=6)

# -- 栈桥尽头铭牌 (zone_sign 缩比: 双柱 + 发光板 + 三彩点) --
SXY = (PIER_X, PIER_Y1 - 0.7)
for sx in (-0.6, 0.6):
    add_cyl(f"C_SignPost{sx}", 0.05, 1.15, (SXY[0] + sx, SXY[1], DECK_Z + 0.575),
            mat=m_wood_d, verts=6)
add_box("C_SignBoard", (1.6, 0.08, 0.46), (SXY[0], SXY[1], DECK_Z + 1.05), mat=m_plaque)
for k in range(3):
    add_sphere(f"C_SignDot{k}", 0.055, (SXY[0] + (k - 1) * 0.45, SXY[1], DECK_Z + 1.05),
               mat=m_dot[k], seg=8, ring=5)

# -- 半沉石 ×4 + 芦苇丛 ×3 (岸缘细节) --
for ri, ang in enumerate((radians(150), radians(210), radians(255), radians(300))):
    x, y = ellipse_pt(RX - 1.2, RY - 1.2, ang)
    add_sphere(f"C_Rock{ri}", 1.0, (x, y, -0.15), mat=m_rock, seg=8, ring=5,
               scale=(random.uniform(0.8, 1.5), random.uniform(0.6, 1.0), 0.42), sm=True)
REED_C = hex_lin("#182A1E")[:3]
for ci, ang in enumerate((radians(195), radians(242), radians(286))):
    bx, by = ellipse_pt(RX + 1.6, RY + 1.6, ang)
    tip_kind = random.random()
    tip = hex_lin("#4E6A3A")[:3] if tip_kind < 0.7 else hex_lin("#6A6238")[:3]
    for k in range(8):
        a = ang + random.uniform(-0.22, 0.22)
        rx_ = random.uniform(0.1, 1.3)
        blade(f"C_Reed{ci}_{k}", (bx + rx_ * cos(a), by + rx_ * sin(a), 0.05),
              random.uniform(0.8, 1.35), 0.028, a + random.uniform(-0.5, 0.5),
              random.uniform(0.25, 0.6), m_reed, REED_C, tip)

# -- 灯笼海 ~155 盏: 西南(栈桥视角轴)密 东北稀; 中环留航道(下一版船路) --
# 三个原型 (低多边形棱面球, sm=False): A 大胖 / B 中圆 / C 小圆
PROTO = [
    ("A", 0.30, 10, 6, 0.45),
    ("B", 0.24, 8, 5, 0.35),
    ("C", 0.18, 8, 5, 0.20),
]
def lantern_weights(x, y):
    n = hypot(x / RX, y / RY)
    if n > 0.94:
        return 0.0
    t = max(-1.0, min(1.0, 0.55 * (x / RX) + 0.45 * (y / RY)))  # -1 西南 .. +1 东北
    w = 0.92 - 0.55 * (t * 0.5 + 0.5)
    if 0.30 < n < 0.56:      # 航道稀疏带
        w *= 0.4
    return w

kinds = [k for k, _c, _s, w in LANTERN_KINDS for _ in range(int(w * 100))]
placed = 0
tries = 0
while placed < 155 and tries < 6000:
    tries += 1
    x = random.uniform(-RX + 2.5, RX - 2.5)
    y = random.uniform(-RY + 2.5, RY - 2.5)
    if random.random() > lantern_weights(x, y):
        continue
    pname, pr, pseg, pring, pprob = PROTO[0]
    roll = random.random()
    if roll < 0.45:
        pname, pr, pseg, pring, _ = PROTO[0]
    elif roll < 0.80:
        pname, pr, pseg, pring, _ = PROTO[1]
    else:
        pname, pr, pseg, pring, _ = PROTO[2]
    s = random.uniform(0.75, 1.25)
    r_eff = pr * s
    kind = random.choice(kinds)
    add_sphere(f"C_Lant_{pname}{placed}", r_eff,
               (x, y, r_eff * 0.42), mat=m_lantern[kind],
               seg=pseg, ring=pring, sm=False)
    placed += 1
tmark(f"lanterns placed: {placed}")

# 近景特写用三盏样灯 (variant 展示位, 紧邻 float 机位)
for si, (pname, pr, pseg, pring, _p) in enumerate(PROTO):
    sx_, sy_ = [(-7.2, -12.2), (-5.4, -10.6), (-6.8, -9.2)][si]
    add_sphere(f"C_Lant_Sample{pname}", pr, (sx_, sy_, pr * 0.42),
               mat=m_lantern["cream" if si == 0 else "orange" if si == 1 else "pink"],
               seg=pseg, ring=pring, sm=False)

# -- 极光卡 (visible_camera=False: 只进水面反射, 预览"极光映水") --
for name, loc, rot_z, col_hex, e_s in (
        ("C_AuroraTeal",  (-16.0, 52.0, 22.0), radians(14), "#1E7A5E", 0.30),
        ("C_AuroraViolet", (19.0, 56.0, 26.0), radians(-11), "#5A3AA8", 0.32)):
    ob = add_box(name, (52.0, 2.0, 26.0), loc, rot=(0, 0, rot_z),
                 mat=make_mat(name + "_m", col_hex, emit=col_hex, strength=e_s))
    try:
        ob.visible_camera = False   # 相机不可见, 反射可见 (Cycles ray visibility)
    except Exception:
        pass

# ---------------- 夜景灯光 / 世界 / 雾 / 相机 ----------------
tmark("lights & world")


def add_light(kind, name, loc, energy, color, target=None, size=4.0, angle=2.5, radius=0.2):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = hex_lin(color)[:3]
    ob = bpy.data.objects.new(name, ld)
    col.objects.link(ob)
    ob.location = loc
    if kind == 'SUN':
        ld.angle = radians(angle)
    if kind == 'AREA':
        ld.size = size
    if kind == 'POINT':
        ld.shadow_soft_size = radius
    if target:
        look_at(ob, target)
    try:
        ob.visible_camera = False   # 5.3 面光会被相机拍到成白墙 (踩坑)
    except Exception:
        pass
    return ob


def rig(cx, cy, warm=True, sun_energy=2.0, warm_energy=30.0):
    """标准夜机位光: 冷月主光 + 极光双色补 + 暖色点光 (照抄 concept_veg.py)"""
    add_light('SUN', f"L_sun_{cx}", (cx - 6, cy - 7, 9), sun_energy, "#B4C7FF",
              target=(cx, cy, 1.2), angle=3.5)
    add_light('AREA', f"L_ag_{cx}", (cx - 5, cy + 7, 8.5), 32, "#2FA97C",
              target=(cx, cy, 0.6), size=7)
    add_light('AREA', f"L_av_{cx}", (cx + 6, cy + 5, 7), 26, "#7A4FA8",
              target=(cx, cy, 0.8), size=6)
    if warm:
        add_light('POINT', f"L_wp_{cx}", (cx + 1.6, cy - 2.2, 1.15), warm_energy,
                  "#FFB24A", radius=0.3)
        add_light('POINT', f"L_wp2_{cx}", (cx - 2.4, cy + 1.8, 0.5), 10, "#FFD9A0",
                  radius=0.4)


rig(-4.0, -18.0, warm_energy=30)          # 栈桥机位
rig(6.0, 2.0, warm=False, sun_energy=1.6)  # 灯海中心
add_light('POINT', "L_pierlamp0", (-5.02, -22.0, 2.6), 26, "#FFD9A0", radius=0.25)
add_light('POINT', "L_pierlamp1", (-2.98, -13.0, 2.6), 26, "#FFD9A0", radius=0.25)

w = bpy.data.worlds.new("ConceptLakeNight")
sc.world = w
w.use_nodes = True
ntw = w.node_tree
# 5.3 的 use_nodes 可能不自动建节点: 手工补齐 Background/Output/Volume (踩坑: StopIteration)
bg = next((n for n in ntw.nodes if n.type == "BACKGROUND"), None)
wout = next((n for n in ntw.nodes if n.type == "WORLD_OUTPUT"), None)
if wout is None:
    wout = ntw.nodes.new("ShaderNodeOutputWorld")
if bg is None:
    bg = ntw.nodes.new("ShaderNodeBackground")
    ntw.links.new(bg.outputs["Background"], wout.inputs["Surface"])
bg.inputs[0].default_value = hex_lin("#05070F")
bg.inputs[1].default_value = 0.5
# 体积雾: 挂 world (无表面风险; 盒式雾立方会以白面挡住相机 — 已踩坑)
wvol = ntw.nodes.new("ShaderNodeVolumePrincipled")
wvol.inputs["Density"].default_value = 0.0005
wvol.inputs["Color"].default_value = hex_lin("#9FB2D8")
wvol.inputs["Anisotropy"].default_value = 0.3
ntw.links.new(wvol.outputs["Volume"], wout.inputs["Volume"])


def add_cam(name, loc, target, lens=40):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    ob = bpy.data.objects.new(name, cd)
    col.objects.link(ob)
    ob.location = loc
    look_at(ob, target)
    return ob


cams = {
    "concept_lake_pier": add_cam("camPier", (-4.5, -27.8, 1.5), (-2.4, -9.5, 0.4), lens=28),
    "concept_lake_float": add_cam("camFloat", (-11.5, -16.0, 0.5), (-5.8, -11.0, 0.3), lens=42),
    "concept_lake_aerial": add_cam("camAerial", (-22.0, -40.0, 32.0), (2.0, 2.0, 0.0), lens=34),
}

# 渲染设置: Cycles + AgX(Punchy) + 雾光合成 (模拟游戏 bloom) — 照抄 concept_veg.py
sc.render.engine = 'CYCLES'
try:
    prefs = bpy.context.preferences.addons.get('cycles')
    if prefs:
        cp = prefs.preferences
        for dtype in ('OPTIX', 'CUDA', 'HIP'):
            try:
                cp.compute_device_type = dtype
                cp.get_devices()
                for d in cp.devices:
                    d.use = True
                sc.cycles.device = 'GPU'
                tmark(f"GPU on: {dtype}")
                break
            except Exception:
                continue
except Exception as e:
    tmark(f"gpu skip: {e}")
sc.cycles.samples = 80
sc.cycles.use_adaptive_sampling = True
sc.cycles.adaptive_threshold = 0.02
sc.cycles.use_denoising = True
sc.render.resolution_x = 1280
sc.render.resolution_y = 800
sc.render.film_transparent = False
try:
    sc.view_settings.view_transform = 'AgX'
    for lk in ('AgX - Punchy', 'Punchy'):
        try:
            sc.view_settings.look = lk
            break
        except Exception:
            continue
    sc.view_settings.exposure = 0.45
except Exception:
    sc.view_settings.view_transform = 'Filmic'

# 合成: FOG_GLOW ≈ 游戏 UnrealBloom (Blender 5 合成器组: RenderLayers→Glare→GroupOutput)
try:
    cnt = getattr(sc, "compositing_node_group", None)
    if cnt is None:
        cnt = bpy.data.node_groups.new("ConceptLakeComp", 'CompositorNodeTree')
        sc.compositing_node_group = cnt
    cnt.nodes.clear()
    rl = cnt.nodes.new('CompositorNodeRLayers')
    rl.location = (-400, 0)
    gl = cnt.nodes.new('CompositorNodeGlare')
    gl.location = (-50, 0)
    try:
        cnt.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    except Exception:
        cnt.outputs.new('NodeSocketColor', 'Image')
    gout = cnt.nodes.new('NodeGroupOutput')
    gout.location = (300, 0)
    glare_ok = True
    try:
        gl.glare_type = 'FOG_GLOW'
        gl.threshold = 1.0
        gl.size = 6
        gl.quality = 'MEDIUM'
    except Exception as e:
        # 5.3 Glare 枚举/API 变更: 属性失配时该节点会以默认 STREAKS 模式渲染十字星芒 —
        # 直接摘除 Glare 直连输出 (游戏内用真 UnrealBloom, 概念稿无需模拟)
        tmark(f"glare unusable ({e}); 摘除直连")
        cnt.nodes.remove(gl)
        glare_ok = False
    if glare_ok:
        cnt.links.new(rl.outputs['Image'], gl.inputs['Image'])
        cnt.links.new(gl.outputs['Image'], gout.inputs['Image'])
    else:
        cnt.links.new(rl.outputs['Image'], gout.inputs['Image'])
except Exception as e:
    tmark(f"compositor skip ({e}); 渲染不带 bloom 模拟")
    try:
        sc.compositing_node_group = None
    except Exception:
        pass

tmark("render start")
import os
if os.environ.get("CONCEPT_DEBUG"):
    dbg = {
        "debug_lake_high": add_cam("camDbgH", (-9.0, -26.0, 6.0), (-2.0, -12.0, 0.2), lens=30),
        "debug_lake_low": add_cam("camDbgL", (-10.0, -18.5, 0.7), (-4.5, -12.0, 0.35), lens=34),
    }
    sc.cycles.samples = 24
    for name, cam in dbg.items():
        sc.camera = cam
        sc.render.filepath = str(OUT / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        tmark(f"rendered {name}")
    tmark("ALL DONE")
else:
    for name, cam in cams.items():
        sc.camera = cam
        sc.render.filepath = str(OUT / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        tmark(f"rendered {name}")
tmark("ALL DONE")
