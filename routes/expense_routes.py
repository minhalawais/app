from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from . import main
from ..crud import expense_crud

@main.route('/expenses/list', methods=['GET'])
@jwt_required()
def get_expenses():
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    try:
        expenses = expense_crud.get_all_expenses(company_id, user_role)
        return jsonify(expenses), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch expenses', 'message': str(e)}), 400

@main.route('/expenses/add', methods=['POST'])
@jwt_required()
def add_expense():
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    data = request.json
    
    try:
        data['company_id'] = company_id
        new_expense = expense_crud.add_expense(data, user_role, current_user_id, request.remote_addr, request.headers.get('User-Agent'))
        return jsonify({'message': 'Expense added successfully', 'id': str(new_expense.id)}), 201
    except Exception as e:
        return jsonify({'error': 'Failed to add expense', 'message': str(e)}), 400

@main.route('/expenses/update/<string:id>', methods=['PUT'])
@jwt_required()
def update_expense(id):
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    data = request.json
    
    try:
        updated_expense = expense_crud.update_expense(id, data, company_id, user_role, current_user_id, request.remote_addr, request.headers.get('User-Agent'))
        if updated_expense:
            return jsonify({'message': 'Expense updated successfully'}), 200
        return jsonify({'message': 'Expense not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Failed to update expense', 'message': str(e)}), 400

@main.route('/expenses/delete/<string:id>', methods=['DELETE'])
@jwt_required()
def delete_expense(id):
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    
    try:
        if expense_crud.delete_expense(id, company_id, user_role, current_user_id, request.remote_addr, request.headers.get('User-Agent')):
            return jsonify({'message': 'Expense deleted successfully'}), 200
        return jsonify({'message': 'Expense not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Failed to delete expense', 'message': str(e)}), 400

@main.route('/expense-types/list', methods=['GET'])
@jwt_required()
def get_expense_types():
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    try:
        expense_types = expense_crud.get_all_expense_types(company_id, user_role)
        return jsonify(expense_types), 200
    except Exception as e:
        print('Error: ',e)
        return jsonify({'error': 'Failed to fetch expense types', 'message': str(e)}), 400

@main.route('/expense-types/add', methods=['POST'])
@jwt_required()
def add_expense_type():
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    data = request.json
    
    try:
        data['company_id'] = company_id
        new_expense_type = expense_crud.add_expense_type(data, user_role, current_user_id, request.remote_addr, request.headers.get('User-Agent'))
        return jsonify({'message': 'Expense type added successfully', 'id': str(new_expense_type.id)}), 201
    except Exception as e:
        print('Error: ',e)
        return jsonify({'error': 'Failed to add expense type', 'message': str(e)}), 400

@main.route('/expense-types/update/<string:id>', methods=['PUT'])
@jwt_required()
def update_expense_type(id):
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    data = request.json
    
    try:
        updated_expense_type = expense_crud.update_expense_type(id, data, company_id, user_role, current_user_id, request.remote_addr, request.headers.get('User-Agent'))
        if updated_expense_type:
            return jsonify({'message': 'Expense type updated successfully'}), 200
        return jsonify({'message': 'Expense type not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Failed to update expense type', 'message': str(e)}), 400

@main.route('/expense-types/delete/<string:id>', methods=['DELETE'])
@jwt_required()
def delete_expense_type(id):
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    
    try:
        if expense_crud.delete_expense_type(id, company_id, user_role, current_user_id, request.remote_addr, request.headers.get('User-Agent')):
            return jsonify({'message': 'Expense type deleted successfully'}), 200
        return jsonify({'message': 'Expense type not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Failed to delete expense type', 'message': str(e)}), 400