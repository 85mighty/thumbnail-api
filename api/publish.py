import json
import base64
import re
import time
import urllib.request
import urllib.error
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
        f'Ultra-realistic travel photograph for a blog post about "{topic}". '
        f'Scene: {title}. '
        f'Shot on Sony A7R V, 35mm lens, natural daylight, photojournalism style. '
        f'Real people, real locations, sharp details, authentic atmosphere. '
        f'NO text, NO watermarks, NO logos, NO overlays. Pure photorealistic image only.'
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
            'Authorization': f'Bearer {openai_key}',
            'Content-Type': 'application/json'
        },
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=120) as res:
        data = json.loads(res.read())

    if not data.get('data') or not data['data'][0].get('b64_json'):
        raise Exception(f"이미지 생성 실패: {data}")
    return data['data'][0]['b64_json']

def upload_to_wordpress(b64, filename, wp_url, wp_auth):
    binary = base64.b64decode(b64)
    req = urllib.request.Request(
        f'{wp_url}/wp-json/wp/v2/media',
        data=binary,
        headers={
            'Authorization': wp_auth,
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Type': 'image/png'
        },
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        data = json.loads(res.read())
    return data.get('source_url') or data.get('link')

def create_post(title, slug, content, status, wp_url, wp_auth):
    body = json.dumps({
        'title': title,
        'slug': slug,
        'content': content,
        'status': status
    }).encode('utf-8')
    req = urllib.request.Request(
        f'{wp_url}/wp-json/wp/v2/posts',
        data=body,
        headers={
            'Authorization': wp_auth,
            'Content-Type': 'application/json'
        },
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read())

def update_post(post_id, content, status, wp_url, wp_auth):
    body = json.dumps({
        'content': content,
        'status': status
    }).encode('utf-8')
    req = urllib.request.Request(
        f'{wp_url}/wp-json/wp/v2/posts/{post_id}',
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
        self._set_cors()
        self.end_headers()

    def do_POST(self):
        self._set_cors()
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)

        try:
            params = json.loads(raw)
        except Exception:
            self._json(400, {'error': 'JSON 파싱 실패'})
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

        if not all([html, wp_url, wp_user, wp_pass, openai_key]):
            self._json(400, {'error': '필수 파라미터 누락'})
            return

        wp_auth = 'Basic ' + base64.b64encode(f'{wp_user}:{wp_pass}'.encode()).decode()
        sections = extract_h2_sections(html)
        log = [f'H2 {len(sections)}개 발견']
        modified_html = html
        ok_count = 0

        for i, sec in enumerate(sections):
            tag   = sec['tag']
            title = sec['title']
            log.append(f'[{i+1}/{len(sections)}] "{title}"')
            try:
                b64 = generate_image(title, topic, openai_key)
                log.append('  ✅ 이미지 생성 완료')

                media_url = upload_to_wordpress(b64, f'section-{i+1}.png', wp_url, wp_auth)
                log.append(f'  ✅ 업로드: {media_url}')

                img_tag = f'\n<figure class="wp-block-image"><img src="{media_url}" alt="{title}" style="width:100%;height:auto;margin-bottom:20px;"></figure>\n'
                modified_html = modified_html.replace(tag, tag + img_tag, 1)
                ok_count += 1

            except Exception as e:
                log.append(f'  ❌ 오류: {str(e)}')

            time.sleep(2)

        log.append(f'이미지 {ok_count}/{len(sections)}개 완료')

        try:
            if post_id:
                post = update_post(post_id, modified_html, post_status, wp_url, wp_auth)
            else:
                post = create_post(post_title, post_slug, modified_html, post_status, wp_url, wp_auth)
            log.append(f'✅ 발행 완료: ID {post["id"]}')
            self._json(200, {
                'success': True,
                'post_id': post['id'],
                'post_url': post.get('link', ''),
                'images_inserted': ok_count,
                'total_sections': len(sections),
                'log': log
            })
        except Exception as e:
            log.append(f'❌ 발행 오류: {str(e)}')
            self._json(500, {'error': str(e), 'log': log})

    def _set_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self._set_cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass
