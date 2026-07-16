/* =====================================================================
   AI DIRECTOR PRODUCTION STUDIO - CLIENT ORCHESTRATOR
   ===================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // -----------------------------------------------------------------
    // GLOBALS & STATE MACHINE
    // -----------------------------------------------------------------
    let CURRENT_PROJECT_ID = null;
    let POLLING_INTERVAL_ID = null;
    let IS_BUILDING = false;
    
    let CURRENT_STORY_DATA = null;     // Local cache for human-in-the-loop editing
    let CURRENT_EPISODE_STATE = "INIT"; // Active stage machine status

    // DOM Cache
    const elProjectTitleInput = document.getElementById("project-title-input");
    const elSynopsis = document.getElementById("synopsis-input");
    const elGenre = document.getElementById("genre-select");
    const elCreateEpisodesCount = document.getElementById("create-episodes-count");
    const elCreateEpisodeTimesInputs = document.getElementById("create-episode-times-inputs");
    const elBtnCreate = document.getElementById("btn-create-project");
    
    // Interactive Gate Desk DOMs
    const elBtnGateAction = document.getElementById("btn-gate-action");
    const elGateBadge = document.getElementById("gate-status-badge");
    const elGateDesc = document.getElementById("gate-status-desc");
    const elPovWrapper = document.getElementById("pov-input-wrapper");
    const elPovInput = document.getElementById("pov-input");
    const elStageResetSelect = document.getElementById("stage-reset-select");
    const elBtnStageReset = document.getElementById("btn-stage-reset");

    const elBtnRefresh = document.getElementById("btn-refresh");
    const elBtnDeleteProject = document.getElementById("btn-delete-project");
    const elProjectSelect = document.getElementById("project-list-select");
    const elEpisodeSelect = document.getElementById("episode-select");
    const elEpisodeBlock = document.getElementById("episode-control-block");
    const elProgressBlock = document.getElementById("progress-block");
    const elProgressBarFill = document.getElementById("progress-bar-fill");
    const elActiveAgentLabel = document.getElementById("active-agent-name");
    const elProgressPercentLabel = document.getElementById("progress-percent-label");
    const elTerminalLogs = document.getElementById("terminal-logs");
    
    // Player DOMs
    const elVideoPlayer = document.getElementById("theater-video-player");
    const elPlayerIdleCard = document.getElementById("player-idle-card");
    const elTheaterMovieTitle = document.getElementById("theater-movie-title");
    const elTheaterEpisodeBadge = document.getElementById("theater-episode-badge");
    const elBtnDownloadVideo = document.getElementById("btn-download-video");
    const elScreenGlow = document.getElementById("screen-glow");

    // Story DOMs
    const elStoryTitle = document.getElementById("story-movie-title");
    const elStorySynopsis = document.getElementById("story-movie-synopsis");
    const elStoryTwists = document.getElementById("story-twists-list");
    const elStoryForeshadow = document.getElementById("story-foreshadow-list");
    const elCharactersGrid = document.getElementById("characters-grid");

    // Script & Storyboard DOMs
    const elScreenplayBody = document.getElementById("screenplay-body");
    const elScriptMovieTitle = document.getElementById("script-movie-title");
    const elScriptEpisodeTitle = document.getElementById("script-episode-title");
    const elStoryboardGallery = document.getElementById("storyboard-gallery");
    const elMixerTimelineGrid = document.getElementById("mixer-timeline-grid");

    // -----------------------------------------------------------------
    // TAB SWITCHING SYSTEM
    // -----------------------------------------------------------------
    const tabButtons = document.querySelectorAll(".tab-btn");
    const tabPanes = document.querySelectorAll(".tab-pane");

    tabButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");
            
            tabButtons.forEach(b => b.classList.remove("active"));
            tabPanes.forEach(pane => pane.classList.remove("active"));
            
            btn.classList.add("active");
            document.getElementById(targetTab).classList.add("active");
            
            // Re-render Lucide icons
            lucide.createIcons();
        });
    });

    // Initialize Lucide icons on start
    lucide.createIcons();

    // -----------------------------------------------------------------
    // TERMINAL LOG HELPER
    // -----------------------------------------------------------------
    function clearTerminal() {
        elTerminalLogs.innerHTML = "";
    }

    function addTerminalLine(text, type = "normal") {
        const line = document.createElement("div");
        line.className = `terminal-line ${type}-msg`;
        line.innerText = text;
        elTerminalLogs.appendChild(line);
        elTerminalLogs.scrollTop = elTerminalLogs.scrollHeight;
    }

    // -----------------------------------------------------------------
    // ACTIVE STAGE STATE MACHINE RENDERER
    // -----------------------------------------------------------------
    function updateGateDeskUI(state) {
        CURRENT_EPISODE_STATE = state;
        
        // Reset classes
        elGateBadge.classList.remove("badge-init", "badge-generating", "badge-pending", "badge-completed");
        elPovWrapper.classList.add("hidden");
        elBtnGateAction.disabled = false;
        
        switch (state) {
            case "INIT":
                elGateBadge.classList.add("badge-init");
                elGateBadge.innerText = "미기획 (INIT)";
                elGateDesc.innerText = "새 프로젝트 생성이 성사되었습니다. 1단계를 실행하여 시즌 시놉시스, 주요 인물 관계, 전체 5부작 시리즈 아웃라인 기획서를 빌드해 보세요.";
                elBtnGateAction.innerHTML = '<i data-lucide="feather"></i> 1단계: 스토리 기획서 생성';
                break;
                
            case "STORY_GENERATING":
                elGateBadge.classList.add("badge-generating");
                elGateBadge.innerText = "기획안 구성 중...";
                elGateDesc.innerText = "Story Agent가 5부작 연재 분량의 기획 성격, 플롯 복선 지도, 캐릭터 도시에를 정교하게 주조하고 있습니다...";
                elBtnGateAction.disabled = true;
                elBtnGateAction.innerHTML = '<i class="spin-icon" data-lucide="loader-2"></i> Story Agent 집필 중';
                break;
                
            case "STORY_PENDING":
                elGateBadge.classList.add("badge-pending");
                elGateBadge.innerText = "스토리 승인 대기";
                elGateDesc.innerText = "드라마 시리즈 기획안이 수립 완료되었습니다. 상단 [Story] 탭에서 극적 반전과 캐릭터 관계를 자유롭게 검토하고 수정사항을 승인하세요.";
                elBtnGateAction.innerHTML = '<i data-lucide="check-circle"></i> 2단계: 스토리 승인 및 대본 집필';
                break;
                
            case "SCRIPT_GENERATING":
                elGateBadge.classList.add("badge-generating");
                elGateBadge.innerText = "극본 집필 중...";
                elGateDesc.innerText = "Scene & Director Agent가 씬 연극 구조를 나누고 분위기 템포 및 디테일한 한글 대사 대본을 밀도 있게 확장하고 있습니다...";
                elBtnGateAction.disabled = true;
                elBtnGateAction.innerHTML = '<i class="spin-icon" data-lucide="loader-2"></i> 극본 대본 집필 중';
                break;
                
            case "SCRIPT_PENDING":
                elGateBadge.classList.add("badge-pending");
                elGateBadge.innerText = "대본 승인 대기";
                elGateDesc.innerText = "[Screenplay] 탭에서 대사 분량을 읽고 연출 지시를 확인하세요. 샷을 나누기 전, 원하시는 '감독 연출 시선 (POV)' 각도를 적어 전송하세요.";
                elPovWrapper.classList.remove("hidden");
                elBtnGateAction.innerHTML = '<i data-lucide="aperture"></i> 3단계: 대본 최종 승인 및 컷 분할';
                break;
                
            case "BOARD_GENERATING":
                elGateBadge.classList.add("badge-generating");
                elGateBadge.innerText = "시각/사운드 설계 중...";
                elGateDesc.innerText = "Cinematography & Sound Agent가 연출가 POV 지침을 녹여내어 개별 촬영 프롬프트 및 사운드 오프셋 볼륨 맵을 조율 중입니다...";
                elBtnGateAction.disabled = true;
                elBtnGateAction.innerHTML = '<i class="spin-icon" data-lucide="loader-2"></i> 촬영 및 사운드 매핑 중';
                break;
                
            case "BOARD_PENDING":
                elGateBadge.classList.add("badge-pending");
                elGateBadge.innerText = "촬영 승인 대기";
                elGateDesc.innerText = "3D 샷 앵글 구성안과 입체 효과음 설계가 도출되었습니다. [Storyboard]와 [Sound Mix] 탭을 검사하고 최종 합성 시네마를 구워내세요.";
                elBtnGateAction.innerHTML = '<i data-lucide="cpu"></i> 4단계: 비디오 시네마 컴파일';
                break;
                
            case "VIDEO_COMPILING":
                elGateBadge.classList.add("badge-generating");
                elGateBadge.innerText = "비디오 인코딩 중...";
                elGateDesc.innerText = "Synthesis Engine이 한국어 성우 나레이션 대사 컴파일, 음향 오프셋 믹싱, 16:9 샷 렌더 및 FFmpeg 융합 비디오를 인코딩하고 있습니다...";
                elBtnGateAction.disabled = true;
                elBtnGateAction.innerHTML = '<i class="spin-icon" data-lucide="loader-2"></i> FFmpeg 융합 컴파일 중';
                break;
                
            case "VIDEO_COMPLETED":
                elGateBadge.classList.add("badge-completed");
                elGateBadge.innerText = "제작 완료 (COMPLETED)";
                elGateDesc.innerText = "성공입니다! 해당 에피소드가 극장 상영에 올라왔습니다. 만약 영상미가 마음에 들지 않거나 다른 AI 화풍으로 새로 굽고 싶다면 언제든 재시도 버튼을 누르세요.";
                elBtnGateAction.disabled = false;
                elBtnGateAction.innerHTML = '<i data-lucide="rotate-ccw"></i> 4단계: 시네마 재컴파일 및 렌더링 (Retry)';
                break;
        }
        lucide.createIcons();
    }

    // -----------------------------------------------------------------
    // API CALLS
    // -----------------------------------------------------------------
    
    // 1. Fetch available projects
    async function fetchProjectList(selectedId = null) {
        try {
            const res = await fetch("/api/projects/list");
            const projects = await res.json();
            
            elProjectSelect.innerHTML = '<option value="">-- 불러올 시네마 프로젝트 선택 --</option>';
            projects.forEach(p => {
                const opt = document.createElement("option");
                opt.value = p.id;
                opt.innerText = `${p.title} (${p.genre_id.toUpperCase()})`;
                if (p.id === selectedId) {
                    opt.selected = true;
                }
                elProjectSelect.appendChild(opt);
            });
        } catch (e) {
            console.error("Error fetching projects:", e);
        }
    }

    // Initialize list on startup
    fetchProjectList();

    // 2. Select Project
    elProjectSelect.addEventListener("change", (e) => {
        const pId = e.target.value;
        if (!pId) {
            CURRENT_PROJECT_ID = null;
            elEpisodeBlock.classList.add("disabled");
            elBtnDeleteProject.disabled = true;
            resetStudioBoard();
            return;
        }
        elBtnDeleteProject.disabled = false;
        selectProject(pId);
    });

    async function selectProject(projectId) {
        CURRENT_PROJECT_ID = projectId;
        elEpisodeBlock.classList.remove("disabled");
        elBtnDeleteProject.disabled = false;
        clearTerminal();
        addTerminalLine(`[SYSTEM]: 프로젝트 '${projectId}'를 지휘 테이블에 올렸습니다.`, "success");
        
        // Sync interactive status mapping from backend meta
        await syncStateWithBackend();
        
        // Load default episode assets
        const epNo = elEpisodeSelect.value;
        loadProjectAssets(projectId, epNo);
        
        elProjectSelect.value = projectId;
    }

    // Direct Status Fetcher to sync clients & gatekeepers
    async function syncStateWithBackend() {
        if (!CURRENT_PROJECT_ID) return;
        try {
            const res = await fetch(`/api/status/${CURRENT_PROJECT_ID}`);
            const data = await res.json();
            
            // Rebuild elEpisodeSelect options dynamically matching backend's initialized episodes!
            if (data.episode_status) {
                const currentSelectedEp = elEpisodeSelect.value;
                const eps = Object.keys(data.episode_status).sort((a,b) => parseInt(a) - parseInt(b));
                
                let optionsHTML = "";
                eps.forEach(ep => {
                    const duration = data.episode_times ? data.episode_times[ep] : 30;
                    optionsHTML += `<option value="${ep}">제 ${ep} 화 (${duration}초 러닝타임)</option>`;
                });
                elEpisodeSelect.innerHTML = optionsHTML;
                
                // Restore selection if valid, else pick first
                if (eps.includes(currentSelectedEp)) {
                    elEpisodeSelect.value = currentSelectedEp;
                } else {
                    elEpisodeSelect.value = eps[0] || "1";
                }
            }
            
            const epNo = elEpisodeSelect.value;
            const epStatus = data.episode_status[epNo] || "INIT";
            
            updateGateDeskUI(epStatus);
            
            // If the task is currently active/generating, resume polling!
            if (data.task.status === "running") {
                startPollingStatus();
            }
        } catch (e) {
            console.error("Failed syncing project meta state:", e);
        }
    }

    // 2b. Dynamic Episode Times Inputs Generator
    if (elCreateEpisodesCount && elCreateEpisodeTimesInputs) {
        elCreateEpisodesCount.addEventListener("change", () => {
            const count = parseInt(elCreateEpisodesCount.value) || 2;
            let html = "";
            for (let i = 1; i <= count; i++) {
                // Sensible defaults: 30s for Ep 1, 45s for Ep 2, 30s for others
                let defaultValue = 30;
                if (i === 2) defaultValue = 45;
                
                html += `
                <div style="display: flex; gap: 8px; align-items: center;" class="duration-input-row" data-ep="${i}">
                    <label style="font-size: 0.72rem; color: #a1a1aa; width: 65px;">${i}화 목표초</label>
                    <input type="number" class="studio-input ep-time-input" data-ep="${i}" value="${defaultValue}" min="10" max="300" style="flex: 1; height: 30px; font-size: 0.75rem; padding: 4px 8px; background: #09090b; border-color: rgba(255,255,255,0.08);">
                    <span style="font-size: 0.72rem; color: #71717a; width: 15px;">초</span>
                </div>`;
            }
            elCreateEpisodeTimesInputs.innerHTML = html;
        });
    }

    // 3. Create New Project
    elBtnCreate.addEventListener("click", async () => {
        const title = elProjectTitleInput.value.trim() || "무제 영화";
        const synopsis = elSynopsis.value.trim();
        const genreId = elGenre.value;
        
        if (!synopsis) {
            alert("강렬한 영화적 시놉시스를 입력해 주세요!");
            return;
        }

        // Gather custom episode times
        const episodeTimes = {};
        const timeInputs = document.querySelectorAll(".ep-time-input");
        timeInputs.forEach(input => {
            const ep = input.getAttribute("data-ep");
            const sec = parseInt(input.value) || 30;
            episodeTimes[ep] = sec;
        });

        elBtnCreate.disabled = true;
        elBtnCreate.innerHTML = '<i class="spin-icon" data-lucide="loader-2"></i> 시네마 공장 기획 중...';
        lucide.createIcons();
        clearTerminal();
        addTerminalLine("[SYSTEM]: 가상 스튜디오 제작진을 소집하여 기획 회의에 돌입합니다.");
        
        try {
            const res = await fetch("/api/projects", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title, synopsis, genre_id: genreId, episode_times: episodeTimes })
            });
            const data = await res.json();
            
            addTerminalLine(`[SYSTEM]: 신규 프로젝트 기지 개설 완료 (프로젝트 ID: ${data.project_id})`, "success");
            
            // Clean up inputs on success
            elProjectTitleInput.value = "";
            elSynopsis.value = "";
            
            // Reload lists and select
            await fetchProjectList(data.project_id);
            await selectProject(data.project_id);
            
        } catch (e) {
            addTerminalLine(`[ERROR]: 시네마 빌드 중 오류 발생: ${e}`, "failed");
        } finally {
            elBtnCreate.disabled = false;
            elBtnCreate.innerHTML = '<i data-lucide="plus-circle"></i> 새 프로젝트 생성 및 기획';
            lucide.createIcons();
        }
    });

    // 4. MULTI-STAGE GATES INTERACTION MANAGER
    elBtnGateAction.addEventListener("click", async () => {
        if (!CURRENT_PROJECT_ID) return;
        const epNo = elEpisodeSelect.value;
        
        if (CURRENT_EPISODE_STATE === "INIT") {
            // Trigger Stage 1 Story Generation
            const latestTitle = elStoryTitle ? elStoryTitle.innerText.trim() : "";
            const latestSynopsis = elStorySynopsis ? elStorySynopsis.innerText.trim() : "";
            
            addTerminalLine(`[SYSTEM]: [1단계] Story Agent 소환. 장편 시리즈 시놉시스 구성 기획을 개시합니다.`);
            try {
                const res = await fetch(`/api/generate/story?project_id=${CURRENT_PROJECT_ID}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ title: latestTitle, synopsis: latestSynopsis })
                });
                const data = await res.json();
                if (data.status === "started" || data.status === "running") {
                    startPollingStatus();
                }
            } catch (e) {
                addTerminalLine(`[ERROR]: 스토리 기획 기동 에러: ${e}`, "failed");
            }
        } 
        else if (CURRENT_EPISODE_STATE === "STORY_PENDING") {
            // Trigger Stage 2 Script Screenplay compilation
            if (!CURRENT_STORY_DATA) {
                alert("기획 데이터 로딩 중입니다. 잠시만 기다려 주세요!");
                return;
            }
            addTerminalLine(`[SYSTEM]: [2단계] 스토리 승인 확인. Scene & Director Agent에게 한국어 극본 대사 및 미장센 가이드 확장을 지시합니다.`);
            try {
                const res = await fetch(`/api/generate/approve-story`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        project_id: CURRENT_PROJECT_ID,
                        episode_no: parseInt(epNo),
                        story_data: CURRENT_STORY_DATA
                    })
                });
                const data = await res.json();
                if (data.status === "started" || data.status === "running") {
                    startPollingStatus();
                }
            } catch (e) {
                addTerminalLine(`[ERROR]: 대본 작문 지시 실패: ${e}`, "failed");
            }
        }
        else if (CURRENT_EPISODE_STATE === "SCRIPT_PENDING") {
            // Trigger Stage 3 Cinematography Storyboard plotting (Reads User POV direction)
            const user_pov = elPovInput.value.trim();
            addTerminalLine(`[SYSTEM]: [3단계] 극본 최종 승인 완료. 감독 촬영 시선 지시('${user_pov || "표준 시네마 연출"}')를 접수하여 샷 절단 및 사운드 오프셋 매핑을 개시합니다.`);
            try {
                const res = await fetch(`/api/generate/approve-script`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        project_id: CURRENT_PROJECT_ID,
                        episode_no: parseInt(epNo),
                        user_pov: user_pov
                    })
                });
                const data = await res.json();
                if (data.status === "started" || data.status === "running") {
                    startPollingStatus();
                }
            } catch (e) {
                addTerminalLine(`[ERROR]: 샷 설계 지시 에러: ${e}`, "failed");
            }
        }
        else if (CURRENT_EPISODE_STATE === "BOARD_PENDING" || CURRENT_EPISODE_STATE === "VIDEO_COMPLETED") {
            // Trigger Stage 4 Final Synthesis Cinema compile
            addTerminalLine(`[SYSTEM]: [4단계/재시도] 최종 오디오 믹싱, AI 장면 렌더링 및 비디오 재컴파일을 실행합니다.`);
            try {
                const res = await fetch(`/api/generate/compile`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        project_id: CURRENT_PROJECT_ID,
                        episode_no: parseInt(epNo)
                    })
                });
                const data = await res.json();
                if (data.status === "started" || data.status === "running") {
                    startPollingStatus();
                }
            } catch (e) {
                addTerminalLine(`[ERROR]: 비디오 합성 요청 에러: ${e}`, "failed");
            }
        }
    });

    // 4b. STAGE ROLLBACK / TIME-TRAVEL HANDLER
    elBtnStageReset.addEventListener("click", async () => {
        if (!CURRENT_PROJECT_ID) {
            alert("먼저 프로젝트를 선택하거나 생성해 주세요!");
            return;
        }
        
        const epNo = elEpisodeSelect.value;
        const targetState = elStageResetSelect.value;
        
        if (!confirm(`정말로 ${epNo}화 기획 과정을 '${targetState}' 단계로 강제 되돌리시겠습니까?\n되돌린 후 기존 기획 데이터(스토리, 대본)를 고치고 파이프라인을 처음부터 다시 구동하실 수 있습니다.`)) {
            return;
        }
        
        addTerminalLine(`[SYSTEM]: [타임머신] ${epNo}화 기획 과정을 '${targetState}' 단계로 강제 복원 요청합니다...`);
        elBtnStageReset.disabled = true;
        
        try {
            const res = await fetch(`/api/projects/${CURRENT_PROJECT_ID}/episodes/${epNo}/reset`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ state: targetState })
            });
            const data = await res.json();
            
            if (data.status === "success") {
                addTerminalLine(`[SYSTEM]: 복원 성공! 에피소드 ${epNo}화 상태가 '${targetState}' 단계로 되돌아왔습니다.`, "success");
                
                // If there's an active status polling, stop it!
                stopPollingStatus();
                
                // Instantly synchronize with backend to reset button & UI states!
                await syncStateWithBackend();
            } else {
                addTerminalLine(`[ERROR]: 단계 복원 실패: ${data.message}`, "failed");
            }
        } catch (e) {
            addTerminalLine(`[ERROR]: 단계 복원 통신 중 장애 발생: ${e}`, "failed");
        } finally {
            elBtnStageReset.disabled = false;
        }
    });

    // 5. Polling pipeline status
    function startPollingStatus() {
        if (POLLING_INTERVAL_ID) clearInterval(POLLING_INTERVAL_ID);
        
        IS_BUILDING = true;
        elProgressBlock.classList.remove("hidden");
        elBtnGateAction.disabled = true;
        
        POLLING_INTERVAL_ID = setInterval(async () => {
            if (!CURRENT_PROJECT_ID) {
                stopPollingStatus();
                return;
            }
            
            try {
                const res = await fetch(`/api/status/${CURRENT_PROJECT_ID}`);
                const data = await res.json();
                
                // Update Progress bar
                elProgressBarFill.style.width = `${data.task.progress}%`;
                elProgressPercentLabel.innerText = `${data.task.progress}%`;
                elActiveAgentLabel.innerText = `${data.task.current_agent}...`;
                
                // Sync pipeline flowchart visual nodes matching backend progress milestones
                updatePipelineMap(data.task.progress);
                
                // Update the state machine badge inside Polling!
                const epNo = elEpisodeSelect.value;
                const epStatus = data.episode_status[epNo] || "INIT";
                updateGateDeskUI(epStatus);
                
                // Append delta logs to terminal box
                if (data.task.logs && data.task.logs.length > 0) {
                    clearTerminal();
                    data.task.logs.forEach(l => {
                        let type = "normal";
                        if (l.includes("성공") || l.includes("완료") || l.includes("성공적으로")) type = "success";
                        if (l.includes("에러") || l.includes("실패") || l.includes("중단") || l.includes("파손")) type = "failed";
                        addTerminalLine(l, type);
                    });
                }
                
                // Handle Success finalization
                if (data.task.status === "success") {
                    addTerminalLine(`[CONGRATULATIONS]: 에이전트 연출 완료! 지휘 성배에 기록되었습니다.`, "success");
                    stopPollingStatus();
                    await loadProjectAssets(CURRENT_PROJECT_ID, elEpisodeSelect.value);
                    
                    // Cinematic Reactive Tab Auto-switching based on achieved checkpoint!
                    if (epStatus === "STORY_PENDING") {
                        document.querySelector('[data-tab="tab-story"]').click();
                    } else if (epStatus === "SCRIPT_PENDING") {
                        document.querySelector('[data-tab="tab-script"]').click();
                    } else if (epStatus === "BOARD_PENDING") {
                        document.querySelector('[data-tab="tab-storyboard"]').click();
                    } else if (epStatus === "VIDEO_COMPLETED") {
                        document.querySelector('[data-tab="tab-player"]').click();
                    }
                } else if (data.task.status === "failed") {
                    addTerminalLine(`[ERROR]: 빌드 중단. 가상 인코더 엔진이 충돌했습니다.`, "failed");
                    stopPollingStatus();
                    syncStateWithBackend();
                }
                
            } catch (e) {
                console.error("Polling error:", e);
            }
        }, 1200);
    }

    function stopPollingStatus() {
        if (POLLING_INTERVAL_ID) {
            clearInterval(POLLING_INTERVAL_ID);
            POLLING_INTERVAL_ID = null;
        }
        IS_BUILDING = false;
        elProgressBlock.classList.add("hidden");
        elBtnGateAction.disabled = false;
    }

    // Flowchart UI dynamic updates matching pipeline milestones
    function updatePipelineMap(progress) {
        const nStory = document.getElementById("node-story");
        const nScene = document.getElementById("node-scene");
        const nDirector = document.getElementById("node-director");
        const nCine = document.getElementById("node-cinematography");
        const nSound = document.getElementById("node-sound");
        const nCompile = document.getElementById("node-compile");
        
        // Reset everything first
        [nStory, nScene, nDirector, nCine, nSound, nCompile].forEach(n => {
            n.classList.remove("active", "completed");
        });
        
        if (progress > 0 && progress < 25) {
            nStory.classList.add("active");
        } else if (progress >= 25 && progress < 45) {
            nStory.classList.add("completed");
            nScene.classList.add("active");
        } else if (progress >= 45 && progress < 65) {
            nStory.classList.add("completed");
            nScene.classList.add("completed");
            nDirector.classList.add("active");
        } else if (progress >= 65 && progress < 82) {
            nStory.classList.add("completed");
            nScene.classList.add("completed");
            nDirector.classList.add("completed");
            nCine.classList.add("active");
        } else if (progress >= 82 && progress < 91) {
            nStory.classList.add("completed");
            nScene.classList.add("completed");
            nDirector.classList.add("completed");
            nCine.classList.add("completed");
            nSound.classList.add("active");
        } else if (progress >= 91 && progress <= 100) {
            nStory.classList.add("completed");
            nScene.classList.add("completed");
            nDirector.classList.add("completed");
            nCine.classList.add("completed");
            nSound.classList.add("completed");
            nCompile.classList.add("active");
            if (progress === 100) {
                nCompile.classList.add("completed");
            }
        }
    }

    // 6. Load Project JSON Assets to render Screenplay, Storyboard cards, timelines
    async function loadProjectAssets(projectId, episodeNo) {
        try {
            const res = await fetch(`/api/projects/${projectId}/assets?episode_no=${episodeNo}`);
            const assets = await res.json();
            
            // A. RENDER STORY TAB
            if (assets.story) {
                CURRENT_STORY_DATA = assets.story; // Cache story locally
                
                // Add warning/hint banner if it doesn't exist
                let hintEl = document.getElementById("story-edit-hint");
                if (!hintEl) {
                    hintEl = document.createElement("div");
                    hintEl.id = "story-edit-hint";
                    hintEl.style.cssText = "margin-bottom: 16px; padding: 10px 14px; background: rgba(99, 102, 241, 0.1); border-left: 4px solid #6366f1; border-radius: 4px; font-size: 0.85rem; color: #e2e8f0; display: flex; align-items: center; gap: 8px;";
                    hintEl.innerHTML = "<span>💡 <strong>편집 가능:</strong> 제목, 시놉시스, 극적 반전, 복선, 등장인물 카드 안의 텍스트를 클릭해 직접 수정한 후 아래 [기획 승인] 버튼을 누르면 수정안이 그대로 적용됩니다.</span>";
                    elStoryTitle.parentNode.insertBefore(hintEl, elStorySynopsis);
                }

                elStoryTitle.innerText = assets.story.title;
                elStoryTitle.contentEditable = "true";
                elStoryTitle.style.borderBottom = "1px dashed rgba(255,255,255,0.2)";
                elStoryTitle.style.paddingBottom = "4px";
                elStoryTitle.addEventListener("blur", () => {
                    CURRENT_STORY_DATA.title = elStoryTitle.innerText.trim();
                });

                elStorySynopsis.innerText = assets.story.synopsis;
                elStorySynopsis.contentEditable = "true";
                elStorySynopsis.style.border = "1px dashed rgba(255,255,255,0.15)";
                elStorySynopsis.style.padding = "8px";
                elStorySynopsis.style.borderRadius = "4px";
                elStorySynopsis.addEventListener("blur", () => {
                    CURRENT_STORY_DATA.synopsis = elStorySynopsis.innerText.trim();
                });
                
                // Twists
                elStoryTwists.innerHTML = "";
                assets.story.twists.forEach((t, index) => {
                    const li = document.createElement("li");
                    li.innerText = t;
                    li.contentEditable = "true";
                    li.style.borderBottom = "1px dashed rgba(255,255,255,0.1)";
                    li.style.paddingBottom = "2px";
                    li.style.marginBottom = "6px";
                    li.style.cursor = "text";
                    li.addEventListener("blur", () => {
                        CURRENT_STORY_DATA.twists[index] = li.innerText.trim();
                    });
                    elStoryTwists.appendChild(li);
                });
                
                // Foreshadowing
                elStoryForeshadow.innerHTML = "";
                const foreshadowList = assets.story.foreshadowing || assets.story.foreshadow || [];
                foreshadowList.forEach((f, index) => {
                    const li = document.createElement("li");
                    li.innerText = f;
                    li.contentEditable = "true";
                    li.style.borderBottom = "1px dashed rgba(255,255,255,0.1)";
                    li.style.paddingBottom = "2px";
                    li.style.marginBottom = "6px";
                    li.style.cursor = "text";
                    li.addEventListener("blur", () => {
                        if (!CURRENT_STORY_DATA.foreshadowing) {
                            CURRENT_STORY_DATA.foreshadowing = [];
                        }
                        CURRENT_STORY_DATA.foreshadowing[index] = li.innerText.trim();
                        CURRENT_STORY_DATA.foreshadow = CURRENT_STORY_DATA.foreshadowing;
                    });
                    elStoryForeshadow.appendChild(li);
                });
                
                // Character dossier cards
                elCharactersGrid.innerHTML = "";
                assets.story.characters.forEach((c, index) => {
                    const card = document.createElement("div");
                    card.className = "character-card";
                    
                    const avatarText = c.name ? c.name.charAt(0) : "?";
                    card.innerHTML = `
                        <div class="char-avatar-sim">${avatarText}</div>
                        <div class="char-details">
                            <h4>
                                <span class="edit-char-name" contenteditable="true" style="border-bottom: 1px dashed rgba(255,255,255,0.2); padding-right: 4px; cursor: text;">${c.name}</span>
                                <span class="char-role-badge" contenteditable="true" style="cursor: text;">${c.role}</span>
                            </h4>
                            <p class="char-desc"><strong>성격 :</strong> <span class="edit-char-personality" contenteditable="true" style="border-bottom: 1px dashed rgba(255,255,255,0.1); display: inline-block; width: 80%; cursor: text;">${c.personality}</span></p>
                            <p class="char-appearance"><strong>외모 :</strong> <span class="edit-char-appearance" contenteditable="true" style="border-bottom: 1px dashed rgba(255,255,255,0.1); display: inline-block; width: 80%; cursor: text;">${c.appearance}</span></p>
                        </div>
                    `;
                    
                    const nameEl = card.querySelector(".edit-char-name");
                    const roleEl = card.querySelector(".char-role-badge");
                    const personalityEl = card.querySelector(".edit-char-personality");
                    const appearanceEl = card.querySelector(".edit-char-appearance");
                    
                    nameEl.addEventListener("blur", () => {
                        CURRENT_STORY_DATA.characters[index].name = nameEl.innerText.trim();
                        card.querySelector(".char-avatar-sim").innerText = nameEl.innerText.trim().charAt(0) || "?";
                    });
                    roleEl.addEventListener("blur", () => {
                        CURRENT_STORY_DATA.characters[index].role = roleEl.innerText.trim();
                    });
                    personalityEl.addEventListener("blur", () => {
                        CURRENT_STORY_DATA.characters[index].personality = personalityEl.innerText.trim();
                    });
                    appearanceEl.addEventListener("blur", () => {
                        CURRENT_STORY_DATA.characters[index].appearance = appearanceEl.innerText.trim();
                    });
                    
                    elCharactersGrid.appendChild(card);
                });
            } else {
                CURRENT_STORY_DATA = null;
                elStoryTitle.innerText = "기획 정보 로드 대기 중";
                elStorySynopsis.innerText = "프로젝트 컴파일을 시작하여 기획서를 활성화하세요.";
                elCharactersGrid.innerHTML = '<div class="no-data-msg">등록된 인물이 없습니다.</div>';
            }
            
            // B. RENDER SCREENPLAY SCRIPTS (Hollywood standard)
            if (assets.scenes && assets.director) {
                elScriptMovieTitle.innerText = assets.story ? assets.story.title.toUpperCase() : "CINEMA";
                elScriptEpisodeTitle.innerText = `제 ${episodeNo}화 시나리오 스크립트`;
                
                elScreenplayBody.innerHTML = "";
                assets.scenes.scenes.forEach(sc => {
                    const dScene = assets.director.scenes.find(d => d.scene_no === sc.scene_no);
                    
                    const block = document.createElement("div");
                    block.className = "screenplay-scene-block";
                    
                    // Slugline
                    const slugline = document.createElement("div");
                    slugline.className = "scene-heading";
                    slugline.innerText = `씬 ${sc.scene_no}. ${sc.location} - ${sc.time}`;
                    block.appendChild(slugline);
                    
                    // Action directions
                    const direction = document.createElement("div");
                    direction.className = "scene-direction";
                    direction.innerText = sc.storyline;
                    block.appendChild(direction);
                    
                    // Director visual styles annotations
                    if (dScene) {
                        const annotation = document.createElement("div");
                        annotation.className = "director-style-annotation";
                        annotation.innerHTML = `
                            <strong>[감독 연출 지시 - Style: ${dScene.pacing.toUpperCase()} PACE]</strong><br>
                            ${dScene.directorial_style} (색감 톤앤매너: ${dScene.color_palette})
                        `;
                        block.appendChild(annotation);
                    }
                    
                    // Speaker Dialogue blocks
                    const dialogueBlock = document.createElement("div");
                    dialogueBlock.className = "screenplay-dialogue-block";
                    
                    // Parse speakers if any
                    let speaker = "NARRATOR";
                    let text = sc.narration;
                    if (sc.narration.includes(":")) {
                        const s_parts = sc.narration.split(":", 1);
                        speaker = s_parts[0].trim();
                        text = sc.narration.replace(speaker + ":", "").trim();
                    }
                    
                    dialogueBlock.innerHTML = `
                        <div class="script-speaker">${speaker}</div>
                        <div class="script-dialogue">${text}</div>
                    `;
                    block.appendChild(dialogueBlock);
                    
                    elScreenplayBody.appendChild(block);
                });
            } else {
                elScreenplayBody.innerHTML = '<div class="no-data-msg">에피소드 시나리오가 아직 작성되지 않았습니다.</div>';
            }
            
            // C. RENDER STORYBOARD GRID WITH AUDIO CHANNELS
            if (assets.cinematography) {
                elStoryboardGallery.innerHTML = "";
                assets.cinematography.shots.forEach(sh => {
                    const card = document.createElement("div");
                    card.className = "storyboard-card";
                    
                    // Path to static storyboard png
                    const imgUrl = `/projects_assets/${projectId}/storyboards/${sh.shot_id}_storyboard.png`;
                    // Path to static narration mp3/wav
                    const audioUrl = `/projects_assets/${projectId}/audio_tts/${sh.shot_id}_narration.mp3`;
                    
                    card.innerHTML = `
                        <div class="card-img-wrapper">
                            <img src="${imgUrl}" alt="${sh.shot_id} storyboard" class="card-img" onerror="this.src='https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=800&auto=format&fit=crop&q=60'">
                            <span class="card-angle-badge badge">${sh.camera_angle}</span>
                        </div>
                        <div class="card-info">
                            <div class="card-header-flex">
                                <span class="card-id-text">${sh.shot_id}</span>
                                <span class="card-duration-text"><i data-lucide="clock" style="width:12px;display:inline;"></i> ${sh.estimated_duration.toFixed(1)}초</span>
                            </div>
                            <p class="card-comp-text">${sh.composition}</p>
                            
                            <div class="shot-audio-btn-wrapper">
                                <audio controls class="mini-audio-player">
                                    <source src="${audioUrl}" type="audio/mpeg">
                                    <source src="${audioUrl.replace('.mp3', '.wav')}" type="audio/wav">
                                </audio>
                            </div>
                        </div>
                    `;
                    elStoryboardGallery.appendChild(card);
                });
                lucide.createIcons();
            } else {
                elStoryboardGallery.innerHTML = '<div class="no-data-msg">스토리보드가 매핑되지 않았습니다. 지휘소에서 승인 전진을 행해 주세요.</div>';
            }
            
            // D. RENDER AUDIO MIXER TIMELINE GRID
            if (assets.cinematography && assets.sound) {
                elMixerTimelineGrid.innerHTML = "";
                
                assets.cinematography.shots.forEach(sh => {
                    const m_track = assets.sound.music_tracks.find(m => m.shot_id === sh.shot_id);
                    const s_track = assets.sound.sfx_effects.find(s => s.shot_id === sh.shot_id);
                    
                    const row = document.createElement("div");
                    row.className = "mixer-shot-row";
                    
                    // Meta
                    const metaBlock = document.createElement("div");
                    metaBlock.className = "mixer-shot-meta";
                    metaBlock.innerHTML = `
                        <h4>${sh.shot_id}</h4>
                        <span>${sh.estimated_duration.toFixed(1)}s (${sh.camera_angle})</span>
                    `;
                    row.appendChild(metaBlock);
                    
                    // Music Channel (BGM)
                    const bgm_style = m_track ? m_track.bgm_style.toUpperCase() : "NONE";
                    const bgm_vol = m_track ? m_track.volume * 100 : 0;
                    
                    const musicChan = document.createElement("div");
                    musicChan.className = "mixer-channel";
                    musicChan.innerHTML = `
                        <div class="channel-label">
                            <span>BGM: ${bgm_style}</span>
                            <span>Vol: ${bgm_vol.toFixed(0)}%</span>
                        </div>
                        <div class="channel-track-bar">
                            <div class="channel-track-fill music" style="width: ${bgm_vol}%"></div>
                        </div>
                    `;
                    row.appendChild(musicChan);
                    
                    // SFX Channel
                    const sfx_type = s_track ? s_track.sfx_type.toUpperCase() : "NONE";
                    const sfx_vol = s_track ? s_track.volume * 100 : 0;
                    const offset_percent = s_track ? (s_track.timing_offset / sh.estimated_duration) * 100 : 0;
                    
                    const sfxChan = document.createElement("div");
                    sfxChan.className = "mixer-channel";
                    sfxChan.innerHTML = `
                        <div class="channel-label">
                            <span>SFX: ${sfx_type}</span>
                            <span>Vol: ${sfx_vol.toFixed(0)}%</span>
                        </div>
                        <div class="channel-track-bar">
                            <div class="channel-track-fill sfx" style="width: ${sfx_vol}%"></div>
                            ${s_track && s_track.sfx_type !== "none" ? `<div class="sfx-offset-marker" style="left: ${offset_percent}%" title="Trigger offset: ${s_track.timing_offset}s"></div>` : ""}
                        </div>
                    `;
                    row.appendChild(sfxChan);
                    
                    elMixerTimelineGrid.appendChild(row);
                });
            } else {
                elMixerTimelineGrid.innerHTML = '<div class="no-data-msg">오디오 믹싱 타임라인 가이드 데이터가 아직 기획되지 않았습니다.</div>';
            }
            
            // E. LOAD THEATER SCREEN PLAYER (MP4 Stream)
            const videoUrl = `/projects_assets/${projectId}/videos/episode_${episodeNo}.mp4`;
            
            // Check if this compiled video already exists using HEAD check
            try {
                const vid_check = await fetch(videoUrl, { method: 'HEAD' });
                if (vid_check.ok) {
                    elPlayerIdleCard.style.display = "none";
                    elVideoPlayer.style.display = "block";
                    elVideoPlayer.src = videoUrl;
                    
                    elTheaterMovieTitle.innerText = assets.story ? `${assets.story.title}` : "영화 상영 룸";
                    elTheaterEpisodeBadge.innerText = `제 ${episodeNo}화 극장판`;
                    elBtnDownloadVideo.style.display = "inline-flex";
                    elBtnDownloadVideo.href = videoUrl;
                    
                    syncScreenGlowColor(assets.story ? assets.story.genre_id : "drama");
                } else {
                    showVideoPlaceholder();
                }
            } catch (e) {
                showVideoPlaceholder();
            }
            
        } catch (e) {
            console.error("Error loading project assets:", e);
        }
    }

    function showVideoPlaceholder() {
        elPlayerIdleCard.style.display = "flex";
        elVideoPlayer.style.display = "none";
        elVideoPlayer.src = "";
        elTheaterMovieTitle.innerText = "상영 대기 중";
        elTheaterEpisodeBadge.innerText = "EPISODE BUILD REQUIRED";
        elBtnDownloadVideo.style.display = "none";
        elScreenGlow.style.background = "rgba(138, 43, 226, 0.08)";
    }

    function syncScreenGlowColor(genreId) {
        const colors = {
            "action": "rgba(239, 68, 68, 0.25)",      // Neon Red
            "thriller": "rgba(0, 242, 254, 0.25)",    // Neon Blue
            "sf": "rgba(168, 85, 247, 0.25)",         // Violet
            "drama": "rgba(245, 158, 11, 0.22)",      // Amber
            "horror": "rgba(16, 185, 129, 0.22)"       // Ghostly Green
        };
        elScreenGlow.style.background = colors[genreId] || "rgba(138, 43, 226, 0.25)";
    }

    function resetStudioBoard() {
        showVideoPlaceholder();
        elStoryTitle.innerText = "기획 정보 로드 대기 중";
        elStorySynopsis.innerText = "좌측 제어판에서 시나리오를 구상하고 새 프로젝트를 기획하세요.";
        elCharactersGrid.innerHTML = '<div class="no-data-msg">등록된 인물이 없습니다.</div>';
        elScreenplayBody.innerHTML = '<div class="no-data-msg">에셋 정보가 존재하지 않습니다.</div>';
        elStoryboardGallery.innerHTML = '<div class="no-data-msg">생성된 스토리보드가 없습니다.</div>';
        elMixerTimelineGrid.innerHTML = '<div class="no-data-msg">오디오 믹서 정보가 없습니다.</div>';
    }

    // Refresh trigger
    elBtnRefresh.addEventListener("click", () => {
        if (CURRENT_PROJECT_ID) {
            syncStateWithBackend();
            loadProjectAssets(CURRENT_PROJECT_ID, elEpisodeSelect.value);
            addTerminalLine("[SYSTEM]: 수동 리로드 에셋 및 상태 동기화 완료.", "success");
        } else {
            fetchProjectList();
        }
    });

    // Delete Project trigger
    elBtnDeleteProject.addEventListener("click", async () => {
        if (!CURRENT_PROJECT_ID) return;
        
        const confirmDelete = confirm("⚠️ 경고: 정말로 이 프로젝트와 이에 포함된 모든 에피소드 시나리오, 스토리보드, 제작된 비디오 클립을 영구 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.");
        if (!confirmDelete) return;
        
        elBtnDeleteProject.disabled = true;
        addTerminalLine(`[SYSTEM]: 프로젝트 '${CURRENT_PROJECT_ID}' 영구 소거 작업 시작...`);
        
        try {
            const res = await fetch(`/api/projects/${CURRENT_PROJECT_ID}`, {
                method: "DELETE"
            });
            const data = await res.json();
            
            addTerminalLine(`[SYSTEM]: ${data.message}`, "success");
            
            // Clean up states and UI
            CURRENT_PROJECT_ID = null;
            elEpisodeBlock.classList.add("disabled");
            elBtnDeleteProject.disabled = true;
            resetStudioBoard();
            
            // Reload select dropdown
            await fetchProjectList();
            
        } catch (e) {
            addTerminalLine(`[ERROR]: 프로젝트 삭제 실패: ${e}`, "failed");
            elBtnDeleteProject.disabled = false;
        }
    });

    // Episode selection change triggers immediate status & asset switch
    elEpisodeSelect.addEventListener("change", () => {
        if (CURRENT_PROJECT_ID) {
            syncStateWithBackend();
            loadProjectAssets(CURRENT_PROJECT_ID, elEpisodeSelect.value);
        }
    });
});
