# --- Base: Python + Zeek ---
FROM python:3.9-slim-trixie

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/opt/zeek/bin:${PATH}"

# Install Zeek from official repo (with runtime deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg ca-certificates \
    && echo "deb http://download.opensuse.org/repositories/security:/zeek/Debian_13/ /" \
       > /etc/apt/sources.list.d/zeek.list \
    && curl -fsSL https://download.opensuse.org/repositories/security:/zeek/Debian_13/Release.key \
       | gpg --dearmor -o /etc/apt/trusted.gpg.d/zeek.gpg \
    && apt-get update \
    && apt-get install -y --no-install-recommends zeek \
    && rm -rf /var/lib/apt/lists/*

# --- App Setup ---
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY processor.py .

CMD ["python", "processor.py"]

