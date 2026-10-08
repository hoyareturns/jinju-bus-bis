// Stop sequence, direction identity, and arrival alarms are independent of GPS.
export function vehicleProgress(vehicle, stops) {
  if (!Number.isInteger(vehicle.nodeOrd) || vehicle.nodeOrd < 0) return null;
  const index = stops.findIndex(stop => stop.nodeOrd === vehicle.nodeOrd);
  if (index < 0) return null;
  const current = stops[index];
  if (vehicle.nodeId && current.nodeId && vehicle.nodeId !== current.nodeId) return null;
  return {index, current, next:stops[index+1] || null};
}

export function alarmChoices(registered, routes, bus, routeId) {
  const directions = registered.includes(bus) ? routes.filter(route=>route.busNo===bus) : [];
  return {buses:[...registered],directions,stops:directions.find(route=>route.routeId===routeId)?.stops || []};
}

function stopKeys(stops) {
  const counts=new Map();
  return stops.map(stop=>{
    const physical=stop.nodeId || `name:${stop.name}`;
    const n=(counts.get(physical)||0)+1;counts.set(physical,n);
    return {...stop,key:`${physical}#${n}`};
  });
}

// A topological union preserves each variant's actual order, including branches.
function mergeStops(routes) {
  const nodes=new Map(),edges=new Map(),indegree=new Map();
  for(const route of routes) {
    const stops=stopKeys(route.stops);
    for(const stop of stops) {
      if(!nodes.has(stop.key)){nodes.set(stop.key,{...stop,targets:[]});edges.set(stop.key,new Set());indegree.set(stop.key,0);}
      nodes.get(stop.key).targets.push({routeId:route.routeId,nodeOrd:stop.nodeOrd,nodeId:stop.nodeId||''});
    }
    for(let i=1;i<stops.length;i++) {
      const from=stops[i-1].key,to=stops[i].key;
      if(!edges.get(from).has(to)){edges.get(from).add(to);indegree.set(to,indegree.get(to)+1);}
    }
  }
  const result=[],ready=[...nodes.keys()].filter(k=>indegree.get(k)===0);
  while(ready.length){const key=ready.shift();result.push(nodes.get(key));for(const next of edges.get(key)){indegree.set(next,indegree.get(next)-1);if(!indegree.get(next))ready.push(next);}}
  return result.length===nodes.size?result:null;
}

export function directionGroups(routes) {
  const groups=[];
  for (const route of [...routes].filter(r=>r.stops?.length).sort((a,b)=>b.stops.length-a.stops.length || a.routeId.localeCompare(b.routeId))) {
    const ids=new Set(route.stops.map(s=>s.nodeId).filter(Boolean));
    const group=groups.find(g=>mergeStops([...g.routes,route]) && g.routes.some(other=>{
      const theirs=new Set(other.stops.map(s=>s.nodeId).filter(Boolean));
      const common=[...ids].filter(id=>theirs.has(id)).length;
      if (ids.size && theirs.size) {
        const a=stopKeys(route.stops).map(s=>s.key),b=stopKeys(other.stops).map(s=>s.key);
        const shared=a.filter(k=>b.includes(k));
        const ordered=shared.every((k,i)=>i===0||b.indexOf(shared[i-1])<b.indexOf(k));
        return ordered && common/Math.min(ids.size,theirs.size)>=.4;
      }
      return route.startName===other.startName && route.endName===other.endName;
    }));
    if (group) group.routes.push(route); else groups.push({routes:[route]});
  }
  const result=groups.map(group=>{
    const merged=mergeStops(group.routes);
    const ends=[...new Set(group.routes.map(r=>r.endName).filter(Boolean))];
    return {...group,id:group.routes.map(r=>r.routeId).sort().join('|'),
      label:ends.length?`${ends.join(' · ')} 방면`:'방향 정보 확인 필요',stops:merged,
      stale:group.routes.some(r=>r.stale)};
  }).sort((a,b)=>a.id.localeCompare(b.id));
  const labels=result.map(g=>g.label);
  for(const [i,group] of result.entries()) {
    if(labels.filter(label=>label===labels[i]).length>1) group.label+=` · ${group.routes[0].startName||'출발지'} 출발 (${i+1})`;
  }
  return result;
}

export function scheduleWindow(rule, now=Date.now()) {
  if (!/^\d{2}:\d{2}$/.test(rule.startTime||'') || !/^\d{2}:\d{2}$/.test(rule.endTime||'') || !Array.isArray(rule.days)) return null;
  const parts=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(now).map(p=>[p.type,p.value]));
  const date=new Date(`${parts.year}-${parts.month}-${parts.day}T00:00:00Z`);
  const minutes=Number(parts.hour)*60+Number(parts.minute);
  const minute=value=>Number(value.slice(0,2))*60+Number(value.slice(3));
  const start=minute(rule.startTime),end=minute(rule.endTime);
  if(start===end || start>=1440 || end>=1440)return null;
  if(start<end) {if(minutes<start || minutes>=end)return null;}
  else if(minutes<end) date.setUTCDate(date.getUTCDate()-1);
  else if(minutes<start)return null;
  if(!rule.days.includes((date.getUTCDay()+6)%7))return null;
  return date.toISOString().slice(0,10);
}

export function readAlarm(raw) {
  try {
    const alarm=JSON.parse(raw);
    if (!alarm || typeof alarm.enabled!=='boolean' || typeof alarm.sound!=='boolean'
      || !['routeId','busNo','stopName','directionLabel','nodeId'].every(key=>typeof alarm[key]==='string')
      || !Number.isInteger(alarm.nodeOrd) || alarm.nodeOrd<0) return null;
    return alarm;
  } catch { return null; }
}

export function evaluateAlarm(alarm, route, topology, saved={}, now=Date.now()) {
  const memory=Object.fromEntries(Object.entries(saved || {}).filter(([,v])=>v && Number.isFinite(v.seenAt) && now-v.seenAt<86400000).slice(-256));
  const events=[];
  if (!alarm?.enabled || !route || !topology || route.routeId!==alarm.routeId || route.busNo!==alarm.busNo
    || topology.routeId!==alarm.routeId || route.stale || route.status!=='ok' || topology.stale) return {events,memory};
  const stamp=Date.parse(route.updatedAt);
  if (!Number.isFinite(stamp) || now-stamp<0 || now-stamp>90000) return {events,memory};
  const target=topology.stops.findIndex(stop=>stop.nodeOrd===alarm.nodeOrd && (!alarm.nodeId || stop.nodeId===alarm.nodeId));
  if (target<0) return {events,memory};
  const signature=JSON.stringify([alarm.routeId,alarm.nodeOrd,alarm.nodeId]);
  for (const vehicle of route.vehicles) {
    const progress=vehicleProgress(vehicle,topology.stops);
    if (!progress) continue;
    const key=signature+'|'+vehicle.id;
    const old=memory[key] || {fired:false,passed:false,stamp:0};
    if (stamp<=old.stamp) continue;
    const entry={...old,stamp,seenAt:now};
    if (progress.index>target) entry.passed=true;
    if (entry.passed && progress.index<target) {entry.fired=false;entry.passed=false;}
    if (progress.index===target && !entry.fired) {
      events.push({vehicleNo:vehicle.vehicleNo, busNo:alarm.busNo, stopName:alarm.stopName,
        directionLabel:alarm.directionLabel, updatedAt:route.updatedAt});
      entry.fired=true;
    }
    memory[key]=entry;
  }
  return {events,memory};
}
