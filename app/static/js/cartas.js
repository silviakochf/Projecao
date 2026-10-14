document.addEventListener('DOMContentLoaded',()=>{
    const el=document.getElementById('cfg-data');
    if(el&&!el.value)el.value=new Date().toLocaleDateString('pt-BR',{day:'numeric',month:'long',year:'numeric'});
});

async function previsaoCartas(){
    try{
        const d=await postJSON('/api/analisar_progressao',{escola_origem:'',bairro:'',
            series_progressao:['GT 5','GT 4','GT 3','GT 2','GT 1','5º ANO','8º ANO','9º ANO']});
        if(!d.success||!d.turmas?.length){toast('Execute a análise na aba Progressão primeiro',false);return;}
        const porEscola={};
        for(const t of d.turmas){
            const sug=t.escola_sugerida;if(!sug)continue;
            const key=`${sug.escola}||${t.serie_destino}||${t.turno}`;
            if(!porEscola[key])porEscola[key]={escola:sug.escola,serie:t.serie_destino,turno:t.turno,alunos:0,turmas:0};
            porEscola[key].alunos+=t.total_alunos;porEscola[key].turmas++;
        }
        const lista=Object.values(porEscola);
        const card=document.getElementById('previa-card');
        const prev=document.getElementById('previa-lista');
        card.style.display='';
        if(!lista.length){prev.innerHTML='<p style="color:#991b1b">Nenhuma sugestão disponível.</p>';return;}
        prev.innerHTML=`<div class="table-wrap" style="max-height:300px"><table>
            <thead><tr><th>Escola Destino</th><th>Série</th><th>Turno</th><th style="text-align:center">Turmas</th><th style="text-align:center">Alunos</th></tr></thead>
            <tbody>${lista.map(l=>`<tr><td style="font-weight:500">${l.escola}</td><td>${l.serie}</td><td>${l.turno}</td><td style="text-align:center">${l.turmas}</td><td style="text-align:center;font-weight:700">${l.alunos}</td></tr>`).join('')}</tbody>
        </table></div>
        <p style="margin-top:.75rem;font-size:.85rem;color:#64748b"><i class="fas fa-info-circle"></i> ${lista.length} carta(s) serão geradas.</p>`;
    }catch(e){toast('Erro: '+e.message,false);}
}

async function gerarCartas(){
    const cfg={
        secretaria:document.getElementById('cfg-secretaria')?.value||'',
        municipio:document.getElementById('cfg-municipio')?.value||'',
        data:document.getElementById('cfg-data')?.value||'',
        assinatura:document.getElementById('cfg-assinatura')?.value||'',
        cargo:document.getElementById('cfg-cargo')?.value||''
    };
    const escola=document.getElementById('cfg-escola-origem')?.value||'';
    const btn=document.getElementById('btn-gerar');
    const status=document.getElementById('cartas-status');
    btnLoading(btn,'Gerando e enviando...');
    status.innerHTML='⏳ Gerando cartas e enviando para o Drive...';
    try{
        const d=await postJSON('/api/gerar_cartas',{escola_origem:escola,template:cfg});
        if(d.success||d.uploaded?.length>0){
            const nomes=d.uploaded.map(u=>u.filename.replace('carta_','').replace('.xlsx','').replace(/_/g,' ')).join(' · ');
            status.innerHTML=`<div style="background:#d1fae5;border:1px solid #86efac;border-radius:8px;padding:.75rem 1rem">
                <strong style="color:#065f46">✅ ${d.uploaded.length} carta(s) enviadas!</strong><br>
                <small style="color:#065f46">${nomes}</small></div>
                ${d.errors?.length?`<div style="background:#fee2e2;border:1px solid #fca5a5;border-radius:8px;padding:.75rem 1rem;margin-top:.5rem">❌ ${d.errors.length} erro(s)</div>`:''}`;
            toast(`✅ ${d.uploaded.length} carta(s) enviadas!`);
        }else{
            status.innerHTML=`<div style="background:#fee2e2;border:1px solid #fca5a5;border-radius:8px;padding:.75rem 1rem">❌ ${d.error||'Erro ao gerar cartas'}</div>`;
            toast('Erro',false);
        }
    }catch(e){
        status.innerHTML=`<div style="background:#fee2e2;border-radius:8px;padding:.75rem 1rem">❌ ${e.message}</div>`;
        toast('Erro de conexão',false);
    }finally{btnRestore(btn);}
}
