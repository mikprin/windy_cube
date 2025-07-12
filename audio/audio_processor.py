import sounddevice as sd
import numpy as np
from threading import Event
import config
import logging
logger = logging.getLogger(__name__)

class AudioProcessor:
    """Typical Amplitude is 0.0023 for voice, 0.0001 for silence"""
    def __init__(self, callback):
        self.callback = callback
        self.current_amplitude = 0.0
        self.is_running = Event()
        self.is_running.set()
        self.stream = None
        logger.info("Аудио процессор инициализирован")

    def _audio_callback(self, indata, frames, time, status):
        try:
            if not self.is_running.is_set():
                logger.debug("Получен сигнал остановки в callback")
                raise sd.CallbackStop

            if status:
                logger.warning(f"Статус аудио потока: {status}")

            if len(indata) > 0:
                amplitude = np.mean(np.abs(indata))
                # self.current_amplitude = (
                #     config.SMOOTHING_FACTOR * amplitude + 
                #     (1 - config.SMOOTHING_FACTOR) * self.current_amplitude
                # )
                self.current_amplitude = amplitude
                logger.info(f"Текущая амплитуда: {self.current_amplitude:.4f}\nAmlitude: {amplitude:.4f}")
                self.callback(self.current_amplitude)
                
        except Exception as e:
            logger.error(f"Ошибка в audio callback: {str(e)}")
            raise

    def start(self):
        try:
            logger.info(f"Запуск аудио потока (SR: {config.SAMPLE_RATE}, "
                       f"Buffer: {config.BUFFER_DURATION} сек)")
            
            self.stream = sd.InputStream(
                samplerate=config.SAMPLE_RATE,
                channels=1,
                callback=self._audio_callback,
                blocksize=int(config.SAMPLE_RATE * config.BUFFER_DURATION),
                dtype='float32'
            )
            
            with self.stream:
                logger.info("Аудио поток успешно запущен")
                while self.is_running.is_set():
                    sd.sleep(1000)
                    
        except sd.PortAudioError as pae:
            logger.error(f"Ошибка PortAudio: {str(pae)}")
            raise
        except Exception as e:
            logger.critical(f"Критическая ошибка в аудио потоке: {str(e)}")
            raise
        finally:
            logger.info("Аудио поток завершен")

    def stop(self):
        if self.is_running.is_set():
            logger.info("Получен сигнал остановки аудио процессора")
            self.is_running.clear()
            
            if self.stream and self.stream.active:
                try:
                    self.stream.abort()
                    logger.debug("Аудио поток принудительно остановлен")
                except Exception as e:
                    logger.error(f"Ошибка при остановке потока: {str(e)}")