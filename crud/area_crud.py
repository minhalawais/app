from app import db
from app.models import Area
from app.utils.logging_utils import log_action
import uuid
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging

logger = logging.getLogger(__name__)

def get_all_areas(company_id, user_role):
    try:
        if user_role == 'super_admin':
            areas = Area.query.order_by(Area.created_at.desc()).all()
        elif user_role == 'auditor':
            areas = Area.query.filter_by(is_active=True, company_id=company_id).order_by(Area.created_at.desc()).all()
        else:
            areas = Area.query.filter_by(company_id=company_id).order_by(Area.created_at.desc()).all()
        
        return [{
            'id': str(area.id),
            'name': area.name,
            'description': area.description or '',
            'is_active': area.is_active,
            'sub_zones_count': area.sub_zones.count() if hasattr(area, 'sub_zones') else 0
        } for area in areas]
    except Exception as e:
        logger.error(f"Error getting areas: {str(e)}")
        raise

def add_area(data, user_role, current_user_id, ip_address, user_agent):
    try:
        company_id_val = uuid.UUID(data['company_id'])
        new_area = Area(
            company_id=company_id_val,
            name=data['name'],
            description=data.get('description', '')
        )
        db.session.add(new_area)
        db.session.commit()

        log_action(
            current_user_id,
            'CREATE',
            'areas',
            new_area.id,
            None,
            data,
            ip_address,
            user_agent,
            company_id_val
        )

        return new_area
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding area: {str(e)}")
        raise

def update_area(id, data, company_id, user_role, current_user_id, ip_address, user_agent):
    try:
        if user_role == 'super_admin':
            area = Area.query.filter_by(id=id).first()
        elif user_role == 'auditor':
            area = Area.query.filter_by(id=id, is_active=True, company_id=company_id).first()
        else:
            area = Area.query.filter_by(id=id, company_id=company_id).first()
        
        if not area:
            return None

        old_values = {
            'name': area.name,
            'description': area.description,
            'is_active': area.is_active
        }

        area.name = data.get('name', area.name)
        area.description = data.get('description', area.description)
        if 'is_active' in data:
            area.is_active = data['is_active']
        db.session.commit()

        log_action(
            current_user_id,
            'UPDATE',
            'areas',
            area.id,
            old_values,
            data,
            ip_address,
            user_agent,
            uuid.UUID(company_id) if isinstance(company_id, str) else company_id
        )

        return area
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating area: {str(e)}")
        raise

def delete_area(id, company_id, user_role, current_user_id, ip_address, user_agent):
    try:
        if user_role == 'super_admin':
            area = Area.query.filter_by(id=id).first()
        elif user_role == 'auditor':
            area = Area.query.filter_by(id=id, is_active=True, company_id=company_id).first()
        else:
            area = Area.query.filter_by(id=id, company_id=company_id).first()
        
        if not area:
            return False

        old_values = {
            'name': area.name,
            'description': area.description,
            'is_active': area.is_active
        }

        db.session.delete(area)
        db.session.commit()

        log_action(
            current_user_id,
            'DELETE',
            'areas',
            area.id,
            old_values,
            None,
            ip_address,
            user_agent,
            uuid.UUID(company_id) if isinstance(company_id, str) else company_id
        )

        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting area: {str(e)}")
        raise
