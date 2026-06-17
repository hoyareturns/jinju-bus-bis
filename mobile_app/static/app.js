const LANDMARKS = [
  "금산우체국/금산푸르지오2단지",
  "선학사거리/제일여자고등학교",
  "경상대(가좌)",
  "중앙시장(주차장)",
  "경남서부보훈지청",
];

const state = {
  map: null,
  nodeByName: new Map(),
  landmarkLayer: L.layerGroup(),
  busLayer: L.layerGroup(),
  requestSeq: 0,
};

const $ = (id) => document.getElementById(id);

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

function parseBusNumbers(value) {
  return value
    .split(",")
    .map((bus) => bus.trim())
    .filter(Boolean);
}

function shortName(name, limit = 12) {
  if (!name) return "";
  return name.length <= limit ? name : `${name.slice(0, limit)}...`;
}

function initMap(center) {
  state.map = L.map("map", { zoomControl: true }).setView(center, 12);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    maxZoom: 19,
  }).addTo(state.map);
  state.landmarkLayer.addTo(state.map);
  state.busLayer.addTo(state.map);
}

function landmarkIcon(name) {
  return L.divIcon({
    className: "",
    iconSize: [132, 42],
    iconAnchor: [11, 35],
    html: `
      <div class="landmark-marker">
        <span class="landmark-dot"></span>
        <span class="landmark-label">${shortName(name, 13)}</span>
      </div>
    `,
  });
}

function busIcon(bearing = 0) {
  return L.divIcon({
    className: "",
    iconSize: [18, 18],
    iconAnchor: [9, 9],
    html: `
      <div class="bus-arrow-wrap">
        <div class="bus-arrow" style="transform: rotate(${bearing}deg)"></div>
      </div>
    `,
  });
}

function renderLandmarks() {
  state.landmarkLayer.clearLayers();
  const bounds = [];

  for (const name of LANDMARKS) {
    const node = state.nodeByName.get(name);
    if (!node) continue;
    bounds.push([node.lat, node.lon]);
    L.marker([node.lat, node.lon], {
      icon: landmarkIcon(name),
      zIndexOffset: 700,
    }).addTo(state.landmarkLayer);
  }

  if (bounds.length) {
    state.map.fitBounds(bounds, { padding: [42, 42], maxZoom: 13 });
  }
}

function renderResultCard(result) {
  const card = document.createElement("article");
  card.className = "route-card";

  const title = document.createElement("h2");
  title.textContent = `${result.busNo}번`;
  card.append(title);

  if (!result.buses.length) {
    const empty = document.createElement("p");
    empty.className = "empty-status";
    empty.textContent = result.status;
    card.append(empty);
    return card;
  }

  for (const bus of result.buses) {
    const row = document.createElement("div");
    row.className = "bus-row";
    row.innerHTML = `
      <strong>${bus.curr}</strong>
      <span>${bus.next ? `${bus.next} 방향` : "방향 정보 없음"}</span>
      <time>${bus.last_time || ""}</time>
    `;
    row.append(renderRouteStrip(result.routeStops || [], bus.ord));
    card.append(row);
  }

  return card;
}

function renderRouteStrip(routeStops, currentOrd) {
  const strip = document.createElement("div");
  strip.className = "route-strip";

  for (const stop of routeStops) {
    const chip = document.createElement("span");
    chip.className = "stop-chip";
    chip.textContent = stop.name;
    if (stop.ord < currentOrd) chip.classList.add("passed");
    if (stop.ord === currentOrd) {
      chip.classList.add("current");
      chip.dataset.currentStop = "true";
    }
    strip.append(chip);
  }

  return strip;
}

function centerCurrentStops() {
  for (const chip of document.querySelectorAll("[data-current-stop='true']")) {
    chip.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }
}

async function refreshLocations() {
  const requestId = (state.requestSeq += 1);
  const buses = parseBusNumbers($("busInput").value);
  $("results").innerHTML = "";
  state.busLayer.clearLayers();
  $("routeCount").textContent = `노선 ${buses.length}`;
  $("vehicleCount").textContent = "버스 0";

  if (!buses.length) {
    $("statusText").textContent = "노선 없음";
    $("results").innerHTML = `<article class="route-card"><p class="empty-status">조회할 노선 번호를 입력하세요.</p></article>`;
    return;
  }

  $("statusText").textContent = "조회 중";

  try {
    const payload = await fetchJson(`/api/locations?buses=${encodeURIComponent(buses.join(", "))}`);
    if (requestId !== state.requestSeq) return;
    let vehicleCount = 0;
    const mapBounds = [];
    const results = [...payload.results].sort((a, b) => b.buses.length - a.buses.length);

    for (const result of results) {
      $("results").append(renderResultCard(result));

      for (const bus of result.buses) {
        vehicleCount += 1;
        if (!bus.lat || !bus.lon) continue;
        mapBounds.push([bus.lat, bus.lon]);
        L.marker([bus.lat, bus.lon], {
          icon: busIcon(bus.bearing || 0),
          zIndexOffset: 1000,
        })
          .bindTooltip(`<strong>${result.busNo}번</strong><span>${bus.curr}</span>`, {
            permanent: true,
            direction: "top",
            offset: [0, -12],
            className: "bus-tooltip",
          })
          .addTo(state.busLayer);
      }
    }

    $("vehicleCount").textContent = `버스 ${vehicleCount}`;
    $("statusText").textContent = "완료";

    if (mapBounds.length) {
      LANDMARKS.forEach((name) => {
        const node = state.nodeByName.get(name);
        if (node) mapBounds.push([node.lat, node.lon]);
      });
      state.map.fitBounds(mapBounds, { padding: [46, 46], maxZoom: 14 });
    }
    setTimeout(centerCurrentStops, 0);
  } catch (error) {
    if (requestId !== state.requestSeq) return;
    $("statusText").textContent = "오류";
    $("results").innerHTML = `<article class="route-card"><p class="empty-status">${error.message}</p></article>`;
  }
}

async function boot() {
  const bootstrap = await fetchJson("/api/bootstrap");
  state.nodeByName = new Map(bootstrap.nodes.map((node) => [node.name, node]));
  $("busInput").value = bootstrap.defaultBuses;

  initMap(bootstrap.defaultCenter);
  renderLandmarks();
  await refreshLocations();
}

$("refresh").addEventListener("click", refreshLocations);
$("busInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter") refreshLocations();
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

boot();
