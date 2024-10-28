import tempfile
import subprocess
import time
import requests
from io import BytesIO
import os, sys
sys.path.append(os.path.abspath(__file__))
from cog import BasePredictor, Input, Path

# 确保字体目录存在
FONTS_DIR = "fonts"
if not os.path.exists(FONTS_DIR):
    os.makedirs(FONTS_DIR)

# 复制字体文件到系统字体目录
def install_fonts():
    system_font_dir = "/usr/share/fonts/truetype/custom"
    if not os.path.exists(system_font_dir):
        subprocess.run(['sudo', 'mkdir', '-p', system_font_dir])
    
    # 复制字体文件
    font_files = [
        (FONT_PATH, "HelveticaNeue-MediumCond.otf"),
        (TRANS_FONT_PATH, "MiSans-Medium.ttf")
    ]
    
    for src, filename in font_files:
        dest = os.path.join(system_font_dir, filename)
        if not os.path.exists(dest):
            subprocess.run(['sudo', 'cp', src, dest])
            subprocess.run(['sudo', 'chmod', '644', dest])
    
    # 更新字体缓存
    subprocess.run(['sudo', 'fc-cache', '-f', '-v'])

# 字幕样式常量
SRC_FONT_SIZE = 18  # 源语言字幕字体大小
TRANS_FONT_SIZE = 22  # 翻译字幕字体大小
SRC_FONT_COLOR = '&HFFFFFF'  # 源语言字幕字体颜色（白色）
SRC_OUTLINE_COLOR = '&H000000'  # 源语言字幕轮廓颜色（黑色）
SRC_OUTLINE_WIDTH = 1  # 源语言字幕轮廓宽度
TRANS_FONT_COLOR = '&HFFFFFF'
TRANS_OUTLINE_COLOR = '&H000000'  # 翻译字幕轮廓颜色（黑色）
TRANS_OUTLINE_WIDTH = 1  # 翻译字幕轮廓宽度

SRC_MARGIN_V = 20 # 源语言字幕距离底部边距
TRANS_MARGIN_V = 38 # 翻译字幕距离底部边距
TRANS_SPACING = 1 # 翻译字幕字间距
TRANS_BG_COLOR = '&H40000000'  # 翻译字幕背景颜色（25%透明黑色）

FONT_PATH = "fonts/HelveticaNeue-MediumCond.otf"
TRANS_FONT_PATH = "fonts/MiSans-Medium.ttf"

FONT_NAME = 'HelveticaNeue-MediumCond'
TRANS_FONT_NAME = 'MiSans Medium'

class Predictor(BasePredictor):
    def setup(self):
        """初始化设置"""
        install_fonts()
        
        # 验证字体安装
        print("检查字体安装情况...")
        print("MiSans Medium字体:")
        subprocess.run(['fc-list', '|', 'grep', '-i', 'MiSans'], shell=True)
        print("\nHelveticaNeue-MediumCond字体:")  
        subprocess.run(['fc-list', '|', 'grep', '-i', 'HelveticaNeue'], shell=True)

    def predict(
        self,
        video_url: str = Input(description="视频URL链接"),
        source_srt_url: str = Input(description="原文字幕URL链接(srt格式)"),
        translated_srt_url: str = Input(description="翻译字幕URL链接(srt格式)"),
        target_height: int = Input(description="输出视频高度", default=480),
    ) -> dict:
        # 下载视频
        print("📥 Downloading video...")
        video_data = requests.get(video_url)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_video:
            temp_video.write(video_data.content)
            video_file = temp_video.name

        # 下载字幕文件
        print("📥 Downloading subtitles...")
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as temp_source_srt:
            source_srt_data = requests.get(source_srt_url)
            temp_source_srt.write(source_srt_data.content)
            source_srt_file = temp_source_srt.name

        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as temp_translated_srt:
            translated_srt_data = requests.get(translated_srt_url)
            temp_translated_srt.write(translated_srt_data.content)
            translated_srt_file = temp_translated_srt.name

        output_files = {}
        
        start_time = time.time()
        # 使用临时文件处理视频
        with tempfile.NamedTemporaryFile(suffix=".mp4") as temp_output:
            # 使用NVIDIA GPU编码
            ffmpeg_cmd = [
                'ffmpeg', '-i', video_file,
                '-vf', (
                    f"scale=-2:{target_height},"
                    f"subtitles={source_srt_file}:fontsdir=fonts:force_style='FontSize={SRC_FONT_SIZE},FontName={FONT_NAME},"
                    f"PrimaryColour={SRC_FONT_COLOR},OutlineColour={SRC_OUTLINE_COLOR},OutlineWidth={SRC_OUTLINE_WIDTH},"
                    f"MarginV={SRC_MARGIN_V},BorderStyle=1',"
                    f"subtitles={translated_srt_file}:fontsdir=fonts:force_style='FontSize={TRANS_FONT_SIZE},FontName={TRANS_FONT_NAME},"
                    f"PrimaryColour={TRANS_FONT_COLOR},OutlineColour={TRANS_OUTLINE_COLOR},OutlineWidth={TRANS_OUTLINE_WIDTH},"
                    f"MarginV={TRANS_MARGIN_V},BorderStyle=4,BackColour={TRANS_BG_COLOR},Spacing={TRANS_SPACING}'"
                ).encode('utf-8'),
                '-c:v', 'h264_nvenc',
                '-preset', 'p4',
                '-rc:v', 'vbr',
                '-cq:v', '36',
                '-y',
                temp_output.name
            ]

            
            print("🚀 使用NVIDIA GPU处理中...")
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding='utf-8'
            )
            
            # 读取并显示进度
            while True:
                stderr_line = process.stderr.readline()
                if not stderr_line and process.poll() is not None:
                    break
                
                if stderr_line:
                    print(f"\r进度: {stderr_line.strip()}", end='', flush=True)
            
            # 等待处理完成
            process.wait()
            print(f"✨ Video processing completed in {time.time() - start_time:.2f} seconds")

            # 将处理后的视频读入BytesIO对象
            output_files["video"] = BytesIO(open(temp_output.name, "rb").read())
            
        # 删除临时文件
        os.remove(video_file)
        os.remove(source_srt_file)
        os.remove(translated_srt_file)

        return output_files
