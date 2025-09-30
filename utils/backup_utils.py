import os
import subprocess
import logging
from datetime import datetime, timedelta
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_database_backup(app, backup_dir='backups'):
    """
    Create a database backup using pg_dump
    """
    try:
        # Create backup directory if it doesn't exist
        os.makedirs(backup_dir, exist_ok=True)
        
        # Get database connection details from app config
        database_url = app.config['SQLALCHEMY_DATABASE_URI']
        
        # Parse database URL
        # Format: postgresql://username:password@host:port/database
        if database_url.startswith('postgresql://'):
            db_parts = database_url.split('://')[1].split('@')
            user_pass = db_parts[0].split(':')
            host_port_db = db_parts[1].split('/')
            host_port = host_port_db[0].split(':')
            
            db_user = user_pass[0]
            db_password = user_pass[1] if len(user_pass) > 1 else ''
            db_host = host_port[0]
            db_port = host_port[1] if len(host_port) > 1 else '5432'
            db_name = host_port_db[1]
            
            # Create timestamp for backup filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"{db_name}_backup_{timestamp}.sql"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            # Set environment variable for password
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password
            
            # Build pg_dump command
            cmd = [
                'pg_dump',
                '-h', db_host,
                '-p', db_port,
                '-U', db_user,
                '-d', db_name,
                '-F', 'c',  # Custom format (compressed)
                '-f', backup_path
            ]
            
            # Execute backup command
            logger.info(f"Creating database backup: {backup_filename}")
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Backup created successfully: {backup_filename}")
                
                # Clean up old backups
                cleanup_old_backups(backup_dir, keep_last=30)
                
                return backup_path
            else:
                logger.error(f"Backup failed: {result.stderr}")
                return None
                
        else:
            logger.error("Unsupported database type. Only PostgreSQL is supported.")
            return None
            
    except Exception as e:
        logger.error(f"Error creating database backup: {str(e)}")
        return None

def cleanup_old_backups(backup_dir, keep_last=30):
    """
    Remove old backups, keeping only the specified number of most recent ones
    """
    try:
        backup_path = Path(backup_dir)
        
        # Get all backup files
        backup_files = list(backup_path.glob('*.sql'))
        
        if len(backup_files) <= keep_last:
            return
        
        # Sort files by modification time (newest first)
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Remove old backups
        for old_backup in backup_files[keep_last:]:
            try:
                os.remove(old_backup)
                logger.info(f"Removed old backup: {old_backup.name}")
            except Exception as e:
                logger.error(f"Error removing backup {old_backup.name}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error cleaning up old backups: {str(e)}")

def restore_database_backup(app, backup_path):
    """
    Restore database from backup
    """
    try:
        database_url = app.config['SQLALCHEMY_DATABASE_URI']
        
        if database_url.startswith('postgresql://'):
            db_parts = database_url.split('://')[1].split('@')
            user_pass = db_parts[0].split(':')
            host_port_db = db_parts[1].split('/')
            host_port = host_port_db[0].split(':')
            
            db_user = user_pass[0]
            db_password = user_pass[1] if len(user_pass) > 1 else ''
            db_host = host_port[0]
            db_port = host_port[1] if len(host_port) > 1 else '5432'
            db_name = host_port_db[1]
            
            # Set environment variable for password
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password
            
            # Build pg_restore command
            cmd = [
                'pg_restore',
                '-h', db_host,
                '-p', db_port,
                '-U', db_user,
                '-d', db_name,
                '-c',  # Clean (drop) database objects before recreating
                backup_path
            ]
            
            logger.info(f"Restoring database from backup: {backup_path}")
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("Database restored successfully")
                return True
            else:
                logger.error(f"Restore failed: {result.stderr}")
                return False
                
        else:
            logger.error("Unsupported database type. Only PostgreSQL is supported.")
            return False
            
    except Exception as e:
        logger.error(f"Error restoring database: {str(e)}")
        return False