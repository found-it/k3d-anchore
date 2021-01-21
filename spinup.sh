
# set -Eeuo pipefail

# TODO: Handle these arguments properly
dockerhub_username=$1
dockerhub_email=$2

k3d_version="v3.4.0"
agent_count=3
cluster_api_port=8443
loadbalancer_port=8080
cluster_name="anchore"
kubeconfig_path="$HOME/.kube/$cluster_name.conf"

if [ -z $dockerhub_username ] || [ -z $dockerhub_email ]; then
    printf "\n"
    printf "ERROR: Incorrect arguments..\n"
    printf "\n"
    printf "  Usage:\n"
    printf "\n"
    printf "    bash spinup.sh <dockerhub_username> <dockerhub_email>\n"
    printf "\n"
    exit 1
fi

# bash -s -- --no-sudo
printf "Checking if k3d is installed\n"
command -v k3d > /dev/null || {
    printf "k3d not found. Installing..\n"
    curl -s https://raw.githubusercontent.com/rancher/k3d/main/install.sh | \
        TAG=$k3d_version bash
}


printf "Cleanup old %s cluster if applicable\n" "$cluster_name"
k3d cluster get $cluster_name
if [ $? -eq 0 ]; then
    k3d cluster delete $cluster_name
    rm -f $kubeconfig_path
    unset KUBECONFIG
    sleep 5
fi


printf "Create %s cluster\n" "$cluster_name"
k3d cluster create "$cluster_name"      \
    --agents=$agent_count               \
    --update-default-kubeconfig=false   \
    --switch-context=false              \
    --port=$loadbalancer_port:80@loadbalancer     \
    --wait=true

printf "Configure the kube config for %s in %s\n" "$cluster_name" "$kubeconfig_path"
k3d kubeconfig get $cluster_name > $kubeconfig_path
while [ $? -ne 0 ]
do
    printf "Waiting for %s to come up\n" "$cluster_name"
    sleep 5
    k3d kubeconfig get $cluster_name > $kubeconfig_path
done

export KUBECONFIG="$kubeconfig_path"
echo "$kubeconfig_path"

kubectl create ns anchore

kubectl --kubeconfig=$kubeconfig_path create secret \
    docker-registry anchore-dockerhub-creds \
    --docker-server=docker.io \
    --docker-username=$dockerhub_username \
    --docker-password=$(security find-internet-password -a $dockerhub_username -gw) \
    --docker-email=$dockerhub_email \
    -n anchore

kubectl --kubeconfig=$kubeconfig_path create secret \
    generic anchore-license \
    --from-file=license.yaml=license.yaml \
    -n anchore

helm repo add anchore https://charts.anchore.io

if test -f values.yaml; then
    helm install enterprise -f values.yaml anchore/anchore-engine -n anchore
else
    printf "No values.yaml file found. Spinning up default anchore deployment\n"
    helm install enterprise anchore/anchore-engine -n anchore
fi
