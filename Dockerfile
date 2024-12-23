FROM registry.gitlab.com/plup/cerebro:latest
RUN pip install --root-user-action=ignore python-json-logger .
