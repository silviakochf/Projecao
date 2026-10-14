let vagasCarregadas=false,alunosCarregados=false,allVagas=[],estaduaisRows=[],progressaoData=[];

document.addEventListener('DOMContentLoaded',async()=>{
    await carregarEstaduals();
    await carregarResumoVagas();
});

function atualizarPassos(){
    ['2','3','4'].forEach(n=>{
        const unlocked=n==='2'?vagasCarregadas:alunosCarregados;
        document.getElementById('num'+n)?.classList.toggle('pending',!unlocked);
        document.getElementById('num'+n)?.classList.toggle('done',unlocked);
        document.getElementById('block'+n)?.classList.toggle('pending',!unlocked);
    });
}

async function importarPDF(input){
    const file=input.files[0];if(!file)return;
    const status=document.getElementById('pdf-status');
    status.innerHTML='<i class="fas fa-spinner fa-spin"></i> Processando PDF...';
    const fd=new FormData();fd.append('file',file);
    try{
        const d=await postForm('/api/importar_vagas_pdf',fd);
        if(d.success){
            status.innerHTML=`<span style="color:#065f46">✅ ${d.escolas} escolas | ${d.total_vagas_disponiveis} vagas disponíveis</span>`;
            vagasCarregadas=true;
            document.getElementById('num1')?.classList.add('done');
            await carregarResumoVagas();atualizarPassos();toast('PDF importado!');
        }else{status.innerHTML=`<span style="color:#991b1b">❌ ${d.error}</span>`;toast('Erro',false);}
    }catch(e){status.innerHTML=`<span style="color:#991b1b">❌ ${e.message}</span>`;}
}

function addRowEstadual(data={}){
    const id=Date.now()+Math.random();estaduaisRows.push(id);
    const div=document.createElement('div');div.id=`est-${id}`;
    div.style.cssText='display:grid;grid-template-columns:2fr 1fr 90px 90px auto;gap:.4rem;align-items:center;margin-bottom:.35rem';
    div.innerHTML=`
        <input class="form-input" style="font-size:.82rem" placeholder="Nome escola estadual" value="${data.escola||''}" id="est-e-${id}"/>
        <input class="form-input" style="font-size:.82rem" placeholder="Série (1º ANO)" value="${data.serie||''}" id="est-s-${id}"/>
        <input class="form-input" style="font-size:.82rem" type="number" min="0" placeholder="Manhã" value="${data.manha||0}" id="est-m-${id}"/>
        <input class="form-input" style="font-size:.82rem" type="number" min="0" placeholder="Tarde" value="${data.tarde||0}" id="est-t-${id}"/>
        <button class="btn btn-red btn-sm" onclick="removeEst('est-${id}','${id}')"><i class="fas fa-trash"></i></button>`;
    document.getElementById('estaduais-rows')?.appendChild(div);
}

function removeEst(divId,id){
    document.getElementById(divId)?.remove();
    estaduaisRows=estaduaisRows.filter(r=>String(r)!==String(id));
}

async function carregarEstaduals(){
    try{
        const d=await(await fetch('/api/get_vagas_estaduais')).json();
        document.getElementById('estaduais-rows').innerHTML='';estaduaisRows=[];
        for(const[escola,series]of Object.entries(d))
            for(const[serie,turnos]of Object.entries(series))
                addRowEstadual({escola,serie,manha:turnos['MANHÃ']||0,tarde:turnos['TARDE']||0});
        if(Object.keys(d).length>0){vagasCarregadas=true;atualizarPassos();}
    }catch(e){console.error(e);}
}

async function salvarEstaduals(){
    const data={};
    for(const id of estaduaisRows){
        const escola=document.getElementById(`est-e-${id}`)?.value.trim();
        const serie=document.getElementById(`est-s-${id}`)?.value.trim();
        const manha=parseInt(document.getElementById(`est-m-${id}`)?.value)||0;
        const tarde=parseInt(document.getElementById(`est-t-${id}`)?.value)||0;
        if(!escola||!serie)continue;
        data[escola]=data[escola]||{};data[escola][serie]={};
        if(manha>0)data[escola][serie]['MANHÃ']=manha;
        if(tarde>0)data[escola][serie]['TARDE']=tarde;
    }
    const d=await postJSON('/api/salvar_vagas_estaduais',data);
    if(d.success){vagasCarregadas=true;document.getElementById('num1')?.classList.add('done');await carregarResumoVagas();atualizarPassos();toast('✅ Salvo!');}
    else toast('❌ Erro',false);
}

async function carregarResumoVagas(){
    try{
        const d=await(await fetch('/api/get_resumo_vagas')).json();
        allVagas=[...d.municipais.map(v=>({...v,tipo:'MUNICIPAL'})),...d.estaduais.map(v=>({...v,tipo:'ESTADUAL'}))];
        if(allVagas.length>0){document.getElementById('vagas-resumo-card').style.display='';vagasCarregadas=true;atualizarPassos();}
        renderVagasGrid(allVagas);
    }catch(e){console.error(e);}
}

function renderVagasGrid(vagas){
    const porSerie={};
    for(const v of vagas){
        if(!porSerie[v.serie])porSerie[v.serie]={total:0,escolas:0};
        porSerie[v.serie].total+=v.vagas_disponiveis;
        if(v.vagas_disponiveis>0)porSerie[v.serie].escolas++;
    }
    const grid=document.getElementById('vagas-resumo-grid');if(!grid)return;
    grid.innerHTML=Object.entries(porSerie).sort((a,b)=>b[1].total-a[1].total)
        .map(([serie,info])=>`<div class="vaga-card">
            <div class="vaga-serie">${serie}</div>
            <div class="vaga-num ${info.total===0?'zero':''}">${info.total}</div>
            <div class="vaga-escolas">${info.escolas} escola(s) c/ vaga</div>
        </div>`).join('');
}

function filtrarResumoPor(f){
    renderVagasGrid(f?allVagas.filter(v=>v.serie.toUpperCase().includes(f.toUpperCase())):allVagas);
}

async function importarAlunos(input){
    const file=input.files[0];if(!file)return;
    const status=document.getElementById('alunos-status');
    status.innerHTML='<i class="fas fa-spinner fa-spin"></i> Processando...';
    const fd=new FormData();fd.append('file',file);
    try{
        const d=await postForm('/api/importar_alunos_html',fd);
        if(d.success){
            status.innerHTML=`<span style="color:#065f46">✅ ${d.total_alunos} alunos | ${d.escolas.join(', ')}</span>`;
            if(d.escolas.length===1){const el=document.getElementById('escola-origem');if(el)el.value=d.escolas[0];}
            alunosCarregados=true;document.getElementById('num2')?.classList.add('done');atualizarPassos();toast('Alunos importados!');
        }else{status.innerHTML=`<span style="color:#991b1b">❌ ${d.error}</span>`;}
    }catch(e){status.innerHTML=`<span style="color:#991b1b">❌ ${e.message}</span>`;}
}

async function analisarProgressao(){
    const escola=document.getElementById('escola-origem')?.value.trim();
    const bairro=document.getElementById('bairro-origem')?.value;
    const series=Array.from(document.querySelectorAll('input[type=checkbox]:checked')).map(c=>c.value);
    if(!escola){toast('Informe a escola',false);return;}
    if(!bairro){toast('Selecione o bairro',false);return;}
    if(!series.length){toast('Selecione uma série',false);return;}
    const btn=document.getElementById('btn-analisar');
    btnLoading(btn,'Analisando...');
    const status=document.getElementById('analise-status');
    status.innerHTML='⏳ A IA está verificando vagas e sugerindo escolas...';
    try{
        const d=await postJSON('/api/analisar_progressao',{escola_origem:escola,bairro,series_progressao:series});
        if(d.success){
            progressaoData=d.turmas;
            status.innerHTML=`<span style="color:#065f46">✅ ${d.total_turmas} turmas | ${d.total_alunos} alunos</span>`;
            ['3','4'].forEach(n=>{document.getElementById('num'+n)?.classList.add('done');document.getElementById('block'+n)?.classList.remove('pending');});
            renderResultado(d.turmas);toast('Análise concluída!');
        }else{status.innerHTML=`<span style="color:#991b1b">❌ ${d.error}</span>`;toast('Erro: '+d.error,false);}
    }catch(e){status.innerHTML=`<span style="color:#991b1b">❌ ${e.message}</span>`;}
    finally{btnRestore(btn);}
}

function renderResultado(turmas){
    const sv=turmas.filter(t=>!t.escola_sugerida).length;
    const cv=turmas.filter(t=>t.escola_sugerida).length;
    const mb=turmas.filter(t=>t.escola_sugerida?.mesmo_bairro).length;
    const ta=turmas.reduce((s,t)=>s+t.total_alunos,0);
    const stats=document.getElementById('prog-stats');
    if(stats)stats.innerHTML=`
        <div class="stat"><div class="stat-num">${turmas.length}</div><div class="stat-label">Turmas</div></div>
        <div class="stat"><div class="stat-num">${ta}</div><div class="stat-label">Alunos</div></div>
        <div class="stat"><div class="stat-num" style="color:#065f46">${cv}</div><div class="stat-label">Com vaga</div></div>
        <div class="stat"><div class="stat-num" style="color:#1e40af">${mb}</div><div class="stat-label">Mesmo bairro</div></div>
        <div class="stat"><div class="stat-num" style="color:#991b1b">${sv}</div><div class="stat-label">Sem vaga</div></div>`;
    const lista=document.getElementById('alocacoes-lista');if(!lista)return;
    lista.innerHTML=turmas.map((t,i)=>{
        const sug=t.escola_sugerida;
        return `<div class="aloc-row ${sug?'':'sem-vaga'}" onclick="toggleAlunos(${i})">
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem">
                <div>
                    <span class="turma-info">${t.turma||t.serie_atual}</span>
                    <span style="color:#94a3b8;margin:0 .4rem">→</span>
                    <span style="font-weight:700;color:#2563eb">${t.serie_destino}</span>
                    <span style="margin-left:.5rem;font-size:.78rem;color:#64748b">${t.turno}</span>
                </div>
                <span style="background:#e2e8f0;padding:.15rem .5rem;border-radius:4px;font-size:.78rem">${t.total_alunos} alunos</span>
            </div>
            <div class="escola-dest" style="margin-top:.3rem">
                ${sug?`<i class="fas fa-school"></i> <strong>${sug.escola}</strong>
                    <span style="margin-left:.5rem;font-size:.75rem;color:#64748b">${sug.tipo} · ${sug.bairro} · ${sug.vagas_disponiveis} vagas</span>
                    ${sug.mesmo_bairro?'<span class="badge badge-green" style="margin-left:.4rem">✅ Mesmo bairro</span>':'<span class="badge badge-yellow" style="margin-left:.4rem">🔄 Próximo</span>'}`:
                    `<i class="fas fa-exclamation-triangle"></i> <strong>Sem vaga para ${t.serie_destino}</strong>`}
            </div>
            <div id="alunos-${i}" style="display:none;margin-top:.5rem">
                <div style="display:flex;flex-wrap:wrap;gap:.25rem">
                    ${(t.alunos||[]).map(a=>`<span style="background:#f1f5f9;padding:.1rem .4rem;border-radius:4px;font-size:.75rem">${a.nome}</span>`).join('')}
                </div>
                ${t.sugestoes?.length>1?`<div style="margin-top:.4rem;font-size:.78rem;color:#64748b">Outras: ${t.sugestoes.slice(1,4).map(s=>`${s.escola} (${s.vagas_disponiveis}v)`).join(' · ')}</div>`:''}
            </div>
        </div>`;
    }).join('');
}

function toggleAlunos(i){const el=document.getElementById(`alunos-${i}`);if(el)el.style.display=el.style.display==='none'?'':'none';}

async function exportarDrive(){
    const escola=document.getElementById('escola-origem')?.value.trim()||'';
    const bairro=document.getElementById('bairro-origem')?.value||'';
    const btn=event.target.closest('button');btnLoading(btn,'Enviando...');
    try{
        const r=await fetch('/api/exportar_excel_progressao',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({escola_origem:escola,bairro})});
        const ct=r.headers.get('content-type')||'';
        if(ct.includes('application/json')){const d=await r.json();if(d.success)toast('✅ Excel enviado!');else toast('❌ '+d.error,false);}
        else{const blob=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`progressao_${escola}.xlsx`.replace(/\s+/g,'_');a.click();URL.revokeObjectURL(a.href);toast('✅ Excel baixado!');}
    }catch(e){toast('❌ '+e.message,false);}finally{btnRestore(btn);}
}

async function baixarExcel(){
    const escola=document.getElementById('escola-origem')?.value.trim()||'';
    const bairro=document.getElementById('bairro-origem')?.value||'';
    try{await downloadBlob('/api/baixar_excel_progressao',{escola_origem:escola,bairro},`progressao_${escola||'salas'}.xlsx`.replace(/\s+/g,'_'));}
    catch(e){toast('❌ '+e.message,false);}
}

async function baixarExcelVagas(){
    const escola=document.getElementById('escola-origem')?.value.trim()||'Secretaria';
    try{await downloadBlob('/api/exportar_excel_vagas',{escola_origem:escola},`vagas_${new Date().toISOString().slice(0,10)}.xlsx`);toast('✅ Excel vagas baixado!');}
    catch(e){toast('❌ '+e.message,false);}
}
