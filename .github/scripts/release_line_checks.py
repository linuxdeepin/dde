# SPDX-FileCopyrightText: 2026 UnionTech Software Technology Co., Ltd.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only G2 release-line checks shared by the coordinator and Prepare."""

import base64
import fnmatch
import json
import os
import re
import subprocess
import tempfile
from urllib.parse import quote, urlencode

import yaml


GUARD_CONTEXT = "group-version-guard"
WORKFLOW_FILES = ("call-update-changelog.yml", "call-verify-group-version.yml")
G2_MEMBER_COUNT = 17
MAX_TRAVERSAL_DEPTH = 100
RELEASE_INPUTS = {
    "version": "string", "name": "string", "email": "string",
    "base_branch": "string", "distribution": "string", "create_pr": "boolean",
}
SHA_RE = re.compile(r"[0-9a-fA-F]{40}")
LINE_RE = re.compile(r"[A-Za-z0-9._-]+")


class ReadinessError(RuntimeError):
    def __init__(self, state, message):
        self.state = state
        super().__init__(f"{state}: {message}")


def api(path, data=None, method=None, missing=False, paginate=False):
    """Same gh API adapter/signature as sync-baseline; errors fail closed."""
    args = ["gh", "api", path]
    if method:
        args += ["--method", method]
    if data is not None:
        args += ["--input", "-"]
    if paginate:
        args += ["--paginate", "--slurp"]
    # Paths are passed as one argv item with shell=False; no shell interpolation occurs.
    result = subprocess.run(args, input=json.dumps(data) if data is not None else None,  # nosemgrep
                            capture_output=True, text=True)
    if result.returncode:
        if missing and "(HTTP 404)" in result.stderr:
            return None
        raise RuntimeError(f"GitHub API 失败: {path}: {result.stderr.strip()}")
    value = json.loads(result.stdout) if result.stdout.strip() else None
    if path == "graphql" and value.get("errors"):
        raise RuntimeError(f"GitHub GraphQL 失败: {value['errors']}")
    return [item for page in value for item in page] if paginate else value


def content(api, repo, path, ref, missing=False):
    value = api(f"repos/{repo}/contents/{quote(path, safe='/')}?"
                f"{urlencode({'ref': ref})}", missing=missing)
    if value is None and missing:
        return None
    if not isinstance(value, dict) or value.get("encoding") != "base64":
        raise RuntimeError(f"无法读取文件: {repo}@{ref}:{path}")
    return base64.b64decode(value["content"]).decode("utf-8")


def validate_line(line, branch):
    if not isinstance(line, str) or not LINE_RE.fullmatch(line):
        raise RuntimeError(f"非法发布线 ID: {line}")
    if not isinstance(branch, str) or subprocess.run(
            ["git", "check-ref-format", "--branch", branch], capture_output=True).returncode:
        raise RuntimeError(f"非法成员分支: {branch}")
    if line == "master":
        if branch != "master":
            raise RuntimeError("master 发布线必须映射 master")
    elif not branch.startswith("develop/"):
        raise RuntimeError("新发布线的成员分支必须为 develop/<name>")


def release_lines(cfg):
    lines = cfg.get("release_lines")
    versions = cfg.get("groups", {}).get("G2", {}).get("versions")
    if not isinstance(lines, dict) or not isinstance(versions, dict) or "master" not in lines:
        raise RuntimeError("请先合并 G2 release_lines / versions 配置迁移")
    branches = []
    for line, value in lines.items():
        if not isinstance(value, dict):
            raise RuntimeError(f"发布线 {line} 配置无效")
        validate_line(line, value.get("member_branch"))
        branches.append(value["member_branch"])
        if line not in versions or not isinstance(versions[line], str):
            raise RuntimeError(f"发布线 {line} 缺少 G2 初始版本")
    if len(branches) != len(set(branches)) or set(lines) != set(versions):
        raise RuntimeError("发布线分支映射必须唯一，且与 G2 versions 一一对应")
    return lines


def g2_members(cfg, owner):
    members = cfg.get("groups", {}).get("G2", {}).get("members")
    if (not isinstance(members, list) or len(members) != G2_MEMBER_COUNT
            or any(not isinstance(m, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", m)
                   for m in members) or len(set(members)) != G2_MEMBER_COUNT):
        raise RuntimeError("只支持 groups.G2.members 中现有的 17 个唯一成员")
    overrides = cfg.get("repo_overrides", {})
    result = []
    for member in members:
        name = overrides.get(member, member)
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", name):
            raise RuntimeError(f"成员 {member} 的 repo_overrides 无效")
        result.append((member, f"{owner}/{name}"))
    if len({repo for _, repo in result}) != G2_MEMBER_COUNT:
        raise RuntimeError("G2 仓库映射重复")
    return result


def head_version(api, repo, sha):
    text = content(api, repo, "debian/changelog", sha)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as changelog:
        changelog.write(text)
        changelog.flush()
        result = subprocess.run(["dpkg-parsechangelog", "-l", changelog.name, "-S", "Version"],
                                capture_output=True, text=True)
    version = result.stdout.strip()
    if result.returncode or not version or subprocess.run(
            ["dpkg", "--validate-version", version], capture_output=True).returncode:
        raise RuntimeError(f"无法解析 {repo}@{sha} 的 changelog: {result.stderr.strip()}")
    return version


def branch_info(api, repo, branch, missing=False):
    return api(f"repos/{repo}/branches/{quote(branch, safe='')}", missing=missing)


def _event(workflow, name):
    events = workflow.get("on", workflow.get(True))
    if isinstance(events, dict) and name in events:
        return events[name] or {}
    if events == name or isinstance(events, list) and name in events:
        return {}
    return None


def _matches(pattern, branch):
    # fnmatch handles character classes; a single * must not cross a GitHub branch slash.
    regex = fnmatch.translate(pattern.replace("**", "__DOUBLE_STAR__")
                            .replace("?", "__SINGLE_CHAR__")).replace(".*", "[^/]*")
    return re.fullmatch(regex.replace("__DOUBLE_STAR__", ".*")
                       .replace("__SINGLE_CHAR__", "[^/]"), branch) is not None


def _covers(event, branch):
    if ("paths" in event or "paths-ignore" in event
            or "branches" in event and "branches-ignore" in event):
        return False
    patterns = event.get("branches")
    selected = patterns is None
    if patterns is not None:
        if not isinstance(patterns, list):
            return False
        for pattern in patterns:
            if not isinstance(pattern, str) or "+" in pattern or "\\" in pattern:
                return False
            if _matches(pattern.removeprefix("!"), branch):
                selected = not pattern.startswith("!")
    ignored = event.get("branches-ignore", [])
    if (not isinstance(ignored, list)
            or any(not isinstance(pattern, str) or "+" in pattern or "\\" in pattern
                   for pattern in ignored)):
        return False
    return selected and not any(_matches(pattern, branch) for pattern in ignored)


def _inputs(event, where):
    inputs = event.get("inputs", {})
    for name, kind in RELEASE_INPUTS.items():
        if inputs.get(name, {}).get("type") != kind:
            raise ReadinessError("TEMPLATE_MISSING", f"{where} 缺少兼容输入 {name}: {kind}")
    if any(value.get("required") and name not in RELEASE_INPUTS
           for name, value in inputs.items()):
        raise ReadinessError("TEMPLATE_MISSING", f"{where} 存在协调器不会提供的必需输入")


def check_workflow_file(api, repo, filename, ref, branch, text=None):
    """Validate a caller and its reusable workflow without running either."""
    where = f"{repo}@{ref}:{filename}"
    if text is None:
        text = content(api, repo, f".github/workflows/{filename}", ref, missing=True)
    if text is None:
        raise ReadinessError("TEMPLATE_MISSING", f"{where} 不存在")
    try:
        workflow = yaml.safe_load(text)
        if not isinstance(workflow, dict):
            raise ValueError("workflow 不是对象")
        dispatch = filename == WORKFLOW_FILES[0]
        event = _event(workflow, "workflow_dispatch" if dispatch else "pull_request_target")
        if not isinstance(event, dict):
            raise ValueError("缺少 workflow_dispatch / pull_request_target 入口")
        if dispatch:
            _inputs(event, where)
        else:
            required = {"opened", "reopened", "synchronize", "edited", "ready_for_review", "closed"}
            types = event.get("types", ["opened", "reopened", "synchronize"])
            if not required.issubset(types) or not _covers(event, branch):
                raise ValueError(f"guard 无法覆盖 {branch} 的全部必要 PR 事件")
            permissions = workflow.get("permissions", {})
            if not isinstance(permissions, dict) or permissions.get("statuses") != "write":
                raise ValueError("guard 缺少 statuses: write")
        shared_file = "update-changelog.yml" if dispatch else "verify-group-version.yml"
        jobs = workflow.get("jobs", {})
        candidates = [job for job in jobs.values() if isinstance(job, dict) and
                      isinstance(job.get("uses"), str) and
                      f"/.github/workflows/{shared_file}@" in job["uses"]]
        if len(candidates) != 1 or candidates[0].get("if") not in (None, True):
            raise ValueError("共享工作流入口缺失、重复或有无法验证的条件")
        job = candidates[0]
        match = re.fullmatch(r"([A-Za-z0-9._-]+/\.github)/(\.github/workflows/[^@]+)@(.+)",
                             job["uses"])
        if not match:
            raise ValueError("共享工作流引用无效")
        shared_repo, path, shared_ref = match.groups()
        if shared_repo != f"{repo.split('/')[0]}/.github":
            raise ValueError("共享工作流必须引用当前组织的 .github 仓库")
        if dispatch and any(job.get("with", {}).get(name) != "${{ inputs." + name + " }}"
                            for name in RELEASE_INPUTS):
            raise ValueError("发版入口必须原样传递 base_branch 及现有输入")
        shared = yaml.safe_load(content(api, shared_repo, path, shared_ref))
        call = _event(shared, "workflow_call")
        if not isinstance(call, dict):
            raise ValueError("共享工作流没有 workflow_call 入口")
        if dispatch:
            _inputs(call, job["uses"])
    except (TypeError, ValueError, KeyError, yaml.YAMLError) as error:
        raise ReadinessError("TEMPLATE_MISSING", f"{where}: {error}") from error
    return text


def check_member_workflows(api, repo, branch, info=None):
    info = info or api(f"repos/{repo}")
    if info.get("archived") is not False or info.get("disabled") is not False:
        raise ReadinessError("WORKFLOW_INACTIVE", f"{repo} 已归档、禁用或状态未知")
    target = branch_info(api, repo, branch, missing=True)
    if target is None:
        raise ReadinessError("BRANCH_MISSING", f"{repo}:{branch}")
    actions = api(f"repos/{repo}/actions/permissions")
    if actions.get("enabled") is not True:
        raise ReadinessError("WORKFLOW_INACTIVE", f"{repo} Actions 未启用或不可读取")
    for ref in dict.fromkeys((info["default_branch"], branch)):
        head = target if ref == branch else branch_info(api, repo, ref)
        for filename in WORKFLOW_FILES:
            check_workflow_file(api, repo, filename, head["commit"]["sha"], branch)
    for filename in WORKFLOW_FILES:
        workflow = api(f"repos/{repo}/actions/workflows/{filename}", missing=True)
        if workflow is None or workflow.get("state") != "active":
            raise ReadinessError("WORKFLOW_INACTIVE", f"{repo}/{filename} 未启用或不可读取")
    return target


def release_app_id(value):
    if type(value) is not int or value <= 0:
        raise ReadinessError("PROTECTION_FAILED", "无法确认发布 App 的身份")
    return value


def read_protection(api, repo, branch, head=None):
    """A protection 404 is only absence when branch state and effective rules agree."""
    head = head or branch_info(api, repo, branch)
    classic = api(f"repos/{repo}/branches/{quote(branch, safe='')}/protection", missing=True)
    rules = api(f"repos/{repo}/rules/branches/{quote(branch, safe='')}?per_page=100",
                paginate=True)
    if classic is not None and not isinstance(classic, dict):
        raise ReadinessError("PROTECTION_FAILED", f"{repo}:{branch} 保护响应格式不可确认")
    if not isinstance(rules, list) or not isinstance(head.get("protected"), bool):
        raise ReadinessError("PROTECTION_FAILED", f"{repo}:{branch} 保护状态不可读取")
    if classic is None and head["protected"] and not rules:
        raise ReadinessError("PROTECTION_FAILED", f"{repo}:{branch} 保护返回 404，无法确认有效规则")
    rulesets = {}
    for rule in rules:
        ruleset_id = rule.get("ruleset_id")
        if type(ruleset_id) is not int:
            raise ReadinessError("PROTECTION_FAILED", f"{repo}:{branch} 有效规则来源未知")
        if ruleset_id not in rulesets:
            value = api(f"repos/{repo}/rulesets/{ruleset_id}?includes_parents=true")
            if value.get("enforcement") != "active" or "bypass_actors" not in value:
                raise ReadinessError("PROTECTION_FAILED", f"{repo}:{branch} 无法读取规则集绕过权限")
            rulesets[ruleset_id] = value
    return {"classic": classic, "rules": rules, "rulesets": rulesets}


def _enabled(protection, name):
    value = protection.get(name)
    return value.get("enabled") if isinstance(value, dict) else value


def _classic_ready(protection, app_id):
    if not isinstance(protection, dict):
        return False
    reviews = protection.get("required_pull_request_reviews")
    checks = protection.get("required_status_checks") or {}
    return (isinstance(reviews, dict)
            and not any(reviews.get("bypass_pull_request_allowances", {}).values())
            and _enabled(protection, "enforce_admins") is True
            and _enabled(protection, "allow_force_pushes") is False
            and _enabled(protection, "allow_deletions") is False
            and _enabled(protection, "lock_branch") is not True
            and checks.get("strict") is True
            and any(check.get("context") == GUARD_CONTEXT and check.get("app_id") == app_id
                    for check in checks.get("checks", [])))


def protection_ready(protection, app_id):
    if _classic_ready(protection["classic"], app_id):
        return True
    # Rules are additive. Only rulesets whose bypass list is known empty prove enforcement.
    rules = [rule for rule in protection["rules"]
             if protection["rulesets"][rule["ruleset_id"]]["bypass_actors"] == []]
    types = {rule["type"] for rule in rules}
    checks = [rule.get("parameters", {}) for rule in rules if rule["type"] == "required_status_checks"]
    return ({"pull_request", "deletion", "non_fast_forward"}.issubset(types)
            and any(value.get("strict_required_status_checks_policy") is True
                    and any(check.get("context") == GUARD_CONTEXT
                            and check.get("integration_id") == app_id
                            for check in value.get("required_status_checks", []))
                    for value in checks))


def check_member_ready(api, repo, branch, app_id=None):
    """Return READY only after live workflow and effective protection checks; never writes."""
    if app_id is None:
        try:
            app_id = int(os.environ["APP_ID"])
        except (KeyError, ValueError) as error:
            raise ReadinessError("PROTECTION_FAILED", "缺少发布 App ID") from error
    state = "TEMPLATE_MISSING"
    try:
        target = check_member_workflows(api, repo, branch)
        state = "PROTECTION_FAILED"
        protection = read_protection(api, repo, branch, target)
        if not protection_ready(protection, release_app_id(app_id)):
            raise ReadinessError(state, f"{repo}:{branch} 需要 PR、禁止绕过/force/delete、严格检查 "
                                 f"{GUARD_CONTEXT}（来源发布 App）")
        return {"repo": repo, "branch": branch, "state": "READY"}
    except RuntimeError:
        raise
    except Exception as error:
        raise ReadinessError(state, f"{repo}:{branch} 工作流或 API 响应格式不可确认: {error}") from error
