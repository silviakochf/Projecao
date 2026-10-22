"""Parser PDF de vagas EducarWEB — usa pypdf (funciona no Windows)."""
import re

def parse_vagas_pdf(pdf_path: str) -> dict:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError("Instale: pip install pypdf")

    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        t = page.extract_text()
        if t: text += t + "\n"

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    TURMA_RE = re.compile(
        r"^((?:\d+[ºo°]\s*ANO|GT\s*\d+)\s*[-\s]?\s*\d*\w*)\s+"
        r"(\d+)\s+"
        r"(MANHÃ|TARDE|INTEGRAL|NOITE|MANHA)\s+"
        r"(SALA\s+\S+)\s+"
        r"[\d.]+\s+"
        r"(\d+)\s+"
        r"(\d+)\s+",
        re.IGNORECASE
    )

    schools_data = {}
    current_school = current_serie = None

    for line in lines:
        m = re.match(r"^\((\d+)\)\s*(.+)", line)
        if m:
            name = re.sub(r"\s*-\s*(INATIVO|FUND|INF)\s*.*$", "",
                          m.group(2).strip(), flags=re.IGNORECASE).strip()
            current_school = name
            schools_data.setdefault(current_school, {})
            continue

        m = re.match(r"^ANO/SÉRIE:\s*(.+)", line)
        if m:
            current_serie = m.group(1).strip()
            if current_school:
                schools_data[current_school].setdefault(current_serie, [])
            continue

        if current_school and current_serie:
            m = TURMA_RE.match(line)
            if m:
                turno = m.group(3).upper().replace("MANHA", "MANHÃ")
                schools_data[current_school][current_serie].append({
                    "turma": m.group(1).strip(),
                    "turno": turno,
                    "sala":  m.group(4),
                    "vagas_existentes":  int(m.group(2)),
                    "vagas_ocupadas":    int(m.group(5)),
                    "vagas_disponiveis": int(m.group(6)),
                })

    return schools_data

def get_resumo_vagas(schools_data: dict) -> list:
    rows = []
    for escola, series in schools_data.items():
        for serie, turmas in series.items():
            by_turno = {}
            for t in turmas:
                tr = t["turno"]
                by_turno.setdefault(tr, {"exist":0,"ocup":0,"disp":0})
                by_turno[tr]["exist"] += t["vagas_existentes"]
                by_turno[tr]["ocup"]  += t["vagas_ocupadas"]
                by_turno[tr]["disp"]  += t["vagas_disponiveis"]
            for turno, v in by_turno.items():
                rows.append({"escola":escola,"serie":serie,"turno":turno,
                             "vagas_existentes":v["exist"],
                             "vagas_ocupadas":v["ocup"],
                             "vagas_disponiveis":v["disp"]})
    return rows
