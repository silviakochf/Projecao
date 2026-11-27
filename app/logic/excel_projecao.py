"""Excel da projeção de salas (a partir do resultado de calcular_projecao)."""
import io
from datetime import datetime
from openpyxl import Workbook
from .excel_progressao import _titulo, _tabela, VERDE, AMARELO, VERMELHO, AZUL_CL, LARANJA
from .projecao_engine import FAIXAS


def gerar_excel_projecao(r: dict) -> io.BytesIO:
    R = r['resumo']
    sub = (f"Gerado em {datetime.now():%d/%m/%Y %H:%M}  |  {R['salas_convertidas']} salas em {R['unidades_alteradas']} unidades  |  "
           f"alunos que não cabem na própria unidade: {R['nao_cabem_antes']} → {R['nao_cabem_depois']}")
    wb = Workbook()

    # 1) Resumo
    ws = wb.active; ws.title = 'Resumo'
    _titulo(ws, 'G', 'PROJEÇÃO DE SALAS (DENTRO DE CADA UNIDADE) — RESUMO', sub)
    linhas = [[d['serie'], d['sobem'], d['falta_antes'], d['falta_depois'], d['falta_antes'] - d['falta_depois'],
               d['sobra_antes'], d['sobra_depois']] for d in r['por_serie']]
    _tabela(ws, 4, ['Série (ano seguinte)', 'Alunos que sobem da série anterior', 'Não cabem ANTES', 'Não cabem DEPOIS',
                    'Passam a caber', 'Vagas livres p/ alunos de fora ANTES', 'Vagas livres p/ alunos de fora DEPOIS'],
            linhas, [20, 22, 16, 16, 14, 22, 22],
            lambda v: VERDE if v[2] and not v[3] else (AMARELO if v[3] < v[2] else (VERMELHO if v[3] else None)),
            centro=(0, 1, 2, 3, 4, 5, 6))
    n = 6 + len(linhas)
    for i, a in enumerate(r.get('avisos', [])):
        ws.cell(row=n + i, column=1, value='⚠ ' + a)
    ws.cell(row=n + len(r.get('avisos', [])) + 1, column=1,
            value='Remanejamento SOMENTE dentro de cada unidade; trocas de unidade ficam na Progressão. Regras: teto por série (GT0=15, '
                  'GT1-3=20, GT4-5=25, 1º-5º=30, 6º-9º=35); capacidade física = (m² − 2,5) ÷ 1,3; excedentes (até 5 por sala) não entram.')

    # 2) Salas convertidas
    wc = wb.create_sheet('Salas convertidas')
    _titulo(wc, 'M', 'SALAS SUGERIDAS PARA MUDAR DE SÉRIE NO ANO SEGUINTE', sub)
    linhas = [[c['escola'], c['bairro'] or 'não identificado', c['sala'], c['turno'], c['serie_antes'], c['serie_nova'],
               c['vagas_antes'], c['vagas_novas'], c['vagas_novas'] - c['vagas_antes'], c['area_m2'],
               'SIM' if c['abre_serie_nova'] else 'não', 'SIM' if c['reduz_entrada'] else 'não',
               c['motivo'], c['origem']] for c in r['salas_convertidas']]
    _tabela(wc, 4, ['Unidade', 'Bairro', 'Sala', 'Turno', 'Série hoje', 'Série no ano seguinte', 'Vagas hoje', 'Vagas depois',
                    'Diferença', 'Área (m²)', 'Unidade passa a oferecer essa série?', 'Sai de série de entrada?',
                    'Por que mudar', 'De onde a sala sai'],
            linhas, [44, 18, 16, 10, 11, 14, 10, 10, 10, 10, 18, 14, 70, 70],
            lambda v: LARANJA if v[10] == 'SIM' else (AMARELO if v[11] == 'SIM' else AZUL_CL),
            centro=(3, 4, 5, 6, 7, 8, 9, 10, 11))

    # 3) Balanço por unidade e série
    wb_ = wb.create_sheet('Balanço por unidade')
    _titulo(wb_, 'L', 'ALUNOS QUE SOBEM × VAGAS, POR UNIDADE E SÉRIE (ANO SEGUINTE)', sub)
    linhas = [[b['escola'], b['bairro'] or 'não identificado', b['serie'], b['sobem'], b['vagas_antes'], b['vagas_depois'],
               b['falta_antes'], b['falta_depois'], b['sobra_antes'], b['sobra_depois'],
               'sim' if b['entrada'] else 'não', 'SIM' if b['aberta'] else ('mudou' if b['mudou'] else '')] for b in r['balanco']]
    _tabela(wb_, 4, ['Unidade', 'Bairro', 'Série', 'Alunos que sobem', 'Vagas ANTES', 'Vagas DEPOIS', 'Não cabem ANTES',
                     'Não cabem DEPOIS', 'Sobram p/ fora ANTES', 'Sobram p/ fora DEPOIS', 'Série de entrada?', 'Série aberta / alterada'],
            linhas, [44, 18, 10, 12, 10, 10, 12, 12, 12, 12, 10, 14],
            lambda v: VERMELHO if v[7] else (AMARELO if v[6] else (LARANJA if v[11] == 'SIM' else None)),
            centro=tuple(range(2, 12)))

    # 4) Ainda não cabem
    wn = wb.create_sheet('Ainda não cabem')
    _titulo(wn, 'F', 'SÉRIES EM QUE AINDA FALTA SALA PARA QUEM SOBE, MESMO COM A PROJEÇÃO', sub)
    linhas = [[b['escola'], b['bairro'] or 'não identificado', b['serie'], b['sobem'], b['vagas_depois'], b['falta_depois']]
              for b in r['balanco'] if b['falta_depois'] > 0]
    _tabela(wn, 4, ['Unidade', 'Bairro', 'Série', 'Alunos que sobem', 'Vagas depois', 'Não cabem'],
            linhas, [44, 18, 10, 14, 12, 12], lambda v: VERMELHO, centro=(2, 3, 4, 5))

    # 5) Capacidade das salas
    wk = wb.create_sheet('Capacidade das salas')
    nomes = [f for f, _ in FAIXAS]
    _titulo(wk, 'Q', 'QUANTOS ALUNOS CABEM EM CADA SALA', sub)
    linhas = []
    for s in r['salas']:
        linhas.append([s['escola'], s['bairro'] or 'não identificado', s['sala'] or '—', s['turno'], s['turma'], s['serie'],
                       s['area_m2'] or '—', s['vagas_relatorio'], s['cap_area'] if s['area_m2'] else '—',
                       s['cap_teorica'] if s['area_m2'] else '—',
                       ('' if s['diferenca'] is None else s['diferenca'])] + [s['cap_faixa'][n] if s['area_m2'] else '—' for n in nomes]
                     + [s['excedentes_reserva']])
    _tabela(wk, 4, ['Unidade', 'Bairro', 'Sala', 'Turno', 'Turma', 'Série hoje', 'Área (m²)', 'Vagas no relatório',
                    'Cabem pela área (m²−2,5)÷1,3', 'Cabem na série de hoje (área + teto)',
                    'Relatório − teórico'] + [f'Cabem: {n}' for n in nomes] + ['Reserva de excedentes'],
            linhas, [44, 18, 16, 10, 14, 10, 10, 11, 14, 14, 11, 10, 12, 12, 12, 12, 12],
            lambda v: AMARELO if isinstance(v[10], int) and v[10] != 0 else None,
            centro=tuple(range(3, 17)))

    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return buf