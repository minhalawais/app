from app import db
from app.models import Company
from app.utils.logging_utils import log_action
import os
import uuid
import logging
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

# Base upload folder for company branding assets (logos, favicons)
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'companies')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'svg', 'gif', 'webp', 'ico'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_company_file(file, company_id, file_type):
    """Save company logo or favicon to disk and return relative path"""
    if file and allowed_file(file.filename):
        company_folder = os.path.join(UPLOAD_FOLDER, str(company_id))
        os.makedirs(company_folder, exist_ok=True)
        
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{file_type}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(company_folder, filename)
        file.save(filepath)
        return filepath
    return None


def get_company_profile(company_id):
    """
    Get full company profile & branding details.
    """
    try:
        company = Company.query.get(company_id)
        if not company:
            return None
        
        return {
            'id': str(company.id),
            'name': company.name,
            'address': company.address or '',
            'contact_number': company.contact_number or '',
            'email': company.email or '',
            'website': company.website or '',
            'tagline': company.tagline or '',
            'tax_number': company.tax_number or '',
            'currency_symbol': company.currency_symbol or 'Rs.',
            'invoice_footer_notes': company.invoice_footer_notes or '',
            'logo': company.logo or '',
            'favicon': company.favicon or '',
            'logo_url': f"/public/company/{company.id}/logo" if company.logo else None,
            'favicon_url': f"/public/company/{company.id}/favicon" if company.favicon else None,
            'company_type': company.company_type,
            'is_active': company.is_active,
            'created_at': company.created_at.isoformat() if company.created_at else None,
        }
    except Exception as e:
        logger.error(f"Error getting company profile for company {company_id}: {str(e)}")
        raise


def update_company_profile(company_id, data, files, current_user_id, ip_address, user_agent, user_role):
    """
    Update company profile & upload new logo/favicon.
    Permission check: Only company_owner or super_admin.
    """
    if user_role not in ['company_owner', 'super_admin']:
        raise PermissionError("Access denied: only company owner or super admin can update company settings")
    
    try:
        company = Company.query.get(company_id)
        if not company:
            raise ValueError("Company not found")

        old_values = {
            'name': company.name,
            'address': company.address,
            'contact_number': company.contact_number,
            'email': company.email,
            'website': company.website,
            'tagline': company.tagline,
            'tax_number': company.tax_number,
            'currency_symbol': company.currency_symbol,
            'invoice_footer_notes': company.invoice_footer_notes,
        }

        # Update text fields
        if 'name' in data and data['name']:
            company.name = data['name'].strip()
        if 'address' in data:
            company.address = data['address'].strip() if data['address'] else ''
        if 'contact_number' in data:
            company.contact_number = data['contact_number'].strip() if data['contact_number'] else ''
        if 'email' in data:
            company.email = data['email'].strip() if data['email'] else ''
        if 'website' in data:
            company.website = data['website'].strip() if data['website'] else ''
        if 'tagline' in data:
            company.tagline = data['tagline'].strip() if data['tagline'] else ''
        if 'tax_number' in data:
            company.tax_number = data['tax_number'].strip() if data['tax_number'] else ''
        if 'currency_symbol' in data and data['currency_symbol']:
            company.currency_symbol = data['currency_symbol'].strip()
        if 'invoice_footer_notes' in data:
            company.invoice_footer_notes = data['invoice_footer_notes'].strip() if data['invoice_footer_notes'] else ''

        # Handle file uploads (logo & favicon)
        if files:
            if 'logo' in files and files['logo'].filename:
                saved_logo = save_company_file(files['logo'], company.id, 'logo')
                if saved_logo:
                    company.logo = saved_logo

            if 'favicon' in files and files['favicon'].filename:
                saved_favicon = save_company_file(files['favicon'], company.id, 'favicon')
                if saved_favicon:
                    company.favicon = saved_favicon

        db.session.commit()

        log_action(
            current_user_id,
            'UPDATE_COMPANY_PROFILE',
            'companies',
            company.id,
            old_values,
            data,
            ip_address,
            user_agent,
            company_id
        )

        return get_company_profile(company_id)
    except ValueError:
        db.session.rollback()
        raise
    except PermissionError:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating company profile: {str(e)}")
        raise


def get_company_file_path(company_id, file_type):
    """
    Get file system path for logo or favicon.
    """
    try:
        company = Company.query.get(company_id)
        if not company:
            return None
        
        file_path = company.logo if file_type == 'logo' else (company.favicon if file_type == 'favicon' else None)
        if file_path and os.path.exists(file_path):
            return file_path
        return None
    except Exception as e:
        logger.error(f"Error getting company file: {str(e)}")
        return None
