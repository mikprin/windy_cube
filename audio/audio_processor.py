import sounddevice as sd
import numpy as np
from threading import Event
import config
import logging
import math
logger = logging.getLogger(__name__)
import pyaudio

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
                if amplitude > 0:
                    amplitude_db = 20 * math.log10(amplitude)
                    min_db = -60
                    max_db = 0
                    
                    amplitude_db = max(min_db, min(max_db, amplitude_db))
                    normalized_amplitude = ((amplitude_db - min_db) / (max_db - min_db)) * 29 + 1
                    
                    self.current_amplitude = normalized_amplitude
                else:
                    self.current_amplitude = 1
            
            logger.info(f"Посчитанная амплитуда: {self.current_amplitude}")
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