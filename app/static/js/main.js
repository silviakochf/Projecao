let _tt;
function toast(msg,ok=true){
    const el=document.getElementById('toast');
    if(!el)return;
    el.textContent=msg;
    el.style.background=ok?'#0a192f':'#dc2626';
    el.classList.add('show');
    clearTimeout(_tt);
    _tt=setTimeout(()=>el.classList.remove('show'),3200);
}
document.addEventListener('DOMContentLoaded',()=>{
    document.querySelectorAll('.dropzone').forEach(zone=>{
        zone.addEventListener('dragover',e=>{e.preventDefault();zone.classList.add('drag')});
        zone.addEventListener('dragleave',()=>zone.classList.remove('drag'));
        zone.addEventListener('drop',e=>{
            e.preventDefault();zone.classList.remove('drag');
            const input=zone.querySelector('input[type=file]');
            if(input&&e.dataTransfer.files.length){
                try{const dt=new DataTransfer();dt.items.add(e.dataTransfer.files[0]);input.files=dt.files;}catch(ex){}
                input.dispatchEvent(new Event('change'));
            }
        });
    });
});
async function postJSON(url,body){
    const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    return r.json();
}
async function postForm(url,fd){
    const r=await fetch(url,{method:'POST',body:fd});
    return r.json();
}
async function downloadBlob(url,body,filename){
    const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!r.ok)throw new Error('HTTP '+r.status);
    const blob=await r.blob();
    const a=document.createElement('a');
    a.href=URL.createObjectURL(blob);a.download=filename;a.click();URL.revokeObjectURL(a.href);
}
function btnLoading(btn,msg='Aguarde...'){btn._orig=btn.innerHTML;btn.disabled=true;btn.innerHTML=`<i class="fas fa-spinner fa-spin"></i> ${msg}`;}
function btnRestore(btn){btn.disabled=false;btn.innerHTML=btn._orig||btn.innerHTML;}
