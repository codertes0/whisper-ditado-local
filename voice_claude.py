"""
voice-claude — push-to-talk dictation pra Claude Code (e qualquer outro campo de texto).

Segure a tecla HOTKEY (padrao: "[") pra gravar; solte pra transcrever e colar no campo focado.
Voce aperta Enter pra enviar.
"""

import os
import sys
import time
import queue
import threading

# Tentar disponibilizar DLLs CUDA do pip (Windows GPU)
def _add_cuda_dlls():
    """Garante que as DLLs CUDA dos pacotes pip sao encontradas.

    1) os.add_dll_directory — pra ctypes/loadlibrary modernos
    2) PATH — pra libs nativas que fazem lazy-load via PATH legado
    3) ctypes.WinDLL upfront — prende as DLLs em memoria pra qualquer load posterior achar
    """
    try:
        import ctypes
        import nvidia.cublas  # type: ignore
        import nvidia.cudnn   # type: ignore
        paths = []
        for mod in (nvidia.cublas, nvidia.cudnn):
            bases = list(getattr(mod, "__path__", []) or [])
            for base in bases:
                for sub in ("bin", "lib"):
                    p = os.path.join(base, sub)
                    if os.path.isdir(p):
                        os.add_dll_directory(p)
                        paths.append(p)
        if paths:
            os.environ["PATH"] = os.pathsep.join(paths) + os.pathsep + os.environ.get("PATH", "")
        # Pre-carrega DLLs criticas pra travar em memoria
        for dll_name in ("cublas64_12.dll", "cublasLt64_12.dll", "cudnn64_9.dll"):
            for p in paths:
                full = os.path.join(p, dll_name)
                if os.path.isfile(full):
                    try:
                        ctypes.WinDLL(full)
                    except OSError as oe:
                        print(f"[voice-claude] aviso: falha ao pre-carregar {dll_name}: {oe}")
                    break
    except Exception as e:
        print(f"[voice-claude] aviso: nao consegui preparar DLLs CUDA ({e})")

if sys.platform == "win32":
    _add_cuda_dlls()

import numpy as np
import sounddevice as sd
import keyboard
import pyperclip
from faster_whisper import WhisperModel

# ---------- CONFIG ----------
HOTKEY      = "["                         # tecla PTT (push-to-talk). Pode trocar por "f8", "f9", "right ctrl", etc.
AUTO_ENTER  = False                       # aperta Enter automatico depois de colar (deixe False pra uso system-wide)
ENTER_HOTKEY = None                       # tecla PTT que cola + manda Enter (pra usar em chats). None pra desativar.
MODEL_SIZE  = "large-v3"                  # tiny | base | small | medium | large-v3
BEAM_SIZE   = 5                           # mais hipoteses = mais preciso (1 = mais rapido)
LANGUAGE    = "pt"
SAMPLE_RATE = 16000
CHANNELS    = 1
MIN_SECONDS = 0.3                         # ignora gravacao mais curta que isso
BEEP        = True                        # toca beep ao iniciar/terminar
# ----------------------------


def beep(freq, dur_ms):
    if not BEEP or sys.platform != "win32":
        return
    try:
        import winsound
        winsound.Beep(freq, dur_ms)
    except Exception:
        pass


def load_model():
    print(f"[voice-claude] Carregando Whisper '{MODEL_SIZE}'...")
    try:
        m = WhisperModel(MODEL_SIZE, device="cuda", compute_type="float16")
        print("[voice-claude] OK — rodando em CUDA (float16)")
        return m
    except Exception as e:
        print(f"[voice-claude] CUDA indisponivel ({type(e).__name__}: {e}); usando CPU int8")
        m = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
        print("[voice-claude] OK — rodando em CPU (int8)")
        return m


class Recorder:
    def __init__(self):
        self.recording = False
        self.q: "queue.Queue[np.ndarray]" = queue.Queue()
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            callback=self._callback,
            dtype="float32",
        )
        self.stream.start()

    def _callback(self, indata, frames, time_info, status):
        if self.recording:
            self.q.put(indata.copy())

    def start(self):
        if self.recording:
            return
        # esvazia buffer residual
        while not self.q.empty():
            try: self.q.get_nowait()
            except queue.Empty: break
        self.recording = True
        beep(880, 70)
        print("[voice-claude] 🎙  gravando...")

    def stop(self):
        if not self.recording:
            return None
        self.recording = False
        chunks = []
        while not self.q.empty():
            try: chunks.append(self.q.get_nowait())
            except queue.Empty: break
        if not chunks:
            print("[voice-claude] (sem audio capturado)")
            return None
        audio = np.concatenate(chunks, axis=0).flatten().astype(np.float32)
        dur = len(audio) / SAMPLE_RATE
        if dur < MIN_SECONDS:
            print(f"[voice-claude] (muito curto: {dur:.2f}s, ignorado)")
            return None
        return audio, dur


def transcribe_and_paste(model, audio, dur, send_enter=False):
    print(f"[voice-claude] transcrevendo {dur:.1f}s...")
    t0 = time.time()
    segments, _info = model.transcribe(
        audio,
        language=LANGUAGE,
        beam_size=BEAM_SIZE,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    elapsed = time.time() - t0
    print(f"[voice-claude] ({elapsed:.1f}s) → {text!r}")
    if not text:
        beep(300, 120)
        return
    pyperclip.copy(text)
    time.sleep(0.05)
    keyboard.send("ctrl+v")
    if send_enter:
        time.sleep(0.08)
        keyboard.send("enter")
    beep(1200, 60)


def main():
    model = load_model()
    rec = Recorder()
    print(f"[voice-claude] Pronto.")
    print(f"[voice-claude]   '{HOTKEY}'  = segurar pra falar -> cola texto (uso geral, qualquer app)")
    if ENTER_HOTKEY:
        print(f"[voice-claude]   '{ENTER_HOTKEY}'  = segurar pra falar -> cola + Enter (chats)")
    print(f"[voice-claude] Auto-Enter padrao: {'ON' if AUTO_ENTER else 'OFF'}")
    print("[voice-claude] Ctrl+C aqui no terminal pra sair.\n")

    transcribe_lock = threading.Lock()
    state = {"held_by": None}  # None | HOTKEY | ENTER_HOTKEY

    def do_transcribe(audio, dur, send_enter):
        with transcribe_lock:
            transcribe_and_paste(model, audio, dur, send_enter=send_enter)

    def make_press(which):
        def on_press(_e):
            if state["held_by"] is not None:
                return
            state["held_by"] = which
            rec.start()
        return on_press

    def make_release(which):
        def on_release(_e):
            if state["held_by"] != which:
                return
            state["held_by"] = None
            send_enter = AUTO_ENTER or (which == ENTER_HOTKEY)
            result = rec.stop()
            if result is not None:
                audio, dur = result
                threading.Thread(target=do_transcribe, args=(audio, dur, send_enter), daemon=True).start()
        return on_release

    keyboard.on_press_key(HOTKEY, make_press(HOTKEY), suppress=True)
    keyboard.on_release_key(HOTKEY, make_release(HOTKEY), suppress=True)
    if ENTER_HOTKEY:
        keyboard.on_press_key(ENTER_HOTKEY, make_press(ENTER_HOTKEY), suppress=True)
        keyboard.on_release_key(ENTER_HOTKEY, make_release(ENTER_HOTKEY), suppress=True)

    try:
        keyboard.wait()
    except KeyboardInterrupt:
        print("\n[voice-claude] saindo...")
    finally:
        rec.stream.stop()
        rec.stream.close()


if __name__ == "__main__":
    main()
