import os
import json
import random
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_IMAGE_MODEL, GEMINI_VIDEO_MODEL, GEMINI_AUDIO_MODEL, CAMERA_ANGLES, DEFAULT_SFX, DEFAULT_BGM, GENRES

# Try to import Google GenAI and Agent Development Kit (ADK) SDKs
HAS_GEMINI = False
try:
    from google import genai
    from google.genai import types
    from google.adk.agents import LlmAgent
    from google.adk.models.google_llm import Gemini
    from google.adk.runners import InMemoryRunner
    if GEMINI_API_KEY:
        HAS_GEMINI = True
except ImportError:
    pass

# =====================================================================
# Pydantic Schemas for Structured JSON Output
# =====================================================================

class Character(BaseModel):
    name: str = Field(description="등장인물 이름")
    role: str = Field(description="역할 (예: 주인공, 조력자, 대적자)")
    personality: str = Field(description="성격 및 핵심 대인관계 특성")
    appearance: str = Field(description="외모 묘사 (스토리보드 이미지 생성용 상세 묘사)")

class Episode(BaseModel):
    episode_no: int = Field(description="에피소드 번호 (1-5)")
    title: str = Field(description="에피소드 제목")
    logline: str = Field(description="에피소드 핵심 시놉시스/로그라인")

class StoryOutput(BaseModel):
    title: str = Field(description="드라마 시리즈의 전체 제목")
    synopsis: str = Field(description="스토리 에이전트가 가다듬은 전체 시놉시스")
    characters: List[Character] = Field(description="핵심 등장인물 프로필 리스트 (3-4명)")
    episodes: List[Episode] = Field(description="5부작 에피소드 아웃라인 리스트")
    twists: List[str] = Field(description="전체 시나리오에 적용될 반전 요소들")
    foreshadowing: List[str] = Field(description="복선 및 단서 배치 기획")

class Scene(BaseModel):
    scene_no: int = Field(description="씬 번호")
    location: str = Field(description="장소 (예: 실내-지하철, 야외-빗속의 골목길 등)")
    time: str = Field(description="시간대 (낮, 밤, 노을, 새벽 등)")
    storyline: str = Field(description="씬에서 일어나는 짧은 이야기 전개")
    narration: str = Field(description="지문 및 독백/나레이션, 캐릭터 대사")
    visual_description: str = Field(description="씬의 구체적인 비주얼 상황 묘사")

class SceneOutput(BaseModel):
    episode_no: int
    scenes: List[Scene] = Field(description="시간/장소 단위로 씬 분할")

class DirectorScene(BaseModel):
    scene_no: int
    directorial_style: str = Field(description="씬별 연출 방식 (예: '칼싸움 장면의 역동성을 극대화하기 위해 롱테이크 카메라 워크 적용', '감정 고조를 위한 슬로우모션')")
    mood: str = Field(description="장면의 핵심 분위기 (suspense, action, sad, epic, horror 등)")
    pacing: str = Field(description="템포 (fast, normal, slow)")
    color_palette: str = Field(description="시각적 톤앤매너 색감 (예: '차가운 블루 & 그림자', '화려한 네온 그린 & 퍼플')")

class DirectorOutput(BaseModel):
    scenes: List[DirectorScene] = Field(description="씬별 연출 정보 기획 리스트")

class Shot(BaseModel):
    shot_id: str = Field(description="샷 고유 ID (예: E1-S1-C1)")
    scene_no: int
    camera_angle: str = Field(description="카메라 구도 (Wide, Closeup, Overshoulder, Topview, POV 중 택1)")
    composition: str = Field(description="샷 구도/조성 상세 묘사")
    visual_prompt: str = Field(description="생성 AI 전달용 고품질 이미지 프롬프트 (스토리 인물묘사, 배경 및 연출 색감 혼합)")
    estimated_duration: float = Field(description="예상 지속 시간 (초 단위, 대개 3.0 ~ 7.0초)")

class CinematographyOutput(BaseModel):
    shots: List[Shot] = Field(description="각 씬을 컷(Shot) 단위로 쪼갠 전체 리스트")

class MusicCue(BaseModel):
    shot_id: str
    bgm_style: str = Field(description="BGM 스타일 (suspense, action, sad, epic, none 중 택1. 불필요한 곳에는 none을 지정)")
    volume: float = Field(description="배경음 볼륨 레벨 (0.0 ~ 1.0, none일 경우 0.0)")

class SFXCue(BaseModel):
    shot_id: str
    sfx_type: str = Field(description="효과음 종류 (rain_ambient, door_open, sword_clash, footsteps, thunder, siren, none 중 택1)")
    volume: float = Field(description="효과음 볼륨 레벨 (0.0 ~ 1.0)")
    timing_offset: float = Field(description="해당 샷의 시작점으로부터 몇 초 뒤에 효과음이 실행될지 오프셋 (초 단위, 해당 샷 재생길이 이내)")

class SoundOutput(BaseModel):
    music_tracks: List[MusicCue] = Field(description="샷별 배경음악 강약/무음 배치 계획")
    sfx_effects: List[SFXCue] = Field(description="샷별 효과음 사운드 이벤트 매핑 리스트")

# All residual simulation/fallback code has been completely pruned.
# Only Live GeminiAgents are maintained below.

# =====================================================================
# LIVE AGENTS WITH GOOGLE GEMINI (using structured outputs)
# =====================================================================

class GeminiAgents:
    def __init__(self):
        pass
        
    def _run_adk_agent(self, agent_name: str, instruction: str, prompt: str, output_schema) -> str:
        """Helper to invoke a structured LlmAgent via google-adk (Agent Development Kit)."""
        # 1. Instantiate the Gemini LLM binding via ADK
        llm = Gemini(
            model=GEMINI_MODEL,
            client_kwargs={'api_key': GEMINI_API_KEY}
        )
        
        # 2. Build the ADK LlmAgent with enforced output schema
        agent = LlmAgent(
            name=agent_name,
            model=llm,
            instruction=instruction,
            output_schema=output_schema
        )
        
        # 3. Create the lightweight InMemoryRunner and enable automatic session creation
        runner = InMemoryRunner(agent=agent, app_name='cinema_app')
        runner.auto_create_session = True
        
        # 4. Wrap prompt into ADK-compliant types.Content
        content = types.Content(parts=[types.Part.from_text(text=prompt)])
        
        # 5. Run and block synchronously to extract final response events
        events = runner.run(
            user_id='director_user', 
            session_id=f'session_{agent_name}', 
            new_message=content
        )
        
        # 6. Accumulate and return the final response text
        final_text = ""
        for ev in events:
            if hasattr(ev, 'text') and ev.text:
                final_text = ev.text
            elif hasattr(ev, 'content') and ev.content:
                content_obj = ev.content
                if hasattr(content_obj, 'parts') and content_obj.parts:
                    text_parts = [part.text for part in content_obj.parts if hasattr(part, 'text') and part.text]
                    if text_parts:
                        final_text = "".join(text_parts)
                elif hasattr(content_obj, 'text') and content_obj.text:
                    final_text = content_obj.text
                    
        return final_text

    def generate_story(self, synopsis: str, genre_id: str) -> StoryOutput:
        if not HAS_GEMINI:
            raise RuntimeError("구글 Gemini API 키 혹은 필수 라이브러리(google-genai, google-adk)가 감지되지 않았습니다. 가상환경의 환경변수(GEMINI_API_KEY) 설정을 점검해 주세요.")
            
        genre_name = next((g["name"] for g in GENRES if g["id"] == genre_id), genre_id)
        instruction = """
        너는 5부작 시리즈 드라마의 전체적인 시놉시스와 캐릭터 아크, 그리고 복선 및 장기 아크 구조를 짜는 'Story Agent'다.
        [★체스판 세계관 강제 고정 룰★]: 사용자의 시놉시스에 체스(Chess), 폰(Pawn), 퀸(Queen), 기물, 체스판 등이 언급된다면, 이를 가상의 중세 인간 왕국이나 인간 전쟁물 등 메타포적인 이야기로 의인화/치환하여 각색하는 것을 절대 금지한다. 무조건 '실제 가로세로 64칸 흑백 격자무늬 체스판 위'에 올려진 실제 피규어 형태의 기물들(Pawn, Knight, Bishop, Rook, Queen, King)이 격자 칸을 가로지르며 살아서 기동하고 부딪혀 부서지고 아군을 위해 기꺼이 희생해 끝내 퀸으로 승급(Promotion)하는 '진짜 체스판 미니어처 드라마' 세계관으로 무조건 박박 박아 고정해서 등장인물 명칭과 아크를 기획해야 한다.
        """
        prompt = f"""
        사용자 시놉시스: '{synopsis}'
        선택 장르: {genre_name}
        
        위 시놉시스와 장르 정보를 기반으로 한 5부작 미니 드라마의 전체적인 뼈대를 잡는 'Story Agent' 역할을 수행해라.
        다음 요구사항을 충족하여 스키마 포맷에 부합하는 완벽한 드라마 기획서를 작성하라:
        1. 시리즈 전체의 웅장하고 몰입력 있는 제목을 작명할 것.
        2. 등장인물(characters)은 주연, 대역자, 조력을 포함한 최소 3명 이상을 기획하고 특히 스토리보드 이미지 프롬프트 작성에 용이하도록 '외모 묘사(appearance)'를 아주 구체적이고 일관된 특징(머리색, 패션, 눈매 등) 위주로 작성할 것.
        3. 전체 5부작(Episodes)의 각 화별 쫄깃한 소제목과 매력적인 한 줄 로그라인을 작성할 것.
        4. 전체 드라마를 관통할 메인 '반전 요소(twists)' 2개 이상 및 1~2화에서 뿌리고 4~5화에서 수거할 구체적인 '복선 설계(foreshadowing)' 2개 이상을 작성할 것.
        
        출력은 반드시 주어진 JSON 스키마 규격을 충족해야 한다.
        """
        try:
            response_text = self._run_adk_agent(
                agent_name="story_agent",
                instruction=instruction,
                prompt=prompt,
                output_schema=StoryOutput
            )
            return StoryOutput.model_validate_json(response_text)
        except Exception as e:
            raise RuntimeError(f"Gemini Story Agent 기획 수립 중 오류가 발생했습니다: {str(e)}")

    def generate_scenes(self, episode_no: int, story: StoryOutput, genre_id: str) -> SceneOutput:
        if not HAS_GEMINI:
            raise RuntimeError("구글 Gemini API 키 혹은 필수 라이브러리(google-genai, google-adk)가 감지되지 않았습니다. 가상환경의 환경변수(GEMINI_API_KEY) 설정을 점검해 주세요.")
            
        story_json = story.model_dump_json(indent=2)
        instruction = """
        너는 드라마 시리즈의 개별 에피소드 아웃라인을 시간 및 장소 단위의 구체적인 '씬(Scene) 대본'으로 분할하는 전문 'Scene Agent'다.
        [★체스판 대본 및 행동 룰★]: 기획에 체스 요소가 관여되어 있다면, 대사(narration)와 연출(visual_description) 전반에서 인간들의 이야기가 아닌 '체스판 위 기물들의 생존극'을 철저히 다뤄라. 예를 들어 장소는 '어두운 격자판의 e4 칸', '나이트가 도사리는 f5 격자 전선' 등 체스판 격자 좌표 위가 배경이어야 하며, 기물들의 대사나 나레이션은 "나는 킹의 보위를 위해 이곳 C3에서 생을 다한다" 혹은 "우리는 고작 나무 기물일 뿐이지만, 한 칸씩 묵묵히 나아가 퀸이 될 것이다"와 같이 체스 고유의 규칙과 희생을 절절하게 표현해야 한다. 시각 묘사(visual_description) 또한 거대한 손가락이 위에서 기물을 내려놓거나, 체스판 격자선이 가로막힌 전경을 미니어처 구도로 신비롭게 직조하라.
        """
        prompt = f"""
        기획 정보: {story_json}
        현재 타겟 에피소드: {episode_no}화
        장르: {genre_id}
        
        기획 정보를 완벽하게 흡수하여 {episode_no}화 에피소드를 시간 및 장소 단위의 씬(Scene)으로 분할하는 'Scene Agent' 역할을 수행하라.
        요구사항:
        1. 1개 에피소드 당 정확히 3개의 개별 씬(scene)으로 분리할 것 (컴팩트하고 세련된 편집을 위함).
        2. 인물 기획의 이름, 성격, 행동지문을 기반으로 씬을 구성할 것.
        3. 'storyline'은 장면 내부 갈등을 상세히 묘사하고, 'narration'에는 대사(Dialogue) 또는 극적인 나레이션을 한국어로 풍부하게 작성할 것.
        4. 'visual_description'은 카메라 프레임에 잡힐 시각적 상황(배경, 기후, 조명, 인물 행동 등)을 아주 섬세하고 디테일하게 영어나 한국어로 묘사하여 이미지 생성이 수월하게 도울 것.
        
        출력은 반드시 JSON 규격 스키마를 따를 것.
        """
        try:
            response_text = self._run_adk_agent(
                agent_name="scene_agent",
                instruction=instruction,
                prompt=prompt,
                output_schema=SceneOutput
            )
            return SceneOutput.model_validate_json(response_text)
        except Exception as e:
            raise RuntimeError(f"Gemini Scene Agent 극본 대사 집필 중 오류가 발생했습니다: {str(e)}")

    def generate_director(self, scenes: List[Scene], genre_id: str) -> DirectorOutput:
        if not HAS_GEMINI:
            raise RuntimeError("구글 Gemini API 키 혹은 필수 라이브러리(google-genai, google-adk)가 감지되지 않았습니다. 가상환경의 환경변수(GEMINI_API_KEY) 설정을 점검해 주세요.")
            
        scenes_list = [sc.model_dump() for sc in scenes]
        scenes_json = json.dumps(scenes_list, ensure_ascii=False, indent=2)
        instruction = """
        너는 분할된 대본 극본을 입체적인 시네마 가이드로 전환하고 미장센을 지정하는 총괄 'Director Agent(영화감독)' 역할을 수행한다.
        각 장면의 긴장 속도, 정서 톤, 그리고 독창적인 조명 스타일을 완벽하게 지정해야 한다.
        """
        prompt = f"""
        분할된 씬 정보: {scenes_json}
        장르: {genre_id}
        
        위 씬들을 바탕으로 각 씬의 예술적 연출 방식과 톤앤매너를 결정하는 'Director Agent(영화감독)' 역할을 수행하라.
        요구사항:
        1. 'directorial_style'은 연출 방식에 대한 디렉팅 지시서다. 예를 들어 싸움씬인 경우 "긴장감을 극대화하기 위해 원테이크/롱테이크 카메라 컷 설계" 혹은 긴장 상황에서 "인물의 정서적 몰입을 위한 타이트한 핸드헬드 기법 및 슬로우 모션 활용" 등 시네마틱한 고품격 연출 지시를 구체적으로 작성해라.
        2. 'mood'는 장면의 감정적 무드로 suspense, action, sad, epic, horror 중 반드시 하나를 선택해라.
        3. 'pacing'은 씬의 스피드로 fast, normal, slow 중 하나를 지정해라.
        4. 'color_palette'는 조명 및 색조 보정 가이드라인이다. 예: "차가운 강철빛 스틸 블루 & 밤 그림자", "공포를 극대화하는 자색 마젠타 & 음울한 녹색광" 등으로 구체적으로 작명하라.
        
        출력은 반드시 JSON 스키마 규격을 충족해야 한다.
        """
        try:
            response_text = self._run_adk_agent(
                agent_name="director_agent",
                instruction=instruction,
                prompt=prompt,
                output_schema=DirectorOutput
            )
            return DirectorOutput.model_validate_json(response_text)
        except Exception as e:
            raise RuntimeError(f"Gemini Director Agent 연출서 설계 중 오류가 발생했습니다: {str(e)}")

    def generate_cinematography(self, episode_no: int, scenes: List[Scene], director: DirectorOutput, user_pov: str = "") -> CinematographyOutput:
        if not HAS_GEMINI:
            raise RuntimeError("구글 Gemini API 키 혹은 필수 라이브러리(google-genai, google-adk)가 감지되지 않았습니다. 가상환경의 환경변수(GEMINI_API_KEY) 설정을 점검해 주세요.")
            
        scenes_json = json.dumps([sc.model_dump() for sc in scenes], ensure_ascii=False)
        dir_json = director.model_dump_json()
        instruction = """
        너는 대본과 감독의 연출서를 바탕으로 카메라 구도를 잡고, 3D 스토리보드 이미지 생성용 상세 영문 프롬프트를 빌드하는 'Cinematography Agent(촬영감독)'다.
        [★체스판 3D 미니어처 촬영 룰★]: 만약 체스 기물 시놉시스가 바탕이라면, 영문 이미지 생성 프롬프트(visual_prompt) 빌드 시 절대로 '인간(Human)이나 판타지 기사 캐릭터'를 묘사하지 마라. 무조건 실제 체스판 위 기물의 모습을 묘사할 것! 예: "Professional cinematic macro photograph of a single polished wooden pawn piece standing alone on a black and white checkered wooden chessboard, dramatic side lighting, shallow depth of field, tilt-shift lens, toy miniature scale, 8k resolution, photorealistic" 혹은 "An elegant white marble queen chess piece facing off against a dark obsidian knight piece, dust particles in the sunbeam, highly detailed wooden textures of the chessboard squares, tension, 35mm lens."와 같이 물리적으로 체판 격자 위에서 사투를 벌이는 사물의 정교함과 매크로 렌즈 미장센을 극대화해 프롬프트를 조달하라.
        """
        prompt = f"""
        씬 리스트: {scenes_json}
        감독 연출서: {dir_json}
        현재 에피소드 번호: {episode_no}
        
        감독의 연출서와 각 씬의 대본을 기반으로 씬별 샷(Cut)을 분할하고 카메라 구도와 이미지 생성을 위한 고해상도 프롬프트를 매핑하는 'Cinematography Agent(촬영감독)' 역할을 수행하라.
        요구사항:
        1. 하나의 Scene 당 정확히 3개의 Shot(컷)으로 세분화할 것.
        2. 'camera_angle'은 반드시 다음 중 가장 알맞은 구도를 하나 골라 매핑할 것: {CAMERA_ANGLES} (Wide로 전경을 보여주고, Closeup으로 표정을 조명하며, Overshoulder로 인물 간 갈등 대면 구도를 연출하고, Topview로 상황 전체를 내려다봄).
        3. 'composition'에는 해당 구도를 활용하는 이유와 카메라 움직임(틸트 업, 트랙 아웃 등)을 디테일하게 서술할 것.
        4. 'visual_prompt'는 구글의 최신 고품질 이미지 생성 모델 {GEMINI_IMAGE_MODEL} (Nano Banana 2)에 입력할 최상급 영문 프롬프트다. 인물의 외모 특징, 씬의 시각적 배경, 감독이 명시한 조명/색조(color_palette), 무드 및 카메라 구도 지문이 모두 정밀하게 병합되어 사진과 구분이 가지 않을 정교한 시네마 샷 프롬프트로 작성할 것 (Professional cinematic screengrab, 8k resolution, 35mm lens, photorealistic, 등으로 시작).
        5. 'estimated_duration'은 컷의 적절한 재생 시간(대개 3.0 ~ 6.0초 사이)을 소수점으로 산정하라.
        """
        
        if user_pov:
            prompt += f"\n\n[★ 감독 연출 시선/POV 지시 ★]\n- 사용자가 명시한 다음 촬영 지침을 카메라 구도(camera_angle) 선택과 영문 이미지 프롬프트(visual_prompt) 빌드 시 최우선적으로 강제 반영하라: '{user_pov}'"
            
        prompt += "\n\n출력은 반드시 JSON 규격 스키마를 만족해야 한다."
        
        try:
            response_text = self._run_adk_agent(
                agent_name="cinematography_agent",
                instruction=instruction,
                prompt=prompt,
                output_schema=CinematographyOutput
            )
            return CinematographyOutput.model_validate_json(response_text)
        except Exception as e:
            raise RuntimeError(f"Gemini Cinematography Agent 촬영 가이드 및 샷 분할 중 오류가 발생했습니다: {str(e)}")

    def generate_sound(self, shots: List[Shot], genre_id: str) -> SoundOutput:
        if not HAS_GEMINI:
            raise RuntimeError("구글 Gemini API 키 혹은 필수 라이브러리(google-genai, google-adk)가 감지되지 않았습니다. 가상환경의 환경변수(GEMINI_API_KEY) 설정을 점검해 주세요.")
            
        shots_json = json.dumps([sh.model_dump() for sh in shots], ensure_ascii=False)
        instruction = """
        너는 에피소드 비주얼 타임라인을 파악하여 영화적 몰입감을 배가시키는 선택적 BGM 및 초 단위 폴리 효과음(SFX) 오프셋을 설계하는 'Sound Agent(음향감독)'다.
        사운드의 시작 시점과 볼륨 강화를 정밀하게 기획해야 한다.
        """
        prompt = f"""
        샷 리스트: {shots_json}
        장르 ID: {genre_id}
        
        촬영감독이 확정한 샷들의 흐름을 읽고 대사와 비주얼에 가장 고도화된 음향 디자인을 배치하는 'Sound Agent(음악/효과음 오디오 감독)' 역할을 수행하라.
        
        요구사항:
        1. [Music Agent 역할 - 선택적 BGM]
           - 샷 흐름 상 굳이 음악이 흐르지 않고 침묵이 흘러야 숨 막히는 긴장감이 극대화되거나 표정 연기가 강조되는 연출 구간을 판단하라.
           - 음악을 아예 생략할 샷의 경우 'bgm_style'을 "none"으로, 볼륨(volume)을 0.0으로 명시하라. (극도로 중요!)
           - 음악이 들어갈 경우 장르에 매칭되는 'bgm_style'을 고르라: {list(DEFAULT_BGM.keys())} 중 택1. 볼륨은 0.1~0.6 사이로 부드럽게 지정하라.
           
         2. [Sound SFX Agent 역할 - 샷별 효과음 매핑]
           - 샷의 시각 묘사(visual_prompt, composition)와 나레이션을 읽고 필요한 0.1초 단위 효과음 사운드를 타임라인에 꽂아야 한다.
           - 비 내리는 씬의 배경음, 묵직한 발소리, 삐걱 문 열기, 번쩍 칼 부딪히기, 천둥소리, 경보음 등 시각 지문에 부합하는 효과음을 배치하라.
           - 'sfx_type'은 반드시 {list(DEFAULT_SFX.keys())} 및 "none" 중에서 고르고, 'volume'은 효과의 강도(0.2 ~ 1.0)를, 'timing_offset'은 해당 샷이 플레이 시작된 시점으로부터 몇 초 뒤에 효과음이 탁 터질지 오프셋(초)을 소수점으로 기입할 것 (반드시 샷의 'estimated_duration'보다 작아야 함!).
           
         출력은 반드시 JSON 규격 스키마를 만족해야 한다.
         """
        try:
            response_text = self._run_adk_agent(
                agent_name="sound_agent",
                instruction=instruction,
                prompt=prompt,
                output_schema=SoundOutput
            )
            return SoundOutput.model_validate_json(response_text)
        except Exception as e:
            raise RuntimeError(f"Gemini Sound Agent 사운드 연출 설계 중 오류가 발생했습니다: {str(e)}")
