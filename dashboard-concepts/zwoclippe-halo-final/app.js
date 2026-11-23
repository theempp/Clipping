/* Zwoclippe finalists: shared sample data + behavior. Each page styles the same class names its own way. */
(function(){
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const Q=[
 {id:'q1',who:'Lacy',av:'av_lacy.jpg',src:'full.mp4',img:'full.jpg',len:'0:40',sec:40,sc:91,hook:94,pay:88,trend:90,age:'4 min ago',t:'Lacy gets told "you all die" before the heist',h:'IF ANYTHING GOES WRONG WE ALL DIE',views:'62K',when:'Today 7:30 PM'},
 {id:'q2',who:'Lacy',av:'av_lacy.jpg',src:'clip2.mp4',img:'clip2.jpg',len:'0:08',sec:8,sc:86,hook:90,pay:84,trend:81,age:'11 min ago',t:'Lacy is locking in for the vault run',h:"I'M LOCKING IN",views:'41K',when:'Today 10:00 PM'},
 {id:'q3',who:'Lacy',av:'av_lacy.jpg',src:'clip1.mp4',img:'clip1.jpg',len:'0:08',sec:8,sc:82,hook:85,pay:80,trend:79,age:'18 min ago',t:'Lacy shuts down the crew plan in one word',h:'NOPE.',views:'33K',when:'Tomorrow 12:30 PM'},
 {id:'q4',who:'Jynxzi',av:'av_jynxzi.jpg',src:'clip3.mp4',img:'clip3.jpg',len:'0:08',sec:8,sc:78,hook:81,pay:76,trend:77,age:'26 min ago',t:'Jynxzi rage quits after the heist speech',h:'HE REALLY SAID THAT',views:'28K',when:'Tomorrow 3:00 PM'},
 {id:'q5',who:'Stable Ronaldo',av:'av_stableronaldo.jpg',src:'clip4.mp4',img:'clip4.jpg',len:'0:08',sec:8,sc:71,hook:74,pay:70,trend:68,age:'40 min ago',t:'Stable Ronaldo finds the hidden armory',h:'THE ARMORY IS INSANE',views:'19K',when:'Tomorrow 5:30 PM'},
 {id:'q6',who:'Lacy',av:'av_lacy.jpg',src:'clip3.mp4',img:'clip3.jpg',len:'0:08',sec:8,sc:68,hook:70,pay:66,trend:69,age:'52 min ago',t:"Lacy's chat floods the screen at the reveal",h:'CHAT WENT CRAZY',views:'15K',when:'Not scheduled'},
 {id:'q7',who:'Jynxzi',av:'av_jynxzi.jpg',src:'clip1.mp4',img:'clip1.jpg',len:'0:08',sec:8,sc:64,hook:66,pay:63,trend:62,age:'1 h ago',t:'Jynxzi argues with the heist crew',h:'WHO PLANNED THIS',views:'11K',when:'Not scheduled'}
];
const st={hero:'q1',status:{},edited:{},picks:{q1:['YouTube','TikTok']},pop:null,ed:null};
const byId=id=>Q.find(q=>q.id===id);
const PL=['YouTube','TikTok','X'];
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
window.ZW={Q,st,$,$$};

/* toast */
let tt;function toast(m){let t=$('#toast');if(!t){t=document.createElement('div');t.id='toast';t.className='toast';t.setAttribute('role','status');document.body.append(t)}t.textContent=m;t.classList.add('on');clearTimeout(tt);tt=setTimeout(()=>t.classList.remove('on'),2400)}
window.ZW.toast=toast;

/* score dial */
function dial(sc,size=74){const r=size/2-6,c=2*Math.PI*r;return `<svg class="dialsvg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" aria-label="Grok score ${sc}"><circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" class="dtrk" stroke-width="7"/><circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" class="darc" stroke-width="7" stroke-linecap="round" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${(c*(1-sc/100)).toFixed(1)}" transform="rotate(-90 ${size/2} ${size/2})"/><text x="50%" y="54%" text-anchor="middle" dominant-baseline="middle" class="dtxt" font-size="${Math.round(size*.28)}">${sc}</text></svg>`}
window.ZW.dial=dial;

/* queue list */
const COL={Lacy:'#ff7a59',Jynxzi:'#8fc4ff','Stable Ronaldo':'#6fe3b0',xQc:'#b18cff'};
function ring(sc){const c=2*Math.PI*15;return `<svg class="qring" viewBox="0 0 38 38" aria-label="Score ${sc}"><circle cx="19" cy="19" r="15" fill="none" class="qrt" stroke-width="3.5"/><circle cx="19" cy="19" r="15" fill="none" class="qra" stroke-width="3.5" stroke-linecap="round" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${(c*(1-sc/100)).toFixed(1)}" transform="rotate(-90 19 19)"/><text x="19" y="20" text-anchor="middle" dominant-baseline="middle">${sc}</text></svg>`}
function renderQueue(){const box=$('#queue');if(!box)return;const list=Q.filter(q=>q.id!==st.hero&&st.status[q.id]!=='Rejected');
 box.innerHTML=list.map((q,i)=>`<li><button class="qi${st.status[q.id]?' done':''}" data-open="${q.id}" style="--d:${i*45}ms;--c:${COL[q.who]||'#8fc4ff'}">
  <span class="qth"><img src="${q.img}" alt=""><em>${q.len}</em><i class="qplay" aria-hidden="true">▶</i></span>
  <span class="qtx"><span class="qtop">${/min ago/.test(q.age)&&parseInt(q.age)<15?'<span class="new">NEW</span>':''}<span class="qwho"><img class="qav" src="${q.av}" alt="">${q.who}</span><span class="qage">${q.age}</span></span><b>${esc(q.t)}</b>
  <span class="qmeta">${st.status[q.id]?`<span class="tag ok">${st.status[q.id]}</span>`:`<span>Hook ${q.hook}</span><span>Est. ${q.views}</span>`}</span></span>
  ${ring(q.sc)}</button></li>`).join('');
 const n=$('#qcount');if(n)n.textContent=list.length+1;}
let hv;document.addEventListener('mouseover',e=>{const b=e.target.closest('#queue .qi');if(!b||b.querySelector('video'))return;const it=byId(b.dataset.open);const v=document.createElement('video');v.src=it.src;v.muted=true;v.autoplay=true;v.loop=true;v.playsInline=true;b.querySelector('.qth').append(v)});
document.addEventListener('mouseout',e=>{const b=e.target.closest('#queue .qi');if(!b||b.contains(e.relatedTarget))return;const v=b.querySelector('video');v&&v.remove()});
window.ZW.renderQueue=renderQueue;

/* post chips */
function chips(id){const p=st.picks[id]||[];return PL.map(x=>`<button class="pch${p.includes(x)?' on':''}" data-pick="${x}" data-for="${id}" aria-pressed="${p.includes(x)}">${icon(x)}${x==='X'?'':x}</button>`).join('')}
function icon(x){return {YouTube:'<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M21.6 7.2a2.7 2.7 0 0 0-1.9-1.9C18 4.8 12 4.8 12 4.8s-6 0-7.7.5a2.7 2.7 0 0 0-1.9 1.9C2 8.9 2 12 2 12s0 3.1.4 4.8a2.7 2.7 0 0 0 1.9 1.9c1.7.5 7.7.5 7.7.5s6 0 7.7-.5a2.7 2.7 0 0 0 1.9-1.9c.4-1.7.4-4.8.4-4.8s0-3.1-.4-4.8ZM10 15.1V8.9l5.2 3.1Z"/></svg>',
 TikTok:'<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M16.6 3c.3 2.2 1.6 3.6 3.9 3.8v2.6a6.6 6.6 0 0 1-3.8-1.2v5.5c0 3.4-2.5 5.8-5.7 5.8a5.6 5.6 0 0 1-5.6-5.6c0-3.4 2.9-6 6.6-5.5v2.8c-1.6-.4-3.8.4-3.8 2.7 0 1.6 1.2 2.8 2.8 2.8 1.7 0 2.9-1.1 2.9-3.1V3Z"/></svg>',
 X:'<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path fill="currentColor" d="M17.8 3h3l-6.6 7.6L22 21h-6.1l-4.8-6.3L5.6 21h-3l7.1-8.1L2.2 3h6.2l4.3 5.8Zm-1 16.2h1.7L7.3 4.7H5.5Z"/></svg>'}[x]}
window.ZW.chips=chips;window.ZW.icon=icon;

/* hero */
function renderHero(){const q=byId(st.hero);const h=$('#hero');if(!h)return;
 $('#h-title').textContent=q.t;$('#h-who').textContent=`${q.who} · Twitch · ${q.len} · found ${q.age}`;
 $('#h-dial').innerHTML=dial(q.sc,parseInt($('#h-dial').dataset.size||84));
 $('#h-break').innerHTML=[['Hook',q.hook],['Payoff',q.pay],['Trend',q.trend]].map(([k,v])=>`<span><b>${v}</b>${k}<i><i style="width:${v}%"></i></i></span>`).join('')+`<span class="evv"><b>${q.views}</b>Est. views</span>`;
 $('#h-cap').textContent=$('#h-in').value=q.h;$('#h-chips').innerHTML=chips(q.id);
 const s=st.status[q.id],e=st.edited[q.id];$('#h-state').innerHTML=(e?'<span class="tag ed">Edited by you · saved</span>':'')+(s?`<span class="tag ok">${s}</span>`:'<span class="tag">Waiting for you</span>');
 h.classList.toggle('approved',s==='Approved');h.classList.toggle('justsaved',!!e);
 $$('[data-edit]',h).forEach(b=>b.dataset.edit=q.id);$$('[data-post]',h).forEach(b=>b.dataset.post=q.id);
 const v=$('video',h);if(v&&!v.getAttribute('src').endsWith(q.src)){v.src=q.src;v.poster=q.img;v.play().catch(()=>{})}
 const bg=$('.bgv',h);if(bg)bg.style.backgroundImage=`url(${q.img})`;}
window.ZW.renderHero=renderHero;

/* popup */
function openPop(id){const q=byId(id);st.pop=id;const m=document.createElement('div');m.className='pop';m.id='pop';
 m.innerHTML=`<div class="popbx" role="dialog" aria-modal="true" aria-label="Review clip">
 <button class="x" data-close aria-label="Close">✕</button>
 <div class="pvid"><video id="pv" src="${q.src}" poster="${q.img}" playsinline loop autoplay muted></video><span class="pcap">${esc(q.h)}</span>
  <div class="pctl"><button data-pp aria-label="Play or pause">❚❚</button><div class="pscrub" data-scrub><i id="pvb"></i></div><button data-mute aria-label="Sound">🔇</button></div></div>
 <div class="pmeta"><span class="lbl">${q.who} · Twitch · ${q.len} · found ${q.age}</span><h3>${esc(q.t)}</h3>
  <div class="prow">${dial(q.sc,70)}<div class="pbrk"><span><b>${q.hook}</b>Hook</span><span><b>${q.pay}</b>Payoff</span><span><b>${q.trend}</b>Trend</span><span><b>${q.views}</b>Est. views</span></div></div>
  <label class="lbl" for="p-in">Headline</label><input class="fld" id="p-in" value="${esc(q.h)}">
  <div class="acts"><button class="btn w" data-st="Approved" data-for="${id}">Approve</button><button class="btn" data-st="Revise requested" data-for="${id}">Revise</button><button class="btn r" data-st="Rejected" data-for="${id}">Reject</button><button class="btn ed" data-edit="${id}">✎ Edit clip</button></div>
  <span class="lbl">Post to</span><div class="chips">${chips(id)}</div>
  <div class="acts"><button class="btn post" data-post="${id}">Post now</button><span class="mut sm">Scheduled slot: ${q.when}</span></div>
 </div></div>`;
 document.body.append(m);requestAnimationFrame(()=>m.classList.add('on'));$('[data-close]',m).focus();
 const v=$('#pv');v.addEventListener('timeupdate',()=>{$('#pvb').style.width=(v.currentTime/v.duration*100||0)+'%'});}
function closePop(){const m=$('#pop');if(!m)return;m.classList.remove('on');setTimeout(()=>m.remove(),220);st.pop=null}
window.ZW.openPop=openPop;

/* confirm post */
function confirmPost(id){const p=st.picks[id]||[];if(!p.length){toast('Pick at least one platform first');return}
 if(st.status[id]!=='Approved'){toast('Approve the clip before posting');return}
 const q=byId(id);const c=document.createElement('div');c.className='pop cf';c.id='cf';
 c.innerHTML=`<div class="popbx sm" role="alertdialog" aria-modal="true" aria-label="Confirm post"><h3>Post this clip?</h3><p class="mut">"${esc(q.t)}" goes public on <b>${p.join(', ')}</b>. This can't be undone from here.</p><div class="acts"><button class="btn w" data-go="${id}">Post to ${p.length} platform${p.length>1?'s':''}</button><button class="btn" data-cfx>Cancel</button></div></div>`;
 document.body.append(c);requestAnimationFrame(()=>c.classList.add('on'));$('[data-go]',c).focus()}

/* editor */
const TOOLS=[['trim','Trim'],['cap','Captions'],['head','Headline'],['crop','Crop'],['fb','Flashback'],['aud','Audio']];
function openEditor(id){closePop();const q=byId(id);st.ed={id,tool:'trim',a:8,b:92};const r=$('#editor');
 r.innerHTML=`<div class="edbar"><button class="btn" data-edx>← Back</button><div class="edttl"><span class="lbl">Editing · ${q.who}</span><b>${esc(q.t)}</b></div><span class="sp"></span><span class="mut sm" id="ed-dirty">No changes yet</span><button class="btn" data-edx>Cancel</button><button class="btn w" data-save>Save changes</button></div>
 <div class="edmain"><nav class="edtools" aria-label="Editing tools">${TOOLS.map(([k,l],i)=>`<button data-tool="${k}" class="${i?'':'on'}">${tIcon(k)}<span>${l}</span></button>`).join('')}</nav>
  <div class="edstage"><div class="edphone"><video id="ev" src="${q.src}" poster="${q.img}" playsinline loop autoplay muted></video><span class="pcap" id="ed-cap">${esc(q.h)}</span><div class="safe" aria-hidden="true"></div></div></div>
  <aside class="edinsp" id="ed-insp"></aside></div>
 <div class="edtl"><div class="tlhead"><button class="btn sm2" data-epp>❚❚ Pause</button><span class="mono" id="ed-time">0:00 / ${q.len}</span><span class="sp"></span><span class="mut sm">Drag the handles to trim. Zoom effects are off for every clip.</span></div>
  <div class="tracks" id="tracks"><div class="trk vid"><span class="tn">Video</span><div class="lane" id="lane">${Array.from({length:14},(_,i)=>`<i style="background-image:url(${q.img})"></i>`).join('')}<div class="trim" id="trim"><b class="hd l" data-h="a"></b><b class="hd r" data-h="b"></b></div></div></div>
  <div class="trk cap"><span class="tn">Captions</span><div class="lane">${['IF','ANYTHING','GOES','WRONG','WE ALL','DIE'].map((w,i)=>`<em style="left:${10+i*14}%">${w}</em>`).join('')}</div></div>
  <div class="trk aud"><span class="tn">Audio</span><div class="lane wave">${Array.from({length:90},(_,i)=>`<i style="height:${18+Math.abs(Math.sin(i*.7)*60+Math.sin(i*.23)*20)}%"></i>`).join('')}</div></div>
  <div class="ph" id="ph"></div></div></div>`;
 document.body.classList.add('editing');renderInsp();
 const v=$('#ev');v.addEventListener('timeupdate',()=>{const p=v.currentTime/v.duration||0;$('#ph').style.left=`calc(84px + (100% - 84px) * ${p})`;const s=Math.floor(v.currentTime);$('#ed-time').textContent=`0:${String(s).padStart(2,'0')} / ${q.len}`});
 drawTrim();}
function tIcon(k){const p={trim:'M6 4v16M18 4v16M6 12h12',cap:'M4 6h16v12H4zM8 12h3M13 12h3M8 15h8',head:'M5 5h14M12 5v14',crop:'M7 3v14h14M3 7h14v14',fb:'M4 12a8 8 0 1 0 3-6.2M4 4v4h4',aud:'M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2'}[k];return `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="${p}"/></svg>`}
function renderInsp(){const e=st.ed,q=byId(e.id),i=$('#ed-insp');const T={
 trim:`<h4>Trim</h4><p class="mut sm">Start and end of the clip. Hook must land in the first 3 s.</p><div class="kv"><span>Start</span><b class="mono" id="k-a"></b></div><div class="kv"><span>End</span><b class="mono" id="k-b"></b></div><div class="kv"><span>Length</span><b class="mono" id="k-l"></b></div><button class="btn full" data-snap>Snap start to hook</button>`,
 cap:`<h4>Captions</h4><p class="mut sm">Word-by-word, 72 px. Minimum is 60 px.</p><label class="lbl" for="e-sz">Size</label><input type="range" id="e-sz" min="60" max="96" value="72"><div class="seg"><button class="on">Bold pop</button><button>Clean</button><button>Outline</button></div><label class="lbl" for="e-cc">Highlight color</label><div class="sw"><button class="on" style="--c:#ffe14d" aria-label="Yellow"></button><button style="--c:#7cf0c0" aria-label="Mint"></button><button style="--c:#ff6fb5" aria-label="Pink"></button><button style="--c:#fff" aria-label="White"></button></div>`,
 head:`<h4>Headline</h4><p class="mut sm">Shows for the first 3 s.</p><label class="lbl" for="e-h">Text</label><textarea class="fld" id="e-h" rows="3">${esc(q.h)}</textarea><div class="kv"><span>Grok suggests</span><b>WE ALL DIE IF THIS FAILS</b></div>`,
 crop:`<h4>Crop</h4><p class="mut sm">Facecam on top, gameplay below. Lacy's crop box is approved.</p><div class="seg"><button class="on">Stack</button><button>Full game</button><button>Facecam</button></div><div class="kv"><span>Split</span><b class="mono">38 / 62</b></div>`,
 fb:`<h4>Flashback</h4><p class="mut sm">Hard cut back to a related moment with heavy effects and a rewind sound.</p><button class="fbpick on"><img src="clip2.jpg" alt=""><span><b>Same stream, 1:42:10</b><small>Lacy promises the plan is safe</small></span></button><button class="fbpick"><img src="clip4.jpg" alt=""><span><b>Lacy viral, Kick</b><small>"Nothing can go wrong" · 1.2M</small></span></button><div class="kv"><span>Rewind SFX</span><b>On</b></div><div class="kv"><span>Effect strength</span><b>Intense</b></div>`,
 aud:`<h4>Audio</h4><label class="lbl" for="e-v">Stream volume</label><input type="range" id="e-v" min="0" max="100" value="85"><label class="lbl" for="e-m">Music bed</label><input type="range" id="e-m" min="0" max="100" value="20"><div class="kv"><span>Loudness</span><b class="mono">-14 LUFS</b></div>`};
 i.innerHTML=T[e.tool];$$('.edtools button').forEach(b=>b.classList.toggle('on',b.dataset.tool===e.tool));drawTrim()}
function fmt(p){const s=byId(st.ed.id).sec*p/100;return '0:'+String(Math.floor(s)).padStart(2,'0')+'.'+Math.floor(s%1*10)}
function drawTrim(){const e=st.ed;if(!e)return;const t=$('#trim');if(!t)return;t.style.left=e.a+'%';t.style.width=(e.b-e.a)+'%';
 if($('#k-a')){$('#k-a').textContent=fmt(e.a);$('#k-b').textContent=fmt(e.b);$('#k-l').textContent=fmt(e.b-e.a).replace('0:','')+' s'}}
function dirty(){const d=$('#ed-dirty');if(d){d.textContent='Unsaved changes';d.classList.add('dirty')}}
function closeEditor(save){const e=st.ed;if(!e)return;if(save){st.edited[e.id]=true;const h=$('#e-h');if(h)byId(e.id).h=h.value.toUpperCase()}
 document.body.classList.remove('editing');$('#editor').innerHTML='';st.ed=null;
 if(save){if(e.id!==st.hero){st.hero=e.id;renderQueue()}renderHero();toast('Saved. Pick where to post it.');const c=$('#h-chips');c&&c.classList.add('nudge');setTimeout(()=>c&&c.classList.remove('nudge'),2600)}}

/* drag trim */
let drag=null;document.addEventListener('pointerdown',ev=>{const h=ev.target.closest('[data-h]');if(!h)return;drag=h.dataset.h;h.setPointerCapture(ev.pointerId);ev.preventDefault()});
document.addEventListener('pointermove',ev=>{if(!drag)return;const l=$('#lane').getBoundingClientRect();let p=(ev.clientX-l.left)/l.width*100;p=Math.max(0,Math.min(100,p));const e=st.ed;
 if(drag==='a')e.a=Math.min(p,e.b-5);else e.b=Math.max(p,e.a+5);drawTrim();dirty()});
document.addEventListener('pointerup',()=>drag=null);

/* wake */
function setWake(on){document.body.classList.toggle('awake',on);const w=$('#wake');if(w)w.setAttribute('aria-pressed',on);
 const l=$('#wakel');if(l)l.textContent=on?'Awake · 3 agents':'Asleep · 3 min ago';
 if(on){document.body.classList.remove('waking');void document.body.offsetWidth;document.body.classList.add('waking');setTimeout(()=>document.body.classList.remove('waking'),1600)}}
window.ZW.setWake=setWake;

/* clicks */
document.addEventListener('click',e=>{const t=e.target;let b;
 if(b=t.closest('[data-open]'))return openPop(b.dataset.open);
 if(t.closest('[data-close]')||t.classList.contains('pop')&&!t.classList.contains('cf'))return closePop();
 if(b=t.closest('[data-pick]')){const id=b.dataset.for,p=st.picks[id]=st.picks[id]||[];const x=b.dataset.pick;p.includes(x)?p.splice(p.indexOf(x),1):p.push(x);b.classList.toggle('on');b.setAttribute('aria-pressed',p.includes(x));return}
 if(b=t.closest('[data-st]')){const id=b.dataset.for||st.hero,s=b.dataset.st;st.status[id]=s;toast(s==='Approved'?'Approved. Pick platforms, then post.':s==='Rejected'?'Rejected. Grok learns from it.':'Sent back to the editing agent');
  if(id===st.hero)renderHero();else{if(s==='Rejected')closePop();renderQueue();const a=t.closest('.popbx');a&&a.classList.toggle('approved',s==='Approved')}return}
 if(b=t.closest('[data-edit]'))return openEditor(b.dataset.edit);
 if(b=t.closest('[data-post]'))return confirmPost(b.dataset.post);
 if(b=t.closest('[data-go]')){const id=b.dataset.go;st.status[id]='Posted';$('#cf').remove();closePop();toast('Posting to '+(st.picks[id]||[]).join(', '));id===st.hero?renderHero():renderQueue();return}
 if(t.closest('[data-cfx]'))return $('#cf').remove();
 if(b=t.closest('[data-tool]')){st.ed.tool=b.dataset.tool;return renderInsp()}
 if(t.closest('[data-save]'))return closeEditor(true);
 if(t.closest('[data-edx]'))return closeEditor(false);
 if(t.closest('[data-snap]')){st.ed.a=3;drawTrim();dirty();return}
 if(b=t.closest('.seg button,.sw button,.fbpick')){$$('button',b.parentElement).forEach(x=>x.classList.toggle('on',x===b));dirty();return}
 if(b=t.closest('[data-epp]')){const v=$('#ev');v.paused?(v.play(),b.textContent='❚❚ Pause'):(v.pause(),b.textContent='▶ Play');return}
 if(b=t.closest('[data-pp]')){const v=$('#pv');v.paused?(v.play(),b.textContent='❚❚'):(v.pause(),b.textContent='▶');return}
 if(b=t.closest('[data-mute]')){const v=$('#pv');v.muted=!v.muted;b.textContent=v.muted?'🔇':'🔊';return}
 if(b=t.closest('[data-scrub]')){const v=$('#pv'),r=b.getBoundingClientRect();v.currentTime=(e.clientX-r.left)/r.width*v.duration;return}
 if(b=t.closest('#wake'))return setWake(b.getAttribute('aria-pressed')!=='true');
 if(b=t.closest('[data-dock]'))return toast(b.dataset.dock);
 if(b=t.closest('.dots a')){e.preventDefault();if(!b.classList.contains('on'))toast('This round finalizes the Review page. Other pages follow the winner.');return}
});
document.addEventListener('input',e=>{if(e.target.id==='h-in'){$('#h-cap').textContent=e.target.value.toUpperCase();byId(st.hero).h=e.target.value.toUpperCase()}
 if(e.target.id==='e-h'){$('#ed-cap').textContent=e.target.value.toUpperCase();dirty()}if(e.target.id==='p-in'){$('.pcap',$('#pop')).textContent=e.target.value.toUpperCase()}
 if(e.target.closest('#ed-insp'))dirty()});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){if($('#cf'))$('#cf').remove();else if($('#pop'))closePop();else if(st.ed)closeEditor(false)}
 if(e.key==='/'&&document.activeElement.tagName!=='INPUT'&&document.activeElement.tagName!=='TEXTAREA'){const q=$('#q');if(q){e.preventDefault();q.focus()}}});

document.addEventListener('DOMContentLoaded',()=>{renderHero();renderQueue();document.body.classList.add('awake','waking');setTimeout(()=>document.body.classList.remove('waking'),1800)});
})();
