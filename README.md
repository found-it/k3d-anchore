# k3d Anchore Deployment

#### Installation

This repo comes with a Makefile so you can just run
```sh
make install
```

This will install a local pip package in editable mode, it doesn't install on the system (future work)

#### Script Usage

From the root of this repo you can use the following command to spin up a basic deployment of Anchore Engine

```sh
python3 spinup --values=values.yaml engine
```

This will delete any old clusters named `anchore` and then spin up a new Anchore Enterprise deployment. It _currently_ uses the MacOS Keychain to grab the password for the dockerhub pullcreds. If you are using another system then you will need to change the secret creation line. Future work will remove this dependency.

The cluster will expose the loadbalancer to port 8080 on the host machine and will set up ingresses so you will want to put the following in `etc/hosts`
```
# Local Dev Cluster
127.0.0.1   anchore-api.k3d.localhost
127.0.0.1   anchore-ui.k3d.localhost
# End of section
```

Then to access the UI navigate to [anchore-ui.k3d.localhost:8080](anchore-ui.k3d.localhost:8080)

To access the API use the following credentials (or the ones you have configured)

```yaml
default:
  ANCHORE_CLI_USER: 'admin'
  ANCHORE_CLI_PASS: 'foobar'
  ANCHORE_CLI_URL: http://anchore-api.k3d.localhost:8080/v1/
```


# Dev Notes

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
