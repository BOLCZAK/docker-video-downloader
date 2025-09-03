# Wybieramy bazowy obraz z Pythona
FROM python:3.9-slim

# Ustalamy katalog roboczy w kontenerze
WORKDIR /app

# Instalujemy niezbędne zależności systemowe (w tym ffmpeg)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean

# Kopiujemy plik requirements.txt do kontenera
COPY requirements.txt /app/

# Instalujemy zależności
RUN pip install --no-cache-dir -r requirements.txt

# Kopiujemy resztę aplikacji (w tym pliki .html i inne)
COPY . /app/

# Eksponujemy port, na którym działa aplikacja Flask (domyślnie port 5000)
EXPOSE 5000

# Ustawiamy zmienną środowiskową, aby Flask działał w trybie produkcyjnym
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Komenda do uruchomienia aplikacji Flask
#CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]

# Komenda do uruchomienia aplikacji Flask przez Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
