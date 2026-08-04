import subprocess
import sys
import shutil

print("Installing requirements...")
uv_path = shutil.which("uv")
if uv_path:
    print("Using 'uv' for ultra-fast package installation...")
    try:
        subprocess.run([uv_path, "pip", "install", "-r", "requirements.txt"], check=True)
    except subprocess.CalledProcessError:
        print("Installation with 'uv' failed. Falling back to standard 'pip'...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
else:
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

print("Installing Playwright browsers...")
subprocess.run([sys.executable, "-m", "playwright", "install"], check=True)

print("\n✅ Setup complete! Run 'python main.py' to start MARK XXV.")

