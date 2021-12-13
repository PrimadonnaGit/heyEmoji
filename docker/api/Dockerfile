FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9
WORKDIR /app
ADD ./docker/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt
ENV API_ENV=prod
CMD ["uvicorn", "heyEmoji.main:app", "--host", "0.0.0.0", "--port", "8000"]