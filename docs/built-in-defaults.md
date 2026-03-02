# Dippy Built-in Defaults

What Dippy auto-approves out of the box with zero configuration.

## Decision Priority

1. Config rules (highest) — user's `allow`/`deny`/`ask` in `~/.dippy/config` and `.dippy`
2. CLI handlers — 85+ command-specific analyzers
3. Wrapper unwrap — passes through to inner command
4. Built-in allowlist — ~200 known safe read-only commands
5. Default → `ask`

---

## Built-in Safe Commands (any args, always allowed)

Hardcoded in `src/dippy/core/allowlists.py`. Output redirects are still checked separately.

**File Viewing:**
`cat` `head` `tail` `less` `more` `bat` `tac` `od` `hexdump` `strings`

**Compressed File Viewers:**
`bzcat` `bzmore` `funzip` `lz4cat` `xzcat` `xzless` `xzmore` `zcat` `zless` `zmore` `zstdcat` `zstdless` `zipinfo`

**Binary Analysis:**
`dwarfdump` `dyld_info` `ldd` `lsbom` `nm` `objdump` `otool` `pagestuff` `readelf` `size`

**Directory Listing:**
`ls` `ll` `la` `tree` `exa` `eza` `dir` `vdir`

**File & Disk Info:**
`stat` `file` `wc` `du` `df`

**Path Utilities:**
`basename` `dirname` `pathchk` `pwd` `cd` `readlink` `realpath`

**Search & Find:**
`grep` `rg` `ripgrep` `ag` `ack` `locate` `look` `mdfind` `mdls`

**Text Processing:**
`uniq` `cut` `col` `colrm` `column` `comm` `cmp` `diff` `diff3` `diffstat` `expand` `fmt` `fold` `jot` `join` `lam` `nl` `paste` `pr` `rev` `rs` `seq` `tr` `tsort` `ul` `unexpand` `unvis` `vis` `what`

**Calculators:**
`bc` `dc` `expr` `units`

**Structured Data:**
`jq` `xq`

**Encoding & Checksums:**
`base64` `md5sum` `sha1sum` `sha256sum` `sha512sum` `b2sum` `cksum` `md5` `shasum` `sum`

**User & System Info:**
`whoami` `hostname` `hostinfo` `uname` `sw_vers` `id` `finger` `groups` `last` `locale` `logname` `users` `w` `who` `klist`

**Date & Time:**
`date` `cal` `ncal` `uptime`

**System Configuration:**
`getconf` `machine` `pagesize` `uuidgen`

**Process & Resource Monitoring:**
`atos` `btop` `footprint` `free` `fs_usage` `fuser` `heap` `htop` `ioreg` `iostat` `ipcs` `leaks` `lskq` `lsmp` `lsof` `lsvfs` `lpstat` `nettop` `pgrep` `powermetrics` `ps` `system_profiler` `top` `vm_stat` `vmmap` `vmstat`

**Environment & Output:**
`printenv` `echo` `printf`

**Network Diagnostics:**
`ping` `host` `dig` `nslookup` `traceroute` `mtr` `netstat` `ss` `arp` `route` `whois`

**Command Lookup & Help:**
`which` `whereis` `type` `command` `hash` `apropos` `man` `help` `info` `osalang` `tldr` `whatis`

**Code Quality & Linting:**
`cloc` `flake8` `mypy`

**Media & Image Info:**
`afinfo` `afplay` `ffprobe` `heif-info` `identify` `opj_dump` `rdjpgcom` `sndfile-info` `tiffdump` `tiffinfo` `webpinfo`

**Shell Builtins & Utilities:**
`true` `false` `getopt` `getopts` `shopt` `sleep` `read` `test` `wait` `yes`

**Terminal:**
`banner` `clear` `pbpaste` `reset` `tabs` `tput` `tty`

---

## Transparent Wrappers

These pass through to the inner command for analysis:

`time` `timeout` `nice` `nohup` `strace` `ltrace` `command` `builtin`

---

## CLI Handlers

Dedicated analyzers in `src/dippy/cli/` that inspect subcommands and arguments. Read-only subcommands are auto-approved; write operations may `ask` or `deny`.

`7z` `ansible` `arch` `auth0` `awk` `aws` `azure` `binhex` `black` `brew` `caffeinate` `cargo` `cdk` `codesign` `compression_tool` `curl` `defaults` `diskutil` `dmesg` `docker` `dscl` `duckdb` `env` `fd` `find` `fzf` `gcloud` `gh` `git` `gzip` `hdiutil` `helm` `iconv` `ifconfig` `ip` `isort` `journalctl` `kubectl` `launchctl` `lipo` `mdimport` `mktemp` `mysql` `networksetup` `npm` `open` `openssl` `packer` `pip` `pkgutil` `plutil` `pre_commit` `profiles` `prometheus` `psql` `pytest` `python` `qlmanage` `ruff` `sample` `say` `script` `scutil` `security` `sed` `shell` `sips` `sort` `spctl` `sqlcmd` `sqlite3` `symbols` `sysctl` `tar` `tee` `terraform` `textutil` `tmutil` `uv` `wget` `xargs` `xattr` `xxd` `yq`
