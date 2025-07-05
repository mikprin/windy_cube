from time import sleep
import config
from wled.wled_common_client import WLED, WLEDGroup
import logging
logger = logging.getLogger(__name__)

class WLEDController:
    def __init__(self):
        self.sound_group = None
        self.motion_group = None
        self._init_devices()

    def _init_devices(self):
        logger.info("Инициализация WLED устройств...")
        
        try:
            # Инициализация звуковых лент
            self.sound_group = self._init_device_group(
                config.SOUND_DEVICES, 
                "звуковые"
            )
            
            # Инициализация лент датчика движения
            self.motion_group = self._init_device_group(
                config.MOTION_DEVICES,
                "датчика движения"
            )
            
        except Exception as e:
            logger.error(f"Критическая ошибка при инициализации: {str(e)}")
            raise

    def _init_device_group(self, ip_list, group_name):
        active_devices = []
        failed_devices = []
        
        for ip in ip_list:
            try:
                device = WLED(ip)
                device.set_hsv(0, 0, 0, 0.1)
                active_devices.append(device)
                logger.info(f"Устройство {ip} ({group_name}) успешно подключено")
            except Exception as e:
                failed_devices.append(ip)
                logger.warning(
                    f"Не удалось подключиться к устройству {ip} ({group_name}): {str(e)}"
                )
                continue
        
        if not active_devices:
            logger.error(f"Ни одно из устройств {group_name} не доступно!")
            return None
        
        if failed_devices:
            logger.warning(
                f"Не подключены некоторые устройства {group_name}: {', '.join(failed_devices)}"
            )
        
        return WLEDGroup([d.ip for d in active_devices])

    def _setup_group(self, group):
        if group is None:
            return
            
        for device in group.devices:
            try:
                device.set_hsv(0, 255, 100, transition_time=0.1)
                sleep(0.1)
            except Exception as e:
                logger.warning(
                    f"Ошибка настройки устройства {device.ip}: {str(e)}"
                )
                continue


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
        self.sound_group.close()
        self.motion_group.close()