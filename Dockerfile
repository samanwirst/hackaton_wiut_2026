# Alternative to requirements.txt. Build and run with a GPU:
#   docker build -t team .
#   docker run --gpus all -v /data/test:/data/test -v $PWD/out:/out team \
#          python run_submission.py --videos /data/test --out /out/predictions.json
FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime
ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 YOLO_OFFLINE=true
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "run_submission.py", "--videos", "/data/test", "--out", "/out/predictions.json"]
