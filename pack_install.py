# 1. vLLM + torch cu128 — uv auto-détecte CUDA 12.8
uv pip install vllm --torch-backend auto

# 2. Torch cu128 explicite (vLLM bundle parfois une version incompatible)
uv pip install torch torchvision \
    --index-url https://download.pytorch.org/whl/cu128 \
    --reinstall

# 3. Dépendances de ton pipeline
uv pip install \
    transformers>=5.0 \
    tokenizers \
    accelerate \
    pymupdf \
    pillow \
    openpyxl \
    numpy \
    pandas \
    qwen-vl-utils \
    sentencepiece \
    protobuf

# 4. Vérification
python3 -c "
import torch, vllm
print('vllm :', vllm.__version__)
print('torch:', torch.__version__, '| cuda:', torch.version.cuda)
print('GPU  :', torch.cuda.get_device_name(0))
print('VRAM :', round(torch.cuda.get_device_properties(0).total_memory/1e9,1), 'GB')
print('OK' if torch.cuda.is_available() else 'ERREUR GPU')
"
