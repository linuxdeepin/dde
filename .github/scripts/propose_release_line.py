# SPDX-FileCopyrightText: 2026 UnionTech Software Technology Co., Ltd.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Propose a fixed G2 snapshot in a draft configuration PR, never on master."""

import copy
import difflib
import json
import os
import re
import subprocess
from urllib.parse import quote, urlencode

import yaml

from release_line_checks import (
    MAX_TRAVERSAL_DEPTH, SHA_RE, api, content, g2_members, head_version, release_lines,
    validate_line,
)


MARKER = "<!-- propose-release-line\n"
RELEASE_MARKER = "<!-- group-release\n"


def ref(api, repo, branch):
    value = api(f"repos/{repo}/git/ref/heads/{quote(branch, safe='/')}", missing=True)
    return value["object"]["sha"] if value else None


def prs(api, repo, branch=None, base=None, state="all"):
    query = {"state": state, "per_page": 100, "sort": "created", "direction": "desc"}
    if branch:
        query["head"] = f"{repo.split('/')[0]}:{branch}"
    if base:
        query["base"] = base
    return api(f"repos/{repo}/pulls?{urlencode(query)}", paginate=True)


def source_idle(api, repo, cfg, source_branch, default, master_sha):
    source_line = next((line for line, value in release_lines(cfg).items()
                        if value["member_branch"] == source_branch), None)
    members = g2_members(cfg, repo.split("/")[0])
    member_prs = {}
    for _, member_repo in members:
        member_prs[member_repo] = prs(api, member_repo, base=source_branch)
        if any(p["state"] == "open" and p["head"]["ref"].startswith("automation/update-changelog/")
               for p in member_prs[member_repo]):
            raise RuntimeError(f"源分支 {source_branch} 有未完成的成员发布 PR: {member_repo}")
    if source_line is None:
        return
    branches = [f"baseline/{source_line}/G2"]
    if source_line == "master":
        branches.append("baseline/G2")
    for branch in branches:
        baselines = prs(api, repo, branch)
        if any(p["state"] == "open" for p in baselines):
            raise RuntimeError(f"源线 {source_line} 有未完成的基线 PR: {branch}")
        reservation = ref(api, repo, branch)
        if not reservation and not baselines:
            continue
        latest = baselines[0] if baselines else None
        sha = reservation or latest["head"]["sha"]
        completed = latest if (latest and latest.get("merged_at")
                              and latest["head"]["sha"] == sha and latest["base"]["ref"] == default
                              and latest["head"]["repo"]
                              and latest["head"]["repo"]["full_name"] == repo) else None
        if not completed:
            raise RuntimeError(f"源线 {source_line} 有未完成或异常的预留记录: {branch}")
        delta = api(f"repos/{repo}/compare/{completed['merge_commit_sha']}...{master_sha}")
        if delta["merge_base_commit"]["sha"] != completed["merge_commit_sha"]:
            raise RuntimeError(f"{branch} 的完成记录未合入协调默认分支")
        commit = api(f"repos/{repo}/git/commits/{sha}")
        depth = 0
        while RELEASE_MARKER not in commit["message"]:
            if len(commit["parents"]) != 2 or depth >= 100:
                raise RuntimeError(f"{branch} 的原发布记录不可确认")
            commit = api(f"repos/{repo}/git/commits/{commit['parents'][0]['sha']}")
            depth += 1
        release = json.loads(commit["message"].split(RELEASE_MARKER, 1)[1].split("\n-->", 1)[0])
        if (release.get("group") != "G2" or release.get("release_line", "master") != source_line
                or release.get("base_branch") != default
                or [m["repo"] for m in release["members"]] != [r for _, r in members]):
            raise RuntimeError(f"{branch} 的发布线或成员记录异常")
        for member in release["members"]:
            version = member.get("version", release["version"])
            safe = re.sub(r"[^A-Za-z0-9._-]+", "-", version).strip("-")
            if member["base"] != source_branch or not any(
                    p.get("merged_at") and p["head"]["ref"] == f"automation/update-changelog/{safe}"
                    and p["created_at"] >= release["started_at"] and p["head"]["repo"]
                    and p["head"]["repo"]["full_name"] == member["repo"]
                    and p.get("merge_commit_sha")
                    and head_version(api, member["repo"], p["merge_commit_sha"]) == version
                    for p in member_prs[member["repo"]]):
                raise RuntimeError(f"{branch} 的成员发布尚未完成: {member['repo']}")


def snapshot(api, members, branch, bases=None, version=None):
    fixed, versions = {}, {}
    if bases is not None and set(bases) != {member for member, _ in members}:
        raise RuntimeError("草稿 bases 必须恰好包含 G2 的 17 个成员 ID")
    for member, repo in members:
        sha = bases[member] if bases is not None else ref(api, repo, branch)
        if sha is None and bases is None:
            raise RuntimeError(f"{repo} 源分支不存在: {branch}")
        if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            raise RuntimeError(f"{repo} 缺少完整的基准 SHA")
        commit = api(f"repos/{repo}/git/commits/{sha}")
        if commit.get("sha", "").lower() != sha.lower():
            raise RuntimeError(f"{repo} 基准 commit 不存在: {sha}")
        fixed[member] = commit["sha"]
        versions[member] = head_version(api, repo, fixed[member]).split(":", 1)[-1]
    if len(set(versions.values())) != 1:
        raise RuntimeError(f"17 个基准 changelog 去 epoch 后版本不一致: {versions}")
    common = next(iter(versions.values()))
    if version is not None and version != common:
        raise RuntimeError(f"草稿初始版本 {version} 与固定基准共同版本 {common} 不符")
    return fixed, common


def rewrite(text, line, branch, bases, version):
    before = yaml.safe_load(text)
    expected = copy.deepcopy(before)
    expected["release_lines"][line] = {"member_branch": branch, "bases": bases}
    expected["groups"]["G2"]["versions"][line] = version
    root = {k.value: v for k, v in yaml.compose(text).value}
    groups = {k.value: v for k, v in root["groups"].value}
    g2 = {k.value: v for k, v in groups["G2"].value}
    line_key = line if yaml.safe_load(line) == line else json.dumps(line)
    additions = [
        (root["release_lines"].end_mark.line,
         [f"  {line_key}:", f"    member_branch: {json.dumps(branch)}", "    bases:"] +
         [f"      {member}: {json.dumps(sha)}" for member, sha in bases.items()]),
        (g2["versions"].end_mark.line, [f"      {line_key}: {json.dumps(version)}"]),
    ]
    lines = text.splitlines()
    for position, new_lines in sorted(additions, reverse=True):
        # YAML end_mark skips comments belonging to the following section.
        indent = len(new_lines[0]) - len(new_lines[0].lstrip())
        while position and (not lines[position - 1].strip() or (
                lines[position - 1].lstrip().startswith("#")
                and len(lines[position - 1]) - len(lines[position - 1].lstrip()) < indent)):
            position -= 1
        lines[position:position] = new_lines
    updated = "\n".join(lines) + "\n"
    if yaml.safe_load(updated) != expected:
        raise RuntimeError("无法在保留 G1 与既有配置的前提下增加发布线")
    return updated


def propose(api, repo, line, target, source_branch="master", dry_run=True):
    validate_line(line, target)
    if line == "master":
        raise RuntimeError("Propose 只新增 develop 发布线")
    if (not isinstance(source_branch, str) or subprocess.run(
            ["git", "check-ref-format", "--branch", source_branch], capture_output=True).returncode):
        raise RuntimeError(f"非法源成员分支: {source_branch}")
    info = api(f"repos/{repo}")
    default = info["default_branch"]
    base_sha = ref(api, repo, default)
    text = content(api, repo, "groups.yaml", base_sha)
    cfg = yaml.safe_load(text)
    lines = release_lines(cfg)
    members = g2_members(cfg, repo.split("/")[0])
    if line in lines:
        if lines[line]["member_branch"] != target:
            raise RuntimeError("已合并发布线不能覆盖或改投成员分支")
        print(f"{line} 配置已合并；使用 Prepare，不修改既有线")
        return None
    if target in {value["member_branch"] for value in lines.values()}:
        raise RuntimeError(f"成员分支 {target} 已映射到另一发布线")
    branch = f"automation/propose-release-line/{line}"
    if subprocess.run(["git", "check-ref-format", "--branch", branch],
                      capture_output=True).returncode:
        raise RuntimeError("发布线 ID 生成了无效的提案分支")
    proposals = prs(api, repo, branch)
    if len([p for p in proposals if p["state"] == "open"]) > 1:
        raise RuntimeError("提案分支有重复的开放 PR，需人工核实")
    pr = proposals[0] if proposals else None
    identity = {"release_line": line, "target_branch": target, "source_branch": source_branch}
    if pr and (pr.get("merged_at") or pr["state"] != "open" or not pr.get("draft")
               or pr["base"]["ref"] != default or not pr["head"]["repo"]
               or pr["head"]["repo"]["full_name"] != repo):
        raise RuntimeError("只更新原开放草稿 PR；已关闭、已审核或已合并提案请人工核实")
    previous = ref(api, repo, branch)
    bases = version = None
    if previous:
        if pr and pr["head"]["sha"] != previous:
            raise RuntimeError("草稿 PR 与提案分支 SHA 不一致，重跑前请核实")
        delta = api(f"repos/{repo}/compare/{base_sha}...{previous}")
        original = yaml.safe_load(content(api, repo, "groups.yaml",
                                         delta["merge_base_commit"]["sha"]))
        candidate = yaml.safe_load(content(api, repo, "groups.yaml", previous))
        release_lines(candidate)
        value = candidate["release_lines"].get(line, {})
        bases, version = value.get("bases"), candidate["groups"]["G2"]["versions"].get(line)
        expected = copy.deepcopy(original)
        expected["release_lines"][line] = value
        expected["groups"]["G2"]["versions"][line] = version
        if (candidate != expected or value.get("member_branch") != target
                or not isinstance(bases, dict)
                or [(f["filename"], f["status"]) for f in delta["files"]]
                != [("groups.yaml", "modified")]):
            raise RuntimeError("原提案只能增加本线配置与初始版本，不能覆盖其他已合并配置")
        commit = api(f"repos/{repo}/git/commits/{previous}")
        for _ in range(MAX_TRAVERSAL_DEPTH + 1):
            if MARKER in commit["message"]:
                saved = json.loads(commit["message"].split(MARKER, 1)[1].split("\n-->", 1)[0])
                if "source_line" in saved and "source_branch" not in saved:
                    saved["source_branch"] = lines.get(saved.pop("source_line"), {}).get("member_branch")
                if saved != identity:
                    raise RuntimeError("原草稿提案的源分支或目标输入不同")
                break
            if not commit["parents"]:
                raise RuntimeError("提案分支没有可确认的来源标记")
            commit = api(f"repos/{repo}/git/commits/{commit['parents'][0]['sha']}")
        else:
            raise RuntimeError("提案来源记录过深，需人工核实")
    source_idle(api, repo, cfg, source_branch, default, base_sha)
    bases, version = snapshot(api, members, source_branch, bases, version)
    updated = rewrite(text, line, target, bases, version)
    output = (f"G2 {line} -> {target}，源成员分支 {source_branch}，初始版本 {version}\n\n" +
              "\n".join(f"- {member} ({member_repo}): {bases[member]}"
                        for member, member_repo in members) + "\n\n" +
              "".join(difflib.unified_diff(text.splitlines(True), updated.splitlines(True),
                                          fromfile="groups.yaml", tofile="groups.yaml")))
    print(output)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(f"```\n{output}\n```\n")
    if dry_run:
        return {"bases": bases, "version": version, "config": updated}
    if ref(api, repo, default) != base_sha or ref(api, repo, branch) != previous:
        raise RuntimeError("配置或草稿在预检期间变化；请重跑，不覆盖新提交")
    source_idle(api, repo, cfg, source_branch, default, base_sha)
    if previous is None or content(api, repo, "groups.yaml", previous) != updated:
        tree = api(f"repos/{repo}/git/commits/{base_sha}")["tree"]["sha"]
        tree = api(f"repos/{repo}/git/trees", {"base_tree": tree, "tree": [
            {"path": "groups.yaml", "mode": "100644", "type": "blob", "content": updated}]})
        parents = [previous, base_sha] if previous else [base_sha]
        commit = api(f"repos/{repo}/git/commits", {"tree": tree["sha"], "parents": parents,
            "message": f"chore: propose G2 {line}\n\n{MARKER}{json.dumps(identity)}\n-->"})
        if previous:
            api(f"repos/{repo}/git/refs/heads/{quote(branch, safe='/')}",
                {"sha": commit["sha"], "force": False}, method="PATCH")
        else:
            try:
                api(f"repos/{repo}/git/refs", {"ref": f"refs/heads/{branch}", "sha": commit["sha"]})
            except RuntimeError:
                if ref(api, repo, branch) != commit["sha"]:
                    raise RuntimeError("提案分支并发创建或 API 失败；保留现状并重跑")
    body = (f"{MARKER}{json.dumps(identity)}\n-->\n\n源成员分支：`{source_branch}`。\n\n"
            "固定下列 SHA 作为新线分支快照。可在本草稿中修改历史 SHA 及初始版本，"
            "合并检查须重新验证所有基准。不自动创建成员分支或合并本 PR。\n\n" +
            "\n".join(f"- `{member}`: [{bases[member]}](https://github.com/{member_repo}/commit/{bases[member]})"
                      for member, member_repo in members))
    details = {"title": f"chore: propose G2 {line} ({version})", "body": body}
    if pr:
        if any(pr.get(key) != value for key, value in details.items()):
            pr = api(f"repos/{repo}/pulls/{pr['number']}", details, method="PATCH")
    else:
        try:
            pr = api(f"repos/{repo}/pulls", {**details, "head": branch, "base": default, "draft": True})
        except RuntimeError:
            existing = prs(api, repo, branch, state="open")
            head = ref(api, repo, branch)
            if (len(existing) != 1 or not existing[0].get("draft") or existing[0]["base"]["ref"] != default
                    or not existing[0]["head"]["repo"] or existing[0]["head"]["repo"]["full_name"] != repo
                    or existing[0]["head"]["ref"] != branch or existing[0]["head"]["sha"] != head):
                raise
            pr = existing[0]
    print(f"配置草稿 PR: {pr['html_url']}")
    return pr


if __name__ == "__main__":
    if "SOURCE_BRANCH" not in os.environ and "SOURCE_LINE" in os.environ:
        raise RuntimeError("来源参数已改为 source_branch；请重新从表单发起，不要重跑旧参数的运行")
    propose(api, os.environ["GITHUB_REPOSITORY"], os.environ["RELEASE_LINE"],
            os.environ["TARGET_BRANCH"], os.environ.get("SOURCE_BRANCH", "master"),
            os.environ.get("DRY_RUN", "true").lower() == "true")
