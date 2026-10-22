"use strict";
const slider = document.getElementById("compare-slider");
const layer = document.getElementById("candidate-layer");
const line = document.getElementById("split-line");
const value = document.getElementById("slider-value");
slider.addEventListener("input", () => {
  const position = Math.max(0, Math.min(100, Number(slider.value)));
  layer.style.clipPath = `inset(0 ${100 - position}% 0 0)`;
  line.style.left = `${position}%`;
  value.textContent = `${position}%`;
});
document.getElementById("copy-skill").addEventListener("click", async () => {
  const command = document.getElementById("skill-command").textContent;
  const status = document.getElementById("copy-status");
  try {
    await navigator.clipboard.writeText(command);
    status.textContent = "已复制，可粘贴到项目终端。";
  } catch {
    status.textContent = "浏览器未允许复制，请选中上方命令手动复制。";
  }
});
