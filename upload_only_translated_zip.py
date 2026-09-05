import sys
import os
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, r'f:\Workplace\outside\test-tmp\story-translator-cli')
from app.services.gdrive import GoogleDriveService
from googleapiclient.http import MediaFileUpload

STORY_DIR = Path(r'f:\Workplace\outside\test-tmp\storage\novel543\0912620228')
FILE_NAME = 'translated_chapters.zip'

def main():
    print(f"🚀 Initializing Google Drive Service...")
    gdrive = GoogleDriveService()
    service = gdrive.service

    repo_key, story_id, root_folder_id = gdrive.detect_repo_info(STORY_DIR)
    print(f"📁 Repo: {repo_key}, Story ID: {story_id}, Root Folder ID: {root_folder_id}")

    story_folder_id = gdrive.get_or_create_story_folder(root_folder_id, story_id)
    print(f"📁 Story Folder ID on Drive: {story_folder_id}")

    local_file = STORY_DIR / FILE_NAME
    if not local_file.exists():
        print(f"❌ File not found: {local_file}")
        sys.exit(1)

    print(f"📦 Local file size: {local_file.stat().st_size:,} bytes")
    
    # Check existing file on Drive
    query = f"'{story_folder_id}' in parents and name = '{FILE_NAME}' and trashed = false"
    res = service.files().list(
        q=query,
        fields='files(id, name, size)',
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()

    existing = res.get('files', [])
    media = MediaFileUpload(str(local_file), mimetype='application/zip', resumable=True)

    if existing:
        file_id = existing[0]['id']
        print(f"🔄 Updating existing file: {FILE_NAME} (ID: {file_id})...")
        updated = service.files().update(
            fileId=file_id,
            media_body=media,
            fields='id, name, webViewLink, size',
            supportsAllDrives=True
        ).execute()
        print(f"\n🎉 [THÀNH CÔNG] Đã ghi đè {FILE_NAME} lên Google Drive!")
        print(f"📄 File ID: {updated.get('id')}")
        print(f"📏 Size: {int(updated.get('size', 0)):,} bytes")
        print(f"🔗 Link: {updated.get('webViewLink')}")
    else:
        print(f"⬆️ Uploading new file: {FILE_NAME}...")
        meta = {
            'name': FILE_NAME,
            'parents': [story_folder_id]
        }
        created = service.files().create(
            body=meta,
            media_body=media,
            fields='id, name, webViewLink, size',
            supportsAllDrives=True
        ).execute()
        print(f"\n🎉 [THÀNH CÔNG] Đã tải mới {FILE_NAME} lên Google Drive!")
        print(f"📄 File ID: {created.get('id')}")
        print(f"📏 Size: {int(created.get('size', 0)):,} bytes")
        print(f"🔗 Link: {created.get('webViewLink')}")

if __name__ == '__main__':
    main()
