from http.server import BaseHTTPRequestHandler
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import json
import base64

class handler(BaseHTTPRequestHandler):
    
    def _set_headers(self, status=200, content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_OPTIONS(self):
        self._set_headers()
        
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            keyword = data.get('keyword', '제목 없음')
            
            result = create_thumbnail(keyword)
            
            self._set_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))
            
        except Exception as e:
            self._set_headers(500)
            error_response = {
                'success': False,
                'error': str(e)
            }
            self.wfile.write(json.dumps(error_response).encode('utf-8'))

def create_thumbnail(keyword):
    width, height = 1000, 1000
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)
    
    # 그라데이션 배경
    for y in range(height):
        r = int(33 + (156 - 33) * y / height)
        g = int(150 + (39 - 150) * y / height)
        b = int(243 + (176 - 243) * y / height)
        draw.rectangle([(0, y), (width, y + 1)], fill=(r, g, b))
    
    # 텍스트 3줄 분리
    words = keyword.strip().split(' ')
    total_words = len(words)
    
    if total_words == 1:
        lines = [keyword, '', '']
    elif total_words == 2:
        lines = [words[0], words[1], '']
    else:
        words_per_line = (total_words + 2) // 3
        line1 = ' '.join(words[:words_per_line])
        line2 = ' '.join(words[words_per_line:words_per_line*2])
        line3 = ' '.join(words[words_per_line*2:])
        lines = [line1, line2, line3]
    
    # 폰트 설정
    font_sizes = [90, 80, 70]
    fonts = []
    
    for size in font_sizes:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except:
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", size)
            except:
                font = ImageFont.load_default()
        fonts.append(font)
    
    # 색상 설정
    colors = [
        (255, 215, 0),   # 노란색
        (0, 255, 0),     # 초록색
        (255, 20, 147)   # 분홍색
    ]
    
    outline_color = (0, 0, 0)
    outline_width = 5
    y_positions = [250, 500, 750]
    
    # 텍스트 그리기
    for i, line in enumerate(lines):
        if not line:
            continue
        
        font = fonts[i]
        color = colors[i]
        y_pos = y_positions[i]
        
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (width - text_width) / 2
        y = y_pos - text_height / 2
        
        # 외곽선
        for adj_x in range(-outline_width, outline_width + 1):
            for adj_y in range(-outline_width, outline_width + 1):
                if adj_x != 0 or adj_y != 0:
                    draw.text((x + adj_x, y + adj_y), line, font=font, fill=outline_color)
        
        # 메인 텍스트
        draw.text((x, y), line, font=font, fill=color)
    
    # Base64 인코딩
    buffered = BytesIO()
    img.save(buffered, format="PNG", quality=95)
    img_bytes = buffered.getvalue()
    img_base64 = base64.b64encode(img_bytes).decode('utf-8')
    
    return {
        'success': True,
        'image_base64': img_base64,
        'image_data_url': f'data:image/png;base64,{img_base64}',
        'image_size': len(img_bytes),
        'lines': {
            'line1': lines[0],
            'line2': lines[1],
            'line3': lines[2]
        }
    }
