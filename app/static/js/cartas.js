/* cartas.js — uma carta por criança. Estado só na memória da página; o texto fica no navegador (localStorage). */
const CHAVE_LS = 'cartas_cfg_v1';
let textoPadrao = '', campos = {}, arquivos = { html: null, excel: null }, montado = null, posPrevia = 0, timerPrevia = null;
const $c = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

document.addEventListener('DOMContentLoaded', async () => {
    const cfg = await (await fetch('/api/cartas/config')).json();
    textoPadrao = cfg.texto_padrao; campos = cfg.campos;
    $c('chips').innerHTML = Object.entries(campos).map(([k, d]) =>
        `<button type="button" class="btn btn-outline btn-sm" title="${esc(d)}" onclick="inserirCampo('${k}')">{${k}}</button>`).join('');

    let salvo = {};
    try { salvo = JSON.parse(localStorage.getItem(CHAVE_LS) || '{}'); } catch (e) { /* sem localStorage */ }
    $c('texto').value = salvo.texto || textoPadrao;
    $c('cfg-secretaria').value = salvo.secretaria || 'SECRETARIA MUNICIPAL DE EDUCAÇÃO';
    $c('cfg-municipio').value = salvo.municipio || 'Palhoça';
    $c('cfg-assinatura').value = salvo.assinatura || '';
    $c('cfg-cargo').value = salvo.cargo || 'Secretária de Educação';
    $c('cfg-data').value = new Date().toLocaleDateString('pt-BR', { day: 'numeric', month: 'long', year: 'numeric' });
    $c('cfg-ano').value = new Date().getFullYear() + 1;
    validarCampos();
});

function cfg() {
    return { texto: $c('texto').value, secretaria: $c('cfg-secretaria').value, municipio: $c('cfg-municipio').value,
             data: $c('cfg-data').value, ano_letivo: $c('cfg-ano').value, assinatura: $c('cfg-assinatura').value, cargo: $c('cfg-cargo').value };
}
function aoMudarTexto() {
    const c = cfg();
    try { localStorage.setItem(CHAVE_LS, JSON.stringify({ texto: c.texto, secretaria: c.secretaria, municipio: c.municipio, assinatura: c.assinatura, cargo: c.cargo })); } catch (e) { /* ignora */ }
    validarCampos();
    clearTimeout(timerPrevia); timerPrevia = setTimeout(atualizarPrevia, 250);
}
function validarCampos() {
    const usados = [...$c('texto').value.matchAll(/\{([A-Za-z_]+)\}/g)].map(m => m[1]);
    const ruins = [...new Set(usados.filter(u => !(u.toUpperCase() in campos)))];
    const el = $c('aviso-campos');
    el.style.display = ruins.length ? '' : 'none';
    el.innerHTML = ruins.length ? `<i class="fas fa-exclamation-triangle"></i> Campo(s) que não existem: ${ruins.map(r => '<strong>{' + esc(r) + '}</strong>').join(', ')} — saem do jeito que estão na carta. Use os botões acima.` : '';
}
function inserirCampo(nome) {
    const t = $c('texto'), ini = t.selectionStart ?? t.value.length, fim = t.selectionEnd ?? ini;
    t.value = t.value.slice(0, ini) + '{' + nome + '}' + t.value.slice(fim);
    t.focus(); t.selectionStart = t.selectionEnd = ini + nome.length + 2;
    aoMudarTexto();
}
function restaurarTexto() { $c('texto').value = textoPadrao; aoMudarTexto(); toast('Texto padrão restaurado'); }

/* ── arquivos ── */
function escolherArquivo(tipo, input) {
    const f = input.files[0]; if (!f) return;
    arquivos[tipo] = f;
    $c(tipo === 'html' ? 'html-nome' : 'xlsx-nome').innerHTML = `<i class="fas fa-check-circle" style="color:#10b981"></i> ${esc(f.name)}`;
    $c('btn-montar').disabled = !(arquivos.html && arquivos.excel);
}

async function montarCartas() {
    const btn = $c('btn-montar'), st = $c('montar-status');
    btnLoading(btn, 'Montando…'); st.innerHTML = '';
    const fd = new FormData(); fd.append('html', arquivos.html); fd.append('excel', arquivos.excel);
    try {
        const d = await postForm('/api/cartas/preparar', fd);
        if (!d.success) { st.innerHTML = `<span style="color:#991b1b">❌ ${esc(d.error)}</span>`; return; }
        montado = d; posPrevia = 0;
        $c('cnum2').classList.add('done');
        if (!d.cartas.length) {
            st.innerHTML = '<span style="color:#991b1b">❌ Nenhuma carta foi gerada — veja os avisos abaixo.</span>';
        } else {
            st.innerHTML = `<span style="color:#065f46">✅ ${d.cartas.length} cartas montadas</span>`;
        }
        renderResultado();
    } catch (e) { st.innerHTML = `<span style="color:#991b1b">❌ ${esc(e.message)}</span>`; }
    finally { btnRestore(btn); }
}

function lista(titulo, itens, fmt, cor, fundo, borda) {
    if (!itens.length) return '';
    const mostra = itens.slice(0, 8).map(fmt).join('<br>');
    const resto = itens.length > 8 ? `<br>… e mais ${itens.length - 8}` : '';
    return `<div style="background:${fundo};border:1px solid ${borda};border-radius:8px;padding:.6rem .9rem;margin-top:.5rem;font-size:.8rem;color:${cor}"><strong>${titulo}</strong><br>${mostra}${resto}</div>`;
}

function renderResultado() {
    const d = montado, t = d.totais, a = d.avisos;
    $c('resultado-cartas').style.display = '';
    const temCartas = d.cartas.length > 0;
    $c('cnum3').classList.toggle('pending', !temCartas); $c('cnum3').classList.toggle('done', temCartas);
    $c('cblock3').classList.remove('pending');
    const card = (n, l, cor) => `<div class="stat"><div class="stat-num" style="color:${cor}">${n}</div><div class="stat-label">${l}</div></div>`;
    $c('cartas-stats').innerHTML = card(t.cartas, 'Cartas (1 por criança)', '#065f46') + card(t.escolas_destino, 'Escolas de destino', '#5b21b6') +
        card(t.estudantes_html, 'Estudantes ativos no HTML', '#475569') + card(t.fora_da_progressao, 'Em turmas que não mudam de escola', '#94a3b8');

    $c('cartas-avisos').innerHTML =
        lista('A escola do HTML não foi encontrada no Excel:', a.unidades_sem_origem, x => esc(x), '#991b1b', '#fee2e2', '#fca5a5') +
        lista('Turmas sem escola de destino no Excel (não geram carta):', a.sem_destino, x => `${esc(x.turma)} — ${x.alunos_html} aluno(s) no HTML`, '#991b1b', '#fee2e2', '#fca5a5') +
        lista('Turmas que estão no Excel mas não têm alunos neste HTML (relatório de outro turno?):', a.sem_alunos, x => esc(x.turma), '#854d0e', '#fef9c3', '#fde047') +
        lista('Quantidade diferente entre o Excel e o HTML (confira):', a.divergentes, x => `${esc(x.turma)}: Excel ${x.excel} · HTML ${x.html}`, '#1e40af', '#eff6ff', '#93c5fd');

    $c('tabela-destinos').innerHTML = d.destinos.map(x =>
        `<tr><td>${x.tipo === 'ESTADUAL' ? '🏛️' : '🏫'} ${esc(x.escola_destino)}</td><td>${esc(x.serie_destino)}</td><td style="text-align:center;font-weight:700">${x.cartas}</td></tr>`).join('')
        || '<tr><td colspan="3" style="color:#94a3b8;text-align:center">Nenhuma carta</td></tr>';
    atualizarPrevia();
}

/* ── prévia (o servidor monta o texto, igual ao Word) ── */
function moverPrevia(delta) {
    if (!montado || !montado.cartas.length) return;
    posPrevia = (posPrevia + delta + montado.cartas.length) % montado.cartas.length;
    atualizarPrevia();
}
async function atualizarPrevia() {
    const papel = $c('previa-papel');
    if (!montado || !montado.cartas.length) { papel.innerHTML = '<span style="color:#94a3b8">Monte as cartas para ver a prévia.</span>'; $c('previa-pos').textContent = ''; $c('previa-quem').textContent = ''; return; }
    const carta = montado.cartas[posPrevia];
    $c('previa-pos').textContent = `${posPrevia + 1} / ${montado.cartas.length}`;
    $c('previa-quem').textContent = carta.nome;
    try {
        const d = await postJSON('/api/cartas/previa', { carta, cfg: cfg() });
        const c = d.carta;
        papel.innerHTML = `<div style="text-align:center;font-weight:700;font-size:.95rem">${esc(c.secretaria)}</div>
            <div style="text-align:center;margin-bottom:.8rem">${esc(c.municipio_titulo)}</div>
            <div style="text-align:center;font-weight:700;font-size:1rem;margin-bottom:.8rem">CARTA DE ENCAMINHAMENTO</div>
            <div style="text-align:right;margin-bottom:.8rem">${esc(c.local_data)}</div>
            <div style="font-weight:700;margin-bottom:.6rem">${esc(c.destinatario)}</div>
            ${c.paragrafos.map(p => p ? `<p style="text-align:justify;margin:0 0 .45rem">${esc(p)}</p>` : '<div style="height:.4rem"></div>').join('')}
            <div style="height:1.6rem"></div>
            <div style="text-align:center">__________________________________</div>
            <div style="text-align:center;font-weight:700">${esc(c.assinatura)}</div>
            <div style="text-align:center">${esc(c.cargo)}</div>`;
    } catch (e) { papel.innerHTML = '<span style="color:#991b1b">Não consegui montar a prévia.</span>'; }
}

/* ── gerar ── */
async function baixarZip() {
    if (!montado || !montado.cartas.length) return toast('Monte as cartas primeiro', false);
    const st = $c('gerar-status'); st.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Gerando os arquivos Word…';
    try {
        const r = await fetch('/api/cartas/gerar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ cartas: montado.cartas, cfg: cfg() }) });
        if (!r.ok) throw new Error((await r.json()).error || 'Falha ao gerar');
        const a = document.createElement('a'); a.href = URL.createObjectURL(await r.blob());
        a.download = `cartas_encaminhamento_${new Date().toISOString().slice(0, 10)}.zip`; a.click(); URL.revokeObjectURL(a.href);
        st.innerHTML = `<span style="color:#065f46">✅ ${montado.destinos.length ? new Set(montado.destinos.map(x => x.escola_destino)).size : 0} arquivo(s) Word no ZIP</span>`;
    } catch (e) { st.innerHTML = `<span style="color:#991b1b">❌ ${esc(e.message)}</span>`; }
}
async function enviarDrive() {
    if (!montado || !montado.cartas.length) return toast('Monte as cartas primeiro', false);
    const st = $c('gerar-status'); st.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando para o Drive…';
    try {
        const d = await postJSON('/api/cartas/drive', { cartas: montado.cartas, cfg: cfg() });
        st.innerHTML = d.success
            ? `<span style="color:#065f46">✅ ${d.uploaded.length} arquivo(s) enviados${d.errors.length ? ` · <span style="color:#991b1b">${d.errors.length} com erro</span>` : ''}</span>`
            : `<span style="color:#991b1b">❌ ${esc(d.errors?.[0]?.error || d.error || 'Falha no envio')}</span>`;
    } catch (e) { st.innerHTML = `<span style="color:#991b1b">❌ ${esc(e.message)}</span>`; }
}
