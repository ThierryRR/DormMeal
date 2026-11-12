FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501
# GEMINI_API_KEY is optional (free-text parsing); pass it at run time: docker run -e GEMINI_API_KEY=... 
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
