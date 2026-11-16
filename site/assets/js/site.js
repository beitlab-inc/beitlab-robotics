// Beitlab Robotics site: theme toggle, menus, copy buttons, heading anchors, TOC highlight, video chapters.
(function () {
  "use strict";
  var root = document.documentElement;

  function store(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* private mode */ } }

  var themeBtn = document.querySelector(".theme-toggle");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var current = root.dataset.theme ||
        (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
      var next = current === "light" ? "dark" : "light";
      root.dataset.theme = next;
      store("bl-theme", next);
    });
  }

  function toggler(button, panel) {
    if (!button || !panel) return;
    button.addEventListener("click", function () {
      var open = panel.classList.toggle("open");
      button.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }
  toggler(document.querySelector(".nav-toggle"), document.getElementById("site-nav"));
  toggler(document.querySelector(".side-toggle"), document.getElementById("docs-nav"));

  // Copy buttons on code blocks (prompt markers and comments are left out).
  document.querySelectorAll("pre").forEach(function (pre) {
    var btn = document.createElement("button");
    btn.className = "copy";
    btn.type = "button";
    btn.textContent = "Copy";
    btn.addEventListener("click", function () {
      var clone = pre.querySelector("code").cloneNode(true);
      clone.querySelectorAll(".p, .c").forEach(function (n) { n.remove(); });
      var text = clone.textContent.replace(/\n{2,}/g, "\n").trim();
      var done = function () { btn.textContent = "Copied"; setTimeout(function () { btn.textContent = "Copy"; }, 1400); };
      if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () {});
    });
    pre.appendChild(btn);
  });

  // Hover anchors on headings with ids.
  document.querySelectorAll(".prose h2[id], .prose h3[id]").forEach(function (h) {
    var a = document.createElement("a");
    a.className = "anchor";
    a.href = "#" + h.id;
    a.setAttribute("aria-label", "Link to this section");
    a.textContent = "#";
    h.appendChild(a);
  });

  // Highlight the current section in "On this page".
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll(".toc a"));
  if (tocLinks.length && "IntersectionObserver" in window) {
    var byId = {};
    tocLinks.forEach(function (a) { byId[a.getAttribute("href").slice(1)] = a; });
    var visible = {};
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { visible[e.target.id] = e.isIntersecting; });
      var first = tocLinks.find(function (a) { return visible[a.getAttribute("href").slice(1)]; });
      if (first) {
        tocLinks.forEach(function (a) { a.classList.toggle("active", a === first); });
      }
    }, { rootMargin: "-70px 0px -65% 0px" });
    Object.keys(byId).forEach(function (id) {
      var h = document.getElementById(id);
      if (h) obs.observe(h);
    });
  }

  // Video chapters: <button data-seek="SECONDS" data-video="ID">.
  document.querySelectorAll("[data-seek]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var video = document.getElementById(btn.dataset.video);
      if (!video) return;
      video.currentTime = parseFloat(btn.dataset.seek);
      video.play().catch(function () {});
      video.scrollIntoView({ block: "center", behavior: "smooth" });
    });
  });
  document.querySelectorAll("video[data-chapters]").forEach(function (video) {
    var buttons = Array.prototype.slice.call(document.querySelectorAll('.chapters [data-video="' + video.id + '"]'));
    video.addEventListener("timeupdate", function () {
      var t = video.currentTime, current = null;
      buttons.forEach(function (b) { if (parseFloat(b.dataset.seek) <= t + 0.2) current = b; });
      buttons.forEach(function (b) { b.classList.toggle("active", b === current); });
    });
  });

  // Homepage: one CAD orbit, frame chosen by scroll position.
  var orbit = document.querySelector(".orbit");
  var canvas = document.getElementById("orbit-canvas");
  if (orbit && canvas && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    var count = parseInt(canvas.dataset.count, 10);
    var src = canvas.dataset.src;
    var beats = Array.prototype.slice.call(orbit.querySelectorAll(".orbit-beat"));
    var frames = new Array(count);
    var shown = -1;
    var ctx = canvas.getContext("2d", { alpha: true });
    // Where the robot sits inside every frame. The rest of the frame is empty.
    var box = { x: 0.25, y: 0.115, w: 0.50, h: 0.80 };

    function pad(i) { return (i < 10 ? "0" : "") + i; }
    function headerH() {
      var v = getComputedStyle(document.documentElement).getPropertyValue("--header-h");
      var n = parseFloat(v);
      return n || 64;
    }
    function textBottom() {
      var panel = orbit.querySelector(".orbit-panel");
      var bottom = 0;
      // The buttons sit at the foot of the stage, so only the headline and the line under it
      // reserve space. Otherwise the robot shrinks to fit the tallest beat on every frame.
      beats.forEach(function (b) {
        var line = b.querySelector("p");
        if (line) bottom = Math.max(bottom, line.offsetTop + line.offsetHeight);
      });
      return Math.min(panel.clientHeight * 0.34, bottom + 18);
    }
    function progress() {
      var travel = orbit.offsetHeight - orbit.querySelector(".orbit-sticky").offsetHeight;
      if (travel <= 0) return 0;
      var y = headerH() - orbit.getBoundingClientRect().top;
      return Math.min(1, Math.max(0, y / travel));
    }
    function paint(i) {
      var img = frames[i];
      if (!img) {
        for (var d = 1; d < count; d++) {
          if (frames[i - d]) { img = frames[i - d]; break; }
          if (frames[i + d]) { img = frames[i + d]; break; }
        }
      }
      if (!img) return;
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      var w = canvas.clientWidth, h = canvas.clientHeight;
      var pw = Math.round(w * dpr), ph = Math.round(h * dpr);
      if (canvas.width !== pw || canvas.height !== ph) {
        canvas.width = pw;
        canvas.height = ph;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      // Fit the robot, not the empty frame, into the space under the type.
      var top = textBottom(), avail = h - top - 76;
      var scale = Math.min((w * 0.94) / (box.w * img.width), avail / (box.h * img.height));
      var dw = img.width * scale, dh = img.height * scale;
      var x = (w - box.w * dw) / 2 - box.x * dw;
      var y = top - box.y * dh;
      var sx = x + dw * 0.5, sy = y + dh * 0.9, rad = dw * 0.2;
      var shade = ctx.createRadialGradient(sx, sy, rad * 0.15, sx, sy, rad);
      shade.addColorStop(0, "rgba(0, 0, 0, 0.38)");
      shade.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = shade;
      ctx.beginPath();
      ctx.ellipse(sx, sy, rad, Math.max(10, dh * 0.028), 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.drawImage(img, x, y, dw, dh);
      shown = i;
    }
    function update() {
      var p = progress();
      var i = Math.round(p * (count - 1));
      if (i !== shown || canvas.width === 0) paint(i);
      var active = 0;
      beats.forEach(function (b, i) {
        if (p >= parseFloat(b.dataset.start)) active = i;
      });
      beats.forEach(function (b, i) {
        var on = i === active;
        b.style.opacity = on ? "1" : "0";
        b.classList.toggle("on", on);
        if (on) b.removeAttribute("inert"); else b.setAttribute("inert", "");
      });
    }
    for (var n = 0; n < count; n++) {
      (function (n) {
        var img = new Image();
        img.onload = function () {
          frames[n] = img;
          if (!orbit.classList.contains("is-ready") && n === 0) {
            orbit.classList.add("is-ready");
            update();
          } else if (n === shown || shown < 0) {
            paint(Math.max(shown, 0));
          }
        };
        img.src = src + pad(n) + ".png";
      })(n);
    }
    var ticking = false;
    function onScroll() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () { ticking = false; update(); });
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", function () { shown = -1; onScroll(); });
    update();
  }
})();
