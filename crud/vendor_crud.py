from app import db
from app.models import Vendor, Company, User
from app.utils.logging_utils import log_action
import uuid
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from werkzeug.security import generate_password_hash
import logging
import os
import secrets
import string
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'vendors')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file, vendor_id, file_type):
    """Save uploaded file and return the path"""
    if file and allowed_file(file.filename):
        # Create directory if it doesn't exist
        vendor_folder = os.path.join(UPLOAD_FOLDER, str(vendor_id))
        os.makedirs(vendor_folder, exist_ok=True)
        
        # Generate unique filename
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{file_type}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(vendor_folder, filename)
        file.save(filepath)
        return filepath
    return None


def get_all_vendors(company_id, user_role):
    """Get all vendors for a company with vendor_company_id"""
    try:
        if user_role == 'super_admin':
            vendors = Vendor.query.order_by(Vendor.created_at.desc()).all()
        elif user_role == 'auditor':
            vendors = Vendor.query.filter_by(is_active=True, company_id=company_id).order_by(Vendor.created_at.desc()).all()
        else:
            vendors = Vendor.query.filter_by(company_id=company_id).order_by(Vendor.created_at.desc()).all()
        
        return [{
            'id': str(v.id),
            'name': v.name,
            'phone': v.phone,
            'email': v.email,
            'cnic': v.cnic,
            'picture': v.picture,
            'cnic_front_image': v.cnic_front_image,
            'cnic_back_image': v.cnic_back_image,
            'agreement_document': v.agreement_document,
            'vendor_company_id': str(v.vendor_company_id) if v.vendor_company_id else None,
            'is_provisioned': v.vendor_company_id is not None,
            'is_active': v.is_active,
            'created_at': v.created_at.isoformat() if v.created_at else None,
            'updated_at': v.updated_at.isoformat() if v.updated_at else None,
        } for v in vendors]
    except Exception as e:
        logger.error(f"Error getting vendors: {str(e)}")
        return []


def get_vendor_by_id(vendor_id, company_id, user_role):
    """Get a single vendor by ID"""
    try:
        if user_role == 'super_admin':
            vendor = Vendor.query.filter_by(id=vendor_id).first()
        else:
            vendor = Vendor.query.filter_by(id=vendor_id, company_id=company_id).first()
        
        if not vendor:
            return None

        vendor_company = Company.query.get(vendor.vendor_company_id) if vendor.vendor_company_id else None
        logo_url = None
        if vendor_company and vendor_company.logo:
            logo_url = f"/public/company/{vendor_company.id}/logo"
        elif vendor.picture:
            logo_url = f"/vendors/file/{vendor.id}/picture"

        return {
            'id': str(vendor.id),
            'name': vendor.name,
            'phone': vendor.phone,
            'email': vendor.email,
            'cnic': vendor.cnic,
            'picture': vendor.picture,
            'logo_url': logo_url,
            'cnic_front_image': vendor.cnic_front_image,
            'cnic_back_image': vendor.cnic_back_image,
            'agreement_document': vendor.agreement_document,
            'vendor_company_id': str(vendor.vendor_company_id) if vendor.vendor_company_id else None,
            'is_provisioned': vendor.vendor_company_id is not None,
            'is_active': vendor.is_active,
            'created_at': vendor.created_at.isoformat() if vendor.created_at else None,
            'updated_at': vendor.updated_at.isoformat() if vendor.updated_at else None,
        }
    except Exception as e:
        logger.error(f"Error getting vendor: {str(e)}")
        return None


def add_vendor(data, files, company_id, user_role, current_user_id, ip_address, user_agent):
    """
    Add a new vendor — provisions a full independent company.
    
    This creates:
    1. A new Company (company_type='vendor', parent_company_id=company_id)
    2. A default company_owner User for the vendor company
    3. A Vendor relationship record linking parent -> vendor company
    
    Returns dict with vendor record, vendor_company_id, and generated credentials.
    """
    try:
        # 1. Validate: Check if CNIC already exists
        existing = Vendor.query.filter_by(cnic=data.get('cnic')).first()
        if existing:
            raise ValueError("A vendor with this CNIC already exists")
        
        # Also check if CNIC exists in users table
        existing_user = User.query.filter_by(cnic=data.get('cnic')).first()
        if existing_user:
            raise ValueError("A user with this CNIC already exists in the system")
        
        # 2. Create the vendor's independent company
        vendor_company = Company(
            parent_company_id=uuid.UUID(company_id),
            company_type='vendor',
            name=data.get('name'),
            address=data.get('address', ''),
            contact_number=data.get('phone'),
            email=data.get('email'),
        )
        db.session.add(vendor_company)
        db.session.flush()  # Get vendor_company.id
        
        # 3. Generate credentials for the vendor company owner
        # Username: vendor_ + last 5 digits of CNIC
        cnic_val = data.get('cnic', '00000')
        phone_val = data.get('phone', '0000')
        username = f"vendor_{cnic_val[-5:]}"
        default_password = f"Vendor@{phone_val[-4:]}"
        
        # Ensure username uniqueness
        counter = 1
        original_username = username
        while User.query.filter_by(username=username).first():
            username = f"{original_username}_{counter}"
            counter += 1
        
        # Parse name into first/last
        name_parts = data.get('name', '').strip().split(' ', 1)
        first_name = name_parts[0] if name_parts else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        vendor_owner = User(
            company_id=vendor_company.id,
            username=username,
            password=generate_password_hash(default_password),
            email=data.get('email', f"{username}@vendor.local"),
            role='company_owner',
            first_name=first_name,
            last_name=last_name,
            contact_number=data.get('phone'),
            cnic=data.get('cnic'),
            is_active=True,
        )
        db.session.add(vendor_owner)
        db.session.flush()
        
        # 4. Create the vendor relationship record
        new_vendor = Vendor(
            company_id=uuid.UUID(company_id),
            vendor_company_id=vendor_company.id,
            name=data.get('name'),
            phone=data.get('phone'),
            email=data.get('email'),
            cnic=data.get('cnic'),
        )
        db.session.add(new_vendor)
        db.session.flush()
        
        # 5. Handle file uploads
        if files:
            if 'picture' in files:
                new_vendor.picture = save_file(files['picture'], new_vendor.id, 'picture')
            if 'cnic_front_image' in files:
                new_vendor.cnic_front_image = save_file(files['cnic_front_image'], new_vendor.id, 'cnic_front')
            if 'cnic_back_image' in files:
                new_vendor.cnic_back_image = save_file(files['cnic_back_image'], new_vendor.id, 'cnic_back')
            if 'agreement_document' in files:
                new_vendor.agreement_document = save_file(files['agreement_document'], new_vendor.id, 'agreement')
        
        db.session.commit()

        # 6. Audit log
        log_action(
            current_user_id,
            'CREATE',
            'vendors',
            new_vendor.id,
            None,
            {
                'name': data.get('name'),
                'cnic': data.get('cnic'),
                'vendor_company_id': str(vendor_company.id),
                'vendor_owner_username': username
            },
            ip_address,
            user_agent,
            company_id
        )

        return {
            'vendor': new_vendor,
            'vendor_company_id': str(vendor_company.id),
            'credentials': {
                'username': username,
                'password': default_password,
                'email': data.get('email', f"{username}@vendor.local")
            }
        }
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"Integrity error adding vendor: {str(e)}")
        raise ValueError("A vendor with this CNIC already exists")
    except ValueError:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding vendor: {str(e)}")
        raise


def update_vendor(vendor_id, data, files, company_id, user_role, current_user_id, ip_address, user_agent):
    """Update an existing vendor's metadata (does NOT modify the vendor company)"""
    try:
        if user_role == 'super_admin':
            vendor = Vendor.query.filter_by(id=vendor_id).first()
        else:
            vendor = Vendor.query.filter_by(id=vendor_id, company_id=company_id).first()
        
        if not vendor:
            return None

        old_values = {
            'name': vendor.name,
            'phone': vendor.phone,
            'email': vendor.email,
            'cnic': vendor.cnic,
            'is_active': vendor.is_active
        }

        # Update basic fields
        if 'name' in data:
            vendor.name = data['name']
        if 'phone' in data:
            vendor.phone = data['phone']
        if 'email' in data:
            vendor.email = data['email']
        if 'cnic' in data:
            vendor.cnic = data['cnic']
        if 'is_active' in data:
            is_act = data['is_active'] in ['true', 'True', True, '1', 1]
            vendor.is_active = is_act
            # Sync deactivation to vendor company and its users
            if vendor.vendor_company_id:
                vendor_comp = Company.query.get(vendor.vendor_company_id)
                if vendor_comp:
                    vendor_comp.is_active = is_act
                    User.query.filter_by(company_id=vendor.vendor_company_id).update({'is_active': is_act})
        
        # Handle file uploads
        if files:
            if 'picture' in files:
                vendor.picture = save_file(files['picture'], vendor.id, 'picture')
            if 'cnic_front_image' in files:
                vendor.cnic_front_image = save_file(files['cnic_front_image'], vendor.id, 'cnic_front')
            if 'cnic_back_image' in files:
                vendor.cnic_back_image = save_file(files['cnic_back_image'], vendor.id, 'cnic_back')
            if 'agreement_document' in files:
                vendor.agreement_document = save_file(files['agreement_document'], vendor.id, 'agreement')
        
        db.session.commit()

        log_action(
            current_user_id,
            'UPDATE',
            'vendors',
            vendor.id,
            old_values,
            data,
            ip_address,
            user_agent,
            company_id
        )

        return vendor
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating vendor: {str(e)}")
        raise


def delete_vendor(vendor_id, company_id, user_role, current_user_id, ip_address, user_agent):
    """Delete a vendor (soft-delete the relationship, does NOT delete the vendor company)"""
    try:
        if user_role == 'super_admin':
            vendor = Vendor.query.filter_by(id=vendor_id).first()
        else:
            vendor = Vendor.query.filter_by(id=vendor_id, company_id=company_id).first()
        
        if not vendor:
            return False

        old_values = {
            'name': vendor.name,
            'phone': vendor.phone,
            'email': vendor.email,
            'cnic': vendor.cnic,
            'is_active': vendor.is_active
        }

        db.session.delete(vendor)
        db.session.commit()

        log_action(
            current_user_id,
            'DELETE',
            'vendors',
            vendor_id,
            old_values,
            None,
            ip_address,
            user_agent,
            company_id
        )

        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting vendor: {str(e)}")
        return False


def _generate_secure_password(length=12):
    """Generate a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    # Ensure at least one of each required character class
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%"),
    ]
    password += [secrets.choice(alphabet) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)


def reset_vendor_credentials(vendor_id, company_id, user_role, current_user_id, ip_address, user_agent):
    """
    Reset the login credentials for a vendor's company owner account.
    Only the parent company can do this.
    Returns: { username, new_password } — shown ONCE to the parent company.
    """
    try:
        # Find the vendor relationship
        if user_role == 'super_admin':
            vendor = Vendor.query.filter_by(id=vendor_id).first()
        else:
            vendor = Vendor.query.filter_by(id=vendor_id, company_id=company_id).first()

        if not vendor:
            raise ValueError("Vendor not found or access denied")

        if not vendor.vendor_company_id:
            raise ValueError("This vendor has no provisioned company account")

        # Find the company_owner user of the vendor's company
        vendor_owner = User.query.filter_by(
            company_id=vendor.vendor_company_id,
            role='company_owner'
        ).first()

        if not vendor_owner:
            raise ValueError("No owner account found for this vendor company")

        # Generate new secure password
        new_password = _generate_secure_password(12)
        vendor_owner.password = generate_password_hash(new_password)
        db.session.commit()

        log_action(
            current_user_id,
            'RESET_CREDENTIALS',
            'vendors',
            vendor.id,
            {'action': 'credential_reset', 'vendor_name': vendor.name},
            {'username': vendor_owner.username},
            ip_address,
            user_agent,
            company_id
        )

        return {
            'username': vendor_owner.username,
            'new_password': new_password,
            'vendor_name': vendor.name,
        }
    except ValueError:
        raise
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error resetting vendor credentials: {str(e)}")
        raise


def get_vendor_account_info(vendor_id, company_id, user_role):
    """
    Get the vendor's portal account information (username, status).
    Used by the dashboard Account Management panel.
    """
    try:
        if user_role == 'super_admin':
            vendor = Vendor.query.filter_by(id=vendor_id).first()
        else:
            vendor = Vendor.query.filter_by(id=vendor_id, company_id=company_id).first()

        if not vendor or not vendor.vendor_company_id:
            return None

        vendor_owner = User.query.filter_by(
            company_id=vendor.vendor_company_id,
            role='company_owner'
        ).first()

        if not vendor_owner:
            return None

        return {
            'username': vendor_owner.username,
            'is_active': vendor_owner.is_active,
            'email': vendor_owner.email,
            'last_login': vendor_owner.last_login.isoformat() if hasattr(vendor_owner, 'last_login') and vendor_owner.last_login else None,
            'vendor_company_id': str(vendor.vendor_company_id),
        }
    except Exception as e:
        logger.error(f"Error fetching vendor account info: {str(e)}")
        return None
