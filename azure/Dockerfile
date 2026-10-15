# The GPU container image: the same Jupyter + interp stack that pod_setup.sh used to install on every pod
# restart, built once. Built in the cloud by azure/build.sh (no Docker needed on the laptop).
#
# Rebuild (azure/build.sh, ~10 min) only when a package changes. Code in src/ and pod/ is NOT in the image: it
# lives on the project's file share, mounted at /workspace/<project>, and is uploaded by azure/push.sh.
FROM pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1 \
    HF_HOME=/scratch/hf-cache HF_HUB_ENABLE_HF_TRANSFER=1 HF_XET_HIGH_PERFORMANCE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates tmux && \
    rm -rf /var/lib/apt/lists/*

# Interp stack. transformer-lens / nnsight may pull a different torch; the check at the end fails the build loudly
# rather than at 3am inside a notebook (same guard as the old pod_setup.sh).
RUN TORCH_BEFORE="$(python -c 'import torch; print(torch.__version__)')" && \
    pip install -q -U \
      jupyterlab jupyter-mcp-tools ipykernel \
      'transformers>=5.4.0' accelerate huggingface_hub hf_transfer \
      transformer-lens nnsight \
      matplotlib pandas einops scikit-learn scipy pyyaml tqdm joblib && \
    TORCH_AFTER="$(python -c 'import torch; print(torch.__version__)')" && \
    if [ "$TORCH_BEFORE" != "$TORCH_AFTER" ]; then echo "torch changed $TORCH_BEFORE -> $TORCH_AFTER" >&2; exit 1; fi && \
    pip uninstall -y -q torchvision torchaudio || true

# Project-specific extras (same file the legacy pod/post_setup.sh installed from).
COPY pod/requirements-pod.txt /tmp/requirements-pod.txt
RUN if grep -q -v -E '^\s*(#|$)' /tmp/requirements-pod.txt; then pip install -q -r /tmp/requirements-pod.txt; fi

# /scratch: the container's own fast local disk (~470 GB, wiped when the container stops). The HF cache lives
# here: re-downloading a model from HF inside Azure runs at >1 GB/s, far faster than reading it off the share.
# /workspace: the project's file share, mounted at run time (code, data, notebooks, results; survives).
# The base image runs as a non-root user ("appuser"), so both must be world-writable (found by the first
# end-to-end test: the model download failed with PermissionError on /scratch/hf-cache).
RUN mkdir -p /scratch/hf-cache /workspace && chmod -R a+rwx /scratch /workspace

# A C compiler for Triton: vLLM (torch.compile and its LoRA kernels) JIT-compiles Triton kernels, and Triton builds
# a small C helper at first use. The runtime base image has no compiler ("Failed to find C compiler"; found by
# judge-rewards-hacking's first vLLM job, 2026-10-07). Added last so the pip layers above stay cached.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/* && \
    gcc --version | head -1
WORKDIR /workspace

COPY azure/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["jupyter"]
