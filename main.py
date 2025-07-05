from wled.controller import WLEDController
from audio.audio_processor import AudioProcessor
from network.motion_server import MotionServer
from time import sleep
from threading import Thread
import config
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    wled_controller = WLEDController()
    
    def sound_callback(amplitude):
        # hue = int((wled_controller.sound_color_hue + 2) % 360)
        # wled_controller.sound_color_hue = hue
        # brightness = int(config.MIN_BRIGHTNESS + 
        #                (config.MAX_BRIGHTNESS - config.MIN_BRIGHTNESS) * amplitude)
        # wled_controller.set_sound_color(hue, brightness)
        pass
    

    wled_controller.sound_color_hue = 0
    audio_processor = AudioProcessor(sound_callback)
    
    motion_server = MotionServer(wled_controller)
    
    audio_thread = Thread(target=audio_processor.start)
    motion_thread = Thread(target=motion_server.start)
    
    audio_thread.daemon = True
    motion_thread.daemon = True
    
    audio_thread.start()
    motion_thread.start()
    
    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        audio_processor.stop()
        motion_server.stop()

if __name__ == "__main__":
    main()
