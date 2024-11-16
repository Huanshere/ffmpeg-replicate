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
        os.makedirs(system_font_dir)
    
    # 复制字体文件
    font_files = [
        (FONT_PATH, "HelveticaNeue-MediumCond.otf"),
        (TRANS_FONT_PATH, "MiSans-Medium.ttf")
    ]
    
    for src, filename in font_files:
        dest = os.path.join(system_font_dir, filename)
        if not os.path.exists(dest):
            subprocess.run(['cp', src, dest])
            os.chmod(dest, 0o644)
    
    # 更新字体缓存
    subprocess.run(['fc-cache', '-f', '-v'])

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
        # print("检查字体安装情况...")
        # print("MiSans Medium字体:")
        # subprocess.run(['fc-list', '|', 'grep', '-i', 'MiSans'], shell=True)
        # print("\nHelveticaNeue-MediumCond字体:")  
        # subprocess.run(['fc-list', '|', 'grep', '-i', 'HelveticaNeue'], shell=True)

    def predict(
        self,
        video_url: str = Input(description="视频URL链接"),
        source_srt_url: str = Input(description="原文字幕URL链接(srt格式)", default=None),
        translated_srt_url: str = Input(description="翻译字幕URL链接(srt格式)"),
        target_height: int = Input(description="输出视频高度", default=480),
        watermark: bool = Input(description="是否添加水印", default=False),
        cqv: int = Input(description="视频质量 0~51 越高压缩越厉害", default=32),
        dub_audio_url: str = Input(description="配音音频URL链接(mp3格式)", default=None),
        bgm_audio_url: str = Input(description="背景音乐音频URL链接(mp3格式)", default=None),
        dub_volumn: float = Input(description="配音音量增益", default=1.5),
        mode: str = Input(description="模式, sub or dub", default="sub")
    ) -> dict:
        # 下载视频
        print("📥 Downloading video...")
        video_data = requests.get(video_url)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_video:
            temp_video.write(video_data.content)
            video_file = temp_video.name

        # 下载字幕文件
        print("📥 Downloading translated subtitles...")
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as temp_translated_srt:
            translated_srt_data = requests.get(translated_srt_url)
            temp_translated_srt.write(translated_srt_data.content)
            translated_srt_file = temp_translated_srt.name
        
        
        if mode == "sub":
            print("📥 Downloading source subtitles...")
            with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as temp_source_srt:
                source_srt_data = requests.get(source_srt_url)
                temp_source_srt.write(source_srt_data.content)
                source_srt_file = temp_source_srt.name

        if mode == "dub":
            print("📥 Downloading dub audio...")
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_dub_audio:
                dub_audio_data = requests.get(dub_audio_url)
                temp_dub_audio.write(dub_audio_data.content)
                dub_audio_file = temp_dub_audio.name
            print("📥 Downloading bgm audio...")
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_bgm_audio:
                bgm_audio_data = requests.get(bgm_audio_url)
                temp_bgm_audio.write(bgm_audio_data.content)
                bgm_audio_file = temp_bgm_audio.name

        

        output_files = {}
        print("🚀 开始处理视频...")
        start_time = time.time()
        # 使用临时文件处理视频
        # for mode == sub
        with tempfile.NamedTemporaryFile(suffix=".mp4") as temp_output:
            if mode == "sub":
                # 构建基础的字幕滤镜命令
                subtitle_filter = (
                    f"scale=-2:{target_height},"
                    f"subtitles={source_srt_file}:fontsdir=fonts:force_style='FontSize={SRC_FONT_SIZE},FontName={FONT_NAME},"
                    f"PrimaryColour={SRC_FONT_COLOR},OutlineColour={SRC_OUTLINE_COLOR},OutlineWidth={SRC_OUTLINE_WIDTH},"
                    f"MarginV={SRC_MARGIN_V},BorderStyle=1',"
                    f"subtitles={translated_srt_file}:fontsdir=fonts:force_style='FontSize={TRANS_FONT_SIZE},FontName={TRANS_FONT_NAME},"
                    f"PrimaryColour={TRANS_FONT_COLOR},OutlineColour={TRANS_OUTLINE_COLOR},OutlineWidth={TRANS_OUTLINE_WIDTH},"
                    f"MarginV={TRANS_MARGIN_V},BorderStyle=4,BackColour={TRANS_BG_COLOR},Spacing={TRANS_SPACING}'"
                )

                # 基础命令列表
                ffmpeg_cmd = ['ffmpeg', '-i', video_file]

                if watermark:
                    # 添加水印配置
                    filter_complex = (
                        f"[0:v]{subtitle_filter}[v1];"
                        f"[v1]drawtext=text='Made by VideoLingo':fontcolor=white:fontsize=20:"
                        f"x=w-tw-10:y=20:bordercolor=black:borderw=1.5:alpha='if(lt(t,3),0,0.5)'[outv]"
                    ).encode('utf-8')
                    ffmpeg_cmd.extend(['-filter_complex', filter_complex, '-map', '[outv]', '-map', '0:a'])
                else:
                    ffmpeg_cmd.extend(['-vf', subtitle_filter.encode('utf-8')])

                # 添加通用的编码配置
                ffmpeg_cmd.extend([
                    '-c:v', 'h264_nvenc',
                    '-preset', 'p4',
                    '-rc:v', 'vbr',
                    '-cq:v', str(cqv),
                    '-y',
                    temp_output.name
                ])
            if mode == "dub":
                    # 构建配音模式的字幕滤镜
                subtitle_filter = (
                    f"scale=-2:{target_height},"
                    f"subtitles={translated_srt_file}:fontsdir=fonts:force_style='FontSize={TRANS_FONT_SIZE},"
                    f"FontName={TRANS_FONT_NAME},PrimaryColour={TRANS_FONT_COLOR},"
                    f"OutlineColour={TRANS_OUTLINE_COLOR},OutlineWidth={TRANS_OUTLINE_WIDTH},"
                    f"MarginV={TRANS_MARGIN_V},BorderStyle=4,BackColour={TRANS_BG_COLOR},Spacing={TRANS_SPACING}'"
                )

                # 构建音频混合和视频处理的复杂滤镜
                filter_complex = (
                    f"[0:v]{subtitle_filter}[v1];"
                    f"[1:a]volume=1[a1];[2:a]volume={dub_volumn}[a2];"
                    f"[a1][a2]amix=inputs=2:duration=first:dropout_transition=3[a]"
                )

                if watermark:
                    filter_complex = (
                        f"[0:v]{subtitle_filter}[vtmp];"
                        f"[vtmp]drawtext=text='Made by VideoLingo':fontcolor=white:fontsize=20:"
                        f"x=w-tw-10:y=20:bordercolor=black:borderw=1.5:alpha='if(lt(t,3),0,0.5)'[v1];"
                        f"[1:a]volume=1[a1];[2:a]volume={dub_volumn}[a2];"
                        f"[a1][a2]amix=inputs=2:duration=first:dropout_transition=3[a]"
                    )

                ffmpeg_cmd = [
                    'ffmpeg', '-i', video_file,
                    '-i', temp_bgm_audio.name,
                    '-i', temp_dub_audio.name,
                    '-filter_complex', filter_complex.encode('utf-8'),
                    '-map', '[v1]', '-map', '[a]',
                    '-c:v', 'h264_nvenc',
                    '-preset', 'p4',
                    '-rc:v', 'vbr',
                    '-cq:v', str(cqv),
                    '-c:a', 'aac',
                    '-b:a', '192k',
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
        
        # 清理临时文件
        os.remove(video_file)
        os.remove(translated_srt_file)
        if mode == "sub":
            os.remove(source_srt_file)
        elif mode == "dub":
            os.remove(temp_dub_audio.name)
            os.remove(temp_bgm_audio.name)

        return output_files
