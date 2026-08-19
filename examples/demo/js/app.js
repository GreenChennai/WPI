// WPI 示例页脚本：canvas 进度动画 + 状态标记
(function () {
  const canvas = document.getElementById("stage");
  const footer = document.getElementById("footer");
  if (!canvas || !footer) return;

  const ctx = canvas.getContext("2d");
  const DURATION = 2600; // ms，动画完成后绘制最终静止画面
  const start = performance.now();
  const w = canvas.width;
  const h = canvas.height;

  let finished = false;

  function drawBar(progress) {
    ctx.clearRect(0, 0, w, h);
    // 轨道
    ctx.fillStyle = "#e4e8f7";
    ctx.fillRect(20, 52, w - 40, 16);
    // 进度条
    const grad = ctx.createLinearGradient(20, 0, w - 40, 0);
    grad.addColorStop(0, "#4a6cf7");
    grad.addColorStop(1, "#7b96ff");
    ctx.fillStyle = grad;
    ctx.fillRect(20, 52, (w - 40) * progress, 16);

    // 圆点
    const x = 20 + (w - 40) * progress;
    const y = 24 + 26 * (1 - progress);
    ctx.beginPath();
    ctx.arc(x, y, 9, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(247,107,74,0.9)";
    ctx.fill();

    // 文本
    ctx.fillStyle = "#1d2233";
    ctx.font = "13px 'Segoe UI','Microsoft YaHei',sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(Math.round(progress * 100) + "%", w / 2, 30);
  }

  function frame(now) {
    const p = Math.min(1, (now - start) / DURATION);
    drawBar(p);
    if (p >= 1) {
      finished = true;
      footer.textContent = "动画已完成 — 此即导出终帧";
      footer.style.color = "#2e7d32";
      return;
    }
    footer.textContent = "动画播放中…";
    requestAnimationFrame(frame);
  }

  // 动画结束后 DOM 状态也同步到位（验证 getAnimations / 帧稳定判据）
  footer.dataset.done = "0";
  setTimeout(function () {
    footer.dataset.done = "1";
  }, DURATION + 300);

  requestAnimationFrame(frame);
})();