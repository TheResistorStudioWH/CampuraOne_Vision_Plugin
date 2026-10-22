'use strict';
const $ = id => document.getElementById(id);
// Fragment is never sent in an HTTP request. Keep token only in this page's memory.
const token = location.hash.slice(1);
history.replaceState(null, '', '/');
let input = null;
let revision = 0;
let autoCalculate = true;
const labels = {scenario:'模拟情景范围', partial:'仅有分段', unavailable:'资料不足', pending:'待商家确认', ready:'已可取餐', cancelled:'已取消', not_supported:'本版不提供'};
const sources = {vision:'视觉汇总', orders:'订单快照', service_queue:'交易队伍', forecast:'未来需求情景', page_views:'页面浏览人数', calibration:'匿名时长样本'};
const range = x => x ? `${x[0]}–${x[1]}` : '—';
const node = (tag, text, className) => { const e=document.createElement(tag); if(text!==undefined)e.textContent=text; if(className)e.className=className; return e; };
async function api(path, data) {
  const response=await fetch(path, {method:data===undefined?'GET':'POST', headers:{'X-Campura-Token':token, 'Content-Type':'application/json'}, ...(data===undefined?{}:{body:JSON.stringify(data)})});
  const result=await response.json();
  if(!response.ok) throw new Error(result.error || '本机服务不可用');
  return result;
}
function error(message) { $('error').textContent=message; $('error').hidden=!message; }
function syncForm() {
  const c=input.capacity, dining=input.kind==='dining', prefix=dining?'order':'checkout';
  $('arrival').value=input.arrival_minutes??'';
  $('prep').value=c.prep_minutes??1.5; $('slots').value=c.prep_slots??2;
  $('service').value=c[prefix+'_minutes']??0.5; $('service-slots').value=c[prefix+'_slots']??1;
  $('waiting').value=input.service_queue?.waiting??0; $('variation').value=(c.variation??0.2)*100;
  $('dining-fields').hidden=!dining;
  $('service-label').textContent=dining?'每次点单时长 · 分钟':'每笔结账时长 · 分钟';
  $('json-input').value=JSON.stringify(input,null,2);
}
function metric(name, value, detail) {
  const e=node('div',undefined,'metric');e.append(node('div',name,'name'),node('div',value,'value'),node('div',detail,'detail'));return e;
}
function render(result) {
  $('updated').textContent='计算于 '+new Date(result.calculated_at).toLocaleTimeString();
  const count=result.counts, stale=count.vision_state!=='fresh';
  const band={low:'较空',medium:'适中',high:'较挤',unknown:'未知'}[result.congestion.band];
  $('metrics').replaceChildren(
    metric('当前排队人数',count.queue_people??'—',stale?'过期 / 缺失，不代表当前': '人 · 独立于 ETA'),
    metric('店内总人数',count.occupancy??'—',stale?'视觉快照不可用':'包含浏览及候餐者'),
    result.kind==='dining'?metric('已接未完成订单',result.backlog??'—','单 · 按订单 ID 去重'):metric('拥挤程度',band,'模拟空间占用比例'),
    metric('页面浏览人数',count.active_page_viewers??'—',count.views_state==='fresh'?'人 · 尚未用于转化预测':'过期 / 缺失 · 不参与预测'));
  const cards=[];
  ['arrival_now','arrival_route','preorder'].forEach((key,i)=>{
    const value=result[key], card=node('article',undefined,'card');
    card.append(node('div',String(i+1).padStart(2,'0')+' / '+labels[value.status],'index'),node('h3',value.label));
    if(key==='arrival_route')card.append(node('div',`路程 ${result.travel_minutes??'未知'} 分钟 · 不含在等待中`,'route'));
    card.append(node('div',value.minutes?range(value.minutes):(labels[value.status]||'无法计算'),value.minutes?'eta':'eta empty'));
    card.append(node('div',value.minutes?'分钟 · 输入假设下的范围':'总 ETA 暂不显示','unit'));
    if(Object.keys(value.parts).length){const parts=node('div',undefined,'parts');Object.entries(value.parts).forEach(([k,v])=>{const p=node('div',undefined,'part');p.append(node('span',k),node('strong',range(v)+' 分钟'));parts.append(p)});card.append(parts);}
    const list=node('ul');[...value.reasons,...value.basis].forEach(text=>list.append(node('li',text)));card.append(list);cards.push(card);
  });
  $('cards').replaceChildren(...cards);
  $('kind').textContent=result.kind==='dining'?'餐饮 · 统一先确认先制作':'自选零售 · 挑选 + 结账';
  $('warnings').replaceChildren(...result.warnings.map(x=>node('li',x)));
  $('selection').textContent=result.selection?`${result.selection.basis}（匹配样本 ${result.selection.matching_samples} 个）`:'';
  const times=[];Object.entries(result.source_updated_at).forEach(([k,v])=>times.push(node('dt',sources[k]||k),node('dd',v?new Date(v).toLocaleString():'未提供')));$('timestamps').replaceChildren(...times);
  $('json-output').textContent=JSON.stringify(result,null,2);
}
async function calculate() {
  if(!input)return;
  const current=++revision;
  try {const result=await api('/api/estimate',input);if(current!==revision)return;render(result);error('');}
  catch(e){if(current!==revision)return;error(e.message);$('cards').replaceChildren(node('div','本次计算失败，旧结果已隐藏。','panel'));$('metrics').replaceChildren();$('updated').textContent='结果不可用';$('json-output').textContent='';}
}
async function load() {
  try{input=await api('/api/example?name='+encodeURIComponent($('scenario').value||'dining'));autoCalculate=true;syncForm();await calculate();}catch(e){error(e.message)}
}
$('load').addEventListener('click',load);
$('form').addEventListener('submit',async e=>{
  e.preventDefault();if(!input)return;autoCalculate=true;
  const c=input.capacity, prefix=input.kind==='dining'?'order':'checkout';
  input.arrival_minutes=$('arrival').value===''?null:Number($('arrival').value);
  c.prep_minutes=Number($('prep').value);c.prep_slots=Number($('slots').value);
  c[prefix+'_minutes']=Number($('service').value);c[prefix+'_slots']=Number($('service-slots').value);
  c.variation=Number($('variation').value)/100;
  if(input.service_queue)input.service_queue.waiting=Number($('waiting').value);
  $('json-input').value=JSON.stringify(input,null,2);await calculate();
});
$('refresh').addEventListener('click',async()=>{
  if(!input)return;autoCalculate=true;const now=new Date().toISOString();
  // Explicitly regenerate mock observation times; never used for real data.
  for(const name of ['vision','orders','service_queue','forecast','page_views','calibration'])if(input[name])input[name].observed_at=now;
  $('json-input').value=JSON.stringify(input,null,2);await calculate();
});
$('apply-json').addEventListener('click',async()=>{
  autoCalculate=false;revision++;
  try {const candidate=JSON.parse($('json-input').value);const result=await api('/api/estimate',candidate);revision++;input=candidate;autoCalculate=true;syncForm();render(result);error('');}
  catch(e){error(e.message);$('cards').replaceChildren(node('div','JSON 输入未应用；请修正后再计算。','panel'));$('metrics').replaceChildren();$('updated').textContent='结果不可用';$('json-output').textContent='';}
});
(async()=>{
  if(!token){error('请使用终端显示的完整启动地址打开。页面刷新后需要重新打开启动地址。');return;}
  try{const names=await api('/api/examples');for(const [key,value]of Object.entries(names)){const option=node('option',value);option.value=key;$('scenario').append(option)}await load();}
  catch(e){error(e.message)}
})();
// A disconnected or frozen input must not leave a live-looking ETA on screen.
setInterval(()=>{if(input&&autoCalculate)calculate()},10000);
