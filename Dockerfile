FROM python:3.13-alpine
RUN apk add --no-cache tzdata
COPY app /app
RUN printf '#!/usr/bin/env python3\nimport sys\nsys.path.insert(0, "/app")\nimport ps5backup\nsys.exit(ps5backup.main())\n' > /usr/local/bin/ps5backup \
 && chmod 755 /usr/local/bin/ps5backup
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8765
ENTRYPOINT ["ps5backup"]
CMD ["daemon"]
