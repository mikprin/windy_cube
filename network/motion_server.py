"""
MotionServer class for handling MQTT motion detection from ESP32 PIR sensor
and triggering actions like WLED control.

Requirements:
    pip install paho-mqtt python-dotenv
"""

import json
import logging
import os
import time
import threading
from datetime import datetime
from typing import Optional, Callable, Any, Dict
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class MotionServer:
    """
    MQTT-based motion detection server that handles messages from ESP32 PIR sensor
    and triggers configurable actions on motion detection.
    """
    
    def __init__(
        self, 
        wled_controller=None,
        debug: bool = False
    ):
        """
        Initialize MotionServer
        
        Args:
            wled_controller: WLED controller object with methods like turn_on(), turn_off()
            debug: Enable debug logging
            
        Environment variables:
            MQTT_HOST: MQTT broker hostname/IP (default: "192.168.50.9")
            MQTT_PORT: MQTT broker port (default: 1883)
            MQTT_USERNAME: MQTT username (optional)
            MQTT_PASSWORD: MQTT password (optional)
            MOTION_TIMEOUT: Seconds to keep action active after motion detection (default: 30)
        """
        self.wled_controller = wled_controller
        
        # Load configuration from environment variables
        self.mqtt_host = os.getenv("MQTT_HOST", "192.168.50.9")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.mqtt_username = os.getenv("MQTT_USERNAME")
        self.mqtt_password = os.getenv("MQTT_PASSWORD", None)
        self.motion_timeout = int(os.getenv("MOTION_TIMEOUT", "10"))
        
        # Setup logging
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # MQTT topics (matching ESP32 code)
        self.topics = {
            'motion_detected': 'motion/detected',
            'motion_status': 'motion/status', 
            'motion_events': 'motion/events',
            'motion_error': 'motion/error'
        }
        
        # State management
        self._running = False
        self._connected = False
        self._motion_active = False
        self._last_motion_time = 0
        self._motion_count = 0
        self._motion_timer = None
        self._lock = threading.Lock()
        
        # MQTT client setup
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        if self.mqtt_username and self.mqtt_password:
            self.client.username_pw_set(self.mqtt_username, self.mqtt_password)
            
        # Custom callback functions
        self.on_motion_detected: Optional[Callable] = None
        self.on_motion_ended: Optional[Callable] = None
        self.on_status_update: Optional[Callable] = None
        
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when MQTT client connects"""
        if rc == 0:
            self._connected = True
            self.logger.info(f"Connected to MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
            
            # Subscribe to all motion topics
            for topic_name, topic in self.topics.items():
                client.subscribe(topic)
                self.logger.debug(f"Subscribed to {topic}")
                
        else:
            self.logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
            
    def _on_disconnect(self, client, userdata, rc):
        """Callback for when MQTT client disconnects"""
        self._connected = False
        if rc != 0:
            self.logger.warning("Unexpected MQTT disconnection. Will auto-reconnect.")
        else:
            self.logger.info("MQTT disconnected gracefully")
            
    def _on_message(self, client, userdata, msg):
        """Callback for when MQTT message is received"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            self.logger.debug(f"Received message on topic '{topic}': {payload}")
            
            if topic == self.topics['motion_detected']:
                self._handle_motion_detected(payload)
            elif topic == self.topics['motion_status']:
                self._handle_status_update(payload)
            elif topic == self.topics['motion_events']:
                self._handle_motion_event(payload)
            elif topic == self.topics['motion_error']:
                self._handle_error(payload)
                
        except Exception as e:
            self.logger.error(f"Error processing MQTT message: {e}")
            
    def _handle_motion_detected(self, payload: str):
        """Handle motion detection message"""
        try:
            data = json.loads(payload)
            motion = data.get('motion', False)
            timestamp = data.get('timestamp', 0)
            count = data.get('count', 0)
            
            if motion:
                with self._lock:
                    self._last_motion_time = time.time()
                    self._motion_count = count
                    
                    if not self._motion_active:
                        self._motion_active = True
                        self.logger.info(f"Motion detected! Count: {count}")
                        self._trigger_motion_action()
                    else:
                        self.logger.debug(f"Motion still active, extending timeout. Count: {count}")
                        
                    # Reset/extend the motion timeout
                    self._reset_motion_timer()
                    
                # Call custom callback if set
                if self.on_motion_detected:
                    self.on_motion_detected(data)
                    
        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON in motion detected payload: {payload}")
        except Exception as e:
            self.logger.error(f"Error handling motion detection: {e}")
            
    def _handle_status_update(self, payload: str):
        """Handle status update message"""
        try:
            data = json.loads(payload)
            self.logger.debug(f"Status update: {data}")
            
            # Call custom callback if set
            if self.on_status_update:
                self.on_status_update(data)
                
        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON in status payload: {payload}")
        except Exception as e:
            self.logger.error(f"Error handling status update: {e}")
            
    def _handle_motion_event(self, payload: str):
        """Handle motion event message"""
        self.logger.info(f"Motion event: {payload}")
        
    def _handle_error(self, payload: str):
        """Handle error message"""
        self.logger.error(f"ESP32 Error: {payload}")
        
    def _trigger_motion_action(self):
        """Trigger action when motion is detected"""
        try:
            if self.wled_controller:
                if hasattr(self.wled_controller, 'turn_on'):
                    self.wled_controller.turn_on()
                    self.logger.info("WLED turned on due to motion")
                elif hasattr(self.wled_controller, 'activate'):
                    self.wled_controller.activate()
                    self.logger.info("WLED activated due to motion")
                else:
                    self.logger.warning("WLED controller has no recognized activation method")
            else:
                self.logger.debug("No WLED controller configured")
                
        except Exception as e:
            self.logger.error(f"Error triggering motion action: {e}")
            
    def _end_motion_action(self):
        """End motion action after timeout"""
        try:
            with self._lock:
                if self._motion_active:
                    self._motion_active = False
                    self.logger.info("Motion timeout reached, ending motion action")
                    
                    if self.wled_controller:
                        if hasattr(self.wled_controller, 'turn_off'):
                            self.wled_controller.turn_off()
                            self.logger.info("WLED turned off after motion timeout")
                        elif hasattr(self.wled_controller, 'deactivate'):
                            self.wled_controller.deactivate()
                            self.logger.info("WLED deactivated after motion timeout")
                            
                    # Call custom callback if set
                    if self.on_motion_ended:
                        self.on_motion_ended()
                        
        except Exception as e:
            self.logger.error(f"Error ending motion action: {e}")
            
    def _reset_motion_timer(self):
        """Reset the motion timeout timer"""
        if self._motion_timer:
            self._motion_timer.cancel()
            
        self._motion_timer = threading.Timer(self.motion_timeout, self._end_motion_action)
        self._motion_timer.start()
        
    def start(self):
        """Start the motion server (blocking call for thread)"""
        self._running = True
        self.logger.info("Starting MotionServer...")
        
        try:
            # Connect to MQTT broker
            self.client.connect(self.mqtt_host, self.mqtt_port, 60)
            
            # Start MQTT loop
            self.client.loop_start()
            
            # Keep running until stopped
            while self._running:
                time.sleep(1)
                
                # Reconnect if disconnected
                if not self._connected and self._running:
                    try:
                        self.logger.info("Attempting to reconnect to MQTT...")
                        self.client.reconnect()
                    except Exception as e:
                        self.logger.error(f"Reconnection failed: {e}")
                        time.sleep(4)  # Wait before next attempt
                        
        except Exception as e:
            self.logger.error(f"Error in motion server: {e}")
        finally:
            self._cleanup()
            
    def stop(self):
        """Stop the motion server"""
        self.logger.info("Stopping MotionServer...")
        self._running = False
        
    def _cleanup(self):
        """Clean up resources"""
        self.logger.info("Cleaning up MotionServer...")
        
        # Cancel motion timer
        if self._motion_timer:
            self._motion_timer.cancel()
            
        # End any active motion action
        if self._motion_active:
            self._end_motion_action()
            
        # Disconnect MQTT
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as e:
            self.logger.error(f"Error disconnecting MQTT: {e}")
            
    def get_status(self) -> Dict[str, Any]:
        """Get current server status"""
        with self._lock:
            return {
                'running': self._running,
                'mqtt_connected': self._connected,
                'motion_active': self._motion_active,
                'last_motion_time': self._last_motion_time,
                'motion_count': self._motion_count,
                'motion_timeout': self.motion_timeout
            }
            
    def set_motion_timeout(self, timeout: int):
        """Change motion timeout duration"""
        self.motion_timeout = timeout
        self.logger.info(f"Motion timeout set to {timeout} seconds")
        
    def is_motion_active(self) -> bool:
        """Check if motion is currently active"""
        with self._lock:
            return self._motion_active


# Example usage and testing
if __name__ == "__main__":
    # Create a .env file with:
    # MQTT_HOST=192.168.50.9
    # MQTT_PORT=1883
    # MQTT_USERNAME=your_username
    # MOTION_TIMEOUT=10
    
    # Mock WLED controller for testing
    class MockWLEDController:
        def __init__(self):
            self.state = False
            
        def turn_on(self):
            self.state = True
            print("Mock WLED: Turned ON")
            
        def turn_off(self):
            self.state = False
            print("Mock WLED: Turned OFF")
    
    # Custom callbacks example
    def on_motion_callback(data):
        print(f"Custom motion callback: {data}")
        
    def on_status_callback(data):
        print(f"Custom status callback: {data}")
    
    # Create and start motion server
    wled = MockWLEDController()
    motion_server = MotionServer(
        wled_controller=wled,
        debug=True
    )
    
    # Set custom callbacks
    motion_server.on_motion_detected = on_motion_callback
    motion_server.on_status_update = on_status_callback
    
    # Start in thread as requested
    from threading import Thread
    motion_thread = Thread(target=motion_server.start)
    motion_thread.daemon = True
    motion_thread.start()
    
    try:
        # Keep main thread alive
        while True:
            status = motion_server.get_status()
            print(f"Status: {status}")
            time.sleep(30)
    except KeyboardInterrupt:
        print("Shutting down...")
        motion_server.stop()
        motion_thread.join(timeout=5)