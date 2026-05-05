# TheHive create alerts

```
$ curl -u user@thehive.local:'<pass>' -H 'Content-Type: application/json' https://thehive/api/v1/alert -d '{
  "type": "alertType",
  "source": "test",
  "sourceRef": "1",
  "title": "alert title",
  "description": "alert description",
  "observables": [
     { "dataType": "url", "data": "http://example.org" },
     { "dataType": "mail", "data": "foo@example.org" }
  ]
}'
```
