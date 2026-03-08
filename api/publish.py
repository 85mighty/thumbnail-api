import json
import base64
import re
import time
import urllib.request
from http.server import BaseHTTPRequestHandler

SKIP_KEYWORDS = ['자주 묻는 질문', 'FAQ', '함께 읽으면', '함께읽으면']


def extract_h2_sections(html):
    pattern = re.compile(r'<h2[^>]*>([\s\S]*?)<\/h2>', re.IGNORECASE)
    sections = []
    for match in pattern.finditer(html):
        title = re.sub(r'<[^>]+>', '', match.group(1)).strip()
        if not any(kw in title for kw in SKIP_KEYWORDS):
            sections.append({'tag': match.group(0), 'title': title})
    return sections


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


def create_or_update_post(post_id, title, slug, content, status, wp_url, wp_auth):
    body_data = {'content': content, 'status': status}
    if not post_id:
        body_data['title'] = title
        body_data['slug'] = slug

    body = json.dumps(body_data).encode('utf-8')
    url = wp_url + '/wp-json/wp/v2/posts'
    if post_id:
        url = url + '/' + str(post_id)

    req = urllib.request.Request(
        url, data=body,
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
            params = json.loads(raw.decode('utf-8', errors='replace'))
        except Exception as e:
            self._json(400, {'error': 'JSON 파싱 실패: ' + str(e)})
            return

        html       = params.get('html', '')
        post_id    = params.get('post_id')
        post_title = params.get('post_title', '새 포스트')
        post_slug  = params.get('post_slug', '')
        post_status= params.get('post_status', 'publish')
        topic      = params.get('topic', '일본 여행')
        wp_url     = params.get('wp_url', '').rstrip('/')
        wp_user    = params.get('wp_user', '')
        wp_pass    = params.get('wp_pass', '')
        openai_key = params.get('openai_key', '')

        missing = [k for k in ['html','wp_url','wp_user','wp_pass','openai_key'] if not params.get(k)]
        if missing:
            self._json(400, {'error': '필수 파라미터 누락: ' + ', '.join(missing)})
            return

        wp_auth = 'Basic ' + base64.b64encode((wp_user + ':' + wp_pass).encode()).decode()
        sections = extract_h2_sections(html)
        log = ['H2 ' + str(len(sections)) + '개 발견']
        modified_html = html
        ok_count = 0

        for i, sec in enumerate(sections):
            tag   = sec['tag']
            title = sec['title']
            log.append('[' + str(i+1) + '/' + str(len(sections)) + '] ' + title)
            try:
                b64 = generate_image(title, topic, openai_key)
                log.append('  이미지 생성 완료')
                media_url = upload_to_wordpress(b64, 'section-' + str(i+1) + '.png', wp_url, wp_auth)
                log.append('  업로드: ' + str(media_url))
                img_tag = (
                    '\n<figure class="wp-block-image">'
                    '<img src="' + str(media_url) + '" alt="' + title + '" '
                    'style="width:100%;height:auto;margin-bottom:20px;">'
                    '</figure>\n'
                )
                modified_html = modified_html.replace(tag, tag + img_tag, 1)
                ok_count += 1
            except Exception as e:
                log.append('  오류: ' + str(e))
            time.sleep(2)

        try:
            post = create_or_update_post(
                post_id, post_title, post_slug,
                modified_html, post_status, wp_url, wp_auth
            )
            self._json(200, {
                'success': True,
                'post_id': post.get('id'),
                'post_url': post.get('link', ''),
                'images_inserted': ok_count,
                'total_sections': len(sections),
                'log': log
            })
        except Exception as e:
            self._json(500, {'error': str(e), 'log': log})

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
