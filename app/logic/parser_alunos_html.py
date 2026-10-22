"""Parser HTML alunos EducarWEB."""
import re
from lxml import html as lhtml

def parse_alunos_html(html_content):
    tree = lhtml.fromstring(html_content)
    spans = [s.text_content().replace("\xa0"," ").strip()
             for s in tree.xpath("//span") if s.text_content().strip()]
    result = {}
    turma_atual = ""
    i = 0
    while i < len(spans):
        t = spans[i]
        if t.startswith("Turma:"):
            m = re.match(r"Turma:\s*(.+?)\s*\((.+?)\)", t)
            if m:
                turma_atual = m.group(1).strip()
            i += 1; continue
        if re.match(r"^\d{5,7}$", t):
            try:
                codigo=t; nome=spans[i+1]; sexo=spans[i+2]; nasc=spans[i+3]
                unidade=spans[i+4]; serie=spans[i+5]; turno=spans[i+6]; sit=spans[i+7]
                if sit in ("ATIVO","MATRICULADO"):
                    escola = unidade.split("-")[0].strip()
                    serie  = re.sub(r"[oO°](?=\s)","º",serie.strip())
                    turno  = turno.upper()
                    # Usa série como nome da turma se turma_atual estiver vazio
                    turma_nome = turma_atual if turma_atual else serie
                    result.setdefault(escola,{}).setdefault(serie,{}).setdefault(turno,[]).append(
                        {"codigo":codigo,"nome":nome,"sexo":sexo,"nascimento":nasc,
                         "turma":turma_nome,"situacao":sit})
                i += 8; continue
            except IndexError:
                pass
        i += 1
    return result

def get_turmas_para_progressao(data, series_progressao):
    turmas = []
    for escola, series in data.items():
        for serie, turnos in series.items():
            serie_norm = serie.upper()
            if not any(p.upper() in serie_norm or serie_norm in p.upper() for p in series_progressao):
                continue
            for turno, alunos in turnos.items():
                por_turma = {}
                for a in alunos:
                    por_turma.setdefault(a.get("turma", serie), []).append(a)
                for turma_nome, lista in por_turma.items():
                    turmas.append({"escola":escola,"serie":serie,"turma":turma_nome,
                                   "turno":turno,"alunos":lista,"total":len(lista)})
    return turmas
