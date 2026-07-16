import os
import math
import random
import struct
import wave
import subprocess
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
import imageio_ffmpeg
from config import get_project_paths, DEFAULT_SFX, DEFAULT_BGM, CAMERA_ANGLES, GEMINI_API_KEY, GEMINI_IMAGE_MODEL

# Try to load Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    HAS_GENAI_SDK = True
except ImportError:
    HAS_GENAI_SDK = False

# Find static ffmpeg path
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

# =====================================================================
# MATHEMATICAL AUDIO SYNTHESIZERS (Zero-Config Sound Engine)
# =====================================================================

def write_wav_file(filepath: str, samplerate: int, samples: list[float]):
    """
    Saves float audio samples (-1.0 to 1.0) into a standard 16-bit PCM mono WAV file.
    """
    with wave.open(filepath, 'wb') as wav:
        wav.setnchannels(1)  # Mono
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(samplerate)
        
        # Convert float to 16-bit signed integer bytes
        binary_data = b""
        for s in samples:
            # Clamp to prevent overflow
            s = max(-1.0, min(1.0, s))
            val = int(s * 32767)
            binary_data += struct.pack('<h', val)
            
        wav.writeframes(binary_data)


def synthesize_sfx(sfx_type: str, filepath: str, duration: float = 3.0):
    """
    Programmatically generates highly realistic cinematic sound effects using math equations.
    """
    sr = 22050
    num_samples = int(sr * duration)
    samples = [0.0] * num_samples
    
    if sfx_type == "rain_ambient":
        # Pinkish/White noise with low-pass filtering for soothing rainfall
        prev = 0.0
        for i in range(num_samples):
            white = random.uniform(-1.0, 1.0)
            # Low pass filter formula (leaky integrator) to remove harsh high frequencies
            samples[i] = 0.12 * white + 0.88 * prev
            prev = samples[i]
            
    elif sfx_type == "door_open":
        # Step 1: Wood creaking pulses (frequency-modulated sweeps)
        for i in range(int(sr * 1.5)):
            t = i / sr
            # Pulse density slows down over time
            pulse_rate = 25 - 12 * t
            pulse = math.sin(2.0 * math.pi * pulse_rate * t)
            if pulse > 0.95:
                # Creak chirp
                chirp_freq = 600 - 200 * t
                samples[i] = 0.45 * math.sin(2.0 * math.pi * chirp_freq * t) * (1.5 - t)
        # Step 2: Door latched click at 1.5s
        click_idx = int(sr * 1.4)
        for i in range(click_idx, min(num_samples, click_idx + int(sr * 0.4))):
            t = (i - click_idx) / sr
            decay = math.exp(-25 * t)
            samples[i] += 0.7 * random.uniform(-1.0, 1.0) * decay
            samples[i] += 0.4 * math.sin(2.0 * math.pi * 95 * t) * decay
            
    elif sfx_type == "sword_clash":
        # Sharp high-frequency ringing with fast decay + noise transient
        clash_freqs = [1800, 2200, 2750, 3100]
        for i in range(num_samples):
            t = i / sr
            decay = math.exp(-6.5 * t)
            # Metallic frequency components
            wave_val = sum(math.sin(2.0 * math.pi * f * t) for f in clash_freqs) / len(clash_freqs)
            # Initial spark burst (noise) in first 0.05 seconds
            noise = random.uniform(-1.0, 1.0) * math.exp(-95 * t)
            samples[i] = (0.6 * wave_val + 0.4 * noise) * decay
            
    elif sfx_type == "footsteps":
        # 3 periodic low-frequency muffled thuds
        step_interval = 0.8
        for step in range(3):
            start_idx = int(sr * step * step_interval)
            for i in range(start_idx, min(num_samples, start_idx + int(sr * 0.25))):
                t = (i - start_idx) / sr
                decay = math.exp(-18 * t)
                # Muffled sound: 75Hz sine wave with low frequency rumble
                samples[i] = 0.75 * math.sin(2.0 * math.pi * 75 * t) * decay
                
    elif sfx_type == "thunder":
        # Deep rumble: bandpass-filtered noise with massive initial burst and slow decay
        rumble_duration = duration
        prev = 0.0
        for i in range(num_samples):
            t = i / sr
            envelope = math.exp(-1.5 * t) * (1.0 + 0.3 * math.sin(2.0 * math.pi * 6 * t))
            white = random.uniform(-1.0, 1.0)
            # Heavy low-pass filtering around 50Hz - 150Hz
            filt_noise = 0.04 * white + 0.96 * prev
            prev = filt_noise
            samples[i] = filt_noise * envelope * 1.8
            
    elif sfx_type == "siren":
        # Oscillating police alert (500Hz to 900Hz sweeps over 1.5s period)
        for i in range(num_samples):
            t = i / sr
            sweep_freq = 700 + 200 * math.sin(2.0 * math.pi * 0.7 * t)
            samples[i] = 0.35 * math.sin(2.0 * math.pi * sweep_freq * t)
            
    else:
        # Generate absolute silence or very subtle ambient tape hiss
        for i in range(num_samples):
            samples[i] = random.uniform(-0.005, 0.005)
            
    write_wav_file(filepath, sr, samples)


def synthesize_bgm(bgm_style: str, filepath: str, duration: float = 15.0):
    """
    Generates rich, fully dynamic background music loops programmatically based on cinematic moods.
    """
    sr = 22050
    num_samples = int(sr * duration)
    samples = [0.0] * num_samples
    
    if bgm_style == "suspense":
        # Sinister low sub-drones + chilling ringing beeps at interval
        for i in range(num_samples):
            t = i / sr
            # Low sub drone (55Hz + 82.5Hz - perfect fifth interval)
            drone = 0.4 * math.sin(2.0 * math.pi * 55 * t) + 0.25 * math.sin(2.0 * math.pi * 82.5 * t)
            # Shivering slow pitch vibrato
            drone += 0.1 * math.sin(2.0 * math.pi * (110 + 2.0 * math.sin(2.0 * math.pi * 0.2 * t)) * t)
            
            # Ambient icy chime repeating every 3 seconds
            chime_t = t % 3.0
            chime_envelope = math.exp(-2.5 * chime_t)
            chime = 0.15 * math.sin(2.0 * math.pi * 1250 * chime_t) * chime_envelope
            
            samples[i] = drone + chime
            
    elif bgm_style == "action":
        # Heavy pulsating industrial synthwave (125 BPM base, 55Hz pulsing bass, arpeggios)
        bpm = 125
        beat_dur = 60.0 / bpm
        for i in range(num_samples):
            t = i / sr
            beat_idx = int(t / beat_dur)
            beat_t = t % beat_dur
            
            # Pulsing kick/bass sweep on every beat
            bass_env = math.exp(-12 * beat_t)
            bass = 0.35 * math.sin(2.0 * math.pi * 55 * beat_t) * bass_env
            
            # Rhythmic saw-tooth hats
            hat_env = math.exp(-45 * (t % (beat_dur / 2.0)))
            hat = 0.08 * random.uniform(-1.0, 1.0) * hat_env
            
            # Rising arpeggio (Minor key synth lead)
            notes = [110, 130.8, 164.8, 196] # Am7 notes (A, C, E, G)
            note_dur = beat_dur / 4.0
            arp_idx = int((t % beat_dur) / note_dur)
            arp_freq = notes[arp_idx % len(notes)]
            arp_env = math.exp(-8 * (t % note_dur))
            # Square wave for retro 16-bit texture
            arp = 0.15 * (1.0 if math.sin(2.0 * math.pi * arp_freq * t) > 0 else -1.0) * arp_env
            
            samples[i] = bass + hat + arp
            
    elif bgm_style == "sad":
        # Solitary sad piano progression: Am -> Dm -> G -> C (Slow tempo, soft sine waves)
        bpm = 60
        chord_dur = 4.0 # 4 seconds per chord
        for i in range(num_samples):
            t = i / sr
            chord_idx = int(t / chord_dur)
            chord_t = t % chord_dur
            
            # Choose root notes based on chords
            # Am (220, 261.6, 329.6), Dm (146.8, 293.7, 349.2), G (196, 246.9, 293.7), C (130.8, 261.6, 329.6)
            if chord_idx % 4 == 0:
                freqs = [220.0, 261.6, 329.6]
            elif chord_idx % 4 == 1:
                freqs = [146.8, 293.7, 349.2]
            elif chord_idx % 4 == 2:
                freqs = [196.0, 246.9, 293.7]
            else:
                freqs = [130.8, 261.6, 329.6]
                
            # Soft piano strike envelope
            envelope = math.exp(-1.5 * chord_t)
            piano = sum(0.18 * math.sin(2.0 * math.pi * f * chord_t) * envelope for f in freqs)
            
            # Add a higher emotional solo melody note
            mel_dur = chord_dur / 2.0
            mel_t = t % mel_dur
            mel_notes = [329.6, 392.0, 440.0, 523.3, 392.0, 329.6, 293.7, 261.6]
            mel_freq = mel_notes[int(t / mel_dur) % len(mel_notes)]
            mel_envelope = math.exp(-2.2 * mel_t)
            melody = 0.08 * math.sin(2.0 * math.pi * mel_freq * mel_t) * mel_envelope
            
            samples[i] = piano + melody
            
    elif bgm_style == "epic":
        # Grand heroic horn pads & low string chords (Sawtooth + rich brassy chorus)
        for i in range(num_samples):
            t = i / sr
            # Low strings (G major / Em progression)
            root_freq = 98.0 if int(t / 6.0) % 2 == 0 else 82.4
            fifths = root_freq * 1.5
            
            strings = 0.25 * math.sin(2.0 * math.pi * root_freq * t) + 0.18 * math.sin(2.0 * math.pi * fifths * t)
            
            # Rich brass melody: layered sawtooth waves with detuning
            horn_t = t % 4.0
            horn_envelope = 1.0 - math.exp(-3 * horn_t) if horn_t < 1.0 else math.exp(-1.2 * (horn_t - 1.0))
            horn_freq = 196.0 if int(t / 4.0) % 3 == 0 else (246.9 if int(t / 4.0) % 3 == 1 else 293.7)
            
            # detuned sawtooth brass representation
            saw1 = 0.12 * (2.0 * (horn_t * horn_freq - math.floor(horn_t * horn_freq + 0.5)))
            saw2 = 0.10 * (2.0 * (horn_t * (horn_freq * 1.01) - math.floor(horn_t * (horn_freq * 1.01) + 0.5)))
            horn = (saw1 + saw2) * horn_envelope
            
            samples[i] = strings + horn
    else:
        # Silence
        for i in range(num_samples):
            samples[i] = 0.0
            
    write_wav_file(filepath, sr, samples)

# =====================================================================
# CINEMATIC STORYBOARD RENDERING (PIL Library)
# =====================================================================

def create_storyboard_image(filepath: str, shot_id: str, scene_no: int, angle: str, composition: str, narration: str, mood: str, visual_prompt: str = ""):
    """
    Creates a widescreen card representing the storyboard shot. If GEMINI_API_KEY and visual_prompt
    are provided, it generates a photorealistic cinematic shot using Google's latest image model.
    Otherwise, it falls back to programmatically drawing abstract HUD/camera grids with PIL.
    """
    if HAS_GENAI_SDK and GEMINI_API_KEY and visual_prompt:
        try:
            print(f"[SYSTEM]: Calling Google GenAI {GEMINI_IMAGE_MODEL} for shot {shot_id}...")
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            # Enrich prompt with camera angle & composition rules for extreme cinematic coherence
            enriched_prompt = f"Cinematic film frame, high production value scene, masterfully shot, {visual_prompt}"
            if angle:
                enriched_prompt += f", {angle} shot angle"
            if composition:
                enriched_prompt += f", framing: {composition}"
            if mood:
                enriched_prompt += f", {mood} mood lighting and high-contrast color grading"
                
            response = client.models.generate_content(
                model=GEMINI_IMAGE_MODEL,
                contents=enriched_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio="16:9"
                    )
                )
            )
            
            saved = False
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    with open(filepath, "wb") as f:
                        f.write(image_bytes)
                    print(f"[SYSTEM]: Successfully generated AI cinematic frame for {shot_id}!")
                    saved = True
                    break
            
            if saved:
                
                # Draw movie subtitles & HUD overlay on top of the real AI image
                try:
                    img = Image.open(filepath)
                    draw = ImageDraw.Draw(img)
                    width, height = img.size
                    
                    # Subtle letterboxes (dark overlays) for high-contrast subtitle legibility
                    # Top & Bottom black letterboxes
                    draw.rectangle([(0, 0), (width, 80)], fill="black")
                    draw.rectangle([(0, height - 100), (width, height)], fill="black")
                    
                    # High-tech shot metadata HUD box in top left
                    draw.rectangle([(50, 20), (320, 65)], fill=(10, 10, 20), outline="#22d3ee", width=1)
                    draw.text((65, 28), f"CUT: {shot_id} | SCENE: {scene_no:02d}", fill="white")
                    
                    # Render cinematic yellow narration subtitles centered on bottom letterbox
                    sub_text = narration if narration else "..."
                    # Simple text wrapper for readability
                    if len(sub_text) > 70:
                        sub_text_wrapped = sub_text[:70] + "...\n" + sub_text[70:]
                    else:
                        sub_text_wrapped = sub_text
                    
                    draw.text((width // 2, height - 50), sub_text_wrapped, fill="#facc15", anchor="mm")
                    img.save(filepath)
                    return # Return early on success!
                except Exception as e_overlay:
                    print(f"HUD overlay failed: {e_overlay}, saving raw image.")
                    return # Return early on success!
        except Exception as e:
            print(f"[ERROR]: Google GenAI Image generation failed: {e}. Falling back to PIL drawing.")

    # FALLBACK: 1920x1080 Full HD Canvas programmatical drawing
    width, height = 1920, 1080
    img = Image.new("RGB", (width, height), "#06070a")
    draw = ImageDraw.Draw(img)
    
    # Render premium gradient background
    # Set gradient colors based on mood
    c1, c2 = (15, 23, 42), (8, 47, 73) # Slate Blue / Dark Cyan (Suspense)
    if mood == "action":
        c1, c2 = (30, 9, 9), (15, 23, 42) # Crimson Dark / Charcoal
    elif mood == "sad":
        c1, c2 = (17, 24, 39), (28, 25, 23) # Grey Space / Stone Brown
    elif mood == "horror":
        c1, c2 = (14, 116, 144), (2, 43, 58) # Deep Violet Magenta
        c1, c2 = (22, 10, 32), (6, 5, 10)
        
    for y in range(height):
        ratio = y / height
        r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
        g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
        b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
        
    # Draw Movie Letterboxes (Cinematic Black Bars)
    draw.rectangle([(0, 0), (width, 100)], fill="black")
    draw.rectangle([(0, height - 120), (width, height)], fill="black")
    
    # Glowing Frame border (Glassmorphism effect)
    border_color = "#22d3ee" if mood == "suspense" else ("#ef4444" if mood == "action" else "#a855f7")
    draw.rectangle([(40, 120), (width - 40, height - 140)], outline=border_color, width=3)
    
    # Geometric drawings removed per user request (keeps fallback placeholder clean and minimalist!)
    pass
        
    # Typography details
    try:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
    except Exception:
        font_title = None
        font_sub = None
        
    # Draw Info badges
    # Since load_default() fonts are tiny on 1080p, we draw larger structured bounding blocks
    # Draw dark overlay bars for readable labels
    draw.rectangle([(60, 140), (400, 260)], fill=(0, 0, 0, 160), outline=border_color, width=1)
    draw.text((80, 155), f"CUT ID : {shot_id}", fill="white")
    draw.text((80, 185), f"ANGLE : {angle} ANGLE", fill=border_color)
    draw.text((80, 215), f"SCENE : {scene_no:02d}", fill="white")
    
    # Draw Composition label in bottom box
    draw.rectangle([(60, height - 260), (width - 60, height - 160)], fill=(0, 0, 0, 180), outline=(255, 255, 255, 20), width=1)
    draw.text((80, height - 240), f"[연출/카메라 구도]", fill=border_color)
    draw.text((80, height - 210), composition, fill="white")
    
    # Draw Dialogue subtitle inside the black bar at the very bottom
    # Text wrapping if long
    sub_text = narration if narration else "..."
    if len(sub_text) > 65:
        sub_text_wrapped = sub_text[:65] + "\n" + sub_text[65:]
    else:
        sub_text_wrapped = sub_text
        
    draw.text((width // 2, height - 80), sub_text_wrapped, fill="yellow", anchor="mm")
    
    # Save image
    img.save(filepath)

# =====================================================================
# MODULAR VIDEO COMPILATION & SYNTHESIS PIPELINE
# =====================================================================

class SynthesisPipeline:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.paths = get_project_paths(project_id)
        
    def generate_narration_audio(self, shot_id: str, text: str) -> str:
        """
        Synthesizes Korean voiceover dialogue for a shot using Google TTS and returns its file path.
        """
        filename = f"{shot_id}_narration.mp3"
        filepath = os.path.join(self.paths["audio_tts"], filename)
        
        # Strip narrator prefix e.g. "강진혁: " for clean sound
        clean_text = text
        if ":" in text:
            clean_text = text.split(":", 1)[1].strip()
        clean_text = clean_text.replace("'", "").replace('"', "")
        
        if not clean_text or clean_text == "...":
            # If no narration, generate silent wav
            write_wav_file(filepath.replace(".mp3", ".wav"), 22050, [0.0] * int(22050 * 2.0))
            return filepath.replace(".mp3", ".wav")
            
        try:
            tts = gTTS(text=clean_text, lang='ko')
            tts.save(filepath)
        except Exception as e:
            # TTS failed, fallback to programmatically synthesized silence (3s) to prevent breaking
            print(f"gTTS failed for {shot_id}: {e}. Creating fallback WAV silence.")
            filepath = filepath.replace(".mp3", ".wav")
            write_wav_file(filepath, 22050, [0.0] * int(22050 * 3.0))
            
        return filepath

    def get_audio_duration(self, filepath: str) -> float:
        """
        Retrieves the exact duration in seconds of an audio file using FFprobe.
        """
        # Call ffprobe statically
        ffprobe_exe = FFMPEG_EXE.replace("ffmpeg", "ffprobe")
        if not os.path.exists(ffprobe_exe):
            # Fallback estimation if ffprobe not packaged
            if filepath.endswith(".wav"):
                try:
                    with wave.open(filepath, 'r') as w:
                        frames = w.getnframes()
                        rate = w.getframerate()
                        return frames / float(rate)
                except Exception:
                    pass
            # standard fallback duration
            return 4.0
            
        try:
            cmd = [
                ffprobe_exe, "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", filepath
            ]
            output = subprocess.check_output(cmd).decode().strip()
            return float(output)
        except Exception:
            return 4.5

    def compile_single_shot(self, shot: dict, narration_text: str, mood: str, sfx_type: str, sfx_volume: float, sfx_offset: float) -> str:
        """
        Stage 1: Compiles a single self-contained MP4 video cut for a single shot.
        Locks image slide, TTS sound, and overlaid SFX in precise synchrony!
        """
        shot_id = shot["shot_id"]
        img_filename = f"{shot_id}_storyboard.png"
        img_path = os.path.join(self.paths["storyboards"], img_filename)
        
        # 1. Create storyboard image (if not already pre-generated in Stage 3)
        if not os.path.exists(img_path):
            create_storyboard_image(
                filepath=img_path,
                shot_id=shot_id,
                scene_no=shot["scene_no"],
                angle=shot["camera_angle"],
                composition=shot["composition"],
                narration=narration_text,
                mood=mood,
                visual_prompt=shot.get("visual_prompt", "")
            )
        
        # 2. Create TTS voiceover
        tts_path = self.generate_narration_audio(shot_id, narration_text)
        tts_dur = self.get_audio_duration(tts_path)
        
        # 3. Dynamic Duration Synced to Voice length
        # Keep shot open for at least estimated_duration or voiceover length + pad
        shot_dur = max(float(shot["estimated_duration"]), tts_dur + 0.8)
        
        # 4. Generate local SFX file
        sfx_path = os.path.join(self.paths["audio_sfx"], f"{shot_id}_sfx.wav")
        synthesize_sfx(sfx_type, sfx_path, duration=shot_dur)
        
        # 5. Build Mixed Audio for the Cut (TTS + SFX at offset)
        mixed_audio_path = os.path.join(self.paths["temp"], f"{shot_id}_mixed.wav")
        
        # Construct FFmpeg Audio overlay command
        # -i [TTS] -i [SFX] -filter_complex "[1:a]volume={sfx_volume}[sfx];[0:a][sfx]adelay={offset_ms}|{offset_ms}[delayed_sfx];[delayed_sfx][0:a]amix=inputs=2:duration=first"
        offset_ms = int(sfx_offset * 1000)
        
        # Clean audio paths
        tts_input = tts_path.replace("\\", "/")
        sfx_input = sfx_path.replace("\\", "/")
        mixed_output = mixed_audio_path.replace("\\", "/")
        
        audio_filter = f"[1:a]volume={sfx_volume:.2f}[sfx];[0:a][sfx]adelay={offset_ms}|{offset_ms}[delayed_sfx];[0:a][delayed_sfx]amix=inputs=2:duration=first"
        if sfx_type == "none" or sfx_volume <= 0.0:
            audio_filter = f"[0:a]volume=1.0"
            
        cmd_audio = [
            FFMPEG_EXE, "-y",
            "-i", tts_input,
            "-i", sfx_input,
            "-filter_complex", audio_filter,
            "-ac", "1", "-ar", "22050",
            mixed_output
        ]
        
        # Execute Audio Mix
        subprocess.run(cmd_audio, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not os.path.exists(mixed_audio_path):
            # Fallback to copy TTS directly if mix fails
            mixed_audio_path = tts_path
            
        # 6. Compile Slide Image and Mixed Audio into single MP4 Cut
        shot_video_path = os.path.join(self.paths["temp"], f"{shot_id}_cut.mp4")
        
        # FFmpeg render image loop matched with audio duration
        cmd_video = [
            FFMPEG_EXE, "-y",
            "-loop", "1", "-i", img_path.replace("\\", "/"),
            "-i", mixed_audio_path.replace("\\", "/"),
            "-c:v", "libx264", "-t", f"{shot_dur:.2f}",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            shot_video_path.replace("\\", "/")
        ]
        
        subprocess.run(cmd_video, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return shot_video_path

    def compile_full_episode(self, episode_no: int, shots: list[dict], scenes: list[dict], sound: dict, genre_id: str) -> str:
        """
        Stage 2: Merges all compiled single shot cuts sequentially into a single video,
        synthesizes/loops background music, and mixes with selective volume envelopes.
        """
        episode_video_path = os.path.join(self.paths["videos"], f"episode_{episode_no}.mp4")
        
        # 1. Compile all individual shots
        shot_files = []
        total_duration = 0.0
        
        for shot in shots:
            shot_id = shot["shot_id"]
            scene = next((sc for sc in scenes if sc["scene_no"] == shot["scene_no"]), None)
            narration = scene["narration"] if scene else "..."
            mood = "suspense"
            
            # Extract sfx and music parameters mapped by Sound Agent
            sfx_cue = next((s for s in sound["sfx_effects"] if s["shot_id"] == shot_id), None)
            sfx_type = sfx_cue["sfx_type"] if sfx_cue else "none"
            sfx_vol = sfx_cue["volume"] if sfx_cue else 0.0
            sfx_offset = sfx_cue["timing_offset"] if sfx_cue else 0.0
            
            cut_video = self.compile_single_shot(
                shot=shot,
                narration_text=narration,
                mood=mood,
                sfx_type=sfx_type,
                sfx_volume=sfx_vol,
                sfx_offset=sfx_offset
            )
            shot_files.append(cut_video)
            
            # calculate total duration of compiled cuts
            total_duration += self.get_audio_duration(cut_video)
            
        if not shot_files:
            raise ValueError("No compiled shot video cuts available for compilation.")
            
        # 2. Concatenate all compiled shots into a single draft video
        concat_txt_path = os.path.join(self.paths["temp"], "concat_list.txt")
        with open(concat_txt_path, "w", encoding="utf-8") as f:
            for s_file in shot_files:
                f.write(f"file '{s_file.replace('\\', '/')}'\n")
                
        draft_video_path = os.path.join(self.paths["temp"], "draft_concatenated.mp4")
        cmd_concat = [
            FFMPEG_EXE, "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_txt_path.replace("\\", "/"),
            "-c", "copy",
            draft_video_path.replace("\\", "/")
        ]
        subprocess.run(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 3. Generate master Background Music (BGM) of exact matching duration
        bgm_style_master = {
            "action": "action",
            "thriller": "suspense",
            "sf": "suspense",
            "drama": "sad",
            "horror": "suspense"
        }.get(genre_id, "suspense")
        
        # Sound agent details
        music_cue = next((m for m in sound["music_tracks"] if m["shot_id"] == shots[0]["shot_id"]), None)
        if music_cue and music_cue["bgm_style"] != "none":
            bgm_style_master = music_cue["bgm_style"]
            
        master_bgm_path = os.path.join(self.paths["audio_bgm"], "master_bgm.wav")
        synthesize_bgm(bgm_style_master, master_bgm_path, duration=total_duration + 2.0)
        
        # 4. Sound Agent Selective Music Ducking / Muting
        # Build dynamic volume envelope for the BGM track
        # Since generating complex audio filter curves can crash, we construct a neat volume filter
        # that ducks background music volume during narration or turns it off entirely in selective silent shots!
        volume_filters = []
        current_time = 0.0
        
        for shot in shots:
            shot_id = shot["shot_id"]
            # Check duration of this compiled cut
            cut_idx = shots.index(shot)
            cut_dur = self.get_audio_duration(shot_files[cut_idx])
            
            # Retrieve Sound Agent instructions for this shot
            m_cue = next((m for m in sound["music_tracks"] if m["shot_id"] == shot_id), None)
            shot_vol = m_cue["volume"] if m_cue else 0.45
            if m_cue and m_cue["bgm_style"] == "none":
                shot_vol = 0.0 # Selective silence!
                
            # Apply volume timeline constraint
            volume_filters.append(
                f"volume=enable='between(t,{current_time:.2f},{current_time + cut_dur:.2f})':volume={shot_vol:.2f}"
            )
            current_time += cut_dur
            
        # Combine volume timeline filters
        vol_filter_str = ",".join(volume_filters) if volume_filters else "volume=0.35"
        
        # 5. Merge Concatenated Video and Dynamic BGM into final playable MP4!
        # cmd: -i [draft] -i [BGM] -filter_complex "[1:a]{vol_filter_str}[ducked_bgm];[0:a][ducked_bgm]amix=inputs=2:duration=first"
        cmd_final = [
            FFMPEG_EXE, "-y",
            "-i", draft_video_path.replace("\\", "/"),
            "-i", master_bgm_path.replace("\\", "/"),
            "-filter_complex", f"[1:a]{vol_filter_str}[ducked_bgm];[0:a][ducked_bgm]amix=inputs=2:duration=first",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            episode_video_path.replace("\\", "/")
        ]
        
        subprocess.run(cmd_final, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return episode_video_path
