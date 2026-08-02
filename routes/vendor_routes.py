from flask import jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from . import main
from ..crud import vendor_crud
from ..crud import vendor_analytics_crud
import os


# ============================================================
# VENDOR CRUD ENDPOINTS
# ============================================================

@main.route('/vendors/list', methods=['GET'])
@jwt_required()
def get_vendors():
    """Get all vendors for the company"""
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    vendors = vendor_crud.get_all_vendors(company_id, user_role)
    return jsonify(vendors), 200


@main.route('/vendors/<string:id>', methods=['GET'])
@jwt_required()
def get_vendor(id):
    """Get a single vendor by ID"""
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    vendor = vendor_crud.get_vendor_by_id(id, company_id, user_role)
    if vendor:
        return jsonify(vendor), 200
    return jsonify({'message': 'Vendor not found'}), 404


@main.route('/vendors/add', methods=['POST'])
@jwt_required()
def add_new_vendor():
    """
    Create a new vendor — provisions a full independent company.
    Returns the vendor record, vendor_company_id, and auto-generated login credentials.
    """
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    
    # Accept both JSON (application/json) and multipart form-data (for file uploads)
    data = request.get_json(silent=True) or request.form.to_dict()
    files = request.files
    
    try:
        result = vendor_crud.add_vendor(data, files, company_id, user_role, current_user_id, ip_address, user_agent)
        return jsonify({
            'message': 'Vendor added successfully. A new company has been provisioned for this vendor.',
            'id': str(result['vendor'].id),
            'vendor_company_id': result['vendor_company_id'],
            'credentials': result['credentials']
        }), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to add vendor', 'message': str(e)}), 500


@main.route('/vendors/update/<string:id>', methods=['PUT'])
@jwt_required()
def update_existing_vendor(id):
    """Update an existing vendor"""
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    
    # Accept both JSON (application/json) and multipart form-data (for file uploads)
    data = request.get_json(silent=True) or request.form.to_dict()
    files = request.files
    
    try:
        updated_vendor = vendor_crud.update_vendor(id, data, files, company_id, user_role, current_user_id, ip_address, user_agent)
        if updated_vendor:
            return jsonify({'message': 'Vendor updated successfully'}), 200
        return jsonify({'message': 'Vendor not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Failed to update vendor', 'message': str(e)}), 500


@main.route('/vendors/delete/<string:id>', methods=['DELETE'])
@jwt_required()
def delete_existing_vendor(id):
    """Delete a vendor"""
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    
    if vendor_crud.delete_vendor(id, company_id, user_role, current_user_id, ip_address, user_agent):
        return jsonify({'message': 'Vendor deleted successfully'}), 200
    return jsonify({'message': 'Vendor not found'}), 404


@main.route('/vendors/file/<string:vendor_id>/<string:file_type>', methods=['GET'])
@jwt_required()
def get_vendor_file(vendor_id, file_type):
    """Get a vendor's file (picture, cnic_front, cnic_back, agreement)"""
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    
    vendor = vendor_crud.get_vendor_by_id(vendor_id, company_id, user_role)
    if not vendor:
        return jsonify({'message': 'Vendor not found'}), 404
    
    file_path = None
    if file_type == 'picture':
        file_path = vendor.get('picture')
    elif file_type == 'cnic_front':
        file_path = vendor.get('cnic_front_image')
    elif file_type == 'cnic_back':
        file_path = vendor.get('cnic_back_image')
    elif file_type == 'agreement':
        file_path = vendor.get('agreement_document')
    
    if file_path and os.path.exists(file_path):
        return send_file(file_path)
    return jsonify({'message': 'File not found'}), 404


# ============================================================
# VENDOR ANALYTICS ENDPOINTS (Parent Company → Vendor Stats)
# ============================================================

@main.route('/vendors/summary', methods=['GET'])
@jwt_required()
def get_vendors_summary():
    """
    Get all vendors with summary stats for the parent company.
    Returns vendor list with key KPIs (customers, revenue, invoices, complaints) per vendor.
    """
    claims = get_jwt()
    company_id = claims['company_id']
    
    try:
        data = vendor_analytics_crud.get_all_vendors_summary(company_id)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch vendor summary', 'message': str(e)}), 500


@main.route('/vendors/<string:vendor_company_id>/stats', methods=['GET'])
@jwt_required()
def get_vendor_stats(vendor_company_id):
    """
    Get detailed aggregated stats for a specific vendor company.
    Includes: customer metrics, revenue, invoices, expenses, profit, complaints, employees.
    """
    claims = get_jwt()
    company_id = claims['company_id']
    
    try:
        data = vendor_analytics_crud.get_vendor_overview(company_id, vendor_company_id)
        return jsonify(data), 200
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    except Exception as e:
        return jsonify({'error': 'Failed to fetch vendor stats', 'message': str(e)}), 500


@main.route('/vendors/<string:vendor_company_id>/revenue-trend', methods=['GET'])
@jwt_required()
def get_vendor_revenue_trend(vendor_company_id):
    """
    Get monthly revenue/expense/profit trend for a vendor company.
    Query params: months (default 6)
    """
    claims = get_jwt()
    company_id = claims['company_id']
    months = request.args.get('months', 6, type=int)
    
    try:
        data = vendor_analytics_crud.get_vendor_revenue_trend(company_id, vendor_company_id, months)
        return jsonify(data), 200
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    except Exception as e:
        return jsonify({'error': 'Failed to fetch vendor revenue trend', 'message': str(e)}), 500


@main.route('/vendors/<string:vendor_company_id>/customer-growth', methods=['GET'])
@jwt_required()
def get_vendor_customer_growth(vendor_company_id):
    """
    Get monthly customer growth trend for a vendor company.
    Query params: months (default 6)
    """
    claims = get_jwt()
    company_id = claims['company_id']
    months = request.args.get('months', 6, type=int)
    
    try:
        data = vendor_analytics_crud.get_vendor_customer_growth(company_id, vendor_company_id, months)
        return jsonify(data), 200
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    except Exception as e:
        return jsonify({'error': 'Failed to fetch vendor customer growth', 'message': str(e)}), 500


# ============================================================
# VENDOR ACCOUNT MANAGEMENT ENDPOINTS
# ============================================================

@main.route('/vendors/<string:vendor_id>/reset-credentials', methods=['POST'])
@jwt_required()
def reset_vendor_credentials(vendor_id):
    """
    Reset the login credentials for a vendor's portal account.
    Only the parent company (company_owner) can call this.
    Returns the new username and password ONCE — parent must share with vendor.
    """
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')

    try:
        result = vendor_crud.reset_vendor_credentials(
            vendor_id, company_id, user_role,
            current_user_id, ip_address, user_agent
        )
        return jsonify({
            'message': 'Vendor credentials reset successfully',
            'username': result['username'],
            'new_password': result['new_password'],
            'vendor_name': result['vendor_name'],
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to reset vendor credentials', 'message': str(e)}), 500


@main.route('/vendors/<string:vendor_id>/account-info', methods=['GET'])
@jwt_required()
def get_vendor_account_info(vendor_id):
    """
    Get the vendor portal account details (username, active status).
    Used by the Vendor Dashboard Account Management panel.
    """
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']

    result = vendor_crud.get_vendor_account_info(vendor_id, company_id, user_role)
    if result:
        return jsonify(result), 200
    return jsonify({'error': 'Vendor account not found'}), 404
