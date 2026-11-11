import sys
import shutil
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from auto_translator_daemon.qc_validator import QCValidator, compute_file_sha256

def setup_mock_story_dir(base_path: Path, story_name: str, num_old_chapters: int = 5):
    story_dir = base_path / story_name
    chapters_dir = story_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    
    for i in range(1, num_old_chapters + 1):
        chap_dir = chapters_dir / f"chap_{i}"
        chap_dir.mkdir(parents=True, exist_ok=True)
        (chap_dir / "content.txt").write_text(f"Raw content chapter {i}", encoding='utf-8')
        (chap_dir / "content_vi.txt").write_text(f"Chương {i}: Nội dung tiếng Việt chương {i}", encoding='utf-8')
    
    return story_dir

def test_scenario_1_success():
    print("\n--- Test Scenario 1: Hợp lệ (Thêm chương mới, chương cũ giữ nguyên) ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        story_dir = setup_mock_story_dir(tmp_path, "story_test_1", 5)
        
        validator = QCValidator()
        snapshot = validator.create_chapters_snapshot(story_dir)
        assert len(snapshot) == 5, f"Expected 5 chapters in snapshot, got {len(snapshot)}"
        
        # Thêm 2 chương mới (chương 6, 7)
        for i in [6, 7]:
            chap_dir = story_dir / "chapters" / f"chap_{i}"
            chap_dir.mkdir(parents=True, exist_ok=True)
            (chap_dir / "content.txt").write_text(f"Raw content chapter {i}", encoding='utf-8')
            (chap_dir / "content_vi.txt").write_text(f"Chương {i}: Nội dung tiếng Việt chương {i}", encoding='utf-8')
            
        passed, reason, stats = validator.validate_total_chapters_integrity(
            chapters_dir=story_dir / "chapters",
            initial_count=5,
            new_chaps_count=2,
            initial_snapshot=snapshot,
            story_dir=story_dir
        )
        assert passed is True, f"Validation failed: {reason}"
        print(f"✅ PASS: {reason}")
        print(f"   Stats: {stats}")

def test_scenario_2_file_deleted():
    print("\n--- Test Scenario 2: LLM vô tình xóa mất 1 chương cũ ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        story_dir = setup_mock_story_dir(tmp_path, "story_test_2", 5)
        
        validator = QCValidator()
        snapshot = validator.create_chapters_snapshot(story_dir)
        
        # Thêm 2 chương mới
        for i in [6, 7]:
            chap_dir = story_dir / "chapters" / f"chap_{i}"
            chap_dir.mkdir(parents=True, exist_ok=True)
            (chap_dir / "content_vi.txt").write_text(f"Chương {i}: Nội dung mới", encoding='utf-8')
            
        # Xóa mất chương 2 cũ
        (story_dir / "chapters" / "chap_2" / "content_vi.txt").unlink()
        
        passed, reason, stats = validator.validate_total_chapters_integrity(
            chapters_dir=story_dir / "chapters",
            initial_count=5,
            new_chaps_count=2,
            initial_snapshot=snapshot,
            story_dir=story_dir
        )
        assert passed is False, "Should have failed due to missing chapter"
        assert "bị mất hoặc rỗng" in reason, f"Unexpected reason: {reason}"
        print(f"✅ Bắt lỗi thành công khi bị xóa: {reason}")

def test_scenario_3_file_modified():
    print("\n--- Test Scenario 3: LLM sửa đổi dữ liệu chương cũ (kích thước vẫn > 0) ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        story_dir = setup_mock_story_dir(tmp_path, "story_test_3", 5)
        
        validator = QCValidator()
        snapshot = validator.create_chapters_snapshot(story_dir)
        
        # Thêm 2 chương mới
        for i in [6, 7]:
            chap_dir = story_dir / "chapters" / f"chap_{i}"
            chap_dir.mkdir(parents=True, exist_ok=True)
            (chap_dir / "content_vi.txt").write_text(f"Chương {i}: Nội dung mới", encoding='utf-8')
            
        # Sửa đổi 1 ký tự trong chương 3 cũ
        chap3_file = story_dir / "chapters" / "chap_3" / "content_vi.txt"
        chap3_content = chap3_file.read_text(encoding='utf-8')
        chap3_file.write_text(chap3_content + " (đã bị LLM sửa đổi trái phép)", encoding='utf-8')
        
        passed, reason, stats = validator.validate_total_chapters_integrity(
            chapters_dir=story_dir / "chapters",
            initial_count=5,
            new_chaps_count=2,
            initial_snapshot=snapshot,
            story_dir=story_dir
        )
        assert passed is False, "Should have failed due to modified hash"
        assert "bị sửa đổi trái phép" in reason, f"Unexpected reason: {reason}"
        assert "chap_3/content_vi.txt" in reason or "chap_3\\content_vi.txt" in reason, f"Should mention chap_3: {reason}"
        print(f"✅ Bắt lỗi thành công khi bị sửa đổi nội dung: {reason}")

def test_scenario_4_multithreaded():
    print("\n--- Test Scenario 4: Chạy song song đa luồng (Multi-workers) ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        validator = QCValidator()
        
        def worker_task(idx):
            s_dir = setup_mock_story_dir(tmp_path, f"story_thread_{idx}", 10)
            snap = validator.create_chapters_snapshot(s_dir)
            assert len(snap) == 10
            
            # Thêm chương 11..15
            for i in range(11, 16):
                c_dir = s_dir / "chapters" / f"chap_{i}"
                c_dir.mkdir(parents=True, exist_ok=True)
                (c_dir / "content_vi.txt").write_text(f"Chương {i} thread {idx}", encoding='utf-8')
                
            p, r, s = validator.validate_total_chapters_integrity(
                chapters_dir=s_dir / "chapters",
                initial_count=10,
                new_chaps_count=5,
                initial_snapshot=snap,
                story_dir=s_dir
            )
            return p, r
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(worker_task, i) for i in range(1, 5)]
            for f in futures:
                passed, reason = f.result()
                assert passed is True, f"Thread failed: {reason}"
                
        print("✅ PASS: 4 workers chạy song song đồng thời hoàn toàn độc lập và chính xác 100%!")

if __name__ == "__main__":
    test_scenario_1_success()
    test_scenario_2_file_deleted()
    test_scenario_3_file_modified()
    test_scenario_4_multithreaded()
    print("\n🎉 TOÀN BỘ 4 TEST CASES ĐỀU ĐẠT CHUẨN XUẤT SẮC!")
