
# Bash Tools Reference

Tools available via Bash that have no native Claude Code alternative.
Use these when the built-in Read/Write/Edit/Glob/Grep tools can't do the job.

> **Reminder:** Prefer native tools first: `Read` over cat/head/tail, `Grep` over grep/rg/ag,
> `Glob` over find/ls, `Edit` over sed/awk for file edits, `Write` over echo redirection.

---

## Go Toolchain

| Tool | When to use |
|------|------------|
| `go test` | Run unit/integration tests, benchmarks, coverage |
| `go vet` | Catch suspicious code patterns before committing |
| `go build` | Compile to verify code builds without errors |
| `go doc` | Look up package/function documentation from terminal |
| `go list` | Query package paths, module info, dependency metadata |
| `go mod graph` | Visualize full module dependency tree |
| `go mod why` | Explain why a specific module is in go.sum |
| `go tool` | Run pprof profiling, trace analysis, coverage reports |

## Go Linters & Analysis

| Tool | When to use |
|------|------------|
| `staticcheck` | Deep static analysis — catches bugs, performance issues, deprecated APIs |
| `golangci-lint` | Run multiple linters in one pass before committing |
| `deadcode` | Find unreachable functions to clean up |
| `callgraph` | Build function call graph to understand code flow |
| `guru` | Find callers, implementers, referrers of Go symbols |
| `gopls` | Query Go language server for definitions, references, rename |
| `gosec` | Scan for security vulnerabilities in Go code |

## Java Toolchain

| Tool | When to use |
|------|------------|
| `javac` | Compile Java sources to check for errors |
| `java` | Run Java programs or JVM-based tools |
| `javap` | Disassemble .class files to inspect bytecode |
| `jar` | Inspect or create JAR archives |
| `mvn` | Build, test, package with Maven (compile/test/verify/install) |
| `jdeps` | Analyze class-level dependencies between JARs |
| `jstack` | Dump thread stacks of a running JVM for debugging |

## Build & Code Gen

| Tool | When to use |
|------|------------|
| `make` | Run Makefile targets (build, test, lint, generate) |
| `cmake` | Generate build files for C/C++ projects |
| `ninja` | Fast parallel builds (often paired with cmake) |
| `meson` | Configure Meson build projects |
| `protoc` | Compile .proto files to generate Go/Java/TS stubs |
| `plantuml` | Generate UML diagrams from text descriptions |
| `tsc` | Type-check TypeScript without bundling |

## Git (write operations)

Dippy's git handler auto-approves all read-only git commands.
These write operations are also allowed:

| Tool | When to use |
|------|------------|
| `git add` | Stage files for commit |
| `git commit` | Create a commit (use HEREDOC for message) |
| `git pull` | Fetch and merge remote changes |
| `git push` | Push to remote (will ask for confirmation) |
| `git stash` | Temporarily save uncommitted changes |
| `git branch` | Create, list, or delete branches |
| `git checkout` | Switch branches or restore files |
| `git merge` | Merge branches |
| `git rebase` | Reapply commits on top of another base |
| `git worktree add` | Create a worktree for parallel work |

## Docker & Containers

Dippy's docker handler auto-approves inspect/logs/ps/stats.
Use Bash for:

| Tool | When to use |
|------|------------|
| `docker compose up/down` | Start/stop local dev environment |
| `docker compose logs` | Tail service logs in compose stack |
| `docker build` | Build container images |
| `docker exec` | Run a command inside a running container |

## Kubernetes

Dippy's kubectl handler auto-approves get/describe/logs/top.
Use Bash for:

| Tool | When to use |
|------|------------|
| `kubectl events` | View cluster events for debugging |
| `kubectl debug` | Attach ephemeral debug container to a pod |
| `kubectx` | Switch between k8s cluster contexts |
| `kubens` | Switch between k8s namespaces |
| `kustomize` | Generate k8s manifests from overlays |
| `stern` | Tail logs from multiple pods simultaneously |

## Helm

Dippy's helm handler auto-approves list/status/get/show/template.
Use Bash for:

| Tool | When to use |
|------|------------|
| `helm template` | Render chart templates locally without installing |
| `helm lint` | Validate chart structure before deploying |
| `helm diff` | Preview changes before helm upgrade |

## Shell & Text Processing

Use these for **pipeline data transformations** (not file reading — use `Read` for that):

| Tool | When to use |
|------|------------|
| `jq` | Parse, filter, transform JSON (API responses, configs) |
| `yq` | Parse, filter, transform YAML/XML/TOML |
| `sort` | Sort lines in a pipeline (e.g. `\| sort -u`) |
| `uniq` | Deduplicate adjacent lines (pair with sort) |
| `diff` | Compare two files side by side |
| `comm` | Set operations on sorted files (intersection, difference) |
| `xargs` | Convert stdin to arguments for another command |
| `tee` | Write pipeline output to file AND stdout |
| `wc` | Count lines, words, bytes |

## File Operations

| Tool | When to use |
|------|------------|
| `mkdir` | Create directories |
| `touch` | Create empty files or update timestamps |
| `cp` | Copy files or directories |
| `mv` | Move or rename files |
| `chmod +x` | Make scripts executable |
| `trasher` | Safe delete (moves to trash, not permanent rm) |
| `tree` | Visualize directory structure as tree |
| `file` | Detect file type by content (binary vs text, encoding) |

## HTTP & Network

| Tool | When to use |
|------|------------|
| `curl` | Make HTTP requests to localhost APIs (POST/PUT/DELETE) |
| `http` / `https` | HTTPie — human-readable HTTP client for API testing |
| `grpcurl` | Call gRPC services (like curl for gRPC) |
| `evans` | Interactive gRPC REPL for exploring services |
| `nmap` | Scan network ports for debugging connectivity |
| `wget` | Download files from URLs |

## gRPC / Protobuf

| Tool | When to use |
|------|------------|
| `buf lint` | Lint .proto files for style violations |
| `buf breaking` | Check for breaking changes in proto schemas |
| `buf build` | Compile protobuf files |
| `buf format` | Auto-format .proto files |
| `grpcui` | Open web UI for exploring gRPC services |

## Linters & Quality

| Tool | When to use |
|------|------------|
| `shellcheck` | Lint shell scripts for bugs and portability issues |
| `markdownlint` | Check markdown files for style violations |

## Code Search (specialized)

| Tool | When to use |
|------|------------|
| `zoekt` | Trigram-based instant code search across repos |
| `grepai` | Semantic AI-powered code search |
| `delta` | Pretty git diff viewer with syntax highlighting |
| `difft` | Structural diff (understands language AST, not just lines) |

## JS/TS Runtimes

| Tool | When to use |
|------|------------|
| `node` | Run Node.js scripts |
| `npx` | Run npm packages without installing globally |
| `pnpx` | Run pnpm packages without installing globally |
| `corepack` | Manage Node package manager versions (npm/yarn/pnpm) |
| `deno` | Run TypeScript/JavaScript with built-in tooling |

## NATS Messaging

| Tool | When to use |
|------|------------|
| `nats pub/sub` | Publish or subscribe to NATS subjects |
| `nats stream` | Manage JetStream streams |
| `nats kv` | Key-value store operations |

> **Caution:** `nats delete/rm/purge` will ask for confirmation.

## GitLab CLI

| Tool | When to use |
|------|------------|
| `glab mr list/view/diff` | Browse merge requests |
| `glab issue list/view` | Browse issues |
| `glab ci list/view/trace` | Check CI/CD pipeline status and logs |
| `glab repo search` | Search repositories |
| `glab release list/view` | Browse releases |

## Misc Dev Tools

| Tool | When to use |
|------|------------|
| `pandoc` | Convert between document formats (md, html, pdf, docx) |
| `excalidraw-converter` | Convert Excalidraw diagrams to images |
| `allure` | Generate test report from results |
| `envsubst` | Substitute environment variables in templates |
| `ctags` | Generate tag files for code navigation |
| `gdu` | Interactive disk usage analyzer |
| `memory_pressure` | Check macOS memory pressure |
| `watch` | Re-run a command periodically to monitor changes |
| `ollama` | Run local LLMs for testing/comparison |
| `jenv` | Switch between Java versions |
| `opam` | OCaml package manager |
