# -*- coding: utf-8 -*-
"""
幽冥回环 NETHER LOOP v1 - 玩家可乘坐钢铁过山车 (game-ready glTF asset)
Run: blender --background --python roller_coaster.py

北区官方预留位 (Blender +Y=北, 园区原点=摩天轮):
  站台 (18, 54..78) 车头朝北 -> 15° 偏东链条提升(33m) -> 75° 首俯冲
  -> 东扫弯 -> 克洛索衣德大回环 -> 右扫向南 -> 3 连驼峰 -> 零重力滚
  -> 双螺丝钻 -> 西南下降螺旋 -> 刹车 -> S 弯回站
真实铁律: 曲率 G1 连续(弧段积分), 能量守恒+阻力仿真 v(s), 回环顶 g>=0.8,
  峰值 <=4.0g 瞬时(真实 Batman 级), banking 由横向 g<=1.2 反解。
输出: roller_coaster.glb(静态) + roller_coaster_train.glb(列车)
      + centerline.json(0.5m 弧长采样: pos/tan/up/zone/v) + preview/
"""
import bpy
import json
import math
import time
from math import radians, pi, cos, sin, atan2, hypot, sqrt, degrees, asin
from pathlib import Path
import numpy as np
from mathutils import Vector, Quaternion, Matrix

T0 = time.time()
def tmark(label):
    print(f"[t={time.time()-T0:6.1f}s] {label}", flush=True)

P = {
    "ds_raw": 0.4,          # 求解器积分步长 (m)
    "ds_out": 0.5,          # 导出采样步长 (m)
    "gauge": 1.15,          # 轨距
    "heart_off": 1.10,      # 心线(乘客心脏)在轨中心上方 (到轨顶再 +rail_r 0.062)
    "spine_drop": 0.85,     # 脊柱在轨面下方
    "tie_step": 1.2,        # 轨枕节距
    "rail_r": 0.062,
    "spine_r": 0.21,
    "support_step": 10.0,   # 立柱间距
    "station_h": 3.0,       # 站内轨面高
    "lift_top_h": 33.3,
    "lift_angle": 32.0,
    "res_still": (1600, 900),
    "render_video": False,
}

HEX = {
    "orange": "#FFA53B", "violet": "#9B5BFF", "green": "#8CFF4A",
    "red": "#C43B3B", "warm": "#FFE9C4", "cream": "#E8D9B8",
    "steel": "#2A2140",       # 轨道主构 暗夜紫近黑
    "rail": "#4A4458",        # 跑轨钢管
    "metal": "#3A4152", "metal_d": "#1E2330", "iron": "#23273A",
    "wood": "#4A3526", "stone": "#3A3F4C",
    "night": "#060913", "ground_prev": "#0B0F14",
    "paint": "#6E4BC4",       # 客舱金属漆(亮一点的紫)
    "seat": "#C89B6A",        # 座垫皮革暖色
}

def hex_lin(h, a=1.0):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i+2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, a)

# ------------------------------------------------------------- scene prep ---
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
col_static = bpy.data.collections.new("Static")
col_train = bpy.data.collections.new("Train")
sc.collection.children.link(col_static)
sc.collection.children.link(col_train)

# ------------------------------------------------------------ turtle path ---
def rot_about(v, k, a):
    """Rodrigues: v 绕单位轴 k 旋转 a 弧度."""
    c, s = cos(a), sin(a)
    return (v * c + k.cross(v) * s + k * (k.dot(v) * (1.0 - c))).normalized()

class Turtle:
    """心线海龟: pos/T/U 构成刚体正交帧, 弧段积分保证 G1 连续."""
    def __init__(self, pos, heading, zone="station"):
        self.pos = Vector(pos)
        self.T = Vector(heading).normalized()
        self.U = Vector((0.0, 0.0, 1.0))
        self.U = (self.U - self.T * self.U.dot(self.T)).normalized()
        self.zone = zone
        self.samples = []   # (pos, T, U, zone)
        self.elements = []  # (zone, s0, s1, note)
        self._s = 0.0
        self._mark()

    def _mark(self):
        self.samples.append((self.pos.copy(), self.T.copy(), self.U.copy(), self.zone))

    def _step(self):
        self.pos += self.T * P["ds_raw"]
        self._s += P["ds_raw"]
        self._mark()

    def begin(self, zone):
        if self.elements and self.elements[-1][0] == zone and not self.elements[-1][3]:
            return
        self.elements.append([zone, self._s, self._s, ""])
        self.zone = zone

    def end(self, note=""):
        if self.elements:
            self.elements[-1][2] = self._s
            self.elements[-1][3] = note

    def forward(self, L, zone=None, pitch_to=None):
        """直线(可带目标坡度微调: pitch_to 为高度差)."""
        if zone: self.begin(zone)
        n = max(1, int(L / P["ds_raw"]))
        for _ in range(n):
            self._step()
        self.end(f"L={L:.0f}")

    def vturn(self, deg, r, zone=None):
        """竖直面弧: deg>0 抬头 (绕 T×U 轴)."""
        if zone: self.begin(zone)
        total = radians(deg)
        B = self.T.cross(self.U).normalized()
        n = max(1, int((abs(total) * r) / P["ds_raw"]))
        d = total / n
        for _ in range(n):
            self.T = rot_about(self.T, B, d)
            self.U = rot_about(self.U, B, d)
            self._step()
        self.end(f"vturn {deg:.0f}deg r{r:.0f}")

    def planar_turn(self, deg, r, bank=0.0, zone=None, dz=None):
        """水平弯: deg>0 右转(顺时针俯视), banking 向弯内倾(右转右倾).
        滚转必须按[目标角-已转角]的增量施加, 直接施加目标角会逐帧叠加!"""
        if zone: self.begin(zone)
        total = radians(deg)
        n = max(2, int((abs(total) * r) / P["ds_raw"]))
        d = total / n
        Z = Vector((0, 0, 1))
        phi_prev = 0.0
        sgn = 1 if deg >= 0 else -1
        for i in range(n):
            u = (i + 0.5) / n
            # bank 缓变 (首尾 30% smoothstep)
            ramp = 1.0 if abs(total) < 0.05 else min(1.0, min(u, 1 - u) / 0.30)
            ramp = ramp * ramp * (3 - 2 * ramp)
            phi = radians(bank) * ramp * sgn
            self.T = rot_about(self.T, Z, -d)          # 右转
            self.U = rot_about(self.U, Z, -d)
            self.U = rot_about(self.U, self.T, phi - phi_prev)  # 增量滚转
            phi_prev = phi
            if dz is not None:
                drop = Vector((0, 0, 1)) * (dz / n)
                self.pos += drop
            self._step()
        # 收尾回正
        self.U = (self.U - self.T * self.U.dot(self.T)).normalized()
        self.end(f"turn {deg:.0f}deg r{r:.0f} bank{bank:.0f}")

    def loop(self, r_mid, taper, zone="loop"):
        """克洛索衣德回环: r(t)=r_mid+taper*cos(t), 顶=底+2*r_mid."""
        self.begin(zone)
        B = self.T.cross(self.U).normalized()
        th = 0.0
        while th < 2 * pi:
            r = r_mid + taper * cos(th)
            d = P["ds_raw"] / r
            d = min(d, radians(6))
            self.T = rot_about(self.T, B, d)
            self.U = rot_about(self.U, B, d)
            self.pos += self.T * (r * d)
            th += d
            self._s += r * d
            self._mark()
        self.end(f"loop r{r_mid:.1f}+/-{taper:.1f}")

    def screw_turn(self, deg, r, bank=0.0, pitch_from=None, pitch_to=None,
                   zone=None, sgn_note=""):
        """马蹄弯: 水平转弯与俯仰拉出耦合 (真实俯冲的旋降/旋升形态).
        pitch_from/to 为坡度(度)起止, 反馈控制逐帧跟踪目标坡度."""
        if zone: self.begin(zone)
        total = radians(deg)
        n = max(4, int((abs(total) * r) / P["ds_raw"]))
        dplan = total / n
        Z = Vector((0, 0, 1))
        cur_slope = asin(max(-1, min(1, self.T.z)))
        p0 = degrees(cur_slope) if pitch_from is None else pitch_from
        p1 = degrees(cur_slope) if pitch_to is None else pitch_to
        phi_prev = 0.0
        sgn = 1 if deg >= 0 else -1
        for i in range(n):
            u = (i + 0.5) / n
            self.T = rot_about(self.T, Z, -dplan)
            self.U = rot_about(self.U, Z, -dplan)
            # 坡度反馈: 必须绕水平右轴旋转 (带倾角时绕倾斜B轴会偷改航向!)
            uu = u * u * (3 - 2 * u)
            tgt = radians(p0 + (p1 - p0) * uu)
            cur = asin(max(-1, min(1, self.T.z)))
            err = tgt - cur
            if abs(err) > 1e-5:
                B = self.T.cross(self.U).normalized()
                Bh = B - Z * B.dot(Z)
                if Bh.length < 1e-5:
                    Bh = B
                Bh = Bh.normalized()
                self.T = rot_about(self.T, Bh, err)
                self.U = rot_about(self.U, Bh, err)
            # banking 渐变
            ramp = 1.0 if abs(total) < 0.05 else min(1.0, min(u, 1 - u) / 0.30)
            ramp = ramp * ramp * (3 - 2 * ramp)
            phi = radians(bank) * ramp * sgn
            self.U = rot_about(self.U, self.T, phi - phi_prev)
            phi_prev = phi
            self._step()
        self.U = (self.U - self.T * self.U.dot(self.T)).normalized()
        self.end(f"screw {deg:.0f}deg r{r:.0f} p{p0:.0f}->{p1:.0f} b{bank:.0f}{sgn_note}")

    def corkscrew(self, r, turns, right=True, zone="corkscrew", advance=None):
        """螺丝钻: 心线绕前进轴 E1/E2 螺旋, 首尾 12% 行程半径渐起渐收,
        出口切线=入口切线, 整圈数出口正立. 切线用数值差分."""
        self.begin(zone)
        if advance is None:
            advance = 0.9 * r * 2 * pi
        A = self.T.copy()
        E1 = self.U.copy()
        E2 = A.cross(E1) * (1 if right else -1)
        total = 2 * pi * turns
        n = max(8, int((total * r + advance) / P["ds_raw"]))
        P0 = self.pos.copy()
        prev = P0.copy()
        for i in range(1, n + 1):
            u = i / n
            phi = total * u
            lead = min(1.0, min(u, 1 - u) / 0.12)
            lead = lead * lead * (3 - 2 * lead)
            radial = E1 * cos(phi) + E2 * sin(phi)
            self.pos = P0 + A * (advance * u) + radial * (r * lead)
            step_vec = self.pos - prev
            L = step_vec.length
            if L > 1e-6:
                self.T = step_vec.normalized()
                Ur = rot_about(E1, A, phi)
                self.U = (Ur - self.T * Ur.dot(self.T)).normalized()
                self._s += L
                self._mark()
            prev = self.pos.copy()
        self.U = (self.U - self.T * self.U.dot(self.T)).normalized()
        # 出口强制回正: 整圈数时 T=A, U=E1 (数值切线在收尾处有微小摆动)
        self.T = A.normalized()
        self.U = (E1 - self.T * E1.dot(self.T)).normalized()
        self.end(f"cork r{r:.1f} x{turns} adv{advance:.0f}")

    def close_to(self, target, heading_deg, r=18.0, bank=8.0, zone="return"):
        """两圆弧闭环求解器: 从当前位姿闭合到 (target, heading).
        网格搜第一弯角(±240deg)与多半径, 第二弯角由航向差决定."""
        Q = Vector((target[0], target[1], 0))
        th_e = heading_deg
        th_s = degrees(atan2(self.T.x, self.T.y))
        Ps = Vector((self.pos.x, self.pos.y, 0))

        def arc_from_start(p0, hdg, deg_, rr):
            """从 (p0,hdg) 前进 deg_ 弧后的位置 (deg>0 右转)."""
            a = radians(deg_)
            c0, s0 = cos(radians(hdg)), sin(radians(hdg))
            if deg_ >= 0:
                c = p0 + Vector((c0, -s0, 0)) * rr
            else:
                c = p0 + Vector((-c0, s0, 0)) * rr
            a0 = atan2(p0.y - c.y, p0.x - c.x)
            a1 = a0 - a
            return Vector((c.x + rr * cos(a1), c.y + rr * sin(a1), 0))

        def arc_end_start_pt(Q_, th_end, b_, rr):
            """以 (Q_,th_end) 为终点、转角 b_ 的弧的起点.
            关键: 终点处圆心在 [最终航向的转弯侧]."""
            c0, s0 = cos(radians(th_end)), sin(radians(th_end))
            if b_ >= 0:   # 右转弧 -> 终点时圆心在右侧
                c = Q_ + Vector((c0, -s0, 0)) * rr
            else:         # 左转弧 -> 圆心在左侧
                c = Q_ + Vector((-c0, s0, 0)) * rr
            a_end = atan2(Q_.y - c.y, Q_.x - c.x)
            a_st = a_end + radians(b_) if b_ >= 0 else a_end - radians(b_)
            return Vector((c.x + rr * cos(a_st), c.y + rr * sin(a_st), 0))

        best = None
        for rr in (16.0, 20.0, 24.0):
            for a1 in np.linspace(-135, 135, 1081):
                h1 = th_s + a1
                P1 = arc_from_start(Ps, th_s, a1, rr)
                b = (th_e - h1 + 540) % 360 - 180
                if abs(b) > 135:
                    continue
                P2 = arc_end_start_pt(Q, th_e, b, rr)
                L = (P2 - P1).length
                if L > 400:
                    continue
                dv = (P2 - P1).normalized() if L > 1e-6 else Vector((0, 1, 0))
                align = degrees(atan2(dv.x, dv.y))
                err = abs(((align - h1 + 540) % 360) - 180)
                if L < -0.5:
                    continue
                score = err * 6 + L * 0.02   # 航向残差重罚: 闭环后还有 ~26m 直线, 1deg≈0.45m 侧漂
                if best is None or score < best[0]:
                    best = (score, a1, b, L, err, rr)
        if best is None or best[4] > 3.0:
            print(f"CLOSER_FAIL best={best}")
            print(f"  Ps=({Ps.x:.1f},{Ps.y:.1f}) th_s={th_s:.1f} Q=({Q.x:.1f},{Q.y:.1f}) th_e={th_e}")
            return
        _, a1, b, L, _, rr = best
        P1v = arc_from_start(Ps, th_s, a1, rr)
        P2v = arc_end_start_pt(Q, th_e, b, rr)
        print(f"CLOSER: r{rr:.0f} turn1 {a1:+.1f} straight {L:.1f}m turn2 {b:+.1f}")
        print(f"  Ps=({Ps.x:.2f},{Ps.y:.2f}) th_s={th_s:.2f} P1=({P1v.x:.2f},{P1v.y:.2f}) "
              f"P2=({P2v.x:.2f},{P2v.y:.2f}) Q=({Q.x:.2f},{Q.y:.2f}) err={best[4]:.2f}")
        if abs(a1) > 0.5:
            self.planar_turn(a1, rr, bank=bank * (1 if a1 > 0 else -1), zone=zone)
        if L > 0.5:
            self.forward(L, zone=zone)
        if abs(b) > 0.5:
            self.planar_turn(b, rr, bank=bank * (1 if b > 0 else -1), zone=zone)

    def roll_straight(self, L, roll_total_deg, zone="zerog"):
        """直线上滚转(零重力滚): 全程缓慢转 360deg (增量施加)."""
        self.begin(zone)
        n = max(2, int(L / P["ds_raw"]))
        phi_prev = 0.0
        for i in range(n):
            u = (i + 0.5) / n
            ramp = u * u * (3 - 2 * u)
            phi = radians(roll_total_deg) * ramp
            self.U = rot_about(self.U, self.T, phi - phi_prev)
            phi_prev = phi
            self._step()
        self.U = (self.U - self.T * self.U.dot(self.T)).normalized()
        self.end(f"roll {roll_total_deg:.0f}deg L{L:.0f}")

    def hill(self, dh, r_up=16.0, zone="camelback"):
        """驼峰: 爬升弧+直线+峰顶长弧(负g)+下降回平 (净高变为0)."""
        self.begin(zone)
        th = radians(26)
        rc = r_up * 1.45
        self.vturn(+math.degrees(th), r_up)
        climb_arc = r_up * (1 - cos(th))
        need = dh - climb_arc
        if need > 0:
            self.forward(need / sin(th))
        self.vturn(-2 * math.degrees(th), rc)     # 峰顶 (负 g 段)
        self.vturn(+math.degrees(th), rc)          # 下降拉平
        self.end(f"hill +{dh:.0f}")

    def descend_to(self, h_target, r=18.0):
        """缓降到目标高度, 三级坡度(24/12/6deg)防过冲."""
        while self.pos.z - h_target > 0.05:
            rem = self.pos.z - h_target
            th = 24 if rem > 3.2 else (12 if rem > 0.9 else 6)
            thr = radians(th)
            self.vturn(-th, r)
            drop = r * (1 - cos(thr))
            remain = (self.pos.z - drop) - h_target
            if remain > 0:
                self.forward(min(remain / sin(thr), 40))
            self.vturn(+th, r)
            if th <= 6 and self.pos.z - h_target < 0.5:
                break

# ---------------------------------------------------------------- layout ---
def build_centerline(qx=0.0, qy=0.0):
    """v4 定线 (顺时针大环, r146 围栏内):
    站台(14,38)朝北 -> 螺旋弯链提升 r65 右弯56° -> 峰(50,121)h27
    -> 右马蹄旋降105° -> 大回环 -> 爬升h17 -> 零重力滚 -> 右转40
    -> 双螺丝钻 r5.2 -> 旋降西转 -> 驼峰串x3 西返 -> 两弧闭环求解器回站"""
    X0, Y0 = 11.5, 44.0
    t = Turtle((X0, Y0, P["station_h"]), (0, 1, 0), zone="station")
    t.forward(22.0, zone="station")
    t.forward(7.0, zone="dispatch")
    t.planar_turn(8, 40, bank=4, zone="lift")
    # --- 螺旋弯链提升: 全程右弯 56deg (0->35 / 35 / 35->0), h3 -> 27 ---
    t.screw_turn(+20, 65, bank=0, pitch_from=0, pitch_to=+35, zone="lift")
    t.screw_turn(+16, 65, bank=0, pitch_from=+35, pitch_to=+35, zone="lift")
    t.screw_turn(+20, 65, bank=0, pitch_from=+35, pitch_to=0, zone="lift")
    t.crest_h = t.pos.z
    # --- 首俯冲: 45deg 陡入 + 105deg 右旋拉出 (旋降 -45->-10), 出口 ~θ175 h9 ---
    t.vturn(-45, 13, zone="drop")
    t.screw_turn(+105, 24, bank=34, pitch_from=-45, pitch_to=-10, zone="drop")
    t.screw_turn(0.01, 20, pitch_from=-10, pitch_to=0, zone="drop")
    # --- 大回环 r7.5 (底 h9, 顶 24, 顶点 +0.56g, 入口 4.2g 瞬时 Batman级) ---
    t.loop(r_mid=7.5, taper=3.3)
    # --- 爬升 h~18.5 (压螺丝钻入速, g ~2.6) ---
    t.screw_turn(+6, 30, bank=4, pitch_from=0, pitch_to=+18, zone="climb")
    t.forward(40.0, zone="climb")
    t.screw_turn(0.01, 30, pitch_from=+18, pitch_to=0, zone="climb")
    # --- 零重力滚 360 ---
    t.roll_straight(30, 360, zone="zerog")
    # --- 双螺丝钻 r5.8 (入速 ~14, g ~3.5) ---
    t.corkscrew(5.8, 1.0, right=True, zone="corkscrew", advance=9.0)
    t.forward(2.0, zone="sweep")
    t.corkscrew(5.8, 1.0, right=True, zone="corkscrew", advance=9.0)
    t.forward(2.0, zone="sweep")
    # --- 东南 160deg 大回旋掉头 (招牌收尾元素, 旋降; 185->160: 出口航向偏西, 终段 S 弯可解) ---
    t.screw_turn(+160, 30, bank=22, pitch_from=0, pitch_to=-8, zone="uturn")
    # --- 末段 (P0 闭环重写): 改平 -> 闭环器到站台正南 -> 刹车段降高 -> 精确闭合到 s=0 位姿 ---
    # 原缺陷: uturn 出口 -8deg 俯角未改平, close_to 直线段一路下扎 + descend_to 目标 3.8 过冲,
    # 末端悬空断轨 6.5m (站台区双轨并排). 现在: 平面精确闭合 (X0, Y0-26) -> 刹车段降回站高 -> 直段补到 Y0.
    _pitch = degrees(asin(max(-1.0, min(1.0, t.T.z))))
    if _pitch < -0.2:
        t.vturn(-_pitch, 24.0, zone="return")
    t.close_to((X0 + qx, Y0 - 26.0 + qy), 0.0, bank=8.0, zone="return")
    t.begin("brake")                       # 下降段+进场直段 = 刹车段 (v(s) 平滑减速 + 刹车鳍)
    t.descend_to(P["station_h"], r=20.0)
    if Y0 - t.pos.y > 0.05:
        t.forward(Y0 - t.pos.y, zone="brake")
    # 闭合校验 (P0)
    gp = t.pos - Vector((X0, Y0, P["station_h"]))
    print(f"CLOSE_3D {gp.length:.3f}m  end=({t.pos.x:.3f},{t.pos.y:.3f},{t.pos.z:.3f})")
    t.gap = gp.length
    t.gap_heading = degrees(atan2(t.T.x, t.T.y))
    t.x0, t.y0 = X0, Y0
    return t

def frame_matrix(pos, Rv, Tv, Uv):
    """世界帧 -> 4x4 (基向量为列)."""
    return Matrix(((Rv.x, Tv.x, Uv.x, pos.x),
                   (Rv.y, Tv.y, Uv.y, pos.y),
                   (Rv.z, Tv.z, Uv.z, pos.z),
                   (0.0, 0.0, 0.0, 1.0)))

t = build_centerline()
# 自动校准闭环: close_to 解析解 vs ds_raw 积分有 ~1-2m 漂移, 反向补偿目标点迭代消除 (P0)
qx = qy = 0.0
for _cal in range(3):
    t = build_centerline(qx, qy)
    _dr = t.pos - Vector((t.x0, t.y0, P["station_h"]))
    print(f"CALIB{_cal} drift=({_dr.x:+.2f},{_dr.y:+.2f},{_dr.z:+.2f}) |xy|={hypot(_dr.x, _dr.y):.2f}")
    if hypot(_dr.x, _dr.y) < 0.4:
        break
    qx -= _dr.x
    qy -= _dr.y
tmark(f"centerline raw: {len(t.samples)} pts, L={t._s:.1f}m, crest={t.crest_h:.1f}m")
print(f"CLOSE_GAP end->start: {t.gap:.2f}m, end_heading={t.gap_heading:+.1f}deg (want ~0)")

# ------------------------------------------------------- resample 0.5m ---
def resample(samples, ds):
    out = [samples[0]]
    acc = 0.0
    for i in range(1, len(samples)):
        p0, T0v, U0, z0 = samples[i - 1]
        p1, T1, U1, z1 = samples[i]
        seg = (p1 - p0).length
        if seg < 1e-9:
            continue
        acc += seg
        while acc >= ds:
            a = 1 - (acc - ds) / seg
            pm = p0.lerp(p1, a)
            Tm = (T0v.lerp(T1, a)).normalized()
            Um = (U0.lerp(U1, a))
            Um = (Um - Tm * Um.dot(Tm)).normalized()
            out.append((pm, Tm, Um, z1))
            acc -= ds
    return out

RS = resample(t.samples, P["ds_out"])
tmark(f"resampled: {len(RS)} pts @ {P['ds_out']}m")
# 闭环缝合 (P0): 末端距首样本 <1.2 步长时补首样本, sweep 画出闭缝段
_seam = (RS[0][0] - RS[-1][0]).length
if _seam < P["ds_out"] * 1.2:
    RS.append((RS[0][0], RS[0][1], RS[0][2], "station"))
    print(f"SEAM_OK {_seam:.3f}m -> 已补缝合样本")
else:
    print(f"SEAM_WARN {_seam:.3f}m 超限未缝合 (查 CLOSE_3D)")

# ------------------------------------------------------- speed sim v(s) ---
G_ACC = 9.81
C_AIR = 0.0011     # 风阻系数 (1/m)
C_ROLL = 0.004     # 滚阻
zones_s = {}
for e in t.elements:
    zones_s.setdefault(e[0], []).append((e[1], e[2]))

def zone_at(s):
    for z, spans in zones_s.items():
        for a, b in spans:
            if a <= s <= b:
                return z
    return "track"

speeds = np.zeros(len(RS))
v2 = 2.0 ** 2
prev_z = RS[0][0].z
S_ARR = np.arange(len(RS)) * P["ds_out"]
for i in range(len(RS)):
    z = RS[i][0].z
    zn = zone_at(S_ARR[i])
    if zn == "lift":
        v2 = 3.2 ** 2
    elif zn in ("brakes", "brake", "station_in"):
        v2 = max(1.5 ** 2, v2 - 2 * 4.2 * P["ds_out"])
    elif zn == "station":
        v2 = 2.0 ** 2
    else:
        dz = prev_z - z
        v2 = max(0.5, v2 + 2 * G_ACC * dz - 2 * C_ROLL * G_ACC * P["ds_out"] - 2 * C_AIR * v2 * P["ds_out"])
    speeds[i] = sqrt(v2)
    prev_z = z
vmax = speeds.max()
tmark(f"speed sim: vmax={vmax:.1f} m/s ({vmax*3.6:.0f} km/h), end={speeds[-1]:.1f}")

# g 校验表 (逐元素)
print("\n=== G-CHECK ===")
for z, s0, s1, note in t.elements:
    if s1 <= s0: continue
    i0, i1 = int(s0 / P["ds_out"]), min(len(RS) - 1, int(s1 / P["ds_out"]))
    v_in, v_out = speeds[i0], speeds[i1]
    p0, p1 = RS[i0][0], RS[i1][0]
    hdg = degrees(atan2(RS[i1][1].x, RS[i1][1].y))
    print(f"  {z:<11} s{s0:5.0f}-{s1:<5.0f} ({p0.x:6.1f},{p0.y:6.1f},{p0.z:5.1f})->({p1.x:6.1f},{p1.y:6.1f},{p1.z:5.1f}) "
          f"v {v_in:4.1f}->{v_out:4.1f} hdg{hdg:+6.0f} {note}")
r_fence = max(hypot(p[0].x, p[0].y) for p in RS)
z_min = min(p[0].z for p in RS)
print(f"  fence_r_max={r_fence:.1f} (围栏146)  heart_z_min={z_min:.2f}")
if r_fence > 142:
    print("  !! WARN 超出围栏包络")

# ------------------------------------------------------------ materials ---
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

M = {
    "steel":  make_mat("NL_Steel",  HEX["steel"],  rough=0.55, metal=0.85),
    "rail":   make_mat("NL_Rail",   HEX["rail"],   rough=0.35, metal=0.9),
    "spine":  make_mat("NL_Spine",  HEX["violet"], rough=0.5,  metal=0.7),
    "phos":   make_mat("NL_Phosphor", HEX["steel"], rough=0.4, metal=0.3,
                       emit=HEX["green"], strength=6.0),
    "dog":    make_mat("NL_Dog",    HEX["red"],    rough=0.6, metal=0.5,
                       emit=HEX["red"], strength=0.35),  # P1-2: 棘齿暗红夜光(与刹车鳍同档)
    "fin":    make_mat("NL_Fin",    HEX["red"],    rough=0.5, metal=0.6,
                       emit=HEX["red"], strength=0.35),
    "column": make_mat("NL_Column", HEX["steel"],  rough=0.6, metal=0.8),
    "foot":   make_mat("NL_Footing", HEX["stone"], rough=0.9),
    "plat":   make_mat("NL_Platform", HEX["wood"], rough=0.85),
    "plattop": make_mat("NL_PlatTop", HEX["stone"], rough=0.8),
    "roof":   make_mat("NL_Roof",   HEX["steel"],  rough=0.7, metal=0.4),
    "sign":   make_mat("NL_Sign",   HEX["violet"], rough=0.6, emit=HEX["violet"], strength=0.5),
    "signphos": make_mat("NL_SignPhos", HEX["steel"], rough=0.4, emit=HEX["green"], strength=1.0),  # 终审 P2b: 边框 4.0 压过主字 -> 1.0 (主1.5>框1.0 倒挂解除)
    "warmemit": make_mat("NL_Warm",  HEX["orange"], rough=0.5, emit=HEX["orange"], strength=5.0),
    "creamemit": make_mat("NL_Cream", HEX["warm"], rough=0.5, emit=HEX["warm"], strength=4.5),  # P2: §6 灯笼芯 4.0->4.5
    "paint":  make_mat("NL_Paint",  HEX["paint"],  rough=0.35, metal=0.75),
    "trim":   make_mat("NL_Trim",   HEX["orange"], rough=0.45, metal=0.5,
                       emit=HEX["orange"], strength=0.8),
    "oglow":  make_mat("NL_OrangeGlow", HEX["orange"], rough=0.5, emit=HEX["orange"], strength=4.0),  # P2: §6 补位
    "phos2":  make_mat("NL_Phos2",  HEX["steel"], rough=0.4, metal=0.3,
                       emit=HEX["green"], strength=5.0),   # P2: 列车磷光件 (轨道 NL_Phosphor 6.0 不变)
    "dark":   make_mat("NL_DarkIron", "#14161F", rough=0.5, metal=0.8),  # P2: 提前 (站台南瓜蒂也用)
    "signglow": make_mat("NL_SignGlow", HEX["orange"], rough=0.5, emit=HEX["orange"], strength=1.5),  # 终审 P2b: 主字档位(预览分离已验证)
    "subglow": make_mat("NL_SubGlow", HEX["orange"], rough=0.5, emit=HEX["orange"], strength=1.0),   # 终审 P2b: 副标 0.8 临界 -> 1.0
    "bead":   make_mat("NL_BeadGlow", HEX["warm"], rough=0.5, emit=HEX["warm"], strength=2.0),  # P1-2: 骨爪指尖光珠
    "seat":   make_mat("NL_Seat",   HEX["seat"],   rough=0.8),
    "tire":   make_mat("NL_Tire",   "#1A1A20",     rough=0.95),
    "wheel":  make_mat("NL_Wheel",  HEX["metal_d"], rough=0.4, metal=0.9),
    "pumpkin": make_mat("NL_Pumpkin", HEX["orange"], rough=0.5,
                        emit=HEX["orange"], strength=0.55),
    "pumpface": make_mat("NL_PumpFace", HEX["orange"], rough=0.5, emit=HEX["green"], strength=5.0),
    "tail":   make_mat("NL_Tail",   HEX["red"],   rough=0.5, emit=HEX["red"], strength=3.5),
    "ground_prev": make_mat("NL_GroundPrev", HEX["ground_prev"], rough=1.0),
}

# ------------------------------------------------------------- mesh bags ---
class Bag:
    """按材质聚合顶点/面, 一次性 bpy.data 直建 (无 ops, 秒级)."""
    def __init__(self):
        self.verts = []
        self.faces = []
        self._smooth = False

    def add_sweep(self, frames, profile, close_ring=True, cap=True):
        """frames: [(pos,T,U)], profile: [(right,up)] 偏移."""
        n = len(frames)
        if n < 2: return
        base = len(self.verts)
        prof = profile + ([profile[0]] if close_ring else [])
        np_pts = len(prof)
        for pos, Tv, Uv in frames:
            Rv = Tv.cross(Uv)
            for (px, py) in prof:
                self.verts.append(pos + Rv * px + Uv * py)
        for i in range(n - 1):
            a0 = base + i * np_pts
            b0 = base + (i + 1) * np_pts
            for j in range(np_pts - 1):
                self.faces.append((a0 + j, a0 + j + 1, b0 + j + 1, b0 + j))
        if cap:
            for ring0 in (base, base + (n - 1) * np_pts):
                c = len(self.verts)
                cx = sum(self.verts[ring0 + j] for j in range(np_pts)) if False else None
                # 端帽: 极点扇形
                pos, Tv, Uv = frames[0] if ring0 == base else frames[-1]
                center = pos + Tv.cross(Uv) * sum(p[0] for p in profile) / len(profile) \
                         + Uv * sum(p[1] for p in profile) / len(profile)
                self.verts.append(center)
                for j in range(np_pts - 1):
                    if ring0 == base:
                        self.faces.append((ring0 + j, ring0 + j + 1, c, c))
                    else:
                        self.faces.append((ring0 + j + 1, ring0 + j, c, c))

    def add_box(self, center, R, Td, U, size):
        """正交框处放一个盒 (R/Td/U 为世界单位轴)."""
        hw, hl, hh = size[0] / 2, size[1] / 2, size[2] / 2
        base = len(self.verts)
        for sy in (-hl, hl):
            for sz in (-hh, hh):
                for sx in (-hw, hw):
                    self.verts.append(center + R * (sx) + Td * (sy) + U * (sz))
        f = base
        self.faces += [
            (f, f+1, f+3, f+2), (f+4, f+6, f+7, f+5),
            (f, f+4, f+5, f+1), (f+2, f+3, f+7, f+6),
            (f, f+2, f+6, f+4), (f+1, f+5, f+7, f+3),
        ]

    def add_beam(self, p1, p2, w, d):
        """两点间任意朝向盒梁 (侧轴自动取水平)."""
        p1, p2 = Vector(p1), Vector(p2)
        ax = (p2 - p1).normalized()
        side = ax.cross(Vector((0, 0, 1)))
        if side.length < 1e-4:
            side = Vector((1, 0, 0))
        side = side.normalized()
        up2 = side.cross(ax).normalized()
        self.add_box((p1 + p2) / 2, side, ax, up2, (w, (p2 - p1).length, d))

    def to_mesh(self, name, mat, smooth=False, collection=None, matrix=None):
        if not self.faces:
            return None
        if matrix is not None:
            verts = [tuple(matrix @ Vector(v)) for v in self.verts]
        else:
            verts = [tuple(v) for v in self.verts]
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], self.faces)
        me.validate()
        me.update()
        ob = bpy.data.objects.new(name, me)
        ob.data.materials.append(mat)
        if smooth:
            for poly in me.polygons:
                poly.use_smooth = True
        (collection or col_static).objects.link(ob)
        return ob

def frame_at(idx):
    pos, Tv, Uv, zn = RS[idx]
    return pos, Tv, Uv, zn

HO = P["heart_off"]        # 心线 -> 轨中心 (轨顶 = 心线 - HO - rail_r)
SP = P["spine_drop"]       # 轨面 -> 脊柱中心

# ------------------------------------------------------------- rails ------
bags = {k: Bag() for k in ("rail", "spine", "phos", "steel", "dog", "fin", "column", "foot", "bone", "dark",
                           "bead", "pumpface",
                           "plat", "plattop", "warmemit", "creamemit", "roof", "sign", "signphos")}
ring_prof = [(P["rail_r"] * cos(a), P["rail_r"] * sin(a)) for a in
             [i * 2 * pi / 8 for i in range(8)]]
spine_prof = [(P["spine_r"] * cos(a), P["spine_r"] * sin(a)) for a in
              [i * 2 * pi / 8 for i in range(8)]]
strip_prof = [(-0.035, -0.05), (0.035, -0.05), (0.035, 0.05), (-0.035, 0.05), (-0.035, -0.05)]

def offset_frames(idx_range, ox, oy):
    out = []
    for i in idx_range:
        pos, Tv, Uv, zn = RS[i]
        Rv = Tv.cross(Uv)
        out.append((pos + Rv * ox + Uv * oy, Tv, Uv))
    return out

step = 2   # 0.5m 采样 -> 1.0m 环距
idx_all = list(range(0, len(RS), step))
bags["rail"].add_sweep(offset_frames(idx_all, +P["gauge"] / 2, -HO), ring_prof)
bags["rail"].add_sweep(offset_frames(idx_all, -P["gauge"] / 2, -HO), ring_prof)
bags["spine"].add_sweep(offset_frames(idx_all, 0, -HO - SP), spine_prof)
bags["phos"].add_sweep(offset_frames(idx_all, +P["spine_r"] + 0.01, -HO - SP), strip_prof, cap=False)
bags["phos"].add_sweep(offset_frames(idx_all, -P["spine_r"] - 0.01, -HO - SP), strip_prof, cap=False)
tmark("rails+spine+phosphor swept")

# ------------------------------------------------------------- ties -------
tie_box_w, tie_box_l, tie_box_h = P["gauge"] + 0.42, 0.09, 0.15
rod_len = hypot(P["gauge"] / 2, SP - 0.05)
n_ties = int(len(RS) * P["ds_out"] / P["tie_step"])
for k in range(n_ties):
    i = min(len(RS) - 1, int(k * P["tie_step"] / P["ds_out"]))
    pos, Tv, Uv, zn = RS[i]
    s = i * P["ds_out"]
    Rv = Tv.cross(Uv)
    rail_c = pos - Uv * HO
    bags["steel"].add_box(rail_c, Rv, Tv, Uv, (tie_box_w, tie_box_l, tie_box_h))
    # 轨->脊柱 斜撑 x2
    spine_c = rail_c - Uv * SP
    for sgn in (1, -1):
        a = rail_c + Rv * (sgn * P["gauge"] / 2)
        mid = (a + spine_c) / 2
        d = (spine_c - a)
        L = d.length
        dirv = d.normalized()
        side = Rv - dirv * Rv.dot(dirv)
        if side.length < 1e-5: continue
        side = side.normalized()
        up2 = dirv.cross(side).normalized()
        bags["steel"].add_box(mid, side, dirv, up2, (0.07, L, 0.07))
    # 提升段防逆棘齿 / 刹车鳍片
    if zn == "lift":
        for sgn in (1, -1):
            bags["dog"].add_box(rail_c + Rv * (sgn * 0.30) + Uv * 0.10,
                                Rv, Tv, Uv, (0.10, 0.16, 0.10))
    elif zn in ("brake", "brakes"):        # 刹车鳍 (P1: 原zone"brakes"从未触发, 已无此zone)
        bags["fin"].add_box(rail_c - Uv * 0.45, Rv, Tv, Uv, (0.06, 0.55, 0.18))
tmark(f"ties: {n_ties}")

# 提升链条 (轨面中央细轨)
lift_frames = [i for i in idx_all if zone_at(i * P["ds_out"]) == "lift"]
if lift_frames:
    bags["steel"].add_sweep(offset_frames(lift_frames, 0, -HO + 0.05),
                            [(-0.05, -0.03), (0.05, -0.03), (0.05, 0.03), (-0.05, 0.03), (-0.05, -0.03)],
                            cap=False)
tmark("chain")

# ------------------------------------------------------------- supports ---
STATION_BOX = (6.5, 17.0, 40.0, 70.0)   # x0,x1,y0,y1 站台区不落柱
def in_station(x, y):
    return STATION_BOX[0] <= x <= STATION_BOX[1] and STATION_BOX[2] <= y <= STATION_BOX[3]

n_sup = int(t._s / P["support_step"])
sup_idx = set()
for k in range(1, n_sup):
    s = k * P["support_step"]
    i = min(len(RS) - 1, int(s / P["ds_out"]))
    pos, Tv, Uv, zn = RS[i]
    if zn in ("loop", "corkscrew", "zerog", "station_in", "brake"):
        continue   # 翻转段改主题骨爪支撑; 刹车段脊柱 z<1.2 本就不落柱
    spine_pt = pos - Uv * (HO + SP)
    if in_station(pos.x, pos.y):
        continue
    sup_idx.add(i)
    gx, gy, top_z = spine_pt.x, spine_pt.y, spine_pt.z
    if top_z < 1.2:
        continue
    bags["column"].add_beam((gx, gy, 0.0), (gx, gy, top_z), 0.52 if top_z > 12 else 0.4, 0.52 if top_z > 12 else 0.4)
    bags["foot"].add_box(Vector((gx, gy, 0.22)), Vector((1, 0, 0)), Vector((0, 1, 0)),
                         Vector((0, 0, 1)), (1.7, 1.7, 0.44))
    if top_z > 14:
        side = Vector((-Tv.y, Tv.x, 0)).normalized()
        for sgn in (1, -1):
            base = Vector((gx, gy, 0)) + side * (sgn * 3.2)
            bags["column"].add_beam(base, spine_pt - Uv * 0.0 + Vector((0, 0, 0)) , 0.16, 0.16)
tmark(f"supports: {len(sup_idx)}")

# ------------------------- 翻转段主题支撑 (P1, 用户选定: 骨爪/墓碑语汇) ----------
# loop/corkscrew/zerog 原来零支撑 (33% 轨道悬空). 方案: 竖骨柱(弧线渐细) + 横臂 + 三指环扣脊柱,
# 回环加墓碑环列. 所有柱折线对全轨心线+脊柱点做 1.35m 碰撞自查, 碰撞即弃柱 (确定性安全网).
SP_R = P["spine_r"]
TRACK_PTS = []
for _r in RS[::4]:
    TRACK_PTS.append(_r[0])
    TRACK_PTS.append(_r[0] - _r[2] * (HO + SP))   # 脊柱点

def bone_chain(bag, pts, w0, w1):
    """折线骨梁, 宽度渐细."""
    for _k in range(len(pts) - 1):
        _w = w0 + (w1 - w0) * (_k / max(1, len(pts) - 2))
        bag.add_beam(pts[_k], pts[_k + 1], _w, _w)

def claw_grip(i, side, lat):
    """竖骨柱 + 横臂 + 三指环扣样本 i 的脊柱. 返回是否成功落柱."""
    pos, Tv, Uv, zn = RS[i]
    Rv = Tv.cross(Uv).normalized()
    spine_c = pos - Uv * (HO + SP)
    top = spine_c + Rv * (side * lat)
    base = Vector((top.x, top.y, 0.0))
    mid = (base + top) / 2 + Rv * (side * -0.3)
    # 碰撞自查: 柱折线采样点距任何轨心线/脊柱点 < 1.35m 则弃
    for _u in range(11):
        _p = base.lerp(mid, min(1.0, _u / 5.0)) if _u < 5 else mid.lerp(top, (_u - 5) / 5.0)
        for _tp in TRACK_PTS:
            if (_tp - _p).length < 1.35:
                return False
    bone_chain(bags["bone"], [base, mid, top], 0.34, 0.20)
    arm_to = spine_c + Rv * (side * (SP_R + 0.35))
    bags["bone"].add_beam(top, arm_to, 0.18, 0.18)
    # 三指: 绕脊柱 (轴=Tv) 的环扣弧, 沿轴错开; 指尖各缀一颗暖光珠 (P1-2 幽冥上夜班)
    for _off in (-0.16, 0.0, 0.16):
        arc = []
        a0 = 0.0 if side > 0 else pi
        for _k in range(6):
            _a = a0 + (_k / 5) * radians(150) * (1 if side > 0 else -1)
            arc.append(spine_c + Tv * _off + (Rv * cos(_a) + Uv * sin(_a)) * (SP_R + 0.13))
        bone_chain(bags["bone"], arc, 0.09, 0.05)
        bags["bead"].add_box(arc[-1] + (arc[-1] - arc[-2]).normalized() * 0.02,
                             Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)), (0.05, 0.05, 0.05))
    bags["foot"].add_box(Vector((base.x, base.y, 0.22)), Vector((1, 0, 0)),
                         Vector((0, 1, 0)), Vector((0, 0, 1)), (1.1, 1.1, 0.44))
    return True

_loop_idx = [i for i, r in enumerate(RS) if r[3] == "loop"]
if len(_loop_idx) > 6:
    _zls = [RS[i][0].z for i in _loop_idx]
    _z_lo, _z_hi = min(_zls), max(_zls)
    _top_i = _loop_idx[_zls.index(_z_hi)]
    _z_grip = _z_lo + (_z_hi - _z_lo) * 0.50
    _asc = [i for i in _loop_idx if i < _top_i and RS[i][0].z <= _z_grip]
    _desc = [i for i in _loop_idx if i > _top_i and RS[i][0].z <= _z_grip]
    _grips = ([max(_asc)] if _asc else []) + ([min(_desc)] if _desc else [])
    _n_claw = sum(1 for _sd in (1, -1) for _gi in _grips if claw_grip(_gi, _sd, 1.9))
    # 墓碑环列 (环底外围, 碰轨即跳)
    _lc = (RS[_loop_idx[0]][0] + RS[_loop_idx[-1]][0] + RS[_top_i][0]) / 3
    _lc = Vector((_lc.x, _lc.y, 0.0))
    _n_ts = 0
    for _k in range(9):
        _a = _k / 9 * 2 * pi + 0.35
        _tc = _lc + Vector((cos(_a), sin(_a), 0)) * 9.5
        if min((_tp - _tc).length for _tp in TRACK_PTS) < 2.0:
            continue
        _rz = radians(18.0 * ((_k % 3) - 1))
        _d = Vector((cos(_rz), sin(_rz), 0))
        _s2 = Vector((-sin(_rz), cos(_rz), 0))
        bags["bone"].add_box(Vector((_tc.x, _tc.y, 0.55)), _d, _s2, Vector((0, 0, 1)), (0.18, 0.62, 1.10))
        bags["bone"].add_box(Vector((_tc.x, _tc.y, 1.10)), _d, _s2, Vector((0, 0, 1)), (0.14, 0.46, 0.26))
        # P1-2: 墓碑面向环心的一对暗绿"眼" (夜里读出墓碑群)
        _in = Vector((-cos(_a), -sin(_a), 0)) * 0.105
        _pp = Vector((-sin(_a), cos(_a), 0)) * 0.10
        for _eye in (_pp, -1 * _pp):
            bags["pumpface"].add_box(Vector((_tc.x, _tc.y, 0.72)) + _in + _eye,
                                     _d, _s2, Vector((0, 0, 1)), (0.05, 0.03, 0.09))
        _n_ts += 1
    print(f"THEME loop: claws={_n_claw}/{2 * len(_grips)}, tombstones={_n_ts}")

for _zn2, _fr in (("corkscrew", (0.12, 0.88)), ("zerog", (0.3, 0.7))):
    _zi = [i for i, r in enumerate(RS) if r[3] == _zn2]
    if not _zi:
        continue
    _clusters, _cur = [], [_zi[0]]
    for _i in _zi[1:]:
        if _i - _cur[-1] > 12:
            _clusters.append(_cur)
            _cur = [_i]
        else:
            _cur.append(_i)
    _clusters.append(_cur)
    _ok = sum(1 for _cl in _clusters for _f in _fr
              if claw_grip(_cl[min(len(_cl) - 1, int(len(_cl) * _f))], 1 if _f < 0.5 else -1, 1.6))
    print(f"THEME {_zn2}: claws={_ok}")
tmark("theme supports")

# ------------------------------------------------------------- station ----
SX, SY0, SY1 = 11.5, 44.0, 66.0
PLAT_H = 2.33                 # P1: 站台面≈车厢地板顶(2.38), 登车近零高差 (原 2.78 高出地板 0.41m)
PLAT_IN = 0.75                # P1: 站台内缘距心线 (车最宽 0.661 + 0.089 间隙; 原 0.6125 嵌车)
for sgn in (-1, 1):
    cx = SX + sgn * (PLAT_IN + 1.35)
    half_w = 1.35
    bags2 = Bag()
    center = Vector((cx, (SY0 + SY1) / 2, PLAT_H / 2))
    bags["plat"].add_box(center, Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)),
                         (half_w * 2, SY1 - SY0, PLAT_H))
    bags["plattop"].add_box(Vector((cx, (SY0 + SY1) / 2, PLAT_H + 0.02)),
                            Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)),
                            (half_w * 2, SY1 - SY0, 0.06))
    # 站台边缘暖光灯带 (P1: 移到内立面外表面, 原埋进站台体内不可见)
    edge_x = SX + sgn * (PLAT_IN - 0.04)
    bags["warmemit"].add_box(Vector((edge_x, (SY0 + SY1) / 2, PLAT_H - 0.30)),
                             Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)),
                             (0.06, SY1 - SY0 - 1.0, 0.08))
# 站台端部阶梯台 (单向环路动线 fix: 西=唯一入口[侧墙+1.5m阶梯槽+闸机], 东=唯一出口[侧墙+1.8m槽])
# 每级 0.34 高 x 0.514 深, 顶级 2.38 与站台面齐平; 两侧实心墙与站台面齐平 -> 阶梯不可侧向攀入
for sgn, _slot_w in ((-1, 1.5), (1, 1.8)):
    cx = SX + sgn * (PLAT_IN + 1.35)
    _half = 1.35 - _slot_w / 2       # 侧墙厚度
    for _sw in (-1, 1):              # 两侧实心墙 (全高, 即阶梯槽侧壁)
        bags["plat"].add_box(Vector((cx + _sw * (_slot_w / 2 + _half / 2), SY0 - 1.6, PLAT_H / 2 + 0.05)),
                             Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)),
                             (_half, 3.6, PLAT_H + 0.05))
    for _k5 in range(7):             # 中央阶梯槽
        _h5 = 0.34 * (_k5 + 1)
        _yc5 = (SY0 - 1.6) - 1.8 + (_k5 + 0.5) * (3.6 / 7)
        bags["plat"].add_box(Vector((cx, _yc5, _h5 / 2)), Vector((1, 0, 0)),
                             Vector((0, 1, 0)), Vector((0, 0, 1)), (_slot_w, 3.6 / 7, _h5))
        bags["bead"].add_box(Vector((cx, _yc5 - (3.6 / 7) / 2 + 0.03, _h5 + 0.011)),
                             Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)),
                             (_slot_w, 0.05, 0.02))          # 终审 P2c: 踏面前缘夜光条
# 登台口铺面 (迷宫出口 -> 闸机的进场走廊地面, y 39.2-40.6)
bags["dark"].add_box(Vector((7.6, 39.9, 0.015)), Vector((1, 0, 0)), Vector((0, 1, 0)),
                     Vector((0, 0, 1)), (3.4, 1.2, 0.03))
# 雨棚柱 + 顶 (P1: 柱落地, 原起于 PLAT_H 悬空 2.7m 断头)
for sx_ in (SX - 4.0, SX + 4.0):
    for yy in (SY0 + 1.5, (SY0 + SY1) / 2, SY1 - 1.5):
        bags["column"].add_beam((sx_, yy, 0.0), (sx_, yy, 7.4), 0.22, 0.22)
bags["roof"].add_box(Vector((SX, (SY0 + SY1) / 2, 7.55)), Vector((1, 0, 0)),
                     Vector((0, 1, 0)), Vector((0, 0, 1)), (11.0, SY1 - SY0 + 2.5, 0.3))
bags["roof"].add_box(Vector((SX, (SY0 + SY1) / 2, 7.2)), Vector((1, 0, 0)),
                     Vector((0, 1, 0)), Vector((0, 0, 1)), (11.4, SY1 - SY0 + 2.9, 0.12))
# 雨棚灯串 (三线垂弧) — P2: 裸方块灯升级迷你南瓜灯 (八棱旋转体, 交替橙/暖白自发光)
def pumpkin_lantern(bag, cx, cy, cz, r):
    prof = [(-0.55 * r, 0.32 * r), (-0.30 * r, 0.72 * r), (0.0, 0.95 * r),
            (0.30 * r, 0.72 * r), (0.55 * r, 0.30 * r)]     # (dz, dr) 瓜身轮廓
    sides = 8
    base = len(bag.verts)
    for (dz, dr) in prof:
        for q in range(sides):
            a = q / sides * 2 * pi
            bag.verts.append(Vector((cx + cos(a) * dr, cy + sin(a) * dr, cz + dz)))
    for li in range(len(prof) - 1):
        for q in range(sides):
            q2 = (q + 1) % sides
            bag.faces.append((base + li * sides + q, base + li * sides + q2,
                              base + (li + 1) * sides + q2, base + (li + 1) * sides + q))
    for li in (0, len(prof) - 1):                            # 顶/底凹盖 (扇形)
        c_idx = len(bag.verts)
        bag.verts.append(Vector((cx, cy, cz + prof[li][0])))
        top = base + li * sides
        for q in range(sides):
            bag.faces.append((top + q, top + (q + 1) % sides, c_idx, c_idx))
    R = Vector((1, 0, 0)); Td = Vector((0, 1, 0)); U2 = Vector((0, 0, 1))
    bags["dark"].add_box(Vector((cx, cy, cz + 0.55 * r)), R, Td, U2, (0.035, 0.035, 0.06))  # 瓜蒂

for k, lx in enumerate((SX - 3.4, SX, SX + 3.4)):
    n_l = int((SY1 - SY0 + 2.0) / 1.3)
    for j in range(n_l + 1):
        u = j / n_l
        yy = (SY0 - 1.0) + u * (SY1 - SY0 + 2.0)
        sag = 0.42 * sin(pi * u)
        zz = 7.15 - sag
        pumpkin_lantern(bags["warmemit"] if (j % 2) == 0 else bags["creamemit"],
                        lx, yy, zz - 0.12, 0.165)
# 立面站牌 (北端龙门)
for sx_ in (SX - 5.2, SX + 5.2):
    bags["column"].add_beam((sx_, SY1 + 1.2, 0), (sx_, SY1 + 1.2, 9.6), 0.3, 0.3)
bags["sign"].add_box(Vector((SX, SY1 + 1.2, 9.0)), Vector((1, 0, 0)),
                     Vector((0, 1, 0)), Vector((0, 0, 1)), (10.4, 0.25, 1.7))
bags["signphos"].add_box(Vector((SX, SY1 + 1.08, 9.0)), Vector((1, 0, 0)),
                         Vector((0, 1, 0)), Vector((0, 0, 1)), (10.55, 0.1, 1.85))
# 站牌发光大字 + FONT 文本基建 (A5 车厢号 / A6 统计牌复用; 统一在列车落位后转网格)
_fnt = None
try:
    _fnt = bpy.data.fonts.load("C:/Windows/Fonts/msyh.ttc")
except Exception as _e:
    print(f"FONT_FAIL {type(_e).__name__} {_e}")

def text_mesh(name, body, size, loc, mat, rot=(90, 0, 0), space=1.0, extrude=0.03):
    if _fnt is None:
        return None
    _cu = bpy.data.curves.new(name + "C", type="FONT")
    _cu.body = body
    _cu.font = _fnt
    _cu.size = size
    _cu.extrude = extrude
    _cu.align_x = "CENTER"
    _cu.space_character = space
    _cu.materials.append(mat)
    _ob = bpy.data.objects.new(name, _cu)
    _ob.location = loc
    _ob.rotation_euler = (radians(rot[0]), radians(rot[1]), radians(rot[2]))
    col_static.objects.link(_ob)
    return _ob

if _fnt:
    _sign_face_y = SY1 + 1.2 - 0.155          # 站牌南立面
    text_mesh("NL_SignText", "幽冥回环", 1.15, (SX, _sign_face_y, 9.26), M["signglow"],
              space=1.18)                      # P1-1: 字距+18% 防 33m 亮核融合
    text_mesh("NL_SignTextB", "NETHER LOOP", 0.40, (SX, _sign_face_y, 8.44), M["subglow"], space=1.18)
# 排队迷宫 (A1/M3): 灯环西侧蛇形回廊 4 折 ~17m, 避开轨道回流走廊(x~11.5)与地面灯环带
# (x3.2-6.0 在灯环外缘 6.2 以西; 出口导栏绕环北缘接西端坡道)
def queue_fence(x0, y0, x1, y1):
    L = hypot(x1 - x0, y1 - y0)
    n = max(2, int(L / 2.2))
    for k in range(n + 1):
        u = k / n
        px, py = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
        bags["column"].add_beam((px, py, 0), (px, py, 1.1), 0.09, 0.09)
    for hz in (0.55, 1.05):
        for k in range(n):
            u0, u1 = k / n, (k + 1) / n
            bags["steel"].add_beam(
                Vector((x0 + (x1 - x0) * u0, y0 + (y1 - y0) * u0, hz)),
                Vector((x0 + (x1 - x0) * u1, y0 + (y1 - y0) * u1, hz)), 0.06, 0.1)
    for k in range(n):                                # 终审 P2c: 顶轨暖白低档光帽 (夜态动线引导)
        u0, u1 = k / n, (k + 1) / n
        bags["bead"].add_beam(
            Vector((x0 + (x1 - x0) * u0, y0 + (y1 - y0) * u0, 1.10)),
            Vector((x0 + (x1 - x0) * u1, y0 + (y1 - y0) * u1, 1.10)), 0.028, 0.028)

for _q in ((3.2, 30.6, 6.0, 30.6),    # 南墙
           (3.2, 30.6, 3.2, 39.8),    # 西墙
           (6.0, 32.2, 6.0, 39.8),    # 东墙 (南端 y30.6-32.2 留入口)
           (4.6, 32.9, 6.0, 32.9),    # 齿1 东起 -> 西通口
           (3.2, 35.2, 4.6, 35.2),    # 齿2 西起 -> 东通口
           (4.6, 37.5, 6.0, 37.5),    # 齿3 东起 -> 西通口
           (3.2, 39.8, 5.0, 39.8)):   # 北墙 (x5.0-6.0 留出口, 即唯一入口)
    queue_fence(*_q)
# 进场走廊封闭 (终审 P0 修复): c 墙原为单段横贯西槽口(8.65-10.15)封死唯一登台路 -> 拆两段, 槽口让给闸机线
for _q in ((6.0, 39.8, 6.0, 44.2),     # a: 迷宫东墙北延, 封西侧至站台角
           (6.0, 44.2, 8.05, 44.2),    # b: 西北口袋北封 (接西阶梯侧墙)
           (6.0, 40.6, 8.05, 40.6),    # c1: 走廊北墙西段 (至西侧墙, 不越槽口)
           (10.75, 40.6, 12.25, 40.6), # c2: 走廊北墙东段 (东侧墙->东端块, 仍封轨道沟南缘)
           (6.0, 39.2, 12.25, 39.2)):  # d: 走廊南墙 (唯一进口=迷宫缺口, 唯一出口=过闸)
    queue_fence(*_q)

# --- A2 验票闸门 x2 (终审 P0: 闸线横跨槽口本身, 行进向 +Y, 双转子全宽, 闸即门) ---
for _gx in (8.65, 9.4, 10.15):                      # 三柱 (槽口两缘+中)
    bags["column"].add_beam((_gx, 40.4, 0), (_gx, 40.4, 1.15), 0.07, 0.07)
bags["steel"].add_beam(Vector((8.65, 40.4, 0.12)), Vector((10.15, 40.4, 0.12)), 0.06, 0.06)  # 底梁
bags["steel"].add_beam(Vector((8.65, 40.4, 1.12)), Vector((10.15, 40.4, 1.12)), 0.06, 0.06)  # 顶梁
for _gi, _gx in enumerate((9.03, 9.78)):
    bags["dark"].add_box(Vector((_gx, 40.4, 0.33)), Vector((1, 0, 0)), Vector((0, 1, 0)),
                         Vector((0, 0, 1)), (0.55, 0.22, 0.66))          # 柜体封 0-0.66
    for _aa in (90, 210, 330):                       # 三臂闸翼 (轴沿 X, 行进向 +Y)
        _ar = radians(_aa)
        bags["phos"].add_beam(Vector((_gx, 40.4, 0.95)),
                              Vector((_gx, 40.4 + 0.30 * cos(_ar), 0.95 + 0.30 * sin(_ar))), 0.035, 0.035)
    _ge = bpy.data.objects.new(f"NL_Gate_{_gi}", None)     # M3/M4 闸翼开合锚点
    _ge.location = (_gx, 40.4, 0.95)
    col_static.objects.link(_ge)
# 出口标识: 东阶梯槽南侧「出口 EXIT」+ 基座东翼导栏 (终审 P2: 柱位东移避灯环带, 距环心 >4.8)
queue_fence(15.0, 40.6, 15.9, 39.4)
for _sp in ((13.4, 39.05), (14.1, 39.05)):
    bags["column"].add_beam((_sp[0], _sp[1], 0), (_sp[0], _sp[1], 1.9), 0.07, 0.07)
bags["steel"].add_beam(Vector((13.4, 39.05, 1.82)), Vector((14.1, 39.05, 1.82)), 0.05, 0.05)
text_mesh("NL_ExitSign", "出口 EXIT", 0.24, (13.75, 38.97, 1.45), M["oglow"], rot=(90, 0, 0), extrude=0.02)
# 东出口反向上行阻挡 (M4 单向逻辑前的视觉栏): 三低桩 + 「仅下行」小牌
for _sx3 in (12.95, 13.6, 14.25):
    bags["dark"].add_box(Vector((_sx3, 40.5, 0.25)), Vector((1, 0, 0)), Vector((0, 1, 0)),
                         Vector((0, 0, 1)), (0.08, 0.08, 0.5))
bags["dark"].add_box(Vector((13.6, 40.38, 0.95)), Vector((1, 0, 0)), Vector((0, 1, 0)),
                     Vector((0, 0, 1)), (0.62, 0.05, 0.30))
text_mesh("NL_ExitDown", "↓ 仅下行", 0.17, (13.6, 40.33, 0.95), M["oglow"], rot=(90, 0, 0), extrude=0.012)

# --- A3 发车钟 (西站台北端: 立柱+吊臂+铜钟, 暗铜微光) ---
def bell_lathe(cx, cy, cz_top, h, r_max):
    prof = [(0.00, 0.30 * r_max), (0.18 * h, 0.62 * r_max), (0.55 * h, 0.95 * r_max),
            (0.82 * h, r_max), (h, 0.55 * r_max)]
    sides = 10
    base = len(bags["dark"].verts)     # 终审 P3: 钟体改暗铁 (原 NL_Dog 刹车红语义误用)
    for (dz, dr) in prof:
        for q in range(sides):
            a = q / sides * 2 * pi
            bags["dark"].verts.append(Vector((cx + cos(a) * dr, cy + sin(a) * dr, cz_top - dz)))
    for li in range(len(prof) - 1):
        for q in range(sides):
            q2 = (q + 1) % sides
            bags["dark"].faces.append((base + li * sides + q, base + li * sides + q2,
                                       base + (li + 1) * sides + q2, base + (li + 1) * sides + q))
    c_idx = len(bags["dark"].verts)
    bags["dark"].verts.append(Vector((cx, cy, cz_top)))
    for q in range(sides):
        bags["dark"].faces.append((base + q, base + (q + 1) % sides, c_idx, c_idx))

bags["column"].add_beam((9.4, 65.2, PLAT_H + 0.05), (9.4, 65.2, 3.62), 0.07, 0.07)
bags["steel"].add_beam(Vector((9.4, 65.2, 3.58)), Vector((9.78, 65.2, 3.58)), 0.05, 0.05)
bell_lathe(9.78, 65.2, 3.56, 0.24, 0.11)
bags["dark"].add_box(Vector((9.78, 65.2, 3.30)), Vector((1, 0, 0)), Vector((0, 1, 0)),
                     Vector((0, 0, 1)), (0.05, 0.05, 0.10))                  # 钟舌

# --- A4 暗夜紫幡旗 (雨棚南北檐口三角旗串, 双面) ---
for _fy in (SY0 + 0.25, SY1 - 0.25):
    _fx = 6.3
    while _fx < 16.7:
        _b0 = len(bags["sign"].verts)
        bags["sign"].verts += [Vector((_fx, _fy, 7.32)), Vector((_fx + 0.30, _fy, 7.32)),
                               Vector((_fx + 0.15, _fy, 6.86))]
        bags["sign"].faces.append((_b0, _b0 + 1, _b0 + 2))
        bags["sign"].faces.append((_b0, _b0 + 2, _b0 + 1))                   # 背面
        _fx += 1.5

# --- A5 站台防滑条 (双侧, 暗色横条) ---
for _cx2 in (SX - 2.1, SX + 2.1):
    _yy = 44.8
    while _yy < 65.4:
        bags["dark"].add_box(Vector((_cx2, _yy, PLAT_H + 0.057)), Vector((1, 0, 0)),
                             Vector((0, 1, 0)), Vector((0, 0, 1)), (2.2, 0.10, 0.014))
        _yy += 1.1

# --- A6 彩蛋三件: 回环内侧可走观景台 / 螺旋下南瓜田一角 / 尖叫统计牌(静态) ---
_li2 = [i for i, r in enumerate(RS) if r[3] == "loop"]
if _li2:
    _lx = sum(RS[i][0].x for i in _li2) / len(_li2)
    _lys = [RS[i][0].y for i in _li2]
    _lcy = (min(_lys) + max(_lys)) / 2
    _r_in = (max(_lys) - min(_lys)) / 2 - 2.6          # 环内净空 (扣轨/脊柱结构)
    if _r_in >= 2.2:
        _tw = min(1.6, _r_in * 0.42)                   # 平台半宽
        # 环底弧 (heart z≈2.9) 从环心正下方跨过, 爬升段在 y~99-103/z3-4.5 穿越车体包络 ->
        # 柱立轨带外侧 x±3.3, 悬臂梁抬台到 z6.5 (该高度轨管已退到 y±3.8, 台下乘客头顶净空 ~2.3m)
        for _sx2 in (-1, 1):
            for _sy2 in (-0.9, 0.9):
                bags["column"].add_beam((_lx + _sx2 * 3.3, _lcy + _sy2, 0),
                                        (_lx + _sx2 * 3.3, _lcy + _sy2, 7.1), 0.13, 0.13)
        for _sy2 in (-0.9, 0.9):
            bags["steel"].add_beam(Vector((_lx - 3.3, _lcy + _sy2, 7.05)),
                                   Vector((_lx + 3.3, _lcy + _sy2, 7.05)), 0.10, 0.12)
        bags["plattop"].add_box(Vector((_lx, _lcy, 7.22)), Vector((1, 0, 0)), Vector((0, 1, 0)),
                                Vector((0, 0, 1)), (_tw * 2 + 0.2, _tw * 2 + 0.2, 0.12))
        for _e0, _e1 in (((-_tw, -_tw), (_tw, -_tw)), ((_tw, -_tw), (_tw, _tw)),
                         ((_tw, _tw), (-_tw, _tw)), ((-_tw, _tw), (-_tw, -_tw))):
            _p0 = Vector((_lx + _e0[0], _lcy + _e0[1], 0))
            _p1 = Vector((_lx + _e1[0], _lcy + _e1[1], 0))
            _nl = (_p1 - _p0).length
            _n2 = max(2, int(_nl / 1.6))
            for _k3 in range(_n2 + 1):
                _pp = _p0.lerp(_p1, _k3 / _n2)
                bags["column"].add_beam((_pp.x, _pp.y, 7.28), (_pp.x, _pp.y, 8.35), 0.05, 0.05)
            for _hz2 in (7.65, 8.20):
                bags["steel"].add_beam(Vector((_p0.x, _p0.y, _hz2)), Vector((_p1.x, _p1.y, _hz2)), 0.045, 0.06)
        # 东侧块式楼梯 18 级 x0.40/级 (终审 P2a: 0.42 超步高契约 0.40; 顶 7.20≈台面 7.22)
        for _k4 in range(18):
            bags["plattop"].add_box(Vector((_lx + 5.86 - _k4 * 0.27, _lcy, 0.20 * (_k4 + 1))),
                                    Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)),
                                    (0.27, 1.10, 0.40 * (_k4 + 1)))
        bags["plattop"].add_box(Vector((_lx + 1.35, _lcy, 7.22)), Vector((1, 0, 0)),
                                Vector((0, 1, 0)), Vector((0, 0, 1)), (1.4, 1.30, 0.12))
        print(f"A6_TOWER ({_lx:.1f},{_lcy:.1f}) 半宽{_tw:.2f} 悬臂台 z7.2 净空{_r_in:.2f}")
# 南瓜田一角 (双螺丝钻下方, 九颗发光南瓜)
for _pk in ((80.2, 11.0, 0.30), (81.6, 10.2, 0.22), (82.9, 11.4, 0.26), (84.1, 10.6, 0.19),
            (80.8, 12.6, 0.24), (83.5, 12.9, 0.28), (82.0, 14.0, 0.20), (84.6, 13.8, 0.23),
            (81.3, 15.7, 0.26)):
    pumpkin_lantern(bags["warmemit"], _pk[0], _pk[1], _pk[2] * 0.58 + 0.02, _pk[2])
# 尖叫统计牌 (零重力滚段旁, 静态面; 柱封板两端 y37/39)
for _sp in ((84.5, 37.0), (84.5, 39.0)):
    bags["column"].add_beam((_sp[0], _sp[1], 0), (_sp[0], _sp[1], 3.1), 0.10, 0.10)
bags["sign"].add_box(Vector((84.5, 38.0, 2.72)), Vector((1, 0, 0)), Vector((0, 1, 0)),
                     Vector((0, 0, 1)), (0.10, 2.0, 1.15))
text_mesh("NL_ScreamSign", "本季尖叫 8642 次", 0.26, (84.44, 38.0, 2.72), M["oglow"],
          rot=(90, 0, -90), extrude=0.02)   # 立起再转面西: 阅读方向-Y, 字头+Z
# 地面灯环 (站前小广场; 单向环路 fix: 南移缩小让出进场走廊带 y39.2-40.6)
ring_bag = Bag()
RC = Vector((SX + 0.4, 34.3, 0.06))
for a in range(48):
    a0 = a / 48 * 2 * pi
    a1 = (a + 1) / 48 * 2 * pi
    r0, r1 = 4.2, 4.8
    p00 = Vector((SX + 0.4 + r0 * cos(a0), 34.3 + r0 * sin(a0), 0.06))
    p01 = Vector((SX + 0.4 + r1 * cos(a0), 34.3 + r1 * sin(a0), 0.06))
    p10 = Vector((SX + 0.4 + r0 * cos(a1), 34.3 + r0 * sin(a1), 0.06))
    p11 = Vector((SX + 0.4 + r1 * cos(a1), 34.3 + r1 * sin(a1), 0.06))
    base = len(ring_bag.verts)
    ring_bag.verts += [p00, p01, p11, p10]
    ring_bag.faces.append((base, base + 1, base + 2, base + 3))
tmark("station")

# ------------------------------------------------------------- train ------
# 幽冥回环列车 v2 —— 幽灵灯笼车头 + 肩式压肩 + 三件套走行部 (TRAIN_BRIEF v1.0)
# 局部坐标系: x=右, y=前进, z=上, 原点=心线; 轨面 z=-HO; 建模后按车位姿矩阵落位.
CAR_N = 6
CAR_GAP = 2.35
HO = P["heart_off"]
RAIL_Z = -HO                       # 轨顶基准 (轨中心)
ROW_Y = (0.32, -0.42)              # 两排座椅纵向位

M["bone"] = make_mat("NL_Bone", "#E8D9B8", rough=0.7)
M["leaf"] = make_mat("NL_Leaf", "#2A4030", rough=0.85)

st_idx = [i for i, r in enumerate(RS) if r[3] == "station"]
mid_i = st_idx[len(st_idx) // 2] if st_idx else 0

train_root = bpy.data.objects.new("NL_TrainRoot", None)
train_root.empty_display_size = 1.0
col_train.objects.link(train_root)

def parent_keep(child, parent):
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()

# ------------------------------------------------------- 局部建模工具 ---
def bag_tube(bag, pts, r, sides=8, taper_to=None):
    """任意 3D 折线扫掠圆管 (平行传输标架)."""
    pts = [Vector(q) for q in pts]
    n = len(pts)
    if n < 2:
        return
    tang = []
    for i in range(n):
        a = pts[max(0, i - 1)]
        b = pts[min(n - 1, i + 1)]
        tang.append((b - a).normalized())
    ref = Vector((1, 0, 0)) if abs(tang[0].x) < 0.9 else Vector((0, 1, 0))
    nv = (ref - tang[0] * ref.dot(tang[0])).normalized()
    rings = []
    for i in range(n):
        if i > 0:
            ax = tang[i - 1].cross(tang[i])
            if ax.length > 1e-6:
                nv = rot_about(nv, ax.normalized(), tang[i - 1].angle(tang[i]))
            nv = (nv - tang[i] * nv.dot(tang[i])).normalized()
        bv = tang[i].cross(nv)
        rr = r if taper_to is None else r + (taper_to - r) * i / (n - 1)
        ring = []
        for k in range(sides):
            a = k / sides * 2 * pi
            ring.append(pts[i] + nv * cos(a) * rr + bv * sin(a) * rr)
        rings.append(ring)
    base = len(bag.verts)
    for ring in rings:
        bag.verts.extend(ring)
        bag.verts.append(ring[0])
    for i in range(n - 1):
        for k in range(sides):
            a0 = base + i * (sides + 1) + k
            b0 = base + (i + 1) * (sides + 1) + k
            bag.faces.append((a0, a0 + 1, b0 + 1, b0))

def bag_lathe(bag, profile, sides=8, y_center=0.0, axis="Z", close_top=False):
    """旋转体: profile=[(height, radius)], 绕局部轴."""
    base = len(bag.verts)
    for (h, rr) in profile:
        for k in range(sides):
            a = k / sides * 2 * pi
            if axis == "Z":
                bag.verts.append(Vector((cos(a) * rr, y_center + sin(a) * rr, h)))
            else:
                bag.verts.append(Vector((cos(a) * rr, h, sin(a) * rr)))
    for i in range(len(profile) - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            a0 = base + i * sides + k
            a1 = base + i * sides + k2
            b0 = base + (i + 1) * sides + k
            b1 = base + (i + 1) * sides + k2
            bag.faces.append((a0, b0, b1, a1))
    if close_top and len(profile) >= 2:
        h, rr = profile[-1]
        c = len(bag.verts)
        bag.verts.append(Vector((0, y_center, h)) if axis == "Z" else Vector((0, h, 0)))
        top = base + (len(profile) - 1) * sides
        for k in range(sides):
            bag.faces.append((top + k, top + (k + 1) % sides, c, c))

def make_wheel_obj(name, i_c, parent, car_mat, local_pos, r=0.15, w=0.10):
    """独立车轮对象 (轴沿局部X, three.js 转 rotation.x 即滚动)."""
    bag = Bag()
    # 胎面: 双环圆柱 axis X
    n_seg = 14
    for x in (-w / 2, w / 2):
        ring = []
        for k in range(n_seg):
            a = k / n_seg * 2 * pi
            ring.append(Vector((x, cos(a) * r, sin(a) * r)))
        bag.verts.extend(ring)
    for k in range(n_seg):
        k2 = (k + 1) % n_seg
        bag.faces.append((k, k2, n_seg + k2, n_seg + k))
        bag.faces.append((k, n_seg + k, n_seg + k2, k2))       # 侧面封闭(简化)
    # 轮毂 + 六角锁母 (外侧)
    hub_r, hub_w = r * 0.42, w + 0.05
    for x in (-hub_w / 2, hub_w / 2):
        off = len(bag.verts)
        for k in range(8):
            a = k / 8 * 2 * pi
            bag.verts.append(Vector((x, cos(a) * hub_r, sin(a) * hub_r)))
    for k in range(8):
        k2 = (k + 1) % 8
        a0 = 2 * n_seg + k
        bag.faces.append((a0, a0 + 1, 2 * n_seg + 8 + k2, 2 * n_seg + 8 + k))
    ob = bag.to_mesh(name, M["wheel"], collection=col_train,
                     matrix=car_mat @ Matrix.Translation(Vector(local_pos)))
    if ob:
        for poly in ob.data.polygons:
            poly.use_smooth = True
        parent_keep(ob, parent)

# ------------------------------------------------------- 单车局部建模 ---
def build_car_local(ci):
    """返回 (bmap材质袋, wheels[(pos,r)], anchors{...}) 全局部坐标."""
    bmap = {}
    def B(k):
        if k not in bmap:
            bmap[k] = Bag()
        return bmap[k]
    def lbox(k, cx, cy, cz, sx, sy, sz):
        B(k).add_box(Vector((cx, cy, cz)), Vector((1, 0, 0)), Vector((0, 1, 0)),
                     Vector((0, 0, 1)), (sx, sy, sz))
    def lbeam(k, p1, p2, w, d):
        B(k).add_beam(p1, p2, w, d)
    is_head = (ci == 0)
    is_tail = (ci == CAR_N - 1)

    # --- 走行部: 底架 + 2 转向架 ---
    for sgn in (1, -1):
        lbox("wheel", sgn * 0.42, 0, -HO - 0.52, 0.09, 1.72, 0.13)      # 纵梁
    for by in (-0.58, 0.58):
        lbox("wheel", 0, by, -HO - 0.52, 0.88, 0.10, 0.13)              # 横梁
        lbox("dark", 0, by, -HO - 0.44, 0.76, 0.30, 0.06)               # 摇枕板
        for sgn in (1, -1):
            lbeam("wheel", (sgn * 0.44, by, -HO - 0.48), (sgn * 0.50, by, -HO - 0.18), 0.055, 0.055)  # 吊杆
            lbox("fin", sgn * 0.575, by + 0.02, -HO - 0.30, 0.05, 0.16, 0.10)   # 制动卡钳
    wheels = []
    for by, bi in ((0.60, 1), (-0.60, 0)):
        for sgn in (1, -1):
            # 跑轮 (独立对象, 轮底切轨顶; 原符号反沉轨 0.296m)
            wheels.append(((sgn * 0.575, by, RAIL_Z + 0.062 + 0.15), 0.15, f"NL_Wheel_{ci}_{bi}_{'R' if sgn>0 else 'L'}"))
            # 侧导轮 (外缘贴轨内侧 0.513; 原 0.415 悬空 6cm)
            for off in (-0.10, 0.10):
                lbox("wheel", sgn * 0.4755, by + off, RAIL_Z + 0.01, 0.075, 0.06, 0.18)
            # 防脱轮 (轨底, 错位)
            lbox("wheel", sgn * 0.575, by + 0.20, RAIL_Z - 0.155, 0.075, 0.06, 0.18)

    # --- 车体: 底板/侧裙/舱壁 ---
    lbox("paint", 0, 0, -HO + 0.415, 1.16, 1.90, 0.07)                  # 底板
    for sgn in (1, -1):
        lbox("paint", sgn * 0.615, 0, -HO + 0.55, 0.055, 1.90, 0.36)    # 侧裙主板
        lbox("paint", sgn * 0.60, 0, -HO + 0.76, 0.085, 1.86, 0.09)     # 上收弧沿
        lbox("trim", sgn * 0.648, 0, -HO + 0.76, 0.018, 1.80, 0.055)    # 橙饰线
        # 分缝 + 检修盖板线
        lbox("dark", sgn * 0.646, 0.42, -HO + 0.56, 0.012, 0.016, 0.30)
        lbox("dark", sgn * 0.646, -0.42, -HO + 0.56, 0.012, 0.016, 0.30)
        lbox("dark", sgn * 0.646, 0.66, -HO + 0.47, 0.012, 0.24, 0.014)
        lbox("dark", sgn * 0.646, 0.66, -HO + 0.65, 0.012, 0.24, 0.014)
        # 铆钉 12
        for k in range(6):
            yy = -0.75 + k * 0.30
            for zz in (-HO + 0.44, -HO + 0.72):
                B("wheel").verts.extend([
                    Vector((sgn * 0.648, yy + dy * 0.013, zz + dz * 0.013))
                    for dy, dz in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
                b = len(B("wheel").verts) - 4
                B("wheel").faces.append((b, b + 1, b + 2, b + 3))
        # 侧徽牌: 南瓜脸
        lbox("paint", sgn * 0.652, -0.55, -HO + 0.58, 0.012, 0.20, 0.15)
        lbox("pumpface", sgn * 0.658, -0.55, -HO + 0.615, 0.006, 0.035, 0.028)
        lbox("pumpface", sgn * 0.658, -0.595, -HO + 0.54, 0.006, 0.05, 0.02)
        # 侧裙格栅
        for k in range(4):
            lbox("dark", sgn * 0.647, 0.10 + k * 0.05, -HO + 0.40, 0.012, 0.018, 0.09)

    # --- 座椅 + 肩式压肩 (每排) ---
    anchors = {}
    for ri, ry in enumerate(ROW_Y):
        if is_head and ri == 0:
            continue                      # 头车前排让位幽灵灯笼区
        for sgn in (1, -1):
            sx = sgn * 0.34
            lbox("seat", sx, ry, -HO + 0.60, 0.56, 0.46, 0.10)           # 坐盆
            lbox("seat", sx, ry + 0.21, -HO + 0.565, 0.56, 0.09, 0.075) # 前缘上翘
            lbox("seat", sx, ry - 0.255, -HO + 0.815, 0.56, 0.11, 0.42) # 靠背
            lbox("seat", sx, ry - 0.315, -HO + 1.03, 0.58, 0.08, 0.10)  # 头枕
            for wy in (-0.14, 0.02):                                     # 缝线槽
                lbox("dark", sx, ry - 0.255, -HO + 0.815 + wy * 0 + -HO * 0 + 0.42 * 0 + wy, 0.0, 0.0, 0.0) if False else None
            lbox("dark", sx + sgn * 0.235, ry - 0.24, -HO + 0.86, 0.09, 0.13, 0.30)   # 侧翼抱肩
            anchors[f"seat_{ri}{'R' if sgn>0 else 'L'}"] = (sx, ry, 0.40)  # P2: 坐面(-0.45)上方0.85m 眼位 (原0.05, 短0.35m)
        lbox("seat", 0, ry, -HO + 0.63, 0.035, 0.40, 0.09)               # 中央分流鳍
        # 肩式压肩: 双立柱 + U 形肩环 + 软垫 + 液压缸
        hy = ry - 0.34
        for sgn in (1, -1):
            lbox("paint", sgn * 0.55, hy, -HO + 0.48, 0.07, 0.09, 0.62)  # 立柱
            lbeam("steel", (sgn * 0.53, ry - 0.10, -HO + 0.42), (sgn * 0.55, hy, -HO + 0.55), 0.05, 0.05)  # 液压缸
            lbox("dark", sgn * 0.53, ry - 0.10, -HO + 0.40, 0.075, 0.075, 0.16)      # 缸体
        arc = []
        for k in range(13):
            a = k / 12 * pi
            arc.append((cos(a) * 0.55, hy - 0.02, sin(a) * 0.16 + (-HO + 0.44)))
        bag_tube(B("paint"), arc, 0.036, sides=8)                        # U 形肩环
        for k in (3, 4, 5, 6, 7, 8, 9):                                   # 肩垫(环内侧)
            a = k / 12 * pi
            lbox("seat", cos(a) * 0.50, hy - 0.02, sin(a) * 0.145 + (-HO + 0.425),
                 0.085 if abs(cos(a)) > 0.3 else 0.5, 0.075, 0.055)
        anchors[f"rest_{ri}"] = (0, hy, 0.30)
        anchors[f"lapbar_{ri}"] = (0, hy - 0.02, -HO + 0.62)   # P2: §3 NL_LapBar 压肩开合锚点 (U 环顶)

    # --- 尾板 + 尾灯 (尾车) ---
    lbox("paint", 0, -0.95, -HO + 0.62, 1.16, 0.12, 0.40)
    if is_tail:
        lbox("dark", 0, -1.005, -HO + 0.60, 0.52, 0.03, 0.14)            # 灯组底座
        for k in (-1, 0, 1):
            lbox("tail", k * 0.15, -1.03, -HO + 0.60, 0.10, 0.035, 0.075)

    # --- 车钩 + 缓冲垫 (P2: §1"半自动钩+缓冲垫"; 车距精确 2.35m 后净隙 0.40m) ---
    bz = -HO + 0.30
    for sgn in (1, -1):
        lbox("dark", sgn * 0.28, -1.02, bz, 0.14, 0.12, 0.14)        # 后端缓冲垫 (橡胶)
        if not is_head:                                              # 前端 (头车前端是鼻锥, 不设)
            lbox("dark", sgn * 0.28, 1.02, bz, 0.14, 0.12, 0.14)
    lbox("steel", 0, -1.10, bz, 0.055, 0.24, 0.055)                  # 后伸钩臂
    lbox("steel", 0, -1.245, bz - 0.04, 0.085, 0.09, 0.13)           # T 型钩头 (扣入后车销座)
    if not is_head:
        lbox("steel", 0, 1.16, bz, 0.055, 0.22, 0.055)               # 前伸承接梁
        lbox("dark", 0, 1.12, bz, 0.09, 0.09, 0.16)                  # 承销座

    # --- 头车: 棱纹流线矮鼻锥 + 低挂小灯笼 ---
    if is_head:
        # 车长位: 斜踏板 + 扶手 (矮, 不挡视线)
        lbox("paint", 0, 0.42, -HO + 0.50, 0.72, 0.26, 0.05)
        bag_tube(B("steel"), [(-0.30, 0.30, -HO + 0.50), (-0.30, 0.30, -HO + 0.84),
                              (-0.27, 0.44, -HO + 0.90)], 0.026)
        bag_tube(B("steel"), [(0.30, 0.30, -HO + 0.50), (0.30, 0.30, -HO + 0.84),
                              (0.27, 0.44, -HO + 0.90)], 0.026)
        bag_tube(B("steel"), [(-0.28, 0.44, -HO + 0.89), (0, 0.48, -HO + 0.925),
                              (0.28, 0.44, -HO + 0.89)], 0.024)
        # --- 三瓣棱纹流线鼻锥 (南瓜棱抽象化, 峰脊 z~-0.24 远低于视线) ---
        # 中瓣 (最高最长)
        lbox("paint", 0, 0.94, -HO + 0.38, 0.46, 0.78, 0.30)
        lbox("paint", 0, 1.03, -HO + 0.60, 0.34, 0.62, 0.22)
        lbox("paint", 0, 1.26, -HO + 0.74, 0.22, 0.16, 0.15)
        # 侧瓣 (低短, 阶梯棱纹)
        for sgn in (1, -1):
            lbox("paint", sgn * 0.40, 0.86, -HO + 0.34, 0.32, 0.62, 0.26)
            lbox("paint", sgn * 0.40, 0.92, -HO + 0.52, 0.24, 0.50, 0.19)
            lbox("oglow", sgn * 0.40, 0.90, -HO + 0.635, 0.25, 0.46, 0.022)  # 橙棱线 (P2: NL_OrangeGlow 4.0)
        # 中脊磷光线 (鼻锥顶棱, 招牌光带) — P2: 列车磷光件拆到 NL_Phos2 (§6 强度 5.0)
        bag_tube(B("phos2"), [(0, 0.58, -HO + 0.53), (0, 0.95, -HO + 0.685),
                              (0, 1.28, -HO + 0.815)], 0.018, sides=6)
        # 领航灯 + 徽牌 (P2: 5cm 方块放大到 12cm, 30m 外夜航可辨)
        lbox("dark", 0, 1.315, -HO + 0.76, 0.17, 0.10, 0.15)
        lbox("phos2", 0, 1.375, -HO + 0.76, 0.115, 0.055, 0.115)
        lbox("paint", 0, 0.60, -HO + 0.545, 0.22, 0.02, 0.14)
        lbox("pumpface", 0, 0.615, -HO + 0.585, 0.05, 0.012, 0.035)
        lbox("pumpface", 0, 0.615, -HO + 0.52, 0.075, 0.012, 0.02)
        # 侧导流小鳍
        for sgn in (1, -1):
            lbox("paint", sgn * 0.555, 0.98, -HO + 0.52, 0.03, 0.30, 0.14)
        # --- 低挂小灯笼 x2 (鼻尖两外侧下方, 不挡视线) ---
        for sgn in (1, -1):
            bx, by = sgn * 0.58, 1.20
            bag_tube(B("steel"), [(sgn * 0.48, 0.98, -HO + 0.55), (sgn * 0.56, 1.12, -HO + 0.52),
                                  (bx, by, -HO + 0.50)], 0.026, sides=6, taper_to=0.018)
            ring = [(sgn * 0.48 + cos(a) * 0.05, 0.98 + sin(a) * 0.05, -HO + 0.55)
                    for a in [k / 8 * 2 * pi for k in range(9)]]
            bag_tube(B("dark"), ring, 0.012, sides=6)
            # 灯笼 (缩版: 顶 -0.62 底 -0.98, 骨白八棱+暖芯)
            lz0 = -0.62
            for k in range(3):
                ring2 = [(bx + cos(a) * 0.02, by + sin(a) * 0.02, lz0 + 0.09 - k * 0.045)
                         for a in [q / 8 * 2 * pi for q in range(9)]]
                bag_tube(B("dark"), ring2, 0.008, sides=6)
            bag_lathe(B("dark"), [(lz0, 0.032), (lz0 + 0.028, 0.068), (lz0 + 0.042, 0.076)], sides=8)
            bag_lathe(B("dark"), [(-0.955, 0.03), (-0.93, 0.065)], sides=8)
            bulge = lambda t: 0.075 + 0.028 * sin(pi * t)
            for k in range(8):
                a = k / 8 * 2 * pi
                rib = [(bx + cos(a) * bulge(t), by + sin(a) * bulge(t), lz0 - 0.015 - t * 0.32)
                       for t in (q / 6 for q in range(7))]
                bag_tube(B("bone"), rib, 0.008, sides=5)
            cb = len(B("creamemit").verts)
            for (hh, rr) in [(lz0 - 0.03, bulge(0.06) - 0.016),
                             (lz0 - 0.09, bulge(0.3) - 0.017),
                             (lz0 - 0.17, bulge(0.55) - 0.017),
                             (lz0 - 0.25, bulge(0.8) - 0.016),
                             (lz0 - 0.29, bulge(0.94) - 0.015)]:
                for q in range(8):
                    a = q / 8 * 2 * pi
                    B("creamemit").verts.append(Vector((bx + cos(a) * rr, by + sin(a) * rr, hh)))
            for i in range(4):
                for q in range(8):
                    q2 = (q + 1) % 8
                    B("creamemit").faces.append((cb + i * 8 + q, cb + i * 8 + q2,
                                                 cb + (i + 1) * 8 + q2, cb + (i + 1) * 8 + q))
            lbox("bone", bx, by, -1.00, 0.032, 0.032, 0.05)
        anchors["pov"] = (0, 0.80, 0.12)
        anchors["pov"] = (0, 0.74, 0.18)

    return bmap, wheels, anchors

# ------------------------------------------------------------- 落位 ---
def frame_at_s(s):
    """任意弧长处线性插值帧 (P2: 车距 2.35m 不再吸附 0.5m 采样栅格)."""
    f = max(0.0, min((len(RS) - 1.001) * P["ds_out"], s)) / P["ds_out"]
    i0 = min(len(RS) - 2, int(f))
    u = f - i0
    p0, t0, u0v, _ = RS[i0]
    p1, t1, u1v, _ = RS[i0 + 1]
    pos = p0.lerp(p1, u)
    Tv = (t0.lerp(t1, u)).normalized()
    Uv = u0v.lerp(u1v, u)
    Uv = (Uv - Tv * Uv.dot(Tv)).normalized()
    return pos, Tv, Uv

car_obs = []
for ci in range(CAR_N):
    s_car = mid_i * P["ds_out"] + (CAR_N / 2 - 0.5 - ci) * CAR_GAP   # P2: 精确 2.35m 车距
    pos, Tv, Uv = frame_at_s(s_car)                                   # ci=0 头车在 s 最大端(行进方向最前)
    Rv = Tv.cross(Uv)
    root = bpy.data.objects.new(f"NL_Car_{ci}", None)
    root.empty_display_size = 0.5
    root.matrix_world = frame_matrix(pos, Rv, Tv, Uv)
    col_train.objects.link(root)
    parent_keep(root, train_root)
    car_obs.append(root)

    bmap, wheels, anchors = build_car_local(ci)
    car_mat = frame_matrix(pos, Rv, Tv, Uv)
    for mk, bg in bmap.items():
        ob = bg.to_mesh(f"NL_C{ci}_{mk}", M[mk], smooth=(mk in ("paint", "seat")),
                        collection=col_train, matrix=car_mat)
        if ob:
            parent_keep(ob, root)
    for (lw, r, wname) in wheels:
        make_wheel_obj(wname, ci, root, car_mat, lw, r=r)
    for key, (ax, ay, az) in anchors.items():
        if key == "pov":
            e = bpy.data.objects.new("NL_CamPov", None)
        elif key.startswith("rest_"):
            e = bpy.data.objects.new(f"NL_Rest_{ci}_{key[5:]}", None)
        elif key.startswith("lapbar_"):
            e = bpy.data.objects.new(f"NL_LapBar_{ci}_{key[7:]}", None)
        else:
            e = bpy.data.objects.new(f"NL_Seat_{ci}{key[5:]}", None)
        e.matrix_world = car_mat @ Matrix.Translation(Vector((ax, ay, az)))
        col_train.objects.link(e)
        parent_keep(e, root)

# A5: 站台车厢号 01-06 (西站台地面发光字, 对齐各车停位)
for _ci, _root in enumerate(car_obs):
    text_mesh(f"NL_CarNum_{_ci}", f"{_ci + 1:02d}", 0.30,
              (10.30, _root.matrix_world.translation.y, PLAT_H + 0.056),
              M["oglow"], rot=(0, 0, 0), extrude=0.015)
# 全部 FONT 对象统一转网格 (站牌大字/车厢号/统计牌)
_txt_all = [o for o in col_static.all_objects if o.type == "FONT"]
if _txt_all:
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    for _o in _txt_all:
        _o.select_set(True)
    bpy.context.view_layer.objects.active = _txt_all[0]
    bpy.ops.object.convert(target="MESH")
    print(f"TEXTMESH_OK {len(_txt_all)}")
tmark("train v2")

# --------------------------------------------------------- build meshes ---
obs = {}
for k in ("rail", "spine", "phos", "steel", "dog", "fin", "column", "foot", "bone", "dark", "bead", "pumpface"):
    obs[k] = bags[k].to_mesh(f"NL_Track_{k}", M[k], smooth=(k in ("rail", "spine")), collection=col_static)
obs["plat"] = bags["plat"].to_mesh("NL_Plat", M["plat"], collection=col_static)
obs["plattop"] = bags["plattop"].to_mesh("NL_PlatTop", M["plattop"], collection=col_static)
obs["warmemit"] = bags["warmemit"].to_mesh("NL_WarmEmit", M["warmemit"], collection=col_static)
obs["creamemit"] = bags["creamemit"].to_mesh("NL_CreamEmit", M["creamemit"], collection=col_static)
obs["roof"] = bags["roof"].to_mesh("NL_Roof", M["roof"], collection=col_static)
obs["sign"] = bags["sign"].to_mesh("NL_Sign", M["sign"], collection=col_static)
obs["signphos"] = bags["signphos"].to_mesh("NL_SignPhos", M["signphos"], collection=col_static)
obs["ring"] = ring_bag.to_mesh("NL_GroundRing", M["phos"], collection=col_static)
tmark("meshes built")

tris = 0
for ob in bpy.context.scene.objects:
    if ob.type == "MESH":
        tris += sum(len(p.vertices) - 2 for p in ob.data.polygons)
tmark(f"TRIS total ~{tris}")

# ---------------------------------------------- lights, world, cameras ----
bpy.ops.object.light_add(type="SUN", location=(60, 30, 90))
sun = bpy.context.active_object
sun.data.energy = 2.2
sun.data.color = hex_lin("#B4C7FF")[:3]
sun.data.angle = radians(6)
sun.rotation_euler = (radians(55), radians(15), radians(160))

bpy.ops.object.light_add(type="AREA", location=(SX, 66, 16))
fill = bpy.context.active_object
fill.data.energy = 400
fill.data.size = 18
fill.data.color = hex_lin("#FF9A5C")[:3]
fill.rotation_euler = (radians(60), 0, 0)

w = bpy.data.worlds.new("Night")
sc.world = w
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = hex_lin(HEX["night"])
bg.inputs[1].default_value = 0.5   # P2: 0.35->0.5 远处轨道剪影有衬底

# 预览地面盘 (仅渲染用, 导出前删)
gp = Bag()
GROUND_R = 150.0
n_g = 64
for a in range(n_g):
    a0 = a / n_g * 2 * pi
    a1 = (a + 1) / n_g * 2 * pi
    base = len(gp.verts)
    gp.verts += [Vector((GROUND_R * cos(a0), GROUND_R * sin(a0), -0.05)),
                 Vector((GROUND_R * cos(a1), GROUND_R * sin(a1), -0.05)),
                 Vector((0, 0, -0.05))]
    gp.faces.append((base, base + 1, base + 2))
ground_prev = gp.to_mesh("NL_GroundPrev", M["ground_prev"], collection=col_static)

def add_cam(name, loc, target, lens=40, ortho=False, scale=100.0):
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.active_object
    cam.name = name
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = scale
    else:
        cam.data.lens = lens
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    col_static.objects.link(cam)
    return cam

_xmin, _xmax = min(p[0].x for p in RS), max(p[0].x for p in RS)
_ymin, _ymax = min(p[0].y for p in RS), max(p[0].y for p in RS)
cam_top = add_cam("NL_CamTop", ((_xmin + _xmax) / 2, (_ymin + _ymax) / 2, 130),
                  ((_xmin + _xmax) / 2, (_ymin + _ymax) / 2, 0),
                  ortho=True, scale=max(_xmax - _xmin, _ymax - _ymin) + 16)   # 终审 P1: 布局包围盒全覆盖(含南区)
cam_three = add_cam("NL_CamThree", (105, -18, 42), (18, 88, 6.0), lens=30)  # P2: 目标下移+上仰 8° 收回顶部死区(提升峰)
cam_three.rotation_euler.rotate_axis("X", radians(8))
cam_front = add_cam("NL_CamFront", (18, -34, 9), (18, 95, 19), lens=26)
cam_loop = add_cam("NL_CamLoop", (104, 76, 12), (80.6, 101, 8), lens=44)   # 终审 P1: 目标=环心(骨爪/墓碑/观景台入画)
cam_station = add_cam("NL_CamStation", (32, 34, 5.5), (18, 62, 4.5), lens=40)
cam_queue = add_cam("NL_CamQueue", (2.0, 22.0, 24.0), (5.8, 37.0, 0.8), lens=45)   # A1 排队迷宫取证机位
cam_south = add_cam("NL_CamSouth", (92.0, 26.0, 12.0), (82.0, 13.0, 1.5), lens=48)  # A6 南区南瓜田取证
cam_scream = add_cam("NL_CamScream", (78.5, 38.0, 4.2), (84.5, 38.0, 2.5), lens=50)  # A6 尖叫统计牌取证(西面)
# 列车特写机位: 全部从车位姿矩阵计算, 禁止手填 (手填曾偏 50 度拍空轨道)
def carpoint(car_i, dx, dy, dz):
    return tuple(car_obs[car_i].matrix_world @ Vector((dx, dy, dz)))
cam_carhead = add_cam("NL_CamCarHead", carpoint(0, 0.0, 5.5, -0.70),
                      carpoint(0, 0, 1.05, -0.55), lens=48)         # 正前方平拍鼻锥 (站台开档内, 两灯笼之间穿视)
cam_carside = add_cam("NL_CamCarSide", carpoint(2, 3.4, 1.4, 0.2),
                      carpoint(2, 0, 0, -0.35), lens=46)
cam_bogie = add_cam("NL_CamBogie", carpoint(5, 2.2, -1.6, -2.5),
                    carpoint(5, 0.2, -0.6, -1.5), lens=30)  # P1-d: 尾车后下方仰视走行部 (原机位自 v1 起在站台体内拍空图)
cam_train = add_cam("NL_CamTrain", carpoint(0, 7.0, 6.0, 2.8),
                    carpoint(3, 0, -4.5, 0.4), lens=24)      # P1-d: 鼻锥前方 3/4 俯瞰 24mm 广角, 头车近距最大
cam_sign = add_cam("NL_CamSign", (11.5, 34.0, 9.0), (11.5, 67.0, 9.0), lens=40)  # 终审 P1: 站名 33m 定距验收机位

# POV: 挂到头车 NL_CamPov 锚点正后方
_pov = bpy.data.objects.get("NL_CamPov")
if _pov:
    cam_pov = add_cam("NL_CamPovCam",
                      tuple(_pov.matrix_world.translation + Vector((0, -0.25, 0.12))),
                      tuple(_pov.matrix_world.translation + Vector((0, 6, -0.2))), lens=24)

def fit_cam(cam, target, points, margin=0.85):
    """P1-d 防拍空: 沿视轴后退直至 points 全部落入 85% 视场 (水平/垂直取严者)."""
    f = cam.data.lens
    h_half = math.atan(18.0 / f)                      # sensor 36mm 横半视场
    v_half = math.atan(18.0 / f / (sc.render.resolution_x / sc.render.resolution_y))
    lim = margin * min(h_half, v_half)
    t_vec = Vector(target)
    for _ in range(24):
        loc = cam.location
        axis = (t_vec - loc).normalized()
        worst = max(axis.angle(Vector(p) - loc) for p in points)
        if worst < lim:
            break
        d = (loc - t_vec).length
        new_loc = t_vec + axis * -1.0 * (d * 1.18)
        if new_loc.z < 0.4:                 # 仰视机位后退会钻地/进站台体, 钳制最低高度
            new_loc.z = 0.4
        cam.location = new_loc
    print(f"FIT {cam.name}: worst={degrees(worst):.1f}deg lim={degrees(lim):.1f}deg d={(cam.location - t_vec).length:.1f}m")

fit_cam(cam_train, carpoint(3, 0, -4.5, 0.4),
        [carpoint(0, 0, 1.45, 1.0), carpoint(0, 0.75, 0, 1.3),
         carpoint(5, 0, -1.1, 1.2), carpoint(5, 0, 0, -0.5)])
fit_cam(cam_carhead, carpoint(0, 0, 1.05, -0.55),
        [carpoint(0, 0.72, 0.55, -0.20), carpoint(0, -0.72, 0.55, -0.20),
         carpoint(0, 0.72, 1.45, -0.95), carpoint(0, -0.72, 1.45, -0.95)])   # 只包鼻锥区(峰脊 z≈-0.29): 特写不拉远
fit_cam(cam_carside, carpoint(2, 0, 0, -0.35),
        [carpoint(2, 0, 0, 1.3), carpoint(2, 0, -1.05, -0.5), carpoint(2, 0, 1.0, -0.5)])
fit_cam(cam_bogie, carpoint(5, 0.2, -0.6, -1.5),
        [carpoint(5, 0.78, -0.2, -0.75), carpoint(5, -0.55, -0.2, -0.75),
         carpoint(5, 0.78, -1.05, -2.25), carpoint(5, -0.55, -1.05, -2.25)])
fit_cam(cam_queue, (5.8, 37.0, 0.8),
        [(3.2, 30.6, 0.0), (7.6, 30.6, 0.0), (3.2, 43.2, 0.0), (7.6, 43.2, 1.2),
         (7.5, 41.0, 1.2)])
fit_cam(cam_loop, (80.6, 101, 8),                                    # 终审 P1: 回环簇取证(爪/碑/台全入画)
        [(70.6, 90.5, 0.5), (90.6, 111.5, 0.5), (80.6, 101, 24.5),
         (70.6, 111.5, 1.0), (90.6, 90.5, 1.0), (79.0, 99.4, 7.5), (82.2, 102.6, 7.5)])
fit_cam(cam_station, (18, 62, 4.5),
        [(8.0, 44.0, 2.4), (15.0, 44.0, 2.4), (8.0, 66.0, 3.0), (15.0, 66.0, 3.0),
         (11.5, 67.2, 9.9)])
fit_cam(cam_front, (16, 70, 7),
        [(8.0, 44.0, 2.4), (15.0, 66.0, 3.0), (11.5, 67.2, 9.9), (6.3, 67.2, 9.6)])
fit_cam(cam_south, (82.0, 13.0, 1.5),
        [(79.5, 9.8, 0.1), (85.0, 9.8, 0.1), (79.5, 16.5, 0.6), (85.0, 16.5, 0.6)])
fit_cam(cam_scream, (84.5, 38.0, 2.5),
        [(83.5, 37.0, 0.1), (85.5, 39.0, 0.1), (83.5, 37.0, 3.2), (85.5, 39.0, 3.2)])

sc.view_settings.view_transform = "Standard"
sc.view_settings.exposure = 0.15

ASSET_BLOOM = str(Path(bpy.app.binary_path).parent / "5.3" / "datafiles" /
                  "assets" / "nodes" / "compositing_nodes_essentials.blend")
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

OUT = Path(__file__).resolve().parent
PREV = OUT / "preview"
PREV.mkdir(exist_ok=True)

bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "roller_coaster.blend"))
tmark("blend saved")

# ------------------------------------------------------------- renders ----
sc.render.engine = "BLENDER_EEVEE"
try:
    sc.eevee.taa_render_samples = 64
except Exception:
    pass
sc.render.resolution_x, sc.render.resolution_y = P["res_still"]
sc.render.resolution_percentage = 100

stills = [("01_top.png", cam_top), ("02_three_quarter.png", cam_three),
          ("03_front_road.png", cam_front), ("04_loop.png", cam_loop),
          ("05_station.png", cam_station),
          ("06_car_head.png", cam_carhead), ("07_car_side.png", cam_carside),
          ("08_bogie.png", cam_bogie), ("09_train_all.png", cam_train)]
if "_pov" in dir() and _pov:
    stills.append(("10_pov.png", cam_pov))
stills.append(("11_sign_33m.png", cam_sign))

def render_still(name, cam):
    sc.camera = cam
    sc.render.image_settings.file_format = "PNG"
    path = PREV / name
    sc.render.filepath = str(path)
    try:
        bpy.ops.render.render(write_still=True)
        return True
    except Exception as e:
        print("RENDER_FAIL", name, type(e).__name__, str(e)[:100])
        return False

for name, cam in stills:
    render_still(name, cam)
tmark("stills rendered")

# 验证渲染 (P1-d): Workbench 均光检视几何, 与夜景情绪稿分离; 夜景预览不再承担验收职责
_verify = [("verify_03_front", cam_front), ("verify_04_loop", cam_loop),
           ("verify_05_station", cam_station), ("verify_12_queue", cam_queue),
           ("verify_13_south", cam_south), ("verify_14_scream", cam_scream),
           ("verify_06_car_head", cam_carhead), ("verify_07_car_side", cam_carside),
           ("verify_09_train", cam_train)]
if "_pov" in dir() and _pov:
    _verify.append(("verify_10_pov", cam_pov))
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.display.shading.show_object_outline = True
for name, cam in _verify:
    render_still(name + ".png", cam)
# verify_08 专属: 隐藏静态件(站台/轨道), 空背景单看走行部结构 (沟槽内必然被裙板/站台遮挡)
for _ob in col_static.all_objects:
    _ob.hide_render = True
render_still("verify_08_bogie.png", cam_bogie)
for _ob in col_static.all_objects:
    _ob.hide_render = False
tmark("verify stills (workbench)")

# ------------------------------------------------------- export glb -------
# 删预览地面
if ground_prev:
    bpy.data.objects.remove(ground_prev, do_unlink=True)

def export_glb(path, collection):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in collection.all_objects:
        if ob.type in ("MESH", "EMPTY"):   # EMPTY = 列车锚点(CamPov/Seat)
            ob.select_set(True)
    try:
        bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB",
                                  use_selection=True, export_apply=True)
    except (TypeError, RuntimeError) as e:
        print("GLTF_KWARG_FALLBACK", type(e).__name__)
        bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB",
                                  use_selection=True)

export_glb(OUT / "roller_coaster.glb", col_static)
export_glb(OUT / "roller_coaster_train.glb", col_train)
tmark("glb exported")

# ---------------------------------------------------- centerline.json -----
data = {
    "name": "nether_loop",
    "ds": P["ds_out"],
    "coords": "blender Z-up, +Y north, origin=ferris wheel; app: x=x, y=z, z=-y",
    "length": round(t._s, 2),
    "vmax_ms": round(float(vmax), 2),
    "samples": [],
    "elements": [
        {"zone": z, "s0": round(a, 2), "s1": round(b, 2), "note": n}
        for z, a, b, n in t.elements if b > a
    ],
}
for i, (pos, Tv, Uv, zn) in enumerate(RS):
    data["samples"].append({
        "s": round(i * P["ds_out"], 2),
        "p": [round(pos.x, 3), round(pos.y, 3), round(pos.z, 3)],
        "t": [round(Tv.x, 4), round(Tv.y, 4), round(Tv.z, 4)],
        "u": [round(Uv.x, 4), round(Uv.y, 4), round(Uv.z, 4)],
        "zone": zn,
        "v": round(float(speeds[i]), 2),
    })
with open(OUT / "centerline.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)
tmark(f"centerline.json: {len(data['samples'])} samples")

print("\nDONE")
