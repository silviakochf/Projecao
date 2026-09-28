import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'progressao-secret-2026')
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'session_data')
    APPS_SCRIPT_URL = os.environ.get(
        'GOOGLE_APPS_SCRIPT_URL',
        'https://script.google.com/macros/s/AKfycbynKYAQnvRy-s3bMm57KuADK1inIz8E4YcZJhWCm8lJxeCvzjljEr9EuggMRfW7MqYkhg/exec'
    )
    DRIVE_FOLDER_PROGRESSAO = "1dfULMNbu0-83A-Di7dtlxrSm3_MQ1X1k"
    DRIVE_FOLDER_CARTAS      = "13C4IZYrMMIioMz2ymYaP29C3SCFJu8gR"
