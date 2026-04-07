FROM python:3.11-slim
RUN pip install requests
COPY neuron.py job.py /
ENTRYPOINT ["python", "/job.py"]
