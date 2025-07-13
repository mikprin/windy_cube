#!/usr/bin/env python3
"""
Microphone monitor using PulseAudio pactl (no additional deps)
Works on most modern Linux systems with PulseAudio
"""

import subprocess
import time
import re
import sys

class MicMonitorPulse:
    def __init__(self):
        self.running = False
        self.source_name = None
        
    def get_default_source(self):
        """Get default audio input source"""
        try:
            result = subprocess.run(['pactl', 'get-default-source'], 
                                  capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except:
            return None
    
    def get_source_volume(self, source):
        """Get current volume level of audio source"""
        try:
            result = subprocess.run(['pactl', 'list', 'sources'], 
                                  capture_output=True, text=True, check=True)
            
            # Find our source section
            lines = result.stdout.split('\n')
            in_our_source = False
            
            for line in lines:
                if f"Name: {source}" in line:
                    in_our_source = True
                elif line.startswith('Source #') and in_our_source:
                    break
                elif in_our_source and 'Volume:' in line:
                    # Extract volume percentage
                    volume_match = re.search(r'(\d+)%', line)
                    if volume_match:
                        return int(volume_match.group(1))
            return 0
        except:
            return 0
    
    def monitor_with_parec(self):
        """Monitor using parec (PulseAudio record)"""
        print("🎤 PulseAudio microphone monitor")
        print("Press Ctrl+C to stop")
        print("-" * 50)
        
        try:
            # Start parec process to capture audio
            cmd = ['parec', '--format=s16le', '--rate=44100', '--channels=1']
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            while True:
                # Read a small chunk of audio data
                data = process.stdout.read(4096)  # 2048 samples * 2 bytes
                if not data:
                    break
                
                # Convert bytes to amplitude (simple approach)
                # This is a rough approximation
                max_val = 0
                for i in range(0, len(data), 2):
                    if i + 1 < len(data):
                        sample = int.from_bytes(data[i:i+2], byteorder='little', signed=True)
                        max_val = max(max_val, abs(sample))
                
                # Normalize to percentage
                amplitude_percent = (max_val / 32767) * 100
                
                # Create visual bar
                bar_length = 40
                filled_length = int(bar_length * amplitude_percent / 100)
                bar = '█' * filled_length + '░' * (bar_length - filled_length)
                
                print(f"\rAmplitude: {amplitude_percent:5.1f}% |{bar}|", end='', flush=True)
                
                time.sleep(0.05)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Monitoring stopped")
            if 'process' in locals():
                process.terminate()
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Make sure PulseAudio is running: pulseaudio --check -v")

if __name__ == "__main__":
    monitor = MicMonitorPulse()
    monitor.monitor_with_parec()