import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "story-translator-cli"))

from new_story_translator_daemon.config import RAW_DRIVE_FOLDERS as NEW_RAW, VAULT_DRIVE_FOLDERS as NEW_VAULT
from new_story_translator_daemon.drive_new_scanner import DriveNewScanner
from new_story_translator_daemon.drive_syncer import DriveSyncer as NewDriveSyncer
import new_story_translator_daemon.worker as new_worker

from auto_translator_daemon.config import RAW_DRIVE_FOLDERS as AUTO_RAW, VAULT_DRIVE_FOLDERS as AUTO_VAULT
from auto_translator_daemon.drive_scanner import DriveScanner
from auto_translator_daemon.drive_syncer import DriveSyncer as AutoDriveSyncer
import auto_translator_daemon.worker as auto_worker


def test_folder_mappings_match():
    print("\n--- Test 1: Kiểm tra cấu hình 5 cặp thư mục Nguồn Raw ↔ Kho Dịch tpc-dw ---")
    assert NEW_RAW == AUTO_RAW
    assert NEW_VAULT == AUTO_VAULT
    expected_vault = {
        "fanqienovel": "1xz0LbGrtzw8bszkjhdTvNeEaQx0dIF25",
        "ixdzs8": "1OQOR6g2mQx01j4GpSXb4PdGFKFAsZWle",
        "biquge": "1hCTEVsat8EYSqSitbo6MloO0-XpktXXr",
        "truyendichwiki": "1uV-TH8m4FtmY7TgIFZJIofa6UITq_ZT1",
        "novel543": "1XtmQyLBUFpJuKJyU3vfvi4-HwpskYiao",
    }
    assert AUTO_VAULT == expected_vault
    print("✅ PASS: 5 cặp Root ID chuẩn xác 100%.")


def test_new_scanner_left_anti_join_ignores_stale_raw_translated_zip():
    print("\n--- Test 2: DriveNewScanner Left Anti Join (loại truyện đã có trên Vault, phớt lờ file dịch cũ sót bên Raw) ---")
    mock_gdrive = MagicMock()
    scanner = DriveNewScanner(mock_gdrive)

    src = "truyendichwiki"
    raw_root = NEW_RAW[src]
    vault_root = NEW_VAULT[src]

    # Story A: có bên Raw VÀ đã có translated_chapters.zip bên Vault -> phải BỎ QUA
    # Story B: có bên Raw (thậm chí còn sót file translated_chapters.zip cũ bên Raw), nhưng CHƯA CÓ bên Vault -> phải CHỌN dịch mới!
    def fake_fetch_children(root_id):
        if root_id == raw_root:
            return {
                "raw_A": {"id": "raw_A", "name": "STORY_A"},
                "raw_B": {"id": "raw_B", "name": "STORY_B"},
            }
        if root_id == vault_root:
            return {
                "vault_A": {"id": "vault_A", "name": "STORY_A"},
            }
        return {}

    scanner.fetch_all_child_folders = fake_fetch_children
    scanner.fetch_all_relevant_files = lambda: {
        "raw_A": {"chapters.zip": {"id": "cz_A", "size": "50000", "modifiedTime": "2026-11-10T00:00:00Z"}},
        "vault_A": {"translated_chapters.zip": {"id": "tz_A", "size": "60000"}},
        "raw_B": {
            "chapters.zip": {"id": "cz_B", "size": "50000", "modifiedTime": "2026-11-11T00:00:00Z"},
            "info.json": {"id": "info_B", "size": "500"},
            "translated_chapters.zip": {"id": "stale_tz_B", "size": "99999"},  # File rác cũ còn sót bên Raw
        },
    }

    res = scanner.scan_all_new_stories(target_source=src)
    stories = res[src]
    assert len(stories) == 1
    assert stories[0]["story_id"] == "STORY_B"
    assert stories[0]["raw_folder_id"] == "raw_B"
    assert stories[0]["vault_folder_id"] is None
    assert "translated_chapters.zip" not in stories[0]["files_meta"]
    print("✅ PASS: DriveNewScanner nhận diện chính xác truyện mới theo tpc-dw và chống đọc nhầm file cũ bên Raw.")


def test_auto_scanner_inner_join_and_web_priority():
    print("\n--- Test 3: DriveScanner Inner Join & Web Priority Dual-Resolver ---")
    mock_gdrive = MagicMock()
    mock_web_mgr = MagicMock()
    src = "fanqienovel"
    raw_root = AUTO_RAW[src]
    vault_root = AUTO_VAULT[src]

    mock_web_mgr.priority_stories = {
        "7627509785704811545": {
            "story_id": "7627509785704811545",
            "title": "Truyện Test Web",
            "drive_folder_id": "raw_folder_123",  # driveUrl cũ trên Web DB
            "source": "fanqienovel",
            "is_web_priority": True,
        }
    }

    scanner = DriveScanner(mock_gdrive, web_priority_mgr=mock_web_mgr)

    # Giả lập API get folder trả về parent thuộc RAW_DRIVE_FOLDERS
    mock_gdrive.service.files().get.return_value.execute.return_value = {
        "id": "raw_folder_123",
        "name": "7627509785704811545",
        "parents": [raw_root],
    }
    scanner._find_child_folder_id = lambda r_id, sid: "vault_folder_999" if (r_id == vault_root and sid == "7627509785704811545") else None
    scanner._list_folder_files = lambda fid, fnames: (
        {"chapters.zip": {"id": "cz_1", "size": "100000", "modifiedTime": "2026-11-11T01:00:00Z"}}
        if fid == "raw_folder_123"
        else {"translated_chapters.zip": {"id": "tz_1", "size": "80000"}, "glossary.json": {"id": "gl_1", "size": "200"}}
    )

    mock_inspector = MagicMock()
    mock_inspector.inspect_story_remotely.return_value = {
        "is_valid": True,
        "raw_chapters_count": 120,
        "translated_chapters_count": 100,
        "new_chapters": list(range(101, 121)),
    }

    web_q, count, proc_ids, skipped = scanner.inspect_web_priority_stories(mock_inspector, limit=50)
    assert len(web_q) == 1
    assert count == 20
    s_info = web_q[0]["story_info"]
    assert s_info["raw_folder_id"] == "raw_folder_123"
    assert s_info["vault_folder_id"] == "vault_folder_999"
    assert s_info["chapters_file"]["id"] == "cz_1"
    assert s_info["translated_chapters_file"]["id"] == "tz_1"
    print("✅ PASS: Web Priority tự động ánh xạ RawFolderId cũ sang VaultFolderId trên tpc-dw thành công.")


def test_upload_failure_alerts_telegram_and_isolates_story():
    print("\n--- Test 4: Lỗi Upload lên Google Drive -> Bắn cảnh báo Telegram & Cô lập giữ an toàn bản dịch ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        temp_resume = tmp_root / "temp"
        temp_failed = tmp_root / "temp_failed"
        temp_resume.mkdir()
        temp_failed.mkdir()

        orig_resume = auto_worker.TEMP_RESUME_DIR
        orig_failed = auto_worker.TEMP_FAILED_DIR
        orig_pre = auto_worker.PreTranslateValidator
        orig_dl = auto_worker.download_resume_story_to_dir
        orig_tok = auto_worker.get_drive_auth_token

        try:
            auto_worker.TEMP_RESUME_DIR = temp_resume
            auto_worker.TEMP_FAILED_DIR = temp_failed
            auto_worker.get_drive_auth_token = lambda _: "mock_token"

            def fake_download(story_info, local_dir, auth_token, service=None):
                c1 = local_dir / "chapters" / "chap_1"
                c2 = local_dir / "chapters" / "chap_2"
                c1.mkdir(parents=True, exist_ok=True)
                c2.mkdir(parents=True, exist_ok=True)
                (c1 / "content.txt").write_text("Raw chap 1", encoding="utf-8")
                (c1 / "content_vi.txt").write_text("Chương 1: Bản dịch cũ", encoding="utf-8")
                (c2 / "content.txt").write_text("Raw chap 2", encoding="utf-8")
                return True

            auto_worker.download_resume_story_to_dir = fake_download

            mock_pre_instance = MagicMock()
            mock_pre_instance.validate_story.return_value = (True, {"allowed_to_translate": True, "is_complete": False, "report_brief": "OK"})
            auto_worker.PreTranslateValidator = lambda timeout_minutes=5: mock_pre_instance

            mock_agy = MagicMock()
            mock_agy.prepare_local_workspace.return_value = "Truyện Test Upload Fail"

            def fake_run_translation(story_dir, chaps):
                c2 = story_dir / "chapters" / "chap_2"
                (c2 / "content_vi.txt").write_text("Chương 2: Nội dung mới dịch đạt chuẩn QC", encoding="utf-8")
                return True

            mock_agy.run_translation.side_effect = fake_run_translation

            mock_qc = MagicMock()
            mock_qc.create_chapters_snapshot.return_value = {"chapters/chap_1/content_vi.txt": "hash1"}
            mock_qc.validate_directory_chapters.return_value = (True, [{"chapter": 2, "passed": True, "reason": "OK"}])
            mock_qc.validate_total_chapters_integrity.return_value = (True, "PASSED", {})

            # Giả lập Google Drive bị lỗi mạng khi upload translated_chapters.zip
            mock_gdrive = MagicMock()
            mock_gdrive.upload_or_update_file.return_value = None
            mock_gdrive.get_last_error.return_value = "HttpError 503: Backend Error"
            syncer = AutoDriveSyncer(mock_gdrive)

            mock_notifier = MagicMock()

            item = {
                "story_id": "STORY_UPLOAD_ERR",
                "source": "fanqienovel",
                "chapters_to_translate": [2],
                "story_info": {
                    "source": "fanqienovel",
                    "story_id": "STORY_UPLOAD_ERR",
                    "raw_folder_id": "raw_111",
                    "vault_folder_id": "vault_222",
                    "story_folder_id": "vault_222",
                },
                "inspected_meta": {"raw_chapters_count": 2},
            }

            res = auto_worker.process_single_resume_story(
                item=item,
                gdrive_service=mock_gdrive,
                agy_runner=mock_agy,
                qc_validator=mock_qc,
                syncer=syncer,
                notifier=mock_notifier,
                no_upload=False,
            )

            assert res["sync_status"] == "FAILED ❌"
            # Kiểm tra Telegram notify_story_failed ĐÃ ĐƯỢC GỌI với lý do lỗi upload và vault_folder_id
            assert mock_notifier.notify_story_failed.called, "Phải gọi notify_story_failed khi upload lỗi!"
            call_args, call_kwargs = mock_notifier.notify_story_failed.call_args
            assert "HttpError 503" in call_args[2]
            assert call_kwargs["folder_id"] == "vault_222"
            assert call_kwargs["isolated_path"] == "storage/temp_failed/STORY_UPLOAD_ERR"

            # Kiểm tra bản dịch mới được bảo toàn trong temp_failed, KHÔNG bị xóa mất!
            isolated_vi = temp_failed / "STORY_UPLOAD_ERR" / "chapters" / "chap_2" / "content_vi.txt"
            assert isolated_vi.exists(), "Bản dịch phải được giữ lại trong temp_failed khi upload Drive lỗi!"
            print("✅ PASS: Lỗi Upload Drive đã kích hoạt cảnh báo Telegram và bảo toàn dữ liệu vào storage/temp_failed!")
        finally:
            auto_worker.TEMP_RESUME_DIR = orig_resume
            auto_worker.TEMP_FAILED_DIR = orig_failed
            auto_worker.PreTranslateValidator = orig_pre
            auto_worker.download_resume_story_to_dir = orig_dl
            auto_worker.get_drive_auth_token = orig_tok


if __name__ == "__main__":
    test_folder_mappings_match()
    test_new_scanner_left_anti_join_ignores_stale_raw_translated_zip()
    test_auto_scanner_inner_join_and_web_priority()
    test_upload_failure_alerts_telegram_and_isolates_story()
    print("\n🎉 TOÀN BỘ 4 TEST CASES DUAL-DRIVE & TELEGRAM UPLOAD ALERT ĐỀU PASS 100%!")
