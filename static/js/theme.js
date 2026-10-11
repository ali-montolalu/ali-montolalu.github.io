/* 明暗主题切换（无第三方依赖）。三态：跟随系统 → 亮 → 暗 → 跟随系统。
   首屏的 data-theme 已由 <head> 里的内联脚本设好；这里只负责按钮、记忆和 giscus。 */
(function () {
  var KEY = "theme", root = document.documentElement;
  var mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  function getStored() { try { var v = localStorage.getItem(KEY); return v === "light" || v === "dark" ? v : null; } catch (e) { return null; } }
  function setStored(v) { try { if (v) localStorage.setItem(KEY, v); else localStorage.removeItem(KEY); } catch (e) {} }
  var pref = getStored() || "system";
  function effective() { return pref === "system" ? (mq && mq.matches ? "dark" : "light") : pref; }
  function giscusTheme() { return effective() === "dark" ? "dark" : "light"; }
  var giscusScript = null;   // theme.js 生成的 giscus client.js；执行前改它的 data-theme 即可
  function giscusFrame() { return document.querySelector("iframe.giscus-frame"); }
  function sendGiscus() {
    if (giscusScript && giscusScript.isConnected) giscusScript.setAttribute("data-theme", giscusTheme());
    var f = giscusFrame();
    if (f && f.contentWindow) f.contentWindow.postMessage({ giscus: { setConfig: { theme: giscusTheme() } } }, "https://giscus.app");
  }
  var btn = document.getElementById("theme-toggle");
  function render() {
    var eff = effective();
    root.setAttribute("data-theme", eff);
    root.setAttribute("data-theme-pref", pref);
    if (btn) {
      var label = btn.getAttribute("data-label-" + pref);
      var aria = btn.getAttribute("data-aria-" + pref);
      btn.querySelector(".theme-toggle-text").textContent = label;
      btn.setAttribute("aria-label", aria);
      btn.setAttribute("title", aria);
    }
    sendGiscus();
  }
  if (btn) {
    btn.hidden = false;
    btn.addEventListener("click", function () {   // <button> 自带 Enter / 空格键盘操作
      pref = pref === "system" ? "light" : pref === "light" ? "dark" : "system";
      setStored(pref === "system" ? null : pref);
      render();
    });
  }
  if (mq) {
    var onChange = function () { if (pref === "system") render(); };
    if (mq.addEventListener) mq.addEventListener("change", onChange); else if (mq.addListener) mq.addListener(onChange);
  }
  // giscus：按当前主题创建官方 client.js。执行前的切换直接改 data-theme；
  // iframe load 后与 iframe 发来消息时各主动同步一次（只认 giscus.app 且来源是该 iframe）。
  var mount = document.getElementById("giscus-mount");
  if (mount) {
    var s = document.createElement("script");
    s.src = "https://giscus.app/client.js";
    for (var i = 0; i < mount.attributes.length; i++) {
      var a = mount.attributes[i];
      if (a.name.indexOf("data-") === 0) s.setAttribute(a.name, a.value);
    }
    s.setAttribute("data-theme", giscusTheme());
    s.crossOrigin = "anonymous";
    s.async = true;
    giscusScript = s;
    mount.parentNode.insertBefore(s, mount.nextSibling);
    var hooked = null;
    var hook = function () {
      var f = giscusFrame();
      if (f && f !== hooked) { hooked = f; f.addEventListener("load", sendGiscus); }
    };
    if (window.MutationObserver) new MutationObserver(hook).observe(mount.parentNode, { childList: true, subtree: true });
    window.addEventListener("message", function (e) {
      var f = giscusFrame();
      if (e.origin === "https://giscus.app" && f && e.source === f.contentWindow && e.data && e.data.giscus) sendGiscus();
    });
  }
  render();
})();
