
# set -Eeuo pipefail


fetch_inputs() {
    while getopts ":u:e:hd" opt;
    do
        case "${opt}" in
            u  )
                dockerhub_username="${OPTARG}"
                ;;

            e  )
                dockerhub_email="${OPTARG}"
                ;;

            d  )
                set -Eeuox pipefail
                ;;

            h  )
                usage
                exit 0 ;;

            \? )
                printf "\n Invalid Option: -%s\n\n" "${OPTARG}" >&2
                usage
                exit 1 ;;
        esac
    done
    shift $((OPTIND -1))
    if [ -z $dockerhub_username ] || [ -z $dockerhub_email ]; then
        printf "\n !! Missing options !!\n\n"
        usage
        exit 1
    fi
}

usage() {
cat << EOF

 Spin up Anchore using k3d from rancher

 This script will install k3d from rancher and spin up a cluster
 locally on your computer. It will then install Anchore using helm.

 Usage: bash ${0##*/} [ OPTIONS ]

   -u <string>  Docker Hub Username to use as pullcreds [REQUIRED].
   -e <email>   Docker Hub email [REQUIRED].
   -h           Display this menu.
   -d           Debug mode - prints out all commands before executing them.

EOF
}


install_k3d() {
    local -r k3d_version="$1"

    # bash -s -- --no-sudo
    printf "Checking if k3d is installed\n"
    command -v k3d > /dev/null || {
        printf "k3d not found. Installing..\n"
        curl -s https://raw.githubusercontent.com/rancher/k3d/main/install.sh | \
            TAG="$k3d_version" bash
    }
}


spinup_cluster() {
    local -r cluster_name="$1"
    local -r kubeconfig_path="$2"
    local -r agent_count="$3"
    local -r loadbalancer_port="$4"

    printf "Cleanup old %s cluster if applicable\n" "$cluster_name"
    k3d cluster get "$cluster_name"
    if [ $? -eq 0 ]; then
        k3d cluster delete "$cluster_name"
        rm -f "$kubeconfig_path"
        unset KUBECONFIG
        sleep 5
    fi


    printf "Create %s cluster\n" "$cluster_name"
    k3d cluster create "$cluster_name"              \
        --agents="$agent_count"                     \
        --update-default-kubeconfig=false           \
        --switch-context=false                      \
        --port="$loadbalancer_port:80@loadbalancer" \
        --wait=true

    printf "Configure the kube config for %s in %s\n" "$cluster_name" "$kubeconfig_path"
    k3d kubeconfig get "$cluster_name" > "$kubeconfig_path"
    while [ $? -ne 0 ]
    do
        printf "Waiting for %s to come up\n" "$cluster_name"
        sleep 5
        k3d kubeconfig get "$cluster_name" > "$kubeconfig_path"
    done

    export KUBECONFIG="$kubeconfig_path"
    echo "$kubeconfig_path"
}


install_anchore() {
    local -r kubeconfig_path="$1"
    local -r dockerhub_username="$2"
    local -r dockerhub_email="$3"

    kubectl create ns anchore

    kubectl --kubeconfig="$kubeconfig_path" create secret                                 \
        docker-registry anchore-dockerhub-creds                                           \
        --docker-server=docker.io                                                         \
        --docker-username="$dockerhub_username"                                           \
        --docker-password=$(security find-internet-password -a "$dockerhub_username" -gw) \
        --docker-email="$dockerhub_email"                                                 \
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
    # TODO: Give option to install kai
    # helm install kai anchore/kai
}


main() {
    dockerhub_username=''
    dockerhub_email=''

    k3d_version="v3.4.0"
    agent_count=5
    loadbalancer_port=8080
    cluster_name="anchore"
    kubeconfig_path="$HOME/.kube/$cluster_name.conf"

    fetch_inputs "$@"
    install_k3d "$k3d_version"
    spinup_cluster "$cluster_name" "$kubeconfig_path" "$agent_count" "$loadbalancer_port"
    install_anchore "$kubeconfig_path" "$dockerhub_username" "$dockerhub_email"
}

main "$@"
