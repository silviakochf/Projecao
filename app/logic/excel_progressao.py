"""
Gerador do Excel de progressão de alunos.
"""
import io
from datetime import datetime
from app.services.excel_service import (make_fill, make_font, make_border,
    make_align, set_widths, write_header, write_col_headers,
    write_data_row, write_total_row, write_section_header, COLORS)
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Cores
PRIMARY  = "0A192F"
WHITE    = "FFFFFF"
HDR_GRAY = "334155"
HDR_SEC  = "172A45"
GREEN_BG = "D1FAE5"; GREEN_FG = "065F46"
RED_BG   = "FEE2E2"; RED_FG   = "991B1B"
YELLOW_BG= "FEF9C3"; YELLOW_FG= "854D0E"
BLUE_BG  = "DBEAFE"; BLUE_FG  = "1E40AF"
GRAY1    = "F8FAFC"

def _fill(h): return PatternFill("solid", fgColor=h)
def _font(bold=False, color="1E293B", size=10, italic=False):
    return Font(name="Arial", bold=bold, color=color, size=size, italic=italic)
def _border():
    s = Side(style="thin", color="CBD5E1")
    return Border(left=s, right=s, top=s, bottom=s)
def _align(h="left", v="center", wrap=False):
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)
def _set_widths(ws, widths):
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
def _header(ws, row, col_end, text, bg, fg, size=12, h=28):
    ws.merge_cells(f"B{row}:{col_end}{row}")
    c = ws[f"B{row}"]
    c.value = text; c.font = _font(True, fg, size)
    c.fill = _fill(bg); c.alignment = _align("center")
    ws.row_dimensions[row].height = h
def _col_headers(ws, row, cols, bg=HDR_GRAY, fg=WHITE, h=16):
    for ci, label in enumerate(cols, start=2):
        c = ws[f"{get_column_letter(ci)}{row}"]
        c.value = label; c.font = _font(True, fg, 9)
        c.fill = _fill(bg); c.alignment = _align("center"); c.border = _border()
    ws.row_dimensions[row].height = h


def gerar_excel_progressao(escola_origem: str, bairro: str,
                            turmas_progressao: list,
                            vagas_municipais_raw: dict,
                            vagas_estaduais: dict) -> io.BytesIO:
    """
    turmas_progressao: resultado de processar_turmas_para_progressao()
    """
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    wb = Workbook()

    # ═══════════════════════════════════════
    # ABA 1 — SUGESTÕES DE PROGRESSÃO
    # ═══════════════════════════════════════
    ws = wb.active
    ws.title = "Progressão"
    ws.sheet_view.showGridLines = False
    _set_widths(ws, {"A":3,"B":6,"C":22,"D":12,"E":12,"F":10,
                     "G":30,"H":12,"I":12,"J":8,"K":3})

    _header(ws, 2, "J", f"PROGRESSÃO DE ALUNOS — {escola_origem.upper()}", PRIMARY, WHITE, 13, 30)
    _header(ws, 3, "J", f"Bairro: {bairro}  |  Gerado em {now}", HDR_SEC, WHITE, 9, 16)
    ws.row_dimensions[4].height = 8

    _col_headers(ws, 5, ["#","Turma","Série Atual","Série Destino","Turno",
                          "Escola Sugerida","Tipo","Bairro Destino","Vagas Disp.","Mesmo Bairro"])
    ws.freeze_panes = "B6"

    for ri, t in enumerate(turmas_progressao):
        row = ri + 6
        sug = t.get('escola_sugerida')
        mesmo_bairro = sug.get('mesmo_bairro', False) if sug else False
        bg = GREEN_BG if mesmo_bairro else YELLOW_BG

        vals = [
            ri + 1,
            t['turma'],
            t['serie_atual'],
            t['serie_destino'],
            t['turno'],
            sug['escola'] if sug else '⚠️ SEM VAGA',
            sug['tipo'] if sug else '—',
            sug['bairro'] if sug else '—',
            sug['vagas_disponiveis'] if sug else 0,
            '✅ Sim' if mesmo_bairro else '🔄 Próximo'
        ]

        for ci, v in enumerate(vals, start=2):
            cell = ws[f"{get_column_letter(ci)}{row}"]
            cell.value = v; cell.border = _border()
            cell.font = _font(size=9, bold=(ci==7 and not sug))
            cell.fill = _fill(bg if sug else RED_BG)
            cell.alignment = _align("center" if ci != 7 else "left")
        ws.row_dimensions[row].height = 16

    # ═══════════════════════════════════════
    # ABA 2 — LISTA DE ALUNOS POR TURMA
    # ═══════════════════════════════════════
    wa = wb.create_sheet("Alunos por Turma")
    wa.sheet_view.showGridLines = False
    _set_widths(wa, {"A":3,"B":8,"C":36,"D":8,"E":12,"F":22,"G":14,"H":14,"I":3})

    _header(wa, 2, "H", "ALUNOS PARA PROGRESSÃO", PRIMARY, WHITE, 13, 30)
    _header(wa, 3, "H", f"{escola_origem}  |  {now}", HDR_SEC, WHITE, 9, 16)
    wa.row_dimensions[4].height = 8

    row = 5
    for t in turmas_progressao:
        sug = t.get('escola_sugerida')

        # Cabeçalho da turma
        wa.merge_cells(f"B{row}:H{row}")
        c = wa[f"B{row}"]
        escola_dest = sug['escola'] if sug else 'SEM VAGA DISPONÍVEL'
        c.value = f"📋 {t['turma']} | {t['serie_atual']} → {t['serie_destino']} | {t['turno']} | {t['total_alunos']} alunos → {escola_dest}"
        c.font = _font(True, WHITE if sug else RED_FG, 9)
        c.fill = _fill(HDR_GRAY if sug else RED_BG)
        c.alignment = _align("left")
        wa.row_dimensions[row].height = 18
        row += 1

        # Cabeçalho colunas
        _col_headers(wa, row, ["#","Nome","Sexo","Nascimento","Escola Destino","Série Destino","Turno"])
        row += 1

        # Alunos
        for ai, aluno in enumerate(t.get('alunos', [])):
            bg = GRAY1 if ai % 2 == 0 else WHITE
            for ci, v in enumerate([ai+1, aluno['nome'], aluno['sexo'],
                                      aluno['nascimento'], escola_dest,
                                      t['serie_destino'], t['turno']], start=2):
                cell = wa[f"{get_column_letter(ci)}{row}"]
                cell.value = v; cell.border = _border()
                cell.font = _font(size=9)
                cell.fill = _fill(bg)
                cell.alignment = _align("center" if ci != 3 else "left")
            wa.row_dimensions[row].height = 15
            row += 1
        row += 1  # Espaço entre turmas

    # ═══════════════════════════════════════
    # ABA 3 — VAGAS DISPONÍVEIS
    # ═══════════════════════════════════════
    wv = wb.create_sheet("Vagas Disponíveis")
    wv.sheet_view.showGridLines = False
    _set_widths(wv, {"A":3,"B":36,"C":18,"D":10,"E":10,"F":10,"G":10,"H":3})

    _header(wv, 2, "G", "VAGAS DISPONÍVEIS POR ESCOLA E SÉRIE", PRIMARY, WHITE, 13, 30)
    _header(wv, 3, "G", f"Municipal e Estadual  |  {now}", HDR_SEC, WHITE, 9, 16)
    wv.row_dimensions[4].height = 8

    row = 5

    # Municipais
    wv.merge_cells(f"B{row}:G{row}")
    wv[f"B{row}"].value = "🏫 ESCOLAS MUNICIPAIS"
    wv[f"B{row}"].font = _font(True, WHITE, 10)
    wv[f"B{row}"].fill = _fill(PRIMARY)
    wv[f"B{row}"].alignment = _align("center")
    wv.row_dimensions[row].height = 18
    row += 1

    _col_headers(wv, row, ["Escola","Série","Turno","Existentes","Ocupadas","Disponíveis"])
    row += 1

    for escola, series in sorted(vagas_municipais_raw.items()):
        first = True
        for serie, turmas in series.items():
            by_turno = {}
            for t in turmas:
                tr = t['turno']
                by_turno.setdefault(tr, {'exist':0,'ocup':0,'disp':0})
                by_turno[tr]['exist'] += t['vagas_existentes']
                by_turno[tr]['ocup']  += t['vagas_ocupadas']
                by_turno[tr]['disp']  += t['vagas_disponiveis']

            for turno, v in by_turno.items():
                bg = GREEN_BG if v['disp'] > 0 else RED_BG
                vals = [escola if first else '', serie, turno,
                        v['exist'], v['ocup'], v['disp']]
                for ci, val in enumerate(vals, start=2):
                    cell = wv[f"{get_column_letter(ci)}{row}"]
                    cell.value = val; cell.border = _border()
                    cell.font = _font(size=9, bold=(ci==2 and first))
                    cell.fill = _fill(bg if ci >= 6 else GRAY1)
                    cell.alignment = _align("center" if ci > 2 else "left")
                wv.row_dimensions[row].height = 15
                row += 1
                first = False

    # Estaduais
    row += 1
    wv.merge_cells(f"B{row}:G{row}")
    wv[f"B{row}"].value = "🏛️ ESCOLAS ESTADUAIS (inseridas manualmente)"
    wv[f"B{row}"].font = _font(True, WHITE, 10)
    wv[f"B{row}"].fill = _fill("5B21B6")
    wv[f"B{row}"].alignment = _align("center")
    wv.row_dimensions[row].height = 18
    row += 1

    _col_headers(wv, row, ["Escola","Série","Turno","—","—","Disponíveis"], bg="5B21B6")
    row += 1

    for escola, series in sorted(vagas_estaduais.items()):
        first = True
        for serie, turnos in series.items():
            for turno, vagas in turnos.items():
                bg = GREEN_BG if vagas > 0 else RED_BG
                vals = [escola if first else '', serie, turno, '—', '—', vagas]
                for ci, val in enumerate(vals, start=2):
                    cell = wv[f"{get_column_letter(ci)}{row}"]
                    cell.value = val; cell.border = _border()
                    cell.font = _font(size=9, bold=(ci==2 and first))
                    cell.fill = _fill(bg if ci == 7 else GRAY1)
                    cell.alignment = _align("center" if ci > 2 else "left")
                wv.row_dimensions[row].height = 15
                row += 1
                first = False

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
