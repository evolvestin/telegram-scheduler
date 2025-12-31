import os
import time
import json
import logging
import subprocess
import glob
import zipfile
from django.conf import settings
from oauth2client.service_account import ServiceAccountCredentials
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

class BackupManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._cached_file_ids = {}
            self._drive = None
            self._initialized = True
    
    def perform_backup(self):
        drive = self._get_drive_service()
        if not drive:
            return

        data_dir = settings.DATA_DIR
        
        # 1. Backup Database (Dump -> Upload -> Delete)
        # Using a FIXED name for the remote file to allow "Update Only" logic
        remote_db_name = "telegram_scheduler_db.dump" 
        local_db_dump = os.path.join(data_dir, f"temp_db_{int(time.time())}.dump")
        
        self._dump_database(local_db_dump)
        if os.path.exists(local_db_dump):
            self._update_existing_file_only(drive, local_db_dump, remote_db_name)
            os.remove(local_db_dump)

        # 2. Backup Sessions (Zip -> Upload -> Delete)
        # Requirement: Archive sessions and upload as a single file
        remote_archive_name = "telegram_sessions.zip"
        local_archive_path = os.path.join(data_dir, f"temp_sessions_{int(time.time())}.zip")
        
        session_files = glob.glob(os.path.join(data_dir, "*.session"))
        if session_files:
            try:
                with zipfile.ZipFile(local_archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file in session_files:
                        zipf.write(file, os.path.basename(file))
                
                logging.info(f"Zipped {len(session_files)} sessions into {local_archive_path}")
                self._update_existing_file_only(drive, local_archive_path, remote_archive_name)
            except Exception as e:
                logging.error(f"Failed to zip sessions: {e}")
            finally:
                if os.path.exists(local_archive_path):
                    os.remove(local_archive_path)
        else:
            logging.info("No session files found to backup.")

    def _dump_database(self, path):
        try:
            db_conf = settings.DATABASES['default']
            env = os.environ.copy()
            env['PGPASSWORD'] = db_conf['PASSWORD']
            command = [
                'pg_dump', '-h', db_conf['HOST'], '-p', str(db_conf['PORT']),
                '-U', db_conf['USER'], '-F', 'c', '-b', '-v', '-f', path, db_conf['NAME']
            ]
            subprocess.run(command, env=env, check=True)
        except Exception as e:
            logging.error(f"DB Dump failed: {e}")

    def _get_drive_service(self):
        if not getattr(settings, 'GOOGLE_DRIVE_CREDENTIALS_JSON', None):
            logging.error('Google Drive credentials are not configured.')
            return None
        try:
            if self._drive:
                return self._drive
            creds_dict = json.loads(settings.GOOGLE_DRIVE_CREDENTIALS_JSON)
            gauth = GoogleAuth()
            scope = ['https://www.googleapis.com/auth/drive']
            gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            self._drive = GoogleDrive(gauth)
            return self._drive
        except Exception as e:
            logging.error(f'Failed to authenticate with Google Drive: {e}')
            return None

    def _get_file_id(self, drive, filename):
        if filename in self._cached_file_ids:
            return self._cached_file_ids[filename]
        
        query = (
            f"'{settings.GOOGLE_DRIVE_FOLDER_ID}' "
            f"in parents and title = '{filename}' and trashed = false"
        )
        file_list = drive.ListFile({'q': query}).GetList()
        if file_list:
            file_id = file_list[0]['id']
            self._cached_file_ids[filename] = file_id
            return file_id
        return None

    def _update_existing_file_only(self, drive, local_path, remote_name):
        """
        Updates content of an existing file. 
        Does NOT create new files (per strict requirements).
        """
        try:
            file_id = self._get_file_id(drive, remote_name)
            
            if file_id:
                g_file = drive.CreateFile({'id': file_id})
                g_file.SetContentFile(local_path)
                g_file.Upload()
                logging.info(f'Successfully updated existing file: {remote_name}')
            else:
                logging.warning(
                    f"SKIPPED BACKUP: File '{remote_name}' not found on Drive. "
                    "Creation is forbidden. Please create an empty file with this name manually."
                )
            
        except Exception as e:
            logging.error(f'An error occurred during update of {remote_name}: {e}')
            if remote_name in self._cached_file_ids:
                del self._cached_file_ids[remote_name]
    
    def schedule_backup(self):
        from app.tasks import perform_backup_task
        perform_backup_task.delay()
        logging.info("Backup task scheduled via Celery.")
    
    def perform_restore(self):
        drive = self._get_drive_service()
        if not drive:
            raise Exception("Google Drive service not available.")

        data_dir = settings.DATA_DIR
        remote_db_name = "telegram_scheduler_db.dump"
        remote_archive_name = "telegram_sessions.zip"
        
        local_db_dump = os.path.join(data_dir, f"restore_db_{int(time.time())}.dump")
        local_archive_path = os.path.join(data_dir, f"restore_sessions_{int(time.time())}.zip")

        try:
            logging.info("Downloading database dump...")
            if self._download_file(drive, remote_db_name, local_db_dump):
                self._restore_database(local_db_dump)
            else:
                logging.error(f"Remote file {remote_db_name} not found.")

            logging.info("Downloading sessions archive...")
            if self._download_file(drive, remote_archive_name, local_archive_path):
                self._restore_sessions(local_archive_path, data_dir)
            else:
                logging.error(f"Remote file {remote_archive_name} not found.")

        finally:
            if os.path.exists(local_db_dump):
                os.remove(local_db_dump)
            if os.path.exists(local_archive_path):
                os.remove(local_archive_path)

    def _download_file(self, drive, filename, target_path):
        file_id = self._get_file_id(drive, filename)
        if not file_id:
            return False
        
        g_file = drive.CreateFile({'id': file_id})
        g_file.GetContentFile(target_path)
        return True

    def _restore_database(self, path):
        try:
            db_conf = settings.DATABASES['default']
            env = os.environ.copy()
            env['PGPASSWORD'] = db_conf['PASSWORD']
            
            # -c: Clean (drop) database objects before creating them
            command = [
                'pg_restore', '-h', db_conf['HOST'], '-p', str(db_conf['PORT']),
                '-U', db_conf['USER'], '-d', db_conf['NAME'],
                '-c', '-v', '--no-owner', '--no-privileges', path
            ]
            logging.info("Running pg_restore...")
            subprocess.run(command, env=env, check=True)
            logging.info("Database restoration completed.")
        except subprocess.CalledProcessError as e:
            logging.error(f"pg_restore failed: {e}")
            raise e

    def _restore_sessions(self, zip_path, target_dir):
        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                zipf.extractall(target_dir)
            logging.info(f"Sessions extracted to {target_dir}")
        except Exception as e:
            logging.error(f"Failed to extract sessions: {e}")
            raise e