from flask import jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from . import main
from ..crud import isp_payment_crud
import os
from werkzeug.utils import secure_filename

@main.route('/isp-payments/list', methods=['GET'])
@jwt_required()
def get_isp_payments():
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    employee_id = claims['id']
    
    try:
        payments = isp_payment_crud.get_all_isp_payments(company_id, user_role, employee_id)
        return jsonify(payments), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch ISP payments', 'message': str(e)}), 500

@main.route('/isp-payments/add', methods=['POST'])
@jwt_required()
def add_new_isp_payment():
    UPLOAD_FOLDER = 'uploads/isp_payment_proofs'
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    
    data = request.json
    data['company_id'] = company_id
    data['processed_by'] = current_user_id
    
    # Handle file upload
    if 'payment_proof' in request.files:
        file = request.files['payment_proof']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{company_id}_{data.get('isp_id', 'unknown')}_{file.filename}")
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            data['payment_proof'] = file_path
    try:
        new_payment = isp_payment_crud.add_isp_payment(data, user_role, current_user_id, ip_address, user_agent)
        return jsonify({'message': 'ISP payment added successfully', 'id': str(new_payment.id)}), 201
    except Exception as e:
        return jsonify({'error': 'Failed to add ISP payment', 'message': str(e)}), 400

@main.route('/isp-payments/update/<string:id>', methods=['PUT'])
@jwt_required()
def update_existing_isp_payment(id):
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    
    data = request.form.to_dict() if request.form else request.json
    
    # Handle file upload for updates
    if 'payment_proof' in request.files:
        file = request.files['payment_proof']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)
            data['payment_proof'] = file_path
    
    try:
        updated_payment = isp_payment_crud.update_isp_payment(id, data, company_id, user_role, current_user_id, ip_address, user_agent)
        if updated_payment:
            return jsonify({'message': 'ISP payment updated successfully'}), 200
        return jsonify({'message': 'ISP payment not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Failed to update ISP payment', 'message': str(e)}), 400

@main.route('/isp-payments/delete/<string:id>', methods=['DELETE'])
@jwt_required()
def delete_existing_isp_payment(id):
    claims = get_jwt()
    company_id = claims['company_id']
    user_role = claims['role']
    current_user_id = get_jwt_identity()
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    
    try:
        if isp_payment_crud.delete_isp_payment(id, company_id, user_role, current_user_id, ip_address, user_agent):
            return jsonify({'message': 'ISP payment deleted successfully'}), 200
        return jsonify({'message': 'ISP payment not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Failed to delete ISP payment', 'message': str(e)}), 400

@main.route('/isp-payments/proof-image/<string:id>', methods=['GET'])
@jwt_required()
def get_isp_payment_proof_image(id):
    UPLOAD_FOLDER_PATH = 'uploads/isp_payment_proofs'
    claims = get_jwt()
    company_id = claims.get('company_id')

    try:
        payment_proof = isp_payment_crud.get_isp_payment_proof(id, company_id)
        if payment_proof and payment_proof.get('proof_of_payment'):
            proof_image_path = payment_proof['proof_of_payment']
            if os.path.exists(proof_image_path):
                return send_file(proof_image_path, mimetype='image/jpeg')
            else:
                return jsonify({'error': 'ISP payment proof image file not found'}), 404
        return jsonify({'error': 'ISP payment proof not found'}), 404
    except Exception as error:
        return jsonify({'error': 'An error occurred while retrieving the ISP payment proof image'}), 500

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS