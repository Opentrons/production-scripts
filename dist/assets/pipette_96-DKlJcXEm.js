import{d as T,b as u,o as f,a as x,w as t,f as e,g as s,r as m,N as A,C as G,y as U,e as _,u as c,I,V as H,Q as y,F as Q,L as j,t as q,M as J,v as W,x as X,P as Y,_ as Z}from"./index-DSXcx6Pv.js";import{$ as ee}from"./utils-Cj5XumDE.js";import{a as te,b as le}from"./request-Cfy3JS2Z.js";const N=T({__name:"CommandTable",props:{tableData:{default:[]},production:{default:""}},setup(d){const i=()=>{console.log("click")},r=d;return console.log(r.tableData,r.production),(V,C)=>{const l=u("el-table-column"),b=u("el-button"),w=u("el-table");return f(),x(w,{data:r.tableData,style:{width:"100%"}},{default:t(()=>[e(l,{fixed:"",prop:"date",label:"Date",width:"150"}),e(l,{prop:"auth",label:"作者",width:"120"}),e(l,{prop:"robot_name",label:"机器名",width:"120"}),e(l,{prop:"device_ip",label:"设备IP",width:"120"}),e(l,{prop:"cmd",label:"运行命令",width:"600"}),e(l,{prop:"params",label:"参数",width:"500"}),e(l,{prop:"use_key",label:"密钥",width:"120"}),e(l,{prop:"description",label:"说明",width:"120"}),e(l,{prop:"id",label:"Id",width:"120"}),e(l,{fixed:"right",label:"Operations",width:"160"},{default:t(()=>[e(b,{link:"",type:"primary",size:"small",onClick:i},{default:t(()=>[s("Detail")]),_:1}),e(b,{link:"",type:"primary",size:"small"},{default:t(()=>[s("Edit")]),_:1}),e(b,{link:"",type:"primary",size:"small",onClick:i},{default:t(()=>[s("Run")]),_:1})]),_:1})]),_:1},8,["data"])}}}),ae=async d=>await le("/tests/create/run",d),oe=async d=>await te("/tests/get/runs",d),z=d=>(W("data-v-7c618ce5"),d=d(),X(),d),ne={class:"main-box"},se={class:"left-box"},ue={class:"dialog-footer"},de={class:"test4-mian"},ie=z(()=>_("div",{class:"test4-top"},null,-1)),re={class:"test4-content"},pe=z(()=>_("div",{class:"right-box"},null,-1)),R="96ch",ce=T({__name:"pipette_96",setup(d){const i=m(["--chnannel 8","--update","--operator Andy"]),r=m(""),V=m(!1),C=m();let l=m(!1);const b=ee(),w=m([]),n=A({date:b,auth:"default",robot_name:"",device_ip:"192.168.6.11",cmd:"",params:i.value,use_key:!0,description:"",production:R,type:[]}),D=async()=>{let v=await oe({type:"96ch"});v.success&&(w.value=v.data)};D(),G(()=>{});const B=v=>{i.value.splice(i.value.indexOf(v),1)},$=()=>{r.value&&i.value.push(r.value),V.value=!1,r.value=""},F=()=>{V.value=!0,Y(()=>{C.value.input.focus()})},P=async()=>{await ae(n),D(),l.value=!1};return(v,o)=>{const h=u("el-button"),p=u("el-form-item"),E=u("el-switch"),g=u("el-checkbox"),S=u("el-checkbox-group"),K=u("el-tag"),L=u("el-form"),M=u("el-dialog"),k=u("el-tab-pane"),O=u("el-tabs");return f(),U("div",ne,[_("div",se,[e(h,{type:"primary",icon:c(H),onClick:o[0]||(o[0]=a=>I(l)?l.value=!0:l=!0),style:{margin:"10px"}},{default:t(()=>[s("新建")]),_:1},8,["icon"]),e(M,{modelValue:c(l),"onUpdate:modelValue":o[9]||(o[9]=a=>I(l)?l.value=a:l=a),title:"新建运行",width:"500"},{footer:t(()=>[_("div",ue,[e(h,{onClick:o[8]||(o[8]=a=>I(l)?l.value=!1:l=!1)},{default:t(()=>[s("Cancel")]),_:1}),e(h,{type:"primary",onClick:P},{default:t(()=>[s(" Confirm ")]),_:1})])]),default:t(()=>[e(L,{model:n,"label-width":"auto",style:{"max-width":"600px"}},{default:t(()=>[e(p,{label:"机器名"},{default:t(()=>[e(c(y),{modelValue:n.robot_name,"onUpdate:modelValue":o[1]||(o[1]=a=>n.robot_name=a)},null,8,["modelValue"])]),_:1}),e(p,{label:"设备IP"},{default:t(()=>[e(c(y),{modelValue:n.device_ip,"onUpdate:modelValue":o[2]||(o[2]=a=>n.device_ip=a)},null,8,["modelValue"])]),_:1}),e(p,{label:"使用密钥"},{default:t(()=>[e(E,{modelValue:n.use_key,"onUpdate:modelValue":o[3]||(o[3]=a=>n.use_key=a)},null,8,["modelValue"])]),_:1}),e(p,{label:"添加类别"},{default:t(()=>[e(S,{modelValue:n.type,"onUpdate:modelValue":o[4]||(o[4]=a=>n.type=a)},{default:t(()=>[e(g,{value:"diagnostic",name:"type"},{default:t(()=>[s(" 诊断测试 ")]),_:1}),e(g,{value:"protocol",name:"type"},{default:t(()=>[s(" 协议测试 ")]),_:1}),e(g,{value:"gravimetric",name:"type"},{default:t(()=>[s(" 容量测试 ")]),_:1}),e(g,{value:"lifetime",name:"type"},{default:t(()=>[s(" 老化测试 ")]),_:1})]),_:1},8,["modelValue"])]),_:1}),e(p,{label:"运行命令"},{default:t(()=>[e(c(y),{modelValue:n.cmd,"onUpdate:modelValue":o[5]||(o[5]=a=>n.cmd=a)},null,8,["modelValue"])]),_:1}),e(p,{label:"参数"},{default:t(()=>[_("div",null,[(f(!0),U(Q,null,j(i.value,a=>(f(),x(K,{key:a,closable:"","disable-transitions":!1,onClose:_e=>B(a),style:{"margin-right":"10px"}},{default:t(()=>[s(q(a),1)]),_:2},1032,["onClose"]))),128)),V.value?(f(),x(c(y),{key:0,ref_key:"InputRef",ref:C,modelValue:r.value,"onUpdate:modelValue":o[6]||(o[6]=a=>r.value=a),class:"w-20",size:"small",onKeyup:J($,["enter"]),onBlur:$},null,8,["modelValue"])):(f(),x(h,{key:1,class:"button-new-tag",size:"small",onClick:F},{default:t(()=>[s(" + New Tag ")]),_:1}))])]),_:1}),e(p,{label:"详情"},{default:t(()=>[e(c(y),{modelValue:n.description,"onUpdate:modelValue":o[7]||(o[7]=a=>n.description=a),type:"textarea"},null,8,["modelValue"])]),_:1}),e(p)]),_:1},8,["model"])]),_:1},8,["modelValue"]),e(O,{type:"border-card"},{default:t(()=>[e(k,{label:"诊断测试"},{default:t(()=>[e(N)]),_:1}),e(k,{label:"Protocol 测试"},{default:t(()=>[s(" Protocol ")]),_:1}),e(k,{label:"容量测试"},{default:t(()=>[s(" Grav ")]),_:1}),e(k,{label:"老化测试"},{default:t(()=>[_("div",de,[ie,_("div",re,[e(N,{tableData:w.value,production:R},null,8,["tableData"])])])]),_:1})]),_:1})]),pe])}}}),ve=Z(ce,[["__scopeId","data-v-7c618ce5"]]);export{ve as default};