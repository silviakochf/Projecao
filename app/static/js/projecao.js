/* projecao.js — tudo fica na memória da página (nada é salvo no servidor). */
const SERIES = ['GT 0','GT 1','GT 2','GT 3','GT 4','GT 5','1º ANO','2º ANO','3º ANO','4º ANO','5º ANO','6º ANO','7º ANO','8º ANO','9º ANO'];
let vagasMun = null, inativas = [], salas = [], resultado = null;

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $ = id => document.getElementById(id);
const stat = (n, l, cor) => `<div class="stat"><div class="stat-num" style="color:${cor}">${n}</div><div class="stat-label">${l}</div></div>`;
const aviso = (t, cor = '#fef9c3', borda = '#fde047', txt = '#854d0e') =>
    `<div style="background:${cor};border:1px solid ${borda};border-radius:8px;padding:.6rem 1rem;margin:.5rem 0;font-size:.82rem;color:${txt}">${t}</div>`;

document.addEventListener('DOMContentLoaded', () => atualizarPassos());

function atualizarPassos() {
    const ok = !!vagasMun;
    $('num1').classList.toggle('done', ok);
    for (const n of [2, 3]) { $('num' + n).classList.toggle('pending', !ok); $('block' + n).classList.toggle('pending', !ok); }
    $('num2').classList.toggle('done', ok && salas.length > 0);
    $('num3').classList.toggle('done', !!resultado);
}

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
    $('salas-body').innerHTML = mostra.map(s => {
        const dif = s.area_m2 > 0 && s.diferenca !== 0;
        const num = v => `<td style="text-align:right">${v}</td>`;
        return `<tr style="${dif ? 'background:#fefce8' : ''}">
            <td>${esc(s.escola)}</td><td>${esc(s.sala || '—')}</td><td>${esc(s.turno)}</td><td>${esc(s.serie)}</td>
            ${num(s.area_m2 > 0 ? s.area_m2.toFixed(2) : '—')}
            ${num(`<strong>${s.vagas_relatorio}</strong>${dif ? ` <span title="calculado: ${s.cap_teorica}" style="color:#b45309">(${s.diferenca > 0 ? '+' : ''}${s.diferenca})</span>` : ''}`)}
            ${num(s.area_m2 > 0 ? s.cap_area : '—')}</tr>`;
    }).join('');
    $('salas-info').textContent = `${mostra.length} de ${lista.length} linhas` + (lista.length > MAX ? ` — use os filtros para ver as demais (o Excel traz todas)` : '') +
        '. O número entre parênteses é a diferença entre o relatório e o calculado.';
}

/* ── Passo 3: projeção ── */
async function calcularProjecao() {
    if (!vagasMun) return toast('Importe o PDF de vagas primeiro', false);
    const btn = $('btn-calc'); btnLoading(btn, 'Calculando…'); $('calc-status').innerHTML = '';
    try {
        const d = await postJSON('/api/calcular_projecao', { vagas: vagasMun, inativas,
            params: { abrir_series: $('p-abrir').checked, entre_etapas: $('p-etapas').checked, proteger_entrada: $('p-proteger').checked } });
        if (!d.success) { $('calc-status').innerHTML = `<span style="color:#991b1b">❌ ${esc(d.error)}</span>`; return; }
        resultado = d; $('resultado-card').style.display = '';
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
const cor = (n, ruim = '#b91c1c', bom = '#065f46') => `<strong style="color:${n ? ruim : bom}">${n}</strong>`;

function renderResultado() {
    const R = resultado.resumo;
    $('res-stats').innerHTML =
        stat(`${R.nao_cabem_antes} → ${R.nao_cabem_depois}`, 'Alunos que não cabem na própria unidade (antes → depois)', R.nao_cabem_depois < R.nao_cabem_antes ? '#065f46' : '#b45309') +
        stat(R.salas_convertidas, `Salas que mudam de série (${R.unidades_alteradas} de ${R.unidades} unidades)`, '#1e40af') +
        stat(R.abrem_serie_nova, `Unidades que abrem série nova (${R.alunos_que_continuam} alunos continuam nelas)`, '#5b21b6') +
        stat(R.vagas_entrada_retiradas, 'Vagas tiradas de séries de entrada (menos vagas p/ alunos de fora)', R.vagas_entrada_retiradas ? '#b45309' : '#065f46') +
        stat(`${R.sobra_antes} → ${R.sobra_depois}`, 'Vagas livres para alunos de outras unidades (antes → depois)', '#0a192f');
    $('res-avisos').innerHTML = (resultado.avisos || []).map(t => aviso('⚠️ ' + esc(t))).join('');

    const serie = tabela(['Série (ano seguinte)', 'Alunos que sobem da série anterior', 'Não cabem antes', 'Não cabem depois', 'Passam a caber', 'Vagas livres p/ alunos de fora (antes → depois)'],
        resultado.por_serie.map(s => [esc(s.serie), s.sobem, s.falta_antes, cor(s.falta_depois), s.falta_antes - s.falta_depois, `${s.sobra_antes} → ${s.sobra_depois}`]),
        'Nenhuma série encontrada.', 320);

    const conv = tabela(['Unidade', 'Bairro', 'Sala', 'Turno', 'Série hoje → ano seguinte', 'Vagas hoje → depois', 'Série nova?', 'Por que mudar', 'De onde a sala sai'],
        resultado.salas_convertidas.map(c => [esc(c.escola), esc(c.bairro || '—'), esc(c.sala || '—'), esc(c.turno),
            `${esc(c.serie_antes)} → <strong>${esc(c.serie_nova)}</strong>`, `${c.vagas_antes} → <strong>${c.vagas_novas}</strong>`,
            c.abre_serie_nova ? '<span class="badge badge-purple">sim</span>' : 'não',
            `<span style="font-size:.78rem;color:#475569">${esc(c.motivo)}</span>`,
            `<span style="font-size:.78rem;color:${c.reduz_entrada ? '#b45309' : '#64748b'}">${esc(c.origem)}</span>`]),
        'Nenhuma sala precisa mudar de série com as regras atuais.', 440);

    const rotulo = b => b.aberta ? '<span class="badge badge-purple">série aberta</span>' : (b.mudou ? '<span class="badge badge-green">alterada</span>' : '');
    const bal = resultado.balanco;
    const nao = tabela(['Unidade', 'Bairro', 'Série', 'Alunos que sobem', 'Vagas depois', 'Não cabem'],
        bal.filter(b => b.falta_depois > 0).map(b => [esc(b.escola), esc(b.bairro || '—'), esc(b.serie), b.sobem, b.vagas_depois, cor(b.falta_depois)]),
        'Todos os alunos que sobem de série cabem na própria unidade. 🎉', 360);

    const unidades = [...new Set(bal.map(b => b.escola))];
    const filtro = `<div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.5rem">
        <select class="form-select" id="b-escola" style="max-width:340px" onchange="renderBalanco()"><option value="">Todas as unidades</option>${unidades.map(u => `<option>${esc(u)}</option>`).join('')}</select>
        <label style="display:flex;align-items:center;gap:.4rem;font-size:.82rem"><input type="checkbox" id="b-so" checked onchange="renderBalanco()"> só linhas com falta ou alteração</label></div>
        <div id="balanco-tabela"></div>`;

    let html = secao('Por série (ano seguinte)', serie, true) + secao(`Salas sugeridas para mudar de série (${resultado.salas_convertidas.length})`, conv, true) +
        secao('Alunos que sobem × vagas, por unidade e série', filtro) +
        secao(`Ainda não cabem na própria unidade (${bal.filter(b => b.falta_depois > 0).length} séries)`, nao);
    $('res-corpo').innerHTML = html;
    window._rotulo = rotulo; renderBalanco();
}

function renderBalanco() {
    const fe = $('b-escola').value, so = $('b-so').checked;
    const linhas = resultado.balanco.filter(b => (!fe || b.escola === fe) && (!so || b.falta_antes || b.falta_depois || b.mudou || b.aberta));
    $('balanco-tabela').innerHTML = tabela(['Unidade', 'Série', 'Alunos que sobem', 'Vagas antes → depois', 'Não cabem antes → depois', 'Livres p/ fora antes → depois', ''],
        linhas.map(b => [esc(b.escola), esc(b.serie) + (b.entrada ? ' <span style="color:#94a3b8;font-size:.72rem">(entrada)</span>' : ''), b.sobem,
            `${b.vagas_antes} → <strong>${b.vagas_depois}</strong>`, `${b.falta_antes} → ${cor(b.falta_depois)}`, `${b.sobra_antes} → ${b.sobra_depois}`, window._rotulo(b)]),
        'Nenhuma linha com esse filtro.', 420);
}

async function baixarExcel() {
    if (!resultado) return toast('Calcule a projeção primeiro', false);
    try { await downloadBlob('/api/baixar_excel_projecao', { resultado }, 'projecao_salas.xlsx'); toast('Excel gerado!'); }
    catch (e) { toast('Erro ao gerar o Excel: ' + e.message, false); }
}