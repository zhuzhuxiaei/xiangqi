"""
音效层 - Kivy 适配版。
合成逻辑保留（与桌面版一致，音色不变），播放由 winsound/aplay 换成 Kivy SoundLoader。
"""
import os
import math
import struct
import random
import tempfile
import threading
import wave


class SoundBank:
    SAMPLE_RATE = 22050

    def __init__(self, cache_dir=None, enabled=True):
        """
        cache_dir: 缓存目录。Android 上传 App.user_data_dir；
                   None 时回退到系统临时目录（桌面调试）。
        """
        self.enabled = enabled
        self.cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), "xq_sounds")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.files = {}
        self._players = {}  # name -> kivy Sound，复用避免每次创建
        self._build_all()

    # ---------- WAV 写入 ----------
    def _write_wav(self, path, samples):
        with wave.open(path, "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.SAMPLE_RATE)
            frames = b"".join(
                struct.pack("<h", max(-32768, min(32767, int(s * 32767))))
                for s in samples
            )
            w.writeframes(frames)

    # ---------- 合成 ----------
    def _tone(self, freq, dur, volume=0.5, decay=True, wave_type="sine"):
        n = int(self.SAMPLE_RATE * dur)
        out = []
        for i in range(n):
            t = i / self.SAMPLE_RATE
            if wave_type == "sine":
                v = math.sin(2 * math.pi * freq * t)
            elif wave_type == "square":
                v = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
            elif wave_type == "noise":
                v = random.uniform(-1, 1)
            else:
                v = math.sin(2 * math.pi * freq * t)
            env = math.exp(-6 * t / dur) if decay else 1.0
            attack = min(1.0, i / (self.SAMPLE_RATE * 0.005 + 1))
            out.append(v * env * attack * volume)
        return out

    def _synth(self, partials, dur, volume=0.5, decay_rate=6.0,
               attack=0.005, noise_amt=0.0):
        """
        以多个正弦分音叠加合成更柔和的音色。
        partials: [(freq, amp), ...]  amp 为相对权重
        noise_amt: 起始瞬态噪声占比（0~1），用于增加"木质"敲击感
        """
        n = int(self.SAMPLE_RATE * dur)
        out = [0.0] * n
        atk_n = int(self.SAMPLE_RATE * attack)
        for i in range(n):
            t = i / self.SAMPLE_RATE
            v = 0.0
            for freq, amp in partials:
                v += amp * math.sin(2 * math.pi * freq * t)
            env = math.exp(-decay_rate * t / dur) if decay_rate > 0 else 1.0
            a = min(1.0, i / (atk_n + 1))
            out[i] = v * env * a * volume
        if noise_amt > 0:
            burst_len = max(1, int(self.SAMPLE_RATE * 0.008))
            for i in range(min(burst_len, n)):
                env = math.exp(-40 * i / burst_len)
                out[i] += noise_amt * env * random.uniform(-1, 1) * volume
        peak = max((abs(x) for x in out), default=1.0)
        if peak > 1.0:
            out = [x / peak for x in out]
        return out

    def _mix(self, *tracks):
        n = max(len(t) for t in tracks)
        out = [0.0] * n
        for t in tracks:
            for i, v in enumerate(t):
                out[i] += v
        return [max(-1.0, min(1.0, v)) for v in out]

    def _concat(self, *tracks):
        out = []
        for t in tracks:
            out.extend(t)
        return out

    def _silence(self, dur):
        return [0.0] * int(self.SAMPLE_RATE * dur)

    def _build_all(self):
        # 走子：木质轻敲
        move = self._synth(
            partials=[(440, 1.0), (880, 0.35), (1320, 0.12)],
            dur=0.12, volume=0.40, decay_rate=9.0, noise_amt=0.25,
        )
        # 吃子
        cap_body = self._synth(
            partials=[(196, 1.0), (294, 0.5), (392, 0.3)],
            dur=0.20, volume=0.55, decay_rate=7.0, noise_amt=0.35,
        )
        cap_bell = self._synth(
            partials=[(587, 1.0), (1175, 0.3)],
            dur=0.18, volume=0.22, decay_rate=8.0,
        )
        capture = self._mix(cap_body, cap_bell)
        # 将军
        chk1 = self._synth(
            partials=[(659, 1.0), (1318, 0.25)],
            dur=0.16, volume=0.40, decay_rate=7.0,
        )
        chk2 = self._synth(
            partials=[(880, 1.0), (1760, 0.25)],
            dur=0.22, volume=0.42, decay_rate=6.5,
        )
        check = self._concat(chk1, self._silence(0.04), chk2)
        # 非法
        illegal = self._synth(
            partials=[(110, 1.0), (165, 0.4)],
            dur=0.22, volume=0.45, decay_rate=5.5, noise_amt=0.15,
        )
        # 绝杀
        m1 = self._synth([(880, 1.0), (1320, 0.3)], 0.16, 0.42, 7.0)
        m2 = self._synth([(659, 1.0), (988, 0.3)],  0.16, 0.42, 7.0)
        m3 = self._synth([(440, 1.0), (660, 0.3)],  0.30, 0.46, 5.5)
        mate = self._concat(m1, self._silence(0.03), m2,
                            self._silence(0.03), m3)

        data = {"move_v2": move, "capture_v2": capture, "check_v2": check,
                "illegal_v2": illegal, "mate_v2": mate}
        alias = {"move_v2": "move", "capture_v2": "capture",
                 "check_v2": "check", "illegal_v2": "illegal",
                 "mate_v2": "mate"}
        for name, samples in data.items():
            path = os.path.join(self.cache_dir, f"{name}.wav")
            if not os.path.exists(path):
                try:
                    self._write_wav(path, samples)
                except Exception:
                    continue
            self.files[alias[name]] = path

    # ---------- 播放 ----------
    def play(self, name):
        if not self.enabled:
            return
        path = self.files.get(name)
        if not path or not os.path.exists(path):
            return
        # Kivy SoundLoader 必须在主线程创建/播放
        threading.Thread(target=self._play_kivy, args=(name, path), daemon=True).start()

    def _play_kivy(self, name, path):
        try:
            from kivy.core.audio import SoundLoader
        except Exception:
            # 桌面调试时若未安装 Kivy，回退到 winsound/aplay
            self._play_fallback(path)
            return

        try:
            snd = self._players.get(name)
            if snd is None:
                snd = SoundLoader.load(path)
                if snd is None:
                    return
                self._players[name] = snd
            # 重新从头播放
            try:
                snd.stop()
            except Exception:
                pass
            snd.play()
        except Exception:
            pass

    @staticmethod
    def _play_fallback(path):
        """桌面调试回退：未安装 Kivy 时用系统命令播放。"""
        import sys
        try:
            if sys.platform.startswith("win"):
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                import subprocess
                from shutil import which as _which
                for player in (["paplay"], ["aplay", "-q"], ["afplay"]):
                    if _which(player[0]):
                        subprocess.Popen(player + [path],
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
                        return
        except Exception:
            pass
