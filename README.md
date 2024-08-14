# Cerebro

## Run with minikube

Build the images:
```
$ minikube image build . -t cerebro:latest -f images/cerebro.dock
$ minikube image build . -t job:latest -f images/job.dock
```

Deploy Cerebro and TheHive:
```
$ kubectl apply -f thehive.yml -f cerebro.yml
```

Access TheHive:
```
$ minikube service thehive
```
