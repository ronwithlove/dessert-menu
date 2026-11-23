const fs=require('fs');
const html=fs.readFileSync(process.argv[3],'utf8');
const m=html.match(/<script>([\s\S]*?)<\/script>/);
let js=m[1];
const cut=js.indexOf("const $=id=>document.getElementById(id);");
js=js.slice(0,cut);
js+=`
const out={};
for(const rid of ['cake','cookie']){
  RID=rid;R=RECIPES[rid];
  for(const n of R.opts){N=n;build();
    B.forEach(b=>{const key=b.v+'|'+b.i;(out[key]=out[key]||{v:b.v,i:b.i,recipes:new Set()}).recipes.add(rid+':'+n)})}
}
module.exports=Object.entries(out).map(([k,o])=>({key:k,v:o.v,i:o.i,where:[...o.recipes]}));
}
`;
fs.writeFileSync('/tmp/_ex.js',js);
const res=require('/tmp/_ex.js');
fs.writeFileSync(process.argv[2],JSON.stringify(res.map(r=>({key:r.key,v:r.v,i:r.i})),null,1));
for(const r of res)console.log(r.key.padEnd(24),r.where.length);
console.log(res.length);
