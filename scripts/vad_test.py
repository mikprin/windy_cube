#!/usr/bin/env python3
"""
CLI script to test webrtcvad Voice Activity Detection
Usage: python test_webrtcvad.py [--aggressiveness 0-3] [--duration seconds]
"""

import argparse
import sys
import time
import collections
import pyaudio
import webrtcvad
import numpy as np
from datetime import datetime

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class VADTester:
    def __init__(self, aggressiveness=2):
        try:
            self.vad = webrtcvad.Vad(aggressiveness)
        except Exception as e:
            print(f"{Colors.RED}Error initializing VAD: {e}{Colors.ENDC}")
            sys.exit(1)
            
        self.sample_rate = 16000  # webrtcvad requires 8, 16, 32, or 48 kHz
        self.frame_duration = 30  # 30ms frames
        self.frame_size = int(self.sample_rate * self.frame_duration / 1000)
        
        # Statistics
        self.total_frames = 0
        self.speech_frames = 0
        self.silence_frames = 0
        
        # For voice activity tracking
        self.ring_buffer = collections.deque(maxlen=10)  # Last 10 frames
        self.in_speech = False
        
    def print_stats(self):
        if self.total_frames > 0:
            speech_percent = (self.speech_frames / self.total_frames) * 100
            silence_percent = (self.silence_frames / self.total_frames) * 100
            
            print(f"\n{Colors.BLUE}=== VAD Statistics ==={Colors.ENDC}")
            print(f"Total frames: {self.total_frames}")
            print(f"Speech: {self.speech_frames} ({speech_percent:.1f}%)")
            print(f"Silence: {self.silence_frames} ({silence_percent:.1f}%)")
    
    def process_frame(self, audio_data):
        """Process audio frame and return VAD result"""
        try:
            # Convert to bytes if numpy array
            if isinstance(audio_data, np.ndarray):
                audio_bytes = audio_data.astype(np.int16).tobytes()
            else:
                audio_bytes = audio_data
            
            is_speech = self.vad.is_speech(audio_bytes, self.sample_rate)
            
            # Update statistics
            self.total_frames += 1
            if is_speech:
                self.speech_frames += 1
            else:
                self.silence_frames += 1
                
            # Track speech segments
            self.ring_buffer.append(is_speech)
            
            # Determine if we're in a speech segment
            recent_speech = sum(self.ring_buffer)
            was_in_speech = self.in_speech
            
            if not self.in_speech and recent_speech >= 3:  # Start of speech
                self.in_speech = True
                return "SPEECH_START"
            elif self.in_speech and recent_speech <= 1:  # End of speech
                self.in_speech = False
                return "SPEECH_END"
            elif self.in_speech:
                return "SPEECH"
            else:
                return "SILENCE"
                
        except Exception as e:
            print(f"{Colors.RED}Error processing frame: {e}{Colors.ENDC}")
            return "ERROR"

def main():
    parser = argparse.ArgumentParser(description='Test webrtcvad Voice Activity Detection')
    parser.add_argument('--aggressiveness', '-a', type=int, default=2, choices=[0,1,2,3],
                       help='VAD aggressiveness (0=least, 3=most aggressive)')
    parser.add_argument('--duration', '-d', type=int, default=60,
                       help='Test duration in seconds (0 = infinite)')
    parser.add_argument('--show-amplitude', '-s', action='store_true',
                       help='Also show audio amplitude')
    
    args = parser.parse_args()
    
    print(f"{Colors.BOLD}WebRTC VAD Tester{Colors.ENDC}")
    print(f"Aggressiveness: {args.aggressiveness}")
    print(f"Sample Rate: 16000 Hz")
    print(f"Frame Duration: 30ms")
    print("=" * 50)
    
    # Initialize VAD
    vad_tester = VADTester(args.aggressiveness)
    
    # Initialize PyAudio
    try:
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=480,  # 30ms at 16kHz
            input_device_index=None  # Use default microphone
        )
    except Exception as e:
        print(f"{Colors.RED}Error opening audio stream: {e}{Colors.ENDC}")
        sys.exit(1)
    
    print(f"{Colors.GREEN}Listening... (Ctrl+C to stop){Colors.ENDC}")
    print("Legend:")
    print(f"  {Colors.GREEN}█{Colors.ENDC} = Speech detected")
    print(f"  {Colors.RED}█{Colors.ENDC} = Silence/noise")
    print(f"  {Colors.YELLOW}▲{Colors.ENDC} = Speech start")
    print(f"  {Colors.YELLOW}▼{Colors.ENDC} = Speech end")
    
    start_time = time.time()
    
    try:
        while True:
            # Check duration limit
            if args.duration > 0 and (time.time() - start_time) > args.duration:
                break
                
            # Read audio frame
            try:
                frame = stream.read(480, exception_on_overflow=False)
                audio_array = np.frombuffer(frame, dtype=np.int16)
                
                # Process with VAD
                vad_result = vad_tester.process_frame(frame)
                
                # Calculate amplitude if requested
                amplitude_str = ""
                if args.show_amplitude:
                    amplitude = np.sqrt(np.mean(audio_array.astype(float)**2))
                    amplitude_str = f" (amp: {amplitude:6.1f})"
                
                # Display result
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                
                if vad_result == "SPEECH_START":
                    print(f"[{timestamp}] {Colors.YELLOW}▲ SPEECH START{Colors.ENDC}{amplitude_str}")
                elif vad_result == "SPEECH_END":
                    print(f"[{timestamp}] {Colors.YELLOW}▼ SPEECH END{Colors.ENDC}{amplitude_str}")
                elif vad_result == "SPEECH":
                    print(f"[{timestamp}] {Colors.GREEN}█ SPEECH{Colors.ENDC}{amplitude_str}")
                elif vad_result == "SILENCE":
                    print(f"[{timestamp}] {Colors.RED}█ SILENCE{Colors.ENDC}{amplitude_str}")
                else:
                    print(f"[{timestamp}] ? {vad_result}{amplitude_str}")
                    
            except Exception as e:
                print(f"{Colors.RED}Error reading audio: {e}{Colors.ENDC}")
                break
                
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Stopping...{Colors.ENDC}")
    
    finally:
        # Cleanup
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        # Print final statistics
        vad_tester.print_stats()

if __name__ == "__main__":
    # Check dependencies
    try:
        import webrtcvad
        import pyaudio
        import numpy as np
    except ImportError as e:
        print(f"{Colors.RED}Missing dependency: {e}{Colors.ENDC}")
        print("Install with: pip install webrtcvad pyaudio numpy")
        sys.exit(1)
    
    main()