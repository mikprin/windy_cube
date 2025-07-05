import socket
import time
import logging
import random

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_motion_server(host='localhost', port=65432, num_tests=5):
    for i in range(1, num_tests + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                
                logger.info(f"Тест {i}/{num_tests}: Подключаемся к {host}:{port}...")
                s.connect((host, port))
                
                # Симулируем случайное событие движения (70% вероятность)
                motion_detected = random.random() < 0.7
                message = "MOTION" if motion_detected else "NO_MOTION"
                
                logger.debug(f"Отправляем сообщение: {message}")
                s.sendall(message.encode('utf-8'))
                
                try:
                    data = s.recv(1024)
                    if data:
                        logger.info(f"Ответ сервера: {data.decode('utf-8')}")
                    else:
                        logger.debug("Сервер закрыл соединение без ответа")
                except socket.timeout:
                    logger.debug("Сервер не ответил (таймаут)")
                
                logger.info(f"Тест {i} завершен. Отправлено: {message}")
                
        except ConnectionRefusedError:
            logger.error("Сервер недоступен: соединение отклонено")
            break
        except socket.timeout:
            logger.error("Таймаут подключения к серверу")
            break
        except Exception as e:
            logger.error(f"Ошибка при тестировании: {str(e)}")
            break
        
        if i < num_tests:
            time.sleep(random.uniform(0.5, 2.0))

if __name__ == "__main__":
    SERVER_HOST = 'localhost'
    SERVER_PORT = 65432
    
    test_motion_server(host=SERVER_HOST, port=SERVER_PORT)