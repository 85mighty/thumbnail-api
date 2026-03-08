import json
import base64
import re
import urllib.request
from http.server import BaseHTTPRequestHandler


def insert_images_into_html(html, pairs):
    """
    pairs = "제목1|||url1\n제목2|||url2\n..."
    각 H2 아래에 이미지 삽입
    """
    modified = html
    for line in pairs.strip().split('\n'):
        if '|||' not in line:
            continue
        parts = line.split('|||', 1)
        if len(parts) != 2:
            continue
        title = parts[0].strip()
        media_url = parts[1].strip()
        if not title or not media_url:
            continue

        pattern = re.compile(r'<h2[^>]*>([\s\S]*?)<\/h2>', re.IGNORECASE)
        for match in pattern.finditer(modified):
            tag_text = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            if tag_text == title:
                img_tag = (
                    '\n<figure class="wp-block-image">'
                    '<img src="' + media_url + '" alt="' + title + '" '
                    'style="width:100%;height:auto;margin-bottom:20px;">'
                    '</figure>\n'
                )
                modified = modified.replace(match.group(0), match.group(0) + img_tag, 1)
                break

    return modified


def create_post(title, slug, content, status, wp_url, wp_auth):
    body = json.dumps({
        'title': title,
        'slug': slug,
        'content': content,
        'status': status
    }).encode('utf-8')

    req = urllib.request.Request(
        wp_url + '/wp-json/wp/v2/posts',
        data=body,
        headers={
            'Authorization': wp_auth,
            'Content-Type': 'application/json'
        },
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read())


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)

        try:
            raw_text = raw.decode('utf-8', errors='replace')
            # 줄바꿈(\n, \r) 제외한 제어문자만 제거 (JSON 파싱 오류 방지)
            raw_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw_text)
            params = json.loads(raw_text)
        except Exception as e:
            self._json(400, {'error': 'JSON 파싱 실패: ' + str(e)})
            return

        # html: base64 인코딩된 경우 디코딩, 아닌 경우 그대로 사용
        html_raw = params.get('html', '')
        try:
            html = base64.b64decode(html_raw).decode('utf-8')
        except Exception:
            html = html_raw

        pairs      = params.get('pairs', '')
        post_title = params.get('post_title', '')
        post_slug  = params.get('post_slug', '')
        post_status= params.get('post_status', 'publish')
        wp_url     = params.get('wp_url', '').rstrip('/')
        wp_user    = params.get('wp_user', '')
        wp_pass    = params.get('wp_pass', '')

        missing = [k for k in ['html','pairs','wp_url','wp_user','wp_pass'] if not params.get(k)]
        if missing:
            self._json(400, {'error': '필수 파라미터 누락: ' + ', '.join(missing)})
            return

        wp_auth = 'Basic ' + base64.b64encode((wp_user + ':' + wp_pass).encode()).decode()

        final_html = insert_images_into_html(html, pairs)

        try:
            post = create_post(post_title, post_slug, final_html, post_status, wp_url, wp_auth)
            self._json(200, {
                'success': True,
                'post_id': post.get('id'),
                'post_url': post.get('link', '')
            })
        except Exception as e:
            self._json(500, {'error': str(e)})

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
