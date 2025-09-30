from app import db
from app.models import Invoice, Customer, Payment
from app.utils.logging_utils import log_action
import uuid
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, DatabaseError
from datetime import datetime
import logging
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)

class InvoiceError(Exception):
    """Custom exception for invoice operations"""
    pass

class PaymentError(Exception):
    """Custom exception for payment operations"""
    pass

def get_all_invoices(company_id, user_role, employee_id):
    try:
        if user_role == 'super_admin':
            invoices = db.session.query(Invoice).options(joinedload(Invoice.customer)).all()
        elif user_role == 'auditor':
            invoices = db.session.query(Invoice).options(joinedload(Invoice.customer)).filter(Invoice.is_active == True).all()
        elif user_role == 'company_owner':
            invoices = db.session.query(Invoice).options(joinedload(Invoice.customer)).filter(Invoice.company_id == company_id).all()
        elif user_role == 'employee':
            invoices = db.session.query(Invoice).options(joinedload(Invoice.customer)).filter(Invoice.generated_by == employee_id).all()
        # Include customer.internet_id in the returned data
        return [
            {
                **invoice_to_dict(invoice),
                "internet_id": invoice.customer.internet_id if invoice.customer else None
            }
            for invoice in invoices
        ]
    except Exception as e:
        logger.error(f"Error listing invoices: {str(e)}")
        raise InvoiceError("Failed to list invoices")

def invoice_to_dict(invoice):
    return {
        'id': str(invoice.id),
        'invoice_number': invoice.invoice_number,
        'company_id': str(invoice.company_id),
        'customer_id': str(invoice.customer_id),
        'customer_name': f"{invoice.customer.first_name} {invoice.customer.last_name}" if invoice.customer else "N/A",\
        'customer_phone': invoice.customer.phone_1 if invoice.customer else "",
        'billing_start_date': invoice.billing_start_date.isoformat(),
        'billing_end_date': invoice.billing_end_date.isoformat(),
        'due_date': invoice.due_date.isoformat(),
        'subtotal': float(invoice.subtotal),
        'discount_percentage': float(invoice.discount_percentage),
        'total_amount': float(invoice.total_amount),
        'invoice_type': invoice.invoice_type,
        'notes': invoice.notes,
        'generated_by': str(invoice.generated_by),
        'status': invoice.status,
        'is_active': invoice.is_active
    }

def generate_invoice_number():
    try:
        year = datetime.now().year
        last_invoice = Invoice.query.order_by(Invoice.created_at.desc()).first()
        if last_invoice and last_invoice.invoice_number.startswith(f'INV-{year}-'):
            try:
                last_number = int(last_invoice.invoice_number.split('-')[-1])
                new_number = last_number + 1
            except (ValueError, IndexError) as e:
                logger.error(f"Error parsing invoice number: {str(e)}")
                raise InvoiceError("Failed to generate invoice number")
        else:
            new_number = 1
        return f'INV-{year}-{new_number:04d}'
    except Exception as e:
        logger.error(f"Error generating invoice number: {str(e)}")
        raise InvoiceError("Failed to generate invoice number")

def add_invoice(data, current_user_id, user_role, ip_address, user_agent):
    try:
        # Validate required fields
        required_fields = ['company_id', 'customer_id', 'billing_start_date', 
                         'billing_end_date', 'due_date', 'subtotal', 
                         'discount_percentage', 'total_amount', 'invoice_type']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        # Parse and validate dates
        date_fields = ['billing_start_date', 'billing_end_date', 'due_date']
        parsed_dates = {}
        for field in date_fields:
            try:
                parsed_dates[field] = datetime.fromisoformat(data[field].rstrip('Z'))
            except ValueError:
                raise ValueError(f"Invalid date format for {field}")
        
        company_id = uuid.UUID(data['company_id'])

        new_invoice = Invoice(
            company_id=company_id,
            invoice_number=generate_invoice_number(),
            customer_id=uuid.UUID(data['customer_id']),
            billing_start_date=parsed_dates['billing_start_date'],
            billing_end_date=parsed_dates['billing_end_date'],
            due_date=parsed_dates['due_date'],
            subtotal=data['subtotal'],
            discount_percentage=data['discount_percentage'],
            total_amount=data['total_amount'],
            invoice_type=data['invoice_type'],
            notes=data.get('notes'),
            generated_by=current_user_id,
            status='pending',
            is_active=True
        )
        
        db.session.add(new_invoice)
        db.session.commit()

        # Prepare data for logging by converting datetime objects to strings
        log_data = data.copy()
        for field in date_fields:
            if field in log_data:
                log_data[field] = parsed_dates[field].isoformat()

        log_action(
            current_user_id,
            'CREATE',
            'invoices',
            new_invoice.id,
            None,
            log_data,  # Use the modified data with string dates
            ip_address,
            user_agent,
            str(company_id)
        )

        return new_invoice
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise InvoiceError(str(e))
    except Exception as e:
        logger.error(f"Error adding invoice: {str(e)}")
        db.session.rollback()
        raise InvoiceError("Failed to create invoice")

def update_invoice(id, data, company_id, user_role, current_user_id, ip_address, user_agent):
    try:
        if user_role == 'super_admin':
            invoice = Invoice.query.get(id)
        elif user_role == 'auditor':
            invoice = Invoice.query.filter_by(id=id, is_active=True, company_id=company_id).first()
        elif user_role == 'company_owner':
            invoice = Invoice.query.filter_by(id=id, company_id=company_id).first()

        if not invoice:
            raise ValueError(f"Invoice with id {id} not found")

        old_values = invoice_to_dict(invoice)

        # Prepare data for logging by converting datetime objects to strings
        log_data = data.copy()
        date_fields = ['billing_start_date', 'billing_end_date', 'due_date']
        for field in date_fields:
            if field in log_data and isinstance(log_data[field], datetime):
                log_data[field] = log_data[field].isoformat()

        # Validate UUID fields
        if 'customer_id' in data:
            try:
                data['customer_id'] = uuid.UUID(data['customer_id'])
            except ValueError:
                raise ValueError("Invalid customer_id format")

        if 'generated_by' in data:
            try:
                data['generated_by'] = uuid.UUID(data['generated_by'])
            except ValueError:
                raise ValueError("Invalid generated_by format")

        # Update fields
        fields_to_update = [
            'customer_id', 'billing_start_date', 'billing_end_date', 
            'due_date', 'subtotal', 'discount_percentage', 'total_amount',
            'invoice_type', 'notes', 'generated_by', 'is_active'
        ]
        
        for field in fields_to_update:
            if field in data:
                setattr(invoice, field, data[field])

        db.session.commit()

        log_action(
            current_user_id,
            'UPDATE',
            'invoices',
            invoice.id,
            old_values,
            log_data,  # Use the modified data with string dates
            ip_address,
            user_agent,
            company_id
        )

        return invoice
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise InvoiceError(str(e))
    except Exception as e:
        logger.error(f"Error updating invoice {id}: {str(e)}")
        db.session.rollback()
        raise InvoiceError("Failed to update invoice")
    
def delete_invoice(id, company_id, user_role, current_user_id, ip_address, user_agent):
    try:
        if user_role == 'super_admin':
            invoice = Invoice.query.get(id)
        elif user_role == 'auditor':
            invoice = Invoice.query.filter_by(id=id, is_active=True, company_id=company_id).first()
        elif user_role == 'company_owner':
            invoice = Invoice.query.filter_by(id=id, company_id=company_id).first()

        if not invoice:
            raise ValueError(f"Invoice with id {id} not found")

        # Check for related payments
        payments = Payment.query.filter_by(invoice_id=id).all()
        if payments:
            raise ValueError("Cannot delete invoice with associated payments")

        old_values = invoice_to_dict(invoice)

        db.session.delete(invoice)
        db.session.commit()

        log_action(
            current_user_id,
            'DELETE',
            'invoices',
            invoice.id,
            old_values,
            None,
                        ip_address,
            user_agent,
            company_id
)

        return True
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise InvoiceError(str(e))
    except Exception as e:
        logger.error(f"Error deleting invoice {id}: {str(e)}")
        db.session.rollback()
        raise InvoiceError("Failed to delete invoice")

def get_invoice_by_id(id, company_id, user_role):
    try:
        if user_role == 'super_admin':
            invoice = Invoice.query.get(id)
        elif user_role == 'auditor':
            invoice = Invoice.query.filter_by(id=id, is_active=True, company_id=company_id).first()
        elif user_role == 'company_owner':
            invoice = Invoice.query.filter_by(id=id, company_id=company_id).first()

        return invoice
    except Exception as e:
        logger.error(f"Error getting invoice {id}: {str(e)}")
        raise InvoiceError("Failed to retrieve invoice")


def generate_monthly_invoices(company_id, user_role, current_user_id, ip_address, user_agent):
    """
    Generate monthly invoices for customers whose recharge date is today.
    
    Args:
        company_id: UUID of the company
        user_role: Role of the current user
        current_user_id: UUID of the current user
        ip_address: IP address of the request
        user_agent: User agent of the request
        
    Returns:
        Dictionary with statistics about the operation:
        - generated: Number of invoices generated
        - skipped: Number of invoices skipped (already exist)
        - total_customers: Total number of customers processed
    """
    try:
        today = datetime.now().date()
        
        # Get all active customers whose recharge date is today
        customers = Customer.query.filter(
            Customer.is_active == True,
            Customer.company_id == company_id,
            Customer.recharge_date != None,
            db.func.extract('day', Customer.recharge_date) == today.day,
            db.func.extract('month', Customer.recharge_date) == today.month
        ).all()
        
        logger.info(f"Found {len(customers)} customers with recharge date today for company {company_id}")
        
        # Check if invoices have already been generated this month
        current_month_start = datetime(today.year, today.month, 1).date()
        next_month_start = (datetime(today.year, today.month, 1) + timedelta(days=32)).replace(day=1).date()
        
        invoice_count = 0
        skipped_count = 0
        error_count = 0
        
        for customer in customers:
            try:
                # Check if an invoice already exists for this customer in the current month
                existing_invoice = Invoice.query.filter(
                    Invoice.customer_id == customer.id,
                    Invoice.billing_start_date >= current_month_start,
                    Invoice.billing_start_date < next_month_start,
                    Invoice.invoice_type == 'subscription'
                ).first()
                
                if existing_invoice:
                    logger.info(f"Invoice already exists for customer {customer.id} this month")
                    skipped_count += 1
                    continue
                
                # Get the customer's service plan
                service_plan = ServicePlan.query.get(customer.service_plan_id)
                if not service_plan:
                    logger.error(f"Service plan not found for customer {customer.id}")
                    error_count += 1
                    continue
                
                # Calculate billing period
                billing_start_date = today
                next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
                billing_end_date = (next_month - timedelta(days=1))
                
                # Calculate due date (7 days from today)
                due_date = today + timedelta(days=7)
                
                # Calculate amounts
                subtotal = float(service_plan.price)
                discount_percentage = 0
                if customer.discount_amount:
                    discount_percentage = (float(customer.discount_amount) / subtotal) * 100
                
                total_amount = subtotal - (subtotal * discount_percentage / 100)
                
                # Create invoice data
                invoice_data = {
                    'company_id': str(company_id),
                    'customer_id': str(customer.id),
                    'billing_start_date': billing_start_date.isoformat(),
                    'billing_end_date': billing_end_date.isoformat(),
                    'due_date': due_date.isoformat(),
                    'subtotal': subtotal,
                    'discount_percentage': discount_percentage,
                    'total_amount': total_amount,
                    'invoice_type': 'subscription',
                    'notes': f"Manually generated invoice for {service_plan.name} plan"
                }
                
                # Add the invoice
                add_invoice(
                    invoice_data, 
                    current_user_id, 
                    user_role, 
                    ip_address,
                    user_agent
                )
                
                invoice_count += 1
                logger.info(f"Generated invoice for customer {customer.id} ({customer.first_name} {customer.last_name})")
                
            except Exception as e:
                logger.error(f"Error generating invoice for customer {customer.id}: {str(e)}")
                error_count += 1
        
        logger.info(f"Monthly invoice generation completed. Generated: {invoice_count}, Skipped: {skipped_count}, Errors: {error_count}")
        
        return {
            'generated': invoice_count,
            'skipped': skipped_count,
            'errors': error_count,
            'total_customers': len(customers)
        }
        
    except Exception as e:
        logger.error(f"Error in generate_monthly_invoices: {str(e)}")
        raise InvoiceError(f"Failed to generate monthly invoices: {str(e)}")

def get_enhanced_invoice_by_id(id, company_id, user_role):
    try:
        if user_role == 'super_admin':
            invoice = db.session.query(Invoice).options(
                joinedload(Invoice.customer).joinedload(Customer.service_plan)
            ).filter(Invoice.id == id).first()
        elif user_role == 'auditor':
            invoice = db.session.query(Invoice).options(
                joinedload(Invoice.customer).joinedload(Customer.service_plan)
            ).filter(Invoice.id == id, Invoice.is_active == True, Invoice.company_id == company_id).first()
        elif user_role == 'company_owner':
            invoice = db.session.query(Invoice).options(
                joinedload(Invoice.customer).joinedload(Customer.service_plan)
            ).filter(Invoice.id == id, Invoice.company_id == company_id).first()

        if not invoice:
            return None

        # Enhanced invoice data with customer and service plan details
        return {
            'id': str(invoice.id),
            'invoice_number': invoice.invoice_number,
            'company_id': str(invoice.company_id),
            'customer_id': str(invoice.customer_id),
            'customer_name': f"{invoice.customer.first_name} {invoice.customer.last_name}" if invoice.customer else "N/A",
            'customer_address': invoice.customer.installation_address if invoice.customer else "",
            'customer_internet_id': invoice.customer.internet_id if invoice.customer else "",
            'customer_phone': invoice.customer.phone_1 if invoice.customer else "",
            'service_plan_name': invoice.customer.service_plan.name if invoice.customer and invoice.customer.service_plan else "N/A",
            'billing_start_date': invoice.billing_start_date.isoformat(),
            'billing_end_date': invoice.billing_end_date.isoformat(),
            'due_date': invoice.due_date.isoformat(),
            'subtotal': float(invoice.subtotal),
            'discount_percentage': float(invoice.discount_percentage),
            'total_amount': float(invoice.total_amount),
            'invoice_type': invoice.invoice_type,
            'notes': invoice.notes,
            'generated_by': str(invoice.generated_by),
            'status': invoice.status,
            'is_active': invoice.is_active
        }
    except Exception as e:
        logger.error(f"Error getting enhanced invoice {id}: {str(e)}")
        raise InvoiceError("Failed to retrieve invoice details")
