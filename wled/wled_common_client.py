import socket
from concurrent.futures import ThreadPoolExecutor

class WLED:
    def __init__(self, ip):
        self.ip = ip
        self.udp_port = 21324
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    def send_udp_sync(self, brightness=255, col=[255,0,0], transition_delay=1000):
        """Основной метод для плавных переходов"""
        packet = bytearray(37)
        # Базовые настройки
        packet[0] = 0  # WLED protocol
        packet[1] = 1  # Direct change
        packet[2] = brightness  # Яркость
        # Основной цвет (RGB)
        packet[3] = col[0]  # R
        packet[4] = col[1]  # G
        packet[5] = col[2]  # B
        # Время перехода (мс)
        packet[17] = (transition_delay >> 0) & 0xFF
        packet[18] = (transition_delay >> 8) & 0xFF
        # Версия протокола (9+ поддерживает плавные переходы)
        packet[11] = 9
        
        self.sock.sendto(packet, (self.ip, self.udp_port))

    def set_hsv(self, hue, saturation, value, transition_time=1.0):
        """Плавный переход к HSV цвету"""
        r, g, b = self.hsv_to_rgb(hue, saturation, value)
        self.send_udp_sync(
            brightness=value,
            col=[r, g, b],
            transition_delay=int(transition_time * 1000)
        )

    @staticmethod
    def hsv_to_rgb(h, s, v):
        """Конвертация HSV в RGB"""
        h = float(h)/255
        s = float(s)/255
        v = float(v)/255
        i = int(h*6)
        f = h*6 - i
        p = v*(1-s)
        q = v*(1-f*s)
        t = v*(1-(1-f)*s)

        if i%6 == 0: r,g,b = v,t,p
        elif i == 1: r,g,b = q,v,p
        elif i == 2: r,g,b = p,v,t
        elif i == 3: r,g,b = p,q,v
        elif i == 4: r,g,b = t,p,v
        else: r,g,b = v,p,q

        return int(r*255), int(g*255), int(b*255)

class WLEDGroup:
    def __init__(self, ips):
        self.devices = [WLED(ip) for ip in ips]
        self.executor = ThreadPoolExecutor(max_workers=10)
    
    def set_hsv(self, hue, saturation, value, transition_time=1.0):
        """Установка HSV цвета для всей группы с плавным переходом"""
        for device in self.devices:
            self.executor.submit(
                device.set_hsv,
                hue,
                saturation,
                value,
                transition_time
            )
    
    def close(self):
        self.executor.shutdown()