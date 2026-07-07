FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pyreadstat

# Copy application code
COPY app/ ./app/
COPY chat/ ./chat/

# Streamlit config
RUN mkdir -p /root/.streamlit
RUN echo '[server]\nport = 8080\naddress = "0.0.0.0"\nheadless = true\nenableCORS = false\nenableXsrfProtection = false\n' > /root/.streamlit/config.toml

EXPOSE 8080

CMD ["streamlit", "run", "app/main.py", "--server.port=8080", "--server.address=0.0.0.0"]
