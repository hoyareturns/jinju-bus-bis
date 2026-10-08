import test from 'node:test';
import assert from 'node:assert/strict';
import {AlarmPanel} from '../static/alarm-panel.mjs';
import {directionGroups} from '../static/stops.mjs';
const now=Date.parse('2026-10-07T22:10:00Z');
function fixture(){const nodes={arrivalNotice:{hidden:true},arrivalText:{textContent:''}};globalThis.document={getElementById:id=>nodes[id]};const panel=Object.create(AlarmPanel.prototype);panel.arrivals=[];panel.registered=()=>['10','160'];panel.topologies=()=>['10','160'].map(bus=>({routeId:bus,stale:false,stops:[{nodeOrd:4,nodeId:bus,name:'도착'}]}));panel.local=['10','160'].map(bus=>({id:bus,enabled:true,sound:false,rule:{busNo:bus,directionLabel:'시내 방면',stopName:'도착',targets:[{routeId:bus,nodeOrd:4,nodeId:bus}],startTime:'07:00',endTime:'07:30',days:[0,1,2,3,4,5,6]}}));panel.store=()=>{};const routes=['10','160'].map(bus=>({routeId:bus,busNo:bus,stale:false,status:'ok',updatedAt:new Date(now).toISOString(),vehicles:[{id:bus,nodeOrd:4,nodeId:bus}]}));return {panel,nodes,routes};}
test('multiple simultaneous and later arrivals remain visible; once per window survives reload',()=>{const old=Date.now;Date.now=()=>now;try{const {panel,nodes,routes}=fixture();panel.check([routes[0]]);panel.check(routes);assert.equal(panel.arrivals.length,2);assert.match(nodes.arrivalText.textContent,/10번/);assert.match(nodes.arrivalText.textContent,/160번/);assert.equal(nodes.arrivalNotice.hidden,false);const saved=JSON.parse(JSON.stringify(panel.local));panel.local=saved;panel.check(routes);assert.equal(panel.arrivals.length,2);}finally{Date.now=old;delete globalThis.document;}});
test('removing bus waits for pending server synchronization and deletes all matching alarms',async()=>{let release;const panel=Object.create(AlarmPanel.prototype);panel.token='device';panel.local=[];panel.remote=[];panel.store=()=>{};panel.render=()=>{};panel.syncPromise=new Promise(resolve=>{release=()=>{panel.remote=[{id:'remote',rule:{busNo:'10'}}];panel.synced=true;resolve();};});const removed=[];panel.remove=async a=>removed.push(a.id);const pending=panel.removeBus('10');assert.deepEqual(removed,[]);release();await pending;assert.deepEqual(removed,['remote']);panel.synced=false;await assert.rejects(()=>panel.removeBus('10'));});
test('shared physical stops in a different order cannot form a false sequence',()=>{const route=(id,ids)=>({routeId:id,startName:'출발',endName:'도착',stops:ids.map((nodeId,nodeOrd)=>({nodeId,nodeOrd,name:nodeId}))});const groups=directionGroups([route('a',['1','2','3','4']),route('b',['1','4','3','2'])]);assert.equal(groups.length,2);for(const g of groups)for(const r of g.routes){const positions=r.stops.map(s=>g.stops.findIndex(x=>x.nodeId===s.nodeId));assert.ok(positions.every((x,i)=>!i||x>positions[i-1]));}});
import {readFileSync} from 'node:fs';
test('all bundled route variants retain actual stop order; 10 and160 have two directions',()=>{
 const data=JSON.parse(readFileSync(new URL('../../bus_data.json',import.meta.url),'utf8'));
 for(const [bus,variants] of Object.entries(data)){
  const routes=Object.entries(variants).filter(([,stops])=>stops.length).map(([routeId,stops])=>({routeId,busNo:bus,startName:stops[0].nodenm,endName:stops.at(-1).nodenm,stops:stops.map(s=>({nodeId:s.nodeid,nodeOrd:Number(s.nodeord),name:s.nodenm}))}));
  const groups=directionGroups(routes);if(['10','160'].includes(bus))assert.equal(groups.length,2);
  assert.equal(new Set(groups.map(g=>g.label)).size,groups.length);
  for(const group of groups)for(const route of group.routes){const positions=route.stops.map(s=>group.stops.findIndex(u=>u.targets.some(t=>t.routeId===route.routeId&&t.nodeOrd===s.nodeOrd)));assert.ok(positions.every((v,i)=>v>=0&&(!i||v>positions[i-1])),bus+' '+route.routeId);}
 }
});
