const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/src-Cfreso1X.js","assets/rolldown-runtime-hePW80VL.js"])))=>i.map(i=>d[i]);
import{r as e}from"./rolldown-runtime-hePW80VL.js";import{n as t,t as n}from"./jsx-runtime-DE3RlOCf.js";import{t as r}from"./preload-helper-Czpn1I53.js";import{En as i,Er as a,It as o,Mn as s,Qn as c,Rr as l,Rt as u,dr as d,mr as f,nn as p,or as m,tr as h,ur as g}from"./index-Bl0G2K_i.js";var _=e(t(),1),v=n(),y={teoria:{stroke:`#bc8cff`,fill:`rgba(188,140,255,0.2)`},scripts:{stroke:`#3fb950`,fill:`rgba(63,185,80,0.2)`},test:{stroke:`#3fb950`,fill:`rgba(63,185,80,0.2)`},viz:{stroke:`#d29922`,fill:`rgba(210,153,34,0.2)`},docs:{stroke:`#58a6ff`,fill:`rgba(88,166,255,0.2)`},whitepapers:{stroke:`#ffd700`,fill:`rgba(255,215,0,0.2)`},pdf:{stroke:`#ff5555`,fill:`rgba(255,85,85,0.2)`},media:{stroke:`#bd93f9`,fill:`rgba(189,147,249,0.2)`}},b={teoria:`math1`,scripts:`code_architect`,viz:`viz-designer`,docs:`proof-reviewer`,whitepaper:`proof-reviewer`,pdf:`online_journalist`,media:`online_journalist`};function x({onOpenFile:e}){let{theme:t}=u(),n=t===`light`,i=(0,_.useRef)(null),a=(0,_.useRef)(null),[o,s]=(0,_.useState)([]),[c,l]=(0,_.useState)(!0),[d,f]=(0,_.useState)(null),[p,m]=(0,_.useState)(null),[h,g]=(0,_.useState)(null),[x,S]=(0,_.useState)(null),[C,w]=(0,_.useState)({width:500,height:260}),[T,ee]=(0,_.useState)({topics:0,modules:0,docs:0,teoria:0,test:0,viz:0,parentLinks:0}),[E,te]=(0,_.useState)(()=>localStorage.getItem(`sigma_mappa_explore`)===`true`),[D,ne]=(0,_.useState)(``),[re,O]=(0,_.useState)({}),[ie,ae]=(0,_.useState)({}),[oe,se]=(0,_.useState)(!0),[ce,k]=(0,_.useState)(!1),[A,le]=(0,_.useState)(null),[ue,de]=(0,_.useState)({x:0,y:0}),[j,fe]=(0,_.useState)([]),[M,N]=(0,_.useState)(!1),[pe,P]=(0,_.useState)(``),[F,me]=(0,_.useState)(`teoria`),[he,ge]=(0,_.useState)(!1),[I,_e]=(0,_.useState)(``),[L,ve]=(0,_.useState)(`math1`),[ye,R]=(0,_.useState)(``),[z,B]=(0,_.useState)(``);(0,_.useEffect)(()=>{b[F]&&ve(b[F])},[F]);let[V,be]=(0,_.useState)(``),[xe,Se]=(0,_.useState)(``),[Ce,we]=(0,_.useState)(`teoria`),[Te,Ee]=(0,_.useState)(``),[H,U]=(0,_.useState)(`ai_edit`),[W,De]=(0,_.useState)(`standard`),[G,Oe]=(0,_.useState)(null),[ke,Ae]=(0,_.useState)(!1),je=(0,_.useRef)(null),[Me,Ne]=(0,_.useState)(`create`),[Pe,Fe]=(0,_.useState)(``),[K,Ie]=(0,_.useState)(()=>{try{let e=localStorage.getItem(`sigma_graph_font_size`);return e?parseInt(e,10):16}catch{return 16}}),Le=e=>{Ie(e);try{localStorage.setItem(`sigma_graph_font_size`,String(e))}catch{}},[q,Re]=(0,_.useState)(()=>{try{let e=localStorage.getItem(`sigma_graph_branch_length`);return e?parseInt(e,10):240}catch{return 240}}),ze=e=>{Re(e);try{localStorage.setItem(`sigma_graph_branch_length`,String(e))}catch{}},[J,Be]=(0,_.useState)(()=>{try{return localStorage.getItem(`sigma_argomenti_theme`)||`costellazione`}catch{return`costellazione`}}),Ve=e=>{Be(e);try{localStorage.setItem(`sigma_argomenti_theme`,e)}catch{}window.dispatchEvent(new CustomEvent(`sigma_argomenti_theme_changed`,{detail:e}))};(0,_.useEffect)(()=>{let e=e=>{e.detail&&Be(e.detail)};return window.addEventListener(`sigma_argomenti_theme_changed`,e),()=>window.removeEventListener(`sigma_argomenti_theme_changed`,e)},[]);let He=()=>{if(!Y.current)return;let e=Y.current.nodes(),t={},n=e=>e==null?null:Math.round(e*10)/10;e.forEach(e=>{let r=e.fx==null?e.x:e.fx,i=e.fy==null?e.y:e.fy;t[e.id]={fx:n(r),fy:n(i),x:n(r),y:n(i)},e.fx=r,e.fy=i});try{localStorage.setItem(`sigma_graph_custom_positions`,JSON.stringify(t)),window.dispatchEvent(new CustomEvent(`sigma_toast`,{detail:{message:`💾 Layout del grafo salvato con successo!`,type:`success`,duration:5e3}}))}catch(e){if(e.name===`QuotaExceededError`||e.code===22||e.code===1014)try{localStorage.removeItem(`sigma_graph_custom_positions`),localStorage.setItem(`sigma_graph_custom_positions`,JSON.stringify(t))}catch{}}},Ue=()=>{try{localStorage.removeItem(`sigma_graph_custom_positions`)}catch{}Y.current&&(Y.current.nodes().forEach(e=>{e.fx=null,e.fy=null}),Y.current.alpha(1).restart()),window.dispatchEvent(new CustomEvent(`sigma_toast`,{detail:{message:`🔄 Layout del grafo ripristinato ai valori predefiniti!`,type:`info`,duration:5e3}}))};(0,_.useEffect)(()=>{ce||(De(`standard`),Oe(null),Ae(!1),B(``))},[ce]),(0,_.useEffect)(()=>{if(ce&&A&&A.type===`doc`){if(U(`ai_edit`),B(``),R(``),(async()=>{try{let e=await(await fetch(`/api/get_file?path=${encodeURIComponent(A.filePath)}`)).json();e.success&&Ee(e.content||``)}catch(e){console.error(`Error fetching file content:`,e)}})(),o.length>0){be(o[0].id);let e=o[0].modules||[];e.length>0?Se(e[0].number):Se(``)}we(A.docType||`teoria`)}else Ee(``)},[ce,A]),(0,_.useEffect)(()=>{if(V){let e=o.find(e=>e.id===V)?.modules||[];e.length>0?Se(e[0].number):Se(``)}},[V,o]);let[We,Ge]=(0,_.useState)(!1),[Ke,qe]=(0,_.useState)({x:0,y:0}),Je=e=>{e.button===0&&(Ge(!0),qe({x:e.clientX-ue.x,y:e.clientY-ue.y}),e.preventDefault())};(0,_.useEffect)(()=>{if(!We)return;let e=e=>{de({x:e.clientX-Ke.x,y:e.clientY-Ke.y})},t=()=>{Ge(!1)};return window.addEventListener(`mousemove`,e),window.addEventListener(`mouseup`,t),()=>{window.removeEventListener(`mousemove`,e),window.removeEventListener(`mouseup`,t)}},[We,Ke]);let Ye=e=>{e.preventDefault(),e.stopPropagation(),e.type===`dragenter`||e.type===`dragover`?Ae(!0):e.type===`dragleave`&&Ae(!1)},Xe=e=>{if(e.preventDefault(),e.stopPropagation(),Ae(!1),e.dataTransfer.files&&e.dataTransfer.files[0]){let t=e.dataTransfer.files[0];Oe(t);let n=t.name.split(`.`);n.length>1&&n.pop(),P(n.join(`.`))}},Ze=e=>{if(e.target.files&&e.target.files[0]){let t=e.target.files[0];Oe(t);let n=t.name.split(`.`);n.length>1&&n.pop(),P(n.join(`.`))}};(0,_.useEffect)(()=>{j.length>0&&!I&&_e(j[0].name)},[j,I]),(0,_.useEffect)(()=>{(async()=>{try{let e=await(await fetch(`/api/ollama_models`)).json();e.success&&e.models&&fe(e.models)}catch(e){console.error(`Error fetching AI models:`,e)}})()},[]);let Y=(0,_.useRef)(null),Qe=(0,_.useRef)(null),$e=(0,_.useRef)([]),[et,tt]=(0,_.useState)({}),[X,nt]=(0,_.useState)(null);(0,_.useEffect)(()=>{r(()=>import(`./src-Cfreso1X.js`).then(e=>e.t).then(e=>{nt(e),window.d3=e}),__vite__mapDeps([0,1]))},[]),(0,_.useEffect)(()=>{p&&p.type===`module`&&O(e=>({...e,[p.data.number]:!0}))},[p]);let Z=(0,_.useCallback)(async()=>{l(!0),f(null);try{let e=await fetch(`/api/topics`);if(!e.ok)throw Error(`HTTP ${e.status}`);let t=await e.json();if(!t.topics)throw Error(`Formato risposta non valido`);s(t.topics);try{let e=await fetch(`/api/agents/colors`);if(e.ok){let t=await e.json();t.success&&tt(t.colors)}}catch{}return t.topics}catch(e){return f(e.message),null}finally{l(!1)}},[]);(0,_.useEffect)(()=>{Z();let e=()=>{Z()};return window.addEventListener(`sigma_topics_updated`,e),window.addEventListener(`sigma_file_created`,e),()=>{window.removeEventListener(`sigma_topics_updated`,e),window.removeEventListener(`sigma_file_created`,e)}},[Z]),(0,_.useEffect)(()=>{let e=()=>{if(a.current){let e=a.current.clientWidth,t=a.current.clientHeight;e>0&&t>0&&w({width:e,height:t})}};e();let t=setTimeout(e,100);return window.addEventListener(`resize`,e),()=>{clearTimeout(t),window.removeEventListener(`resize`,e)}},[c,X]),(0,_.useEffect)(()=>{let e=0,t=0,n=0,r=0,i=0,a=0;for(let s of o)if(s.modules){e+=s.modules.length;for(let e of s.modules)t+=(e.docs||[]).length+(e.whitepapers||[]).length,n+=(e.teoria||[]).length,r+=(e.test||[]).length,i+=(e.viz||[]).length;s.parent_id&&a++}ee({topics:o.length,modules:e,docs:t,teoria:n,test:r,viz:i,parentLinks:a})},[o]);let rt=(0,_.useCallback)(()=>{let e=[],t=[],n={},r={},i=e=>{if(r[e]!==void 0)return r[e];let t=o.find(t=>t.id===e);if(!t||!t.parent_id)return r[e]=0,0;r[e]=0;let n=i(t.parent_id);return r[e]=n+1,r[e]};o.forEach(e=>i(e.id));let a={};for(let e of o)e.parent_id&&(a[e.parent_id]||(a[e.parent_id]=[]),a[e.parent_id].push(e.id));for(let i of o){let o=!i.parent_id,s=`topic-`+i.id,c=r[i.id]||0,l=0,u=0;if(i.parent_id&&a[i.parent_id]&&(l=a[i.parent_id].indexOf(i.id),u=a[i.parent_id].length),e.push({id:s,label:i.name,type:o?`topic`:`module`,data:i,topicId:i.id,parentTopicId:i.parent_id?`topic-`+i.parent_id:null,depth:c,childTopicIndex:l,totalChildTopics:u,r:o?22:16}),n[s]=!0,E){let r=0;for(let e of[`teoria`,`scripts`,`test`,`viz`,`docs`,`whitepapers`,`pdf`,`media`])r+=(i[e]||[]).length;let a=0;for(let o of[`teoria`,`scripts`,`test`,`viz`,`docs`,`whitepapers`,`pdf`,`media`]){let l=i[o]||[];for(let u of l){let l=`doc-`+i.id+`-`+u.path.replace(/[^a-zA-Z0-9_-]/g,`_`);e.push({id:l,label:u.name||u.filename,type:`doc`,docType:o,filePath:u.path,parentModId:s,depth:c+1,docIndex:a,totalDocs:r,r:6}),n[l]=!0,t.push({source:s,target:l}),a++}}}}for(let e of o)if(e.parent_id){let r=`topic-`+e.parent_id,i=`topic-`+e.id;n[r]&&n[i]&&t.push({source:r,target:i,type:`parent`})}let s=e.filter(e=>e.type===`topic`),c=s.length||1,l=(C.width||800)/2,u=(C.height||600)/2.5;s.forEach((e,t)=>{let n=t/c*(2*Math.PI)-Math.PI/2;e.angle=n;let r=Math.round(q*1.35);e.targetX=l+Math.cos(n)*r,e.targetY=u+Math.sin(n)*r,e.x??=e.targetX,e.y??=e.targetY});let d={};e.forEach(e=>{d[e.id]=e}),e.forEach(e=>{if(e.type===`module`&&e.parentTopicId){let t=d[e.parentTopicId],n=t?.angle??-Math.PI/2,r=e.totalChildTopics||1,i=e.childTopicIndex||0,a=Math.min(Math.PI*1.1,Math.max(Math.PI*.45,r*.5)),o=r>1?n-a/2+i/(r-1)*a:n;e.angle=o;let s=Math.round(q*(1+.12*(e.depth||1))),c=t?t.targetX??t.x:l,f=t?t.targetY??t.y:u;e.targetX=c+Math.cos(o)*s,e.targetY=f+Math.sin(o)*s,e.x??=e.targetX,e.y??=e.targetY}else if(e.type===`doc`&&e.parentModId){let t=d[e.parentModId],n=t?.angle??0,r=e.totalDocs||1,i=e.docIndex||0,a=Math.min(Math.PI*.9,Math.max(Math.PI*.35,r*.35)),o=r>1?n-a/2+i/(r-1)*a:n+.25;e.angle=o;let s=Math.round(q*.55),c=t?t.targetX??t.x:l,f=t?t.targetY??t.y:u;e.targetX=c+Math.cos(o)*s,e.targetY=f+Math.sin(o)*s,e.x??=e.targetX,e.y??=e.targetY}});try{let t=localStorage.getItem(`sigma_graph_custom_positions`);if(t){let n=JSON.parse(t);e.forEach(e=>{n[e.id]&&(e.fx=n[e.id].fx??n[e.id].x,e.fy=n[e.id].fy??n[e.id].y,e.x=n[e.id].x,e.y=n[e.id].y)})}}catch(e){console.error(`Error restoring graph positions:`,e)}return{nodes:e,links:t}},[o,E]);(0,_.useEffect)(()=>{if(!X||!i.current||o.length===0)return;let e=C.width,t=C.height;if(!e||!t||e<=0||t<=0)return;let n=X.select(i.current);n.selectAll(`*`).remove(),n.on(`click`,()=>{k(!1)});let{nodes:r,links:s}=rt();if(r.length===0)return;$e.current=s;let c=J===`costellazione`,l=J===`classico`,u=J===`crema`,d=n.append(`defs`);if(c){let r=d.append(`filter`).attr(`id`,`constellation-glow`).attr(`x`,`-50%`).attr(`y`,`-50%`).attr(`width`,`200%`).attr(`height`,`200%`);r.append(`feGaussianBlur`).attr(`stdDeviation`,`3.5`).attr(`result`,`coloredBlur`);let i=r.append(`feMerge`);i.append(`feMergeNode`).attr(`in`,`coloredBlur`),i.append(`feMergeNode`).attr(`in`,`SourceGraphic`);let a=d.append(`radialGradient`).attr(`id`,`constellation-star-topic`);a.append(`stop`).attr(`offset`,`0%`).attr(`stop-color`,`#ffffff`),a.append(`stop`).attr(`offset`,`35%`).attr(`stop-color`,`#d2a8ff`),a.append(`stop`).attr(`offset`,`75%`).attr(`stop-color`,`#8957e5`),a.append(`stop`).attr(`offset`,`100%`).attr(`stop-color`,`rgba(137, 87, 229, 0.3)`);let o=d.append(`radialGradient`).attr(`id`,`constellation-star-module`);o.append(`stop`).attr(`offset`,`0%`).attr(`stop-color`,`#ffffff`),o.append(`stop`).attr(`offset`,`35%`).attr(`stop-color`,`#7dd3fc`),o.append(`stop`).attr(`offset`,`75%`).attr(`stop-color`,`#0284c7`),o.append(`stop`).attr(`offset`,`100%`).attr(`stop-color`,`rgba(2, 132, 199, 0.3)`);let s=d.append(`radialGradient`).attr(`id`,`constellation-star-orange`);s.append(`stop`).attr(`offset`,`0%`).attr(`stop-color`,`#ffffff`),s.append(`stop`).attr(`offset`,`35%`).attr(`stop-color`,`#fbbf24`),s.append(`stop`).attr(`offset`,`75%`).attr(`stop-color`,`#d97706`),s.append(`stop`).attr(`offset`,`100%`).attr(`stop-color`,`rgba(217, 119, 6, 0.3)`);let c=d.append(`linearGradient`).attr(`id`,`constellation-link-grad`).attr(`x1`,`0%`).attr(`y1`,`0%`).attr(`x2`,`100%`).attr(`y2`,`100%`);c.append(`stop`).attr(`offset`,`0%`).attr(`stop-color`,`#bc8cff`).attr(`stop-opacity`,`0.75`),c.append(`stop`).attr(`offset`,`100%`).attr(`stop-color`,`#00d2ff`).attr(`stop-opacity`,`0.75`);let l=d.append(`linearGradient`).attr(`id`,`parent-link-grad`).attr(`x1`,`0%`).attr(`y1`,`0%`).attr(`x2`,`100%`).attr(`y2`,`100%`);l.append(`stop`).attr(`offset`,`0%`).attr(`stop-color`,`#fbbf24`).attr(`stop-opacity`,`0.85`),l.append(`stop`).attr(`offset`,`100%`).attr(`stop-color`,`#ec4899`).attr(`stop-opacity`,`0.85`);let u=n.append(`g`).attr(`class`,`background-starfield`);for(let n=0;n<100;n++){let r=(Math.sin(n*997+12)*.5+.5)*(e*1.8)-e*.4,i=(Math.cos(n*613+45)*.5+.5)*(t*1.8)-t*.4,a=n%5==0?2.4:n%3==0?1.8:1,o=.2+n%7*.1,s=2+n%5*1.2,c=n%9*.4;u.append(`circle`).attr(`cx`,r).attr(`cy`,i).attr(`r`,a).attr(`fill`,n%4==0?`#7dd3fc`:n%3==0?`#c084fc`:n%5==0?`#fde047`:`#ffffff`).attr(`opacity`,o).style(`animation`,`constellation-twinkle ${s}s ease-in-out ${c}s infinite alternate`)}}else l&&(d.selectAll(`marker`).data([`topic-module`,`parent-child`]).enter().append(`marker`).attr(`id`,e=>e).attr(`viewBox`,`0 -5 10 10`).attr(`refX`,22).attr(`refY`,0).attr(`markerWidth`,6).attr(`markerHeight`,6).attr(`orient`,`auto`).append(`path`).attr(`fill`,e=>e===`parent-child`?`rgba(210,153,34,0.5)`:`rgba(0,210,255,0.4)`).attr(`d`,`M0,-5L10,0L0,5`),d.append(`pattern`).attr(`id`,`tech-grid-pattern`).attr(`width`,36).attr(`height`,36).attr(`patternUnits`,`userSpaceOnUse`).append(`path`).attr(`d`,`M 36 0 L 0 0 0 36`).attr(`fill`,`none`).attr(`stroke`,`rgba(0, 210, 255, 0.06)`).attr(`stroke-width`,1),n.append(`rect`).attr(`width`,`100%`).attr(`height`,`100%`).attr(`fill`,`url(#tech-grid-pattern)`));let f=n.append(`g`).attr(`class`,`zoom-group`),h=X.zoom().scaleExtent([.05,5]).on(`zoom`,e=>{f.attr(`transform`,e.transform)});n.call(h),Qe.current=h;let _=Math.min(e,t)/1800,v=X.zoomIdentity.translate(e/2,t/2.5).scale(Math.max(.2,Math.min(.425,_)));n.call(h.transform,v);let b={};for(let e of o)if(e.parent_id){let t=`topic-`+e.parent_id+`|topic-`+e.id;b[t]=!0}let x=f.append(`g`).attr(`class`,`links`).selectAll(`line`).data(s).enter().append(`line`).attr(`class`,e=>b[e.source.id+`|`+e.target.id]||b[e.target.id+`|`+e.source.id]?`graph-link parent-link`:`graph-link`).attr(`stroke`,e=>{let t=b[e.source.id+`|`+e.target.id]||b[e.target.id+`|`+e.source.id];return c?t?`url(#parent-link-grad)`:`url(#constellation-link-grad)`:l?t?`#d29922`:`rgba(0, 210, 255, 0.4)`:u?t?`#c8963e`:`rgba(139, 107, 61, 0.45)`:t?`#bc8cff`:`rgba(255, 255, 255, 0.18)`}).attr(`stroke-width`,e=>{let t=b[e.source.id+`|`+e.target.id]||b[e.target.id+`|`+e.source.id];return c?t?2.6:1.8:l||u?t?2.2:1.6:1.4}).attr(`stroke-dasharray`,e=>b[e.source.id+`|`+e.target.id]||b[e.target.id+`|`+e.source.id]?c?`6,4`:`4,3`:`none`).attr(`marker-end`,e=>l?b[e.source.id+`|`+e.target.id]||b[e.target.id+`|`+e.source.id]?`url(#parent-child)`:`url(#topic-module)`:null).style(`filter`,c?`url(#constellation-glow)`:`none`),w=f.append(`g`).attr(`class`,`nodes`).selectAll(`g`).data(r).enter().append(`g`).attr(`class`,e=>`graph-node`+(p&&e.id===(p.type===`topic`?`topic-`+p.data.id:`mod-`+p.topicId+`-`+p.data.number)?` selected`:``)).on(`click`,(e,t)=>{if(e.stopPropagation(),t.type===`doc`?m({type:`doc`,data:t}):t.type===`topic`?(m({type:`topic`,data:t.data}),g(t.data.id),S(null)):(m({type:`module`,data:t.data,topicId:t.topicId}),g(t.topicId),S(t.data.number)),a.current){let t=a.current.getBoundingClientRect();de({x:e.clientX-t.left+15,y:e.clientY-t.top+15})}le(t),k(!0)}).on(`contextmenu`,(e,t)=>{if(e.preventDefault(),e.stopPropagation(),t.type===`doc`?m({type:`doc`,data:t}):t.type===`topic`?(m({type:`topic`,data:t.data}),g(t.data.id),S(null)):(m({type:`module`,data:t.data,topicId:t.topicId}),g(t.topicId),S(t.data.number)),a.current){let t=a.current.getBoundingClientRect();de({x:e.clientX-t.left+15,y:e.clientY-t.top+15})}le(t),k(!0)}).on(`mouseenter`,(e,t)=>{Y.current&&(x.attr(`class`,e=>{let n=typeof e.source==`object`?e.source.id:e.source,r=typeof e.target==`object`?e.target.id:e.target,i=b[n+`|`+r]||b[r+`|`+n]?`graph-link parent-link`:`graph-link`;return n===t.id||r===t.id?i+` highlight`:i}),w.attr(`opacity`,e=>{if(e.id===t.id)return 1;for(let n of s){let r=typeof n.source==`object`?n.source.id:n.source,i=typeof n.target==`object`?n.target.id:n.target;if(r===t.id&&i===e.id||i===t.id&&r===e.id)return 1}return .25}))}).on(`mouseleave`,()=>{x.attr(`class`,e=>{let t=typeof e.source==`object`?e.source.id:e.source,n=typeof e.target==`object`?e.target.id:e.target;return b[t+`|`+n]||b[n+`|`+t]?`graph-link parent-link`:`graph-link`}),w.attr(`opacity`,1)});c?(w.append(`circle`).attr(`class`,`constellation-orbit-ring`).attr(`r`,e=>e.r+(e.type===`topic`?12:e.type===`module`?8:4)).attr(`fill`,`none`).attr(`stroke`,e=>e.type===`topic`?`rgba(188,140,255,0.3)`:e.type===`module`?`rgba(0,210,255,0.25)`:`none`).attr(`stroke-width`,1).attr(`stroke-dasharray`,`3,3`),w.filter(e=>e.type!==`doc`).append(`path`).attr(`class`,`constellation-star-flare`).attr(`d`,e=>{let t=e.r+(e.type===`topic`?16:9);if(e.type===`topic`){let e=t*.42,n=t*.18;return`M 0,${-t} Q 0,0 ${n},${-n} L ${e},${-e} Q 0,0 ${t},0 Q 0,0 ${e},${e} L ${n},${n} Q 0,0 0,${t} Q 0,0 ${-n},${n} L ${-e},${e} Q 0,0 ${-t},0 Q 0,0 ${-e},${-e} L ${-n},${-n} Z`}return`M 0,${-t} Q 0,0 ${t},0 Q 0,0 0,${t} Q 0,0 ${-t},0 Q 0,0 0,${-t} Z`}).attr(`fill`,e=>p&&e.id===(p.type===`topic`?`topic-`+p.data.id:`mod-`+p.topicId+`-`+p.data.number)?`rgba(251, 191, 36, 0.75)`:e.type===`topic`?`rgba(188, 140, 255, 0.65)`:`rgba(0, 210, 255, 0.65)`).style(`filter`,`url(#constellation-glow)`),w.append(`circle`).attr(`class`,`constellation-star-core`).attr(`r`,e=>e.r).attr(`fill`,e=>e.type===`doc`?(y[e.docType]||y.docs).fill:p&&e.id===(p.type===`topic`?`topic-`+p.data.id:`mod-`+p.topicId+`-`+p.data.number)?`url(#constellation-star-orange)`:e.type===`topic`?`url(#constellation-star-topic)`:`url(#constellation-star-module)`).attr(`stroke`,e=>e.type===`doc`?(y[e.docType]||y.docs).stroke:p&&e.id===(p.type===`topic`?`topic-`+p.data.id:`mod-`+p.topicId+`-`+p.data.number)?`#fbbf24`:e.type===`topic`?`#bc8cff`:`#00d2ff`).attr(`stroke-width`,e=>e.type===`doc`?1.5:2.5).style(`filter`,`url(#constellation-glow)`),w.filter(e=>e.type!==`doc`).append(`circle`).attr(`class`,`constellation-center-dot`).attr(`r`,e=>e.type===`topic`?4:3).attr(`fill`,`#ffffff`)):w.append(`circle`).attr(`class`,`theme-node-circle`).attr(`r`,e=>e.r).attr(`fill`,e=>e.type===`doc`?(y[e.docType]||y.docs).fill:p&&e.id===(p.type===`topic`?`topic-`+p.data.id:`mod-`+p.topicId+`-`+p.data.number)?`rgba(210,153,34,0.25)`:l?e.type===`topic`?`rgba(188,140,255,0.18)`:`rgba(0,210,255,0.15)`:u?e.type===`topic`?`rgba(139,107,61,0.22)`:`rgba(200,150,62,0.18)`:e.type===`topic`?`#1e1633`:`#102233`).attr(`stroke`,e=>e.type===`doc`?(y[e.docType]||y.docs).stroke:p&&e.id===(p.type===`topic`?`topic-`+p.data.id:`mod-`+p.topicId+`-`+p.data.number)?`#d29922`:u?e.type===`topic`?`#8b6b3d`:`#c8963e`:e.type===`topic`?`#bc8cff`:`#00d2ff`).attr(`stroke-width`,e=>e.type===`doc`?1.5:l?2.5:2).style(`filter`,l?e=>e.type===`topic`?`drop-shadow(0 0 6px rgba(188,140,255,0.4))`:`drop-shadow(0 0 6px rgba(0,210,255,0.3))`:u?e=>e.type===`topic`?`drop-shadow(0 0 6px rgba(139,107,61,0.3))`:`drop-shadow(0 0 6px rgba(200,150,62,0.25))`:`none`),w.append(`text`).attr(`class`,e=>`node-label `+e.type).attr(`text-anchor`,e=>{let t=Math.cos(e.angle||0);return t>.25?`start`:t<-.25?`end`:`middle`}).attr(`dx`,e=>{let t=Math.cos(e.angle||0);return t>.25?e.r+8:t<-.25?-(e.r+8):0}).attr(`dy`,e=>{let t=Math.cos(e.angle||0),n=Math.sin(e.angle||0);return Math.abs(t)>.25?4:n<-.25?-(e.r+8):e.r+Math.round(e.type===`topic`?K*1.1:K*.95)+2}).attr(`fill`,u?`#4a3b25`:`#e2e4eb`).attr(`font-size`,e=>e.type===`topic`?Math.round(K*1.15)+`px`:e.type===`module`?K+`px`:Math.max(10,Math.round(K*.85))+`px`).attr(`font-weight`,e=>e.type===`topic`?`700`:`600`).attr(`pointer-events`,`none`).attr(`stroke`,u?`#faf6ec`:`#050612`).attr(`stroke-width`,`3.5px`).attr(`stroke-linejoin`,`round`).style(`paint-order`,`stroke fill`).style(`text-shadow`,e=>c?e.type===`topic`?`0 0 10px rgba(188,140,255,0.8)`:`0 0 8px rgba(0,210,255,0.7)`:`none`).text(e=>e.label.length>40?e.label.slice(0,38)+`…`:e.label);let T=X.forceSimulation(r).force(`link`,X.forceLink(s).id(e=>e.id).distance(e=>e.type===`doc`?Math.round(q*.55):Math.round(q*1.15)).strength(.35)).force(`charge`,X.forceManyBody().strength(e=>e.type===`topic`?-1800:e.type===`module`?-1e3:-250)).force(`center`,X.forceCenter(e/2,t/2.5).strength(.02)).force(`collision`,X.forceCollide().radius(e=>{let t=(e.label||``).length,n=Math.min(180,K*.32*t);return e.type===`topic`?Math.max(e.r+65,n+25):e.type===`module`?Math.max(e.r+45,n+15):e.r+20}).strength(.9)).on(`tick`,()=>{r.forEach(e=>{if(e.fx!=null&&e.fy!=null){e.x=e.fx,e.y=e.fy;return}e.targetX!=null&&e.targetY!=null&&(e.x+=(e.targetX-e.x)*.12,e.y+=(e.targetY-e.y)*.12)}),x.attr(`x1`,e=>e.source.x).attr(`y1`,e=>e.source.y).attr(`x2`,e=>e.target.x).attr(`y2`,e=>e.target.y),w.attr(`transform`,e=>`translate(${e.x},${e.y})`)}),ee=(e,t)=>{let n=[],r=[e.id],i=new Set([e.id]);for(;r.length>0;){let e=r.shift();t.forEach(t=>{i.has(t.id)||(t.parentTopicId===e||t.parentModId===e)&&(i.add(t.id),n.push(t),r.push(t.id))})}return n},E=0,te=0,D=[],ne=(e,t)=>{try{let n=null;try{n=localStorage.getItem(`sigma_graph_custom_positions`)}catch{}let r=n?JSON.parse(n):{},i=e=>e==null?null:Math.round(e*10)/10;r[e.id]={x:i(e.x),y:i(e.y),fx:i(e.fx??e.x),fy:i(e.fy??e.y)},t.forEach(e=>{e.fx=e.x,e.fy=e.y,r[e.id]={x:i(e.x),y:i(e.y),fx:i(e.fx),fy:i(e.fy)}});let a=JSON.stringify(r);try{localStorage.setItem(`sigma_graph_custom_positions`,a)}catch(n){if(n.name===`QuotaExceededError`||n.code===22||n.code===1014){let n={};n[e.id]=r[e.id],t.forEach(e=>{n[e.id]=r[e.id]});try{localStorage.setItem(`sigma_graph_custom_positions`,JSON.stringify(n))}catch{}}}}catch{}},re=X.drag().on(`start`,(e,t)=>{e.active||T.alphaTarget(.3).restart(),t.fx=t.x,t.fy=t.y,E=e.x,te=e.y,D=ee(t,r)}).on(`drag`,(e,t)=>{let n=e.x-E,r=e.y-te;E=e.x,te=e.y,t.fx=e.x,t.fy=e.y,D.forEach(e=>{e.targetX!=null&&(e.targetX+=n),e.targetY!=null&&(e.targetY+=r),e.x+=n,e.y+=r,e.fx!=null&&(e.fx+=n),e.fy!=null&&(e.fy+=r)})}).on(`end`,(e,t)=>{e.active||T.alphaTarget(0),ne(t,D)});w.call(re),Y.current=T;let O=o.find(e=>!e.parent_id)||o[0];return O&&(p||(m({type:`topic`,data:O}),g(O.id)),setTimeout(()=>{it(O.id,.82)},250)),()=>{T.stop()}},[X,o,C,rt,q,J]),(0,_.useEffect)(()=>{if(!X||!i.current||o.length===0)return;let e=X.select(i.current);e.selectAll(`.graph-node .constellation-star-core`).attr(`fill`,e=>e.type===`doc`?(y[e.docType]||y.docs).fill:p&&e.id===(p.type===`topic`?`topic-`+p.data.id:`mod-`+p.topicId+`-`+p.data.number)?`url(#constellation-star-orange)`:e.type===`topic`?`url(#constellation-star-topic)`:`url(#constellation-star-module)`).attr(`stroke`,e=>e.type===`doc`?(y[e.docType]||y.docs).stroke:p&&e.id===(p.type===`topic`?`topic-`+p.data.id:`mod-`+p.topicId+`-`+p.data.number)?`#fbbf24`:e.type===`topic`?`#bc8cff`:`#00d2ff`),e.selectAll(`.graph-node .constellation-star-flare`).attr(`fill`,e=>p&&e.id===(p.type===`topic`?`topic-`+p.data.id:`mod-`+p.topicId+`-`+p.data.number)?`rgba(251, 191, 36, 0.85)`:e.type===`topic`?`rgba(188, 140, 255, 0.65)`:`rgba(0, 210, 255, 0.65)`),e.selectAll(`.graph-node`).attr(`class`,e=>`graph-node`+(p&&e.id===(p.type===`topic`?`topic-`+p.data.id:`mod-`+p.topicId+`-`+p.data.number)?` selected`:``))},[X,p,o]),(0,_.useEffect)(()=>{X&&i.current&&X.select(i.current).selectAll(`.node-label`).attr(`font-size`,e=>e?e.type===`topic`?Math.round(K*1.15)+`px`:e.type===`module`?K+`px`:Math.max(10,Math.round(K*.85))+`px`:K+`px`)},[X,K]);let it=(0,_.useCallback)((e,t=null)=>{if(!Y.current||!i.current||!Qe.current||!window.d3)return;let n=window.d3,r=Y.current.nodes().find(t=>t.id===e||t.id===`topic-`+e||t.topicId===e);if(r&&r.x!=null&&r.y!=null){let e=C.width||800,a=C.height||600,o=n.zoomTransform(i.current),s=t||o.k||.82,c=n.zoomIdentity.translate(e/2-r.x*s,a/2.5-r.y*s).scale(s);n.select(i.current).transition().duration(700).ease(n.easeCubicInOut).call(Qe.current.transform,c)}},[C]),Q=e=>e?String(e).replace(/&/g,`&`).replace(/</g,`<`).replace(/>/g,`>`).replace(/"/g,`"`):``,at=async e=>{let t=null,n=`Argomento`;typeof e==`string`?t=e:e&&(t=e.id||(e.folder?e.folder.replace(/^data\//,``):null),n=e.name||e.label||t||`Argomento`,!t&&e.number&&e.name&&(t=e.folder?e.folder.replace(/^data\//,``):`${e.topicId||h}/${e.number}_${e.name}`.toLowerCase().replace(/ /g,`_`)));let r=prompt(`Nome del nuovo sottoargomento (cartella) dentro "${n}":`);if(!r||!r.trim())return;let i=r.trim().toLowerCase().replace(/[^a-z0-9_]+/g,`_`).replace(/^_+|_+$/g,``);if(i)try{let e=await(await fetch(`/api/create_topic`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({id:i,parent_id:t,name:r.trim(),description:`Sottoargomento di ${n}`})})).json();e.success?(window.dispatchEvent(new CustomEvent(`sigma_toast`,{detail:{message:`✨ Sottoargomento "${r}" creato in costellazione!`,type:`success`,duration:4e3}})),await Z()):alert(`Errore creazione sottoargomento: `+(e.error||`sconosciuto`))}catch(e){alert(`Errore di rete: `+e.message)}},ot=(e,t)=>{let n=new Set([e]),r=[e];for(;r.length>0;){let e=r.shift(),i=t.filter(t=>t.parent_id===e);for(let e of i)n.has(e.id)||(n.add(e.id),r.push(e.id))}return n},st=e=>{if(!e)return[];let t=ot(e.id,o);return o.filter(e=>!t.has(e.id))},ct=e=>{let t=e&&e.id?e:o.find(t=>t.id===e.id||t.name===e.name)||e;if(!t)return;let n=Y.current?.nodes().find(e=>e.data?.id===t.id||e.id===`topic-`+t.id);n&&a.current?(de({x:Math.min((n.x||300)+15,(C.width||800)-320),y:Math.max((n.y||200)-20,20)}),le(n)):(le({type:t.parent_id?`module`:`topic`,data:t,label:t.name}),de({x:200,y:150})),Fe(t.parent_id||``),Ne(`move`),k(!0),B(``),it(t.id)},lt=async()=>{let e=prompt(`Nome del nuovo argomento:`,`nuovo_argomento`);if(!e)return;let t=e.toLowerCase().replace(/ /g,`_`).replace(/[^a-z0-9_]/g,``),n=prompt(`Dominio (matematica, fisica, informatica...):`,`matematica`)||`generale`,r=prompt(`Descrizione:`,``)||``;try{let i=await(await fetch(`/api/create_topic`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({id:t,name:e,description:r,domain:n})})).json();if(i.success){let e=await Z();if(e){let n=e.find(e=>e.id===t);n&&(g(t),m({type:`topic`,data:n}),S(null))}}else alert(`Errore: `+(i.error||`sconosciuto`))}catch(e){alert(`Errore di rete: `+e.message)}},ut=async(e,t)=>{try{let n=await(await fetch(`/api/update_topic`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({topic_id:e.id,parent_id:t||null})})).json();n.success?(await Z(),m({type:`topic`,data:{...e,parent_id:t||null}})):alert(`Errore: `+(n.error||`sconosciuto`))}catch(e){alert(`Errore di rete: `+e.message)}},dt=async(e,t)=>{if(!confirm(`Eliminare definitivamente il sottoargomento "${e.name}" e tutti i suoi file?`))return;let n=o.find(e=>e.id===t);if(n)try{let t=await(await fetch(`/api/delete_module`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({folder:e.folder||`${n.folder}/${e.number}_${e.name}`.toLowerCase().replace(/ /g,`_`)})})).json();t.success?await Z()&&(m(null),S(null)):alert(`Errore: `+(t.error||`sconosciuto`))}catch(e){alert(`Errore di rete: `+e.message)}},ft=async e=>{if(confirm(`Eliminare definitivamente l'argomento "${e.name}" e tutti i suoi sottoargomenti e file?`))try{let t=await(await fetch(`/api/delete_topic`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({topic_id:e.id})})).json();if(t.success){let e=await Z();e&&(m(null),g(e.length>0?e[0].id:null),S(null))}else alert(`Errore: `+(t.error||`sconosciuto`))}catch(e){alert(`Errore di rete: `+e.message)}},pt=async(e,t)=>{let n=prompt(`Nuovo nome per il sottoargomento:`,e.name);if(!n||n===e.name)return;let r=o.find(e=>e.id===t);if(r)try{let i=await(await fetch(`/api/update_module`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({old_folder:e.folder||`${r.folder}/${e.number}_${e.name}`.toLowerCase().replace(/ /g,`_`),number:e.number,name:n,description:e.description||``})})).json();if(i.success){let n=await Z();if(n){let r=n.find(e=>e.id===t);if(r){let n=r.modules?.find(t=>t.number===e.number);n&&(m({type:`module`,data:n,topicId:t}),S(n.number))}}}else alert(`Errore: `+(i.error||`sconosciuto`))}catch(e){alert(`Errore di rete: `+e.message)}},mt=async e=>{if(confirm(`Eliminare definitivamente il file "${e.split(`/`).pop()}"?`))try{let t=await(await fetch(`/api/delete_file`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({path:e})})).json();t.success?await Z():alert(`Errore: `+(t.error||`sconosciuto`))}catch(e){alert(`Errore di rete: `+e.message)}},ht=async t=>{if(t&&t.preventDefault(),!ye.trim()){B(`Inserisci le istruzioni di modifica`);return}N(!0),B(``);try{let t=await(await fetch(`/api/ai/action`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({action:`edit_file`,path:A.filePath,model:I,role:L,prompt:ye,existing_content:Te})})).json();t.success?(R(``),k(!1),await Z(),e&&e(A.filePath)):B(t.error||`Errore modifica AI`)}catch(e){B(`Errore di rete: `+e.message)}finally{N(!1)}},gt=async t=>{if(t&&t.preventDefault(),!V){B(`Seleziona un argomento di destinazione`);return}N(!0),B(``);try{let t=o.find(e=>e.id===V);if(!t){B(`Argomento di destinazione non trovato`),N(!1);return}let n=t.folder;if(xe){let e=t.modules?.find(e=>e.number===Number(xe));e&&(n=e.folder||`${t.folder}/${e.number}_${e.name}`.toLowerCase().replace(/ /g,`_`))}let r={whitepaper:`whitepapers`,teoria:`teoria`,docs:`docs`,test:`test`,viz:`viz`,whitepapers:`whitepapers`}[Ce]||Ce,i=A.label,a=`${n}/${r}/${i}`,s=await(await fetch(`/api/rename_file`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({old_path:A.filePath,new_path:a})})).json();s.success?(k(!1),await Z(),e&&e(a)):B(s.error||`Errore spostamento file`)}catch(e){B(`Errore di rete: `+e.message)}finally{N(!1)}},_t=async e=>{if(e&&e.preventDefault(),window.confirm(`Sei sicuro di voler eliminare definitivamente il file: ${A.label}?`)){N(!0),B(``);try{let e=await(await fetch(`/api/delete_file`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({path:A.filePath})})).json();e.success?(k(!1),await Z()):B(e.error||`Errore eliminazione file`)}catch(e){B(`Errore di rete: `+e.message)}finally{N(!1)}}},vt=async t=>{t&&t.preventDefault();let n=A.data?.folder||(A.data?.id?`data/${A.data.id}`:``);if(!n){B(`Cartella di destinazione non trovata`);return}let r={whitepaper:`whitepapers`,teoria:`teoria`,docs:`docs`,test:`test`,viz:`viz`},i={whitepaper:`.md`,teoria:`.md`,test:`.py`,viz:`.html`,docs:`.md`},a=r[F]||F,o=i[F]||`.md`,s=pe.trim();if(W===`upload`){if(!G){B(`Seleziona o trascina un file prima di caricarlo`);return}if(!s){B(`Inserisci un nome file`);return}N(!0),B(``);try{let t=G.name,r=t.lastIndexOf(`.`),i=r===-1?``:t.substring(r),o=s;o.toLowerCase().endsWith(i.toLowerCase())||(o+=i),F===`whitepaper`&&!o.toUpperCase().startsWith(`WHITEPAPER_`)&&(o=`WHITEPAPER_`+o);let c=`${n}/${a}/${o}`,l=new FormData;l.append(`file`,G,o),l.append(`folder`,n),l.append(`type`,F);let u=await(await fetch(`/api/upload_file`,{method:`POST`,body:l})).json();u.success?(P(``),Oe(null),k(!1),await Z(),e&&e(c)):B(u.error||`Errore durante il caricamento`)}catch(e){B(`Errore di rete: `+e.message)}finally{N(!1)}return}if(!s){B(`Inserisci un nome file`);return}F===`whitepaper`&&!s.toUpperCase().startsWith(`WHITEPAPER_`)&&(s=`WHITEPAPER_`+s);let c=`${n}/${a}/${s}${o}`;if(he){let t=`${s}${o}`,n=L||b[F]||`code_architect`,r=`ai-gen-${Date.now()}`;P(``),R(``),k(!1),window.dispatchEvent(new CustomEvent(`sigma_toast`,{detail:{id:r,message:`⏳ Generazione AI in corso per "${t}"...`,type:`loop`,duration:0}})),(async()=>{try{let i=await(await fetch(`/api/ai/action`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({action:`create_file`,path:c,model:I,role:n,prompt:ye})})).json();window.dispatchEvent(new CustomEvent(`sigma_toast`,{detail:{id:r,action:`close`}})),i.success?(window.dispatchEvent(new CustomEvent(`sigma_toast`,{detail:{message:`✅ File "${t}" generato con successo!`,type:`success`,duration:7e3}})),await Z(),window.dispatchEvent(new Event(`sigma_topics_updated`)),e&&e(c)):window.dispatchEvent(new CustomEvent(`sigma_toast`,{detail:{message:`❌ Errore generazione AI per "${t}": ${i.error||`Errore sconosciuto`}`,type:`error`,duration:8e3}}))}catch(e){window.dispatchEvent(new CustomEvent(`sigma_toast`,{detail:{id:r,action:`close`}})),window.dispatchEvent(new CustomEvent(`sigma_toast`,{detail:{message:`❌ Errore di rete durante la generazione: ${e.message}`,type:`error`,duration:8e3}}))}finally{N(!1)}})();return}N(!0),B(``);try{let t=F===`scripts`||F===`test`?`# ${s}\n# Script per Sigma\n\ndef run():\n    print('Running ${s}...')\n\nif __name__ == '__main__':\n    run()\n`:`# ${s}\n\nContenuto del file ${F}.\n`,n=await(await fetch(`/api/create_file`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({path:c,content:t})})).json();n.success?(P(``),R(``),k(!1),await Z(),window.dispatchEvent(new Event(`sigma_topics_updated`)),e&&e(c)):B(n.error||`Errore sconosciuto`)}catch(e){B(`Errore di rete: `+e.message)}finally{N(!1)}},yt=async(t,n)=>{let r={whitepaper:`whitepapers`,teoria:`teoria`,docs:`docs`,test:`test`,viz:`viz`},i={whitepaper:`.md`,teoria:`.md`,test:`.py`,viz:`.html`,docs:`.md`},a=r[n]||n,o=i[n]||`.md`,s=prompt(`Nome del nuovo file ${n} (senza estensione):`,`nuovo_${n}`);if(!s)return;let c=`${t}/${a}/${s}${o}`,l=n===`test`?`# ${s}\n# Test script for Sigma\n\ndef run():\n    print('Running ${s}...')\n\nif __name__ == '__main__':\n    run()\n`:`# ${s}\n\nContenuto del file ${n}.\n`;try{let t=await(await fetch(`/api/create_file`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({path:c,content:l})})).json();t.success?(await Z(),e&&e(c)):alert(`Errore: `+(t.error||`sconosciuto`))}catch(e){alert(`Errore di rete: `+e.message)}};(0,_.useEffect)(()=>{o.length>0&&!h&&g(o[0].id)},[o,h]);let $=o.find(e=>e.id===h),bt=e=>{let t={whitepapers:[],docs:[],teoria:[],test:[],viz:[]};if(!e||!e.modules)return t;for(let n of e.modules)n.whitepapers&&n.whitepapers.forEach(e=>t.whitepapers.push({...e,modNum:n.number,modName:n.name})),n.docs&&n.docs.forEach(e=>t.docs.push({...e,modNum:n.number,modName:n.name})),n.teoria&&n.teoria.forEach(e=>t.teoria.push({...e,modNum:n.number,modName:n.name})),n.test&&n.test.forEach(e=>t.test.push({...e,modNum:n.number,modName:n.name})),n.viz&&n.viz.forEach(e=>t.viz.push({...e,modNum:n.number,modName:n.name}));return t},xt={matematica:`∑`,fisica:`Φ`,informatica:`⚙`,mathematics:`∑`,physics:`Φ`,cs:`⚙`},St=e=>xt[e]||`🔬`,Ct=e=>{g(e.id),S(null),m({type:e.parent_id?`module`:`topic`,data:e}),it(e.id)},wt=[{key:`teoria`,icon:`📄`,label:`Docs`,color:`#bc8cff`,borderColor:`rgba(188,140,255,0.2)`},{key:`docs`,icon:`📄`,label:`Docs`,color:`#58a6ff`,borderColor:`rgba(88,166,255,0.2)`},{key:`scripts`,icon:`⚡`,label:`Scripts`,color:`#00d2ff`,borderColor:`rgba(0,210,255,0.2)`},{key:`whitepapers`,icon:`📜`,label:`Whitepapers`,color:`#ffd700`,borderColor:`#ffd700`},{key:`test`,icon:`🧪`,label:`Test`,color:`#3fb950`,borderColor:`rgba(63,185,80,0.2)`},{key:`viz`,icon:`📊`,label:`Visualizzazioni`,color:`#d29922`,borderColor:`rgba(210,153,34,0.2)`},{key:`pdf`,icon:`📜`,label:`PDF`,color:`#ff7b72`,borderColor:`rgba(255,123,114,0.2)`},{key:`media`,icon:`🎥`,label:`Media`,color:`#d2a8ff`,borderColor:`rgba(210,168,255,0.2)`}];if(d)return(0,v.jsxs)(`div`,{className:`mappa-error`,children:[(0,v.jsx)(`div`,{className:`error-icon`,children:`⚠️`}),(0,v.jsxs)(`div`,{className:`error-msg`,children:[`Errore di caricamento: `,Q(d),(0,v.jsx)(`br`,{}),`Assicurati che Sigma Server sia in esecuzione.`]}),(0,v.jsx)(`button`,{className:`retry-btn`,onClick:Z,children:`⟳ Riprova`})]});if(o.length===0&&!c)return(0,v.jsx)(`div`,{className:`mappa-loading`,style:{gap:0,height:`100%`,display:`flex`,alignItems:`center`,justifyContent:`center`},children:(0,v.jsxs)(`div`,{style:{background:`linear-gradient(135deg, rgba(188,140,255,0.04) 0%, rgba(0,210,255,0.04) 100%)`,border:`1px solid rgba(188,140,255,0.12)`,borderRadius:`16px`,padding:`48px 32px`,maxWidth:`520px`,width:`100%`,display:`flex`,flexDirection:`column`,alignItems:`center`,gap:`20px`,backdropFilter:`blur(4px)`,boxShadow:`0 0 60px rgba(188,140,255,0.03), inset 0 1px 0 rgba(255,255,255,0.02)`,margin:`auto`},children:[(0,v.jsx)(`div`,{style:{width:`72px`,height:`72px`,borderRadius:`20px`,background:`linear-gradient(135deg, rgba(188,140,255,0.15) 0%, rgba(0,210,255,0.1) 100%)`,border:`1px solid rgba(188,140,255,0.2)`,display:`flex`,alignItems:`center`,justifyContent:`center`,fontSize:`1.8rem`,boxShadow:`0 8px 32px rgba(188,140,255,0.08)`},children:`🧬`}),(0,v.jsxs)(`div`,{style:{textAlign:`center`},children:[(0,v.jsx)(`h2`,{style:{margin:0,fontSize:`1.15rem`,fontWeight:700,color:`#e2e4eb`,letterSpacing:`-0.02em`,lineHeight:1.3},children:`Inizia la tua ricerca`}),(0,v.jsx)(`p`,{style:{margin:`8px 0 0 0`,fontSize:`0.78rem`,color:`#5a5e72`,lineHeight:1.6,maxWidth:`380px`},children:`Crea il tuo primo argomento per organizzare moduli, teoria, test e visualizzazioni in una mappa interattiva.`})]}),(0,v.jsxs)(`button`,{onClick:lt,style:{padding:`12px 28px`,background:`linear-gradient(135deg, #bc8cff 0%, #9b6fff 100%)`,border:`none`,borderRadius:`10px`,color:`#0e1016`,cursor:`pointer`,fontWeight:700,fontSize:`0.8rem`,fontFamily:`inherit`,letterSpacing:`0.01em`,boxShadow:`0 4px 24px rgba(188,140,255,0.25)`,transition:`all 0.2s ease`,display:`flex`,alignItems:`center`,gap:`8px`},onMouseEnter:e=>{e.currentTarget.style.transform=`translateY(-2px)`,e.currentTarget.style.boxShadow=`0 8px 32px rgba(188,140,255,0.35)`},onMouseLeave:e=>{e.currentTarget.style.transform=`translateY(0)`,e.currentTarget.style.boxShadow=`0 4px 24px rgba(188,140,255,0.25)`},children:[(0,v.jsx)(`span`,{style:{fontSize:`1rem`},children:`+`}),`Crea il primo argomento`]}),(0,v.jsxs)(`div`,{style:{fontSize:`0.65rem`,color:`#3d4050`,textAlign:`center`,lineHeight:1.5},children:[`Ogni argomento contiene moduli con `,(0,v.jsx)(`span`,{style:{color:`#bc8cff`},children:`teoria`}),`, `,(0,v.jsx)(`span`,{style:{color:`#3fb950`},children:`test`}),` e `,(0,v.jsx)(`span`,{style:{color:`#d29922`},children:`visualizzazioni`})]})]})});$&&bt($);let Tt=o.filter(e=>!e.parent_id),Et=Tt.filter(e=>(e.name||``).toLowerCase().includes(D.toLowerCase())||(e.domain||``).toLowerCase().includes(D.toLowerCase())),Dt=$?o.filter(e=>e.parent_id===$.id&&(!D||(e.name||``).toLowerCase().includes(D.toLowerCase()))):[];return(0,v.jsxs)(`div`,{className:`mappa-argomenti${n?` theme-light`:``}`,children:[c&&(0,v.jsxs)(`div`,{className:`mappa-loading-overlay`,style:{position:`absolute`,inset:0,background:`rgba(14, 16, 22, 0.8)`,backdropFilter:`blur(4px)`,display:`flex`,flexDirection:`column`,alignItems:`center`,justifyContent:`center`,gap:`12px`,zIndex:1e3},children:[(0,v.jsx)(`div`,{className:`spinner`}),(0,v.jsx)(`div`,{className:`label`,style:{color:`#8b8fa3`,fontSize:`0.75rem`},children:`Caricamento bacheca…`})]}),(0,v.jsx)(`style`,{children:`
        @keyframes constellation-twinkle {
          0%, 100% { opacity: 0.2; transform: scale(0.85); }
          50% { opacity: 0.95; transform: scale(1.25); }
        }
        @keyframes constellation-orbit-spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        .mappa-argomenti {
          position: relative;
          display: flex;
          flex-direction: column;
          height: 100%;
          background: radial-gradient(ellipse at 50% 30%, #10132b 0%, #080918 60%, #03040b 100%);
          color: #e2e4eb;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          font-size: 15px;
          overflow: hidden;
        }
        /* === TEMA LIGHT OVERRIDES (palette Manifesti crema/bianco) === */
        .mappa-argomenti.theme-light {
          background: radial-gradient(ellipse at 50% 30%, #f7f4ed 0%, #f2ede2 60%, #e8e0d0 100%);
          color: #111111;
        }
        .mappa-argomenti.theme-light ::-webkit-scrollbar-thumb { background: rgba(190, 160, 110, 0.35); }
        .mappa-argomenti.theme-light ::-webkit-scrollbar-thumb:hover { background: rgba(234, 88, 12, 0.4); }
        .mappa-argomenti.theme-light .mappa-header-bar {
          background: linear-gradient(135deg, rgba(255, 253, 249, 0.97) 0%, rgba(247, 244, 237, 0.94) 100%) !important;
          border-color: rgba(190, 160, 110, 0.35) !important;
          box-shadow: 0 4px 20px rgba(190, 160, 110, 0.12) !important;
        }
        .mappa-argomenti.theme-light .mappa-header-bar button {
          background: rgba(255, 253, 249, 0.9);
          border-color: rgba(190, 160, 110, 0.35);
          color: #111111;
        }
        .mappa-argomenti.theme-light .mappa-detail-panel {
          background: #fffdf9 !important;
          border-left-color: rgba(190, 160, 110, 0.35) !important;
        }
        .mappa-argomenti.theme-light .mappa-header-bar .theme-control,
        .mappa-argomenti.theme-light .mappa-header-bar .font-size-control,
        .mappa-argomenti.theme-light .mappa-header-bar .branch-length-control {
          background: #fffdf9 !important;
          border-color: rgba(190, 160, 110, 0.35) !important;
          color: #2e2820 !important;
          box-shadow: 0 2px 8px rgba(190, 160, 110, 0.15) !important;
        }
        .mappa-argomenti.theme-light .mappa-header-bar .font-size-control span,
        .mappa-argomenti.theme-light .mappa-header-bar .branch-length-control span {
          color: #d97706;
        }
        .mappa-argomenti.theme-light .mappa-header-bar .font-size-control input,
        .mappa-argomenti.theme-light .mappa-header-bar .branch-length-control input {
          accent-color: #ea580c;
        }
        .mappa-argomenti.theme-light .mappa-header-bar .btn-explore,
        .mappa-argomenti.theme-light .mappa-header-bar .btn-explore.active { color: #3fb950; }
        .mappa-argomenti.theme-light .mappa-header-bar .btn-update { color: #d97706; }
        .mappa-argomenti.theme-light .mappa-header-bar .btn-new-topic { color: #111111; background: rgba(190, 160, 110, 0.14); border-color: rgba(190, 160, 110, 0.35); }
        .mappa-argomenti.theme-light .module-filter-bar,
        .mappa-argomenti.theme-light .topic-tab-bar {
          background: #f7f4ed !important;
          border-bottom-color: rgba(190, 160, 110, 0.35) !important;
        }
        .mappa-argomenti.theme-light .mfb-label { color: #2e2820; }
        .mappa-argomenti.theme-light .mfb-btn,
        .mappa-argomenti.theme-light .topic-tab { color: #2e2820; }
        .mappa-argomenti.theme-light .mfb-btn:hover,
        .mappa-argomenti.theme-light .topic-tab:hover { color: #111111; background: #f2ede2; border-color: rgba(190, 160, 110, 0.35); }
        .mappa-argomenti.theme-light .mfb-btn.active { color: #d97706; border-color: rgba(190, 160, 110, 0.5); background: rgba(190, 160, 110, 0.14); }
        .mappa-argomenti.theme-light .topic-tab.active { color: #111111; border-bottom-color: #d97706; background: rgba(190, 160, 110, 0.14); }
        .mappa-argomenti.theme-light .topic-tab .tab-count { background: rgba(190, 160, 110, 0.14); color: #2e2820; }
        .mappa-argomenti.theme-light .topic-tab.active .tab-count { background: rgba(190, 160, 110, 0.28); color: #111111; }
        .mappa-argomenti.theme-light .file-columns-area { border-top-color: rgba(190, 160, 110, 0.35); }
        .mappa-argomenti.theme-light .file-column {
          background: #fffdf9 !important;
          border-color: rgba(190, 160, 110, 0.35) !important;
        }
        .mappa-argomenti.theme-light .file-column-header {
          border-bottom-color: rgba(190, 160, 110, 0.35);
          color: #111111;
        }
        .mappa-argomenti.theme-light .file-column .empty-col-hint { color: #2e2820; }
        .mappa-argomenti.theme-light .col-file-item .col-file-name { color: #2e2820; }
        .mappa-argomenti.theme-light .col-file-item .col-file-name:hover { color: #111111; }
        .mappa-argomenti.theme-light .col-file-item:hover { background: #f2ede2; }
        .mappa-argomenti.theme-light .col-file-item .col-mod-badge { background: rgba(190, 160, 110, 0.14); color: #2e2820; }
        .mappa-argomenti.theme-light .sidebar-search-box {
          background: #fffdf9;
          border-color: rgba(190, 160, 110, 0.35);
        }
        .mappa-argomenti.theme-light .sidebar-search-box .search-icon { color: #2e2820; }
        .mappa-argomenti.theme-light .sidebar-search-input { color: #111111; }
        .mappa-argomenti.theme-light .sidebar-search-input::placeholder { color: #2e2820; }
        .mappa-argomenti.theme-light .explorer-section { border-bottom-color: rgba(190, 160, 110, 0.35); }
        .mappa-argomenti.theme-light .explorer-section-header { color: #2e2820; }
        .mappa-argomenti.theme-light .explorer-section-header:hover { color: #111111; }
        .mappa-argomenti.theme-light .explorer-topic-item { color: #2e2820; }
        .mappa-argomenti.theme-light .explorer-topic-item:hover { background: #f2ede2; color: #111111; }
        .mappa-argomenti.theme-light .explorer-topic-item.active { background: rgba(190, 160, 110, 0.14); color: #111111; border-left-color: #d97706; }
        .mappa-argomenti.theme-light .explorer-topic-icon { background: rgba(190, 160, 110, 0.14); }
        .mappa-argomenti.theme-light .explorer-topic-count { background: rgba(190, 160, 110, 0.14); color: #2e2820; }
        .mappa-argomenti.theme-light .explorer-topic-item.active .explorer-topic-count { color: #111111; background: rgba(190, 160, 110, 0.28); }
        .mappa-argomenti.theme-light .folder-header { color: #2e2820; }
        .mappa-argomenti.theme-light .folder-header:hover { background: #f2ede2; color: #111111; }
        .mappa-argomenti.theme-light .folder-header-count { color: #2e2820; }
        .mappa-argomenti.theme-light .category-folder-header { color: #2e2820; }
        .mappa-argomenti.theme-light .category-folder-header:hover { background: #f2ede2; color: #111111; }
        .mappa-argomenti.theme-light .file-tree-item { color: #2e2820; }
        .mappa-argomenti.theme-light .file-tree-item:hover { background: #f2ede2; color: #111111; }
        .mappa-argomenti.theme-light .detail-type { color: #2e2820 !important; }
        .mappa-argomenti.theme-light .detail-desc { color: #2e2820; }
        .mappa-argomenti.theme-light .detail-meta .tag { background: rgba(190, 160, 110, 0.14); color: #2e2820; }
        .mappa-argomenti.theme-light .detail-meta .tag.modules-tag { color: #d97706; background: rgba(190, 160, 110, 0.14); }
        .mappa-argomenti.theme-light .detail-rel-label { color: #2e2820; }
        .mappa-argomenti.theme-light .detail-rel-value { color: #2e2820; }
        .mappa-argomenti.theme-light .detail-rel-tag { background: rgba(190, 160, 110, 0.14); border: 1px solid rgba(190, 160, 110, 0.28); color: #111111; }
        .mappa-argomenti.theme-light .detail-files h4 { color: #2e2820; border-bottom-color: rgba(190, 160, 110, 0.35); }
        .mappa-argomenti.theme-light .detail-file-item .fname { color: #2e2820; }
        .mappa-argomenti.theme-light .detail-file-item .fname:hover { color: #111111; }
        .mappa-argomenti.theme-light .detail-file-item:hover { background: #f2ede2; }
        .mappa-argomenti.theme-light .detail-action-btn { border-color: rgba(190, 160, 110, 0.35); color: #2e2820; }
        .mappa-argomenti.theme-light .detail-action-btn:hover { background: rgba(190, 160, 110, 0.14); color: #111111; border-color: rgba(190, 160, 110, 0.5); }
        .mappa-argomenti.theme-light .detail-empty { color: #2e2820; }
        .mappa-argomenti ::-webkit-scrollbar { width: 3px; height: 3px; }
        .mappa-argomenti ::-webkit-scrollbar-track { background: transparent; }
        .mappa-argomenti ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.05); border-radius: 10px; }
        .mappa-argomenti ::-webkit-scrollbar-thumb:hover { background: #00d2ff; }
        .mappa-loading, .mappa-error {
          display: flex; flex-direction: column; align-items: center; justify-content: center;
          height: 100%; gap: 12px; color: #5a5e72; font-size: 0.75rem;
        }
        .spinner { width: 28px; height: 28px; border: 2px solid #1e2030; border-top-color: #bc8cff; border-radius: 50%; animation: spin 0.8s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .retry-btn { padding: 6px 16px; background: #1e2030; border: 1px solid #2a2d3e; border-radius: 6px; color: #e2e4eb; cursor: pointer; font-size: 0.7rem; }
        .retry-btn:hover { background: #2a2d3e; }
        
        /* === TOP: graph + detail panel (35%) === */
        .mappa-top-section {
          height: 100%; display: flex; flex-shrink: 0;
        }
        .mappa-graph-container {
          flex: 1; position: relative; overflow: hidden;
          min-width: 0;
          background: radial-gradient(ellipse at 40% 40%, rgba(137, 87, 229, 0.09) 0%, rgba(0, 210, 255, 0.04) 45%, transparent 85%);
        }
        .constellation-orbit-ring {
          transform-origin: center;
          animation: constellation-orbit-spin 30s linear infinite;
        }
        .graph-node:hover .constellation-star-flare {
          transform: scale(1.35);
          transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .mappa-graph-svg { width: 100%; height: 100%; display: block; }
        .graph-link { stroke-width: 1.8; transition: opacity 0.2s; }
        .graph-link.parent-link { stroke-dasharray: 6,4; }
        .graph-link.highlight { stroke: #00d2ff !important; stroke-width: 3 !important; }
        .graph-link.parent-link.highlight { stroke: #fbbf24 !important; stroke-width: 3.5 !important; }
        .graph-node { cursor: pointer; transition: opacity 0.2s; }
        .mappa-zoom-controls {
          position: absolute; bottom: 12px; left: 12px; display: flex; gap: 6px; align-items: center;
        }
        .mappa-header-bar button {
          background: rgba(22, 27, 40, 0.75);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          color: #e2e4eb;
          cursor: pointer;
          font-family: inherit;
          font-weight: 600;
          transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
          backdrop-filter: blur(8px);
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .mappa-header-bar .btn-explore {
          background: rgba(46, 160, 67, 0.12);
          border-color: rgba(46, 160, 67, 0.35);
          color: #3fb950;
        }
        .mappa-header-bar .btn-explore:hover {
          background: rgba(46, 160, 67, 0.22);
          border-color: rgba(46, 160, 67, 0.6);
          box-shadow: 0 0 12px rgba(46, 160, 67, 0.25);
          transform: translateY(-1px);
        }
        .mappa-header-bar .btn-explore.active {
          background: rgba(255, 85, 85, 0.12);
          border-color: rgba(255, 85, 85, 0.35);
          color: #ff5555;
        }
        .mappa-header-bar .btn-explore.active:hover {
          background: rgba(255, 85, 85, 0.22);
          border-color: rgba(255, 85, 85, 0.6);
          box-shadow: 0 0 12px rgba(255, 85, 85, 0.25);
        }
        .mappa-header-bar .btn-update {
          background: rgba(0, 210, 255, 0.12);
          border-color: rgba(0, 210, 255, 0.35);
          color: #00d2ff;
        }
        .mappa-header-bar .btn-update:hover {
          background: rgba(0, 210, 255, 0.22);
          border-color: rgba(0, 210, 255, 0.6);
          box-shadow: 0 0 14px rgba(0, 210, 255, 0.3);
          transform: translateY(-1px);
        }
        .mappa-header-bar .btn-new-topic {
          background: linear-gradient(135deg, rgba(188, 140, 255, 0.2), rgba(137, 87, 229, 0.14));
          border-color: rgba(188, 140, 255, 0.4);
          color: #d2a8ff;
        }
        .mappa-header-bar .btn-new-topic:hover {
          background: linear-gradient(135deg, rgba(188, 140, 255, 0.3), rgba(137, 87, 229, 0.25));
          border-color: rgba(188, 140, 255, 0.65);
          box-shadow: 0 0 14px rgba(188, 140, 255, 0.35);
          transform: translateY(-1px);
        }


        /* Detail Panel (side panel in top section) */
        .mappa-detail-panel {
          width: 380px; border-left: 1px solid #1e2030;
          padding: 12px 16px; flex-shrink: 0; background: #11131b;
          display: flex; flex-direction: column; overflow: hidden;
        }
        .detail-body-scrollable {
          flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px;
          margin-top: 4px;
        }
        
        /* Search Box in Sidebar */
        .sidebar-search-box {
          position: relative; display: flex; align-items: center; margin-bottom: 12px;
          background: #0e1016; border: 1px solid #1e2030; border-radius: 6px; padding: 6px 10px;
          flex-shrink: 0;
        }
        .sidebar-search-box .search-icon { font-size: 0.65rem; color: #5a5e72; margin-right: 6px; }
        .sidebar-search-input {
          flex: 1; background: transparent; border: none; outline: none;
          color: #e2e4eb; font-size: 0.65rem; font-family: inherit;
        }
        .sidebar-search-input::placeholder { color: #5a5e72; }
        .clear-search-btn {
          background: none; border: none; color: #5a5e72; cursor: pointer; font-size: 0.6rem; padding: 2px;
        }
        .clear-search-btn:hover { color: #ff5555; }

        /* Explorer Sections */
        .explorer-section {
          margin-bottom: 10px; border-bottom: 1px solid #1e2030; padding-bottom: 12px;
        }
        .explorer-section-header {
          font-size: 0.5rem; font-weight: 600; color: #5a5e72; letter-spacing: 1px;
          cursor: pointer; display: flex; align-items: center; justify-content: space-between;
          padding: 4px 0; user-select: none;
        }
        .explorer-section-header:hover { color: #8b8fa3; }
        .explorer-section-content { display: flex; flex-direction: column; gap: 2px; margin-top: 4px; }
        
        /* Topic Item in Explorer */
        .explorer-topic-item {
          display: flex; align-items: center; gap: 8px; padding: 6px 8px;
          border-radius: 6px; cursor: pointer; transition: all 0.15s; font-size: 0.65rem; color: #8b8fa3;
        }
        .explorer-topic-item:hover { background: rgba(255,255,255,0.03); color: #e2e4eb; }
        .explorer-topic-item.active { background: rgba(188,140,255,0.06); color: #bc8cff; border-left: 2px solid #bc8cff; }
        .explorer-topic-icon { font-size: 0.6rem; width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,0.03); border-radius: 4px; }
        .explorer-topic-item.active .explorer-topic-icon { background: rgba(188,140,255,0.1); }
        .explorer-topic-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .explorer-topic-count { font-size: 0.5rem; background: #1e2030; padding: 1px 5px; border-radius: 4px; color: #5a5e72; }
        .explorer-topic-item.active .explorer-topic-count { color: #bc8cff; background: rgba(188,140,255,0.1); }

        /* Folder Tree Explorer */
        .folder-tree { display: flex; flex-direction: column; gap: 4px; margin-top: 6px; }
        .folder-item { display: flex; flex-direction: column; }
        .folder-header {
          display: flex; align-items: center; gap: 6px; padding: 6px 8px; border-radius: 6px;
          cursor: pointer; transition: all 0.12s; font-size: 0.65rem; color: #8b8fa3; position: relative;
        }
        .folder-header:hover { background: rgba(255,255,255,0.03); color: #e2e4eb; }
        .folder-header-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: flex; align-items: center; gap: 4px; }
        .folder-header-count { font-size: 0.5rem; color: #5a5e72; margin-left: 4px; }
        .folder-actions { display: none; align-items: center; gap: 6px; position: absolute; right: 8px; }
        .folder-header:hover .folder-actions { display: flex; }
        .folder-action-btn { background: none; border: none; cursor: pointer; font-size: 0.55rem; color: #5a5e72; padding: 2px; }
        .folder-action-btn:hover { color: #e2e4eb; }
        .folder-action-btn.del:hover { color: #ff5555; }
        .folder-contents { padding-left: 14px; border-left: 1px dashed rgba(255,255,255,0.05); margin: 2px 0 4px 6px; display: flex; flex-direction: column; gap: 2px; }

        /* Category Folder Item */
        .category-folder-header {
          display: flex; align-items: center; gap: 4px; padding: 4px 6px; border-radius: 4px;
          cursor: pointer; transition: all 0.12s; font-size: 0.6rem; color: #8b8fa3; position: relative;
        }
        .category-folder-header:hover { background: rgba(255,255,255,0.03); color: #e2e4eb; }
        .category-folder-actions { display: none; align-items: center; position: absolute; right: 6px; }
        .category-folder-header:hover .category-folder-actions { display: flex; }
        .category-folder-add-btn { background: none; border: none; cursor: pointer; font-size: 0.5rem; color: #5a5e72; padding: 1px 3px; border-radius: 3px; }
        .category-folder-add-btn:hover { color: #e2e4eb; background: rgba(255,255,255,0.05); }

        /* File Item inside Folder */
        .file-tree-item {
          display: flex; align-items: center; gap: 6px; padding: 4px 6px; border-radius: 4px;
          cursor: pointer; transition: all 0.1s; font-size: 0.6rem; color: #8b8fa3; position: relative;
        }
        .file-tree-item:hover { background: rgba(255,255,255,0.03); color: #e2e4eb; }
        .file-tree-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .file-tree-actions { display: none; align-items: center; position: absolute; right: 6px; }
        .file-tree-item:hover .file-tree-actions { display: flex; }
        .file-tree-del-btn { background: none; border: none; cursor: pointer; font-size: 0.5rem; color: #ff5555; padding: 1px 3px; border-radius: 3px; }
        .file-tree-del-btn:hover { background: rgba(255,85,85,0.1); }

        .detail-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 8px; color: #5a5e72; font-size: 0.65rem; text-align: center; }
        .detail-empty-icon { font-size: 1.2rem; }
        .detail-body { flex: 1; display: flex; flex-direction: column; gap: 0; }
        .detail-header { margin-bottom: 6px; }
        .detail-type { font-size: 0.45rem; font-weight: 600; color: #5a5e72; letter-spacing: 1px; margin-bottom: 1px; }
        .detail-title { font-size: 0.8rem; font-weight: 700; line-height: 1.2; }
        .detail-desc { font-size: 0.85rem; color: #8b8fa3; margin-bottom: 6px; line-height: 1.4; }
        .detail-meta { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 4px; }
        .detail-meta .tag { font-size: 0.45rem; background: #1e2030; padding: 1px 6px; border-radius: 4px; color: #8b8fa3; }
        .detail-meta .tag.modules-tag { color: #00d2ff; background: rgba(0,210,255,0.08); }
        .detail-meta.manifesto-ref { font-size: 0.5rem; color: #5a5e72; }
        .detail-rel { font-size: 0.55rem; margin-bottom: 4px; }
        .detail-rel-label { color: #5a5e72; font-size: 0.45rem; display: block; margin-bottom: 1px; }
        .detail-rel-value { color: #8b8fa3; }
        .detail-rel-list { display: flex; gap: 3px; flex-wrap: wrap; margin-top: 2px; }
        .detail-rel-tag { font-size: 0.45rem; background: rgba(188,140,255,0.08); border: 1px solid rgba(188,140,255,0.15); padding: 1px 5px; border-radius: 3px; color: #bc8cff; }
        .detail-files { margin-top: 2px; }
        .detail-files h4 { font-size: 0.5rem; font-weight: 600; color: #5a5e72; letter-spacing: 0.5px; margin-bottom: 2px; border-bottom: 1px solid #1e2030; padding-bottom: 2px; }
        .detail-file-item { display: flex; align-items: center; gap: 4px; padding: 3px 6px; cursor: pointer; border-radius: 4px; transition: background 0.1s; font-size: 0.75rem; }
        .detail-file-item:hover { background: rgba(255,255,255,0.05); }
        .detail-file-item .icon { flex-shrink: 0; font-size: 0.6rem; }
        .detail-file-item .fname { color: #8b8fa3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .detail-file-item .fname:hover { color: #e2e4eb; }
        .detail-action-btn {
          width: 100%; padding: 8px 12px; border-radius: 6px; font-size: 0.65rem;
          cursor: pointer; border: 1px solid #1e2030; background: transparent;
          color: #8b8fa3; font-family: inherit; transition: all 0.12s;
          display: flex; align-items: center; gap: 6px;
        }
        .detail-action-btn:hover { background: rgba(0,210,255,0.06); color: #00d2ff; border-color: rgba(0,210,255,0.2); }

        /* === BOTTOM: tab bar + columns (65%) === */
        .mappa-bottom-section {
          flex: 1; display: flex; flex-direction: column; min-height: 0;
        }

        /* === MODULE FILTER BAR === */
        .module-filter-bar {
          display: flex; gap: 4px; padding: 6px 24px; align-items: center;
          background: #0e1016; border-bottom: 1px solid #1e2030; flex-shrink: 0; overflow-x: auto;
        }
        .module-filter-bar::-webkit-scrollbar { height: 2px; }
        .module-filter-bar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.05); }
        .mfb-label {
          font-size: 0.6rem; color: #5a5e72; white-space: nowrap; margin-right: 4px; font-weight: 500;
        }
        .mfb-btn {
          padding: 4px 10px; border-radius: 6px; font-size: 0.6rem; cursor: pointer;
          border: 1px solid #1e2030; background: transparent; color: #5a5e72;
          font-family: inherit; transition: all 0.12s; white-space: nowrap;
        }
        .mfb-btn:hover { color: #8b8fa3; border-color: #2a2d3e; }
        .mfb-btn.active { color: #00d2ff; border-color: rgba(0,210,255,0.3); background: rgba(0,210,255,0.08); }

        /* === TOPIC TAB BAR === */
        .topic-tab-bar {
          display: flex; gap: 2px; padding: 0 24px; background: #11131b;
          border-bottom: 1px solid #1e2030; flex-shrink: 0; overflow-x: auto; flex-wrap: nowrap;
        }
        .topic-tab-bar::-webkit-scrollbar { height: 2px; }
        .topic-tab-bar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.05); border-radius: 2px; }
        .topic-tab {
          display: flex; align-items: center; gap: 8px; padding: 10px 16px;
          font-size: 0.7rem; cursor: pointer; border-bottom: 2px solid transparent;
          color: #5a5e72; white-space: nowrap; transition: all 0.15s;
          font-family: inherit; background: transparent; border-top: none; border-left: none; border-right: none;
        }
        .topic-tab:hover { color: #8b8fa3; background: rgba(255,255,255,0.015); }
        .topic-tab.active { color: #e2e4eb; border-bottom-color: #bc8cff; background: rgba(188,140,255,0.05); }
        .topic-tab .tab-icon { width: 22px; height: 22px; background: rgba(188,140,255,0.08); border: 1px solid rgba(188,140,255,0.15); border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 0.65rem; flex-shrink: 0; }
        .topic-tab .tab-count { font-size: 0.5rem; background: #1e2030; padding: 1px 6px; border-radius: 4px; color: #5a5e72; }
        .topic-tab.active .tab-count { background: rgba(188,140,255,0.08); color: #bc8cff; }

        /* === FILE COLUMNS === */
        .file-columns-area {
          flex: 1; overflow-y: auto; padding: 18px 24px; display: flex; gap: 16px;
          border-top: 1px solid #1e2030;
        }
        .file-column {
          flex: 1; min-width: 200px; display: flex; flex-direction: column;
          background: #11131b; border: 1px solid #1e2030; border-radius: 8px; overflow: hidden;
        }
        .file-column-header {
          padding: 10px 12px; font-size: 0.6rem; font-weight: 600; letter-spacing: 1px;
          border-bottom: 1px solid #1e2030; flex-shrink: 0; display: flex; align-items: center; gap: 6px;
        }
        .file-column-list { padding: 6px 8px; overflow-y: auto; flex: 1; }
        .file-column .empty-col-hint { font-size: 0.55rem; color: #5a5e72; text-align: center; padding: 16px 8px; }

        .col-file-item {
          display: flex; align-items: center; gap: 6px; padding: 5px 8px;
          border-radius: 6px; cursor: pointer; transition: all 0.12s; font-size: 0.6rem;
          border-left: 2px solid transparent; margin-bottom: 2px;
        }
        .col-file-item:hover { background: rgba(255,255,255,0.04); transform: translateX(2px); }
        .col-file-item .col-file-icon { flex-shrink: 0; font-size: 0.6rem; }
        .col-file-item .col-file-name { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #8b8fa3; }
        .col-file-item .col-file-name:hover { color: #e2e4eb; }
        .col-file-item .col-file-del {
          opacity: 0; font-size: 0.5rem; cursor: pointer; padding: 1px 3px; border: none; background: none;
          color: #ff5555; transition: opacity 0.12s; border-radius: 2px;
        }
        .col-file-item:hover .col-file-del { opacity: 0.6; }
        .col-file-item .col-file-del:hover { opacity: 1 !important; background: rgba(255,85,85,0.1); }
        .col-file-item .col-mod-badge {
          font-size: 0.45rem; background: #1e2030; padding: 1px 5px; border-radius: 3px;
          color: #5a5e72; flex-shrink: 0; font-weight: 500;
        }

        /* AI action overlay card styles */
        .ai-overlay-card {
          position: absolute;
          width: 320px;
          background: rgba(11, 16, 27, 0.96);
          backdrop-filter: blur(16px);
          border: 1px solid rgba(0, 210, 255, 0.2);
          border-radius: 12px;
          box-shadow: 0 8px 32px rgba(0, 210, 255, 0.12), 0 0 0 1px rgba(0, 210, 255, 0.05);
          z-index: 1000;
          padding: 12px 14px;
          color: #e2e4eb;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        .ai-overlay-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          border-bottom: 1px solid rgba(255, 255, 255, 0.06);
          padding-bottom: 6px;
          cursor: grab;
          user-select: none;
        }
        .ai-overlay-header:active {
          cursor: grabbing;
        }
        .ai-overlay-title {
          font-size: 0.7rem;
          font-weight: 700;
          color: #00d2ff;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 250px;
        }
        .ai-overlay-close {
          background: none;
          border: none;
          color: #5a5e72;
          cursor: pointer;
          font-size: 0.75rem;
          padding: 2px;
        }
        .ai-overlay-close:hover {
          color: #ff5555;
        }
        .ai-overlay-tabs {
          display: flex;
          background: #0e1016;
          border-radius: 6px;
          padding: 2px;
          gap: 2px;
        }
        .ai-overlay-tab {
          flex: 1;
          background: none;
          border: none;
          border-radius: 4px;
          color: #8b8fa3;
          font-size: 0.6rem;
          font-weight: 600;
          padding: 5px;
          cursor: pointer;
          transition: all 0.12s;
          text-align: center;
        }
        .ai-overlay-tab.active {
          background: rgba(0, 210, 255, 0.12);
          color: #00d2ff;
          border: 1px solid rgba(0, 210, 255, 0.15);
        }
        .ai-overlay-form {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .ai-overlay-group {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .ai-overlay-label {
          font-size: 0.5rem;
          font-weight: 600;
          color: #5a5e72;
          letter-spacing: 0.5px;
          text-transform: uppercase;
        }
        .ai-overlay-input, .ai-overlay-select, .ai-overlay-textarea {
          background: #0e1016;
          border: 1px solid #1e2030;
          border-radius: 6px;
          color: #e2e4eb;
          font-size: 0.65rem;
          font-family: inherit;
          padding: 6px 8px;
          outline: none;
          transition: border-color 0.12s;
        }
        .ai-overlay-input:focus, .ai-overlay-select:focus, .ai-overlay-textarea:focus {
          border-color: #00d2ff;
        }
        .ai-overlay-textarea {
          resize: vertical;
          min-height: 50px;
          line-height: 1.4;
        }
        .ai-overlay-error {
          font-size: 0.6rem;
          color: #ff5555;
          background: rgba(255, 85, 85, 0.08);
          border-radius: 6px;
          padding: 6px;
        }
        .ai-overlay-footer {
          display: flex;
          gap: 6px;
          margin-top: 4px;
        }
        .ai-overlay-btn {
          flex: 1;
          padding: 8px;
          border-radius: 6px;
          font-size: 0.65rem;
          font-weight: 600;
          cursor: pointer;
          border: 1px solid #1e2030;
          background: #1e2030;
          color: #e2e4eb;
          transition: all 0.12s;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
        }
        .ai-overlay-btn.primary {
          background: rgba(0, 210, 255, 0.10);
          border-color: rgba(0, 210, 255, 0.25);
          color: #00d2ff;
        }
        .ai-overlay-btn.primary:hover:not(:disabled) {
          background: rgba(0, 210, 255, 0.18);
          border-color: rgba(0, 210, 255, 0.45);
        }
        .ai-overlay-btn.secondary {
          background: transparent;
          color: #8b8fa3;
        }
        .ai-overlay-btn.secondary:hover {
          background: rgba(255, 255, 255, 0.03);
          color: #e2e4eb;
        }
        .ai-overlay-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .ai-overlay-spinner {
          width: 12px;
          height: 12px;
          border: 2px solid transparent;
          border-top-color: currentColor;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        .ai-overlay-dropzone:hover {
          border-color: rgba(0, 210, 255, 0.45) !important;
          background: rgba(0, 210, 255, 0.04) !important;
        }
        .ai-overlay-dropzone.dragging {
          border-color: #00d2ff !important;
          background: rgba(0, 210, 255, 0.08) !important;
          box-shadow: 0 0 12px rgba(0, 210, 255, 0.15);
        }
      `}),(0,v.jsxs)(`div`,{className:`mappa-top-section`,style:{flex:1,minHeight:0,display:`flex`,gap:`14px`,margin:`12px 16px 14px 16px`},children:[(0,v.jsxs)(`div`,{className:`mappa-left-column`,style:{flex:1,minWidth:0,display:`flex`,flexDirection:`column`,position:`relative`,overflow:`hidden`,borderRadius:`10px`},children:[(0,v.jsx)(`div`,{className:`mappa-header-bar`,style:{display:`flex`,alignItems:`center`,justifyContent:`space-between`,flexWrap:`wrap`,gap:`10px`,padding:`8px 12px`,margin:`0 0 10px 0`,background:`linear-gradient(135deg, rgba(17, 19, 27, 0.95), rgba(24, 27, 40, 0.85))`,border:`1px solid rgba(255, 255, 255, 0.08)`,borderRadius:`10px`,backdropFilter:`blur(12px)`,boxShadow:`0 4px 20px rgba(0, 0, 0, 0.25)`,zIndex:5,flexShrink:0},children:(0,v.jsxs)(`div`,{style:{display:`flex`,alignItems:`center`,gap:`8px`,flexWrap:`wrap`},children:[(0,v.jsxs)(`div`,{className:`theme-control`,style:{display:`flex`,alignItems:`center`,gap:`6px`,background:`#11131b`,border:`1px solid rgba(0, 210, 255, 0.25)`,padding:`4px 10px`,borderRadius:`8px`,fontSize:`0.68rem`,color:`#8b8fa3`,boxShadow:`0 2px 10px rgba(0,0,0,0.3)`,transition:`border-color 0.2s`},title:`Cambia tema della Mappa Argomenti`,children:[(0,v.jsx)(`span`,{style:{fontSize:`0.72rem`},children:`🎨 Tema:`}),(0,v.jsxs)(`select`,{value:J,onChange:e=>Ve(e.target.value),style:{background:J===`crema`?`rgba(245, 239, 227, 0.98)`:`rgba(14, 16, 22, 0.95)`,color:J===`costellazione`?`#bc8cff`:J===`classico`?`#00d2ff`:J===`crema`?`#8b6b3d`:`#fbbf24`,border:`1px solid `+(J===`costellazione`?`rgba(188, 140, 255, 0.4)`:J===`classico`?`rgba(0, 210, 255, 0.4)`:J===`crema`?`rgba(200, 150, 62, 0.5)`:`rgba(251, 191, 36, 0.4)`),borderRadius:`6px`,padding:`4px 8px`,outline:`none`,fontSize:`0.68rem`,fontWeight:700,cursor:`pointer`,boxShadow:J===`costellazione`?`0 0 10px rgba(188, 140, 255, 0.2)`:J===`classico`?`0 0 10px rgba(0, 210, 255, 0.2)`:J===`crema`?`0 0 10px rgba(200, 150, 62, 0.3)`:`0 0 10px rgba(251, 191, 36, 0.2)`,transition:`all 0.2s ease`},children:[(0,v.jsx)(`option`,{value:`costellazione`,style:{background:`#0e1016`,color:`#bc8cff`},children:`🌌 Costellazione Spaziale`}),(0,v.jsx)(`option`,{value:`classico`,style:{background:`#0e1016`,color:`#00d2ff`},children:`📊 Grafo Tecnologico`}),(0,v.jsx)(`option`,{value:`minimal`,style:{background:`#0e1016`,color:`#fbbf24`},children:`✨ Minimal & Contrast`}),(0,v.jsx)(`option`,{value:`crema`,style:{background:`#f5efe3`,color:`#8b6b3d`},children:`🎨 Tema Crema`})]})]}),(0,v.jsxs)(`div`,{className:`font-size-control`,style:{display:`flex`,alignItems:`center`,gap:`6px`,background:`#11131b`,border:`1px solid #1e2030`,padding:`5px 10px`,borderRadius:`8px`,fontSize:`0.68rem`,color:`#8b8fa3`},title:`Regola la dimensione del testo dei nodi (da 6px a 90px)`,children:[(0,v.jsx)(`span`,{children:`🔤 Testo:`}),(0,v.jsx)(`input`,{type:`range`,min:`6`,max:`90`,step:`1`,value:K,onChange:e=>Le(parseInt(e.target.value,10)),style:{width:`85px`,accentColor:`#00d2ff`,cursor:`pointer`}}),(0,v.jsxs)(`span`,{style:{color:`#00d2ff`,fontWeight:600,minWidth:`32px`},children:[K,`px`]})]}),(0,v.jsxs)(`div`,{className:`branch-length-control`,style:{display:`flex`,alignItems:`center`,gap:`6px`,background:`#11131b`,border:`1px solid #1e2030`,padding:`5px 10px`,borderRadius:`8px`,fontSize:`0.68rem`,color:`#8b8fa3`},title:`Regola la lunghezza dei rami del grafico (da 40px a 800px)`,children:[(0,v.jsx)(`span`,{children:`🌿 Rami:`}),(0,v.jsx)(`input`,{type:`range`,min:`40`,max:`800`,step:`10`,value:q,onChange:e=>ze(parseInt(e.target.value,10)),style:{width:`85px`,accentColor:`#bc8cff`,cursor:`pointer`}}),(0,v.jsxs)(`span`,{style:{color:`#bc8cff`,fontWeight:600,minWidth:`36px`},children:[q,`px`]})]}),(0,v.jsx)(`button`,{className:`btn-explore ${E?`active`:``}`,onClick:()=>{te(e=>{let t=!e;return localStorage.setItem(`sigma_mappa_explore`,String(t)),t})},title:E?`Collidi`:`Esplora`,style:{padding:`6px 12px`,fontSize:`0.72rem`,borderRadius:`8px`},children:E?`✕ Collidi`:`🔍 Esplora`}),(0,v.jsx)(`button`,{className:`btn-update`,onClick:Z,title:`Aggiorna dati e grafico`,style:{padding:`6px 12px`,fontSize:`0.72rem`,borderRadius:`8px`},children:`🔄 Aggiorna`}),(0,v.jsx)(`button`,{className:`btn-update`,onClick:He,title:`Salva le posizioni trascinate dei nodi del grafo`,style:{padding:`6px 12px`,fontSize:`0.72rem`,borderRadius:`8px`,background:`rgba(63, 185, 80, 0.12)`,borderColor:`rgba(63, 185, 80, 0.3)`,color:`#3fb950`},children:`💾 Salva Layout`}),(0,v.jsx)(`button`,{className:`btn-update`,onClick:Ue,title:`Ripristina il layout predefinito con calcolo automatico della forza`,style:{padding:`6px 12px`,fontSize:`0.72rem`,borderRadius:`8px`,background:`rgba(210, 153, 34, 0.12)`,borderColor:`rgba(210, 153, 34, 0.3)`,color:`#d29922`},children:`🔄 Layout Default`}),(0,v.jsx)(`button`,{className:`btn-new-topic`,onClick:lt,title:`Crea nuovo argomento`,style:{padding:`6px 12px`,fontSize:`0.72rem`,borderRadius:`8px`},children:`🌐 Nuovo Argomento`})]})}),(0,v.jsxs)(`div`,{ref:a,className:`mappa-graph-container`,style:{flex:1,minHeight:0,display:`flex`,position:`relative`,overflow:`hidden`,borderRadius:`10px`,background:J===`costellazione`?`radial-gradient(ellipse at 40% 40%, rgba(137, 87, 229, 0.14) 0%, rgba(0, 210, 255, 0.06) 45%, #050612 90%)`:J===`classico`?`radial-gradient(circle at 50% 50%, rgba(0, 210, 255, 0.08) 0%, #090b14 85%)`:J===`crema`?`radial-gradient(ellipse at 40% 40%, rgba(200, 150, 62, 0.14) 0%, rgba(139, 107, 61, 0.06) 45%, #f2e8d4 100%)`:`#0e1018`},children:[(0,v.jsx)(`svg`,{ref:i,className:`mappa-graph-svg`,style:{flex:1}}),ce&&A&&(0,v.jsxs)(`div`,{className:`ai-overlay-card`,style:{left:`${ue.x}px`,top:`${ue.y}px`},onClick:e=>e.stopPropagation(),children:[(0,v.jsxs)(`div`,{className:`ai-overlay-header`,onMouseDown:Je,children:[(0,v.jsxs)(`span`,{className:`ai-overlay-title`,children:[A.type===`doc`?`📄 `:A.type===`topic`?`🌐 `:`➕ `,Q(A.label)]}),(0,v.jsxs)(`div`,{style:{display:`flex`,alignItems:`center`,gap:`4px`},children:[A.type===`doc`&&(0,v.jsx)(`button`,{className:`ai-overlay-close`,type:`button`,style:{color:`#ff5555`,background:`rgba(255,85,85,0.1)`,border:`1px solid rgba(255,85,85,0.2)`,padding:`2px 6px`,borderRadius:`4px`,fontSize:`0.65rem`},onClick:()=>{U(`delete`),B(``)},onMouseDown:e=>e.stopPropagation(),title:`Elimina questo file`,children:`🗑️`}),(0,v.jsx)(`button`,{className:`ai-overlay-close`,type:`button`,onClick:()=>k(!1),onMouseDown:e=>e.stopPropagation(),children:`✕`})]})]}),A.type===`doc`?(0,v.jsxs)(v.Fragment,{children:[(0,v.jsxs)(`div`,{style:{display:`flex`,gap:`6px`,marginBottom:`8px`},children:[(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-btn primary`,style:{flex:1,padding:`8px 10px`,background:`rgba(0, 210, 255, 0.15)`,borderColor:`rgba(0, 210, 255, 0.35)`,color:`#00d2ff`,fontSize:`0.68rem`,borderRadius:`8px`,fontWeight:600,boxShadow:`0 0 10px rgba(0, 210, 255, 0.15)`},onClick:()=>{e&&A.filePath&&e(A.filePath),k(!1)},children:`👁️ Visualizza`}),(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-btn`,style:{flex:1,padding:`8px 10px`,background:`rgba(255, 85, 85, 0.12)`,borderColor:`rgba(255, 85, 85, 0.3)`,color:`#ff5555`,fontSize:`0.68rem`,borderRadius:`8px`,fontWeight:600,cursor:`pointer`},onClick:()=>{U(`delete`),B(``)},children:`🗑️ Elimina`})]}),(0,v.jsxs)(`div`,{className:`ai-overlay-tabs`,children:[(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-tab ${H===`ai_edit`?`active`:``}`,onClick:()=>{U(`ai_edit`),B(``)},children:`🤖 Modifica AI`}),(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-tab ${H===`move`?`active`:``}`,onClick:()=>{U(`move`),B(``)},children:`📦 Sposta`}),(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-tab ${H===`delete`?`active`:``}`,onClick:()=>{U(`delete`),B(``)},children:`🗑️ Elimina`})]}),H===`ai_edit`&&(0,v.jsxs)(`form`,{className:`ai-overlay-form`,onSubmit:ht,children:[(0,v.jsxs)(`div`,{className:`ai-overlay-group`,children:[(0,v.jsx)(`span`,{className:`ai-overlay-label`,children:`Modello AI`}),(0,v.jsx)(`select`,{className:`ai-overlay-select`,value:I,onChange:e=>_e(e.target.value),children:j.length>0?j.map(e=>(0,v.jsxs)(`option`,{value:e.name,children:[e.name,` (`,e.size,`)`]},e.name)):(0,v.jsx)(`option`,{value:`llama3.2`,children:`llama3.2 (default)`})})]}),(0,v.jsxs)(`div`,{className:`ai-overlay-group`,children:[(0,v.jsx)(`span`,{className:`ai-overlay-label`,children:`Ruolo Agente`}),(0,v.jsxs)(`select`,{className:`ai-overlay-select`,value:L,onChange:e=>ve(e.target.value),children:[(0,v.jsx)(`option`,{value:`code_architect`,children:`💻 Code Architect`}),(0,v.jsx)(`option`,{value:`math1`,children:`🔬 Math Architect`}),(0,v.jsx)(`option`,{value:`test-engineer`,children:`🧪 Test Engineer`}),(0,v.jsx)(`option`,{value:`viz-designer`,children:`🎨 Viz Designer`}),(0,v.jsx)(`option`,{value:`proof-reviewer`,children:`👁️ Proof Reviewer`})]})]}),(0,v.jsxs)(`div`,{className:`ai-overlay-group`,children:[(0,v.jsx)(`span`,{className:`ai-overlay-label`,children:`Istruzioni di modifica`}),(0,v.jsx)(`textarea`,{className:`ai-overlay-textarea`,placeholder:`Come vuoi modificare il file...`,value:ye,onChange:e=>R(e.target.value),required:!0})]}),z&&(0,v.jsx)(`div`,{className:`ai-overlay-error`,children:z}),(0,v.jsxs)(`div`,{className:`ai-overlay-footer`,children:[(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-btn secondary`,onClick:()=>{e&&e(A.filePath),k(!1)},children:`👁️ Visualizza`}),(0,v.jsx)(`button`,{type:`submit`,className:`ai-overlay-btn primary`,disabled:M,children:M?(0,v.jsxs)(v.Fragment,{children:[(0,v.jsx)(`div`,{className:`ai-overlay-spinner`}),`Applicazione...`]}):`🤖 Modifica`})]})]}),H===`move`&&(0,v.jsxs)(`form`,{className:`ai-overlay-form`,onSubmit:gt,children:[(0,v.jsxs)(`div`,{className:`ai-overlay-group`,children:[(0,v.jsx)(`span`,{className:`ai-overlay-label`,children:`Argomento di destinazione`}),(0,v.jsx)(`select`,{className:`ai-overlay-select`,value:V,onChange:e=>be(e.target.value),children:o.map(e=>(0,v.jsxs)(`option`,{value:e.id,children:[`🌐 `,Q(e.name)]},e.id))})]}),(0,v.jsxs)(`div`,{className:`ai-overlay-group`,children:[(0,v.jsx)(`span`,{className:`ai-overlay-label`,children:`Sottoargomento (Modulo)`}),(0,v.jsxs)(`select`,{className:`ai-overlay-select`,value:xe,onChange:e=>Se(e.target.value),children:[(0,v.jsx)(`option`,{value:``,children:`— Nessun modulo (radice argomento) —`}),(o.find(e=>e.id===V)?.modules||[]).map(e=>(0,v.jsxs)(`option`,{value:e.number,children:[`M`,e.number,` — `,Q(e.name)]},e.number))]})]}),(0,v.jsxs)(`div`,{className:`ai-overlay-group`,children:[(0,v.jsx)(`span`,{className:`ai-overlay-label`,children:`Categoria File`}),(0,v.jsxs)(`select`,{className:`ai-overlay-select`,value:Ce,onChange:e=>we(e.target.value),children:[(0,v.jsx)(`option`,{value:`teoria`,children:`📖 Teoria`}),(0,v.jsx)(`option`,{value:`scripts`,children:`⚡ Script / Codice`}),(0,v.jsx)(`option`,{value:`viz`,children:`📊 Visualizzazione`}),(0,v.jsx)(`option`,{value:`docs`,children:`📄 Documentazione`}),(0,v.jsx)(`option`,{value:`whitepaper`,children:`📜 Whitepaper`})]})]}),z&&(0,v.jsx)(`div`,{className:`ai-overlay-error`,children:z}),(0,v.jsxs)(`div`,{className:`ai-overlay-footer`,children:[(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-btn secondary`,onClick:()=>k(!1),children:`Annulla`}),(0,v.jsx)(`button`,{type:`submit`,className:`ai-overlay-btn primary`,disabled:M,children:M?(0,v.jsxs)(v.Fragment,{children:[(0,v.jsx)(`div`,{className:`ai-overlay-spinner`}),`Spostamento...`]}):`📦 Sposta`})]})]}),H===`delete`&&(0,v.jsxs)(`div`,{className:`ai-overlay-form`,children:[(0,v.jsx)(`div`,{style:{fontSize:`0.65rem`,color:`#8b8fa3`,margin:`4px 0 8px 0`,lineHeight:`1.4`},children:`Sei sicuro di voler eliminare definitivamente questo file? Questa azione non può essere annullata.`}),z&&(0,v.jsx)(`div`,{className:`ai-overlay-error`,children:z}),(0,v.jsxs)(`div`,{className:`ai-overlay-footer`,children:[(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-btn secondary`,onClick:()=>k(!1),children:`Annulla`}),(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-btn`,style:{background:`rgba(255, 85, 85, 0.1)`,borderColor:`rgba(255, 85, 85, 0.25)`,color:`#ff5555`},onClick:_t,disabled:M,children:M?`Eliminazione...`:`🗑️ Elimina Definitivamente`})]})]})]}):(0,v.jsxs)(v.Fragment,{children:[(0,v.jsxs)(`div`,{className:`ai-overlay-tabs`,style:{marginBottom:`10px`},children:[(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-tab ${Me===`create`?`active`:``}`,onClick:()=>{Ne(`create`),B(``)},children:`➕ Contenuti & Azioni`}),(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-tab ${Me===`move`?`active`:``}`,onClick:()=>{Ne(`move`),Fe(A.data?.parent_id||``),B(``)},children:`📦 Sposta`})]}),Me===`move`?(0,v.jsx)(`div`,{className:`ai-overlay-form`,style:{display:`flex`,flexDirection:`column`,gap:`8px`},children:(()=>{let e=A.data,t=st(e),n=o.find(t=>t.id===e?.parent_id);return(0,v.jsxs)(v.Fragment,{children:[(0,v.jsxs)(`div`,{style:{fontSize:`0.62rem`,background:`rgba(255, 255, 255, 0.03)`,border:`1px solid rgba(255, 255, 255, 0.06)`,borderRadius:`6px`,padding:`6px 8px`,color:`#8b8fa3`},children:[`📍 Posizione Attuale: `,(0,v.jsx)(`strong`,{style:{color:`#bc8cff`},children:n?Q(n.name):`🌐 Cartella Principale (1° Livello)`})]}),(0,v.jsxs)(`div`,{className:`ai-overlay-group`,children:[(0,v.jsx)(`span`,{className:`ai-overlay-label`,children:`Seleziona Destinazione`}),(0,v.jsxs)(`select`,{className:`ai-overlay-select`,value:Pe,onChange:e=>Fe(e.target.value),children:[(0,v.jsx)(`option`,{value:``,children:`🌐 Cartella Principale (1° Livello)`}),t.map(e=>(0,v.jsxs)(`option`,{value:e.id,children:[e.parent_id?`📂 `:`🌐 `,Q(e.name)]},e.id))]}),(0,v.jsx)(`div`,{style:{fontSize:`0.55rem`,color:`#5a5e72`,marginTop:`2px`,fontStyle:`italic`},children:`* I sottoargomenti figli di questo nodo sono stati nascosti per evitare cicli.`})]}),z&&(0,v.jsx)(`div`,{className:`ai-overlay-error`,children:z}),(0,v.jsxs)(`div`,{className:`ai-overlay-footer`,style:{marginTop:`8px`,display:`flex`,gap:`6px`,justifyContent:`flex-end`},children:[(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-btn secondary`,onClick:()=>Ne(`create`),children:`Annulla`}),(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-btn primary`,disabled:M,onClick:async()=>{N(!0),B(``);try{let t=await(await fetch(`/api/update_topic`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({topic_id:e.id,parent_id:Pe||null})})).json();if(t.success){let t=await Z();if(k(!1),t){let n=t.find(t=>t.id===e.id);n&&(m({type:n.parent_id?`module`:`topic`,data:n}),n.parent_id&&g(n.parent_id),it(n.id))}window.dispatchEvent(new CustomEvent(`sigma_toast`,{detail:{message:`📦 "${e.name}" spostato con successo!`,type:`success`,duration:3500}}))}else B(t.error||`Errore durante lo spostamento`)}catch(e){B(`Errore di connessione: `+e.message)}finally{N(!1)}},children:M?`Spostamento...`:`📦 Conferma Spostamento`})]})]})})()}):(0,v.jsxs)(v.Fragment,{children:[A.type===`topic`&&(0,v.jsxs)(`div`,{className:`ai-overlay-actions-section`,style:{display:`flex`,flexDirection:`column`,gap:`6px`,marginBottom:`10px`,paddingBottom:`8px`,borderBottom:`1px solid rgba(255,255,255,0.06)`},children:[(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-btn`,style:{background:`rgba(0, 210, 255, 0.16)`,borderColor:`rgba(0, 210, 255, 0.4)`,color:`#00d2ff`,fontSize:`0.65rem`,padding:`6px 10px`,borderRadius:`6px`,cursor:`pointer`,fontWeight:600,width:`100%`},onClick:()=>{at(A.data),k(!1)},children:`➕ Nuovo Sottoargomento`}),(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-btn`,style:{background:`rgba(255, 85, 85, 0.08)`,borderColor:`rgba(255, 85, 85, 0.2)`,color:`#ff5555`,fontSize:`0.6rem`,padding:`4px 8px`,borderRadius:`6px`,cursor:`pointer`,marginTop:`2px`},onClick:()=>{ft(A.data),k(!1)},children:`🗑️ Elimina Argomento`})]}),A.type===`module`&&(0,v.jsxs)(`div`,{className:`ai-overlay-actions-section`,style:{display:`flex`,flexDirection:`column`,gap:`6px`,marginBottom:`10px`,paddingBottom:`8px`,borderBottom:`1px solid rgba(255,255,255,0.06)`},children:[(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-btn`,style:{background:`rgba(0, 210, 255, 0.16)`,borderColor:`rgba(0, 210, 255, 0.4)`,color:`#00d2ff`,fontSize:`0.65rem`,padding:`6px 10px`,borderRadius:`6px`,cursor:`pointer`,fontWeight:600,width:`100%`},onClick:()=>{at(A.data),k(!1)},children:`➕ Nuovo Sottoargomento`}),(0,v.jsxs)(`div`,{style:{display:`flex`,gap:`6px`},children:[(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-btn`,style:{flex:1,background:`rgba(210, 153, 34, 0.1)`,borderColor:`rgba(210, 153, 34, 0.25)`,color:`#d29922`,fontSize:`0.6rem`,padding:`5px`,borderRadius:`6px`,cursor:`pointer`},onClick:()=>{pt(A.data,A.topicId),k(!1)},children:`✏️ Rinomina`}),(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-btn`,style:{flex:1,background:`rgba(255, 85, 85, 0.08)`,borderColor:`rgba(255, 85, 85, 0.2)`,color:`#ff5555`,fontSize:`0.6rem`,padding:`5px`,borderRadius:`6px`,cursor:`pointer`},onClick:()=>{dt(A.data,A.topicId),k(!1)},children:`🗑️ Elimina`})]})]}),(()=>{let t=[];return A.data&&[`teoria`,`scripts`,`test`,`viz`,`docs`,`whitepapers`,`pdf`,`media`].forEach(e=>{(A.data[e]||[]).forEach(n=>{let r=typeof n==`string`?n:n.path||n.filePath,i=r?r.split(`/`).pop():n.name||n;r&&t.push({name:i,path:r,category:e})})}),t.length===0?null:(0,v.jsxs)(`div`,{className:`ai-overlay-group`,style:{marginBottom:`10px`,paddingBottom:`8px`,borderBottom:`1px solid rgba(255,255,255,0.06)`},children:[(0,v.jsxs)(`span`,{className:`ai-overlay-label`,children:[`📄 File Esistenti (`,t.length,`)`]}),(0,v.jsx)(`div`,{style:{maxHeight:`110px`,overflowY:`auto`,display:`flex`,flexDirection:`column`,gap:`4px`,background:`rgba(0,0,0,0.2)`,padding:`6px`,borderRadius:`6px`},children:t.map((t,n)=>(0,v.jsxs)(`div`,{style:{display:`flex`,alignItems:`center`,justifyContent:`space-between`,fontSize:`0.6rem`,color:`#c5c9db`,background:`rgba(255,255,255,0.03)`,padding:`3px 6px`,borderRadius:`4px`},children:[(0,v.jsxs)(`span`,{style:{overflow:`hidden`,textOverflow:`ellipsis`,whiteSpace:`nowrap`,maxWidth:`140px`},title:t.path,children:[`📄 `,Q(t.name)]}),(0,v.jsxs)(`div`,{style:{display:`flex`,gap:`4px`},children:[(0,v.jsx)(`button`,{type:`button`,style:{background:`rgba(0,210,255,0.12)`,border:`1px solid rgba(0,210,255,0.25)`,color:`#00d2ff`,padding:`1px 5px`,borderRadius:`3px`,cursor:`pointer`,fontSize:`0.55rem`},onClick:()=>{e&&e(t.path),k(!1)},title:`Apri file`,children:`👁️`}),(0,v.jsx)(`button`,{type:`button`,style:{background:`rgba(255,85,85,0.12)`,border:`1px solid rgba(255,85,85,0.25)`,color:`#ff5555`,padding:`1px 5px`,borderRadius:`3px`,cursor:`pointer`,fontSize:`0.55rem`},onClick:async()=>{await mt(t.path),k(!1)},title:`Elimina file`,children:`🗑️`})]})]},n))})]})})(),(0,v.jsxs)(v.Fragment,{children:[(0,v.jsx)(`div`,{style:{fontSize:`0.5rem`,fontWeight:600,color:`#5a5e72`,letterSpacing:`0.5px`,marginBottom:`6px`,textTransform:`uppercase`},children:`CREA NUOVO FILE DENTRO QUESTO SOTTOARGOMENTO`}),(0,v.jsxs)(`div`,{className:`ai-overlay-tabs`,children:[(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-tab ${W===`standard`?`active`:``}`,onClick:()=>{De(`standard`),ge(!1),B(``)},children:`Standard`}),(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-tab ${W===`ai`?`active`:``}`,onClick:()=>{De(`ai`),ge(!0),B(``)},children:`🤖 Genera con AI`}),(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-tab ${W===`upload`?`active`:``}`,onClick:()=>{De(`upload`),ge(!1),B(``)},children:`📎 Allega File`})]}),(0,v.jsxs)(`form`,{className:`ai-overlay-form`,onSubmit:vt,children:[(0,v.jsxs)(`div`,{className:`ai-overlay-group`,children:[(0,v.jsx)(`span`,{className:`ai-overlay-label`,children:`Categoria File`}),(0,v.jsxs)(`select`,{className:`ai-overlay-select`,value:F,onChange:e=>me(e.target.value),children:[(0,v.jsx)(`option`,{value:`teoria`,children:`📖 Teoria`}),(0,v.jsx)(`option`,{value:`scripts`,children:`⚡ Script / Codice`}),(0,v.jsx)(`option`,{value:`viz`,children:`📊 Visualizzazione (D3)`}),(0,v.jsx)(`option`,{value:`docs`,children:`📄 Documentazione`}),(0,v.jsx)(`option`,{value:`whitepaper`,children:`📜 Whitepaper`})]})]}),W===`upload`&&(0,v.jsxs)(`div`,{className:`ai-overlay-group`,style:{gap:`8px`},children:[(0,v.jsx)(`span`,{className:`ai-overlay-label`,children:`Carica File da PC`}),(0,v.jsxs)(`div`,{className:`ai-overlay-dropzone ${ke?`dragging`:``} ${G?`has-file`:``}`,onDragEnter:Ye,onDragOver:Ye,onDragLeave:Ye,onDrop:Xe,onClick:()=>je.current?.click(),style:{border:`1.5px dashed rgba(0, 210, 255, 0.25)`,borderRadius:`8px`,padding:`16px 12px`,textAlign:`center`,background:ke?`rgba(0, 210, 255, 0.08)`:G?`rgba(0, 210, 255, 0.02)`:`rgba(0,0,0,0.15)`,cursor:`pointer`,transition:`all 0.15s ease`,display:`flex`,flexDirection:`column`,alignItems:`center`,justifyContent:`center`,gap:`6px`},children:[(0,v.jsx)(`input`,{ref:je,type:`file`,style:{display:`none`},onChange:Ze}),G?(0,v.jsxs)(v.Fragment,{children:[(0,v.jsx)(`span`,{style:{fontSize:`1.2rem`},children:`📎`}),(0,v.jsx)(`div`,{style:{fontSize:`0.65rem`,fontWeight:`600`,color:`#00d2ff`,maxWidth:`100%`,overflow:`hidden`,textOverflow:`ellipsis`,whiteSpace:`nowrap`},children:G.name}),(0,v.jsxs)(`div`,{style:{fontSize:`0.5rem`,color:`#5a5e72`},children:[(G.size/1024).toFixed(1),` KB`]}),(0,v.jsx)(`button`,{type:`button`,onClick:e=>{e.stopPropagation(),Oe(null),P(``)},style:{background:`rgba(255,85,85,0.1)`,border:`1px solid rgba(255,85,85,0.2)`,color:`#ff5555`,fontSize:`0.5rem`,padding:`2px 8px`,borderRadius:`4px`,marginTop:`4px`,cursor:`pointer`},children:`Rimuovi`})]}):(0,v.jsxs)(v.Fragment,{children:[(0,v.jsx)(`span`,{style:{fontSize:`1.2rem`,opacity:.6},children:`📥`}),(0,v.jsxs)(`div`,{style:{fontSize:`0.62rem`,color:`#8b8fa3`},children:[`Trascina qui il file o `,(0,v.jsx)(`span`,{style:{color:`#00d2ff`,textDecoration:`underline`},children:`sfoglia`})]}),(0,v.jsx)(`div`,{style:{fontSize:`0.5rem`,color:`#5a5e72`},children:`Supporta qualsiasi tipo di documento`})]})]}),G&&(0,v.jsxs)(`div`,{className:`ai-overlay-group`,children:[(0,v.jsx)(`span`,{className:`ai-overlay-label`,children:`Nome file sul server (senza estensione)`}),(0,v.jsx)(`input`,{type:`text`,className:`ai-overlay-input`,placeholder:`nome_file_salvato`,value:pe,onChange:e=>P(e.target.value.replace(/[^a-zA-Z0-9_-]/g,`_`)),required:!0})]})]}),W!==`upload`&&(0,v.jsxs)(`div`,{className:`ai-overlay-group`,children:[(0,v.jsx)(`span`,{className:`ai-overlay-label`,children:`Nome File (senza estensione)`}),(0,v.jsx)(`input`,{type:`text`,className:`ai-overlay-input`,placeholder:`nome_file`,value:pe,onChange:e=>P(e.target.value.replace(/[^a-zA-Z0-9_-]/g,`_`)),required:!0})]}),W===`ai`&&(0,v.jsxs)(v.Fragment,{children:[(0,v.jsxs)(`div`,{className:`ai-overlay-group`,children:[(0,v.jsx)(`span`,{className:`ai-overlay-label`,children:`Modello AI`}),(0,v.jsx)(`select`,{className:`ai-overlay-select`,value:I,onChange:e=>_e(e.target.value),children:j.length>0?j.map(e=>(0,v.jsxs)(`option`,{value:e.name,children:[e.name,` (`,e.size,`)`]},e.name)):(0,v.jsx)(`option`,{value:`llama3.2`,children:`llama3.2 (default)`})})]}),(0,v.jsxs)(`div`,{className:`ai-overlay-group`,children:[(0,v.jsx)(`span`,{className:`ai-overlay-label`,children:`Ruolo Agente (Associato Automaticamente)`}),(0,v.jsxs)(`div`,{style:{padding:`6px 10px`,background:`rgba(0, 210, 255, 0.08)`,border:`1px solid rgba(0, 210, 255, 0.25)`,borderRadius:`6px`,fontSize:`0.68rem`,color:`#00d2ff`,fontWeight:600,display:`flex`,alignItems:`center`,gap:`6px`},children:[`🤖 `,L===`math1`?`🔬 Math Architect (Teoria)`:L===`code_architect`?`💻 Code Architect (Script)`:L===`viz-designer`?`🎨 Viz Designer (Visualizzazione)`:`👁️ Proof Reviewer (Documentazione)`]})]}),(0,v.jsxs)(`div`,{className:`ai-overlay-group`,children:[(0,v.jsx)(`span`,{className:`ai-overlay-label`,children:`Descrizione per l'AI`}),(0,v.jsx)(`textarea`,{className:`ai-overlay-textarea`,placeholder:`Cosa deve contenere il file...`,value:ye,onChange:e=>R(e.target.value),required:!0})]})]}),z&&(0,v.jsx)(`div`,{className:`ai-overlay-error`,children:z}),(0,v.jsxs)(`div`,{className:`ai-overlay-footer`,children:[(0,v.jsx)(`button`,{type:`button`,className:`ai-overlay-btn secondary`,onClick:()=>k(!1),disabled:M,children:`Annulla`}),(0,v.jsx)(`button`,{type:`submit`,className:`ai-overlay-btn primary`,disabled:M||W===`upload`&&!G,children:M?(0,v.jsxs)(v.Fragment,{children:[(0,v.jsx)(`div`,{className:`ai-overlay-spinner`}),W===`ai`?`Generazione...`:W===`upload`?`Caricamento...`:`Creazione...`]}):W===`ai`?`🤖 Genera`:W===`upload`?`📎 Carica`:`📄 Crea File`})]})]})]})]})]})]})]})]}),(0,v.jsxs)(`div`,{className:`mappa-detail-panel`,children:[(0,v.jsxs)(`div`,{className:`sidebar-search-box`,children:[(0,v.jsx)(`span`,{className:`search-icon`,children:`🔍`}),(0,v.jsx)(`input`,{type:`text`,placeholder:`Cerca argomenti, moduli o file...`,value:D,onChange:e=>ne(e.target.value),className:`sidebar-search-input`}),D&&(0,v.jsx)(`button`,{className:`clear-search-btn`,onClick:()=>ne(``),children:`✕`})]}),(0,v.jsxs)(`div`,{className:`detail-body-scrollable`,children:[(0,v.jsxs)(`div`,{className:`explorer-section`,children:[(0,v.jsx)(`div`,{className:`explorer-section-header`,onClick:()=>se(!oe),children:(0,v.jsxs)(`span`,{children:[oe?`▼`:`▶`,` 🌐 ARGOMENTI PRINCIPALI (`,Tt.length,`)`]})}),oe&&(0,v.jsxs)(`div`,{className:`explorer-section-content`,children:[Et.length===0&&(0,v.jsx)(`div`,{style:{fontSize:`0.6rem`,color:`#5a5e72`,padding:`6px 10px`},children:`Nessun argomento trovato.`}),Et.map(e=>{let t=o.filter(t=>t.parent_id===e.id).length;return(0,v.jsxs)(`div`,{className:`explorer-topic-item ${h===e.id?`active`:``}`,onClick:()=>Ct(e),children:[(0,v.jsx)(`span`,{className:`explorer-topic-icon`,children:St(e.domain)}),(0,v.jsx)(`span`,{className:`explorer-topic-name`,children:Q(e.name)}),(0,v.jsx)(`span`,{className:`explorer-topic-count`,title:`${t} sottoargomenti`,children:t})]},e.id)})]})]}),$&&(0,v.jsxs)(`div`,{className:`explorer-section`,style:{borderBottom:`none`},children:[(0,v.jsxs)(`div`,{className:`detail-header`,children:[(0,v.jsx)(`div`,{className:`detail-type`,style:{color:`#bc8cff`},children:`ARGOMENTO ATTIVO`}),(0,v.jsx)(`div`,{className:`detail-title`,style:{color:`#bc8cff`,fontSize:`0.85rem`},children:Q($.name)}),$.description&&(0,v.jsx)(`div`,{className:`detail-desc`,style:{fontSize:`0.65rem`,marginTop:`4px`,color:`#5a5e72`},children:Q($.description)}),(0,v.jsxs)(`div`,{className:`active-topic-controls`,style:{display:`flex`,gap:`6px`,flexWrap:`wrap`,marginTop:`8px`,alignItems:`center`},children:[(0,v.jsx)(`button`,{className:`btn-new-subtopic`,onClick:()=>at($),title:`Crea nuovo sottoargomento dentro questo argomento`,style:{padding:`4px 8px`,fontSize:`0.6rem`,background:`rgba(0,210,255,0.12)`,color:`#00d2ff`,border:`1px solid rgba(0,210,255,0.3)`,borderRadius:`6px`,cursor:`pointer`,fontWeight:600},children:`➕ Nuovo Sottoargomento`}),o.length>1&&(0,v.jsxs)(`select`,{value:$.parent_id||``,onChange:e=>ut($,e.target.value),title:`Seleziona argomento padre`,style:{background:`#0e1016`,color:`#bc8cff`,border:`1px solid rgba(188,140,255,0.3)`,borderRadius:`6px`,padding:`3px 6px`,fontSize:`0.6rem`,outline:`none`},children:[(0,v.jsx)(`option`,{value:``,children:`— Nessun Padre —`}),o.filter(e=>e.id!==$.id).map(e=>(0,v.jsxs)(`option`,{value:e.id,children:[`⬆ Padre: `,Q(e.name)]},e.id))]})]})]}),(0,v.jsx)(`div`,{className:`explorer-section-header`,style:{marginTop:`12px`},children:(0,v.jsxs)(`span`,{children:[`📂 SOTTOARGOMENTI DI `,Q($.name).toUpperCase(),` (`,Dt.length,`)`]})}),(0,v.jsxs)(`div`,{className:`folder-tree`,children:[Dt.length===0&&(0,v.jsx)(`div`,{style:{fontSize:`0.6rem`,color:`#5a5e72`,padding:`8px 0`,fontStyle:`italic`},children:`Nessun sottoargomento presente. Clicca "➕ Nuovo Sottoargomento" per crearne uno.`}),Dt.map(t=>{let n=t.id,r=D?!0:re[n],i=p&&p.data?.id===t.id,a=()=>{O(e=>({...e,[n]:!e[n]})),m({type:`module`,data:t,topicId:t.id}),it(t.id)},o=0;[`teoria`,`scripts`,`test`,`viz`,`docs`,`whitepapers`,`pdf`,`media`].forEach(e=>{o+=(t[e]||[]).length});let s=t.folder||`data/${t.id}`;return(0,v.jsxs)(`div`,{className:`folder-item`,children:[(0,v.jsxs)(`div`,{className:`folder-header ${i?`selected-folder`:``}`,onClick:a,style:{background:i?`rgba(0,210,255,0.08)`:`transparent`,color:i?`#00d2ff`:`#8b8fa3`},children:[(0,v.jsxs)(`span`,{className:`folder-header-title`,children:[(0,v.jsx)(`span`,{children:r?`📂`:`📁`}),(0,v.jsx)(`span`,{children:Q(t.name)}),(0,v.jsxs)(`span`,{className:`folder-header-count`,children:[`(`,o,`)`]})]}),(0,v.jsxs)(`div`,{className:`folder-actions`,children:[(0,v.jsx)(`button`,{className:`folder-action-btn`,onClick:e=>{e.stopPropagation(),at(t)},title:`Crea sotto-sottoargomento dentro questo sottoargomento`,style:{color:`#00d2ff`,fontWeight:`bold`},children:`➕`}),(0,v.jsx)(`button`,{className:`folder-action-btn`,onClick:e=>{e.stopPropagation(),ct(t,$.id)},title:`Sposta sottoargomento in un altro Argomento`,children:`⇄`}),(0,v.jsx)(`button`,{className:`folder-action-btn`,onClick:e=>{e.stopPropagation(),pt(t,$.id)},title:`Rinomina Sottoargomento`,children:`✏️`}),(0,v.jsx)(`button`,{className:`folder-action-btn del`,onClick:e=>{e.stopPropagation(),dt(t,$.id)},title:`Elimina Sottoargomento`,children:`🗑️`})]})]}),r&&(0,v.jsxs)(`div`,{className:`folder-contents`,children:[o===0&&(0,v.jsx)(`div`,{style:{fontStyle:`italic`,color:`#5a5e72`,fontSize:`0.6rem`,padding:`6px 12px`},children:`Nessun file presente in questo sottoargomento.`}),wt.map(n=>{let r=t[n.key]||[];if(r.length===0)return null;let i=`${t.id}-${n.key}`,a=D?!0:ie[i],o=n.key===`whitepapers`?`whitepaper`:n.key;return(0,v.jsxs)(`div`,{className:`category-folder`,children:[(0,v.jsxs)(`div`,{className:`category-folder-header`,onClick:()=>{ae(e=>({...e,[i]:!e[i]}))},children:[(0,v.jsxs)(`span`,{style:{display:`flex`,alignItems:`center`,gap:`4px`,color:n.color},children:[(0,v.jsx)(`span`,{children:a?`📂`:`📁`}),(0,v.jsxs)(`span`,{children:[n.icon,` `,n.label]}),(0,v.jsxs)(`span`,{style:{fontSize:`0.5rem`,opacity:.6},children:[`(`,r.length,`)`]})]}),(0,v.jsx)(`div`,{className:`category-folder-actions`,children:(0,v.jsx)(`button`,{className:`category-folder-add-btn`,onClick:e=>{e.stopPropagation(),yt(s,o)},title:`Crea nuovo ${n.label}`,children:`➕`})})]}),a&&(0,v.jsxs)(`div`,{style:{paddingLeft:`12px`,display:`flex`,flexDirection:`column`,gap:`2px`},children:[r.length===0&&(0,v.jsx)(`div`,{style:{fontStyle:`italic`,color:`#5a5e72`,fontSize:`0.55rem`,padding:`2px 6px`},children:`Vuoto`}),r.map((t,r)=>{let i=typeof t==`string`?t:t.path||t.filePath,a=typeof t==`string`?t.split(`/`).pop():t.name||t.filename;return(0,v.jsxs)(`div`,{className:`file-tree-item`,children:[(0,v.jsx)(`span`,{className:`explorer-topic-icon`,style:{background:`none`,width:`auto`,height:`auto`},children:n.icon}),(0,v.jsx)(`span`,{className:`file-tree-name`,onClick:()=>e&&e(i),children:Q(a)}),(0,v.jsx)(`div`,{className:`file-tree-actions`,children:(0,v.jsx)(`button`,{className:`file-tree-del-btn`,onClick:e=>{e.stopPropagation(),mt(i)},title:`Elimina file`,children:`🗑️`})})]},i||r)})]})]},n.key)})]})]},t.id)})]})]})]})]})]})]})}var S={markdown:f,python:a,javascript:a,html:m,image:h,json:p,text:f};function C(){let[e,t]=(0,_.useState)({}),[n,r]=(0,_.useState)(!0),[a,o]=(0,_.useState)(null),[l,u]=(0,_.useState)(null),[p,m]=(0,_.useState)(``),[h,y]=(0,_.useState)(!1),[b,x]=(0,_.useState)(`code`),[C,w]=(0,_.useState)(!1),[T,ee]=(0,_.useState)(``),[E,te]=(0,_.useState)(!1),D=async()=>{r(!0);try{let e=await fetch(`/api/nodes`);if(e.ok){let n=await e.json();t(n.nodes||{});let r=Object.keys(n.nodes||{});r.length>0&&!a&&o(r[0])}}catch(e){console.error(`Error fetching knowledge nodes:`,e)}finally{r(!1)}};(0,_.useEffect)(()=>{D()},[]);let ne=async e=>{u(e),y(!0),m(``),e.type===`html`||e.name.endsWith(`.html`)?x(`app_runner`):x(`code`);try{let t=await fetch(`/api/view_file?file_path=${encodeURIComponent(e.path)}`);if(t.ok){let e=await t.text();m(e)}}catch(e){m(`// Error loading file: ${e.message}`)}finally{y(!1)}},re=async()=>{if(T.trim()){te(!0);try{let e=a?`${a}/${T.trim().toLowerCase().replace(/\s+/g,`_`)}`:T.trim().toLowerCase().replace(/\s+/g,`_`);(await fetch(`/api/nodes/create`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({node_path:e})})).ok&&(ee(``),w(!1),await D(),o(e))}catch(e){console.error(`Failed to create node:`,e)}finally{te(!1)}}},O=e[a]||null;return(0,v.jsxs)(`div`,{style:{background:`#0a0c14`,color:`#e2e4eb`,minHeight:`100%`,display:`flex`,flexDirection:`column`},children:[(0,v.jsx)(`div`,{style:{position:`relative`,zIndex:1,borderRadius:0,overflow:`hidden`,padding:`20px 32px 18px 32px`,minHeight:`100px`,borderBottom:`1px solid rgba(0, 210, 255, 0.25)`,boxShadow:`0 8px 32px rgba(0,0,0,0.4)`,backgroundImage:`linear-gradient(to right, rgba(28, 12, 4, 0.96) 35%, rgba(120, 45, 10, 0.6) 75%, rgba(234, 88, 12, 0.22) 100%), url("/images/hero_banner.jpg")`,backgroundSize:`cover`,backgroundRepeat:`no-repeat`,backgroundPosition:`center center`,marginBottom:`20px`,flexShrink:0},children:(0,v.jsxs)(`div`,{style:{position:`relative`,zIndex:2,display:`flex`,alignItems:`center`,justifyContent:`space-between`,flexWrap:`wrap`,gap:`16px`},children:[(0,v.jsxs)(`div`,{style:{maxWidth:`680px`},children:[(0,v.jsxs)(`div`,{style:{display:`inline-flex`,alignItems:`center`,gap:`6px`,padding:`3px 12px`,borderRadius:`14px`,background:`rgba(0, 210, 255, 0.15)`,border:`1px solid rgba(0, 210, 255, 0.35)`,color:`#00d2ff`,fontSize:`0.68rem`,fontWeight:800,letterSpacing:`1px`,textTransform:`uppercase`,marginBottom:`6px`},children:[(0,v.jsx)(c,{size:14}),` UNIVERSAL KNOWLEDGE GRAPH & APP EXPLORER`]}),(0,v.jsx)(`h1`,{style:{margin:`0 0 4px 0`,fontSize:`1.35rem`,fontWeight:800,color:`#fff`,letterSpacing:`-0.3px`},children:`🌐 Universal Knowledge Nodes & App Explorer`}),(0,v.jsx)(`p`,{style:{margin:0,fontSize:`0.78rem`,color:`#ffffff`,lineHeight:1.4},children:`Gestione nodi gerarchici universali, codice, documenti ed applicativi integrati in Sigma Studio.`})]}),(0,v.jsxs)(`div`,{style:{display:`flex`,gap:`10px`,alignItems:`center`},children:[(0,v.jsxs)(`button`,{onClick:D,style:{background:`rgba(255, 255, 255, 0.05)`,border:`1px solid rgba(255, 255, 255, 0.1)`,color:`#e2e4eb`,padding:`10px 16px`,borderRadius:`12px`,fontWeight:800,fontSize:`0.82rem`,cursor:`pointer`,display:`flex`,alignItems:`center`,gap:`6px`},children:[(0,v.jsx)(i,{size:15,className:n?`spin`:``}),(0,v.jsx)(`span`,{children:`Aggiorna Nodi`})]}),(0,v.jsxs)(`button`,{onClick:()=>w(!0),style:{background:`linear-gradient(135deg, #00d2ff, #0072ff)`,border:`none`,color:`#fff`,padding:`10px 18px`,borderRadius:`12px`,fontWeight:800,fontSize:`0.82rem`,cursor:`pointer`,display:`flex`,alignItems:`center`,gap:`6px`,boxShadow:`0 4px 16px rgba(0,210,255,0.3)`},children:[(0,v.jsx)(d,{size:15}),(0,v.jsx)(`span`,{children:`Nuovo Nodo / App Folder`})]})]})]})}),(0,v.jsx)(`div`,{style:{padding:`0 24px 24px 24px`,display:`flex`,flexDirection:`column`,gap:`20px`,flex:1},children:(0,v.jsxs)(`div`,{style:{display:`grid`,gridTemplateColumns:`300px 1fr`,gap:`20px`},children:[(0,v.jsxs)(`div`,{style:{background:`rgba(15, 17, 26, 0.8)`,border:`1px solid rgba(255, 255, 255, 0.08)`,borderRadius:`12px`,padding:`16px`,display:`flex`,flexDirection:`column`,gap:`10px`},children:[(0,v.jsxs)(`h3`,{style:{fontSize:`0.9rem`,margin:0,color:`#fff`,display:`flex`,alignItems:`center`,gap:`6px`},children:[(0,v.jsx)(g,{size:16,color:`#00d2ff`}),(0,v.jsx)(`span`,{children:`Albero Nodi di Conoscenza`})]}),(0,v.jsx)(`div`,{style:{display:`flex`,flexDirection:`column`,gap:`4px`,maxHeight:`550px`,overflowY:`auto`},children:Object.values(e).map(e=>{let t=a===e.id,n=!!e.parent_id;return(0,v.jsxs)(`div`,{onClick:()=>{o(e.id),u(null)},style:{padding:`8px 12px`,marginLeft:n?`16px`:`0px`,background:t?`rgba(0, 210, 255, 0.15)`:`rgba(255, 255, 255, 0.02)`,border:t?`1px solid rgba(0, 210, 255, 0.4)`:`1px solid rgba(255, 255, 255, 0.05)`,borderRadius:`8px`,cursor:`pointer`,display:`flex`,alignItems:`center`,justifyContent:`space-between`,transition:`all 0.2s ease`},children:[(0,v.jsxs)(`div`,{style:{display:`flex`,alignItems:`center`,gap:`8px`,overflow:`hidden`},children:[(0,v.jsx)(g,{size:15,color:e.has_app?`#50fa7b`:`#00d2ff`}),(0,v.jsx)(`span`,{style:{fontSize:`0.82rem`,color:t?`#fff`:`#c0c5d6`,fontWeight:t?700:500,overflow:`hidden`,textOverflow:`ellipsis`,whiteSpace:`nowrap`},children:e.name})]}),e.has_app&&(0,v.jsx)(`span`,{style:{fontSize:`0.65rem`,padding:`2px 6px`,background:`rgba(80, 250, 123, 0.15)`,color:`#50fa7b`,borderRadius:`6px`,fontWeight:600},children:`APP`})]},e.id)})})]}),(0,v.jsx)(`div`,{style:{background:`rgba(15, 17, 26, 0.8)`,border:`1px solid rgba(255, 255, 255, 0.08)`,borderRadius:`12px`,padding:`20px`,display:`flex`,flexDirection:`column`,gap:`16px`},children:O?(0,v.jsxs)(v.Fragment,{children:[(0,v.jsxs)(`div`,{style:{borderBottom:`1px solid rgba(255, 255, 255, 0.08)`,paddingBottom:`12px`,display:`flex`,justifyContent:`space-between`,alignItems:`center`},children:[(0,v.jsxs)(`div`,{children:[(0,v.jsxs)(`h2`,{style:{margin:0,fontSize:`1.2rem`,color:`#fff`,display:`flex`,alignItems:`center`,gap:`8px`},children:[(0,v.jsx)(`span`,{children:O.name}),(0,v.jsxs)(`span`,{style:{fontSize:`0.7rem`,color:`#8b8fa3`,fontFamily:`monospace`},children:[`(`,O.folder,`)`]})]}),(0,v.jsx)(`div`,{style:{fontSize:`0.8rem`,color:`#8b8fa3`,marginTop:`4px`},children:O.description})]}),O.has_app&&(0,v.jsx)(`div`,{style:{display:`flex`,gap:`8px`},children:(0,v.jsxs)(`button`,{onClick:()=>{let e=O.files.find(e=>e.type===`html`||e.is_entrypoint);e&&ne(e)},style:{background:`rgba(80, 250, 123, 0.15)`,border:`1px solid rgba(80, 250, 123, 0.3)`,color:`#50fa7b`,padding:`6px 12px`,borderRadius:`6px`,fontWeight:600,fontSize:`0.8rem`,cursor:`pointer`,display:`flex`,alignItems:`center`,gap:`6px`},children:[(0,v.jsx)(s,{size:14}),(0,v.jsx)(`span`,{children:`Esegui App del Nodo`})]})})]}),(0,v.jsxs)(`div`,{children:[(0,v.jsxs)(`div`,{style:{fontSize:`0.8rem`,color:`#8b8fa3`,marginBottom:`8px`,fontWeight:600},children:[`File & Applicativi Contenuti (`,O.files.length,`):`]}),(0,v.jsx)(`div`,{style:{display:`flex`,flexWrap:`wrap`,gap:`10px`},children:O.files.map(e=>{let t=l?.path===e.path,n=S[e.type]||f;return(0,v.jsxs)(`div`,{onClick:()=>ne(e),style:{background:t?`rgba(0, 210, 255, 0.15)`:`rgba(255, 255, 255, 0.03)`,border:t?`1px solid rgba(0, 210, 255, 0.4)`:`1px solid rgba(255, 255, 255, 0.08)`,borderRadius:`8px`,padding:`8px 12px`,cursor:`pointer`,display:`flex`,alignItems:`center`,gap:`8px`},children:[(0,v.jsx)(n,{size:16,color:e.type===`html`?`#50fa7b`:e.type===`python`?`#ff79c6`:`#00d2ff`}),(0,v.jsx)(`span`,{style:{fontSize:`0.82rem`,color:t?`#fff`:`#c0c5d6`},children:e.name})]},e.path)})})]}),l?(0,v.jsxs)(`div`,{style:{marginTop:`10px`,display:`flex`,flexDirection:`column`,gap:`10px`},children:[(0,v.jsxs)(`div`,{style:{display:`flex`,justifyContent:`space-between`,alignItems:`center`},children:[(0,v.jsxs)(`div`,{style:{fontSize:`0.85rem`,color:`#00d2ff`,fontWeight:600},children:[`Visualizzatore: `,l.name]}),(0,v.jsxs)(`div`,{style:{display:`flex`,gap:`8px`},children:[(0,v.jsx)(`button`,{onClick:()=>x(`code`),style:{background:b===`code`?`rgba(0, 210, 255, 0.2)`:`transparent`,border:`1px solid rgba(0, 210, 255, 0.3)`,color:`#00d2ff`,padding:`4px 10px`,borderRadius:`4px`,fontSize:`0.75rem`,cursor:`pointer`},children:`Codice / Testo`}),(l.type===`html`||l.name.endsWith(`.html`))&&(0,v.jsxs)(`button`,{onClick:()=>x(`app_runner`),style:{background:b===`app_runner`?`rgba(80, 250, 123, 0.2)`:`transparent`,border:`1px solid rgba(80, 250, 123, 0.3)`,color:`#50fa7b`,padding:`4px 10px`,borderRadius:`4px`,fontSize:`0.75rem`,cursor:`pointer`,display:`flex`,alignItems:`center`,gap:`4px`},children:[(0,v.jsx)(s,{size:12}),(0,v.jsx)(`span`,{children:`Esegui App Web Live`})]})]})]}),b===`app_runner`?(0,v.jsx)(`div`,{style:{border:`1px solid rgba(80, 250, 123, 0.3)`,borderRadius:`8px`,overflow:`hidden`,height:`400px`,background:`#fff`},children:(0,v.jsx)(`iframe`,{srcDoc:p,title:l.name,style:{width:`100%`,height:`100%`,border:`none`}})}):(0,v.jsx)(`pre`,{style:{background:`#05060a`,border:`1px solid rgba(255, 255, 255, 0.08)`,borderRadius:`8px`,padding:`14px`,color:`#f8f8f2`,fontSize:`0.8rem`,fontFamily:`monospace`,maxHeight:`400px`,overflowY:`auto`,whiteSpace:`pre-wrap`},children:h?`Caricamento contenuto...`:p})]}):(0,v.jsx)(`div`,{style:{color:`#8b8fa3`,fontSize:`0.85rem`,textAlign:`center`,padding:`40px 0`},children:`Seleziona un file dal nodo per aprirne il codice o avviarne l'applicazione.`})]}):(0,v.jsx)(`div`,{style:{color:`#8b8fa3`,fontSize:`0.85rem`,textAlign:`center`,padding:`60px 0`},children:`Nessun nodo selezionato.`})})]})}),C&&(0,v.jsx)(`div`,{style:{position:`fixed`,top:0,left:0,right:0,bottom:0,background:`rgba(0,0,0,0.7)`,display:`flex`,alignItems:`center`,justifyContent:`center`,zIndex:1e3},children:(0,v.jsxs)(`div`,{style:{background:`#0f111a`,border:`1px solid rgba(0, 210, 255, 0.3)`,borderRadius:`12px`,padding:`24px`,width:`400px`,display:`flex`,flexDirection:`column`,gap:`14px`},children:[(0,v.jsx)(`h3`,{style:{margin:0,color:`#fff`},children:`Crea Nuovo Nodo o Cartella App`}),(0,v.jsx)(`input`,{type:`text`,placeholder:`Nome del nodo (es. simulazioni_fisica)`,value:T,onChange:e=>ee(e.target.value),style:{background:`rgba(0,0,0,0.5)`,border:`1px solid rgba(255,255,255,0.1)`,borderRadius:`6px`,color:`#fff`,padding:`10px`,fontSize:`0.85rem`}}),(0,v.jsxs)(`div`,{style:{display:`flex`,justifyContent:`flex-end`,gap:`10px`},children:[(0,v.jsx)(`button`,{onClick:()=>w(!1),style:{background:`transparent`,border:`1px solid rgba(255,255,255,0.1)`,color:`#8b8fa3`,padding:`6px 12px`,borderRadius:`6px`,cursor:`pointer`},children:`Annulla`}),(0,v.jsx)(`button`,{onClick:re,disabled:E,style:{background:`linear-gradient(135deg, #00d2ff, #0072ff)`,border:`none`,color:`#fff`,padding:`6px 14px`,borderRadius:`6px`,fontWeight:600,cursor:`pointer`},children:`Crea Nodo`})]})]})})]})}function w({onOpenFile:e,openTab:t}){let[n,r]=(0,_.useState)(`mappa`);return(0,v.jsxs)(`div`,{style:{width:`100%`,height:`100%`,display:`flex`,flexDirection:`column`,overflow:`hidden`},children:[(0,v.jsx)(o,{icon:l,title:`Argomenti & Conoscenza`,highlight:`KNOWLEDGE GRAPH`,tabs:[{id:`mappa`,label:`Mappa Relazionale D3`,icon:l,active:n===`mappa`,onClick:()=>r(`mappa`)},{id:`nodes`,label:`Universal Knowledge Nodes`,icon:c,active:n===`nodes`,onClick:()=>r(`nodes`)}],description:`Mappa concettuale interattiva D3, ontologia della conoscenza e nodi universali`}),(0,v.jsx)(`div`,{style:{flex:1,minHeight:0,overflow:`hidden`},children:n===`mappa`?(0,v.jsx)(x,{onOpenFile:e}):(0,v.jsx)(C,{})})]})}export{w as default};