import os, json, base64, requests
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, send_file, current_app

from app.logic.parser_vagas_pdf  import parse_vagas_pdf, get_resumo_vagas
from app.logic.parser_alunos_html import parse_alunos_html, get_turmas_para_progressao
from app.logic.progressao_engine  import processar_turmas_para_progressao
from app.logic.excel_progressao   import gerar_excel_progressao
from app.logic.carta_encaminhamento import gerar_todas_cartas
from app.logic.bairros            import get_bairro_by_escola
from app.services.drive_service   import upload_to_drive

main_bp = Blueprint('main', __name__)

# ── Helpers de sessão ───────────────────────────────────────────
def _session_path(name):
    folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, name)

def _load(name):
    p = _session_path(name)
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    return {}

def _save(name, data):
    with open(_session_path(name), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── Páginas ─────────────────────────────────────────────────────
@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/progressao')
def progressao():
    return render_template('progressao.html')

@main_bp.route('/cartas')
def cartas():
    return render_template('cartas.html')

@main_bp.context_processor
def inject_now():
    return {'now': datetime.now()}

# ── API: Importar PDF de vagas ──────────────────────────────────
@main_bp.route('/api/importar_vagas_pdf', methods=['POST'])
def importar_vagas_pdf():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo'}), 400
    file = request.files['file']
    path = _session_path('vagas_upload.pdf')
    file.save(path)
    try:
        data = parse_vagas_pdf(path)
        _save('vagas_municipais.json', data)
        resumo = get_resumo_vagas(data)
        total_disp = sum(r['vagas_disponiveis'] for r in resumo)
        return jsonify({'success': True, 'escolas': len(data),
                        'total_vagas_disponiveis': total_disp,
                        'resumo': resumo})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── API: Vagas estaduais (inseridas manualmente) ────────────────
@main_bp.route('/api/salvar_vagas_estaduais', methods=['POST'])
def salvar_vagas_estaduais():
    """
    Body: {escola: {serie: {turno: vagas}}}
    """
    data = request.json or {}
    _save('vagas_estaduais.json', data)
    return jsonify({'success': True})

@main_bp.route('/api/get_vagas_estaduais', methods=['GET'])
def get_vagas_estaduais():
    return jsonify(_load('vagas_estaduais.json'))

@main_bp.route('/api/get_vagas_municipais', methods=['GET'])
def get_vagas_municipais():
    return jsonify(_load('vagas_municipais.json'))

@main_bp.route('/api/get_resumo_vagas', methods=['GET'])
def get_resumo_vagas_route():
    mun = _load('vagas_municipais.json')
    est = _load('vagas_estaduais.json')
    resumo_mun = get_resumo_vagas(mun)
    resumo_est = []
    for escola, series in est.items():
        for serie, turnos in series.items():
            for turno, vagas in turnos.items():
                resumo_est.append({'escola': escola, 'serie': serie,
                                   'turno': turno, 'vagas_disponiveis': vagas,
                                   'tipo': 'ESTADUAL'})
    for r in resumo_mun:
        r['tipo'] = 'MUNICIPAL'
    return jsonify({'municipais': resumo_mun, 'estaduais': resumo_est})

# ── API: Importar HTML de alunos ────────────────────────────────
@main_bp.route('/api/importar_alunos_html', methods=['POST'])
def importar_alunos_html():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo'}), 400
    file = request.files['file']
    content = file.read().decode('utf-8', errors='ignore')
    try:
        data = parse_alunos_html(content)
        _save('alunos.json', data)
        total = sum(
            len(alunos)
            for series in data.values()
            for turnos in series.values()
            for alunos in turnos.values()
        )
        escolas = list(data.keys())
        return jsonify({'success': True, 'escolas': escolas, 'total_alunos': total})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── API: Executar análise de progressão ─────────────────────────
@main_bp.route('/api/analisar_progressao', methods=['POST'])
def analisar_progressao():
    req = request.json or {}
    escola_origem    = req.get('escola_origem', '')
    bairro           = req.get('bairro', '') or get_bairro_by_escola(escola_origem)
    series_progressao = req.get('series_progressao', ['GT 5','5º ANO','8º ANO'])

    alunos_data    = _load('alunos.json')
    vagas_mun_raw  = _load('vagas_municipais.json')
    vagas_est      = _load('vagas_estaduais.json')

    if not alunos_data:
        return jsonify({'success': False, 'error': 'Importe o relatório de alunos primeiro'}), 400
    if not vagas_mun_raw and not vagas_est:
        return jsonify({'success': False, 'error': 'Importe as vagas antes de analisar'}), 400

    # Converte vagas municipais para {escola: {serie: {turno: vagas}}}
    vagas_mun = {}
    for escola, series in vagas_mun_raw.items():
        vagas_mun[escola] = {}
        for serie, turmas in series.items():
            vagas_mun[escola][serie] = {}
            for t in turmas:
                tr = t['turno']
                vagas_mun[escola][serie][tr] = \
                    vagas_mun[escola][serie].get(tr, 0) + t['vagas_disponiveis']

    turmas_alunos = get_turmas_para_progressao(alunos_data, series_progressao)

    if not turmas_alunos:
        return jsonify({'success': False,
                        'error': f'Nenhuma turma encontrada para progressão: {series_progressao}'}), 400

    resultado = processar_turmas_para_progressao(
        turmas_alunos, vagas_mun, vagas_est, bairro
    )
    _save('progressao_resultado.json', resultado)

    return jsonify({'success': True, 'turmas': resultado,
                    'total_turmas': len(resultado),
                    'total_alunos': sum(t['total_alunos'] for t in resultado)})

# ── API: Exportar Excel progressão ──────────────────────────────
@main_bp.route('/api/exportar_excel_progressao', methods=['POST'])
def exportar_excel_progressao():
    req = request.json or {}
    escola_origem = req.get('escola_origem', 'Escola')
    bairro        = req.get('bairro', '')
    folder_id     = req.get('folder_id',
                             current_app.config['DRIVE_FOLDER_PROGRESSAO'])

    resultado    = _load('progressao_resultado.json')
    vagas_mun    = _load('vagas_municipais.json')
    vagas_est    = _load('vagas_estaduais.json')

    if not resultado:
        return jsonify({'success': False, 'error': 'Execute a análise primeiro'}), 400

    buf = gerar_excel_progressao(escola_origem, bairro, resultado, vagas_mun, vagas_est)
    date_str = datetime.now().strftime('%d-%m-%Y')
    filename = f"progressao_{escola_origem[:20]}_{date_str}.xlsx".replace(' ','_')

    result = upload_to_drive(buf.getvalue(), filename, folder_id)
    if result.get('success'):
        return jsonify({'success': True, 'fileId': result.get('fileId'), 'filename': filename})
    # Fallback: download local
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# ── API: Gerar e exportar cartas ────────────────────────────────
@main_bp.route('/api/gerar_cartas', methods=['POST'])
def gerar_cartas():
    req = request.json or {}
    escola_origem = req.get('escola_origem', '')
    template_cfg  = req.get('template', {})
    folder_id     = req.get('folder_id', current_app.config['DRIVE_FOLDER_CARTAS'])

    resultado = _load('progressao_resultado.json')
    if not resultado:
        return jsonify({'success': False, 'error': 'Execute a análise primeiro'}), 400

    cartas = gerar_todas_cartas(resultado, template_cfg, escola_origem)
    script_url = current_app.config['APPS_SCRIPT_URL']
    uploaded = []
    errors   = []

    for filename, buf in cartas.items():
        try:
            payload = {'fileName': filename, 'folderId': folder_id,
                       'fileData': base64.b64encode(buf.getvalue()).decode()}
            resp = requests.post(script_url, json=payload, timeout=60, allow_redirects=True)
            result = resp.json()
            if result.get('success'):
                uploaded.append({'filename': filename, 'fileId': result.get('fileId')})
            else:
                errors.append({'filename': filename, 'error': result.get('error')})
        except Exception as e:
            errors.append({'filename': filename, 'error': str(e)})

    return jsonify({'success': len(uploaded) > 0, 'uploaded': uploaded,
                    'errors': errors, 'total': len(cartas)})

# ── API: Download local do Excel ────────────────────────────────
@main_bp.route('/api/baixar_excel_progressao', methods=['POST'])
def baixar_excel_progressao():
    req = request.json or {}
    escola_origem = req.get('escola_origem', 'Escola')
    bairro        = req.get('bairro', '')
    resultado     = _load('progressao_resultado.json')
    vagas_mun     = _load('vagas_municipais.json')
    vagas_est     = _load('vagas_estaduais.json')

    if not resultado:
        return jsonify({'success': False, 'error': 'Execute a análise primeiro'}), 400

    buf = gerar_excel_progressao(escola_origem, bairro, resultado, vagas_mun, vagas_est)
    date_str = datetime.now().strftime('%d-%m-%Y')
    filename = f"progressao_{escola_origem[:20]}_{date_str}.xlsx".replace(' ','_')
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@main_bp.route('/api/exportar_excel_vagas', methods=['POST'])
def exportar_excel_vagas():
    """Gera e baixa o Excel com resumo de vagas disponíveis."""
    from app.services.excel_service import gerar_excel_vagas
    req = request.json or {}
    escola = req.get('escola_origem', 'Secretaria')
    vagas_mun = _load('vagas_municipais.json')
    vagas_est = _load('vagas_estaduais.json')

    if not vagas_mun and not vagas_est:
        return jsonify({'success': False, 'error': 'Nenhuma vaga carregada'}), 400

    buf = gerar_excel_vagas(vagas_mun, vagas_est, escola)
    date_str = datetime.now().strftime('%d-%m-%Y')
    filename = f"vagas_disponiveis_{date_str}.xlsx"
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
