from time import sleep
import config
from utils.math_funcs import generate_sine_wave
from wled.wled_common_client import Wled, Wleds
import logging
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
import time
import math
import colorsys
logger = logging.getLogger(__name__)

AMP_COEFF = 0.7
TRANSITION_SPEED = 0.05  # How fast colors transition
HYPNO_SPEED = 0.02  # Speed of hypnotic animation
AMPLITUDE_THRESHOLD = 0.01  # Threshold to detect amplitude changes


INSIDE_COLORS = [
    # [255, 120, 245]
    [187, 186, 255],
    [255, 194, 226],
    [244, 253, 177],
    [124, 139, 255],
    [149, 255, 247]
]
    


class WLEDController:
    def __init__(self):
        self.sound_group = None
        self.motion_group = None
        
        self.audio_leds = []

        self.audio_leds_colors = INSIDE_COLORS[0]
        self.target_colors = INSIDE_COLORS[0]
        self.current_colors = [float(c) for c in INSIDE_COLORS[0]]

        self.last_amplitude = 0
        self.amplitude_change_time = time.time()
        self.hypno_phase = 0
        self.animation_time = 0

        self.audio_leds_thread = Thread(target=self._init_audio_leds, daemon=True)
        self.audio_leds_thread.start()
    

    def _init_audio_leds(self):
        logger.info("Инициализация WLED устройств...")
        self.audio_leds = [Wled.from_one_ip("192.168.8.40")]
        
        logger.info(f"Количество внутренних лент лент: {self.audio_leds}")
        for audio_wled in self.audio_leds:
            audio_wled.dmx.start()
            logger.info(f"Лента запущена: {audio_wled}")
        
        n_leds = self.audio_leds[0].dmx.n_leds

    
        try:
            while True:
                current_time = time.time()
                time_since_change = current_time - self.amplitude_change_time
                
                self._update_color_transition()
                
                if time_since_change > 1.0:
                    dmx_data = self._generate_hypno_animation(n_leds, current_time)
                else:
                    dmx_data = self._generate_amplitude_animation(n_leds, current_time)
                
                with ThreadPoolExecutor() as executor:
                    futures = [
                        executor.submit(wled.dmx.set_data, dmx_data)
                        for wled in self.audio_leds
                    ]
                
                time.sleep(0.033)
        except Exception as e:
            logger.error(f"Ошибка в работе лент: {e}")
            self.stop()


    def _update_color_transition(self):
        for i in range(3):
            diff = self.target_colors[i] - self.current_colors[i]
            if abs(diff) > 1:
                self.current_colors[i] += diff * TRANSITION_SPEED
            else:
                self.current_colors[i] = self.target_colors[i]

    def _generate_amplitude_animation(self, n_leds, current_time):
        self.animation_time = current_time
        sine_wave = generate_sine_wave(n_leds, frequency=2, amplitude=AMP_COEFF)
        
        dmx_data = []
        for led_idx, sine_value in enumerate(sine_wave):
            phase_offset = (current_time * 2 + led_idx * 0.1) % (2 * math.pi)
            wave_modifier = (math.sin(phase_offset) * 0.3 + 0.7)  # 0.4 to 1.0 range
            
            rgb = [
                int(self.current_colors[0] * sine_value * wave_modifier),
                int(self.current_colors[1] * sine_value * wave_modifier),
                int(self.current_colors[2] * sine_value * wave_modifier)
            ]
            dmx_data.extend(rgb)
        
        return dmx_data

    def _generate_hypno_animation(self, n_leds, current_time):
        dmx_data = []
        
        # Create multiple overlapping waves for hypnotic effect
        for led_idx in range(n_leds):
            # Primary spiral wave
            spiral_phase = (current_time * 4.5 + led_idx * 0.3) % (2 * math.pi)
            spiral_intensity = (math.sin(spiral_phase) + 1) * 0.7
            
            # Secondary wave for complexity
            wave2_phase = (current_time * 1.5 + led_idx * 0.15) % (2 * math.pi)
            wave2_intensity = (math.sin(wave2_phase) + 1) * 0.3
            
            # Breathing effect
            breath_phase = (current_time * 1.2) % (2 * math.pi)
            breath_intensity = (math.sin(breath_phase) + 1) * 0.5 + 0.2
            
            # Combine effects
            final_intensity = spiral_intensity * breath_intensity + wave2_intensity
            final_intensity = max(0.1, min(1.0, final_intensity))
            
            # Color cycling for hypnotic effect
            hue_offset = (current_time * 0.5 + led_idx * 0.05) % 1.0
            base_hue = self._rgb_to_hue(self.current_colors)
            new_hue = (base_hue + hue_offset * 0.2) % 1.0
            
            # Convert back to RGB with original saturation and brightness
            rgb = self._hue_to_rgb(new_hue, self.current_colors, final_intensity)
            
            dmx_data.extend([int(c) for c in rgb])
        
        return dmx_data

    def _rgb_to_hue(self, rgb):
        r, g, b = [c / 255.0 for c in rgb]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        return h

    def _hue_to_rgb(self, hue, original_rgb, intensity):
        r, g, b = [c / 255.0 for c in original_rgb]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        
        # Use new hue but keep original saturation characteristics
        new_r, new_g, new_b = colorsys.hsv_to_rgb(hue, s, v)
        
        # Apply intensity
        return [
            new_r * 255 * intensity,
            new_g * 255 * intensity,
            new_b * 255 * intensity
        ]
    
    def set_audio_gipnojam_from_amplitude(self, amplitude):
        amplitude_change = abs(amplitude - self.last_amplitude)
        if amplitude_change > AMPLITUDE_THRESHOLD:
            self.amplitude_change_time = time.time()
        
        self.last_amplitude = amplitude
        
        # amplitude = max(1, min(30, amplitude))  # Clamp to 1-30 range
        logger.info(f"Посчитанная амплитуда: {amplitude}")
        
        
        if amplitude <= 5:
            # Pure purple
            self.target_colors = INSIDE_COLORS[0]
        elif amplitude <= 11:
            frac = (amplitude - 5) / 6.0 
            color1 = INSIDE_COLORS[0]  # purple
            color2 = INSIDE_COLORS[1]  # pink
            self.target_colors = [
                color1[0] + (color2[0] - color1[0]) * frac,
                color1[1] + (color2[1] - color1[1]) * frac,
                color1[2] + (color2[2] - color1[2]) * frac
            ]
        elif amplitude <= 16:
            frac = (amplitude - 11) / 5.0  # 5 = 16-11
            color1 = INSIDE_COLORS[1]  # pink
            color2 = INSIDE_COLORS[2]  # yellow
            self.target_colors = [
                color1[0] + (color2[0] - color1[0]) * frac,
                color1[1] + (color2[1] - color1[1]) * frac,
                color1[2] + (color2[2] - color1[2]) * frac
            ]
        elif amplitude <= 21:
            frac = (amplitude - 16) / 5.0  # 5 = 21-16
            color1 = INSIDE_COLORS[2]  # yellow
            color2 = INSIDE_COLORS[3]  # blue
            self.target_colors = [
                color1[0] + (color2[0] - color1[0]) * frac,
                color1[1] + (color2[1] - color1[1]) * frac,
                color1[2] + (color2[2] - color1[2]) * frac
            ]
        else:
            frac = (amplitude - 21) / 9.0  # 9 = 30-21
            color1 = INSIDE_COLORS[3]  # blue
            color2 = INSIDE_COLORS[4]  # turquoise
            self.target_colors = [
                color1[0] + (color2[0] - color1[0]) * frac,
                color1[1] + (color2[1] - color1[1]) * frac,
                color1[2] + (color2[2] - color1[2]) * frac
            ]


    def stop(self):
        for audio_wled in self.audio_leds:
            audio_wled.dmx.stop()
            logger.info(f"Лента остановлена: {audio_wled}")
        