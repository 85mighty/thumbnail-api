"""
Vercel 썸네일 API - Binary 직접 반환 버전
WordPress 호환
"""

from http.server import BaseHTTPRequestHandler
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import json
import os

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            title = data.get('title', '제목 없음')
            keyword = data.get('keyword', '')
            bg_color1 = data.get('bg_color1', '#667eea')
            bg_color2 = data.get('bg_color2', '#764ba2')
            
            # 썸네일 생성
            thumbnail = self.create_thumbnail(title, keyword, bg_color1, bg_color2)
            
            # PNG로 변환
            buffer = BytesIO()
            thumbnail.save(buffer, format='PNG', quality=95)
            buffer.seek(0)
            
            # 🔥 Binary로 직접 반환 (JSON 아님!)
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', str(len(buffer.getvalue())))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(buffer.getvalue())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            error_response = {
                'success': False,
                'error': str(e)
            }
            
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def load_font(self, size, bold=False):
        """폰트 로드"""
        try:
            if bold:
                font_path = '/var/task/fonts/NanumGothicBold.ttf'
            else:
                font_path = '/var/task/fonts/NanumGothic.ttf'
            
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, size)
        except:
            pass
        
        try:
            if bold:
                font_path = 'fonts/NanumGothicBold.ttf'
            else:
                font_path = 'fonts/NanumGothic.ttf'
            
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, size)
        except:
            pass
        
        return ImageFont.load_default()
    
    def create_thumbnail(self, title, keyword, bg_color1, bg_color2):
        """썸네일 생성"""
        width, height = 1200, 630
        
        img = Image.new('RGB', (width, height), color=bg_color1)
        draw = ImageDraw.Draw(img)
        
        # 그라데이션
        self.draw_gradient(draw, width, height, bg_color1, bg_color2)
        
        # 폰트
        font_title = self.load_font(70, bold=True)
        font_keyword = self.load_font(36, bold=False)
        
        # 제목
        wrapped_lines = self.wrap_text(title, font_title, draw, max_width=1000)
        
        y_offset = 180
        for line in wrapped_lines[:3]:
            bbox = draw.textbbox((0, 0), line, font=font_title)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            x = (width - text_width) // 2
            
            # 그림자
            draw.text((x + 4, y_offset + 4), line, font=font_title, fill=(0, 0, 0, 80))
            
            # 메인 텍스트
            draw.text((x, y_offset), line, font=font_title, fill='white')
            
            y_offset += text_height + 20
        
        # 키워드 배지
        if keyword:
            self.draw_keyword_badge(draw, keyword, font_keyword, width, height)
        
        # 워터마크
        self.draw_watermark(draw, width, height, font_keyword)
        
        return img
    
    def draw_gradient(self, draw, width, height, color1, color2):
        """그라데이션"""
        r1, g1, b1 = self.hex_to_rgb(color1)
        r2, g2, b2 = self.hex_to_rgb(color2)
        
        for y in range(height):
            ratio = y / height
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            
            draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    def wrap_text(self, text, font, draw, max_width):
        """줄바꿈"""
        words = text.split()
        lines = []
        current_line = ''
        
        for word in words:
            test_line = current_line + word + ' '
            bbox = draw.textbbox((0, 0), test_line, font=font)
            line_width = bbox[2] - bbox[0]
            
            if line_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line.strip())
                current_line = word + ' '
        
        if current_line:
            lines.append(current_line.strip())
        
        return lines
    
    def draw_keyword_badge(self, draw, keyword, font, width, height):
        """키워드 배지"""
        badge_y = height - 100
        
        bbox = draw.textbbox((0, 0), keyword, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        badge_width = text_width + 40
        badge_height = text_height + 24
        badge_x = (width - badge_width) // 2
        
        draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + badge_width, badge_y + badge_height],
            radius=badge_height // 2,
            fill='#764ba2',
            outline='white',
            width=2
        )
        
        text_x = badge_x + 20
        text_y = badge_y + 12
        draw.text((text_x, text_y), keyword, font=font, fill='white')
    
    def draw_watermark(self, draw, width, height, font):
        """워터마크"""
        watermark = 'ekunblog.com'
        
        bbox = draw.textbbox((0, 0), watermark, font=font)
        text_width = bbox[2] - bbox[0]
        
        x = width - text_width - 30
        y = height - 50
        
        draw.text((x, y), watermark, font=font, fill=(255, 255, 255, 180))
    
    def hex_to_rgb(self, hex_color):
        """HEX to RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
