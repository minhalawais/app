from flask import jsonify, request, Blueprint
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from app.crud import invoice_crud
from app.models import Customer, ServicePlan
from datetime import datetime, timedelta
import logging
from . import main

logger = logging.getLogger(__name__)

@main.route('/invoices/list', methods=['GET'])
@jwt_required()
def get_invoices():
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    employee_id = claims['id']
    invoices = invoice_crud.get_all_invoices(company_id, user_role, employee_id)
    return jsonify(invoices), 200

@main.route('/invoices/add', methods=['POST'])
@jwt_required()
def add_new_invoice():
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Add company_id to the data
        data['company_id'] = company_id
        
        new_invoice = invoice_crud.add_invoice(
            data, 
            current_user_id, 
            user_role, 
            ip_address, 
            user_agent
        )
        return jsonify({
            'message': 'Invoice added successfully', 
            'id': str(new_invoice.id)
        }), 201
    except Exception as e:
        logger.error(f"Failed to add invoice: {str(e)}")
        return jsonify({
            'error': 'Failed to add invoice', 
            'message': str(e)
        }), 400
    
@main.route('/invoices/update/<string:id>', methods=['PUT'])
@jwt_required()
def update_existing_invoice(id):
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    data = request.json
    updated_invoice = invoice_crud.update_invoice(id, data, company_id, user_role, current_user_id, ip_address, user_agent)
    if updated_invoice:
        return jsonify({'message': 'Invoice updated successfully'}), 200
    return jsonify({'message': 'Invoice not found'}), 404

@main.route('/invoices/delete/<string:id>', methods=['DELETE'])
@jwt_required()
def delete_existing_invoice(id):
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    if invoice_crud.delete_invoice(id, company_id, user_role, current_user_id, ip_address, user_agent):
        return jsonify({'message': 'Invoice deleted successfully'}), 200
    return jsonify({'message': 'Invoice not found'}), 404

@main.route('/invoices/<string:id>', methods=['GET'])
@jwt_required()
def get_invoice(id):
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    
    try:
        invoice = invoice_crud.get_enhanced_invoice_by_id(id, company_id, user_role)
        if invoice:
            return jsonify(invoice), 200
        return jsonify({'message': 'Invoice not found'}), 404
    except Exception as e:
        logger.error(f"Error fetching invoice {id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch invoice'}), 500


@main.route('/invoices/generate-monthly', methods=['POST'])
@jwt_required()
def generate_monthly_invoices():
    """
    Manually trigger the generation of monthly invoices for customers with today's recharge date.
    This endpoint can be used for testing or manual invoice generation.
    """
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    
    if user_role not in ['super_admin', 'company_owner']:
        return jsonify({'error': 'Unauthorized access'}), 403
    
    try:
        # Call the CRUD function to generate monthly invoices
        result = invoice_crud.generate_monthly_invoices(
            company_id, 
            user_role, 
            current_user_id, 
            ip_address, 
            user_agent
        )
        
        return jsonify({
            'message': 'Invoice generation completed',
            'generated': result['generated'],
            'skipped': result['skipped'],
            'errors': result.get('errors', 0),
            'total_customers': result['total_customers']
        }), 200
        
    except invoice_crud.InvoiceError as e:
        logger.error(f"Invoice error: {str(e)}")
        return jsonify({'error': 'Failed to generate invoices', 'message': str(e)}), 400
    except Exception as e:
        logger.error(f"Error generating invoices: {str(e)}")
        return jsonify({'error': 'Failed to generate invoices', 'message': str(e)}), 500
    
@main.route('/invoices/bulk-monthly/preview', methods=['POST'])
@jwt_required()
def get_monthly_invoice_preview():
    """
    Get preview of customers eligible for monthly invoice generation
    """
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    
    if user_role not in ['super_admin', 'company_owner', 'manager']:
        return jsonify({'error': 'Unauthorized access'}), 403
    
    try:
        data = request.get_json() or {}
        target_month = data.get('target_month')  # Format: '01' for January, '02' for February, etc.
        
        customers = invoice_crud.get_customers_for_monthly_invoices(company_id, target_month)
        return jsonify({'customers': customers}), 200
        
    except invoice_crud.InvoiceError as e:
        logger.error(f"Invoice error: {str(e)}")
        return jsonify({'error': 'Failed to get monthly invoice preview', 'message': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting monthly invoice preview: {str(e)}")
        return jsonify({'error': 'Failed to get monthly invoice preview', 'message': str(e)}), 500

@main.route('/invoices/bulk-monthly/generate', methods=['POST'])
@jwt_required()
def generate_bulk_monthly_invoices():
    """
    Generate monthly invoices for selected customers
    """
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    
    if user_role not in ['super_admin', 'company_owner', 'manager']:
        return jsonify({'error': 'Unauthorized access'}), 403
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        customer_ids = data.get('customer_ids', [])
        target_month = data.get('target_month')
        
        if not customer_ids:
            return jsonify({'error': 'No customers selected'}), 400
        
        result = invoice_crud.generate_bulk_monthly_invoices(
            company_id, 
            customer_ids, 
            target_month,
            current_user_id, 
            user_role, 
            ip_address, 
            user_agent
        )
        
        return jsonify(result), 200
        
    except invoice_crud.InvoiceError as e:
        logger.error(f"Invoice error: {str(e)}")
        return jsonify({'error': 'Failed to generate bulk monthly invoices', 'message': str(e)}), 400
    except Exception as e:
        logger.error(f"Error generating bulk monthly invoices: {str(e)}")
        return jsonify({'error': 'Failed to generate bulk monthly invoices', 'message': str(e)}), 500

@main.route('/public/invoice/<string:id>', methods=['GET'])
def get_public_invoice(id):
    """
    Public endpoint to view invoice without authentication
    """
    try:
        # Get invoice with complete data for public view (now includes all fields)
        invoice = invoice_crud.get_enhanced_invoice_by_id(id, None, 'public')
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        # Return all the data (matching the authenticated version)
        return jsonify(invoice), 200
        
    except Exception as e:
        logger.error(f"Error fetching public invoice {id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch invoice'}), 500

@main.route('/public/payments/invoice/<string:invoice_id>', methods=['GET'])
def get_public_payment_details(invoice_id):
    """
    Public endpoint to get payment details for an invoice
    """
    try:
        from app.crud import payment_crud
        payments = payment_crud.get_payment_by_invoice_id(invoice_id, None)  # No company_id for public access
        
        if not payments:
            return jsonify({'error': 'No payments found'}), 404
        
        return jsonify(payments), 200
        
    except Exception as e:
        logger.error(f"Error fetching public payment details for invoice {invoice_id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch payment details'}), 500

@main.route('/public/bank-accounts/list', methods=['GET'])
def get_public_bank_accounts():
    """
    Public endpoint to get bank account information for payments
    """
    try:
        from app.models import BankAccount
        accounts = BankAccount.query.filter(BankAccount.is_active == True).all()
        
        return jsonify([{
            'id': str(account.id),
            'bank_name': account.bank_name,
            'account_title': account.account_title,
            'account_number': account.account_number,
            'iban': account.iban,
            'branch_code': account.branch_code
        } for account in accounts]), 200
        
    except Exception as e:
        logger.error(f"Error fetching public bank accounts: {str(e)}")
        return jsonify({'error': 'Failed to fetch bank accounts'}), 500

@main.route('/invoices/page', methods=['GET'])
@jwt_required()
def get_invoices_page():
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    employee_id = claims['id']

    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    sort = request.args.get('sort')  # e.g. "invoice_number:asc,due_date:desc"
    q = request.args.get('q')

    result = invoice_crud.get_invoices_page(
        company_id=company_id,
        user_role=user_role,
        employee_id=employee_id,
        page=page,
        page_size=page_size,
        sort=sort,
        q=q,
    )
    return jsonify(result), 200

@main.route('/invoices/summary', methods=['GET'])
@jwt_required()
def get_invoices_summary():
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    employee_id = claims['id']

    summary = invoice_crud.get_invoices_summary(
        company_id=company_id,
        user_role=user_role,
        employee_id=employee_id,
    )
    return jsonify(summary), 200
