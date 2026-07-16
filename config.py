import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Base directory paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
PROJECTS_DIR = os.path.join(OUTPUT_DIR, "projects")
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Subdirectories for assets inside a project
SUBDIRS = ["scripts", "storyboards", "audio_tts", "audio_sfx", "audio_bgm", "videos", "temp"]

# Ensure directories exist
for path in [OUTPUT_DIR, PROJECTS_DIR, STATIC_DIR, TEMPLATES_DIR]:
    os.makedirs(path, exist_ok=True)

# GEMINI API Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Gemini Model Selection (Defaults to gemini-3.5-flash as the latest frontier-class flash model)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

# Latest Specialized Gemini/Google GenAI Models for Media Tasks (2026 Stable Lineup)
GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")       # Image Generation (Nano Banana 2)
GEMINI_VIDEO_MODEL = os.environ.get("GEMINI_VIDEO_MODEL", "veo-3.1-generate-001")          # Video Generation (Veo 3.1)
GEMINI_AUDIO_MODEL = os.environ.get("GEMINI_AUDIO_MODEL", "gemini-3.1-flash-tts-preview")  # Audio & Speech (Flash TTS)

# Standard Cinematic Preset Categories
GENRES = [
    {"id": "action", "name": "느와르/액션 (Noir & Action)"},
    {"id": "thriller", "name": "미스터리/스릴러 (Mystery & Thriller)"},
    {"id": "sf", "name": "SF/판타지 (Sci-Fi & Fantasy)"},
    {"id": "drama", "name": "휴먼 드라마 (Human Drama)"},
    {"id": "horror", "name": "호러/공포 (Horror)"}
]

CAMERA_ANGLES = ["Wide", "Closeup", "Overshoulder", "Topview", "POV"]

# Default Sound FX definitions (Mapped to mathematical synthesizers)
DEFAULT_SFX = {
    "rain_ambient": "빗소리 (Rain Ambient) - 촉촉한 배경음",
    "door_open": "문 열리는 소리 (Door Creak/Open) - 삐걱이는 문소리",
    "sword_clash": "칼 부딪히는 소리 (Sword Clash) - 챙그랑 금속음",
    "footsteps": "발자국 소리 (Footsteps) - 터벅터벅 묵직한 소리",
    "thunder": "천둥 소리 (Thunder Rumble) - 콰릉 우르릉",
    "siren": "사이렌 소리 (Siren Warning) - 긴박한 경보음"
}

# Default BGM definitions (Synthesized with chord progression loops)
DEFAULT_BGM = {
    "suspense": "긴장감 넘치는 다크 앰비언트 (Suspenseful Dark Ambient)",
    "action": "긴박하고 빠른 테크노/아날로그 신스 (Fast Action Chase Synth)",
    "sad": "쓸쓸하고 고독한 피아노 선율 (Melancholic Solitary Piano)",
    "epic": "웅장하고 비장한 오케스트라 패드 (Grand Epic Orchestral Pad)"
}

def get_project_paths(project_id: str):
    """
    Returns an absolute path mapping for a specific project
    """
    proj_root = os.path.join(PROJECTS_DIR, project_id)
    paths = {"root": proj_root}
    for sub in SUBDIRS:
        subdir_path = os.path.join(proj_root, sub)
        os.makedirs(subdir_path, exist_ok=True)
        paths[sub] = subdir_path
    return paths
