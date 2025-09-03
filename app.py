from flask import Flask, render_template, request, jsonify, send_from_directory
import yt_dlp
import os
import threading
import re

ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

app = Flask(__name__)
DOWNLOAD_FOLDER = os.getenv("DOWNLOAD_FOLDER", "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

download_progress = {}

def get_existing_folders():
    """Zwraca listę istniejących folderów w katalogu downloads"""
    return [f for f in os.listdir(DOWNLOAD_FOLDER) if os.path.isdir(os.path.join(DOWNLOAD_FOLDER, f))]

def progress_hook(d):
    video_id = d['info_dict'].get('id', 'unknown')
    
    # Upewnij się, że mamy już słownik dla video_id (np. ustawiony przy inicjalizacji pobierania)
    if video_id not in download_progress:
        download_progress[video_id] = {'progress': 0, 'status': '', 'logs': ''}
    
    if d['status'] == 'downloading':
        if '_percent_str' in d:
            p_str = d['_percent_str'].strip()  # np. "42.3%"
            # Usuń kody ANSI (np. kolory) z ciągu
            p_str = ansi_escape.sub('', p_str)
            p_str = p_str.replace('%', '').strip()  # usuwamy znak %
            try:
                print("PRZED PERCENTEM")
                percent = float(p_str)
                print(f"PO PERCENTCIE {percent}")
                download_progress[video_id]['progress'] = percent
                download_progress[video_id]['status'] = 'Pobieranie...'
            except ValueError:
                download_progress[video_id]['progress'] = 0
                download_progress[video_id]['status'] = 'Błąd konwersji procentów'
        else:
            downloaded_bytes = d.get('downloaded_bytes', 0)
            total_bytes = d.get('total_bytes', 1)
            if total_bytes > 0:
                percent = (downloaded_bytes / total_bytes) * 100
                download_progress[video_id]['progress'] = round(percent, 2)
                download_progress[video_id]['status'] = 'Pobieranie...'
            else:
                download_progress[video_id]['progress'] = 0
                download_progress[video_id]['status'] = 'Trwa inicjalizacja pobierania...'
    
    elif d['status'] == 'finished':
        download_progress[video_id]['progress'] = 100
        download_progress[video_id]['status'] = 'Pobieranie zakończone!'



# Niestandardowy logger zapisujący logi bezpośrednio do download_progress
class MyLogger:
    def __init__(self, video_id):
        self.video_id = video_id
    def debug(self, msg):
        download_progress[self.video_id]['logs'] += msg + "\n"
    def info(self, msg):
        download_progress[self.video_id]['logs'] += msg + "\n"
    def warning(self, msg):
        download_progress[self.video_id]['logs'] += msg + "\n"
    def error(self, msg):
        download_progress[self.video_id]['logs'] += msg + "\n"

def download_video(url, download_path, video_id):
    """Pobiera film w osobnym wątku i aktualizuje postęp oraz logi"""
    # Inicjalizujemy strukturę dla tego pobierania
    download_progress[video_id] = {'progress': 0, 'status': 'Rozpoczynanie...', 'logs': ''}
    
    ydl_opts = {
        'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
        'format': 'bestvideo+bestaudio/best',
        'progress_hooks': [progress_hook],
        'quiet': True,  # wyłącza standardowe logi yt-dlp
        'writeinfojson': False,
        'logger': MyLogger(video_id),  # używamy naszego niestandardowego loggera
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        download_progress[video_id]['progress'] = 0
        download_progress[video_id]['status'] = f'Błąd: {str(e)}'

@app.route('/')
def index():
    """Renderuje stronę główną z listą folderów"""
    folders = get_existing_folders()
    return render_template('index.html', folders=folders)

@app.route('/download', methods=['POST'])
def download():
    """Rozpoczyna pobieranie filmu i zwraca ID do śledzenia progresu"""
    url = request.form.get('url')
    custom_path = request.form.get('path', '').strip()
    folder_name = custom_path if custom_path else "default"
    download_path = os.path.join(DOWNLOAD_FOLDER, folder_name)
    os.makedirs(download_path, exist_ok=True)

    video_id = url.split("=")[-1]  # Pobieramy ID z URL

    # Inicjalizacja rekordu dla pobierania
    download_progress[video_id] = {'progress': 0, 'status': 'Rozpoczynanie...', 'logs': ''}
    
    # Pobieranie w osobnym wątku
    threading.Thread(target=download_video, args=(url, download_path, video_id)).start()

    return jsonify({"message": "Pobieranie rozpoczęte!", "video_id": video_id})

@app.route('/progress', methods=['GET'])
def progress():
    """Zwraca postęp pobierania dla wszystkich filmów"""
    return jsonify(download_progress)

@app.route('/logs/<video_id>')
def get_logs(video_id):
    """Zwraca logi z procesu pobierania i czyści je po odczycie"""
    entry = download_progress.get(video_id, {})
    logs = entry.get('logs', '')
    # # Czyścimy logi, aby przy następnym fetchu zwrócić tylko nowe
    # entry['logs'] = ''
    return jsonify({"logs": logs if logs else "Brak logów."})

@app.route('/api/download')
def api_download():
    """API do pobierania filmów przez query parameter"""
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Brak URL"}), 400

    folder_name = "default"
    download_path = os.path.join(DOWNLOAD_FOLDER, folder_name)
    os.makedirs(download_path, exist_ok=True)

    video_id = url.split("=")[-1]
    threading.Thread(target=download_video, args=(url, download_path, video_id)).start()

    return jsonify({"message": "Pobieranie rozpoczęte!", "video_id": video_id})

@app.route('/videos')
def videos():
    """Wyświetla listę folderów i plików w katalogu downloads"""
    def get_files_in_folder(path):
        files_structure = {}
        for folder in os.listdir(path):
            folder_path = os.path.join(path, folder)
            if os.path.isdir(folder_path):
                files_structure[folder] = get_files_in_folder(folder_path)
            else:
                files_structure[folder] = None
        return files_structure

    files_tree = get_files_in_folder(DOWNLOAD_FOLDER)
    return render_template('videos.html', files_tree=files_tree)

@app.route('/downloads/<folder>/<filename>')
def download_file(folder, filename):
    """Serwuje pliki z folderu downloads"""
    download_path = os.path.join(DOWNLOAD_FOLDER, folder)
    return send_from_directory(download_path, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
