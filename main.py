import os
import uuid
import json
import datetime
import threading
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

import config
from config import PROJECTS_DIR, get_project_paths, GENRES
from agents import GeminiAgents, StoryOutput, SceneOutput, DirectorOutput, CinematographyOutput, SoundOutput
from synthesis import SynthesisPipeline, create_storyboard_image

app = FastAPI(title="AI Director & Production Studio", version="2.0")

# Mount output directory as static path to serve compiled assets, images and video streams instantly
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
app.mount("/projects_assets", StaticFiles(directory=PROJECTS_DIR), name="projects_assets")

templates = Jinja2Templates(directory=config.TEMPLATES_DIR)

# Global dictionary to track active agent production tasks
ACTIVE_TASKS: Dict[str, Dict[str, Any]] = {}

# Initialize Gemini agents
gemini_agents = GeminiAgents()

# =====================================================================
# REQUEST SCHEMAS
# =====================================================================

class CreateProjectRequest(BaseModel):
    title: str = "무제 영화"
    synopsis: str
    genre_id: str
    episode_times: dict[str, int] = None

class ApproveStoryRequest(BaseModel):
    project_id: str
    episode_no: int
    story_data: dict  # Fits StoryOutput schema

class GenerateStoryRequest(BaseModel):
    title: str = None
    synopsis: str = None

class ApproveScriptRequest(BaseModel):
    project_id: str
    episode_no: int
    user_pov: str = ""

class CompileVideoRequest(BaseModel):
    project_id: str
    episode_no: int

class ResetStageRequest(BaseModel):
    state: str

# =====================================================================
# API ENDPOINTS
# =====================================================================

@app.get("/")
def read_root(request: Request):
    """
    Renders the web dashboard
    """
    return templates.TemplateResponse(request, "index.html", {"genres": GENRES})


@app.get("/api/genres")
def get_genres():
    return JSONResponse(content=GENRES)


@app.post("/api/projects")
def create_project(req: CreateProjectRequest):
    """
    Creates a new project directory structure and initializes the project metadata state machine
    """
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    paths = get_project_paths(project_id)
    
    # Dynamic episode_times initialization (Fallback to 5 standard episodes of 30s if none provided)
    times = req.episode_times or {"1": 30, "2": 30, "3": 30, "4": 30, "5": 30}
    episode_status = {str(ep): "INIT" for ep in times.keys()}
    
    # Save project configuration with dynamic initial state machine
    metadata = {
        "id": project_id,
        "title": req.title,
        "synopsis": req.synopsis,
        "genre_id": req.genre_id,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "episodes_built": [],
        "status": "INIT",
        "episode_status": episode_status,
        "episode_times": times
    }
    
    meta_path = os.path.join(paths["root"], "project_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
        
    return JSONResponse(content={"project_id": project_id, "message": "새로운 시네마 프로젝트가 생성되었습니다."})


@app.post("/api/projects/{project_id}/episodes/{episode_no}/reset")
def reset_episode_stage(project_id: str, episode_no: int, req: ResetStageRequest):
    """
    Manually resets/time-travels an episode's status in the state machine, allowing the user
    to modify previous stages (Story, Screenplay, Storyboard) and re-run the pipeline.
    Also releases any running task locks so users are never stuck in an error loop.
    """
    paths = get_project_paths(project_id)
    meta_path = os.path.join(paths["root"], "project_meta.json")
    if not os.path.exists(meta_path):
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
        
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    if req.state not in ["INIT", "STORY_PENDING", "SCRIPT_PENDING", "BOARD_PENDING"]:
        raise HTTPException(status_code=400, detail="유효하지 않은 기획 단계 상태입니다.")
        
    # Set the target state in metadata
    meta["episode_status"][str(episode_no)] = req.state
    
    # If resetting to earlier than board pending, remove from episodes_built to allow rebuild indicator
    if req.state != "BOARD_PENDING" and "episodes_built" in meta:
        if episode_no in meta["episodes_built"]:
            meta["episodes_built"].remove(episode_no)
            
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        
    # Clear any active task for this project so they can instantly start new tasks without lock!
    if project_id in ACTIVE_TASKS:
        ACTIVE_TASKS.pop(project_id)
        
    return JSONResponse(content={
        "status": "success",
        "message": f"에피소드 {episode_no}화 상태가 {req.state} 단계로 강제 복원되었습니다.",
        "episode_status": meta["episode_status"]
    })


@app.post("/api/generate/story")
def generate_story(project_id: str, req: GenerateStoryRequest = None):
    """
    1단계: Story Agent 구동하여 전체 시리즈 드라마 기획안 수립
    """
    paths = get_project_paths(project_id)
    meta_path = os.path.join(paths["root"], "project_meta.json")
    if not os.path.exists(meta_path):
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
        
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    # Check if task is already running
    if project_id in ACTIVE_TASKS and ACTIVE_TASKS[project_id]["status"] == "running":
        return JSONResponse(content={"status": "running", "message": "이미 다른 작업이 진행 중입니다."})
        
    # If edited story title/synopsis was sent, update project_meta.json first!
    if req:
        updated = False
        if req.title and req.title.strip():
            meta["title"] = req.title.strip()
            updated = True
        if req.synopsis and req.synopsis.strip():
            meta["synopsis"] = req.synopsis.strip()
            updated = True
        if updated:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
                
    # Reset active task state
    ACTIVE_TASKS[project_id] = {
        "status": "running",
        "progress": 5,
        "current_agent": "Story Agent",
        "logs": ["Story Agent: 전체 시즌 줄거리 및 반전 기획안 구상 개시..."],
        "video_url": None
    }
    
    # Update project status
    meta["status"] = "STORY_GENERATING"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        
    def run_story():
        task = ACTIVE_TASKS[project_id]
        try:
            story = gemini_agents.generate_story(meta["synopsis"], meta["genre_id"])
            story_path = os.path.join(paths["scripts"], "story.json")
            with open(story_path, "w", encoding="utf-8") as f:
                f.write(story.model_dump_json(indent=2))
                
            # Move state machine to STORY_PENDING (Awaiting director's manual review)
            meta["status"] = "STORY_PENDING"
            meta["episode_status"]["1"] = "STORY_PENDING"
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
                
            task["status"] = "success"
            task["progress"] = 100
            task["logs"].append(f"Story Agent: '{story.title}' 기획 성공! 캐릭터들과 반전 설계가 완성되었습니다. 줄거리를 검토하고 승인해 주세요.")
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            task["status"] = "failed"
            task["logs"].append(f"Story Agent 기획 실패: {str(e)}")
            meta["status"] = "INIT"
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
                
    thread = threading.Thread(target=run_story)
    thread.daemon = True
    thread.start()
    
    return JSONResponse(content={"status": "started", "message": "줄거리 기획 수립을 시작했습니다."})


@app.post("/api/generate/approve-story")
def approve_story(req: ApproveStoryRequest):
    """
    2단계: 감독이 줄거리 기획안을 최종 승인함 ➡️ 씬 분할 극본 집필 시작 (Scene & Director Agent)
    """
    project_id = req.project_id
    episode_no = req.episode_no
    paths = get_project_paths(project_id)
    meta_path = os.path.join(paths["root"], "project_meta.json")
    if not os.path.exists(meta_path):
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
        
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    if project_id in ACTIVE_TASKS and ACTIVE_TASKS[project_id]["status"] == "running":
        return JSONResponse(content={"status": "running", "message": "이미 다른 작업이 진행 중입니다."})
        
    # Save approved story (user could have edited characters/twists in UI)
    story_path = os.path.join(paths["scripts"], "story.json")
    with open(story_path, "w", encoding="utf-8") as f:
        json.dump(req.story_data, f, ensure_ascii=False, indent=2)
        
    # Update states
    meta["status"] = "STORY_APPROVED"
    meta["episode_status"][str(episode_no)] = "SCRIPT_GENERATING"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        
    ACTIVE_TASKS[project_id] = {
        "status": "running",
        "progress": 10,
        "current_agent": "Scene & Director Agent",
        "logs": [f"Scene & Director Agent: {episode_no}화 씬 분량 쪼개기 및 극본 대사(Dialogue) 집필 개시..."],
        "video_url": None
    }
    
    def run_script():
        task = ACTIVE_TASKS[project_id]
        try:
            story_obj = StoryOutput.model_validate(req.story_data)
            
            # Step 1: Scene Script generation
            task["logs"].append("Scene Agent: 인물 관계에 맞춘 가로등, 지하실 씬 분리 및 디테일 독백/대사 한국어 확장 작성 중...")
            task["progress"] = 40
            scenes = gemini_agents.generate_scenes(episode_no, story_obj, meta["genre_id"])
            scenes_path = os.path.join(paths["scripts"], f"episode_{episode_no}_scenes.json")
            with open(scenes_path, "w", encoding="utf-8") as f:
                f.write(scenes.model_dump_json(indent=2))
                
            # Step 2: Director Style guideline mapping
            task["logs"].append("Director Agent: 각 장소별 톤앤매너 조명 색감 및 연출 기법(롱테이크, 헨드헬드 등) 가이드 설계 중...")
            task["progress"] = 80
            director = gemini_agents.generate_director(scenes.scenes, meta["genre_id"])
            director_path = os.path.join(paths["scripts"], f"episode_{episode_no}_director.json")
            with open(director_path, "w", encoding="utf-8") as f:
                f.write(director.model_dump_json(indent=2))
                
            # Move states to SCRIPT_PENDING
            meta["episode_status"][str(episode_no)] = "SCRIPT_PENDING"
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
                
            task["status"] = "success"
            task["progress"] = 100
            task["logs"].append(f"Scene & Director Agent: {episode_no}화 극본 집필 및 미장센 연출서 완성! 대본을 승인하고 연출 지시를 전달해 주세요.")
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            task["status"] = "failed"
            task["logs"].append(f"대본 집필 중 파손: {str(e)}")
            meta["episode_status"][str(episode_no)] = "STORY_PENDING"
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
                
    thread = threading.Thread(target=run_script)
    thread.daemon = True
    thread.start()
    
    return JSONResponse(content={"status": "started", "message": "에피소드 대본 및 연출 계획 작성을 기동했습니다."})


@app.post("/api/generate/approve-script")
def approve_script(req: ApproveScriptRequest):
    """
    3단계: 감독이 대본을 최종 승인 및 카메라 시선(POV) 연출 지시를 전달 ➡️ 촬영 및 사운드 오케스트레이션 (Cinematography & Sound)
    """
    project_id = req.project_id
    episode_no = req.episode_no
    user_pov = req.user_pov
    paths = get_project_paths(project_id)
    meta_path = os.path.join(paths["root"], "project_meta.json")
    if not os.path.exists(meta_path):
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
        
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    if project_id in ACTIVE_TASKS and ACTIVE_TASKS[project_id]["status"] == "running":
        return JSONResponse(content={"status": "running", "message": "이미 다른 작업이 진행 중입니다."})
        
    # Update states
    meta["episode_status"][str(episode_no)] = "BOARD_GENERATING"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        
    ACTIVE_TASKS[project_id] = {
        "status": "running",
        "progress": 10,
        "current_agent": "Cinematography & Sound Agent",
        "logs": [f"Cinematography Agent: 샷 분할 기획 시작 (감독 촬영지시: '{user_pov or '없음'}')..."],
        "video_url": None
    }
    
    def run_storyboard():
        task = ACTIVE_TASKS[project_id]
        try:
            # Read inputs
            scenes_path = os.path.join(paths["scripts"], f"episode_{episode_no}_scenes.json")
            director_path = os.path.join(paths["scripts"], f"episode_{episode_no}_director.json")
            
            with open(scenes_path, "r", encoding="utf-8") as f:
                scenes = SceneOutput.model_validate_json(f.read())
            with open(director_path, "r", encoding="utf-8") as f:
                director = DirectorOutput.model_validate_json(f.read())
                
            # Step 1: Cinematography mapping with POV
            task["logs"].append(f"Cinematography Agent: 각 씬을 3컷으로 세부 절단 중... 사용자 POV 연출 지정 병합 완료.")
            task["progress"] = 50
            cinematography = gemini_agents.generate_cinematography(episode_no, scenes.scenes, director, user_pov)
            cinematography_path = os.path.join(paths["scripts"], f"episode_{episode_no}_cinematography.json")
            with open(cinematography_path, "w", encoding="utf-8") as f:
                f.write(cinematography.model_dump_json(indent=2))
                
            # Step 2: Dynamic Sound & Selective BGM mapping
            task["logs"].append("Sound Agent: 씬 긴장감에 비례한 무음 BGM 구간 설정 및 빗소리/칼부딪힘 효과음 오프셋 수립 중...")
            task["progress"] = 85
            sound = gemini_agents.generate_sound(cinematography.shots, meta["genre_id"])
            sound_path = os.path.join(paths["scripts"], f"episode_{episode_no}_sound.json")
            with open(sound_path, "w", encoding="utf-8") as f:
                f.write(sound.model_dump_json(indent=2))
                
            # Step 3: Pre-generate Storyboard Images for Visual Planning (So users see actual unique images instantly)
            task["logs"].append("Storyboard Agent: 각 컷별 AI 기획 이미지 전제 드로잉 중 (대시보드 스토리보드 탭 시각화)...")
            task["progress"] = 88
            
            # Map each shot to its sound and narration to render overlay
            sound_map = {s.shot_id: s for s in sound.sounds}
            total_shots = len(cinematography.shots)
            
            for idx, shot in enumerate(cinematography.shots):
                shot_id = shot.shot_id
                img_filename = f"{shot_id}_storyboard.png"
                img_path = os.path.join(paths["storyboards"], img_filename)
                
                narration_text = sound_map[shot_id].narration if shot_id in sound_map else ""
                
                task["logs"].append(f"Storyboard Agent: 컷 '{shot_id}' 연출 드로잉 진행 중 ({idx + 1}/{total_shots})...")
                task["progress"] = int(88 + (idx / total_shots) * 11)
                
                create_storyboard_image(
                    filepath=img_path,
                    shot_id=shot_id,
                    scene_no=shot.scene_no,
                    angle=shot.camera_angle,
                    composition=shot.composition,
                    narration=narration_text,
                    mood=sound.mood,
                    visual_prompt=shot.visual_prompt or ""
                )
                
            # Update states
            meta["episode_status"][str(episode_no)] = "BOARD_PENDING"
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
                
            task["status"] = "success"
            task["progress"] = 100
            task["logs"].append(f"Cinematography & Sound Agent: {episode_no}화 촬영 레이아웃 및 3D 음향 설계 장부 발행 완료. 합성 상영 버튼을 클릭하여 영상을 구워내세요!")
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            task["status"] = "failed"
            task["logs"].append(f"카메라 촬영계획 조율 실패: {str(e)}")
            meta["episode_status"][str(episode_no)] = "SCRIPT_PENDING"
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
                
    thread = threading.Thread(target=run_storyboard)
    thread.daemon = True
    thread.start()
    
    return JSONResponse(content={"status": "started", "message": "카메라 앵글 컷 및 입체 사운드 설계를 시작했습니다."})


@app.post("/api/generate/compile")
def compile_video(req: CompileVideoRequest):
    """
    4단계: 최종 촬영/사운드 승인 ➡️ FFmpeg 자동 인코딩 믹서 가동하여 최종 무비 클립 컴파일
    """
    project_id = req.project_id
    episode_no = req.episode_no
    paths = get_project_paths(project_id)
    meta_path = os.path.join(paths["root"], "project_meta.json")
    if not os.path.exists(meta_path):
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
        
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    if project_id in ACTIVE_TASKS and ACTIVE_TASKS[project_id]["status"] == "running":
        return JSONResponse(content={"status": "running", "message": "이미 다른 작업이 진행 중입니다."})
        
    # Update states
    meta["episode_status"][str(episode_no)] = "VIDEO_COMPILING"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        
    ACTIVE_TASKS[project_id] = {
        "status": "running",
        "progress": 5,
        "current_agent": "Synthesis Engine",
        "logs": ["Synthesis Engine: 이미지 렌더링, 오디오 및 TTS 다채널 믹서 가동 및 FFmpeg 인코딩 가동..."],
        "video_url": None
    }
    
    pipeline = SynthesisPipeline(project_id)
    
    def run_synthesis():
        task = ACTIVE_TASKS[project_id]
        try:
            # Read prepared details
            scenes_path = os.path.join(paths["scripts"], f"episode_{episode_no}_scenes.json")
            cine_path = os.path.join(paths["scripts"], f"episode_{episode_no}_cinematography.json")
            sound_path = os.path.join(paths["scripts"], f"episode_{episode_no}_sound.json")
            
            with open(scenes_path, "r", encoding="utf-8") as f:
                scenes_data = json.load(f)["scenes"]
            with open(cine_path, "r", encoding="utf-8") as f:
                cine_data = json.load(f)["shots"]
            with open(sound_path, "r", encoding="utf-8") as f:
                sound_data = json.load(f)
                
            task["progress"] = 30
            final_video = pipeline.compile_full_episode(
                episode_no=episode_no,
                shots=cine_data,
                scenes=scenes_data,
                sound=sound_data,
                genre_id=meta["genre_id"]
            )
            
            # Transition states on success
            meta["episode_status"][str(episode_no)] = "VIDEO_COMPLETED"
            if episode_no not in meta["episodes_built"]:
                meta["episodes_built"].append(episode_no)
                
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
                
            task["status"] = "success"
            task["progress"] = 100
            task["video_url"] = f"/projects_assets/{project_id}/videos/episode_{episode_no}.mp4"
            task["logs"].append(f"Synthesis Engine: {episode_no}화 비디오 렌더링 및 음향 합성 완전 성공! 대시보드 상영관에서 극장급 음향과 감상하세요.")
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            task["status"] = "failed"
            task["logs"].append(f"시네마 컴파일 실패: {str(e)}")
            meta["episode_status"][str(episode_no)] = "BOARD_PENDING"
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
                
    thread = threading.Thread(target=run_synthesis)
    thread.daemon = True
    thread.start()
    
    return JSONResponse(content={"status": "started", "message": "최종 비디오 컴파일 인코더를 가동시켰습니다."})


@app.get("/api/status/{project_id}")
def get_status(project_id: str):
    """
    Returns the real-time background compiler logs merged with project metadata state machine gates
    """
    paths = get_project_paths(project_id)
    meta_path = os.path.join(paths["root"], "project_meta.json")
    if not os.path.exists(meta_path):
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
        
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    task = ACTIVE_TASKS.get(project_id, {
        "status": "idle",
        "progress": 100,
        "current_agent": "Ready",
        "logs": ["스튜디오 가동 준비 완료."],
        "video_url": None
    })
    
    return JSONResponse(content={
        "task": task,
        "project_status": meta.get("status", "INIT"),
        "episode_status": meta.get("episode_status", {"1": "INIT", "2": "INIT", "3": "INIT", "4": "INIT", "5": "INIT"})
    })


@app.get("/api/projects/list")
def list_projects():
    """
    Lists all projects, their scripts, generated media, and status inside PROJECTS_DIR
    """
    if not os.path.exists(PROJECTS_DIR):
        return JSONResponse(content=[])
        
    projects = []
    for d in os.listdir(PROJECTS_DIR):
        root_path = os.path.join(PROJECTS_DIR, d)
        meta_path = os.path.join(root_path, "project_meta.json")
        
        if os.path.isdir(root_path) and os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    
                # Scan for compiled videos
                videos_dir = os.path.join(root_path, "videos")
                meta["videos"] = []
                if os.path.exists(videos_dir):
                    for v in os.listdir(videos_dir):
                        if v.endswith(".mp4"):
                            meta["videos"].append({
                                "episode_no": int(v.split("_")[1].replace(".mp4", "")),
                                "url": f"/projects_assets/{meta['id']}/videos/{v}"
                            })
                            
                # Scan for generated screenplay script files
                scripts_dir = os.path.join(root_path, "scripts")
                meta["has_script"] = os.path.exists(os.path.join(scripts_dir, "story.json"))
                
                # Fetch story title, prioritized: 1) Custom project title, 2) Generated story title, 3) Fallback "무제 영화"
                project_title = meta.get("title", "무제 영화")
                meta["title"] = project_title
                if meta["has_script"]:
                    with open(os.path.join(scripts_dir, "story.json"), "r", encoding="utf-8") as sf:
                        story_data = json.load(sf)
                        # Fallback to AI-generated title only if custom title is default/empty
                        if project_title == "무제 영화" or not project_title:
                            meta["title"] = story_data.get("title", "무제 영화")
                        meta["characters_count"] = len(story_data.get("characters", []))
                        
                projects.append(meta)
            except Exception as e:
                print(f"Error loading project {d}: {e}")
                
    return JSONResponse(content=projects)


@app.get("/api/projects/{project_id}/assets")
def get_project_full_assets(project_id: str, episode_no: int):
    """
    Loads all JSON script assets generated by agents for the frontend editor/timeline
    """
    paths = get_project_paths(project_id)
    assets = {
        "story": None,
        "scenes": None,
        "director": None,
        "cinematography": None,
        "sound": None
    }
    
    try:
        # Load meta to get user's custom project title and synopsis
        meta_path = os.path.join(paths["root"], "project_meta.json")
        project_title = "무제 영화"
        project_synopsis = ""
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            project_title = meta.get("title") or "무제 영화"
            project_synopsis = meta.get("synopsis") or ""
            
        story_path = os.path.join(paths["scripts"], "story.json")
        if os.path.exists(story_path):
            with open(story_path, "r", encoding="utf-8") as f:
                assets["story"] = json.load(f)
                # Overwrite AI-generated title with custom user project title to preserve custom naming!
                assets["story"]["title"] = project_title
        else:
            assets["story"] = {
                "title": project_title,
                "synopsis": project_synopsis,
                "twists": [
                    "1단계 지휘권을 기동하여 '스토리 기획 수립'을 시작해 주세요. 감독님의 시놉시스를 기초로 감동적인 체스 전쟁의 극적 반전이 설계됩니다!"
                ],
                "characters": [
                    {
                        "name": "체스 전쟁의 전사들 (기획 대기)",
                        "role": "온갖 전투에서 목숨을 걸고 활약할 폰(Pawn), 다른 기물들(Rook, Knight, Bishop)의 위대한 희생 스토리가 곧 여기에 전개됩니다."
                    }
                ]
            }
                
        scenes_path = os.path.join(paths["scripts"], f"episode_{episode_no}_scenes.json")
        if os.path.exists(scenes_path):
            with open(scenes_path, "r", encoding="utf-8") as f:
                assets["scenes"] = json.load(f)
                
        dir_path = os.path.join(paths["scripts"], f"episode_{episode_no}_director.json")
        if os.path.exists(dir_path):
            with open(dir_path, "r", encoding="utf-8") as f:
                assets["director"] = json.load(f)
                
        cine_path = os.path.join(paths["scripts"], f"episode_{episode_no}_cinematography.json")
        if os.path.exists(cine_path):
            with open(cine_path, "r", encoding="utf-8") as f:
                assets["cinematography"] = json.load(f)
                
        sound_path = os.path.join(paths["scripts"], f"episode_{episode_no}_sound.json")
        if os.path.exists(sound_path):
            with open(sound_path, "r", encoding="utf-8") as f:
                assets["sound"] = json.load(f)
                
        return JSONResponse(content=assets)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"에셋 로드 중 실패: {e}")


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str):
    """
    Deletes a project directory and cleans up its active tasks
    """
    import shutil
    paths = get_project_paths(project_id)
    root_dir = paths["root"]
    
    if project_id in ACTIVE_TASKS:
        ACTIVE_TASKS.pop(project_id, None)
        
    if os.path.exists(root_dir):
        try:
            shutil.rmtree(root_dir)
            return JSONResponse(content={"project_id": project_id, "message": "프로젝트가 성공적으로 삭제되었습니다."})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"프로젝트 삭제 실패: {e}")
    else:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
