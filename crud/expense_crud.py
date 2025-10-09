from app import db
from app.models import Expense,ExpenseType
import uuid
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class ExpenseError(Exception):
    pass

class ExpenseTypeError(Exception):
    pass
def get_all_expenses(company_id, user_role):
    try:
        if user_role == 'super_admin':
            expenses = Expense.query.join(ExpenseType).all()
        elif user_role == 'auditor':
            expenses = Expense.query.join(ExpenseType).filter(Expense.is_active==True, Expense.company_id==company_id).all()
        elif user_role == 'company_owner':
            expenses = Expense.query.join(ExpenseType).filter(Expense.company_id==company_id).all()
        elif user_role == 'employee':
            expenses = Expense.query.join(ExpenseType).filter(Expense.company_id==company_id, Expense.is_active==True).all()

        result = []
        for expense in expenses:
            result.append({
                'id': str(expense.id),
                'expense_type_id': str(expense.expense_type_id),
                'expense_type_name': expense.expense_type.name,
                'description': expense.description,
                'amount': float(expense.amount),
                'expense_date': expense.expense_date.isoformat(),
                'payment_method': expense.payment_method,
                'vendor_payee': expense.vendor_payee,
                'bank_account_id': str(expense.bank_account_id) if expense.bank_account_id else None,
                'is_active': expense.is_active,
                'created_at': expense.created_at.isoformat() if expense.created_at else None,
            })
        return result
    except Exception as e:
        logger.error(f"Error getting expenses: {str(e)}")
        raise ExpenseError("Failed to retrieve expenses")

def add_expense(data, user_role, current_user_id, ip_address, user_agent):
    try:
        required_fields = ['expense_type_id', 'amount', 'expense_date']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        new_expense = Expense(
            company_id=uuid.UUID(data['company_id']),
            expense_type_id=uuid.UUID(data['expense_type_id']),
            description=data.get('description'),
            amount=Decimal(str(data['amount'])),
            expense_date=data['expense_date'],
            payment_method=data.get('payment_method'),
            vendor_payee=data.get('vendor_payee'),
            bank_account_id=uuid.UUID(data['bank_account_id']) if data.get('bank_account_id') else None,
            is_active=data.get('is_active', True)
        )

        db.session.add(new_expense)
        db.session.commit()
        return new_expense
    except Exception as e:
        logger.error(f"Error adding expense: {str(e)}")
        db.session.rollback()
        raise ExpenseError("Failed to create expense")

def update_expense(id, data, company_id, user_role, current_user_id, ip_address, user_agent):
    try:
        if user_role == 'super_admin':
            expense = Expense.query.get(id)
        else:
            expense = Expense.query.filter_by(id=id, company_id=company_id).first()

        if not expense:
            raise ValueError(f"Expense with id {id} not found")

        # Update fields
        updatable_fields = ['expense_type_id', 'description', 'amount', 'expense_date', 'payment_method', 'vendor_payee', 'bank_account_id', 'is_active']
        for field in updatable_fields:
            if field in data:
                if field == 'amount':
                    setattr(expense, field, Decimal(str(data[field])))
                elif field in ['expense_type_id', 'bank_account_id']:
                    setattr(expense, field, uuid.UUID(data[field]) if data[field] else None)
                else:
                    setattr(expense, field, data[field])

        db.session.commit()
        return expense
    except Exception as e:
        logger.error(f"Error updating expense {id}: {str(e)}")
        db.session.rollback()
        raise ExpenseError("Failed to update expense")
def delete_expense(id, company_id, user_role, current_user_id, ip_address, user_agent):
    try:
        if user_role == 'super_admin':
            expense = Expense.query.get(id)
        else:
            expense = Expense.query.filter_by(id=id, company_id=company_id).first()

        if not expense:
            raise ValueError(f"Expense with id {id} not found")

        expense.is_active = False
        db.session.commit()
        return True
    except Exception as e:
        logger.error(f"Error deleting expense {id}: {str(e)}")
        db.session.rollback()
        raise ExpenseError("Failed to delete expense")

def get_all_expense_types(company_id, user_role):
    try:
        if user_role == 'super_admin':
            expense_types = ExpenseType.query.all()
        else:
            expense_types = ExpenseType.query.filter_by(company_id=company_id).all()

        result = []
        for expense_type in expense_types:
            result.append({
                'id': str(expense_type.id),
                'name': expense_type.name,
                'description': expense_type.description,
                'is_active': expense_type.is_active,
                'created_at': expense_type.created_at.isoformat() if expense_type.created_at else None,
            })
        return result
    except Exception as e:
        logger.error(f"Error getting expense types: {str(e)}")
        raise ExpenseTypeError("Failed to retrieve expense types")

def add_expense_type(data, user_role, current_user_id, ip_address, user_agent):
    try:
        if 'name' not in data:
            raise ValueError("Missing required field: name")

        new_expense_type = ExpenseType(
            company_id=uuid.UUID(data['company_id']),
            name=data['name'],
            description=data.get('description'),
            is_active=data.get('is_active', True)
        )

        db.session.add(new_expense_type)
        db.session.commit()
        return new_expense_type
    except Exception as e:
        logger.error(f"Error adding expense type: {str(e)}")
        db.session.rollback()
        raise ExpenseTypeError("Failed to create expense type")

def delete_expense_type(id, company_id, user_role, current_user_id, ip_address, user_agent):
    try:
        if user_role == 'super_admin':
            expense_type = ExpenseType.query.get(id)
        else:
            expense_type = ExpenseType.query.filter_by(id=id, company_id=company_id).first()

        if not expense_type:
            raise ValueError(f"Expense type with id {id} not found")

        # Check if expense type is being used
        from app.models import Expense
        expense_count = Expense.query.filter_by(expense_type_id=id).count()
        if expense_count > 0:
            raise ValueError("Cannot delete expense type that is being used by expenses")

        db.session.delete(expense_type)
        db.session.commit()
        return True
    except Exception as e:
        logger.error(f"Error deleting expense type {id}: {str(e)}")
        db.session.rollback()
        raise ExpenseTypeError("Failed to delete expense type")