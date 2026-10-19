"""
Parser do PDF de vagas EducarWEB.
Usa pypdf (Python puro) — funciona no Windows sem instalar pdftotext.
"""
import re


def parse_vagas_pdf(pdf_path: str) -> dict:
    """
    Retorna: {escola: {serie: [{turma, turno, sala, vagas_existentes,
                                vagas_ocupadas, vagas_disponiveis}]}}
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError(
            "Instale o pypdf: pip install pypdf\n"
            "Ou: pip install pypdf2"
        )

    # Extrai texto de todas as páginas
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text += t + "\n"

    lines = [l.strip() for l in text.split('\n') if l.strip()]

    # Padrão de turma inline: "6º ANO 1 33 MANHÃ SALA 08 45.30 33 0 0 2"
    TURMA_RE = re.compile(
        r'^((?:\d+[ºo°]\s*ANO|GT\s*\d+)\s*[-\s]?\s*\d*\w*)\s+'  # nome turma
        r'(\d+)\s+'                                                 # vagas exist
        r'(MANHÃ|TARDE|INTEGRAL|NOITE|MANHA)\s+'                   # turno
        r'(SALA\s+\S+)\s+'                                         # sala
        r'[\d.]+\s+'                                               # área
        r'(\d+)\s+'                                                # ocupadas
        r'(\d+)\s+',                                               # disponíveis
        re.IGNORECASE
    )

    schools_data = {}
    current_school = None
    current_serie  = None

    for line in lines:
        # Escola: (01) NOME...
        m = re.match(r'^\((\d+)\)\s*(.+)', line)
        if m:
            name = m.group(2).strip()
            name = re.sub(
                r'\s*-\s*(INATIVO|FUND|INF)\s*.*$', '',
                name, flags=re.IGNORECASE
            ).strip()
            current_school = name
            schools_data.setdefault(current_school, {})
            continue

        # Série: ANO/SÉRIE: 6º ANO
        m = re.match(r'^ANO/SÉRIE:\s*(.+)', line)
        if m:
            current_serie = m.group(1).strip()
            if current_school:
                schools_data[current_school].setdefault(current_serie, [])
            continue

        # Turma numa linha só (formato pypdf)
        if current_school and current_serie:
            m = TURMA_RE.match(line)
            if m:
                turma_nome  = m.group(1).strip()
                vagas_exist = int(m.group(2))
                turno       = m.group(3).upper().replace('MANHA', 'MANHÃ')
                sala        = m.group(4)
                ocupadas    = int(m.group(5))
                disponiveis = int(m.group(6))

                schools_data[current_school][current_serie].append({
                    'turma':             turma_nome,
                    'turno':             turno,
                    'sala':              sala,
                    'vagas_existentes':  vagas_exist,
                    'vagas_ocupadas':    ocupadas,
                    'vagas_disponiveis': disponiveis,
                })

    return schools_data


def get_resumo_vagas(schools_data: dict) -> list:
    """
    Retorna lista [{escola, serie, turno, vagas_existentes,
                    vagas_ocupadas, vagas_disponiveis}]
    """
    rows = []
    for escola, series in schools_data.items():
        for serie, turmas in series.items():
            by_turno = {}
            for t in turmas:
                tr = t['turno']
                by_turno.setdefault(tr, {'exist': 0, 'ocup': 0, 'disp': 0})
                by_turno[tr]['exist'] += t['vagas_existentes']
                by_turno[tr]['ocup']  += t['vagas_ocupadas']
                by_turno[tr]['disp']  += t['vagas_disponiveis']
            for turno, v in by_turno.items():
                rows.append({
                    'escola':            escola,
                    'serie':             serie,
                    'turno':             turno,
                    'vagas_existentes':  v['exist'],
                    'vagas_ocupadas':    v['ocup'],
                    'vagas_disponiveis': v['disp'],
                })
    return rows
