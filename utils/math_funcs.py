import numpy as np

def generate_sine_wave(n_leds, frequency=0.1, amplitude=1.0):
    x = np.arange(n_leds)
    sine_wave = amplitude * np.sin(2 * np.pi * frequency * x / n_leds)
    return (sine_wave + 1) / 2