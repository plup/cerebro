# Cerebro

## Run in kubernetes

Build the images:
```
$ docker buildx build . -t cerebro -f k8s/cerebro.dock
$ docker buildx build . -t job -f k8s/job.dock
```

Deploy Cerebro and TheHive:
```
$ kubectl apply -f k8s/
```

Access TheHive:
```
$ kubectl get svc/thehive
NAME      TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)
thehive   NodePort   10.43.112.109   <none>        9000:30001/TCP

$ export THEHIVE=http://localhost:30001
```

## Mount local files

Add a `hostPath` to mount the code and run cerebro from the code itself:
```
      volumes:
        - name: host-volume
          hostPath:
            path: /path/on/host
      containers:
        - name: cerebro
          volumeMounts:
            - name: host-volume
              mountPath: /app
           env:
             - name: PYTHONPATH
               value: /app/src
```

Then reload the pods after a code change:
```
kubectl rollout restart deploy/cerebro
```

## Create alerts

With a user created in a non admin organisation (set as default):
```
$ curl -X POST -H 'Content-Type: application/json' $THEHIVE/api/v1/alert -u user@thehive.local:secret -d @tests/alert.json
```
