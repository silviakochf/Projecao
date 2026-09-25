import os, io, json, base64, logging, requests
from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)

APPS_SCRIPT_URL = os.environ.get(
    'GOOGLE_APPS_SCRIPT_URL',
    'https://script.google.com/macros/s/AKfycbxFn4UnPPKmZrQMkLur7x1ESRmztUd9QcogIrF3J-UtBaJyYm6DEcL57bseq90qi_1w/exec'
)

def upload_to_drive(data: bytes, filename: str, folder_id: str) -> dict:
    try:
        payload = {
            'fileName': filename,
            'folderId': folder_id,
            'fileData': base64.b64encode(data).decode('utf-8')
        }
        resp = requests.post(APPS_SCRIPT_URL, json=payload, timeout=60, allow_redirects=True)
        text = resp.text.strip()
        if not text:
            return {'success': False, 'error': 'Resposta vazia do Apps Script'}
        result = json.loads(text)
        logger.info(f"Drive upload: {filename} → {result}")
        return result
    except Exception as e:
        logger.error(f"Erro upload Drive: {e}")
        return {'success': False, 'error': str(e)}
