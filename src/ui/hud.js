// 幽夜游乐场 HUD：组件构建 + 状态驱动
// 世界：降神之夜 The Séance（契约见 .impeccable/surfaces/index-html.md）
const SVG = {
  star: `<svg viewBox="0 0 24 24"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.2 L18.2 21.8 L12 17 L5.8 21.8 L8.2 14.2 L2 9.6 L9.6 9.6 Z"/></svg>`,
  moon: `<svg viewBox="0 0 32 32"><path class="moon-path" d="M22 4 A12 12 0 1 0 22 28 A14.5 14.5 0 0 1 22 4 Z"/><line class="slash" x1="5" y1="27" x2="27" y2="5"/></svg>`,
  pendulum: `<svg viewBox="0 0 22 30"><line class="chain" x1="11" y1="0" x2="11" y2="16"/><circle class="bob" cx="11" cy="21" r="7"/><circle class="dot" cx="11" cy="21" r="2.6"/></svg>`,
};

const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  return n;
};

export function createHUD() {
  const hudRoot = document.getElementById("hud");

  // ---------- 加载屏（DOM 在 index.html，这里只驱动） ----------
  const loading = document.getElementById("loading-screen");
  const board = document.getElementById("seance-board");
  const pct = document.getElementById("load-pct");
  const summon = document.getElementById("summon-line");
  const planchette = document.getElementById("planchette");
  const arcSpans = [...document.querySelectorAll("#board-arc span")];
  const starBtn = document.getElementById("enter-btn");
  const enterHint = document.getElementById("enter-hint");

  let targetP = 0;
  let shownP = 0;
  let ready = false;

  // 平滑显示进度（rAF 内插，避免跳变）
  function tick() {
    if (shownP !== targetP) {
      shownP += (targetP - shownP) * 0.12;
      if (Math.abs(targetP - shownP) < 0.004) shownP = targetP;
      renderProgress(shownP);
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);

  function renderProgress(p) {
    const pctNum = Math.round(p * 100);
    pct.textContent = `${pctNum}%`;
    // 灵摆沿字母弧滑行 12% -> 74%（滑过哪个字母，哪个字母点亮）
    planchette.style.left = `${12 + p * 62}%`;
    // 字母弧逐字点亮
    const lit = Math.floor(p * arcSpans.length);
    arcSpans.forEach((s, i) => s.classList.toggle("lit", i < lit));
  }

  function setReady() {
    if (ready) return;
    ready = true;
    targetP = 1;
    shownP = 1;
    renderProgress(1);
    summon.textContent = "显灵完成 · 点五芒星入园";
    starBtn.disabled = false;
    starBtn.classList.add("ready");
    enterHint.classList.add("show");
  }

  // ---------- HUD 组件 ----------
  const keysBar = el("div", "keys-bar");
  keysBar.append(
    keycap("W A S D", "移动"),
    keycap("Space", "跳跃"),
    keycap("E", "互动"),
    keycap("Shift", "疾走"),
    keycap("Esc", "释放鼠标"),
    keycap("O", "设置"),
  );
  function keycap(k, label) {
    const wrap = el("span", "key-group");
    wrap.style.display = "flex";
    wrap.style.alignItems = "center";
    wrap.style.gap = "8px";
    const cap = el("span", "keycap", k);
    const lab = el("span", "key-label", label);
    wrap.append(cap, lab);
    return wrap;
  }

  const starMap = el("div", "star-map");
  const starSvgs = [];
  const starCount = el("span", "star-count", "");
  starMap.append(starCount);
  function setStars(got, total) {
    while (starSvgs.length < total) {
      const s = el("span");
      s.innerHTML = SVG.star;
      const svg = s.firstChild;
      starSvgs.push(svg);
      starMap.insertBefore(s, starCount);
    }
    starSvgs.forEach((s, i) => s.classList.toggle("lit", i < got));
    starCount.textContent = `${got} / ${total}`;
    starMap.classList.add("show");
  }

  const moonToggle = el("button", "moon-toggle on");
  moonToggle.type = "button";
  moonToggle.setAttribute("aria-label", "声音开关");
  moonToggle.innerHTML = SVG.moon;
  let onMute = null;
  moonToggle.addEventListener("click", () => {
    const mutedNow = moonToggle.classList.contains("on");
    setMuted(mutedNow);
    if (onMute) onMute(mutedNow);
  });
  function setMuted(muted) {
    moonToggle.classList.toggle("on", !muted);
    moonToggle.classList.toggle("off", muted);
    moonToggle.setAttribute("aria-label", muted ? "开启声音" : "静音");
    try { localStorage.setItem("hnc-muted", muted ? "1" : "0"); } catch { /* 隐私模式忽略 */ }
  }
  let stored = null;
  try { stored = localStorage.getItem("hnc-muted"); } catch { /* 忽略 */ }
  setMuted(stored === "1");

  const prompt = el("div", "spirit-prompt");
  const pendulum = el("span", "pendulum", SVG.pendulum);
  const promptKey = keycap("E", "");
  promptKey.style.marginRight = "0";
  const promptText = el("span", "prompt-text", "");
  prompt.append(pendulum, promptKey, promptText);

  const plaque = el("div", "ride-plaque");
  const plaqueName = el("div", "plaque-name", "");
  const plaqueHint = el("div", "plaque-hint", "");
  plaque.append(plaqueName, plaqueHint);

  const veil = el("div", "");
  veil.id = "fade-veil";

  const lookHint = el("div", "look-hint", "点击画面 · 锁定视角");
  const toastEl = el("div", "toast");
  let toastTimer = null;

  hudRoot.append(keysBar, starMap, moonToggle, prompt, plaque, lookHint, toastEl, veil);

  // ---------- 公开 API ----------
  let enterCb = null;
  starBtn.addEventListener("click", () => {
    if (!ready || !enterCb) return;
    board.classList.add("flash");
    setTimeout(enterCb, 420); // 等辉光一闪到峰值
  });

  return {
    // 加载
    setLoadingProgress(p) { if (!ready) targetP = Math.min(Math.max(p, 0), 0.99); },
    setReady,
    onEnter(cb) { enterCb = cb; },
    // 入园：加载屏淡出（终态移出无障碍树），键位条现身，6s 后减淡
    enterPark() {
      loading.classList.add("hidden");
      loading.addEventListener("transitionend", () => loading.classList.add("gone"), { once: true });
      keysBar.classList.add("show");
      setTimeout(() => keysBar.classList.add("dim"), 6000);
    },
    // 交互提示（灵摆指向 E 键帽）
    showPrompt(text, key = "E") {
      if (promptText.textContent === text && prompt.classList.contains("show")) return;
      promptKey.querySelector(".keycap").textContent = key;
      promptText.textContent = text;
      prompt.classList.add("show");
    },
    hidePrompt() { prompt.classList.remove("show"); },
    // 打卡
    setStars,
    // 乘坐铭牌
    showPlaque(name, hint) {
      plaqueName.textContent = name;
      plaqueHint.textContent = hint;
      plaque.classList.add("show");
    },
    hidePlaque() { plaque.classList.remove("show"); },
    // 转场遮罩：淡入 → cb（切换）→ 淡出
    transition(cb) {
      veil.classList.add("active");
      setTimeout(() => {
        cb && cb();
        setTimeout(() => veil.classList.remove("active"), 120);
      }, 420);
    },
    // 声音
    onMuteChange(cb) { onMute = cb; },
    isMuted: () => moonToggle.classList.contains("off"),
    // 视角锁定提示
    setLookHint(v) { lookHint.classList.toggle("show", v); },
    // 顶部横幅
    toast(text) {
      toastEl.textContent = text;
      toastEl.classList.add("show");
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toastEl.classList.remove("show"), 2600);
    },
  };
}
