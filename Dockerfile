FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Mount a folder with data files and read reports from it:
#   docker run --rm -v "$PWD:/work" -w /work metocean-qc check data/41010.txt --out reports/41010
ENTRYPOINT ["metqc"]
CMD ["--help"]
