"""
Parser do HTML de estudantes matriculados (EducarWEB).
"""
import re
from lxml import html as lhtml


def parse_alunos_html(html_content: str) -> dict:
    """
    Retorna: {
      escola: {
        serie: {
          turno: [
            {codigo, nome, sexo, nascimento, turma, situacao}
          ]
        }
      }
    }
    """
    tree = lhtml.fromstring(html_content)
    spans = [s.text_content().replace('\xa0', ' ').strip()
             for s in tree.xpath('//span') if s.text_content().strip()]

    alunos_por_escola = {}
    turma_atual = ''
    escola_atual = ''
    serie_atual = ''
    turno_atual = ''

    i = 0
    while i < len(spans):
        t = spans[i]

        # Turma header: "Turma: 5º ANO - 1 (ESCOLA...)"
        if t.startswith('Turma:'):
            m = re.match(r'Turma:\s*(.+?)\s*\((.+?)\)', t)
            if m:
                turma_atual = m.group(1).strip()
                escola_raw = m.group(2).strip()
                escola_atual = escola_raw.split('-')[0].strip()
            i += 1
            continue

        # Aluno: código numérico de 6 dígitos
        if re.match(r'^\d{5,7}$', t):
            try:
                codigo    = t
                nome      = spans[i+1]
                sexo      = spans[i+2]
                nasc      = spans[i+3]
                unidade   = spans[i+4]
                serie_raw = spans[i+5]
                turno_raw = spans[i+6]
                sit       = spans[i+7]

                if sit in ('ATIVO', 'MATRICULADO'):
                    escola_nome = unidade.split('-')[0].strip()
                    serie_norm  = _normaliza_serie(serie_raw)
                    turno_norm  = turno_raw.upper()

                    alunos_por_escola \
                        .setdefault(escola_nome, {}) \
                        .setdefault(serie_norm, {}) \
                        .setdefault(turno_norm, []) \
                        .append({
                            'codigo':      codigo,
                            'nome':        nome,
                            'sexo':        sexo,
                            'nascimento':  nasc,
                            'turma':       turma_atual,
                            'situacao':    sit
                        })
                i += 8
                continue
            except IndexError:
                pass
        i += 1

    return alunos_por_escola


def _normaliza_serie(s: str) -> str:
    s = s.strip()
    s = re.sub(r'[oO°](?=\s)', 'º', s)
    return s


def get_turmas_para_progressao(alunos_por_escola: dict, series_progressao: list) -> list:
    """
    Filtra e retorna turmas que precisam de progressão.
    series_progressao: lista de séries que vão progredir (ex: ['5º ANO', 'GT 5', '8º ANO'])
    """
    turmas = []
    for escola, series in alunos_por_escola.items():
        for serie, turnos in series.items():
            serie_norm = serie.upper()
            match = any(p.upper() in serie_norm or serie_norm in p.upper()
                        for p in series_progressao)
            if not match:
                continue
            for turno, alunos in turnos.items():
                # Agrupa por turma
                por_turma = {}
                for a in alunos:
                    turma_key = a.get('turma', serie)
                    por_turma.setdefault(turma_key, []).append(a)

                for turma_nome, lista_alunos in por_turma.items():
                    turmas.append({
                        'escola':  escola,
                        'serie':   serie,
                        'turma':   turma_nome,
                        'turno':   turno,
                        'alunos':  lista_alunos,
                        'total':   len(lista_alunos)
                    })
    return turmas
