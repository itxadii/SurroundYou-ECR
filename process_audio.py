import boto3
import os
import time
import urllib.parse
import numpy as np
from pydub import AudioSegment
from pedalboard import Pedalboard, Reverb, Gain, Limiter
from scipy.interpolate import interp1d

# --- ADVANCED EFFECT FUNCTION (FIXED ROOM SIZE ASSIGNMENT) ---
def apply_8d_effect_advanced_dynamic(
    input_file,
    output_file,
    # Old Parameters
    dry_wet_mix=0.3, 
    gain_db=-0.2, 
    reverb_damping=0.5, 
    reverb_wet_level=0.1, 
    reverb_dry_level=0.3, 
    reverb_width=0.9, 
    limiter_threshold_db=30,
    # Dynamic/New Parameters
    random_pan_frequency=0.5, 
    bias_strength=2, 
    min_room_size=0.1, 
    max_room_size=0.6,
    room_size_frequency=0.5 
):
    # ... (function start code remains the same until the loop) ...

    start_time = time.time()
    audio = AudioSegment.from_mp3(input_file)
    samples = np.array(audio.get_array_of_samples()).astype(np.float32) / (2**15)
    
    if audio.channels == 1:
        samples = np.column_stack((samples, samples))
    else:
        samples = samples.reshape((-1, 2))

    sr = audio.frame_rate
    duration = len(samples) / sr
    total_samples = len(samples)
    
    num_pan_points = max(2, int(duration * random_pan_frequency))
    control_times_pan = np.linspace(0, duration, num_pan_points)
    biased_randoms = np.random.uniform(0, 1, num_pan_points)
    control_pans = np.where(biased_randoms < 0.5, -1.0, 1.0) * (0.5 + bias_strength/2)
    control_pans = np.clip(control_pans, -1, 1) 
    pan_interpolator = interp1d(control_times_pan, control_pans, kind='cubic', bounds_error=False, fill_value="extrapolate")
    
    num_room_points = max(2, int(duration * room_size_frequency))
    control_times_room = np.linspace(0, duration, num_room_points)
    control_room_sizes = np.random.uniform(min_room_size, max_room_size, num_room_points)
    room_interpolator = interp1d(control_times_room, control_room_sizes, kind='cubic', bounds_error=False, fill_value="extrapolate")

    output_audio = np.zeros_like(samples)
    step_size_samples = 1024 

    board = Pedalboard([
        Gain(gain_db=gain_db),
        Reverb(
            room_size=min_room_size, 
            damping=reverb_damping,
            wet_level=reverb_wet_level,
            dry_level=reverb_dry_level,
            width=reverb_width
        ),
        Limiter(threshold_db=limiter_threshold_db)
    ])
    
    reverb_plugin = next(p for p in board if isinstance(p, Reverb))

    for i in range(0, total_samples, step_size_samples):
        chunk = samples[i : i + step_size_samples]
        if len(chunk) == 0:
            continue
            
        # Time array for the chunk - we only need the start time for the current room size
        chunk_start_time = i / sr
        chunk_time_array = np.linspace(chunk_start_time, (i + len(chunk)) / sr, len(chunk))

        # --- Apply Panning to this chunk ---
        chunk_pan_mod = pan_interpolator(chunk_time_array)
        chunk_pan_mod = np.clip(chunk_pan_mod, -1.0, 1.0)
        
        left_gain = np.sqrt(0.5 * (1 - chunk_pan_mod))
        right_gain = np.sqrt(0.5 * (1 + chunk_pan_mod))
        panned_chunk = np.column_stack((chunk[:, 0] * left_gain, chunk[:, 1] * right_gain))
        
        # --- Update Dynamic Reverb Room Size for this chunk (FIXED) ---
        # Get ONE float value from the interpolator using the chunk start time
        current_room_size_float = float(room_interpolator(chunk_start_time)) 
        reverb_plugin.room_size = current_room_size_float # Assign single float value

        processed_chunk = board.process(panned_chunk.T.astype(np.float32), float(sr), reset=False) 
        
        output_audio[i : i + len(chunk)] = processed_chunk.T

    # ... (Export logic remains the same) ...

    final_output_segment = AudioSegment(
        (output_audio * (2**15 - 1)).astype(np.int16).tobytes(),
        frame_rate=sr, sample_width=2, channels=2
    )
    final_output_segment.export(output_file, format='mp3', bitrate='192k')

    end_time = time.time()
    processing_time = end_time - start_time
    print(f"Dynamic 8D audio processed and saved to {output_file}")
    print(f"Processing Time: {processing_time:.2f} seconds")


# --- LOCAL TEST MODE LOGIC (PATHS FIXED) ---

def run_local_test_mode():
    # Use double backslashes or raw strings to fix the SyntaxWarning
    input_path = r"C:\Users\Admin\Desktop\surroundyou-fargate\input\aud.mp3"
    output_path = r"C:\Users\Admin\Desktop\surroundyou-fargate\output\8D-dynamic-biased-output.mp3"

    print(f"Input file: {input_path}")

    try:
        apply_8d_effect_advanced_dynamic(
            input_file=input_path, 
            output_file=output_path, 
            dry_wet_mix=0.5, 
            gain_db=-0.2, 
            reverb_damping=0.9, 
            reverb_wet_level=0.55, 
            reverb_dry_level=0.6, 
            reverb_width=0.9, 
            limiter_threshold_db=10,
            random_pan_frequency=0.5,
            bias_strength=0.9, 
            min_room_size=0.3, 
            max_room_size=0.8, 
            room_size_frequency=0.2 
        )
    except Exception as e:
        print(f"An error occurred during local testing: {e}")

# --- SCRIPT ENTRY POINT ---
if __name__ == "__main__":
    if 'S3_BUCKET' in os.environ and 'S3_KEY' in os.environ:
        print("Fargate mode not fully implemented in provided code, running local test.")
        run_local_test_mode()
    else:
        run_local_test_mode()
