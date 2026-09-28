"""
excel_service.py
Serviço auxiliar para geração de relatórios Excel.
Centraliza operações comuns de formatação e estilos.
"""
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


# ── Constantes de cor ───────────────────────────────────────────
COLORS = {
    'primary':    '0A192F',
    'primary2':   '172A45',
    'gray_hdr':   '334155',
    'white':      'FFFFFF',
    'gray1':      'F8FAFC',
    'gray2':      'E2E8F0',
    'green_bg':   'D1FAE5',
    'green_fg':   '065F46',
    'red_bg':     'FEE2E2',
    'red_fg':     '991B1B',
    'yellow_bg':  'FEF9C3',
    'yellow_fg':  '854D0E',
    'blue_bg':    'DBEAFE',
    'blue_fg':    '1E40AF',
    'purple_bg':  'EDE9FE',
    'purple_fg':  '5B21B6',
}


# ── Helpers de estilo ───────────────────────────────────────────
def make_fill(hex_color: str) -> PatternFill:
    return PatternFill('solid', fgColor=hex_color.lstrip('#'))

def make_font(bold=False, color='1E293B', size=10, italic=False) -> Font:
    return Font(name='Arial', bold=bold, color=color.lstrip('#'), size=size, italic=italic)

def make_border(color='CBD5E1') -> Border:
    s = Side(style='thin', color=color)
    return Border(left=s, right=s, top=s, bottom=s)

def make_border_bottom(color='CBD5E1') -> Border:
    return Border(bottom=Side(style='thin', color=color))

def make_align(h='left', v='center', wrap=False) -> Alignment:
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)

def set_widths(ws, widths: dict):
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

def set_row_heights(ws, heights: dict):
    for row, h in heights.items():
        ws.row_dimensions[row].height = h


# ── Blocos compostos ────────────────────────────────────────────
def write_header(ws, row: int, col_end: str, text: str,
                 bg: str, fg: str, size=13, height=30):
    """Escreve um cabeçalho mesclado de B{row} até col_end{row}."""
    ws.merge_cells(f'B{row}:{col_end}{row}')
    c = ws[f'B{row}']
    c.value = text
    c.font = make_font(True, fg, size)
    c.fill = make_fill(bg)
    c.alignment = make_align('center')
    ws.row_dimensions[row].height = height


def write_col_headers(ws, row: int, cols: list,
                      bg='334155', fg='FFFFFF', start_col=2, height=18):
    """Escreve cabeçalhos de colunas a partir de start_col."""
    for ci, label in enumerate(cols, start=start_col):
        col = get_column_letter(ci)
        cell = ws[f'{col}{row}']
        cell.value = label
        cell.font = make_font(True, fg, 9)
        cell.fill = make_fill(bg)
        cell.alignment = make_align('center')
        cell.border = make_border()
    ws.row_dimensions[row].height = height


def write_data_row(ws, row: int, values: list,
                   bg='FFFFFF', start_col=2,
                   bold_first=False, center_cols=None, height=15):
    """
    Escreve uma linha de dados.
    center_cols: índices (base 0) das colunas a centralizar.
    """
    center_cols = center_cols or []
    for ci, v in enumerate(values, start=start_col):
        col = get_column_letter(ci)
        cell = ws[f'{col}{row}']
        cell.value = v
        cell.font = make_font(bold=(ci == start_col and bold_first), size=9)
        cell.fill = make_fill(bg)
        cell.border = make_border()
        idx = ci - start_col
        cell.alignment = make_align('center' if idx in center_cols else 'left')
    ws.row_dimensions[row].height = height


def write_total_row(ws, row: int, values: list,
                    bg='0A192F', fg='FFFFFF', start_col=2, height=18):
    """Escreve uma linha de total com fundo escuro."""
    for ci, v in enumerate(values, start=start_col):
        col = get_column_letter(ci)
        cell = ws[f'{col}{row}']
        cell.value = v
        cell.font = make_font(True, fg, 9)
        cell.fill = make_fill(bg)
        cell.border = make_border()
        cell.alignment = make_align('center' if ci > start_col else 'left')
    ws.row_dimensions[row].height = height


def write_section_header(ws, row: int, col_end: str, text: str,
                          bg: str, fg: str, height=20):
    """Escreve um cabeçalho de seção dentro de uma aba."""
    ws.merge_cells(f'B{row}:{col_end}{row}')
    c = ws[f'B{row}']
    c.value = text
    c.font = make_font(True, fg, 10)
    c.fill = make_fill(bg)
    c.alignment = make_align('center')
    ws.row_dimensions[row].height = height


# ── Criação de workbook padrão ──────────────────────────────────
def create_workbook() -> Workbook:
    wb = Workbook()
    # Remove a aba padrão vazia (será recriada com título adequado)
    return wb


def finalize_workbook(wb: Workbook) -> io.BytesIO:
    """Salva o workbook em memória e retorna BytesIO."""
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ── Gerador de resumo de vagas ──────────────────────────────────
def gerar_excel_vagas(vagas_municipais: dict, vagas_estaduais: dict,
                      escola_origem: str) -> io.BytesIO:
    """
    Gera um Excel com o resumo completo de vagas disponíveis
    (municipais + estaduais) por série e turno.
    """
    from datetime import datetime
    now = datetime.now().strftime('%d/%m/%Y %H:%M')

    wb = create_workbook()
    ws = wb.active
    ws.title = 'Vagas Disponíveis'
    ws.sheet_view.showGridLines = False

    set_widths(ws, {'A': 3, 'B': 38, 'C': 16, 'D': 10,
                    'E': 12, 'F': 12, 'G': 12, 'H': 3})

    write_header(ws, 2, 'G', 'VAGAS DISPONÍVEIS POR ESCOLA E SÉRIE',
                 COLORS['primary'], COLORS['white'], 13, 30)
    write_header(ws, 3, 'G', f'{escola_origem}  |  Gerado em {now}',
                 COLORS['primary2'], COLORS['white'], 9, 16)
    ws.row_dimensions[4].height = 8

    row = 5

    # ── Municipais ──
    write_section_header(ws, row, 'G', '🏫 ESCOLAS MUNICIPAIS',
                         COLORS['primary'], COLORS['white'])
    row += 1
    write_col_headers(ws, row, ['Escola', 'Série', 'Turno',
                                 'Existentes', 'Ocupadas', 'Disponíveis'])
    row += 1

    for escola, series in sorted(vagas_municipais.items()):
        first = True
        for serie, turmas in series.items():
            by_turno = {}
            for t in turmas:
                tr = t['turno']
                by_turno.setdefault(tr, {'exist': 0, 'ocup': 0, 'disp': 0})
                by_turno[tr]['exist'] += t['vagas_existentes']
                by_turno[tr]['ocup']  += t['vagas_ocupadas']
                by_turno[tr]['disp']  += t['vagas_disponiveis']

            for turno, v in sorted(by_turno.items()):
                bg = COLORS['green_bg'] if v['disp'] > 0 else COLORS['gray1']
                vals = [escola if first else '', serie, turno,
                        v['exist'], v['ocup'], v['disp']]
                write_data_row(ws, row, vals, bg=bg,
                               bold_first=first, center_cols=[2, 3, 4, 5])
                # Coluna de disponíveis com cor especial
                cell_disp = ws[f'G{row}']
                cell_disp.font = make_font(True,
                    COLORS['green_fg'] if v['disp'] > 0 else COLORS['red_fg'], 9)
                row += 1
                first = False

    # Total municipais
    total_mun = sum(
        t['vagas_disponiveis']
        for series in vagas_municipais.values()
        for turmas in series.values()
        for t in turmas
    )
    write_total_row(ws, row, ['TOTAL MUNICIPAL', '', '', '', '', total_mun])
    row += 2

    # ── Estaduais ──
    write_section_header(ws, row, 'G', '🏛️ ESCOLAS ESTADUAIS (inseridas manualmente)',
                         '5B21B6', COLORS['white'])
    row += 1
    write_col_headers(ws, row, ['Escola', 'Série', 'Turno', '—', '—', 'Disponíveis'],
                      bg='5B21B6')
    row += 1

    total_est = 0
    for escola, series in sorted(vagas_estaduais.items()):
        first = True
        for serie, turnos in series.items():
            for turno, vagas in sorted(turnos.items()):
                bg = COLORS['green_bg'] if vagas > 0 else COLORS['gray1']
                vals = [escola if first else '', serie, turno, '—', '—', vagas]
                write_data_row(ws, row, vals, bg=bg,
                               bold_first=first, center_cols=[2, 3, 4, 5])
                cell_disp = ws[f'G{row}']
                cell_disp.font = make_font(True,
                    COLORS['green_fg'] if vagas > 0 else COLORS['red_fg'], 9)
                total_est += vagas
                row += 1
                first = False

    if total_est > 0:
        write_total_row(ws, row, ['TOTAL ESTADUAL', '', '', '', '', total_est],
                        bg='5B21B6')
        row += 1

    write_total_row(ws, row, ['TOTAL GERAL', '', '', '', '', total_mun + total_est])

    return finalize_workbook(wb)
