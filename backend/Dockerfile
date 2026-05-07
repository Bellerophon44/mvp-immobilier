FROM python:3.12-slim

WORKDIR /app

# Installer les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code
COPY . .

# Lancer FastAPI avec uvicorn (PAS fastapi run)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
