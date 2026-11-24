"""Excel da projeção de salas (a partir do resultado de calcular_projecao)."""
import io
from datetime import datetime
from openpyxl import Workbook
from .excel_progressao import (_titulo, _tabela, VERDE, AMARELO, VERMELHO, AZUL_CL, ROXO, LARANJA)
from .projecao_engine import FAIXAS


def gerar_excel_projecao(r: dict) -> io.BytesIO:
    R, ant, dep = r['resumo'], r['resumo']['antes'], r['resumo']['depois']
    sub = (f"Gerado em {datetime.now():%d/%m/%Y %H:%M}  |  {R['salas_convertidas']} salas em {R['escolas_afetadas']} escolas  |  "
           f"alunos sem vaga: {ant['alunos_sem_vaga']} → {dep['alunos_sem_vaga']}  |  "
           f"turmas sem vaga: {ant['sem_vaga']} → {dep['sem_vaga']}")
    wb = Workbook()

    # 1) Resumo
    ws = wb.active; ws.title = 'Resumo'
    _titulo(ws, 'F', 'PROJEÇÃO DE SALAS — RESUMO', sub)
    linhas = [[d['serie'], d['alunos'], d['sem_vaga_antes'], d['sem_vaga_depois'], d['sem_vaga_antes'] - d['sem_vaga_depois'],
               R['folga_por_serie'].get(d['serie'], 0)] for d in r['por_serie']]
    _tabela(ws, 4, ['Série de destino', 'Alunos que precisam trocar de unidade', 'Sem vaga ANTES',
                    'Sem vaga DEPOIS', 'Alunos que ganharam vaga', 'Vagas livres que ainda sobram na série (soltas: não dão uma sala inteira)'],
            linhas, [18, 22, 16, 16, 18, 30],
            lambda v: VERDE if v[2] and not v[3] else (AMARELO if v[3] < v[2] else (VERMELHO if v[3] else None)),
            centro=(0, 1, 2, 3, 4, 5))
    n = 6 + len(linhas)
    for i, a in enumerate(r.get('avisos', [])):
        c = ws.cell(row=n + i, column=1, value='⚠ ' + a)
    ws.cell(row=n + len(r.get('avisos', [])) + 1, column=1,
            value='Regras: teto por série (GT0=15, GT1-3=20, GT4-5=25, 1º-5º=30, 6º-9º=35); capacidade física = (m² − 2,5) ÷ 1,3; '
                  'excedentes (até 5 por sala) ficam de reserva e não entram.')

    # 2) Salas convertidas
    wc = wb.create_sheet('Salas convertidas')
    _titulo(wc, 'K', 'SALAS SUGERIDAS PARA MUDAR DE SÉRIE NO ANO SEGUINTE', sub)
    linhas = [[c['escola'], c['bairro'] or 'não identificado', c['sala'], c['turno'], c['serie_antes'], c['serie_nova'],
               c['vagas_antes'], c['vagas_novas'], c['vagas_novas'] - c['vagas_antes'], c['area_m2'],
               'SIM' if c['abre_serie_nova'] else 'não', c['motivo']] for c in r['salas_convertidas']]
    _tabela(wc, 4, ['Escola', 'Bairro', 'Sala', 'Turno', 'Série hoje', 'Série no ano seguinte', 'Vagas hoje',
                    'Vagas no ano seguinte', 'Diferença', 'Área (m²)', 'Escola passa a oferecer essa série?', 'Para atender'],
            linhas, [44, 18, 16, 10, 11, 14, 10, 14, 10, 10, 18, 70],
            lambda v: LARANJA if v[10] == 'SIM' else AZUL_CL, centro=(3, 4, 5, 6, 7, 8, 9, 10))

    # 3) Escolas que ampliam
    we = wb.create_sheet('Escolas que ampliam')
    _titulo(we, 'I', 'ESCOLAS QUE GANHAM VAGAS EM UMA SÉRIE', sub)
    linhas = [[p['escola'], p['bairro'] or 'não identificado', p['serie'], p['turno'], p['salas'], p['vagas_retiradas'],
               p['vagas_novas'], p['alunos_alocados'], 'SIM' if p['abre_serie_nova'] else 'não'] for p in r['destinos_ampliados']]
    _tabela(we, 4, ['Escola', 'Bairro', 'Série', 'Turno', 'Salas convertidas', 'Vagas que saem de outras séries',
                    'Vagas que entram', 'Alunos alocados na série', 'Série nova na escola?'],
            linhas, [44, 18, 10, 10, 10, 16, 12, 14, 14], lambda v: LARANJA if v[8] == 'SIM' else AZUL_CL,
            centro=(2, 3, 4, 5, 6, 7, 8))

    # 4) Turmas que passam a ter vaga / sem vaga / perderam
    wr = wb.create_sheet('Turmas atendidas')
    _titulo(wr, 'H', 'TURMAS QUE GANHAM VAGA COM A PROJEÇÃO', sub)
    linhas = [[t['escola_origem'], t['bairro_origem'] or 'não identificado', t['turma'], t['serie_atual'], t['serie_destino'],
               t['total_alunos'], t['escola_destino'] + (' (continua na própria escola)' if t['fica_na_escola'] else ''),
               t['turno_destino']] for t in r['turmas_resolvidas']]
    _tabela(wr, 4, ['Escola de origem', 'Bairro', 'Turma', 'Série atual', 'Série destino', 'Alunos', 'Escola de destino', 'Turno'],
            linhas, [42, 18, 14, 10, 12, 8, 60, 10], lambda v: VERDE, centro=(3, 4, 5, 7))

    wv = wb.create_sheet('Ainda sem vaga')
    _titulo(wv, 'G', 'TURMAS QUE CONTINUAM SEM VAGA MESMO COM A PROJEÇÃO', sub)
    linhas = [[t['escola_origem'], t['bairro_origem'] or 'não identificado', t['turma'], t['serie_atual'], t['serie_destino'],
               t['turno'], t['total_alunos']] for t in r['turmas_sem_vaga']]
    _tabela(wv, 4, ['Escola de origem', 'Bairro', 'Turma', 'Série atual', 'Série destino', 'Turno', 'Alunos'],
            linhas, [42, 18, 14, 10, 12, 10, 8], lambda v: VERMELHO, centro=(3, 4, 5, 6))

    if r.get('turmas_perderam_vaga'):
        wp = wb.create_sheet('Perderam a vaga')
        _titulo(wp, 'E', 'ATENÇÃO: TURMAS QUE TINHAM VAGA SEM A PROJEÇÃO E FICARAM SEM', sub)
        linhas = [[t['escola_origem'], t['turma'], t['serie_destino'], t['total_alunos'], t['tinha_vaga_em']]
                  for t in r['turmas_perderam_vaga']]
        _tabela(wp, 4, ['Escola de origem', 'Turma', 'Série destino', 'Alunos', 'Tinha vaga em'],
                linhas, [42, 14, 12, 8, 60], lambda v: AMARELO, centro=(2, 3))

    # 5) Capacidade das salas (todas)
    wk = wb.create_sheet('Capacidade das salas')
    nomes = [f for f, _ in FAIXAS]
    _titulo(wk, 'O', 'QUANTOS ALUNOS CABEM EM CADA SALA', sub)
    linhas = []
    for s in r['salas']:
        linhas.append([s['escola'], s['bairro'] or 'não identificado', s['sala'] or '—', s['turno'], s['turma'], s['serie'],
                       s['area_m2'] or '—', s['vagas_relatorio'], s['cap_area'] if s['area_m2'] else '—',
                       s['cap_teorica'] if s['area_m2'] else '—',
                       ('' if s['diferenca'] is None else s['diferenca'])] + [s['cap_faixa'][n] if s['area_m2'] else '—' for n in nomes]
                     + [s['excedentes_reserva']])
    _tabela(wk, 4, ['Escola', 'Bairro', 'Sala', 'Turno', 'Turma', 'Série hoje', 'Área (m²)', 'Vagas no relatório',
                    'Cabem pela área (m²−2,5)÷1,3', 'Cabem na série de hoje (área + teto)',
                    'Relatório − teórico'] + [f'Cabem: {n}' for n in nomes] + ['Reserva de excedentes'],
            linhas, [44, 18, 16, 10, 14, 10, 10, 11, 14, 14, 11, 10, 12, 12, 12, 12, 12],
            lambda v: AMARELO if isinstance(v[10], int) and v[10] != 0 else None,
            centro=tuple(range(3, 17)))

    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return buf
