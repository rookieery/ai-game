# -*- coding: utf-8 -*-
"""
幽冥回环 NETHER LOOP v1 - 玩家可乘坐钢铁过山车 (game-ready glTF asset)
Run: blender --background --python roller_coaster.py

北区官方预留位 (Blender +Y=北, 园区原点=摩天轮) — v8.4 马蹄包络:
  站台 (11.5,44) 车头朝北 -> 螺旋链提升(右弯40°, 顶冠z25) -> -80°近垂直俯冲
  -> 扫出拉平+东转 -> 经典水滴环(世界轴转正 r7.5±3.3) -> 零重力滚 -> 双螺丝钻
  -> 短陡坡爬升 -> 行进漂移螺旋(顺时针2圈 边旋边向站台向漂移+渐扭bank) -> 刹车回站
真实铁律: 曲率 G1 连续(弧段积分), 能量守恒+阻力仿真 v(s), 回环顶 g>=0.8,
  峰值 <=4.0g 瞬时(真实 Batman 级), banking 由横向 g<=1.2 反解。
输出: roller_coaster.glb(静态) + roller_coaster_train.glb(列车)
      + centerline.json(0.5m 弧长采样: pos/tan/up/zone/v) + preview/
"""
import bpy
import json
import math
import time
from math import radians, pi, cos, sin, tan, atan2, hypot, sqrt, degrees, asin, acos
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
        """克洛索衣德回环 (v8 世界轴版): r(t)=r_mid+taper*cos(t), 顶=底+2*r_mid.
        旋转轴从入口帧 B=T×U 改为[水平航向×Z]的世界水平轴 —— 老版残余滚转会带歪环面
        (v6.3 实测倾 37.3°); 环面法向恒水平 => 环严格垂直于地面, 形状与 v4 经典水滴一致
        (只转正, 不改形, 底部两股交叉). 出口帧=入口帧, 下游定线零扰动."""
        self.begin(zone)
        Zv = Vector((0, 0, 1))
        h = Vector((self.T.x, self.T.y, 0.0))
        h = h.normalized() if h.length > 1e-6 else Vector((0.0, 1.0, 0.0))
        B = h.cross(Zv).normalized()
        p_in, t_in = self.pos.copy(), self.T.copy()
        th = 0.0
        while th < 2 * pi:
            r = r_mid + taper * cos(th)
            d = min(P["ds_raw"] / max(1.5, r), radians(6), 2 * pi - th)   # 末步钳制: 精确转满 2pi
            self.T = rot_about(self.T, B, d)
            self.U = rot_about(self.U, B, d)
            self.pos += self.T * (r * d)
            th += d
            self._s += r * d
            self._mark()
        dp = self.pos - p_in
        dh = degrees(acos(max(-1.0, min(1.0, self.T.dot(t_in)))))
        print(f"LOOP rm{r_mid:.1f}±{taper:.1f} 入口({p_in.x:.1f},{p_in.y:.1f},{p_in.z:.1f}) "
              f"出口Δ=({dp.x:.1f},{dp.y:.1f},{dp.z:.1f}) 航向Δ={dh:.2f}°")
        self.end(f"loop r{r_mid:.1f}+/-{taper:.1f} world-axis")

    def vloop(self, r_mid, taper, lat=2.2, zone="loop"):
        """v7.1 世界系垂直水滴环 (干净形态): 在[含当前航向 h 的竖直平面]内积分
          r(th) = r_mid + taper*cos(th), 切线 = h*cos(th) + Z*sin(th).
        对称水滴形, 进出口同高同航向, 前进量 D = taper*pi (垂直环固有几何, 两股前后错开).
        (v7.0 的 u_asym/lat 工程修饰把环做成了"断裂螺旋"观感 — 用户反馈后移除;
         底部瞬时 g 放宽到 4.2 换取形状干净, 顶部能量余量已复核 v_top~7)"""
        self.begin(zone)
        h = Vector((self.T.x, self.T.y, 0.0))
        if h.length < 1e-6:
            h = Vector((0, 1, 0))
        h = h.normalized()
        Z = Vector((0, 0, 1))
        self.T = h
        self.U = Z
        P0 = self.pos.copy()
        nrm = h.cross(Z)                      # 平面法向 (crosstie 错位方向)
        pts = [P0.copy()]
        ths = [0.0]
        th = 0.0
        while th < 2 * pi:
            r = r_mid + taper * cos(th)
            d = min(P["ds_raw"] / max(1.5, r), radians(6))
            tang = h * cos(th) + Z * sin(th)
            pts.append(pts[-1] + tang * (r * d))
            th += d
            ths.append(th)
        # 出口半段横向 crosstie 错位 (真实环底部两股错开形态; 无落差, 环仍对称干净).
        # ramp 窗口 0.25pi — 交叉点须已错开 >=2.2 (轨道包络净距, v7.0 无错版实测交叉 0.6m 穿模)
        for i in range(len(pts)):
            if ths[i] > pi:
                _u2 = min(1.0, (ths[i] - pi) / (pi * 0.25))
                pts[i] += nrm * (lat * _u2 * _u2 * (3 - 2 * _u2))
        # 闭环残差回摊: 只吸收离散积分残差 (<0.3m); 设计前进量 D 与 lat 错位末值保留
        tgt_end = P0 + h * (taper * pi) + nrm * lat
        resid = pts[-1] - tgt_end
        n = len(pts)
        pts = [p - resid * (i / (n - 1)) for i, p in enumerate(pts)]
        if resid.length > 0.6:
            print(f"VLOOP_WARN resid={resid.length:.2f}m 超限")
        # 数值切线 + 世界竖直投影 U
        for i in range(n):
            a = pts[max(0, i - 1)]
            b = pts[min(n - 1, i + 1)]
            Tv = (b - a)
            if Tv.length < 1e-9:
                Tv = self.T
            Tv = Tv.normalized()
            Uv = Z - Tv * Z.dot(Tv)
            if Uv.length < 1e-6:
                Uv = self.U
            Uv = Uv.normalized()
            self.pos = pts[i]
            self.T, self.U = Tv, Uv
            if i > 0:
                self._mark()
                self._s += (pts[i] - pts[i - 1]).length
        self.T = h
        self.U = Z
        self.pos = pts[-1]
        _h_top = max(p.z for p in pts) - pts[0].z
        print(f"VLOOP rm{r_mid:.1f} t{taper:.1f} H={_h_top:.1f} D={taper*pi:.1f} "
              f"r_bot={r_mid+taper:.1f} r_top={r_mid-taper:.1f}")
        self.end(f"vloop rm{r_mid:.1f} t{taper:.1f} H{_h_top:.1f}")

    def retrue(self, L, zone="sweep"):
        """v7 归正直线: 行进 L 米, 同时把 U 缓动回世界竖直、T 的 pitch 缓动归零.
        根治 bank 元素 (planar_turn/screw_turn) 的滚转全息泄漏 — 实测扫出拉平出口
        U 残余 37.4°, 直接带歪下游回环; 叠旋弧段 +0.86° 上坡漂移也是同一根因."""
        self.begin(zone)
        n = max(2, int(L / P["ds_raw"]))
        Z = Vector((0, 0, 1))

        def roll_err():
            Ustar = (Z - self.T * Z.dot(self.T)).normalized()
            c = max(-1.0, min(1.0, self.U.dot(Ustar)))
            ang = acos(c)
            if self.U.cross(Ustar).dot(self.T) < 0:
                ang = -ang
            return ang

        roll0 = roll_err()
        pitch0 = asin(max(-1.0, min(1.0, self.T.z)))
        phi_done = 0.0
        for i in range(n):
            u = (i + 0.5) / n
            w = u * u * (3 - 2 * u)
            # 滚转: 目标累计到 w*roll0
            phi = roll0 * w
            self.U = rot_about(self.U, self.T, phi - phi_done)
            phi_done = phi
            # 俯仰: 目标 (1-w)*pitch0 -> 0
            tgt = pitch0 * (1 - w)
            cur = asin(max(-1.0, min(1.0, self.T.z)))
            err = tgt - cur
            if abs(err) > 1e-6:
                B = self.T.cross(self.U).normalized()
                Bh = (B - Z * B.dot(Z))
                Bh = Bh.normalized() if Bh.length > 1e-5 else B
                self.T = rot_about(self.T, Bh, err)
                self.U = rot_about(self.U, Bh, err)
            self._step()
        # 收尾吸附 (残差 <0.5°, 轨面拐点不可见)
        self.T = Vector((self.T.x, self.T.y, 0.0)).normalized()
        self.U = (Z - self.T * Z.dot(self.T)).normalized()
        self.end(f"retrue L={L:.0f} roll{degrees(roll0):+.1f} p{degrees(pitch0):+.2f}")

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
                # v8 轴修正: 水平航向×Z 与航向正交且恒水平, 修俯仰不偷改航向
                # (老 T×U 被 bank 带歪, 修俯仰时耦合出 ~33° 航向泄漏, 扫出弯实测漂 142.9°/设计110°)
                hh = Vector((self.T.x, self.T.y, 0.0))
                if hh.length > 1e-6:
                    Bh = hh.normalized().cross(Z)
                else:
                    Bh = self.T.cross(self.U).normalized()
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
        _ropts = (max(11.0, r), max(11.0, r) + 4.0, max(11.0, r) + 8.0)
        for rr in _ropts:
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

    def turn3d(self, deg, r, bank=0.0, dz=0.0, zone=None):
        """v8 带俯仰的平面转弯: 平面等角旋转 + 正弦俯仰剖面 (dz>0 降 / dz<0 升).
        俯仰修正轴 = [水平航向×Z] (与 screw_turn 的 T×U 不同 —— 后者被 bank 带歪时会
        耦合出航向泄漏); 俯仰幅值 slopeMax 二分数值解, 使 Σ ds·sin(pitch) 精确=|dz|.
        根治 planar_turn dz 剪切 (pos 降了但切线仍水平, 切线误差=坡度角)."""
        if zone: self.begin(zone)
        total = radians(deg)
        n = max(2, int(abs(total) * r / P["ds_raw"]))
        step = total / n
        Z = Vector((0, 0, 1))
        sm_lo, sm_hi = 0.0, radians(60)
        for _ in range(30):
            mid = (sm_lo + sm_hi) / 2
            acc = sum(sin(mid * sin(pi * (i + 0.5) / n)) for i in range(n)) * P["ds_raw"]
            if acc < abs(dz):
                sm_lo = mid
            else:
                sm_hi = mid
        sm_max = (sm_lo + sm_hi) / 2
        dsgn = 1.0 if dz >= 0 else -1.0
        phi_prev = 0.0
        sgn = 1 if deg >= 0 else -1
        for i in range(n):
            u = (i + 0.5) / n
            self.T = rot_about(self.T, Z, -step)
            self.U = rot_about(self.U, Z, -step)
            tgt = -sm_max * sin(pi * u) * dsgn
            cur = asin(max(-1, min(1, self.T.z)))
            err = tgt - cur
            if abs(err) > 1e-6:
                hh = Vector((self.T.x, self.T.y, 0.0))
                if hh.length > 1e-6:
                    B = hh.normalized().cross(Z)
                    self.T = rot_about(self.T, B, err)
                    self.U = rot_about(self.U, B, err)
            ramp = 1.0 if abs(total) < 0.05 else min(1.0, min(u, 1 - u) / 0.30)
            ramp = ramp * ramp * (3 - 2 * ramp)
            phi = radians(bank) * ramp * sgn
            self.U = rot_about(self.U, self.T, phi - phi_prev)
            phi_prev = phi
            self._step()
        self.U = (self.U - self.T * self.U.dot(self.T)).normalized()
        self.end(f"turn3D {deg:.0f}deg r{r:.0f} bank{bank:.0f} dz{dz:+.1f}")

# ---------------------------------------------------------------- layout ---
def helix_turn(self, total_deg, r, drop, left=False, bank=40.0, zone="helix"):
    """真·下降螺旋 (v6.4): plan 等角旋转 + 恒坡度下降 + 几何理想倾角.
    纯运动学定义路径 (无 pitch 反馈), bank 仅倾斜 U 外观 —— 零漂移, 层距精确.
    left=False 顺时针 (入口段西侧绕行), True 逆时针."""
    self.begin(zone)
    total = radians(total_deg)
    n = max(24, int(abs(total) * r / P["ds_raw"]))
    dth = (total if left else -total) / n   # left=True: CCW 绕 Z 正向
    slope = radians(degrees(atan2(drop, abs(total) * r)))
    step_len = abs(total) * r / n
    bank_r = radians(bank)
    Zv = Vector((0, 0, 1))
    for _ in range(n):
        self.T = rot_about(self.T, Zv, dth)
        Th = Vector((self.T.x, self.T.y, 0)).normalized()
        self.T = (Th * cos(slope) - Zv * sin(slope)).normalized()
        self.U = (Zv - self.T * Zv.dot(self.T)).normalized()
        self.U = rot_about(self.U, self.T, bank_r)
        self.pos += self.T * step_len
        self._s += step_len                            # v11 修复: v6.4 潜伏 bug —— helix_turn 从不累计 _s,
        self._mark()                                   # 元素 s 跨度为零被 G-CHECK 跳过且下游 zone 全错位 (首装即炸)
    self.end(f"helix {total_deg:.0f}deg r{r:.0f} drop{drop:.1f} {'L' if left else 'R'}")

Turtle.helix_turn = helix_turn                      # v11 接线: 三层折叠螺旋首次投入使用

def drift_helix(self, total_deg, r, drop, c1, ctrl, bank0=32.0, bank1=58.0, zone="helix"):
    """v12 行进螺旋: 顺时针下降, 圆心沿二次贝塞尔 (入口圆心->ctrl->c1) 漂移.
    入口: 列车朝南, 位于圆心 C0=(pos.x-r, pos.y) 正东点; 顺时针整圈出口在西点朝北
    (total_deg 须为 360 整倍数). drop 用 smoothstep 剖面: 首末坡度 0 (与前后段 G1 衔接),
    中段最大坡度 = 1.5*avg (轨道方向与地面成角); bank 从 bank0 渐扭到 bank1 (轨道自身扭曲)."""
    self.begin(zone)
    c0 = Vector((self.pos.x - r, self.pos.y))
    Zv = Vector((0, 0, 1))
    n = max(96, int(abs(total_deg) / 360 * 2 * pi * r / P["ds_raw"]))
    z0 = self.pos.z
    prev = self.pos.copy()
    for i in range(1, n + 1):
        u = i / n
        th = radians(total_deg) * u
        # 贝塞尔参数 smoothstep 缓入缓出: 末段圆心速度->0, 出口切线不被漂移拽偏 (v12 首版
        # 线性参数实测出口航向被拖偏 -16°, 刹车 39m 斜进 x 漂 -11m)
        uu = u * u * (3 - 2 * u)
        C = c0 * ((1 - uu) * (1 - uu)) + ctrl * (2 * uu * (1 - uu)) + c1 * (uu * uu)
        ang = -th                                   # 顺时针 (俯视)
        zoff = drop * uu                            # smoothstep 坡度剖面
        self.pos = Vector((C.x + r * cos(ang), C.y + r * sin(ang), z0 - zoff))
        step = self.pos - prev
        L = step.length
        if L > 1e-9:
            self.T = step.normalized()
            Uv = (Zv - self.T * Zv.dot(self.T)).normalized()
            w = u * u * (3 - 2 * u)
            Uv = rot_about(Uv, self.T, radians(bank0 + (bank1 - bank0) * w))
            self.U = Uv
            self._s += L
            self._mark()
        prev = self.pos.copy()
    # 出口解析切线吸附: smoothstep 坡度末速为 0, 末点切线 = 纯旋转分量 (西点+顺时针 = 朝北);
    # 数值弦每步 ~2.9° 会残留 ~1.5° 航向偏斜 -> 刹车 39m 斜进 (v12 二版实测 x 漂 -1.1)
    ang_end = -radians(total_deg)
    self.T = Vector((sin(ang_end), -cos(ang_end), 0.0)).normalized()
    self.end(f"drift_helix {total_deg:.0f}deg r{r:.1f} drop{drop:.1f} -> c1({c1.x:.1f},{c1.y:.1f})")

Turtle.drift_helix = drift_helix                    # v12 接线: 行进漂移螺旋

def build_centerline(qx=0.0, qy=0.0):
    """v8 定线 (马蹄包络: 老版骨架 + 新元素挂环带; 用户三轮确认的 v8.4 方案):
    站台(11.5,44)朝北 -> 螺旋链提升(右弯40° r65, pitch→45, 顶冠 z≈25.2, 北端南收换围栏余量)
    -> 顶冠拉平+缓冲 -> -80° 近垂直俯冲(直落加深, 凹弧拉平整体落谷底, 消半空 S 拐点)
    -> 扫出拉平(俯冲+东转合一) -> retrue×2 归正
    -> 高速贴地东转70° r34 bank61 (turn3d 降高按谷底实测差 → 环入口贴地 z≈5.07)
    -> 经典水滴环 r7.5±3.3 (世界水平轴, 只转正不改形, v4 原版参数, 底部两股交叉)
    -> 环出口缓俯降至贴地 z2.63 -> 零重力滚9m -> 爬坡(30°) -> 双螺丝钻
    -> 短陡坡25°(+2.7m, summit z13.8) -> 行进漂移螺旋 (drift_helix 顺时针2整圈 r8,
    圆心贝塞尔向站台向漂移 每圈错位~25m, smoothstep坡度中段~9°, bank 32->58 渐扭)
    -> 西点切线朝北接刹车回站 (v12)"""
    X0, Y0 = 11.5, 44.0
    t = Turtle((X0, Y0, P["station_h"]), (0, 1, 0), zone="station")
    t.forward(22.0, zone="station")
    t.forward(7.0, zone="dispatch")
    # --- 西缘: 螺旋链提升 (老版骨架; 顶冠压低到 ~25 换围栏余量, v4 曾贴脸 142.1) ---
    t.screw_turn(40, 65, 0, 0, 45, zone="lift")
    _p1 = degrees(asin(max(-1.0, min(1.0, t.T.z))))
    t.forward((24.3 - t.pos.z) / sin(radians(_p1)), zone="lift")
    t.vturn(-_p1, 4.0, zone="lift")
    t.crest_h = t.pos.z
    t.forward(14.5, zone="lift")                       # v13: 4->14.5m 顶冠平段容纳完整六节车厢 (14.1m);
                                                       # 平段水平不增能, 下游沿 hdg40 刚性平移 (10.5m) 已核: 围栏 140.5<142 ✓
    # --- 北端: 近垂直俯冲 (-80°; 精确 -90 会让 T 水平分量退化, 扫出拉平平面随机化) ---
    t.vturn(-80, 3.4, zone="drop")
    # --- v9 俯冲重塑 (用户确认): 原弧线与 -80° 方向不变, 直落段加深, 凹弧拉平整体下移到谷底
    #     (旧症: 直落仅 4m 即在 z≈17.5 半空反凹, 俯冲中段形成 S 拐点) ---
    _z_dive = t.pos.z
    _z_pull_end = 5.87                                 # 拉平终点 (uturn 再降 ~0.8, 环入口 z≈5.07 不动)
    _pull_dz = 8.0                                     # 拉平弧竖降 (v8.4 实测 17.46->9.47)
    _str_drop = (_z_dive - (_z_pull_end + _pull_dz)) / sin(radians(80))
    t.forward(_str_drop, zone="drop")
    t.screw_turn(70, 13, 40, -80, 0, zone="drop")      # 扫出拉平: 俯冲+东转合一 (形状不变, 落位下移)
    t.retrue(8.0, zone="valley")
    t.retrue(4.0, zone="valley")
    _z_valley = t.pos.z
    # --- 高速贴地东转70° r34 bank61 (东缘 x≈68-78): 降高按谷底实测差, 环入口 z 与 v8.4 一致 ---
    _uturn_dz = _z_valley - 5.07
    t.turn3d(70, 34, 61, _uturn_dz, zone="uturn")
    print(f"DROP_V9 dive_end_z={_z_dive:.2f} straight={_str_drop:.2f} "
          f"valley_z={_z_valley:.2f} uturn_dz={_uturn_dz:+.2f}")
    # --- 东缘: 经典水滴环 (世界水平轴; v4 原版参数, 底部两股交叉为经典形态特征) ---
    t.forward(5.0, zone="valley")
    t.loop(7.5, 3.3)
    # --- v10 贴地带紧凑化 (用户确认: 零重力滚保留, 高度 2.63 不变, 区间 44.5->37.7m):
    #     俯降 22°/r12 (谷底 g3.9<4.2) + 滚直段 9m + 爬升 30° 与尾部 ramp 同坡度 ---
    _z_loop_exit = t.pos.z
    _low_z = 2.55                                      # 滚直段轨面目标 (实测半高 2.68, 预扣离散浮差 -> 实落 ≈2.63)
    _dip_r, _dip_deg = 12.0, 22.0
    _dz_arc = _dip_r * (1 - cos(radians(_dip_deg)))    # 单竖弧竖降 0.875
    _dz_str = (_z_loop_exit - _dz_arc) - (_low_z + _dz_arc)
    t.vturn(-_dip_deg, _dip_r, zone="zerog")
    t.forward(_dz_str / sin(radians(_dip_deg)), zone="zerog")
    t.vturn(_dip_deg, _dip_r, zone="zerog")
    t.roll_straight(9.0, 360, zone="zerog")
    # --- 爬坡 30° (轴高 10.5 不变 -> 螺丝钻形态不变) ---
    _climb_deg = 30.0
    t.screw_turn(0.01, 20, 0, 0, _climb_deg, zone="climb")
    t.forward((10.5 - t.pos.z) / sin(radians(_climb_deg)), zone="climb")
    t.screw_turn(0.01, 20, 0, _climb_deg, 0, zone="climb")
    print(f"LOW_V10 loop_exit_z={_z_loop_exit:.2f} "
          f"roll_len=9.0 zerog_z={t.pos.z:.2f}")
    t.forward(2.0, zone="sweep")
    t.corkscrew(5.8, 1.0, right=True, zone="corkscrew", advance=9.0)
    t.forward(2.0, zone="sweep")
    t.corkscrew(5.8, 1.0, right=True, zone="corkscrew", advance=9.0)
    # --- v12 尾部重构 / v14 螺旋放大 (用户确认): 钻出口即爬坡 -> 行进漂移螺旋 -> 相切刹车 ---
    # 25° 爬坡 (+2.7m 能量上限, summit z13.8, v_top~8.1) -> drift_helix 顺时针 2 整圈
    # r12 (v14: 8->12, 圈径24m), 圆心贝塞尔 (65.5,4)->(43,-30)->(23.5,5): 每圈向站台
    # 方向错位 ~18m, 中段南潜避木马净空圈 r13.5@(45,18) (北弧距≥17.6); smoothstep
    # 坡度中段 ~6°; bank 30->55 渐扭; 西点出口朝北相切 x11.5 刹车线, 刹车 ~39m
    t.vturn(25, 9.0, zone="ramp")                      # 短陡坡上
    t.vturn(-25, 9.0, zone="ramp")                     # 坡顶回平
    t.forward((13.8 - t.pos.z) / sin(radians(25)), zone="ramp")  # 爬到 summit z13.8
    t.drift_helix(900, 12.0 - 0.51 * qx, t.pos.z - 3.0, Vector((23.5, 5.0)),
                  Vector((52, -38)), bank0=30.0, bank1=55.0, zone="helix")  # 2圈+半圈进西点, 出口 (11.5,5) 朝北 z3; ctrl 深南潜+先东摆: 第一圈西北弧距木马心≥15
    # (v12 调试探针已移除)
    # --- 西缘: 刹车回站 (沿 x=11.5 直北, 不用 close_to —— v7 实测解会斜穿摩天轮盘面) ---
    t.begin("brake")
    t.retrue(6.0, zone="brake")                        # 缝口必须水平到站
    if Y0 + qy - t.pos.y > 0.05:
        t.forward(Y0 + qy - t.pos.y, zone="brake")
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
for _cal in range(5):
    t = build_centerline(qx, qy)
    _dr = t.pos - Vector((t.x0, t.y0, P["station_h"]))
    print(f"CALIB{_cal} drift=({_dr.x:+.2f},{_dr.y:+.2f},{_dr.z:+.2f}) |xy|={hypot(_dr.x, _dr.y):.2f}")
    if hypot(_dr.x, _dr.y) < 0.10:
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
    elif zn == "chainrun":          # v7: 第二提升链前的入链减速段 (平滑咬链, 防 v 突跳)
        v2 = max(3.4 ** 2, v2 - 2 * 4.5 * P["ds_out"])
    elif zn in ("brakes", "brake", "station_in"):
        v2 = max(1.5 ** 2, v2 - 2 * 5.5 * P["ds_out"])   # v7: 回流变短, 刹车 4.2->5.5 m/s²
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
           (3.2, 30.6, 3.2, 44.2),    # 西墙 (M4 北延封西北绕行, 与 b 北封闭合)
           (6.0, 32.2, 6.0, 39.8),    # 东墙 (南端 y30.6-32.2 留入口)
           (4.6, 32.9, 6.0, 32.9),    # 齿1 东起 -> 西通口
           (3.2, 35.2, 4.6, 35.2),    # 齿2 西起 -> 东通口
           (4.6, 37.5, 6.0, 37.5),    # 齿3 东起 -> 西通口
           (3.2, 39.8, 4.7, 39.8)):   # 北墙 (M4: 出口加宽 x4.7-6.0=1.16m, 原 0.86m 仅 0.1m 中心容差)
    queue_fence(*_q)
# 进场走廊封闭 (终审 P0 修复): c 墙原为单段横贯西槽口(8.65-10.15)封死唯一登台路 -> 拆两段, 槽口让给闸机线
# M4 修复: a 墙南端 39.8 -> 40.74 (原封死「迷宫出口→走廊」接口致全线断路; 截短后重开口子 z40.74-39.8=0.94m);
#   b 墙西延至西墙 (3.2, 封西北旁路, 保「单进单出」)
for _q in ((6.0, 40.74, 6.0, 44.2),    # a: 迷宫东墙北延 (南端让出走廊西口)
           (3.2, 44.2, 8.05, 44.2),    # b: 西北口袋北封 (西延接迷宫西墙)
           (6.5, 40.6, 8.05, 40.6),    # c1: 走廊北墙西段 (M4: 西端 6.0->6.5, 原角圆把西口压窄到 0.36m 无法通行)
           (10.75, 40.6, 12.25, 40.6), # c2: 走廊北墙东段 (东侧墙->东端块, 仍封轨道沟南缘)
           (6.0, 39.2, 12.25, 39.2)):  # d: 走廊南墙 (唯一进口=迷宫缺口, 唯一出口=过闸)
    queue_fence(*_q)
# 回流沟护栏 (M3-B2): 刹车/进站段 x~11.5 两侧, 防玩家走上进站轨道 (顶轨暖白光帽兼作夜态导引)
queue_fence(10.55, 13.5, 10.55, 40.5)
queue_fence(12.45, 13.5, 12.45, 40.5)

# --- A2 验票闸门 x2 (终审 P0: 闸线横跨槽口本身, 行进向 +Y, 双转子全宽, 闸即门) ---
for _gx in (8.65, 9.4, 10.15):                      # 三柱 (槽口两缘+中)
    bags["column"].add_beam((_gx, 40.4, 0), (_gx, 40.4, 1.15), 0.07, 0.07)
bags["steel"].add_beam(Vector((8.65, 40.4, 0.12)), Vector((10.15, 40.4, 0.12)), 0.06, 0.06)  # 底梁
bags["steel"].add_beam(Vector((8.65, 40.4, 1.12)), Vector((10.15, 40.4, 1.12)), 0.06, 0.06)  # 顶梁
for _gi, _gx in enumerate((9.03, 9.78)):
    bags["dark"].add_box(Vector((_gx, 40.4, 0.33)), Vector((1, 0, 0)), Vector((0, 1, 0)),
                         Vector((0, 0, 1)), (0.55, 0.22, 0.66))          # 柜体封 0-0.66
    # M4: 三臂闸翼拆独立节点 NL_GateArm_{gi}, 顶点相对轴心 (枢轴 = NL_Gate 锚点),
    # 普通父子挂锚点下 -> 游戏转 NL_Gate_{gi} rotation.x 即开合
    # (转子 120° 旋转首末位姿重合: 关闭位与烘焙位姿逐点一致, 90/210/330 -> 210/330/450≡90)
    _hinge = Vector((_gx, 40.4, 0.95))
    _arm = Bag()
    for _aa in (90, 210, 330):                       # 三臂闸翼 (轴沿 X, 行进向 +Y)
        _ar = radians(_aa)
        _arm.add_beam(Vector((0, 0, 0)),
                      Vector((0, 0.30 * cos(_ar), 0.30 * sin(_ar))), 0.035, 0.035)
    _ge = bpy.data.objects.new(f"NL_Gate_{_gi}", None)     # M3/M4 闸翼开合锚点
    _ge.location = tuple(_hinge)
    col_static.objects.link(_ge)
    _go = _arm.to_mesh(f"NL_GateArm_{_gi}", M["phos"], collection=col_static)
    if _go:
        _go.parent = _ge
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

# --- A6 彩蛋: 俯冲谷观景台 (贴地俯冲扫出+东转90°北侧 (20,118); 台上看贴地飞行/东转/俯冲) ---
_vx, _vy = 20.0, 118.0
_A6_LX, _A6_LCY = _vx, _vy
_A6_TOWER_BUILT = True
_li_loop = [i for i, r in enumerate(RS) if r[3] == "loop"]
if _li_loop:
    _LOOP_C = Vector((sum(RS[i][0].x for i in _li_loop) / len(_li_loop),
                      sum(RS[i][0].y for i in _li_loop) / len(_li_loop), 0.0))
else:
    _LOOP_C = Vector((_A6_LX, _A6_LCY, 0.0))
_tw = 1.6
for _sx2 in (-1, 1):
    for _sy2 in (-1.1, 1.1):
        bags["column"].add_beam((_vx + _sx2 * 2.2, _vy + _sy2, 0),
                                (_vx + _sx2 * 2.2, _vy + _sy2, 6.4), 0.13, 0.13)
for _sy2 in (-1.1, 1.1):
    bags["steel"].add_beam(Vector((_vx - 2.2, _vy + _sy2, 6.35)),
                           Vector((_vx + 2.2, _vy + _sy2, 6.35)), 0.10, 0.12)
bags["plattop"].add_box(Vector((_vx, _vy, 6.47)), Vector((1, 0, 0)), Vector((0, 1, 0)),
                        Vector((0, 0, 1)), (_tw * 2 + 0.2, _tw * 2 + 0.2, 0.12))
for _e0, _e1 in (((-_tw, -_tw), (_tw, -_tw)), ((_tw, -_tw), (_tw, _tw)),
                 ((_tw, _tw), (-_tw, _tw)), ((-_tw, _tw), (-_tw, -_tw))):
    _p0 = Vector((_vx + _e0[0], _vy + _e0[1], 0))
    _p1 = Vector((_vx + _e1[0], _vy + _e1[1], 0))
    _nl = (_p1 - _p0).length
    _n2 = max(2, int(_nl / 1.6))
    for _k3 in range(_n2 + 1):
        _pp = _p0.lerp(_p1, _k3 / _n2)
        bags["column"].add_beam((_pp.x, _pp.y, 6.53), (_pp.x, _pp.y, 7.6), 0.05, 0.05)
    for _hz2 in (6.9, 7.45):
        bags["steel"].add_beam(Vector((_p0.x, _p0.y, _hz2)), Vector((_p1.x, _p1.y, _hz2)), 0.045, 0.06)
# 西侧楼梯 18 级 x0.40 (顶 7.2 ≈ 台面)
for _k4 in range(18):
    bags["plattop"].add_box(Vector((_vx - 5.86 + _k4 * 0.27, _vy, 0.20 * (_k4 + 1))),
                            Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)),
                            (0.27, 1.10, 0.40 * (_k4 + 1)))
bags["plattop"].add_box(Vector((_vx - 1.35, _vy, 7.22)), Vector((1, 0, 0)),
                        Vector((0, 1, 0)), Vector((0, 0, 1)), (1.4, 1.30, 0.12))
print(f"A6_DECK ({_vx:.1f},{_vy:.1f}) 俯冲谷观景台 z7.2")
# 南瓜田一角 (v5.1: 双螺丝钻下方 x42.6-45.8 西侧带, 九颗发光南瓜; 心线绕轴摆幅 ±5.8, 地面净空 ~2.5m)
for _pk in ((43.0, 62.0, 0.30), (44.4, 61.4, 0.22), (45.8, 62.6, 0.26), (42.6, 63.8, 0.19),
            (44.2, 64.6, 0.24), (45.6, 65.4, 0.28), (43.2, 66.8, 0.20), (44.8, 67.6, 0.23),
            (43.6, 69.2, 0.26)):
    pumpkin_lantern(bags["warmemit"], _pk[0], _pk[1], _pk[2] * 0.58 + 0.02, _pk[2])
# 尖叫统计牌 (v10: 双螺丝钻西侧 (70,19-21) 随钻北移 9m, 面向东轨 x78)
for _sp in ((70.0, 19.0), (70.0, 21.0)):
    bags["column"].add_beam((_sp[0], _sp[1], 0), (_sp[0], _sp[1], 3.1), 0.10, 0.10)
bags["sign"].add_box(Vector((70.0, 20.0, 2.72)), Vector((1, 0, 0)), Vector((0, 1, 0)),
                     Vector((0, 0, 1)), (0.10, 2.0, 1.15))
text_mesh("NL_ScreamSign", "本季尖叫 8642 次", 0.26, (69.94, 20.0, 2.72), M["oglow"],
          rot=(90, 0, -90), extrude=0.02)   # 立起再转面西: 阅读方向-Y, 字头+Z
# 入口立牌 (M3-B6 实机发现: 大牌在雨棚正后, 地面视角被 24.5m 棚顶全遮 -> 大牌当天际线地标,
# 近距可读由排队口双柱牌承担; oglew 4.0 档 = EXIT 牌实机已证可读档位)
for _sp in ((3.8, 27.5), (7.2, 27.5)):
    bags["column"].add_beam((_sp[0], _sp[1], 0), (_sp[0], _sp[1], 4.6), 0.12, 0.12)
bags["sign"].add_box(Vector((5.5, 27.5, 3.95)), Vector((1, 0, 0)), Vector((0, 1, 0)),
                     Vector((0, 0, 1)), (3.6, 0.16, 1.30))
text_mesh("NL_EntrySign", "幽冥回环", 0.55, (5.5, 27.41, 4.12), M["oglow"], rot=(90, 0, 0), extrude=0.025)
text_mesh("NL_EntrySignB", "NETHER LOOP", 0.18, (5.5, 27.41, 3.55), M["subglow"], rot=(90, 0, 0), extrude=0.02)

# 地面灯环 (M3: 三移至东广场 (17.5,30.5) —— 回流沟护栏上线, 原位会被双护栏切割)
ring_bag = Bag()
RC = Vector((17.5, 30.5, 0.06))
for a in range(48):
    a0 = a / 48 * 2 * pi
    a1 = (a + 1) / 48 * 2 * pi
    r0, r1 = 4.2, 4.8
    p00 = Vector((17.5 + r0 * cos(a0), 30.5 + r0 * sin(a0), 0.06))
    p01 = Vector((17.5 + r1 * cos(a0), 30.5 + r1 * sin(a0), 0.06))
    p10 = Vector((17.5 + r0 * cos(a1), 30.5 + r0 * sin(a1), 0.06))
    p11 = Vector((17.5 + r1 * cos(a1), 30.5 + r1 * sin(a1), 0.06))
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

def make_wheel_obj(name, i_c, parent, local_pos, r=0.15, w=0.10):
    """独立车轮对象 (轴沿局部X, three.js 转 rotation.x 即滚动).

    轮心契约: 顶点=以轮心为中心的轮形(不烘位置), 节点平移=轮心局部坐标 -> glb 中
    NL_Wheel_* 节点 T=轮心、几何居中, rotation.x 原地自转即滚动。
    若把 local_pos 烘进顶点而节点恒等, rotation.x 会绕车原点公转 -> 轮子甩上车顶。"""
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
    ob = bag.to_mesh(name, M["wheel"], collection=col_train)
    if ob:
        for poly in ob.data.polygons:
            poly.use_smooth = True
        # 普通父子 (basis=T(local_pos), parent_inverse=I): 站台帧旋转=恒等下 world 预览不变;
        # 若走 parent_keep(烘 world + parent_inverse 抵消), 导出器把世界坐标烘进顶点
        # -> glb 变"站台快照", 游戏重摆车根后姿态全错
        ob.location = Vector(local_pos)
        ob.parent = parent

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
            # 侧导轮 (外缘距轨内侧 5mm; 原 0.4755 精确贴靠 0.000mm -> three.js 轮缘/轨面 z-fight 黑闪)
            for off in (-0.10, 0.10):
                lbox("wheel", sgn * 0.4705, by + off, RAIL_Z + 0.01, 0.075, 0.06, 0.18)
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
    specials = []   # M4: 需挂锚点下的开合网格 (压肩), 装配段在锚点 empty 建好后创建
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
        # 肩式压肩: 双立柱 + 液压缸 (静态, 材质袋) | U 形肩环 + 肩垫 (M4 拆独立开合节点)
        hy = ry - 0.34
        for sgn in (1, -1):
            lbox("paint", sgn * 0.55, hy, -HO + 0.48, 0.07, 0.09, 0.62)  # 立柱
            lbeam("steel", (sgn * 0.53, ry - 0.10, -HO + 0.42), (sgn * 0.55, hy, -HO + 0.55), 0.05, 0.05)  # 液压缸
            lbox("dark", sgn * 0.53, ry - 0.10, -HO + 0.40, 0.075, 0.075, 0.16)      # 缸体
        # M4: U 形肩环+肩垫 独立节点 (NL_LapBarMesh_ = U环/paint, NL_LapBarPad_ = 肩垫/seat),
        # 顶点相对枢轴 (枢轴 = NL_LapBar 锚点 = U 环顶), 游戏转锚点 rotation.x 即开合;
        # 普通父子挂锚点下 (契约同车轮: 勿烘位姿), 闭合位 = 建模位 (与旧烘焙位逐点一致)
        _hinge = Vector((0, hy - 0.02, -HO + 0.62))
        _lb = Bag()
        _arc = []
        for k in range(13):
            a = k / 12 * pi
            _arc.append(Vector((cos(a) * 0.55, hy - 0.02, sin(a) * 0.16 + (-HO + 0.44))) - _hinge)
        bag_tube(_lb, _arc, 0.036, sides=8)                              # U 形肩环
        _lp = Bag()
        for k in (3, 4, 5, 6, 7, 8, 9):                                   # 肩垫(环内侧, 皮革色随 seat 材质)
            a = k / 12 * pi
            _lp.add_box(Vector((cos(a) * 0.50, hy - 0.02, sin(a) * 0.145 + (-HO + 0.425))) - _hinge,
                        Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)),
                        (0.085 if abs(cos(a)) > 0.3 else 0.5, 0.075, 0.055))
        specials.append({"name": f"NL_LapBarMesh_{ci}_{ri}", "bag": _lb,
                         "mat": "paint", "smooth": True, "anchor": f"lapbar_{ri}"})
        specials.append({"name": f"NL_LapBarPad_{ci}_{ri}", "bag": _lp,
                         "mat": "seat", "smooth": True, "anchor": f"lapbar_{ri}"})
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

    return bmap, wheels, anchors, specials

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

    bmap, wheels, anchors, specials = build_car_local(ci)
    car_mat = frame_matrix(pos, Rv, Tv, Uv)
    for mk, bg in bmap.items():
        # matrix=None: 车局部数据不烘 car_mat; 普通父子 world=car_mat 预览不变,
        # 导出器输出"车局部顶点+恒等节点" (契约见 src/rides/coaster.js frameAt)
        ob = bg.to_mesh(f"NL_C{ci}_{mk}", M[mk], smooth=(mk in ("paint", "seat")),
                        collection=col_train)
        if ob:
            ob.parent = root
    for (lw, r, wname) in wheels:
        make_wheel_obj(wname, ci, root, lw, r=r)
    anchor_objs = {}
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
        anchor_objs[key] = e
    # M4 开合网格: 普通父子挂锚点 (location 恒 0, 顶点已相对枢轴) -> 游戏转锚点即开合
    for sp in specials:
        ob = sp["bag"].to_mesh(sp["name"], M[sp["mat"]], smooth=sp.get("smooth", False),
                               collection=col_train)
        if ob:
            ob.parent = anchor_objs[sp["anchor"]]

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
cam_three = add_cam("NL_CamThree", (118, -6, 46), ((_xmin + _xmax) / 2, (_ymin + _ymax) / 2, 8.0),
                    lens=30)   # v5.1: 三分之二点机位随新足迹包围盒
cam_front = add_cam("NL_CamFront", (18, -34, 9), (14, 102, 20), lens=26)
_loop_c = _LOOP_C if _LOOP_C else Vector((_A6_LX, _A6_LCY, 0.0))
cam_loop = add_cam("NL_CamLoop", (_loop_c.x + 23.4, _loop_c.y - 25.0, 12), (_loop_c.x, _loop_c.y, 8),
                   lens=44)   # v5.1: 目标=新环心(骨爪/墓碑/观景台入画)
cam_station = add_cam("NL_CamStation", (32, 34, 5.5), (18, 62, 4.5), lens=40)
cam_queue = add_cam("NL_CamQueue", (2.0, 22.0, 24.0), (5.8, 37.0, 0.8), lens=45)   # A1 排队迷宫取证机位
cam_south = add_cam("NL_CamSouth", (50.0, 30.0, 12.0), (42.0, 22.0, 1.0), lens=48)  # A6 南瓜田取证 (螺丝钻东侧)
cam_scream = add_cam("NL_CamScream", (34.5, 39.4, 4.2), (41.5, 46.0, 2.5), lens=50)  # A6 尖叫统计牌取证(西南)
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
fit_cam(cam_loop, (_loop_c.x, _loop_c.y, 8),                         # v5.1: 回环簇取证(爪/碑/台全入画)
        [(_loop_c.x - 10, _loop_c.y - 10.5, 0.5), (_loop_c.x + 10, _loop_c.y + 10.5, 0.5),
         (_loop_c.x, _loop_c.y, 23.5), (_loop_c.x - 10, _loop_c.y + 10.5, 1.0),
         (_loop_c.x + 10, _loop_c.y - 10.5, 1.0), (_A6_LX - 1.6, _A6_LCY - 1.6, 7.5),
         (_A6_LX + 1.6, _A6_LCY + 1.6, 7.5)])
fit_cam(cam_station, (18, 62, 4.5),
        [(8.0, 44.0, 2.4), (15.0, 44.0, 2.4), (8.0, 66.0, 3.0), (15.0, 66.0, 3.0),
         (11.5, 67.2, 9.9)])
fit_cam(cam_front, (16, 70, 7),
        [(8.0, 44.0, 2.4), (15.0, 66.0, 3.0), (11.5, 67.2, 9.9), (6.3, 67.2, 9.6)])
fit_cam(cam_south, (42.0, 22.0, 1.0),
        [(40.5, 18.0, 0.1), (44.5, 18.0, 0.1), (40.5, 26.5, 0.6), (44.5, 26.5, 0.6)])
fit_cam(cam_scream, (41.5, 46.0, 2.5),
        [(40.5, 45.0, 0.1), (42.5, 47.0, 0.1), (40.5, 45.0, 3.2), (42.5, 47.0, 3.2)])

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

# ------------------------------------------ colliders_coaster.json (M3-B2) ----
# 玩家碰撞表 (app 坐标: x=x, z=-y): 与控制器语义对齐 —
#   rects = 轴对齐盒墙(推挤); steps = 顶面平台矩形 {h=顶面高, 台阶≤0.34 可迈上}; circles = 柱/物件(无h=阻挡)
_R = []   # solid walls
_S = []   # step platforms
_C = []   # circles
def wall(x0, y0, x1, y1, t=0.14):
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = max(abs(x1 - x0) / 2, t), max(abs(y1 - y0) / 2, t)
    _R.append({"x": round(cx, 2), "z": round(-cy, 2), "hw": round(hx, 2), "hd": round(hy, 2)})
# 排队迷宫 7 段 + 进场走廊 4 段 + 闸线 + 出口东翼 (M4: 西墙北延/北墙缺口加宽/a 截短重开接口/b 西延封旁路)
wall(3.2, 30.6, 6.0, 30.6); wall(3.2, 30.6, 3.2, 44.2); wall(6.0, 32.2, 6.0, 39.8)
wall(4.6, 32.9, 6.0, 32.9); wall(3.2, 35.2, 4.6, 35.2); wall(4.6, 37.5, 6.0, 37.5)
wall(3.2, 39.8, 4.7, 39.8)
wall(6.0, 40.74, 6.0, 44.2); wall(3.2, 44.2, 8.05, 44.2)
wall(6.5, 40.6, 8.05, 40.6); wall(10.75, 40.6, 12.25, 40.6)
wall(6.0, 39.2, 12.25, 39.2)
wall(8.65, 40.4, 10.15, 40.4)                       # 闸线 (M4 改交互开合)
wall(15.0, 39.4, 15.9, 40.6, t=0.2)                 # 出口东翼
# 回流沟双护栏
wall(10.55, 13.5, 10.55, 40.5); wall(12.45, 13.5, 12.45, 40.5)
# 阶梯槽四道侧墙 (全高实心)
for _wx in (8.35, 10.45, 12.475, 14.725):
    _R.append({"x": _wx, "z": -42.4, "hw": 0.30, "hd": 1.80})
# 站台双 deck (顶面 2.38) + 双槽 7 级台阶
for _dx in (9.4, 13.6):
    _S.append({"x": _dx, "z": -55.0, "hw": 1.35, "hd": 11.0, "h": 2.38})
_d7 = 3.6 / 7
for _k in range(7):
    yc = 40.6 + (_k + 0.5) * _d7
    _S.append({"x": 9.4, "z": round(-yc, 2), "hw": 0.75, "hd": round(_d7 / 2 + 0.02, 3), "h": round(0.34 * (_k + 1), 2)})
    _S.append({"x": 13.6, "z": round(-yc, 2), "hw": 0.90, "hd": round(_d7 / 2 + 0.02, 3), "h": round(0.34 * (_k + 1), 2)})
# 观景塔: 台面 + 搭板 + 18 级楼梯 (v6.3: 俯冲谷观景台 _A6_LX/_A6_LCY = (20,118))
_S.append({"x": round(_A6_LX, 2), "z": round(-_A6_LCY, 2), "hw": 1.14, "hd": 1.14, "h": 7.28})
_S.append({"x": round(_A6_LX + 1.35, 2), "z": round(-_A6_LCY, 2), "hw": 0.70, "hd": 0.65, "h": 7.28})
for _k in range(18):
    _S.append({"x": round(_A6_LX + 5.86 - _k * 0.27, 2), "z": round(-_A6_LCY, 2),
               "hw": 0.135, "hd": 0.55, "h": round(0.40 * (_k + 1), 2)})
# 柱位圆: 雨棚柱6 / 站牌龙门2 / 钟柱 / 出口牌2 / 塔柱4 / 统计牌2
for _cx2 in (7.5, 15.5):
    for _cy2 in (45.5, 55.0, 64.5):
        _C.append({"x": _cx2, "z": round(-_cy2, 2), "r": 0.15})
for _cx2 in (6.3, 16.7):
    _C.append({"x": _cx2, "z": -67.2, "r": 0.20})
_C.append({"x": 9.4, "z": -65.2, "r": 0.12})
for _cx2 in (13.4, 14.1):
    _C.append({"x": _cx2, "z": -39.05, "r": 0.12})
if _A6_TOWER_BUILT:
    for _sx3 in (-1, 1):
        for _sy3 in (-0.9, 0.9):
            _C.append({"x": round(_A6_LX + _sx3 * 3.3, 2), "z": round(-(_A6_LCY + _sy3), 2), "r": 0.18})
for _cy2 in (10.0, 12.0):
    _C.append({"x": 70.0, "z": round(-_cy2, 2), "r": 0.14})
for _cx2 in (3.8, 7.2):
    _C.append({"x": _cx2, "z": -27.5, "r": 0.16})
# 南瓜田 9 颗 (v8.4: 东缘 x78 东侧带)
for _pk in ((84.0, 44.0, 0.30), (85.4, 43.4, 0.22), (86.8, 44.6, 0.26), (83.6, 45.8, 0.19),
            (85.2, 46.6, 0.24), (86.6, 47.4, 0.28), (84.2, 48.8, 0.20), (85.8, 49.6, 0.23),
            (84.6, 51.2, 0.26)):
    _C.append({"x": _pk[0], "z": round(-_pk[1], 2), "r": round(_pk[2] * 0.9, 2)})
coaster_colliders = {
    "version": 1,
    "note": "过山车玩家碰撞表 (app 坐标); 由 roller_coaster.py 建模常数生成; steps.h=顶面高度(≤0.34级差可迈上), rects=盒墙, circles 无h=阻挡",
    "rects": _R, "steps": _S, "circles": _C,
}
with open(OUT / "colliders_coaster.json", "w", encoding="utf-8") as f:
    json.dump(coaster_colliders, f, ensure_ascii=False, indent=1)
print(f"colliders_coaster.json: rects={len(_R)} steps={len(_S)} circles={len(_C)}")

print("\nDONE")
