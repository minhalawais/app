from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from . import main
from ..crud import extra_income_crud

@main.route('/extra-incomes/list', methods=['GET'])
@jwt_required()
def get_extra_incomes():
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    try:
        incomes = extra_income_crud.get_all_extra_incomes(company_id, user_role)
        return jsonify(incomes), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch extra incomes', 'message': str(e)}), 400

@main.route('/extra-incomes/add', methods=['POST'])
@jwt_required()
def add_extra_income():
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    data = request.json
    
    try:
        data['company_id'] = company_id
        new_income = extra_income_crud.add_extra_income(data, user_role, current_user_id, request.remote_addr, request.headers.get('User-Agent'))
        return jsonify({'message': 'Extra income added successfully', 'id': str(new_income.id)}), 201
    except Exception as e:
        return jsonify({'error': 'Failed to add extra income', 'message': str(e)}), 400

@main.route('/extra-incomes/update/<string:id>', methods=['PUT'])
@jwt_required()
def update_extra_income(id):
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    data = request.json
    
    try:
        updated_income = extra_income_crud.update_extra_income(id, data, company_id, user_role, current_user_id, request.remote_addr, request.headers.get('User-Agent'))
        if updated_income:
            return jsonify({'message': 'Extra income updated successfully'}), 200
        return jsonify({'message': 'Extra income not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Failed to update extra income', 'message': str(e)}), 400

@main.route('/extra-incomes/delete/<string:id>', methods=['DELETE'])
@jwt_required()
def delete_extra_income(id):
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    
    try:
        if extra_income_crud.delete_extra_income(id, company_id, user_role, current_user_id, request.remote_addr, request.headers.get('User-Agent')):
            return jsonify({'message': 'Extra income deleted successfully'}), 200
        return jsonify({'message': 'Extra income not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Failed to delete extra income', 'message': str(e)}), 400

@main.route('/extra-income-types/list', methods=['GET'])
@jwt_required()
def get_extra_income_types():
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    try:
        income_types = extra_income_crud.get_all_extra_income_types(company_id, user_role)
        return jsonify(income_types), 200
    except Exception as e:
        print('Error: ',e)
        return jsonify({'error': 'Failed to fetch extra income types', 'message': str(e)}), 400

@main.route('/extra-income-types/add', methods=['POST'])
@jwt_required()
def add_extra_income_type():
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    data = request.json
    
    try:
        data['company_id'] = company_id
        new_income_type = extra_income_crud.add_extra_income_type(data, user_role, current_user_id, request.remote_addr, request.headers.get('User-Agent'))
        return jsonify({'message': 'Extra income type added successfully', 'id': str(new_income_type.id)}), 201
    except Exception as e:
        print('Error: ',e)
        return jsonify({'error': 'Failed to add extra income type', 'message': str(e)}), 400

@main.route('/extra-income-types/update/<string:id>', methods=['PUT'])
@jwt_required()
def update_extra_income_type(id):
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    data = request.json
    
    try:
        updated_income_type = extra_income_crud.update_extra_income_type(id, data, company_id, user_role, current_user_id, request.remote_addr, request.headers.get('User-Agent'))
        if updated_income_type:
            return jsonify({'message': 'Extra income type updated successfully'}), 200
        return jsonify({'message': 'Extra income type not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Failed to update extra income type', 'message': str(e)}), 400

@main.route('/extra-income-types/delete/<string:id>', methods=['DELETE'])
@jwt_required()
def delete_extra_income_type(id):
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    
    try:
        if extra_income_crud.delete_extra_income_type(id, company_id, user_role, current_user_id, request.remote_addr, request.headers.get('User-Agent')):
            return jsonify({'message': 'Extra income type deleted successfully'}), 200
        return jsonify({'message': 'Extra income type not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Failed to delete extra income type', 'message': str(e)}), 400