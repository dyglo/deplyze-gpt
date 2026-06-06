FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        python3 \
        python3-pip \
        libglib2.0-0 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt

RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install --extra-index-url https://download.pytorch.org/whl/cu121 \
        torch==2.5.1+cu121 \
        torchvision==0.20.1+cu121 \
    && python3 -m pip install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
