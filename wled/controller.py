from time import sleep
import config
from wled.wled_common_client import Wled, Wleds
import logging
from threading import Thread
import numpy as np
import time
logger = logging.getLogger(__name__)

AMP_COEFF = 0.7
    
def generate_sine_wave(n_leds, frequency=0.1, amplitude=1.0):
    x = np.arange(n_leds)
    sine_wave = amplitude * np.sin(2 * np.pi * frequency * x / n_leds)
    return (sine_wave + 1) / 2  # Normalize to 0-1

class WLEDController:
    def __init__(self):
        self.sound_group = None
        self.motion_group = None
        
        self.audio_leds = []
        self.audio_leds_thread = Thread(target=self._init_audio_leds)
        self.audio_leds_thread.daemon = True
        
        self.audio_leds_colors = [255, 120, 245]
        # motion_leds_thread = Thread(target=motion_server.start)
        
        # self._init_devices()
        
        # Start the thread to initialize audio LEDs
        self.audio_leds_thread.start()
    

    def _init_audio_leds(self):
        logger.info("Инициализация WLED устройств...")
        wled = Wled.from_one_ip("192.168.8.40")
        
        self.audio_leds.append(wled)
        wled.dmx.start()
        # self.audio_leds[0].dmx.start()
        # n_leds = self.audio_leds[0].dmx.n_leds
        n_leds = wled.dmx.n_leds
        logger.info(f"Количество светодиодов: {n_leds}")
        
        sine_wave = generate_sine_wave(n_leds, frequency=2, amplitude=AMP_COEFF)
        
        while True:
            for led in range(n_leds):
                # Calculate the sine wave value for this LED
                sine_value = sine_wave[led]
                
                # Pink color (high red, medium green, low blue)
                red = int(self.audio_leds_colors[0] * sine_value)
                green = int(self.audio_leds_colors[1] * sine_value)  # Medium intensity for pink
                blue = int(self.audio_leds_colors[2] * sine_value)   # Higher blue for pink tone
                
                wled.dmx.set_data([red, green, blue] * n_leds)
                time.sleep(0.01)  # Adjust speed of animation

        
        

    # def _init_device_group(self, ip_list, group_name):
    #     active_devices = []
    #     failed_devices = []
        
    #     for ip in ip_list:
    #         try:
    #             device = WLED(ip)
    #             device.set_hsv(0, 0, 0, 0.1)
    #             active_devices.append(device)
    #             logger.info(f"Устройство {ip} ({group_name}) успешно подключено")
    #         except Exception as e:
    #             failed_devices.append(ip)
    #             logger.warning(
    #                 f"Не удалось подключиться к устройству {ip} ({group_name}): {str(e)}"
    #             )
    #             continue
        
    #     if not active_devices:
    #         logger.error(f"Ни одно из устройств {group_name} не доступно!")
    #         return None
        
    #     if failed_devices:
    #         logger.warning(
    #             f"Не подключены некоторые устройства {group_name}: {', '.join(failed_devices)}"
    #         )
        
    #     return WLEDGroup([d.ip for d in active_devices])

    # def _setup_group(self, group):
    #     if group is None:
    #         return
            
    #     for device in group.devices:
    #         try:
    #             device.set_hsv(0, 255, 100, transition_time=0.1)
    #             sleep(0.1)
    #         except Exception as e:
    #             logger.warning(
    #                 f"Ошибка настройки устройства {device.ip}: {str(e)}"
    #             )
    #             continue


    def set_audio_gipnojam_from_amplitude(self, amplitude):
        # self.audio_leds_colors[0] = amplitude
        # self.audio_leds_colors[1] = amplitude
        # self.audio_leds_colors[2] = amplitude
        pass


    def set_sound_color(self, hue, brightness, transition_time=0.2):
        brightness = max(config.MIN_BRIGHTNESS, min(config.MAX_BRIGHTNESS, brightness))
        self.sound_group.set_hsv(
            hue, 
            255,
            brightness,
            transition_time
        )

    def set_motion_color(self, hue, transition_time=0.5):
        self.motion_group.set_hsv(
            hue,
            255,
            200,  # фиксированная яркость для внешних лент движения
            transition_time
        )

    def close(self):
        for wled in self.audio_leds:
            wled.dmx.stop()
            
        # self.sound_group.close()
        # self.motion_group.close()
        