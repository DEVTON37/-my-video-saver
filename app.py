from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import yt_dlp
import os
import threading
import re
import traceback
import logging

import static_ffmpeg
static_ffmpeg.add_paths()

app = Flask(__name__)
CORS(app)

# Create a folder for downloads
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'downloads')
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Setup logging
logging.basicConfig(
    filename='server.log',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s'
)

class MyLogger:
    def debug(self, msg):
        if msg.startswith('[debug] '):
            pass
        else:
            self.info(msg)
    def info(self, msg):
        logging.info(msg)
    def warning(self, msg):
        logging.warning(msg)
    def error(self, msg):
        logging.error(msg)

def clean_error_message(msg):
    if msg is None:
        return "เกิดข้อผิดพลาดที่ไม่ทราบสาเหตุค่ะ (Unknown Error)"
    
    msg = str(msg)
    # Remove ANSI escape sequences
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    msg = ansi_escape.sub('', msg)
    
    if "Unsupported URL" in msg:
        return "ขอโทษนะคะคุณพี่ ลิงก์นี้ไม่ใช่ลิงก์วิดีโอที่นุ่นรู้จักค่ะ รบกวนตรวจสอบว่าเป็นลิงก์จาก YouTube, Facebook, TikTok หรือเว็บวิดีโออื่นๆ หรือเปล่านะคะ"
    if "403" in msg or "Forbidden" in msg:
        return "เข้าถึงไม่ได้ (403 Forbidden) เว็บไซต์นี้บล็อกการดาวน์โหลดจากเซิร์ฟเวอร์ค่ะ คุณพี่ลองเปลี่ยนความละเอียดเป็น 360p หรือ 480p ดูนะคะ"
    if "Sign in" in msg or "login" in msg.lower() or "confirm you're not a bot" in msg.lower():
        return "YouTube บล็อกการเข้าถึงจากเซิร์ฟเวอร์ชั่วคราวค่ะ (Bot Detection) นุ่นกำลังปรับจูนระบบให้ใหม่นะคะ คุณพี่ลองกดใหม่อีกครั้ง หรือลองเปลี่ยนลิงก์อื่นดูก่อนนะคะ"
    if "ffmpeg" in msg.lower():
        return "ระบบประมวลผลวิดีโอ (FFmpeg) มีปัญหาเล็กน้อยค่ะ นุ่นกำลังพยายามแก้ไขให้นะคะ"
    
    return msg

def get_ydl_opts(f_str, is_bilibili=False):
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9,th;q=0.8',
        'Referer': 'https://www.bilibili.com/' if is_bilibili else 'https://www.youtube.com/',
    }
    
    opts = {
        'format': f_str,
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'nocheckcertificate': True,
        'quiet': False,
        'no_warnings': False,
        'ignoreerrors': False,
        'no_playlist': True,
        'retries': 5,
        'fragment_retries': 5,
        'retry_sleep': 2,
        'overwrites': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'http_headers': headers,
        'logger': MyLogger(),
        'merge_output_format': 'mp4',
    }
    
    # Add postprocessors for merging or converting
    opts['postprocessors'] = [{
        'key': 'FFmpegVideoConvertor',
        'preferedformat': 'mp4',
    }]
    
    # Cloud-friendly extractor args
    opts['extractor_args'] = {
        'youtube': {
            'player_client': ['android', 'ios'],
            'player_skip': ['webpage', 'configs'],
        }
    }
    
    return opts

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/assets/<path:path>')
def send_assets(path):
    return send_from_directory('assets', path)

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.json
    video_url = data.get('url')
    quality = data.get('quality', '720')
    
    if not video_url:
        return jsonify({'success': False, 'error': 'กรุณาวางลิงก์ก่อนนะคะ'}), 400

    logging.info(f"Start download request: {video_url} (Quality: {quality})")
    is_bilibili = 'bilibili.com' in video_url.lower() or 'bilibili.tv' in video_url.lower()
    result_container = {'success': False, 'error': None}

    def run_dl(current_format, attempt_name):
        try:
            logging.info(f"Attempting: {attempt_name} with format: {current_format}")
            opts = get_ydl_opts(current_format, is_bilibili)
            with yt_dlp.YoutubeDL(opts) as ydl:
                try:
                    info = ydl.extract_info(video_url, download=True)
                except Exception as inner_e:
                    logging.error(f"Error during extract_info in {attempt_name}: {str(inner_e)}")
                    result_container['error'] = str(inner_e)
                    return False

                if info is None:
                    result_container['error'] = "ไม่สามารถดึงข้อมูลวิดีโอได้ค่ะ"
                    return False
                
                filename = ydl.prepare_filename(info)
                # yt-dlp might change extension after merge
                if not os.path.exists(filename):
                    base_name = os.path.splitext(filename)[0]
                    for f in os.listdir(DOWNLOAD_FOLDER):
                        if os.path.join(DOWNLOAD_FOLDER, f).startswith(base_name):
                            filename = os.path.join(DOWNLOAD_FOLDER, f)
                            break
                
                if os.path.exists(filename):
                    result_container['success'] = True
                    result_container['title'] = info.get('title', 'Video')
                    result_container['file'] = os.path.basename(filename)
                    result_container['is_bilibili'] = is_bilibili
                    return True
                
                result_container['error'] = "โหลดเสร็จแต่หาไฟล์ไม่เจอค่ะ"
                return False
        except Exception as e:
            result_container['error'] = str(e)
            return False

    # --- EXECUTION STRATEGY ---
    try:
        success = False
        if is_bilibili:
            success = run_dl('bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[ext=mp4]/best', "Bilibili AVC")
            if not success:
                success = run_dl('bestvideo+bestaudio/best', "Bilibili Best")
        else:
            if quality == 'worst': format_str = 'best[ext=mp4]/worst[ext=mp4]/worst'
            elif quality == '360': format_str = 'best[height<=360][ext=mp4]/best[height<=360]/best'
            elif quality == '480': format_str = 'best[height<=480][ext=mp4]/best[height<=480]/best'
            elif quality == '720': format_str = 'best[height<=720][ext=mp4]/best[height<=720]/best'
            elif quality == '1080': format_str = 'best[height<=1080][ext=mp4]/best[height<=1080]/best'
            else: format_str = 'best[ext=mp4]/best'

            success = run_dl(format_str, "Primary")
            if not success:
                success = run_dl('best', "Fallback")

        if result_container['success']:
            return jsonify(result_container)
        else:
            error_msg = clean_error_message(result_container.get('error', 'Unknown error'))
            return jsonify({'success': False, 'error': error_msg}), 500

    except Exception as e:
        logging.error(f"Critical error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': f'เกิดข้อผิดพลาดรุนแรง: {str(e)}'}), 500

@app.route('/api/open-folder', methods=['POST'])
def open_folder():
    try:
        import subprocess
        # This only works on local Windows
        if os.name == 'nt':
            subprocess.Popen(f'explorer "{os.path.abspath(DOWNLOAD_FOLDER)}"')
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Cannot open folder on cloud server'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get-file/<path:filename>')
def get_file(filename):
    try:
        return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)
    except Exception as e:
        return str(e), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8001))
    app.run(host='0.0.0.0', port=port, debug=True)
