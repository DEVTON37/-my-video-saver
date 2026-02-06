from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import yt_dlp
import os
import threading

import static_ffmpeg
static_ffmpeg.add_paths()

app = Flask(__name__)
CORS(app)

# Create a folder for downloads
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'downloads')
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/assets/<path:path>')
def send_assets(path):
    return send_from_directory('assets', path)

import re
import traceback
import logging

# Setup logging
logging.basicConfig(
    filename='server.log',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s'
)

def clean_error_message(msg):
    # Remove ANSI escape sequences (like [0;31m)
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    msg = ansi_escape.sub('', msg)
    
    # Friendly messages for common errors
    if "Unsupported URL" in msg:
        return "ขอโทษนะคะคุณพี่ ลิงก์นี้ไม่ใช่ลิงก์วิดีโอที่นุ่นรู้จักค่ะ รบกวนตรวจสอบว่าเป็นลิงก์จาก YouTube, Facebook, TikTok หรือเว็บวิดีโออื่นๆ หรือเปล่านะคะ"
    if "403" in msg or "Forbidden" in msg:
        return "เข้าถึงไม่ได้ (403 Forbidden) นุ่นพยายามแก้แล้วแต่ดูเหมือนเว็บนี้จะบล็อกเข้มงวดมากค่ะ คุณพี่ลองเปิดวิดีโอนี้ใน Chrome ทิ้งไว้แล้วค่อยมากดดาวน์โหลดอีกทีนะคะ"
    if "Sign in" in msg:
        return "วิดีโอนี้ต้องเข้าสู่ระบบก่อนถึงจะดูได้ นุ่นเลยโหลดให้ไม่ได้ค่ะ"
    if "ffmpeg" in msg.lower():
        return "เว็บไซต์นี้ (เช่น Bilibili) แยกไฟล์ภาพกับเสียงออกจากกันค่ะ และเนื่องจากเครื่องคุณพี่ไม่มีโปรแกรม FFmpeg นุ่นเลยรวมร่างให้ไม่ได้ค่ะ แต่นุ่นจะพยายามโหลดแบบภาพอย่างเดียวให้แทนนะคะ!"
    
    return msg

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.json
    video_url = data.get('url')
    quality = data.get('quality', '720')
    
    print(f"\n--- New Download Request ---")
    print(f"URL: {video_url}")
    print(f"Quality: {quality}")
    
    if not video_url:
        return jsonify({'success': False, 'error': 'กรุณาวางลิงก์ก่อนนะคะ'}), 400

    logging.info(f"Start download request: {video_url} (Quality: {quality})")

    try:
        is_bilibili = 'bilibili.com' in video_url.lower() or 'bilibili.tv' in video_url.lower()
        
        # Base configuration for yt-dlp
        def get_ydl_opts(f_str, use_cookies=False):
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'en-US,en;q=0.9,th;q=0.8',
                'Referer': 'https://www.bilibili.com/' if is_bilibili else 'https://www.google.com/',
            }
            
            return {
                'format': f_str,
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
                'nocheckcertificate': True,
                'quiet': False,
                'no_warnings': False,
                'ignoreerrors': False,
                'no_playlist': True,
                'retries': 10,
                'fragment_retries': 10,
                'retry_sleep': 5,
                'overwrites': True, # Ensure we re-download if the user tries again
                # Remove impersonate as it's causing AssertionError in this environment
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'http_headers': headers,
                'cookiesfrombrowser': ('chrome',) if use_cookies else None,
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                        'skip': ['dash', 'hls']
                    },
                    'bilibili': {
                        'use_api_device': 'pc'
                    }
                },
                'merge_output_format': 'mp4',
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }]
            }
        
        result_container = {'success': False, 'error': None}

        def run_dl(current_format, attempt_name, use_cookies=False):
            try:
                logging.info(f"Attempting: {attempt_name} with format: {current_format}")
                opts = get_ydl_opts(current_format, use_cookies)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(video_url, download=True)
                    if not info:
                        logging.warning(f"No info returned for {attempt_name}")
                        return False
                    
                    filename = ydl.prepare_filename(info)
                    logging.info(f"Expected filename: {filename}")
                    
                    # Extension check fallback (sometimes yt-dlp changes extension during download)
                    if not os.path.exists(filename):
                        base_name = os.path.splitext(filename)[0]
                        for f in os.listdir(DOWNLOAD_FOLDER):
                            if os.path.join(DOWNLOAD_FOLDER, f).startswith(base_name):
                                filename = os.path.join(DOWNLOAD_FOLDER, f)
                                logging.info(f"Found actual file via fallback: {filename}")
                                break
                    
                    if os.path.exists(filename):
                        result_container['success'] = True
                        result_container['title'] = info.get('title', 'Video')
                        result_container['file'] = os.path.basename(filename)
                        result_container['is_bilibili'] = is_bilibili
                        logging.info(f"Success! File saved: {filename}")
                        return True
                    
                    logging.error(f"File not found after download: {filename}")
                    return False
            except Exception as e:
                err = str(e)
                logging.error(f"Error in {attempt_name}: {err}\n{traceback.format_exc()}")
                result_container['error'] = err
                return False

        # --- EXECUTION STRATEGY ---
        success = False
        
        if is_bilibili:
            # Bilibili Strategy: Force H.264 + AAC for Windows Media Player compatibility
            # Try 1: Best AVC (h264) video + AAC audio
            success = run_dl('bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[ext=mp4]/best', "Bilibili AVC+AAC")
            
            if not success:
                # Try 2: General best video + best audio (might get HEVC/AV1)
                success = run_dl('bestvideo+bestaudio/best', "Bilibili Best Combined")
            
            if not success:
                # Try 3: Any single stream that might exist
                success = run_dl('best', "Bilibili Single Stream")
            
            if not success:
                # Try 4: Worst but single
                success = run_dl('worst', "Bilibili Worst")
        else:
            # Standard Strategy (YouTube, etc.)
            # Optimized format string for NO-FFMPEG environment
            if quality == 'worst':
                format_str = 'best[ext=mp4]/worst[ext=mp4]/worst'
            elif quality == '360':
                format_str = 'best[height<=360][ext=mp4]/best[height<=360]/best'
            elif quality == '480':
                format_str = 'best[height<=480][ext=mp4]/best[height<=480]/best'
            elif quality == '720':
                format_str = 'best[height<=720][ext=mp4]/best[height<=720]/best'
            elif quality == '1080':
                format_str = 'best[height<=1080][ext=mp4]/best[height<=1080]/best'
            else:
                format_str = 'best[ext=mp4]/best'

            # 1. Try with Cookies + Quality
            success = run_dl(f"{format_str}", "Primary (With Cookies)", use_cookies=True)
            if not success:
                # 2. Try without cookies
                success = run_dl(f"{format_str}", "Retry without Cookies")
            if not success:
                # 3. Fallback to best available single stream
                success = run_dl('best', "Fallback Best")

        if result_container['success']:
            if result_container.get('is_bilibili'):
                result_container['message'] = "นุ่นโหลดวิดีโอจาก Bilibili พร้อมเสียงมาให้คุณพี่สำเร็จแล้วค่ะ! ครั้งนี้นุ่นติดตั้งระบบรวมร่างไฟล์ (FFmpeg) ให้เรียบร้อยแล้ว ดูได้แบบฟินๆ เลยนะคะ"
            return jsonify(result_container)
        else:
            error_msg = clean_error_message(result_container.get('error', 'Unknown error'))
            logging.error(f"All attempts failed. Final error: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500

    except Exception as e:
        print(f"CRITICAL SERVER ERROR: {str(e)}")
        return jsonify({'success': False, 'error': f'เกิดข้อผิดพลาดรุนแรง: {str(e)}'}), 500

@app.route('/api/open-folder', methods=['POST'])
def open_folder():
    try:
        import subprocess
        # Use explorer to open the download folder in Windows
        subprocess.Popen(f'explorer "{os.path.abspath(DOWNLOAD_FOLDER)}"')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get-file/<path:filename>')
def get_file(filename):
    try:
        return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)
    except Exception as e:
        return str(e), 404

if __name__ == '__main__':
    # สำหรับรันบน Cloud หรือ Heroku/Render ต้องใช้ PORT จาก Environment Variable ค่ะ
    port = int(os.environ.get('PORT', 8001))
    app.run(host='0.0.0.0', port=port, debug=True)
