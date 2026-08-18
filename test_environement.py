import subprocess, sys, platform
print("=== SYSTEME ===")
print("OS       :", platform.platform())
print("Python   :", sys.version.split()[0])
print("Exec     :", sys.executable)

print("\n=== GLIBC ===")
print(subprocess.run(['ldd','--version'], capture_output=True, text=True).stdout.split('\n')[0])

print("\n=== GPU / DRIVER ===")
print(subprocess.run(['nvidia-smi','--query-gpu=name,driver_version,memory.total',
                      '--format=csv,noheader'], capture_output=True, text=True).stdout)

print("=== CUDA TOOLKIT ===")
r = subprocess.run(['nvcc','--version'], capture_output=True, text=True)
print(r.stdout.strip() if r.returncode==0 else "nvcc absent")
print(subprocess.run('ls -d /usr/local/cuda* 2>/dev/null', shell=True,
                     capture_output=True, text=True).stdout)
print("libcudart dispo :")
print(subprocess.run('find / -name "libcudart.so.*" 2>/dev/null | head -5',
                     shell=True, capture_output=True, text=True).stdout)

print("=== TORCH ===")
try:
    import torch
    print("torch    :", torch.__version__, "| cuda build:", torch.version.cuda)
    print("available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("capability:", torch.cuda.get_device_capability(0))
except Exception as e:
    print("torch:", e)

print("\n=== PACKAGES CLES ===")
print(subprocess.run(
    'pip list 2>/dev/null | grep -Ei "^(torch|transformers|vllm|accelerate|kernels|xformers|flashinfer|numpy|openpyxl|pymupdf|pillow|triton)"',
    shell=True, capture_output=True, text=True).stdout)

print("=== ACCES RESEAU ===")
for url in ['https://pypi.org', 'https://download.pytorch.org', 'https://github.com', 'https://wheels.vllm.ai']:
    r = subprocess.run(['curl','-s','-o','/dev/null','-w','%{http_code}','--max-time','8',url],
                       capture_output=True, text=True)
    print(f"  {url:38s} -> {r.stdout}")

print("\n=== DROITS ===")
print("write venv :", subprocess.run('touch $(python -c "import site;print(site.getsitepackages()[0])")/.t 2>&1 && echo OK || echo READONLY',
                                     shell=True, capture_output=True, text=True).stdout.strip())
print("disk /home :", subprocess.run('df -h /home | tail -1', shell=True, capture_output=True, text=True).stdout.strip())
