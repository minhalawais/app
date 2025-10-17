from app import db
from app.models import ExtraIncome, ExtraIncomeType
import uuid
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class ExtraIncomeError(Exception):
    pass

class ExtraIncomeTypeError(Exception):
    pass

def get_all_extra_incomes(company_id, user_role):
    try:
        if user_role == 'super_admin':
            incomes = ExtraIncome.query.join(ExtraIncomeType).all()
        elif user_role == 'auditor':
            incomes = ExtraIncome.query.join(ExtraIncomeType).filter(
                ExtraIncome.is_active==True, 
                ExtraIncome.company_id==company_id
            ).all()
        elif user_role == 'company_owner':
            incomes = ExtraIncome.query.join(ExtraIncomeType).filter(
                ExtraIncome.company_id==company_id
            ).all()
        elif user_role == 'employee':
            incomes = ExtraIncome.query.join(ExtraIncomeType).filter(
                ExtraIncome.company_id==company_id, 
                ExtraIncome.is_active==True
            ).all()

        result = []
        for income in incomes:
            result.append({
                'id': str(income.id),
                'income_type_id': str(income.income_type_id),
                'income_type_name': income.income_type.name,
                'description': income.description,
                'amount': float(income.amount),
                'income_date': income.income_date.isoformat(),
                'payment_method': income.payment_method,
                'payer': income.payer,
                'bank_account_id': str(income.bank_account_id) if income.bank_account_id else None,
                'is_active': income.is_active,
                'created_at': income.created_at.isoformat() if income.created_at else None,
            })
        return result
    except Exception as e:
        logger.error(f"Error getting extra incomes: {str(e)}")
        raise ExtraIncomeError("Failed to retrieve extra incomes")

def add_extra_income(data, user_role, current_user_id, ip_address, user_agent):
    try:
        required_fields = ['income_type_id', 'amount', 'income_date']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        new_income = ExtraIncome(
            company_id=uuid.UUID(data['company_id']),
            income_type_id=uuid.UUID(data['income_type_id']),
            description=data.get('description'),
            amount=Decimal(str(data['amount'])),
            income_date=data['income_date'],
            payment_method=data.get('payment_method'),
            payer=data.get('payer'),
            bank_account_id=uuid.UUID(data['bank_account_id']) if data.get('bank_account_id') else None,
            is_active=data.get('is_active', True)
        )

        db.session.add(new_income)
        db.session.commit()
        return new_income
    except Exception as e:
        logger.error(f"Error adding extra income: {str(e)}")
        db.session.rollback()
        raise ExtraIncomeError("Failed to create extra income")

def update_extra_income(id, data, company_id, user_role, current_user_id, ip_address, user_agent):
    try:
        if user_role == 'super_admin':
            income = ExtraIncome.query.get(id)
        else:
            income = ExtraIncome.query.filter_by(id=id, company_id=company_id).first()

        if not income:
            raise ValueError(f"Extra income with id {id} not found")

        # Update fields
        updatable_fields = ['income_type_id', 'description', 'amount', 'income_date', 'payment_method', 'payer', 'bank_account_id', 'is_active']
        for field in updatable_fields:
            if field in data:
                if field == 'amount':
                    setattr(income, field, Decimal(str(data[field])))
                elif field in ['income_type_id', 'bank_account_id']:
                    setattr(income, field, uuid.UUID(data[field]) if data[field] else None)
                else:
                    setattr(income, field, data[field])

        db.session.commit()
        return income
    except Exception as e:
        logger.error(f"Error updating extra income {id}: {str(e)}")
        db.session.rollback()
        raise ExtraIncomeError("Failed to update extra income")

def delete_extra_income(id, company_id, user_role, current_user_id, ip_address, user_agent):
    try:
        if user_role == 'super_admin':
            income = ExtraIncome.query.get(id)
        else:
            income = ExtraIncome.query.filter_by(id=id, company_id=company_id).first()

        if not income:
            raise ValueError(f"Extra income with id {id} not found")

        # Actually delete the record
        db.session.delete(income)
        db.session.commit()
        return True
    except Exception as e:
        logger.error(f"Error deleting extra income {id}: {str(e)}")
        db.session.rollback()
        raise ExtraIncomeError("Failed to delete extra income")

def get_all_extra_income_types(company_id, user_role):
    try:
        if user_role == 'super_admin':
            income_types = ExtraIncomeType.query.all()
        else:
            income_types = ExtraIncomeType.query.filter_by(company_id=company_id).all()

        result = []
        for income_type in income_types:
            result.append({
                'id': str(income_type.id),
                'name': income_type.name,
                'description': income_type.description,
                'is_active': income_type.is_active,
                'created_at': income_type.created_at.isoformat() if income_type.created_at else None,
            })
        return result
    except Exception as e:
        logger.error(f"Error getting extra income types: {str(e)}")
        raise ExtraIncomeTypeError("Failed to retrieve extra income types")

def add_extra_income_type(data, user_role, current_user_id, ip_address, user_agent):
    try:
        if 'name' not in data:
            raise ValueError("Missing required field: name")

        new_income_type = ExtraIncomeType(
            company_id=uuid.UUID(data['company_id']),
            name=data['name'],
            description=data.get('description'),
            is_active=data.get('is_active', True)
        )

        db.session.add(new_income_type)
        db.session.commit()
        return new_income_type
    except Exception as e:
        logger.error(f"Error adding extra income type: {str(e)}")
        db.session.rollback()
        raise ExtraIncomeTypeError("Failed to create extra income type")

def update_extra_income_type(id, data, company_id, user_role, current_user_id, ip_address, user_agent):
    try:
        if user_role == 'super_admin':
            income_type = ExtraIncomeType.query.get(id)
        else:
            income_type = ExtraIncomeType.query.filter_by(id=id, company_id=company_id).first()

        if not income_type:
            raise ValueError(f"Extra income type with id {id} not found")

        # Update fields
        if 'name' in data:
            income_type.name = data['name']
        if 'description' in data:
            income_type.description = data['description']
        if 'is_active' in data:
            income_type.is_active = data['is_active']

        db.session.commit()
        return income_type
    except Exception as e:
        logger.error(f"Error updating extra income type {id}: {str(e)}")
        db.session.rollback()
        raise ExtraIncomeTypeError("Failed to update extra income type")

def delete_extra_income_type(id, company_id, user_role, current_user_id, ip_address, user_agent):
    try:
        if user_role == 'super_admin':
            income_type = ExtraIncomeType.query.get(id)
        else:
            income_type = ExtraIncomeType.query.filter_by(id=id, company_id=company_id).first()

        if not income_type:
            raise ValueError(f"Extra income type with id {id} not found")

        # Check if income type is being used
        income_count = ExtraIncome.query.filter_by(income_type_id=id).count()
        if income_count > 0:
            raise ValueError("Cannot delete income type that is being used by extra incomes")

        db.session.delete(income_type)
        db.session.commit()
        return True
    except Exception as e:
        logger.error(f"Error deleting extra income type {id}: {str(e)}")
        db.session.rollback()
        raise ExtraIncomeTypeError("Failed to delete extra income type")