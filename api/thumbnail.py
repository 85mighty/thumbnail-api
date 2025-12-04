"""
Vercel 썸네일 API - 1:1 비율, 포커스 키워드 전용
각 줄마다 다른 색상 (노란색, 초록색, 핑크색)
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
            
            # 키워드만 사용
            keyword = data.get('keyword', '키워드 없음')
            bg_color1 = data.get('bg_color1', '#667eea')
            bg_color2 = data.get('bg_color2', '#764ba2')
            
            # 썸네일 생성 (1:1 비율)
            thumbnail = self.create_thumbnail(keyword, bg_color1, bg_color2)
            
            # PNG로 변환
            buffer = BytesIO()
            thumbnail.save(buffer, format='PNG', quality=95)
            buffer.seek(0)
            
            # Binary로 직접 반환
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
    
    def load_font(self, size, bold=True):
        """폰트 로드 (기본 볼드)"""
        try:
            font_path = '/var/task/fonts/NanumGothicBold.ttf'
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, size)
        except:
            pass
        
        try:
            font_path = 'fonts/NanumGothicBold.ttf'
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, size)
        except:
            pass
        
        return ImageFont.load_default()
    
    def create_thumbnail(self, keyword, bg_color1, bg_color2):
        """1:1 썸네일 생성 - 포커스 키워드만"""
        # 1:1 비율 (정사각형)
        size = 1080
        
        img = Image.new('RGB', (size, size), color=bg_color1)
        draw = ImageDraw.Draw(img)
        
        # 그라데이션 배경
        self.draw_gradient(draw, size, size, bg_color1, bg_color2)
        
        # 키워드를 띄어쓰기로 분리
        words = keyword.split()
        
        # 줄 색상 (노란색, 초록색, 핑크색, 핑크색)
        line_colors = [
            '#FFD700',  # 노란색 (Gold)
            '#00FF00',  # 초록색 (Lime)
            '#FF1493',  # 핑크색 (DeepPink)
            '#FF1493'   # 핑크색 (DeepPink)
        ]
        
        # 최대 4줄
        lines = words[:4]
        num_lines = len(lines)
        
        # 폰트 크기 계산 (화면의 85% 채우도록 더욱 크게)
        if num_lines == 1:
            font_size = 320
        elif num_lines == 2:
            font_size = 260
        elif num_lines == 3:
            font_size = 210
        else:  # 4줄
            font_size = 170
        
        font = self.load_font(font_size)
        
        # 전체 텍스트 높이 계산
        total_height = 0
        line_heights = []
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_height = bbox[3] - bbox[1]
            line_heights.append(line_height)
            total_height += line_height
        
        # 줄 간격 (조금 더 넓게)
        line_spacing = 30
        total_height += line_spacing * (num_lines - 1)
        
        # 시작 Y 위치 (중앙 정렬)
        y_offset = (size - total_height) // 2
        
        # 각 줄 그리기
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            
            # X 위치 (중앙 정렬)
            x = (size - text_width) // 2
            
            # 색상 선택
            color = line_colors[i]
            
            # 검은색 테두리 (2px, 8방향)
            outline_width = 2
            for offset_x in range(-outline_width, outline_width + 1):
                for offset_y in range(-outline_width, outline_width + 1):
                    if offset_x != 0 or offset_y != 0:
                        draw.text((x + offset_x, y_offset + offset_y), 
                                 line, font=font, fill='black')
            
            # 메인 텍스트 (컬러)
            draw.text((x, y_offset), line, font=font, fill=color)
            
            # 다음 줄 위치
            y_offset += line_heights[i] + line_spacing
        
        # 워터마크 (우측 하단)
        self.draw_watermark(draw, size, size)
        
        return img
    
    def draw_gradient(self, draw, width, height, color1, color2):
        """그라데이션 배경"""
        r1, g1, b1 = self.hex_to_rgb(color1)
        r2, g2, b2 = self.hex_to_rgb(color2)
        
        for y in range(height):
            ratio = y / height
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            
            draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    def draw_watermark(self, draw, width, height):
        """워터마크 (작은 폰트)"""
        watermark = 'ekunblog.com'
        
        try:
            font_path = '/var/task/fonts/NanumGothic.ttf'
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, 24)
            else:
                font_path = 'fonts/NanumGothic.ttf'
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, 24)
                else:
                    font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        bbox = draw.textbbox((0, 0), watermark, font=font)
        text_width = bbox[2] - bbox[0]
        
        x = width - text_width - 20
        y = height - 40
        
        # 반투명 흰색
        draw.text((x, y), watermark, font=font, fill=(255, 255, 255, 180))
    
    def hex_to_rgb(self, hex_color):
        """HEX to RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
