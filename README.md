# dde

本仓库维护 DDE 各组件组的版本。发版时，在这里统一触发成员仓库的 changelog 更新。

这里原先维护 UOS 20 的 `dde` 元包，2023 年后停止更新，现已停用。旧打包文件保留在 Git 历史中。

## 版本规则

- 组基线 `version` 不带 epoch；每轮发布完成后，成员 `debian/changelog` 去掉 epoch 的版本须与组基线一致。
- G2 保留各成员现有 epoch；成员完整目标去掉 epoch 后须与组目标一致。
- 组内任一仓库有更新，整组一起升版本、重新打包。
- 统一发版沿用 `debian/control` 中现有的依赖下界，不修改 `>=` / `>>` 约束。

## 仓库文件

- [groups.yaml](./groups.yaml)：分组、成员、仓库名映射和最近完成轮次的组基线。首次统一前，
  该版本只是起始基线，不代表成员当前已经统一；发版以此文件为准。
- [release-group.yml](./.github/workflows/release-group.yml)：创建本组的基线草稿 PR，再触发成员工作流。
- [sync-baseline.yml](./.github/workflows/sync-baseline.yml)：检查成员发布进度，更新基线 PR 的检查状态。

## 发版

整组发版从本仓库发起，由各成员工作流更新 changelog。不要单独到成员仓库修改版本。

首次统一也从 `Release group` 发起，不需要先运行 `Sync baseline`。本组没有统一发布记录时，成员起始版本可以不同。
首轮发布完成后，后续发布要求成员完整版本与上轮记录的成员目标一致，包括 epoch。

打开 `Actions → Release group → Run workflow`，填写以下参数：

- `group`：要发布的组。
- `version`：不带 epoch 的组目标版本，须高于基线；继承 epoch 后的各成员目标须高于其当前完整版本。继续未完成的发布时，填写原组目标版本。G1 新发布只接受正式三段版本，不支持 `-rc` 等预发布版本。
- `name` / `email`：写入成员 `debian/changelog` 的维护者姓名和邮箱，必填。
- `base_branch`：G2 的成员目标分支；留空使用各成员默认分支。所填分支须在所有成员中存在并接入调用工作流。
- `distribution`：G2 的 changelog 发行套件，默认 `unstable`。新发布记录会固定该值，恢复时须沿用。
- `create_pr`：默认 `true`。G2 取消勾选后只生成成员 changelog，在成员 Actions 中显示 diff 并上传产物，不创建本轮基线分支或任何发布 PR。
- `dry_run`：默认 `true`，检查当前状态并列出需要触发的成员；设为 `false` 后才创建 PR、触发工作流。

只生成 changelog 时也须把 `dry_run` 设为 `false`，才会触发成员工作流。
G1 的 Auto Release 支持 `name` / `email`，使用默认分支及原有发布方式，不支持上述三个额外选项；传入不支持的选项会在创建基线前报错。

新一轮发布在 `create_pr=true` 时按以下顺序执行：

1. 检查目标版本和已有发布记录，确认本组没有未完成的发布。已有统一发布记录的组，还须确认成员当前完整版本与上轮成员目标一致。
2. 创建 `baseline/<组>` 分支和原始发布提交，只修改本组的版本，并在提交中固定各成员继承 epoch 后的完整目标；此时暂不创建基线 PR。
3. 按记录中的完整目标并行触发成员工作流，由各仓库生成 changelog 并创建发布 PR。
4. 等待每个成员都创建开放或已合并的发布 PR，再创建草稿基线 PR，并直接写入全部成员 PR 的裸链接。
5. 所有成员 PR 合并、changelog 完整版本均为各自记录的目标后，`group-release-ready` 检查通过，基线草稿 PR 转为待审。
6. 人工审查并合并基线 PR，完成本轮发布，之后才能开始下一轮。

同一组一次只能发布一个目标版本，不同组可以同时发布。成员陆续合入时，组内版本可能暂时不同。
创建发布分支遇到冲突时，流程会报错停止，不会覆盖已有分支。

### 成员工作流

- G1（DTK）：调用 `call-auto-release.yml`，dtkcore 使用 `auto-release.yml`，对应 `Auto Release` 工作流。
- 其他组：调用 `call-update-changelog.yml`，对应 `Call update changelog` 工作流，见 [linuxdeepin/.github PR #790](https://github.com/linuxdeepin/.github/pull/790)。

新增成员前，先在成员仓库的默认分支接入对应工作流。工作流按上述文件名调用，文件名变更时要同步修改本仓库的调用配置。

### 更新 PR 分支

发布完成前，不要更改本组成员、各仓库的默认分支或 PR 目标分支。

基线 PR 落后默认分支时，使用 `Update branch` 的 merge 方式同步，保留最初的发布提交。
同步后的 PR 相对默认分支仍应只修改本组版本。不要对基线分支做 rebase 或强推；基线 PR 不支持 merge queue。

普通文档或代码 PR 在合并前需同步到最新默认分支，并重新通过检查。
同一提交上的普通 PR 和基线 PR 共用一份状态；写成功前会一起复检，普通 PR 的版本或成员变更错误不会被基线结果覆盖。

## 发布检查与恢复

`Sync baseline` 每 15 分钟检查一次，也可以手动运行。手动运行时必须选择 `group`，只检查指定组，
并立即刷新该组基线 PR 描述中的成员发布 PR 链接；定时任务仍检查全部组。
它读取本轮成员 PR 的合并记录和所记录目标分支的 changelog，
把检查结果写入基线 PR 的 `group-release-ready` 状态。尚无统一发布记录且版本不同的组，会提示从 `Release group` 发起首轮发布。
已有发布记录的组，成员版本变化却没有对应的发布 PR 时，工作流会报错，需先核实已有发布。
检查时也会更新基线 PR 描述中的成员发布 PR 链接；有链接时仅保留裸 URL，不再附加合并状态。
尚未创建的会标注“尚无发布 PR”。
自动链接区块之外的人工说明会保留。

定时同步、PR 检查和手动发布的协调步骤共用一个串行队列，每次开始执行后重新读取当前状态。
队列最多保留 100 个等待任务，避免旧检查晚于新检查写回结果，也避免新事件替换其他 PR 的等待任务。
超过 GitHub 队列上限而被取消的任务需要重跑。成员工作流的派发仍可并行。

触发步骤成功只说明 GitHub 已接受请求，发布进度以成员运行结果和基线 PR 的检查状态为准。
某个成员触发失败时，其他成员仍会继续，整次 `Release group` 运行会标为失败。

恢复时，重新运行 `Release group`，填写原来的组和目标版本，将 `dry_run` 设为 `false`：

- 填写维护者姓名、邮箱和原发行套件；`create_pr` 保持 `true`。`base_branch` 留空时沿用本轮记录的成员分支，显式填写时必须与原分支一致。
- 已合并、发布 PR 仍打开、工作流仍运行的成员会被跳过。
- 没有发布 PR，也没有正在运行的工作流的成员会重新触发。
- 基线分支已创建但草稿 PR 创建失败的，成员 PR 全部创建后可从原始提交补建基线 PR。
- 基线 PR 未合并关闭时，会同步关闭本轮仍开放的成员 PR。恢复前需重新打开或重新创建这些成员 PR，
  再重新运行 `Release group` 打开原基线 PR；成员 PR 已关闭或版本不符时不会自动恢复。

完成一轮发布后可以增加成员。新增成员不在上一轮记录中时，按首次加入检查当前版本和发版入口；已有成员仍须与上轮目标一致。

如果触发时网络超时，先查看成员仓库的 Actions 运行记录，再决定是否重试。请求可能已经成功提交，
重复运行仍可能再次触发成员工作流。本流程不会撤回已提交的请求。

关闭 PR 或删除分支不能代替完成本轮发布；关闭未合并的基线 PR 会同步关闭仍开放的成员 PR。
工作流会读取原始发布提交和历史 PR 来检查进度。
已有成员合入时，应继续完成原目标。基线 PR 若被提前合入，需要先人工完成原成员 PR；流程不会自动回退基线，
也不会再次触发成员工作流，完成前不能开始下一轮。

恢复时沿用记录中的完整成员版本，不重新推导 epoch。旧发布记录没有成员版本字段时，继续使用原组目标，
包括旧记录已有的 epoch；不会改变正在进行的发布目标。
旧轮完成后，新轮按去掉 epoch 的组基线判断升版，新基线写入不带 epoch 的组目标，成员继续继承原 epoch。

## 配置与上线

沿用组织的 `APP_ID` 和 `APP_PRIVATE_KEY`。成员发版调用模板使用 `secrets: inherit`，
因此这两个 Secret 必须对 `dde` 和 25 个成员仓库可用；建议使用组织 Secret 并只授权这 26 个仓库。
GitHub App 须安装到 dde 和各成员仓库，并授予以下仓库权限：

- `Actions`：Read and write。
- `Contents`：Read and write。
- `Pull requests`：Read and write。
- `Commit statuses`：Read and write。

成员仓库创建 changelog PR 所用的 GitHub App secret 沿用现有工作流配置。
本仓库各 job 单独生成 GitHub App 安装 Token，结束后自动撤销；派发 job 的 Token 只访问对应成员仓库。
共享成员发版工作流创建 PR 时的 Token 也只访问当前成员仓库。
认证或查询失败时，运行会直接停止。

给 dde 默认分支启用保护规则，把 **`group-release-ready`** 设为必需检查，并禁止绕过。
配置时将该 GitHub App 设为检查状态的来源。成员发布未完成时，保护规则会阻止基线 PR 合入。
普通 PR 同样需要通过此检查；手工修改基线版本的 PR 无法通过。
普通 PR 即使没有修改基线版本，只要与当前基线 PR 共用同一提交，也要通过该轮发布检查；
成员未全部合并时仍为等待，发布记录或 PR 状态异常时失败。

基线 PR 创建成功前，保留 `baseline/*` 分支。此时发布记录只在该分支中，删除后无法自动恢复。

首次使用前，先等待成员仓库已有的发版工作流结束，处理现有成员 PR、旧格式的 `baseline/<组>-<版本>` PR
和一次修改多组的基线 PR。确认成员默认分支已接入对应工作流；go-lib 的 `call-update-changelog.yml` 需先合入其默认分支。
创建基线前会检查成员是否归档或禁用、发版工作流是否启用，以及默认分支和所选目标分支的入口是否支持
`workflow_dispatch` 且包含本轮所需的参数名和参数类型。

## 本地测试

```sh
python3 -I .github/tests/test_group_release.py -v
```

## 组件侧校验

成员通过 `linuxdeepin/.github` 的 `verify-group-version.yml` 校验 `debian/changelog` 版本，
调用入口为 `workflow-templates/call-verify-group-version.yml`。模板同步配置覆盖全部 25 个成员；
成员默认分支接入入口、启用分支保护后才会阻止合并。

不改 changelog 版本的普通 PR 可以通过。改版 PR 的完整成员目标版本、来源仓库、自动化分支、目标分支和
创建时间须匹配本仓库的原始发布记录；首次统一允许成员起始版本不同。未发起组发布的改版 PR 会失败，
本轮发布 `6.0.50` 时单独改成 `6.0.51` 也会失败。关闭未合并的基线 PR 会同步关闭本轮仍开放的成员 PR。

成员检查名为 **`group-version-guard`**，来源为 GitHub Actions，不需要新增 App Secret。
给各成员发布目标分支启用此必需检查，并要求通过 PR 合入、保持分支最新、禁止直接推送或绕过。
这也适用于显式选择的 `base_branch`。本次模板安装沿用原有 SSH 同步方式，
已有保护拒绝直推时，通过单独 PR 安装；启用保护后，后续模板更新也必须通过 PR。

部署前先完成上述首用准备，再合入共享校验工作流和模板配置，
逐仓库确认成员入口安装完成后，上线本仓库协调器。自动创建模板 PR 的工具升级单独安排。
验证两种检查均能运行且来源正确后，逐组启用保护。测试 fork 会自动读取同组织的 `dde` 发布记录。
go-lib 的发布入口须先合入其默认分支。

## 分组

分组主要考虑循环依赖、构建和接口耦合，以及共同交付需求。

| 组 | 说明 | 成员 |
|---|---|---|
| G1 | DTK 基础库 | dtkcommon、dtklog、dtkcore、dtkgui、dtkwidget、dtkdeclarative、qt5platform-plugins、qt5integration |
| G2 | 服务与会话桌面应用 | go-lib、go-dbus-factory、dde-api、dde-daemon、dde-services、dde-session、dde-session-shell-v25、dde-shell、dde-tray-loader、dde-application-manager、deepin-service-manager、dde-control-center、dde-launchpad、dde-network-core、deepin-update-ui、xdg-desktop-portal-dde、dde-appearance |

dde-dialog、dde-manual-content、gnome-keyring 不参与组版本统一，保留各自的版本。
dtk6log 已归档，不参与组发布。

具体成员和版本以 [groups.yaml](./groups.yaml) 为准。
