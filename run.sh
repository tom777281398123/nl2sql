#!/usr/bin/env bash
# 掌柜问数 (storekeeper-nl2sql) 一键起停脚本
#
# 用法:
#   ./run.sh start      启动全部 (中间件 + 后端 + 前端)
#   ./run.sh stop       停止全部 (前端 + 后端 + 中间件)
#   ./run.sh restart    重启全部
#   ./run.sh status     查看各组件状态
#   ./run.sh logs       跟踪后端 + 前端日志
#   ./run.sh build-kb   构建/重建元数据知识库
#
# 也可只操作某一层:
#   ./run.sh start  middleware|backend|frontend
#   ./run.sh stop   middleware|backend|frontend
#
# 说明:
#   - 中间件 (MySQL/ES/Kibana/Qdrant/Embedding) 由 Makefile + docker compose 管理。
#   - 后端 (FastAPI:8000) 与 前端 (Vite:5173) 以后台进程方式启动，
#     PID 写入 .run/ 目录，日志写入 logs/。
#   - embedding 模型走本地离线加载，详见 CLAUDE.md。

set -uo pipefail

# ---- 路径 ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RUN_DIR="$SCRIPT_DIR/.run"
LOG_DIR="$SCRIPT_DIR/logs"
BACKEND_PID="$RUN_DIR/backend.pid"
FRONTEND_PID="$RUN_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend.out"
FRONTEND_LOG="$LOG_DIR/frontend.out"
mkdir -p "$RUN_DIR" "$LOG_DIR"

# ---- 颜色输出 ----
c_green()  { printf '\033[32m%s\033[0m\n' "$*"; }
c_red()    { printf '\033[31m%s\033[0m\n' "$*"; }
c_yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
c_blue()   { printf '\033[36m%s\033[0m\n' "$*"; }
info()  { c_blue  "==> $*"; }
ok()    { c_green "  ✓ $*"; }
warn()  { c_yellow "  ! $*"; }
err()   { c_red   "  ✗ $*"; }

# ---- 工具检查 ----
need() { command -v "$1" >/dev/null 2>&1 || { err "缺少命令: $1"; exit 1; }; }

# ---- PID 进程判活 ----
pid_alive() {
  local pidfile="$1"
  [ -f "$pidfile" ] || return 1
  local pid; pid="$(cat "$pidfile" 2>/dev/null)"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

http_ready() {
  local url="$1"
  curl -fsS -m 3 -o /dev/null "$url" 2>/dev/null
}

listen_pid() {
  local port="$1"
  command -v lsof >/dev/null 2>&1 || return 1
  lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n 1
}

recover_http_process() {
  local name="$1" port="$2" url="$3" pidfile="$4"
  http_ready "$url" || return 1

  local pid; pid="$(listen_pid "$port" 2>/dev/null || true)"
  if [ -n "$pid" ]; then
    echo "$pid" >"$pidfile"
    ok "$name 已在运行 (端口 $port, PID $pid)"
  else
    ok "$name 已在运行 (端口 $port)"
    warn "未能记录 $name PID，停止时可能需要手动处理端口 $port"
  fi
  return 0
}

fail_if_port_busy() {
  local name="$1" port="$2"
  local pid; pid="$(listen_pid "$port" 2>/dev/null || true)"
  [ -z "$pid" ] && return 0
  err "$name 端口 $port 已被占用 (PID $pid)，为避免重复启动已中止"
  warn "如确认是旧进程，可先手动停止，或执行: kill $pid"
  return 1
}

# 等待某 URL 返回成功 (默认 60 次 * 2s)
wait_http() {
  local url="$1" name="$2" tries="${3:-60}"
  for ((i=1; i<=tries; i++)); do
    if http_ready "$url"; then
      ok "$name 就绪"
      return 0
    fi
    sleep 2
  done
  warn "$name 等待超时 (可能仍在启动): $url"
  return 1
}

# ============================ 中间件 ============================
start_middleware() {
  need docker; need make
  info "启动中间件 (MySQL / ES / Kibana / Qdrant / Embedding)"
  if ! docker info >/dev/null 2>&1; then
    err "Docker 守护进程未运行，请先启动 Docker Desktop"
    return 1
  fi
  make middleware
}

stop_middleware() {
  need make
  info "停止中间件"
  make down
}

# ============================ 后端 ============================
start_backend() {
  need uv
  if pid_alive "$BACKEND_PID"; then
    if http_ready "http://localhost:8000/docs"; then
      ok "后端已在运行 (PID $(cat "$BACKEND_PID"))"
      return 0
    fi
    warn "后端 PID 存在但健康检查未通过 (PID $(cat "$BACKEND_PID"))"
    warn "查看日志: tail -f $BACKEND_LOG"
    return 1
  fi
  recover_http_process "后端" 8000 "http://localhost:8000/docs" "$BACKEND_PID" && return 0
  fail_if_port_busy "后端" 8000 || return 1

  info "启动后端 FastAPI (http://0.0.0.0:8000)"
  nohup uv run python -m backend.main >"$BACKEND_LOG" 2>&1 &
  echo $! >"$BACKEND_PID"
  if ! wait_http "http://localhost:8000/docs" "后端" 30; then
    warn "查看日志: tail -f $BACKEND_LOG"
    return 1
  fi
}

stop_backend() {
  if pid_alive "$BACKEND_PID"; then
    local pid; pid="$(cat "$BACKEND_PID")"
    info "停止后端 (PID $pid)"
    kill "$pid" 2>/dev/null
    sleep 1; kill -9 "$pid" 2>/dev/null || true
    ok "后端已停止"
  else
    warn "后端未在运行"
  fi
  rm -f "$BACKEND_PID"
}

# ============================ 前端 ============================
start_frontend() {
  need npm
  if pid_alive "$FRONTEND_PID"; then
    if http_ready "http://127.0.0.1:5173/"; then
      ok "前端已在运行 (PID $(cat "$FRONTEND_PID"))"
      return 0
    fi
    warn "前端 PID 存在但健康检查未通过 (PID $(cat "$FRONTEND_PID"))"
    warn "查看日志: tail -f $FRONTEND_LOG"
    return 1
  fi
  recover_http_process "前端" 5173 "http://127.0.0.1:5173/" "$FRONTEND_PID" && return 0
  fail_if_port_busy "前端" 5173 || return 1

  if [ ! -d "$SCRIPT_DIR/fronted/node_modules" ]; then
    info "首次启动，安装前端依赖 (npm install)"
    ( cd "$SCRIPT_DIR/fronted" && npm install )
  fi
  info "启动前端 Vite (http://127.0.0.1:5173)"
  ( cd "$SCRIPT_DIR/fronted" && nohup npm run dev >"$FRONTEND_LOG" 2>&1 & echo $! >"$FRONTEND_PID" )
  if ! wait_http "http://127.0.0.1:5173/" "前端" 30; then
    warn "查看日志: tail -f $FRONTEND_LOG"
    return 1
  fi
}

stop_frontend() {
  if pid_alive "$FRONTEND_PID"; then
    local pid; pid="$(cat "$FRONTEND_PID")"
    info "停止前端 (PID $pid)"
    # vite 会派生子进程，按进程组杀
    kill "$pid" 2>/dev/null
    pkill -P "$pid" 2>/dev/null || true
    sleep 1; kill -9 "$pid" 2>/dev/null || true
    ok "前端已停止"
  else
    warn "前端未在运行"
  fi
  rm -f "$FRONTEND_PID"
}

# ============================ 知识库 ============================
build_kb() {
  need uv
  info "构建/重建元数据知识库 (build_meta_knowledge)"
  local clean_flag source_desc
  if [ "${SYS_ISCLEAN_CONFIG+x}" = "x" ]; then
    clean_flag="$SYS_ISCLEAN_CONFIG"
    source_desc="当前 shell 环境变量"
  else
    clean_flag="$(grep -E '^SYS_ISCLEAN_CONFIG=' "$SCRIPT_DIR/.env" 2>/dev/null | tail -n 1 | cut -d= -f2-)"
    source_desc=".env"
  fi
  case "$clean_flag" in
    true|TRUE|True|1|yes|YES|Yes|y|Y)
      warn "$source_desc 中 SYS_ISCLEAN_CONFIG=$clean_flag，本命令会先清空 meta 表、Qdrant collection 和 ES 索引，再重建"
      warn "如需保留已有知识库数据，可临时执行: SYS_ISCLEAN_CONFIG=false ./run.sh build-kb"
      ;;
    "")
      warn "未读取到 SYS_ISCLEAN_CONFIG，是否清空取决于 build 脚本默认行为"
      ;;
    *)
      warn "$source_desc 中 SYS_ISCLEAN_CONFIG=$clean_flag，默认不会先清空知识库数据"
      ;;
  esac
  uv run python -m backend.app.scripts.build_meta_knowledge --conf backend/conf/meta_config.yaml
}

# ============================ 组合命令 ============================
do_start() {
  start_middleware || return 1
  # 等 embedding 真正能 embed (本地加载需要 warmup)
  wait_http "http://localhost:8081/health" "Embedding 模型" 60 || return 1
  start_backend || return 1
  start_frontend || return 1
  echo
  c_green "===================================================="
  c_green "  全部启动完成"
  c_green "  前端:  http://127.0.0.1:5173"
  c_green "  后端:  http://localhost:8000/docs"
  c_green "===================================================="
  c_yellow "  首次使用如未建过知识库，请先执行: ./run.sh build-kb"
}

do_stop() {
  stop_frontend
  stop_backend
  stop_middleware
  ok "全部已停止"
}

status() {
  info "组件状态"
  # 中间件
  if docker info >/dev/null 2>&1; then
    docker ps --filter "name=storekeeper" \
      --format "  {{.Names}}: {{.Status}}" 2>/dev/null | grep . \
      || warn "无 storekeeper 中间件容器在运行"
  else
    err "Docker 守护进程未运行"
  fi
  # 后端
  if pid_alive "$BACKEND_PID"; then ok "后端 PID $(cat "$BACKEND_PID")"; else warn "后端未运行"; fi
  # 前端
  if pid_alive "$FRONTEND_PID"; then ok "前端 PID $(cat "$FRONTEND_PID")"; else warn "前端未运行"; fi
  echo
  info "端口健康检查"
  curl -fsS -m 3 -o /dev/null "http://localhost:8081/health" 2>/dev/null && ok "Embedding 8081" || warn "Embedding 8081 不可达"
  curl -fsS -m 3 -o /dev/null "http://localhost:9200/_cluster/health" 2>/dev/null && ok "Elasticsearch 9200" || warn "ES 9200 不可达"
  curl -fsS -m 3 -o /dev/null "http://localhost:6333/healthz" 2>/dev/null && ok "Qdrant 6333" || warn "Qdrant 6333 不可达"
  curl -fsS -m 3 -o /dev/null "http://localhost:8000/docs" 2>/dev/null && ok "后端 8000" || warn "后端 8000 不可达"
  curl -fsS -m 3 -o /dev/null "http://127.0.0.1:5173/" 2>/dev/null && ok "前端 5173" || warn "前端 5173 不可达"
}

logs() {
  info "跟踪后端 + 前端日志 (Ctrl-C 退出)"
  touch "$BACKEND_LOG" "$FRONTEND_LOG"
  tail -f "$BACKEND_LOG" "$FRONTEND_LOG"
}

usage() {
  cat <<EOF
掌柜问数 起停脚本

用法: ./run.sh <命令> [组件]

命令:
  start    [middleware|backend|frontend]   启动 (默认全部)
  stop     [middleware|backend|frontend]   停止 (默认全部)
  restart                                  重启全部
  status                                   查看状态 + 健康检查
  logs                                     跟踪后端/前端日志
  build-kb                                 构建/重建元数据知识库

示例:
  ./run.sh start            # 一键全启
  ./run.sh start backend    # 只启后端
  ./run.sh status
  ./run.sh stop
EOF
}

# ============================ 入口 ============================
cmd="${1:-}"; comp="${2:-}"
case "$cmd" in
  start)
    case "$comp" in
      middleware) start_middleware ;;
      backend)    start_backend ;;
      frontend)   start_frontend ;;
      "")         do_start ;;
      *)          err "未知组件: $comp"; usage; exit 1 ;;
    esac ;;
  stop)
    case "$comp" in
      middleware) stop_middleware ;;
      backend)    stop_backend ;;
      frontend)   stop_frontend ;;
      "")         do_stop ;;
      *)          err "未知组件: $comp"; usage; exit 1 ;;
    esac ;;
  restart)  do_stop; echo; do_start ;;
  status)   status ;;
  logs)     logs ;;
  build-kb) build_kb ;;
  ""|-h|--help|help) usage ;;
  *) err "未知命令: $cmd"; usage; exit 1 ;;
esac
