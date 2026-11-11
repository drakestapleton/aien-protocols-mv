# aien-protocols

<!-- languages -->
[English](README.md) · **简体中文**
<!-- /languages -->

本仓库收录 AIEN 各组成部分共同遵守的书面契约：智能体状态、推理请求、评估、证据凭证、碎屑、执行记录、已编译的 Omega 单元、Omega shell 边界的字节格式与规则，以及树莓派与 DGX Spark 之间的任务消息。每份契约都是 `specs/` 中的一份规范，通常附带测试向量（固定的输入文件，以及读取方必须给出的判定结果），还有一个小型 C 检查器，用来证明这些向量与规范文本一致。规范旁边是 `crates/` 中的 Rust 参考 crate。本仓库只收录契约，从不收录私有实现。

本仓库属于 Sovereign Intelligence（SI）。Aienix 已退役。[sovereign-intelligence](https://github.com/aien-dev/sovereign-intelligence) 是集成、发布与安装中心，签名的 Spark 测试也在那里运行。AienOS 只是操作系统层。参见 aien-architecture 的 [ADR 0045](https://github.com/aien-dev/aien-architecture-mv/blob/main/docs/adr/0045-aienix-retired-sovereign-intelligence-center.md)。

**2026-10-19 状态：研究级，pre-alpha。** 有一项规范已冻结（osc-unit-artifact v1，2026-10-08），一项标记为稳定（crumb-visible），其余均为草案。这里没有任何协议被宣称已在硬件上通过鉴定。整个系统的状态由 [aien-architecture-mv](https://github.com/aien-dev/aien-architecture-mv) 负责，见 [CURRENT_EXECUTION_PLAN.md](https://github.com/aien-dev/aien-architecture-mv/blob/main/CURRENT_EXECUTION_PLAN.md)。

## 规范

状态一列引用的是 `main` 分支上每份规范顶部的 `Status` 行。

| 规范 | 定义内容 | 状态 | 本仓库中的检查方式 |
|---|---|---|---|
| [agent-state](specs/agent-state/SPEC.md) | 可移植的智能体状态快照 | 草案 | 暂无 |
| [inference](specs/inference/SPEC.md) | 推理请求与响应 | 草案 | 暂无 |
| [evaluation](specs/evaluation/SPEC.md) | 评估器接口与判定身份域 | 草案 | `aien-evaluation-protocol` 中的 Rust 测试 |
| [evidence](specs/evidence/ADAPTIVE_EVIDENCE_INTERFACE.md) | 自适应证据接口（AEI1）的要求 | 待冻结草案，2026-10-11 | `aien-evaluation-protocol` 中的 Rust 测试（AEI1 凭证） |
| [evidence-receipt](specs/evidence-receipt/SUBSET.md) | 证据凭证中被 VC1 绑定的部分 | 部分提取，2026-10-02；完整提取尚未完成 | 暂无 |
| [verified-crumb](specs/verified-crumb/SPEC.md) | 经验证碎屑 V1（VC1）的字节编码与解析规则 | 草案 v0，2026-10-02 | `tools/check-golden.sh`（C 检查器，17 个黄金向量） |
| [crumb-visible](specs/crumb-visible/CRUMB_READER_CONTRACT.md) | CRB1 可见碎屑记录的读取方契约 | 稳定 | 仅有向量生成器（`tools/make-vectors.sh`） |
| [execution-transcript](specs/execution-transcript/TRN1_TRANSCRIPT_SPEC.md) | TRN1 执行记录，契约 0.2.0 | 草案 v0，2026-10-01；尚无任何运行时生成 | `tools/check-corpus.sh`（C 验证器，见 [tools/README.md](specs/execution-transcript/tools/README.md)） |
| [osc-unit-artifact](specs/osc-unit-artifact/OSC_UNIT_ARTIFACT.md) | 已编译 Omega 单元的签名容器 | v1 已冻结，2026-10-08 | `tools/check-vectors.sh`（见 [vectors/README.md](specs/osc-unit-artifact/vectors/README.md)） |
| [osh-platform](specs/osh-platform/OSH_PLATFORM_ABI.md) | Omega shell 核心与其平台之间的边界 | v1 草案，未冻结 | 仅有向量生成器（见 [vectors/README.md](specs/osh-platform/vectors/README.md)） |
| [pi-spark-task](specs/pi-spark-task/SPEC.md) | PST1，树莓派与 Spark 之间的任务消息 | 草案 v0.1，2026-10-16；尚无任何运行时生成或读取 | `tools/check-vectors.sh`（C 检查器，23 个头部向量）以及 Rust crate `aien-pi-spark-task` |
| [latent-payload](specs/latent-payload/SPEC.md) | 草案 MJB1 中按需启用、有界的 LTP0 张量 CONTENT 配置，不引入新的任务、凭证或能力协议 | 草案 v0；运行时集成 NOT_RUN | 种子自举的手写 Omega 校验器、固定的合成向量和原生变异对照，通过 `sh specs/latent-payload/run-native.sh OMEGA_SRC` 运行（omega-mv 取 `sources.json` 中记录的修订版本）；见 `results.json` |
| [microjob](specs/microjob/SPEC.md) | MJB1 类型化、有界的微作业 DAG（token 配置从 64/16 至 512/128，或零神经网络、资源上限、必需的验证器、重试与取消）以及 MJR1 凭证 | 草案 v0.1，2026-10-24；尚无任何运行时生成或读取 | `tools/check-vectors.sh`（C 检查器，104 个文档向量，58 个变异体）以及 Rust crate `aien-microjob`（向量测试和凭证账本测试） |
| [discovery-capsule](specs/discovery-capsule/SPEC.md) | DCP1 系列：发现胶囊、所有者同意、签名撤回、撤回确认与经验谱系 | 草案 v0.1，2026-10-24；尚无任何运行时生成或读取 | `tools/check-vectors.sh`（C 检查器，96 个记录向量，62 个变异体）以及 Rust crate `aien-discovery-capsule`（向量测试和双所有者生命周期测试） |

向量数量取自 [CHANGELOG.md](CHANGELOG.md)。契约如果有实现，实现归其所有者维护，不放在这里。2026-10-19 各 `main` 分支的情况如下：omega 保存了 VC1 黄金向量和 CRB1 向量的固定副本（`tests/vcstore/golden/PIN`、`tests/crumbline/crb1/PIN`），并在 `tests/osh/` 中运行 20 个 OSH 向量；aienos 有一个用 C 编写的 OSC 单元准入检查（`native/kernel/artifact/osc_unit.c`），附带一份 osc-unit-artifact 向量的副本。本仓库不运行这些测试。

## 参考 crate

全部十二个 crate 均采用 Apache-2.0 许可（依据 `cargo metadata`）。它们遵循 aien-architecture 的 [ADR 0024](https://github.com/aien-dev/aien-architecture-mv/blob/main/docs/adr/0024-rust-scaffolding-omega-destination.md)：Rust 是脚手架，Omega 是终点，因此规范才是长期保留的部分。

用途一列是从每个 crate 的 `Cargo.toml` 中的 `description` 字段缩写而来。

| Crate | 用途 |
|---|---|
| `aien-protocol-types` | 其他 crate 共用的标识符、原语和摘要 |
| `aien-agent-state-abi` | 智能体状态快照、状态转换事件与谱系检查 |
| `aien-inference-protocol` | 推理契约，包括租约式 KV 缓存固定和写时复制的上下文分支 |
| `aien-inference-client` | 推理协议的客户端 |
| `aien-action-protocol` | 动作、能力授予与隔离授权 |
| `aien-event-protocol` | 事件信封与流式遥测 |
| `aien-evaluation-protocol` | 评估器接口、验证器证明、评估凭证以及 AEI1 凭证 |
| `aien-provenance` | 摘要、Merkle 树与签名检查 |
| `aien-probe` | 探针评估引擎（见[其 README](crates/aien-probe/README.md)） |
| `aien-pi-spark-task` | PST1 头部的读取器和写入器；其测试会读取每一个 PST1 向量 |
| `aien-microjob` | MJB1 微作业 DAG 的读取器、写入器和检查器，以及 MJR1 凭证账本；其测试会读取每一个 MJB1 向量 |
| `aien-discovery-capsule` | DCP1 系列读取器、P-256 签名检查和接收方规则（撤回链、使用检查、执行准入、谱系）；其测试会读取每一个 DCP1 向量 |

哪个 crate 由谁使用，记录在 [CONSUMERS.md](CONSUMERS.md) 中。

### 源授权签名字节序列（下一个次版本的草案）

`SourceGrant::compute_unsigned_digest` 按以下顺序对这些字节计算 SHA-256：ASCII `AIEN_SOURCE_GRANT_V2` 加一个零字节；16 个原始授权 UUID 字节；UTF-8 编码的 `source_uri`，前面加上以 u64 小端序表示的字节长度；UTF-8 编码的 `license_spdx`，带同样的长度前缀；以 u32 小端序表示的权限位；UTF-8 编码的 `issuer`，带同样的长度前缀；一个字节 `0` 表示不过期，或者 `1` 后接以 u64 小端序表示的 `expires_at_epoch_sec`。不做任何规范化或填充。P-256 签名仍然覆盖 32 字节的 SHA-256 结果，而不是 JSON 表示。验证器从不尝试旧式的字段拼接签名。Drake 于 2026-10-26 批准了这次破坏性的摘要切换。采用它需要重新签发所有此前签名的授权；协同更新的使用方以及保持不变的历史证据记录在 `CONSUMERS.md` 和 `CHANGELOG.md` 中。

## 目录结构

```text
specs/         Specifications (Community Specification License 1.0), one directory each,
               with tools/ (generators and C checkers) and vectors/ where they exist
crates/        Reference Rust crates (Apache-2.0)
tests/gates/   Gate manifests and run.sh, the entry point the Spark judge runs
.aien/         Spark judge settings: always-run gates and the bundle public key
docs/          PIPELINE.md, how a pull request is tested and merged
```

治理与政策文件：[GOVERNANCE.md](GOVERNANCE.md)、[SCOPE.md](SCOPE.md)、[VERSIONING.md](VERSIONING.md)、[CHANGELOG.md](CHANGELOG.md)、[CONSUMERS.md](CONSUMERS.md)、[ANTI_ENCLOSURE.md](ANTI_ENCLOSURE.md)、[NOTICES.md](NOTICES.md)、[TRADEMARKS.md](TRADEMARKS.md)。

## 指向规则

协议不向内指向任何东西。实现向下指向协议。实现之间从不横向互相指向：任何需要在同一进程中使用两个实现的部署，都在上层完成组合。

## 与其他仓库的关系

- [omega-mv](https://github.com/aien-dev/omega-mv) 和 [aienos-mv](https://github.com/aien-dev/aienux) 用 C 实现了部分契约（见上文“规范”一节）。
- [aien-sovereign-core-mv](https://github.com/aien-dev/aien-sovereign-core-mv) 是 Rust 宿主运行时，使用了部分参考 crate（[CONSUMERS.md](CONSUMERS.md)）。它还包含 Spark 测试评判器（`tools/aien-test`）。
- [aien-architecture-mv](https://github.com/aien-dev/aien-architecture-mv) 负责规划、各项 ADR 以及整个系统的状态。
- [aien-receipts](https://github.com/aien-dev/aien-receipts) 存放本仓库的签名测试结果。

## 长期规则

语言规则：Rust 是脚手架，Omega 是终点，C 或汇编只保留在硬件、启动、ABI 或测量确有需要的地方（ADR 0024，它取代了旧的“C 是目标，不再新增 Rust”规则）。可信基中不使用 Python、不使用 CUDA 工具包、不使用 systemd，也没有任何外部依赖。

## 构建与测试

参考 crate 需要 Rust 工具链。各个门禁运行的命令如下：

```bash
cargo fmt --all -- --check
cargo check --workspace --all-targets
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

规范检查器只需要 bash、coreutils 和一个 C99 编译器：

```bash
bash specs/verified-crumb/tools/check-golden.sh
bash specs/osc-unit-artifact/tools/check-vectors.sh
bash specs/execution-transcript/tools/check-corpus.sh
bash specs/pi-spark-task/tools/check-vectors.sh
bash specs/microjob/tools/check-vectors.sh
bash specs/discovery-capsule/tools/check-vectors.sh
```

`tests/gates/run.sh <step>` 按名称运行单个门禁步骤。这些步骤是 `fmt`、`check`、`clippy`、`test`、`zero-disk-secrets`、`anti-slop` 和 `c-vectors`。`c-vectors` 步骤会运行所有 `specs/*/tools/check-*.sh`（即上面的检查器），只有全部通过时才算通过。`anti-slop` 步骤只要在 `crates/`、`docs/`、`README.md` 和 `ANTI_ENCLOSURE.md` 中发现任何长破折号或短破折号，就判为失败。

2026-10-19，上述所有命令都在 Spark 上针对 `main` 分支的 `fb5fca9` 运行通过，`crumb verify .` 输出了 `OK: 41 crumbs current`。

## 测试与证据

DGX Spark 是拉取请求唯一的测试评判器（aien-architecture 的 [ADR 0033](https://github.com/aien-dev/aien-architecture-mv/blob/main/docs/adr/0033-aien-verification-pipeline.md)；Spark 评判器于 2026-10-16 启用，PR #25）。2026-10-18，托管的测试工作流 `ci.yml` 被删除（PR #42）。剩下的唯一一个工作流 `.github/workflows/aien-verification.yml` 不构建也不测试代码：它只检查 Spark 签名的结果。2026-10-19，[docs/PIPELINE.md](docs/PIPELINE.md) 随之更新（PR #45），`.crumb` 文件也不再存储生成的数据；碎屑工具会按需计算这些数据（PR #44）。

- Spark 会运行 `tests/gates/` 中与改动相关的门禁，以及 `.aien/always` 中列出的门禁（`PROTO-ZERO-DISK-SECRETS`、`PROTO-ANTI-SLOP`），并发布提交状态“AIEN Verification (Spark)”。
- 签名结果发布在 [aien-receipts/aien-protocols](https://github.com/aien-dev/aien-receipts/tree/main/aien-protocols)，每个提交一个目录。
- [docs/PIPELINE.md](docs/PIPELINE.md) 说明了流程和合并规则。

## 待完成的工作

以下议题和拉取请求在 2026-10-19 时仍处于打开状态：

- 议题 #27 跟踪整个树莓派与 Spark 协议通道。其后续部分是会话规则（议题 #32，拉取请求 #38）和工具调用任务（议题 #33，拉取请求 #41）。
- 议题 #43：冻结 OSH 流与任务 ABI 向量。

## 参与贡献

针对 `main` 发起拉取请求，并附上你运行的命令及其输出。规范变更遵循 [GOVERNANCE.md](GOVERNANCE.md) 和 [VERSIONING.md](VERSIONING.md)。只有在 Spark 评判器通过且维护者加上 `ready-to-merge` 标签之后，拉取请求才会被合并。联系方式：aien@aienos.com。

## 许可

规范：[Community Specification License 1.0](LICENSE-SPEC)。代码与 crate：[Apache License 2.0](LICENSE-CODE)（Apache-2.0）。反封闭承诺：[ANTI_ENCLOSURE.md](ANTI_ENCLOSURE.md)。

## 人类主导的智能体工程

开发遵循人类主导的智能体工程（HDAE）：由人类确定目标、架构、约束、验收标准和停止点；智能体在这些边界内负责实现、执行检查、诊断失败并进行修改。人工评审保留对主张、验收和发布决策的责任。这里描述的是开发方法，并不改变运行时自主性或历史证据。

有关该方法的文档说明以及一个系统软件案例研究，参见 Gregory M. Kurtzer（2026），*Ginux: Building an Independent Kernel That Runs Linux Userspace through Human-Directed Agentic Engineering*，技术报告，v1，Zenodo，<https://doi.org/10.5281/zenodo.23682548>。
