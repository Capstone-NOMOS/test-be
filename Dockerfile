FROM python:3.13-slim

WORKDIR /app

# 런타임 의존성이 없으므로 소스만 복사한다.
COPY app ./app

ENV PORT=8080 \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["python", "-m", "app"]
