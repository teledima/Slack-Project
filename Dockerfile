FROM python:3.9
WORKDIR /app
COPY requirements.txt /app
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python", "-m", "gunicorn", "-b", ":8080", "main_file:app"]
