import json
import base64
import urllib.request
from http.server import BaseHTTPRequestHandler


def generate_image(title, topic, openai_key):
    prompt = (
        'Ultra-realistic travel photograph for a blog post about "' + topic + '". '
        'Scene: ' + title + '. '
        'Shot on Sony A7R V, 35mm lens, natural daylight, photojournalism style. '
        'Real people, real locations, sharp details. '
        'NO text, NO watermarks, NO logos. Pure photorealistic image only.'
    )
    body = json.dumps({
        'model': 'gpt-image-1',
        'prompt': prompt,
        'n': 1,
        'size': '1536x1024',
        'quality': 'high'
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.openai.com/v1/images/generations',
        data=body,
        headers={
            'Authorization': 'Bearer ' + openai_key,
            'Content-Type': 'application/json'
        },
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=120) as res:
        data = json.loads(res.read())

    if not data.get('data') or not data['data'][0].get('b64_json'):
        raise Exception('이미지 생성 실패: ' + str(data))
    return data['data'][0]['b64_json']


def upload_to_wordpress(b64, filename, wp_url, wp_auth):
    binary = base64.b64decode(b64)
    req = urllib.request.Request(
        wp_url + '/wp-json/wp/v2/media',
        data=binary,
        headers={
            'Authorization': wp_auth,
            'Content-Disposition': 'attachment; filename="' + filename + '"',
            'Content-Type': 'image/png'
        },
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        data = json.loads(res.read())
    return data.get('source_url') or data.get('link')


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)

        try:
            params = json.loads(raw.decode('utf-8', errors='replace'))
        except Exception as e:
            self._json(400, {'error': 'JSON 파싱 실패: ' + str(e)})
            return

        # title: base64 인코딩된 경우 디코딩, 아닌 경우 그대로 사용
        title_raw  = params.get('title', '')
        try:
            title = base64.b64decode(title_raw).decode('utf-8')
        except Exception:
            title = title_raw
        topic      = params.get('topic', '일본 여행')
        index      = params.get('index', 1)
        wp_url     = params.get('wp_url', '').rstrip('/')
        wp_user    = params.get('wp_user', '')
        wp_pass    = params.get('wp_pass', '')
        openai_key = params.get('openai_key', '')

        # html 파라미터 없음 - title, wp_url, wp_user, wp_pass, openai_key 만 체크
        missing = [k for k in ['title', 'wp_url', 'wp_user', 'wp_pass', 'openai_key'] if not params.get(k)]
        if missing:
            self._json(400, {'error': '필수 파라미터 누락: ' + ', '.join(missing)})
            return

        wp_auth = 'Basic ' + base64.b64encode((wp_user + ':' + wp_pass).encode()).decode()

        try:
            b64 = generate_image(title, topic, openai_key)

            media_url = upload_to_wordpress(
                b64,
                'section-' + str(index) + '.png',
                wp_url,
                wp_auth
            )

            self._json(200, {
                'success': True,
                'title': title,
                'index': index,
                'media_url': media_url
            })

        except Exception as e:
            self._json(500, {'error': str(e), 'title': title})

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass
