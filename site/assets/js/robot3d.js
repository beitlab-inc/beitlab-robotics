// Live Balance Robot for the homepage hero. Poses the URDF (packed by tools/site/robot_model.py):
// the head pan/tilt servos follow the pointer, and scroll turns the camera around the robot while
// the four-bar legs crouch and stand. Throws if WebGL or the model is unavailable, so the caller can
// fall back to the pre-rendered frames.
import * as THREE from "./vendor/three.module.min.js";

const DEG = Math.PI / 180;
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

// Look of each URDF material. Colours come from the URDF; this is only the surface finish.
const FINISH = {
  metal: { roughness: 0.32, metalness: 0.85 },
  rim: { roughness: 0.38, metalness: 0.35 },
  servo: { roughness: 0.5, metalness: 0.15 },
  tread: { roughness: 0.92, metalness: 0 },
  eye: { roughness: 0.22, metalness: 0.1 },
  estop: { roughness: 0.35, metalness: 0 },
  pcb: { roughness: 0.6, metalness: 0.1 },
};

function environment(renderer) {
  // A small studio: gradient sky plus two soft boxes, baked once into a PMREM.
  const scene = new THREE.Scene();
  const sky = new THREE.Mesh(
    new THREE.SphereGeometry(20, 32, 16),
    new THREE.ShaderMaterial({
      side: THREE.BackSide,
      uniforms: {
        top: { value: new THREE.Color(0.86, 0.9, 0.97) },
        mid: { value: new THREE.Color(0.55, 0.58, 0.64) },
        low: { value: new THREE.Color(0.2, 0.21, 0.24) },
      },
      vertexShader: "varying vec3 d; void main(){ d = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }",
      fragmentShader: "uniform vec3 top; uniform vec3 mid; uniform vec3 low; varying vec3 d;" +
        "void main(){ float h = d.y; vec3 c = h > 0.0 ? mix(mid, top, smoothstep(0.0, 0.9, h)) : mix(mid, low, smoothstep(0.0, 0.6, -h));" +
        "gl_FragColor = vec4(c, 1.0); }",
    }));
  scene.add(sky);
  const box = (x, y, z, w, h, k) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h),
      new THREE.MeshBasicMaterial({ color: new THREE.Color(k, k, k), side: THREE.DoubleSide, toneMapped: false }));
    m.position.set(x, y, z);
    m.lookAt(0, 0, 0);
    scene.add(m);
  };
  box(-8, 9, 7, 10, 6, 5);
  box(9, 4, -6, 8, 5, 2.5);
  box(0, 14, 0, 9, 9, 2);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const tex = pmrem.fromScene(scene, 0.03).texture;
  pmrem.dispose();
  sky.geometry.dispose();
  return tex;
}

function shadowTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(64, 64, 4, 64, 64, 64);
  grad.addColorStop(0, "rgba(0,0,0,0.55)");
  grad.addColorStop(0.5, "rgba(0,0,0,0.22)");
  grad.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function buildRobot(model, bin) {
  const mats = {};
  for (const [name, rgb] of Object.entries(model.materials)) {
    const f = FINISH[name] || { roughness: 0.55, metalness: 0.05 };
    mats[name] = new THREE.MeshStandardMaterial({
      color: new THREE.Color().setRGB(rgb[0], rgb[1], rgb[2], THREE.SRGBColorSpace),
      roughness: f.roughness, metalness: f.metalness, envMapIntensity: 0.95,
    });
  }
  const link = {};
  for (const name of Object.keys(model.links)) {
    link[name] = new THREE.Group();
    link[name].name = name;
  }
  for (const [name, parts] of Object.entries(model.links)) {
    for (const i of parts) {
      const m = model.meshes[i];
      const [lo, hi] = m.box;
      const p16 = new Uint16Array(bin, m.pos, m.vertices * 3);
      const n8 = new Int8Array(bin, m.nrm, m.vertices * 3);
      const pos = new Float32Array(m.vertices * 3);
      const nrm = new Float32Array(m.vertices * 3);
      for (let v = 0; v < m.vertices; v++) {
        for (let k = 0; k < 3; k++) {
          const a = v * 3 + k;
          pos[a] = lo[k] + (p16[a] / 65535) * (hi[k] - lo[k]);
          nrm[a] = n8[a] / 127;
        }
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      geo.setAttribute("normal", new THREE.BufferAttribute(nrm, 3));
      const idx = m.idx_bytes === 2 ? new Uint16Array(bin, m.idx, m.triangles * 3) : new Uint32Array(bin, m.idx, m.triangles * 3);
      geo.setIndex(new THREE.BufferAttribute(idx, 1));
      geo.computeBoundingSphere();
      link[name].add(new THREE.Mesh(geo, mats[m.material]));
    }
  }
  // Joint = fixed origin frame + a pivot that turns about the axis.
  const joint = {};
  const children = new Set();
  for (const j of model.joints) {
    const origin = new THREE.Group();
    origin.position.set(j.xyz[0], j.xyz[1], j.xyz[2]);
    origin.rotation.set(j.rpy[0], j.rpy[1], j.rpy[2], "ZYX"); // URDF rpy is Rz*Ry*Rx
    const pivot = new THREE.Group();
    origin.add(pivot);
    pivot.add(link[j.child]);
    link[j.parent].add(origin);
    children.add(j.child);
    joint[j.name] = { def: j, pivot, axis: new THREE.Vector3(...j.axis).normalize(), value: 0 };
  }
  const rootLink = Object.keys(link).find((n) => !children.has(n));
  const root = new THREE.Group(); // URDF is Z-up, three.js is Y-up. X stays forward.
  root.rotation.x = -Math.PI / 2;
  root.add(link[rootLink]);

  const mimics = Object.values(joint).filter((j) => j.def.mimic);
  function set(name, v) {
    const j = joint[name];
    if (j.def.lower !== null && j.def.upper !== null) v = clamp(v, j.def.lower, j.def.upper);
    j.value = v;
    j.pivot.quaternion.setFromAxisAngle(j.axis, v);
  }
  function pose(values) {
    for (const [name, v] of Object.entries(values)) set(name, v);
    for (const j of mimics) set(j.def.name, j.def.mimic.multiplier * joint[j.def.mimic.joint].value + j.def.mimic.offset);
  }
  return { root, link, joint, pose };
}

export async function start(opts) {
  const { canvas, base } = opts;
  const [model, bin] = await Promise.all([
    fetch(base + "robot.json").then((r) => { if (!r.ok) throw new Error("robot.json"); return r.json(); }),
    fetch(base + "robot.bin").then((r) => { if (!r.ok) throw new Error("robot.bin"); return r.arrayBuffer(); }),
  ]);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
  renderer.setClearColor(0x000000, 0);
  renderer.autoClear = false;
  const scene = new THREE.Scene();
  scene.environment = environment(renderer);

  const robot = buildRobot(model, bin);
  scene.add(robot.root);
  const hipLimits = [robot.joint.r_hip_joint.def.lower, robot.joint.r_hip_joint.def.upper];
  // Hip at its lower limit (15 deg) is standing tall, at its upper limit (55 deg) the legs are folded.
  // 0 = stand, 1 = squat.
  const standHip = (squat) => hipLimits[0] + (hipLimits[1] - hipLimits[0]) * squat;
  const panDef = robot.joint.head_pan_joint.def, tiltDef = robot.joint.head_tilt_joint.def;

  const shadow = new THREE.Mesh(
    new THREE.PlaneGeometry(0.3, 0.3),
    new THREE.MeshBasicMaterial({ map: shadowTexture(), transparent: true, depthWrite: false, toneMapped: false }));
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.y = 0.0004;
  scene.add(shadow);

  const camera = new THREE.PerspectiveCamera(20, 1, 0.05, 20);
  scene.add(camera);
  const key = new THREE.DirectionalLight(0xffffff, 1.5);
  key.position.set(-0.6, 0.9, 0.8); // lights ride with the camera, so every view is lit alike
  camera.add(key, key.target);
  key.target.position.set(0, 0, -1);
  camera.add(new THREE.HemisphereLight(0xffffff, 0x8890a0, 0.35));

  // Wheels stay on the floor at every hip angle. Returns the body's standing and crouched extents.
  const wheel = robot.link.r_wheel;
  const tmp = new THREE.Vector3();
  function ground() {
    robot.root.position.y = 0;
    robot.root.updateMatrixWorld(true);
    wheel.getWorldPosition(tmp);
    robot.root.position.y = model.wheel_radius - tmp.y;
    robot.root.updateMatrixWorld(true);
  }
  const bounds = new THREE.Box3();
  for (const hip of hipLimits) {
    robot.pose({ r_hip_joint: hip, l_hip_joint: hip, head_pan_joint: 0, head_tilt_joint: 0 });
    ground();
    bounds.union(new THREE.Box3().setFromObject(robot.root));
  }
  const target = bounds.getCenter(new THREE.Vector3());
  const height = bounds.max.y - bounds.min.y;
  const reach = Math.max(bounds.max.x - bounds.min.x, bounds.max.z - bounds.min.z) / 2;

  const view = { w: 1, h: 1, top: 0, bottom: 0, dist: 1 };
  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(w, h, false);
    const lay = opts.layout();
    view.w = w; view.h = h; view.top = lay.top; view.bottom = lay.bottom;
    // The robot is framed in the space between the headline and the buttons, but drawn into the
    // whole area under the headline, so nothing is clipped at the edge of that space.
    const full = Math.max(80, h - view.top);
    const vh = Math.max(40, full - view.bottom);
    camera.aspect = w / full;
    const t = Math.tan(camera.fov * DEG / 2) * (vh / full);
    view.dist = Math.max((height / 2) * 0.98 / t, (reach * 1.1 * (vh / full)) / (t * camera.aspect)) + reach * 0.45;
    camera.setViewOffset(w, full, 0, view.bottom / 2, w, full);
    camera.updateProjectionMatrix();
  }

  // Pointer, in canvas pixels. Inactive when it has not moved for a while or has left the page.
  const pointer = { x: 0, y: 0, last: -1e9, inside: true };
  const aim = (e) => {
    const r = canvas.getBoundingClientRect();
    pointer.x = e.clientX - r.left;
    pointer.y = e.clientY - r.top;
    pointer.last = performance.now();
    pointer.inside = true;
  };
  window.addEventListener("pointermove", aim, { passive: true });
  window.addEventListener("touchmove", (e) => { if (e.touches[0]) aim(e.touches[0]); }, { passive: true });
  document.addEventListener("pointerleave", () => { pointer.inside = false; });
  document.documentElement.addEventListener("mouseleave", () => { pointer.inside = false; });

  const state = { p: 0, hip: hipLimits[0], az: 0, el: 0, pan: 0, tilt: 0 };
  let want = { p: 0 };
  let last = performance.now(), visible = true, running = false, dead = false;
  const head = new THREE.Vector3(), cam = new THREE.Vector3(), goal = new THREE.Vector3(), local = new THREE.Vector3();
  const panOrigin = new THREE.Vector3(...robot.joint.head_pan_joint.def.xyz);
  const tiltRise = robot.joint.head_tilt_joint.def.xyz[2];

  function slew(cur, to, rate, dt, tau) {
    const d = (to - cur) * (1 - Math.exp(-dt / tau)), cap = rate * dt;
    return cur + clamp(d, -cap, cap);
  }

  function gaze(now) {
    // Where the head wants to look, as pan and tilt in the robot's own frame.
    const idle = !pointer.inside || now - pointer.last > 3500;
    if (idle) {
      const t = now / 1000;
      return [Math.sin(t * 0.45) * 0.38 + Math.sin(t * 1.1) * 0.06, Math.sin(t * 0.7 + 1) * 0.1];
    }
    const nx = (pointer.x / view.w) * 2 - 1;
    const ny = ((view.h - pointer.y) / Math.max(80, view.h - view.top)) * 2 - 1;
    cam.copy(camera.position);
    head.set(panOrigin.x, panOrigin.y, panOrigin.z + tiltRise);
    robot.root.localToWorld(head);
    goal.set(clamp(nx, -1.6, 1.6), clamp(ny, -1.6, 1.6), 0.5).unproject(camera).sub(cam).normalize();
    // A point on the pointer's ray, in front of the head toward the camera, so a pointer over the
    // head makes it look straight out of the screen.
    goal.multiplyScalar(head.distanceTo(cam) * 0.62).add(cam);
    local.copy(goal);
    robot.root.worldToLocal(local);
    local.sub(panOrigin);
    const pan = Math.atan2(local.y, local.x);
    const flat = Math.hypot(local.x, local.y);
    return [pan, Math.atan2(local.z - tiltRise, flat)];
  }

  function step(now) {
    const dt = Math.min(0.05, Math.max(0.001, (now - last) / 1000));
    last = now;
    const p = want.p;
    // Scroll: two squats over the page, standing tall at the top and at the call to action.
    const squat = 0.5 - 0.5 * Math.cos(Math.PI * 4 * p);
    const hip = standHip(squat);
    state.hip = slew(state.hip, hip, 3.2, dt, 0.12);
    state.az = slew(state.az, (38 + 360 * p) * DEG, 14, dt, 0.1);
    state.el = slew(state.el, (13 + 7 * Math.sin(Math.PI * 2 * p)) * DEG, 3, dt, 0.2);
    const [pan, tilt] = gaze(now);
    state.pan = slew(state.pan, clamp(pan, panDef.lower, panDef.upper), panDef.velocity || 6, dt, 0.09);
    state.tilt = slew(state.tilt, clamp(tilt, tiltDef.lower, tiltDef.upper), tiltDef.velocity || 12, dt, 0.07);

    robot.pose({ r_hip_joint: state.hip, l_hip_joint: state.hip, head_pan_joint: state.pan, head_tilt_joint: state.tilt });
    ground();
    const ce = Math.cos(state.el);
    camera.position.set(
      target.x + view.dist * ce * Math.cos(state.az),
      target.y + view.dist * Math.sin(state.el),
      target.z + view.dist * ce * Math.sin(state.az));
    camera.lookAt(target);
    camera.updateMatrixWorld(true);
  }

  function draw() {
    renderer.setScissorTest(false);
    renderer.clear();
    renderer.setViewport(0, 0, view.w, Math.max(80, view.h - view.top));
    renderer.render(scene, camera);
  }

  function frame(now) {
    running = false;
    if (dead || !visible) return;
    step(now);
    draw();
    running = true;
    requestAnimationFrame(frame);
  }
  function kick() {
    if (!running && visible && !dead) {
      last = performance.now();
      running = true;
      requestAnimationFrame(frame);
    }
  }

  const io = new IntersectionObserver((entries) => {
    visible = entries[entries.length - 1].isIntersecting;
    if (visible) kick();
  });
  io.observe(canvas);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) kick(); });
  canvas.addEventListener("webglcontextlost", (e) => {
    e.preventDefault();
    dead = true;
    if (opts.onLost) opts.onLost();
  });

  resize();
  // Put the pose for progress p in place without easing, so the first paint does not move.
  function jump(p) {
    want.p = p;
    state.hip = standHip(0.5 - 0.5 * Math.cos(Math.PI * 4 * p));
    state.az = (38 + 360 * p) * DEG;
    state.el = (13 + 7 * Math.sin(Math.PI * 2 * p)) * DEG;
    step(performance.now());
    draw();
  }
  jump(opts.progress ? opts.progress() : 0);
  kick();

  return {
    setProgress(p) { want.p = p; kick(); },
    resize() { resize(); kick(); },
    // Test hook: pose and render synchronously.
    debug: { robot, state, camera, step, draw, jump, THREE },
  };
}
