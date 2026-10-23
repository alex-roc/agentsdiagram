// Shared by the documentation pages: theme toggle and copy buttons on code blocks.
(function () {
  var KEY = "agentsdiagram.theme";
  var root = document.documentElement;
  var btn = document.getElementById("theme");
  var mq = window.matchMedia("(prefers-color-scheme: dark)");
  function current() { return root.dataset.theme || (mq.matches ? "dark" : "light"); }
  function label() {
    btn.setAttribute("aria-label", current() === "dark" ? "Switch to light theme" : "Switch to dark theme");
  }
  label();
  mq.addEventListener("change", label);
  btn.addEventListener("click", function () {
    var next = current() === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem(KEY, next); } catch (e) {}
    label();
    // embedded demos read the same key on load
    Array.prototype.forEach.call(document.querySelectorAll("figure.live iframe"), function (f) {
      try { f.contentWindow.location.reload(); } catch (e) {}
    });
  });

  // Keep the navigation open on wide screens, collapsed on phones.
  var navBox = document.querySelector(".docs-nav");
  if (navBox && window.matchMedia("(max-width: 860px)").matches) navBox.open = false;

  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) {}
    document.body.removeChild(ta);
    return ok ? Promise.resolve() : Promise.reject();
  }
  Array.prototype.forEach.call(document.querySelectorAll(".prose .hl"), function (block) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "copy";
    b.textContent = "Copy";
    b.addEventListener("click", function () {
      var text = block.querySelector("pre").innerText.replace(/\n$/, "");
      copy(text).then(function () { b.textContent = "Copied"; }, function () { b.textContent = "Press ⌘C"; })
        .then(function () { setTimeout(function () { b.textContent = "Copy"; }, 1600); });
    });
    block.appendChild(b);
  });
})();
