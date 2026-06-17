const state = {
  map: null,
  nodes: [],
  nodeByName: new Map(),
  stationLayer: L.layerGroup(),
  busLayer: L.layerGroup(),
  targetLayer: L.layerGroup(),
  selectedStation: null,
  target1: null,
  target2: "선택 안 함",
  routeNotice: null,
};

const $ = (id) => document.getElementById(id);

function shortName(name, limit = 16) {
  if (!name || name === "선택 안 함") return "선택 안 함";
  return name.length <= limit ? name : `${name.slice(0, limit)}...`;
}

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

function initMap(center) {
  state.map = L.map("map", { zoomControl: true }).setView(center, 12);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    maxZoom: 19,
  }).addTo(state.map);
  state.stationLayer.addTo(state.map);
  state.busLayer.addTo(state.map);
  state.targetLayer.addTo(state.map);
}

function targetIcon(label, name, color) {
  return L.divIcon({
    className: "",
    iconSize: [86, 42],
    iconAnchor: [10, 38],
    html: `
      <div class="target-flag">
        <div class="pole" style="background:${color}"></div>
        <div class="label" style="background:${color}">${label}</div>
        <div class="name" style="border:2px solid ${color}">${name}</div>
      </div>
    `,
  });
}

function busIcon(busNo, curr, color) {
  return L.divIcon({
    className: "",
    iconSize: [52, 34],
    iconAnchor: [26, 17],
    html: `<div class="bus-marker" style="color:${color}">${busNo}<br><span>${shortName(curr, 8)}</span></div>`,
  });
}

function renderTargets() {
  $("target1Card").querySelector("strong").textContent = state.target1 || "선택 안 함";
  $("target2Card").querySelector("strong").textContent = state.target2 || "선택 안 함";
  $("target1Select").value = state.target1 || "선택 안 함";
  $("target2Select").value = state.target2 || "선택 안 함";

  state.targetLayer.clearLayers();
  if (state.target1 && state.nodeByName.has(state.target1)) {
    const n = state.nodeByName.get(state.target1);
    L.marker([n.lat, n.lon], {
      icon: targetIcon("목표1", shortName(n.name, 10), "#dc2626"),
      zIndexOffset: 1000,
    }).addTo(state.targetLayer);
  }
  if (state.target2 && state.target2 !== "선택 안 함" && state.nodeByName.has(state.target2)) {
    const n = state.nodeByName.get(state.target2);
    L.marker([n.lat, n.lon], {
      icon: targetIcon("목표2", shortName(n.name, 10), "#2563eb"),
      zIndexOffset: 1000,
    }).addTo(state.targetLayer);
  }
}

function renderStationLayer() {
  state.stationLayer.clearLayers();
  if (!$("showStations").checked) return;

  const renderer = L.canvas({ padding: 0.5 });
  for (const node of state.nodes) {
    const marker = L.circleMarker([node.lat, node.lon], {
      renderer,
      radius: 5,
      color: "#475569",
      weight: 2,
      fill: true,
      fillColor: "#f8fafc",
      fillOpacity: 0.95,
    });
    marker.bindTooltip(node.name);
    marker.on("click", () => selectStation(node.name));
    marker.addTo(state.stationLayer);
  }
}

function selectStation(name) {
  state.selectedStation = name;
  $("selectedStationName").textContent = `지도 선택: ${name}`;
  $("selectedStationPanel").classList.remove("hidden");
}

function applySelected(slot) {
  if (!state.selectedStation) return;
  if (slot === 1) state.target1 = state.selectedStation;
  if (slot === 2) state.target2 = state.selectedStation;
  const node = state.nodeByName.get(state.selectedStation);
  if (node) state.map.setView([node.lat, node.lon], Math.max(state.map.getZoom(), 15));
  renderTargets();
}

function populateSelects(filter = "") {
  const names = state.nodes
    .map((n) => n.name)
    .filter((name) => !filter || name.includes(filter));
  const safeNames = new Set(["선택 안 함", state.target1, state.target2, state.selectedStation, ...names]);
  const options = [...safeNames].filter(Boolean).sort();

  for (const select of [$("target1Select"), $("target2Select")]) {
    select.innerHTML = "";
    for (const name of options) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      select.append(option);
    }
  }
  renderTargets();
}

function colorForBus(busNo) {
  const colors = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#0891b2"];
  const sum = [...String(busNo)].reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
  return colors[sum % colors.length];
}

function sortBusNumbers(buses) {
  return [...buses].sort((a, b) => String(a).localeCompare(String(b), "ko", { numeric: true }));
}

async function refreshLocations() {
  const buses = $("busInput").value
    .split(",")
    .map((bus) => bus.trim())
    .filter(Boolean);

  state.busLayer.clearLayers();
  $("results").innerHTML = "";
  $("routeCount").textContent = String(buses.length);
  $("vehicleCount").textContent = "0";

  if (!buses.length) {
    $("statusText").textContent = "노선 없음";
    $("results").innerHTML = `<article class="route-card"><h3>조회할 노선 없음</h3><div class="bus-row"><span>목표 정류장을 다시 선택해 주세요.</span></div></article>`;
    renderTargets();
    return;
  }

  $("statusText").textContent = "조회 중";
  if (state.routeNotice) {
    const notice = document.createElement("article");
    notice.className = "route-card route-notice";
    notice.innerHTML = `
      <h3>${state.routeNotice.title}</h3>
      <div class="bus-row"><strong>${state.routeNotice.buses.join(", ")}</strong></div>
    `;
    $("results").append(notice);
  }
  const payload = await fetchJson(`/api/locations?buses=${encodeURIComponent(buses.join(", "))}`);

  let vehicleCount = 0;

  for (const result of payload.results) {
    const card = document.createElement("article");
    card.className = "route-card";
    card.innerHTML = `<h3>${result.busNo}번 ${result.buses.length ? `${result.buses.length}대` : result.status}</h3>`;

    for (const bus of result.buses) {
      vehicleCount += 1;
      if (bus.lat && bus.lon) {
        L.marker([bus.lat, bus.lon], {
          icon: busIcon(result.busNo, bus.curr, colorForBus(result.busNo)),
        }).addTo(state.busLayer);
      }
      const row = document.createElement("div");
      row.className = "bus-row";
      row.innerHTML = `<strong>${bus.curr} 통과</strong><span>다음: ${bus.next}</span><span>${bus.last_time || ""}</span>`;
      card.append(row);
    }
    $("results").append(card);
  }

  $("routeCount").textContent = String(buses.length);
  $("vehicleCount").textContent = String(vehicleCount);
  $("statusText").textContent = "완료";
  renderTargets();
}

async function findRoutes() {
  state.routeNotice = null;
  if (state.target1 && state.target2 && state.target2 !== "선택 안 함") {
    const buses1 = new Set(state.nodeByName.get(state.target1)?.buses || []);
    const buses2 = new Set(state.nodeByName.get(state.target2)?.buses || []);
    const common = sortBusNumbers([...buses1].filter((bus) => buses2.has(bus)));
    if (common.length) {
      $("busInput").value = common.join(", ");
      state.routeNotice = { title: `직통 노선 ${common.length}개`, buses: common };
    } else {
      const target2Buses = sortBusNumbers(buses2);
      $("busInput").value = target2Buses.join(", ");
      state.routeNotice = { title: `직통 없음 · 목표2 경유 ${target2Buses.length}개`, buses: target2Buses };
    }
  } else if (state.target1) {
    const target1Buses = sortBusNumbers(state.nodeByName.get(state.target1)?.buses || []);
    $("busInput").value = target1Buses.join(", ");
    state.routeNotice = { title: `목표1 경유 ${target1Buses.length}개`, buses: target1Buses };
  }
  await refreshLocations();
}

async function boot() {
  const bootstrap = await fetchJson("/api/bootstrap");
  state.nodes = bootstrap.nodes;
  state.nodeByName = new Map(state.nodes.map((node) => [node.name, node]));
  state.target1 = bootstrap.defaultNode1;
  $("busInput").value = bootstrap.defaultBuses;

  initMap(bootstrap.defaultCenter);
  populateSelects();
  renderTargets();
  await refreshLocations().catch((error) => {
    $("statusText").textContent = "설정 필요";
    $("results").innerHTML = `<article class="route-card"><h3>API 설정 필요</h3><div class="bus-row"><span>${error.message}</span></div></article>`;
  });
}

$("showStations").addEventListener("change", renderStationLayer);
$("applyTarget1").addEventListener("click", () => applySelected(1));
$("applyTarget2").addEventListener("click", () => applySelected(2));
$("stationSearch").addEventListener("input", (event) => populateSelects(event.target.value));
$("target1Select").addEventListener("change", (event) => {
  state.target1 = event.target.value;
  renderTargets();
});
$("target2Select").addEventListener("change", (event) => {
  state.target2 = event.target.value;
  renderTargets();
});
$("findRoutes").addEventListener("click", findRoutes);
$("refresh").addEventListener("click", refreshLocations);

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

boot();
