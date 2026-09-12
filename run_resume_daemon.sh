#!/usr/bin/env bash
# ==============================================================================
# Script điều phối Auto Translator Daemon
# Dùng chung cho cả nohup và crontab
# ==============================================================================
set -e

# Tự động chuyển vào thư mục dự án
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Nạp môi trường cho cron và nohup
export PATH="/home/hiept/.local/bin:/usr/local/bin:$PATH"
export HOME="/home/hiept"

# Tạo sẵn thư mục logs nếu chưa có
mkdir -p "$SCRIPT_DIR/logs/resume_stories"

# Cấu hình mặc định (dễ dàng bật/tắt comment từng dòng bằng dấu #):
if [ $# -eq 0 ]; then
    ARGS=(
        --chapters 150
        --max-per-story 30
        # --sort-by recent       # recent (mới nhất) hoặc oldest (cũ nhất)
        # --strategy SPLIT       # SPLIT (cắt vừa trần) hoặc ATOMIC (bảo toàn mạch)
        # --story-id <id>        # Chỉ định dịch riêng 1 story_id
        # --no-upload            # Bỏ qua upload Google Drive (chạy thử nghiệm)
        # --dry-run              # Chỉ mô phỏng quét RAM, không tải file, không dịch
    )
    set -- "${ARGS[@]}"
fi

# Chuyển quyền thực thi sang Python daemon (-u: xả buffer log realtime)
exec "$SCRIPT_DIR/venv/bin/python" -u -m auto_translator_daemon.main "$@"