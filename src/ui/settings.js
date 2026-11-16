// 设置面板：右上角齿轮按钮 + 右侧抽屉
// 行为约定：
//   · 打开时释放指针锁定（等同 Esc），关闭后点击画面重新锁定
//   · 快捷键 O 开关；Esc 在面板打开时关闭面板
//   · 滑杆 input -> settings.set -> 主循环侧统一 applySettings，即时生效
import { SETTINGS_GROUPS } from "../core/config.js";

const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  return n;
};

const GEAR_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
  <circle cx="12" cy="12" r="3.1"/>
  <path d="M12 2.6v2.8M12 18.6v2.8M2.6 12h2.8M18.6 12h2.8M5.35 5.35l2 2M16.65 16.65l2 2M18.65 5.35l-2 2M7.35 16.65l-2 2"/>
</svg>`;

export function createSettingsPanel(settings, { onOpenChange } = {}) {
  const hudRoot = document.getElementById("hud");

  // ---------- 齿轮按钮 ----------
  const gearBtn = el("button", "gear-btn");
  gearBtn.type = "button";
  gearBtn.setAttribute("aria-label", "园区设置 (O)");
  gearBtn.innerHTML = GEAR_SVG;

  // ---------- 抽屉 ----------
  const drawer = el("aside", "settings-drawer");
  drawer.setAttribute("aria-label", "园区设置");

  const head = el("header", "settings-head");
  const title = el("div", "settings-title", "园区设置");
  const closeBtn = el("button", "settings-close", "×");
  closeBtn.type = "button";
  closeBtn.setAttribute("aria-label", "关闭设置 (Esc)");
  head.append(title, closeBtn);

  const body = el("div", "settings-body");
  const foot = el("footer", "settings-foot");
  const resetBtn = el("button", "settings-reset", "恢复默认");
  resetBtn.type = "button";
  foot.append(resetBtn, el("div", "settings-foot-hint", "配置自动保存 · 下次入园保留"));
  drawer.append(head, body, foot);

  hudRoot.append(gearBtn, drawer);

  // ---------- 滑杆行 ----------
  const rows = []; // { item, input, valEl }
  for (const group of SETTINGS_GROUPS) {
    const section = el("section", "set-group");
    section.append(el("h3", null, group.name));
    for (const item of group.items) {
      const row = el("div", "set-row");
      const headRow = el("div", "set-head");
      const valEl = el("span", "set-val", item.fmt(settings.get(item.key)));
      headRow.append(el("label", "set-label", item.label), valEl);
      const input = el("input", "set-slider");
      input.type = "range";
      input.min = item.min;
      input.max = item.max;
      input.step = item.step;
      input.value = settings.get(item.key);
      input.setAttribute("aria-label", item.label);
      input.addEventListener("input", () => {
        const v = parseFloat(input.value);
        valEl.textContent = item.fmt(v);
        settings.set(item.key, v);
      });
      row.append(headRow, input);
      section.append(row);
      rows.push({ item, input, valEl });
    }
    body.append(section);
  }

  function syncAll() {
    for (const { item, input, valEl } of rows) {
      input.value = settings.get(item.key);
      valEl.textContent = item.fmt(settings.get(item.key));
    }
  }

  // ---------- 开合状态 ----------
  let open = false;
  function setOpen(v) {
    if (open === v) return;
    open = v;
    drawer.classList.toggle("open", open);
    gearBtn.classList.toggle("active", open);
    if (open && document.pointerLockElement) document.exitPointerLock();
    onOpenChange && onOpenChange(open);
  }

  gearBtn.addEventListener("click", () => setOpen(!open));
  closeBtn.addEventListener("click", () => setOpen(false));
  resetBtn.addEventListener("click", () => {
    settings.reset(); // onChange -> main.js applyAll；这里只负责回填 UI
    syncAll();
  });

  window.addEventListener("keydown", (e) => {
    if (e.repeat) return;
    if (e.code === "KeyO") {
      e.preventDefault();
      setOpen(!open);
    } else if (e.code === "Escape" && open) {
      setOpen(false);
    }
  });

  return {
    get isOpen() { return open; },
    open: () => setOpen(true),
    close: () => setOpen(false),
  };
}
