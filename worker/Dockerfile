FROM python:3.14-slim
WORKDIR /app
ENV PYTHONPATH=/app
RUN pip install --no-cache-dir requests
COPY neuron.py /app/
COPY sample.py /
CMD ["python", "/sample.py"]
