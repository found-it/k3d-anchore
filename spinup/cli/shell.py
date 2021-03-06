import logging
import os
import shutil
import subprocess
import sys


def stream_output(cmd, redact=None):
    try:
        os.environ["PYTHONUNBUFFERED"] = "1"
        if redact:
            redacted = [r.replace(redact, "<redacted>") for r in cmd]
            logging.info(" ".join(redacted))
        else:
            logging.info(" ".join(cmd))
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
        )

        while p.poll() is None:
            line = p.stdout.readline().strip()
            if line:
                logging.info(line)
        os.environ["PYTHONUNBUFFERED"] = "0"

    except subprocess.SubprocessError:
        logging.exception(" ".join(cmd))
        sys.exit(1)

    return p


def preflight():
    die = 0
    cmds = ["k3d", "helm", "kubectl"]
    for cmd in cmds:
        if not shutil.which(cmd):
            logging.error(f"Need to install {cmd}")
            die = 1
        else:
            logging.info(f"Found {cmd}")

    if die:
        sys.exit(1)

    logging.info("Preflight checks passed")


def get_kubeconfig(cluster_name):
    cmd = ["k3d", "kubeconfig", "write", cluster_name]
    try:
        logging.info(" ".join(cmd))
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )
    except subprocess.SubprocessError:
        logging.exception(" ".join(cmd))
        sys.exit(1)

    if p.returncode != 0:
        logging.error(p.stdout)
        logging.error(p.stderr)
        sys.exit(p.returncode)

    return p.stdout


def get_password(username):
    # TODO: Give option to prompt in cli
    cmd = ["security", "find-internet-password", "-a", username, "-gw"]
    try:
        logging.info(" ".join(cmd))
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )
    except subprocess.SubprocessError:
        logging.exception(" ".join(cmd))
        sys.exit(1)

    if p.returncode != 0:
        logging.error(p.stderr)
        sys.exit(p.returncode)

    return p.stdout[:-1]


def create_pullcreds(config, username, email, hardened=False):
    # TODO: Fix ImagePullBackoff for hardened
    if hardened:
        registry = "registry1.dso.mil"
    else:
        registry = "docker.io"

    password = get_password(username)
    stream_output(
        [
            "kubectl",
            "--kubeconfig",
            config,
            "create",
            "secret",
            "docker-registry",
            "anchore-enterprise-pullcreds",
            "--docker-server",
            registry,
            "--docker-username",
            username,
            "--docker-password",
            password,
            "--docker-email",
            email,
            "--namespace",
            "anchore",
        ],
        redact=password,
    )


def helm_upgrade(config, values, hardened=False, enterprise=False):
    cmd = [
        "helm",
        "--kubeconfig",
        config,
        "upgrade",
        "--namespace",
        "anchore",
        "--install",
        "anchore",
        "anchore/anchore-engine",
        "--values",
        values,
    ]

    if enterprise:
        cmd += ["--set", "anchoreEnterpriseGlobal.enabled=true"]

    if hardened:
        cmd += [
            "--set",
            "anchoreEnterpriseGlobal.image=registry1.dso.mil/anchore/enterprise/enterprise:3.0.0",
            "--set",
            "anchoreEnterpriseUi.image=registry1.dso.mil/anchore/enterpriseui/enterpriseui:3.0.0",
            "--set",
            "anchoreGlobal.image=registry1.dso.mil/anchore/engine/engine:0.9.0",
        ]
    stream_output(cmd)


def create_cluster(fresh, cluster_name, agent_count, loadbalancer_port):
    preflight()

    cmd = ["k3d", "cluster", "get", cluster_name]
    exists = stream_output(cmd)
    if exists.returncode == 0:
        if fresh:
            logging.info(f"{cluster_name} cluster exists. Deleting it..")
            cmd = ["k3d", "cluster", "delete", cluster_name]
            stream_output(cmd)
        else:
            logging.warning(f"{cluster_name} already exists.")
            logging.warning("Use --fresh if you want to replace it.")
            sys.exit(0)

    logging.info(f"Creating cluster {cluster_name}")
    cmd = [
        "k3d",
        "cluster",
        "create",
        cluster_name,
        "--agents",
        agent_count,
        "--update-default-kubeconfig=false",
        "--switch-context=false",
        "--port",
        f"{loadbalancer_port}:80@loadbalancer",
        "--wait=true",
    ]
    stream_output(cmd)

    config = get_kubeconfig(cluster_name=cluster_name).strip()
    stream_output(["kubectl", "--kubeconfig", config, "create", "ns", "anchore"])

    logging.info("export KUBECONFIG=(k3d kubeconfig write anchore)")
    return config
