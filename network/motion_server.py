import socket
import threading
import config
import logging

logger = logging.getLogger(__name__)

class MotionServer:
    def __init__(self, wled_controller):
        self.wled = wled_controller
        self.is_running = True
        
        try:
            logger.info("Инициализация сервера для датчика движения...")
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            logger.debug("Сокет успешно создан")
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            logger.debug("Установлена опция SO_REUSEADDR")
            bind_address = (config.MOTION_HOST, config.MOTION_PORT)
            self.server_socket.bind(bind_address)
            logger.info(f"Сокет привязан к {bind_address}")
            self.server_socket.listen(1)
            logger.info(f"Сервер запущен и ожидает подключений на порту {config.MOTION_PORT}")
        except socket.error as e:
            logger.error(f"Ошибка при инициализации сервера: {str(e)}")
            self.is_running = False
            raise
        except Exception as e:
            logger.critical(f"Неожиданная ошибка при создании сервера: {str(e)}")
            self.is_running = False
            raise

    def _handle_client(self, client_socket):
        try:
            while self.is_running:
                data = client_socket.recv(1024)
                if not data:
                    break
                
                print(data.decode().strip())

                # TODO: Прмиерно так надо будет накрутить ифаков чтобы менять
                self.wled.set_motion_color(
                    hue=0,
                    transition_time=0.1
                )
        except Exception as e:
            logger.error(f"Ошибка обработки клиента: {str(e)}")
        finally:
            client_socket.close()

    def start(self):
        if not self.is_running:
            logger.warning("Попытка запуска неинициализированного сервера")
            return

        logger.info("Запуск основного цикла сервера...")
        try:
            while self.is_running:
                try:
                    client_sock, addr = self.server_socket.accept()
                    logger.info(f"Получено подключение от {addr}")
                    threading.Thread(target=self._handle_client, args=(client_sock,)).start()
                except socket.timeout:
                    continue
                except socket.error as e:
                    logger.error(f"Ошибка при принятии подключения: {str(e)}")
                    continue
        except Exception as e:
            logger.critical(f"Критическая ошибка в основном цикле: {str(e)}")
        finally:
            self.stop()

    def stop(self):
        if hasattr(self, 'server_socket'):
            try:
                self.server_socket.close()
                logger.info("Серверный сокет успешно закрыт")
            except Exception as e:
                logger.error(f"Ошибка при закрытии сокета: {str(e)}")
        self.is_running = False
        logger.info("Сервер остановлен")