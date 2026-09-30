"""
Gerador de cartas de encaminhamento para cada escola destino.
"""
import io
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter


def _font(bold=False, size=11, color="000000", italic=False):
    return Font(name="Arial", bold=bold, size=size, color=color, italic=italic)

def _align(h="left", v="center", wrap=False):
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)

def _border_bottom():
    return Border(bottom=Side(style="thin", color="000000"))

def _border_all():
    s = Side(style="thin", color="000000")
    return Border(left=s, right=s, top=s, bottom=s)


def gerar_carta(escola_origem: str,
                escola_destino: str,
                serie_destino: str,
                turno: str,
                alunos: list,
                template_config: dict = None) -> io.BytesIO:
    """
    Gera uma carta de encaminhamento para UMA escola destino.
    alunos: [{nome, nascimento, sexo, turma, ...}]
    template_config: {secretaria, municipio, data, assinatura, cargo}
    """
    cfg = template_config or {}
    secretaria = cfg.get('secretaria', 'SECRETARIA MUNICIPAL DE EDUCAÇÃO')
    municipio  = cfg.get('municipio', 'PALHOÇA')
    data_str   = cfg.get('data', datetime.now().strftime('%d de %B de %Y'))
    assinatura = cfg.get('assinatura', '')
    cargo      = cfg.get('cargo', 'Secretária de Educação')

    wb = Workbook()
    ws = wb.active
    ws.title = "Carta"
    ws.sheet_view.showGridLines = False

    # Margens A4
    ws.page_setup.paperSize = 9  # A4
    ws.page_margins.left   = 0.787
    ws.page_margins.right  = 0.787
    ws.page_margins.top    = 0.984
    ws.page_margins.bottom = 0.984

    # Larguras de coluna
    ws.column_dimensions['A'].width = 2
    ws.column_dimensions['B'].width = 8
    ws.column_dimensions['C'].width = 42
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 14
    ws.column_dimensions['F'].width = 14
    ws.column_dimensions['G'].width = 2

    row = 1

    # Cabeçalho
    ws.merge_cells(f"B{row}:F{row}")
    ws[f"B{row}"].value = secretaria
    ws[f"B{row}"].font = _font(True, 13)
    ws[f"B{row}"].alignment = _align("center")
    ws.row_dimensions[row].height = 22
    row += 1

    ws.merge_cells(f"B{row}:F{row}")
    ws[f"B{row}"].value = f"MUNICÍPIO DE {municipio}"
    ws[f"B{row}"].font = _font(False, 11)
    ws[f"B{row}"].alignment = _align("center")
    ws.row_dimensions[row].height = 18
    row += 2

    # Título
    ws.merge_cells(f"B{row}:F{row}")
    ws[f"B{row}"].value = "CARTA DE ENCAMINHAMENTO"
    ws[f"B{row}"].font = _font(True, 14)
    ws[f"B{row}"].alignment = _align("center")
    ws.row_dimensions[row].height = 26
    row += 2

    # Data e destino
    ws.merge_cells(f"B{row}:F{row}")
    ws[f"B{row}"].value = f"Palhoça, {data_str}"
    ws[f"B{row}"].font = _font(False, 11)
    ws[f"B{row}"].alignment = _align("right")
    ws.row_dimensions[row].height = 18
    row += 2

    ws.merge_cells(f"B{row}:F{row}")
    ws[f"B{row}"].value = f"À Direção da {escola_destino}"
    ws[f"B{row}"].font = _font(True, 11)
    ws[f"B{row}"].alignment = _align("left")
    ws.row_dimensions[row].height = 18
    row += 2

    # Corpo da carta
    corpo = (
        f"Por meio desta, encaminhamos para matrícula nessa unidade escolar os alunos abaixo "
        f"relacionados, provenientes de {escola_origem}, para o {serie_destino} no turno {turno} "
        f"do ano letivo {datetime.now().year + 1}, conforme processo de progressão escolar."
    )
    ws.merge_cells(f"B{row}:F{row}")
    ws[f"B{row}"].value = corpo
    ws[f"B{row}"].font = _font(False, 11)
    ws[f"B{row}"].alignment = _align("left", wrap=True)
    ws.row_dimensions[row].height = 52
    row += 2

    # Tabela de alunos
    # Cabeçalho da tabela
    headers = ["#", "Nome do Aluno", "Nascimento", "Sexo", "Turma Atual"]
    widths_ci = [2, 3, 4, 5, 6]
    for ci, h in zip(widths_ci, headers):
        col = get_column_letter(ci)
        cell = ws[f"{col}{row}"]
        cell.value = h
        cell.font = _font(True, 10, "FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0A192F")
        cell.alignment = _align("center")
        cell.border = _border_all()
    ws.row_dimensions[row].height = 16
    row += 1

    # Alunos
    for ai, aluno in enumerate(alunos):
        bg = "F8FAFC" if ai % 2 == 0 else "FFFFFF"
        fill = PatternFill("solid", fgColor=bg)
        vals = [ai+1, aluno['nome'], aluno.get('nascimento',''), aluno.get('sexo',''), aluno.get('turma','')]
        for ci, v in zip(widths_ci, vals):
            col = get_column_letter(ci)
            cell = ws[f"{col}{row}"]
            cell.value = v
            cell.font = _font(False, 10)
            cell.fill = fill
            cell.alignment = _align("center" if ci != 3 else "left")
            cell.border = _border_all()
        ws.row_dimensions[row].height = 15
        row += 1

    row += 2

    # Observações
    ws.merge_cells(f"B{row}:F{row}")
    ws[f"B{row}"].value = f"Total de alunos encaminhados: {len(alunos)}"
    ws[f"B{row}"].font = _font(True, 11)
    ws[f"B{row}"].alignment = _align("left")
    ws.row_dimensions[row].height = 18
    row += 3

    # Assinatura
    ws.merge_cells(f"B{row}:F{row}")
    ws[f"B{row}"].value = "_" * 50
    ws[f"B{row}"].alignment = _align("center")
    ws.row_dimensions[row].height = 18
    row += 1

    ws.merge_cells(f"B{row}:F{row}")
    ws[f"B{row}"].value = assinatura or "_" * 40
    ws[f"B{row}"].font = _font(True, 11)
    ws[f"B{row}"].alignment = _align("center")
    ws.row_dimensions[row].height = 18
    row += 1

    ws.merge_cells(f"B{row}:F{row}")
    ws[f"B{row}"].value = cargo
    ws[f"B{row}"].font = _font(False, 11)
    ws[f"B{row}"].alignment = _align("center")
    ws.row_dimensions[row].height = 18

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def gerar_todas_cartas(turmas_progressao: list, template_config: dict,
                       escola_origem: str) -> dict:
    """
    Agrupa alunos por escola destino e gera uma carta por escola.
    Retorna: {escola_destino: BytesIO}
    """
    por_escola = {}

    for t in turmas_progressao:
        sug = t.get('escola_sugerida')
        if not sug:
            continue
        escola_dest = sug['escola']
        key = f"{escola_dest}|{t['serie_destino']}|{t['turno']}"
        if key not in por_escola:
            por_escola[key] = {
                'escola_destino': escola_dest,
                'serie_destino':  t['serie_destino'],
                'turno':          t['turno'],
                'alunos':         []
            }
        por_escola[key]['alunos'].extend(t.get('alunos', []))

    cartas = {}
    for key, data in por_escola.items():
        buf = gerar_carta(
            escola_origem=escola_origem,
            escola_destino=data['escola_destino'],
            serie_destino=data['serie_destino'],
            turno=data['turno'],
            alunos=data['alunos'],
            template_config=template_config
        )
        nome_arquivo = f"carta_{data['escola_destino'][:30].replace(' ','_')}.xlsx"
        cartas[nome_arquivo] = buf

    return cartas
