
Need to use something like
```sh
k3d cluster create --agents 3 --servers 1 -p 8080:80@loadbalancer anchore
```

Which will expose the loadbalancer to port 8080 on the host machine.

Need to put the following in `etc/hosts`
```
# Local Dev Cluster
127.0.0.1   anchore-api.k3d.localhost
127.0.0.1   anchore-ui.k3d.localhost
# End of section
```

To use curl to access stuff
```sh
curl  http://anchore-api.k3d.localhost:8080/v1/ --resolve 'k3d.localhost:8080:127.0.0.1'
curl  http://anchore-ui.k3d.localhost:8080/ --resolve 'k3d.localhost:8080:127.0.0.1'
```

__Note: `--resolve` cannot be used with localhost for the address field. Must contain a numerical IP in both the command and `/etc/hosts`__


Creating an ingress for Anchore (manually)
```yaml
apiVersion: networking.k8s.io/v1beta1
kind: Ingress
metadata:
  name: anchore-api
  labels:
    app: anchore
    component: ingress
spec:
  rules:
  - host: anchore-api.k3d.localhost
    http:
      paths:
      - path: /v1/
        backend:
          serviceName: engine-anchore-engine-api
          servicePort: 8228
  tls:
    - hosts:
      - anchore-api.k3d.localhost
```

Or you can just use the `ingress` field of the anchore values file
