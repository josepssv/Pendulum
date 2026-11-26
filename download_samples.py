"""
Downloader for high-quality base acoustic instrument samples & organ soundscape banks.
Downloads dry, studio-quality samples into assets/samples/ for:
- piano, marimba, celesta, guitar-nylon, harp, drums
- organ-pipe, organ-harmonium, organ-hammond
And generates studio soundscape organ banks:
- organ-cathedral, organ-drone, organ-glass, organ-paisaje-mix
"""

import os
import time
import argparse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
import soundfile as sf
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(BASE_DIR, "assets", "samples")

HEADERS = {'User-Agent': 'Mozilla/5.0'}

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def download_file(url, dest_path, timeout=20, retries=2):
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1000:
        return True
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read()
                if len(content) > 500:
                    with open(dest_path, 'wb') as f:
                        f.write(content)
                    return True
        except Exception as e:
            if attempt >= retries:
                print(f"Error downloading {url}: {e}")
            else:
                time.sleep(0.4)
    return False


def download_batch_concurrent(url_dest_pairs, max_workers=6):
    """Downloads a list of (url, dest_path) concurrently."""
    ok_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(download_file, url, dst) for url, dst in url_dest_pairs]
        for fut in as_completed(futures):
            if fut.result():
                ok_count += 1
    return ok_count

def setup_piano():
    dest = os.path.join(SAMPLES_DIR, "piano")
    ensure_dir(dest)
    print("Downloading Piano samples...")
    # Download key notes across octaves from tonejs-instruments
    notes = [
        "A1", "C2", "E2", "G2", "B2",
        "D3", "F3", "A3", "C4", "E4",
        "G4", "B4", "D5", "F5", "A5",
        "C6", "E6", "G6", "B6", "C7"
    ]
    base_url = "https://raw.githubusercontent.com/nbrosowsky/tonejs-instruments/master/samples/piano/"
    for n in notes:
        url = f"{base_url}{n}.mp3"
        dest_file = os.path.join(dest, f"{n}.mp3")
        download_file(url, dest_file)
    print(f"Piano ready in {dest}")

def setup_marimba():
    dest = os.path.join(SAMPLES_DIR, "marimba")
    ensure_dir(dest)
    print("Downloading Marimba samples...")
    notes = [
        "C2", "E2", "G2", "C3", "E3", "G3",
        "C4", "E4", "G4", "C5", "E5", "G5",
        "C6", "E6", "G6", "C7"
    ]
    base_url = "https://raw.githubusercontent.com/gleitz/midi-js-soundfonts/gh-pages/FluidR3_GM/marimba-mp3/"
    for n in notes:
        url = f"{base_url}{n}.mp3"
        dest_file = os.path.join(dest, f"{n}.mp3")
        download_file(url, dest_file)
    print(f"Marimba ready in {dest}")

def setup_celesta():
    dest = os.path.join(SAMPLES_DIR, "celesta")
    ensure_dir(dest)
    print("Downloading Celesta samples...")
    notes = [
        "C3", "G3", "C4", "E4", "G4",
        "C5", "E5", "G5", "C6", "E6", "G6", "C7"
    ]
    base_url = "https://raw.githubusercontent.com/gleitz/midi-js-soundfonts/gh-pages/FluidR3_GM/celesta-mp3/"
    for n in notes:
        url = f"{base_url}{n}.mp3"
        dest_file = os.path.join(dest, f"{n}.mp3")
        download_file(url, dest_file)
    print(f"Celesta ready in {dest}")

def setup_guitar():
    dest = os.path.join(SAMPLES_DIR, "guitar-nylon")
    ensure_dir(dest)
    print("Downloading Nylon Guitar samples...")
    notes = [
        "E2", "A2", "D3", "G3", "B3",
        "E4", "A4", "D5", "G5", "B5"
    ]
    base_url = "https://raw.githubusercontent.com/nbrosowsky/tonejs-instruments/master/samples/guitar-nylon/"
    for n in notes:
        url = f"{base_url}{n}.mp3"
        dest_file = os.path.join(dest, f"{n}.mp3")
        download_file(url, dest_file)
    print(f"Nylon Guitar ready in {dest}")

def setup_harp():
    dest = os.path.join(SAMPLES_DIR, "harp")
    ensure_dir(dest)
    print("Downloading Harp samples...")
    notes = [
        "C2", "G2", "C3", "G3", "C4", "G4",
        "C5", "G5", "C6", "G6"
    ]
    base_url = "https://raw.githubusercontent.com/nbrosowsky/tonejs-instruments/master/samples/harp/"
    for n in notes:
        url = f"{base_url}{n}.mp3"
        dest_file = os.path.join(dest, f"{n}.mp3")
        download_file(url, dest_file)
    print(f"Harp ready in {dest}")

def setup_drums():
    dest = os.path.join(SAMPLES_DIR, "drums")
    ensure_dir(dest)
    print("Downloading Drum kit samples...")
    drum_files = {
        "kick.wav": "https://raw.githubusercontent.com/wesbos/JavaScript30/master/01%20-%20JavaScript%20Drum%20Kit/sounds/kick.wav",
        "snare.wav": "https://raw.githubusercontent.com/wesbos/JavaScript30/master/01%20-%20JavaScript%20Drum%20Kit/sounds/snare.wav",
        "hihat.wav": "https://raw.githubusercontent.com/wesbos/JavaScript30/master/01%20-%20JavaScript%20Drum%20Kit/sounds/hihat.wav",
        "openhat.wav": "https://raw.githubusercontent.com/wesbos/JavaScript30/master/01%20-%20JavaScript%20Drum%20Kit/sounds/openhat.wav",
        "tom.wav": "https://raw.githubusercontent.com/wesbos/JavaScript30/master/01%20-%20JavaScript%20Drum%20Kit/sounds/tom.wav",
        "clap.wav": "https://raw.githubusercontent.com/wesbos/JavaScript30/master/01%20-%20JavaScript%20Drum%20Kit/sounds/clap.wav",
        "ride.wav": "https://raw.githubusercontent.com/wesbos/JavaScript30/master/01%20-%20JavaScript%20Drum%20Kit/sounds/ride.wav"
    }
    for fname, url in drum_files.items():
        dest_file = os.path.join(dest, fname)
        download_file(url, dest_file)
    print(f"Drums ready in {dest}")

def setup_organ_pipe():
    dest = os.path.join(SAMPLES_DIR, "organ-pipe")
    ensure_dir(dest)
    print("Downloading Pipe Organ (organ-pipe) samples...")
    notes = [
        "C1", "Ds1", "Fs1", "A1",
        "C2", "Ds2", "Fs2", "A2",
        "C3", "Ds3", "Fs3", "A3",
        "C4", "Ds4", "Fs4", "A4",
        "C5", "Ds5", "Fs5", "A5",
        "C6"
    ]
    base_url = "https://raw.githubusercontent.com/nbrosowsky/tonejs-instruments/master/samples/organ/"
    pairs = [(f"{base_url}{n}.mp3", os.path.join(dest, f"{n}.mp3")) for n in notes]
    ok = download_batch_concurrent(pairs, max_workers=6)
    print(f"organ-pipe ready ({ok}/{len(pairs)} files) in {dest}")


def setup_organ_harmonium():
    dest = os.path.join(SAMPLES_DIR, "organ-harmonium")
    ensure_dir(dest)
    print("Downloading Harmonium (organ-harmonium) samples...")
    notes = [
        "C2", "D2", "E2", "Fs2", "Gs2", "As2",
        "C3", "D3", "E3", "Fs3", "Gs3", "As3",
        "C4", "D4", "E4", "Gs4", "As4",
        "C5"
    ]
    base_url = "https://raw.githubusercontent.com/nbrosowsky/tonejs-instruments/master/samples/harmonium/"
    pairs = [(f"{base_url}{n}.mp3", os.path.join(dest, f"{n}.mp3")) for n in notes]
    ok = download_batch_concurrent(pairs, max_workers=6)
    print(f"organ-harmonium ready ({ok}/{len(pairs)} files) in {dest}")


def setup_organ_hammond():
    dest = os.path.join(SAMPLES_DIR, "organ-hammond")
    ensure_dir(dest)
    print("Downloading Drawbar Hammond Organ (organ-hammond) samples...")
    notes = [
        "C2", "E2", "G2",
        "C3", "E3", "G3",
        "C4", "E4", "G4",
        "C5", "E5", "G5",
        "C6", "E6", "G6",
        "C7"
    ]
    base_url = "https://raw.githubusercontent.com/gleitz/midi-js-soundfonts/gh-pages/FluidR3_GM/drawbar_organ-mp3/"
    pairs = [(f"{base_url}{n}.mp3", os.path.join(dest, f"{n}.mp3")) for n in notes]
    ok = download_batch_concurrent(pairs, max_workers=6)
    print(f"organ-hammond ready ({ok}/{len(pairs)} files) in {dest}")


def setup_organs():
    ensure_dir(SAMPLES_DIR)
    setup_organ_pipe()
    setup_organ_harmonium()
    setup_organ_hammond()
    from generate_organ_soundscapes import generate_all
    generate_all()


def main():
    parser = argparse.ArgumentParser(description="Download acoustic samples & generate organ soundscapes.")
    parser.add_argument("--organs-only", action="store_true", help="Only set up the 7 organ soundscape banks.")
    args = parser.parse_args()

    ensure_dir(SAMPLES_DIR)
    if not args.organs_only:
        setup_piano()
        setup_marimba()
        setup_celesta()
        setup_guitar()
        setup_harp()
        setup_drums()
    setup_organs()
    print("All sample banks successfully set up!")


if __name__ == "__main__":
    main()
