// 程序化音频（WebAudio 全合成，零音频素材）
//  - 环境风声：噪声 + 低通 + 慢 LFO 起伏
//  - 八音盒 BGM：三角波 + 指数衰减 + 回声，A 小调五声慢圆舞
//  - 乘坐嗡鸣：带通噪声 + 滤频摆动
//  - 收集风铃：五声琶音
//  - 烟花：音色合成与空间播放全在 fw_sound.js（爆裂 / 碎裂 / 升空哨音 + 声延迟·声像·距离衰减）,
//    这里只负责建声、接 master、套设置项
import { createFwVoice } from "./fw_sound.js";

export function createAudio(hud) {
  let ctx = null;
  let master = null;
  let started = false;
  let muted = false;
  let rideGain = null;
  let rideFilter = null;
  let bgmTimer = null;
  let bgmGain = null;
  let bgmWanted = true; // 设置面板「背景音乐」开关 (音频图未启动前先记意图, ensure 时生效)
  let fw = null;        // 烟花播放引擎 (ensure 后创建)
  // 烟花设置意图 (音频图未启动前先记下); 取值口径同 core/config.js 烟花组
  const fwSet = { volume: 1, delay: true, ascentDb: 0, brightness: 0, crackle: true };
  const pct = (v, lo, hi) => Math.max(lo, Math.min(hi, Number(v))) / 100;
  function applyFw() {
    if (!fw) return;
    fw.setVolume(fwSet.volume);
    fw.setDelay(fwSet.delay);
    fw.setAscentLevel(fwSet.ascentDb);
    fw.setBrightness(fwSet.brightness);
    fw.setCrackle(fwSet.crackle);
  }

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
    // BGM 专用总线: 开关只切八音盒, 环境风/乘坐嗡鸣/风铃直连 master 不受控
    bgmGain = ctx.createGain();
    bgmGain.gain.value = bgmWanted ? 1 : 0;
    bgmGain.connect(master);
    // 回声总线
    const delay = ctx.createDelay(1.0);
    delay.delayTime.value = 0.45;
    const fb = ctx.createGain();
    fb.gain.value = 0.3;
    delay.connect(fb).connect(delay);
    delay.connect(bgmGain);
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
          g.connect(bgmGain);
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
      fw = createFwVoice(ctx);   // 烟花: 经自带总线限幅后进 master, 随 HUD 静音一起静音
      fw.output.connect(master);
      applyFw();
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
    // 背景音乐开关 (仅八音盒 BGM; 未启动时只记意图, ensure 后生效)
    setBGM(on) {
      bgmWanted = !!on;
      if (bgmGain) {
        bgmGain.gain.cancelScheduledValues(ctx.currentTime);
        bgmGain.gain.linearRampToValueAtTime(bgmWanted ? 1 : 0, ctx.currentTime + 0.4);
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
    // ---- 烟花: 三个发声触发点 (fx/fireworks.js 调用), o = { dist 距离(m), pan 方位(-1 左..1 右), at 画面事件时刻 } ----
    // 声延迟由播放引擎按 dist 叠加 (343m/s); 音频未启动时静默返回
    fireworkLaunch(o) {
      fw?.launch(o);            // 管口闷响 + 连续哨音 (o.ascent 升空秒数, o.endDist 炸点距离: 哨音响到炸点)
    },
    fireworkBurst(kind, o) {
      fw?.burst(kind, o);       // 裂响 → 轰鸣 → 滚动尾音, 叠碎裂层
    },
    fireworkCrack(o) {
      fw?.crack(o);             // 椰芯火星分裂的脆响
    },
    // 烟花设置 (取值口径见 core/config.js 烟花组; 音频未启动时只记意图)
    setFireworks(v = {}) {
      fwSet.volume = pct(v.fireworkVolume ?? 100, 0, 200);
      fwSet.delay = v.fireworkSoundDelay !== false;
      fwSet.ascentDb = 20 * Math.log10(pct(v.fireworkAscentVolume ?? 100, 50, 200));
      fwSet.brightness = (pct(v.fireworkCrisp ?? 100, 50, 200) - 1) * 8;   // 100% = 标准, 每 +50% 高架 +4dB
      fwSet.crackle = v.fireworkCrackle !== false;
      applyFw();
    },
    // 调试钩子 (取证脚本用)
    get fw() { return fw; },
    get ctx() { return ctx; },
    get master() { return master; },
  };
}
