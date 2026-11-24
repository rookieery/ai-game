// 旧版烟花音效快照 —— 取自 src/core/audio.js @ 43c804c 的 noiseBuffer / fireworkLaunch / fireworkBurst
// 用途仅两个: 试听页的「旧版」A/B 对照、取证探针的 before 基线。游戏接入新合成器后请勿再改这里,
// 否则 before 不再是 before。
export function createLegacy(ctx, dest) {
  function noiseBuffer(seconds) {
    const buf = ctx.createBuffer(1, ctx.sampleRate * seconds, ctx.sampleRate);
    const d = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < d.length; i++) {
      const w = Math.random() * 2 - 1;
      last = (last + 0.02 * w) / 1.02; // 布朗噪声, 更像风
      d[i] = last * 3.2;
    }
    return buf;
  }

  // 烟花升空啸声: 带通噪声扫频上行 (~1s)
  function launch() {
    const t = ctx.currentTime;
    const src = ctx.createBufferSource();
    src.buffer = noiseBuffer(1.2);
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.Q.value = 6;
    bp.frequency.setValueAtTime(500, t);
    bp.frequency.exponentialRampToValueAtTime(2400, t + 1.0);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.05, t + 0.25);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 1.1);
    src.connect(bp).connect(g).connect(dest);
    src.start(t);
    src.stop(t + 1.2);
  }

  // 烟花爆裂: 低通噪声扫频下坠 + 低频正弦轰; 分型尾音
  function burst(vol = 1, kind = "A") {
    const t = ctx.currentTime;
    const src = ctx.createBufferSource();
    src.buffer = noiseBuffer(1.0);
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.setValueAtTime(3200, t);
    lp.frequency.exponentialRampToValueAtTime(160, t + 0.7);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.28 * vol, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.85);
    src.connect(lp).connect(g).connect(dest);
    src.start(t);
    src.stop(t + 1.0);
    const osc = ctx.createOscillator();
    osc.type = "sine";
    osc.frequency.setValueAtTime(110, t);
    osc.frequency.exponentialRampToValueAtTime(38, t + 0.5);
    const og = ctx.createGain();
    og.gain.setValueAtTime(0.22 * vol, t);
    og.gain.exponentialRampToValueAtTime(0.0001, t + 0.6);
    osc.connect(og).connect(dest);
    osc.start(t);
    osc.stop(t + 0.7);
    if (kind === "B") {
      // 垂柳 shimmer: 带通噪声缓缓下滑 2.2s, 如金瀑簌簌
      const s2 = ctx.createBufferSource();
      s2.buffer = noiseBuffer(2.4);
      const bp = ctx.createBiquadFilter();
      bp.type = "bandpass";
      bp.Q.value = 1.2;
      bp.frequency.setValueAtTime(1600, t + 0.15);
      bp.frequency.exponentialRampToValueAtTime(420, t + 2.3);
      const g2 = ctx.createGain();
      g2.gain.setValueAtTime(0.0001, t + 0.15);
      g2.gain.exponentialRampToValueAtTime(0.075 * vol, t + 0.45);
      g2.gain.exponentialRampToValueAtTime(0.0001, t + 2.35);
      s2.connect(bp).connect(g2).connect(dest);
      s2.start(t + 0.15);
      s2.stop(t + 2.4);
    } else if (kind === "C") {
      // 椰芯连串爆响: 二次炸裂时刻的短促噼啪串
      const cb = noiseBuffer(1.4);
      const pops = 7 + ((Math.random() * 4) | 0);
      let pt = t + 0.75;
      for (let i = 0; i < pops; i++) {
        const s3 = ctx.createBufferSource();
        s3.buffer = cb;
        const hp = ctx.createBiquadFilter();
        hp.type = "highpass";
        hp.frequency.value = 2200 + Math.random() * 1200;
        const g3 = ctx.createGain();
        g3.gain.setValueAtTime((0.05 + Math.random() * 0.06) * vol, pt);
        g3.gain.exponentialRampToValueAtTime(0.0001, pt + 0.09);
        s3.connect(hp).connect(g3).connect(dest);
        s3.start(pt, Math.random() * 1.2, 0.1);
        pt += 0.08 + Math.random() * 0.07;
      }
    }
  }

  return { launch, burst };
}

// 旧版距离模型: 只按 1 - d/300 线性调音量（无延迟/声像/音色变化）
export const legacyVol = (d) => Math.max(0.12, Math.min(1, 1 - d / 300));
