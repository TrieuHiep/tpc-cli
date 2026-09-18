#!/usr/bin/env bash
# ==============================================================================
# Script điều phối New Story Translator Daemon (Dịch mới truyện)
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
mkdir -p "$SCRIPT_DIR/logs/new_stories"

# Cấu hình mặc định (dễ dàng bật/tắt comment từng dòng bằng dấu #):
ARGS=(
    --workers 2
    --limit-stories 4
    --chapters 110
    # --sort-by recent          # recent (mới nhất) hoặc oldest (cũ nhất)
    # --source truyendichwiki    # Quét riêng 1 nguồn: ixdzs8, biquge, truyendichwiki, novel543
    # --story-id "id_A, id_B"             # Chỉ định 1 hoặc nhiều story_id phân cách bằng dấu phẩy
    # --exclude-story-id "id_C, id_D"     # Bỏ qua 1 hoặc nhiều story_id phân cách bằng dấu phẩy
    # --no-upload               # Bỏ qua upload Google Drive (chạy thử nghiệm)
    # --dry-run                 # Chỉ mô phỏng quét RAM, không tải file, không dịch
)

# Chuyển quyền thực thi sang Python daemon (-u: xả buffer log realtime)
# Nạp cấu hình ARGS từ file trước, sau đó nối thêm "$@" từ dòng lệnh (cho phép bổ sung / ghi đè)
exec "$SCRIPT_DIR/venv/bin/python" -u -m new_story_translator_daemon.main "${ARGS[@]}" "$@"