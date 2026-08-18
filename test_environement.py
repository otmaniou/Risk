import subprocess, sys, platform

def sh(cmd, shell=True, timeout=30):
    try:
        r = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip() or "(vide)"
    except FileNotFoundError:
        return "ABSENT"
    except Exception as e:
        return f"ERREUR: {e}"

print("=== SYSTEME ===")
print("OS      :", platform.platform())
print("Arch    :", platform.machine())
print("Python  :", sys.version.split()[0])
print("Exec    :", sys.executable)

print("\n=== GLIBC (doit etre >= 2.28) ===")
print(sh("ldd --version | head -1"))

print("\n=== GPU / DRIVER ===")
print(sh("nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader"))

print("=== CUDA RUNTIME (le point decisif) ===")
print("Toolkit dirs :", sh("ls -d /usr/local/cuda* 2>/dev/null"))
print("libcudart trouves :")
print(sh('find / -name "libcudart.so*" 2>/dev/null | head -10'))
print("nvcc :", sh("nvcc --version 2>&1 | tail -1"))

print("\n=== TORCH ===")
try:
    import torch
    print("torch      :", torch.__version__, "| cuda build:", torch.version.cuda)
    print("available  :", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("capability :", torch.cuda.get_device_capability(0), "(9,0)=H100")
        print("device     :", torch.cuda.get_device_name(0))
except Exception as e:
    print("torch:", e)

print("\n=== PACKAGES CLES ===")
print(sh('pip list 2>/dev/null | grep -Ei "^(torch|transformers|vllm|accelerate|kernels|xformers|flashinfer|numpy|openpyxl|pymupdf|pillow|triton|ray)"'))

print("=== ACCES RESEAU ===")
for url in ['https://pypi.org', 'https://download.pytorch.org',
            'https://github.com', 'https://objects.githubusercontent.com',
            'https://wheels.vllm.ai']:
    code = sh(f'curl -s -o /dev/null -w "%{{http_code}}" --max-time 8 {url}')
    print(f"  {url:42s} -> {code}")

print("\n=== ESPACE DISQUE ===")
print(sh("df -h /home /tmp 2>/dev/null | grep -v '^Filesystem'"))
