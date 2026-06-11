#!/usr/bin/env bash
#
# @file        backup.sh
# @description One-click backup script for ABC Desktop project
#              Backs up: Git repo, ArangoDB, Qdrant, .env files, Docker state
# @lastUpdate  2026-05-22 12:30:00
# @author      Daniel Chung
# @version     1.0.0
#
# Usage:
#   ./backup.sh                    # Full backup with all components
#   ./backup.sh --no-git           # Skip git archive
#   ./backup.sh --no-db            # Skip database backups
#   ./backup.sh --dry-run          # Show what would be done without doing it
#   ./backup.sh --help             # Show this help message
#
# Config:
#   BACKUP_DIR - Backup output directory (default: ./backups)
#   KEEP_LAST  - Number of old backups to keep (default: 5)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_ROOT}/backups}"
KEEP_LAST="${KEEP_LAST:-5}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_NAME="abc-desktop-${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

DO_GIT=true
DO_DB=true
DRY_RUN=false

usage() {
    sed -n 's/^# //p; s/^#$//p' "${BASH_SOURCE[0]}" | sed '1,2d'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-git)   DO_GIT=false;  shift ;;
        --no-db)    DO_DB=false;   shift ;;
        --dry-run)  DRY_RUN=true;  shift ;;
        --help|-h)  usage ;;
        *)          echo "Unknown option: $1"; usage ;;
    esac
done

info()  { echo -e "[\033[1;34mINFO\033[0m]  $*"; }
ok()    { echo -e "[\033[1;32m OK \033[0m]  $*"; }
warn()  { echo -e "[\033[1;33mWARN\033[0m]  $*"; }
err()   { echo -e "[\033[1;31mERR \033[0m]  $*"; }

run() {
    if [[ "$DRY_RUN" == true ]]; then
        echo -e "[\033[1;35mDRY\033[0m]  $*"
    else
        "$@"
    fi
}

preflight() {
    local fail=false

    if [[ ! -d "${PROJECT_ROOT}/.git" ]]; then
        err "Not a git repository: ${PROJECT_ROOT}"
        fail=true
    fi

    if ! command -v docker &>/dev/null; then
        warn "docker not found — container backups will be skipped"
    fi

    if [[ "$DRY_RUN" == false && -d "$BACKUP_PATH" ]]; then
        err "Backup directory already exists: ${BACKUP_PATH}"
        fail=true
    fi

    if [[ "$fail" == true ]]; then
        exit 1
    fi
}

step_create_dir() {
    info "Creating backup directory: ${BACKUP_PATH}"
    run mkdir -p "${BACKUP_PATH}"
    ok "Backup directory created"
}

step_git_archive() {
    if [[ "$DO_GIT" == false ]]; then
        info "Skipping git archive (--no-git)"
        return
    fi

    local archive_path="${BACKUP_PATH}/code.tar.gz"

    info "Creating git archive..."
    if [[ "$DRY_RUN" == false ]]; then
        (cd "$PROJECT_ROOT" && git archive --format=tar.gz HEAD > "$archive_path")
    fi
    ok "Git archive created: ${archive_path}"
}

step_db_backups() {
    if [[ "$DO_DB" == false ]]; then
        info "Skipping database backups (--no-db)"
        return
    fi

    if docker ps --format '{{.Names}}' | grep -q '^arangodb$'; then
        info "Backing up ArangoDB..."
        if command -v arangodump &>/dev/null; then
            run arangodump \
                --server.endpoint tcp://localhost:8529 \
                --server.username root \
                --server.password "abc_desktop_2026" \
                --server.database abc_desktop \
                --output-directory "${BACKUP_PATH}/arangodb/"
            ok "ArangoDB backup via arangodump complete"
        else
            info "arangodump not found — copying Docker volume data instead..."
            run docker cp arangodb:/var/lib/arangodb3 "${BACKUP_PATH}/arangodb-data/"
            ok "ArangoDB Docker volume copied"
        fi
    else
        warn "ArangoDB container not running — skipping database backup"
    fi

    if docker ps --format '{{.Names}}' | grep -q '^qdrant$'; then
        info "Backing up Qdrant..."
        run docker cp qdrant:/qdrant/storage "${BACKUP_PATH}/qdrant-storage/"
        ok "Qdrant storage copied"
    else
        warn "Qdrant container not running — skipping"
    fi

    if docker ps --format '{{.Names}}' | grep -q '^redis$'; then
        info "Backing up Redis RDB..."
        run mkdir -p "${BACKUP_PATH}/redis/"
        run docker exec redis redis-cli BGSAVE &>/dev/null || true
        sleep 1
        run docker cp redis:/data/dump.rdb "${BACKUP_PATH}/redis/dump.rdb" 2>/dev/null || \
            warn "Could not copy Redis dump (may be empty or container just started)"
        ok "Redis backup complete"
    else
        warn "Redis container not running — skipping"
    fi
}

step_env_files() {
    info "Copying .env files..."

    local env_files=(
        "${PROJECT_ROOT}/.env"
        "${PROJECT_ROOT}/.env.production"
        "${PROJECT_ROOT}/.env.development"
        "${PROJECT_ROOT}/api/.env"
        "${PROJECT_ROOT}/ai-services/.env"
    )

    for env_file in "${env_files[@]}"; do
        if [[ -f "$env_file" ]]; then
            local base_name
            base_name="$(basename "$(dirname "$env_file")")-$(basename "$env_file")"
            if [[ "$(dirname "$env_file")" == "$PROJECT_ROOT" ]]; then
                base_name="$(basename "$env_file")"
            fi
            run cp "$env_file" "${BACKUP_PATH}/${base_name}"
            ok "Copied: ${env_file}"
        else
            info "Skipping (not found): ${env_file}"
        fi
    done
}

step_docker_state() {
    info "Saving Docker services state..."

    if command -v docker &>/dev/null; then
        if [[ "$DRY_RUN" == false ]]; then
            docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}" \
                > "${BACKUP_PATH}/docker-services.txt"
        fi
        ok "Docker services state saved"
    else
        warn "docker not available — skipping"
    fi
}

step_final_tarball() {
    local tarball="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"

    info "Creating final tarball: ${tarball}"
    if [[ "$DRY_RUN" == false ]]; then
        (cd "$BACKUP_DIR" && tar -czf "${tarball}" "${BACKUP_NAME}/" && rm -rf "${BACKUP_NAME}/")
    fi
    ok "Tarball created: ${tarball}"

    if [[ "$DRY_RUN" == false && -f "$tarball" ]]; then
        local size
        size="$(du -h "$tarball" | cut -f1)"
        info "Backup size: ${size}"
    fi
}

step_cleanup() {
    info "Cleaning up old backups (keeping last ${KEEP_LAST})..."

    if [[ "$DRY_RUN" == false ]]; then
        local count
        count="$(ls -1t "${BACKUP_DIR}"/abc-desktop-*.tar.gz 2>/dev/null | wc -l | tr -d ' ')"

        if [[ "$count" -gt "$KEEP_LAST" ]]; then
            local to_delete
            to_delete=$((count - KEEP_LAST))
            warn "Removing ${to_delete} old backup(s)..."
            ls -1t "${BACKUP_DIR}"/abc-desktop-*.tar.gz 2>/dev/null | tail -n "$to_delete" | while read -r old; do
                rm -f "$old"
                ok "Removed: ${old}"
            done
        else
            info "No old backups to clean (${count} total, max ${KEEP_LAST})"
        fi
    fi
}

main() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║        ABC Desktop — Full Backup                            ║"
    echo "║        ${TIMESTAMP}                            ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo ""

    preflight

    step_create_dir
    step_git_archive
    step_db_backups
    step_env_files
    step_docker_state
    step_final_tarball
    step_cleanup

    echo ""
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║        Backup Complete!                                      ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo ""
    info "Backup file: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
    if [[ "$DRY_RUN" == true ]]; then
        warn "DRY RUN — no files were actually created"
    fi
    echo ""
}

main
