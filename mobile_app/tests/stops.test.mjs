import test from 'node:test';
import assert from 'node:assert/strict';
import {vehicleProgress, evaluateAlarm, readAlarm, alarmChoices, directionGroups, scheduleWindow} from '../static/stops.mjs';
const stops=[{nodeOrd:2,nodeId:'A',name:'출발'},{nodeOrd:5,nodeId:'B',name:'중앙'},{nodeOrd:9,nodeId:'C',name:'중앙'},{nodeOrd:12,nodeId:'D',name:'도착'},{nodeOrd:16,nodeId:'E',name:'종점'}];
const now=Date.parse('2026-10-08T02:00:00Z');
const vehicle={id:'R|1',vehicleNo:'1',nodeOrd:5,nodeId:'B',nodeName:'중앙'};
const route={routeId:'R',busNo:'160',status:'ok',stale:false,updatedAt:new Date(now).toISOString(),vehicles:[vehicle]};
const arrived={...route,vehicles:[{...vehicle,nodeOrd:12,nodeId:'D'}]};
const topology={routeId:'R',busNo:'160',stale:false,stops};
const alarm={enabled:true,routeId:'R',busNo:'160',nodeOrd:12,nodeId:'D',stopName:'도착',directionLabel:'종점 방면',sound:true};
test('current and next stop use sequence, not GPS or ordinal arithmetic',()=>{
  const progress=vehicleProgress(vehicle,stops);
  assert.equal(progress.index,1); assert.equal(progress.current.name,'중앙'); assert.equal(progress.next.nodeOrd,9);
  assert.equal(vehicleProgress({...vehicle,nodeOrd:99},stops),null);
  assert.equal(vehicleProgress({...vehicle,nodeId:'C'},stops),null);
});
test('terminal is explicit and repeated stop names remain distinct',()=>{
  assert.equal(vehicleProgress({...vehicle,nodeOrd:16,nodeId:'E'},stops).next,null);
  assert.equal(vehicleProgress({...vehicle,nodeOrd:9,nodeId:'C'},stops).index,2);
});
test('alarm requires arrival and fires once per vehicle including after reload',()=>{
  assert.equal(evaluateAlarm(alarm,route,topology,{},now).events.length,0);
  const first=evaluateAlarm(alarm,arrived,topology,{},now); assert.equal(first.events.length,1);
  const restored=JSON.parse(JSON.stringify(first.memory));
  assert.equal(evaluateAlarm(alarm,{...arrived,updatedAt:new Date(now+15000).toISOString()},topology,restored,now+15000).events.length,0);
});
test('stale, failed, old, wrong direction and disabled data never ring',()=>{
  for(const changed of [{...arrived,stale:true},{...arrived,status:'error'},{...arrived,updatedAt:new Date(now-91000).toISOString()},{...arrived,routeId:'other'}])
    assert.equal(evaluateAlarm(alarm,changed,topology,{},now).events.length,0);
  assert.equal(evaluateAlarm({...alarm,enabled:false},arrived,topology,{},now).events.length,0);
  assert.equal(evaluateAlarm(alarm,arrived,{...topology,stale:true},{},now).events.length,0);
  assert.equal(evaluateAlarm({...alarm,nodeId:'wrong'},arrived,topology,{},now).events.length,0);
});
test('skipping over target is not arrival; after passing a new trip can rearm',()=>{
  let result=evaluateAlarm(alarm,arrived,topology,{},now);
  const passed={...route,updatedAt:new Date(now+15000).toISOString(),vehicles:[{...vehicle,nodeOrd:16,nodeId:'E'}]};
  assert.equal(evaluateAlarm(alarm,passed,topology,{},now+15000).events.length,0);
  result=evaluateAlarm(alarm,passed,topology,result.memory,now+15000);
  const reset={...route,updatedAt:new Date(now+30000).toISOString(),vehicles:[{...vehicle,nodeOrd:2,nodeId:'A'}]};
  result=evaluateAlarm(alarm,reset,topology,result.memory,now+30000);
  result=evaluateAlarm(alarm,{...arrived,updatedAt:new Date(now+45000).toISOString()},topology,result.memory,now+45000);
  assert.equal(result.events.length,1);
});
test('three dropdowns can use only registered buses and their own direction stops',()=>{
  const all=[topology,{...topology,busNo:'10',routeId:'OTHER',stops:[{nodeOrd:1,name:'다른 정류소'}]}];
  assert.deepEqual(alarmChoices(['160'],all,'10','OTHER'),{buses:['160'],directions:[],stops:[]});
  assert.equal(alarmChoices(['160'],all,'160','R').stops.length,5);
  assert.equal(alarmChoices(['160'],all,'160','OTHER').stops.length,0);
  assert.deepEqual(alarmChoices([],all,'160','R').buses,[]);
});
test('corrupted saved alarm is disabled safely',()=>{
  assert.equal(readAlarm('{oops'),null); assert.equal(readAlarm('{"enabled":true}'),null);
  assert.deepEqual(readAlarm(JSON.stringify(alarm)),alarm);
});

test('same-direction variants form two groups and target stops exclude the reverse road',()=>{
  const forward={routeId:'F',busNo:'160',startName:'출발',endName:'도착',stops};
  const branch={...forward,routeId:'F2',endName:'연장종점',stops:[...stops,{nodeOrd:20,nodeId:'Z',name:'연장'}]};
  const reverse={routeId:'R',busNo:'160',startName:'도착',endName:'출발',stops:[...stops].reverse().map((s,i)=>({...s,nodeId:s.nodeId+'other',nodeOrd:i+1}))};
  const groups=directionGroups([forward,branch,reverse]);
  assert.equal(groups.length,2);
  const outward=groups.find(g=>g.routes.some(r=>r.routeId==='F'));
  assert.equal(outward.routes.length,2);
  assert.equal(outward.stops.length,6);
  assert.equal(outward.stops.some(s=>s.nodeId.endsWith('other')),false);
  assert.equal(outward.stops.find(s=>s.nodeId==='Z').targets.length,1);
});
test('Korean time window includes start, excludes end and respects days and overnight',()=>{
  const rule={startTime:'07:00',endTime:'07:30',days:[0,1,2,3,4],timezone:'Asia/Seoul'};
  assert.equal(scheduleWindow(rule,Date.parse('2026-10-07T22:00:00Z')),'2026-10-08');
  assert.equal(scheduleWindow(rule,Date.parse('2026-10-07T22:30:00Z')),null);
  assert.equal(scheduleWindow(rule,Date.parse('2026-10-09T22:10:00Z')),null);
  assert.equal(scheduleWindow({...rule,startTime:'23:00',endTime:'01:00'},Date.parse('2026-10-08T15:30:00Z')),'2026-10-08');
});
