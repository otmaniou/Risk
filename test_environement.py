python3 -c "
import sys, subprocess, os, glob

print('=== PYTHON ===')
print(sys.version)

print('\n=== GPU (nvidia-smi) ===')
subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version,memory.total,compute_cap', '--format=csv,noheader'])

print('\n=== CUDA VERSION ===')
for f in glob.glob('/usr/local/cuda*/version*.txt') + glob.glob('/usr/local/cuda*/version.json'):
    print(f'-- {f}')
    subprocess.run(['cat', f])
r = subprocess.run('ls /usr/local/ | grep cuda', shell=True, capture_output=True, text=True)
print('cuda dirs:', r.stdout.strip())

print('\n=== LIBCUDART (sans nvcc) ===')
subprocess.run('ldconfig -p | grep libcudart', shell=True)

print('\n=== TORCH ===')
try:
    import torch
    print('torch:', torch.__version__)
    print('torch.cuda:', torch.version.cuda)
    print('GPU dispo:', torch.cuda.is_available())
    if torch.cuda.is_available():
        print('GPU name:', torch.cuda.get_device_name(0))
        print('capability:', torch.cuda.get_device_capability(0))
        print('VRAM total:', round(torch.cuda.get_device_properties(0).total_memory/1e9,1), 'GB')
except ImportError:
    print('torch non installe')

print('\n=== TRANSFORMERS ===')
try:
    import transformers; print(transformers.__version__)
except: print('non installe')

print('\n=== UV / PIP ===')
subprocess.run('which uv && uv --version || echo uv absent', shell=True)
subprocess.run(['pip', '--version'])

print('\n=== GLIBC ===')
r = subprocess.run('ldd --version | head -1', shell=True, capture_output=True, text=True)
print(r.stdout.strip())

print('\n=== OS ===')
subprocess.run('cat /etc/os-release | grep -E \"^(NAME|VERSION)=\"', shell=True)
" 2>&1
