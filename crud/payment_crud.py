from app import db
from app.models import Payment, Customer, Invoice, Company, BankAccount
from app.utils.logging_utils import log_action
import uuid
import logging
import os
from werkzeug.utils import secure_filename
from sqlalchemy import func  # ADD THIS IMPORT
from decimal import Decimal  # ADD THIS IMPORT

logger = logging.getLogger(__name__)

class InvoiceError(Exception):
    """Custom exception for invoice operations"""
    pass

class PaymentError(Exception):
    """Custom exception for payment operations"""
    pass

def get_all_payments(company_id, user_role,employee_id):
    try:
        if user_role == 'super_admin':
            payments = Payment.query.all()
        elif user_role == 'auditor':
            payments = Payment.query.filter_by(is_active=True, company_id=company_id).all()
        elif user_role == 'company_owner':
            payments = Payment.query.filter_by(company_id=company_id).all()
        elif user_role == 'employee':
            payments = Payment.query.filter_by(received_by=employee_id).all()

        result = []
        for payment in payments:
            try:
                result.append({
                    'id': str(payment.id),
                    'invoice_id': str(payment.invoice_id),
                    'invoice_number': payment.invoice.invoice_number,
                    'customer_name': f"{payment.invoice.customer.first_name} {payment.invoice.customer.last_name}",
                    'amount': float(payment.amount),
                    'payment_date': payment.payment_date.isoformat(),
                    'payment_method': payment.payment_method,
                    'transaction_id': payment.transaction_id,
                    'status': payment.status,
                    'failure_reason': payment.failure_reason,
                    'payment_proof': payment.payment_proof,
                    'received_by': f"{payment.receiver.first_name} {payment.receiver.last_name}",
                    'is_active': payment.is_active,
                    'due_date': payment.invoice.due_date.isoformat() if payment.invoice.due_date else None,  # Add this
                    'status': payment.invoice.status if hasattr(payment.invoice, 'status') else 'N/A',  # Add this
                    'billing_start_date': payment.invoice.billing_start_date.isoformat() if payment.invoice.billing_start_date else None,
                    'billing_end_date': payment.invoice.billing_end_date.isoformat() if payment.invoice.billing_end_date else None,
                    'bank_account_id': str(payment.bank_account_id) if payment.bank_account_id else None,
                    'bank_account_details': f"{payment.bank_account.bank_name} - {payment.bank_account.account_number}" if payment.bank_account else None,
                })
            except AttributeError as e:
                logger.error(f"Error processing payment {payment.id}: {str(e)}")
                continue
        return result
    except Exception as e:
        logger.error(f"Error getting payments: {str(e)}")
        raise PaymentError("Failed to retrieve payments")

# In payment_crud.py - Simplified logic
def add_payment(data, user_role, current_user_id, ip_address, user_agent):
    try:
        # Validate required fields
        required_fields = ['company_id', 'invoice_id', 'amount', 'payment_date', 
                         'payment_method', 'status', 'received_by']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        UPLOAD_FOLDER = 'uploads/payment_proofs'
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # Get invoice details for validation
        invoice = Invoice.query.get(uuid.UUID(data['invoice_id']))
        if not invoice:
            raise ValueError("Invalid invoice_id")

        # Calculate total paid amount for this invoice
        total_paid = db.session.query(func.sum(Payment.amount)).filter(
            Payment.invoice_id == uuid.UUID(data['invoice_id']),
            Payment.is_active == True,
            Payment.status == 'paid'  # Only count successful payments
        ).scalar() or Decimal('0.00')

        current_payment_amount = Decimal(str(data['amount']))
        invoice_total = invoice.total_amount

        # Check if payment exceeds invoice total
        if total_paid + current_payment_amount > invoice_total:
            raise ValueError(f"Payment amount exceeds invoice balance. Remaining balance: PKR {invoice_total - total_paid}")

        # Validate and create payment
        try:
            new_payment = Payment(
                company_id=uuid.UUID(data['company_id']),
                invoice_id=uuid.UUID(data['invoice_id']),
                amount=current_payment_amount,
                payment_date=data['payment_date'],
                payment_method=data['payment_method'],
                transaction_id=data.get('transaction_id'),
                status=data['status'],  # paid, failed, etc.
                failure_reason=data.get('failure_reason'),
                received_by=uuid.UUID(data['received_by']),
                bank_account_id=uuid.UUID(data['bank_account_id']) if data.get('bank_account_id') else None,
                is_active=True
            )
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid data format: {str(e)}")

        # Handle payment proof
        if 'payment_proof' in data and data['payment_proof']:
            new_payment.payment_proof = data['payment_proof']

        db.session.add(new_payment)
        
        # Update invoice status ONLY if payment is successful
        if data['status'] == 'paid':
            total_paid_after = total_paid + current_payment_amount
            
            if total_paid_after == invoice_total:
                invoice.status = 'paid'
            elif total_paid_after > Decimal('0.00'):
                invoice.status = 'partially_paid'
            else:
                invoice.status = 'pending'
        
        db.session.commit()

        log_action(
            current_user_id,
            'CREATE',
            'payments',
            new_payment.id,
            None,
            {k: v for k, v in data.items() if k != 'payment_proof'},
            ip_address,
            user_agent,
            uuid.UUID(data['company_id'])
        )

        return new_payment
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise PaymentError(str(e))
    except Exception as e:
        logger.error(f"Error adding payment: {str(e)}")
        db.session.rollback()
        raise PaymentError("Failed to create payment")
def fetch_active_bank_accounts(company_id):
    try:
        bank_accounts = BankAccount.query.filter_by(company_id=company_id, is_active=True).all()
        return [
            {
                'id': str(account.id),
                'bank_name': account.bank_name,
                'account_title': account.account_title,
                'account_number': account.account_number,
                'iban': account.iban,
                'branch_code': account.branch_code,
                'branch_address': account.branch_address
            }
            for account in bank_accounts
        ]
    except Exception as e:
        raise Exception(f"Database operation failed: {str(e)}")
def update_payment(id, data, company_id, user_role, current_user_id, ip_address, user_agent):
    try:
        if user_role == 'super_admin':
            payment = Payment.query.get(id)
        elif user_role == 'auditor':
            payment = Payment.query.filter_by(id=id, is_active=True, company_id=company_id).first()
        elif user_role == 'company_owner':
            payment = Payment.query.filter_by(id=id, company_id=company_id).first()

        if not payment:
            raise ValueError(f"Payment with id {id} not found")

        UPLOAD_FOLDER = 'uploads/payment_proofs'
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        old_values = {
            'invoice_id': str(payment.invoice_id),
            'amount': float(payment.amount),
            'payment_date': payment.payment_date.isoformat(),
            'payment_method': payment.payment_method,
            'transaction_id': payment.transaction_id,
            'status': payment.status,
            'failure_reason': payment.failure_reason,
            'payment_proof': payment.payment_proof,
            'received_by': str(payment.received_by),
            'bank_account_id': str(payment.bank_account_id) if payment.bank_account_id else None,
            'is_active': payment.is_active
        }

        # Update fields
        if 'invoice_id' in data:
            payment.invoice_id = uuid.UUID(data['invoice_id'])
        if 'amount' in data:
            payment.amount = float(data['amount'])
        if 'payment_date' in data:
            payment.payment_date = data['payment_date']
        if 'payment_method' in data:
            payment.payment_method = data['payment_method']
        if 'transaction_id' in data:
            payment.transaction_id = data['transaction_id']
        if 'status' in data:
            payment.status = data['status']
        if 'failure_reason' in data:
            payment.failure_reason = data['failure_reason']
        if 'received_by' in data:
            payment.received_by = uuid.UUID(data['received_by'])
        if 'is_active' in data:
            # Convert string boolean to actual boolean
            if isinstance(data['is_active'], str):
                payment.is_active = data['is_active'].lower() == 'true'
            else:
                payment.is_active = bool(data['is_active'])
        if 'bank_account_id' in data:
            payment.bank_account_id = uuid.UUID(data['bank_account_id']) if data['bank_account_id'] else None
        
        # Handle payment proof update
        if 'payment_proof' in data and data['payment_proof']:
            try:
                # Delete old file if it exists and is different from new one
                if payment.payment_proof and os.path.exists(payment.payment_proof) and payment.payment_proof != data['payment_proof']:
                    os.remove(payment.payment_proof)
                
                payment.payment_proof = data['payment_proof']
            except Exception as e:
                logger.error(f"Error updating payment proof: {str(e)}")
                raise PaymentError("Failed to update payment proof")

        # Update invoice status based on payment status
        if payment.status == 'paid':
            invoice = Invoice.query.get(payment.invoice_id)
            if invoice:
                invoice.status = 'paid'
        elif payment.status in ['failed', 'cancelled', 'refunded']:
            invoice = Invoice.query.get(payment.invoice_id)
            if invoice and invoice.status == 'paid':
                invoice.status = 'pending'

        db.session.commit()

        log_action(
            current_user_id,
            'UPDATE',
            'payments',
            payment.id,
            old_values,
            {k: v for k, v in data.items() if k != 'payment_proof'},
            ip_address,
            user_agent,
            company_id
        )

        return payment
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise PaymentError(str(e))
    except Exception as e:
        logger.error(f"Error updating payment {id}: {str(e)}")
        db.session.rollback()
        raise PaymentError("Failed to update payment")

def delete_payment(id, company_id, user_role, current_user_id, ip_address, user_agent):
    try:
        if user_role == 'super_admin':
            payment = Payment.query.get(id)
        elif user_role == 'auditor':
            payment = Payment.query.filter_by(id=id, is_active=True, company_id=company_id).first()
        elif user_role == 'company_owner':
            payment = Payment.query.filter_by(id=id, company_id=company_id).first()

        if not payment:
            raise ValueError(f"Payment with id {id} not found")

        old_values = {
            'invoice_id': str(payment.invoice_id),
            'amount': float(payment.amount),
            'payment_date': payment.payment_date.isoformat(),
            'payment_method': payment.payment_method,
            'transaction_id': payment.transaction_id,
            'status': payment.status,
            'failure_reason': payment.failure_reason,
            'payment_proof': payment.payment_proof,
            'received_by': str(payment.received_by),
            'is_active': payment.is_active
        }

        # Delete payment proof file if it exists
        if payment.payment_proof and os.path.exists(payment.payment_proof):
            try:
                os.remove(payment.payment_proof)
            except OSError as e:
                logger.error(f"Error deleting payment proof file: {str(e)}")

        db.session.delete(payment)
        db.session.commit()

        log_action(
            current_user_id,
            'DELETE',
            'payments',
            payment.id,
            old_values,
            None,
                        ip_address,
            user_agent,
            company_id
)

        return True
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise PaymentError(str(e))
    except Exception as e:
        logger.error(f"Error deleting payment {id}: {str(e)}")
        db.session.rollback()
        raise PaymentError("Failed to delete payment")

def get_payment_proof(invoice_id,company_id):
    try:
        payment_record = Payment.query.get(invoice_id)
        if not payment_record:
            raise ValueError("Payment invoice not found")

        payment_proof_details = {
            'invoice_id': str(payment_record.id),
            'proof_of_payment': payment_record.payment_proof
        }
        return payment_proof_details
    except ValueError as validation_error:
        logger.error(f"Validation error: {str(validation_error)}")
        raise PaymentError(str(validation_error))
    except Exception as general_error:
        logger.error(f"Unexpected error while retrieving payment proof: {str(general_error)}")
        raise PaymentError("Unable to retrieve the payment proof")

def get_payment_by_invoice_id(invoice_id, company_id=None):
    """
    Get all payments for an invoice.
    For public access, company_id can be None.
    """
    try:
        query = db.session.query(Payment).filter(
            Payment.invoice_id == invoice_id,
            Payment.is_active == True
        )
        
        # Only filter by company_id if provided (for authenticated users)
        if company_id:
            query = query.filter(Payment.company_id == company_id)
        
        payments = query.order_by(Payment.payment_date.desc()).all()
        
        if not payments:
            return []
            
        return [
            {
                'id': str(payment.id),
                'amount': float(payment.amount),
                'payment_date': payment.payment_date.isoformat(),
                'payment_method': payment.payment_method,
                'transaction_id': payment.transaction_id,
                'status': payment.status,
                'failure_reason': payment.failure_reason
            }
            for payment in payments
        ]
    except Exception as e:
        logger.error(f"Error getting payments for invoice {invoice_id}: {str(e)}")
        raise PaymentError("Failed to retrieve payment details")