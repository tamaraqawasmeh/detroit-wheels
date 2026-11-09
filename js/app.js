// Detroit Wheels: interactive story map.
(async function () {
  const css = getComputedStyle(document.documentElement);
  const v = name => css.getPropertyValue(name).trim();
  // Transit-map line styles, keyed by network class.
  const LINE = {
    protected: { color: v("--protected"), weight: 5 },
    path: { color: v("--path"), weight: 4.5 },
    lane: { color: v("--lane"), weight: 3 },
    shared: { color: v("--shared"), weight: 2, dashArray: "4 4" },
    jlg_open: { color: v("--jlg"), weight: 6.5 },
    jlg_building: { color: v("--jlg"), weight: 5, dashArray: "10 7" },
    jlg_planned: { color: v("--jlg"), weight: 4, dashArray: "2 7", opacity: 0.75 },
  };
  const NETWORK_KEYS = ["protected", "path", "lane", "shared"];
  const JLG_KEYS = ["jlg_open", "jlg_building", "jlg_planned"];
  const REACH_RAMP = ["#f3f3ee", "#dcebe2", "#b5d8c4", "#7fbf9c", "#3f9b6f"];
  const fmt = n => n.toLocaleString("en-US");

  const [network, hoods, crashes, points, calm, S] = await Promise.all(
    ["network", "neighborhoods", "crashes", "points", "calm"].map(n => fetch(`data/${n}.geojson`).then(r => r.json())).concat(fetch("data/summary.json").then(r => r.json()))
  );

  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  set("s-ded", Math.round(S.dedicated_miles)); set("s-ded2", `${Math.round(S.dedicated_miles)} miles`);
  set("s-prot", `${Math.round(S.miles.protected)} miles`);
  set("s-reach", Math.round(S.city_reach_pct) + "%"); set("s-zero", S.zero_reach_hoods);
  set("s-crashes", fmt(S.crashes)); set("s-years", S.crash_years); set("s-fatal", S.fatal); set("s-serious", S.serious);
  set("s-off", Math.round(S.pct_off_facility) + "%");
  set("s-slow", fmt(S.slow_segments)); set("s-safe", S.safe_corridors); set("s-mogo", S.mogo); set("s-repair", S.repair);

  const map = L.map("map", { zoomControl: false, minZoom: 10, maxZoom: 17, zoomSnap: 0.25 });
  L.control.zoom({ position: "bottomright" }).addTo(map);
  const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas";
  L.tileLayer(`${ESRI}/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}`, {
    attribution: 'Basemap: Esri, HERE, Garmin, &copy; OpenStreetMap contributors · Data: <a href="https://data.detroitmi.gov/">City of Detroit Open Data</a>', maxNativeZoom: 16,
  }).addTo(map);
  for (const [name, z] of [["calm", 405], ["net", 420], ["crash", 440], ["pts", 445], ["labels", 450]]) map.createPane(name).style.zIndex = z;
  map.getPane("labels").style.pointerEvents = "none";

  // Classes match the legend: none, under 10%, 10–25%, 25–75%, 75% and up.
  const reachColor = r => REACH_RAMP[r === 0 ? 0 : r < 10 ? 1 : r < 25 ? 2 : r < 75 ? 3 : 4];
  let reachOn = false, selected = null;
  const hoodStyle = f => ({ fillColor: reachOn ? reachColor(f.properties.reach) : "#ffffff", fillOpacity: reachOn ? 0.85 : 0.35, color: "#c9cbc4", weight: 0.8 });
  const hoodLayer = L.geoJSON(hoods, {
    style: hoodStyle,
    onEachFeature: (f, layer) => {
      layer.bindTooltip(() => `${f.properties.name}${reachOn ? `<br><b>${f.properties.reach}%</b> within ¼ mi of a bike facility` : ""}`, { className: "tip", sticky: true, direction: "top", offset: [0, -8] });
      layer.on({
        mouseover: () => selected !== layer && layer.setStyle({ weight: 2, color: "#15171a" }),
        mouseout: () => selected !== layer && hoodLayer.resetStyle(layer),
        click: () => select(layer),
      });
    },
  }).addTo(map);
  L.tileLayer(`${ESRI}/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}`, { pane: "labels", opacity: 0.7, maxNativeZoom: 16 }).addTo(map);

  const calmLayer = L.geoJSON(calm, {
    pane: "calm",
    style: f => f.properties.kind === "slow" ? { color: v("--slow"), weight: 1.2, opacity: 0.6 } : { color: "#15171a", weight: 4, opacity: 0.85, dashArray: "1 6", lineCap: "round" },
    onEachFeature: (f, l) => f.properties.kind === "safe" && l.bindTooltip(`<b>Safe Streets: ${f.properties.name}</b><br>${f.properties.extent || ""}<br>${f.properties.scope} · ${f.properties.status}`, { className: "tip", sticky: true }),
  });

  const visible = new Set([...NETWORK_KEYS, ...JLG_KEYS]);
  const netLayer = L.geoJSON(network, {
    pane: "net",
    style: f => ({ ...LINE[f.properties.cls], lineCap: "round", lineJoin: "round" }),
    onEachFeature: (f, l) => l.bindTooltip(`<b style="color:${LINE[f.properties.cls].color}">${S.labels[f.properties.cls]}</b>${f.properties.name ? `<br>${f.properties.name}` : ""}${f.properties.detail && !f.properties.cls.startsWith("jlg") ? `<br>${f.properties.detail}` : ""}`, { className: "tip", sticky: true }),
  }).addTo(map);
  function applyNetwork(focus) {
    netLayer.eachLayer(l => {
      const c = l.feature.properties.cls, on = visible.has(c);
      const dim = focus && !focus.includes(c);
      l.setStyle({ opacity: on ? (dim ? 0.15 : LINE[c].opacity ?? 1) : 0 });
    });
    document.querySelectorAll(".lines button").forEach(b => b.setAttribute("aria-pressed", visible.has(b.dataset.key)));
  }

  const crashLayer = L.geoJSON(crashes, {
    pane: "crash",
    pointToLayer: (f, ll) => {
      const severe = f.properties.fatal || f.properties.serious;
      return L.circleMarker(ll, { radius: severe ? 5.5 : 3, color: "#fff", weight: severe ? 1.5 : 0.5, fillColor: v("--crash"), fillOpacity: severe ? 0.95 : 0.65 });
    },
    onEachFeature: (f, l) => {
      const p = f.properties;
      const sev = p.fatal ? `<b style="color:var(--crash)">${p.fatal} killed</b>` : p.serious ? `<b style="color:var(--crash)">Serious injury</b>` : "Crash involving a bicyclist";
      l.bindTooltip(`${sev}<br>${p.road}<br>${p.date}${p.ft_to_facility != null ? ` · ${fmt(p.ft_to_facility)} ft from a bike facility` : ""}`, { className: "tip", direction: "top" });
    },
  });

  const ptsLayer = L.geoJSON(points, {
    pane: "pts",
    pointToLayer: (f, ll) => f.properties.kind === "mogo"
      ? L.circleMarker(ll, { radius: 4.5, color: "#fff", weight: 1.5, fillColor: "#15171a", fillOpacity: 1 })
      : L.circleMarker(ll, { radius: 4, color: v("--path"), weight: 2, fillColor: "#fff", fillOpacity: 1 }),
    onEachFeature: (f, l) => l.bindTooltip(`<b>${f.properties.kind === "mogo" ? "MoGo station" : "Bike repair stand"}</b><br>${f.properties.name}`, { className: "tip", direction: "top" }),
  });

  // Line toggles (chapter 1)
  const list = document.getElementById("line-list");
  NETWORK_KEYS.forEach(k => {
    const li = document.createElement("li");
    const st = LINE[k];
    li.innerHTML = `<button type="button" data-key="${k}" aria-pressed="true"><span class="swatch" style="border-top-width:${st.weight}px;border-top-color:${st.color};border-top-style:${st.dashArray ? "dashed" : "solid"}"></span>${S.labels[k]}<span class="mi">${Math.round(S.miles[k])} mi</span></button>`;
    li.firstChild.addEventListener("click", () => { visible.has(k) ? visible.delete(k) : visible.add(k); applyNetwork(); });
    list.appendChild(li);
  });

  // Joe Louis Greenway progress bar (chapter 3)
  const jlgTotal = JLG_KEYS.reduce((s, k) => s + S.jlg_miles[k], 0);
  const jlgFill = { jlg_open: v("--jlg"), jlg_building: "#a774db", jlg_planned: "#d9c5ef" };
  document.getElementById("jlg-bar").innerHTML = JLG_KEYS.map(k => `<div style="width:${(100 * S.jlg_miles[k]) / jlgTotal}%;background:${jlgFill[k]}"></div>`).join("");
  document.getElementById("jlg-legend").innerHTML = JLG_KEYS.map(k => `<span><i style="border-top-color:${jlgFill[k]}"></i>${(t => t[0].toUpperCase() + t.slice(1))(S.labels[k].replace("Joe Louis Greenway · ", ""))}<b>${S.jlg_miles[k]} mi</b></span>`).join("");

  // Legend, rebuilt per chapter
  const legend = document.getElementById("legend");
  const lineRow = k => `<div class="row"><span class="sw" style="border-top-width:${LINE[k].weight}px;border-top-color:${LINE[k].color};border-top-style:${LINE[k].dashArray ? "dashed" : "solid"}"></span>${S.labels[k]}</div>`;
  function renderLegend(ch) {
    let html = `<section><h4>Bike network</h4>${(ch === "jlg" ? JLG_KEYS : NETWORK_KEYS.concat(["jlg_open"])).map(lineRow).join("")}</section>`;
    if (ch === "reach") html += `<section><h4>Share within ¼ mile</h4><div class="ramp">${REACH_RAMP.map(c => `<div style="background:${c}"></div>`).join("")}${["0", "<10", "10–25", "25–75", "75+"].map(t => `<span>${t}</span>`).join("")}</div></section>`;
    if (ch === "crashes") html += `<section><h4>Bike crashes 2020–24</h4><div class="row"><span class="dot" style="background:var(--crash)"></span>Crash involving a bicyclist</div><div class="row"><span class="dot" style="background:var(--crash);width:14px;height:14px;margin:0 6px;border:2px solid #fff;box-shadow:0 0 0 1px var(--crash)"></span>Death or serious injury</div></section>`;
    if (ch === "calm") html += `<section><h4>Calmer streets</h4><div class="row"><span class="sw" style="border-top:2px solid var(--slow)"></span>Slow Streets (speed humps)</div><div class="row"><span class="sw" style="border-top:4px dotted #15171a"></span>Safe Streets corridor (in design)</div><div class="row"><span class="dot" style="background:#15171a"></span>MoGo bike share</div><div class="row"><span class="dot" style="border:2px solid var(--path)"></span>Repair stand</div></section>`;
    legend.innerHTML = html;
  }

  function findHood(name) { let hit = null; hoodLayer.eachLayer(l => { if (l.feature.properties.name === name) hit = l; }); return hit; }
  const card = document.getElementById("card");
  function select(layer) {
    if (selected) hoodLayer.resetStyle(selected);
    selected = layer;
    layer.setStyle({ weight: 3, color: "#15171a" });
    const p = layer.feature.properties;
    const n = crashes.features.filter(c => contains(layer, c.geometry.coordinates)).length;
    card.innerHTML = `<button class="close" aria-label="Close">×</button><h3>${p.name}</h3><p class="sub">Council District ${p.district}</p>
      <div class="big">${Math.round(p.reach)}%<small>within ¼ mile of a bike facility</small></div>
      <div class="meter"><div style="width:${p.reach}%"></div></div>
      <p class="sub" style="margin-top:10px">${n} bike crash${n === 1 ? "" : "es"} here, 2020–2024</p>`;
    card.hidden = false;
    card.querySelector(".close").addEventListener("click", clearSelection);
  }
  function clearSelection() { if (selected) hoodLayer.resetStyle(selected); selected = null; card.hidden = true; }
  function contains(layer, [x, y]) {
    if (!layer.getBounds().contains([y, x])) return false;
    const g = layer.feature.geometry, polys = g.type === "MultiPolygon" ? g.coordinates : [g.coordinates];
    const inRing = r => { let c = false; for (let i = 0, j = r.length - 1; i < r.length; j = i++) { const [xi, yi] = r[i], [xj, yj] = r[j]; if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c; } return c; };
    return polys.some(p => inRing(p[0]) && !p.slice(1).some(inRing));
  }

  const cityBounds = hoodLayer.getBounds();
  const city = () => map.flyToBounds(cityBounds, { padding: [20, 20], duration: 1 });
  const CHAPTERS = {
    network: { view: city },
    protected: { view: () => map.flyTo([42.345, -83.06], 13, { duration: 1.3 }), focus: ["protected"] },
    jlg: { view: () => map.flyTo([42.37, -83.1], 12.25, { duration: 1.3 }), focus: JLG_KEYS },
    reach: { view: city, reach: true },
    crashes: { view: city, crashes: true, focus: NETWORK_KEYS.concat(["jlg_open"]) },
    calm: { view: city, calm: true, pts: true },
  };
  map.fitBounds(cityBounds, { padding: [20, 20] });

  let current = null;
  function enter(name) {
    if (name === current) return;
    current = name;
    const c = CHAPTERS[name];
    document.querySelectorAll(".chapter").forEach(s => s.classList.toggle("active", s.dataset.chapter === name));
    NETWORK_KEYS.concat(JLG_KEYS).forEach(k => visible.add(k));
    reachOn = !!c.reach;
    hoodLayer.eachLayer(l => l.setStyle(hoodStyle(l.feature)));
    c.crashes ? crashLayer.addTo(map) : crashLayer.remove();
    c.calm ? calmLayer.addTo(map) : calmLayer.remove();
    c.pts ? ptsLayer.addTo(map) : ptsLayer.remove();
    applyNetwork(c.focus);
    renderLegend(name);
    clearSelection();
    c.view();
  }

  // On phones the page scrolls under a sticky map; on desktop the story panel scrolls.
  const mobile = matchMedia("(max-width: 800px)").matches;
  const io = new IntersectionObserver(entries => {
    entries.filter(e => e.isIntersecting).forEach(e => enter(e.target.dataset.chapter));
  }, mobile ? { rootMargin: "-60% 0px -30% 0px" } : { root: document.getElementById("story"), rootMargin: "-35% 0px -55% 0px" });
  document.querySelectorAll(".chapter").forEach(s => io.observe(s));
  enter("network");
})();
