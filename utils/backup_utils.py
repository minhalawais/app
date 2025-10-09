import os
import subprocess
import logging
import psycopg2
from datetime import datetime, timedelta
import shutil
from pathlib import Path
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PostgreSQLBackupManager:
    def __init__(self, app=None, database_url=None, backup_dir="backups"):
        self.app = app
        self.database_url = database_url or (app.config.get("SQLALCHEMY_DATABASE_URI") if app else None)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        
    def parse_database_url(self):
        """Parse database URL safely"""
        if not self.database_url:
            raise ValueError("No database URL provided")
            
        if self.database_url.startswith('postgresql://'):
            url = self.database_url.replace('postgresql://', '')
        elif self.database_url.startswith('postgres://'):
            url = self.database_url.replace('postgres://', '')
        else:
            raise ValueError("Invalid PostgreSQL database URL")
            
        # Handle credentials and host
        if '@' in url:
            creds, host_db = url.split('@', 1)
            if ':' in creds:
                user, password = creds.split(':', 1)
            else:
                user, password = creds, ''
        else:
            user, password, host_db = 'postgres', '', url
            
        # Handle host, port, and database
        if '/' in host_db:
            host_port, database = host_db.split('/', 1)
        else:
            host_port, database = host_db, 'postgres'
            
        if ':' in host_port:
            host, port = host_port.split(':', 1)
        else:
            host, port = host_port, '5432'
            
        # Remove query parameters from database name
        database = database.split('?')[0]
        
        return {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }

    def find_postgres_binary(self, binary_name):
        """Find PostgreSQL binaries with cross-platform support"""
        # Check if binary is in PATH
        binary = shutil.which(binary_name)
        if binary:
            return binary
            
        # Platform-specific common paths
        if sys.platform == "win32":
            # Windows paths
            possible_paths = [
                r"C:\Program Files\PostgreSQL\16\bin\{}.exe",
                r"C:\Program Files\PostgreSQL\15\bin\{}.exe",
                r"C:\Program Files\PostgreSQL\14\bin\{}.exe",
                r"C:\Program Files\PostgreSQL\13\bin\{}.exe",
                r"C:\Program Files\PostgreSQL\12\bin\{}.exe",
            ]
        else:
            # Linux paths (including Hostinger VPS)
            possible_paths = [
                "/usr/bin/{}",
                "/usr/local/bin/{}",
                "/usr/pgsql-16/bin/{}",
                "/usr/pgsql-15/bin/{}",
                "/usr/pgsql-14/bin/{}",
                "/opt/local/lib/postgresql16/bin/{}",
                "/opt/local/lib/postgresql15/bin/{}",
            ]
        
        for path_template in possible_paths:
            path = path_template.format(binary_name)
            if os.path.exists(path):
                return path
                
        # Fallback to just the binary name
        return binary_name

    def test_connection(self):
        """Test database connection"""
        try:
            db_config = self.parse_database_url()
            conn = psycopg2.connect(
                host=db_config['host'],
                port=db_config['port'],
                database=db_config['database'],
                user=db_config['user'],
                password=db_config['password']
            )
            conn.close()
            logger.info("Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            return False

    def create_backup(self, formats=['sql', 'custom']):
        """Create database backups in specified formats"""
        try:
            db_config = self.parse_database_url()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_files = []
            
            # Find pg_dump
            pg_dump_path = self.find_postgres_binary('pg_dump')
            logger.info(f"Using pg_dump from: {pg_dump_path}")
            
            # Set environment
            env = os.environ.copy()
            env['PGPASSWORD'] = db_config['password']
            
            for format_type in formats:
                if format_type == 'sql':
                    filename = f"{db_config['database']}_backup_{timestamp}.sql"
                    filepath = self.backup_dir / filename
                    cmd = [
                        pg_dump_path,
                        '-h', db_config['host'],
                        '-p', db_config['port'],
                        '-U', db_config['user'],
                        '-d', db_config['database'],
                        '-f', str(filepath),
                        '--verbose'
                    ]
                elif format_type == 'custom':
                    filename = f"{db_config['database']}_backup_{timestamp}.dump"
                    filepath = self.backup_dir / filename
                    cmd = [
                        pg_dump_path,
                        '-h', db_config['host'],
                        '-p', db_config['port'],
                        '-U', db_config['user'],
                        '-d', db_config['database'],
                        '-F', 'c',
                        '-f', str(filepath),
                        '--verbose'
                    ]
                else:
                    logger.warning(f"Unsupported format: {format_type}")
                    continue
                
                logger.info(f"Creating {format_type} backup: {filename}")
                result = subprocess.run(
                    cmd, 
                    env=env, 
                    capture_output=True, 
                    text=True,
                    timeout=3600  # 1 hour timeout
                )
                
                if result.returncode == 0:
                    backup_files.append(str(filepath))
                    logger.info(f"Successfully created {format_type} backup")
                else:
                    logger.error(f"Failed to create {format_type} backup: {result.stderr}")
                    
            return backup_files if backup_files else None
            
        except subprocess.TimeoutExpired:
            logger.error("Backup process timed out after 1 hour")
            return None
        except Exception as e:
            logger.error(f"Error creating backup: {str(e)}")
            return None

    def restore_backup(self, backup_path, format_type='auto'):
        """Restore database from backup"""
        try:
            db_config = self.parse_database_url()
            
            # Determine format
            if format_type == 'auto':
                if backup_path.endswith('.sql'):
                    format_type = 'sql'
                else:
                    format_type = 'custom'
            
            # Find appropriate binary
            if format_type == 'sql':
                binary_name = 'psql'
            else:
                binary_name = 'pg_restore'
                
            binary_path = self.find_postgres_binary(binary_name)
            logger.info(f"Using {binary_name} from: {binary_path}")
            
            # Set environment
            env = os.environ.copy()
            env['PGPASSWORD'] = db_config['password']
            
            if format_type == 'sql':
                cmd = [
                    binary_path,
                    '-h', db_config['host'],
                    '-p', db_config['port'],
                    '-U', db_config['user'],
                    '-d', db_config['database'],
                    '-f', backup_path
                ]
            else:
                cmd = [
                    binary_path,
                    '-h', db_config['host'],
                    '-p', db_config['port'],
                    '-U', db_config['user'],
                    '-d', db_config['database'],
                    '-c',  # Clean (drop) objects before recreating
                    '-v',  # Verbose
                    backup_path
                ]
            
            logger.info(f"Restoring database from: {backup_path}")
            result = subprocess.run(
                cmd, 
                env=env, 
                capture_output=True, 
                text=True,
                timeout=3600
            )
            
            if result.returncode == 0:
                logger.info("Database restored successfully")
                return True
            else:
                logger.error(f"Restore failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Restore process timed out after 1 hour")
            return False
        except Exception as e:
            logger.error(f"Error restoring database: {str(e)}")
            return False

    def cleanup_old_backups(self, keep_last=30):
        """Remove old backups, keeping only specified number"""
        try:
            # Get all backup files
            backup_files = list(self.backup_dir.glob('*_backup_*.*'))
            
            if len(backup_files) <= keep_last:
                logger.info("No old backups to clean up")
                return
                
            # Sort by modification time
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Remove old ones
            removed_count = 0
            for old_backup in backup_files[keep_last:]:
                try:
                    os.remove(old_backup)
                    removed_count += 1
                    logger.debug(f"Removed old backup: {old_backup.name}")
                except Exception as e:
                    logger.error(f"Error removing {old_backup.name}: {str(e)}")
                    
            logger.info(f"Cleaned up {removed_count} old backup(s)")
            
        except Exception as e:
            logger.error(f"Error during backup cleanup: {str(e)}")

    def list_backups(self):
        """List all available backups"""
        try:
            backup_files = list(self.backup_dir.glob('*_backup_*.*'))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            backups = []
            for backup in backup_files:
                stat = backup.stat()
                backups.append({
                    'name': backup.name,
                    'path': str(backup),
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime),
                    'size_mb': round(stat.st_size / (1024 * 1024), 2)
                })
                
            return backups
        except Exception as e:
            logger.error(f"Error listing backups: {str(e)}")
            return []