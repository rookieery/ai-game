// 输入层：键盘状态 + 指针锁定 + 鼠标视角增量
export function createInput(canvas) {
  const keys = new Set();
  const pressHandlers = new Map(); // code -> [cb, ...]（同一键可多订阅）
  const lockListeners = [];
  let locked = false;
  const mouse = { dx: 0, dy: 0 };

  window.addEventListener("keydown", (e) => {
    if (e.repeat) return;
    keys.add(e.code);
    for (const cb of pressHandlers.get(e.code) ?? []) cb();
  });
  window.addEventListener("keyup", (e) => keys.delete(e.code));
  window.addEventListener("blur", () => keys.clear());

  window.addEventListener("mousemove", (e) => {
    if (locked) {
      mouse.dx += e.movementX;
      mouse.dy += e.movementY;
    }
  });

  document.addEventListener("pointerlockchange", () => {
    locked = document.pointerLockElement === canvas;
    mouse.dx = 0;
    mouse.dy = 0;
    for (const cb of lockListeners) cb(locked);
  });

  return {
    isDown: (code) => keys.has(code),
    onPress(code, cb) {
      let arr = pressHandlers.get(code);
      if (!arr) {
        arr = [];
        pressHandlers.set(code, arr);
      }
      arr.push(cb);
    },
    consumeMouse() {
      const d = { dx: mouse.dx, dy: mouse.dy };
      mouse.dx = 0;
      mouse.dy = 0;
      return d;
    },
    requestLock() {
      if (!locked && canvas.requestPointerLock) canvas.requestPointerLock();
    },
    get locked() { return locked; },
    onLockChange(cb) { lockListeners.push(cb); },
  };
}
