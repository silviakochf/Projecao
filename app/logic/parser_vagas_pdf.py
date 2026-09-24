"""
Parser do PDF de vagas por série e turma (EducarWEB).
"""
import re
import subprocess


def parse_vagas_pdf(pdf_path: str) -> dict:
  
    result = subprocess.run(['pdftotext', pdf_path, '-'], capture_output=True, text=True)
    lines = [l.strip() for l in result.stdout.split('\n')]

    def is_turma(s):
        return bool(re.match(
            r'^(\d+[ºo°]\s*ANO\s*[-\s]\s*\d+|GT\s*\d+\s*[A-Z]?)$', s, re.IGNORECASE
        ))

    def is_turno(s):
        return s.upper() in ('MANHÃ', 'TARDE', 'INTEGRAL', 'NOITE', 'MANHA')

    schools_data = {}
    current_school = None
    current_serie = None

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line:
            i += 1
            continue

        # Escola: (01) NOME...
        m = re.match(r'^\((\d+)\)\s*(.+)', line)
        if m:
            name = m.group(2).strip()
            name = re.sub(r'\s*-\s*(INATIVO|FUND|INF)\s*.*$', '', name, flags=re.IGNORECASE).strip()
            current_school = name
            if current_school not in schools_data:
                schools_data[current_school] = {}
            i += 1
            continue

        # Série: ANO/SÉRIE: 6º ANO
        m = re.match(r'^ANO/SÉRIE:\s*(.+)', line)
        if m:
            current_serie = m.group(1).strip()
            if current_school:
                schools_data[current_school].setdefault(current_serie, [])
            i += 1
            continue

        # Turma: "6º ANO 1" ou "GT 5 A"
        if is_turma(line) and current_school and current_serie:
            turma_nome = line
            vals = []
            j = i + 1
            while j < len(lines) and len(vals) < 7:
                if lines[j]:
                    vals.append(lines[j])
                j += 1

            try:
                vagas_exist  = int(vals[0]) if len(vals) > 0 and vals[0].isdigit() else 0
                turno        = vals[1].upper() if len(vals) > 1 else ''
                sala         = vals[2] if len(vals) > 2 else ''
                area         = vals[3] if len(vals) > 3 else ''
                ocupadas     = int(vals[4]) if len(vals) > 4 and vals[4].isdigit() else 0
                disponiveis  = int(vals[5]) if len(vals) > 5 and vals[5].isdigit() else 0
            except Exception:
                vagas_exist = 0; turno = ''; sala = ''; ocupadas = 0; disponiveis = 0

            if is_turno(turno):
                schools_data[current_school][current_serie].append({
                    'turma': turma_nome,
                    'turno': turno,
                    'sala': sala,
                    'vagas_existentes': vagas_exist,
                    'vagas_ocupadas': ocupadas,
                    'vagas_disponiveis': disponiveis
                })
            i = j
            continue

        i += 1

    return schools_data


def vagas_para_dict_serie_turno(schools_data: dict) -> dict:
    """
    Converte para: {escola: {serie: {turno: total_vagas_disponiveis}}}
    """
    resultado = {}
    for escola, series in schools_data.items():
        resultado[escola] = {}
        for serie, turmas in series.items():
            resultado[escola][serie] = {}
            for t in turmas:
                turno = t['turno']
                resultado[escola][serie][turno] = \
                    resultado[escola][serie].get(turno, 0) + t['vagas_disponiveis']
    return resultado


def get_resumo_vagas(schools_data: dict) -> list:
    """
    Retorna lista resumida: [{escola, serie, turno, vagas_exist, vagas_ocup, vagas_disp}]
    """
    rows = []
    for escola, series in schools_data.items():
        for serie, turmas in series.items():
            by_turno = {}
            for t in turmas:
                turno = t['turno']
                if turno not in by_turno:
                    by_turno[turno] = {'exist': 0, 'ocup': 0, 'disp': 0}
                by_turno[turno]['exist'] += t['vagas_existentes']
                by_turno[turno]['ocup']  += t['vagas_ocupadas']
                by_turno[turno]['disp']  += t['vagas_disponiveis']

            for turno, v in by_turno.items():
                rows.append({
                    'escola': escola,
                    'serie': serie,
                    'turno': turno,
                    'vagas_existentes': v['exist'],
                    'vagas_ocupadas': v['ocup'],
                    'vagas_disponiveis': v['disp']
                })
    return rows