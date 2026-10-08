export function normalizeBuses(values) {
  if (!Array.isArray(values)) return [];
  return [...new Set(values.filter(v => typeof v === 'string').map(v => v.trim())
    .filter(v => /^[0-9A-Za-z가-힣-]{1,16}$/.test(v)))].slice(0, 10);
}

export function readSelection(raw) {
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? normalizeBuses(parsed) : ['10'];
  } catch { return ['10']; }
}

export function previous(route, message = '이전에 저장된 정보입니다.') {
  return {...route, stale: true, status: 'error', message,
    vehicles: route.vehicles.map(vehicle => ({...vehicle, bearing: null}))};
}

export function mergeLocations(oldRoutes, payload, selected) {
  const fresh = payload.routes.filter(route => selected.includes(route.busNo));
  const ids = new Set(fresh.map(route => route.routeId));
  for (const route of oldRoutes) {
    if (!selected.includes(route.busNo) || ids.has(route.routeId)) continue;
    const error = payload.errors.find(error => error.busNo === route.busNo && !error.routeId && error.code !== 'NOT_FOUND');
    if (error) fresh.push(previous(route, error.message));
  }
  return fresh;
}

export function restoreSnapshot(raw, selected, now = Date.now()) {
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(route => selected.includes(route.busNo) && typeof route.routeId === 'string'
      && Array.isArray(route.vehicles) && route.vehicles.every(v => v && typeof v.id === 'string')
      && now - Date.parse(route.updatedAt) >= 0 && now - Date.parse(route.updatedAt) < 86400000)
      .map(route => previous(route));
  } catch { return []; }
}
