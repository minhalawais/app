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