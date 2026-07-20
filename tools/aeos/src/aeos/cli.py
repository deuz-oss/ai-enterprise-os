from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
TEMPLATES_ROOT = REPO_ROOT / "tools" / "templates"
REQUIRED_ENV_VARS = [
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "REDIS_PASSWORD",
    "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD",
    "KEYCLOAK_ADMIN",
    "KEYCLOAK_ADMIN_PASSWORD",
]


def _command_version(cmd: list[str]) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return "not_found"
    output = (result.stdout or result.stderr).strip().splitlines()
    return output[0] if output else "unknown"


def _structured_not_implemented(command_name: str, notes: list[str]) -> int:
    print(
        json.dumps(
            {
                "status": "not_fully_implemented",
                "command": command_name,
                "summary": "Command framework is available and this command provides guided usage.",
                "next_steps": notes,
            },
            indent=2,
        )
    )
    return 0


def _copy_tree(src: Path, dest: Path) -> None:
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        target = dest / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        content = path.read_text(encoding="utf-8")
        content = content.replace("__NAME__", dest.name)
        target.write_text(content, encoding="utf-8")


def cmd_doctor(_: argparse.Namespace) -> int:
    env_file = REPO_ROOT / ".env"
    env_values: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if not line or line.strip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env_values[key.strip()] = value.strip()

    checks = {
        "python": _command_version(["python", "--version"]),
        "node": _command_version(["node", "--version"]),
        "docker": _command_version(["docker", "--version"]),
        "docker_compose": _command_version(["docker", "compose", "version"]),
        "flutter": _command_version(["flutter", "--version"]),
        "git": _command_version(["git", "--version"]),
    }
    env_report = {
        key: "ok" if (os.environ.get(key) or env_values.get(key)) else "missing"
        for key in REQUIRED_ENV_VARS
    }
    payload = {
        "status": "ok",
        "platform": platform.platform(),
        "checks": checks,
        "environment": env_report,
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_init(_: argparse.Namespace) -> int:
    env_example = REPO_ROOT / ".env.example"
    env_target = REPO_ROOT / ".env"
    if env_example.exists() and not env_target.exists():
        env_target.write_text(env_example.read_text(encoding="utf-8"), encoding="utf-8")
    for folder in ["apps", "services", "packages", "agents", "tools", "schemas"]:
        (REPO_ROOT / folder).mkdir(exist_ok=True)
    print(json.dumps({"status": "ok", "initialized": True, "repo": str(REPO_ROOT)}, indent=2))
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    selected_template = args.template
    if args.kind == "service":
        selected_template = "fastapi-service"
        target = REPO_ROOT / "services" / args.name
    elif args.kind == "package":
        selected_template = selected_template or "python-package"
        target = REPO_ROOT / "packages" / args.name
    elif args.kind == "app":
        selected_template = selected_template or "react-app"
        target = REPO_ROOT / "apps" / args.name
    else:
        selected_template = "ai-agent"
        target = REPO_ROOT / "agents" / args.name

    template_name = selected_template
    template_dir = TEMPLATES_ROOT / template_name
    if not template_dir.exists():
        print(
            json.dumps(
                {"status": "error", "message": f"template '{template_name}' not found"},
                indent=2,
            )
        )
        return 1
    if target.exists():
        print(json.dumps({"status": "error", "message": f"{target} already exists"}, indent=2))
        return 1
    target.mkdir(parents=True, exist_ok=True)
    _copy_tree(template_dir, target)
    print(
        json.dumps(
            {
                "status": "ok",
                "kind": args.kind,
                "name": args.name,
                "template": template_name,
                "path": str(target),
            },
            indent=2,
        )
    )
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    if args.kind == "api":
        return _structured_not_implemented(
            "aeos generate api",
            [
                "Target service should be provided via --service.",
                "OpenAPI model generation will be produced from route signatures.",
                "Use `aeos docs` now to export current OpenAPI contracts.",
            ],
        )
    return _structured_not_implemented(
        "aeos generate crud",
        [
            "Provide --service, --entity, and --fields.",
            "Generator will produce repository/service/router/model modules.",
            "CRUD generator is scaffold-ready in next sprint.",
        ],
    )


def _run_make_target(target: str) -> int:
    if shutil.which("make") is None:
        return _structured_not_implemented(
            f"aeos {target}",
            [
                f"`make {target}` is the standard execution path.",
                "Install make or run equivalent commands manually.",
            ],
        )
    result = subprocess.run(["make", target], cwd=REPO_ROOT, check=False)
    return result.returncode


def cmd_docs(_: argparse.Namespace) -> int:
    script = REPO_ROOT / "tools" / "openapi" / "generate_openapi.py"
    result = subprocess.run([sys.executable, str(script)], cwd=REPO_ROOT, check=False)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(prog="aeos", description="AI Enterprise OS Developer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Validate local developer environment")
    doctor.set_defaults(func=cmd_doctor)

    init = subparsers.add_parser("init", help="Initialize local developer workspace")
    init.set_defaults(func=cmd_init)

    new = subparsers.add_parser("new", help="Generate a new component from templates")
    new_sub = new.add_subparsers(dest="kind", required=True)
    for kind in ["service", "package", "app", "agent"]:
        p = new_sub.add_parser(kind, help=f"Create a new {kind}")
        p.add_argument("name")
        if kind == "app":
            p.add_argument("--template", choices=["react-app", "flutter-app"])
        if kind == "package":
            p.add_argument("--template", choices=["python-package", "typescript-package"])
        p.set_defaults(func=cmd_new, kind=kind)

    generate = subparsers.add_parser("generate", help="Code generators")
    gen_sub = generate.add_subparsers(dest="kind", required=True)
    for kind in ["crud", "api"]:
        p = gen_sub.add_parser(kind, help=f"Generate {kind} artifacts")
        p.set_defaults(func=cmd_generate, kind=kind)

    migrate = subparsers.add_parser("migrate", help="Run migrations")
    migrate.set_defaults(func=lambda _: _run_make_target("migrate"))
    seed = subparsers.add_parser("seed", help="Seed baseline data")
    seed.set_defaults(
        func=lambda _: _structured_not_implemented(
            "aeos seed",
            [
                "Define per-service seed entrypoint in scripts/seed.sh or service package.",
                "Use deterministic fixture bundles for shared environments.",
            ],
        )
    )
    docs = subparsers.add_parser("docs", help="Generate documentation artifacts")
    docs.set_defaults(func=cmd_docs)
    lint = subparsers.add_parser("lint", help="Run lint checks")
    lint.set_defaults(func=lambda _: _run_make_target("lint"))
    test = subparsers.add_parser("test", help="Run tests")
    test.set_defaults(func=lambda _: _run_make_target("test"))
    build = subparsers.add_parser("build", help="Run build checks")
    build.set_defaults(
        func=lambda _: _structured_not_implemented(
            "aeos build",
            [
                "Build orchestration will run service image builds and frontend bundles.",
                "Use CI workflow docker-build job as baseline for now.",
            ],
        )
    )
    release = subparsers.add_parser("release", help="Release flow")
    release.set_defaults(
        func=lambda _: _structured_not_implemented(
            "aeos release",
            [
                "Tagging, changelog generation, and artifact publishing are not yet automated.",
                "Use branch protection and PR gates before release tagging.",
            ],
        )
    )

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
