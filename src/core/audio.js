// 程序化音频（WebAudio 全合成，零音频素材）
//  - 环境风声：噪声 + 低通 + 慢 LFO 起伏
//  - 八音盒 BGM：三角波 + 指数衰减 + 回声，A 小调五声慢圆舞
//  - 乘坐嗡鸣：带通噪声 + 滤频摆动
//  - 收集风铃：五声琶音
export function createAudio(hud) {
  let ctx = null;
  let master = null;
  let started = false;
  let muted = false;
  let rideGain = null;
  let rideFilter = null;
  let bgmTimer = null;

  const NOTE = 0.42; // 一拍秒数
  const MELODY = [
    [880.0, 1], [659.25, 1], [523.25, 1], [0, 1],
    [587.33, 1], [659.25, 2], [0, 1],
    [783.99, 1], [659.25, 1], [523.25, 1], [0, 1],
    [440.0, 2], [0, 2],
    [523.25, 1], [587.33, 1], [659.25, 1], [0, 1],
    [880.0, 1], [783.99, 1], [659.25, 2],
    [0, 4],
  ];

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

  function playNote(freq, t, beats) {
    const dur = beats * NOTE;
    const osc = ctx.createOscillator();
    osc.type = "triangle";
    osc.frequency.value = freq;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(0.16, t + 0.008);
    g.gain.exponentialRampToValueAtTime(0.001, t + Math.max(dur * 1.6, 1.4));
    osc.connect(g).connect(master);
    osc.start(t);
    osc.stop(t + 1.6);
  }

  function startBGM() {
    // 回声总线
    const delay = ctx.createDelay(1.0);
    delay.delayTime.value = 0.45;
    const fb = ctx.createGain();
    fb.gain.value = 0.3;
    delay.connect(fb).connect(delay);
    delay.connect(master);
    bgmBus = delay;
    // 前瞻调度
    let step = 0;
    let nextTime = ctx.currentTime + 0.8;
    bgmTimer = setInterval(() => {
      if (!ctx) return;
      while (nextTime < ctx.currentTime + 1.5) {
        const [freq, beats] = MELODY[step % MELODY.length];
        if (freq > 0) {
          const dur = beats * NOTE;
          const osc = ctx.createOscillator();
          osc.type = "triangle";
          osc.frequency.value = freq;
          const g = ctx.createGain();
          g.gain.setValueAtTime(0, nextTime);
          g.gain.linearRampToValueAtTime(0.10, nextTime + 0.008);
          g.gain.exponentialRampToValueAtTime(0.001, nextTime + Math.max(dur * 1.6, 1.4));
          osc.connect(g);
          g.connect(master);
          g.connect(bgmBus); // 送回声
          osc.start(nextTime);
          osc.stop(nextTime + 1.6);
        }
        nextTime += beats * NOTE;
        step++;
      }
    }, 400);
  }

  let bgmBus = null;

  function startAmbient() {
    const src = ctx.createBufferSource();
    src.buffer = noiseBuffer(3);
    src.loop = true;
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 380;
    const g = ctx.createGain();
    g.gain.value = 0.05;
    // 风声起伏 LFO
    const lfo = ctx.createOscillator();
    lfo.frequency.value = 0.12;
    const lfoG = ctx.createGain();
    lfoG.gain.value = 0.025;
    lfo.connect(lfoG).connect(g.gain);
    src.connect(lp).connect(g).connect(master);
    src.start();
    lfo.start();
  }

  function startRideLoop() {
    const src = ctx.createBufferSource();
    src.buffer = noiseBuffer(2);
    src.loop = true;
    rideFilter = ctx.createBiquadFilter();
    rideFilter.type = "bandpass";
    rideFilter.frequency.value = 320;
    rideFilter.Q.value = 2.2;
    rideGain = ctx.createGain();
    rideGain.gain.value = 0;
    const lfo = ctx.createOscillator();
    lfo.frequency.value = 0.5;
    const lfoG = ctx.createGain();
    lfoG.gain.value = 90;
    lfo.connect(lfoG).connect(rideFilter.frequency);
    src.connect(rideFilter).connect(rideGain).connect(master);
    src.start();
    lfo.start();
  }

  return {
    // 首次手势调用（入园点击）启动整个音频图
    ensure() {
      if (started) {
        ctx?.resume();
        return;
      }
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      master = ctx.createGain();
      master.gain.value = muted ? 0 : 1;
      master.connect(ctx.destination);
      startAmbient();
      startBGM();
      startRideLoop();
      started = true;
    },
    setMuted(m) {
      muted = m;
      if (master) {
        master.gain.cancelScheduledValues(ctx.currentTime);
        master.gain.linearRampToValueAtTime(m ? 0 : 1, ctx.currentTime + 0.25);
      }
    },
    setRiding(on) {
      if (!rideGain) return;
      rideGain.gain.cancelScheduledValues(ctx.currentTime);
      rideGain.gain.linearRampToValueAtTime(on ? 0.12 : 0, ctx.currentTime + 0.8);
    },
    // 收集风铃: 五声上行琶音
    chime(n) {
      if (!ctx) return;
      const base = [523.25, 587.33, 659.25, 783.99, 880.0];
      const t0 = ctx.currentTime;
      base.slice(0, Math.min(n + 1, 5)).forEach((f, i) => {
        const osc = ctx.createOscillator();
        osc.type = "sine";
        osc.frequency.value = f * 2;
        const g = ctx.createGain();
        g.gain.setValueAtTime(0, t0 + i * 0.09);
        g.gain.linearRampToValueAtTime(0.12, t0 + i * 0.09 + 0.01);
        g.gain.exponentialRampToValueAtTime(0.001, t0 + i * 0.09 + 0.9);
        osc.connect(g).connect(master);
        osc.start(t0 + i * 0.09);
        osc.stop(t0 + i * 0.09 + 1.0);
      });
    },
    // 烟花升空啸声: 带通噪声扫频上行 (~1s)
    fireworkLaunch() {
      if (!ctx) return;
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
      src.connect(bp).connect(g).connect(master);
      src.start(t);
      src.stop(t + 1.2);
    },
    // 烟花爆裂: 低通噪声扫频下坠 + 低频正弦轰; 分型尾音
    // A 牡丹 = 纯轰; B 垂柳 = + 金瀑 shimmer 长尾; C 椰芯 = + 连串爆响 (vol 按爆点距离衰减)
    fireworkBurst(vol = 1, kind = "A") {
      if (!ctx) return;
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
      src.connect(lp).connect(g).connect(master);
      src.start(t);
      src.stop(t + 1.0);
      const osc = ctx.createOscillator();
      osc.type = "sine";
      osc.frequency.setValueAtTime(110, t);
      osc.frequency.exponentialRampToValueAtTime(38, t + 0.5);
      const og = ctx.createGain();
      og.gain.setValueAtTime(0.22 * vol, t);
      og.gain.exponentialRampToValueAtTime(0.0001, t + 0.6);
      osc.connect(og).connect(master);
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
        s2.connect(bp).connect(g2).connect(master);
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
          s3.connect(hp).connect(g3).connect(master);
          s3.start(pt, Math.random() * 1.2, 0.1);
          pt += 0.08 + Math.random() * 0.07;
        }
      }
    },
  };
}
