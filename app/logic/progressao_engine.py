"""
Motor de progressão — 100% automático, a partir do PDF de vagas + vagas estaduais.

Regra de progressão anual
-------------------------
Cada unidade (escola ou CEI) oferece uma sequência de séries. A ÚLTIMA série que
ela oferece é "terminal": os alunos dela precisam ir para a próxima série em outra
unidade.  Ex.: escola até o 5º ano  -> 5º vai para o 6º ano;  até o 4º -> 5º ano;
até o 8º -> 9º ano;  CEI até GT 3 -> GT 4;  GT 5 -> 1º ano.
Sequência: GT 0..GT 5, 1º..9º ANO  (9º ANO não tem próxima série aqui).

Alocação
--------
* A turma inteira vai para a MESMA escola (nunca é dividida).
* Vagas do ANO SEGUINTE (projeção): a série de destino se renova, pois os alunos de hoje
  avançam. Capacidade total (ocupadas + não ocupadas) da série, menos os alunos da série
  anterior que sobem DENTRO da própria escola.  Vagas estaduais = as informadas à mão.
* Prioridade: 1) estadual no mesmo bairro  2) estadual em bairro próximo
              3) municipal no mesmo bairro 4) municipal em bairro próximo
              5) estadual distante         6) municipal distante
* Ao alocar uma turma, as vagas usadas são descontadas para as próximas.
"""
from .bairros import get_bairro_escola, get_bairros_proximos, distancias_bairro
from .parser_vagas_pdf import normalizar_serie

SEQUENCIA = [f'GT {i}' for i in range(0, 6)] + [f'{i}º ANO' for i in range(1, 10)]
TIPOS_TIER = {('ESTADUAL', 'mesmo'): 1, ('ESTADUAL', 'proximo'): 2,
              ('MUNICIPAL', 'mesmo'): 3, ('MUNICIPAL', 'proximo'): 4,
              ('ESTADUAL', 'distante'): 5, ('MUNICIPAL', 'distante'): 6}
ROTULO_PROX = {'mesmo': 'Mesmo bairro', 'proximo': 'Bairro próximo', 'distante': 'Bairro distante'}


def proxima_serie(serie: str):
    s = normalizar_serie(serie)
    if s in SEQUENCIA:
        i = SEQUENCIA.index(s)
        if i + 1 < len(SEQUENCIA):
            return SEQUENCIA[i + 1]
    return None


# ── vagas -----------------------------------------------------------
def _serie_anterior(serie: str):
    s = normalizar_serie(serie)
    if s in SEQUENCIA:
        i = SEQUENCIA.index(s)
        return SEQUENCIA[i - 1] if i > 0 else None
    return None


def chave_turma(escola: str, serie: str, turma: str, turno: str):
    """Identifica uma turma (= uma sala em um turno) dentro do PDF."""
    return (escola, normalizar_serie(serie), turma, turno)


def montar_capacidades(vagas_mun: dict, vagas_est: list, inativas=(), conversoes=None) -> list:
    """
    Uma linha por (escola, série, turno).
      total       = capacidade da série no ANO SEGUINTE (vagas existentes das salas que a atendem;
                    salas convertidas pela Projeção entram na série nova e saem da antiga)
      ocupadas / livres_hoje = situação de HOJE no PDF (informativo)
      fluxo       = alunos da série anterior que sobem para cá, na própria escola
      disponiveis = vagas do ANO SEGUINTE  = total − fluxo   (é o que a IA usa)
      abre_nova   = True quando a escola NÃO oferece essa série hoje e passa a oferecer por conversão
                    de sala; nesse caso os alunos da série anterior da própria escola não "sobem
                    sozinhos": eles entram na alocação como qualquer outra turma (fluxo = 0).
    conversoes: lista de {escola, serie, turma, turno, serie_nova, vagas_novas} (vem da Projeção).
    Sem conversões o resultado é idêntico ao da versão anterior.
    """
    inativas = set(inativas or [])
    conv = {chave_turma(c['escola'], c['serie'], c['turma'], c['turno']): c for c in (conversoes or [])}
    cap = []
    for escola, series in vagas_mun.items():
        if escola in inativas:
            continue
        bairro = get_bairro_escola(escola)
        agg = {}                                   # HOJE:    serie -> turno -> {e,o,d}
        proj = {}                                  # PROJETADO: serie -> turno -> vagas
        for serie, turmas in series.items():
            for t in turmas:
                a = agg.setdefault(normalizar_serie(serie), {}).setdefault(
                    t['turno'], {'e': 0, 'o': 0, 'd': 0})
                a['e'] += t['vagas_existentes']
                a['o'] += t['vagas_ocupadas']
                a['d'] += t['vagas_disponiveis']
                c = conv.get(chave_turma(escola, serie, t['turma'], t['turno']))
                destino, vagas = (normalizar_serie(c['serie_nova']), c['vagas_novas']) if c \
                    else (normalizar_serie(serie), t['vagas_existentes'])
                p = proj.setdefault(destino, {})
                p[t['turno']] = p.get(t['turno'], 0) + vagas
        for serie, turnos in proj.items():
            anterior = _serie_anterior(serie)
            nova = serie not in agg
            for turno, total in turnos.items():
                hoje = agg.get(serie, {}).get(turno, {'o': 0, 'd': 0})
                fluxo = 0 if (nova or not anterior) else agg.get(anterior, {}).get(turno, {}).get('o', 0)
                cap.append({'escola': escola, 'tipo': 'MUNICIPAL', 'bairro': bairro,
                            'serie': serie, 'turno': turno,
                            'total': total, 'ocupadas': hoje['o'], 'livres_hoje': hoje['d'],
                            'fluxo': fluxo, 'disponiveis': max(0, total - fluxo), 'abre_nova': nova})

    somados = {}
    for v in (vagas_est or []):
        n = int(v.get('vagas') or 0)
        if n <= 0 or not v.get('escola') or not v.get('serie'):
            continue
        chave = (v['escola'], normalizar_serie(v['serie']))
        somados[chave] = somados.get(chave, 0) + n
    for (escola, serie), n in somados.items():
        cap.append({'escola': escola, 'tipo': 'ESTADUAL', 'bairro': get_bairro_escola(escola),
                    'serie': serie, 'turno': 'QUALQUER',
                    'total': None, 'ocupadas': None, 'livres_hoje': None,
                    'fluxo': 0, 'disponiveis': n, 'abre_nova': False})
    return cap


def detectar_turmas(vagas_mun: dict, inativas=()) -> list:
    """Turmas da série final de cada unidade -> precisam de vaga na série seguinte."""
    inativas = set(inativas or [])
    itens = []
    for escola, series in vagas_mun.items():
        if escola in inativas:
            continue
        por_serie = {}
        for serie, turmas in series.items():
            por_serie.setdefault(normalizar_serie(serie), []).extend(turmas)
        for serie, turmas in por_serie.items():
            destino = proxima_serie(serie)
            if not destino or destino in por_serie:
                continue                      # não é a série final da unidade
            for t in turmas:
                if t['vagas_ocupadas'] > 0:
                    itens.append({'escola_origem': escola, 'bairro_origem': get_bairro_escola(escola),
                                  'turma': t['turma'], 'serie_atual': serie, 'serie_destino': destino,
                                  'turno': t['turno'], 'total_alunos': t['vagas_ocupadas']})
    return itens


# ── alocação --------------------------------------------------------
def _proximidade(bairro_origem, bairro_destino, vizinhos, dist):
    """('mesmo'|'proximo'|'distante', rank). Distantes são ordenados pelo nº de bairros de separação."""
    if bairro_origem and bairro_destino == bairro_origem:
        return 'mesmo', 0
    if bairro_destino in vizinhos:
        return 'proximo', vizinhos.index(bairro_destino) + 1
    saltos = dist.get(bairro_destino)
    return 'distante', (saltos * 100 if saltos else 9999)


def processar(vagas_mun: dict, vagas_est: list, inativas=(), conversoes=None) -> dict:
    cap = montar_capacidades(vagas_mun, vagas_est, inativas, conversoes)
    usadas = {}
    itens = detectar_turmas(vagas_mun, inativas)

    def candidatos(t):
        """Escolas da série de destino, da melhor para a pior, com as vagas que AINDA restam."""
        vizinhos = get_bairros_proximos(t['bairro_origem'])
        dist = distancias_bairro(t['bairro_origem'])
        lista = []
        for c in cap:
            if c['serie'] != t['serie_destino']:
                continue
            if c['escola'] == t['escola_origem'] and not c.get('abre_nova'):
                continue            # a própria escola só serve se ela passou a oferecer a série (Projeção)
            restante = c['disponiveis'] - usadas.get((c['escola'], c['serie'], c['turno']), 0)
            if restante <= 0:
                continue
            prox, rank = _proximidade(t['bairro_origem'], c['bairro'], vizinhos, dist)
            turno_ok = c['turno'] in (t['turno'], 'QUALQUER')
            lista.append({
                'escola': c['escola'], 'tipo': c['tipo'], 'bairro': c['bairro'] or 'não identificado',
                'turno': c['turno'], 'vagas_disponiveis': restante, 'proximidade': prox,
                'proximidade_rotulo': ROTULO_PROX[prox], 'turno_diferente': not turno_ok,
                'mesmo_bairro': prox == 'mesmo', 'fica_na_escola': c['escola'] == t['escola_origem'],
                '_chave': (c['escola'], c['serie'], c['turno']),
                '_ordem': (TIPOS_TIER[(c['tipo'], prox)], rank, not turno_ok, -restante),
            })
        lista.sort(key=lambda x: x['_ordem'])
        return lista

    # Ordem de atendimento: quem tem a MELHOR opção disponível (ex.: estadual no próprio bairro)
    # é atendido primeiro; em empate, a turma maior primeiro (cabe menos opções).
    def melhor_opcao(t):
        cabem = [c['_ordem'][0] for c in candidatos(t) if c['vagas_disponiveis'] >= t['total_alunos']]
        return min(cabem) if cabem else 99
    for t in itens:
        t['_prioridade'] = melhor_opcao(t)
    itens.sort(key=lambda t: (t['_prioridade'], -t['total_alunos'], t['escola_origem'], t['turma']))

    limpar = lambda c: {k: v for k, v in c.items() if not k.startswith('_')}
    for t in itens:
        lista = candidatos(t)
        cabem = [c for c in lista if c['vagas_disponiveis'] >= t['total_alunos']]
        escolhida = cabem[0] if cabem else None
        if escolhida:
            usadas[escolhida['_chave']] = usadas.get(escolhida['_chave'], 0) + t['total_alunos']
            outras = cabem[1:4]
        else:
            outras = sorted(lista, key=lambda x: -x['vagas_disponiveis'])[:3]
        t['escola_sugerida'] = limpar(escolhida) if escolhida else None
        t['sugestoes'] = [limpar(c) for c in outras]
        t['status'] = 'ok' if escolhida else 'sem_vaga'
        del t['_prioridade']

    itens.sort(key=lambda t: (t['escola_origem'], t['serie_atual'], t['turma']))

    destinos = []
    for c in cap:
        alocados = usadas.get((c['escola'], c['serie'], c['turno']), 0)
        destinos.append({**c, 'alocados': alocados, 'restantes': c['disponiveis'] - alocados})

    alocadas = [t for t in itens if t['status'] == 'ok']
    resumo = {
        'turmas': len(itens), 'alunos': sum(t['total_alunos'] for t in itens),
        'turmas_alocadas': len(alocadas),
        'alunos_alocados': sum(t['total_alunos'] for t in alocadas),
        'estadual': sum(1 for t in alocadas if t['escola_sugerida']['tipo'] == 'ESTADUAL'),
        'municipal': sum(1 for t in alocadas if t['escola_sugerida']['tipo'] == 'MUNICIPAL'),
        'sem_vaga': len(itens) - len(alocadas),
        'alunos_sem_vaga': sum(t['total_alunos'] for t in itens if t['status'] != 'ok'),
        'escolas_origem': len({t['escola_origem'] for t in itens}),
    }
    return {'turmas': itens, 'destinos': destinos, 'resumo': resumo}
