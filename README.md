# Cerebro

## Run with minikube

Build the images:
```
$ minikube image build . -t cerebro:latest -f k8s/cerebro.dock
$ minikube image build . -t job:latest -f k8s/job.dock
```

Deploy Cerebro and TheHive:
```
$ kubectl apply -f k8s/thehive.yml -f k8s/cerebro.yml
```

Access TheHive:
```
$ minikube service thehive --url
$ export THEHIVE=http://127.0.0.1:<port>
```

## Create alerts

With a user created in a non admin organisation (set as default):
```
$ curl -X POST -H 'Content-Type: application/json' $THEHIVE/api/v1/alert -u user@thehive.local:secret -d @tests/alert.json
```

## Develop locally

```
$ python3 -m venv venv
$ . venv/bin/activate
$ pip install -e .[dev]
$ pytest
```
