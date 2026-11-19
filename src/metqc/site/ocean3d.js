// Ocean3D: a WebGL ocean surface (three.js) whose sea state is driven by data.
//   const ocean = Ocean3D.mount(element);
//   ocean.set({ waveHeight: 3.8, wind: 12, warmth: 0 });   // metres, m/s, 0..1 (tints the water warmer)
// Gerstner waves in the vertex shader; fresnel sky reflection, sun glint and depth colour in the fragment shader.
// Falls back to nothing (the CSS gradient behind it stays) if WebGL is unavailable. Static frame with reduced motion.
(function () {
  const VERT = `
    uniform float uTime, uAmp, uChop, uSpeed;
    varying vec3 vPos; varying vec3 vNormal; varying float vCrest;
    const float PI = 3.14159265;
    vec3 gerstner(vec2 dir, float steep, float wavelength, vec3 p, inout vec3 tangent, inout vec3 binormal) {
      float k = 2.0 * PI / wavelength;
      float c = sqrt(9.8 / k) * uSpeed;
      vec2 d = normalize(dir);
      float f = k * (dot(d, p.xz) - c * uTime);
      float a = steep / k;
      tangent += vec3(-d.x * d.x * steep * sin(f), d.x * steep * cos(f), -d.x * d.y * steep * sin(f));
      binormal += vec3(-d.x * d.y * steep * sin(f), d.y * steep * cos(f), -d.y * d.y * steep * sin(f));
      return vec3(d.x * a * cos(f), a * sin(f), d.y * a * cos(f));
    }
    void main() {
      vec3 p = position.xzy; p.y = 0.0;
      vec3 t = vec3(1.0, 0.0, 0.0), b = vec3(0.0, 0.0, 1.0), q = p;
      float s = uChop;
      q += uAmp * gerstner(vec2(1.0, 0.25), 0.22 * s, 60.0, p, t, b);
      q += uAmp * gerstner(vec2(0.7, 0.9), 0.18 * s, 31.0, p, t, b);
      q += uAmp * gerstner(vec2(1.0, -0.6), 0.14 * s, 18.0, p, t, b);
      q += uAmp * gerstner(vec2(-0.3, 1.0), 0.10 * s, 9.0, p, t, b);
      vNormal = normalize(cross(b, t));
      vPos = q; vCrest = q.y;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(q, 1.0);
    }`;
  const FRAG = `
    uniform vec3 uDeep, uShallow, uSky, uSun; uniform vec3 uSunDir; uniform float uWarm;
    varying vec3 vPos; varying vec3 vNormal; varying float vCrest;
    void main() {
      vec3 n = normalize(vNormal);
      vec3 v = normalize(cameraPosition - vPos);
      float fres = pow(1.0 - max(dot(n, v), 0.0), 4.0);
      vec3 deep = mix(uDeep, vec3(0.32, 0.04, 0.07), uWarm * 0.85);
      vec3 shallow = mix(uShallow, vec3(1.0, 0.45, 0.22), uWarm * 0.9);
      vec3 sky = mix(uSky, vec3(0.62, 0.24, 0.20), uWarm * 0.75);
      vec3 water = mix(deep, shallow, clamp(vCrest * 0.18 + 0.35, 0.0, 1.0));
      vec3 col = mix(water, sky, fres * 0.85);
      vec3 h = normalize(uSunDir + v);
      col += uSun * pow(max(dot(n, h), 0.0), 220.0) * 1.6;
      col += vec3(0.9) * smoothstep(1.4, 2.6, vCrest) * 0.25;          // foam on the highest crests
      float dist = length(cameraPosition - vPos);
      col = mix(col, sky, smoothstep(60.0, 260.0, dist));               // haze to the horizon
      gl_FragColor = vec4(col, 1.0);
    }`;

  function mount(el) {
    if (!window.THREE) return { set() {} };
    let renderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); } catch (e) { return { set() {} }; }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.domElement.className = "ocean3d";
    el.prepend(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 600);
    camera.position.set(0, 13, 30); camera.lookAt(0, 0, -25);
    const geo = new THREE.PlaneGeometry(520, 420, 260, 210);
    geo.translate(0, -150, 0);  // plane spans z from -360 to 60 (in front of the camera)
    const uniforms = {
      uTime: { value: 0 }, uAmp: { value: 1 }, uChop: { value: 1 }, uSpeed: { value: 1 }, uWarm: { value: 0 },
      uDeep: { value: new THREE.Color("#04325a") }, uShallow: { value: new THREE.Color("#22b8c9") },
      uSky: { value: new THREE.Color("#3a86ad") }, uSun: { value: new THREE.Color("#fff3d6") },
      uSunDir: { value: new THREE.Vector3(-0.35, 0.45, -1).normalize() },
    };
    const mat = new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: FRAG, uniforms });
    scene.add(new THREE.Mesh(geo, mat));

    const target = { amp: 1, chop: 1, speed: 1, warm: 0 };
    function resize() {
      const w = el.clientWidth, h = el.clientHeight;
      renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    }
    window.addEventListener("resize", resize); resize();

    let visible = true;
    new IntersectionObserver((e) => { visible = e[0].isIntersecting; }).observe(el);
    const clock = new THREE.Clock();
    function frame() {
      const dt = Math.min(clock.getDelta(), 0.05);
      // ease towards the data-driven sea state
      for (const [k, u] of [["amp", "uAmp"], ["chop", "uChop"], ["speed", "uSpeed"], ["warm", "uWarm"]]) {
        uniforms[u].value += (target[k] - uniforms[u].value) * Math.min(1, dt * 1.5);
      }
      uniforms.uTime.value += dt;
      if (visible) renderer.render(scene, camera);
      if (!reduce) requestAnimationFrame(frame);
    }
    if (reduce) { uniforms.uTime.value = 12; Object.assign(uniforms, {}); }
    frame();

    return {
      // waveHeight: significant wave height (m); wind: m/s; warmth: 0 (cool) .. 1 (heat stress)
      set({ waveHeight, wind, warmth } = {}) {
        if (waveHeight != null) target.amp = 0.35 + Math.min(waveHeight, 10) * 0.42;
        if (wind != null) { target.chop = 0.7 + Math.min(wind, 25) / 25; target.speed = 0.7 + Math.min(wind, 25) / 40; }
        if (warmth != null) target.warm = Math.max(0, Math.min(1, warmth));
        if (reduce) {
          for (const [k, u] of [["amp", "uAmp"], ["chop", "uChop"], ["speed", "uSpeed"], ["warm", "uWarm"]]) uniforms[u].value = target[k];
          renderer.render(scene, camera);
        }
      },
    };
  }
  window.Ocean3D = { mount };
})();
