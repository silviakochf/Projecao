/* projecao.js — tudo fica na memória da página (nada é salvo no servidor). */
const SERIES = ['GT 0','GT 1','GT 2','GT 3','GT 4','GT 5','1º ANO','2º ANO','3º ANO','4º ANO','5º ANO','6º ANO','7º ANO','8º ANO','9º ANO'];
let vagasMun = null, inativas = [], salas = [], estaduais = [], resultado = null;

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $ = id => document.getElementById(id);
const stat = (n, l, cor) => `<div class="stat"><div class="stat-num" style="color:${cor}">${n}</div><div class="stat-label">${l}</div></div>`;
const aviso = (t, cor = '#fef9c3', borda = '#fde047', txt = '#854d0e') =>
    `<div style="background:${cor};border:1px solid ${borda};border-radius:8px;padding:.6rem 1rem;margin:.5rem 0;font-size:.82rem;color:${txt}">${t}</div>`;

document.addEventListener('DOMContentLoaded', async () => {
    $('est-serie').innerHTML = SERIES.map(s => `<option value="${s}" ${s==='6º ANO'?'selected':''}>${s}</option>`).join('');
    try {
        const lista = await (await fetch('/api/escolas_estaduais')).json();
        $('est-escola').innerHTML = '<option value="">Selecione…</option>' +
            lista.map(e => `<option value="${esc(e.escola)}">${esc(e.escola)} — ${esc(e.bairro)}</option>`).join('');
    } catch (e) { toast('Não consegui carregar a lista de escolas estaduais', false); }
    renderEstaduais(); atualizarPassos();
});

function atualizarPassos() {
    const ok = !!vagasMun;
    $('num1').classList.toggle('done', ok);
    for (const n of [2, 3, 4]) { $('num' + n).classList.toggle('pending', !ok); $('block' + n).classList.toggle('pending', !ok); }
    $('num2').classList.toggle('done', ok && salas.length > 0);
    $('num3').classList.toggle('done', estaduais.length > 0);
    $('num4').classList.toggle('done', !!resultado);
}
function marcarDesatualizado() { if (resultado) $('desatualizado').style.display = ''; }

/* ── Passo 1: PDF ── */
async function importarPDF(input) {
    const arq = input.files[0]; if (!arq) return;
    const st = $('pdf-status');
    st.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Lendo o PDF (pode levar alguns segundos)…';
    const fd = new FormData(); fd.append('file', arq);
    try {
        const d = await postForm('/api/importar_vagas_pdf', fd);
        input.value = '';
        if (!d.success) { st.innerHTML = `<span style="color:#991b1b">❌ ${esc(d.error)}</span>`; toast('Erro ao ler o PDF', false); return; }
        vagasMun = d.vagas; inativas = d.inativas; resultado = null;
        $('resultado-card').style.display = 'none'; $('calc-status').innerHTML = '';
        st.innerHTML = '';
        $('pdf-resumo').style.display = '';
        $('pdf-titulo').innerHTML = `✅ ${d.unidades} unidades lidas (${d.escolas} escolas + ${d.ceis} CEIs/creches)`;
        let av = '';
        if (d.inativas.length) av += `<div class="badge badge-gray" style="margin:.2rem .3rem .2rem 0">Ignorada (INATIVA no PDF): ${esc(d.inativas.join(', '))}</div>`;
        if (d.nao_lidas) av += `<div class="badge badge-red">${d.nao_lidas} linha(s) do PDF não foram lidas</div>`;
        $('pdf-avisos').innerHTML = av;
        await carregarSalas();
        atualizarPassos(); toast('PDF importado!');
    } catch (e) { st.innerHTML = `<span style="color:#991b1b">❌ ${esc(e.message)}</span>`; }
}
function removerPDF() {
    vagasMun = null; inativas = []; salas = []; resultado = null;
    $('pdf-resumo').style.display = 'none'; $('resultado-card').style.display = 'none';
    $('pdf-status').innerHTML = ''; $('calc-status').innerHTML = ''; $('salas-body').innerHTML = '';
    atualizarPassos(); toast('PDF removido — importe um novo');
}

/* ── Passo 2: capacidade das salas ── */
async function carregarSalas() {
    const d = await postJSON('/api/capacidade_salas', { vagas: vagasMun, inativas });
    if (!d.success) { toast(d.error, false); return; }
    salas = d.salas;
    const unidades = [...new Set(salas.map(s => s.escola))].sort();
    $('f-escola').innerHTML = '<option value="">Todas as unidades</option>' + unidades.map(u => `<option>${esc(u)}</option>`).join('');
    $('f-serie').innerHTML = '<option value="">Todas as séries</option>' + SERIES.filter(s => salas.some(x => x.serie === s)).map(s => `<option>${s}</option>`).join('');
    const comArea = salas.filter(s => s.area_m2 > 0), dif = comArea.filter(s => s.diferenca !== 0);
    $('sala-stats').innerHTML =
        stat(salas.length, 'Turmas (sala + turno)', '#0a192f') +
        stat(comArea.reduce((a, s) => a + s.vagas_relatorio, 0), 'Vagas no relatório', '#1e40af') +
        stat(comArea.reduce((a, s) => a + s.cap_teorica, 0), 'Vagas pelo cálculo da metragem', '#065f46') +
        stat(dif.length, 'Salas com número diferente', dif.length ? '#b45309' : '#065f46') +
        stat(salas.length - comArea.length, 'Sem metragem no PDF', salas.length - comArea.length ? '#b45309' : '#065f46');
    renderSalas();
}
function renderSalas() {
    const fe = $('f-escola').value, fs = $('f-serie').value, fd = $('f-dif').checked;
    const lista = salas.filter(s => (!fe || s.escola === fe) && (!fs || s.serie === fs) && (!fd || (s.area_m2 > 0 && s.diferenca !== 0)));
    const MAX = 400, mostra = lista.slice(0, MAX);
    const f = n => s => s.area_m2 > 0 ? s.cap_faixa[n] : '—';
    $('salas-body').innerHTML = mostra.map(s => {
        const dif = s.area_m2 > 0 && s.diferenca !== 0;
        const num = v => `<td style="text-align:right">${v}</td>`;
        return `<tr style="${dif ? 'background:#fefce8' : ''}">
            <td>${esc(s.escola)}</td><td>${esc(s.sala || '—')}</td><td>${esc(s.turno)}</td><td>${esc(s.serie)}</td>
            ${num(s.area_m2 > 0 ? s.area_m2.toFixed(2) : '—')}
            ${num(`<strong>${s.vagas_relatorio}</strong>${dif ? ` <span title="calculado: ${s.cap_teorica}" style="color:#b45309">(${s.diferenca > 0 ? '+' : ''}${s.diferenca})</span>` : ''}`)}
            ${num(s.area_m2 > 0 ? s.cap_area : '—')}
            ${['GT 0','GT 1 a GT 3','GT 4 e GT 5','1º ao 5º ano','6º ao 9º ano'].map(n => num(f(n)(s))).join('')}</tr>`;
    }).join('');
    $('salas-info').textContent = `${mostra.length} de ${lista.length} linhas` + (lista.length > MAX ? ` — use os filtros para ver as demais (o Excel traz todas)` : '') +
        '. O número entre parênteses é a diferença entre o relatório e o calculado.';
}

/* ── Passo 3: vagas estaduais ── */
function adicionarEstadual() {
    const escola = $('est-escola').value, serie = $('est-serie').value, qtd = parseInt($('est-qtd').value);
    if (!escola) return toast('Escolha a escola estadual', false);
    if (!qtd || qtd < 1) return toast('Informe a quantidade de vagas', false);
    const ex = estaduais.find(e => e.escola === escola && e.serie === serie);
    if (ex) ex.vagas += qtd; else estaduais.push({ escola, serie, vagas: qtd });
    $('est-qtd').value = ''; renderEstaduais(); marcarDesatualizado(); atualizarPassos();
}
function editarEstadual(i, v) { const n = parseInt(v); if (!n || n < 1) { renderEstaduais(); return; } estaduais[i].vagas = n; marcarDesatualizado(); }
function removerEstadual(i) { estaduais.splice(i, 1); renderEstaduais(); marcarDesatualizado(); atualizarPassos(); }
function limparEstaduais() { estaduais = []; renderEstaduais(); marcarDesatualizado(); atualizarPassos(); }
function renderEstaduais() {
    const el = $('est-lista');
    if (!estaduais.length) { el.innerHTML = '<div style="font-size:.82rem;color:#94a3b8">Nenhuma vaga estadual adicionada — a projeção usará só as vagas municipais do PDF.</div>'; return; }
    const total = estaduais.reduce((s, e) => s + e.vagas, 0);
    el.innerHTML = `<div class="table-wrap" style="max-height:240px"><table>
        <thead><tr><th>Escola estadual</th><th>Série</th><th style="width:120px">Vagas</th><th style="width:50px"></th></tr></thead>
        <tbody>${estaduais.map((e, i) => `<tr><td>${esc(e.escola)}</td><td>${esc(e.serie)}</td>
            <td><input class="form-input" type="number" min="1" value="${e.vagas}" style="padding:.3rem .5rem" onchange="editarEstadual(${i}, this.value)"/></td>
            <td><button class="btn btn-red btn-sm" onclick="removerEstadual(${i})"><i class="fas fa-trash"></i></button></td></tr>`).join('')}</tbody></table></div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:.6rem;font-size:.82rem;color:#64748b">
            <span>${estaduais.length} linha(s) · ${total} vagas estaduais</span>
            <button class="btn btn-outline btn-sm" onclick="limparEstaduais()"><i class="fas fa-eraser"></i> Limpar tudo</button></div>`;
}

/* ── Passo 4: projeção ── */
async function calcularProjecao() {
    if (!vagasMun) return toast('Importe o PDF de vagas primeiro', false);
    const btn = $('btn-calc'); btnLoading(btn, 'Calculando…'); $('calc-status').innerHTML = '';
    try {
        const d = await postJSON('/api/calcular_projecao', { vagas: vagasMun, inativas, estaduais,
            params: { abrir_series: $('p-abrir').checked, entre_etapas: $('p-etapas').checked } });
        if (!d.success) { $('calc-status').innerHTML = `<span style="color:#991b1b">❌ ${esc(d.error)}</span>`; return; }
        resultado = d; $('desatualizado').style.display = 'none'; $('resultado-card').style.display = '';
        renderResultado(); atualizarPassos(); toast('Projeção calculada!');
    } catch (e) { $('calc-status').innerHTML = `<span style="color:#991b1b">❌ ${esc(e.message)}</span>`; }
    finally { btnRestore(btn); }
}

function tabela(cabecalho, linhas, vazio, max = 360) {
    if (!linhas.length) return `<div style="font-size:.82rem;color:#94a3b8;margin:.4rem 0">${vazio}</div>`;
    return `<div class="table-wrap" style="max-height:${max}px"><table><thead><tr>${cabecalho.map(c => `<th>${c}</th>`).join('')}</tr></thead>
        <tbody>${linhas.map(l => `<tr>${l.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
const secao = (titulo, corpo, aberta = false) =>
    `<details ${aberta ? 'open' : ''} style="margin-top:1rem"><summary style="cursor:pointer;font-weight:600;font-size:.9rem;color:#0a192f;margin-bottom:.5rem">${titulo}</summary>${corpo}</details>`;

function renderResultado() {
    const R = resultado.resumo, a = R.antes, d = R.depois;
    $('res-stats').innerHTML =
        stat(`${a.alunos_sem_vaga} → ${d.alunos_sem_vaga}`, 'Alunos sem vaga (antes → depois)', d.alunos_sem_vaga < a.alunos_sem_vaga ? '#065f46' : '#b45309') +
        stat(`${a.sem_vaga} → ${d.sem_vaga}`, 'Turmas sem vaga (antes → depois)', '#0a192f') +
        stat(R.salas_convertidas, `Salas a mudar de série (${R.escolas_afetadas} escolas)`, '#1e40af') +
        stat(R.alunos_resolvidos, 'Alunos que ganham vaga', '#065f46') +
        stat(R.abrem_serie_nova, 'Escolas que abrem série nova', '#5b21b6');
    $('res-avisos').innerHTML = (resultado.avisos || []).map(t => aviso('⚠️ ' + esc(t))).join('');

    const serie = tabela(['Série de destino', 'Alunos que precisam trocar de unidade', 'Sem vaga antes', 'Sem vaga depois', 'Ganham vaga', 'Vagas livres que sobram na série'],
        resultado.por_serie.map(s => [esc(s.serie), s.alunos, s.sem_vaga_antes, `<strong style="color:${s.sem_vaga_depois ? '#b91c1c' : '#065f46'}">${s.sem_vaga_depois}</strong>`,
            s.sem_vaga_antes - s.sem_vaga_depois, R.folga_por_serie[s.serie] || 0]), 'Nenhuma turma precisa trocar de unidade.', 260);

    const conv = tabela(['Unidade', 'Bairro', 'Sala', 'Turno', 'Série hoje → ano seguinte', 'Vagas hoje → depois', 'Série nova na escola?', 'Para atender'],
        resultado.salas_convertidas.map(c => [esc(c.escola), esc(c.bairro || '—'), esc(c.sala || '—'), esc(c.turno),
            `${esc(c.serie_antes)} → <strong>${esc(c.serie_nova)}</strong>`, `${c.vagas_antes} → <strong>${c.vagas_novas}</strong>`,
            c.abre_serie_nova ? '<span class="badge badge-purple">sim</span>' : 'não', `<span style="font-size:.78rem;color:#64748b">${esc(c.motivo)}</span>`]),
        'Nenhuma sala precisa mudar de série com as regras atuais.', 420);

    const amp = tabela(['Unidade', 'Série', 'Turno', 'Salas convertidas', 'Vagas que saem de outras séries', 'Vagas que entram', 'Alunos alocados', 'Série nova?'],
        resultado.destinos_ampliados.map(p => [esc(p.escola), esc(p.serie), esc(p.turno), p.salas, p.vagas_retiradas, p.vagas_novas, p.alunos_alocados, p.abre_serie_nova ? 'sim' : 'não']), '—', 300);

    const ok = tabela(['Turma', 'Série', 'Alunos', 'Passa a ter vaga em', 'Turno'],
        resultado.turmas_resolvidas.map(t => [`${esc(t.escola_origem)} · ${esc(t.turma)}`, `${esc(t.serie_atual)} → ${esc(t.serie_destino)}`, t.total_alunos,
            esc(t.escola_destino) + (t.fica_na_escola ? ' <span class="badge badge-green">continua na própria escola</span>' : ''), esc(t.turno_destino)]),
        'Nenhuma turma ganhou vaga.', 320);

    const sem = tabela(['Turma', 'Bairro', 'Série', 'Turno', 'Alunos'],
        resultado.turmas_sem_vaga.map(t => [`${esc(t.escola_origem)} · ${esc(t.turma)}`, esc(t.bairro_origem || '—'), `${esc(t.serie_atual)} → ${esc(t.serie_destino)}`, esc(t.turno), t.total_alunos]),
        'Todas as turmas têm vaga. 🎉', 320);

    let html = secao('Por série de destino', serie, true) + secao(`Salas sugeridas para mudar de série (${resultado.salas_convertidas.length})`, conv, true) +
        secao(`Unidades que ganham vagas (${resultado.destinos_ampliados.length})`, amp) +
        secao(`Turmas que passam a ter vaga (${resultado.turmas_resolvidas.length})`, ok) +
        secao(`Turmas que continuam sem vaga (${resultado.turmas_sem_vaga.length})`, sem);
    if ((resultado.turmas_perderam_vaga || []).length)
        html += secao(`⚠️ Turmas que perderam a vaga (${resultado.turmas_perderam_vaga.length})`, tabela(['Turma', 'Série destino', 'Alunos', 'Tinha vaga em'],
            resultado.turmas_perderam_vaga.map(t => [`${esc(t.escola_origem)} · ${esc(t.turma)}`, esc(t.serie_destino), t.total_alunos, esc(t.tinha_vaga_em)]), '—', 200), true);
    $('res-corpo').innerHTML = html;
}

async function baixarExcel() {
    if (!resultado) return toast('Calcule a projeção primeiro', false);
    try { await downloadBlob('/api/baixar_excel_projecao', { resultado }, 'projecao_salas.xlsx'); toast('Excel gerado!'); }
    catch (e) { toast('Erro ao gerar o Excel: ' + e.message, false); }
}
