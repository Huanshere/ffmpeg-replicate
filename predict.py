import tempfile
import subprocess
import time
import requests
from io import BytesIO
from cog import BasePredictor, Input, Path

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

# FONT_NAME = 'Arial'
# TRANS_FONT_NAME = 'Arial'

FONT_PATH = "fonts/HelveticaNeue-MediumCond.otf"
TRANS_FONT_PATH = "fonts/MiSans-Medium.ttf"

class Predictor(BasePredictor):
    def setup(self):
        """初始化设置"""
        # 确保字体文件存在
        if not Path(FONT_PATH).exists() or not Path(TRANS_FONT_PATH).exists():
            raise RuntimeError("Required font files not found")
        pass

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
                    f"subtitles={source_srt_file}:force_style='FontSize={SRC_FONT_SIZE},FontName={FONT_PATH},"
                    f"PrimaryColour={SRC_FONT_COLOR},OutlineColour={SRC_OUTLINE_COLOR},OutlineWidth={SRC_OUTLINE_WIDTH},"
                    f"MarginV={SRC_MARGIN_V},BorderStyle=1',"
                    f"subtitles={translated_srt_file}:force_style='FontSize={TRANS_FONT_SIZE},FontName={TRANS_FONT_PATH},"
                    f"PrimaryColour={TRANS_FONT_COLOR},OutlineColour={TRANS_OUTLINE_COLOR},OutlineWidth={TRANS_OUTLINE_WIDTH},"
                    f"MarginV={TRANS_MARGIN_V},BorderStyle=4,BackColour={TRANS_BG_COLOR},Spacing={TRANS_SPACING}'"
                ).encode('utf-8'),
                '-c:v', 'h264_nvenc',
                '-preset', 'p4',
                '-rc:v', 'vbr',
                '-b:v', '1M',        # 添加目标比特率限制
                '-maxrate', '2M',    # 最大比特率
                '-bufsize', '2M',    # 缓冲区大小
                '-cq:v', '28',       # 提高 CQ 值（原来是24，越大压缩率越高，画质略降）
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
                    # 查找包含时间信息的行
                    if "time=" in stderr_line:
                        print(f"\r进度: {stderr_line.strip()}", end='', flush=True)
            
            # 等待处理完成
            process.wait()
            print(f"✨ Video processing completed in {time.time() - start_time:.2f} seconds")

            # 将处理后的视频读入BytesIO对象
            output_files["video"] = BytesIO(open(temp_output.name, "rb").read())

        return output_files
