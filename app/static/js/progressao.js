/* progressao.js — tudo fica na memória da página (nada é salvo no servidor). */
const SERIES = ['GT 0','GT 1','GT 2','GT 3','GT 4','GT 5','1º ANO','2º ANO','3º ANO','4º ANO','5º ANO','6º ANO','7º ANO','8º ANO','9º ANO'];
let vagasMun = null, inativas = [], resumoVagas = [], estaduais = [], resultado = null, filtro = 'todos';

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $ = id => document.getElementById(id);

document.addEventListener('DOMContentLoaded', async () => {
    $('est-serie').innerHTML = SERIES.map(s => `<option value="${s}" ${s==='6º ANO'?'selected':''}>${s}</option>`).join('');
    try {
        const lista = await (await fetch('/api/escolas_estaduais')).json();
        $('est-escola').innerHTML = '<option value="">Selecione…</option>' +
            lista.map(e => `<option value="${esc(e.escola)}">${esc(e.escola)} — ${esc(e.bairro)}</option>`).join('');
    } catch (e) { toast('Não consegui carregar a lista de escolas estaduais', false); }
    renderEstaduais();
    atualizarPassos();
});

function atualizarPassos() {
    const ok = !!vagasMun;
    $('num1').classList.toggle('done', ok);
    $('num2').classList.toggle('done', estaduais.length > 0);
    $('num3').classList.toggle('pending', !ok);
    $('block3').classList.toggle('pending', !ok);
    $('num3').classList.toggle('done', !!resultado);
}
function marcarDesatualizado() { if (resultado) $('desatualizado').style.display = ''; }

/* ── Passo 1 ── */
async function importarPDF(input) {
    const arq = input.files[0]; if (!arq) return;
    const st = $('pdf-status');
    st.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Lendo o PDF (pode levar alguns segundos)…';
    const fd = new FormData(); fd.append('file', arq);
    try {
        const d = await postForm('/api/importar_vagas_pdf', fd);
        input.value = '';
        if (!d.success) { st.innerHTML = `<span style="color:#991b1b">❌ ${esc(d.error)}</span>`; toast('Erro ao ler o PDF', false); return; }
        vagasMun = d.vagas; inativas = d.inativas; resumoVagas = d.resumo; resultado = null;
        $('resultado-card').style.display = 'none';
        st.innerHTML = '';
        renderResumoPDF(d);
        atualizarPassos();
        toast('PDF importado!');
    } catch (e) { st.innerHTML = `<span style="color:#991b1b">❌ ${esc(e.message)}</span>`; }
}

function removerPDF() {
    vagasMun = null; inativas = []; resumoVagas = []; resultado = null;
    $('pdf-resumo').style.display = 'none';
    $('resultado-card').style.display = 'none';
    $('analise-status').innerHTML = '';
    $('pdf-status').innerHTML = '';
    atualizarPassos();
    toast('PDF removido — importe um novo');
}

function renderResumoPDF(d) {
    $('pdf-resumo').style.display = '';
    $('pdf-titulo').innerHTML = `✅ ${d.unidades} unidades lidas (${d.escolas} escolas + ${d.ceis} CEIs/creches)`;
    const card = (n, l, cor) => `<div class="stat"><div class="stat-num" style="color:${cor}">${n}</div><div class="stat-label">${l}</div></div>`;
    $('pdf-stats').innerHTML =
        card(d.unidades, 'Unidades', '#0a192f') + card(d.total_existentes, 'Vagas totais (ocup.+livres)', '#1e40af') +
        card(d.total_ocupadas, 'Ocupadas', '#475569') + card(d.total_disponiveis, 'Livres hoje', '#065f46');
    let av = '';
    if (d.inativas.length) av += `<div class="badge badge-gray" style="margin:.2rem .3rem .2rem 0">Ignorada (INATIVA no PDF): ${esc(d.inativas.join(', '))}</div>`;
    if (d.sem_bairro.length) av += `<div style="background:#fef9c3;border:1px solid #fde047;border-radius:8px;padding:.6rem 1rem;margin-top:.5rem;font-size:.8rem;color:#854d0e">
        <i class="fas fa-map-marker-alt"></i> <strong>${d.sem_bairro.length} unidade(s) sem bairro no documento de bairros</strong> — a IA as trata como "bairro distante" até você incluí-las em <code>OVERRIDES_BAIRRO</code> (app/logic/bairros.py):<br>${esc(d.sem_bairro.join(' · '))}</div>`;
    if (d.nao_lidas) av += `<div class="badge badge-red">${d.nao_lidas} linha(s) do PDF não foram lidas</div>`;
    $('pdf-avisos').innerHTML = av;

    const porSerie = {};
    for (const v of d.resumo) {
        const a = porSerie[v.serie] = porSerie[v.serie] || { total: 0, livres: 0 };
        a.total += v.vagas_existentes; a.livres += v.vagas_disponiveis;
    }
    const ordem = s => SERIES.indexOf(s) < 0 ? 99 : SERIES.indexOf(s);
    $('vagas-resumo-grid').innerHTML = Object.entries(porSerie).sort((a, b) => ordem(a[0]) - ordem(b[0])).map(([s, a]) =>
        `<div class="vaga-card"><div class="vaga-serie">${esc(s)}</div>
         <div class="vaga-num ${a.livres === 0 ? 'zero' : ''}">${a.livres}</div>
         <div class="vaga-escolas">livres de ${a.total}</div></div>`).join('');
}

/* ── Passo 2 ── */
function adicionarEstadual() {
    const escola = $('est-escola').value, serie = $('est-serie').value, qtd = parseInt($('est-qtd').value);
    if (!escola) return toast('Escolha a escola estadual', false);
    if (!qtd || qtd < 1) return toast('Informe a quantidade de vagas', false);
    const ex = estaduais.find(e => e.escola === escola && e.serie === serie);
    if (ex) ex.vagas += qtd; else estaduais.push({ escola, serie, vagas: qtd });
    $('est-qtd').value = '';
    renderEstaduais(); marcarDesatualizado(); atualizarPassos();
}
function editarEstadual(i, v) {
    const n = parseInt(v);
    if (!n || n < 1) { renderEstaduais(); return; }
    estaduais[i].vagas = n; marcarDesatualizado();
}
function removerEstadual(i) { estaduais.splice(i, 1); renderEstaduais(); marcarDesatualizado(); atualizarPassos(); }
function limparEstaduais() { estaduais = []; renderEstaduais(); marcarDesatualizado(); atualizarPassos(); }

function renderEstaduais() {
    const el = $('est-lista');
    if (!estaduais.length) { el.innerHTML = '<div style="font-size:.82rem;color:#94a3b8">Nenhuma vaga estadual adicionada — a IA usará só as vagas municipais do PDF.</div>'; return; }
    const total = estaduais.reduce((s, e) => s + e.vagas, 0);
    el.innerHTML = `<div class="table-wrap" style="max-height:260px"><table>
        <thead><tr><th>Escola estadual</th><th>Série</th><th style="width:120px">Vagas</th><th style="width:50px"></th></tr></thead>
        <tbody>${estaduais.map((e, i) => `<tr>
            <td>${esc(e.escola)}</td><td>${esc(e.serie)}</td>
            <td><input class="form-input" type="number" min="1" value="${e.vagas}" style="padding:.3rem .5rem"
                       onchange="editarEstadual(${i}, this.value)"/></td>
            <td><button class="btn btn-red btn-sm" onclick="removerEstadual(${i})" title="Remover"><i class="fas fa-trash"></i></button></td>
        </tr>`).join('')}</tbody></table></div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:.6rem;font-size:.82rem;color:#64748b">
            <span>${estaduais.length} linha(s) · ${total} vagas estaduais</span>
            <button class="btn btn-outline btn-sm" onclick="limparEstaduais()"><i class="fas fa-eraser"></i> Limpar tudo</button></div>`;
}

/* ── Passo 3 ── */
async function executarAnalise() {
    if (!vagasMun) return toast('Importe o PDF de vagas primeiro', false);
    const btn = $('btn-analisar'); btnLoading(btn, 'Analisando…');
    $('analise-status').innerHTML = '';
    try {
        const d = await postJSON('/api/analisar_progressao', { vagas: vagasMun, inativas, estaduais });
        if (!d.success) { $('analise-status').innerHTML = `<span style="color:#991b1b">❌ ${esc(d.error)}</span>`; return; }
        resultado = d; filtro = 'todos';
        $('desatualizado').style.display = 'none';
        $('resultado-card').style.display = '';
        $('analise-status').innerHTML = `<span style="color:#065f46">✅ ${d.resumo.turmas} turmas de ${d.resumo.escolas_origem} unidades analisadas</span>`;
        renderResultado(); atualizarPassos(); toast('Análise concluída!');
    } catch (e) { $('analise-status').innerHTML = `<span style="color:#991b1b">❌ ${esc(e.message)}</span>`; }
    finally { btnRestore(btn); }
}

function setFiltro(f) { filtro = f; renderResultado(); }

function renderResultado() {
    const r = resultado.resumo;
    const card = (n, l, cor) => `<div class="stat"><div class="stat-num" style="color:${cor}">${n}</div><div class="stat-label">${l}</div></div>`;
    $('prog-stats').innerHTML = card(r.turmas, 'Turmas a realocar', '#0a192f') + card(r.alunos, 'Alunos', '#475569') +
        card(r.estadual, '→ Estadual', '#5b21b6') + card(r.municipal, '→ Municipal', '#1e40af') +
        card(r.sem_vaga + ' <small style="font-size:.9rem">(' + r.alunos_sem_vaga + ' al.)</small>', 'Sem vaga p/ turma inteira', '#991b1b');

    const filtros = [['todos', 'Todas', r.turmas], ['estadual', '🏛️ Estadual', r.estadual], ['municipal', '🏫 Municipal', r.municipal], ['sem_vaga', '⚠️ Sem vaga', r.sem_vaga]];
    $('filtros').innerHTML = filtros.map(([k, l, n]) =>
        `<button class="btn ${filtro === k ? 'btn-primary' : 'btn-outline'} btn-sm" onclick="setFiltro('${k}')">${l} (${n})</button>`).join('');

    const passa = t => filtro === 'todos' ||
        (filtro === 'sem_vaga' && t.status !== 'ok') ||
        (filtro === 'estadual' && t.escola_sugerida?.tipo === 'ESTADUAL') ||
        (filtro === 'municipal' && t.escola_sugerida?.tipo === 'MUNICIPAL');

    const grupos = {};
    resultado.turmas.filter(passa).forEach(t => (grupos[t.escola_origem] = grupos[t.escola_origem] || []).push(t));
    $('alocacoes-lista').innerHTML = Object.entries(grupos).map(([escola, ts]) => {
        const al = ts.reduce((s, t) => s + t.total_alunos, 0);
        return `<div style="margin-bottom:1.1rem">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.4rem;padding:.45rem .2rem;border-bottom:2px solid #e2e8f0;margin-bottom:.5rem">
                <strong style="color:#0a192f">${esc(escola)}</strong>
                <span style="font-size:.78rem;color:#64748b">${esc(ts[0].bairro_origem || 'bairro não identificado')} · ${ts.length} turma(s) · ${al} alunos</span></div>
            ${ts.map(linhaTurma).join('')}</div>`;
    }).join('') || '<div style="color:#94a3b8;font-size:.9rem">Nenhuma turma neste filtro.</div>';
}

function linhaTurma(t) {
    const s = t.escola_sugerida;
    let destino;
    if (s) {
        const tipo = s.tipo === 'ESTADUAL' ? '<span class="badge badge-purple">🏛️ ESTADUAL</span>' : '<span class="badge badge-blue">🏫 MUNICIPAL</span>';
        const prox = s.proximidade === 'mesmo' ? 'badge-green' : s.proximidade === 'proximo' ? 'badge-yellow' : 'badge-red';
        destino = `${tipo} <strong>${esc(s.escola)}</strong>
            <span style="font-size:.75rem;color:#64748b">${esc(s.bairro)} · ${s.vagas_disponiveis} vagas</span>
            <span class="badge ${prox}">${esc(s.proximidade_rotulo)}</span>
            ${s.turno_diferente ? '<span class="badge badge-gray">turno diferente</span>' : ''}`;
    } else {
        const melhor = t.sugestoes[0];
        destino = `<i class="fas fa-exclamation-triangle"></i> <strong>Nenhuma escola tem vagas para a turma inteira (${t.total_alunos})</strong>` +
            (melhor ? `<span style="font-size:.75rem;color:#64748b"> · maior vaga: ${esc(melhor.escola)} (${melhor.vagas_disponiveis})</span>`
                    : '<span style="font-size:.75rem;color:#64748b"> · nenhuma unidade oferece essa série</span>');
    }
    const outras = s && t.sugestoes.length
        ? `<div style="font-size:.74rem;color:#94a3b8;margin-top:.25rem">Alternativas: ${t.sugestoes.map(o => esc(o.escola) + ' (' + o.vagas_disponiveis + 'v)').join(' · ')}</div>` : '';
    return `<div class="aloc-row ${s ? '' : 'sem-vaga'}" style="cursor:default">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem">
            <div><span class="turma-info">${esc(t.turma)}</span>
                 <span style="color:#94a3b8;margin:0 .35rem">→</span>
                 <span style="font-weight:700;color:#2563eb">${esc(t.serie_destino)}</span>
                 <span style="margin-left:.5rem;font-size:.76rem;color:#64748b">${esc(t.turno)}</span></div>
            <span style="background:#e2e8f0;padding:.15rem .55rem;border-radius:4px;font-size:.78rem;font-weight:600">${t.total_alunos} alunos</span></div>
        <div class="escola-dest" style="margin-top:.3rem;display:flex;gap:.45rem;align-items:center;flex-wrap:wrap">${destino}</div>${outras}</div>`;
}

/* ── Exportação ── */
function avisoSeDesatualizado() {
    if ($('desatualizado').style.display !== 'none') { toast('Vagas alteradas: execute a análise de novo antes de exportar', false); return true; }
    return false;
}
async function baixarExcel() {
    if (!resultado || avisoSeDesatualizado()) return;
    try { await downloadBlob('/api/baixar_excel_progressao', { resultado }, `progressao_${new Date().toISOString().slice(0, 10)}.xlsx`); }
    catch (e) { toast('❌ ' + e.message, false); }
}
async function exportarDrive() {
    if (!resultado || avisoSeDesatualizado()) return;
    const btn = event.target.closest('button'); btnLoading(btn, 'Enviando…');
    try {
        const r = await fetch('/api/exportar_excel_progressao', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ resultado }) });
        if ((r.headers.get('content-type') || '').includes('application/json')) {
            const d = await r.json(); d.success ? toast('✅ Excel enviado para o Drive!') : toast('❌ ' + d.error, false);
        } else {
            const a = document.createElement('a'); a.href = URL.createObjectURL(await r.blob());
            a.download = `progressao_${new Date().toISOString().slice(0, 10)}.xlsx`; a.click(); URL.revokeObjectURL(a.href);
            toast('Drive indisponível — o Excel foi baixado no computador', false);
        }
    } catch (e) { toast('❌ ' + e.message, false); } finally { btnRestore(btn); }
}
async function baixarExcelVagas() {
    if (!vagasMun) return;
    try { await downloadBlob('/api/exportar_excel_vagas', { vagas: vagasMun, estaduais }, `vagas_${new Date().toISOString().slice(0, 10)}.xlsx`); }
    catch (e) { toast('❌ ' + e.message, false); }
}
