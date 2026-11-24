# -*- coding: utf-8 -*-
"""
缠魂塔 SOUL SPIRE - 眺望塔 (game-ready glTF asset)  v3
Run: blender --background --python lookout_tower.py

原点建模 (塔心 = 原点, Blender Z up). 游戏侧摆到过山车地面灯环圆心:
  app (17.5, 0, -30.5)  =  blender 世界 (17.5, 30.5).
坐标: app = (bx, bz, -by). 方位角一律用 **app 方位** alpha = atan2(z, x):
  东 0° / 南 90° / 西 180° / 北 270°;  blender 局部点 = (r cos a, -r sin a, z).

v3 (2026-11-24 impeccable critique 修复批):
  入口程序整体旋转 ROT=-90° —— 门厅与主招牌朝南 (真实来向: 绕回流沟护栏南端 / 东草坪),
  梯口东南, 栈桥与笼顶门朝北 (出梯正对提升段), 梯顶到达到西南偏南、面向摩天轮; 西侧开间为第二入口.
  碰撞带截到构件顶面以下; 顶门补门槛; 到达口井侧封栏杆; 环廊家具内移成环; 轿厢门加宽;
  首层封闭开间补碰撞. 光线拆档: TW_Rail 细白扶手 / TW_Ribbon 南瓜橙缠带 / TW_Glow 关节灯珠.

布局 (自内向外):
  核心笼 r1.62 (24 根笼柱, 内藏升降梯轿厢)      底门 90° (南) / 顶门 270° (北), 各带滑移层门
  螺旋梯 r1.72-3.36 (242 级 x 4.8 圈)          梯口 58° (东南), 首 4 级半高, 俯视逆时针盘升, 到顶 130°
  南瓜橙缠带 r3.36-3.42 (踏步外缘弦带, 跑满 239 级) / 细白扶手 r3.39
  8 主柱 + 8 副柱桁架 r3.80->3.68               主柱方位 22.5°+45°k; 首层开敞: 22.5-112.5° 与 157.5-202.5°
  观景环廊 r3.38-5.6 @ 40m + 栈桥 (北, 接笼顶门)
  灯室 Ø4.16 @ 42.8-46.0 + 宝顶 + 尖顶 ~50.4m (乌鸦风向标, 可转节点)
节点约定 (运行时驱动):
  TW_Lift      —— 升降梯轿厢根 (local z = 轿底; 游戏改 position.y)
  TW_GateB/T   —— 轿厢两扇滑门 (子节点; 游戏沿 local 切向平移开合)
  TW_LGateB/T  —— 两站层门 (常闭, 轿厢到位时滑开)
  TW_CallLamp_B/T —— 呼梯灯 (独立材质, 游戏改自发光色)
  TW_FlameAnchor —— 灯室鬼火锚点 / TW_CrowPivot —— 乌鸦风向标转轴 (绕竖轴)
输出: lookout_tower.blend / lookout_tower.glb / colliders_tower.json / preview/ (入库预览 12 张)
校验: node scripts/verify_tower_colliders.mjs (碰撞表离线走线/通道/漏点/可达性, 31 项)
"""
import bpy
import bmesh
import json
import math
import random
import time
from math import radians, degrees, pi, cos, sin, atan2, hypot, sqrt
from pathlib import Path
from mathutils import Vector, Matrix, Euler

T0 = time.time()
def tmark(label):
    print(f"[t={time.time()-T0:6.1f}s] {label}", flush=True)

random.seed(11)

# ---------------------------------------------------------------- params ---
OUT = Path(__file__).resolve().parent
PREV = OUT / "preview"

SX, SY = 17.5, 30.5                  # blender 世界落位 (= app 17.5, -30.5)
DECK = 40.0                          # 主平台面
ROT = -90.0                          # 入口程序整体旋转 (v2 朝西 -> v3 朝南)

DOOR_B, DOOR_T, DOOR_HALF = 180.0 + ROT, 0.0 + ROT, 30.0   # 笼门方位 (底/顶) / 半角
LINT_B = 2.55                        # 底门楣高
CAGE_Z0, CAGE_TOP = 0.10, 42.5
LINT_T = CAGE_TOP - 0.20             # 顶门楣高 42.3
CORE_R, CORE_BARS = 1.62, 24         # 核心笼
LGT_R = CORE_R + 0.11                # 层门滑轨半径 (滑开时贴着笼柱外侧走过, 不穿插)

ST_IN, ST_OUT = 1.72, 3.36           # 螺旋梯内外半径
RIB_R0, RIB_R1 = 3.36, 3.42          # 缠带 (踏步外缘弦带, 发光)
ST_RAIL_R, ST_RAIL_H = 3.39, 1.05    # 外扶手 (细白光线)
ST_A0, ST_DIR, ST_TURNS, ST_N = 148.0 + ROT, -1.0, 4.8, 242   # 梯口 58°: 让开 22.5° 主柱石座, 进梯带 >=0.8m
RISE = DECK / ST_N                   # 基准级高 0.1653 (控制器步高 0.35)
N_LOW = 4                            # 梯口首 4 级半高: 地面可一步迈上 4 级, 进梯带 >= 0.8m
LOW = RISE / 2.0
RISE2 = (DECK - N_LOW * LOW) / (ST_N - N_LOW)   # 其余 238 级级高 (0.1666)
DA = ST_DIR * ST_TURNS * 360.0 / ST_N   # 每级方位增量 (度; 负 = app 方位递减)
ST_RAIL_END, ST_POST_END, ST_RIB_END = 231.5, 232, 238   # 扶手/立柱/缠带止于第几级
ARR_GAP = 36.0                       # 到达口: 梯侧让空到 ST_ARR + 36° (出梯带 >=0.7m)
ARR_NEWEL_LO = -6.0                  # 到达口: 井侧望柱在 ST_ARR - 6°

COL_R0, COL_R1 = 3.80, 3.68          # 桁架柱半径 (底 -> 顶)
COL_Z0, COL_Z1 = 0.55, 39.66         # 主柱起止高 (副柱 0.30 起; 柱顶伸进环廊搁栅)
COL_A0, COL_N, COL_LEV = 22.5, 8, 12

DK_IN, DK_OUT, DK_RAIL_H = 3.38, 5.6, 1.15
DK_T = 0.12                          # 环廊楼板厚
BR_GAP = 14.0                        # 内栏杆的栈桥口半角
BR_HALF = 0.625                      # 栈桥半宽
BR_X0, BR_X1 = 1.66, DK_IN + 0.05    # 栈桥板径向范围
SILL_X0, SILL_X1, SILL_HALF = 1.31, 1.72, 0.72   # 顶门门槛板

CAB_R, CAB_H, CAB_FLOOR = 1.30, 2.30, 0.08   # 轿厢
CAB_DOOR_HALF = 30.0                          # 轿厢门半角 (门洞弦长 1.27m)
CAB_ZB = 0.06                                 # 轿底停靠底层 (轿厢地面顶 0.14)
CAB_ZT = DECK - CAB_FLOOR                     # 轿底停靠顶层 (地面顶 40.00)

LAN_Z0, LAN_R, LAN_H = 42.8, 2.08, 3.2

RES = (1600, 900)


def pol(a_deg, r, z=0.0):
    """app 方位 -> blender 局部点"""
    a = radians(a_deg)
    return Vector((r * cos(a), -r * sin(a), z))


def rad_u(a_deg):
    a = radians(a_deg)
    return Vector((cos(a), -sin(a), 0.0))


def tan_u(a_deg):
    """+alpha 方向 (app 方位递增 = 俯视顺时针) 的切向单位向量"""
    a = radians(a_deg)
    return Vector((-sin(a), -cos(a), 0.0))


def ang_diff(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


Z = Vector((0.0, 0.0, 1.0))
X = Vector((1.0, 0.0, 0.0))
Y = Vector((0.0, 1.0, 0.0))


def step_a(k):
    """第 k 级踏步的起始方位 (app 度)"""
    return ST_A0 + DA * k


def step_az(k):
    """第 k 级踏步的中点方位"""
    return ST_A0 + DA * (k + 0.5)


def hf(u):
    """螺旋高度函数 (u = 级序, 可小数; 整数处 = 该级前缘踏面高)"""
    return LOW * u if u <= N_LOW else N_LOW * LOW + (u - N_LOW) * RISE2


def step_h(k):
    """第 k 级踏步面高"""
    return hf(k + 1)


def colR(z):
    return COL_R0 + (COL_R1 - COL_R0) * (z - COL_Z0) / (COL_Z1 - COL_Z0)


ST_ARR = step_a(ST_N) % 360.0         # 到顶方位 = 120.0
U_T, T_T = rad_u(DOOR_T), tan_u(DOOR_T)   # 栈桥径向 / 切向单位向量


def bp(x, y, z):
    """栈桥局部坐标 (x 径向, y 切向) -> blender 局部点"""
    return U_T * x + T_T * y + Z * z


# ------------------------------------------------------------- scene prep ---
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
col_static = bpy.data.collections.new("Static")
col_lift = bpy.data.collections.new("Lift")
col_ref = bpy.data.collections.new("REF (仅参考, 不导出)")
for _c in (col_static, col_lift, col_ref):
    sc.collection.children.link(_c)


# ---------------------------------------------------------------- utils ---
def hex_lin(h, a=1.0):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, a)


def sock(node, ident):
    for s in node.inputs:
        if s.identifier == ident:
            return s
    return None


def make_mat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0, alpha=1.0):
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
    m.use_backface_culling = False                      # glTF doubleSided
    m.diffuse_color = hex_lin(emit if emit else color)  # 实体视图色
    return m


def make_vcol_mat(name, color, rough=0.5, emit=None, strength=0.0):
    """顶点色材质: Base = 颜色 x COLOR_0 (同 park_env PE_Pumpkin 语义), 可选微发光"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "Col"
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
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
    m.use_backface_culling = False
    m.diffuse_color = hex_lin(color)
    return m


HEX = {
    "iron": "#2A2140", "dark": "#14161F", "brass": "#C9A227", "steel": "#4A4458",
    "warm": "#FFE9C4", "orange": "#FFA53B", "lamporange": "#FF8A1E", "violet": "#9B5BFF",
    "spirit": "#8FE3D9", "wood": "#4A3526", "stone": "#3A3F4C",
    "pump": "#C87419", "crow": "#0A0A0C", "stem": "#4A4030",
    "night": "#060913", "ground": "#0B0F14", "green": "#8CFF4A",
}


class Bag:
    """按材质聚合顶点/面, 一次性 bpy.data 直建 (无 ops). face() 自动按期望法线翻面."""

    def __init__(self):
        self.verts = []
        self.faces = []
        self.fsmooth = []
        self.vcol = None       # None 或 每顶点 (r,g,b)
        self.has_vcol = False

    def face(self, pts, want=None, smooth=False):
        pts = [Vector(p) for p in pts]
        n = len(pts)
        nx = ny = nz = 0.0
        for i in range(n):
            p, q = pts[i], pts[(i + 1) % n]
            nx += (p.y - q.y) * (p.z + q.z)
            ny += (p.z - q.z) * (p.x + q.x)
            nz += (p.x - q.x) * (p.y + q.y)
        if nx * nx + ny * ny + nz * nz < 1e-18:
            return
        if want is not None and (nx * want.x + ny * want.y + nz * want.z) < 0:
            pts = pts[::-1]
        b = len(self.verts)
        self.verts += [tuple(p) for p in pts]
        self.faces.append(tuple(b + i for i in range(n)))
        self.fsmooth.append(smooth)

    def box(self, c, ex, ey, ez, sx, sy, sz):
        c = Vector(c)
        hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0

        def P(i, j, k):
            return c + ex * (i * hx) + ey * (j * hy) + ez * (k * hz)
        self.face([P(-1, -1, -1), P(1, -1, -1), P(1, 1, -1), P(-1, 1, -1)], -ez)
        self.face([P(-1, -1, 1), P(1, -1, 1), P(1, 1, 1), P(-1, 1, 1)], ez)
        self.face([P(-1, -1, -1), P(1, -1, -1), P(1, -1, 1), P(-1, -1, 1)], -ey)
        self.face([P(-1, 1, -1), P(1, 1, -1), P(1, 1, 1), P(-1, 1, 1)], ey)
        self.face([P(-1, -1, -1), P(-1, 1, -1), P(-1, 1, 1), P(-1, -1, 1)], -ex)
        self.face([P(1, -1, -1), P(1, 1, -1), P(1, 1, 1), P(1, -1, 1)], ex)

    def obox(self, c, a_deg, s_t, s_r, s_z):
        """方位盒: 切向长 s_t / 径向厚 s_r / 高 s_z"""
        self.box(c, tan_u(a_deg), rad_u(a_deg), Z, s_t, s_r, s_z)

    def beam(self, p1, p2, w, d):
        """两点间盒梁 (侧轴自动取水平)"""
        p1, p2 = Vector(p1), Vector(p2)
        ax = p2 - p1
        L = ax.length
        if L < 1e-6:
            return
        ax = ax / L
        side = ax.cross(Z)
        if side.length < 1e-4:
            side = Vector((1, 0, 0))
        side.normalize()
        up2 = side.cross(ax).normalized()
        self.box((p1 + p2) / 2, side, ax, up2, w, L, d)

    def taper(self, p1, p2, s1, s2):
        """方棱锥柱: 两端截面 (w, d) 不同"""
        p1, p2 = Vector(p1), Vector(p2)
        ax = p2 - p1
        L = ax.length
        ax = ax / L
        side = ax.cross(Z)
        if side.length < 1e-4:
            side = Vector((1, 0, 0))
        side.normalize()
        up2 = side.cross(ax).normalized()
        cor = ((-1, -1), (1, -1), (1, 1), (-1, 1))
        a = [p1 + side * (i * s1[0] / 2) + up2 * (j * s1[1] / 2) for i, j in cor]
        b = [p2 + side * (i * s2[0] / 2) + up2 * (j * s2[1] / 2) for i, j in cor]
        self.face(a[::-1], -ax)
        self.face(b, ax)
        self.face([a[0], a[1], b[1], b[0]], -up2)
        self.face([a[2], a[3], b[3], b[2]], up2)
        self.face([a[3], a[0], b[0], b[3]], -side)
        self.face([a[1], a[2], b[2], b[1]], side)

    def to_mesh(self, name, mat, collection, parent=None, smooth_all=False):
        if not self.faces:
            return None
        vs, fs, sm, vc = [], [], [], []
        remap = {}
        for f, s in zip(self.faces, self.fsmooth):
            pts = [self.verts[i] for i in f]
            nx = ny = nz = 0.0
            for i in range(len(pts)):          # Newell 面积: 丢退化面
                px, py, pz = pts[i]
                qx, qy, qz = pts[(i + 1) % len(pts)]
                nx += (py - qy) * (pz + qz)
                ny += (pz - qz) * (px + qx)
                nz += (px - qx) * (py + qy)
            if nx * nx + ny * ny + nz * nz < 1e-14:
                continue
            nf = []
            for i in f:
                if i not in remap:
                    remap[i] = len(vs)
                    vs.append(self.verts[i])
                    if self.has_vcol:
                        vc.append(self.vcol[i])
                nf.append(remap[i])
            fs.append(tuple(nf))
            sm.append(True if smooth_all else s)
        if not fs:
            return None
        me = bpy.data.meshes.new(name)
        me.from_pydata(vs, [], fs)
        me.validate(verbose=False)
        me.update()
        ob = bpy.data.objects.new(name, me)
        me.materials.append(mat)
        for p, s in zip(me.polygons, sm):
            p.use_smooth = s
        if self.has_vcol:
            flat = []
            for c in vc:
                flat += [c[0], c[1], c[2], 1.0]
            attr = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
            attr.data.foreach_set("color", flat)
            try:
                me.color_attributes.active_color = attr
            except Exception:
                pass
        collection.objects.link(ob)
        if parent is not None:
            ob.parent = parent           # 普通父子 (无逆矩阵): 顶点即节点局部坐标
        return ob

    def bake(self, ob, origin=None, smooth=True):
        """把已有网格对象烘进 bag (世界坐标; origin 非空时转为相对 origin 的局部坐标)"""
        mw = ob.matrix_world
        off = Vector(origin) if origin is not None else Vector((0, 0, 0))
        base = len(self.verts)
        nv = len(ob.data.vertices)
        for v in ob.data.vertices:
            self.verts.append(tuple(mw @ v.co - off))
        colattr = ob.data.color_attributes[0] if len(ob.data.color_attributes) else None
        if colattr is not None and not self.has_vcol:
            self.vcol = [(1.0, 1.0, 1.0)] * base
            self.has_vcol = True
        if colattr is not None:
            buf = [0.0] * (nv * 4)
            colattr.data.foreach_get("color", buf)
            self.vcol += [(buf[i * 4], buf[i * 4 + 1], buf[i * 4 + 2]) for i in range(nv)]
        elif self.has_vcol:
            self.vcol += [(1.0, 1.0, 1.0)] * nv
        for p in ob.data.polygons:
            self.faces.append(tuple(base + i for i in p.vertices))
            self.fsmooth.append(smooth and p.use_smooth)


def tube(bag, pts, r, sides=6, cap=False, radii=None, smooth=True):
    """折线扫掠圆管 (平行输运标架)."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    if n < 2:
        return
    tans = []
    for i in range(n):
        t = pts[min(n - 1, i + 1)] - pts[max(0, i - 1)]
        tans.append(t.normalized() if t.length > 1e-9 else Vector((0, 0, 1)))
    ref = Vector((1, 0, 0)) if abs(tans[0].x) < 0.9 else Vector((0, 1, 0))
    nv = (ref - tans[0] * ref.dot(tans[0])).normalized()
    rings = []
    for i in range(n):
        if i > 0:
            ax = tans[i - 1].cross(tans[i])
            if ax.length > 1e-9:
                nv = Matrix.Rotation(tans[i - 1].angle(tans[i]), 4, ax.normalized()) @ nv
            nv = (nv - tans[i] * nv.dot(tans[i])).normalized()
        bv = tans[i].cross(nv)
        rr = r if radii is None else radii[i]
        rings.append([pts[i] + (nv * cos(2 * pi * k / sides) + bv * sin(2 * pi * k / sides)) * rr
                      for k in range(sides)])
    for i in range(n - 1):
        c = (pts[i] + pts[i + 1]) / 2
        for k in range(sides):
            k2 = (k + 1) % sides
            q = [rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]]
            mid = (q[0] + q[1] + q[2] + q[3]) / 4
            bag.face(q, mid - c, smooth)
    if cap:
        for idx, sgn in ((0, -1), (n - 1, 1)):
            rg = rings[idx]
            for k in range(sides):
                bag.face([rg[k], rg[(k + 1) % sides], pts[idx]], tans[idx] * sgn, smooth)


def ring(a0, a1, r, z, n):
    """方位 a0->a1 (app 度) 的圆弧点列"""
    return [pol(a0 + (a1 - a0) * i / n, r, z) for i in range(n + 1)]


def circle(r, z, n):
    return ring(0.0, 360.0, r, z, n)


def frustum(bag, z0, r0, z1, r1, n=32, a0=0.0, a1=360.0, cap0=False, cap1=False, smooth=False):
    """旋转台 (侧带 + 可选端盖); r1=0 为锥顶. 非整圆时端盖为扇形."""
    full = abs(a1 - a0) >= 359.999
    for i in range(n):
        b0 = a0 + (a1 - a0) * i / n
        b1 = a0 + (a1 - a0) * (i + 1) / n
        want = rad_u(0.5 * (b0 + b1))
        p00, p01 = pol(b0, r0, z0), pol(b1, r0, z0)
        if r1 <= 1e-6:
            bag.face([p00, p01, Vector((0, 0, z1))], want, smooth)
        else:
            p10, p11 = pol(b0, r1, z1), pol(b1, r1, z1)
            bag.face([p00, p01, p11, p10], want, smooth)
    if cap1 and r1 > 1e-6:
        pts = [pol(a0 + (a1 - a0) * i / n, r1, z1) for i in range(n)]
        bag.face(pts if full else [Vector((0, 0, z1))] + pts, Z)
    if cap0 and r0 > 1e-6:
        pts = [pol(a0 + (a1 - a0) * i / n, r0, z0) for i in range(n)]
        bag.face(pts if full else [Vector((0, 0, z0))] + pts, -Z)


def annulus(bag, r0, r1, z0, z1, a0, a1, n, caps=True):
    """环/扇环实体块 (上下面 + 内外面 + 两端径向面)"""
    dz = Vector((0, 0, z1 - z0))
    for i in range(n):
        b0 = a0 + (a1 - a0) * i / n
        b1 = a0 + (a1 - a0) * (i + 1) / n
        am = 0.5 * (b0 + b1)
        p00, p10, p11, p01 = pol(b0, r0, z0), pol(b0, r1, z0), pol(b1, r1, z0), pol(b1, r0, z0)
        bag.face([p00, p10, p11, p01], -Z)
        bag.face([p00 + dz, p10 + dz, p11 + dz, p01 + dz], Z)
        bag.face([p10, p11, p11 + dz, p10 + dz], rad_u(am))
        bag.face([p00, p01, p01 + dz, p00 + dz], -rad_u(am))
    if caps:
        for a, sgn in ((a0, -1.0), (a1, 1.0)):
            p0, p1 = pol(a, r0, z0), pol(a, r1, z0)
            bag.face([p0, p1, p1 + dz, p0 + dz], tan_u(a) * sgn)


def slab(bag, poly2d, origin, u, v, w, t):
    """薄板: 多边形在 (u,v) 平面, 沿 w 厚 t"""
    o = Vector(origin)
    f = [o + u * x + v * y + w * (t / 2) for x, y in poly2d]
    b = [o + u * x + v * y - w * (t / 2) for x, y in poly2d]
    cx = sum(p[0] for p in poly2d) / len(poly2d)
    cy = sum(p[1] for p in poly2d) / len(poly2d)
    cen = o + u * cx + v * cy
    bag.face(f, w)
    bag.face(b, -w)
    n = len(poly2d)
    for i in range(n):
        j = (i + 1) % n
        bag.face([b[i], b[j], f[j], f[i]], (f[i] + f[j]) / 2 - cen)


def flag(bag, top_l, top_r, tip, normal):
    """双面三角旗"""
    bag.face([top_l, top_r, tip], normal)
    bag.face([top_l, top_r, tip], -normal)


def dot(bag, c, r):
    """八面体小灯珠"""
    c = Vector(c)
    q = [c + Vector((r, 0, 0)), c + Vector((-r, 0, 0)), c + Vector((0, r, 0)),
         c + Vector((0, -r, 0)), c + Vector((0, 0, r)), c + Vector((0, 0, -r))]
    for (i, j) in ((0, 2), (2, 1), (1, 3), (3, 0)):
        bag.face([q[i], q[j], q[4]], (q[i] + q[j]) / 2 - c)
        bag.face([q[j], q[i], q[5]], (q[i] + q[j]) / 2 - c)


def sphere(bag, c, r, seg=14, ring_n=8, lobes=0, amp=0.0):
    c = Vector(c)
    rows = []
    for j in range(ring_n + 1):
        phi = pi * j / ring_n
        sp, cp = sin(phi), cos(phi)
        row = []
        for i in range(seg):
            th = 2 * pi * i / seg
            lobe = 1 + amp * cos(lobes * th) * (sp ** 0.6) if lobes else 1.0
            row.append(c + Vector((r * sp * cos(th) * lobe, r * sp * sin(th) * lobe, r * cp)))
        rows.append(row)
    for j in range(ring_n):
        for i in range(seg):
            i2 = (i + 1) % seg
            if j == 0:
                q = [rows[0][0], rows[1][i2], rows[1][i]]
            elif j == ring_n - 1:
                q = [rows[ring_n][0], rows[ring_n - 1][i], rows[ring_n - 1][i2]]
            else:
                q = [rows[j][i], rows[j][i2], rows[j + 1][i2], rows[j + 1][i]]
            bag.face(q, sum(q, Vector()) / len(q) - c, True)


# ------------------------------------------------------------ materials ---
M = {
    "iron":      make_mat("TW_Iron", HEX["iron"], rough=0.55, metal=0.8),
    "steel":     make_mat("TW_Steel", HEX["steel"], rough=0.5, metal=0.6),
    "dark":      make_mat("TW_IronDark", HEX["dark"], rough=0.5, metal=0.8),
    "brass":     make_mat("TW_Brass", HEX["brass"], rough=0.35, metal=0.9,
                          emit=HEX["brass"], strength=0.2),
    "glow":      make_mat("TW_Glow", HEX["warm"], rough=0.5, emit=HEX["warm"], strength=2.6),
    "rail":      make_mat("TW_Rail", HEX["warm"], rough=0.5, emit=HEX["warm"], strength=1.0),
    "ribbon":    make_mat("TW_Ribbon", HEX["orange"], rough=0.6, emit=HEX["orange"], strength=1.6),
    "stepglow":  make_mat("TW_StepGlow", HEX["warm"], rough=0.5, emit="#FFC070", strength=1.1),
    "floorglow": make_mat("TW_FloorGlow", HEX["warm"], rough=0.5, emit="#FFC070", strength=0.7),
    "webglow":   make_mat("TW_WebGlow", HEX["warm"], rough=0.6, emit=HEX["warm"], strength=0.35),
    "glass":     make_mat("TW_Glass", "#FFD9A0", rough=0.3, emit="#FFB060", strength=0.9, alpha=0.30),
    "cabglass":  make_mat("TW_CabGlass", "#FFD9A0", rough=0.3, emit="#FFB060", strength=0.6, alpha=0.38),
    "lamp":      make_mat("TW_LampCore", HEX["lamporange"], rough=0.5, emit=HEX["lamporange"], strength=2.2),
    "spirit":    make_mat("TW_Spirit", HEX["spirit"], rough=0.5, emit=HEX["spirit"], strength=2.4),
    "wood":      make_mat("TW_Wood", HEX["wood"], rough=0.85),
    "woodlit":   make_mat("TW_WoodLit", HEX["wood"], rough=0.8, emit="#FFC070", strength=0.22),
    "stone":     make_mat("TW_Stone", HEX["stone"], rough=0.9),
    "sign":      make_mat("TW_Sign", HEX["violet"], rough=0.6, emit=HEX["violet"], strength=0.5),
    "flag":      make_mat("TW_FlagOrange", HEX["orange"], rough=0.7, emit=HEX["orange"], strength=0.35),
    "crow":      make_mat("TW_Crow", HEX["crow"], rough=0.8),
    "pglow":     make_mat("TW_PumpGlow", "#2A1608", rough=0.8, emit="#FFC46B", strength=2.5),
    "sglow":     make_mat("TW_SignGlow", HEX["orange"], rough=0.5, emit=HEX["orange"], strength=1.3),
    "subglow":   make_mat("TW_SubGlow", HEX["orange"], rough=0.5, emit=HEX["orange"], strength=1.0),
}
M["pump"] = make_vcol_mat("TW_Pumpkin", HEX["pump"], rough=0.42, emit="#FF8A1E", strength=0.35)   # 40m 高处没有环境光, 瓜身自带微光
CALL_B = make_mat("TW_CallLamp_B", "#302020", rough=0.5, emit="#C43B3B", strength=3.0)
CALL_T = make_mat("TW_CallLamp_T", "#302020", rough=0.5, emit="#C43B3B", strength=3.0)

KEYS = ["iron", "steel", "dark", "brass", "glow", "rail", "ribbon", "stepglow", "floorglow",
        "webglow", "glass", "lamp", "spirit", "wood", "woodlit", "stone", "sign", "flag",
        "crow", "pump", "pglow", "sglow", "subglow"]
B = {k: Bag() for k in KEYS}
tmark("prep")

# =========================== 塔基石座 + 8 主柱 8 副柱桁架 ===========================
verts16 = []
for k in range(COL_N):
    verts16.append((COL_A0 + 45.0 * k, False))
    verts16.append((45.0 * k, True))
verts16.sort(key=lambda t: t[0] % 360.0)          # 0°,22.5°,... (副/主交替)
LEVELS = [COL_Z0 + (COL_Z1 - COL_Z0) * i / COL_LEV for i in range(COL_LEV + 1)]
OPEN_ZONES = ((22.5, 67.5), (67.5, 112.5), (157.5, 202.5))   # 首层开敞: 梯口 / 门厅 / 西侧第二入口
OPEN_MINOR = {45.0: LEVELS[1], 90.0: 5.45, 180.0: 5.45}      # 无石座、抬高起柱的副柱 (给入口让空)


def bay_open(a0, a1):
    m = 0.5 * (a0 + a1)
    return any(lo - 1e-6 <= m <= hi + 1e-6 for lo, hi in OPEN_ZONES)


def bay_angles(j):
    a1 = verts16[j][0]
    return a1, verts16[(j + 1) % 16][0] + (360.0 if j == 15 else 0.0)


FOOT = []                                        # 有石座的柱 (a, minor, 边长, 高)
for (a, minor) in verts16:
    u, t = rad_u(a), tan_u(a)
    s, h = (0.50, 0.30) if minor else (0.70, 0.55)
    z_start = h
    if minor and a in OPEN_MINOR:
        z_start = OPEN_MINOR[a]                  # 入口正中: 不设石座, 招牌梁以上才起柱
    else:
        c0 = pol(a, colR(h), 0.0)                # 石座方位对齐 (径向方, 角点不出灯环)
        B["stone"].box(c0 + Z * (h / 2), u, t, Z, s, s, h)
        B["stone"].box(c0 + Z * (h + 0.03), u, t, Z, s + 0.04, s + 0.04, 0.06)
        FOOT.append((a, minor, s + 0.04, h + 0.06))
    w0 = 0.12 if minor else 0.26
    for i in range(COL_LEV):
        za, zb = max(LEVELS[i], z_start), LEVELS[i + 1]
        if zb - za < 1e-6:
            continue
        f1 = (zb - COL_Z0) / (COL_Z1 - COL_Z0)
        B["iron"].taper(pol(a, colR(za), za), pol(a, colR(zb), zb),
                        (w0, w0), (w0 * (1.0 - 0.2 * f1),) * 2)

L0_CLOSED = [bay_angles(j) for j in range(16) if not bay_open(*bay_angles(j))]
for i in range(COL_LEV + 1):
    z = LEVELS[i]
    for j in range(16):
        a1, a2 = bay_angles(j)
        if i == 0 and bay_open(a1, a2):
            continue                              # 首层: 梯口/门厅/第二入口开敞 (不设环梁与斜撑)
        p1, p2 = pol(a1, colR(z), z), pol(a2, colR(z), z)
        B["iron"].beam(p1, p2, 0.10, 0.16)        # 环梁
        if i < COL_LEV:
            z2 = LEVELS[i + 1]
            if (i + j) % 2 == 0:
                d1, d2 = p1, pol(a2, colR(z2), z2)
            else:
                d1, d2 = p2, pol(a1, colR(z2), z2)
            B["iron"].beam(d1, d2, 0.05, 0.05)    # 交替斜撑

for i in range(1, COL_LEV + 1):                   # 关节灯: 夜里把桁架读成点阵笼
    z = LEVELS[i]
    for (a, minor) in verts16:
        if a in OPEN_MINOR and z < OPEN_MINOR[a] - 1e-6:
            continue
        dot(B["glow"], pol(a, colR(z) + 0.13, z), 0.075)
tmark("lattice")

# ================================ 核心笼 (升降梯井) ================================
for j in range(CORE_BARS):
    a = 360.0 * j / CORE_BARS
    heavy = (j % 4 == 0)
    in_b = abs(ang_diff(a, DOOR_B)) < DOOR_HALF - 1e-6
    in_t = abs(ang_diff(a, DOOR_T)) < DOOR_HALF - 1e-6
    jamb = (min(abs(ang_diff(a, DOOR_B)), abs(ang_diff(a, DOOR_T))) < DOOR_HALF + 1e-6) \
        and not (in_b or in_t)
    rr = 0.08 if jamb else (0.065 if heavy else 0.04)
    segs = [(LINT_B, CAGE_TOP)] if in_b else \
        ([(CAGE_Z0, DECK - 0.05)] if in_t else [(CAGE_Z0, CAGE_TOP)])
    for za, zb in segs:
        tube(B["iron"], [pol(a, CORE_R, za), pol(a, CORE_R, zb)], rr, sides=6, cap=True)

for m in range(16):
    z = 2.9 + 2.6 * m
    if DECK < z < CAGE_TOP - 0.2:                 # 顶层门带内: 断环让出门洞
        tube(B["iron"], ring(DOOR_T + DOOR_HALF, DOOR_T + 360.0 - DOOR_HALF, CORE_R, z, 48), 0.032, sides=5)
    else:
        tube(B["iron"], circle(CORE_R, z, 64), 0.032, sides=5)

for (ad, za, zb) in ((DOOR_B, CAGE_Z0, LINT_B), (DOOR_T, DECK - 0.02, LINT_T)):
    tube(B["brass"], ring(ad - DOOR_HALF, ad + DOOR_HALF, CORE_R, zb, 24), 0.05, sides=6, cap=True)
    for sgn in (-1, 1):
        tube(B["brass"], [pol(ad + sgn * DOOR_HALF, CORE_R + 0.03, za),
                          pol(ad + sgn * DOOR_HALF, CORE_R + 0.03, zb)], 0.04, sides=6)
frustum(B["iron"], LINT_T, CORE_R, CAGE_TOP, CORE_R, n=12,
        a0=DOOR_T - DOOR_HALF, a1=DOOR_T + DOOR_HALF)          # 顶门楣以上补壁
for a in (45.0, 135.0, 225.0, 315.0):                          # 导轨
    B["dark"].beam(pol(a, 1.44, CAGE_Z0), pol(a, 1.44, CAGE_TOP - 0.10), 0.08, 0.08)
CALLB, CALLT = Bag(), Bag()
for ad, zb, bagc in ((DOOR_B, LINT_B, CALLB), (DOOR_T, LINT_T, CALLT)):
    bagc.obox(pol(ad, CORE_R + 0.15, zb + 0.30), ad, 0.28, 0.16, 0.18)
    B["brass"].obox(pol(ad, CORE_R + 0.15, zb + 0.20), ad, 0.34, 0.20, 0.03)   # 灯座
    B["brass"].obox(pol(ad, CORE_R + 0.17, zb + 0.41), ad, 0.38, 0.24, 0.03)   # 灯帽
tmark("cage")

# ================================ 滑门扇 (轿厢门 / 站层门共用造型) ================================
def gate_bags(ad, rr, half, hgt, nbar=6):
    """滑门扇: 顶点相对门扇闭合位中心 (节点原点), 绕塔弧 2*half, 高 hgt"""
    g = {k: Bag() for k in ("brass", "iron")}
    for z in (0.06, hgt - 0.06):
        tube(g["brass"], ring(ad - half, ad + half, rr, z, 10), 0.03, sides=6, cap=True)
    for a in (ad - half, ad + half):
        tube(g["brass"], [pol(a, rr, 0.06), pol(a, rr, hgt - 0.06)], 0.03, sides=6, cap=True)
    for i in range(1, nbar + 1):
        a = ad - half + 2 * half * i / (nbar + 1)
        tube(g["iron"], [pol(a, rr, 0.09), pol(a, rr, hgt - 0.09)], 0.013, sides=4)
    tube(g["brass"], ring(ad - half, ad + half, rr, hgt * 0.45, 10), 0.018, sides=5)
    return g


CR = CAB_R - 0.03
CGT_R = CR - 0.07                     # 轿厢滑门半径 (滑开时在玻璃板与立梃内侧走过)
lift_root = bpy.data.objects.new("TW_Lift", None)
lift_root.empty_display_size = 1.5
lift_root.location = (0.0, 0.0, CAB_ZB)
col_lift.objects.link(lift_root)

# ================================ 升降梯轿厢 (节点 TW_Lift) ================================
CB = {k: Bag() for k in ("iron", "brass", "cabglass", "lamp")}
frustum(CB["iron"], 0.0, CAB_R, CAB_FLOOR, CAB_R, n=32, cap0=True, cap1=True)            # 轿底
frustum(CB["iron"], CAB_H - 0.07, CAB_R, CAB_H, CAB_R, n=32, cap0=True, cap1=True)       # 轿顶
frustum(CB["lamp"], CAB_H - 0.09, 0.36, CAB_H - 0.07, 0.36, n=16, cap0=True)             # 顶灯 (朝下)
CAB_POSTS = sorted({(d + o) % 360.0 for d in (DOOR_B, DOOR_T) for o in (-90.0, -30.0, 30.0, 90.0)})
CAB_BAYS = [(CAB_POSTS[i], CAB_POSTS[(i + 1) % len(CAB_POSTS)] + (360.0 if i == len(CAB_POSTS) - 1 else 0.0))
            for i in range(len(CAB_POSTS))]                # 相邻立梃之间的 6 个隔间 (含 2 个门洞)
for a in CAB_POSTS:                                                                     # 6 立梃
    tube(CB["brass"], [pol(a, CR, CAB_FLOOR), pol(a, CR, CAB_H - 0.07)], 0.04, sides=6)
for z, rr in ((CAB_FLOOR + 0.05, 0.035), (CAB_H - 0.13, 0.035)):                          # 底圈/顶圈
    tube(CB["brass"], circle(CR, z, 48), rr, sides=6)
tube(CB["brass"], circle(CR, 1.05, 48), 0.028, sides=6)                                 # 玻璃上槛
tube(CB["brass"], circle(CAB_R - 0.14, 1.00, 48), 0.022, sides=6)                        # 轿内扶手圈
for (a1, a2) in CAB_BAYS:
    ac = 0.5 * (a1 + a2)
    if abs(ang_diff(ac, DOOR_B)) < 1.0 or abs(ang_diff(ac, DOOR_T)) < 1.0:
        continue                                                                       # 门洞
    R = CAB_R - 0.02
    nseg = 8
    for q in range(nseg):                                                              # 下半暖光玻璃
        b0 = ac - 26.0 + 52.0 * q / nseg
        b1 = ac - 26.0 + 52.0 * (q + 1) / nseg
        CB["cabglass"].face([pol(b0, R, 0.16), pol(b1, R, 0.16), pol(b1, R, 1.05), pol(b0, R, 1.05)],
                            rad_u(0.5 * (b0 + b1)))
    for q in range(1, 6):                                                              # 上半黄铜细条 (视野打开)
        a = a1 + (a2 - a1) * q / 6
        tube(CB["brass"], [pol(a, CR, 1.07), pol(a, CR, CAB_H - 0.13)], 0.012, sides=4)

GATES = {}
for gname, gad in (("B", DOOR_B), ("T", DOOR_T)):
    ge = bpy.data.objects.new(f"TW_Gate{gname}", None)
    ge.empty_display_size = 0.4
    ge.parent = lift_root
    ge.location = pol(gad, CGT_R, 0.0)
    col_lift.objects.link(ge)
    GATES[gname] = (ge, gate_bags(gad, CGT_R, CAB_DOOR_HALF - 3.0, CAB_H))

# ================================ 站层门 (节点 TW_LGateB/T, 常闭) ================================
LGATES = {}
for gname, gad, zb, hgt in (("B", DOOR_B, 0.12, LINT_B - 0.17), ("T", DOOR_T, DECK - 0.02, LINT_T - DECK)):
    ge = bpy.data.objects.new(f"TW_LGate{gname}", None)
    ge.empty_display_size = 0.4
    ge.location = pol(gad, LGT_R, zb)
    col_static.objects.link(ge)
    LGATES[gname] = (ge, gate_bags(gad, LGT_R, DOOR_HALF - 3.0, hgt))
tmark("cab")

# ================================ 螺旋梯 ================================
R_MID = (ST_IN + ST_OUT) / 2
for k in range(ST_N):
    a0, a1 = step_a(k), step_a(k + 1)         # a0 = 背侧 (朝上一级), a1 = 前缘
    z = step_h(k)
    annulus(B["steel"], ST_IN, ST_OUT, z - 0.06, z, a0, a1, 3)                # 踏板
    rz0 = 0.0 if z < 1.9 else z - RISE                                       # 低段踢面落地成实体
    B["steel"].box(pol(a0, R_MID, (rz0 + z) / 2), rad_u(a0), tan_u(a0), Z,
                   ST_OUT - ST_IN, 0.03, z - rz0)
    B["stepglow"].box(pol(a1, R_MID, z + 0.006), rad_u(a1), tan_u(a1), Z,
                      ST_OUT - ST_IN - 0.10, 0.035, 0.012)                   # 踏前缘夜光条
    if k <= ST_RIB_END:                                                      # 南瓜橙缠带 (外缘弦带)
        annulus(B["ribbon"], RIB_R0, RIB_R1, max(z - 0.36, 0.0), z - 0.06, a0, a1, 3)
    am = step_az(k)
    if k % 2 == 0 and 4 <= k <= ST_POST_END:                                 # 外栏杆立柱 (首 4 级留作梯口)
        B["iron"].box(pol(am, ST_RAIL_R, z + ST_RAIL_H / 2), rad_u(am), tan_u(am), Z,
                      0.03, 0.03, ST_RAIL_H)
    if k % 2 == 0 and k <= ST_N - 6:                                         # 内栏杆立柱 (立在踏步内缘)
        B["iron"].box(pol(am, ST_IN + 0.05, z + 0.475), rad_u(am), tan_u(am), Z,
                      0.03, 0.03, 0.95)


def helix_pts(r, dz, u0, u1, du):
    """沿梯的螺旋点列: u = 级序 (可小数), 高度 = 平滑螺旋"""
    out = []
    n = max(1, int(round((u1 - u0) / du)))
    for i in range(n + 1):
        u = u0 + (u1 - u0) * i / n
        out.append(pol(ST_A0 + DA * u, r, hf(u) + dz))
    return out


tube(B["rail"], helix_pts(ST_RAIL_R, 1.02, 0.0, float(ST_RAIL_END), 0.5), 0.022, sides=6, cap=True)
tube(B["dark"], helix_pts(ST_RAIL_R, 0.985, 0.0, float(ST_RAIL_END), 0.5), 0.014, sides=5, cap=True)
tube(B["rail"], helix_pts(ST_IN + 0.05, 0.95, 0.0, float(ST_N - 6), 0.5), 0.018, sides=5, cap=True)
for u, zb, hh in ((0.0, 0.0, 1.30), (float(ST_RAIL_END), step_h(int(ST_RAIL_END)), 1.10)):   # 起止望柱
    p0 = pol(ST_A0 + DA * u, ST_RAIL_R, zb)
    p1 = pol(ST_A0 + DA * u, ST_RAIL_R, zb + hh)
    B["iron"].beam(p0, p1, 0.07, 0.07)
    tube(B["brass"], [p1, p1 + Z * 0.09], 0.055, sides=8, cap=True, radii=[0.055, 0.02])
# 梯顶尽头护栏 (径向): 末级前缘之外是 8.3m 深的梯井, 必须封住; 出梯只走梯侧 (内栏杆缺口)
GE_Z = step_h(ST_N - 1)
GUARD_R = (1.88, 2.38, 2.88, 3.33)
for r in GUARD_R:
    p = pol(ST_ARR, r, GE_Z)
    B["iron"].beam(p, p + Z * 1.05, 0.04, 0.04)
tube(B["rail"], [pol(ST_ARR, 1.76, GE_Z + 1.05), pol(ST_ARR, 3.38, GE_Z + 1.05)], 0.022, sides=6, cap=True)
B["dark"].beam(pol(ST_ARR, 1.76, GE_Z + 0.55), pol(ST_ARR, 3.38, GE_Z + 0.55), 0.02, 0.02)
tmark("stair")

# ================================ 观景环廊 @40m ================================
DK_RO = DK_OUT - 0.025
for i in range(48):                                              # 48 块扇形木地板 (留缝)
    annulus(B["wood"], DK_IN, DK_OUT, DECK - DK_T, DECK,
            360.0 * i / 48 + 0.10, 360.0 * (i + 1) / 48 - 0.10, 4)
for j in range(64):                                              # 外圈梁 / 内圈梁 (让开梯顶构件)
    b0, b1 = 360.0 * j / 64, 360.0 * (j + 1) / 64
    B["dark"].beam(pol(b0, DK_OUT - 0.08, DECK - 0.30), pol(b1, DK_OUT - 0.08, DECK - 0.30), 0.10, 0.30)
    B["dark"].beam(pol(b0, 3.62, DECK - 0.28), pol(b1, 3.62, DECK - 0.28), 0.10, 0.26)
for j in range(32):                                              # 径向搁栅 (压住柱顶)
    a = 360.0 * j / 32
    B["dark"].beam(pol(a, 3.60, DECK - 0.28), pol(a, DK_OUT - 0.06, DECK - 0.28), 0.08, 0.20)

annulus(B["floorglow"], DK_OUT - 0.05, DK_OUT, DECK, DECK + 0.12, 0, 360, 96)      # 踢脚环 (脚边边缘标记)
annulus(B["floorglow"], 3.54, 3.58, DECK, DECK + 0.006, 0, 360, 120, caps=False)   # 地面光带 x2
annulus(B["floorglow"], 5.26, 5.30, DECK, DECK + 0.006, 0, 360, 120, caps=False)
for j in range(40):                                              # 外栏杆立柱
    a = 9.0 * j
    B["iron"].box(pol(a, DK_RO, DECK + 0.57), rad_u(a), tan_u(a), Z, 0.04, 0.04, 1.14)
tube(B["rail"], circle(DK_RO, DECK + 1.17, 160), 0.022, sides=6)
tube(B["dark"], circle(DK_RO, DECK + 0.60, 128), 0.020, sides=5)

ARR_LO, ARR_HI = ST_ARR + ARR_NEWEL_LO, ST_ARR + ARR_GAP        # 到达口: 114° .. 144°


def inner_gap(a):
    return (ARR_LO < a < ARR_HI) or (abs(ang_diff(a, DOOR_T)) < BR_GAP)


for j in range(60):                                              # 内栏杆立柱 (留到达口 / 栈桥口)
    a = 6.0 * j
    if inner_gap(a):
        continue
    B["iron"].box(pol(a, DK_IN + 0.03, DECK + 0.57), rad_u(a), tan_u(a), Z, 0.035, 0.035, 1.14)
for (g0, g1) in ((ARR_HI, DOOR_T - BR_GAP), (DOOR_T + BR_GAP, ARR_LO + 360.0)):
    tube(B["rail"], ring(g0, g1, DK_IN + 0.03, DECK + 1.17, max(24, int((g1 - g0) * 0.5))), 0.020, sides=6, cap=True)
    tube(B["dark"], ring(g0, g1, DK_IN + 0.03, DECK + 0.60, max(24, int((g1 - g0) * 0.5))), 0.016, sides=5, cap=True)
NEWELS = (ARR_LO, ARR_HI, DOOR_T - BR_GAP, DOOR_T + BR_GAP)      # 缺口望柱 (带碰撞)
for a in NEWELS:
    p0 = pol(a, DK_IN + 0.03, DECK)
    p1 = pol(a, DK_IN + 0.03, DECK + 1.20)
    B["iron"].beam(p0, p1, 0.07, 0.07)
    tube(B["brass"], [p1, p1 + Z * 0.09], 0.055, sides=8, cap=True, radii=[0.055, 0.02])

for j in range(40):                                              # 幡旗挂中横杆, 让出 0.6-1.17m 视线带
    a = 9.0 * j + 4.5
    zt = DECK + 0.58
    flag(B["sign" if j % 2 == 0 else "flag"],
         pol(a - 2.7, DK_OUT - 0.03, zt), pol(a + 2.7, DK_OUT - 0.03, zt),
         pol(a, DK_OUT - 0.03, zt - 0.36), rad_u(a))

# ================================ 栈桥 (DOOR_T 侧, 接笼顶门) + 门槛 ================================
xc, xl = (BR_X0 + BR_X1) / 2, BR_X1 - BR_X0
B["wood"].box(bp(xc, 0, DECK - 0.05), U_T, T_T, Z, xl, BR_HALF * 2 - 0.10, 0.10)
B["dark"].box(bp(xc, 0, DECK - 0.23), U_T, T_T, Z, xl, BR_HALF * 2, 0.26)
B["iron"].box(bp((SILL_X0 + SILL_X1) / 2, 0, DECK - 0.06), U_T, T_T, Z,
              SILL_X1 - SILL_X0, SILL_HALF * 2, 0.12)            # 顶门门槛板 (补 40m 高的缺口)
for sgn in (-1, 1):
    yy = sgn * BR_HALF
    B["floorglow"].box(bp(xc, sgn * (BR_HALF - 0.11), DECK + 0.003), U_T, T_T, Z, xl - 0.12, 0.04, 0.006)
    for x in (1.85, 2.35, 2.85, 3.30):
        B["iron"].box(bp(x, yy, DECK + 0.57), U_T, T_T, Z, 0.035, 0.035, 1.14)
    tube(B["rail"], [bp(BR_X0 + 0.06, yy, DECK + 1.17), bp(BR_X1 + 0.02, yy, DECK + 1.17)],
         0.022, sides=6, cap=True)
    tube(B["dark"], [bp(BR_X0 + 0.06, yy, DECK + 0.60), bp(BR_X1 + 0.02, yy, DECK + 0.60)],
         0.018, sides=5, cap=True)

# ================================ 檐下托架 + 蛛网纹 ===============================
def web_bracket(a):
    A, Bp, Cs, Ch = (Vector((colR(36.3), 36.3)), Vector((colR(39.4), 39.4)),
                     Vector((DK_OUT - 0.04, DECK - 0.34)), Vector((DK_OUT - 0.02, DECK - 0.42)))
    P = lambda q: pol(a, q.x, q.y)
    B["iron"].beam(P(A), P(Cs), 0.09, 0.09)                      # 斜撑 (外端伸进外圈梁)
    B["iron"].beam(P(Bp), P(Ch), 0.07, 0.07)
    e = Cs - A
    for th in (20.0, 45.0, 70.0):                                # 放射丝
        d = Vector((sin(radians(th)), -cos(radians(th))))
        den = -d.x * e.y + e.x * d.y
        s = (-(A.x - Bp.x) * e.y + e.x * (A.y - Bp.y)) / den
        tube(B["webglow"], [P(Bp), P(Bp + d * s)], 0.014, sides=4)
    for dd in (0.7, 1.4, 2.1):                                   # 环丝
        pts = []
        for th in range(0, 91, 6):
            q = Bp + dd * Vector((sin(radians(th)), -cos(radians(th))))
            if e.x * (q.y - A.y) - e.y * (q.x - A.x) <= 1e-9:
                if len(pts) >= 2:
                    tube(B["webglow"], [P(p) for p in pts], 0.014, sides=4)
                pts = []
            else:
                pts.append(q)
        if len(pts) >= 2:
            tube(B["webglow"], [P(p) for p in pts], 0.014, sides=4)


for (a, minor) in verts16:
    web_bracket(a)
tmark("deck")

# ================================ 灯室 + 宝顶 + 尖顶 ===============================
frustum(B["dark"], CAGE_TOP, CORE_R + 0.33, CAGE_TOP + 0.30, CORE_R + 0.33, n=48, cap0=True, cap1=True)
tube(B["brass"], circle(CORE_R + 0.33, CAGE_TOP + 0.04, 64), 0.03, sides=6)
for k in range(8):                                               # 黄铜斜撑
    a = 45.0 * k + 22.5
    B["brass"].beam(pol(a, CORE_R, CAGE_TOP - 1.0), pol(a, CORE_R + 0.33, CAGE_TOP + 0.04), 0.05, 0.05)
frustum(B["dark"], LAN_Z0, LAN_R + 0.04, LAN_Z0 + 0.06, LAN_R + 0.04, n=32, cap0=True, cap1=True)
frustum(B["glass"], LAN_Z0, LAN_R, LAN_Z0 + LAN_H, LAN_R, n=32)
for k in range(8):
    a = 45.0 * k
    tube(B["brass"], [pol(a, LAN_R, LAN_Z0 - 0.02), pol(a, LAN_R, LAN_Z0 + LAN_H + 0.14)], 0.05, sides=6, cap=True)
tube(B["brass"], circle(LAN_R, LAN_Z0 + 1.25, 64), 0.03, sides=6)
frustum(B["brass"], LAN_Z0 + LAN_H, LAN_R + 0.07, LAN_Z0 + LAN_H + 0.14, LAN_R + 0.07, n=48,
        cap0=True, cap1=True)
LZ1 = LAN_Z0 + LAN_H                                             # 46.0
LAMP_Z = LAN_Z0 + 1.42
ORB_Z = LAN_Z0 + 2.25
sphere(B["lamp"], (0, 0, LAMP_Z), 0.62, seg=24, ring_n=12, lobes=8, amp=0.06)      # 南瓜形灯芯 (饱和橙)
sphere(B["spirit"], (0, 0, ORB_Z), 0.30, seg=12, ring_n=7)                          # 灵火珠 (自灯芯顶升起)
tube(B["dark"], [(0, 0, LZ1 + 0.10), (0, 0, ORB_Z + 0.05)], 0.035, sides=6, cap=True)
roof = [(LAN_R + 0.70, LZ1), (LAN_R + 0.40, LZ1 + 0.55), (1.70, LZ1 + 1.45),
        (0.90, LZ1 + 2.15), (0.14, LZ1 + 2.65)]
annulus(B["dark"], LAN_R + 0.02, LAN_R + 0.70, LZ1 - 0.04, LZ1, 0, 360, 48)
for (r0, z0), (r1, z1) in zip(roof, roof[1:]):
    frustum(B["dark"], z0, r0, z1, r1, n=48)
tube(B["rail"], circle(LAN_R + 0.70, LZ1 + 0.03, 112), 0.020, sides=6)
SP0 = LZ1 + 2.65                                                 # 48.65
tube(B["iron"], [(0, 0, SP0), (0, 0, 49.65)], 0.07, sides=8, cap=True, radii=[0.07, 0.02])
sphere(B["brass"], (0, 0, 49.72), 0.12, seg=10, ring_n=6)
CROW_Z = 49.98
tube(B["brass"], [(0, 0, 49.80), (0, 0, CROW_Z + 0.02)], 0.03, sides=6, cap=True)       # 球顶到横杆的销
tube(B["brass"], [(-0.45, 0, CROW_Z), (0.45, 0, CROW_Z)], 0.018, sides=5, cap=True)
tube(B["brass"], [(0, -0.45, CROW_Z), (0, 0.45, CROW_Z)], 0.018, sides=5, cap=True)
CROW = [(0.62, 0.30), (0.44, 0.32), (0.42, 0.42), (0.28, 0.42), (0.05, 0.36), (-0.20, 0.26),
        (-0.55, 0.12), (-0.78, 0.00), (-0.70, -0.05), (-0.62, -0.03), (-0.54, -0.09),
        (-0.48, -0.06), (-0.44, -0.12), (-0.20, 0.00), (0.02, -0.05), (0.03, -0.16),
        (0.10, -0.16), (0.09, -0.05), (0.16, -0.07), (0.17, -0.16), (0.24, -0.16),
        (0.22, -0.04), (0.34, 0.04), (0.42, 0.16), (0.58, 0.24)]
CROWB = Bag()                                                    # 乌鸦: 相对转轴原点 (可转节点)
slab(CROWB, CROW, (0, 0, 0), X, Z, Y, 0.06)
for sgn in (-1, 1):
    sphere(CROWB, (0.385, sgn * 0.034, 0.355), 0.045, seg=8, ring_n=5)
crow_pivot = bpy.data.objects.new("TW_CrowPivot", None)
crow_pivot.empty_display_size = 0.6
crow_pivot.location = (0.0, 0.0, CROW_Z)
col_static.objects.link(crow_pivot)
flame_anchor = bpy.data.objects.new("TW_FlameAnchor", None)
flame_anchor.empty_display_size = 0.5
flame_anchor.location = (0.0, 0.0, LAN_Z0 + 2.05)
col_static.objects.link(flame_anchor)
tmark("lantern")

# ================================ 门厅铺面 ===============================
AP_X0, AP_X1, AP_HALF, APH = 1.31, 4.70, 1.05, 0.10
for a in (DOOR_B, 180.0):                                        # 门厅 (南) / 第二入口 (西)
    B["stone"].box(pol(a, (AP_X0 + AP_X1) / 2, APH / 2), tan_u(a), rad_u(a), Z,
                   AP_HALF * 2, AP_X1 - AP_X0, APH)
    for sgn in (-1, 1):                                          # 铺面两侧夜光条
        B["stepglow"].box(pol(a, (AP_X0 + AP_X1) / 2, APH + 0.004) + tan_u(a) * (sgn * (AP_HALF - 0.09)),
                          tan_u(a), rad_u(a), Z, 0.06, AP_X1 - AP_X0 - 0.5, 0.008)

# ================================ 长椅 x2 (贴内栏杆, 带靠背) ===============================
BENCH = []
for a in (0.0, 90.0):                                                   # 东西向轴对齐 (碰撞用 AABB)
    ro, ta = rad_u(a), tan_u(a)
    c = pol(a, 3.80, 0)
    for off in (-0.13, 0.0, 0.13):
        B["woodlit"].box(c + ro * off + Z * (DECK + 0.42), ro, ta, Z, 0.115, 1.60, 0.05)
    B["woodlit"].box(c - ro * 0.20 + Z * (DECK + 0.74), ro, ta, Z, 0.05, 1.60, 0.30)
    for sgn in (-1, 1):
        B["iron"].box(c + ta * (sgn * 0.68) + Z * (DECK + 0.20), ro, ta, Z, 0.40, 0.06, 0.40)
        B["iron"].box(c - ro * 0.20 + ta * (sgn * 0.68) + Z * (DECK + 0.47), ro, ta, Z, 0.05, 0.06, 0.94)
    BENCH.append(c)


def mini_pumpkin(bag, c, r):
    """迷你南瓜灯 (八棱旋转体) + 蒂"""
    prof = [(-0.55 * r, 0.32 * r), (-0.30 * r, 0.72 * r), (0.0, 0.95 * r),
            (0.30 * r, 0.72 * r), (0.55 * r, 0.30 * r)]
    sides = 8
    c = Vector(c)
    rows = []
    for (dz, dr) in prof:
        rows.append([c + Vector((cos(2 * pi * q / sides) * dr, sin(2 * pi * q / sides) * dr, dz))
                     for q in range(sides)])
    for li in range(len(prof) - 1):
        for q in range(sides):
            q2 = (q + 1) % sides
            bag.face([rows[li][q], rows[li][q2], rows[li + 1][q2], rows[li + 1][q]],
                     (rows[li][q] + rows[li][q2] + rows[li + 1][q2] + rows[li + 1][q]) / 4 - c)
    for li, sgn in ((0, -1.0), (len(prof) - 1, 1.0)):
        top = c + Z * prof[li][0]
        for q in range(sides):
            bag.face([rows[li][q], rows[li][(q + 1) % sides], top], Z * sgn)
    B["dark"].box(c + Z * (0.55 * r + 0.035), X, Y, Z, 0.035, 0.035, 0.09)


for j in range(16):                                              # 檐下南瓜灯串 x16 (蒂顶搭到搁栅底)
    mini_pumpkin(B["lamp"], pol(22.5 * j + 11.25, 5.28, DECK - 0.50), 0.17)
mini_pumpkin(B["lamp"], pol(ST_A0, ST_RAIL_R, 1.52), 0.19)       # 梯口望柱顶 (落到铜顶上)
for (b0, b1) in ((67.5, 112.5), (157.5, 202.5)):                 # 入口开间檐口南瓜灯串 x7
    p1, p2 = pol(b0, colR(3.5)), pol(b1, colR(3.5))
    B["dark"].beam(p1 + Z * 3.52, p2 + Z * 3.52, 0.025, 0.025)
    for i in range(7):
        mini_pumpkin(B["lamp"], p1.lerp(p2, (i + 0.5) / 7) + Z * 3.40, 0.17)

# ================================ 打卡南瓜灯 (园区同款 v3 雕空脸, 朝向水平) ===============================
FACES = {
    "classic": {
        "eyes": [[(-0.155, 0.045), (-0.055, 0.045), (-0.105, 0.15)],
                 [(0.155, 0.045), (0.055, 0.045), (0.105, 0.15)]],
        "mouth": [(-0.17, -0.02), (-0.125, 0.05), (-0.08, -0.01), (-0.04, 0.05),
                  (0.0, -0.01), (0.04, 0.05), (0.08, -0.01), (0.125, 0.05),
                  (0.17, -0.02), (0.11, -0.115), (-0.11, -0.115)],
    },
}


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
    col_static.objects.link(ob)
    return ob


def ring_at(bag, cx, cy, r0, r1, z0, z1, n=48):
    """任意圆心的扁环 (地面光环)"""
    c = Vector((cx, cy, 0.0))
    for i in range(n):
        a0 = 2 * pi * i / n
        a1 = 2 * pi * (i + 1) / n
        p00 = c + Vector((cos(a0) * r0, sin(a0) * r0, z0))
        p01 = c + Vector((cos(a0) * r1, sin(a0) * r1, z0))
        p11 = c + Vector((cos(a1) * r1, sin(a1) * r1, z0))
        p10 = c + Vector((cos(a1) * r0, sin(a1) * r0, z0))
        dz = Vector((0, 0, z1 - z0))
        bag.face([p00, p01, p11, p10], -Z)
        bag.face([p00 + dz, p01 + dz, p11 + dz, p10 + dz], Z)
        bag.face([p00, p10, p10 + dz, p00 + dz], -(p00 + p10) / 2 + c)
        bag.face([p01, p11, p11 + dz, p01 + dz], (p01 + p11) / 2 - c)


def park_pumpkin(name, base, face_dir, s=1.35):
    """园区同款 v3 南瓜灯: 瓣纹体 + EXACT 贯通雕空脸 (两面) + 暗腔 + 内焰 + 弯蒂.
    face_dir 必须是水平向量 (v2 bug: 目标点高度写 0, 脸被朝下雕)."""
    f = Vector((face_dir[0], face_dir[1], 0.0))
    f.normalize()
    rt = Vector((-f.y, f.x, 0.0))
    sz = 0.86
    C = Vector(base) + Z * (0.34 * s * sz * 0.92)
    rx, rz = 0.34 * s, 0.34 * s * sz
    seg, ring_n, lobes, amp = 24, 14, 8, 0.075
    vs, vcol = [], []
    for j in range(ring_n + 1):
        phi = pi * j / ring_n
        sp, cp = sin(phi), cos(phi)
        for i in range(seg):
            th = 2 * pi * i / seg
            lobe = 1 + amp * sin(lobes * th) * (sp ** 1.4)
            pz = rz * cp
            if pz < 0:
                pz *= 0.8
            if phi < 0.42:
                pz *= 0.94
            vs.append((C.x + rx * sp * cos(th) * lobe, C.y + rx * sp * sin(th) * lobe, C.z + pz))
            g = 0.85 + 0.40 * ((0.5 + 0.5 * sin(lobes * th)) ** 0.65)
            g *= 0.8 if cp < -0.2 else 1.0
            vcol.append((g, g, g))
    fs = []
    for j in range(ring_n):
        r0, r1 = j * seg, (j + 1) * seg
        for i in range(seg):
            i2 = (i + 1) % seg
            fs.append((r0 + i, r1 + i, r1 + i2, r0 + i2))
    body = _new_obj(name + "_body", vs, fs, M["pump"], True)
    flat = []
    for c in vcol:
        flat += [c[0], c[1], c[2], 1.0]
    attr = body.data.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    attr.data.foreach_set("color", flat)
    # 逐个 EXACT 雕刻 (CCW 棱柱 / 一腔一切 / 贯通切割: 棱柱沿 f 贯穿瓜体, 正反两面同时成脸)
    for poly in FACES["classic"]["eyes"] + [FACES["classic"]["mouth"]]:
        p2 = [(r_ * s, u_ * s) for r_, u_ in poly]
        if sum(p2[i][0] * p2[(i + 1) % len(p2)][1] - p2[(i + 1) % len(p2)][0] * p2[i][1]
               for i in range(len(p2))) < 0:
            p2 = p2[::-1]
        cv = [tuple(C + f * (-0.6 * s) + rt * r_ + Z * u_) for r_, u_ in p2] + \
             [tuple(C + f * (0.5 * s) + rt * r_ + Z * u_) for r_, u_ in p2]
        n = len(p2)
        cf = []
        for i in range(n):
            cf.append((i, (i + 1) % n, n + (i + 1) % n, n + i))
        cf.append(tuple(range(n - 1, -1, -1)))
        cf.append(tuple(range(n, 2 * n)))
        cob = _new_obj(name + "_cut", cv, cf, None, False)
        mod = body.modifiers.new("carve", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.object = cob
        dg = bpy.context.evaluated_depsgraph_get()
        me_new = bpy.data.meshes.new_from_object(body.evaluated_get(dg))
        body.modifiers.remove(mod)
        old = body.data
        body.data = me_new
        bpy.data.meshes.remove(old)
        bpy.data.objects.remove(cob, do_unlink=True)
    # 内焰 = 中心发光球 (两面脸的开孔都看得到光); 暗腔 = 顶/底两个碗, 不挡在脸后面
    # (v3 初版把暗腔做成绕脸轴的正反两个半球, 结果另一面那半正好盖在脸孔后面, 孔里是黑的)
    sphere(B["pglow"], C, 0.20 * s, seg=14, ring_n=8)
    for fa, rta in ((Z, X), (-Z, X)):
        for (R, lo, hi, key, nseg, nring) in ((0.30 * s * min(sz, 1.0), 0, 72, "dark", 18, 5),):
            vs2 = []
            for j in range(nring + 1):
                phi = radians(lo + (hi - lo) * j / nring)
                sp, cp = sin(phi), cos(phi)
                for i in range(nseg):
                    az = 2 * pi * i / nseg
                    d = fa * cp + (Z * cos(az) + rta * sin(az)) * sp
                    vs2.append((C.x + d.x * R, C.y + d.y * R, C.z + d.z * R))
            fs2 = []
            for j in range(nring):
                r0, r1 = j * nseg, (j + 1) * nseg
                for i in range(nseg):
                    i2 = (i + 1) % nseg
                    fs2.append((r0 + i, r1 + i, r1 + i2, r0 + i2))
            for q in fs2:
                cen = Vector((0.0, 0.0, 0.0))
                for i in q:
                    cen += Vector(vs2[i])
                B[key].face([vs2[i] for i in q], cen / len(q) - C, True)
    top = C + Z * (rz * 0.96)
    pts = [top + Z * (0.015 * s), top + rt * (0.03 * s) + Z * (0.055 * s),
           top + rt * (0.07 * s) + Z * (0.09 * s), top + rt * (0.11 * s) + Z * (0.115 * s)]
    tube(B["dark"], pts, 0.03, sides=7, cap=True, radii=[0.042 * s, 0.036 * s, 0.028 * s, 0.02 * s])
    B["pump"].bake(body)
    bpy.data.objects.remove(body, do_unlink=True)
    print(f"POI_PUMPKIN verts={len(B['pump'].verts)} f=({f.x:.2f},{f.y:.2f},{f.z:.2f})")
    return C


POI_A, POI_R = 162.0, 3.72                                      # 到达口尽头、贴梯井边 (外侧留 ≥0.65m)
_poi_base = pol(POI_A, POI_R, DECK)
POI_C = park_pumpkin("TW_PoiPumpkin", _poi_base, -tan_u(POI_A), s=1.15)   # 脸沿环廊方向 (面向梯顶到达口)
_cT = Vector((POI_C.x, POI_C.y, 0.0))                                     # 铁托盘 (南瓜落在环廊边沿上)
_top = [Vector((POI_C.x + cos(2 * pi * i / 24) * 0.46, POI_C.y + sin(2 * pi * i / 24) * 0.46, DECK + 0.035)) for i in range(24)]
B["dark"].face(_top, Z)
for i in range(24):
    p0, p1 = _top[i], _top[(i + 1) % 24]
    B["dark"].face([p0, p1, p1 - Z * 0.035, p0 - Z * 0.035], (p0 + p1) / 2 - _cT)
tmark("furniture")

# ================================ 招牌与指示 ===============================
_fnt = None
try:
    _fnt = bpy.data.fonts.load("C:/Windows/Fonts/msyh.ttc")
except Exception as _e:
    print(f"FONT_FAIL {type(_e).__name__} {_e}")

TEXTS = []


def text_obj(name, body, size, loc, key, az, space=1.0, extrude=0.010):
    """发光字: 面朝 app 方位 az 的外侧, 阅读方向 = 观者右手边; 稍后转网格烘进材质 bag"""
    if _fnt is None:
        return
    cu = bpy.data.curves.new(name + "C", type="FONT")
    cu.body = body
    cu.font = _fnt
    cu.size = size
    cu.extrude = extrude
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.space_character = space
    cu.resolution_u = 2                             # 字形曲线细分 (控三角数)
    ob = bpy.data.objects.new(name, cu)
    n = rad_u(az)
    t = Z.cross(n)                                    # 观者右手方向
    ob.matrix_world = Matrix(((t.x, 0.0, n.x), (t.y, 0.0, n.y), (0.0, 1.0, 0.0))).to_4x4()
    ob.location = loc
    col_static.objects.link(ob)
    TEXTS.append((ob, key))
    return ob


def name_sign(tag, az):
    """站名牌: 挂在 az 两侧主柱 (az±22.5°) 之间, 面朝 az"""
    def cx(z):
        return colR(z) * cos(radians(22.5))
    c = pol(az, cx(4.70) - 0.06, 4.70)
    B["sign"].obox(c, az, 2.90, 0.08, 0.95)
    B["brass"].obox(c + Z * 0.495, az, 2.96, 0.10, 0.04)
    B["brass"].obox(c - Z * 0.495, az, 2.96, 0.10, 0.04)
    B["iron"].beam(pol(az - 22.5, colR(5.45), 5.45), pol(az + 22.5, colR(5.45), 5.45), 0.08, 0.10)
    for yy in (-1.0, 1.0):                             # 吊杆 (上端伸进吊梁)
        h0 = c + tan_u(az) * yy + Z * 0.47
        B["iron"].beam(h0, h0 + Z * 0.33, 0.03, 0.03)
    tp = c + rad_u(az) * 0.055
    text_obj(f"TW_SignName{tag}", "缠魂塔", 0.60, tuple(tp + Z * 0.10), "sglow", az, space=1.22)
    text_obj(f"TW_SignSub{tag}", "SOUL SPIRE · 观景台 40M", 0.155, tuple(tp - Z * 0.33),
             "subglow", az, space=1.1)


name_sign("S", DOOR_B)                                            # 主招牌 (南, 门厅正上方)
name_sign("W", 180.0)                                             # 西侧第二入口的站名牌 (朝西来路)
text_obj("TW_SignLiftB", "升降梯 · 直达", 0.21, tuple(pol(DOOR_B, CORE_R + 0.13, LINT_B + 0.64)),
         "sglow", DOOR_B, space=1.12)

SIGN_A = ST_A0                                         # 立牌在梯口望柱正外侧 (不挡进梯路线)
sp = pol(SIGN_A, 3.74, 0.0)
B["iron"].beam(sp, sp + Z * 2.34, 0.06, 0.06)                     # 梯口立牌柱
cS = sp + Z * 2.00
B["sign"].obox(cS, SIGN_A, 1.34, 0.05, 0.60)
B["brass"].obox(cS + Z * 0.315, SIGN_A, 1.40, 0.07, 0.03)
B["brass"].obox(cS - Z * 0.315, SIGN_A, 1.40, 0.07, 0.03)
for tag, sgn, taz in (("O", 1, SIGN_A), ("I", -1, SIGN_A + 180.0)):   # 双面
    o = cS + rad_u(SIGN_A) * (sgn * 0.04)
    text_obj(f"TW_StairSign{tag}", "螺旋梯 ↑", 0.22, tuple(o + Z * 0.11), "sglow", taz, space=1.12)
    text_obj(f"TW_StairSub{tag}", "242 级 · 步行约 20 秒", 0.095, tuple(o - Z * 0.15), "subglow", taz, space=1.04)


def blade_sign(tag, az, text, tsize=0.19):
    """塔顶径向刀牌 (垂直环廊走向, 两面可读)"""
    r0, r1, zc = 3.56, 4.36, 41.95
    p = pol(az, 3.52, DECK)
    B["iron"].beam(p, p + Z * 2.14, 0.05, 0.05)
    c = pol(az, (r0 + r1) / 2, zc)
    B["sign"].box(c, rad_u(az), tan_u(az), Z, r1 - r0, 0.04, 0.26)
    B["brass"].box(c + Z * 0.145, rad_u(az), tan_u(az), Z, r1 - r0 + 0.04, 0.06, 0.03)
    B["brass"].box(c - Z * 0.145, rad_u(az), tan_u(az), Z, r1 - r0 + 0.04, 0.06, 0.03)
    for sgn in (1, -1):
        text_obj(f"TW_Blade{tag}{'P' if sgn > 0 else 'N'}", text, tsize,
                 tuple(c + tan_u(az) * (sgn * 0.035)), "sglow", az + 90.0 * sgn, space=1.15)


BLADE_T, BLADE_S = DOOR_T - 18.0, ARR_LO - 4.0                    # 252° (栈桥口外) / 120° (到达口井侧外)
blade_sign("Lift", BLADE_T, "升降梯")
blade_sign("Stair", BLADE_S, "螺旋梯")

for k, lab, left in ((60, "10M", 182), (121, "20M", 121), (181, "30M", 61)):   # 梯上高度标记
    a_bar = (15.0 * round(step_a(k) / 15.0)) % 360.0
    u0 = ((ST_A0 - a_bar) % 360.0) / abs(DA)
    cand = [u0 + t * (ST_N / ST_TURNS) for t in range(int(ST_TURNS)) if u0 + t * (ST_N / ST_TURNS) < ST_N - 2]
    u = min(cand, key=lambda v: abs(hf(v) - DECK * k / ST_N))
    zt = step_h(int(math.floor(u)))
    aq = ST_A0 + DA * u                                           # 标记正下方那一级的方位 (≈笼柱方位)
    cm = pol(aq, CORE_R + 0.30, zt + 2.04)                       # 自笼柱伸出的横牌 (头顶以上)
    B["iron"].beam(pol(aq, CORE_R + 0.02, zt + 2.04), pol(aq, CORE_R + 0.12, zt + 2.04), 0.03, 0.03)
    B["sign"].box(cm, rad_u(aq), tan_u(aq), Z, 0.52, 0.04, 0.30)
    tm = cm + tan_u(aq) * 0.035                                   # 面朝上楼的人
    text_obj(f"TW_Height{k}", lab, 0.17, tuple(tm + Z * 0.06), "sglow", aq + 90.0, space=1.1)
    text_obj(f"TW_Height{k}b", f"余 {left} 级", 0.095, tuple(tm - Z * 0.08), "subglow", aq + 90.0, space=1.05)
    print(f"HEIGHT_MARK k={k} az={aq:.1f} z={zt:.2f}")


def rim_plaque(tag, az, text):
    """塔顶方位牌: 外栏杆中横杆处, 面朝环廊内侧"""
    c = pol(az, DK_OUT - 0.10, DECK + 0.83)
    B["sign"].obox(c, az, 0.96, 0.04, 0.21)
    B["brass"].obox(c + Z * 0.12, az, 1.02, 0.06, 0.03)
    B["brass"].obox(c - Z * 0.12, az, 1.02, 0.06, 0.03)
    text_obj(f"TW_Rim{tag}", text, 0.145, tuple(c - rad_u(az) * 0.035), "subglow", az + 180.0, space=1.15)


rim_plaque("Wheel", 120.0, "幽眠摩天轮")
rim_plaque("Horse", 25.0, "显灵木马")
rim_plaque("Coaster", 305.0, "幽冥回环")
tmark("signs")

# ================================ 建网格 ===============================
for k in KEYS:
    B[k].to_mesh(M[k].name, M[k], col_static)
CALLB.to_mesh("TW_CallLamp_B", CALL_B, col_static)
CALLT.to_mesh("TW_CallLamp_T", CALL_T, col_static)
CROWB.to_mesh("TW_Crow", M["crow"], col_static, parent=crow_pivot)
for k, bagc in CB.items():
    bagc.to_mesh("TW_Cab_" + M[k].name[3:], M[k], col_lift, parent=lift_root)
for gname, (ge, g) in GATES.items():
    for k, bagc in g.items():
        bagc.to_mesh(f"TW_Gate{gname}_{M[k].name[3:]}", M[k], col_lift, parent=ge)
for gname, (ge, g) in LGATES.items():
    for k, bagc in g.items():
        bagc.to_mesh(f"TW_LGate{gname}_{M[k].name[3:]}", M[k], col_static, parent=ge)

if TEXTS:
    bpy.ops.object.select_all(action="DESELECT")
    for ob, key in TEXTS:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = TEXTS[0][0]
    bpy.ops.object.convert(target="MESH")
    for ob, key in TEXTS:
        B[key].bake(ob, smooth=False)
        bpy.data.objects.remove(ob, do_unlink=True)
    for key in ("sglow", "subglow"):
        B[key].to_mesh(M[key].name, M[key], col_static)
    print(f"TEXTMESH_OK {len(TEXTS)}")
tmark("meshes built")

tris = 0
for ob in sc.objects:
    if ob.type == "MESH":
        tris += sum(len(p.vertices) - 2 for p in ob.data.polygons)
print(f"TRIS total ~{tris}")
for ob in sorted((o for o in sc.objects if o.type == "MESH"),
                 key=lambda o: -sum(len(p.vertices) - 2 for p in o.data.polygons)):
    print("  MESH", ob.name.ljust(22), sum(len(p.vertices) - 2 for p in ob.data.polygons))

# ================================ 参考件 (不导出) ===============================
m_refg = make_mat("REF_Ground", HEX["ground"], rough=1.0)
m_refr = make_mat("REF_GroundRing", HEX["dark"], rough=0.4, emit=HEX["green"], strength=6.0)
RG = Bag()
frustum(RG, -0.10, 60.0, 0.0, 60.0, n=64, cap1=True)
RG.to_mesh("REF_GroundDisc", m_refg, col_ref)
RR = Bag()
annulus(RR, 4.2, 4.8, 0.02, 0.08, 0.0, 360.0, 64, caps=False)
RR.to_mesh("REF_GroundRing", m_refr, col_ref)

# ================================ 灯光 / 世界 / 相机 ===============================
def add_light(name, ltype, loc, energy, color, **kw):
    ld = bpy.data.lights.new(name, ltype)
    ld.energy = energy
    ld.color = hex_lin(color)[:3]
    for k2, v2 in kw.items():
        setattr(ld, k2, v2)
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    col_ref.objects.link(ob)
    return ob


sun = add_light("REF_Sun", "SUN", (60, 30, 90), 2.2, "#B4C7FF", angle=radians(6))
sun.rotation_euler = (radians(55), radians(15), radians(160))
fill = add_light("REF_Fill", "AREA", (0.0, -11.0, 7.0), 900.0, "#FF9A5C", size=16.0)
fill.rotation_euler = (radians(55), 0, 0)
fill.visible_camera = False
add_light("REF_LanternLight", "POINT", (0.0, 0.0, LAN_Z0 + 1.5), 1500.0, "#FF8A1E", shadow_soft_size=0.8)
add_light("REF_RingLight", "POINT", (0.0, 0.0, 1.6), 130.0, "#8CFF4A", shadow_soft_size=3.0)
add_light("REF_DeckLight", "POINT", (0.0, 0.0, DECK + 1.2), 260.0, "#FFC070", shadow_soft_size=4.0)

w = bpy.data.worlds.new("Night")
sc.world = w
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = hex_lin(HEX["night"])
bg.inputs[1].default_value = 0.5


def add_cam(name, loc, target, lens=35, ortho=False, scale=20.0):
    camd = bpy.data.cameras.new(name)
    ob = bpy.data.objects.new(name, camd)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    camd.clip_end = 2000.0
    if ortho:
        camd.type = "ORTHO"
        camd.ortho_scale = scale
    else:
        camd.lens = lens
    col_ref.objects.link(ob)
    return ob


CREST = (28.67 - SX, 115.4 - SY, 24.0)       # 过山车最高点 (塔局部)
cam_three = add_cam("TW_CamThree", tuple(pol(50.0, 78.0, 30.0)), (0, 0, 23), lens=30)
cam_approach = add_cam("TW_CamApproach", (0.0, -40.0, 1.65), (0, 0, 25), lens=16)      # 南侧来路
cam_east = add_cam("TW_CamEast", tuple(pol(0.0, 40.0, 1.65)), (0, 0, 25), lens=16)
cam_west = add_cam("TW_CamWest", tuple(pol(180.0, 40.0, 1.65)), (0, 0, 25), lens=16)
cam_aerial = add_cam("TW_CamAerial", tuple(pol(300.0, 44.0, 56.0)), (0, 0, 22), lens=30)
cam_lobby = add_cam("TW_CamLobby", (1.6, -9.5, 1.65), (0, -1.5, 2.8), lens=24)
cam_entry = add_cam("TW_CamStairEntry", tuple(pol(76.0, 9.5, 1.65)), tuple(pol(58.0, 2.5, 1.6)), lens=24)
cam_lantern = add_cam("TW_CamLantern", tuple(pol(225.0, 13.0, 45.4)), (0, 0, 44.6), lens=40)
cam_deck = add_cam("TW_CamDeck", tuple(pol(300.0, 4.5, DECK + 1.65)), CREST, lens=20)
cam_deck2 = add_cam("TW_CamDeckWheel", tuple(pol(150.0, 4.6, DECK + 1.65)), (-17.5, -30.5, 20.0), lens=20)
cam_stair = add_cam("TW_CamStair", tuple(pol(step_a(110) + 3.5, 2.9, step_h(110) + 1.6)),
                    tuple(pol(step_a(126), 2.7, step_h(126) + 1.3)), lens=18)
cam_top = add_cam("TW_CamTop", (0, 0, 80), (0, 0, 0), ortho=True, scale=13.0)
cam_well = add_cam("TW_CamWell", tuple(pol(330.0, 5.2, DECK + 1.65)), (0, 0, DECK + 0.8), lens=18)
cam_cab = add_cam("TW_CamCab", (0.3, -0.2, CAB_ZB + 1.65), (0, -3.0, 2.2), lens=18)
sc.camera = cam_three

sc.view_settings.view_transform = "Standard"
sc.view_settings.exposure = 0.15

ASSET_BLOOM = str(Path(bpy.app.binary_path).parent / "5.3" / "datafiles" /
                  "assets" / "nodes" / "compositing_nodes_essentials.blend")
try:
    sc.use_nodes = True
    eff = sc.compositor_effects.new(name="Bloom")
    with bpy.data.libraries.load(ASSET_BLOOM, link=False) as (src, dst):
        dst.node_groups = [n for n in src.node_groups if "Bloom" == n]
    eff.node_group = bpy.data.node_groups.get("Bloom")
    print("BLOOM_OK")
except Exception as e:
    print("BLOOM_FAIL", type(e).__name__, str(e)[:120])

# 场景说明 (Blender 文本块)
_rd = bpy.data.texts.new("README_缠魂塔")
_rd.write(
    "缠魂塔 SOUL SPIRE — 眺望塔 v3 (原点建模, 单位米, 塔心=原点, Z up)\n"
    "游戏落位: app (17.5, 0, -30.5) = 过山车地面灯环圆心 (REF_GroundRing 即该灯环, 仅供对照, 不导出)\n\n"
    "方位一律 app 方位: 东0° 南90° 西180° 北270° (Blender 里 = 数学角取负)\n"
    "  门厅/主招牌 朝南 90°; 螺旋梯梯口 东南 58° (逆时针盘升, 到顶 130° 面向摩天轮);\n"
    "  栈桥与笼顶门 朝北 270° (出梯正对提升段); 西侧 180° 开间为第二入口 (带朝西站名牌).\n"
    "集合: Static = 静态件(按材质合并) + 站层门 TW_LGateB/T / Lift = 轿厢 TW_Lift 与滑门 TW_GateB/T\n"
    "      / REF = 相机·灯光·参考件 (不导出)\n"
    "运行时节点: TW_Lift (轿厢, 改 z) / TW_GateB,T (轿门滑移) / TW_LGateB,T (层门滑移)\n"
    "      / TW_CallLamp_B,T (呼梯灯材质) / TW_FlameAnchor (灯室鬼火锚点) / TW_CrowPivot (乌鸦转轴)\n"
    "相机: TW_CamThree 三分之二 / Approach 南侧来路 / East / West / Lobby 门厅 / StairEntry 梯口\n"
    "      / Deck 塔顶看提升段 / DeckWheel 塔顶看摩天轮 / Stair 梯中 / Well 塔顶看梯井 / Cab 轿厢内\n"
    "      / Lantern 灯室 / Top 正交俯视 / Aerial 鸟瞰\n"
    "重跑: E:\\blender\\blender.exe --background --python lookout_tower.py  (脚本是真源, 勿手改 .blend)\n"
)

PREV.mkdir(exist_ok=True)
try:
    for scr in bpy.data.screens:
        for ar in scr.areas:
            if ar.type == "VIEW_3D":
                for spc in ar.spaces:
                    if spc.type == "VIEW_3D":
                        spc.clip_end = 3000.0
                        r3 = spc.region_3d
                        if r3:
                            r3.view_perspective = "PERSP"
                            r3.view_location = (0.0, 0.0, 23.0)
                            r3.view_distance = 118.0
                            r3.view_rotation = Euler((radians(62.0), 0.0, radians(-28.0)),
                                                     "XYZ").to_quaternion()
    print("VIEWPORT_OK")
except Exception as e:
    print("VIEWPORT_FAIL", type(e).__name__, str(e)[:100])

bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "lookout_tower.blend"))
tmark("blend saved")

# ================================ 渲染 ===============================
def render_still(name, cam):
    sc.camera = cam
    sc.render.image_settings.media_type = "IMAGE"
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = str(PREV / name)
    try:
        bpy.ops.render.render(write_still=True)
        return True
    except Exception as e:
        print("RENDER_FAIL", name, type(e).__name__, str(e)[:100])
        return False


sc.render.engine = "BLENDER_EEVEE"
try:
    sc.eevee.taa_render_samples = 48
except Exception:
    pass
sc.render.resolution_x, sc.render.resolution_y = RES
sc.render.resolution_percentage = 100

# 入库预览精简为 12 张 (夜景 7 + 实体检视 5); 其余机位留在 .blend 里供手动查看,
# 实机取证另见 scripts/verify_tower_shots.mjs (42 机位, 不入库)
for old in PREV.glob("*.png"):
    old.unlink()
for name, cam in (("01_three.png", cam_three), ("02_approach.png", cam_approach),
                  ("03_aerial.png", cam_aerial), ("04_lobby.png", cam_lobby),
                  ("05_entry.png", cam_entry), ("06_deck.png", cam_deck),
                  ("07_lantern.png", cam_lantern)):
    render_still(name, cam)
tmark("night stills")

sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.display.shading.show_object_outline = True
for name, cam in (("verify_top.png", cam_top), ("verify_three.png", cam_three),
                  ("verify_lobby.png", cam_lobby), ("verify_entry.png", cam_entry),
                  ("verify_deck.png", cam_well)):
    render_still(name, cam)
sc.camera = cam_three
tmark("verify stills (workbench)")

# ================================ 导出 glb ===============================
bpy.ops.object.select_all(action="DESELECT")
for coll in (col_static, col_lift):
    for ob in coll.all_objects:
        if ob.type in ("MESH", "EMPTY"):
            ob.select_set(True)
try:
    bpy.ops.export_scene.gltf(filepath=str(OUT / "lookout_tower.glb"), export_format="GLB",
                              use_selection=True, export_apply=True)
except (TypeError, RuntimeError) as e:
    print("GLTF_KWARG_FALLBACK", type(e).__name__)
    bpy.ops.export_scene.gltf(filepath=str(OUT / "lookout_tower.glb"), export_format="GLB",
                              use_selection=True)
tmark("glb exported")

# ================================ colliders_tower.json =================--------------
def app_xy(x, y):
    return round(SX + x, 3), round(-SY - y, 3)


def circ(x, y, r, y0=-1.0, y1=60.0, **extra):
    ax, az = app_xy(x, y)
    d = {"x": ax, "z": az, "r": round(r, 3), "y0": round(y0, 3), "y1": round(y1, 3)}
    d.update(extra)
    return d


def pcirc(p, r, y0=-1.0, y1=60.0, **extra):
    return circ(p.x, p.y, r, y0, y1, **extra)


def radial_rect(x0, x1, half, h, az):
    """沿方位 az 径向 x0..x1、横向 ±half 的轴对齐地面 (az ∈ {0,90,180,270})"""
    u = rad_u(az)
    ax, az_app = app_xy(u.x * (x0 + x1) / 2, u.y * (x0 + x1) / 2)
    along_x = abs(u.x) > 0.5                      # blender x = app x
    hw, hd = ((x1 - x0) / 2, half) if along_x else (half, (x1 - x0) / 2)
    return {"shape": "rect", "x": round(ax, 3), "z": round(az_app, 3),
            "hw": round(hw, 3), "hd": round(hd, 3), "h": h}


DK_Y0, DK_Y1 = DECK - 0.5, DECK + 2.2
floors = [
    {"shape": "helix", "x": SX, "z": -SY, "r0": ST_IN, "r1": RIB_R1,
     "a0": round(radians(ST_A0), 6), "dir": ST_DIR, "da": round(radians(abs(DA)), 8),
     "rise": round(RISE, 5), "n": ST_N,
     "h": [round(step_h(k), 5) for k in range(ST_N)]},                 # 逐级踏面高 (首 4 级半高)
    {"shape": "sector", "x": SX, "z": -SY, "r0": round(DK_IN - 0.04, 3), "r1": DK_OUT,
     "a0": 0.0, "a1": round(2 * pi, 6), "h": DECK},
    radial_rect(BR_X0, BR_X1 + 0.03, BR_HALF + 0.05, DECK, DOOR_T),            # 栈桥
    radial_rect(1.22, SILL_X1 + 0.02, SILL_HALF, DECK, DOOR_T),                # 顶门门槛
    radial_rect(1.25, AP_X1 + 0.10, AP_HALF + 0.05, APH, DOOR_B),              # 门厅铺面
    radial_rect(1.25, AP_X1 + 0.10, AP_HALF + 0.05, APH, 180.0),               # 西侧第二入口铺面
]
for c in BENCH:                                                               # 长椅 (贴内栏杆; 长边沿切向)
    floors.append({"shape": "rect", "x": round(SX + c.x, 3), "z": round(-SY - c.y, 3),
                   "hw": 0.27 if abs(c.x) > abs(c.y) else 0.83,
                   "hd": 0.83 if abs(c.x) > abs(c.y) else 0.27, "h": round(DECK + 0.45, 3)})

circles = []
for j in range(CORE_BARS):                        # 笼柱 (门洞处的分段高度带, 顶到柱顶为止)
    a = 360.0 * j / CORE_BARS
    in_b = abs(ang_diff(a, DOOR_B)) < DOOR_HALF - 1e-6
    in_t = abs(ang_diff(a, DOOR_T)) < DOOR_HALF - 1e-6
    segs = [(LINT_B, CAGE_TOP)] if in_b else \
        ([(CAGE_Z0, DECK - 0.05)] if in_t else [(CAGE_Z0, CAGE_TOP)])
    for za, zb in segs:
        circles.append(pcirc(pol(a, CORE_R), 0.09, -1.0 if za < 0.5 else za - 0.4, zb))
for (a, minor) in verts16:                        # 桁架柱身 (到柱顶为止)
    z0 = OPEN_MINOR[a] if (minor and a in OPEN_MINOR) else (0.30 if minor else COL_Z0)
    circles.append(pcirc(pol(a, (COL_R0 + COL_R1) / 2), 0.14 if minor else 0.20, z0 - 0.3, COL_Z1 + 0.10))
for (a, minor, s, h) in FOOT:                     # 石座 (盖对角)
    circles.append(circ(*pol(a, colR(h))[:2], round(s * 0.5 * 1.42, 3), -1.0, h))
for (a1, a2) in L0_CLOSED:                        # 首层封闭开间: 环梁+斜撑当墙 (3 盘链)
    p1, p2 = pol(a1, colR(0.55)), pol(a2, colR(0.55))
    for t in (1 / 6, 3 / 6, 5 / 6):
        circles.append(pcirc(p1.lerp(p2, t), 0.14, -1.0, 2.6))
for k in range(4, ST_POST_END + 1):               # 梯外栏杆立柱 (逐级; 首 4 级留作梯口)
    p, h = pol(step_az(k), ST_RAIL_R), step_h(k)
    circles.append(pcirc(p, 0.07, h - 1.0, h + 1.6))
circles.append(pcirc(pol(ST_A0, ST_RAIL_R), 0.07, -1.0, 1.6))                  # 梯口望柱
for j in range(40):                               # 环廊外栏杆 (柱 + 柱间中点盘)
    circles.append(pcirc(pol(9.0 * j, DK_RO), 0.08, DK_Y0, DK_Y1))
    circles.append(pcirc(pol(9.0 * j + 4.5, DK_RO), 0.16, DK_Y0, DK_Y1))
for j in range(60):                               # 环廊内栏杆 (留到达口 / 栈桥口)
    a = 6.0 * j
    if inner_gap(a):
        continue
    circles.append(pcirc(pol(a, DK_IN + 0.03), 0.07, DK_Y0, DK_Y1))
for a in NEWELS:                                  # 缺口望柱 (到达口两根收细, 让出梯带宽)
    circles.append(pcirc(pol(a, DK_IN + 0.03), 0.045 if a in (ARR_LO, ARR_HI) else 0.10, DK_Y0, DK_Y1))
for r in GUARD_R:                                  # 梯顶尽头护栏 (封住井一侧)
    circles.append(pcirc(pol(ST_ARR, r), 0.045, DECK - 1.0, DECK + 1.7))
for sgn in (-1, 1):                               # 栈桥栏杆
    for x in (1.85, 2.35, 2.85, 3.30):
        circles.append(pcirc(bp(x, sgn * BR_HALF, 0.0), 0.07, DK_Y0, DK_Y1))
for a in (BLADE_T, BLADE_S):                      # 塔顶刀牌立柱
    circles.append(pcirc(pol(a, 3.52), 0.06, DK_Y0, DK_Y1))
circles.append(pcirc(pol(SIGN_A, 3.74), 0.08, -1.0, 2.5))                       # 梯口立牌柱
circles.append(circ(POI_C.x, POI_C.y, 0.27, DK_Y0, DK_Y1))                      # 打卡南瓜灯

WALL_Y0, WALL_Y1 = round(CAB_ZB - 0.3, 4), round(CAB_ZB + 2.6, 4)
OPEN_BAND = [-5.0, -4.0]


def slide(ad, dist):
    """滑门开启位移: 沿 +alpha 切向, 输出 three.js 节点局部 (Y up): Blender (x,y,z) -> (x,z,-y)"""
    v = tan_u(ad) * dist
    return [round(v.x, 4), 0.0, round(-v.y, 4)]


lift = {
    "zBottom": CAB_ZB, "zTop": round(CAB_ZT, 4), "floorThk": CAB_FLOOR, "cabR": CAB_R,
    "floor": {"shape": "circle", "x": SX, "z": -SY, "r": CAB_R, "h": round(CAB_ZB + CAB_FLOOR, 4)},
    "wallBand": [WALL_Y0 - CAB_ZB, WALL_Y1 - CAB_ZB],            # 相对轿底 z
    "openBand": OPEN_BAND,
    # 轿壁盘: 6 立梃 + 4 块玻璃板的中点 (相邻盘圆心距 0.64m < 推挤半径和 0.86m, 立梃之间才封得住)
    "walls": [circ(*pol(a, CR)[:2], 0.05, WALL_Y0, WALL_Y1) for a in CAB_POSTS
              if abs(ang_diff(a, DOOR_B)) > 1.0 and abs(ang_diff(a, DOOR_T)) > 1.0]
             + [circ(*pol(0.5 * (a1 + a2), CR)[:2], 0.05, WALL_Y0, WALL_Y1) for a1, a2 in CAB_BAYS
                if abs(ang_diff(0.5 * (a1 + a2), DOOR_B)) > 1.0 and abs(ang_diff(0.5 * (a1 + a2), DOOR_T)) > 1.0],
    "gateB": {"post": circ(*pol(DOOR_B, CR)[:2], 0.05, WALL_Y0, WALL_Y1), "open": slide(DOOR_B, 1.14)},
    "gateT": {"post": circ(*pol(DOOR_T, CR)[:2], 0.05, WALL_Y0, WALL_Y1), "open": slide(DOOR_T, 1.14)},
    "lgateB": {"closedBand": [-1.0, round(LINT_B + 0.3, 3)], "open": slide(DOOR_B, 1.50)},
    "lgateT": {"closedBand": [round(DECK - 0.5, 3), round(LINT_T + 0.3, 3)], "open": slide(DOOR_T, 1.50)},
    "gateBottom": [circ(*pol(a, CORE_R)[:2], 0.30, *OPEN_BAND) for a in (DOOR_B - 15.0, DOOR_B, DOOR_B + 15.0)],
    "gateTop": [circ(*pol(a, CORE_R)[:2], 0.30, DECK - 0.5, LINT_T + 0.3) for a in (DOOR_T - 15.0, DOOR_T, DOOR_T + 15.0)],
    "spotBottom": list(app_xy(*pol(DOOR_B, CORE_R + 1.0)[:2])),
    "spotTop": list(app_xy(*bp(BR_X1 - 0.9, 0.0, 0.0)[:2])),
}
pois = [{"x": round(SX + POI_C.x, 3), "y": DECK, "z": round(-SY - POI_C.y, 3), "label": "pumpkin_tower"}]
manifest = {
    "version": 3,
    "note": "缠魂塔玩家碰撞表 v3 (app 坐标, lookout_tower.py 生成). helix.h = 逐级踏面高 (h[k]), rise 仅为兼容保留. "
            "floors = 叠层地面(只取 <=脚底+步高的最高块; "
            "高出不足一人高的当墙; 更高的可从下走过); circles 带 y0/y1 = 仅脚底高度落在带内才推挤; "
            "lift = 升降梯动态碰撞 (轿厢地面 h / 轿壁与轿门高度带随轿厢改写; 层门 gateBottom/gateTop 在轿厢不在该站时闭合); "
            "首层封闭开间的环梁+斜撑已按圆盘链入表",
    "place": {"x": SX, "z": -SY},
    "azimuths": {"doorBottom": DOOR_B, "doorTop": DOOR_T, "stairStart": ST_A0, "stairArrive": round(ST_ARR, 3),
                 "secondEntrance": 180.0},
    "floors": floors, "circles": circles, "lift": lift, "pois": pois,
}
(OUT / "colliders_tower.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
print(f"COLLIDERS floors={len(floors)} circles={len(circles)} lift.walls={len(lift['walls'])}")
print("AZ doorB", DOOR_B, "doorT", DOOR_T, "stair", ST_A0, "->", round(ST_ARR, 2),
      "DA", round(DA, 4), "RISE", round(RISE, 4), "TOP_Z", CROW_Z + 0.42)
print("\nDONE")
