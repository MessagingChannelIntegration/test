from datetime import datetime

# utils.py (��ƿ��Ƽ ����)
class APIError(Exception):
    def __init__(self, service, message):
        super().__init__(f"{service} API Error: {message}")


def handle_error(service, response):
    #API ȣ�� ���� ó��
    error = response.json().get('error', 'Unknown Error')
    raise APIError(service, f"{response.status_code} - {error}")

def format_timestamp(ts):
    return datetime.fromtimestamp(float(ts)).strftime('%Y-%m-%d %H:%M:%S')
