"""Minimal local configuration page; no external assets or network requests."""

PAGE = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Campura One 店内视觉分析 · 离线原型</title>
<style>
:root{font-family:system-ui,-apple-system,"Microsoft YaHei",sans-serif;color:#183047;background:#f5f8fb}
*{box-sizing:border-box}body{margin:0;padding:24px}main{max-width:1160px;margin:auto}h1{font-size:27px;margin:0 0 7px}h2{font-size:18px;margin:0 0 15px}p{line-height:1.55}.muted{color:#526779}.grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(300px,1fr);gap:18px}.panel{background:#fff;border:1px solid #dce5eb;border-radius:16px;padding:20px;box-shadow:0 5px 20px #1d40510a}.preview{width:100%;aspect-ratio:16/9;background:#10202a;border-radius:10px;position:relative;overflow:hidden}.preview canvas{width:100%;height:100%;display:block;cursor:crosshair}.buttons{display:flex;flex-wrap:wrap;gap:9px;margin:14px 0}button{border:1px solid #bfd0d9;background:#eef5f8;color:#163c52;border-radius:9px;padding:9px 13px;font:inherit;cursor:pointer}button.primary{background:#176b83;color:#fff;border-color:#176b83}button:hover{filter:brightness(.96)}button:disabled{opacity:.5;cursor:default}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.stat{background:#eef6f8;padding:13px;border-radius:10px}.stat strong{display:block;font-size:26px}.stat small{color:#526779}.warn{background:#fff5df;border:1px solid #ead9a8;border-radius:9px;padding:10px 12px}.error{color:#a42828;min-height:20px}label{display:block;margin:10px 0}.state{font-weight:700}.footnote{font-size:13px;color:#526779}.file{word-break:break-all}@media(max-width:800px){.grid{grid-template-columns:1fr}.stats{grid-template-columns:1fr 1fr}}
</style></head><body><main>
<h1>店内视觉分析 · 离线原型</h1>
<p class="muted">可选插件独立运行。当前仅分析本机模拟视频；无摄像头接入、无云端上传。画面不录制，短时轨迹不持久化。</p>
<div class="grid"><section class="panel"><h2>本机预览与区域配置</h2><div class="preview"><canvas id="canvas" width="160" height="90"></canvas></div>
<div class="buttons"><button id="line">绘制计数线（点击两点）</button><button id="zone">绘制排队区域（点击四点）</button><button id="save">保存配置</button></div>
<p id="instruction" class="footnote">蓝线为计数线，标有“进入侧”的一边是进入方向；橙色框为排队区域。</p>
<label><input type="checkbox" id="entries" checked> 统计进入／离开人数</label>
<label><input type="checkbox" id="queue" checked> 统计当前排队区域人数</label>
<p class="footnote">测试视频：<span id="file" class="file"></span>。更换视频需重新启动程序并指定本机文件路径。</p>
</section><section class="panel"><h2>运行状态</h2><p>状态：<span id="state" class="state">未启动</span></p><p id="detail" class="muted"></p>
<div class="buttons"><button id="start" class="primary">开始／重新播放</button><button id="stop">停止</button></div>
<div class="stats"><div class="stat"><small>进入人数（累计）</small><strong id="in">0</strong></div><div class="stat"><small>离开人数（累计）</small><strong id="out">0</strong></div><div class="stat"><small id="queue-label">当前排队人数</small><strong id="q">—</strong></div></div>
<p class="warn">预计等候时间：<strong>不提供</strong><br>尚无服务速度或订单事件，不能从人数直接推算精确分钟数。</p>
<p id="error" class="error"></p><p class="footnote">演示检测器依赖固定背景和明显前景。统计值仅用于验证算法，不可用于真实门店决策。</p></section></div>
</main><script>
const token='__TOKEN__'; const canvas=document.getElementById('canvas');const ctx=canvas.getContext('2d');
let config=null,mode=null,points=[],frame=null,lastFrame=-1;
async function api(path,body){const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:{'X-Campura-Token':token,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});const data=await response.json();if(!response.ok)throw Error(data.error||'请求失败');return data}
function pt(p){return [p[0]*160,p[1]*90]}
function paint(){ctx.fillStyle='#10202a';ctx.fillRect(0,0,160,90);if(frame)ctx.drawImage(frame,0,0,160,90);if(!config)return;
const line=mode==='line'&&points.length?points:config.line;ctx.strokeStyle='#58d2f4';ctx.lineWidth=1.6;ctx.beginPath();line.forEach((p,i)=>{const [x,y]=pt(p);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke();if(line.length===2){const [ax,ay]=pt(line[0]),[bx,by]=pt(line[1]),dx=bx-ax,dy=by-ay,size=Math.hypot(dx,dy)||1;ctx.font='5px sans-serif';ctx.fillStyle='#b6ebf7';ctx.fillText('进入侧',(ax+bx)/2-dy/size*9,(ay+by)/2+dx/size*9)}
const zone=mode==='zone'&&points.length?points:config.queue_zone;ctx.strokeStyle='#f9ad56';ctx.fillStyle='#f9ad562b';ctx.lineWidth=1.2;ctx.beginPath();zone.forEach((p,i)=>{const [x,y]=pt(p);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});if(zone.length>=3)ctx.closePath();ctx.fill();ctx.stroke();}
function setMode(value){mode=value;points=[];document.getElementById('instruction').textContent=value==='line'?'依次点击画面上计数线的两个端点。':value==='zone'?'依次点击排队区域的四个顶点。':'配置已更新；点击“保存配置”后生效。';paint()}
document.getElementById('line').onclick=()=>setMode('line');document.getElementById('zone').onclick=()=>setMode('zone');
canvas.onclick=e=>{if(!mode||!config)return;const box=canvas.getBoundingClientRect(),p=[Math.max(0,Math.min(1,(e.clientX-box.left)/box.width)),Math.max(0,Math.min(1,(e.clientY-box.top)/box.height))];points.push(p);const required=mode==='line'?2:4;if(points.length===required){config[mode==='line'?'line':'queue_zone']=points;setMode(null)}paint()};
document.getElementById('save').onclick=async()=>{try{config.count_entries=document.getElementById('entries').checked;config.count_queue=document.getElementById('queue').checked;await api('/api/config',config);showError('配置已保存到本次运行内存。')}catch(e){showError(e.message)}};
document.getElementById('start').onclick=async()=>{try{await api('/api/start',{});showError('')}catch(e){showError(e.message)}};
document.getElementById('stop').onclick=async()=>{try{await api('/api/stop',{});showError('')}catch(e){showError(e.message)}};
function showError(s){document.getElementById('error').textContent=s}
async function refresh(){try{const status=await api('/api/status');if(!config){config=status.config;document.getElementById('entries').checked=config.count_entries;document.getElementById('queue').checked=config.count_queue}document.getElementById('file').textContent=status.video_name;document.getElementById('state').textContent={idle:'未启动',opening:'正在打开',running:'运行中',complete:'播放结束',stopped:'已停止',disconnected:'连接中断',error:'错误'}[status.state]||status.state;document.getElementById('detail').textContent=status.detail;document.getElementById('in').textContent=status.result.entries;document.getElementById('out').textContent=status.result.exits;document.getElementById('q').textContent=status.queue_current_valid?status.result.queue_count:'—';document.getElementById('queue-label').textContent=status.queue_current_valid?'当前排队人数':'当前排队人数（不可用）';if(status.result.frame_index!==lastFrame){lastFrame=status.result.frame_index;const r=await fetch('/api/frame',{headers:{'X-Campura-Token':token},cache:'no-store'});if(r.ok&&r.status===200){const blob=await r.blob();const image=new Image();const url=URL.createObjectURL(blob);image.onload=()=>{frame=image;paint();URL.revokeObjectURL(url)};image.src=url}}paint()}catch(e){showError(e.message)}}
refresh();setInterval(refresh,250);
</script></body></html>'''
