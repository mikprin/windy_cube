import config
from utils.math_funcs import generate_sine_wave
from wled.wled_common_client import Wled, Wleds
import logging
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
import time
import math
logger = logging.getLogger(__name__)

AMP_COEFF = 0.7
TRANSITION_SPEED = 1.2
AMPLITUDE_THRESHOLD = 5 
PRESET_THRESHOLD = 60 


INSIDE_COLORS = [
    [187, 186, 255],
    [255, 194, 226],
    [244, 253, 177],
    [124, 139, 255],
    [149, 255, 247]
]
    
class WLEDController:
    def __init__(self):
        self.audio_leds = []
        self.audio_leds_colors = INSIDE_COLORS[0]
        self.target_colors = list(INSIDE_COLORS[0])
        self.current_colors = [float(c) for c in INSIDE_COLORS[0]]

        self.last_amplitude = 0
        self.amplitude_change_time = time.time()
        self.hypno_phase = 0
        self.animation_time = 0
        self.audio_leds_stopped = False

        self.audio_leds_thread = Thread(target=self._init_audio_leds, daemon=True)
        self.audio_leds_thread.start()
    

    def _init_audio_leds(self):
        logger.info("Инициализация WLED устройств...")
        wled1 = Wled.from_one_ip("192.168.8.40")
        self.audio_leds = [wled1]
        
        logger.info(f"Количество внутренних лент лент: {self.audio_leds}")
        self.start_and_wait()
        
        n_leds = self.audio_leds[0].dmx.n_leds
    
        try:
            while True:
                current_time = time.time()
                time_since_change = current_time - self.amplitude_change_time
                self._update_color_transition()
                dmx_data = self._generate_amplitude_animation(n_leds, current_time)
                
                if time_since_change > PRESET_THRESHOLD:
                    if not self.audio_leds_stopped:
                        logger.info(f"Время с прошлого обновления большое, включаю пресет: {time_since_change}")
                        self.stop_and_wait()
                        self.audio_leds_stopped = True
                else:
                    if self.audio_leds_stopped:
                        self.start_and_wait()
                        self.audio_leds_stopped = False
                        logger.info(f"Начала меняться амплитуда, включаю контроль лент")

                    with ThreadPoolExecutor() as executor:
                        futures = [
                            executor.submit(wled.dmx.set_data, dmx_data)
                            for wled in self.audio_leds
                        ]
                
                time.sleep(0.033)
        except Exception as e:
            logger.error(f"Ошибка в работе лент: {e}")
            self.stop()
        finally:
            self.stop_audio_leds_threaded()


    def _update_color_transition(self):
        color_changed = False
        
        logger.debug(f"BEFORE: current={[round(c, 1) for c in self.current_colors]}, target={[round(c, 1) for c in self.target_colors]}")
        
        for i in range(3):
            diff = self.target_colors[i] - self.current_colors[i]
            logger.debug(f"Channel {i}: diff={diff:.2f}")
            
            if abs(diff) > 0.1:
                old_color = self.current_colors[i]
                self.current_colors[i] += diff * TRANSITION_SPEED
                color_changed = True
                logger.debug(f"Color channel {i}: {old_color:.1f} -> {self.current_colors[i]:.1f} (diff: {diff:.2f})")
            else:
                if abs(self.current_colors[i] - self.target_colors[i]) > 0.01:
                    self.current_colors[i] = self.target_colors[i]
                    color_changed = True
                    logger.debug(f"Color channel {i}: snapped to target {self.target_colors[i]}")
        
        if color_changed:
            logger.debug(f"Colors updated to: {[round(c, 1) for c in self.current_colors]}")
        else:
            logger.debug("No color change needed")
            

    def _generate_amplitude_animation(self, n_leds, current_time):
        self.animation_time = current_time
        sine_wave = generate_sine_wave(n_leds, frequency=2, amplitude=AMP_COEFF)
        
        dmx_data = []
        for led_idx, sine_value in enumerate(sine_wave):
            phase_offset = (current_time * 2 + led_idx * 0.1) % (2 * math.pi)
            wave_modifier = (math.sin(phase_offset) * 0.3 + 0.7)
            
            rgb = [
                max(0, min(255, int(self.current_colors[0] * sine_value * wave_modifier))),
                max(0, min(255, int(self.current_colors[1] * sine_value * wave_modifier))),
                max(0, min(255, int(self.current_colors[2] * sine_value * wave_modifier)))
            ]
            dmx_data.extend(rgb)
        
        return dmx_data

    
    def set_audio_gipnojam_from_amplitude(self, amplitude):
        amplitude_change = abs(amplitude - self.last_amplitude)
        if amplitude_change > AMPLITUDE_THRESHOLD:
            self.amplitude_change_time = time.time()
        
        self.last_amplitude = amplitude
        logger.debug(f"Амплитуда: {amplitude}")
        if amplitude <= 5:
            self.target_colors = list(INSIDE_COLORS[0])
        elif amplitude <= 11:
            frac = (amplitude - 5) / 6.0 
            color1 = INSIDE_COLORS[0]  # purple
            color2 = INSIDE_COLORS[1]  # pink
            self.target_colors = [
                int(color1[0] + (color2[0] - color1[0]) * frac),
                int(color1[1] + (color2[1] - color1[1]) * frac),
                int(color1[2] + (color2[2] - color1[2]) * frac)
            ]
        elif amplitude <= 16:
            frac = (amplitude - 11) / 5.0  # 5 = 16-11
            color1 = INSIDE_COLORS[1]  # pink
            color2 = INSIDE_COLORS[2]  # yellow
            self.target_colors = [
                int(color1[0] + (color2[0] - color1[0]) * frac),
                int(color1[1] + (color2[1] - color1[1]) * frac),
                int(color1[2] + (color2[2] - color1[2]) * frac)
            ]
        elif amplitude <= 21:
            frac = (amplitude - 16) / 5.0  # 5 = 21-16
            color1 = INSIDE_COLORS[2]  # yellow
            color2 = INSIDE_COLORS[3]  # blue
            self.target_colors = [
                int(color1[0] + (color2[0] - color1[0]) * frac),
                int(color1[1] + (color2[1] - color1[1]) * frac),
                int(color1[2] + (color2[2] - color1[2]) * frac)
            ]
        else:
            frac = min(1.0, (amplitude - 21) / 9.0)  # 9 = 30-21
            color1 = INSIDE_COLORS[3]  # blue
            color2 = INSIDE_COLORS[4]  # turquoise
            self.target_colors = [
                int(color1[0] + (color2[0] - color1[0]) * frac),
                int(color1[1] + (color2[1] - color1[1]) * frac),
                int(color1[2] + (color2[2] - color1[2]) * frac)
            ]

    def start_audio_leds_threaded(self):
        def _start_leds():
            try:
                for audio_wled in self.audio_leds:
                    audio_wled.dmx.start()
                    logger.info(f"Лента запущена: {audio_wled}")
            except Exception as e:
                logger.error(f"Ошибка при запуске лент: {e}")
        
        start_thread = Thread(target=_start_leds, daemon=True)
        start_thread.start()
        return start_thread

    def stop_audio_leds_threaded(self):
        def _stop_leds():
            try:
                for audio_wled in self.audio_leds:
                    audio_wled.dmx.stop()
                    logger.info(f"Лента остановлена: {audio_wled}")
            except Exception as e:
                logger.error(f"Ошибка при остановке лент: {e}")
        
        stop_thread = Thread(target=_stop_leds, daemon=True)
        stop_thread.start()
        return stop_thread

    def stop_and_wait(self):
        thread = self.stop_audio_leds_threaded()
        thread.join()
        
    def start_and_wait(self):
        thread = self.start_audio_leds_threaded()
        thread.join()

    def stop(self):
        self.stop_audio_leds_threaded()
        