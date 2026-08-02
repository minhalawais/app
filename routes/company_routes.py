from flask import jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from . import main
from ..crud import company_crud
import os


@main.route('/company/profile', methods=['GET'])
@jwt_required()
def get_company_profile():
    """
    Get current user's company profile & branding.
    """
    claims = get_jwt()
    company_id = claims.get('company_id')
    if not company_id:
        return jsonify({'error': 'No company associated with user'}), 400

    profile = company_crud.get_company_profile(company_id)
    if profile:
        return jsonify(profile), 200
    return jsonify({'error': 'Company profile not found'}), 404


@main.route('/company/profile', methods=['PUT'])
@jwt_required()
def update_company_profile():
    """
    Update current user's company profile & branding (logo, favicon, contact details).
    Permission: company_owner or super_admin only.
    """
    claims = get_jwt()
    company_id = claims.get('company_id')
    user_role = claims.get('role')
    current_user_id = get_jwt_identity()
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')

    if not company_id:
        return jsonify({'error': 'No company associated with user'}), 400

    # Accept both JSON and multipart form-data (for logo/favicon file uploads)
    data = request.get_json(silent=True) or request.form.to_dict()
    files = request.files

    try:
        updated_profile = company_crud.update_company_profile(
            company_id, data, files,
            current_user_id, ip_address, user_agent, user_role
        )
        return jsonify({
            'message': 'Company profile updated successfully',
            'company': updated_profile
        }), 200
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to update company profile', 'message': str(e)}), 500


@main.route('/public/company/<string:company_id>/profile', methods=['GET'])
def get_public_company_profile(company_id):
    """
    Public endpoint for public invoice pages and customer portal.
    Does not require JWT authentication.
    """
    profile = company_crud.get_company_profile(company_id)
    if profile:
        # Exclude internal tracking data
        return jsonify({
            'id': profile['id'],
            'name': profile['name'],
            'address': profile['address'],
            'contact_number': profile['contact_number'],
            'email': profile['email'],
            'website': profile['website'],
            'tagline': profile['tagline'],
            'tax_number': profile['tax_number'],
            'currency_symbol': profile['currency_symbol'],
            'invoice_footer_notes': profile['invoice_footer_notes'],
            'logo_url': profile['logo_url'],
            'favicon_url': profile['favicon_url'],
        }), 200
    return jsonify({'error': 'Company not found'}), 404


@main.route('/public/company/<string:company_id>/logo', methods=['GET'])
def get_public_company_logo(company_id):
    """
    Serve raw logo image file publicly (for public invoices, customer portal, login screen).
    Does not require JWT authentication.
    """
    file_path = company_crud.get_company_file_path(company_id, 'logo')
    if file_path and os.path.exists(file_path):
        return send_file(file_path)
    return jsonify({'error': 'Logo not found'}), 404


@main.route('/public/company/<string:company_id>/favicon', methods=['GET'])
def get_public_company_favicon(company_id):
    """
    Serve raw favicon image file publicly.
    Does not require JWT authentication.
    """
    file_path = company_crud.get_company_file_path(company_id, 'favicon')
    if file_path and os.path.exists(file_path):
        return send_file(file_path)
    return jsonify({'error': 'Favicon not found'}), 404
