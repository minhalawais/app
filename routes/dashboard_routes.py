from flask import Blueprint, jsonify,request
from flask_jwt_extended import jwt_required, get_jwt_identity,get_jwt
from app.crud import dashboard_crud
from app.models import User
from . import main
dashboard = Blueprint('dashboard', __name__)

@main.route('/dashboard/executive-summary', methods=['GET'])
@jwt_required()
def get_executive_summary():
    current_user = get_jwt_identity()
    claims = get_jwt()
    company_id = claims['company_id']
    
    data = dashboard_crud.get_executive_summary_data(company_id)
    return jsonify(data)

@main.route('/dashboard/customer-analytics', methods=['GET'])
@jwt_required()
def get_customer_analytics():
    current_user = get_jwt_identity()
    claims = get_jwt()
    company_id = claims['company_id']
    
    data = dashboard_crud.get_customer_analytics_data(company_id)
    return jsonify(data)

@main.route('/dashboard/financial-analytics', methods=['GET'])
@jwt_required()
def get_financial_analytics():
    current_user = get_jwt_identity()
    claims = get_jwt()
    company_id = claims['company_id']
    
    data = dashboard_crud.get_financial_analytics_data(company_id)
    return jsonify(data)

@main.route('/dashboard/service-support', methods=['GET'])
@jwt_required()
def get_service_support_metrics():
    current_user = get_jwt_identity()
    claims = get_jwt()
    company_id = claims['company_id']
    
    data = dashboard_crud.get_service_support_metrics(company_id)
    return jsonify(data)

@main.route('/dashboard/inventory-management', methods=['GET'])
@jwt_required()
def get_inventory_management_data():
    current_user = get_jwt_identity()
    claims = get_jwt()
    company_id = claims['company_id']
    
    stock_level_data = dashboard_crud.get_stock_level_data(company_id)
    inventory_movement_data = dashboard_crud.get_inventory_movement_data(company_id)
    inventory_metrics = dashboard_crud.get_inventory_metrics(company_id)
    
    data = {
        'stock_level_data': stock_level_data,
        'inventory_movement_data': inventory_movement_data,
        'inventory_metrics': inventory_metrics
    }
    return jsonify(data)

@main.route('/dashboard/employee-analytics', methods=['GET'])
@jwt_required()
def get_employee_analytics():
    current_user = get_jwt_identity()
    claims = get_jwt()
    company_id = claims['company_id']
    
    data = dashboard_crud.get_employee_analytics_data(company_id)
    return jsonify(data)

@main.route('/dashboard/area-analytics', methods=['GET'])
@jwt_required()
def get_area_analytics():
    current_user = get_jwt_identity()
    claims = get_jwt()
    company_id = claims['company_id']
    
    data = dashboard_crud.get_area_analytics_data(company_id)
    return jsonify(data)

@main.route('/dashboard/service-plan-analytics', methods=['GET'])
@jwt_required()
def get_service_plan_analytics():
    current_user = get_jwt_identity()
    claims = get_jwt()
    company_id = claims['company_id']
    
    data = dashboard_crud.get_service_plan_analytics_data(company_id)
    return jsonify(data)

@main.route('/dashboard/recovery-collections', methods=['GET'])
@jwt_required()
def get_recovery_collections():
    current_user = get_jwt_identity()
    claims = get_jwt()
    company_id = claims['company_id']
    
    data = dashboard_crud.get_recovery_collections_data(company_id)
    return jsonify(data)


@main.route('/dashboard/bank-account-analytics', methods=['GET'])
@jwt_required()
def get_bank_account_analytics():
    current_user = get_jwt_identity()
    claims = get_jwt()
    company_id = claims['company_id']
    
    # Get filters from query parameters
    filters = {
        'start_date': request.args.get('start_date'),
        'end_date': request.args.get('end_date'),
        'bank_account_id': request.args.get('bank_account_id', 'all'),
        'payment_method': request.args.get('payment_method', 'all')
    }
    
    data = dashboard_crud.get_bank_account_analytics_data(company_id, filters)
    return jsonify(data)

@main.route('/dashboard/unified-financial', methods=['GET'])
@jwt_required()
def get_unified_financial_data():
    claims = get_jwt()
    company_id = claims['company_id']
    
    # Get filters from query parameters
    filters = {
        'start_date': request.args.get('start_date'),
        'end_date': request.args.get('end_date'),
        'bank_account_id': request.args.get('bank_account_id', 'all'),
        'payment_method': request.args.get('payment_method', 'all'),
        'invoice_status': request.args.get('invoice_status', 'all'),
        'isp_payment_type': request.args.get('isp_payment_type', 'all')
    }
    
    try:
        data = dashboard_crud.get_unified_financial_data(company_id, filters)
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Error fetching unified financial data: {str(e)}")
        return jsonify({'error': 'Failed to fetch unified financial data'}), 500

@main.route('/dashboard/ledger', methods=['GET'])
@jwt_required()
def get_ledger():
    claims = get_jwt()
    company_id = claims['company_id']
    filters = {
        'start_date': request.args.get('start_date'),
        'end_date': request.args.get('end_date'),
        'bank_account_id': request.args.get('bank_account_id', 'all'),
        'payment_method': request.args.get('payment_method', 'all'),
        'invoice_status': request.args.get('invoice_status', 'all'),
        'isp_payment_type': request.args.get('isp_payment_type', 'all'),
    }
    data = dashboard_crud.get_ledger_data(company_id, filters)
    return jsonify(data), 200
