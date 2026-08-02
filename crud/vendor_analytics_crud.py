"""
Vendor Analytics CRUD
Allows parent companies to view aggregated stats of their vendor sub-companies.
Security: Every query verifies parent_company_id relationship before returning data.
"""

from app import db
from app.models import (
    Company, Vendor, Customer, Invoice, Payment, Complaint,
    Expense, ExtraIncome, ISPPayment, User, ServicePlan, CustomerPackage
)
from sqlalchemy import func, case, and_
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging

logger = logging.getLogger(__name__)


def _verify_parent_access(parent_company_id, vendor_company_id):
    """
    Security check: verify the vendor company belongs to the requesting parent company.
    Raises PermissionError if the relationship does not exist.
    """
    vendor = Vendor.query.filter_by(
        company_id=parent_company_id,
        vendor_company_id=vendor_company_id,
        is_active=True
    ).first()
    if not vendor:
        raise PermissionError("Access denied: vendor does not belong to this company")
    return vendor


def get_vendor_overview(parent_company_id, vendor_company_id):
    """
    Get comprehensive overview stats for a single vendor company.
    Returns customer, revenue, invoice, expense, profitability, support, and staff metrics.
    """
    _verify_parent_access(parent_company_id, vendor_company_id)
    vc = vendor_company_id
    
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = month_start - relativedelta(months=1)
    
    try:
        # --- CUSTOMER METRICS ---
        total_customers = Customer.query.filter_by(company_id=vc).count()
        active_customers = Customer.query.filter_by(company_id=vc, is_active=True).count()
        inactive_customers = total_customers - active_customers
        
        new_customers_this_month = Customer.query.filter(
            Customer.company_id == vc,
            Customer.created_at >= month_start
        ).count()
        
        # --- INVOICE / REVENUE METRICS ---
        total_revenue = db.session.query(func.sum(Payment.amount)).filter(
            Payment.company_id == vc, Payment.is_active == True
        ).scalar() or 0
        
        monthly_revenue = db.session.query(func.sum(Payment.amount)).filter(
            Payment.company_id == vc,
            Payment.payment_date >= month_start,
            Payment.is_active == True
        ).scalar() or 0
        
        prev_monthly_revenue = db.session.query(func.sum(Payment.amount)).filter(
            Payment.company_id == vc,
            Payment.payment_date >= prev_month_start,
            Payment.payment_date < month_start,
            Payment.is_active == True
        ).scalar() or 0
        
        pending_invoices = Invoice.query.filter_by(
            company_id=vc, status='pending', is_active=True
        ).count()
        
        pending_amount = db.session.query(func.sum(Invoice.total_amount)).filter(
            Invoice.company_id == vc, Invoice.status == 'pending', Invoice.is_active == True
        ).scalar() or 0
        
        overdue_invoices = Invoice.query.filter(
            Invoice.company_id == vc,
            Invoice.status == 'pending',
            Invoice.due_date < now.date(),
            Invoice.is_active == True
        ).count()
        
        paid_invoices = Invoice.query.filter_by(
            company_id=vc, status='paid', is_active=True
        ).count()
        
        total_invoiced = db.session.query(func.sum(Invoice.total_amount)).filter(
            Invoice.company_id == vc, Invoice.is_active == True
        ).scalar() or 0
        
        # --- EXPENSE METRICS ---
        total_expenses = db.session.query(func.sum(Expense.amount)).filter(
            Expense.company_id == vc, Expense.is_active == True
        ).scalar() or 0
        
        monthly_expenses = db.session.query(func.sum(Expense.amount)).filter(
            Expense.company_id == vc,
            Expense.expense_date >= month_start,
            Expense.is_active == True
        ).scalar() or 0
        
        # --- ISP COSTS ---
        monthly_isp_costs = db.session.query(func.sum(ISPPayment.amount)).filter(
            ISPPayment.company_id == vc,
            ISPPayment.payment_date >= month_start,
            ISPPayment.is_active == True
        ).scalar() or 0
        
        # --- EXTRA INCOME ---
        monthly_extra_income = db.session.query(func.sum(ExtraIncome.amount)).filter(
            ExtraIncome.company_id == vc,
            ExtraIncome.income_date >= month_start,
            ExtraIncome.is_active == True
        ).scalar() or 0
        
        # --- COMPLAINT METRICS ---
        open_complaints = Complaint.query.join(Customer).filter(
            Customer.company_id == vc,
            Complaint.status.in_(['open', 'in_progress']),
            Complaint.is_active == True
        ).count()
        
        resolved_complaints_this_month = Complaint.query.join(Customer).filter(
            Customer.company_id == vc,
            Complaint.status == 'resolved',
            Complaint.resolved_at >= month_start
        ).count()
        
        # --- EMPLOYEE METRICS ---
        total_employees = User.query.filter_by(company_id=vc, is_active=True).count()
        
        # --- PROFIT CALCULATION ---
        net_profit_monthly = float(monthly_revenue) + float(monthly_extra_income) - float(monthly_expenses) - float(monthly_isp_costs)
        
        # --- COLLECTION RATE ---
        collection_rate = (float(total_revenue) / float(total_invoiced) * 100) if float(total_invoiced) > 0 else 0
        
        # --- REVENUE GROWTH ---
        revenue_growth = 0
        if float(prev_monthly_revenue) > 0:
            revenue_growth = round(((float(monthly_revenue) - float(prev_monthly_revenue)) / float(prev_monthly_revenue) * 100), 1)
        
        # --- PROFIT MARGIN ---
        profit_margin = 0
        if float(monthly_revenue) > 0:
            profit_margin = round((net_profit_monthly / float(monthly_revenue) * 100), 1)
        
        return {
            'customer_metrics': {
                'total_customers': total_customers,
                'active_customers': active_customers,
                'inactive_customers': inactive_customers,
                'new_this_month': new_customers_this_month,
            },
            'revenue_metrics': {
                'total_revenue': float(total_revenue),
                'monthly_revenue': float(monthly_revenue),
                'prev_monthly_revenue': float(prev_monthly_revenue),
                'revenue_growth': revenue_growth,
                'monthly_extra_income': float(monthly_extra_income),
            },
            'invoice_metrics': {
                'pending_invoices': pending_invoices,
                'pending_amount': float(pending_amount),
                'overdue_invoices': overdue_invoices,
                'paid_invoices': paid_invoices,
                'collection_rate': round(collection_rate, 1),
            },
            'expense_metrics': {
                'total_expenses': float(total_expenses),
                'monthly_expenses': float(monthly_expenses),
                'monthly_isp_costs': float(monthly_isp_costs),
            },
            'profitability': {
                'net_profit_monthly': round(net_profit_monthly, 2),
                'profit_margin': profit_margin,
            },
            'support_metrics': {
                'open_complaints': open_complaints,
                'resolved_this_month': resolved_complaints_this_month,
            },
            'staff_metrics': {
                'total_employees': total_employees,
            }
        }
    except PermissionError:
        raise
    except Exception as e:
        logger.error(f"Error getting vendor overview for {vendor_company_id}: {str(e)}")
        raise


def get_vendor_revenue_trend(parent_company_id, vendor_company_id, months=6):
    """Get monthly revenue, expenses, and profit trend for a vendor company (last N months)"""
    _verify_parent_access(parent_company_id, vendor_company_id)
    
    now = datetime.utcnow()
    result = []
    
    try:
        for i in range(months - 1, -1, -1):
            m_start = (now - relativedelta(months=i)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            m_end = m_start + relativedelta(months=1)
            
            revenue = db.session.query(func.sum(Payment.amount)).filter(
                Payment.company_id == vendor_company_id,
                Payment.payment_date >= m_start,
                Payment.payment_date < m_end,
                Payment.is_active == True
            ).scalar() or 0
            
            expenses = db.session.query(func.sum(Expense.amount)).filter(
                Expense.company_id == vendor_company_id,
                Expense.expense_date >= m_start,
                Expense.expense_date < m_end,
                Expense.is_active == True
            ).scalar() or 0
            
            isp_costs = db.session.query(func.sum(ISPPayment.amount)).filter(
                ISPPayment.company_id == vendor_company_id,
                ISPPayment.payment_date >= m_start,
                ISPPayment.payment_date < m_end,
                ISPPayment.is_active == True
            ).scalar() or 0
            
            total_expenses = float(expenses) + float(isp_costs)
            
            result.append({
                'month': m_start.strftime('%b %Y'),
                'revenue': float(revenue),
                'expenses': total_expenses,
                'profit': float(revenue) - total_expenses,
            })
        
        return result
    except PermissionError:
        raise
    except Exception as e:
        logger.error(f"Error getting vendor revenue trend: {str(e)}")
        raise


def get_vendor_customer_growth(parent_company_id, vendor_company_id, months=6):
    """Get monthly cumulative customer growth trend for a vendor company"""
    _verify_parent_access(parent_company_id, vendor_company_id)
    
    now = datetime.utcnow()
    result = []
    
    try:
        for i in range(months - 1, -1, -1):
            m_end = (now - relativedelta(months=i)).replace(day=1) + relativedelta(months=1) - timedelta(days=1)
            
            total = Customer.query.filter(
                Customer.company_id == vendor_company_id,
                Customer.created_at <= m_end
            ).count()
            
            active = Customer.query.filter(
                Customer.company_id == vendor_company_id,
                Customer.created_at <= m_end,
                Customer.is_active == True
            ).count()
            
            result.append({
                'month': m_end.strftime('%b %Y'),
                'total_customers': total,
                'active_customers': active,
            })
        
        return result
    except PermissionError:
        raise
    except Exception as e:
        logger.error(f"Error getting vendor customer growth: {str(e)}")
        raise


def get_all_vendors_summary(parent_company_id):
    """
    Get summary stats for ALL vendors of a parent company.
    Used for the vendor list view — shows key KPIs per vendor at a glance.
    """
    vendors = Vendor.query.filter_by(company_id=parent_company_id, is_active=True).all()
    
    result = []
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    for v in vendors:
        vendor_data = {
            'id': str(v.id),
            'name': v.name,
            'phone': v.phone,
            'email': v.email,
            'cnic': v.cnic,
            'picture': v.picture,
            'vendor_company_id': str(v.vendor_company_id) if v.vendor_company_id else None,
            'is_provisioned': v.vendor_company_id is not None,
            'is_active': v.is_active,
            'created_at': v.created_at.isoformat() if v.created_at else None,
        }
        
        if not v.vendor_company_id:
            # Legacy vendor without a provisioned company
            vendor_data['stats'] = None
            result.append(vendor_data)
            continue
        
        try:
            vc = v.vendor_company_id
            
            active_customers = Customer.query.filter_by(company_id=vc, is_active=True).count()
            total_customers = Customer.query.filter_by(company_id=vc).count()
            
            monthly_revenue = db.session.query(func.sum(Payment.amount)).filter(
                Payment.company_id == vc,
                Payment.payment_date >= month_start,
                Payment.is_active == True
            ).scalar() or 0
            
            pending_invoices = Invoice.query.filter_by(
                company_id=vc, status='pending', is_active=True
            ).count()
            
            pending_amount = db.session.query(func.sum(Invoice.total_amount)).filter(
                Invoice.company_id == vc, Invoice.status == 'pending', Invoice.is_active == True
            ).scalar() or 0
            
            overdue_invoices = Invoice.query.filter(
                Invoice.company_id == vc,
                Invoice.status == 'pending',
                Invoice.due_date < now.date(),
                Invoice.is_active == True
            ).count()
            
            open_complaints = Complaint.query.join(Customer).filter(
                Customer.company_id == vc,
                Complaint.status.in_(['open', 'in_progress'])
            ).count()
            
            monthly_expenses = db.session.query(func.sum(Expense.amount)).filter(
                Expense.company_id == vc,
                Expense.expense_date >= month_start,
                Expense.is_active == True
            ).scalar() or 0
            
            monthly_isp_costs = db.session.query(func.sum(ISPPayment.amount)).filter(
                ISPPayment.company_id == vc,
                ISPPayment.payment_date >= month_start,
                ISPPayment.is_active == True
            ).scalar() or 0
            
            net_profit = float(monthly_revenue) - float(monthly_expenses) - float(monthly_isp_costs)
            
            total_employees = User.query.filter_by(company_id=vc, is_active=True).count()
            
            vendor_data['stats'] = {
                'total_customers': total_customers,
                'active_customers': active_customers,
                'monthly_revenue': float(monthly_revenue),
                'pending_invoices': pending_invoices,
                'pending_amount': float(pending_amount),
                'overdue_invoices': overdue_invoices,
                'open_complaints': open_complaints,
                'monthly_expenses': float(monthly_expenses) + float(monthly_isp_costs),
                'net_profit': round(net_profit, 2),
                'total_employees': total_employees,
            }
        except Exception as e:
            logger.error(f"Error fetching stats for vendor {v.id}: {str(e)}")
            vendor_data['stats'] = None
        
        result.append(vendor_data)
    
    return result
