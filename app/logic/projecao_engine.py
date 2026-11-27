"""
Motor de PROJEÇÃO DE SALAS — remanejamento de turmas DENTRO de cada unidade.

Esta etapa nunca move aluno de uma unidade para outra (isso é a Progressão). Ela só decide, unidade
por unidade, que série cada sala/turno deve atender no ano seguinte para que os alunos da própria
unidade caibam da melhor maneira possível. Trabalha só com contagens do PDF (nenhum dado de aluno).

Regras de capacidade
--------------------
* Teto por série: GT 0 = 15 · GT 1 a GT 3 = 20 · GT 4 e GT 5 = 25 · 1º ao 5º ano = 30 · 6º ao 9º ano = 35.
* Capacidade física da sala: (m² − 2,5) ÷ 1,3, arredondado ao inteiro mais próximo (48 m² → 35).
* Vagas de uma sala numa série = o MENOR entre o teto da série e a capacidade física.
* Até 5 alunos EXCEDENTES por sala ficam de reserva (ordem judicial etc.) e nunca entram nas contas.

Como a projeção decide (para cada unidade)
------------------------------------------
1. Demanda do ano seguinte numa série T = alunos da série anterior (T−1) que sobem para ela na própria
   unidade (a primeira série da unidade não recebe ninguém de dentro).
2. Vagas de T = soma das vagas das salas que hoje atendem T (número do relatório).
3. Se faltam vagas em T, procura salas que sobram em outra série S: a sala só pode sair de S se, sem ela,
   S ainda comporta todos os alunos que sobem para S.  Prefere salas de séries que não são a série de
   entrada da unidade (a vaga de entrada é a que a Progressão usa para alunos vindos de fora), depois
   menos salas, menos vaga desperdiçada e série mais próxima.  A sala convertida passa a valer a
   capacidade pela metragem na série nova.
4. Opcional: se a escola não oferece a série seguinte à sua última série, converte salas ociosas para
   que a turma que sairia continue na escola (só se couber a turma inteira).
Nunca zera uma série que a unidade oferece hoje. Opção: proteger a série de entrada (não tirar salas dela).
"""
import math

from .bairros import get_bairro_escola
from .parser_vagas_pdf import normalizar_serie
from .progressao_engine import SEQUENCIA, SO_ESTADUAIS, chave_turma

TETO_SERIE = {'GT 0': 15, 'GT 1': 20, 'GT 2': 20, 'GT 3': 20, 'GT 4': 25, 'GT 5': 25,
              **{f'{i}º ANO': 30 for i in range(1, 6)}, **{f'{i}º ANO': 35 for i in range(6, 10)}}
FAIXAS = [('GT 0', ['GT 0']), ('GT 1 a GT 3', ['GT 1', 'GT 2', 'GT 3']), ('GT 4 e GT 5', ['GT 4', 'GT 5']),
          ('1º ao 5º ano', ['1º ANO']), ('6º ao 9º ano', ['6º ANO'])]
EXCEDENTES_POR_SALA = 5
M2_RESERVA, M2_POR_ALUNO = 2.5, 1.3


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


def _anterior(serie):
    i = SEQUENCIA.index(serie) if serie in SEQUENCIA else 0
    return SEQUENCIA[i - 1] if i > 0 else None


def _proxima(serie):
    i = SEQUENCIA.index(serie) if serie in SEQUENCIA else len(SEQUENCIA)
    return SEQUENCIA[i + 1] if i + 1 < len(SEQUENCIA) else None


def inventario_salas(vagas_mun: dict, inativas=()) -> list:
    """Uma linha por turma (sala + turno): metragem, vagas do relatório e quanto cabe pela área."""
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


# ── projeção, unidade por unidade ----------------------------------
def _slots(series: dict) -> list:
    out = []
    for serie, turmas in series.items():
        for t in turmas:
            out.append({'serie': normalizar_serie(serie), 'turma': t['turma'], 'turno': t['turno'],
                        'sala': t.get('sala') or '', 'area': float(t.get('area_m2') or 0),
                        'vagas': t['vagas_existentes'], 'ocupadas': t['vagas_ocupadas']})
    return out


class _Unidade:
    """Estado de uma unidade durante o cálculo: que série cada sala atende no ano seguinte."""

    def __init__(self, escola, series, params):
        self.escola, self.params = escola, params
        self.slots = _slots(series)
        for i, s in enumerate(self.slots):
            s['id'], s['serie_nova'], s['vagas_novas'] = i, s['serie'], s['vagas']
            s['mudou'], s['abre'], s['motivo'] = False, False, ''
        self.hoje = {s['serie'] for s in self.slots}
        self.ocup = {}
        for s in self.slots:
            self.ocup[s['serie']] = self.ocup.get(s['serie'], 0) + s['ocupadas']
        self.tem_infantil = any(familia(x) == 'INFANTIL' for x in self.hoje)
        self.tem_fund = any(familia(x) == 'FUNDAMENTAL' for x in self.hoje)
        self.vagas_antes = {t: self.cap(t) for t in self.hoje}

    # alunos da própria unidade que sobem para T
    def sobem(self, T):
        a = _anterior(T)
        return self.ocup.get(a, 0) if a in self.hoje else 0

    def cap(self, T):
        return sum(s['vagas_novas'] for s in self.slots if s['serie_nova'] == T)

    def salas_em(self, T):
        return sum(1 for s in self.slots if s['serie_nova'] == T)

    def entrada(self, S):
        """Série de entrada: não recebe aluno de dentro da unidade (a vaga dela serve a quem vem de fora)."""
        return _anterior(S) not in self.hoje

    def sobra(self, S):
        return self.cap(S) - self.sobem(S)

    def pode_virar(self, s, T):
        S = s['serie_nova']
        if S == T or s['mudou'] or s['vagas'] <= 0 or S not in TETO_SERIE or T not in TETO_SERIE:
            return 0
        if familia(S) != familia(T) and not (self.params['entre_etapas'] and self.tem_infantil and self.tem_fund):
            return 0
        if S in self.hoje and self.salas_em(S) <= 1:
            return 0                                   # nunca zera uma série que a unidade já oferece
        if self.sobra(S) < s['vagas_novas']:
            return 0                                   # a sala faz falta para quem sobe para S
        if self.params['proteger_entrada'] and self.entrada(S):
            return 0                                   # opção: não mexer na série de entrada da unidade
        return capacidade_sala(T, s['area'])

    def converter(self, T, falta, abre, motivo):
        """Converte salas para T até cobrir `falta` (False se não der). Prefere série que não é de entrada."""
        feitas = []
        while falta > 0:
            cands = [(self.pode_virar(s, T), s) for s in self.slots]
            cands = [(novo, s) for novo, s in cands if novo > 0]
            if not cands:
                break
            salto = lambda c: abs(SEQUENCIA.index(c[1]['serie_nova']) - SEQUENCIA.index(T))
            melhor = None
            for entrada in (False, True):
                grupo = [c for c in cands if self.entrada(c[1]['serie_nova']) == entrada]
                if not grupo:
                    continue
                cabe = sorted([c for c in grupo if c[0] >= falta], key=lambda c: (c[0], salto(c), c[1]['id']))
                melhor = cabe[0] if cabe else sorted(grupo, key=lambda c: (-c[0], salto(c), c[1]['id']))[0]
                break
            novo, s = melhor
            s.update(origem_entrada=self.entrada(s['serie_nova']), origem_serie=s['serie_nova'],
                     origem_sobra=self.sobra(s['serie_nova']), origem_sobem=self.sobem(s['serie_nova']))
            s['serie_nova'], s['vagas_novas'], s['mudou'], s['abre'], s['motivo'] = T, novo, True, abre, motivo
            feitas.append(s)
            falta -= novo
        return feitas, falta

    def desfazer(self, feitas):
        for s in feitas:
            s['serie_nova'], s['vagas_novas'], s['mudou'], s['abre'], s['motivo'] = s['serie'], s['vagas'], False, False, ''


def _projetar_unidade(escola, series, params):
    u = _Unidade(escola, series, params)
    falta0 = {T: max(0, u.sobem(T) - u.cap(T)) for T in u.hoje if T in TETO_SERIE}
    # 1) séries que a unidade já oferece e não comportam quem sobe para elas
    for T in sorted(falta0, key=lambda t: -falta0[t]):
        f = max(0, u.sobem(T) - u.cap(T))
        if f:
            u.converter(T, f, False, f"{u.sobem(T)} alunos sobem de {_anterior(T)} e só havia {u.vagas_antes[T]} vagas em {T}")
    # 2) opcional: abrir a série seguinte para a turma final continuar na escola
    nao_abertas, abertas, reten = [], [], {}
    if params['abrir_series']:
        finais = {}
        for S in u.hoje:
            T = _proxima(S)
            if T in TETO_SERIE and T not in u.hoje and u.ocup.get(S, 0) > 0:
                finais[T] = u.ocup[S]
        for T in sorted(finais, key=lambda t: -finais[t]):
            u.hoje.add(T); u.ocup.setdefault(T, 0); u.vagas_antes.setdefault(T, 0)
            S = _anterior(T)
            feitas, resta = u.converter(T, finais[T], True,
                                        f"a turma final de {S} ({finais[T]} alunos) deixa de sair da unidade")
            if resta > 0:
                u.desfazer(feitas); u.hoje.discard(T)
                nao_abertas.append({'serie': T, 'alunos': finais[T], 'faltam': resta})
            else:
                abertas.append(T); reten[T] = finais[T]
    return u, falta0, abertas, nao_abertas, reten


def calcular_projecao(vagas_mun: dict, inativas=(), params=None) -> dict:
    params = {'abrir_series': False, 'entre_etapas': False, 'proteger_entrada': False, **(params or {})}
    inativas = set(inativas or [])
    balanco, salas, conv, unidades, avisos = [], [], [], [], []
    por_serie, entrada_delta = {}, {}
    saem_antes = saem_depois = sem_area = 0

    for escola, series in vagas_mun.items():
        if escola in inativas:
            continue
        u, falta0, abertas, nao_abertas, reten = _projetar_unidade(escola, series, params)
        bairro = get_bairro_escola(escola)
        sem_area += sum(1 for s in u.slots if not s['area'] and s['vagas'] > 0)
        tocadas = {s['serie_nova'] for s in u.slots if s['mudou']} | {s['serie'] for s in u.slots if s['mudou']}

        nao_cabem = 0
        for T in sorted(u.hoje, key=lambda t: SEQUENCIA.index(t) if t in SEQUENCIA else 99):
            if T not in TETO_SERIE:
                continue
            aberta = T in abertas
            sobem = reten[T] if aberta else u.sobem(T)
            v_antes, v_depois = u.vagas_antes.get(T, 0), u.cap(T)
            f_antes = 0 if aberta else max(0, sobem - v_antes)
            f_depois = max(0, sobem - v_depois)
            s_antes, s_depois = max(0, v_antes - sobem), max(0, v_depois - sobem)
            nao_cabem += f_depois
            balanco.append({'escola': escola, 'bairro': bairro, 'serie': T, 'sobem': sobem, 'vagas_antes': v_antes,
                            'vagas_depois': v_depois, 'falta_antes': f_antes, 'falta_depois': f_depois,
                            'sobra_antes': s_antes, 'sobra_depois': s_depois, 'aberta': aberta,
                            'mudou': T in tocadas, 'entrada': u.entrada(T) and not aberta})
            d = por_serie.setdefault(T, {'serie': T, 'sobem': 0, 'falta_antes': 0, 'falta_depois': 0,
                                         'sobra_antes': 0, 'sobra_depois': 0})
            for k, v in (('sobem', sobem), ('falta_antes', f_antes), ('falta_depois', f_depois),
                         ('sobra_antes', s_antes), ('sobra_depois', s_depois)):
                d[k] += v

        # alunos da série final de cada unidade: saem dela (a Progressão cuida deles), a não ser que a série seja aberta
        for S in {s['serie'] for s in u.slots}:
            T, n = _proxima(S), u.ocup.get(S, 0)
            if n and T and (T in SO_ESTADUAIS or (T in TETO_SERIE and T not in {s['serie'] for s in u.slots})):
                saem_antes += n
                if T not in abertas:
                    saem_depois += n

        for s in u.slots:
            if not s['mudou']:
                continue
            reduz = bool(s.get('origem_entrada'))
            origem = (f"{s['origem_serie']} é a série de entrada da unidade: a vaga dela serviria a alunos de fora"
                      if reduz else
                      f"{s['origem_serie']} tinha {s['origem_sobra'] + s['origem_sobem']} vagas e só {s['origem_sobem']} alunos sobem para ela")
            salas.append({'escola': escola, 'bairro': bairro, 'sala': s['sala'], 'turno': s['turno'], 'turma': s['turma'],
                          'serie_antes': s['serie'], 'serie_nova': s['serie_nova'], 'vagas_antes': s['vagas'],
                          'vagas_novas': s['vagas_novas'], 'area_m2': s['area'], 'abre_serie_nova': s['abre'],
                          'motivo': s['motivo'], 'origem': origem, 'reduz_entrada': reduz})
            conv.append({'escola': escola, 'serie': s['serie'], 'turma': s['turma'], 'turno': s['turno'],
                         'serie_nova': s['serie_nova'], 'vagas_novas': s['vagas_novas'], 'vagas_antes': s['vagas'],
                         'sala': s['sala'], 'area_m2': s['area'], 'abre_serie': s['abre']})
            if reduz:
                entrada_delta[s['serie']] = entrada_delta.get(s['serie'], 0) + s['vagas']
        unidades.append({'escola': escola, 'bairro': bairro, 'salas_convertidas': sum(1 for s in u.slots if s['mudou']),
                         'nao_cabem': nao_cabem, 'abertas': abertas, 'nao_abertas': nao_abertas})

    por_serie = sorted(por_serie.values(), key=lambda d: SEQUENCIA.index(d['serie']))
    resumo = {
        'unidades': len(unidades), 'unidades_alteradas': sum(1 for x in unidades if x['salas_convertidas']),
        'salas_convertidas': len(salas), 'abrem_serie_nova': sum(len(x['abertas']) for x in unidades),
        'nao_cabem_antes': sum(b['falta_antes'] for b in balanco),
        'nao_cabem_depois': sum(b['falta_depois'] for b in balanco),
        'alunos_que_continuam': sum(b['sobem'] for b in balanco if b['aberta']),
        'alunos_saem_antes': saem_antes, 'alunos_saem_depois': saem_depois,
        'vagas_entrada_retiradas': sum(entrada_delta.values()), 'entrada_retirada_por_serie': entrada_delta,
        'sobra_antes': sum(b['sobra_antes'] for b in balanco), 'sobra_depois': sum(b['sobra_depois'] for b in balanco),
    }
    if sem_area:
        avisos.append(f'{sem_area} turma(s) com vagas mas sem metragem no PDF: essas salas não podem ser convertidas.')
    if resumo['vagas_entrada_retiradas']:
        avisos.append(f"{resumo['vagas_entrada_retiradas']} vagas saem de séries de entrada de unidades. Essas vagas serviriam a "
                      f"alunos vindos de outras unidades na Progressão; confira o efeito lá antes de decidir.")
    for x in unidades:
        for n in x['nao_abertas']:
            avisos.append(f"{x['escola']}: não há salas ociosas para abrir o {n['serie']} (faltam {n['faltam']} vagas); a turma continua saindo.")
    if params['entre_etapas']:
        avisos.append('Conversão entre Educação Infantil e Fundamental ligada (só em unidades que já oferecem as duas).')

    salas.sort(key=lambda c: (c['escola'], c['serie_nova'], c['turno'], c['sala']))
    return {'params': params, 'resumo': resumo, 'por_serie': por_serie, 'balanco': balanco, 'salas_convertidas': salas,
            'unidades': unidades, 'avisos': avisos, 'conversoes': conv, 'salas': inventario_salas(vagas_mun, inativas)}