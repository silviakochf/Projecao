"""
Motor de PROJEÇÃO DE SALAS — quantos alunos cabem em cada sala e que série cada sala deveria atender
no ano seguinte para acompanhar a demanda.  Trabalha só com contagens do PDF (nenhum dado de aluno).

Regras de capacidade
--------------------
* Teto por série (máximo de alunos por turma):
      GT 0 = 15 · GT 1 a GT 3 = 20 · GT 4 e GT 5 = 25 · 1º ao 5º ano = 30 · 6º ao 9º ano = 35
* Capacidade física da sala:  (m² − 2,5) ÷ 1,3, arredondado para o inteiro mais próximo
  (é o que o próprio relatório faz: 48 m² → 35 alunos).
* Vagas de uma sala numa série = o MENOR entre o teto da série e a capacidade física.
* Até 5 alunos EXCEDENTES por sala ficam de reserva (ordem judicial etc.): nunca entram no cálculo.

Como a projeção decide
----------------------
1. Roda a progressão com as salas como estão e separa as turmas que ficaram SEM VAGA.
2. Para cada uma, procura salas OCIOSAS (a vaga inteira da sala sobra no ano seguinte, depois de
   descontar quem sobe dentro da própria escola e quem a progressão já alocou) que possam virar a série
   de que a turma precisa.  Prefere: ficar na própria escola → mesmo bairro → bairro próximo →
   distante; depois, menos salas e menos vaga desperdiçada.
3. Repete até não haver mais ganho e remove conversões que não fizeram diferença.
4. Roda a progressão de novo, já com as salas convertidas, para mostrar o resultado real.

Só converte sala inteira ociosa; nunca tira vaga de quem já tem lugar.
"""
import math

from .bairros import get_bairro_escola, get_bairros_proximos, distancias_bairro
from .parser_vagas_pdf import normalizar_serie
from .progressao_engine import processar, chave_turma, SEQUENCIA, SO_ESTADUAIS

TETO_SERIE = {'GT 0': 15, 'GT 1': 20, 'GT 2': 20, 'GT 3': 20, 'GT 4': 25, 'GT 5': 25,
              **{f'{i}º ANO': 30 for i in range(1, 6)}, **{f'{i}º ANO': 35 for i in range(6, 10)}}
FAIXAS = [('GT 0', ['GT 0']), ('GT 1 a GT 3', ['GT 1', 'GT 2', 'GT 3']), ('GT 4 e GT 5', ['GT 4', 'GT 5']),
          ('1º ao 5º ano', ['1º ANO']), ('6º ao 9º ano', ['6º ANO'])]
EXCEDENTES_POR_SALA = 5
M2_RESERVA, M2_POR_ALUNO = 2.5, 1.3
MAX_RODADAS = 8


# ── capacidade ------------------------------------------------------
def familia(serie: str) -> str:
    return 'INFANTIL' if serie.startswith('GT') else 'FUNDAMENTAL'


def capacidade_pela_area(area_m2) -> int:
    """(m² − 2,5) ÷ 1,3, arredondado ao inteiro mais próximo (48 m² → 35)."""
    if not area_m2 or area_m2 <= M2_RESERVA:
        return 0
    return int(math.floor((area_m2 - M2_RESERVA) / M2_POR_ALUNO + 0.5 + 1e-9))


def capacidade_sala(serie: str, area_m2) -> int:
    """Quantos alunos a sala comporta se atender `serie` (0 = não dá para calcular)."""
    teto = TETO_SERIE.get(normalizar_serie(serie))
    return min(teto, capacidade_pela_area(area_m2)) if teto else 0


def inventario_salas(vagas_mun: dict, inativas=()) -> list:
    """Uma linha por turma (sala + turno): metragem, vagas do relatório e quanto cabe em cada faixa."""
    inativas = set(inativas or [])
    linhas = []
    for escola, series in vagas_mun.items():
        if escola in inativas:
            continue
        nomes = {normalizar_serie(s) for s in series}
        tipo = 'CEI' if all(s.startswith('GT') for s in nomes) else 'Escola'
        for serie, turmas in series.items():
            serie = normalizar_serie(serie)
            for t in turmas:
                area = float(t.get('area_m2') or 0)
                teorica = capacidade_sala(serie, area)
                linhas.append({
                    'escola': escola, 'bairro': get_bairro_escola(escola), 'tipo': tipo,
                    'turma': t['turma'], 'sala': t.get('sala') or '', 'turno': t['turno'], 'serie': serie,
                    'area_m2': area, 'vagas_relatorio': t['vagas_existentes'], 'ocupadas': t['vagas_ocupadas'],
                    'cap_area': capacidade_pela_area(area), 'cap_teorica': teorica,
                    'diferenca': (t['vagas_existentes'] - teorica) if area else None,
                    'cap_faixa': {nome: capacidade_sala(series_f[0], area) for nome, series_f in FAIXAS},
                    'excedentes_reserva': EXCEDENTES_POR_SALA,
                    'excedentes_usados': t.get('vagas_excedentes', 0),
                })
    linhas.sort(key=lambda r: (r['escola'], SEQUENCIA.index(r['serie']) if r['serie'] in SEQUENCIA else 99, r['turma']))
    return linhas


# ── projeção --------------------------------------------------------
def _slots(vagas_mun, inativas):
    """{escola: [slot]} — cada turma (sala + turno) é uma peça que pode mudar de série."""
    inativas, out = set(inativas or []), {}
    for escola, series in vagas_mun.items():
        if escola in inativas:
            continue
        for serie, turmas in series.items():
            for t in turmas:
                out.setdefault(escola, []).append({
                    'escola': escola, 'serie': normalizar_serie(serie), 'turma': t['turma'], 'turno': t['turno'],
                    'sala': t.get('sala') or '', 'area': float(t.get('area_m2') or 0),
                    'vagas': t['vagas_existentes'], 'ocupadas': t['vagas_ocupadas'],
                    'chave': chave_turma(escola, serie, t['turma'], t['turno'])})
    return out


def _tier_bairro(bairro_origem, bairro, vizinhos, dist):
    if bairro_origem and bairro == bairro_origem:
        return 0, 0
    if bairro in vizinhos:
        return 1, vizinhos.index(bairro)
    return 2, dist.get(bairro) or 9999


def _melhor_plano(t, escola, slots, series_atuais, familias, folga, convertidas, params, bairros, vizinhos, dist):
    """Menor conjunto de salas de `escola` que vira a série da turma `t`; None se não der."""
    T, N = t['serie_destino'], t['total_alunos']
    if T not in series_atuais[escola] and not params['abrir_series']:
        return None
    melhores = None
    turnos = sorted({s['turno'] for s in slots})        # ordem fixa: o resultado não pode variar de uma execução para outra
    for turno in turnos:
        ja_tem = folga.get((escola, T, turno), 0)
        precisa = max(0, N - ja_tem)
        local, cand = dict(folga), []
        for s in slots:
            if s['chave'] in convertidas or s['serie'] == T or s['turno'] != turno:
                continue
            mesma_etapa = familia(s['serie']) == familia(T)
            if not mesma_etapa and not (params['entre_etapas'] and len(familias[escola]) > 1):
                continue
            novo = capacidade_sala(T, s['area'])
            if novo <= 0 or s['vagas'] <= 0:
                continue
            cand.append((novo, s))
        escolhidas, total = [], 0
        if precisa == 0:
            continue                       # já cabia: a progressão teria alocado
        salto = lambda c: abs(SEQUENCIA.index(c[1]['serie']) - SEQUENCIA.index(T))      # prefere série mais próxima
        unica = sorted([c for c in cand if c[0] >= precisa], key=lambda c: (c[0], salto(c)))
        ordem = unica + sorted([c for c in cand if c not in unica], key=lambda c: (-c[0], salto(c)))
        for novo, s in ordem:
            pool = (escola, s['serie'], turno)
            if local.get(pool, 0) < s['vagas']:
                continue                   # a sala não está ociosa por inteiro
            local[pool] -= s['vagas']
            escolhidas.append((novo, s)); total += novo
            if total >= precisa:
                break
        if total < precisa:
            continue
        tier = _tier_bairro(t['bairro_origem'], bairros[escola], vizinhos, dist)
        chave = (tier, escola != t['escola_origem'], T not in series_atuais[escola], len(escolhidas), total - precisa)
        if melhores is None or chave < melhores[0]:
            melhores = (chave, turno, escolhidas, ja_tem)
    return melhores


def _aplicar(plano, t, escola, T, folga, conv, convertidas):
    _, turno, escolhidas, ja_tem = plano
    ganho = 0
    for novo, s in escolhidas:
        conv[s['chave']] = {'escola': escola, 'serie': s['serie'], 'turma': s['turma'], 'turno': s['turno'],
                            'serie_nova': T, 'vagas_novas': novo, 'vagas_antes': s['vagas'], 'sala': s['sala'],
                            'area_m2': s['area'],
                            'motivo': f"{t['escola_origem']} · {t['turma']} ({t['total_alunos']} alunos) precisa de {T}"}
        convertidas.add(s['chave'])
        folga[(escola, s['serie'], turno)] -= s['vagas']
        ganho += novo
    folga[(escola, T, turno)] = folga.get((escola, T, turno), 0) + ganho - t['total_alunos']


def _sem_vaga(res):
    return [t for t in res['turmas'] if t['status'] == 'sem_vaga']


def calcular_projecao(vagas_mun: dict, vagas_est=None, inativas=(), params=None) -> dict:
    params = {'abrir_series': True, 'entre_etapas': False, **(params or {})}
    vagas_est = vagas_est or []
    slots = _slots(vagas_mun, inativas)
    series_atuais = {e: {s['serie'] for s in ss} for e, ss in slots.items()}
    familias = {e: {familia(s) for s in sr} for e, sr in series_atuais.items()}
    bairros = {e: get_bairro_escola(e) for e in slots}

    base = processar(vagas_mun, vagas_est, inativas)
    conv, convertidas = {}, set()
    res = base
    for _ in range(MAX_RODADAS):
        # séries que só existem em escola estadual (9º ano → ensino médio) não se resolvem com sala municipal
        pendentes = sorted((t for t in _sem_vaga(res) if t['serie_destino'] not in SO_ESTADUAIS),
                           key=lambda t: (-t['total_alunos'], t['escola_origem'], t['turma']))
        if not pendentes:
            break
        folga = {(d['escola'], d['serie'], d['turno']): d['restantes'] for d in res['destinos'] if d['tipo'] == 'MUNICIPAL'}
        houve = False
        for t in pendentes:
            vizinhos, dist = get_bairros_proximos(t['bairro_origem']), distancias_bairro(t['bairro_origem'])
            melhor = None
            for escola, ss in slots.items():
                p = _melhor_plano(t, escola, ss, series_atuais, familias, folga, convertidas, params, bairros, vizinhos, dist)
                if p and (melhor is None or p[0] < melhor[1][0]):
                    melhor = (escola, p)
            if melhor:
                _aplicar(melhor[1], t, melhor[0], t['serie_destino'], folga, conv, convertidas)
                houve = True
        if not houve:
            break
        res = processar(vagas_mun, vagas_est, inativas, list(conv.values()))

    # remove conversões que não mudaram o resultado
    pior = res['resumo']['alunos_sem_vaga']
    for chave in list(conv)[::-1]:
        teste = {k: v for k, v in conv.items() if k != chave}
        r = processar(vagas_mun, vagas_est, inativas, list(teste.values()))
        if r['resumo']['alunos_sem_vaga'] <= pior:
            conv, res, pior = teste, r, r['resumo']['alunos_sem_vaga']
    final = processar(vagas_mun, vagas_est, inativas, list(conv.values()))
    saida = _montar_saida(vagas_mun, inativas, params, base, final, conv, bairros)
    saida['salas'] = inventario_salas(vagas_mun, inativas)
    return saida


def _montar_saida(vagas_mun, inativas, params, base, final, conv, bairros):
    chave_t = lambda t: (t['escola_origem'], t['turma'], t['serie_atual'], t['turno'])
    antes = {chave_t(t): t for t in base['turmas']}
    resolvidas = [{'escola_origem': t['escola_origem'], 'bairro_origem': t['bairro_origem'], 'turma': t['turma'],
                   'serie_atual': t['serie_atual'], 'serie_destino': t['serie_destino'], 'total_alunos': t['total_alunos'],
                   'escola_destino': t['escola_sugerida']['escola'], 'turno_destino': t['escola_sugerida']['turno'],
                   'fica_na_escola': t['escola_sugerida'].get('fica_na_escola', False)}
                  for t in final['turmas']
                  if t['status'] == 'ok' and antes[chave_t(t)]['status'] == 'sem_vaga']
    perderam = [{'escola_origem': t['escola_origem'], 'turma': t['turma'], 'serie_destino': t['serie_destino'],
                 'total_alunos': t['total_alunos'], 'tinha_vaga_em': antes[chave_t(t)]['escola_sugerida']['escola']}
                for t in final['turmas'] if t['status'] != 'ok' and antes[chave_t(t)]['status'] == 'ok']
    ainda = [{k: t[k] for k in ('escola_origem', 'bairro_origem', 'turma', 'serie_atual', 'serie_destino', 'total_alunos', 'turno')}
             for t in final['turmas'] if t['status'] == 'sem_vaga']

    atendidos = {}                         # alunos que a progressão final colocou em cada série/turno de cada escola
    for t in final['turmas']:
        e = t['escola_sugerida']
        if t['status'] == 'ok' and e['tipo'] == 'MUNICIPAL':
            k = (e['escola'], t['serie_destino'], e['turno'])
            atendidos[k] = atendidos.get(k, 0) + t['total_alunos']
    series_hoje = {e: {normalizar_serie(s) for s in ss} for e, ss in vagas_mun.items()}

    salas = [{**c, 'bairro': bairros.get(c['escola']) or get_bairro_escola(c['escola']),
              'abre_serie_nova': c['serie_nova'] not in series_hoje[c['escola']],
              'serie_antes': c['serie']} for c in conv.values()]
    salas.sort(key=lambda c: (c['escola'], c['serie_nova'], c['turno'], c['sala']))
    pools = {}
    for c in salas:
        k = (c['escola'], c['serie_nova'], c['turno'])
        p = pools.setdefault(k, {'escola': c['escola'], 'bairro': c['bairro'], 'serie': c['serie_nova'],
                                 'turno': c['turno'], 'salas': 0, 'vagas_novas': 0, 'vagas_retiradas': 0,
                                 'abre_serie_nova': c['abre_serie_nova'], 'alunos_alocados': atendidos.get(k, 0)})
        p['salas'] += 1; p['vagas_novas'] += c['vagas_novas']; p['vagas_retiradas'] += c['vagas_antes']
    destinos = sorted(pools.values(), key=lambda p: (p['escola'], p['serie']))

    por_serie = {}
    for fase, r in (('antes', base), ('depois', final)):
        for t in r['turmas']:
            d = por_serie.setdefault(t['serie_destino'], {'serie': t['serie_destino'], 'alunos': 0,
                                                          'sem_vaga_antes': 0, 'sem_vaga_depois': 0})
            if fase == 'antes':
                d['alunos'] += t['total_alunos']
            if t['status'] == 'sem_vaga':
                d['sem_vaga_' + fase] += t['total_alunos']
    por_serie = sorted(por_serie.values(), key=lambda d: SEQUENCIA.index(d['serie']) if d['serie'] in SEQUENCIA else 99)

    folga = {}
    for d in final['destinos']:
        if d['tipo'] == 'MUNICIPAL' and d['restantes'] > 0:
            folga[d['serie']] = folga.get(d['serie'], 0) + d['restantes']

    avisos = []
    sem_area = sum(1 for ss in vagas_mun.values() for s in ss.values() for t in s
                   if not t.get('area_m2') and t['vagas_existentes'] > 0)
    if sem_area:
        avisos.append(f'{sem_area} turma(s) com vagas mas sem metragem no PDF: essas salas não entram na projeção.')
    if any(not b for b in bairros.values()):
        avisos.append('Há unidade(s) sem bairro cadastrado: a proximidade delas é tratada como "distante".')
    so_estado = sum(t['total_alunos'] for t in final['turmas'] if t['status'] == 'sem_vaga' and t['serie_destino'] in SO_ESTADUAIS)
    if so_estado:
        avisos.append(f'{so_estado} alunos do 9º ano seguem sem vaga no 1º ano do ensino médio: essa série só existe em escola '
                      f'estadual, então salas municipais não resolvem. Cadastre as vagas do estado (passo 3) para ver o saldo.')
    if perderam:
        avisos.append(f'{len(perderam)} turma(s) que tinham vaga sem a projeção ficaram sem vaga com ela: a mesma vaga passou a '
                      f'atender mais alunos de outras turmas (veja a lista "Perderam a vaga"). Revise antes de decidir.')
    if params['entre_etapas']:
        avisos.append('Conversão entre Educação Infantil e Fundamental ligada (só em unidades que já oferecem as duas).')

    resumo = {
        'perderam_vaga': len(perderam),
        'antes': base['resumo'], 'depois': final['resumo'],
        'salas_convertidas': len(salas), 'escolas_afetadas': len({c['escola'] for c in salas}),
        'vagas_criadas': sum(c['vagas_novas'] for c in salas), 'vagas_retiradas': sum(c['vagas_antes'] for c in salas),
        'turmas_resolvidas': len(resolvidas), 'alunos_resolvidos': sum(t['total_alunos'] for t in resolvidas),
        'abrem_serie_nova': sum(1 for p in destinos if p['abre_serie_nova']),
        'folga_por_serie': folga,
    }
    return {'params': params, 'resumo': resumo, 'por_serie': por_serie, 'salas_convertidas': salas,
            'destinos_ampliados': destinos, 'turmas_resolvidas': resolvidas, 'turmas_sem_vaga': ainda,
            'turmas_perderam_vaga': perderam,
            'avisos': avisos, 'conversoes': list(conv.values())}