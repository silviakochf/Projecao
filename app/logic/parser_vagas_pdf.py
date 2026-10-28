"""
Parser do PDF "Lista de Vagas por Série e Turma" (EducarWEB).

- Lê o PDF com pypdf (Python puro, funciona no Windows).
- O nome da escola é a linha logo após data/hora do cabeçalho de cada página
  (formatos: "(01) NOME", "(C10) NOME", "(P9) NOME" ou só "NOME").
- Cada turma é lida em uma linha; confere ocupadas + disponíveis = existentes.
"""
import io
import re

HEADER_TITLE = 'Lista de Vagas por Série e Turma'
DATETIME_RE  = re.compile(r'^\d{2}/\d{2}/\d{4}\s*-\s*\d{2}:\d{2}:\d{2}$')

TURMA_RE = re.compile(
    r'(?:^|\s)'
    r'(?P<turma>(?:\d+\s*[ºo°]\s*ANO(?:\s*-\s*\d+)?|GT\s*\d+(?:\s*[A-Z])?))'
    r'\s+(?P<exist>\d+)\s+'
    r'(?P<turno>MANHÃ|MANHA|TARDE|INTEGRAL|NOITE|MATUTINO|VESPERTINO)\b'
    r'(?P<resto>.*)$',
    re.IGNORECASE
)
TURNOS = {'MANHA': 'MANHÃ', 'MATUTINO': 'MANHÃ', 'VESPERTINO': 'TARDE'}


def limpar_nome_escola(raw: str) -> str:
    nome = re.sub(r'^\([A-Za-z]*\d+\)\s*', '', raw.strip())   # (01) (C10) (P9)
    nome = re.sub(r'\s+', ' ', nome)
    # remove sufixos: "- INATIVO", "- AREA/AREA/AREA", "- FUND", "- INF"
    nome = re.sub(r'\s+-\s+(?:INATIVO\b.*|[^-]*/[^-]*(?:\s+-\s+.*)?|FUND|INF)$',
                  '', nome, flags=re.IGNORECASE).strip()
    nome = re.sub(r'\s+-\s+(FUND|INF|INATIVO)\b.*$', '', nome, flags=re.IGNORECASE).strip()
    return nome


def normalizar_serie(texto: str) -> str:
    t = texto.upper().replace('°', 'º').strip()
    m = re.match(r'^GT\s*(\d+)', t)
    if m:
        return f'GT {int(m.group(1))}'
    m = re.match(r'^(\d+)\s*[ºO]?\s*ANO', t)
    if m:
        return f'{int(m.group(1))}º ANO'
    return t


def _inteiros(texto: str) -> list:
    """Inteiros isolados (ignora decimais como 48.00)."""
    return [int(x) for x in re.findall(r'(?<![\d.])\d+(?![\d.])', texto)]


def _linhas_do_pdf(src):
    from pypdf import PdfReader
    if isinstance(src, (bytes, bytearray)):
        src = io.BytesIO(src)
    reader = PdfReader(src)
    for pagina in reader.pages:
        yield [l.strip() for l in (pagina.extract_text() or '').split('\n') if l.strip()]


def parse_vagas_pdf(src, report: dict = None) -> dict:
    """
    src: caminho do arquivo, bytes ou file-like.
    Retorna {escola: {serie: [ {turma, turno, vagas_existentes,
                                vagas_ocupadas, vagas_disponiveis} ]}}
    report (opcional): dict preenchido com 'nao_lidas' e 'divergentes'.
    """
    if report is None:
        report = {}
    report['nao_lidas'] = []
    report['divergentes'] = []
    report['inativas'] = set()
    dados = {}

    for linhas in _linhas_do_pdf(src):
        escola = None
        for i, l in enumerate(linhas):
            if DATETIME_RE.match(l) and i + 1 < len(linhas):
                escola = limpar_nome_escola(linhas[i + 1])
                if re.search(r'\bINATIV[OA]\b', linhas[i + 1], re.IGNORECASE):
                    report['inativas'].add(escola)
                break
        if not escola:
            continue
        dados.setdefault(escola, {})

        i = 0
        while i < len(linhas):
            l = linhas[i]
            i += 1
            m = TURMA_RE.search(l)
            if not m:
                if re.search(r'(\d\s*[ºo°]\s*ANO\s*-\s*\d|GT\s*\d\s*[A-Z]?\s+\d+\s+\w+)', l, re.I) \
                        and not l.upper().startswith('ANO/SÉRIE'):
                    report['nao_lidas'].append(f'{escola}: {l[:90]}')
                continue

            inteiros = _inteiros(m.group('resto'))
            # algumas turmas quebram em 2 linhas ("... SALA 11 -" / "TÉRREO 48.00 30 0 0 2")
            if len(inteiros) < 4 and i < len(linhas) and not TURMA_RE.search(linhas[i]):
                l = l + ' ' + linhas[i]
                i += 1
                m = TURMA_RE.search(l)
                inteiros = _inteiros(m.group('resto'))
            if len(inteiros) < 4:
                report['nao_lidas'].append(f'{escola}: {l[:90]}')
                continue

            ocup, disp, exced, esp = inteiros[-4:]
            exist = int(m.group('exist'))
            if ocup - exced + disp != exist:
                report['divergentes'].append(f'{escola}: {l[:90]}')

            serie = normalizar_serie(m.group('turma'))
            turno = m.group('turno').upper()
            turno = TURNOS.get(turno, turno)
            dados[escola].setdefault(serie, []).append({
                'turma': re.sub(r'\s+', ' ', m.group('turma').upper().replace('°', 'º')).strip(),
                'turno': turno,
                'vagas_existentes':  exist,
                'vagas_ocupadas':    ocup,
                'vagas_disponiveis': disp,
            })

    # remove escolas sem nenhuma turma lida
    return {e: s for e, s in dados.items() if s}


def get_resumo_vagas(dados: dict) -> list:
    """Lista [{escola, serie, turno, existentes, ocupadas, disponiveis}]."""
    linhas = []
    for escola, series in dados.items():
        for serie, turmas in series.items():
            por_turno = {}
            for t in turmas:
                a = por_turno.setdefault(t['turno'], {'e': 0, 'o': 0, 'd': 0})
                a['e'] += t['vagas_existentes']
                a['o'] += t['vagas_ocupadas']
                a['d'] += t['vagas_disponiveis']
            for turno, a in por_turno.items():
                linhas.append({'escola': escola, 'serie': serie, 'turno': turno,
                               'vagas_existentes': a['e'], 'vagas_ocupadas': a['o'],
                               'vagas_disponiveis': a['d']})
    return linhas
