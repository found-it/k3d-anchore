#!/usr/bin/env python3

import pathlib
import os
import sys
import argparse
import subprocess
import shutil

import logging

DEFAULT_FORMAT = "%(levelname)-4s | %(message)s"
# DEFAULT_FORMAT = "%(name)-4s | %(levelname)-4s | %(message)s"

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format=DEFAULT_FORMAT)

CLUSTER_GET = "k3d cluster get".split(" ")
CLUSTER_CREATE = "k3d cluster create".split(" ")
CLUSTER_DELETE = "k3d cluster delete".split(" ")


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


def main():

    preflight()

    # Arguments
    parser = argparse.ArgumentParser(description="Run pipelines arguments")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Testing flag to dry run the script",
    )
    parser.add_argument(
        "--hardened",
        action="store_true",
        help="Use registry1 images",
    )
    parser.add_argument(
        "--engine",
        action="store_true",
        help="Install engine deployment",
    )
    parser.add_argument(
        "--enterprise",
        action="store_true",
        help="Install enterprise deployment",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Install a fresh cluster even if there is already one under the same name",
    )
    parser.add_argument(
        "--cluster-name",
        default="anchore",
        type=str,
        help="Name for cluster.",
    )
    parser.add_argument(
        "--agent-count",
        default="5",
        type=str,
        help="Number of agents in cluster.",
    )
    parser.add_argument(
        "--lb-port",
        default=8080,
        type=int,
        help="Loadbalancer port.",
    )
    parser.add_argument(
        "--values",
        default="values.yaml",
        type=str,
        help="Path to values file.",
    )
    parser.add_argument(
        "--email",
        type=str,
        help="Email for image pullcreds.",
    )
    parser.add_argument(
        "--username",
        type=str,
        help="Username for image pullcreds.",
    )
    parser.add_argument(
        "--kubeconfig",
        type=str,
        help="Kube Config path.",
    )
    parser.add_argument(
        "--license",
        type=str,
        help="Kube Config path.",
    )
    args = parser.parse_args()
    # End arguments

    if args.engine and args.enterprise:
        logging.error("Can't have both --engine and --enterprise")
        sys.exit(1)

    cmd = CLUSTER_GET + [args.cluster_name]
    exists = stream_output(cmd)
    if exists.returncode == 0:
        if args.fresh:
            logging.info(f"{args.cluster_name} cluster exists. Deleting it..")
            cmd = CLUSTER_DELETE + [args.cluster_name]
            stream_output(cmd)
        else:
            logging.warning(f"{args.cluster_name} already exists.")
            logging.warning("Use --fresh if you want to replace it.")
            sys.exit(0)

    logging.info(f"Creating cluster {args.cluster_name}")
    cmd = CLUSTER_CREATE + [
        args.cluster_name,
        "--agents",
        args.agent_count,
        "--update-default-kubeconfig=false",
        "--switch-context=false",
        "--port",
        f"{args.lb_port}:80@loadbalancer",
        "--wait=true",
    ]
    stream_output(cmd)

    config = get_kubeconfig(cluster_name=args.cluster_name).strip()
    stream_output(["kubectl", "--kubeconfig", config, "create", "ns", "anchore"])

    if args.enterprise:
        if not args.email:
            logging.error("Need email --email")
            sys.exit(1)

        if not args.username:
            logging.error("Need username --username")
            sys.exit(1)

        if not args.license:
            logging.error("Need path to license --license")
            sys.exit(1)

        if args.hardened:
            registry = "registry1.dso.mil"
        else:
            registry = "docker.io"

        password = get_password(args.username)
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
                args.username,
                "--docker-password",
                password,
                "--docker-email",
                args.email,
                "--namespace",
                "anchore",
            ],
            redact=password,
        )

        stream_output(
            [
                "kubectl",
                "--kubeconfig",
                config,
                "create",
                "secret",
                "generic",
                "anchore-enterprise-license",
                f"--from-file=license.yaml={args.license}",
                "--namespace",
                "anchore",
            ]
        )

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
        args.values,
    ]

    if args.enterprise:
        cmd += ["--set", "anchoreEnterpriseGlobal.enabled=true"]

    if args.hardened:
        cmd += [
            "--set",
            "anchoreEnterpriseGlobal.image=registry1.dso.mil/anchore/enterprise/enterprise:3.0.0",
            "--set",
            "anchoreEnterpriseUi.image=registry1.dso.mil/anchore/enterpriseui/enterpriseui:3.0.0",
            "--set",
            "anchoreGlobal.image=registry1.dso.mil/anchore/engine/engine:0.9.0",
        ]
    stream_output(cmd)

    logging.info("export KUBECONFIG=(k3d kubeconfig write anchore)")


if __name__ == "__main__":
    main()
