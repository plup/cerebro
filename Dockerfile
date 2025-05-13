FROM registry.gitlab.com/plup/cerebro:1.0.2@sha256:bca684e2983db8bfa5ca0b1c95900e80591b778f52cbfb46c8aea98b478085a1
RUN pip install --root-user-action=ignore python-json-logger .
