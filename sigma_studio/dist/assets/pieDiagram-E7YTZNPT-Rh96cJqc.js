import{n as e}from"./chunk-Y2CYZVJY-DsF7k-Jl.js";import{t}from"./chunk-X3CZISLH-ChyOdCnY.js";import{H as n,K as r,U as i,a,c as o,f as s,v as c,w as l,x as u,y as d}from"./chunk-DU6HZSFF-D09URSq5.js";import{U as f,w as p,x as m}from"./src-Cfreso1X.js";import{i as h,p as g}from"./chunk-75Z2AOVW-DXMYWSQa.js";import{Mt as _}from"./index-Bl0G2K_i.js";import{n as v}from"./mermaid-parser.core-DK0kgowR.js";import{t as y}from"./chunk-JWPE2WC7-DVXcaiue.js";var b=s.pie,x={sections:new Map,showData:!1,config:b},S=x.sections,C=x.showData,w=structuredClone(b),T={getConfig:e(()=>structuredClone(w),`getConfig`),clear:e(()=>{S=new Map,C=x.showData,a()},`clear`),setDiagramTitle:r,getDiagramTitle:l,setAccTitle:i,getAccTitle:d,setAccDescription:n,getAccDescription:c,addSection:e(({label:e,value:n})=>{if(n<0)throw Error(`"${e}" has invalid value: ${n}. Negative values are not allowed in pie charts. All slice values must be >= 0.`);S.has(e)||(S.set(e,n),t.debug(`added new section: ${e}, with value: ${n}`))},`addSection`),getSections:e(()=>S,`getSections`),setShowData:e(e=>{C=e},`setShowData`),getShowData:e(()=>C,`getShowData`)},E=e((e,t)=>{y(e,t),t.setShowData(e.showData),e.sections.map(t.addSection)},`populateDb`),D={parse:e(async e=>{let n=await v(`pie`,e);t.debug(n),E(n,T)},`parse`)},O=e(e=>`
  .pieCircle{
    stroke: ${e.pieStrokeColor};
    stroke-width : ${e.pieStrokeWidth};
    opacity : ${e.pieOpacity};
  }
  .pieCircle.highlighted{
    scale: 1.05;
    opacity: 1;
  }
  .pieCircle.highlightedOnHover:hover{
    transition-duration: 250ms;
    scale: 1.05;
    opacity: 1;
  }
  .pieOuterCircle{
    stroke: ${e.pieOuterStrokeColor};
    stroke-width: ${e.pieOuterStrokeWidth};
    fill: none;
  }
  .pieTitleText {
    text-anchor: middle;
    font-size: ${e.pieTitleTextSize};
    fill: ${e.pieTitleTextColor};
    font-family: ${e.fontFamily};
  }
  .slice {
    font-family: ${e.fontFamily};
    fill: ${e.pieSectionTextColor};
    font-size:${e.pieSectionTextSize};
    // fill: white;
  }
  .legend text {
    fill: ${e.pieLegendTextColor};
    font-family: ${e.fontFamily};
    font-size: ${e.pieLegendTextSize};
  }
`,`getStyles`),k=e(e=>{let t=[...e.values()].reduce((e,t)=>e+t,0),n=[...e.entries()].map(([e,t])=>({label:e,value:t})).filter(e=>e.value/t*100>=1);return m().value(e=>e.value).sort(null)(n)},`createPieArcs`),A={parser:D,db:T,renderer:{draw:e((e,n,r,i)=>{t.debug(`rendering pie chart
`+e);let a=i.db,s=u(),c=h(a.getConfig(),s.pie),l=_(n),d=l.append(`g`);d.attr(`transform`,`translate(225,225)`);let{themeVariables:m}=s,[v]=g(m.pieOuterStrokeWidth);v??=2;let y=c.legendPosition,b=c.textPosition,x=c.donutHole>0&&c.donutHole<=.9?c.donutHole:0,S=p().innerRadius(x*185).outerRadius(185),C=p().innerRadius(185*b).outerRadius(185*b),w=d.append(`g`);w.append(`circle`).attr(`cx`,0).attr(`cy`,0).attr(`r`,185+v/2).attr(`class`,`pieOuterCircle`);let T=a.getSections(),E=k(T),D=[m.pie1,m.pie2,m.pie3,m.pie4,m.pie5,m.pie6,m.pie7,m.pie8,m.pie9,m.pie10,m.pie11,m.pie12],O=0;T.forEach(e=>{O+=e});let A=E.filter(e=>(e.data.value/O*100).toFixed(0)!==`0`),j=f(D).domain([...T.keys()]);w.selectAll(`mySlices`).data(A).enter().append(`path`).attr(`d`,S).attr(`fill`,e=>j(e.data.label)).attr(`class`,e=>{let t=`pieCircle`;return c.highlightSlice===`hover`?t+=` highlightedOnHover`:c.highlightSlice===e.data.label&&(t+=` highlighted`),t}),w.selectAll(`mySlices`).data(A).enter().append(`text`).text(e=>(e.data.value/O*100).toFixed(0)+`%`).attr(`transform`,e=>`translate(`+C.centroid(e)+`)`).style(`text-anchor`,`middle`).attr(`class`,`slice`);let M=d.append(`text`).text(a.getDiagramTitle()).attr(`x`,0).attr(`y`,-200).attr(`class`,`pieTitleText`),N=[...T.entries()].map(([e,t])=>({label:e,value:t})),P=d.selectAll(`.legend`).data(N).enter().append(`g`).attr(`class`,`legend`);P.append(`rect`).attr(`width`,18).attr(`height`,18).style(`fill`,e=>j(e.label)).style(`stroke`,e=>j(e.label)),P.append(`text`).attr(`x`,22).attr(`y`,14).text(e=>a.getShowData()?`${e.label} [${e.value}]`:e.label);let F=Math.max(...P.selectAll(`text`).nodes().map(e=>e?.getBoundingClientRect().width??0)),I=450,L=490,R=N.length*22;switch(y){case`center`:P.attr(`transform`,(e,t)=>{let n=22*N.length/2,r=-F/2-22,i=t*22-n;return`translate(`+r+`,`+i+`)`});break;case`top`:I+=R,P.attr(`transform`,(e,t)=>`translate(${-F/2-22}, ${t*22-185})`),w.attr(`transform`,()=>`translate(0, ${R+22})`);break;case`bottom`:I+=R,P.attr(`transform`,(e,t)=>{let n=-F/2-22,r=t*22- -207;return`translate(`+n+`,`+r+`)`});break;case`left`:L+=22+F,P.attr(`transform`,(e,t)=>{let n=22*N.length/2;return`translate(-207,`+(t*22-n)+`)`}),w.attr(`transform`,()=>`translate(${F+18+4}, 0)`);break;default:L+=22+F,P.attr(`transform`,(e,t)=>{let n=22*N.length/2;return`translate(216,`+(t*22-n)+`)`})}let z=M.node()?.getBoundingClientRect().width??0,B=225-z/2,V=225+z/2,H=Math.min(0,B),U=Math.max(L,V)-H;l.attr(`viewBox`,`${H} 0 ${U} ${I}`),o(l,I,U,c.useMaxWidth)},`draw`)},styles:O};export{A as diagram};