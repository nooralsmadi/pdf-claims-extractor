FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ghostscript \
    libpoppler-cpp-dev \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1 \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pdf_extractor.py  ./pdf_extractor.py
COPY driver.py         ./driver.py
COPY OCR_Test.pdf      ./OCR_Test.pdf

ENTRYPOINT ["python", "driver.py"]
